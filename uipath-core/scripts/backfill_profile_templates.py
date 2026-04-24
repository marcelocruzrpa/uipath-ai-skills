#!/usr/bin/env python3
"""Backfill xaml_template (and related fields) into version-profile JSON files.

For each activity in studio-ground-truth/<pkg>/<ver>/<ActivityKey>.xaml, locates
the matching profile entry by exact filename stem == activity key (case-sensitive).
Extracts the raw XAML snippet, namespace_prefix, and child_elements from the
harvested file, then writes them into the profile JSON where the field is currently
null or missing.

Idempotent: running twice produces the same result. Existing non-null fields are
never overwritten unless --force is passed.

The XAML written into xaml_template is the raw inner snippet (the activity element
itself, not the outer <Activity> wrapper).

Usage:
    # Dry-run all packages/versions (show what would change, write nothing)
    python backfill_profile_templates.py --dry-run

    # Apply to one package/version
    python backfill_profile_templates.py --package UiPath.Testing.Activities --version 25.10

    # Apply all (all ground-truth dirs that have a matching profile)
    python backfill_profile_templates.py --all

    # Overwrite even existing non-null xaml_template entries
    python backfill_profile_templates.py --all --force
"""

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    from defusedxml.ElementTree import fromstring as _safe_fromstring
    import defusedxml.ElementTree as _safe_ET
except ImportError:
    import xml.etree.ElementTree as _safe_ET
    _safe_fromstring = ET.fromstring

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PROFILES_DIR = REPO_ROOT / "uipath-core" / "references" / "version-profiles"
GROUND_TRUTH_DIR = REPO_ROOT / "uipath-core" / "references" / "studio-ground-truth"

# Common Studio xmlns needed to parse snippets in isolation.
_WRAPPER_NS = (
    'xmlns="http://schemas.microsoft.com/netfx/2009/xaml/activities" '
    'xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml" '
    'xmlns:uix="http://schemas.uipath.com/workflow/activities/uix" '
    'xmlns:ui="http://schemas.uipath.com/workflow/activities" '
    'xmlns:sap="http://schemas.microsoft.com/netfx/2009/xaml/activities/presentation" '
    'xmlns:sap2010="http://schemas.microsoft.com/netfx/2010/xaml/activities/presentation" '
    'xmlns:scg="clr-namespace:System.Collections.Generic;assembly=mscorlib" '
    'xmlns:ue="clr-namespace:UiPath.Excel;assembly=UiPath.Excel.Activities" '
    'xmlns:ueab="clr-namespace:UiPath.Excel.Activities.Business;assembly=UiPath.Excel.Activities" '
    'xmlns:utat="clr-namespace:UiPath.Testing.Activities.TestData;assembly=UiPath.Testing.Activities" '
    'xmlns:uta="clr-namespace:UiPath.Testing.Activities;assembly=UiPath.Testing.Activities" '
    'xmlns:up="clr-namespace:UiPath.Platform.Activities;assembly=UiPath.Platform.Activities" '
    'xmlns:sd="clr-namespace:System.Drawing;assembly=System.Drawing.Common" '
    'xmlns:sd1="clr-namespace:System.Drawing;assembly=System.Drawing.Primitives" '
)


def _extract_inner_snippet(xaml_text: str) -> str:
    """Extract the activity element from inside the <Activity> wrapper.

    Returns the raw XML text of the inner element (with its original indentation),
    stripping the outer <Activity>...</Activity> wrapper.
    """
    # Find the first child element start after the opening <Activity ...>
    # Strategy: parse to find the inner element, then extract by string slicing.
    text = xaml_text.strip()

    # Find the end of the outer <Activity ...> opening tag.
    # It may be multi-line, so scan for the first '>' that closes the Activity tag.
    outer_end = text.find(">")
    if outer_end == -1:
        return text

    inner = text[outer_end + 1:]

    # Strip trailing </Activity> (allow optional whitespace / newline)
    inner = re.sub(r"\s*</Activity>\s*$", "", inner, flags=re.DOTALL)

    # Normalize indentation: strip one leading newline + optional common indent.
    lines = inner.split("\n")
    # Drop leading/trailing blank lines.
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()

    # Remove common leading whitespace (2 spaces typically).
    if lines:
        indent = len(lines[0]) - len(lines[0].lstrip())
        lines = [ln[indent:] if ln[:indent] == " " * indent else ln for ln in lines]

    return "\n".join(lines)


