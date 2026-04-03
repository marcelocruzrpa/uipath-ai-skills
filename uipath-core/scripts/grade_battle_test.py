#!/usr/bin/env python3
"""Semi-automated battle test grader.

Runs automatable checks against a generated project directory and reports
pass/fail per checkpoint. Covers ~60-70% of battle test checkpoints;
subjective checks (agent explained rationale, agent refused pattern) still
need manual review.

Usage:
    python3 scripts/grade_battle_test.py <project_dir> --suite core --scenario 1
    python3 scripts/grade_battle_test.py <project_dir> --suite sap --scenario 7
    python3 scripts/grade_battle_test.py <project_dir> --suite ac --scenario 2

Suites: core, sap, ac (action-center)
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).resolve().parent
VALIDATE_XAML = SCRIPT_DIR / "validate_xaml"


# ---------------------------------------------------------------------------
# Check primitives
# ---------------------------------------------------------------------------

class GradeResult:
    def __init__(self):
        self.checks: list[tuple[str, bool, str]] = []  # (name, passed, detail)

    def check(self, name: str, passed: bool, detail: str = ""):
        self.checks.append((name, passed, detail))

    def summary(self) -> str:
        lines = []
        passed = sum(1 for _, p, _ in self.checks if p)
        total = len(self.checks)
        lines.append(f"\n{'='*60}")
        lines.append(f"  GRADE: {passed}/{total} automated checks passed")
        lines.append(f"{'='*60}\n")
        for name, p, detail in self.checks:
            icon = "✅" if p else "❌"
            line = f"  {icon} {name}"
            if detail:
                line += f"  — {detail}"
            lines.append(line)
        lines.append("")
        manual = total - passed
        if manual == 0:
            lines.append("  All automated checks passed.")
        else:
            lines.append(f"  {total - passed} automated check(s) failed.")
        lines.append("  ⚠️  Manual checks (agent explanations, refusals) not graded.\n")
        return "\n".join(lines)


def find_project_json(project_dir: Path) -> Path | None:
    pj = project_dir / "project.json"
    if pj.exists():
        return pj
    # Search one level deep
    for child in project_dir.iterdir():
        if child.is_dir():
            pj = child / "project.json"
            if pj.exists():
                return pj
    return None


def find_xaml_files(project_dir: Path) -> list[Path]:
    return sorted(project_dir.rglob("*.xaml"))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def run_lint(project_dir: Path) -> tuple[int, str]:
    """Run validate_xaml --lint. Returns (exit_code, output)."""
    try:
        r = subprocess.run(
            [sys.executable, str(VALIDATE_XAML), str(project_dir), "--lint"],
            capture_output=True, text=True, timeout=60,
        )
        return r.returncode, r.stdout + r.stderr
    except Exception as e:
        return -1, str(e)


# ---------------------------------------------------------------------------
# Universal checks (apply to all scenarios)
# ---------------------------------------------------------------------------

def check_lint_passes(gr: GradeResult, project_dir: Path):
    code, output = run_lint(project_dir)
    gr.check("Lint passes (0 errors)", code == 0,
             "exit code 0" if code == 0 else f"exit code {code}")


def check_project_json_exists(gr: GradeResult, project_dir: Path) -> dict | None:
    pj = find_project_json(project_dir)
    gr.check("project.json exists", pj is not None)
    if pj:
        try:
            return json.loads(read_text(pj))
        except Exception:
            return None
    return None


def check_decomposition(gr: GradeResult, project_dir: Path, min_workflows: int = 3):
    """Check that project has sub-workflows in Workflows/ (A-5)."""
    workflows_dir = None
    for d in project_dir.rglob("Workflows"):
        if d.is_dir():
            workflows_dir = d
            break
    has_dir = workflows_dir is not None
    xaml_count = len(list(workflows_dir.rglob("*.xaml"))) if has_dir else 0
    gr.check(
        f"Decomposition: ≥{min_workflows} sub-workflows in Workflows/",
        has_dir and xaml_count >= min_workflows,
        f"found {xaml_count}" if has_dir else "Workflows/ dir missing",
    )


def check_no_hardcoded_urls(gr: GradeResult, project_dir: Path):
    """Check that no XAML contains literal http:// or https:// URLs (A-8)."""
    violations = []
    for xaml in find_xaml_files(project_dir):
        content = read_text(xaml)
        # Skip xmlns declarations and assembly references
        for line in content.splitlines():
            if "xmlns" in line or "assembly=" in line:
                continue
            if re.search(r'https?://[^\s"<>]+\.(com|org|net|io)', line):
                violations.append(xaml.name)
                break
    gr.check("No hardcoded URLs in XAML (A-8)", len(violations) == 0,
             f"violations in: {', '.join(violations)}" if violations else "")


