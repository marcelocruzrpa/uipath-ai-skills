"""Generate complete UiPath workflow .xaml files from JSON specifications.

This is the PRIMARY way to create workflow files. It calls generate_activities
generators internally, wraps them in proper XML boilerplate, and outputs a
validated .xaml file.

Usage:
    python generate_workflow.py spec.json output.xaml

The JSON spec format:

{
  "class_name": "ACME_Launch",
  "arguments": [
    {"name": "in_strUrl", "direction": "In", "type": "String"},
    {"name": "out_uiApp", "direction": "Out", "type": "UiElement"}
  ],
  "variables": [
    {"name": "strUsername", "type": "String"},
    {"name": "secstrPassword", "type": "SecureString"}
  ],
  "namespaces": [],
  "activities": [
    {
      "gen": "log_message",
      "args": {"message_expr": "\"[START] ACME_Launch\"", "level": "Info"}
    },
    {
      "gen": "napplicationcard_open",
      "args": {
        "display_name": "ACME System 1",
        "url_variable": "in_strUrl",
        "out_ui_element": "out_uiApp",
        "target_app_selector": "<html app='msedge.exe' title='ACME' />"
      },
      "children": [
        {"gen": "getrobotcredential", "args": {"asset_name_variable": "in_strCredentialAssetName", "username_variable": "strUsername", "password_variable": "secstrPassword"}},
        {"gen": "ntypeinto", "args": {"display_name": "Type Into 'Email'", "selector": "<webctrl id='email' tag='INPUT' />", "text_variable": "strUsername"}},
        {"gen": "ntypeinto", "args": {"display_name": "Type Into 'Password'", "selector": "<webctrl id='password' tag='INPUT' />", "text_variable": "secstrPassword", "is_secure": true}},
        {"gen": "nclick", "args": {"display_name": "Click 'Login'", "selector": "<webctrl tag='BUTTON' aaname='Login' />"}}
      ]
    },
    {
      "gen": "log_message",
      "args": {"message_expr": "\"[END] ACME_Launch\"", "level": "Info"}
    }
  ]
}

Supported generators (gen field) — 93 core (plus plugin extensions):
  UI: ntypeinto, nclick, ncheck, nhover, ndoubleclick, nrightclick, ngettext,
      ncheckstate, nselectitem, nkeyboardshortcuts, nmousescroll,
      ngotourl, ngeturl, nextractdata, pick_login_validation,
      napplicationcard_open, napplicationcard_attach, napplicationcard_close,
      napplicationcard_desktop_open
  Control flow: if, if_else_if, switch, foreach, foreach_row, foreach_file,
      while, do_while, flowchart, state_machine, parallel, parallel_foreach
  Error/invoke: try_catch, throw, rethrow, retryscope, invoke_workflow,
      invoke_code, invoke_method
  Data: assign, multiple_assign, build_data_table, add_data_row,
      add_data_column, filter_data_table, sort_data_table,
      remove_duplicate_rows, output_data_table, join_data_tables,
      lookup_data_table, merge_data_table, generate_data_table,
      deserialize_json
  Orchestrator: add_queue_item, get_queue_item, getrobotcredential,
      get_robot_asset, net_http_request
  File: copy_file, move_file, delete_file, path_exists, create_directory,
      read_text_file, write_text_file, read_csv, write_csv
  Excel/PDF/Email: read_range, write_range, write_cell,
      read_pdf_text, read_pdf_with_ocr, send_mail, get_imap_mail,
      save_mail_attachments
  Database: database_connect, execute_query, execute_non_query
  Tasks: create_form_task, wait_for_form_task (via plugin)
  Dialogs: input_dialog, message_box
  Workflow: log_message, comment, comment_out
  Misc: break, continue, kill_process, terminate_workflow,
      should_stop, add_log_fields, remove_log_fields,
      take_screenshot_and_save
  Containers (with children): napplicationcard_open, napplicationcard_attach,
      napplicationcard_close, napplicationcard_desktop_open, retryscope,
      comment_out, while, do_while, foreach, foreach_row, foreach_file,
      parallel, parallel_foreach
  Containers (with named children): try_catch (try_children, finally_children,
      args.catches[].children), if (then_children, else_children),
      if_else_if (args.conditions[].children, else_children),
      switch (args.cases[].children, default_children),
      ncheckstate (if_exists_children, if_not_exists_children)
"""

import functools
import inspect
import json
import os
import re
import sys
import uuid
from pathlib import Path

# Resolve skill directory
_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))

from generate_activities import UI_GENERATORS as _CORE_UI_GENERATORS
from generate_activities import (
    # UI activities
    gen_ntypeinto, gen_nclick, gen_ncheck, gen_nhover, gen_ndoubleclick, gen_nrightclick,
    gen_ngettext, gen_ncheckstate, gen_nselectitem, gen_nkeyboardshortcuts,
    gen_nmousescroll, gen_ngotourl, gen_nextractdata, gen_ngeturl,
    gen_napplicationcard_open, gen_napplicationcard_attach,
    gen_napplicationcard_close, gen_napplicationcard_desktop_open,
    gen_pick_login_validation,
    # Workflow activities
    gen_logmessage, gen_getrobotcredential, gen_invoke_workflow,
    gen_throw, gen_rethrow, gen_multiple_assign, gen_assign,
    gen_add_queue_item, gen_get_queue_item, gen_retryscope,
    gen_bulk_add_queue_items,
    gen_comment, gen_comment_out,
    # Control flow
    gen_try_catch, gen_if, gen_if_else_if, gen_switch,
    gen_foreach_row, gen_foreach, gen_foreach_file,
    gen_while, gen_do_while,
    gen_flowchart, gen_state_machine, gen_parallel, gen_parallel_foreach,
    # Data operations
    gen_build_data_table, gen_add_data_row, gen_add_data_column,
    gen_remove_data_column,
    gen_filter_data_table, gen_sort_data_table, gen_remove_duplicate_rows,
    gen_output_data_table, gen_join_data_tables, gen_lookup_data_table,
    gen_merge_data_table, gen_generate_data_table,
    # File operations
    gen_copy_file, gen_move_file, gen_delete_file, gen_path_exists,
    gen_create_directory, gen_read_text_file, gen_write_text_file,
    gen_read_csv, gen_write_csv,
    # Excel/PDF/Email
    gen_read_range, gen_write_range, gen_write_cell, gen_append_range,
    gen_read_pdf_text, gen_read_pdf_with_ocr,
    gen_send_mail, gen_get_imap_mail, gen_save_mail_attachments,
    # Database
    gen_database_connect, gen_execute_query, gen_execute_non_query,
    # HTTP/JSON
    gen_net_http_request, gen_deserialize_json,
    # Tasks — loaded via plugin (see plugin_loader)
    # Dialogs
    gen_input_dialog, gen_message_box,
    # Misc
    gen_break, gen_continue, gen_kill_process,
    gen_terminate_workflow, gen_should_stop, gen_get_robot_asset,
    gen_add_log_fields, gen_remove_log_fields,
    gen_invoke_code, gen_invoke_method,
    gen_take_screenshot_and_save,
)
from utils import generate_uuid as _uuid, escape_xml_attr as _escape_xml_attr, TYPE_MAP_BASE, KNOWN_XMLNS_PREFIXES, normalize_selector_quotes as _normalize_selector
from _wf_types import DIRECTION_MAP, _type_map, _normalize_argument_type, _check_type_field
from _wf_boilerplate import _build_namespaces, _build_arguments_xml, _build_variables_xml
from _wf_validation import _validate_activities as _validate_activities_impl, _validate_spec as _validate_spec_impl

