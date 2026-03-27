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
import re
import shutil
import sys
import urllib.request
import urllib.error
import zipfile
import tempfile
from pathlib import Path

# Whitelist pattern for package/version names to prevent path traversal
_SAFE_NAME_RE = re.compile(r'^[A-Za-z0-9._-]+$')

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

UPSTREAM_ZIP = "https://github.com/UiPath/skills/archive/refs/heads/main.zip"
UPSTREAM_DOCS_PREFIX = "skills-main/references/activity-docs/"


def _get_skill_root() -> Path:
    """Return the uipath-core skill root directory."""
    return Path(__file__).resolve().parent.parent


def _get_profiles_dir() -> Path:
    """Return the directory for checked-in version profile JSON."""
    return _get_skill_root() / "references" / "version-profiles"


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
    """Download upstream docs, extract version profiles, write JSON.

    Raw markdown docs are transient — downloaded to a temp directory,
    parsed by discover_version_profile.py, and discarded. Only the
    extracted profile JSON is written to references/version-profiles/.

    Args:
        packages: Set of package names to sync. If None, auto-discovers.
        force: Re-extract even if profile JSON already exists.
        dry_run: Print what would be synced without downloading.

    Returns:
        Dict of {package: [versions_profiled]} for packages that had
        upstream docs.
    """
    if packages is None:
        packages = _discover_packages()

    if dry_run:
        print("Packages that would be synced:")
        for pkg in sorted(packages):
            print(f"  {pkg}")
        return {}

    profiles_dir = _get_profiles_dir()
    results = {}

    # Download upstream ZIP to temp location
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = Path(tmpdir) / "skills-main.zip"
        _download_upstream_zip(zip_path)

        # Import profile extractor
        from discover_version_profile import extract_profile

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

                # Check if profiles already exist
                pkg_profiles_dir = profiles_dir / pkg
                if pkg_profiles_dir.exists() and not force:
                    existing = {p.stem for p in pkg_profiles_dir.glob("*.json")}
                    if versions <= existing:
                        print(f"  OK   {pkg} (profiles up to date: {', '.join(sorted(versions))})")
                        results[pkg] = sorted(versions)
                        continue

                # Extract docs to temp, parse, write profile JSON
                for ver in sorted(versions):
                    # Validate package/version names to prevent path traversal
                    if not _SAFE_NAME_RE.match(pkg) or not _SAFE_NAME_RE.match(ver):
                        print(f"  SKIP {pkg}/{ver} (invalid characters in name)",
                              file=sys.stderr)
                        continue

                    ver_prefix = f"{pkg_prefix}{ver}/"
                    ver_entries = [n for n in pkg_entries if n.startswith(ver_prefix)]

                    # Extract to temp subdirectory
                    tmp_ver_dir = Path(tmpdir) / "docs" / pkg / ver
                    for entry in ver_entries:
                        rel = entry[len(ver_prefix):]
                        dest = tmp_ver_dir / rel
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_bytes(zf.read(entry))

                    # Extract profile
                    profile = extract_profile(tmp_ver_dir)

                    # Write profile JSON
                    pkg_profiles_dir.mkdir(parents=True, exist_ok=True)
                    profile_path = pkg_profiles_dir / f"{ver}.json"
                    with open(profile_path, "w", encoding="utf-8") as f:
                        json.dump(profile, f, indent=2, sort_keys=True)

                print(f"  SYNC {pkg} ({', '.join(sorted(versions))}) — profiles extracted")
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
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        reason = getattr(e, 'reason', None) or str(e)
        print(f"ERROR: Network error — {reason}", file=sys.stderr)
        print("The local mirror is unchanged. Run again when network is available.",
              file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)

    if results:
        print(f"\nExtracted profiles for {len(results)} package(s) to {_get_profiles_dir()}")


if __name__ == "__main__":
    main()