def check_no_credential_arguments(gr: GradeResult, project_dir: Path):
    """Check no workflow has in_strUsername/in_strPassword/in_secPassword args (A-3)."""
    bad_args = ["in_strUsername", "in_strPassword", "in_secPassword"]
    violations = []
    for xaml in find_xaml_files(project_dir):
        content = read_text(xaml)
        for arg in bad_args:
            if arg in content:
                violations.append(f"{xaml.name}:{arg}")
                break
    gr.check("No credential arguments (A-3)", len(violations) == 0,
             f"found: {', '.join(violations)}" if violations else "")


def check_get_robot_credential_inside(gr: GradeResult, project_dir: Path):
    """Check GetRobotCredential is used inside a workflow (not passed as arg)."""
    found = False
    for xaml in find_xaml_files(project_dir):
        content = read_text(xaml)
        if "GetRobotCredential" in content or "GetCredential" in content:
            found = True
            break
    gr.check("GetRobotCredential present in project", found)


def check_log_bookends(gr: GradeResult, project_dir: Path):
    """Spot-check that sub-workflows have LogMessage near start/end (A-7)."""
    workflows_dir = None
    for d in project_dir.rglob("Workflows"):
        if d.is_dir():
            workflows_dir = d
            break
    if not workflows_dir:
        gr.check("Log bookends (A-7)", False, "no Workflows/ dir")
        return
    xamls = list(workflows_dir.rglob("*.xaml"))
    if not xamls:
        gr.check("Log bookends (A-7)", False, "no sub-workflows found")
        return
    has_log = 0
    for xaml in xamls:
        content = read_text(xaml)
        if "LogMessage" in content or "ui:LogMessage" in content:
            has_log += 1
    ratio = has_log / len(xamls) if xamls else 0
    gr.check("Log bookends (A-7)", ratio >= 0.8,
             f"{has_log}/{len(xamls)} sub-workflows have LogMessage")


def check_main_orchestration_only(gr: GradeResult, project_dir: Path,
                                  forbidden_activities: list[str] | None = None):
    """Check Main.xaml is orchestration-only (InvokeWorkflowFile, no direct UI)."""
    main = None
    for xaml in find_xaml_files(project_dir):
        if xaml.name == "Main.xaml":
            main = xaml
            break
    if not main:
        gr.check("Main.xaml exists", False)
        return
    content = read_text(main)
    if forbidden_activities is None:
        forbidden_activities = [
            "NClick", "NTypeInto", "NGetText", "NApplicationCard",
            "NSAPClickToolbarButton", "NSAPCallTransaction",
        ]
    found = [a for a in forbidden_activities if a in content]
    gr.check("Main.xaml is orchestration-only (no direct UI activities)",
             len(found) == 0,
             f"found: {', '.join(found)}" if found else "")


def check_xaml_generated_not_handwritten(gr: GradeResult, project_dir: Path):
    """Heuristic: generated XAML has ViewState and proper namespace blocks."""
    xamls = find_xaml_files(project_dir)
    suspect = []
    for xaml in xamls:
        content = read_text(xaml)
        # Framework files from template are fine
        if "Framework/" in str(xaml) or "Tests/" in str(xaml):
            continue
        # Generated files should have sap2010:ViewState
        if len(content) > 500 and "sap2010:ViewState" not in content:
            suspect.append(xaml.name)
    gr.check("XAML appears generator-produced (has ViewState)", len(suspect) == 0,
             f"suspect: {', '.join(suspect)}" if suspect else "")


# ---------------------------------------------------------------------------
# Variant-specific checks
# ---------------------------------------------------------------------------

