#!/usr/bin/env python3
"""Run UiPath Studio's built-in validator against the repo's good-fixture XAML.

Catches issues the Python XSD + lint rules miss: deprecated activities,
implicit type conversions, missing activity-package references, and other
Studio-only diagnostics.

Requires:
  - @uipath/cli installed globally (`npm i -g @uipath/cli`)
  - UiPath Studio Desktop running against a project that has the relevant
    activity packages installed. The harvester's temp project works fine —
    pass it via --project-dir, or let this script auto-discover the most
    recent uip-harvest-* temp project.

Usage:
    python validate_with_studio.py                        # auto-find temp project
    python validate_with_studio.py --project-dir <path>   # explicit project
    python validate_with_studio.py --paths file1.xaml,file2.xaml  # custom set

Exit code: 0 if every file validates cleanly (no error-severity diagnostics),
1 otherwise. Warnings are reported but do not fail the run.
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TEST_DIR = REPO_ROOT / "uipath-core" / "assets" / "lint-test-cases"

UIP = shutil.which("uip") or shutil.which("uip.cmd") or "uip"


def _run_uip_json(args: list[str], *, timeout: int = 120) -> dict | list | str | None:
    cmd = [UIP, "--output", "json", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8")
    stdout = (proc.stdout or "").strip()
    if proc.returncode != 0 and not stdout:
        raise RuntimeError(f"`uip {' '.join(args)}` rc={proc.returncode}: {(proc.stderr or '').strip() or '(no stderr)'}")
    try:
        payload = json.loads(stdout) if stdout else {}
    except json.JSONDecodeError as e:
        raise RuntimeError(f"`uip {' '.join(args)}` returned non-JSON:\n{stdout[:800]}") from e
    if payload.get("Result") == "Failure":
        raise RuntimeError(f"{payload.get('Message') or payload.get('Data')}")
    return payload.get("Data")


def _find_harvest_project() -> Path | None:
    import tempfile
    base = Path(tempfile.gettempdir()).resolve()
    candidates = sorted(base.glob("uip-harvest-*/Harvest_*"), key=lambda p: p.stat().st_mtime, reverse=True)
    for c in candidates:
        if not c.resolve().is_relative_to(base):
            continue
        if (c / "project.json").exists():
            return c
    return None


def _good_fixture_paths() -> list[Path]:
    """Read the GOOD_FILES and known-clean FILENAME_SENSITIVE_TESTS from
    run_lint_tests.py by importing it. Falls back to a small hardcoded list."""
    try:
        sys.path.insert(0, str(REPO_ROOT / "uipath-core" / "scripts"))
        import run_lint_tests as rlt
        names = list(rlt.GOOD_FILES)
    except Exception as e:
        print(f"(could not import run_lint_tests: {e}; falling back to hardcoded list)",
              file=sys.stderr)
        names = ["good_browser_workflow.xaml", "good_addrow_typed_object.xaml"]
    return [TEST_DIR / n for n in names]


def _summarize_diagnostics(data) -> tuple[int, int, int, list[str]]:
    """Return (errors, warnings, infos, lines) for a get-errors Data payload."""
    errors = warnings = infos = 0
    lines: list[str] = []
    items: list = []
    if isinstance(data, dict):
        if isinstance(data.get("message"), str):
            # "No diagnostics found." happy path
            return 0, 0, 0, [data["message"]]
        for key in ("diagnostics", "Diagnostics", "items", "Items"):
            if isinstance(data.get(key), list):
                items = data[key]
                break
    elif isinstance(data, list):
        items = data

    for d in items:
        if not isinstance(d, dict):
            continue
        sev = (d.get("severity") or d.get("Severity") or "").lower()
        msg = d.get("message") or d.get("Message") or ""
        location = d.get("filePath") or d.get("FilePath") or d.get("activity") or ""
        if sev == "error":
            errors += 1
        elif sev == "warning":
            warnings += 1
        else:
            infos += 1
        lines.append(f"    [{sev or 'info'}] {msg}" + (f"  ({location})" if location else ""))
    return errors, warnings, infos, lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--project-dir", help="UiPath project dir Studio is opened against")
    parser.add_argument("--auto-discover", action="store_true",
                        help="Auto-discover the most recent uip-harvest-* temp project in the system temp dir")
    parser.add_argument("--paths", help="Comma-separated XAML paths to validate (overrides defaults)")
    parser.add_argument("--min-severity", default="warning", choices=["info", "warning", "error"])
    args = parser.parse_args()

    if args.project_dir:
        project_dir = Path(args.project_dir).resolve()
    elif args.auto_discover:
        project_dir = _find_harvest_project()
        if not project_dir:
            print("ERROR: --auto-discover set but no uip-harvest-* temp project found.", file=sys.stderr)
            print("Hint: run harvest_studio_xaml.py first, or pass --project-dir explicitly.", file=sys.stderr)
            return 2
        print(f"(auto-using harvest project: {project_dir})")
    else:
        print("ERROR: provide --project-dir <path> or pass --auto-discover to search for a temp project.", file=sys.stderr)
        return 2

    if args.paths:
        paths = [Path(p.strip()).resolve() for p in args.paths.split(",") if p.strip()]
    else:
        paths = _good_fixture_paths()

    if not paths:
        print("ERROR: no XAML paths to validate.", file=sys.stderr)
        return 2

    total_errors = 0
    total_warnings = 0
    total_infos = 0
    ran = 0
    skipped = 0

    print(f"Validating {len(paths)} file(s) with Studio "
          f"(min-severity={args.min_severity})...\n")
    for path in paths:
        if not path.exists():
            print(f"  SKIP  {path.name} — not found at {path}")
            skipped += 1
            continue
        try:
            data = _run_uip_json(
                ["rpa", "--project-dir", str(project_dir),
                 "get-errors", "--file-path", str(path),
                 "--min-severity", args.min_severity],
                timeout=120,
            )
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            print(f"  ERR   {path.name} — {e}")
            total_errors += 1
            ran += 1
            continue

        errors, warnings, infos, diag_lines = _summarize_diagnostics(data)
        total_errors += errors
        total_warnings += warnings
        total_infos += infos
        ran += 1
        status = "PASS" if errors == 0 else "FAIL"
        tally = f"e={errors} w={warnings} i={infos}"
        print(f"  {status}  {path.name}  ({tally})")
        for line in diag_lines:
            if line.strip() and line.strip() != "No diagnostics found.":
                print(line)

    print(f"\n{'='*60}")
    print(f"Studio-validator: {ran} run, {skipped} skipped | "
          f"errors={total_errors} warnings={total_warnings} infos={total_infos}")
    print(f"{'='*60}")
    return 1 if total_errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
