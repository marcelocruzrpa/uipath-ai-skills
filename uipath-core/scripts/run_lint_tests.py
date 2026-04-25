#!/usr/bin/env python3
"""Lint regression test suite.

Runs validate_xaml --lint against intentionally bad XAML files
and asserts the expected lint rules fire. Also validates that good
files pass cleanly.

Usage:
    python3 scripts/run_lint_tests.py
"""

import re
import subprocess
import sys
import os

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VALIDATE = os.path.join(SCRIPT_DIR, "validate_xaml")
TEST_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "assets", "lint-test-cases")

# Each test: (filename, expected_substring_in_output, should_be_error_or_warn)
TESTS = [
    # Bad files — each should trigger specific lint
    ("bad_hardcoded_url.xaml", "lint 37", "WARN"),
    ("bad_no_incognito.xaml", "lint 38", "WARN"),
    ("bad_credential_args.xaml", "credential", "WARN"),
    ("bad_throw_csharp.xaml", "C# syntax", "ERROR"),
    ("bad_api_no_retry.xaml", "lint 36", "ERROR"),
    ("bad_attach_by_url.xaml", "ByUrl", "ERROR"),
    ("bad_password_text.xaml", "SecureText", "WARN"),
    ("bad_xlist_selectitem.xaml", "x:List", "ERROR"),
    ("bad_nselectitem_version.xaml", "NSelectItem Version", "ERROR"),
    ("bad_addqueue_dict_expr.xaml", "Missing key value", "ERROR"),
    ("bad_closemode_always.xaml", "lint 49", "WARN"),
    ("bad_GetTransactionData_dispatcher.xaml", "lint 51", "ERROR"),
    ("bad_gettext_interactionmode.xaml", "lint 53", "ERROR"),
    ("bad_queue_name_property.xaml", "lint 54", "ERROR"),
    ("bad_invoke_empty_arg.xaml", "lint 55", "WARN"),
    ("bad_invoke_direction_mismatch.xaml", "lint 56", "ERROR"),
    ("bad_references_xstring.xaml", "lint 57", "ERROR"),
    ("bad_orphaned_scoped_activity.xaml", "lint 58", "ERROR"),
    ("bad_attach_no_uielement.xaml", "lint 59", "WARN"),
    ("bad_no_log_bookends.xaml", "lint 62", "WARN"),
    ("bad_fqdn_bre.xaml", "lint 7", "ERROR"),
    ("bad_addqueue_ui_inargument.xaml", "lint 20", "ERROR"),
    ("bad_undeclared_vars.xaml", "lint 67", "ERROR"),
    ("bad_empty_catch.xaml", "lint 108", "ERROR"),
    ("bad_delay_activity.xaml", "lint 109", "WARN"),
    ("bad_launch_login_no_validation.xaml", "lint 69", "ERROR"),
    ("bad_double_escaped_quotes.xaml", "lint 71", "ERROR"),
    ("bad_empty_field_mode.xaml", "lint 70", "ERROR"),
    ("bad_selector_double_quotes.xaml", "lint 89", "ERROR"),
    ("bad_selector_double_escaped.xaml", "lint 90", "ERROR"),
    ("bad_invalid_array_type.xaml", "lint 93", "ERROR"),
    ("bad_fqdn_type_arguments.xaml", "lint 99", "ERROR"),
    ("bad_WebApp_Login.xaml", "lint 72", "ERROR"),
    ("bad_nextractdata_hallucinated.xaml", "lint 73", "ERROR"),
    ("bad_InitAllApplications.xaml", "lint 74", "ERROR"),
    ("bad_Process.xaml", "lint 75", "ERROR"),
    ("bad_argument_type_mismatch.xaml", "lint 76", "ERROR"),
    ("bad_InitAllApps_missing_uielement_out.xaml", "lint 77", "ERROR"),
    ("bad_uielement_in_config.xaml", "lint 78", "ERROR"),
    ("bad_duplicate_invoke_arguments.xaml", "lint 79", "ERROR"),
    ("bad_duplicate_invoke_arguments_children.xaml", "lint 79", "ERROR"),
    ("bad_dict_stray_invoke_argument.xaml", "lint 79", "ERROR"),
    ("bad_nselectitem_null_item.xaml", "lint 80", "ERROR"),
    ("bad_wrong_datatable_prefix.xaml", "lint 87", "ERROR"),
    ("bad_bare_datarow_type.xaml", "lint 87", "ERROR"),
    ("bad_sequence_variables_after_children.xaml", "lint 88", "ERROR"),
    ("bad_bare_variable_no_wrapper.xaml", "lint 88", "ERROR"),
    ("bad_main_undeclared_invoke_var_Main.xaml", "lint 81", "ERROR"),
    ("bad_bare_config_in_process.xaml", "lint 82", "ERROR"),
    ("bad_double_bracket_expr.xaml", "lint 83", "ERROR"),
    # --- New lint coverage tests ---
    ("bad_inline_result_extractdata.xaml", "lint 17", "ERROR"),
    ("bad_targetanchorable_child.xaml", "lint 23", "ERROR"),
    # AC-26 (persistence in sub-workflows) → moved to uipath-tasks plugin
    ("bad_invoke_code_datatable.xaml", "lint 27", "WARN"),
    ("bad_element_type.xaml", "lint 28", "ERROR"),
    ("bad_nselectitem_interactionmode.xaml", "lint 30", "ERROR"),
    ("bad_continue_on_error_x.xaml", "lint 31", "ERROR"),
    ("bad_special_folder_temp.xaml", "lint 32", "ERROR"),
    ("bad_invoke_code_sql.xaml", "lint 33", "ERROR"),
    ("bad_invoke_code_screenshot.xaml", "lint 34", "ERROR"),
    ("bad_invoke_code_filedelete.xaml", "lint 35", "ERROR"),
    ("bad_enum_namespace.xaml", "lint 40", "ERROR"),
    ("bad_fuzzy_default.xaml", "lint 41", "WARN"),
    ("bad_AppName_NavigateTo.xaml", "lint 45", "ERROR"),
    ("bad_AppName_DoAction.xaml", "lint 47", "WARN"),
    ("bad_AppName_Launch_novalidation.xaml", "lint 64", "WARN"),
    ("bad_AppName_Launch_noout.xaml", "lint 66", "ERROR"),
    ("bad_wrong_xmlns_url.xaml", "lint 95", "ERROR"),
    ("bad_css_selector.xaml", "lint 97", "WARN"),
    ("bad_no_trycatch_ui_heavy.xaml", "lint 103", "WARN"),
    ("bad_hardcoded_user_path.xaml", "lint 104", "WARN"),
    ("bad_tab_click_no_sync.xaml", "lint 105", "WARN"),
    ("bad_invoke_bare_typearg.xaml", "lint 110", "ERROR"),
    ("bad_ncheckstate_empty_ifnotexists_NavigateToTab.xaml", "lint 111", "WARN"),
    ("bad_nclick_checkbox.xaml", "lint 112", "WARN"),
    ("bad_assign_type_mismatch.xaml", "lint 113", "ERROR"),
    ("bad_assign_plain_datatable.xaml", "lint 113", "ERROR"),
    ("bad_addrow_mixed_types.xaml", "lint 114", "ERROR"),
]

