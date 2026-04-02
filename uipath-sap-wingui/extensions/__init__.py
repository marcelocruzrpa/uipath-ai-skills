"""UiPath SAP WinGUI skill extension — registers generators, lints, and namespaces.

This module is auto-discovered by plugin_loader.load_plugins() and registers
SAP WinGUI–specific functionality with the core skill's plugin system.

Uses relative imports (.generators, .lint_rules) so that each plugin's
modules are isolated — no sys.path pollution, no cross-plugin name collisions
even when multiple uipath-* skills coexist.
"""

from plugin_loader import (
    register_generator,
    register_lint,
    register_namespace,
    register_known_activities,
    register_key_activities,
)

REQUIRED_API_VERSION = 1

from .generators import (
    gen_sap_logon,
    gen_sap_login,
    gen_sap_call_transaction,
    gen_sap_click_toolbar,
    gen_sap_select_menu_item,
    gen_sap_read_statusbar,
    gen_sap_table_cell_scope,
    # gen_sap_status_bar_check and gen_sap_type_into_cell are Python-only
    # convenience helpers (not registered as generators). status_bar_check
    # returns a tuple (xml, condition) which is incompatible with the JSON
    # spec dispatch in generate_workflow.py. Import them directly when needed:
    #   from extensions.generators import gen_sap_status_bar_check, gen_sap_type_into_cell
)
from .lint_rules import lint_sap_wingui

# --- Generators (7 core) ---
# All SAP generators require uix: namespace (UI automation activities)
register_generator("sap_logon", gen_sap_logon, display_name="NSAPLogon", requires_ui_namespace=True)
register_generator("sap_login", gen_sap_login, display_name="NSAPLogin", requires_ui_namespace=True)
register_generator("sap_call_transaction", gen_sap_call_transaction, display_name="NSAPCallTransaction", requires_ui_namespace=True)
register_generator("sap_click_toolbar", gen_sap_click_toolbar, display_name="NSAPClickToolbarButton", requires_ui_namespace=True)
register_generator("sap_select_menu_item", gen_sap_select_menu_item, display_name="NSAPSelectMenuItem", requires_ui_namespace=True)
register_generator("sap_read_statusbar", gen_sap_read_statusbar, display_name="NSAPReadStatusbar", requires_ui_namespace=True)
register_generator("sap_table_cell_scope", gen_sap_table_cell_scope, display_name="NSAPTableCellScope", requires_ui_namespace=True)
# gen_sap_status_bar_check returns (xml, condition_expr) tuple — not compatible
# with JSON spec dispatch. gen_sap_type_into_cell is a Python composition helper.
# Both are importable from .generators but NOT registered as spec generators.

# --- Lint rules ---
register_lint(lint_sap_wingui, "lint_sap_wingui")

# --- Namespaces ---
# uix is already in core's PREFIX_TO_XMLNS — only register ucas (SAP-specific).
# NOTE: ucas is a legacy namespace from older Studio exports (e.g., ucas:ReadStatusbar
# in golden samples). Current generators use uix:NSAP* prefix instead. Kept for
# validation of existing/legacy workflows that may still reference ucas:.
register_namespace(
    "ucas",
    "clr-namespace:UiPath.Core.Activities.SAP;assembly=UiPath.UiAutomation.Activities"
)

# --- Known activities (IdRef required) ---
register_known_activities(
    "NSAPLogon",
    "NSAPLogin",
    "NSAPCallTransaction",
    "NSAPClickToolbarButton",
    "NSAPSelectMenuItem",
    "NSAPReadStatusbar",
    "NSAPTableCellScope",
)

# --- Key activities (DisplayName required) ---
register_key_activities(
    "uix:NSAPLogon",
    "uix:NSAPLogin",
    "uix:NSAPCallTransaction",
    "uix:NSAPClickToolbarButton",
    "uix:NSAPSelectMenuItem",
    "uix:NSAPReadStatusbar",
    "uix:NSAPTableCellScope",
)