def check_project_variant(gr: GradeResult, pj_data: dict | None, expected: str):
    """Check project.json for variant markers."""
    if not pj_data:
        gr.check(f"Variant: {expected}", False, "no project.json data")
        return
    # Heuristic: dispatcher has GetQueueItems or AddQueueItem references,
    # performer has GetTransactionItem, sequence has neither
    deps = pj_data.get("dependencies", {})
    desc = pj_data.get("description", "").lower()
    name = pj_data.get("name", "").lower()
    if expected == "sequence":
        gr.check("Variant: sequence", "dispatcher" not in name and "performer" not in name,
                 f"name={pj_data.get('name', '')}")
    elif expected == "dispatcher":
        gr.check("Variant: dispatcher", "dispatcher" in name or "dispatcher" in desc,
                 f"name={pj_data.get('name', '')}")
    elif expected == "performer":
        gr.check("Variant: performer", "performer" in name or "performer" in desc,
                 f"name={pj_data.get('name', '')}")


def check_nuget_dependency(gr: GradeResult, pj_data: dict | None, package: str):
    if not pj_data:
        gr.check(f"NuGet: {package}", False, "no project.json data")
        return
    deps = pj_data.get("dependencies", {})
    found = any(package.lower() in k.lower() for k in deps)
    gr.check(f"NuGet: {package}", found,
             f"deps: {list(deps.keys())}" if not found else "")


def check_open_mode(gr: GradeResult, project_dir: Path):
    """Check Launch workflows have OpenMode=Always, others OpenMode=Never."""
    violations = []
    for xaml in find_xaml_files(project_dir):
        content = read_text(xaml)
        name = xaml.name
        if "NApplicationCard" not in content and "NSAPLogon" not in content:
            continue
        is_launch = "_Launch" in name or "InitAllApplications" in name
        if is_launch:
            if 'OpenMode="Never"' in content:
                violations.append(f"{name}: Launch should be Always, found Never")
        else:
            if 'OpenMode="Always"' in content:
                violations.append(f"{name}: non-Launch should be Never, found Always")
    gr.check("OpenMode: Launch=Always, others=Never", len(violations) == 0,
             "; ".join(violations) if violations else "")


def check_incognito(gr: GradeResult, project_dir: Path):
    """Check browser workflows use IsIncognito=True (A-9)."""
    violations = []
    for xaml in find_xaml_files(project_dir):
        content = read_text(xaml)
        if "NApplicationCard" in content and "BrowserType" in content:
            if 'IsIncognito="True"' not in content:
                violations.append(xaml.name)
    gr.check("IsIncognito=True on browsers (A-9)", len(violations) == 0,
             f"missing in: {', '.join(violations)}" if violations else "")


# ---------------------------------------------------------------------------
# SAP-specific checks
# ---------------------------------------------------------------------------

def check_sap_logon_scope(gr: GradeResult, project_dir: Path):
    """Check SAP activities are inside NSAPLogon scope (S-1)."""
    sap_activities = ["NSAPLogin", "NSAPCallTransaction", "NSAPClickToolbarButton",
                      "NSAPSelectMenuItem", "NSAPReadStatusbar", "NSAPTableCellScope"]
    violations = []
    for xaml in find_xaml_files(project_dir):
        content = read_text(xaml)
        has_sap = any(a in content for a in sap_activities)
        if has_sap and "NSAPLogon" not in content:
            violations.append(xaml.name)
    gr.check("SAP activities inside NSAPLogon scope (S-1)", len(violations) == 0,
             f"missing scope in: {', '.join(violations)}" if violations else "")


def check_sap_statusbar_after_write(gr: GradeResult, project_dir: Path):
    """Heuristic: if NSAPClickToolbarButton (Save) present, NSAPReadStatusbar should follow (S-2)."""
    for xaml in find_xaml_files(project_dir):
        content = read_text(xaml)
        if "NSAPClickToolbarButton" in content:
            has_statusbar = "NSAPReadStatusbar" in content
            gr.check("Status bar check after toolbar action (S-2)", has_statusbar,
                     xaml.name)
            return
    # No toolbar clicks found — skip check
    pass