GOOD_FILES = [
    "good_browser_workflow.xaml",
    "good_addrow_typed_object.xaml",
]

# Tests that require specific filenames (path relative to lint-test-cases/)
FILENAME_SENSITIVE_TESTS = [
    ("filename-sensitive/Main.xaml", "lint 46", "WARN"),
    ("filename-sensitive/CloseAllApplications.xaml", "lint 65", "ERROR"),
    ("filename-sensitive/Framework/Process.xaml", "lint 100", "ERROR"),
]

# Tests that require project-level scanning (directory path relative to lint-test-cases/)
PROJECT_TESTS = [
    ("bad_project_crossfile", "lint 50", "ERROR"),
    ("bad_project_crossfile", "lint 60", "WARN"),
    ("bad_project_crossfile", "lint 63", "WARN"),
    ("bad_project_cycle", "lint 101", "ERROR"),
    ("bad_project_orphan", "lint 102", "WARN"),
    # Version-compatibility lints (120/121/122) — directory fixtures with project.json
    ("bad_project_version_compat", "lint 120", "ERROR"),
    ("bad_project_version_compat", "lint 121", "ERROR"),
    ("bad_project_version_compat_band26", "lint 122", "ERROR"),
]


# Lint numbers deliberately excluded from test coverage with justification.
# Every entry here must explain WHY the lint can't be tested.
EXCLUDED_LINTS = {
    39: "Informational OK message (not error/warn) — lists Config keys referenced",
    61: "Requires openpyxl + real Config.xlsx at project level — low ROI",
    68: "Requires REFramework project context (Framework/ dir) — single-file lint test can't trigger",
    94: "Project-level Object Repository check — requires .objects/ directory + UI XAML files",
    106: "Requires NApplicationCard with desktop FilePath — hard to create minimal test without desktop app context",
    107: "Requires NApplicationCard with desktop FilePath — hard to create minimal test without desktop app context",
}

# Lints provided by plugin skills — tested only when the plugin is installed.
# These are excluded from stale-exclusion checks when the plugin isn't loaded.
# Populated dynamically from plugin_loader.
PLUGIN_TESTS = []
try:
    from plugin_loader import load_plugins, get_lint_test_fixtures
    load_plugins()
    for filename, expected_substr, severity, _fixture_dir in get_lint_test_fixtures():
        PLUGIN_TESTS.append((filename, expected_substr, severity))
