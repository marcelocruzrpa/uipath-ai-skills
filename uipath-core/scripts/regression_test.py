#!/usr/bin/env python3
"""
UiPath skill regression test.

Validates golden templates and scaffolded projects to catch regressions
when editing patterns, templates, or the validator itself.

Usage:
    python3 scripts/regression_test.py              # run all tests
    python3 scripts/regression_test.py --verbose     # show details
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SKILL_DIR = Path(__file__).parent.parent
ASSETS_DIR = SKILL_DIR / "assets"
SCRIPTS_DIR = SKILL_DIR / "scripts"
VALIDATOR = SCRIPTS_DIR / "validate_xaml"
SCAFFOLD = SCRIPTS_DIR / "scaffold_project.py"

# Set by main() from --tmpdir; None = system default
TMPDIR_BASE = None


class TestResult:
    def __init__(self, name: str):
        self.name = name
        self.passed = True
        self.messages = []

    def fail(self, msg: str):
        self.passed = False
        self.messages.append(f"FAIL: {msg}")

    def ok(self, msg: str):
        self.messages.append(f"  OK: {msg}")

    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        header = f"{'='*60}\n{status}  {self.name}\n{'='*60}"
        body = "\n".join(f"  {m}" for m in self.messages)
        return f"{header}\n{body}" if self.messages else header


def run_validator(path: str, *extra_args) -> tuple[int, str, str]:
    """Run validate_xaml and return (returncode, stdout, stderr)."""
    cmd = [sys.executable, str(VALIDATOR), path] + list(extra_args)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def test_golden_templates() -> TestResult:
    """Test 1: All golden templates pass validation with 0 errors."""
    t = TestResult("Golden templates — 0 errors (--lint --golden)")

    # Run against assets/ but exclude lint-test-cases (intentionally bad files)
    # Collect XAML dirs that are NOT lint-test-cases
    golden_dirs = [d for d in ASSETS_DIR.iterdir()
                   if d.is_dir() and d.name not in ("lint-test-cases", "stripped", "generator-snapshots")]
    
    all_passed = 0
    all_total = 0
    all_errors = 0
    all_warnings = 0
    error_lines = []
    
    for d in golden_dirs:
        rc, stdout, stderr = run_validator(str(d), "--lint", "--golden")
        m = re.search(r"SUMMARY: (\d+)/(\d+) files passed, (\d+) errors, (\d+) warnings", stdout)
        if m:
            all_passed += int(m.group(1))
            all_total += int(m.group(2))
            all_errors += int(m.group(3))
            all_warnings += int(m.group(4))
            for line in stdout.splitlines():
                if "[ERROR]" in line:
                    error_lines.append(line.strip())

    if all_errors > 0:
        t.fail(f"{all_errors} errors found (expected 0)")
        for line in error_lines[:10]:
            t.messages.append(f"       {line}")
    else:
        t.ok(f"{all_passed}/{all_total} files passed, 0 errors, {all_warnings} warnings")

    if all_passed != all_total:
        t.fail(f"Only {all_passed}/{all_total} files passed")

    return t


def test_scaffold_variant(tmpdir: str, variant: str, name: str) -> TestResult:
    """Scaffold a project variant and validate it."""
    t = TestResult(f"Scaffold {variant} project + validate")

    out_dir = os.path.join(tmpdir, name)
    cmd = [
        sys.executable, str(SCAFFOLD),
        "--name", name,
        "--variant", variant,
        "--output", out_dir,
        "--deps", "UiPath.System.Activities:[25.12.2]",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        t.fail(f"Scaffold failed: {proc.stderr}")
        return t
    t.ok("Scaffold completed")

    rc, stdout, stderr = run_validator(out_dir, "--lint")
    m = re.search(r"SUMMARY: (\d+)/(\d+) files passed, (\d+) errors", stdout)
    if not m:
        t.fail("Validator parse error on scaffold output")
        return t

    passed, total, errors = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if errors > 0:
        t.fail(f"{errors} errors in scaffolded project")
        for line in stdout.splitlines():
            if "[ERROR]" in line:
                t.messages.append(f"       {line.strip()}")
    else:
        t.ok(f"Validation: {passed}/{total} passed, 0 errors")

    return t


def test_reference_files_exist() -> TestResult:
    """All reference and script files exist and are non-empty."""
    t = TestResult("Reference files integrity")

    expected = [
        "references/xaml-foundations.md",
        "references/xaml-control-flow.md",
        "references/xaml-data.md",
        "references/xaml-error-handling.md",
        "references/xaml-invoke.md",
        "references/xaml-orchestrator.md",
        "references/xaml-integrations.md",
        "references/xaml-ui-automation.md",
        "references/expr-foundations.md",
        "references/expr-datatable.md",
        "references/expr-strings-datetime.md",
        "references/expr-collections-json.md",
        "references/golden-templates.md",
        "references/skill-guide.md",
        "references/scaffolding.md",
        "references/decomposition.md",
        "references/generation.md",
        "references/ui-inspection.md",
        "references/playwright-selectors.md",
        "references/ui-inspection-reference.md",
        # "references/project-structure.md",  # Removed — content merged into decomposition.md
        "scripts/validate_xaml",
        "scripts/scaffold_project.py",
        "scripts/inspect-ui-tree.ps1",
        "scripts/resolve_nuget.py",
    ]

    missing = []
    empty = []
    for f in expected:
        fp = SKILL_DIR / f
        if not fp.exists():
            missing.append(f)
        elif fp.stat().st_size == 0:
            empty.append(f)

    if missing:
        t.fail(f"Missing: {', '.join(missing)}")
    if empty:
        t.fail(f"Empty: {', '.join(empty)}")
    if not missing and not empty:
        t.ok(f"All {len(expected)} files present and non-empty")

    return t


def test_skill_md_size() -> TestResult:
    """SKILL.md stays lean (under 400 lines). Anthropic recommends <500; we target <400."""
    t = TestResult("SKILL.md size check (< 400 lines)")

    skill_md = SKILL_DIR / "SKILL.md"
    if not skill_md.exists():
        t.fail("SKILL.md not found")
        return t

    lines = len(skill_md.read_text(encoding="utf-8").splitlines())
    if lines > 400:
        t.fail(f"SKILL.md is {lines} lines (max 400) — move content to skill-guide.md")
    else:
        t.ok(f"{lines} lines (limit: 400)")

    return t


def test_template_coverage() -> TestResult:
    """All asset XAML files are referenced in golden-templates.md."""
    t = TestResult("Template coverage in golden-templates.md")

    golden = (SKILL_DIR / "references" / "golden-templates.md").read_text(encoding="utf-8")

    xaml_files = []
    for root, dirs, files in os.walk(ASSETS_DIR):
        for f in files:
            if f.endswith(".xaml"):
                rel = os.path.relpath(os.path.join(root, f), ASSETS_DIR)
                xaml_files.append((f, rel))

    unreferenced = [rel for fname, rel in xaml_files
                    if fname not in golden
                    and "/Tests/" not in rel and "\\Tests\\" not in rel
                    and "/samples/" not in rel and "\\samples\\" not in rel
                    and "lint-test-cases" not in rel
                    and "generator-snapshots" not in rel]
    if unreferenced:
        t.fail(f"{len(unreferenced)} template(s) not in golden-templates.md: "
               f"{', '.join(unreferenced[:5])}")
    else:
        t.ok(f"All {len(xaml_files)} templates referenced")

    return t


def test_critical_rules_in_skill_md() -> TestResult:
    """SKILL.md contains critical rules that must not be removed."""
    t = TestResult("Critical rules present in SKILL.md")

    content = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")

    # Rules that MUST be in SKILL.md (routing, ground rules, validation summary)
    skill_md_strings = [
        "Never generate XAML from scratch",
        "Never guess NuGet package versions",
        "resolve_nuget.py",
        "SearchSteps=\"Selector\"",
        "golden-templates.md",
        "xaml-ui-automation.md",
        "xaml-foundations.md",
        "skill-guide.md",
        "lint-reference.md",
        # Tiered severity (actual wording uses emoji + title case)
        "Studio crash",
        "Production / security",
        # Key production rules
        "IsIncognito",
        "RetryScope",
        "Config.xlsx",
        # Browser/API rules referenced by number
        "Browser 9-13",
        # PDD adherence
        "Follow the PDD exactly",
        # Namespace anti-fix
        "UIAutomationNext",
        # Architecture
        "Dispatcher + Performer",
    ]

    # Rules that can live in SKILL.md or any of the split reference files
    skill_guide = (SKILL_DIR / "references" / "skill-guide.md").read_text(encoding="utf-8")
    scaffolding = (SKILL_DIR / "references" / "scaffolding.md").read_text(encoding="utf-8")
    decomposition = (SKILL_DIR / "references" / "decomposition.md").read_text(encoding="utf-8")
    combined = content + skill_guide + scaffolding + decomposition

    combined_strings = [
        "CREDENTIAL CHECK",
        "PLAN SELF-CHECK",
        "PLAN OUTPUT FORMAT",
        "ARCHITECTURE CHECK",
    ]

    missing = [s for s in skill_md_strings if s not in content]
    missing += [s for s in combined_strings if s not in combined]
    if missing:
        t.fail(f"Missing critical rules: {missing}")
    else:
        t.ok(f"All {len(skill_md_strings) + len(combined_strings)} critical rules present")

    return t


def test_decomposition_rules_complete() -> TestResult:
    """All 14 decomposition rules present in decomposition.md."""
    t = TestResult("Decomposition rules 1-14 in decomposition.md")

    content = (SKILL_DIR / "references" / "decomposition.md").read_text(encoding="utf-8")

    # Each rule has a bold numbered prefix
    rules = {
        1: "One UI scope per workflow",
        2: "150 lines per file",
        3: "Reusable navigation",
        4: "ALL apps open and ready in InitAllApplications",
        5: "No UI in data workflows",
        6: "Persistence activities stay in Main",
        7: "Log bookends",
        8: "Credentials retrieved where used",
        9: "Navigation is a separate workflow",
        10: "No logout workflow",
        11: "One browser instance per web",
        12: "Extraction workflows return ALL data",
        13: "Wrap API/network activities in RetryScope",
        14: "Desktop navigation is a separate workflow",
    }

    missing = []
    for num, keyword in rules.items():
        if keyword not in content:
            missing.append(f"Rule {num}: '{keyword}'")

    if missing:
        t.fail(f"Missing rules in decomposition.md: {'; '.join(missing)}")
    else:
        t.ok(f"All {len(rules)} decomposition rules present")

    return t


def test_playwright_safety_rules() -> TestResult:
    """Playwright credential safety rules present in SKILL.md, ui-inspection.md, and playwright-selectors.md."""
    t = TestResult("Playwright safety rules (no credential typing)")

    skill_md = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    ui_inspection = (SKILL_DIR / "references" / "ui-inspection.md").read_text(encoding="utf-8")
    pw_selectors = (SKILL_DIR / "references" / "playwright-selectors.md").read_text(encoding="utf-8")

    checks = {
        "SKILL.md: safety rules banner": "Safety Rules" in skill_md,
        "SKILL.md: LOGIN GATE section": "Login Gate" in skill_md,
        "SKILL.md: never type credentials": "NEVER" in skill_md and "credentials" in skill_md,
        "SKILL.md: Phase 2 login warning": "LOGIN PAGES" in skill_md or "login page" in skill_md.lower(),
        "SKILL.md: READ-ONLY inspection": "READ-ONLY" in skill_md,
        "ui-inspection: mandatory message template": "I cannot and will not type anything" in ui_inspection,
        "ui-inspection: placeholder error selector": "PLACEHOLDER_ERROR_SELECTOR" in ui_inspection,
        "ui-inspection: HARD RULE callout": "HARD RULE" in ui_inspection,
        "ui-inspection: never type fake credentials": "not fake ones" in ui_inspection,
        "ui-inspection: stop-yourself check": "If you are about to call a Playwright tool" in ui_inspection,
        "ui-inspection: Step 1 login warning": "DO NOT interact with the login form" in ui_inspection,
        "playwright-selectors: READ-ONLY banner": "READ-ONLY" in pw_selectors and "OBSERVER" in pw_selectors.upper(),
        "playwright-selectors: NEVER type": "NEVER" in pw_selectors and "form field" in pw_selectors,
        "playwright-selectors: re-read warning": "RE-READ THIS WARNING" in pw_selectors,
    }

    failed = [name for name, present in checks.items() if not present]
    if failed:
        t.fail(f"Missing safety rules: {'; '.join(failed)}")
    else:
        t.ok(f"All {len(checks)} Playwright safety checks present across 3 files")

    return t


def test_namespace_conflict_detection() -> TestResult:
    """Validator catches System.Drawing.Primitives / System.Data namespace bugs in OCREngine.

    Regression test for: Studio error 'Could not find type System.Drawing.Image
    in assembly System.Drawing.Primitives' when OCREngine delegate is included
    with wrong namespace bindings.
    """
    t = TestResult("Validator catches OCREngine namespace conflicts")

    # Build minimal test XAML with OCREngine — need uix, scg, sd1 namespaces
    def make_ocr_xaml(xclass: str, extra_ns: str, img_prefix: str) -> str:
        return (
            f'<Activity mc:Ignorable="sap sap2010" x:Class="{xclass}" '
            'VisualBasic.Settings="{x:Null}" '
            'sap:VirtualizedContainerService.HintSize="500,500" '
            'sap2010:WorkflowViewState.IdRef="Act_1" '
            'xmlns="http://schemas.microsoft.com/netfx/2009/xaml/activities" '
            'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
            'xmlns:sap="http://schemas.microsoft.com/netfx/2009/xaml/activities/presentation" '
            'xmlns:sap2010="http://schemas.microsoft.com/netfx/2010/xaml/activities/presentation" '
            'xmlns:scg="clr-namespace:System.Collections.Generic;assembly=System.Private.CoreLib" '
            'xmlns:uix="http://schemas.uipath.com/workflow/activities/uix" '
            f'{extra_ns} '
            'xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml">\n'
            '  <Sequence DisplayName="Do" sap:VirtualizedContainerService.HintSize="400,200" '
            'sap2010:WorkflowViewState.IdRef="Seq_1">\n'
            '    <uix:NApplicationCard.OCREngine>\n'
            f'      <ActivityFunc x:TypeArguments="{img_prefix}:Image, '
            f'scg:IEnumerable(scg:KeyValuePair({img_prefix}:Rectangle, x:String))">\n'
            '        <ActivityFunc.Argument>\n'
            f'          <DelegateInArgument x:TypeArguments="{img_prefix}:Image" Name="Image" />\n'
            '        </ActivityFunc.Argument>\n'
            '      </ActivityFunc>\n'
            '    </uix:NApplicationCard.OCREngine>\n'
            '  </Sequence>\n'
            '</Activity>'
        )

    with tempfile.TemporaryDirectory(dir=TMPDIR_BASE) as tmp:
        # Case A: sd1 → System.Drawing.Primitives (the exact bug from Claude Code test)
        bad_primitives = Path(tmp) / "bad_primitives.xaml"
        bad_primitives.write_text(make_ocr_xaml(
            "bad_primitives",
            'xmlns:sd1="clr-namespace:System.Drawing;assembly=System.Drawing.Primitives"',
            "sd1"
        ), encoding="utf-8")
        rc_a, stdout_a, _ = run_validator(str(bad_primitives), "--lint")
        if "System.Drawing.Primitives" in stdout_a and "[ERROR]" in stdout_a:
            t.ok("Case A: sd1:Image → System.Drawing.Primitives detected as error")
        else:
            t.fail("Case A: Should catch sd1:Image with System.Drawing.Primitives binding")

        # Case B: sd → System.Data used for Image (wrong namespace entirely)
        bad_sysdata = Path(tmp) / "bad_sysdata.xaml"
        bad_sysdata.write_text(make_ocr_xaml(
            "bad_sysdata",
            'xmlns:sd="clr-namespace:System.Data;assembly=System.Data.Common"',
            "sd"
        ), encoding="utf-8")
        rc_b, stdout_b, _ = run_validator(str(bad_sysdata), "--lint")
        if "System.Data" in stdout_b and "[ERROR]" in stdout_b:
            t.ok("Case B: sd:Image → System.Data detected as error")
        else:
            t.fail("Case B: Should catch sd:Image with System.Data binding")

        # Case C: Correct binding — should NOT error
        good = Path(tmp) / "good_ocr.xaml"
        good.write_text(make_ocr_xaml(
            "good_ocr",
            'xmlns:sdraw="clr-namespace:System.Drawing;assembly=System.Drawing.Common"',
            "sdraw"
        ), encoding="utf-8")
        rc_c, stdout_c, _ = run_validator(str(good), "--lint")
        if "[ERROR]" not in stdout_c:
            t.ok("Case C: Correct System.Drawing.Common binding passes clean")
        else:
            t.fail("Case C: Correct System.Drawing.Common binding should not error")

    return t


def test_template_copy_modify() -> TestResult:
    """Copy simplest template, change x:Class + DisplayName → still validates."""
    t = TestResult("Template copy + modify → valid XAML")

    src = ASSETS_DIR / "reframework" / "Framework" / "KillAllProcesses.xaml"
    content = src.read_text(encoding="utf-8-sig")

    with tempfile.TemporaryDirectory(dir=TMPDIR_BASE) as tmp:
        dst = Path(tmp) / "CloseAllBrowsers.xaml"
        modified = content.replace(
            'x:Class="KillAllProcesses"', 'x:Class="CloseAllBrowsers"'
        ).replace(
            'DisplayName="Kill All Processes"', 'DisplayName="Close All Browsers"'
        )
        dst.write_text(modified, encoding="utf-8")

        rc, stdout, _ = run_validator(str(dst), "--lint")
        if "[ERROR]" in stdout:
            t.fail("Modified template has errors")
            for line in stdout.splitlines():
                if "[ERROR]" in line:
                    t.messages.append(f"       {line.strip()}")
        else:
            t.ok("Modified template validates cleanly")

    return t


def test_line_count_accuracy() -> TestResult:
    """Line counts claimed in SKILL.md match actual file line counts."""
    t = TestResult("SKILL.md line count accuracy")

    skill_md = SKILL_DIR / "SKILL.md"
    content = skill_md.read_text(encoding="utf-8")

    # Parse line counts from the reference table: | `references/file.md` | 400 | ...
    # and scripts table: | `scripts/file.py` | 1951 | ...
    pattern = re.compile(r'\|\s*`((?:references|scripts)/[^`]+)`\s*\|\s*(\d[\d,]*)\s*\|')

    drift = []
    checked = 0
    for match in pattern.finditer(content):
        rel_path = match.group(1)
        claimed = int(match.group(2).replace(",", ""))
        actual_path = SKILL_DIR / rel_path
        if not actual_path.exists():
            continue
        actual = sum(1 for _ in actual_path.open(encoding="utf-8", errors="replace"))
        checked += 1
        if abs(actual - claimed) > 5:  # allow +-5 tolerance
            drift.append(f"{rel_path}: claimed {claimed}, actual {actual}")

    if drift:
        t.fail(f"Stale line counts (>5 drift):\n  " + "\n  ".join(drift))
    else:
        t.ok(f"All {checked} line counts within tolerance")

    return t


def test_generator_and_lint_counts() -> TestResult:
    """Generator and lint counts in SKILL.md/cheat-sheet.md match actual code."""
    t = TestResult("Generator and lint counts match code")

    # Count generators dynamically — core and plugins separately
    gen_pkg = SCRIPTS_DIR / "generate_activities"
    gen_content = ""
    for f in gen_pkg.glob("*.py"):
        gen_content += f.read_text(encoding="utf-8")
    actual_core_generators = len(re.findall(r'^def gen_\w+', gen_content, re.MULTILINE))
    # Plugin generators
    from plugin_loader import load_plugins, get_generators, get_lint_rules
    load_plugins()
    actual_plugin_generators = len(get_generators())
    actual_total_generators = actual_core_generators + actual_plugin_generators

    # Count lint numbers dynamically (core + plugins)
    val_pkg = SCRIPTS_DIR / "validate_xaml"
    val_content = ""
    for f in val_pkg.glob("*.py"):
        val_content += f.read_text(encoding="utf-8")
    actual_lint_numbers = len(set(re.findall(r'\[lint (\d+)\]', val_content)))
    # Add plugin lint numbers (scan plugin lint source files for [lint N])
    for lint_fn, _ in get_lint_rules():
        import inspect
        src = inspect.getsource(lint_fn)
        actual_lint_numbers += len(set(re.findall(r'\[lint (\d+)\]', src)))
    actual_lint_functions = len(re.findall(r'^def lint_\w+', val_content, re.MULTILINE))

    # Check SKILL.md claims
    skill_content = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")

    # Core generator count — appears as "N deterministic" in description
    gen_match = re.search(r'(\d+) deterministic', skill_content)
    if gen_match:
        claimed_core = int(gen_match.group(1))
        if claimed_core != actual_core_generators:
            t.fail(f"SKILL.md claims {claimed_core} core generators, actual: {actual_core_generators}")
        else:
            t.ok(f"Core generator count: {actual_core_generators}")
    else:
        t.fail("Cannot find core generator count in SKILL.md")

    # Total generator count — dynamic only (not hardcoded in docs since plugin count is unpredictable)
    t.ok(f"Total generator count (core + plugins): {actual_total_generators}")

    # Lint count — appears as "N lint rules" in scripts table
    lint_match = re.search(r'(\d+) lint rules', skill_content)
    if lint_match:
        claimed_lint = int(lint_match.group(1))
        if claimed_lint != actual_lint_numbers:
            t.fail(f"SKILL.md claims {claimed_lint} lint rules, actual: {actual_lint_numbers}")
        else:
            t.ok(f"Lint rule count: {actual_lint_numbers}")
    else:
        t.fail("Cannot find lint rule count in SKILL.md")

    # Check cheat-sheet.md generator counts
    cs_content = (SKILL_DIR / "references" / "cheat-sheet.md").read_text(encoding="utf-8")
    # Core count — appears as "N core generators"
    cs_core_match = re.search(r'(\d+) core generators', cs_content)
    if cs_core_match:
        claimed_cs_core = int(cs_core_match.group(1))
        if claimed_cs_core != actual_core_generators:
            t.fail(f"cheat-sheet.md claims {claimed_cs_core} core generators, actual: {actual_core_generators}")
        else:
            t.ok(f"cheat-sheet.md core generator count: {actual_core_generators}")
    # Total count no longer hardcoded in docs — plugin count is dynamic

    return t


def test_lint_test_cases() -> TestResult:
    """Each bad_*.xaml in lint-test-cases fires its expected lint rule."""
    t = TestResult("Lint test cases — expected lints fire")

    lint_dir = ASSETS_DIR / "lint-test-cases"
    if not lint_dir.exists():
        t.fail("assets/lint-test-cases/ not found")
        return t

    # Map each bad file to the lint string it MUST trigger
    expected_lints = {
        "bad_api_no_retry.xaml": "lint 36",
        "bad_attach_by_url.xaml": "lint 33",
        "bad_credential_args.xaml": "lint 34",
        "bad_hardcoded_url.xaml": "lint 37",
        "bad_no_incognito.xaml": "lint 38",
        "bad_password_text.xaml": "lint 35",
        "bad_throw_csharp.xaml": "C# syntax",
        "bad_extract_datatable.xaml": "lint 17",
        "bad_enum_namespace.xaml": "lint 40",
        "bad_hallucinated_ui_props.xaml": "lint 23",
    }

    missing = []
    for filename, expected in expected_lints.items():
        fpath = lint_dir / filename
        if not fpath.exists():
            missing.append(f"{filename} (file missing)")
            continue
        rc, stdout, stderr = run_validator(str(fpath), "--lint")
        if expected not in stdout:
            missing.append(f"{filename} (expected '{expected}' not in output)")

    # Also check good_browser_workflow.xaml passes without lint 33-38
    good = lint_dir / "good_browser_workflow.xaml"
    if good.exists():
        rc, stdout, stderr = run_validator(str(good), "--lint")
        for lint_num in ["lint 33", "lint 34", "lint 35", "lint 36", "lint 37", "lint 38"]:
            if lint_num in stdout:
                missing.append(f"good_browser_workflow.xaml (should NOT trigger {lint_num})")

    if missing:
        t.fail(f"{len(missing)} lint test case(s) failed: {'; '.join(missing[:5])}")
    else:
        t.ok(f"All {len(expected_lints)} bad files + 1 good file validated correctly")

    return t


def test_generator_smoke() -> TestResult:
    """All generators produce well-formed XML fragments with required attributes."""
    t = TestResult("Generator smoke test — all generators produce valid output")

    # Import generators
    sys.path.insert(0, str(SCRIPTS_DIR.parent))
    try:
        from scripts.generate_activities import (
            gen_ntypeinto, gen_nclick, gen_ngettext, gen_ncheckstate,
            gen_napplicationcard_open, gen_napplicationcard_attach,
            gen_napplicationcard_close, gen_napplicationcard_desktop_open,
            gen_ngotourl, gen_nselectitem, gen_nextractdata,
            gen_logmessage, gen_throw, gen_rethrow, gen_invoke_workflow,
            gen_retryscope, gen_try_catch, gen_if, gen_if_else_if,
            gen_assign, gen_multiple_assign, gen_add_queue_item,
            gen_get_queue_item, gen_getrobotcredential, gen_get_robot_asset,
            gen_foreach_row, gen_foreach, gen_foreach_file,
            gen_while, gen_do_while, gen_switch,
            gen_variables_block, gen_pick_login_validation,
            gen_copy_file, gen_move_file, gen_delete_file, gen_path_exists,
            gen_create_directory, gen_input_dialog, gen_message_box,
            gen_comment, gen_comment_out, gen_invoke_code, gen_invoke_method,
            gen_deserialize_json, gen_net_http_request,
            gen_build_data_table, gen_add_data_row, gen_add_data_column,
            gen_filter_data_table, gen_output_data_table,
            gen_sort_data_table, gen_remove_duplicate_rows,
            gen_join_data_tables, gen_lookup_data_table, gen_merge_data_table,
            gen_generate_data_table, gen_ngeturl, gen_flowchart,
            gen_read_range, gen_write_range, gen_write_cell,
            gen_database_connect, gen_execute_query, gen_execute_non_query,
            gen_take_screenshot_and_save, gen_read_pdf_text, gen_read_pdf_with_ocr,
            gen_send_mail, gen_get_imap_mail, gen_save_mail_attachments,
            # gen_create_form_task, gen_wait_for_form_task → moved to plugin (uipath-tasks)
            gen_break, gen_continue, gen_kill_process,
            gen_terminate_workflow, gen_add_log_fields, gen_remove_log_fields,
            gen_should_stop,
            gen_parallel, gen_parallel_foreach, gen_state_machine,
            gen_nhover, gen_ndoubleclick, gen_nrightclick,
            gen_nkeyboardshortcuts,
            gen_read_csv, gen_write_csv,
            gen_read_text_file, gen_write_text_file,
            gen_nmousescroll,
        )
    except ImportError as e:
        t.fail(f"Cannot import generators: {e}")
        return t

    # Load plugin generators (Tasks, etc.) — soft skip if not present
    gen_create_form_task = None
    gen_wait_for_form_task = None
    try:
        from plugin_loader import load_plugins, get_generators
        load_plugins()
        plugin_gens = get_generators()
        gen_create_form_task = plugin_gens.get("create_form_task")
        gen_wait_for_form_task = plugin_gens.get("wait_for_form_task")
        if not gen_create_form_task or not gen_wait_for_form_task:
            t.ok("Plugin generators not present (Tasks plugin not installed) — skipping plugin smoke tests")
            gen_create_form_task = None
            gen_wait_for_form_task = None
    except Exception as e:
        t.ok(f"Plugin generators not loaded ({e}) — skipping plugin smoke tests")

    scope = "test-scope-00000000-0000-0000-0000-000000000000"
    errors = []

    # Each tuple: (name, callable, required_substrings)
    smoke_tests = [
        # --- Already tested (35 existing) ---
        ("gen_break", lambda: gen_break("Break_1"),
         ["ui:Break", "IdRef"]),
        ("gen_continue", lambda: gen_continue("Continue_1"),
         ["ui:Continue", "IdRef"]),
        ("gen_kill_process", lambda: gen_kill_process("iexplore", "KP_1"),
         ["ui:KillProcess", "ProcessName"]),
        ("gen_terminate_workflow", lambda: gen_terminate_workflow("New Exception(\"x\")", "TW_1"),
         ["TerminateWorkflow", "Exception"]),
        ("gen_add_log_fields", lambda: gen_add_log_fields({"Field1": "[val]"}, "ALF_1"),
         ["AddLogFields", "AddLogField", "FieldName"]),
        ("gen_remove_log_fields", lambda: gen_remove_log_fields(["Field1"], "RLF_1"),
         ["RemoveLogFields", "x:String"]),
        ("gen_should_stop", lambda: gen_should_stop("boolStop", "SS_1"),
         ["ui:ShouldStop", "Result"]),
        ("gen_nclick", lambda: gen_nclick("Click", "<html />", "NC_1", scope),
         ["uix:NClick", "ScopeIdentifier"]),
        ("gen_ntypeinto", lambda: gen_ntypeinto("Type", "<html />", "[str]", "NT_1", scope),
         ["uix:NTypeInto", "Text="]),
        ("gen_ngettext", lambda: gen_ngettext("Get", "strOut", "NG_1", scope, selector="<html />"),
         ["uix:NGetText", "TextString="]),
        ("gen_logmessage", lambda: gen_logmessage("test", "LM_1"),
         ["ui:LogMessage", "Message="]),
        ("gen_throw", lambda: gen_throw("New Exception(\"x\")", "T_1"),
         ["Throw", "Exception="]),
        ("gen_assign", lambda: gen_assign("strX", '"hello"', "A_1"),
         ["Assign", "Assign.To", "Assign.Value"]),
        ("gen_if", lambda: gen_if("True", "IF_1", then_content="<!-- then -->"),
         ["If", "If.Condition", "If.Then"]),
        ("gen_try_catch", lambda: gen_try_catch("<!-- body -->", "TrySeq_1", "TC_1"),
         ["TryCatch", "Try"]),
        ("gen_invoke_workflow", lambda: gen_invoke_workflow("Sub.xaml", "Invoke Sub", "IWF_1"),
         ["InvokeWorkflowFile", "WorkflowFileName="]),
        # gen_delay intentionally blocked (raises ValueError) — use NCheckState
        ("gen_rethrow", lambda: gen_rethrow("RT_1"),
         ["Rethrow"]),
        ("gen_multiple_assign", lambda: gen_multiple_assign(
            [("strA", '"val"')], "MA_1"),
         ["MultipleAssign", "AssignOperation"]),
        ("gen_add_queue_item", lambda: gen_add_queue_item(
            'in_Config("QueueName").ToString', "AQI_1",
            item_fields={"Field1": "strVal"}),
         ["AddQueueItem", "QueueType="]),
        ("gen_foreach_row", lambda: gen_foreach_row("dt_Data", "FER_1",
            body_content="<!-- row -->", body_sequence_idref="Seq_FER_1"),
         ["ForEachRow", "DataTable="]),
        ("gen_variables_block", lambda: gen_variables_block(
            [("strName", "x:String")]),
         ["Variable", "Name="]),
        ("gen_build_data_table", lambda: gen_build_data_table("dt_Out",
            [("Col1", "String")], "BDT_1"),
         ["BuildDataTable", "TableInfo"]),
        ("gen_parallel", lambda: gen_parallel(["<!-- b1 -->", "<!-- b2 -->"], id_ref="P_1"),
         ["Parallel", "<!-- b1 -->"]),
        ("gen_parallel_foreach", lambda: gen_parallel_foreach(
            "x:String", "lstItems", "<!-- body -->", id_ref="PFE_1"),
         ["ParallelForEach", "DelegateInArgument", "ActivityAction"]),
        ("gen_state_machine", lambda: gen_state_machine(
            [{"ref": "S1", "display_name": "Init", "transitions": [
                {"to_ref": "S2", "display_name": "Go"}]},
             {"ref": "S2", "display_name": "End", "is_final": True}],
            initial_state_ref="S1", id_ref="SM_1"),
         ["StateMachine", "State", "FinalState", "Transition", "x:Reference"]),
        ("gen_nhover", lambda: gen_nhover("Hover menu", "<html />", "NH_1", scope,
            hover_time=3, cursor_motion_type="Smooth"),
         ["uix:NHover", "ScopeIdentifier", "NHover.Target", 'HoverTime="3"',
          'CursorMotionType="[UiPath.UIAutomationNext.Enums.CursorMotionType.Smooth]"']),
        ("gen_ndoubleclick", lambda: gen_ndoubleclick("Double Click", "<html />", "NDC_1", scope),
         ["uix:NClick", 'ClickType="Double"']),
        ("gen_nrightclick", lambda: gen_nrightclick("Right Click", "<html />", "NRC_1", scope),
         ["uix:NClick", 'MouseButton="Right"']),
        ("gen_nkeyboardshortcuts", lambda: gen_nkeyboardshortcuts(
            "Press Ctrl+C", "[d(hk)][d(ctrl)d(c)][u(c)u(ctrl)][u(hk)]", "NKS_1", scope),
         ["uix:NKeyboardShortcuts", "Shortcuts=", "HardwareEvents", "/>"]),
        ("gen_nkeyboardshortcuts_targeted", lambda: gen_nkeyboardshortcuts(
            "Press Ctrl+C on element", "[d(hk)][d(ctrl)d(c)][u(c)u(ctrl)][u(hk)]",
            "NKS_2", scope, selector="<html />"),
         ["NKeyboardShortcuts.Target", "TargetAnchorable"]),
        ("gen_read_csv", lambda: gen_read_csv("dt_Report", "RCSV_1",
            path_variable="strCsvPath"),
         ["ReadCsvFile", 'FilePath="{x:Null}"', "PathResource=", 'Delimitator="Comma"']),
        ("gen_read_csv_literal", lambda: gen_read_csv("dt_Data", "RCSV_2",
            file_path="C:\\Data\\input.csv"),
         ["ReadCsvFile", "FilePath=", 'DataTable="[dt_Data]"']),
        ("gen_write_csv", lambda: gen_write_csv("dt_Output", "WCSV_1",
            path_variable="strOutPath", delimiter="Tab"),
         ["AppendWriteCsvFile", 'Delimitator="Tab"', 'CsvAction="Write"', "ShouldQuote"]),
        ("gen_read_text_file", lambda: gen_read_text_file("strContent", "RTF_1",
            path_variable="strFilePath"),
         ["ReadTextFile", 'File="{x:Null}"', "FileName=", 'Content="[strContent]"']),
        ("gen_write_text_file", lambda: gen_write_text_file("strContent", "WTF_1",
            path_variable="strFilePath"),
         ["WriteTextFile", 'File="{x:Null}"', 'Output="{x:Null}"', 'Text="[strContent]"']),
        ("gen_nmousescroll", lambda: gen_nmousescroll("Scroll Down", "<html />", "NMS_1", scope,
            direction="Down", movement_units=10),
         ["uix:NMouseScroll", "SearchedElement", "TargetAnchorable",
          'Direction="Down"', 'MovementUnits="10"', "InArgument", "OutArgument"]),

        # --- NEW: 58 previously untested generators ---
        ("gen_add_data_column", lambda: gen_add_data_column("dt_Data", "NewCol", "ADC_1"),
         ["AddDataColumn", "ColumnName=", "DataTable="]),
        ("gen_add_data_row", lambda: gen_add_data_row("dt_Data",
            '{"val1", "val2"}', "ADR_1"),
         ["AddDataRow", "DataTable=", "ArrayRow="]),
        ("gen_comment", lambda: gen_comment("This is a comment", "CM_1"),
         ["ui:Comment", "Text="]),
        ("gen_comment_out", lambda: gen_comment_out("<!-- disabled -->", "Seq_CO_1", "CO_1"),
         ["ui:CommentOut", "Body"]),
        ("gen_copy_file", lambda: gen_copy_file("[strSource]", "[strDest]", "CF_1"),
         ["CopyFile", "Path=", "Destination="]),
        ("gen_create_directory", lambda: gen_create_directory("strDirPath", "CD_1"),
         ["CreateDirectory"]),
        ("gen_database_connect", lambda: gen_database_connect(
            "strConnStr", "dbConn", "DBC_1"),
         ["DatabaseConnect", "ConnectionSecureString=", "DatabaseConnection="]),
        ("gen_delete_file", lambda: gen_delete_file("strFilePath", "DF_1"),
         ["DeleteFileX", "Path="]),
        ("gen_deserialize_json", lambda: gen_deserialize_json(
            "strJson", "joResult", "DJ_1"),
         ["DeserializeJson", "JsonString=", "JsonObject="]),
        ("gen_do_while", lambda: gen_do_while("intCount < 10", "DW_1",
            body_content="<!-- loop -->", body_sequence_idref="Seq_DW_1"),
         ["DoWhile", "Condition=", "DoWhile"]),
        ("gen_execute_non_query", lambda: gen_execute_non_query(
            "UPDATE tbl SET col=1", "ENQ_1",
            connection_string_variable="strConnStr"),
         ["ExecuteNonQuery", "Sql="]),
        ("gen_execute_query", lambda: gen_execute_query(
            "SELECT * FROM tbl", "dt_Result", "EQ_1",
            connection_string_variable="strConnStr"),
         ["ExecuteQuery", "Sql=", "DataTable="]),
        ("gen_filter_data_table", lambda: gen_filter_data_table(
            "dt_Data", [("Column1", "=", '"value"', "And")], "FDT_1"),
         ["FilterDataTable", "DataTable=", "OutputDataTable="]),
        ("gen_flowchart", lambda: gen_flowchart(
            steps=[{"ref_id": "Step1", "display_name": "Start", "content": "<!-- start -->", "location": "100,100", "size": "300,200"}],
            decisions=[], start_ref_id="Step1", id_ref="FC_1"),
         ["Flowchart", "FlowStep", "x:Reference"]),
        ("gen_foreach", lambda: gen_foreach("lstItems", "FE_1",
            body_content="<!-- item -->", body_sequence_idref="Seq_FE_1"),
         ["ForEach", "ForEach.Body", "ActivityAction"]),
        ("gen_foreach_file", lambda: gen_foreach_file("strFolder", "FEF_1",
            body_content="<!-- file -->", body_sequence_idref="Seq_FEF_1"),
         ["ForEachFileX", "Folder="]),
        ("gen_generate_data_table", lambda: gen_generate_data_table(
            "strInput", "dt_Output", "GDT_1"),
         ["GenerateDataTable", "Input=", "DataTable="]),
        ("gen_get_imap_mail", lambda: gen_get_imap_mail("lstMail", "GIM_1"),
         ["GetIMAPMailMessages", "Messages="]),
        ("gen_get_queue_item", lambda: gen_get_queue_item(
            'in_Config("QueueName").ToString', "qi_TransactionItem", "GQI_1"),
         ["GetQueueItem", "QueueType=", "TransactionItem="]),
        ("gen_get_robot_asset", lambda: gen_get_robot_asset(
            '"MyAsset"', "strAssetValue", "GRA_1"),
         ["GetRobotAsset", "AssetName=", "OutArgument"]),
        ("gen_getrobotcredential", lambda: gen_getrobotcredential(
            '"CredentialAsset"', "strUser", "secstrPass", "GRC_1"),
         ["GetRobotCredential", "AssetName=", "Username=", "Password="]),
        ("gen_if_else_if", lambda: gen_if_else_if(
            [("intVal > 10", "<!-- high -->"), ("intVal > 5", "<!-- mid -->")],
            "IEI_1", else_content="<!-- low -->"),
         ["IfElseIfV2", "IfElseIfBlock", "Else"]),
        ("gen_input_dialog", lambda: gen_input_dialog(
            "Enter name", "Name Input", "strResult", "ID_1"),
         ["InputDialog", "Label=", "Title="]),
        ("gen_invoke_code", lambda: gen_invoke_code(
            'Console.WriteLine("test")', "IC_1",
            arguments=[("In", "x:String", "in_strVal", "[strVal]")]),
         ["InvokeCode", "Code=", "Language="]),
        ("gen_invoke_method", lambda: gen_invoke_method(
            "ToString", "IM_1", target_type="System.String"),
         ["InvokeMethod", "MethodName=", "TargetType="]),
        ("gen_join_data_tables", lambda: gen_join_data_tables(
            "dt_Left", "dt_Right", "dt_Joined",
            {"Col1": "Col1"}, "JDT_1"),
         ["JoinDataTables", "DataTable1=", "DataTable2=", "JoinType="]),
        ("gen_lookup_data_table", lambda: gen_lookup_data_table(
            "dt_Data", "strLookup", "LookupCol", "TargetCol",
            "strResult", "intRowIdx", "LDT_1"),
         ["LookupDataTable", "LookupValue=", "CellValue=", "RowIndex="]),
        ("gen_merge_data_table", lambda: gen_merge_data_table(
            "dt_Source", "dt_Dest", "MDT_1"),
         ["MergeDataTable", "Source=", "Destination="]),
        ("gen_message_box", lambda: gen_message_box("[strMsg]", "MB_1"),
         ["MessageBox", "Text="]),
        ("gen_move_file", lambda: gen_move_file("strSource", "strDest", "MF_1"),
         ["MoveFile", "Path=", "Destination="]),
        ("gen_napplicationcard_open", lambda: gen_napplicationcard_open(
            "Open Browser", "strUrl", "uiBrowser",
            "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "NAC_Open_1",
            body_content="<!-- browser body -->",
            body_sequence_idref="Seq_NAC_Open_1"),
         ["uix:NApplicationCard", "ScopeGuid=", "OutUiElement=", "NApplicationCard.Body"]),
        ("gen_napplicationcard_attach", lambda: gen_napplicationcard_attach(
            "Attach Browser", "uiBrowser",
            "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "NAC_Att_1",
            body_content="<!-- attach body -->",
            body_sequence_idref="Seq_NAC_Att_1"),
         ["uix:NApplicationCard", 'OpenMode="Never"', "InUiElement=", "NApplicationCard.Body"]),
        ("gen_napplicationcard_close", lambda: gen_napplicationcard_close(
            "uiBrowser",
            "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "NAC_Close_1",
            body_content="<!-- close body -->",
            body_sequence_idref="Seq_NAC_Close_1"),
         ["uix:NApplicationCard", 'CloseMode="Always"', "NApplicationCard.Body"]),
        ("gen_napplicationcard_desktop_open", lambda: gen_napplicationcard_desktop_open(
            "Open Notepad", "strExePath", "uiApp",
            "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "NAC_Desk_1",
            body_content="<!-- desktop body -->",
            body_sequence_idref="Seq_NAC_Desk_1"),
         ["uix:NApplicationCard", "FilePath=\"[strExePath]\"", "OutUiElement=", "NApplicationCard.Body"]),
        ("gen_ncheckstate", lambda: gen_ncheckstate(
            "Check Element", "<html />", "NCS_1", scope,
            if_exists_idref="Seq_Exists_1",
            if_not_exists_idref="Seq_NotExists_1",
            if_exists_body="<!-- exists -->",
            if_not_exists_body="<!-- not exists -->"),
         ["uix:NCheckState", "ScopeIdentifier"]),
        ("gen_net_http_request", lambda: gen_net_http_request(
            "GET", "strApiUrl", "strResponse", "HTTP_1"),
         ["NetHttpRequest", "Method=", "RequestUrl="]),
        ("gen_nextractdata", lambda: gen_nextractdata(
            "Extract Table", "dt_Extracted", "NED_1", scope,
            extract_metadata='<extract><row><column exact="1" name="Col1"><webctrl tag=\'TD\' /></column></row></extract>',
            extract_data_settings='<Table Type="List"><Column Identifier="Col1" ColumnType="Text" /></Table>'),
         ["uix:NExtractDataGeneric", "ExtractedData=", "ExtractMetadata=", "ExtractDataSettings="]),
        ("gen_ngeturl", lambda: gen_ngeturl("strCurrentUrl", "NGU_1"),
         ["uix:NGetUrl", "Url="]),
        ("gen_ngotourl", lambda: gen_ngotourl("strTargetUrl", "NGTU_1", scope),
         ["uix:NGoToUrl", "Url=", "ScopeIdentifier"]),
        ("gen_nselectitem", lambda: gen_nselectitem(
            "Select Status", "<html />", "strSelectedItem", "NSI_1", scope),
         ["uix:NSelectItem", "Item=", "ScopeIdentifier", "NSelectItem.Target"]),
        ("gen_output_data_table", lambda: gen_output_data_table(
            "dt_Data", "strOutput", "ODT_1"),
         ["OutputDataTable", "DataTable=", "Text="]),
        ("gen_path_exists", lambda: gen_path_exists(
            "strFilePath", "boolExists", "PE_1"),
         ["PathExists", "Path=", "Result="]),
        ("gen_pick_login_validation", lambda: gen_pick_login_validation(
            success_selector="<html />",
            error_selector="<html />",
            error_ui_variable="uiError",
            error_text_variable="strErrorText",
            scope_id=scope,
            pick_idref="Pick_1",
            success_branch_idref="PB_Success_1",
            failure_branch_idref="PB_Failure_1",
            success_checkstate_idref="NCS_Success_1",
            failure_checkstate_idref="NCS_Failure_1",
            success_if_exists_idref="Seq_SuccExists_1",
            success_if_not_exists_idref="Seq_SuccNotExists_1",
            failure_if_exists_idref="Seq_FailExists_1",
            failure_if_not_exists_idref="Seq_FailNotExists_1",
            success_action_idref="Seq_SuccAction_1",
            failure_action_idref="Seq_FailAction_1",
            gettext_idref="NGT_Error_1",
            throw_idref="Throw_Login_1",
            success_log_idref="Log_Success_1"),
         ["Pick", "PickBranch", "NCheckState", "NGetText", "Throw"]),
        ("gen_read_pdf_text", lambda: gen_read_pdf_text(
            "strPdfPath", "strPdfContent", "RPT_1"),
         ["ReadPDFText", "FileName=", "Text="]),
        ("gen_read_pdf_with_ocr", lambda: gen_read_pdf_with_ocr(
            "strPdfPath", "strOcrContent", "RPO_1"),
         ["ReadPDFWithOCR", "FileName=", "Text="]),
        ("gen_read_range", lambda: gen_read_range(
            "strWorkbook", "Sheet1", "dt_Excel", "RR_1"),
         ["ReadRange", "SheetName=", "DataTable="]),
        ("gen_remove_duplicate_rows", lambda: gen_remove_duplicate_rows(
            "dt_Data", "RDR_1"),
         ["RemoveDuplicateRows", "DataTable="]),
        ("gen_retryscope", lambda: gen_retryscope(
            "Retry Action", "RS_1",
            body_content="<!-- retryable -->",
            body_sequence_idref="Seq_RS_1"),
         ["RetryScope", "NumberOfRetries=", "RetryScope.ActivityBody"]),
        ("gen_save_mail_attachments", lambda: gen_save_mail_attachments(
            "mmMessage", "strAttachFolder", "SMA_1"),
         ["SaveMailAttachments", "Message=", "FolderPath="]),
        ("gen_send_mail", lambda: gen_send_mail(
            "strTo", "strSubject", "strBody", "SM_1"),
         ["SendMail", "To=", "Subject="]),
        ("gen_sort_data_table", lambda: gen_sort_data_table(
            "dt_Data", "ColumnName", "SDT_1"),
         ["SortDataTable", "DataTable=", "ColumnName="]),
        ("gen_switch", lambda: gen_switch(
            "strStatus", "SW_1",
            cases={"Open": "<!-- open -->", "Closed": "<!-- closed -->"},
            default_content="<!-- default -->", default_sequence_idref="Seq_Def_1"),
         ["Switch", "Default"]),
        ("gen_take_screenshot_and_save", lambda: gen_take_screenshot_and_save(
            "imgScreenshot", "strSavePath", "TSS_1"),
         ["TakeScreenshot", "Image="]),
        ("gen_while", lambda: gen_while(
            "intIdx < intMax", "WH_1",
            body_content="<!-- loop -->",
            body_sequence_idref="Seq_WH_1"),
         ["While", "Condition="]),
        ("gen_write_cell", lambda: gen_write_cell(
            "strWorkbook", "Sheet1", '"A1"', "strValue", "WC_1"),
         ["WriteCell", "SheetName=", "Cell="]),
        ("gen_write_range", lambda: gen_write_range(
            "strWorkbook", "Sheet1", "dt_Output", "WR_1"),
         ["WriteRange", "SheetName=", "DataTable="]),
    ]

    # Append plugin smoke tests only if plugins are loaded
    if gen_create_form_task:
        smoke_tests.append(
            ("gen_create_form_task", lambda: gen_create_form_task(
                '"Review Invoice"', "taskOut", '{}{"components":[]}', "CFT_1"),
             ["CreateFormTask", "TaskTitle=", "FormLayout="]))
    if gen_wait_for_form_task:
        smoke_tests.append(
            ("gen_wait_for_form_task", lambda: gen_wait_for_form_task(
                "taskObj", "WFT_1"),
             ["WaitForFormTaskAndResume", "TaskInput="]))

    for name, fn, required in smoke_tests:
        try:
            output = fn()
            if not output or not isinstance(output, str):
                errors.append(f"{name}: returned empty/non-string")
                continue
            for req in required:
                if req not in output:
                    errors.append(f"{name}: missing '{req}' in output")
                    break
        except Exception as e:
            errors.append(f"{name}: raised {type(e).__name__}: {e}")

    if errors:
        t.fail(f"{len(errors)} generator(s) failed smoke test")
        for err in errors[:10]:
            t.messages.append(f"       {err}")
    else:
        t.ok(f"All {len(smoke_tests)} generator smoke tests passed")

    return t


def test_dispatcher_test_file_transformation(tmpdir: str) -> TestResult:
    """Dispatcher scaffold transforms test case files from QueueItem to DataRow."""
    t = TestResult("Dispatcher scaffold test file type transformation")

    name = "TestDispTypes"
    cmd = [
        sys.executable, str(SCAFFOLD),
        "--name", name,
        "--variant", "dispatcher",
        "--transaction-type", "DataRow",
        "--output", tmpdir,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        t.fail(f"Scaffold failed: {proc.stderr}")
        return t

    project_dir = os.path.join(tmpdir, name)
    test_files = [
        "Tests/GetTransactionDataTestCase.xaml",
        "Tests/ProcessTestCase.xaml",
    ]
    for rel_path in test_files:
        fpath = os.path.join(project_dir, rel_path)
        if not os.path.exists(fpath):
            t.fail(f"Missing: {rel_path}")
            continue
        content = open(fpath, encoding="utf-8-sig").read()
        qi_count = content.count("ui:QueueItem")
        dr_count = content.count("sd:DataRow")
        if qi_count > 0:
            t.fail(f"{rel_path}: still has {qi_count} ui:QueueItem reference(s)")
        elif dr_count == 0:
            t.fail(f"{rel_path}: no sd:DataRow references found")
        else:
            t.ok(f"{rel_path}: {dr_count} sd:DataRow, 0 ui:QueueItem")

    return t


def test_add_variables_type_normalization() -> TestResult:
    """modify_framework.py add-variables normalizes short-form types."""
    t = TestResult("add-variables type normalization")

    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        from _mf_types import _normalize_var_type, VAR_TYPE_MAP
    except ImportError as e:
        t.fail(f"Import error: {e}")
        return t

    # Test short-form mappings
    test_cases = [
        ("DataTable", "sd:DataTable"),
        ("DataRow", "sd:DataRow"),
        ("String", "x:String"),
        ("SecureString", "ss:SecureString"),
        ("MailMessage", "snm:MailMessage"),
        ("Dictionary", "scg:Dictionary(x:String, x:Object)"),
    ]
    for short, expected in test_cases:
        result = _normalize_var_type(short)
        if result != expected:
            t.fail(f"'{short}' → '{result}' (expected '{expected}')")
        else:
            t.ok(f"'{short}' → '{result}'")

    # Test already-prefixed pass through
    prefixed_cases = ["sd:DataTable", "x:String", "snm:MailMessage", "ui:UiElement"]
    for ptype in prefixed_cases:
        result = _normalize_var_type(ptype)
        if result != ptype:
            t.fail(f"Prefixed '{ptype}' changed to '{result}'")
        else:
            t.ok(f"Prefixed '{ptype}' passed through")

    # Test unknown bare type raises ValueError
    try:
        _normalize_var_type("BrowserType")
        t.fail("'BrowserType' should have raised ValueError")
    except ValueError:
        t.ok("'BrowserType' correctly rejected with ValueError")

    return t


def test_annotations_validate() -> TestResult:
    """Annotation files conform to the schema in references/annotations/SCHEMA.md."""
    t = TestResult("Annotation schema — validate_annotations.py (lenient)")
    script = SCRIPTS_DIR / "validate_annotations.py"
    if not script.exists():
        t.fail(f"validate_annotations.py not found at {script}")
        return t
    res = subprocess.run(
        [sys.executable, str(script), "--quiet"],
        capture_output=True,
        text=True,
        cwd=str(SKILL_DIR.parent),
    )
    summary = ""
    for line in (res.stdout + res.stderr).splitlines():
        if line.startswith("summary:"):
            summary = line.strip()
            break
    if res.returncode != 0:
        t.fail(f"validator exited {res.returncode}; {summary}")
        for line in (res.stderr or "").splitlines()[:5]:
            t.messages.append(f"       {line}")
    else:
        t.ok(summary or "validator clean")
    return t


def test_validate_snippet_rejects_non_xaml() -> TestResult:
    """validate_snippet rejects file paths, empty strings, and non-XML input."""
    t = TestResult("validate_snippet rejects non-XAML input")

    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        from _mf_snippet_checks import validate_snippet
    except ImportError as e:
        t.fail(f"Import error: {e}")
        return t

    # Should be REJECTED
    reject_cases = [
        ("Windows file path", "C:/Users/marce/Desktop/specs/snippet.json"),
        ("Windows backslash path", "C:\\Users\\marce\\snippet.xaml"),
        ("Unix file path", "/home/user/snippet.json"),
        ("Relative file path", "./specs/dispatcher_init.json"),
        ("Empty string", ""),
        ("Whitespace only", "   "),
        ("Plain text", "hello world"),
        ("JSON object", '{"key": "value"}'),
    ]
    for label, inp in reject_cases:
        result = validate_snippet(inp)
        if result:
            t.ok(f"Rejected: {label}")
        else:
            t.fail(f"Should reject '{label}' but accepted it")

    # Should be ACCEPTED
    accept_cases = [
        ("Self-closing XAML", '<ui:LogMessage DisplayName="Log" />'),
        ("InvokeWorkflowFile", '<ui:InvokeWorkflowFile WorkflowFileName="Test.xaml" />'),
        ("XAML with path in attr", '<ui:InvokeWorkflowFile WorkflowFileName="C:/project/Test.xaml" />'),
    ]
    for label, inp in accept_cases:
        result = validate_snippet(inp)
        if not result:
            t.ok(f"Accepted: {label}")
        else:
            t.fail(f"Should accept '{label}' but rejected: {result[0][:60]}")

    return t


def main():
    parser = argparse.ArgumentParser(description="UiPath skill regression test")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    parser.add_argument("--tmpdir", default=None,
                        help="Base directory for scratch files (default: system temp). "
                             "Use in restricted environments where the default temp is not writable.")
    args = parser.parse_args()

    base_tmp = args.tmpdir
    if base_tmp:
        os.makedirs(base_tmp, exist_ok=True)

    global TMPDIR_BASE
    TMPDIR_BASE = base_tmp

    tmpdir = tempfile.mkdtemp(prefix="uipath_regtest_", dir=base_tmp)

    try:
        tests = [
            test_golden_templates(),
            test_lint_test_cases(),
            test_generator_smoke(),
            test_reference_files_exist(),
            test_skill_md_size(),
            test_template_coverage(),
            test_critical_rules_in_skill_md(),
            test_decomposition_rules_complete(),
            test_playwright_safety_rules(),
            test_namespace_conflict_detection(),
            test_line_count_accuracy(),
            test_generator_and_lint_counts(),
            test_template_copy_modify(),
            test_scaffold_variant(tmpdir, "sequence", "TestSequence"),
            test_scaffold_variant(tmpdir, "dispatcher", "TestDispatcher"),
            test_scaffold_variant(tmpdir, "performer", "TestPerformer"),
            test_dispatcher_test_file_transformation(tmpdir),
            test_add_variables_type_normalization(),
            test_validate_snippet_rejects_non_xaml(),
            test_annotations_validate(),
        ]
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    total = len(tests)
    passed = sum(1 for t in tests if t.passed)
    failed = total - passed

    for t in tests:
        if args.verbose or not t.passed:
            print(t.summary())
        else:
            status = "PASS" if t.passed else "FAIL"
            print(f"{status}  {t.name}")

    print(f"\n{'='*60}")
    print(f"REGRESSION: {passed}/{total} passed" +
          (f", {failed} FAILED" if failed else " — all clear"))
    print(f"{'='*60}")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
