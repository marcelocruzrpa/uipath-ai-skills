#!/usr/bin/env python3
"""Compare profile xaml_template entries to harvested Studio ground-truth XAML.

For each activity in `references/studio-ground-truth/<pkg>/<ver>/`, locates the
matching profile entry (same package; prefers same version, falls back to any
available version), parses both XAML snippets, and reports attribute-level
divergences.

Output: `REPORT.md` written next to the harvested XAML files.

Usage:
    python compare_to_ground_truth.py --package UiPath.UIAutomation.Activities --version 25.10
    python compare_to_ground_truth.py --package UiPath.UIAutomation.Activities --version 25.10 \
        --profile-version 26.2
"""

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from defusedxml.ElementTree import fromstring as _safe_fromstring

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PROFILES_DIR = REPO_ROOT / "uipath-core" / "references" / "version-profiles"
GROUND_TRUTH_DIR = REPO_ROOT / "uipath-core" / "references" / "studio-ground-truth"

# Common Studio xmlns declarations the snippets need to parse standalone.
#
# Must cover every prefix that appears in any profile xaml_template:
# see `python -c "..."` scan — the current corpus uses sa, sco, scg, sd,
# snm, ue, ueab, ui, uix, um, umab, umae, upaf, usau, uta, utam, utat, x.
# The URI values don't have to match the real Studio CLR namespaces for
# parsing to succeed; downstream code strips namespaces via local-name
# comparison, so any well-formed URI per prefix is sufficient. When a real
# package reuses a prefix with a *different* URI, reuse the same value
# here or the snippets won't parse.
WRAPPER_NSDECLS = (
    'xmlns="http://schemas.microsoft.com/netfx/2009/xaml/activities" '
    'xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml" '
    'xmlns:uix="http://schemas.uipath.com/workflow/activities/uix" '
    'xmlns:ui="http://schemas.uipath.com/workflow/activities" '
    'xmlns:sap="http://schemas.microsoft.com/netfx/2009/xaml/activities/presentation" '
    'xmlns:sap2010="http://schemas.microsoft.com/netfx/2010/xaml/activities/presentation" '
    'xmlns:sa="clr-namespace:System.Activities;assembly=System.Activities" '
    'xmlns:sco="clr-namespace:System.Collections.ObjectModel;assembly=mscorlib" '
    'xmlns:scg="clr-namespace:System.Collections.Generic;assembly=mscorlib" '
    'xmlns:sd="clr-namespace:System.Data;assembly=System.Data" '
    'xmlns:snm="clr-namespace:System.Net.Mail;assembly=System" '
    'xmlns:ue="clr-namespace:UiPath.Excel;assembly=UiPath.Excel.Activities.Api" '
    'xmlns:ueab="clr-namespace:UiPath.Excel.Activities.Business;assembly=UiPath.Excel.Activities.Business.Design" '
    'xmlns:um="clr-namespace:UiPath.Mail.Activities;assembly=UiPath.Mail.Activities" '
    'xmlns:umab="clr-namespace:UiPath.Mail.Activities.Business;assembly=UiPath.Mail.Activities.Business" '
    'xmlns:umae="clr-namespace:UiPath.Mail.Activities.Exchange;assembly=UiPath.Mail.Activities.Exchange" '
    'xmlns:upaf="clr-namespace:UiPath.Persistence.Activities.FormTask;assembly=UiPath.Persistence.Activities" '
    'xmlns:usau="clr-namespace:UiPath.Shared.Activities.Universal;assembly=UiPath.Shared.Activities" '
    'xmlns:uta="clr-namespace:UiPath.Testing.Activities;assembly=UiPath.Testing.Activities" '
    'xmlns:utam="clr-namespace:UiPath.Testing.Activities.Mobile;assembly=UiPath.Testing.Activities" '
    'xmlns:utat="clr-namespace:UiPath.Testing.Activities.TestData;assembly=UiPath.Testing.Activities" '
)


def _strip_xml_comments(s: str) -> str:
    return re.sub(r"<!--.*?-->", "", s, flags=re.DOTALL)


def _sanitize_placeholders(s: str) -> str:
    """Replace doc-style placeholder attribute values like
    `Reference="<some-thing>"` with `Reference="__PLACEHOLDER__"` so the snippet
    parses as XML. Profile xaml_template entries use these as teaching values.
    """
    return re.sub(r'="<[^"<>]*>"', '="__PLACEHOLDER__"', s)


