#!/usr/bin/env python3
"""Harvest canonical XAML from Studio via @uipath/cli.

For each activity in a version-profile JSON, scaffolds a temp project pinning
the requested package version, then calls `uip rpa get-default-activity-xaml`
to capture the exact XAML Studio would emit when dropping that activity onto
a workflow.

Prerequisites:
  - @uipath/cli installed     (npm i -g @uipath/cli)
  - UiPath Studio Desktop installed locally
  - One free Studio process available for IPC (this script may launch one)

Usage:
    # End-to-end (scaffold + restore + start-studio + harvest)
    python harvest_studio_xaml.py --package UiPath.UIAutomation.Activities --version 26.3
    python harvest_studio_xaml.py --package UiPath.UIAutomation.Activities --version 26.3 \
        --activities NClick,NTypeInto,NCheck

    # Reuse an existing scaffolded project (skip scaffold + restore)
    python harvest_studio_xaml.py --package UiPath.UIAutomation.Activities --version 26.3 \
        --project-dir C:\\Users\\marce\\AppData\\Local\\Temp\\uip-harvest-...

    # Skip auto-starting Studio (assume the user already started it)
    python harvest_studio_xaml.py --package ... --version ... --no-start-studio

Output: uipath-core/references/studio-ground-truth/<package>/<version>/{*.xaml, index.json}
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PROFILES_DIR = REPO_ROOT / "uipath-core" / "references" / "version-profiles"
GROUND_TRUTH_DIR = REPO_ROOT / "uipath-core" / "references" / "studio-ground-truth"

# Resolve the npm-installed `uip` shim once. On Windows it's `uip.cmd`, which
# Python's subprocess won't find without PATHEXT lookup unless we resolve it.
UIP = shutil.which("uip") or shutil.which("uip.cmd") or "uip"


def _run_uip_json(args: list[str], *, timeout: int = 120) -> dict | list | str:
    """Invoke `uip --output json ...` and return the parsed Data field."""
    cmd = [UIP, "--output", "json", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8")
    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    if proc.returncode != 0 and not stdout:
        raise RuntimeError(f"`uip {' '.join(args)}` rc={proc.returncode}: {stderr or '(no stderr)'}")
    try:
        payload = json.loads(stdout) if stdout else {}
    except json.JSONDecodeError as e:
        raise RuntimeError(f"`uip {' '.join(args)}` returned non-JSON:\n{stdout[:800]}") from e
    if payload.get("Result") not in ("Success", "Help", None):
        raise RuntimeError(
            f"`uip {' '.join(args)}` Result={payload.get('Result')} "
            f"Code={payload.get('Code')}: {json.dumps(payload.get('Data'))[:400]}"
        )
    return payload.get("Data")


def _scaffold_temp_project(package: str, version: str) -> Path:
    """Bootstrap a modern UiPath project via `uip rpa create-project`.

    Studio 26 only accepts `.uiproj` solution-format projects; legacy
    `project.json`-only projects fail with "WorkflowCompiler does not support
    Legacy projects." So we delegate scaffolding to the CLI's create-project
    command, which builds the right shape and seeds default dependencies.
    The target package is upgraded to the desired version later via
    install-or-update-packages.
    """
    parent = Path(tempfile.mkdtemp(prefix=f"uip-harvest-{package}-{version}-"))
    name = f"Harvest_{package.replace('.', '_')}_{version.replace('.', '_')}"
    data = _run_uip_json(
        ["rpa", "create-project", "--name", name, "--location", str(parent),
         "--target-framework", "Windows", "--expression-language", "VisualBasic"],
        timeout=120,
    )
    proj_dir = (data or {}).get("projectDirectory") if isinstance(data, dict) else None
    if not proj_dir:
        raise RuntimeError(f"create-project returned no projectDirectory: {data}")
    return Path(proj_dir.replace("\\", "/")).resolve()


def _resolve_concrete_version(package: str, version_prefix: str, project_dir: Path) -> str:
    """Map a profile version label (e.g. "26.3") to a concrete NuGet version
    (e.g. "26.3.5") by querying Studio's configured feeds via get-versions.
    Returns the highest stable version whose major.minor matches version_prefix.

    IMPORTANT: The project_dir must already have the target package installed
    (or at least accessible in its configured NuGet feeds) at the requested
    version band. If a mismatched project is reused (e.g. a 25.10-pinned
    project used to resolve 26.2), get-versions will only return versions
    reachable from that project's feeds and the band-match filter will raise.
    Always scaffold a fresh project for the target band before calling this.
    """
    data = _run_uip_json(
        ["rpa", "--project-dir", str(project_dir),
         "get-versions", "--package-id", package],
        timeout=120,
    )
    versions = data if isinstance(data, list) else (
        data.get("versions") or data.get("Versions") or [] if isinstance(data, dict) else []
    )
    if not versions:
        raise RuntimeError(f"get-versions returned no versions for {package}")
    # Each entry may be a string or {Version, IsPrerelease, ...}
    flat = []
    for v in versions:
        if isinstance(v, str):
            flat.append((v, "-" in v))
        elif isinstance(v, dict):
            ver = v.get("Version") or v.get("version")
            if ver:
                flat.append((ver, bool(v.get("IsPrerelease") or v.get("isPrerelease") or "-" in ver)))
    matches = [v for v, pre in flat if not pre and (v == version_prefix or v.startswith(version_prefix + "."))]
    if not matches:
        # Distinguish "prerelease only" from "absent entirely" so callers can tell
        # whether the profile was authored before the band was stable-promoted.
        pre_matches = [v for v, pre in flat if pre and (v == version_prefix or v.startswith(version_prefix + "."))]
        sample = ", ".join(v for v, _ in flat[:8])
        if pre_matches:
            raise RuntimeError(
                f"no STABLE version matching '{version_prefix}' for {package} — "
                f"found prerelease-only: {pre_matches}. "
                f"Either the profile was authored before stable release or the band "
                f"is prerelease-only on this feed. To accept prerelease builds, "
                f"pass --include-prerelease (not yet implemented)."
            )
        raise RuntimeError(
            f"no stable version matching '{version_prefix}' in {package} "
            f"(saw: {sample}). "
            f"This usually means the project at {project_dir} is pinned to a "
            f"different band. Scaffold a fresh project without --project-dir."
        )
    matches.sort(key=lambda s: tuple(int(p) if p.isdigit() else 0 for p in s.split(".")))
    return matches[-1]


def _install_package(package: str, version: str, project_dir: Path) -> None:
    """Install a single package@version into the project via Studio IPC."""
    pkg_arg = json.dumps([{"id": package, "version": version}])
    data = _run_uip_json(
        ["rpa", "--project-dir", str(project_dir),
         "install-or-update-packages", "--packages", pkg_arg],
        timeout=300,
    )
    failures = data.get("Failed") if isinstance(data, dict) else None
    if failures:
        raise RuntimeError(f"install-or-update-packages failures: {failures}")


def _short_class(class_name: str) -> str:
    """Strip assembly-qualified suffix and namespace from a className.

    Studio's find-activities returns className as
    `"Namespace.Short, Assembly, Version=..., Culture=..., PublicKeyToken=..."`.
    This returns just `Short`.
    """
    return (class_name or "").split(",", 1)[0].rsplit(".", 1)[-1]


def _fqn(class_name: str) -> str:
    """Strip the assembly-qualified suffix, returning `Namespace.Short`."""
    return (class_name or "").split(",", 1)[0].strip()


def _query_candidates(key: str, profile_meta: dict) -> list[str]:
    """Build a list of search queries likely to surface activity *key*.

    Studio's find-activities tokenizes display names. Class keys often start
    with an "N" prefix Studio strips (NClick → "Click"), and multi-word names
    split on caps — including acronym runs (NUITask → "UI Task", not "U I Task").
    """
    import re as _re
    candidates: list[str] = []
    doc = (profile_meta or {}).get("doc_name")
    if doc and doc != key:
        candidates.append(doc)

    base = key[1:] if key.startswith("N") and len(key) > 1 and key[1].isupper() else key
    candidates.append(base)

    # Split CamelCase respecting acronym runs: "UITask" -> "UI Task",
    # "TypeInto" -> "Type Into", "ApplicationCard" -> "Application Card".
    spaced = _re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", base)
    if spaced not in candidates:
        candidates.append(spaced)

    # First word only — Studio sometimes labels activities by the primary noun,
    # dropping suffixes (NApplicationCard → "Application").
    first_word = spaced.split(" ", 1)[0]
    if first_word and first_word not in candidates:
        candidates.append(first_word)

    candidates.append(key)
    seen = set()
    return [c for c in candidates if not (c in seen or seen.add(c))]


def _discover_activities_in_package(package: str, project_dir: Path) -> dict[str, str]:
    """Enumerate Studio-visible activities in *package* via many find-activities
    queries (the `*` broad query doesn't return the full catalog). Returns a
    dict of {short_class_name: fully_qualified_class_name}.
    """
    queries = list("abcdefghijklmnopqrstuvwxyz") + [
        "*", "Scope", "Get", "Set", "Read", "Write", "For", "Run",
        "Test", "Verify", "Assert", "Range", "File", "Email", "Excel",
        "Pdf", "Http", "Database", "Sql", "Table", "Dictionary", "Data",
    ]
    found: dict[str, str] = {}
    for q in queries:
        try:
            data = _run_uip_json(
                ["rpa", "--project-dir", str(project_dir),
                 "find-activities", "--query", q, "--limit", "200"],
                timeout=60,
            )
        except (RuntimeError, subprocess.TimeoutExpired):
            continue
        if not isinstance(data, list):
            continue
        for c in data:
            if c.get("packageName") != package:
                continue
            fqn = _fqn(c.get("className", ""))
            short = fqn.rsplit(".", 1)[-1]
            if short and short not in found:
                found[short] = fqn
    return found


def _resolve_class_names(
    profile_keys: list[str],
    profile_activities: dict,
    project_dir: Path,
) -> dict[str, str]:
    """Map each profile key (short class name) to its fully-qualified class name.

    Tries multiple query strategies (display-name variants) per activity and
    matches the result whose short className equals the profile key.
    """
    resolved: dict[str, str] = {}
    for key in profile_keys:
        queries = _query_candidates(key, profile_activities.get(key, {}))
        match = None
        used_query = None
        for q in queries:
            try:
                data = _run_uip_json(
                    ["rpa", "--project-dir", str(project_dir),
                     "find-activities", "--query", q, "--limit", "100"],
                    timeout=60,
                )
            except (RuntimeError, subprocess.TimeoutExpired) as e:
                print(f"  ! find-activities {key} (q={q!r}): {e}", file=sys.stderr)
                continue
            candidates = data if isinstance(data, list) else []
            match = next((c for c in candidates if _short_class(c.get("className", "")) == key), None)
            if match:
                used_query = q
                break
        if match is None:
            print(f"  ? {key}: no match across queries {queries}", file=sys.stderr)
            continue
        resolved[key] = _fqn(match["className"])
        if used_query != key:
            print(f"  . {key}: matched via query {used_query!r}")
    return resolved


def _extract_xaml(payload) -> str:
    """Pull the XAML string out of a get-default-activity-xaml response."""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        for k in ("message", "Message", "xaml", "Xaml", "content", "Content", "value", "Value"):
            v = payload.get(k)
            if isinstance(v, str) and v.strip().startswith("<"):
                return v
    raise RuntimeError(f"unexpected get-default-activity-xaml payload: {json.dumps(payload)[:400]}")


_PKG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_VER_RE = re.compile(r"^[0-9]+(\.[0-9]+){0,3}(-[A-Za-z0-9.]+)?$")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--package", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--activities", help="Comma-separated subset; defaults to all profile keys")
    parser.add_argument("--project-dir", help="Reuse an existing scaffolded project (skip scaffold + restore)")
    parser.add_argument("--no-start-studio", action="store_true",
                        help="Don't call `uip rpa start-studio` — assume Studio is already running")
    parser.add_argument("--keep-going", action="store_true",
                        help="Continue harvesting after individual activity failures (default)")
    parser.add_argument("--discover", action="store_true",
                        help="Discover the activity list via find-activities instead of reading a profile JSON")
    args = parser.parse_args()

    if not _PKG_RE.fullmatch(args.package):
        parser.error(f"--package must match {_PKG_RE.pattern}, got {args.package!r}")
    if not _VER_RE.fullmatch(args.version):
        parser.error(f"--version must match {_VER_RE.pattern}, got {args.version!r}")

    profile_path = PROFILES_DIR / args.package / f"{args.version}.json"
    profile_activities = {}
    if profile_path.exists():
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        profile_activities = profile.get("activities", {})
    else:
        # No exact-version profile — fall back to any same-package profile so we
        # can still resolve doc_name (Studio display name) per activity for the
        # find-activities query. Activity catalog is mostly stable across versions.
        pkg_dir = PROFILES_DIR / args.package
        if pkg_dir.exists():
            for alt in sorted(pkg_dir.glob("*.json")):
                profile_activities = json.loads(alt.read_text(encoding="utf-8")).get("activities", {})
                if profile_activities:
                    print(f"  (no profile for {args.version}; using {alt.name} for doc_name lookup)")
                    break
        if not profile_activities and not args.activities and not args.discover:
            print(f"ERROR: no profile at {profile_path} — pass --activities or --discover", file=sys.stderr)
            return 2

    if args.activities:
        keys = [k.strip() for k in args.activities.split(",") if k.strip()]
        if profile_activities:
            missing = [k for k in keys if k not in profile_activities]
            if missing:
                print(f"WARNING: activities not in profile (will harvest anyway): {missing}", file=sys.stderr)
    else:
        keys = list(profile_activities.keys())

    if args.project_dir:
        project_dir = Path(args.project_dir).resolve()
        if not (project_dir / "project.json").exists():
            print(f"ERROR: no project.json at {project_dir}", file=sys.stderr)
            return 2
        print(f"Reusing project: {project_dir}")
    else:
        print(f"Scaffolding temp project for {args.package}@{args.version}...")
        project_dir = _scaffold_temp_project(args.package, args.version)
        print(f"  -> {project_dir}")

    if not args.no_start_studio:
        print("Ensuring Studio is running (this may open a Studio window)...")
        try:
            _run_uip_json(
                ["rpa", "--project-dir", str(project_dir), "start-studio"],
                timeout=300,
            )
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            print(f"ERROR: start-studio failed: {e}", file=sys.stderr)
            print("Hint: rerun with --no-start-studio after starting Studio yourself.", file=sys.stderr)
            return 3

    if not args.project_dir:
        print(f"Resolving concrete version for {args.package} matching '{args.version}'...")
        try:
            concrete = _resolve_concrete_version(args.package, args.version, project_dir)
            print(f"  -> {concrete}")
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            print(f"ERROR: version resolution failed: {e}", file=sys.stderr)
            return 3
        print(f"Installing {args.package}@{concrete} via Studio IPC...")
        try:
            _install_package(args.package, concrete, project_dir)
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            print(f"ERROR: install failed: {e}", file=sys.stderr)
            return 3
    else:
        # --project-dir reuse: read the actual installed version from the
        # project's dependency list so index.json records what was really
        # harvested, not the caller's profile label.
        pj = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
        spec = pj.get("dependencies", {}).get(args.package, "")
        concrete = spec.strip("[]") or args.version
        # Guard: warn loudly when the installed version does not match the
        # requested version prefix. This catches the case where a pre-existing
        # project (pinned to a different band) is incorrectly reused.
        if concrete and not (
            concrete == args.version or concrete.startswith(args.version + ".")
        ):
            print(
                f"WARNING: --project-dir has {args.package}@{concrete!r} installed "
                f"but requested version prefix is {args.version!r}. "
                f"The harvest XAML and index.json will reflect {concrete!r}, "
                f"not {args.version!r}. Re-run without --project-dir to scaffold "
                f"a fresh project pinned to {args.version!r}.",
                file=sys.stderr,
            )

    if args.discover:
        print(f"\nDiscovering activities in {args.package} via find-activities...")
        fqn_map = _discover_activities_in_package(args.package, project_dir)
        keys = sorted(fqn_map.keys())
        print(f"  -> discovered {len(fqn_map)} activities")
    else:
        print(f"\nResolving full class names for {len(keys)} activities...")
        fqn_map = _resolve_class_names(keys, profile_activities, project_dir)
    if not fqn_map:
        print("ERROR: no activities resolved — Studio may not be reachable", file=sys.stderr)
        return 3

    out_dir = GROUND_TRUTH_DIR / args.package / args.version
    out_dir_resolved = out_dir.resolve()
    ground_truth_resolved = GROUND_TRUTH_DIR.resolve()
    if not out_dir_resolved.is_relative_to(ground_truth_resolved):
        raise ValueError(f"Refusing to write outside ground-truth dir: {out_dir_resolved}")
    out_dir.mkdir(parents=True, exist_ok=True)
    existing_index_path = out_dir / "index.json"
    existing_activities = {}
    if existing_index_path.exists():
        try:
            existing_activities = json.loads(existing_index_path.read_text(encoding="utf-8")).get("activities", {})
        except json.JSONDecodeError:
            pass
    # NOTE: do not persist `project_dir` — it leaks local temp paths (user
    # home, harvest-run nonces) into a checked-in artifact. If we need a
    # harvest-audit trail later, write it to a sibling *.local.json that is
    # gitignored.
    index = {
        "package": args.package,
        "version": args.version,
        "concrete_version": concrete,
        "harvested_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "activities": dict(existing_activities),
    }

    print(f"Harvesting {len(fqn_map)} of {len(keys)} requested activities...")
    for key in keys:
        fqn = fqn_map.get(key)
        if not fqn:
            index["activities"][key] = {"status": "unresolved"}
            continue
        try:
            data = _run_uip_json(
                ["rpa", "--project-dir", str(project_dir),
                 "get-default-activity-xaml", "--activity-class-name", fqn],
                timeout=60,
            )
            xaml = _extract_xaml(data)
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            print(f"  x {key}: {e}", file=sys.stderr)
            index["activities"][key] = {"status": "error", "error": str(e), "class_name": fqn}
            continue
        if not re.fullmatch(r"[A-Za-z0-9_]+", key):
            continue  # skip keys that would traverse or be weird filenames
        (out_dir / f"{key}.xaml").write_text(xaml, encoding="utf-8")
        index["activities"][key] = {"status": "ok", "class_name": fqn, "size": len(xaml)}
        print(f"  ok {key} ({fqn}) -> {key}.xaml ({len(xaml):,} chars)")

    (out_dir / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(f"\nWrote {out_dir}\\index.json")
    _resolved = Path(project_dir).resolve()
    _tmp_root = Path(tempfile.gettempdir()).resolve()
    try:
        _in_tmp = _resolved.is_relative_to(_tmp_root)
    except AttributeError:
        _in_tmp = str(_resolved).startswith(str(_tmp_root))
    if _in_tmp:
        print(f"\nTemp project kept at: {project_dir}")
        print(f"To clean up: python -c \"import shutil; shutil.rmtree(r'{project_dir}')\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
