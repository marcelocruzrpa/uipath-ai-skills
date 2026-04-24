#!/usr/bin/env python3
"""Battle-test Studio IPC: validate every activity xaml_template via Studio.

For each version-profile JSON under references/version-profiles/, scaffold a
temporary UiPath project (one per package), then for each activity that has a
xaml_template call `uip rpa get-errors` to let Studio compile the wrapper XAML
and report any errors/warnings.

Usage:
    python battle_test_studio.py
    python battle_test_studio.py --package UiPath.UIAutomation.Activities
    python battle_test_studio.py --package UiPath.UIAutomation.Activities --version 25.10

Output:
    Streams per-activity progress to stdout.
    Writes JSON + Markdown report to .omc/analysis/battle-test-studio.md
"""

import argparse
import json
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
PROFILES_DIR = REPO_ROOT / "uipath-core" / "references" / "version-profiles"
ANALYSIS_DIR = REPO_ROOT / ".omc" / "analysis"

sys.path.insert(0, str(SCRIPT_DIR))
from harvest_studio_xaml import _run_uip_json  # noqa: E402

# ---------------------------------------------------------------------------
# Minimal XAML wrapper that Studio accepts for activity validation.
# Includes the most common namespaces across all packages.
# ---------------------------------------------------------------------------
WRAPPER_TEMPLATE = """\
<Activity mc:Ignorable="sap sap2010 sads" x:Class="Main"
  xmlns="http://schemas.microsoft.com/netfx/2009/xaml/activities"
  xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"
  xmlns:sap="http://schemas.microsoft.com/netfx/2009/xaml/activities/presentation"
  xmlns:sap2010="http://schemas.microsoft.com/netfx/2010/xaml/activities/presentation"
  xmlns:sads="http://schemas.microsoft.com/netfx/2010/xaml/activities/debugger"
  xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
  xmlns:sa="clr-namespace:System.Activities;assembly=System.Activities"
  xmlns:scg="clr-namespace:System.Collections.Generic;assembly=netstandard"
  xmlns:uix="http://schemas.uipath.com/workflow/activities/uiautomationnext"
  xmlns:ui="http://schemas.uipath.com/workflow/activities"
  xmlns:uta="http://schemas.uipath.com/testing">
  <Sequence DisplayName="Battle" sap2010:WorkflowViewState.IdRef="Seq_1">
    {TEMPLATE_HERE}
  </Sequence>
</Activity>"""


def _ensure_studio_running() -> None:
    """Ensure Studio is running. Calls start-studio and retries if needed."""
    try:
        _run_uip_json(["rpa", "start-studio"], timeout=60)
    except Exception as e:
        print(f"  [warn] start-studio attempt: {e}", file=sys.stderr)


def _scaffold_project(slug: str) -> Path:
    """Scaffold a fresh project for a package slug in a temp directory."""
    parent = tempfile.mkdtemp(prefix=f"uip-battle-{slug}-")
    name = f"BattleTest_{slug}"
    data = _run_uip_json(
        [
            "rpa", "create-project",
            "--name", name,
            "--location", parent,
            "--target-framework", "Windows",
            "--expression-language", "VisualBasic",
        ],
        timeout=180,
    )
    proj_dir = (data or {}).get("projectDirectory") if isinstance(data, dict) else None
    if not proj_dir:
        raise RuntimeError(f"create-project returned no projectDirectory: {data}")
    return Path(proj_dir.replace("\\", "/")).resolve()


