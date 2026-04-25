#!/usr/bin/env python3
"""Import wizard-completed activities from a user-edited UiPath project.

For wizard-launched activities (chart insert, table extraction, event recorder,
form/task designer, etc.), `uip rpa get-default-activity-xaml` returns Failure
because there's no fixed default template — Studio configures them during the
wizard interaction. This script lets the user complete the wizards manually in
Studio, then lifts each captured activity out of the project's .xaml files,
strips noisy session-state attributes, and writes a clean per-activity snippet
into the harvest corpus alongside the headless-harvested activities.

Also performs a `--demote-not-available` pass that marks intervention-list
activities Studio explicitly reports as "not available in the installed
package" with `status: wizard_unavailable` and a substitute hint.

Usage:
    python import_wizard_xaml.py --project-dir <path-to-Studio-project>
    python import_wizard_xaml.py --project-dir <path> --dry-run
    python import_wizard_xaml.py --project-dir <path> --no-demote
"""

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

try:
    from defusedxml.ElementTree import fromstring as _safe_fromstring
except ImportError:
    _safe_fromstring = ET.fromstring

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GROUND_TRUTH_DIR = REPO_ROOT / "uipath-core" / "references" / "studio-ground-truth"

# Matching table — maps an XML element local name to (intervention_key, package, version).
# Multiple intervention keys can map to the same XML element only if they go to
# different packages (none of our cases need that today).
DEFAULT_MATCHES: list[dict] = [
    # UIAutomation 25.10 — Main.xaml in this project
    {"key": "ApplicationEventTrigger", "elem": "NNativeEventTrigger",
     "pkg": "UiPath.UIAutomation.Activities", "ver": "25.10"},
    {"key": "GetAttribute",            "elem": "NGetAttributeGeneric",
     "pkg": "UiPath.UIAutomation.Activities", "ver": "25.10"},
    {"key": "NExtractFormDataGeneric", "elem": "NExtractFormDataGeneric",
     "pkg": "UiPath.UIAutomation.Activities", "ver": "25.10"},
    {"key": "NExtractDataGeneric",     "elem": "NExtractDataGeneric",
     "pkg": "UiPath.UIAutomation.Activities", "ver": "25.10"},
    # Persistence 1.4 — UserAction (upau) namespace, ActivityShowcase.xaml + Main.xaml
    {"key": "GetAppTasks",                 "elem": "GetAppTasks",
     "pkg": "UiPath.Persistence.Activities", "ver": "1.4"},
    {"key": "WaitForUserActionAndResume",  "elem": "WaitForUserActionAndResume",
     "pkg": "UiPath.Persistence.Activities", "ver": "1.4"},
    # Persistence 1.4 — FormTask (upaf) and ExternalTask (upae), Main.xaml form designer
    {"key": "CreateFormTask",                "elem": "CreateFormTask",
     "pkg": "UiPath.Persistence.Activities", "ver": "1.4"},
    {"key": "WaitForFormTaskAndResume",      "elem": "WaitForFormTaskAndResume",
     "pkg": "UiPath.Persistence.Activities", "ver": "1.4"},
    {"key": "CreateExternalTask",            "elem": "CreateExternalTask",
     "pkg": "UiPath.Persistence.Activities", "ver": "1.4"},
    {"key": "WaitForExternalTaskAndResume",  "elem": "WaitForExternalTaskAndResume",
     "pkg": "UiPath.Persistence.Activities", "ver": "1.4"},
    {"key": "GetFormTasks",                  "elem": "GetFormTasks",
     "pkg": "UiPath.Persistence.Activities", "ver": "1.4"},
]

