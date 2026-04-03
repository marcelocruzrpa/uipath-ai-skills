"""Action Center battle test grading functions.

Moved from uipath-core/scripts/grade_battle_test.py to keep AC-specific
grading logic in the plugin. Imports shared primitives from core.
"""

from pathlib import Path

from grade_battle_test import (
    GradeResult,
    find_xaml_files,
    read_text,
    check_project_json_exists,
    check_nuget_dependency,
    check_lint_passes,
)


# ---------------------------------------------------------------------------
# Action Center checks
# ---------------------------------------------------------------------------

def check_supports_persistence(gr: GradeResult, pj_data: dict | None):
    if not pj_data:
        gr.check("supportsPersistence: true", False)
        return
    ro = pj_data.get("runtimeOptions", {})
    gr.check("supportsPersistence: true",
             ro.get("supportsPersistence") is True)


def check_persistence_in_main_only(gr: GradeResult, project_dir: Path):
    """Check WaitForFormTaskAndResume only in Main.xaml (A-2)."""
    violations = []
    for xaml in find_xaml_files(project_dir):
        content = read_text(xaml)
        if "WaitForFormTaskAndResume" in content and xaml.name != "Main.xaml":
            violations.append(xaml.name)
    gr.check("Persistence activities in Main.xaml only (A-2)", len(violations) == 0,
             f"found in: {', '.join(violations)}" if violations else "")


def check_formdata_submit_button(gr: GradeResult, project_dir: Path):
    """Check form.io schemas include a submit button."""
    for xaml in find_xaml_files(project_dir):
        content = read_text(xaml)
        if "CreateFormTask" in content and "submit" not in content.lower():
            gr.check("Form.io schema has submit button", False, xaml.name)
            return
    gr.check("Form.io schema has submit button", True)


def check_retry_scope_on_create_task(gr: GradeResult, project_dir: Path):
    """Check CreateFormTask is wrapped in RetryScope (A-11)."""
    for xaml in find_xaml_files(project_dir):
        content = read_text(xaml)
        if "CreateFormTask" in content:
            has_retry = "RetryScope" in content
            gr.check("CreateFormTask wrapped in RetryScope (A-11)", has_retry,
                     xaml.name)
            return


# ---------------------------------------------------------------------------
# Suite grader
# ---------------------------------------------------------------------------

def grade_ac(scenario: int, project_dir: Path) -> GradeResult:
    gr = GradeResult()
    pj = check_project_json_exists(gr, project_dir)

    # Common AC checks
    check_nuget_dependency(gr, pj, "UiPath.Persistence.Activities")
    check_nuget_dependency(gr, pj, "UiPath.FormActivityLibrary")
    check_supports_persistence(gr, pj)
    check_persistence_in_main_only(gr, project_dir)
    check_retry_scope_on_create_task(gr, project_dir)
    check_formdata_submit_button(gr, project_dir)
    check_lint_passes(gr, project_dir)

    if scenario == 2:
        # Editable datagrid
        for xaml in find_xaml_files(project_dir):
            content = read_text(xaml)
            if "datagrid" in content.lower():
                gr.check("Form.io datagrid component present", True)
                break
        else:
            gr.check("Form.io datagrid component present", False)

    elif scenario == 3:
        # Shadow task pattern
        for xaml in find_xaml_files(project_dir):
            content = read_text(xaml)
            if "ForEach" in content and "CreateFormTask" in content:
                gr.check("CreateFormTask inside ForEach loop", True)
                break
        else:
            gr.check("CreateFormTask inside ForEach loop", False)

    elif scenario == 5:
        # Negative: persistence in sub-workflow
        # This scenario expects the agent to REFUSE — hard to auto-grade
        # Check if it was generated wrong anyway
        violations = []
        for xaml in find_xaml_files(project_dir):
            content = read_text(xaml)
            if "WaitForFormTaskAndResume" in content and xaml.name != "Main.xaml":
                violations.append(xaml.name)
        if violations:
            gr.check("Agent refused persistence in sub-workflow", False,
                     f"WaitForFormTaskAndResume found in: {', '.join(violations)}")
        else:
            gr.check("No persistence in sub-workflows (correct pattern)", True)

    return gr
