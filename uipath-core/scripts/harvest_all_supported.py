#!/usr/bin/env python3
"""Bulk harvest orchestrator — every supported (package, version) pair.

Walks every (band, package) -> profile_version mapping registered in
version_band.BAND_PROFILE_VERSIONS plus any plugin-registered band mappings
(via plugin_loader.get_band_profile_mappings()), filters to bands >= 25, and
shells out to harvest_studio_xaml.py --discover for each unique pair.

Per-pair invocation uses the existing worker, which:
  - filters out prerelease versions when resolving the concrete NuGet version
    (stable-only policy; see policy_stable_only_harvests memory)
  - merges incrementally into the existing index.json (preserves prior `ok`
    activities, retries `error`/`unresolved` ones)

Prerequisites: same as harvest_studio_xaml.py
  - @uipath/cli installed (npm i -g @uipath/cli)
  - UiPath Studio Desktop installed locally
  - Studio running (or omit --no-start-studio so each invocation can start it)

Usage:
    python harvest_all_supported.py --list-only
    python harvest_all_supported.py --bands 25,26
    python harvest_all_supported.py --packages UiPath.Mail.Activities
    python harvest_all_supported.py --no-start-studio --summary-out my-summary.json

Output:
    Per pair: uipath-core/references/studio-ground-truth/<package>/<version>/
    Summary:  uipath-core/references/studio-ground-truth/_bulk_summary.json
"""

import argparse
import json
import subprocess
import sys
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
GROUND_TRUTH_DIR = REPO_ROOT / "uipath-core" / "references" / "studio-ground-truth"
WORKER = SCRIPTS_DIR / "harvest_studio_xaml.py"
DEFAULT_SUMMARY_PATH = GROUND_TRUTH_DIR / "_bulk_summary.json"

# Ensure local imports resolve when invoked as a script
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from version_band import BAND_PROFILE_VERSIONS  # noqa: E402
from plugin_loader import get_band_profile_mappings, load_plugins  # noqa: E402

MIN_BAND = 25
PER_PAIR_TIMEOUT_SECS = 3600
STDERR_TAIL_LINES = 40

# Studio's editor processes (leave Assistant/Updater/Service untouched — those
# are launchers/daemons that the CLI needs to spawn Studio).
STUDIO_EDITOR_PROCESSES = ("UiPath.Studio.Helm", "UiPath.Studio", "UiPath.UIAutomation")
STUDIO_KILL_SETTLE_SECS = 3


def _build_registry() -> dict[str, dict[str, str | None]]:
    """Merge core + plugin band->package->profile_version mappings."""
    load_plugins()
    merged: dict[str, dict[str, str | None]] = {
        band: dict(pkgs) for band, pkgs in BAND_PROFILE_VERSIONS.items()
    }
    for band, mapping in get_band_profile_mappings().items():
        merged.setdefault(band, {}).update(mapping)
    return merged


def _enumerate_pairs(
    registry: dict[str, dict[str, str | None]],
    band_filter: set[str] | None,
    package_filter: set[str] | None,
) -> list[tuple[str, str, list[str]]]:
    """Return [(package, profile_version, [bands])] for every unique pair.

    Bands < MIN_BAND are skipped. Pairs whose profile_version is None are
    skipped. Same (package, version) seen across multiple bands is collapsed
    to a single entry, with the bands list for reporting.
    """
    pair_to_bands: dict[tuple[str, str], list[str]] = {}
    for band, mapping in registry.items():
        if not band.isdigit() or int(band) < MIN_BAND:
            continue
        if band_filter and band not in band_filter:
            continue
        for pkg, ver in mapping.items():
            if ver is None:
                continue
            if package_filter and pkg not in package_filter:
                continue
            pair_to_bands.setdefault((pkg, ver), []).append(band)
    return sorted(
        ((pkg, ver, sorted(bands)) for (pkg, ver), bands in pair_to_bands.items()),
        key=lambda t: (t[0], t[1]),
    )


def _read_index(pkg: str, ver: str) -> dict | None:
    path = GROUND_TRUTH_DIR / pkg / ver / "index.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _activity_status_counts(index: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in (index.get("activities") or {}).values():
        status = (entry or {}).get("status") or "unknown"
        counts[status] = counts.get(status, 0) + 1
    return counts


def _kill_studio_editor() -> int:
    """Kill Studio editor processes via PowerShell. Returns count terminated.

    Targets STUDIO_EDITOR_PROCESSES only — Assistant, Updater, Helm-spawn
    daemons, and the UserHost services are intentionally left running so the
    CLI's next `uip rpa start-studio` call can re-launch a fresh editor bound
    to the new project.
    """
    names = ",".join(f"'{n}'" for n in STUDIO_EDITOR_PROCESSES)
    ps_cmd = (
        f"$names = @({names});"
        "$procs = Get-Process -ErrorAction SilentlyContinue | "
        "  Where-Object { $names -contains $_.ProcessName };"
        "$count = ($procs | Measure-Object).Count;"
        "if ($count -gt 0) { $procs | Stop-Process -Force -Confirm:$false "
        "  -ErrorAction SilentlyContinue };"
        "Write-Output $count"
    )
    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=30,
            encoding="utf-8", errors="replace",
        )
        killed = int((proc.stdout or "0").strip() or "0")
    except (subprocess.TimeoutExpired, ValueError, OSError):
        killed = 0
    if killed:
        time.sleep(STUDIO_KILL_SETTLE_SECS)
    return killed


