#!/usr/bin/env python3
"""Golden/snapshot tests for generator output.

Generates XAML from the same specs used by test_generator_lint_integration.py,
normalizes UUIDs to sequential placeholders, and compares against stored golden
files. Detects any structural change in generator output — even changes that
pass lint and validation.

Usage:
    python3 scripts/test_generator_snapshots.py              # Run tests
    python3 scripts/test_generator_snapshots.py --update      # Regenerate golden files
    python3 scripts/test_generator_snapshots.py --verbose     # Show diffs on failure
"""

import difflib
import os
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPTS_DIR.parent
SNAPSHOTS_DIR = SKILL_DIR / "assets" / "generator-snapshots"

# Ensure scripts/ is on sys.path for imports
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from generate_workflow import generate_workflow
from test_generator_lint_integration import SPECS

# Determine which specs came from plugins and their snapshot directories
_PLUGIN_SPEC_NAMES = set()
_PLUGIN_SNAPSHOT_DIRS = {}  # spec_name -> Path to snapshot dir
try:
    from plugin_loader import get_test_specs
    _PLUGIN_SPEC_NAMES = set(get_test_specs().keys())
    # Derive snapshot dirs from plugin roots — each plugin's __init__.py
    # registers specs, and the snapshot dir is <plugin_root>/assets/generator-snapshots/
    import plugin_loader
    for child in sorted(SKILL_DIR.parent.iterdir()):
        ext_init = child / "extensions" / "__init__.py"
        if ext_init.exists() and child.name != SKILL_DIR.name:
            snap_dir = child / "assets" / "generator-snapshots"
            if snap_dir.exists():
                # Map specs from this plugin to its snapshot dir
                for name in _PLUGIN_SPEC_NAMES:
                    candidate = snap_dir / f"{name}.xaml"
                    if candidate.exists():
                        _PLUGIN_SNAPSHOT_DIRS[name] = snap_dir
except ImportError:
    pass

# Skip specs that intentionally fail generation
SKIP_SPECS = {"delay_and_misc"}

# UUID regex: matches standard 8-4-4-4-12 hex format
_RE_UUID = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', re.IGNORECASE)


def normalize_uuids(content: str) -> str:
    """Replace all UUIDs with sequential placeholders for deterministic comparison.

    Each unique UUID gets a stable placeholder: UUID_001, UUID_002, ...
    Order is determined by first appearance in the content.
    """
    seen = {}
    counter = [0]

    def replacer(match):
        uuid_str = match.group(0).lower()
        if uuid_str not in seen:
            counter[0] += 1
            seen[uuid_str] = f"UUID_{counter[0]:03d}"
        return seen[uuid_str]

    return _RE_UUID.sub(replacer, content)


def generate_and_normalize(spec: dict) -> str:
    """Generate XAML from spec and normalize UUIDs."""
    xaml = generate_workflow(spec)
    return normalize_uuids(xaml)


def golden_path(spec_name: str) -> Path:
    """Path to golden file for a spec — searches core and plugin dirs."""
    # Check plugin snapshot dir first for plugin-originated specs
    if spec_name in _PLUGIN_SNAPSHOT_DIRS:
        return _PLUGIN_SNAPSHOT_DIRS[spec_name] / f"{spec_name}.xaml"
    return SNAPSHOTS_DIR / f"{spec_name}.xaml"


def _target_dir(spec_name: str) -> Path:
    """Directory to write golden files for a spec."""
    if spec_name in _PLUGIN_SNAPSHOT_DIRS:
        return _PLUGIN_SNAPSHOT_DIRS[spec_name]
    return SNAPSHOTS_DIR


def update_golden_files():
    """Regenerate all golden files."""
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    updated = 0
    for name, spec in sorted(SPECS.items()):
        if name in SKIP_SPECS:
            continue
        try:
            normalized = generate_and_normalize(spec)
            target = _target_dir(name)
            target.mkdir(parents=True, exist_ok=True)
            path = target / f"{name}.xaml"
            path.write_text(normalized, encoding="utf-8")
            print(f"  UPDATED  {name}")
            updated += 1
        except Exception as e:
            print(f"  ERROR    {name}: {e}")
    print(f"\n{updated} golden files updated")


def run_tests(verbose: bool = False) -> tuple[int, int]:
    """Run snapshot comparison tests. Returns (passed, failed)."""
    passed = 0
    failed = 0

    for name, spec in sorted(SPECS.items()):
        if name in SKIP_SPECS:
            continue

        gp = golden_path(name)
        if not gp.exists():
            print(f"  FAIL  {name} — golden file not found: {gp.name}")
            print(f"         Run with --update to generate golden files")
            failed += 1
            continue

        try:
            actual = generate_and_normalize(spec)
        except Exception as e:
            print(f"  FAIL  {name} — generation error: {e}")
            failed += 1
            continue

        expected = gp.read_text(encoding="utf-8")

        if actual == expected:
            print(f"  PASS  {name}")
            passed += 1
        else:
            print(f"  FAIL  {name} — output differs from golden file")
            if verbose:
                diff = difflib.unified_diff(
                    expected.splitlines(keepends=True),
                    actual.splitlines(keepends=True),
                    fromfile=f"golden/{name}.xaml",
                    tofile=f"actual/{name}.xaml",
                    n=3,
                )
                diff_lines = list(diff)
                # Show first 30 diff lines to avoid flooding
                for line in diff_lines[:30]:
                    print(f"    {line}", end="")
                if len(diff_lines) > 30:
                    print(f"    ... ({len(diff_lines) - 30} more diff lines)")
            failed += 1

    return passed, failed


def main():
    if "--update" in sys.argv:
        print("Updating golden snapshot files...\n")
        update_golden_files()
        return

    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    specs_to_test = len(SPECS) - len(SKIP_SPECS)
    print(f"Running {specs_to_test} snapshot tests...\n")

    passed, failed = run_tests(verbose=verbose)
    total = passed + failed

    print(f"\n{'='*50}")
    print(f"SNAPSHOT TESTS: {passed}/{total} passed, {failed} failed")
    print(f"{'='*50}")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
