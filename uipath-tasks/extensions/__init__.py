"""UiPath Tasks skill extension — registers generators, lints, and hooks.

This module is auto-discovered by plugin_loader.load_plugins() and registers
long-running task functionality (form tasks, external tasks, task management)
with the core skill's plugin system.

Uses relative imports (.generators, .lint_rules, .scaffold_hooks) so that
each plugin's modules are isolated — no sys.path pollution, no cross-plugin
name collisions even when multiple uipath-* skills coexist.
"""

from pathlib import Path

from plugin_loader import (
    register_generator,
    register_lint,
    register_scaffold_hook,
    register_namespace,
    register_known_activities,
    register_key_activities,
    register_hallucination_pattern,
    register_common_packages,
    register_battle_test_grader,
    register_test_spec,
    register_lint_test_fixture,
    register_type_mapping,
)

REQUIRED_API_VERSION = 1

_PLUGIN_ROOT = Path(__file__).resolve().parent.parent

from .generators import (
    gen_create_form_task, gen_wait_for_form_task,
    gen_create_external_task, gen_wait_for_external_task,
    gen_get_form_tasks, gen_complete_task, gen_assign_tasks,
)
from .lint_rules import (
    lint_tasks, lint_formdata_key_mismatch,
    lint_persistence_in_subworkflow, lint_external_task,
)
from .scaffold_hooks import enable_persistence_support
from .battle_test_grading import grade_ac

# --- Generators ---
register_generator("create_form_task", gen_create_form_task, display_name="CreateFormTask")
register_generator("wait_for_form_task", gen_wait_for_form_task, display_name="WaitForFormTask")
register_generator("create_external_task", gen_create_external_task, display_name="CreateExternalTask")
register_generator("wait_for_external_task", gen_wait_for_external_task, display_name="WaitForExternalTask")
register_generator("get_form_tasks", gen_get_form_tasks, display_name="GetFormTasks")
register_generator("complete_task", gen_complete_task, display_name="CompleteTask")
register_generator("assign_tasks", gen_assign_tasks, display_name="AssignTasks")

# --- Lint rules ---
register_lint(lint_tasks, "lint_tasks")
register_lint(lint_formdata_key_mismatch, "lint_formdata_key_mismatch")
register_lint(lint_persistence_in_subworkflow, "lint_persistence_in_subworkflow")
register_lint(lint_external_task, "lint_external_task")

# --- Scaffold hooks ---
register_scaffold_hook(enable_persistence_support)

# --- Namespaces ---
register_namespace(
    "upaf",
    "clr-namespace:UiPath.Persistence.Activities.FormTask;assembly=UiPath.Persistence.Activities"
)
register_namespace(
    "upae",
    "clr-namespace:UiPath.Persistence.Activities.ExternalTask;assembly=UiPath.Persistence.Activities"
)
register_namespace(
    "upat",
    "clr-namespace:UiPath.Persistence.Activities.Tasks;assembly=UiPath.Persistence.Activities"
)

# --- Type mappings (short spec name → prefixed XAML type) ---
register_type_mapping("FormTaskData", "upaf:FormTaskData")
register_type_mapping("ExternalTaskData", "upae:ExternalTaskData")
register_type_mapping("List(FormTaskData)", "scg:List(upaf:FormTaskData)")
register_type_mapping("List(ExternalTaskData)", "scg:List(upae:ExternalTaskData)")

# --- Known activities (IdRef required) ---
register_known_activities(
    "CreateFormTask", "WaitForFormTaskAndResume",
    "CreateExternalTask", "WaitForExternalTaskAndResume",
    "GetFormTasks", "CompleteTask", "AssignTasks",
)

# --- Key activities (DisplayName required) ---
register_key_activities(
    "upaf:CreateFormTask", "upaf:WaitForFormTaskAndResume",
    "upae:CreateExternalTask", "upae:WaitForExternalTaskAndResume",
    "upaf:GetFormTasks", "upat:CompleteTask", "upat:AssignTasks",
)

# --- Hallucination patterns ---
# Note: Only register patterns that are NEVER valid in any activity.
# FormLayout= and FormData are valid on CreateFormTask, so they can't be
# registered here (the detector does file-wide substring matching).
register_hallucination_pattern("TaskObject=", "TaskOutput/TaskInput", "CreateFormTask/WaitForFormTask")
register_hallucination_pattern("TaskObject=", "TaskOutput/TaskInput", "CreateExternalTask/WaitForExternalTask")