def _harvest_one(
    pkg: str, ver: str, *, no_start_studio: bool
) -> tuple[int, str]:
    argv = [
        sys.executable,
        str(WORKER),
        "--package", pkg,
        "--version", ver,
        "--discover",
    ]
    if no_start_studio:
        argv.append("--no-start-studio")
    try:
        proc = subprocess.run(
            argv,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=PER_PAIR_TIMEOUT_SECS,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        return 124, f"TIMEOUT after {PER_PAIR_TIMEOUT_SECS}s"
    tail_src = proc.stderr or proc.stdout or ""
    tail = "\n".join(deque(tail_src.splitlines(), maxlen=STDERR_TAIL_LINES))
    return proc.returncode, tail


def _write_summary(summary: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--list-only", action="store_true",
                        help="Print enumerated pairs and exit")
    parser.add_argument("--bands", help="Comma-separated band whitelist (e.g. '25,26')")
    parser.add_argument("--packages", help="Comma-separated package whitelist")
    parser.add_argument("--no-start-studio", action="store_true",
                        help="Pass --no-start-studio to each worker invocation")
    parser.add_argument("--restart-between-pairs", action="store_true",
                        help="Kill UiPath.Studio.Helm/Studio/UIAutomation between "
                             "pairs and let the worker re-launch Studio. EXPERIMENTAL: "
                             "currently broken because `uip rpa start-studio` cannot "
                             "cold-launch Studio; only enable if you have an external "
                             "supervisor that brings Studio back up after the kill.")
    parser.add_argument("--summary-out", default=str(DEFAULT_SUMMARY_PATH),
                        help=f"Where to write the run summary (default: {DEFAULT_SUMMARY_PATH})")
    args = parser.parse_args()

    band_filter = (
        {b.strip() for b in args.bands.split(",") if b.strip()}
        if args.bands else None
    )
    package_filter = (
        {p.strip() for p in args.packages.split(",") if p.strip()}
        if args.packages else None
    )

    registry = _build_registry()
    pairs = _enumerate_pairs(registry, band_filter, package_filter)

    if not pairs:
        print("No pairs matched the filters.", file=sys.stderr)
        return 2

    print(f"Enumerated {len(pairs)} unique (package, version) pair(s):")
    for pkg, ver, bands in pairs:
        idx = _read_index(pkg, ver)
        if idx:
            counts = _activity_status_counts(idx)
            counts_str = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
            existing = f"  [existing: {counts_str}]"
        else:
            existing = "  [no prior harvest]"
        print(f"  - {pkg}@{ver}  bands={','.join(bands)}{existing}")

    if args.list_only:
        return 0

    summary_path = Path(args.summary_out).resolve()
    summary: dict = {
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "finished_at": None,
        "total_pairs": len(pairs),
        "succeeded": [],
        "failed": [],
    }
    interrupted = False

    restart_between = args.restart_between_pairs and not args.no_start_studio

    try:
        for n, (pkg, ver, bands) in enumerate(pairs, start=1):
            if n > 1 and restart_between:
                killed = _kill_studio_editor()
                print(f"\n[restart] killed {killed} Studio editor process(es); "
                      f"worker will re-launch")
            print(f"\n[{n}/{len(pairs)}] {pkg}@{ver} (bands {','.join(bands)})")
            rc, tail = _harvest_one(pkg, ver, no_start_studio=args.no_start_studio)
            if rc == 0:
                idx = _read_index(pkg, ver) or {}
                concrete = idx.get("concrete_version")
                counts = _activity_status_counts(idx)
                summary["succeeded"].append({
                    "package": pkg,
                    "version": ver,
                    "bands": bands,
                    "concrete_version": concrete,
                    "activity_counts": counts,
                })
                ok = counts.get("ok", 0)
                total = sum(counts.values())
                print(f"  -> ok ({ok}/{total} activities, concrete={concrete})")
            else:
                summary["failed"].append({
                    "package": pkg,
                    "version": ver,
                    "bands": bands,
                    "exit_code": rc,
                    "stderr_tail": tail,
                })
                print(f"  -> FAILED (rc={rc}); see summary for tail")
    except KeyboardInterrupt:
        interrupted = True
        print("\n[KeyboardInterrupt] Flushing partial summary...", file=sys.stderr)
    finally:
        summary["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if interrupted:
            summary["interrupted"] = True
        _write_summary(summary, summary_path)
        print(f"\nSummary written: {summary_path}")
        print(f"  succeeded: {len(summary['succeeded'])}")
        print(f"  failed:    {len(summary['failed'])}")

    if interrupted:
        return 130
    return 0 if not summary["failed"] else 1


if __name__ == "__main__":
    sys.exit(main())