def _find_activity_element(xaml: str, short_class: str) -> ET.Element | None:
    """Parse XAML and return the first element whose local-name == short_class.

    Wraps the snippet in a synthetic root with all common Studio xmlns decls so
    isolated profile templates parse without LookupError.
    """
    body = _sanitize_placeholders(_strip_xml_comments(xaml)).strip()
    wrapped = f'<__root__ {WRAPPER_NSDECLS}>{body}</__root__>'
    try:
        root = _safe_fromstring(wrapped)
    except ET.ParseError as e:
        raise RuntimeError(f"parse error: {e}") from e
    for el in root.iter():
        local = el.tag.rsplit("}", 1)[-1]
        if local == short_class:
            return el
    return None


def _local_attrs(el: ET.Element) -> dict[str, str]:
    """Return attribute dict keyed by local-name (namespace stripped)."""
    return {k.rsplit("}", 1)[-1]: v for k, v in el.attrib.items()}


def _child_local_names(el: ET.Element) -> list[str]:
    """Return ordered list of child local-names (namespaces stripped)."""
    return [c.tag.rsplit("}", 1)[-1] for c in el]


def _pick_profile(package: str, preferred_version: str | None) -> tuple[Path | str | None, dict | None]:
    """Return (profile_source, activities_dict) for the package, preferring the
    requested version, otherwise the lexicographically-latest available.

    Source may be a Path (on-disk profile) or a synthetic string label like
    ``"<plugin:UiPath.Persistence.Activities@1.4>"`` when the profile was
    registered by a plugin via ``plugin_loader.register_version_profile``.
    Plugin-registered profiles take priority over on-disk profiles for the
    same (package, version).
    """
    plugin_profiles: dict[tuple[str, str], dict] = {}
    try:
        from plugin_loader import load_plugins, get_version_profiles
        load_plugins()
        plugin_profiles = get_version_profiles()
    except ImportError:
        pass

    if preferred_version:
        plugin_key = (package, preferred_version)
        if plugin_key in plugin_profiles:
            return (f"<plugin:{package}@{preferred_version}>",
                    plugin_profiles[plugin_key].get("activities", {}))
        candidate = PROFILES_DIR / package / f"{preferred_version}.json"
        if candidate.exists():
            return candidate, json.loads(candidate.read_text(encoding="utf-8")).get("activities", {})

    # Collect all candidate versions (disk + plugin) and pick the latest.
    pkg_dir = PROFILES_DIR / package
    disk_versions = {p.stem: p for p in pkg_dir.glob("*.json")} if pkg_dir.exists() else {}
    plugin_versions = {ver: (pkg, ver) for (pkg, ver) in plugin_profiles if pkg == package}
    all_versions = sorted(set(disk_versions) | set(plugin_versions))
    if not all_versions:
        return None, None
    chosen = all_versions[-1]
    if chosen in plugin_versions:
        return (f"<plugin:{package}@{chosen}>",
                plugin_profiles[plugin_versions[chosen]].get("activities", {}))
    path = disk_versions[chosen]
    return path, json.loads(path.read_text(encoding="utf-8")).get("activities", {})


def _diff_one(activity: str, harvested: ET.Element, profile_template: str | None) -> dict:
    """Return a dict describing how harvested vs profile diverge for one activity."""
    out: dict = {"activity": activity, "status": "match"}
    h_attrs = _local_attrs(harvested)
    h_children = _child_local_names(harvested)
    out["harvested_attrs"] = h_attrs
    out["harvested_children"] = h_children

    if not profile_template or profile_template.strip() in ("null", ""):
        out["status"] = "profile_template_missing"
        return out

    try:
        p_el = _find_activity_element(profile_template, activity)
    except RuntimeError as e:
        out["status"] = "profile_template_unparseable"
        out["error"] = str(e)
        return out
    if p_el is None:
        out["status"] = "profile_element_not_found"
        return out

    p_attrs = _local_attrs(p_el)
    p_children = _child_local_names(p_el)
    out["profile_attrs"] = p_attrs
    out["profile_children"] = p_children

    only_in_harvest = sorted(set(h_attrs) - set(p_attrs))
    only_in_profile = sorted(set(p_attrs) - set(h_attrs))
    differing_values = sorted(
        a for a in (set(h_attrs) & set(p_attrs)) if h_attrs[a] != p_attrs[a]
    )
    only_h_kids = sorted(set(h_children) - set(p_children))
    only_p_kids = sorted(set(p_children) - set(h_children))

    if not (only_in_harvest or only_in_profile or differing_values or only_h_kids or only_p_kids):
        out["status"] = "match"
    else:
        out["status"] = "divergent"
        out["only_in_harvest"] = only_in_harvest
        out["only_in_profile"] = only_in_profile
        out["differing_values"] = {
            a: {"harvested": h_attrs[a], "profile": p_attrs[a]} for a in differing_values
        }
        out["only_h_children"] = only_h_kids
        out["only_p_children"] = only_p_kids
    return out


