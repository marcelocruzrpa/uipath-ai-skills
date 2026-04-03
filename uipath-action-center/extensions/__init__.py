"""UiPath Action Center skill extension — registers generators, lints, and hooks.

This module is auto-discovered by plugin_loader.load_plugins() and registers
Action Center–specific functionality with the core skill's plugin system.

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
)

REQUIRED_API_VERSION = 1

_PLUGIN_ROOT = Path(__file__).resolve().parent.parent

from .generators import gen_create_form_task, gen_wait_for_form_task
from .lint_rules import lint_action_center, lint_formdata_key_mismatch, lint_persistence_in_subworkflow
from .scaffold_hooks import enable_persistence_support
from .battle_test_grading import grade_ac

# --- Generators ---
register_generator("create_form_task", gen_create_form_task, display_name="CreateFormTask")
register_generator("wait_for_form_task", gen_wait_for_form_task, display_name="WaitForFormTask")

# --- Lint rules ---
register_lint(lint_action_center, "lint_action_center")
register_lint(lint_formdata_key_mismatch, "lint_formdata_key_mismatch")
register_lint(lint_persistence_in_subworkflow, "lint_persistence_in_subworkflow")

# --- Scaffold hooks ---
register_scaffold_hook(enable_persistence_support)

# --- Namespace ---
register_namespace(
    "upaf",
    "clr-namespace:UiPath.Persistence.Activities.FormTask;assembly=UiPath.Persistence.Activities"
)

# --- Known activities (IdRef required) ---
register_known_activities("CreateFormTask", "WaitForFormTaskAndResume")

# --- Key activities (DisplayName required) ---
register_key_activities("upaf:CreateFormTask", "upaf:WaitForFormTaskAndResume")

# --- Hallucination patterns ---
register_hallucination_pattern("TaskObject=", "TaskOutput/TaskInput", "CreateFormTask/WaitForFormTask")

# --- NuGet packages ---
register_common_packages("UiPath.Persistence.Activities", "UiPath.FormActivityLibrary")

# --- Battle test grader ---
register_battle_test_grader("ac", grade_ac)

# --- Test spec (generator integration test) ---
register_test_spec("action_center_form_task", {
    "class_name": "Test_ActionCenter",
    "arguments": [],
    "variables": [
        {"name": "fdtTaskData", "type": "FormTaskData"},
        {"name": "strTaskAction", "type": "String"},
    ],
    "activities": [
        {"gen": "log_message", "args": {"message_expr": "\"[START] Test_ActionCenter\"", "level": "Info"}},
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
        {"gen": "log_message", "args": {"message_expr": "\"[END] Test_ActionCenter\"", "level": "Info"}},
    ]
})

# --- Lint test fixture ---
register_lint_test_fixture(
    "bad_persistence_subworkflow.xaml", "AC-26", "ERROR",
    str(_PLUGIN_ROOT / "assets" / "lint-test-cases"),
)