# Plugin system — load skill extensions (Tasks, etc.)
from plugin_loader import load_plugins, get_generators, get_display_name_map, get_extra_namespaces, get_ui_generators, get_type_mappings
load_plugins()

# Build full xmlns prefix list (core + plugin-registered prefixes)
_ALL_XMLNS_PREFIXES = KNOWN_XMLNS_PREFIXES + tuple(f"{p}:" for p in get_extra_namespaces())

# Merge plugin type mappings into type map (e.g. "FormTaskData" -> "upaf:FormTaskData")
_EXTENDED_TYPE_MAP = dict(TYPE_MAP_BASE)
_EXTENDED_TYPE_MAP.update(get_type_mappings())

# ---------------------------------------------------------------------------
# Child keys that contain nested activity lists (single source of truth)
# ---------------------------------------------------------------------------

_ALL_CHILD_KEYS = ("children", "try_children", "then_children", "else_children",
                   "finally_children", "default_children",
                   "if_exists_children", "if_not_exists_children")

# ---------------------------------------------------------------------------
# Object Repository auto-wiring (module-level state, set before generation)
# ---------------------------------------------------------------------------

_OBJ_REPO_LOOKUP = None  # Set by _build_obj_repo_lookup() when --project-dir is provided
_PROJECT_ROOT = None     # Set in main() when --project-dir is provided; forwarded to plugin generators
_VAR_TYPE_LOOKUP = {}    # {var_name: xaml_type} — set by generate_workflow() for type inference

# Generators that have a 'selector' arg and accept obj_repo
_SELECTOR_BASED_GENS = {
    "ntypeinto", "nclick", "ncheck", "nselectitem", "nhover",
    "ndoubleclick", "nrightclick", "nkeyboardshortcuts", "nmousescroll",
    "ncheckstate", "ngettext",
}


def _build_obj_repo_lookup(project_dir: str) -> dict | None:
    """Load selectors.json + refs.json from project_dir and build auto-wire lookup.

    Returns dict with:
        selector_to_element: {normalized_selector: "AppName/ScreenName/ElementName"}
        refs: parsed refs.json dict
        app_selectors: {normalized_app_selector: obj_repo_app_dict}
    Or None if files not found.
    """
    from pathlib import Path as _Path
    proj = _Path(project_dir)
    sel_path = proj / "selectors.json"
    refs_path = proj / ".objects" / "refs.json"

    if not sel_path.exists():
        print(f"  [WARN] No selectors.json in {project_dir} — skipping auto-wire", file=sys.stderr)
        return None
    if not refs_path.exists():
        print(f"  [WARN] No .objects/refs.json in {project_dir} — skipping auto-wire", file=sys.stderr)
        return None

    with open(sel_path, "r", encoding="utf-8") as f:
        selectors_data = json.load(f)
    with open(refs_path, "r", encoding="utf-8") as f:
        refs_data = json.load(f)

    selector_to_element = {}
    _collisions = set()  # selectors that map to multiple elements
    app_selectors = {}

    for app in selectors_data.get("apps", []):
        app_name = app["name"]
        # App-level selector → obj_repo_app
        app_sel = app.get("selector", "")
        if app_sel:
            normalized = _normalize_selector(app_sel)
            app_ref = refs_data.get("apps", {}).get(app_name)
            if app_ref:
                app_selectors[normalized] = app_ref

        # Element-level selectors
        for screen in app.get("screens", []):
            screen_name = screen["name"]
            for elem in screen.get("elements", []):
                elem_name = elem["name"]
                elem_sel = elem.get("selector", "")
                if elem_sel:
                    normalized = _normalize_selector(elem_sel)
                    key = f"{app_name}/{screen_name}/{elem_name}"
                    if normalized in selector_to_element and selector_to_element[normalized] != key:
                        _collisions.add(normalized)
                    selector_to_element[normalized] = key

    # Remove colliding selectors — ambiguous matches can't be auto-wired
    for sel in _collisions:
        del selector_to_element[sel]
        print(f"  [WARN] Selector collision — skipping auto-wire for duplicate selector across screens", file=sys.stderr)

    n_wirable = len(selector_to_element)
    n_skipped = len(_collisions)
    print(f"  [OBJ-REPO] Loaded {n_wirable} unique selectors ({n_skipped} skipped due to cross-screen duplicates)", file=sys.stderr)

    return {
        "selector_to_element": selector_to_element,
        "refs": refs_data,
        "app_selectors": app_selectors,
    }


# (Type mappings, XML boilerplate, and argument normalization extracted to
#  _wf_types.py and _wf_boilerplate.py)


# ---------------------------------------------------------------------------
# IdRef counter
# ---------------------------------------------------------------------------

class _IdRefCounter:
    """Track IdRef assignments to guarantee uniqueness."""
    def __init__(self):
        self._counts = {}

    def next(self, prefix: str) -> str:
        self._counts[prefix] = self._counts.get(prefix, 0) + 1
        return f"{prefix}_{self._counts[prefix]}"


# ---------------------------------------------------------------------------
# Unified generator registry — single source of truth
# ---------------------------------------------------------------------------

import dataclasses

@dataclasses.dataclass(frozen=True, slots=True)
class _GenEntry:
    """Unified metadata for a generator. Replaces 4 separate dicts."""
    fn: object              # gen_* function or _handle_* container handler
    idref: str              # IdRef prefix (e.g. "NTypeInto")
    required: tuple = ()    # required arg names for spec validation
    container: bool = False # True = fn is a container handler (not auto-dispatched)


@functools.lru_cache(maxsize=None)
def _cached_signature(fn):
    """Cache inspect.signature() results to avoid repeated introspection."""
    return inspect.signature(fn)


def _auto_dispatch(fn, args: dict, **extra) -> str:
    """Dispatch to generator function using signature introspection.

    Maps args dict keys to function parameters by name.
    Extra kwargs (id_ref, scope_id, indent) are injected if the function accepts them.
    Parameters with defaults in the function signature use args.get() semantics automatically.
    """
    sig = _cached_signature(fn)
    kwargs = {}
    for name, param in sig.parameters.items():
        if name in extra:
            kwargs[name] = extra[name]
        elif name in args:
            kwargs[name] = args[name]
        elif param.default is not inspect.Parameter.empty:
            pass  # function's own default is used
        # else: missing required arg — let Python raise TypeError
    return fn(**kwargs)


# ---------------------------------------------------------------------------
# Container handlers — factory + manual handlers for complex cases.
# ---------------------------------------------------------------------------


