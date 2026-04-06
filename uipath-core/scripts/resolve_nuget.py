#!/usr/bin/env python3
"""Resolve latest stable versions for UiPath NuGet packages.

Queries the UiPath Official NuGet feed (Azure DevOps) and returns
the latest stable version for each requested package. Filters out
all prerelease versions (-preview, -beta, -rc, -alpha, etc.).

Usage:
    # Resolve specific packages
    python3 resolve_nuget.py UiPath.System.Activities UiPath.Excel.Activities

    # Resolve and output as --deps format for scaffold_project.py
    python3 resolve_nuget.py --deps UiPath.System.Activities UiPath.Excel.Activities

    # Add/update a dependency in an existing project
    python3 resolve_nuget.py --add /path/to/project UiPath.UIAutomation.Activities

    # Add multiple dependencies at once
    python3 resolve_nuget.py --add /path/to/project UiPath.Excel.Activities UiPath.Mail.Activities

    # Validate a project.json file (check all dependencies exist)
    python3 resolve_nuget.py --validate /path/to/project.json

    # Resolve all common packages
    python3 resolve_nuget.py --all

CRITICAL: Different UiPath packages use DIFFERENT version schemes!
    - UiPath.System.Activities, UiPath.UIAutomation.Activities, UiPath.Testing.Activities
      → Year-based: 25.x.x, 24.x.x
    - UiPath.Excel.Activities, UiPath.PDF.Activities,
      UiPath.Mail.Activities, UiPath.WebAPI.Activities
      → Independent: 3.x.x, 2.x.x, 1.x.x

WARNING: The package is called UiPath.WebAPI.Activities (NOT UiPath.Web.Activities).
         UiPath.Web.Activities does NOT exist on any NuGet feed.

NEVER assume version numbers. ALWAYS query the feed.
"""

import json
import sys
import urllib.request
import urllib.error
import argparse
import re
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

NUGET_FEED = (
    "https://pkgs.dev.azure.com/uipath/"
    "5b98d55c-1b14-4a03-893f-7a59746f1246/"
    "_packaging/1c781268-d43d-45ab-9dfc-0151a1c740b7/"
    "nuget/v3/flat2/{pkg}/index.json"
)

COMMON_PACKAGES = [
    "UiPath.System.Activities",
    "UiPath.UIAutomation.Activities",
    "UiPath.Excel.Activities",
    "UiPath.Testing.Activities",
    "UiPath.Mail.Activities",
    "UiPath.PDF.Activities",
    "UiPath.WebAPI.Activities",        # NOT Web.Activities (doesn't exist)
    "UiPath.Database.Activities",
]

# Merge plugin-provided packages (e.g. Tasks Persistence + FormActivityLibrary)
try:
    from plugin_loader import load_plugins, get_common_packages
    load_plugins()
    COMMON_PACKAGES.extend(get_common_packages())
except ImportError:
    pass

# Common wrong package names → correct names (auto-corrected with warning)
PACKAGE_ALIASES = {
    "UiPath.Web.Activities":               "UiPath.WebAPI.Activities",           # Web.Activities doesn't exist on NuGet
    "UiPath.OCR.Activities":               None,                                  # Deprecated — Tesseract is in UIAutomation.Activities
    "UiPath.CloudService.Activities":       None,                                 # Doesn't exist, remove silently
}

# Timeout for HTTP requests (seconds)
TIMEOUT = 15


def _semver_key(v):
    """Sort key for semver strings — split on dots, parse as ints."""
    parts = []
    for x in v.split("."):
        try:
            parts.append(int(x))
        except ValueError:
            parts.append(0)
    return tuple(parts)


# File-based cache — avoids redundant HTTP calls during multi-step generation
CACHE_DIR = Path.home() / ".uipath-core"
CACHE_FILE = CACHE_DIR / "nuget_cache.json"
CACHE_TTL_HOURS = 24


