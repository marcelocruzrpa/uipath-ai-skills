#!/usr/bin/env python3
"""Sync upstream activity docs from UiPath/skills repo.

Maintainer-only tool — pulls a normalized subset of activity docs from
https://github.com/UiPath/skills and writes them to the local mirror
at uipath-core/references/activity-docs/.

Normal runtime, tests, and generation do not depend on network access.
The mirrored docs are committed artifacts.

Usage:
    # Sync all supported packages (discovered from plugins + COMMON_PACKAGES)
    python3 sync_upstream_docs.py

    # Sync specific packages only
    python3 sync_upstream_docs.py UiPath.UIAutomation.Activities UiPath.System.Activities

    # List which packages would be synced (dry run)
    python3 sync_upstream_docs.py --dry-run

    # Force re-download even if local mirror exists
    python3 sync_upstream_docs.py --force
"""

import json
import os
import shutil
import sys
import urllib.request
import urllib.error
import zipfile
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

UPSTREAM_ZIP = "https://github.com/UiPath/skills/archive/refs/heads/main.zip"
UPSTREAM_DOCS_PREFIX = "skills-main/references/activity-docs/"


def _get_skill_root() -> Path:
    """Return the uipath-core skill root directory."""
    return Path(__file__).resolve().parent.parent


def _get_mirror_dir() -> Path:
    """Return the local mirror directory for activity docs."""
    return _get_skill_root() / "references" / "activity-docs"


def _discover_packages() -> set[str]:
    """Discover which packages to sync from plugins + COMMON_PACKAGES."""
    packages = set()

    # From resolve_nuget.py COMMON_PACKAGES
    try:
        from resolve_nuget import COMMON_PACKAGES
        packages.update(COMMON_PACKAGES)
    except ImportError:
        pass

    # From plugin-registered package dependencies
    try:
        from plugin_loader import load_plugins, get_package_dependencies
        load_plugins()
        packages.update(get_package_dependencies())
    except ImportError:
        pass

    return packages


def _download_upstream_zip(dest: Path) -> None:
    """Download the upstream repo ZIP to *dest*."""
    print(f"Downloading {UPSTREAM_ZIP} ...")
    req = urllib.request.Request(UPSTREAM_ZIP)
    with urllib.request.urlopen(req, timeout=60) as resp:
        dest.write_bytes(resp.read())
    print(f"  Downloaded {dest.stat().st_size / 1024:.0f} KB")


def sync_docs(packages: set[str] | None = None, force: bool = False,
              dry_run: bool = False) -> dict[str, list[str]]:
    """Sync activity docs from upstream for the given packages.

    Args:
        packages: Set of package names to sync. If None, auto-discovers.
        force: Re-download even if local mirror exists.
        dry_run: Print what would be synced without downloading.

    Returns:
        Dict of {package: [version_dirs_synced]} for packages that had
        upstream docs. Packages without upstream docs are skipped with
        a warning.
    """
    if packages is None:
        packages = _discover_packages()

    if dry_run:
        print("Packages that would be synced:")
        for pkg in sorted(packages):
            print(f"  {pkg}")
        return {}

    mirror_dir = _get_mirror_dir()
    results = {}

    # Download upstream ZIP to temp location
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = Path(tmpdir) / "skills-main.zip"
        _download_upstream_zip(zip_path)

        with zipfile.ZipFile(zip_path) as zf:
            # Find which packages have upstream docs
            available = set()
            for name in zf.namelist():
                if name.startswith(UPSTREAM_DOCS_PREFIX) and name.count("/") >= 4:
                    pkg = name.split("/")[3]
                    available.add(pkg)

            for pkg in sorted(packages):
                if pkg not in available:
                    print(f"  SKIP {pkg} (no upstream docs)")
                    continue

                pkg_prefix = f"{UPSTREAM_DOCS_PREFIX}{pkg}/"
                pkg_entries = [n for n in zf.namelist()
                               if n.startswith(pkg_prefix) and not n.endswith("/")]

                if not pkg_entries:
                    print(f"  SKIP {pkg} (empty upstream directory)")
                    continue

                # Determine version directories
                versions = set()
                for entry in pkg_entries:
                    parts = entry[len(pkg_prefix):].split("/")
                    if parts:
                        versions.add(parts[0])

                # Extract to local mirror
                dest_pkg_dir = mirror_dir / pkg
                if dest_pkg_dir.exists() and not force:
                    existing_versions = {d.name for d in dest_pkg_dir.iterdir() if d.is_dir()}
                    new_versions = versions - existing_versions
                    if not new_versions:
                        print(f"  OK   {pkg} (up to date: {', '.join(sorted(versions))})")
                        results[pkg] = sorted(versions)
                        continue

                # Clear and re-extract
                if dest_pkg_dir.exists():
                    shutil.rmtree(dest_pkg_dir)
                dest_pkg_dir.mkdir(parents=True, exist_ok=True)

                extracted = 0
                for entry in pkg_entries:
                    rel_path = entry[len(pkg_prefix):]
                    dest_file = dest_pkg_dir / rel_path
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    dest_file.write_bytes(zf.read(entry))
                    extracted += 1

                print(f"  SYNC {pkg} ({', '.join(sorted(versions))}) — {extracted} files")
                results[pkg] = sorted(versions)

    return results


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Sync activity docs from UiPath/skills repo"
    )
    parser.add_argument("packages", nargs="*",
                        help="Specific packages to sync (default: auto-discover)")
    parser.add_argument("--dry-run", action="store_true",
                        help="List packages without downloading")
    parser.add_argument("--force", action="store_true",
                        help="Force re-download even if local mirror exists")
    args = parser.parse_args()

    packages = set(args.packages) if args.packages else None

    try:
        results = sync_docs(packages=packages, force=args.force, dry_run=args.dry_run)
    except urllib.error.URLError as e:
        print(f"ERROR: Network error — {e.reason}", file=sys.stderr)
        print("The local mirror is unchanged. Run again when network is available.",
              file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)

    if results:
        print(f"\nSynced {len(results)} package(s) to {_get_mirror_dir()}")


if __name__ == "__main__":
    main()