def _make_simple_container_handler(gen_fn, idref_prefix, *, new_scope=False):
    """Create a container handler that recursively generates children and
    dispatches to gen_fn via _auto_dispatch.

    Args:
        gen_fn: Generator function (e.g. gen_foreach_row).
        idref_prefix: IdRef counter prefix (e.g. "ForEachRow").
        new_scope: If True, generate a new scope_guid for children
                   (NApplicationCard pattern). If False, reuse parent scope_id.
    """
    def handler(spec, args, scope_id, counter, indent):
        if new_scope:
            child_scope = args.get("scope_guid", str(uuid.uuid4()))
            # Ensure scope_guid is in args for _auto_dispatch to pick up
            args = dict(args, scope_guid=child_scope)
        else:
            child_scope = scope_id

        child_body = "\n".join(
            _generate_activity(c, child_scope, counter, indent=indent + "    ")
            for c in spec.get("children", [])
        )
        return _auto_dispatch(gen_fn, args,
                              id_ref=counter.next(idref_prefix),
                              body_content=child_body,
                              body_sequence_idref=counter.next("Sequence"),
                              indent=indent)
    return handler


def _handle_try_catch(spec, args, scope_id, counter, indent):
    try_body = "\n".join(
        _generate_activity(c, scope_id, counter, indent=indent + "    ")
        for c in spec.get("try_children", [])
    )
    # Top-level catch_children (shared across catches when individual catch
    # entries don't define their own children)
    top_catch_children = spec.get("catch_children", [])
    # Map FQN exception types to xmlns prefix form for XAML TypeArguments
    _exc_type_map = {
        "System.Exception": "s:Exception",
        "System.NullReferenceException": "s:NullReferenceException",
        "System.ArgumentException": "s:ArgumentException",
        "System.InvalidOperationException": "s:InvalidOperationException",
        "System.TimeoutException": "s:TimeoutException",
        "System.IO.IOException": "s:IO.IOException",
        "UiPath.Core.BusinessRuleException": "ui:BusinessRuleException",
        "UiPath.Core.Activities.BusinessRuleException": "ui:BusinessRuleException",
    }
    # Build catch tuples: (exception_type, var_name, catch_body, catch_seq_idref)
    raw_catches = args.get("catches", [])
    catches = []
    for i_catch, catch_spec in enumerate(raw_catches):
        # Per-catch children take priority; fall back to top-level catch_children
        per_catch = catch_spec.get("children", [])
        effective_children = per_catch if per_catch else top_catch_children
        catch_body = "\n".join(
            _generate_activity(c, scope_id, counter, indent=indent + "    ")
            for c in effective_children
        )
        raw_exc = catch_spec.get("exception_type", "System.Exception")
        exc_type = _exc_type_map.get(raw_exc, raw_exc)
        catches.append((
            exc_type,
            catch_spec.get("name", "exception"),
            catch_body,
            counter.next("Sequence"),
        ))
    finally_body = "\n".join(
        _generate_activity(c, scope_id, counter, indent=indent + "    ")
        for c in spec.get("finally_children", [])
    )
    return gen_try_catch(
        try_content=try_body,
        try_sequence_idref=counter.next("Sequence"),
        id_ref=counter.next("TryCatch"),
        catches=catches if catches else None,
        finally_content=finally_body,
        finally_sequence_idref=counter.next("Sequence") if finally_body else "",
        display_name=args.get("display_name", "Try Catch"),
        indent=indent,
    )


def _handle_if(spec, args, scope_id, counter, indent):
    then_body = "\n".join(
        _generate_activity(c, scope_id, counter, indent=indent + "    ")
        for c in spec.get("then_children", [])
    )
    else_body = "\n".join(
        _generate_activity(c, scope_id, counter, indent=indent + "    ")
        for c in spec.get("else_children", [])
    )
    return gen_if(
        condition_expression=args["condition_expression"],
        id_ref=counter.next("If"),
        then_content=then_body,
        else_content=else_body,
        display_name=args.get("display_name", "If"),
        indent=indent,
    )


def _handle_if_else_if(spec, args, scope_id, counter, indent):
    conditions = []
    for cond_spec in args["conditions"]:
        cond_body = "\n".join(
            _generate_activity(c, scope_id, counter, indent=indent + "    ")
            for c in cond_spec.get("children", [])
        )
        conditions.append((cond_spec["expression"], cond_body, counter.next("Sequence")))
    else_body = "\n".join(
        _generate_activity(c, scope_id, counter, indent=indent + "    ")
        for c in spec.get("else_children", [])
    )
    return gen_if_else_if(
        conditions=conditions,
        id_ref=counter.next("IfElseIf"),
        else_content=else_body,
        display_name=args.get("display_name", "Else If"),
        indent=indent,
    )


def _handle_switch(spec, args, scope_id, counter, indent):
    cases = {}
    for case_spec in args["cases"]:
        case_body = "\n".join(
            _generate_activity(c, scope_id, counter, indent=indent + "    ")
            for c in case_spec.get("children", [])
        )
        cases[case_spec["value"]] = (case_body, counter.next("Sequence"))
    default_body = "\n".join(
        _generate_activity(c, scope_id, counter, indent=indent + "    ")
        for c in spec.get("default_children", [])
    )
    return gen_switch(
        expression_variable=args["expression_variable"],
        id_ref=counter.next("Switch"),
        cases=cases,
        default_content=default_body,
        default_sequence_idref=counter.next("Sequence") if default_body else "",
        switch_type=args.get("switch_type", "x:String"),
        display_name=args.get("display_name", "Switch"),
        indent=indent,
    )


def _handle_ncheckstate(spec, args, scope_id, counter, indent):
    id_ref = counter.next(_idref_prefix("ncheckstate"))
    ie_body = "\n".join(
        _generate_activity(c, scope_id, counter, indent=indent + "    ")
        for c in spec.get("if_exists_children", [])
    )
    ine_body = "\n".join(
        _generate_activity(c, scope_id, counter, indent=indent + "    ")
        for c in spec.get("if_not_exists_children", [])
    )
    return gen_ncheckstate(
        display_name=args["display_name"],
        selector=args["selector"],
        id_ref=id_ref,
        scope_id=scope_id,
        if_exists_idref=counter.next("Sequence"),
        if_not_exists_idref=counter.next("Sequence"),
        if_exists_body=ie_body,
        if_not_exists_body=ine_body,
        out_ui_element=args.get("out_ui_element", ""),
        obj_repo=args.get("obj_repo"),
        indent=indent,
    )


# --- Simple container handlers (factory-generated) ---
_handle_napplicationcard_open = _make_simple_container_handler(gen_napplicationcard_open, "NApplicationCard", new_scope=True)
_handle_napplicationcard_attach = _make_simple_container_handler(gen_napplicationcard_attach, "NApplicationCard", new_scope=True)
_handle_napplicationcard_close = _make_simple_container_handler(gen_napplicationcard_close, "NApplicationCard", new_scope=True)
_handle_napplicationcard_desktop_open = _make_simple_container_handler(gen_napplicationcard_desktop_open, "NApplicationCard", new_scope=True)
_handle_retryscope = _make_simple_container_handler(gen_retryscope, "RetryScope")
_handle_foreach_row = _make_simple_container_handler(gen_foreach_row, "ForEachRow")
_handle_foreach = _make_simple_container_handler(gen_foreach, "ForEach")
_handle_foreach_file = _make_simple_container_handler(gen_foreach_file, "ForEachFile")
_handle_while = _make_simple_container_handler(gen_while, "While")
_handle_do_while = _make_simple_container_handler(gen_do_while, "DoWhile")
_handle_comment_out = _make_simple_container_handler(gen_comment_out, "CommentOut")