# Demotion table — activities Studio flagged as "not in installed package".
DEMOTE_NOT_AVAILABLE: list[dict] = [
    {"key": "ExtractUIData",       "pkg": "UiPath.UIAutomation.Activities", "ver": "25.10",
     "substitute": "NUITask"},
    {"key": "NAccessibilityCheck", "pkg": "UiPath.UIAutomation.Activities", "ver": "25.10",
     "substitute": "NUITask"},
    {"key": "ChangeDataRangeModification", "pkg": "UiPath.Excel.Activities", "ver": "3.4",
     "substitute": "WriteRange"},
    {"key": "InsertChart", "pkg": "UiPath.Excel.Activities", "ver": "3.4",
     "substitute": "CreatePivotTable"},
    {"key": "UpdateChart", "pkg": "UiPath.Excel.Activities", "ver": "3.4",
     "substitute": "CreatePivotTable"},
]

# Attribute localname *suffixes* to remove from the captured activity. We
# match on suffix because Studio attaches presentation attrs via attached
# properties whose localname is `Container.HintSize` or `WorkflowViewState.IdRef`
# — splitting on `}` keeps the whole `Foo.Bar` string. Order doesn't matter.
_STRIP_ATTR_SUFFIXES = (
    "HintSize", "IdRef", "IconBase64", "InformativeScreenshot",
    "Reference", "Guid", "ContentHash", "TriggerId", "ScopeGuid",
    "ScopeIdentifier", "BrowserURL", "Url", "FullSelectorArgument",
    "FuzzySelectorArgument", "ScopeSelectorArgument", "Selector",
    "DesignTimeRectangle", "Area",
)


def _should_strip_attr(local: str) -> bool:
    return any(local == s or local.endswith("." + s) for s in _STRIP_ATTR_SUFFIXES)

# Attribute localnames whose values are large XML blobs — replace with placeholder.
_PLACEHOLDER_ATTRS = frozenset({"ExtractDataSettings", "ExtractMetadata", "TableInfo"})

# Element localnames to drop entirely (presentation noise).
_STRIP_ELEMENTS = frozenset({"ViewState", "WorkflowViewStateService.ViewState"})

# Quoted instance suffix in DisplayName, e.g. "Get Attribute 'foo'" -> "Get Attribute"
_DISPLAY_NAME_SUFFIX = re.compile(r"\s+'.*'\s*$")

# Common Studio xmlns block — wraps cleaned snippets so they parse standalone
# (mirrors the format produced by harvest_studio_xaml.py).
_OUTER_XMLNS = (
    'xmlns="http://schemas.microsoft.com/netfx/2009/xaml/activities" '
    'xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml" '
    'xmlns:ui="http://schemas.uipath.com/workflow/activities" '
    'xmlns:uix="http://schemas.uipath.com/workflow/activities/uix" '
    'xmlns:upau="clr-namespace:UiPath.Persistence.Activities.UserAction;'
    'assembly=UiPath.Persistence.Activities" '
    'xmlns:upaf="clr-namespace:UiPath.Persistence.Activities.FormTask;'
    'assembly=UiPath.Persistence.Activities" '
    'xmlns:upae="clr-namespace:UiPath.Persistence.Activities.ExternalTask;'
    'assembly=UiPath.Persistence.Activities" '
    'xmlns:upat="clr-namespace:UiPath.Persistence.Activities.Tasks;'
    'assembly=UiPath.Persistence.Activities" '
    'xmlns:uuat="clr-namespace:UiPath.UIAutomationNext.Activities.Triggers;'
    'assembly=UiPath.UIAutomationNext.Activities" '
    'xmlns:uuadsfb="clr-namespace:UiPath.UIAutomationNext.Activities.Design.SWEntities.fd1135674040.Bundle;'
    'assembly=fd1135674040.qPNHG3TSMPM1ZMTPy3t2VOM1" '
    'xmlns:scg="clr-namespace:System.Collections.Generic;assembly=System.Private.CoreLib" '
    'xmlns:s="clr-namespace:System;assembly=System.Private.CoreLib" '
    'xmlns:sd2="clr-namespace:System.Data;assembly=System.Data.Common"'
)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _ns_uri(tag: str) -> str:
    if tag.startswith("{"):
        return tag[1:].split("}", 1)[0]
    return ""


def _strip_attr_local(name: str) -> str:
    return name.rsplit("}", 1)[-1] if "}" in name else name