def _validate_activity(
    proj_dir: Path,
    activity_name: str,
    xaml_template: str,
    *,
    studio_retry_done: bool = False,
) -> dict:
    """Write wrapper XAML and call get-errors. Returns classification dict."""
    main_xaml = proj_dir / "Main.xaml"
    wrapped = WRAPPER_TEMPLATE.replace("{TEMPLATE_HERE}", xaml_template)
    main_xaml.write_text(wrapped, encoding="utf-8")
    try:
        resp = _run_uip_json(
            [
                "rpa", "--project-dir", str(proj_dir),
                "get-errors",
                "--file-path", "Main.xaml",
                "--min-severity", "warning",
            ],
            timeout=120,
        )
    except Exception as e:
        err_str = str(e).lower()
        if "studio not running" in err_str and not studio_retry_done:
            print("  [retry] Studio not running — starting Studio and retrying once…", file=sys.stderr)
            _ensure_studio_running()
            return _validate_activity(proj_dir, activity_name, xaml_template, studio_retry_done=True)
        return {
            "errors": -1,
            "warnings": -1,
            "top": f"ipc-error: {str(e)[:120]}",
            "classification": "ipc-error",
        }

    diagnostics: list = []
    if isinstance(resp, dict):
        diagnostics = resp.get("diagnostics", [])
    elif isinstance(resp, list):
        diagnostics = resp

    errs = [d for d in diagnostics if d.get("severity") == "Error"]
    warns = [d for d in diagnostics if d.get("severity") == "Warning"]
    top_msg = (errs[0]["message"] if errs else (warns[0]["message"] if warns else "")).strip()[:120]

    if not errs and not warns:
        cls = "clean"
    elif errs:
        msg = top_msg.lower()
        if any(kw in msg for kw in ("scope", "parent", "must be inside", "container", "within")):
            cls = "scope-required"
        else:
            cls = "unexpected-error"
    else:
        cls = "warn-only"

    return {
        "errors": len(errs),
        "warnings": len(warns),
        "top": top_msg,
        "classification": cls,
    }


def _run_sweep(package_filter: str | None, version_filter: str | None) -> list[dict]:
    """Run the full sweep and return a list of result dicts."""
    results: list[dict] = []

    # One project per package (shared across versions of that package)
    project_cache: dict[str, Path] = {}

    for pkg_dir in sorted(PROFILES_DIR.iterdir()):
        if not pkg_dir.is_dir():
            continue
        if package_filter and pkg_dir.name != package_filter:
            continue

        slug = pkg_dir.name.replace(".", "_")

        for profile_file in sorted(pkg_dir.glob("*.json")):
            ver = profile_file.stem
            if version_filter and ver != version_filter:
                continue

            profile = json.loads(profile_file.read_text(encoding="utf-8"))
            activities = profile.get("activities", {})

            if not activities:
                print(f"  [skip] {pkg_dir.name} {ver}: no activities in profile", flush=True)
                continue

            # Scaffold project once per package (reuse across versions)
            if slug not in project_cache:
                print(f"Scaffolding project for {pkg_dir.name}…", flush=True)
                try:
                    project_cache[slug] = _scaffold_project(slug)
                    print(f"  Project: {project_cache[slug]}", flush=True)
                except Exception as e:
                    print(f"  [error] scaffold failed for {pkg_dir.name}: {e}", file=sys.stderr, flush=True)
                    # Mark all activities in this profile as ipc-error
                    for name in sorted(activities):
                        results.append({
                            "pkg": pkg_dir.name,
                            "ver": ver,
                            "act": name,
                            "classification": "ipc-error",
                            "errors": -1,
                            "warnings": -1,
                            "top": f"scaffold-failed: {str(e)[:80]}",
                        })
                    continue

            proj_dir = project_cache[slug]
            print(f"Package {pkg_dir.name} v{ver}: {len(activities)} activities", flush=True)

            for name, entry in sorted(activities.items()):
                tmpl = entry.get("xaml_template")
                unsupported = entry.get("_unsupported_reason")

                if not tmpl or unsupported:
                    reason = "no-template" if not tmpl else f"unsupported:{unsupported}"
                    results.append({
                        "pkg": pkg_dir.name,
                        "ver": ver,
                        "act": name,
                        "classification": "skipped",
                        "errors": 0,
                        "warnings": 0,
                        "top": reason,
                    })
                    print(f"  {name}: skipped ({reason})", flush=True)
                    continue

                r = _validate_activity(proj_dir, name, tmpl)
                r.update({"pkg": pkg_dir.name, "ver": ver, "act": name})
                results.append(r)
                print(
                    f"  {name}: {r['classification']} "
                    f"(E={r['errors']}, W={r['warnings']})"
                    + (f" — {r['top'][:80]}" if r["top"] else ""),
                    flush=True,
                )

    return results