def _handle_pick_login_validation(spec, args, scope_id, counter, indent):
    id_ref = counter.next(_idref_prefix("pick_login_validation"))
    return gen_pick_login_validation(
        success_selector=args["success_selector"],
        error_selector=args["error_selector"],
        error_ui_variable=args.get("error_ui_variable", "uiErrorElement"),
        error_text_variable=args.get("error_text_variable", "strErrorText"),
        scope_id=scope_id,
        pick_idref=counter.next("Pick"),
        success_branch_idref=counter.next("PickBranch"),
        failure_branch_idref=counter.next("PickBranch"),
        success_checkstate_idref=counter.next("NCheckAppState"),
        failure_checkstate_idref=counter.next("NCheckAppState"),
        success_if_exists_idref=counter.next("Sequence"),
        success_if_not_exists_idref=counter.next("Sequence"),
        failure_if_exists_idref=counter.next("Sequence"),
        failure_if_not_exists_idref=counter.next("Sequence"),
        success_action_idref=counter.next("Sequence"),
        failure_action_idref=counter.next("Sequence"),
        gettext_idref=counter.next("NGetText"),
        throw_idref=counter.next("Throw"),
        success_log_idref=counter.next("LogMessage"),
        indent=indent,
    )


# ---------------------------------------------------------------------------
# Unified generator registry — replaces _SIMPLE_REGISTRY, _CONTAINER_HANDLERS,
# _IDREF_OVERRIDES, and REQUIRED_ARGS with a single dict.
# ---------------------------------------------------------------------------

# Acronym fixes applied after PascalCase conversion (case-sensitive keys)
_ACRONYM_FIXES = {
    "Csv": "CSV", "Pdf": "PDF", "Ocr": "OCR",
    "Imap": "IMAP", "Json": "JSON", "Http": "HTTP",
}


def _derive_idref_prefix(gen: str) -> str:
    """Derive IdRef prefix from gen name using PascalCase convention + acronym fixes."""
    pascal = "".join(w.capitalize() for w in gen.split("_"))
    for short, full in _ACRONYM_FIXES.items():
        pascal = pascal.replace(short, full)
    return pascal


def _e(fn, idref, required=(), *, container=False):
    """Shorthand for _GenEntry construction with auto-derived idref fallback."""
    return _GenEntry(fn=fn, idref=idref, required=tuple(required), container=container)


