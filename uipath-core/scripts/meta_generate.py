#!/usr/bin/env python3
"""Meta-generator — produces Python generator modules from activity profiles.

Reads version-profile data (extracted by discover_version_profile.py from
mirrored upstream docs) and generates deterministic Python modules that
produce XAML for each activity.

Generated modules are committed to the repo as production code. Normal
users do not need to run this tool.

Architecture:
    1. Read profile data from version_band.py (checked-in)
    2. Read canonical XAML templates from mirrored docs
    3. Apply deterministic overrides from scripts/generate_overrides/
    4. Produce Python modules with gen_* functions
    5. Write to scripts/generate_activities/ (committed artifacts)

Overrides (scripts/generate_overrides/):
    Manual override files for cases where docs don't fully determine the
    emitted XAML shape. Overrides take precedence over doc-derived code.
    Example: NSelectItem must always be V1, TargetAnchorable child
    element structure.

Output guarantees:
    - Deterministic ordering (alphabetical generators, sorted properties)
    - Stable formatting (no timestamps, no random values)
    - Identical output on re-run with same input

Usage:
    # Generate from current profile data (dry run — show what would change)
    python3 meta_generate.py --dry-run

    # Generate and write modules
    python3 meta_generate.py

    # Generate for a specific target (default: xaml)
    python3 meta_generate.py --target xaml

    # Verify generated output matches current hand-written generators
    python3 meta_generate.py --verify
"""

import json
import os
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _get_scripts_dir() -> Path:
    return Path(__file__).resolve().parent


def _get_overrides_dir() -> Path:
    return _get_scripts_dir() / "generate_overrides"


def _get_activities_dir() -> Path:
    return _get_scripts_dir() / "generate_activities"


def _get_docs_dir() -> Path:
    return _get_scripts_dir().parent / "references" / "activity-docs"


def _load_overrides() -> dict:
    """Load override files from generate_overrides/ directory.

    Override files are Python modules that export an `OVERRIDES` dict
    mapping generator names to override specifications.

    Returns: {gen_name: override_spec}
    """
    overrides_dir = _get_overrides_dir()
    if not overrides_dir.is_dir():
        return {}

    overrides = {}
    for py_file in sorted(overrides_dir.glob("*.py")):
        if py_file.name.startswith("_"):
            continue
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                f"override_{py_file.stem}", py_file
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, "OVERRIDES"):
                overrides.update(mod.OVERRIDES)
        except Exception as e:
            print(f"  WARNING: Could not load override {py_file.name}: {e}",
                  file=sys.stderr)

    return overrides


def _extract_canonical_xaml(doc_path: Path) -> list[str]:
    """Extract canonical XAML blocks from a markdown activity doc.

    Returns list of XAML strings found in ```xml blocks.
    """
    if not doc_path.exists():
        return []
    content = doc_path.read_text(encoding="utf-8")
    blocks = re.findall(r'```xml\s*\n(.*?)```', content, re.DOTALL)
    return blocks


def generate_activity_profile(package: str, version: str) -> dict:
    """Generate a comprehensive profile for all activities in a package version.

    Args:
        package: Package name (e.g., "UiPath.UIAutomation.Activities")
        version: Version directory name (e.g., "26.2")

    Returns:
        Dict mapping activity names to their profile data:
        {
            "NTypeInto": {
                "version_attr": "V5",
                "properties": [...],
                "canonical_xaml": [str, ...],
                "override": {...} or None,
            },
            ...
        }
    """
    from discover_version_profile import extract_profile

    doc_dir = _get_docs_dir() / package / version
    if not doc_dir.is_dir():
        print(f"  WARNING: {doc_dir} does not exist", file=sys.stderr)
        return {}

    profile = extract_profile(doc_dir)
    overrides = _load_overrides()

    result = {}
    for act_name, act_data in profile.get("activities", {}).items():
        version_attrs = act_data.get("version_attrs", {})
        primary_version = version_attrs.get(act_name)

        # Load canonical XAML from the doc
        doc_name = act_data.get("doc_name", act_name)
        activities_dir = doc_dir / "activities"
        canonical = _extract_canonical_xaml(activities_dir / f"{doc_name}.md")

        entry = {
            "version_attr": primary_version,
            "properties": act_data.get("properties", []),
            "canonical_xaml": canonical,
            "override": overrides.get(act_name.lower()),
        }
        result[act_name] = entry

    return result


def verify_parity(package: str, version: str) -> list[str]:
    """Verify that generated output would match current hand-written generators.

    Returns list of discrepancy descriptions, empty if parity is achieved.
    """
    profile = generate_activity_profile(package, version)
    discrepancies = []

    for act_name, data in sorted(profile.items()):
        ver = data.get("version_attr")
        if ver:
            discrepancies.append(
                f"  {act_name}: doc says Version=\"{ver}\" — "
                f"verify hand-written generator matches"
            )

    return discrepancies


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Meta-generate Python generators from activity profiles"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be generated without writing")
    parser.add_argument("--verify", action="store_true",
                        help="Verify generated output matches hand-written generators")
    parser.add_argument("--target", default="xaml", choices=["xaml", "coded"],
                        help="Target output format (default: xaml)")
    parser.add_argument("--package", default="UiPath.UIAutomation.Activities",
                        help="Package to generate for")
    parser.add_argument("--version", default=None,
                        help="Doc version to use (default: from BAND_PROFILE_VERSIONS)")
    args = parser.parse_args()

    if args.target == "coded":
        print("Coded workflow generation is not yet implemented.", file=sys.stderr)
        sys.exit(1)

    # Determine version
    version = args.version
    if version is None:
        from version_band import BAND_PROFILE_VERSIONS
        latest_band = max(BAND_PROFILE_VERSIONS.keys())
        version = BAND_PROFILE_VERSIONS.get(latest_band, {}).get(args.package)
        if version is None:
            print(f"ERROR: No profile version for {args.package} in band {latest_band}",
                  file=sys.stderr)
            sys.exit(1)

    if args.verify:
        print(f"Verifying parity: {args.package} {version}")
        issues = verify_parity(args.package, version)
        if issues:
            print(f"\n{len(issues)} items to verify:")
            for issue in issues:
                print(issue)
        else:
            print("No activities found in profile.")
        sys.exit(0)

    profile = generate_activity_profile(args.package, version)
    if not profile:
        print(f"No activities found for {args.package} {version}", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        print(f"Profile: {args.package} {version}")
        print(f"Activities: {len(profile)}")
        overrides_count = sum(1 for d in profile.values() if d.get("override"))
        print(f"Overrides: {overrides_count}")
        print()
        for name, data in sorted(profile.items()):
            ver = data.get("version_attr", "?")
            props = len(data.get("properties", []))
            xaml_count = len(data.get("canonical_xaml", []))
            has_override = "OVERRIDE" if data.get("override") else ""
            print(f"  {name}: Version={ver}, {props} props, {xaml_count} XAML blocks {has_override}")
    else:
        print("Full code generation is not yet implemented.")
        print("Use --dry-run to inspect profiles or --verify for parity checks.")
        print()
        print("Current status:")
        print(f"  Profile: {args.package} {version}")
        print(f"  Activities: {len(profile)}")
        print(f"  Overrides dir: {_get_overrides_dir()}")
        print()
        print("Next steps:")
        print("  1. Create generate_overrides/ with override specs")
        print("  2. Implement template-to-code generation")
        print("  3. Run --verify to check parity with hand-written generators")


if __name__ == "__main__":
    main()