def check_no_nclick_on_toolbar(gr: GradeResult, project_dir: Path):
    """Check no NClick is used for system toolbar buttons (S-3)."""
    toolbar_selectors = ["btn[0]", "btn[3]", "btn[8]", "btn[11]", "btn[12]",
                         "btn[15]", "btn[16]"]
    violations = []
    for xaml in find_xaml_files(project_dir):
        content = read_text(xaml)
        if "NClick" in content:
            for btn in toolbar_selectors:
                if btn in content:
                    violations.append(f"{xaml.name}:{btn}")
    gr.check("No NClick on system toolbar buttons (S-3)", len(violations) == 0,
             f"found: {', '.join(violations)}" if violations else "")


def check_table_cell_scope(gr: GradeResult, project_dir: Path):
    """Check table cell interactions use NSAPTableCellScope (S-4)."""
    # Heuristic: if a XAML has table-like selectors but no NSAPTableCellScope
    for xaml in find_xaml_files(project_dir):
        content = read_text(xaml)
        has_table_selector = bool(re.search(r'txt\w+\[\d+,\d+\]', content))
        if has_table_selector and "NSAPTableCellScope" not in content:
            gr.check("Table cells use NSAPTableCellScope (S-4)", False,
                     f"direct cell selector in {xaml.name}")
            return
    gr.check("Table cells use NSAPTableCellScope (S-4)", True)


# ---------------------------------------------------------------------------
# Scenario grading
# ---------------------------------------------------------------------------

def grade_core(scenario: int, project_dir: Path) -> GradeResult:
    gr = GradeResult()
    pj = check_project_json_exists(gr, project_dir)

    if scenario == 1:
        # Simple web form
        check_project_variant(gr, pj, "sequence")
        check_decomposition(gr, project_dir, min_workflows=3)
        check_open_mode(gr, project_dir)
        check_incognito(gr, project_dir)
        check_no_hardcoded_urls(gr, project_dir)
        check_no_credential_arguments(gr, project_dir)
        check_get_robot_credential_inside(gr, project_dir)
        check_log_bookends(gr, project_dir)
        check_xaml_generated_not_handwritten(gr, project_dir)
        check_lint_passes(gr, project_dir)

    elif scenario == 2:
        # Dispatcher + Performer
        check_decomposition(gr, project_dir, min_workflows=2)
        check_no_hardcoded_urls(gr, project_dir)
        check_log_bookends(gr, project_dir)
        check_xaml_generated_not_handwritten(gr, project_dir)
        check_lint_passes(gr, project_dir)

    elif scenario == 3:
        # API integration
        check_decomposition(gr, project_dir, min_workflows=2)
        check_no_hardcoded_urls(gr, project_dir)
        check_log_bookends(gr, project_dir)
        # Check RetryScope on HTTP activities
        for xaml in find_xaml_files(project_dir):
            content = read_text(xaml)
            if "HttpClient" in content or "NetHttpRequest" in content:
                has_retry = "RetryScope" in content
                gr.check("API calls wrapped in RetryScope (A-11)", has_retry)
                break
        check_lint_passes(gr, project_dir)

    elif scenario == 4:
        # Desktop automation
        check_decomposition(gr, project_dir, min_workflows=2)
        check_open_mode(gr, project_dir)
        check_no_hardcoded_urls(gr, project_dir)
        check_log_bookends(gr, project_dir)
        check_lint_passes(gr, project_dir)

    elif scenario == 5:
        # REFramework performer
        check_decomposition(gr, project_dir, min_workflows=3)
        check_open_mode(gr, project_dir)
        check_no_credential_arguments(gr, project_dir)
        check_no_hardcoded_urls(gr, project_dir)
        check_log_bookends(gr, project_dir)
        check_lint_passes(gr, project_dir)

    elif scenario == 6:
        # Lint remediation
        check_lint_passes(gr, project_dir)
        check_xaml_generated_not_handwritten(gr, project_dir)

    elif scenario == 7:
        # NEGATIVE: Monolith Main.xaml (A-5)
        check_decomposition(gr, project_dir, min_workflows=4)
        check_main_orchestration_only(gr, project_dir)
        # Check no sub-workflow >150 lines
        workflows_dir = None
        for d in project_dir.rglob("Workflows"):
            if d.is_dir():
                workflows_dir = d
                break
        if workflows_dir:
            for xaml in workflows_dir.rglob("*.xaml"):
                lines = len(read_text(xaml).splitlines())
                if lines > 150:
                    gr.check(f"Sub-workflow ≤150 lines", False,
                             f"{xaml.name}: {lines} lines")
            else:
                gr.check("Sub-workflows ≤150 lines", True)
        check_lint_passes(gr, project_dir)

    elif scenario == 8:
        # NEGATIVE: Credentials as arguments (A-3)
        check_no_credential_arguments(gr, project_dir)
        check_get_robot_credential_inside(gr, project_dir)
        # Check in_strCredentialAssetName is used
        found_asset_arg = False
        for xaml in find_xaml_files(project_dir):
            content = read_text(xaml)
            if "CredentialAssetName" in content or "credentialAssetName" in content:
                found_asset_arg = True
                break
        gr.check("Uses in_strCredentialAssetName (not raw creds)", found_asset_arg)
        check_lint_passes(gr, project_dir)

    elif scenario == 9:
        # NEGATIVE: Hardcoded URL (A-8)
        check_no_hardcoded_urls(gr, project_dir)
        # Check Config.xlsx reference
        found_config = False
        for xaml in find_xaml_files(project_dir):
            content = read_text(xaml)
            if "Config(" in content or "in_Config" in content or "io_Config" in content:
                found_config = True
                break
        gr.check("URL comes from Config (not hardcoded)", found_config)
        check_lint_passes(gr, project_dir)

    else:
        print(f"Unknown core scenario: {scenario}")
        sys.exit(1)

    return gr