def _parse_activity_element(xaml_text: str, short_class: str) -> ET.Element | None:
    """Parse the XAML (full file or snippet) and return the activity element."""
    # Wrap in a synthetic root with all common xmlns so isolated snippets parse.
    body = xaml_text.strip()
    wrapped = f"<__root__ {_WRAPPER_NS}>{body}</__root__>"
    try:
        root = _safe_fromstring(wrapped)
    except ET.ParseError:
        # Try once more after stripping XML comments.
        body2 = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL).strip()
        wrapped2 = f"<__root__ {_WRAPPER_NS}>{body2}</__root__>"
        try:
            root = _safe_fromstring(wrapped2)
        except ET.ParseError:
            return None
    for el in root.iter():
        local = el.tag.rsplit("}", 1)[-1]
        if local == short_class:
            return el
    return None


def _namespace_prefix_from_xaml(xaml_text: str, short_class: str) -> str | None:
    """Extract the XML namespace prefix used for *short_class* in the XAML.

    Scans the raw text for a tag like `prefix:ShortClass` or `ShortClass` (no prefix).
    Returns the prefix string or None if unprefixed.
    """
    # Match <prefix:ShortClass or <ShortClass (start of tag)
    pattern = re.compile(
        r"<([A-Za-z_][A-Za-z0-9_]*):(?:" + re.escape(short_class) + r")"
        r"|<(?:" + re.escape(short_class) + r")[\s/>]"
    )
    m = pattern.search(xaml_text)
    if not m:
        return None
    # Group 1 is the prefix (captured only in the prefixed branch).
    return m.group(1) if m.group(1) else None


def _child_elements_from_element(el: ET.Element, short_class: str) -> list[str]:
    """Return the list of dotted child element names.

    E.g. children named `{ns}NClick.Target` or `NClick.Target` → `["Target"]`.
    Strips the `ShortClass.` prefix, deduplicates, preserves order.
    """
    seen: set[str] = set()
    result: list[str] = []
    prefix = short_class + "."
    for child in el:
        local = child.tag.rsplit("}", 1)[-1]
        if local.startswith(prefix):
            name = local[len(prefix):]
            if name and name not in seen:
                seen.add(name)
                result.append(name)
    return result


def _extract_activity_info(
    xaml_path: Path, short_class: str
) -> tuple[str | None, str | None, list[str]]:
    """Return (snippet, namespace_prefix, child_elements) from a harvested XAML file.

    snippet: the inner activity XML text (stripped of <Activity> wrapper)
    namespace_prefix: e.g. 'uix', 'ueab', 'utat' or None
    child_elements: list of dotted-child names e.g. ['Body', 'Target']
    """
    xaml_text = xaml_path.read_text(encoding="utf-8")
    snippet = _extract_inner_snippet(xaml_text)
    if not snippet:
        return None, None, []

    ns_prefix = _namespace_prefix_from_xaml(snippet, short_class)
    el = _parse_activity_element(xaml_text, short_class)
    children: list[str] = []
    if el is not None:
        children = _child_elements_from_element(el, short_class)

    return snippet, ns_prefix, children