def _render_report(package: str, harvest_version: str, profile_source: Path | str | None,
                   diffs: list[dict]) -> str:
    lines = []
    lines.append(f"# Ground-truth diff: {package} @ {harvest_version}\n")
    lines.append(f"- Harvested: `references/studio-ground-truth/{package}/{harvest_version}/`")
    if profile_source is None:
        lines.append("- Profile: (none found)")
    elif isinstance(profile_source, Path):
        lines.append(f"- Profile: `{profile_source.relative_to(REPO_ROOT)}`")
    else:
        lines.append(f"- Profile: `{profile_source}` (plugin-registered)")
    lines.append("")
    counts = {"match": 0, "divergent": 0, "profile_template_missing": 0,
              "profile_element_not_found": 0, "profile_template_unparseable": 0}
    for d in diffs:
        counts[d["status"]] = counts.get(d["status"], 0) + 1
    lines.append("## Summary")
    for k in ("match", "divergent", "profile_template_missing",
              "profile_element_not_found", "profile_template_unparseable"):
        lines.append(f"- {k}: {counts.get(k, 0)}")
    lines.append("")

    for status_label, header in [
        ("divergent", "## Divergent"),
        ("profile_template_missing", "## Profile template missing (xaml_template is null)"),
        ("profile_element_not_found", "## Profile element not found in template"),
        ("profile_template_unparseable", "## Profile template unparseable"),
        ("match", "## Match"),
    ]:
        section = [d for d in diffs if d["status"] == status_label]
        if not section:
            continue
        lines.append(header + "\n")
        for d in section:
            lines.append(f"### `{d['activity']}`")
            if status_label == "divergent":
                if d["only_in_harvest"]:
                    lines.append(f"- **Only in harvested (Studio default):** `{', '.join(d['only_in_harvest'])}`")
                if d["only_in_profile"]:
                    lines.append(f"- **Only in profile (enriched):** `{', '.join(d['only_in_profile'])}`")
                if d["differing_values"]:
                    lines.append("- **Differing values:**")
                    for k, v in d["differing_values"].items():
                        lines.append(f"  - `{k}`: harvested=`{v['harvested']}`, profile=`{v['profile']}`")
                if d["only_h_children"]:
                    lines.append(f"- **Children only in harvested:** `{', '.join(d['only_h_children'])}`")
                if d["only_p_children"]:
                    lines.append(f"- **Children only in profile:** `{', '.join(d['only_p_children'])}`")
            elif status_label == "match":
                lines.append(f"- attrs: `{', '.join(sorted(d['harvested_attrs']))}`")
            elif status_label == "profile_template_unparseable":
                lines.append(f"- error: {d.get('error', '(unknown)')}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--package", required=True)
    parser.add_argument("--version", required=True, help="Harvested version (subdir of studio-ground-truth/<package>/)")
    parser.add_argument("--profile-version", help="Specific profile version to compare against; defaults to same as --version, then latest available")
    parser.add_argument("--write", action="store_true", default=False,
                        help="Persist REPORT.md to the harvest dir. Default is dry-run (print to stdout only).")
    args = parser.parse_args()

    harvest_dir = GROUND_TRUTH_DIR / args.package / args.version
    if not harvest_dir.exists():
        print(f"ERROR: no harvest dir at {harvest_dir}", file=sys.stderr)
        return 2
    index_path = harvest_dir / "index.json"
    if not index_path.exists():
        print(f"ERROR: no index.json at {index_path}", file=sys.stderr)
        return 2

    profile_source, profile_activities = _pick_profile(args.package, args.profile_version or args.version)
    if not profile_activities:
        print(f"WARNING: no profile found for {args.package}; comparison will be empty.", file=sys.stderr)

    index = json.loads(index_path.read_text(encoding="utf-8"))
    diffs = []
    for activity, meta in index.get("activities", {}).items():
        if meta.get("status") != "ok":
            continue
        xaml_path = harvest_dir / f"{activity}.xaml"
        if not xaml_path.exists():
            continue
        harvested = _find_activity_element(xaml_path.read_text(encoding="utf-8"), activity)
        if harvested is None:
            diffs.append({"activity": activity, "status": "harvested_element_not_found",
                          "harvested_attrs": {}, "harvested_children": []})
            continue
        profile_meta = (profile_activities or {}).get(activity, {})
        diffs.append(_diff_one(activity, harvested, profile_meta.get("xaml_template")))

    report = _render_report(args.package, args.version, profile_source, diffs)
    report_path = harvest_dir / "REPORT.md"
    if args.write:
        report_path.write_text(report, encoding="utf-8")
        print(f"Wrote {report_path}")
        print()
        print(report)
    else:
        print(f"[compare_to_ground_truth] dry-run: pass --write to persist REPORT.md to {report_path}",
              file=sys.stderr)
        sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
