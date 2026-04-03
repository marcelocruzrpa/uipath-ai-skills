"""UiPath Action Center skill extension — registers generators, lints, and hooks.

This module is auto-discovered by plugin_loader.load_plugins() and registers
Action Center–specific functionality with the core skill's plugin system.

Uses relative imports (.generators, .lint_rules, .scaffold_hooks) so that
each plugin's modules are isolated — no sys.path pollution, no cross-plugin
name collisions even when multiple uipath-* skills coexist.
"""

from plugin_loader import (
    register_generator,
    register_lint,
    register_scaffold_hook,
    register_namespace,
    register_known_activities,
    register_key_activities,
)

REQUIRED_API_VERSION = 1

from .generators import gen_create_form_task, gen_wait_for_form_task
from .lint_rules import lint_action_center, lint_formdata_key_mismatch, lint_persistence_in_subworkflow
from .scaffold_hooks import enable_persistence_support

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