except ImportError:
    pass


def get_tested_lint_numbers() -> set[int]:
    """Extract all lint numbers covered by test arrays."""
    import re
    tested = set()
    all_tests = TESTS + FILENAME_SENSITIVE_TESTS + PROJECT_TESTS
    # Include all PLUGIN_TESTS (they use AC-N or SAP-N format)
    all_tests.extend(PLUGIN_TESTS)
    for _file, substr, _sev in all_tests:
        m = re.search(r"lint (\d+)", substr)
        if m:
            tested.add(int(m.group(1)))
    return tested


def get_tested_plugin_ids() -> set[str]:
    """Extract plugin lint IDs (AC-N, SAP-NNN) covered by test arrays."""
    import re
    ids = set()
    for _file, substr, _sev in PLUGIN_TESTS:
        m = re.search(r"(AC-\d+|SAP-\d+)", substr)
        if m:
            ids.add(m.group(1))
    return ids


def get_code_lint_numbers() -> set[int]:
    """Extract all [lint N] numbers emitted by validate_xaml + plugin lint rules."""
    import re, inspect
    validate_pkg = os.path.join(SCRIPT_DIR, "validate_xaml")
    content = ""
    for fname in os.listdir(validate_pkg):
        if fname.endswith(".py"):
            content += open(os.path.join(validate_pkg, fname), encoding="utf-8").read()
    numbers = set(int(x) for x in re.findall(r"\[lint (\d+)\]", content))
    # Also scan dependency_graph.py for lint numbers
    dep_graph_path = os.path.join(SCRIPT_DIR, "dependency_graph.py")
    if os.path.isfile(dep_graph_path):
        dep_content = open(dep_graph_path, encoding="utf-8").read()
        numbers.update(int(x) for x in re.findall(r"\[lint (\d+)\]", dep_content))
    # Also scan plugin lint rule sources
    try:
        import sys
        sys.path.insert(0, SCRIPT_DIR)
        from plugin_loader import load_plugins, get_lint_rules
        load_plugins()
        for lint_fn, _ in get_lint_rules():
            src = inspect.getsource(lint_fn)
            numbers.update(int(x) for x in re.findall(r"\[lint (\d+)\]", src))
            # Plugin lint IDs (AC-N, SAP-N) are tracked separately via get_tested_plugin_ids()
    except Exception:
        pass
    return numbers


def check_lint_coverage() -> tuple[bool, list[str]]:
    """Verify every lint number in code has a test case (or explicit exclusion).

    Returns (passed, messages).
    """
    code_lints = get_code_lint_numbers()
    tested_lints = get_tested_lint_numbers()
    excluded_lints = set(EXCLUDED_LINTS.keys())

    covered = tested_lints | excluded_lints
    uncovered = sorted(code_lints - covered)
    stale_exclusions = sorted(excluded_lints - code_lints)
    stale_tests = sorted(tested_lints - code_lints)

    msgs = []
    ok = True

    if uncovered:
        ok = False
        msgs.append(
            f"FAIL  {len(uncovered)} lint number(s) have NO test case and NO exclusion: "
            f"{uncovered}. Add a bad_ test file or add to EXCLUDED_LINTS with justification."
        )
    if stale_exclusions:
        ok = False
        msgs.append(
            f"FAIL  EXCLUDED_LINTS contains number(s) not in code: {stale_exclusions}. "
            f"Remove stale entries."
        )
    if stale_tests:
        msgs.append(
            f"WARN  Test arrays reference lint number(s) not in code: {stale_tests}. "
            f"These tests may be stale."
        )

    if ok and not stale_tests:
        msgs.append(
            f"PASS  All {len(code_lints)} lint numbers covered "
            f"({len(tested_lints)} tested, {len(excluded_lints)} excluded)"
        )

    return ok, msgs


def _resolve_plugin_fixture(filename: str) -> str | None:
    """Resolve a plugin lint test fixture file path.

    Checks core TEST_DIR first, then plugin-registered fixture directories.
    """
    core_path = os.path.join(TEST_DIR, filename)
    if os.path.exists(core_path):
        return core_path
    try:
        from plugin_loader import get_lint_test_fixtures
        for fn, _, _, fixture_dir in get_lint_test_fixtures():
            if fn == filename:
                plugin_path = os.path.join(fixture_dir, filename)
                if os.path.exists(plugin_path):
                    return plugin_path
    except ImportError:
        pass
    return None


def run_lint(filepath: str) -> str:
    """Run validate_xaml --lint on a file and return output."""
    result = subprocess.run(
        [sys.executable, VALIDATE, filepath, "--lint"],
        capture_output=True, text=True
    )
    return result.stdout + result.stderr