# --- NuGet packages ---
register_common_packages("UiPath.Persistence.Activities", "UiPath.FormActivityLibrary")

# --- Battle test grader ---
register_battle_test_grader("ac", grade_ac)

# --- Test spec (generator integration test) ---
register_test_spec("tasks_form_task", {
    "class_name": "Test_Tasks",
    "arguments": [],
    "variables": [
        {"name": "fdtTaskData", "type": "FormTaskData"},
        {"name": "strTaskAction", "type": "String"},
    ],
    "activities": [
        {"gen": "log_message", "args": {"message_expr": "\"[START] Test_Tasks\"", "level": "Info"}},
        {"gen": "create_form_task", "args": {
            "task_title_expr": "\"Review Invoice\"",
            "task_output_variable": "fdtTaskData",
            "form_layout_json": "{\"components\":[{\"type\":\"textfield\",\"key\":\"invoiceId\",\"label\":\"Invoice ID\"}]}",
            "display_name": "Create Form Task",
        }},
        {"gen": "wait_for_form_task", "args": {
            "task_input_variable": "fdtTaskData",
            "task_action_variable": "strTaskAction",
            "display_name": "Wait for Form Task and Resume",
        }},
        {"gen": "log_message", "args": {"message_expr": "\"[END] Test_Tasks\"", "level": "Info"}},
    ]
})

# --- Test spec: External Task ---
register_test_spec("tasks_external_task", {
    "class_name": "Test_ExternalTask",
    "arguments": [],
    "variables": [
        {"name": "edtTaskData", "type": "ExternalTaskData"},
        {"name": "strTaskAction", "type": "String"},
        {"name": "edtUpdatedTask", "type": "ExternalTaskData"},
    ],
    "activities": [
        {"gen": "log_message", "args": {"message_expr": "\"[START] Test_ExternalTask\"", "level": "Info"}},
        {"gen": "create_external_task", "args": {
            "task_title_expr": "\"JIRA Integration Task\"",
            "task_output_variable": "edtTaskData",
            "task_priority": "High",
            "display_name": "Create External Task",
        }},
        {"gen": "wait_for_external_task", "args": {
            "task_input_variable": "edtTaskData",
            "task_action_variable": "strTaskAction",
            "task_output_variable": "edtUpdatedTask",
            "display_name": "Wait for External Task and Resume",
        }},
        {"gen": "log_message", "args": {"message_expr": "\"[END] Test_ExternalTask\"", "level": "Info"}},
    ]
})

# --- Test spec: Task Management ---
register_test_spec("tasks_task_management", {
    "class_name": "Test_TaskManagement",
    "arguments": [],
    "variables": [
        {"name": "lstFormTasks", "type": "List(FormTaskData)"},
    ],
    "activities": [
        {"gen": "log_message", "args": {"message_expr": "\"[START] Test_TaskManagement\"", "level": "Info"}},
        {"gen": "get_form_tasks", "args": {
            "output_variable": "lstFormTasks",
            "filter_expr": "Status eq 'Pending'",
            "display_name": "Get Pending Form Tasks",
        }},
        {"gen": "complete_task", "args": {
            "task_id_expr": "lstFormTasks(0).Id.Value",
            "action_expr": "Completed",
            "display_name": "Complete First Task",
        }},
        {"gen": "assign_tasks", "args": {
            "task_id_expr": "lstFormTasks(0).Id.Value",
            "user_name_or_email": "reviewer@company.com",
            "assignment_criteria": "SingleUser",
            "display_name": "Assign Task to Reviewer",
        }},
        {"gen": "log_message", "args": {"message_expr": "\"[END] Test_TaskManagement\"", "level": "Info"}},
    ]
})

# --- Lint test fixture ---
register_lint_test_fixture(
    "bad_persistence_subworkflow.xaml", "AC-26", "ERROR",
    _PLUGIN_ROOT / "assets" / "lint-test-cases",
)
register_lint_test_fixture(
    "bad_external_task_subworkflow.xaml", "AC-26", "ERROR",
    _PLUGIN_ROOT / "assets" / "lint-test-cases",
)