_REGISTRY: dict[str, _GenEntry] = {
    # --- Container generators (custom handlers with child recursion) ---
    "napplicationcard_open":         _e(_handle_napplicationcard_open, "NApplicationCard", ("display_name", "url_variable", "out_ui_element"), container=True),
    "napplicationcard_attach":       _e(_handle_napplicationcard_attach, "NApplicationCard", ("display_name", "ui_element_variable"), container=True),
    "napplicationcard_close":        _e(_handle_napplicationcard_close, "NApplicationCard", ("ui_element_variable",), container=True),
    "napplicationcard_desktop_open": _e(_handle_napplicationcard_desktop_open, "NApplicationCard", ("display_name", "file_path_variable", "out_ui_element"), container=True),
    "retryscope":                    _e(_handle_retryscope, "RetryScope", container=True),
    "retry_scope":                   _e(_handle_retryscope, "RetryScope", container=True),  # alias
    "try_catch":                     _e(_handle_try_catch, "TryCatch", container=True),
    "if":                            _e(_handle_if, "If", ("condition_expression",), container=True),
    "if_else_if":                    _e(_handle_if_else_if, "IfElseIf", ("conditions",), container=True),
    "switch":                        _e(_handle_switch, "Switch", ("expression_variable", "cases"), container=True),
    "ncheckstate":                   _e(_handle_ncheckstate, "NCheckState", ("display_name", "selector"), container=True),
    "foreach_row":                   _e(_handle_foreach_row, "ForEachRow", ("datatable_variable",), container=True),
    "foreach":                       _e(_handle_foreach, "ForEach", ("collection_variable",), container=True),
    "foreach_file":                  _e(_handle_foreach_file, "ForEachFile", ("folder_variable",), container=True),
    "while":                         _e(_handle_while, "While", ("condition_expression",), container=True),
    "do_while":                      _e(_handle_do_while, "DoWhile", ("condition_expression",), container=True),
    "comment_out":                   _e(_handle_comment_out, "CommentOut", container=True),
    "pick_login_validation":         _e(_handle_pick_login_validation, "Pick", ("success_selector", "error_selector"), container=True),

    # --- UI activities (simple, auto-dispatched) ---
    "ntypeinto":           _e(gen_ntypeinto, "NTypeInto", ("display_name", "selector", "text_variable")),
    "nclick":              _e(gen_nclick, "NClick", ("display_name", "selector")),
    "ncheck":              _e(gen_ncheck, "NCheck", ("display_name", "selector")),
    "ngettext":            _e(gen_ngettext, "NGetText", ("display_name", "output_variable")),
    "nselectitem":         _e(gen_nselectitem, "NSelectItem", ("display_name", "selector", "item_variable")),
    "ngotourl":            _e(gen_ngotourl, "NGoToUrl", ("url_variable",)),
    "nhover":              _e(gen_nhover, "NHover", ("display_name", "selector")),
    "ndoubleclick":        _e(gen_ndoubleclick, "NClick", ("display_name", "selector")),
    "nrightclick":         _e(gen_nrightclick, "NClick", ("display_name", "selector")),
    "nkeyboardshortcuts":  _e(gen_nkeyboardshortcuts, "NKeyboardShortcuts", ("display_name", "shortcuts")),
    "nmousescroll":        _e(gen_nmousescroll, "NMouseScroll", ("display_name", "selector")),
    "nextractdata":        _e(gen_nextractdata, "NExtractDataGeneric", ("display_name", "output_variable")),
    "ngeturl":             _e(gen_ngeturl, "NGetUrl", ("output_variable",)),

    # --- Orchestrator / credentials ---
    "getrobotcredential":  _e(gen_getrobotcredential, "GetRobotCredential", ("asset_name_variable", "username_variable", "password_variable")),
    "get_robot_credential": _e(gen_getrobotcredential, "GetRobotCredential", ("asset_name_variable", "username_variable", "password_variable")),  # alias
    "invoke_workflow":     _e(gen_invoke_workflow, "InvokeWorkflowFile", ("workflow_path",)),
    "throw":               _e(gen_throw, "Throw", ("exception_expression",)),
    "rethrow":             _e(gen_rethrow, "Rethrow"),
    "multiple_assign":     _e(gen_multiple_assign, "MultipleAssign", ("assignments",)),
    "assign":              _e(gen_assign, "Assign", ("to_variable", "value_expression")),
    "add_queue_item":      _e(gen_add_queue_item, "AddQueueItem", ("queue_name_config",)),
    "get_queue_item":      _e(gen_get_queue_item, "GetQueueItem", ("queue_name_config", "transaction_item_variable")),
    "bulk_add_queue_items": _e(gen_bulk_add_queue_items, "BulkAddQueueItems", ("queue_name", "datatable_variable")),
    "comment":             _e(gen_comment, "Comment", ("text",)),

    # --- P1 complex generators (pass-through with raw content) ---
    "flowchart":           _e(gen_flowchart, "Flowchart", ("steps", "start_ref_id")),
    "state_machine":       _e(gen_state_machine, "StateMachine", ("states", "initial_state_ref")),
    "parallel":            _e(gen_parallel, "Parallel", ("branches_xml",)),
    "parallel_foreach":    _e(gen_parallel_foreach, "ParallelForEach", ("type_argument", "values_expression", "body_xml")),

    # --- Data operations ---
    "build_data_table":    _e(gen_build_data_table, "BuildDataTable", ("datatable_variable", "columns")),
    "add_data_row":        _e(gen_add_data_row, "AddDataRow", ("datatable_variable", "array_values")),
    "add_data_column":     _e(gen_add_data_column, "AddDataColumn", ("datatable_variable", "column_name")),
    "remove_data_column":  _e(gen_remove_data_column, "RemoveDataColumn", ("datatable_variable", "column_name")),
    "filter_data_table":   _e(gen_filter_data_table, "FilterDataTable", ("datatable_variable", "filters")),
    "sort_data_table":     _e(gen_sort_data_table, "SortDataTable", ("datatable_variable", "column_name")),
    "remove_duplicate_rows": _e(gen_remove_duplicate_rows, "RemoveDuplicateRows", ("datatable_variable",)),
    "output_data_table":   _e(gen_output_data_table, "OutputDataTable", ("datatable_variable", "output_variable")),
    "join_data_tables":    _e(gen_join_data_tables, "JoinDataTables", ("datatable1_variable", "datatable2_variable", "output_variable", "join_rules")),
    "lookup_data_table":   _e(gen_lookup_data_table, "LookupDataTable", ("datatable_variable", "lookup_value_variable", "lookup_column_name", "target_column_name", "cell_value_variable", "row_index_variable")),
    "merge_data_table":    _e(gen_merge_data_table, "MergeDataTable", ("source_variable", "destination_variable")),
    "generate_data_table": _e(gen_generate_data_table, "GenerateDataTable", ("input_variable", "output_variable")),
    "deserialize_json":    _e(gen_deserialize_json, "DeserializeJSON", ("json_string_variable", "output_variable")),

    # --- File operations ---
    "copy_file":           _e(gen_copy_file, "CopyFile", ("source_path", "destination_path")),
    "move_file":           _e(gen_move_file, "MoveFile", ("source_variable", "destination_variable")),
    "delete_file":         _e(gen_delete_file, "DeleteFile", ("path_variable",)),
    "path_exists":         _e(gen_path_exists, "PathExists", ("path_variable", "result_variable")),
    "create_directory":    _e(gen_create_directory, "CreateDirectory", ("path_variable",)),
    "read_text_file":      _e(gen_read_text_file, "ReadTextFile", ("output_variable",)),
    "write_text_file":     _e(gen_write_text_file, "WriteTextFile", ("text_variable",)),
    "read_csv":            _e(gen_read_csv, "ReadCSV", ("output_datatable",)),
    "write_csv":           _e(gen_write_csv, "WriteCSV", ("input_datatable",)),

    # --- Excel/PDF/Email ---
    "read_range":          _e(gen_read_range, "ReadRange", ("workbook_path_variable", "sheet_name", "output_variable")),
    "write_range":         _e(gen_write_range, "WriteRange", ("workbook_path_variable", "sheet_name", "datatable_variable")),
    "write_cell":          _e(gen_write_cell, "WriteCell", ("workbook_path_variable", "sheet_name", "cell_expression", "text_variable")),
    "append_range":        _e(gen_append_range, "AppendRange", ("workbook_path_variable", "sheet_name", "datatable_variable")),
    "read_pdf_text":       _e(gen_read_pdf_text, "ReadPDFText", ("filename_variable", "output_variable")),
    "read_pdf_with_ocr":   _e(gen_read_pdf_with_ocr, "ReadPDFWithOCR", ("filename_variable", "output_variable")),
    "send_mail":           _e(gen_send_mail, "SendMail", ("to_variable", "subject_variable", "body_variable")),
    "get_imap_mail":       _e(gen_get_imap_mail, "GetIMAPMail", ("messages_variable",)),
    "save_mail_attachments": _e(gen_save_mail_attachments, "SaveMailAttachments", ("message_variable", "folder_path_variable")),

    # --- Database ---
    "database_connect":    _e(gen_database_connect, "DatabaseConnect", ("connection_variable", "output_variable")),
    "execute_query":       _e(gen_execute_query, "ExecuteQuery", ("sql", "output_variable")),
    "execute_non_query":   _e(gen_execute_non_query, "ExecuteNonQuery", ("sql",)),

    # --- HTTP ---
    "net_http_request":    _e(gen_net_http_request, "HTTPRequest", ("method", "request_url_variable", "result_variable")),

    # --- Dialogs ---
    "input_dialog":        _e(gen_input_dialog, "InputDialog", ("label", "title", "result_variable")),
    "message_box":         _e(gen_message_box, "MessageBox", ("text_variable",)),

    # --- Misc ---
    "break":               _e(gen_break, "Break"),
    "continue":            _e(gen_continue, "Continue"),
    "kill_process":        _e(gen_kill_process, "KillProcess", ("process_name",)),
    "terminate_workflow":  _e(gen_terminate_workflow, "TerminateWorkflow", ("reason_expression",)),
    "should_stop":         _e(gen_should_stop, "ShouldStop", ("result_variable",)),
    "get_robot_asset":     _e(gen_get_robot_asset, "GetRobotAsset", ("asset_name", "output_variable")),
    "add_log_fields":      _e(gen_add_log_fields, "AddLogFields", ("fields",)),
    "remove_log_fields":   _e(gen_remove_log_fields, "RemoveLogFields", ("field_names",)),
    "invoke_code":         _e(gen_invoke_code, "InvokeCode", ("code",)),
    "invoke_method":       _e(gen_invoke_method, "InvokeMethod"),
    "take_screenshot_and_save": _e(gen_take_screenshot_and_save, "TakeScreenshot", ("screenshot_variable", "save_path_variable")),
}

# Merge plugin display name mappings into IdRef lookup
_PLUGIN_IDREF_MAP = get_display_name_map()


def _idref_prefix(gen: str) -> str:
    """Map generator name to IdRef prefix."""
    entry = _REGISTRY.get(gen)
    if entry:
        return entry.idref
    if gen in _PLUGIN_IDREF_MAP:
        return _PLUGIN_IDREF_MAP[gen]
    return _derive_idref_prefix(gen)


# ---------------------------------------------------------------------------
# Main dispatch function
# ---------------------------------------------------------------------------

