#!/usr/bin/env python3
"""Discover version profiles from mirrored activity docs.

Parses structured markdown activity docs under references/activity-docs/
and extracts version-sensitive markers:
- Version= attribute values from canonical XAML blocks
- Property names and defaults
- Enum values
- Version-notes differences

Outputs machine-readable profile data suitable for checking into version_band.py.

Usage:
    # Extract profile from a single version directory
    python3 discover_version_profile.py references/activity-docs/UiPath.UIAutomation.Activities/26.2

    # Diff two version directories
    python3 discover_version_profile.py references/activity-docs/UiPath.UIAutomation.Activities/26.2 \
        references/activity-docs/UiPath.UIAutomation.Activities/26.3

    # Output as JSON
    python3 discover_version_profile.py --json references/activity-docs/UiPath.UIAutomation.Activities/26.2
"""

import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# Pattern to extract Version="VN" from XAML blocks in markdown
_RE_VERSION_ATTR = re.compile(
    r'<uix:(\w+)\s[^>]*Version="(V\d+)"'
)

# Pattern to extract property rows from markdown tables
# Matches: | `PropertyName` | ... | `Type` | ... |
_RE_PROPERTY_ROW = re.compile(
    r'^\|\s*`(\w+)`\s*\|'
)

# Pattern to find XAML code blocks
_RE_XAML_BLOCK = re.compile(
    r'```xml\s*\n(.*?)```',
    re.DOTALL
)

# Properties known to be version-sensitive
_VERSION_SENSITIVE_PROPERTIES = {
    "HealingAgentBehavior", "ClipboardMode", "InteractionMode",
    "ScopeIdentifier", "ActivateBefore", "ClickBeforeMode",
    "EmptyFieldMode", "Version",
}


def extract_profile(doc_dir: Path) -> dict:
    """Extract a version profile from an activity docs directory.

    Args:
        doc_dir: Path to a versioned docs directory (e.g.,
            references/activity-docs/UiPath.UIAutomation.Activities/26.2)

    Returns:
        Dict with:
        - "activities": {activity_name: {"version": "V5", "properties": [...]}}
        - "version_notes": extracted notes if version-notes.md exists
        - "source": str path
    """
    profile = {
        "source": str(doc_dir),
        "activities": {},
        "version_notes": None,
    }

    # Parse activity docs
    activities_dir = doc_dir / "activities"
    if activities_dir.is_dir():
        for md_file in sorted(activities_dir.glob("*.md")):
            if md_file.name in ("overview.md", "version-notes.md"):
                continue
            activity_data = _parse_activity_doc(md_file)
            if activity_data:
                profile["activities"][activity_data["name"]] = activity_data

    # Parse version-notes if present
    version_notes_path = activities_dir / "version-notes.md" if activities_dir.is_dir() else None
    if version_notes_path and version_notes_path.exists():
        profile["version_notes"] = version_notes_path.read_text(encoding="utf-8")

    return profile


def _parse_activity_doc(md_path: Path) -> dict | None:
    """Parse a single activity markdown doc.

    Returns dict with activity name, version, and properties, or None
    if the doc doesn't contain parseable activity data.
    """
    content = md_path.read_text(encoding="utf-8")

    # Extract activity name from XAML blocks
    versions = {}
    properties = set()

    for block_match in _RE_XAML_BLOCK.finditer(content):
        block = block_match.group(1)
        for m in _RE_VERSION_ATTR.finditer(block):
            activity = m.group(1)
            version = m.group(2)
            if activity not in versions:
                versions[activity] = version

        # Extract property names from XAML attributes
        for line in block.split("\n"):
            line = line.strip()
            # Match attribute assignments like PropertyName="value"
            for attr_match in re.finditer(r'(\w+)="[^"]*"', line):
                prop = attr_match.group(1)
                if prop not in ("xmlns", "x", "sap2010") and not prop.startswith("xmlns:"):
                    properties.add(prop)

    # Extract properties from markdown tables
    for m in _RE_PROPERTY_ROW.finditer(content):
        properties.add(m.group(1))

    if not versions and not properties:
        return None

    # Use the primary activity (usually the doc's namesake)
    primary_name = md_path.stem
    # Map doc names to internal names (e.g., TypeInto -> NTypeInto for 26.3 docs)
    name_map = {
        "TypeInto": "NTypeInto", "Click": "NClick", "CheckElement": "NCheck",
        "CheckAppState": "NCheckState", "GetText": "NGetText",
        "KeyboardShortcuts": "NKeyboardShortcuts", "SelectItem": "NSelectItem",
        "MouseScroll": "NMouseScroll", "Hover": "NHover",
        "GoToURL": "NGoToUrl", "GetURL": "NGetUrl",
        "ExtractData": "NExtractDataGeneric",
        "ApplicationCard": "NApplicationCard",
    }
    canonical_name = name_map.get(primary_name, primary_name)

    return {
        "name": canonical_name,
        "doc_name": primary_name,
        "version_attrs": versions,
        "properties": sorted(properties),
    }