def _load_cache() -> dict:
    """Load cache from disk. Returns {package_id: {"version": str, "ts": float}}."""
    if not CACHE_FILE.exists():
        return {}
    try:
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cache(cache: dict) -> None:
    """Write cache to disk."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, indent=2), encoding="utf-8")


def _cache_get(package_id: str) -> str | None:
    """Return cached version if still valid, else None."""
    import time
    cache = _load_cache()
    entry = cache.get(package_id.lower())
    if not entry:
        return None
    age_hours = (time.time() - entry.get("ts", 0)) / 3600
    if age_hours > CACHE_TTL_HOURS:
        return None
    return entry.get("version")


def _cache_put(package_id: str, version: str) -> None:
    """Store resolved version in cache."""
    import time
    cache = _load_cache()
    cache[package_id.lower()] = {"version": version, "ts": time.time()}
    _save_cache(cache)


def fetch_latest_stable(package_id: str) -> tuple[str | None, str | None]:
    """Fetch the latest stable version for a NuGet package.
    
    Uses file-based cache (24h TTL) to avoid redundant HTTP calls.
    Returns: (version, error_message)
    """
    # Check cache first
    cached = _cache_get(package_id)
    if cached:
        return cached, None

    url = NUGET_FEED.format(pkg=package_id.lower())
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None, f"package not found (404)"
        return None, f"HTTP {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return None, f"network error: {e.reason}"
    except Exception as e:
        return None, f"error: {e}"

    versions = data.get("versions", [])
    if not versions:
        return None, "no versions found"

    # Filter out prerelease versions (contain '-')
    stable = [v for v in versions if "-" not in v]
    if not stable:
        return None, f"no stable versions (all {len(versions)} are prerelease)"

    stable.sort(key=_semver_key)
    version = stable[-1]

    # Cache the result
    _cache_put(package_id, version)

    return version, None


def resolve_packages(package_ids: list[str]) -> dict[str, str]:
    """Resolve latest stable versions for a list of packages.
    
    Returns: dict of {package_id: version} for successful resolutions.
    Prints errors to stderr for failed resolutions.
    """
    results = {}
    for pkg in package_ids:
        version, error = fetch_latest_stable(pkg)
        if version:
            results[pkg] = version
            print(f"  {pkg}: {version}")
        else:
            print(f"  {pkg}: ERROR — {error}", file=sys.stderr)
    return results


def validate_project_json(filepath: str) -> bool:
    """Validate that all dependencies in a project.json exist on the NuGet feed.
    
    Returns True if all dependencies are valid, False otherwise.
    """
    path = Path(filepath)
    if path.is_dir():
        path = path / "project.json"
    if not path.exists():
        print(f"ERROR: {filepath} not found", file=sys.stderr)
        return False

    with open(path, encoding="utf-8") as f:
        pj = json.load(f)

    deps = pj.get("dependencies", {})
    if not deps:
        print("No dependencies found in project.json")
        return True

    print(f"Validating {len(deps)} dependencies in {path.name}:")
    all_valid = True

    for pkg, version_spec in deps.items():
        # Check for known wrong package names
        if pkg in PACKAGE_ALIASES:
            replacement = PACKAGE_ALIASES[pkg]
            if replacement:
                print(f"  ✗ {pkg}: wrong package name → use '{replacement}' instead")
            else:
                print(f"  ✗ {pkg}: package doesn't exist, remove it")
            all_valid = False
            continue

        # Extract version number from brackets: "[25.12.2]" → "25.12.2"
        version = version_spec.strip("[]")
        
        # Fetch all versions for this package
        url = NUGET_FEED.format(pkg=pkg.lower())
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                print(f"  ✗ {pkg}: [{version}] — package does not exist on feed")
                all_valid = False
                continue
            print(f"  ? {pkg}: [{version}] — HTTP {e.code}", file=sys.stderr)
            continue
        except Exception as e:
            print(f"  ? {pkg}: [{version}] — {e}", file=sys.stderr)
            continue

        all_versions = data.get("versions", [])
        stable = [v for v in all_versions if "-" not in v]
        stable.sort(key=_semver_key)
        latest = stable[-1] if stable else None

        if version in all_versions:
            if version == latest:
                print(f"  ✓ {pkg}: [{version}] (latest stable)")
            elif version in stable:
                print(f"  ~ {pkg}: [{version}] (exists, latest stable is {latest})")
            else:
                print(f"  ~ {pkg}: [{version}] (prerelease — latest stable is {latest})")
        else:
            print(f"  ✗ {pkg}: [{version}] — VERSION DOES NOT EXIST")
            if latest:
                print(f"    → latest stable: {latest}")
            # Show closest versions for debugging
            close = [v for v in stable if v.startswith(version.split(".")[0] + ".")]
            if close:
                print(f"    → versions in {version.split('.')[0]}.x.x: {', '.join(close[-5:])}")
            all_valid = False

    return all_valid


def add_packages_to_project(filepath: str, package_ids: list[str]) -> bool:
    """Resolve and add/update packages in a project.json.

    Resolves the latest stable version for each package and adds or updates
    the dependency in the project.json file. Skips packages already at the
    latest version and refuses to downgrade manually pinned newer versions.

    Args:
        filepath: Path to project.json or a directory containing it.
        package_ids: List of NuGet package IDs to add/update.

    Returns True if all packages were resolved successfully.
    """
    path = Path(filepath)
    if path.is_dir():
        path = path / "project.json"
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        return False

    with open(path, encoding="utf-8") as f:
        pj = json.load(f)

    deps = pj.setdefault("dependencies", {})

    all_ok = True
    changes = []
    for pkg in package_ids:
        version, error = fetch_latest_stable(pkg)
        if not version:
            print(f"  ERROR: {pkg} — {error}", file=sys.stderr)
            all_ok = False
            continue

        new_spec = f"[{version}]"
        existing = deps.get(pkg)
        if existing:
            existing_ver = existing.strip("[]")
            if existing_ver == version:
                print(f"  {pkg}: already at [{version}] (latest stable)")
                continue
            if _semver_key(existing_ver) > _semver_key(version):
                print(f"  {pkg}: keeping [{existing_ver}] (newer than resolved {version})")
                continue
            print(f"  {pkg}: [{existing_ver}] -> [{version}]")
        else:
            print(f"  {pkg}: added [{version}]")
        deps[pkg] = new_spec
        changes.append(pkg)

    if changes:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(pj, f, indent=2)
        print(f"\nUpdated {path} ({len(changes)} package(s))")
    else:
        print(f"\nNo changes needed in {path}")

    return all_ok


def main():
    parser = argparse.ArgumentParser(
        description="Resolve latest stable UiPath NuGet package versions"
    )
    parser.add_argument("packages", nargs="*", help="Package IDs to resolve")
    parser.add_argument("--all", action="store_true",
                        help="Resolve all common UiPath packages")
    parser.add_argument("--deps", action="store_true",
                        help="Output in --deps format for scaffold_project.py")
    parser.add_argument("--add", metavar="PROJECT_DIR_OR_JSON",
                        help="Add/update resolved packages in a project.json file")
    parser.add_argument("--validate", metavar="PROJECT_JSON",
                        help="Validate dependency versions in a project.json file")
    parser.add_argument("--no-cache", action="store_true", dest="no_cache",
                        help="Bypass cache, always query the NuGet feed")
    parser.add_argument("--clear-cache", action="store_true", dest="clear_cache",
                        help="Delete the cache file and exit")
    args = parser.parse_args()

    if args.clear_cache:
        if CACHE_FILE.exists():
            CACHE_FILE.unlink()
            print(f"Cache cleared: {CACHE_FILE}")
        else:
            print("No cache file found.")
        sys.exit(0)

    if args.no_cache:
        # Temporarily set TTL to 0 so all cache lookups miss
        import builtins
        global CACHE_TTL_HOURS
        CACHE_TTL_HOURS = 0

    if args.validate:
        valid = validate_project_json(args.validate)
        sys.exit(0 if valid else 1)

    packages = COMMON_PACKAGES if args.all else args.packages
    if not packages:
        parser.print_help()
        sys.exit(1)

    # Auto-correct known wrong package names
    corrected = []
    for pkg in packages:
        if pkg in PACKAGE_ALIASES:
            replacement = PACKAGE_ALIASES[pkg]
            if replacement:
                print(f"  ⚠️  '{pkg}' → '{replacement}' (auto-corrected)")
                corrected.append(replacement)
            else:
                print(f"  ⚠️  '{pkg}' removed (package doesn't exist)")
        else:
            corrected.append(pkg)
    packages = corrected

    if not packages:
        print("No valid packages to resolve.")
        sys.exit(1)

    if args.add:
        print("Resolving and adding packages to project.json...")
        ok = add_packages_to_project(args.add, packages)
        sys.exit(0 if ok else 1)

    print("Resolving latest stable versions from UiPath NuGet feed...")
    results = resolve_packages(packages)

    if args.deps and results:
        deps_str = ",".join(f"{pkg}:[{ver}]" for pkg, ver in results.items())
        print(f"\n--deps \"{deps_str}\"")

    if len(results) < len(packages):
        sys.exit(1)


if __name__ == "__main__":
    main()