def _generate_activity(spec: dict, scope_id: str, counter: _IdRefCounter,
                       indent: str = "            ") -> str:
    """Generate XAML for a single activity from its JSON spec."""
    gen = spec["gen"]
    args = spec.get("args", {})

    # --- Auto-detect desktop context for napplicationcard_attach ---
    if gen == "napplicationcard_attach" and "desktop" not in args:
        def _has_desktop_selectors(activities):
            for a in activities:
                sel = a.get("args", {}).get("selector", "")
                if "<ctrl " in sel or "<ctrl>" in sel:
                    return True
                for key in _ALL_CHILD_KEYS:
                    if _has_desktop_selectors(a.get(key, [])):
                        return True
            return False
        if _has_desktop_selectors(spec.get("children", [])):
            args = dict(args, desktop=True)

    # --- Auto-enrich multiple_assign types from variable/argument declarations ---
    if gen == "multiple_assign" and _VAR_TYPE_LOOKUP and "assignments" in args:
        enriched = []
        for assign in args["assignments"]:
            if len(assign) == 2:
                to_var = assign[0]
                inferred_type = _VAR_TYPE_LOOKUP.get(to_var, "x:String")
                enriched.append([assign[0], assign[1], inferred_type])
            else:
                enriched.append(assign)
        args = dict(args, assignments=enriched)

    # --- Auto-enrich plain assign value_type from the target variable ---
    # Mirrors the multiple_assign block above. Prevents Studio BC30311
    # ("Value of type X cannot be converted to String") when a spec emits an
    # Assign without an explicit value_type and the target variable is not a
    # String (e.g. DataTable, Int32, FormTaskData). Leaves specs that
    # explicitly requested a non-default value_type alone.
    if gen == "assign" and _VAR_TYPE_LOOKUP and "to_variable" in args:
        to_var = args["to_variable"]
        inferred_type = _VAR_TYPE_LOOKUP.get(to_var)
        if inferred_type and args.get("value_type", "x:String") == "x:String":
            args = dict(args, value_type=inferred_type)

    # --- Auto-wire Object Repository references ---
    if _OBJ_REPO_LOOKUP and "obj_repo" not in args:
        selector = args.get("selector", "")
        if selector and gen in _SELECTOR_BASED_GENS:
            normalized = _normalize_selector(selector)
            elem_key = _OBJ_REPO_LOOKUP["selector_to_element"].get(normalized)
            if elem_key:
                obj_repo_ref = _OBJ_REPO_LOOKUP["refs"].get("elements", {}).get(elem_key)
                if obj_repo_ref:
                    args = dict(args, obj_repo=obj_repo_ref)
                    dn = args.get("display_name", gen)
                    print(f"  [AUTO-WIRE] {gen} '{dn}' \u2192 {elem_key}", file=sys.stderr)

    # Auto-wire app-level OR for napplicationcard containers
    if _OBJ_REPO_LOOKUP and "obj_repo_app" not in args:
        app_sel = args.get("target_app_selector", "")
        if app_sel and gen in ("napplicationcard_open",):
            normalized = _normalize_selector(app_sel)
            app_ref = _OBJ_REPO_LOOKUP["app_selectors"].get(normalized)
            if app_ref:
                args = dict(args, obj_repo_app=app_ref)
                dn = args.get("display_name", gen)
                print(f"  [AUTO-WIRE] {gen} '{dn}' \u2192 app:{list(_OBJ_REPO_LOOKUP['refs'].get('apps', {}).keys())[0] if _OBJ_REPO_LOOKUP['refs'].get('apps') else 'unknown'}", file=sys.stderr)

    # Special case: blocked generators
    if gen == "delay":
        raise ValueError(
            "Delay activity is not supported. Use NCheckState/NCheckAppState "
            "for synchronization instead of Delay activities."
        )

    # Special case: log_message / logmessage (custom arg mapping)
    if gen in ("log_message", "logmessage"):
        message = args["message_expr"] if "message_expr" in args else args.get("message", "")
        id_ref = counter.next("LogMessage")
        return gen_logmessage(
            message=message,
            id_ref=id_ref,
            level=args.get("level", "Info"),
            display_name=args.get("display_name", ""),
            indent=indent,
        )

    # Unified dispatch: check registry first
    entry = _REGISTRY.get(gen)
    if entry:
        if entry.container:
            return entry.fn(spec, args, scope_id, counter, indent)
        else:
            id_ref = counter.next(entry.idref)
            return _auto_dispatch(entry.fn, args,
                                  id_ref=id_ref, scope_id=scope_id, indent=indent)

    # Plugin generators (same auto-dispatch as core)
    plugin_gens = get_generators()
    if gen in plugin_gens:
        id_ref = counter.next(_idref_prefix(gen))
        return _auto_dispatch(plugin_gens[gen], args,
                              id_ref=id_ref, scope_id=scope_id,
                              indent=indent, project_root=_PROJECT_ROOT)

    # Final fallback: try the data-driven generator (annotation corpus).
    # Lets activities described purely in references/annotations/*.json be
    # emitted without a hand-written gen_* function.
    #
    # Exception policy:
    #   - WizardOnlyActivityError: let it propagate as its own type so callers
    #     (e.g. battle_test_activities.py) can distinguish "wizard-only refusal"
    #     from generic dispatch errors. The CLI's `except Exception` catch-all
    #     in main() still surfaces a useful message.
    #   - MissingScopeError: already a ValueError subclass — wrapping is
    #     redundant and hides the type from any future caller that wants to
    #     recover. Let it propagate.
    #   - ReviewNeededError: wrap as ValueError so the CLI message is uniform
    #     ("Cannot generate ...: ...") for activities awaiting human review.
    try:
        from generate_activities._data_driven import (
            gen_from_annotation,
            ReviewNeededError,
        )
    except ImportError:
        raise ValueError(f"Unknown generator: {gen}")

    try:
        id_ref = counter.next(_idref_prefix(gen))
        return gen_from_annotation(gen, args, id_ref=id_ref, scope_id=scope_id, indent=indent)
    except KeyError:
        # No annotation entry — preserve the original "Unknown generator" message
        raise ValueError(f"Unknown generator: {gen}")
    except ReviewNeededError as e:
        raise ValueError(f"Cannot generate {gen!r}: {e}") from e


# ---------------------------------------------------------------------------
# Full workflow assembly
# ---------------------------------------------------------------------------