def diff_profiles(profile_a: dict, profile_b: dict) -> dict:
    """Diff two profiles and return the differences.

    Returns dict with:
    - "version_changes": {activity: {"old": "V4", "new": "V5"}}
    - "added_properties": {activity: [prop_names]}
    - "removed_properties": {activity: [prop_names]}
    - "new_activities": [names]
    - "removed_activities": [names]
    """
    acts_a = set(profile_a.get("activities", {}).keys())
    acts_b = set(profile_b.get("activities", {}).keys())

    diff = {
        "source_a": profile_a.get("source", ""),
        "source_b": profile_b.get("source", ""),
        "version_changes": {},
        "added_properties": {},
        "removed_properties": {},
        "new_activities": sorted(acts_b - acts_a),
        "removed_activities": sorted(acts_a - acts_b),
    }

    for act in sorted(acts_a & acts_b):
        a_data = profile_a["activities"][act]
        b_data = profile_b["activities"][act]

        # Version attribute changes
        a_vers = a_data.get("version_attrs", {})
        b_vers = b_data.get("version_attrs", {})
        for activity_tag in set(a_vers) | set(b_vers):
            old_v = a_vers.get(activity_tag)
            new_v = b_vers.get(activity_tag)
            if old_v != new_v:
                diff["version_changes"].setdefault(act, {})[activity_tag] = {
                    "old": old_v, "new": new_v
                }

        # Property changes
        a_props = set(a_data.get("properties", []))
        b_props = set(b_data.get("properties", []))
        added = sorted(b_props - a_props)
        removed = sorted(a_props - b_props)
        if added:
            diff["added_properties"][act] = added
        if removed:
            diff["removed_properties"][act] = removed

    return diff


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Discover version profiles from activity docs"
    )
    parser.add_argument("dirs", nargs="+",
                        help="One or two version directories to analyze/diff")
    parser.add_argument("--json", action="store_true",
                        help="Output as JSON")
    args = parser.parse_args()

    dirs = [Path(d) for d in args.dirs]
    for d in dirs:
        if not d.is_dir():
            print(f"ERROR: {d} is not a directory", file=sys.stderr)
            sys.exit(1)

    if len(dirs) == 1:
        profile = extract_profile(dirs[0])
        if args.json:
            print(json.dumps(profile, indent=2))
        else:
            print(f"Profile: {profile['source']}")
            print(f"Activities: {len(profile['activities'])}")
            for name, data in sorted(profile["activities"].items()):
                vers = data.get("version_attrs", {})
                ver_str = ", ".join(f"{k}={v}" for k, v in vers.items()) if vers else "none"
                print(f"  {name}: versions=[{ver_str}] props={len(data.get('properties', []))}")

    elif len(dirs) == 2:
        profile_a = extract_profile(dirs[0])
        profile_b = extract_profile(dirs[1])
        diff = diff_profiles(profile_a, profile_b)

        if args.json:
            print(json.dumps(diff, indent=2))
        else:
            print(f"Diff: {diff['source_a']} -> {diff['source_b']}")
            if diff["new_activities"]:
                print(f"\nNew activities: {', '.join(diff['new_activities'])}")
            if diff["removed_activities"]:
                print(f"\nRemoved activities: {', '.join(diff['removed_activities'])}")
            if diff["version_changes"]:
                print("\nVersion changes:")
                for act, changes in sorted(diff["version_changes"].items()):
                    for tag, change in changes.items():
                        print(f"  {act}.{tag}: {change['old']} -> {change['new']}")
            if diff["added_properties"]:
                print("\nAdded properties:")
                for act, props in sorted(diff["added_properties"].items()):
                    print(f"  {act}: {', '.join(props)}")
            if diff["removed_properties"]:
                print("\nRemoved properties:")
                for act, props in sorted(diff["removed_properties"].items()):
                    print(f"  {act}: {', '.join(props)}")
            if not any([diff["version_changes"], diff["added_properties"],
                       diff["removed_properties"], diff["new_activities"],
                       diff["removed_activities"]]):
                print("  No differences found.")
    else:
        print("ERROR: Provide 1 or 2 directories", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