def _backfill_one(
    pkg: str, ver: str, dry_run: bool, force: bool
) -> dict[str, int]:
    """Process one package/version pair. Returns stats dict."""
    stats = {
        "activities_in_profile": 0,
        "activities_harvested": 0,
        "filled": 0,
        "skipped_existing": 0,
        "skipped_no_harvest": 0,
        "skipped_case_mismatch": 0,
        "skipped_no_profile_entry": 0,
        "skipped_no_snippet": 0,
    }

    harvest_dir = GROUND_TRUTH_DIR / pkg / ver
    if not harvest_dir.exists():
        return stats

    index_path = harvest_dir / "index.json"
    if not index_path.exists():
        print(f"  WARNING: no index.json at {index_path}", file=sys.stderr)
        return stats

    index = json.loads(index_path.read_text(encoding="utf-8"))
    harvested_keys = {
        k for k, v in index.get("activities", {}).items() if v.get("status") == "ok"
    }

    # Locate profile JSON.
    profile_path = PROFILES_DIR / pkg / f"{ver}.json"
    if not profile_path.exists():
        print(f"  INFO: no profile at {profile_path} — skipping {pkg}@{ver}")
        return stats

    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    activities: dict = profile.get("activities", {})
    stats["activities_in_profile"] = len(activities)

    # Build case-insensitive lookup: lowercase(key) -> actual_key for XAML files.
    # The XAML filename stem must match the profile key exactly (case-sensitive).
    # We only flag a mismatch when a .xaml file exists but doesn't match any profile key.
    harvested_lower: dict[str, str] = {k.lower(): k for k in harvested_keys}

    changed = False

    for activity_key, activity_meta in activities.items():
        stats["activities_in_profile"] += 0  # already counted above

        # Check for exact-match harvest file.
        xaml_path = harvest_dir / f"{activity_key}.xaml"

        if not xaml_path.exists():
            # Check for case mismatch.
            lower = activity_key.lower()
            if lower in harvested_lower and harvested_lower[lower] != activity_key:
                print(
                    f"  SKIP {pkg}@{ver} {activity_key}: case mismatch with "
                    f"harvested file '{harvested_lower[lower]}.xaml'",
                    file=sys.stderr,
                )
                stats["skipped_case_mismatch"] += 1
            else:
                stats["skipped_no_harvest"] += 1
            continue

        stats["activities_harvested"] += 1

        # Check whether backfill is needed.
        existing_template = activity_meta.get("xaml_template")
        if existing_template is not None and not force:
            stats["skipped_existing"] += 1
            continue

        snippet, ns_prefix, child_els = _extract_activity_info(xaml_path, activity_key)
        if snippet is None:
            print(
                f"  SKIP {pkg}@{ver} {activity_key}: could not extract snippet from XAML",
                file=sys.stderr,
            )
            stats["skipped_no_snippet"] += 1
            continue

        if dry_run:
            print(
                f"  [DRY-RUN] would fill {pkg}@{ver} {activity_key}: "
                f"namespace_prefix={ns_prefix!r}, "
                f"child_elements={child_els}, "
                f"xaml_template={snippet[:60].replace(chr(10), ' ')!r}..."
            )
            stats["filled"] += 1
            continue

        # Update fields in-place, preserving key order.
        # Only set namespace_prefix and child_elements when currently missing/None.
        if activity_meta.get("namespace_prefix") is None:
            activity_meta["namespace_prefix"] = ns_prefix
        if not activity_meta.get("child_elements"):
            activity_meta["child_elements"] = child_els
        activity_meta["xaml_template"] = snippet

        stats["filled"] += 1
        changed = True
        print(f"  fill {pkg}@{ver} {activity_key} ({len(snippet)} chars)")

    # Report harvested XAML files not found in profile (case-mismatch or new).
    profile_keys_lower = {k.lower() for k in activities}
    for hk in harvested_keys:
        if hk.lower() not in profile_keys_lower:
            print(
                f"  INFO: harvested '{hk}.xaml' has no profile entry in {pkg}@{ver} — skipped",
                file=sys.stderr,
            )
            stats["skipped_no_profile_entry"] += 1

    if changed and not dry_run:
        out = json.dumps(profile, indent=2, ensure_ascii=False) + "\n"
        profile_path.write_text(out, encoding="utf-8")
        print(f"  Wrote {profile_path}")

    return stats


def _discover_pairs() -> list[tuple[str, str]]:
    """Return all (package, version) pairs that have both a harvest dir and a profile."""
    pairs: list[tuple[str, str]] = []
    for harvest_ver_dir in sorted(GROUND_TRUTH_DIR.rglob("index.json")):
        ver = harvest_ver_dir.parent.name
        pkg = harvest_ver_dir.parent.parent.name
        if (PROFILES_DIR / pkg / f"{ver}.json").exists():
            pairs.append((pkg, ver))
    return pairs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true",
                       help="Process all package/version pairs that have both harvest and profile")
    group.add_argument("--package", metavar="PKG",
                       help="Package name (requires --version)")
    parser.add_argument("--version", metavar="VER",
                        help="Version label matching the harvest subdirectory (e.g. 25.10)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would change without writing any files")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite even existing non-null xaml_template entries")
    args = parser.parse_args()

    if args.package and not args.version:
        parser.error("--package requires --version")

    if args.all:
        pairs = _discover_pairs()
        if not pairs:
            print("No matching package/version pairs found.", file=sys.stderr)
            return 2
    else:
        pairs = [(args.package, args.version)]

    mode = "DRY-RUN" if args.dry_run else "APPLY"
    print(f"backfill_profile_templates — mode={mode}, pairs={len(pairs)}, force={args.force}")
    print()

    total: dict[str, int] = {
        "activities_in_profile": 0,
        "activities_harvested": 0,
        "filled": 0,
        "skipped_existing": 0,
        "skipped_no_harvest": 0,
        "skipped_case_mismatch": 0,
        "skipped_no_profile_entry": 0,
        "skipped_no_snippet": 0,
    }

    for pkg, ver in pairs:
        print(f"{pkg}@{ver}")
        stats = _backfill_one(pkg, ver, dry_run=args.dry_run, force=args.force)
        for k in total:
            total[k] += stats[k]
        # Per-pair summary line.
        print(
            f"  -> filled={stats['filled']}, "
            f"skipped_existing={stats['skipped_existing']}, "
            f"no_harvest={stats['skipped_no_harvest']}, "
            f"case_mismatch={stats['skipped_case_mismatch']}"
        )
        print()

    print("=== TOTALS ===")
    for k, v in total.items():
        print(f"  {k}: {v}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