def generate_workflow(spec: dict) -> str:
    """Generate a complete .xaml workflow from a JSON spec.

    Returns the complete XAML string.
    """
    class_name = spec["class_name"]
    arguments = spec.get("arguments", [])
    variables = spec.get("variables", [])
    activities = spec.get("activities", [])

    # Build variable/argument type lookup for type inference (e.g., multiple_assign)
    global _VAR_TYPE_LOOKUP
    _VAR_TYPE_LOOKUP = {}
    for v in variables:
        raw_type = v.get("type", "String")
        _VAR_TYPE_LOOKUP[v["name"]] = _EXTENDED_TYPE_MAP.get(raw_type, raw_type)
    for a in arguments:
        raw_type = a.get("type", "String")
        _VAR_TYPE_LOOKUP[a["name"]] = _EXTENDED_TYPE_MAP.get(raw_type, raw_type)

    counter = _IdRefCounter()

    # Detect namespace requirements from spec (must be before args/vars building)
    # Walk ALL child keys — not just "children" — to find nested activities.
    def _walk_all_activities(acts):
        """Yield every activity spec in the tree, recursively."""
        for a in acts:
            yield a
            for key in _ALL_CHILD_KEYS:
                yield from _walk_all_activities(a.get(key, []))
            # Switch cases: args.cases[].children
            for case in a.get("args", {}).get("cases", []):
                yield from _walk_all_activities(case.get("children", []))
            # IfElseIf conditions: args.conditions[].children
            for cond in a.get("args", {}).get("conditions", []):
                yield from _walk_all_activities(cond.get("children", []))
            # TryCatch catches: args.catches[].children
            for catch in a.get("args", {}).get("catches", []):
                yield from _walk_all_activities(catch.get("children", []))

    ui_gens = set(_CORE_UI_GENERATORS) | get_ui_generators()
    # Generators that emit sd:DataRow or sd2:DataTable (need sd=Data namespace)
    datatable_gens = {"foreach_row", "nextractdata"}

    # Generators that require uwah: (UiPath.Web.Activities.Http) namespace
    http_gens = {"net_http_request"}

    all_gen_names = {a.get("gen") for a in _walk_all_activities(activities)}
    has_ui = bool(all_gen_names & ui_gens)
    has_datatable = (
        any(a.get("type") in ("DataTable", "DataRow") for a in arguments + variables)
        or bool(all_gen_names & datatable_gens)
    )
    has_securestring = any(
        a.get("type") == "SecureString" for a in arguments + variables
    )
    has_http = bool(all_gen_names & http_gens)
    type_map = _type_map()
    type_map.update(get_type_mappings())  # Merge plugin type mappings

    # Candidate plugin namespaces. Which ones actually get declared in the
    # header is determined *after* the body is built so we can filter out
    # prefixes whose activities or types never appear — no more unused xmlns
    # lines in the emitted XAML.
    plugin_ns_map = get_extra_namespaces()

    # Build x:Members
    args_xml = _build_arguments_xml(arguments, type_map, all_xmlns_prefixes=_ALL_XMLNS_PREFIXES)

    # Build variables
    vars_xml = _build_variables_xml(variables, type_map=type_map)

    # Build activity body
    root_scope = str(uuid.uuid4())
    body_parts = []
    for act_spec in activities:
        body_parts.append(_generate_activity(act_spec, root_scope, counter))

    body = "\n".join(body_parts)

    # Option B post-processing: when UI + DataTable, generators emit sd:Image,
    # sd1:Rectangle (OCREngine blocks) and sd2:DataTable (NExtractData). But in this
    # mode sd=Data. Remap: sd2:→sd:, sd:Image→sdd:Image, sd1:→sdd1:
    if has_ui and has_datatable:
        body = (body
            .replace("sd2:DataTable", "sd:DataTable")
            .replace("sd:Image", "sdd:Image")
            .replace("sd1:Rectangle", "sdd1:Rectangle")
        )

    # Filter plugin_ns_map down to prefixes that actually appear somewhere in
    # the emitted body, variables, or arguments. A prefix like `upaf:` shows
    # up as an element start (`<upaf:CreateFormTask`), a type reference
    # (`x:TypeArguments="upaf:FormTaskData"`), an expression-bracketed type
    # (`[upaf:FormTaskData]`), or in the value of an xmlns-qualified
    # variable/argument declaration — the single regex below catches all of
    # those entry points by anchoring on a preceding `<`, `:`, `[`, `"`, or
    # whitespace character.
    extra_ns = None
    if plugin_ns_map:
        search_haystack = body + "\n" + (vars_xml or "") + "\n" + (args_xml or "")
        used_plugin_ns = {
            p: u for p, u in plugin_ns_map.items()
            if re.search(rf'(?:[<:\["\s]){re.escape(p)}:', search_haystack)
        }
        extra_ns = used_plugin_ns or None

    namespaces = _build_namespaces(has_ui, has_datatable, has_securestring, has_http,
                                    extra_namespaces=extra_ns)

    # ViewState for root sequence
    seq_idref = counter.next("Sequence")

    xml = f'<Activity mc:Ignorable="sap sap2010" x:Class="{class_name}"\n'
    xml += namespaces
    if args_xml:
        xml += args_xml + "\n"
    xml += '  <VisualBasic.Settings>\n    <x:Null />\n  </VisualBasic.Settings>\n'

    # TextExpression blocks — required for VB.NET expression compilation.
    # Without UiPath.Core namespace import, UiElement delegates fail with BC36532.
    xml += '  <sap2010:WorkflowViewState.IdRef>ActivityBuilder_1</sap2010:WorkflowViewState.IdRef>\n'
    xml += '  <TextExpression.NamespacesForImplementation>\n'
    xml += '    <sco:Collection x:TypeArguments="x:String">\n'
    xml += '      <x:String>GlobalConstantsNamespace</x:String>\n'
    xml += '      <x:String>GlobalVariablesNamespace</x:String>\n'
    # Microsoft.VisualBasic: makes bare VB intrinsics (Now, Today, vbCrLf, DateDiff, ...)
    # resolve without DateTime./Microsoft.VisualBasic. qualifiers. Without this import,
    # expressions like "Now.ToString(...)" fail with BC30451 in pure VB.NET XAML compilation.
    xml += '      <x:String>Microsoft.VisualBasic</x:String>\n'
    xml += '      <x:String>Microsoft.VisualBasic.Activities</x:String>\n'
    xml += '      <x:String>System</x:String>\n'
    xml += '      <x:String>System.Collections.Generic</x:String>\n'
    xml += '      <x:String>System.Collections.ObjectModel</x:String>\n'
    # System.IO: lets expressions reference Path.Combine, Directory.*, File.*,
    # FileInfo, StreamReader, etc. by short name. Without this import,
    # "Path.Combine(...)" fails with BC30451 in pure VB.NET XAML compilation.
    xml += '      <x:String>System.IO</x:String>\n'
    xml += '      <x:String>System.Linq</x:String>\n'
    xml += '      <x:String>UiPath.Core</x:String>\n'
    xml += '      <x:String>UiPath.Core.Activities</x:String>\n'
    if has_securestring:
        xml += '      <x:String>System.Security</x:String>\n'
    if has_datatable:
        xml += '      <x:String>System.Data</x:String>\n'
    if has_http:
        xml += '      <x:String>UiPath.Web.Activities.Http</x:String>\n'
    # Plugin CLR namespaces for VB.NET expression compilation
    if extra_ns:
        _seen_ns = set()
        _seen_asm = set()
        for uri in extra_ns.values():
            # Extract CLR namespace and assembly from xmlns URI
            # Format: "clr-namespace:Some.Namespace;assembly=Some.Assembly"
            parts = uri.split(";")
            clr_ns = parts[0].replace("clr-namespace:", "") if parts else ""
            asm = parts[1].replace("assembly=", "") if len(parts) > 1 else ""
            if clr_ns and clr_ns not in _seen_ns:
                xml += f'      <x:String>{clr_ns}</x:String>\n'
                _seen_ns.add(clr_ns)
            if asm and asm not in _seen_asm:
                _seen_asm.add(asm)
    xml += '    </sco:Collection>\n'
    xml += '  </TextExpression.NamespacesForImplementation>\n'
    xml += '  <TextExpression.ReferencesForImplementation>\n'
    xml += '    <sco:Collection x:TypeArguments="AssemblyReference">\n'
    xml += '      <AssemblyReference>Microsoft.VisualBasic</AssemblyReference>\n'
    xml += '      <AssemblyReference>Microsoft.VisualBasic.Core</AssemblyReference>\n'
    xml += '      <AssemblyReference>System.ComponentModel.TypeConverter</AssemblyReference>\n'
    xml += '      <AssemblyReference>System.Linq</AssemblyReference>\n'
    xml += '      <AssemblyReference>System.ObjectModel</AssemblyReference>\n'
    xml += '      <AssemblyReference>UiPath.System.Activities</AssemblyReference>\n'
    if has_ui:
        xml += '      <AssemblyReference>UiPath.UiAutomation.Activities</AssemblyReference>\n'
    if has_http:
        xml += '      <AssemblyReference>UiPath.Web.Activities</AssemblyReference>\n'
    # Plugin assembly references
    if extra_ns:
        for asm in sorted(_seen_asm):
            xml += f'      <AssemblyReference>{asm}</AssemblyReference>\n'
    xml += '    </sco:Collection>\n'
    xml += '  </TextExpression.ReferencesForImplementation>\n'

    xml += f'  <Sequence DisplayName="{_escape_xml_attr(class_name)}" sap2010:WorkflowViewState.IdRef="{seq_idref}">\n'
    xml += '    <sap:WorkflowViewStateService.ViewState>\n'
    xml += '      <scg:Dictionary x:TypeArguments="x:String, x:Object">\n'
    xml += '        <x:Boolean x:Key="IsExpanded">True</x:Boolean>\n'
    xml += '      </scg:Dictionary>\n'
    xml += '    </sap:WorkflowViewStateService.ViewState>\n'
    if vars_xml:
        xml += vars_xml + "\n"
    xml += body + "\n"
    xml += '  </Sequence>\n'
    xml += '</Activity>\n'

    return xml