def grade_sap(scenario: int, project_dir: Path) -> GradeResult:
    gr = GradeResult()
    pj = check_project_json_exists(gr, project_dir)

    # Common SAP checks for most scenarios
    if scenario in range(1, 11):
        check_sap_logon_scope(gr, project_dir)
        check_no_nclick_on_toolbar(gr, project_dir)
        check_log_bookends(gr, project_dir)
        check_lint_passes(gr, project_dir)

    if scenario == 7:
        # Full E2E
        check_decomposition(gr, project_dir, min_workflows=4)
        check_main_orchestration_only(gr, project_dir,
                                      forbidden_activities=["NSAPCallTransaction",
                                                            "NSAPClickToolbarButton",
                                                            "NSAPReadStatusbar",
                                                            "NTypeInto", "NClick"])
        check_open_mode(gr, project_dir)
        check_sap_statusbar_after_write(gr, project_dir)

    elif scenario == 11:
        # NEGATIVE: NClick on toolbar (S-3)
        check_no_nclick_on_toolbar(gr, project_dir)
        # Check NSAPClickToolbarButton IS used for save
        found = False
        for xaml in find_xaml_files(project_dir):
            content = read_text(xaml)
            if "NSAPClickToolbarButton" in content:
                found = True
                break
        gr.check("Uses NSAPClickToolbarButton (not NClick)", found)
        check_sap_statusbar_after_write(gr, project_dir)

    elif scenario == 12:
        # NEGATIVE: Direct cell selector (S-4)
        check_table_cell_scope(gr, project_dir)

    return gr


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Grade a battle test scenario")
    parser.add_argument("project_dir", help="Path to generated project directory")
    parser.add_argument("--suite", required=True,
                        help="Test suite (e.g. core, sap, ac)")
    parser.add_argument("--scenario", required=True, type=int,
                        help="Scenario number")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    if not project_dir.exists():
        print(f"ERROR: Project directory not found: {project_dir}")
        sys.exit(1)

    graders = {"core": grade_core, "sap": grade_sap}

    # Merge plugin-provided battle test graders (e.g. Action Center "ac")
    try:
        sys.path.insert(0, str(SCRIPT_DIR))
        from plugin_loader import load_plugins, get_battle_test_graders
        load_plugins()
        graders.update(get_battle_test_graders())
    except ImportError:
        pass

    if args.suite not in graders:
        print(f"ERROR: Unknown suite '{args.suite}'. Available: {', '.join(sorted(graders.keys()))}")
        sys.exit(1)

    gr = graders[args.suite](args.scenario, project_dir)
    print(gr.summary())

    # Exit code: 0 if all checks passed, 1 otherwise
    all_passed = all(p for _, p, _ in gr.checks)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