def main():
    passed = 0
    failed = 0
    total = len(TESTS) + len(GOOD_FILES) + len(FILENAME_SENSITIVE_TESTS) + len(PROJECT_TESTS)

    print(f"Running {total} lint regression tests...\n")

    # Test bad files — expected to trigger specific lints
    for filename, expected_substr, severity in TESTS:
        filepath = os.path.join(TEST_DIR, filename)
        if not os.path.exists(filepath):
            print(f"  SKIP  {filename} — file not found")
            continue

        output = run_lint(filepath)
        found = expected_substr.lower() in output.lower()
        severity_found = f"[{severity}]" in output

        if found and severity_found:
            print(f"  PASS  {filename} — triggered '{expected_substr}' as [{severity}]")
            passed += 1
        else:
            print(f"  FAIL  {filename} — expected '{expected_substr}' [{severity}]")
            print(f"         Got: {output.strip()[:200]}")
            failed += 1

    # Test plugin-provided lints — only when the plugin is installed
    code_lints = get_code_lint_numbers()
    active_plugin_tests = []
    for filename, expected_substr, severity in PLUGIN_TESTS:
        # Plugin tests use AC-N or SAP-NNN format (not lint N), so match both
        m = re.search(r"(?:lint |AC-|SAP-)(\d+)", expected_substr)
        if m:
            # Always include plugin tests — they're gated by file existence
            active_plugin_tests.append((filename, expected_substr, severity))
    if active_plugin_tests:
        total += len(active_plugin_tests)
        for filename, expected_substr, severity in active_plugin_tests:
            filepath = _resolve_plugin_fixture(filename)
            if not filepath or not os.path.exists(filepath):
                print(f"  SKIP  {filename} — file not found")
                continue
            output = run_lint(filepath)
            found = expected_substr.lower() in output.lower()
            severity_found = f"[{severity}]" in output
            if found and severity_found:
                print(f"  PASS  {filename} — triggered '{expected_substr}' as [{severity}] (plugin)")
                passed += 1
            else:
                print(f"  FAIL  {filename} — expected '{expected_substr}' [{severity}] (plugin)")
                print(f"         Got: {output.strip()[:200]}")
                failed += 1

    # Test good files — expected to pass with 0 errors
    for filename in GOOD_FILES:
        filepath = os.path.join(TEST_DIR, filename)
        if not os.path.exists(filepath):
            print(f"  SKIP  {filename} — file not found")
            continue

        output = run_lint(filepath)
        has_error = "[ERROR]" in output

        if not has_error:
            print(f"  PASS  {filename} — no errors (clean)")
            passed += 1
        else:
            print(f"  FAIL  {filename} — expected clean, got errors")
            print(f"         Got: {output.strip()[:200]}")
            failed += 1

    # Test filename-sensitive files — need specific basenames to trigger
    for relpath, expected_substr, severity in FILENAME_SENSITIVE_TESTS:
        filepath = os.path.join(TEST_DIR, relpath)
        if not os.path.exists(filepath):
            print(f"  SKIP  {relpath} — file not found")
            continue

        output = run_lint(filepath)
        found = expected_substr.lower() in output.lower()
        severity_found = f"[{severity}]" in output

        if found and severity_found:
            print(f"  PASS  {relpath} — triggered '{expected_substr}' as [{severity}]")
            passed += 1
        else:
            print(f"  FAIL  {relpath} — expected '{expected_substr}' [{severity}]")
            print(f"         Got: {output.strip()[:200]}")
            failed += 1

    # Test project-level lints — run against a directory
    for relpath, expected_substr, severity in PROJECT_TESTS:
        dirpath = os.path.join(TEST_DIR, relpath)
        if not os.path.isdir(dirpath):
            print(f"  SKIP  {relpath}/ — directory not found")
            continue

        output = run_lint(dirpath)
        found = expected_substr.lower() in output.lower()
        severity_found = f"[{severity}]" in output

        if found and severity_found:
            print(f"  PASS  {relpath}/ — triggered '{expected_substr}' as [{severity}]")
            passed += 1
        else:
            print(f"  FAIL  {relpath}/ — expected '{expected_substr}' [{severity}]")
            print(f"         Got: {output.strip()[:300]}")
            failed += 1

    # Lint coverage check — every lint number in code must have a test or exclusion
    coverage_ok, coverage_msgs = check_lint_coverage()
    for msg in coverage_msgs:
        print(f"  {msg}")
    if not coverage_ok:
        failed += 1
    else:
        passed += 1
    total += 1

    # Summary
    print(f"\n{'=' * 50}")
    print(f"LINT TESTS: {passed}/{total} passed, {failed} failed")
    print(f"{'=' * 50}")

    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