def _clean_element(el: ET.Element, depth: int = 0) -> ET.Element:
    """Return a cleaned copy of *el* with noise stripped (recursive)."""
    new = ET.Element(el.tag, {})
    for attr_name, attr_value in el.attrib.items():
        local = _strip_attr_local(attr_name)
        if _should_strip_attr(local):
            continue
        if local in _PLACEHOLDER_ATTRS:
            new.attrib[attr_name] = "{x:Null}"
            continue
        if local == "DisplayName":
            new.attrib[attr_name] = _DISPLAY_NAME_SUFFIX.sub("", attr_value)
            continue
        new.attrib[attr_name] = attr_value
    if el.text and el.text.strip():
        new.text = el.text
    for child in el:
        if _local(child.tag) in _STRIP_ELEMENTS:
            continue
        new.append(_clean_element(child, depth + 1))
    if el.tail and el.tail.strip():
        new.tail = el.tail
    return new


def _serialize(el: ET.Element, prefix_map: dict[str, str]) -> str:
    """Serialize cleaned element with original ns prefixes (not ns0/ns1/...)."""
    # Re-register short prefixes for known UiPath namespaces
    for prefix, uri in prefix_map.items():
        ET.register_namespace(prefix, uri)
    raw = ET.tostring(el, encoding="unicode")
    # ElementTree always adds xmlns declarations on the root we're serializing;
    # they'll be re-introduced by the outer wrapper. Strip them from the root.
    raw = re.sub(r'\s+xmlns(?::\w+)?="[^"]*"', '', raw, count=20)
    return raw


def _wrap(snippet: str, x_class: str = "Imported") -> str:
    """Wrap a cleaned snippet in the standard <Activity ...> outer wrapper."""
    return f'<Activity x:Class="{x_class}" {_OUTER_XMLNS}>\n  {snippet}\n</Activity>\n'


def _build_prefix_map(root: ET.Element) -> dict[str, str]:
    """Walk a full source XAML tree and harvest prefix→uri pairs.

    ElementTree doesn't expose declared prefixes on the parsed tree. We can
    still infer them from the tag URIs we see, plus a small known-mapping
    table for the UiPath ones.
    """
    seen_uris: set[str] = set()
    for el in root.iter():
        seen_uris.add(_ns_uri(el.tag))
        for attr_name in el.attrib:
            if "}" in attr_name:
                seen_uris.add(_ns_uri(attr_name))
    known = {
        "http://schemas.microsoft.com/netfx/2009/xaml/activities": "",
        "http://schemas.microsoft.com/winfx/2006/xaml": "x",
        "http://schemas.uipath.com/workflow/activities": "ui",
        "http://schemas.uipath.com/workflow/activities/uix": "uix",
    }
    out = {}
    for uri in seen_uris:
        if uri in known:
            out[known[uri]] = uri
        elif uri.startswith("clr-namespace:UiPath.Persistence.Activities.UserAction"):
            out["upau"] = uri
        elif uri.startswith("clr-namespace:UiPath.Persistence.Activities.FormTask"):
            out["upaf"] = uri
        elif uri.startswith("clr-namespace:UiPath.Persistence.Activities.ExternalTask"):
            out["upae"] = uri
        elif uri.startswith("clr-namespace:UiPath.Persistence.Activities.Tasks"):
            out["upat"] = uri
        elif uri.startswith("clr-namespace:UiPath.UIAutomationNext.Activities.Triggers"):
            out["uuat"] = uri
        elif uri.startswith("clr-namespace:UiPath.UIAutomationNext.Activities.Design.SWEntities"):
            out["uuadsfb"] = uri
        elif uri.startswith("clr-namespace:System.Collections.Generic"):
            out["scg"] = uri
        elif uri.startswith("clr-namespace:System;"):
            out["s"] = uri
        elif uri.startswith("clr-namespace:System.Data;"):
            out["sd2"] = uri
    return out


def _find_match(
    el: ET.Element, matches_by_elem: dict[str, dict]
) -> dict | None:
    return matches_by_elem.get(_local(el.tag))