def _build_report(results: list[dict], elapsed_sec: float) -> str:
    """Build the Markdown report from results."""
    total = len(results)
    by_cls: defaultdict[str, int] = defaultdict(int)
    by_pkg: defaultdict[str, defaultdict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in results:
        by_cls[r["classification"]] += 1
        by_pkg[r["pkg"]][r["classification"]] += 1

    unexpected = [r for r in results if r["classification"] == "unexpected-error"]
    top10 = unexpected[:10]

    lines: list[str] = []
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines.append(f"# Studio IPC Battle-Test Report")
    lines.append(f"")
    lines.append(f"Generated: {ts}  ")
    lines.append(f"Elapsed: {elapsed_sec:.1f}s")
    lines.append(f"")
    lines.append(f"## Summary")
    lines.append(f"")
    lines.append(f"| Metric | Count |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total activities scanned | {total} |")
    for cls in ("clean", "warn-only", "scope-required", "unexpected-error", "ipc-error", "skipped"):
        lines.append(f"| {cls} | {by_cls.get(cls, 0)} |")
    lines.append(f"")

    lines.append(f"## Per-Package Breakdown")
    lines.append(f"")
    pkg_names = sorted(by_pkg.keys())
    cls_cols = ["clean", "warn-only", "scope-required", "unexpected-error", "ipc-error", "skipped"]
    header = "| Package | " + " | ".join(cls_cols) + " |"
    sep = "|---------|" + "|".join(["-------"] * len(cls_cols)) + "|"
    lines.append(header)
    lines.append(sep)
    for pkg in pkg_names:
        counts = by_pkg[pkg]
        row = f"| {pkg} | " + " | ".join(str(counts.get(c, 0)) for c in cls_cols) + " |"
        lines.append(row)
    lines.append(f"")

    if top10:
        lines.append(f"## Top {len(top10)} Unexpected Errors")
        lines.append(f"")
        lines.append(f"| Package | Version | Activity | Error |")
        lines.append(f"|---------|---------|----------|-------|")
        for r in top10:
            msg = r["top"].replace("|", "\\|")
            lines.append(f"| {r['pkg']} | {r['ver']} | {r['act']} | {msg} |")
        lines.append(f"")

    lines.append(f"## Full Per-Activity Table")
    lines.append(f"")
    lines.append(f"| Package | Version | Activity | Classification | E | W | Note |")
    lines.append(f"|---------|---------|----------|----------------|---|---|------|")
    for r in results:
        note = r["top"].replace("|", "\\|") if r["top"] else ""
        lines.append(
            f"| {r['pkg']} | {r['ver']} | {r['act']} | {r['classification']} "
            f"| {r['errors']} | {r['warnings']} | {note} |"
        )
    lines.append(f"")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--package", default=None, help="Filter to a single package name")
    parser.add_argument("--version", default=None, help="Filter to a single version (e.g. 25.10)")
    args = parser.parse_args()

    print("Ensuring Studio is running…", flush=True)
    _ensure_studio_running()

    import time
    t0 = time.monotonic()

    print(f"Starting sweep (profiles: {PROFILES_DIR})", flush=True)
    results = _run_sweep(args.package, args.version)
    elapsed = time.monotonic() - t0

    # Print quick summary
    by_cls: defaultdict[str, int] = defaultdict(int)
    for r in results:
        by_cls[r["classification"]] += 1
    print(f"\n--- Sweep complete in {elapsed:.1f}s ---", flush=True)
    print(f"Total: {len(results)}", flush=True)
    for cls, cnt in sorted(by_cls.items()):
        print(f"  {cls}: {cnt}", flush=True)

    # Write report
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = ANALYSIS_DIR / "battle-test-studio.md"
    report_md = _build_report(results, elapsed)
    report_path.write_text(report_md, encoding="utf-8")
    print(f"\nReport written to: {report_path}", flush=True)

    # Also write raw JSON alongside
    json_path = ANALYSIS_DIR / "battle-test-studio.json"
    json_path.write_text(json.dumps({"elapsed_sec": elapsed, "results": results}, indent=2), encoding="utf-8")
    print(f"Raw JSON written to: {json_path}", flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
