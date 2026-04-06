"""Tasks battle test grading functions.

Moved from uipath-core/scripts/grade_battle_test.py to keep task-specific
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
# Tasks checks
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
    """Check CreateFormTask or CreateExternalTask is wrapped in RetryScope."""
    for xaml in find_xaml_files(project_dir):
        content = read_text(xaml)
        if "CreateFormTask" in content or "CreateExternalTask" in content:
            has_retry = "RetryScope" in content
            gr.check("Create*Task wrapped in RetryScope", has_retry,
                     xaml.name)
            return


def check_external_task_present(gr: GradeResult, project_dir: Path):
    """Check CreateExternalTask activity is present."""
    for xaml in find_xaml_files(project_dir):
        content = read_text(xaml)
        if "CreateExternalTask" in content:
            gr.check("CreateExternalTask activity present", True)
            return
    gr.check("CreateExternalTask activity present", False)


def check_wait_external_in_main_only(gr: GradeResult, project_dir: Path):
    """Check WaitForExternalTaskAndResume only in Main.xaml."""
    violations = []
    for xaml in find_xaml_files(project_dir):
        content = read_text(xaml)
        if "WaitForExternalTaskAndResume" in content and xaml.name != "Main.xaml":
            violations.append(xaml.name)
    gr.check("WaitForExternalTaskAndResume in Main.xaml only", len(violations) == 0,
             f"found in: {', '.join(violations)}" if violations else "")


def check_get_form_tasks_present(gr: GradeResult, project_dir: Path):
    """Check GetFormTasks activity is present."""
    for xaml in find_xaml_files(project_dir):
        content = read_text(xaml)
        if "GetFormTasks" in content:
            gr.check("GetFormTasks activity present", True)
            return
    gr.check("GetFormTasks activity present", False)


def check_complete_task_present(gr: GradeResult, project_dir: Path):
    """Check CompleteTask activity is present."""
    for xaml in find_xaml_files(project_dir):
        content = read_text(xaml)
        if "CompleteTask" in content:
            gr.check("CompleteTask activity present", True)
            return
    gr.check("CompleteTask activity present", False)


def check_assign_tasks_present(gr: GradeResult, project_dir: Path):
    """Check AssignTasks activity is present."""
    for xaml in find_xaml_files(project_dir):
        content = read_text(xaml)
        if "AssignTasks" in content:
            gr.check("AssignTasks activity present", True)
            return
    gr.check("AssignTasks activity present", False)


def check_no_persistence_activities(gr: GradeResult, project_dir: Path):
    """Check that NO wait-and-resume activities are present (for batch workflows)."""
    persistence_names = [
        "WaitForFormTaskAndResume", "WaitForExternalTaskAndResume",
        "WaitForAppTaskAndResume",
    ]
    for xaml in find_xaml_files(project_dir):
        content = read_text(xaml)
        for name in persistence_names:
            if name in content:
                gr.check("No persistence activities (batch workflow)", False,
                         f"{name} found in {xaml.name}")
                return
    gr.check("No persistence activities (batch workflow)", True)


# ---------------------------------------------------------------------------
# Suite grader
# ---------------------------------------------------------------------------

def grade_ac(scenario: int, project_dir: Path) -> GradeResult:
    gr = GradeResult()
    pj = check_project_json_exists(gr, project_dir)

    # All AC scenarios need the persistence package
    check_nuget_dependency(gr, pj, "UiPath.Persistence.Activities")
    check_lint_passes(gr, project_dir)

    # Form task scenarios (1-5) need FormActivityLibrary + form-specific checks
    is_form_scenario = scenario in (1, 2, 3, 4, 5, 8)
    if is_form_scenario:
        check_nuget_dependency(gr, pj, "UiPath.FormActivityLibrary")
        check_formdata_submit_button(gr, project_dir)

    # Scenarios with persistence points need supportsPersistence + Main.xaml constraint
    has_persistence = scenario not in (7,)  # scenario 7 is batch recovery, no persistence
    if has_persistence:
        check_supports_persistence(gr, pj)
        check_persistence_in_main_only(gr, project_dir)
        check_retry_scope_on_create_task(gr, project_dir)

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

    elif scenario == 6:
        # External Task Integration (JIRA)
        check_external_task_present(gr, project_dir)
        check_wait_external_in_main_only(gr, project_dir)
        # Check ExternalTag is set (not {x:Null})
        for xaml in find_xaml_files(project_dir):
            content = read_text(xaml)
            if "CreateExternalTask" in content:
                has_tag = 'ExternalTag="{x:Null}"' not in content
                gr.check("ExternalTag set (not x:Null)", has_tag)
                break

    elif scenario == 7:
        # Recovery Workflow (GetFormTasks)
        check_get_form_tasks_present(gr, project_dir)
        check_complete_task_present(gr, project_dir)
        check_assign_tasks_present(gr, project_dir)
        check_no_persistence_activities(gr, project_dir)

    elif scenario == 8:
        # Programmatic Escalation (Assign + Complete)
        check_assign_tasks_present(gr, project_dir)
        check_complete_task_present(gr, project_dir)
        check_persistence_in_main_only(gr, project_dir)

    return gr