def _ensure_index(pkg: str, ver: str) -> tuple[Path, dict]:
    out_dir = GROUND_TRUTH_DIR / pkg / ver
    idx_path = out_dir / "index.json"
    if idx_path.exists():
        idx = json.loads(idx_path.read_text(encoding="utf-8"))
    else:
        idx = {
            "package": pkg,
            "version": ver,
            "concrete_version": None,
            "harvested_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "activities": {},
        }
    return idx_path, idx


def _process_xaml(
    xaml_path: Path,
    matches_by_elem: dict[str, dict],
    dry_run: bool,
) -> list[tuple[dict, str]]:
    """Return list of (match_row, written_file_basename) for each capture."""
    raw = xaml_path.read_text(encoding="utf-8")
    try:
        root = _safe_fromstring(raw)
    except ET.ParseError as e:
        print(f"  ERROR parsing {xaml_path}: {e}", file=sys.stderr)
        return []
    prefix_map = _build_prefix_map(root)

    captures: list[tuple[dict, ET.Element]] = []
    for el in root.iter():
        match = _find_match(el, matches_by_elem)
        if match:
            captures.append((match, el))

    written: list[tuple[dict, str]] = []
    ground_truth_resolved = GROUND_TRUTH_DIR.resolve()
    for match, el in captures:
        cleaned = _clean_element(deepcopy(el))
        snippet = _serialize(cleaned, prefix_map)
        wrapped = _wrap(snippet, x_class=match["key"])
        out_dir = GROUND_TRUTH_DIR / match["pkg"] / match["ver"]
        out_path = out_dir / f"{match['key']}.xaml"
        # Path-traversal jail guard — mirrors harvest_studio_xaml.py:471-474.
        # match["pkg"]/match["ver"] come from a hardcoded table today, but
        # defense-in-depth: refuse to write outside GROUND_TRUTH_DIR.
        out_path_resolved = out_path.resolve()
        if not out_path_resolved.is_relative_to(ground_truth_resolved):
            raise ValueError(
                f"Refusing to write outside ground-truth dir: {out_path_resolved}"
            )
        size = len(wrapped.encode("utf-8"))
        if dry_run:
            print(f"  [DRY-RUN] would write {out_path} ({size:,} bytes)")
        else:
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path.write_text(wrapped, encoding="utf-8")
            print(f"  wrote {out_path} ({size:,} bytes)")
        written.append((match, out_path.name))

    return written


def _update_index_for_ok(
    pkg: str, ver: str,
    captures: list[dict],
    source_files: dict[str, str],  # key -> source file basename
    dry_run: bool,
) -> int:
    if not captures:
        return 0
    idx_path, idx = _ensure_index(pkg, ver)
    n_changed = 0
    for cap in captures:
        key = cap["key"]
        elem = cap["elem"]
        out_path = GROUND_TRUTH_DIR / pkg / ver / f"{key}.xaml"
        size = out_path.stat().st_size if out_path.exists() and not dry_run else 0
        # Class name is best-effort: we don't know the full CLR class from the
        # element alone. Use what was already in index, or fall back to
        # <last clr_namespace>.<elem> derived from existing peer entries.
        existing = (idx.get("activities") or {}).get(key, {})
        class_name = existing.get("class_name")
        if not class_name and elem != key:
            # Persistence keys equal element names; UIAutomation keys differ.
            # Try to infer from a sibling that uses the same xmlns prefix.
            for sib_key, sib_meta in (idx.get("activities") or {}).items():
                sib_class = (sib_meta or {}).get("class_name") or ""
                if "." in sib_class and sib_meta.get("namespace_prefix") in ("uix", "upau"):
                    class_name = sib_class.rsplit(".", 1)[0] + "." + elem
                    break
        idx.setdefault("activities", {})[key] = {
            "status": "ok",
            "class_name": class_name,
            "size": size,
            "harvest_method": "studio_wizard_manual_user_provided",
            "source_file": source_files.get(key, "?"),
        }
        n_changed += 1
    if not dry_run and n_changed:
        idx_path.parent.mkdir(parents=True, exist_ok=True)
        idx_path.write_text(json.dumps(idx, indent=2), encoding="utf-8")
        print(f"  updated {idx_path} (+{n_changed} ok entries)")
    return n_changed