# ---------------------------------------------------------------------------
# Required args for log_message / logmessage (special-cased in dispatch,
# not in _REGISTRY since they have custom arg mapping)
_LOG_MESSAGE_REQUIRED = ("message_expr",)

# Child keys — use module-level _ALL_CHILD_KEYS (single source of truth)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

# Wrapper functions that bind module-level state (_REGISTRY, etc.) to the
# parameterised implementations in _wf_validation.py, breaking circular imports.

def _validate_activities(activities, path, errors):
    return _validate_activities_impl(activities, path, errors,
                                     registry=_REGISTRY,
                                     log_message_required=_LOG_MESSAGE_REQUIRED,
                                     all_child_keys=_ALL_CHILD_KEYS)


def _validate_spec(spec):
    return _validate_spec_impl(spec,
                               registry=_REGISTRY,
                               log_message_required=_LOG_MESSAGE_REQUIRED,
                               all_child_keys=_ALL_CHILD_KEYS)


def _load_spec(spec_path: str) -> dict:
    """Load and parse a JSON spec from file or stdin."""
    try:
        if spec_path == "--stdin":
            return json.load(sys.stdin)
        else:
            with open(spec_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except FileNotFoundError:
        print(f"ERROR: Spec file not found: {spec_path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in spec: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    # --- --validate-spec mode: validate without generating ---
    if len(sys.argv) >= 2 and sys.argv[1] == "--validate-spec":
        if len(sys.argv) < 3:
            print("Usage: python generate_workflow.py --validate-spec <spec.json> [spec2.json ...]", file=sys.stderr)
            sys.exit(1)
        all_ok = True
        for spec_path in sys.argv[2:]:
            spec = _load_spec(spec_path)
            errs = _validate_spec(spec)
            if errs:
                print(f"FAIL: {spec_path} ({len(errs)} issue(s)):", file=sys.stderr)
                for err in errs:
                    print(f"  - {err}", file=sys.stderr)
                all_ok = False
            else:
                print(f"OK: {spec_path}")
        sys.exit(0 if all_ok else 1)

    # --- Parse positional and optional args ---
    positional = []
    project_dir = None
    snippet_mode = False
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--project-dir" and i + 1 < len(sys.argv):
            project_dir = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--snippet":
            snippet_mode = True
            i += 1
        elif sys.argv[i].startswith("--"):
            print(f"ERROR: Unknown flag: {sys.argv[i]}", file=sys.stderr)
            sys.exit(1)
        else:
            positional.append(sys.argv[i])
            i += 1

    if len(positional) < 2:
        print("Usage: python generate_workflow.py <spec.json> <output.xaml> [--project-dir <path>]", file=sys.stderr)
        print("       python generate_workflow.py --stdin <output.xaml> [--project-dir <path>]", file=sys.stderr)
        print("       python generate_workflow.py --validate-spec <spec.json> [...]", file=sys.stderr)
        print("\nOptions:", file=sys.stderr)
        print("  --project-dir <path>  Auto-wire Object Repository references from", file=sys.stderr)
        print("                        selectors.json + .objects/refs.json in the project", file=sys.stderr)
        sys.exit(1)

    spec_path = positional[0]
    output_path = positional[1]

    # --- Load Object Repository lookup if --project-dir provided ---
    global _OBJ_REPO_LOOKUP, _PROJECT_ROOT
    if project_dir:
        _OBJ_REPO_LOOKUP = _build_obj_repo_lookup(project_dir)
    _PROJECT_ROOT = project_dir

    # --- Load spec ---
    spec = _load_spec(spec_path)

    # --- Validate spec structure ---
    validation_errors = _validate_spec(spec)
    if validation_errors:
        print(f"ERROR: Invalid spec ({len(validation_errors)} issue(s)):", file=sys.stderr)
        for err in validation_errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)

    # --- Generate XAML ---
    try:
        xaml = generate_workflow(spec)
    except KeyError as e:
        print(f"ERROR: Missing required field in activity spec: {e}", file=sys.stderr)
        print("  Check that all activities have required 'args' fields for their generator type.", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"ERROR: Invalid value in spec: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Generation failed: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)

    # --- Snippet mode: extract inner activities only ---
    if snippet_mode:
        import re as _re_snippet
        # Remove everything before and including the outer Sequence opening tag + ViewState + Variables
        xaml = _re_snippet.sub(r'^.*?<Sequence\s[^>]*>\s*', '', xaml, count=1, flags=_re_snippet.DOTALL)
        xaml = _re_snippet.sub(r'\s*</Sequence>\s*</Activity>\s*$', '', xaml, flags=_re_snippet.DOTALL)
        # Remove ViewState block
        xaml = _re_snippet.sub(r'<sap:WorkflowViewStateService\.ViewState>.*?</sap:WorkflowViewStateService\.ViewState>\s*', '', xaml, flags=_re_snippet.DOTALL)
        # Remove Sequence.Variables block
        xaml = _re_snippet.sub(r'<Sequence\.Variables>.*?</Sequence\.Variables>\s*', '', xaml, flags=_re_snippet.DOTALL)
        xaml = xaml.strip()

    # --- Write output ---
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(xaml)
    except OSError as e:
        print(f"ERROR: Cannot write output file '{output_path}': {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Generated: {output_path} ({len(xaml)} bytes)")


if __name__ == "__main__":
    main()