def _demote_not_available(dry_run: bool) -> int:
    by_pair: dict[tuple[str, str], list[dict]] = {}
    for row in DEMOTE_NOT_AVAILABLE:
        by_pair.setdefault((row["pkg"], row["ver"]), []).append(row)
    total = 0
    for (pkg, ver), rows in by_pair.items():
        idx_path, idx = _ensure_index(pkg, ver)
        n_changed = 0
        for row in rows:
            key = row["key"]
            existing = (idx.get("activities") or {}).get(key, {})
            entry = {
                "status": "wizard_unavailable",
                "note": (
                    f"not present in installed {pkg}@{ver}; "
                    f"Studio substituted {row['substitute']}"
                ),
                "class_name": existing.get("class_name"),
                "harvest_method": "studio_wizard_unavailable",
            }
            if dry_run:
                print(f"  [DRY-RUN] would demote {pkg}@{ver} {key} -> wizard_unavailable "
                      f"(sub: {row['substitute']})")
            else:
                idx.setdefault("activities", {})[key] = entry
            n_changed += 1
        if not dry_run and n_changed:
            idx_path.write_text(json.dumps(idx, indent=2), encoding="utf-8")
            print(f"  demoted {n_changed} entry(ies) in {idx_path}")
        total += n_changed
    return total


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--project-dir", required=True,
                        help="Studio project root containing the user-edited .xaml files")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would change; write nothing")
    parser.add_argument("--no-demote", action="store_true",
                        help="Skip the demote-not-available pass")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    if not project_dir.is_dir():
        parser.error(f"--project-dir does not exist or is not a directory: {project_dir}")

    matches_by_elem = {row["elem"]: row for row in DEFAULT_MATCHES}

    print(f"import_wizard_xaml — project={project_dir}, dry_run={args.dry_run}, "
          f"demote={not args.no_demote}")
    print()

    # Scan all .xaml files (skip Studio lock files starting with ~)
    xaml_files = sorted(
        p for p in project_dir.rglob("*.xaml")
        if not p.name.startswith("~")
    )
    print(f"Scanning {len(xaml_files)} XAML file(s):")

    all_captures: dict[tuple[str, str], list[dict]] = {}  # (pkg,ver) -> list of match rows
    source_files: dict[tuple[str, str, str], str] = {}    # (pkg,ver,key) -> source basename

    for xaml_path in xaml_files:
        print(f"\n  {xaml_path.name}:")
        written = _process_xaml(xaml_path, matches_by_elem, args.dry_run)
        if not written:
            print(f"    (no intervention activities matched)")
        for match, _basename in written:
            pair = (match["pkg"], match["ver"])
            all_captures.setdefault(pair, []).append(match)
            source_files[(match["pkg"], match["ver"], match["key"])] = xaml_path.name

    print()
    print(f"=== index.json updates (status=ok) ===")
    total_ok = 0
    for (pkg, ver), caps in sorted(all_captures.items()):
        # Deduplicate by key (same activity could match in multiple files; keep first)
        seen: set[str] = set()
        unique = []
        for c in caps:
            if c["key"] not in seen:
                unique.append(c)
                seen.add(c["key"])
        sf = {c["key"]: source_files[(pkg, ver, c["key"])] for c in unique}
        print(f"\n{pkg}@{ver}:")
        total_ok += _update_index_for_ok(pkg, ver, unique, sf, args.dry_run)

    total_demote = 0
    if not args.no_demote:
        print()
        print(f"=== demote pass (status=wizard_unavailable) ===")
        total_demote = _demote_not_available(args.dry_run)

    print()
    print(f"=== TOTALS ===")
    print(f"  ok captures:    {total_ok}")
    print(f"  demoted:        {total_demote}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
