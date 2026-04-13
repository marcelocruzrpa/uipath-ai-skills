"""Tasks lint rules — moved from uipath-core validate_xaml.py.

AC-10: CreateFormTask / WaitForFormTaskAndResume count mismatch
AC-11: FormData keys don't match form.io component keys
AC-12: CreateExternalTask / WaitForExternalTaskAndResume count mismatch
AC-26: Persistence activities in non-Main workflow
"""

import json
import os
import re
from html import unescape


# form.io component types that are layout/decoration and do NOT bind to
# FormData. Keys on these components (e.g. a heading's `header` key or a
# `columns` container's own key) are not missing bindings — they're not
# data-bearing in the first place. AC-11 must skip them to avoid noise.
_NON_DATA_FORMIO_TYPES = frozenset({
    "button",
    "htmlelement",
    "content",
    "columns",
    "panel",
    "well",
    "fieldset",
    "tabs",
    "table",
})


def lint_tasks(ctx, result):
    """AC-10: CreateFormTask should have matching WaitForFormTaskAndResume."""
    content = ctx.active_content

    create_count = len(re.findall(r'<upaf:CreateFormTask[\s>]', content))
    wait_count = len(re.findall(r'<upaf:WaitForFormTaskAndResume[\s>]', content))

    if create_count == 0:
        return  # No Tasks activities

    if wait_count == 0:
        result.warn(
            f"[AC-10] {create_count} CreateFormTask(s) but no WaitForFormTaskAndResume — "
            f"form tasks will be created but workflow won't wait for user input"
        )
    elif wait_count < create_count:
        result.warn(
            f"[AC-10] {create_count} CreateFormTask(s) but only {wait_count} WaitForFormTaskAndResume — "
            f"some tasks may not be awaited (OK if using shadow task pattern)"
        )
    else:
        result.ok(f"Tasks: {create_count} CreateFormTask, {wait_count} WaitForFormTask")

    # Check FormData bindings: key names should be non-empty
    form_data_keys = re.findall(
        r'<(?:InArgument|OutArgument|InOutArgument)[^>]*x:Key="([^"]*)"',
        content
    )
    empty_keys = [k for k in form_data_keys if not k.strip()]
    if empty_keys:
        result.error(f"[AC-10] {len(empty_keys)} FormData binding(s) with empty x:Key — form field key is required")

    # Check that TaskOutput variable is captured
    create_no_output = re.findall(r'<upaf:CreateFormTask\b[^>]*TaskOutput="\{x:Null\}"', content)
    if create_no_output:
        result.warn(
            f"[AC-10] {len(create_no_output)} CreateFormTask(s) with TaskOutput={{x:Null}} — "
            f"task data won't be captured for WaitForFormTaskAndResume"
        )
    # Note: TaskObject hallucination check is in lint_hallucinated_property_names (core)

    # Check EnableDynamicForms — must be True for form designer to work
    dynamic_false = re.findall(
        r'<upaf:CreateFormTask\b[^>]*EnableDynamicForms="False"', content
    )
    if dynamic_false:
        result.warn(
            f"[AC-10] {len(dynamic_false)} CreateFormTask(s) with EnableDynamicForms=\"False\" — "
            f"form designer won't open in Studio. Set EnableDynamicForms=\"True\""
        )


def lint_formdata_key_mismatch(ctx, result):
    """AC-11: FormData x:Key values should match form.io component keys.

    Extracts component keys from the FormLayout JSON and compares against
    FormData binding x:Key values. Warns on mismatches (keys in FormData
    but not in form.io, or vice versa). Skips button components since they
    don't bind to FormData.
    """
    content = ctx.active_content

    if '<upaf:CreateFormTask' not in content:
        return

    # Extract FormLayout JSON from FormLayout="{}escaped_json" attribute
    form_layout_match = re.search(r'FormLayout="\{\}(.*?)"', content)
    if not form_layout_match:
        return

    raw_json = unescape(form_layout_match.group(1))
    try:
        schema = json.loads(raw_json)
    except (json.JSONDecodeError, ValueError):
        return  # Can't parse — skip silently

    # Extract form.io component keys — only the data-bearing ones.
    # Skip layout/decoration types (see _NON_DATA_FORMIO_TYPES). Do not
    # recurse into datagrid children: a datagrid is bound to FormData via
    # its own key (as a DataTable), and its inner `components` array is a
    # column schema, not a flat list of top-level bindings.
    def extract_keys(components):
        keys = set()
        for comp in components:
            key = comp.get("key", "")
            comp_type = comp.get("type", "")
            if key and comp_type not in _NON_DATA_FORMIO_TYPES:
                keys.add(key)
            if comp_type == "datagrid":
                continue  # inner components are column defs, not bindings
            for sub in comp.get("components", []):
                keys.update(extract_keys([sub]))
            for col in comp.get("columns", []):
                keys.update(extract_keys(col.get("components", [])))
        return keys

    form_keys = extract_keys(schema.get("components", []))
    if not form_keys:
        return

    # Extract FormData x:Key values — scoped to CreateFormTask.FormData blocks
    # to avoid false positives from CreateExternalTask.TaskData entries
    formdata_section = re.search(
        r'<upaf:CreateFormTask\.FormData>(.*?)</upaf:CreateFormTask\.FormData>',
        content, re.DOTALL
    )
    if not formdata_section:
        return
    formdata_keys = set(re.findall(
        r'<(?:InArgument|OutArgument|InOutArgument)[^>]*x:Key="([^"]+)"',
        formdata_section.group(1)
    ))

    # Compare
    in_form_not_data = form_keys - formdata_keys
    in_data_not_form = formdata_keys - form_keys

    if in_data_not_form:
        result.warn(
            f"[AC-11] FormData key(s) not in form.io schema: "
            f"{', '.join(sorted(in_data_not_form))}. "
            f"These bindings won't connect to any form field."
        )
    if in_form_not_data:
        result.warn(
            f"[AC-11] Form.io component(s) without FormData binding: "
            f"{', '.join(sorted(in_form_not_data))}. "
            f"Data won't flow to/from these fields unless bound."
        )


def lint_external_task(ctx, result):
    """AC-12: CreateExternalTask should have matching WaitForExternalTaskAndResume."""
    content = ctx.active_content

    create_count = len(re.findall(r'<upae:CreateExternalTask[\s>]', content))
    wait_count = len(re.findall(r'<upae:WaitForExternalTaskAndResume[\s>]', content))

    if create_count == 0:
        return  # No external task activities

    if wait_count == 0:
        result.warn(
            f"[AC-12] {create_count} CreateExternalTask(s) but no WaitForExternalTaskAndResume — "
            f"external tasks will be created but workflow won't wait for completion"
        )
    elif wait_count < create_count:
        result.warn(
            f"[AC-12] {create_count} CreateExternalTask(s) but only {wait_count} WaitForExternalTaskAndResume — "
            f"some tasks may not be awaited"
        )
    else:
        result.ok(f"External Task: {create_count} CreateExternalTask, {wait_count} WaitForExternalTask")

    # Check that TaskOutput variable is captured
    create_no_output = re.findall(r'<upae:CreateExternalTask\b[^>]*TaskOutput="\{x:Null\}"', content)
    if create_no_output:
        result.warn(
            f"[AC-12] {len(create_no_output)} CreateExternalTask(s) with TaskOutput={{x:Null}} — "
            f"task data won't be captured for WaitForExternalTaskAndResume"
        )


def _current_file_is_entry_point(ctx):
    """True if ctx.filepath is declared in the nearest project.json's entryPoints[].

    Walks up from ctx.filepath looking for project.json (same pattern as
    uipath-core/scripts/validate_xaml/lints_framework.py). Returns False when
    no project.json is found, when it can't be parsed, or when the current
    file's basename doesn't match any entry point.

    Comparing by basename is intentional: UiPath project.json entryPoints store
    relative paths from the project root, and HITL/secondary entry points
    typically live at the project root (a persistence-point workflow must be an
    entry point, so it cannot be buried in a subdirectory).
    """
    try:
        filepath = ctx.filepath
    except Exception:
        return False
    if not filepath:
        return False

    # ctx.filepath can be a relative path (when validate_xaml is invoked with
    # a bare filename from the project dir) — abspath it so os.path.dirname
    # returns something we can walk up from.
    filepath = os.path.abspath(filepath)
    project_dir = os.path.dirname(filepath)
    while project_dir and not os.path.isfile(os.path.join(project_dir, "project.json")):
        parent = os.path.dirname(project_dir)
        if parent == project_dir:
            return False
        project_dir = parent
    if not project_dir:
        return False

    project_json_path = os.path.join(project_dir, "project.json")
    try:
        with open(project_json_path, encoding="utf-8") as f:
            project = json.load(f)
    except (OSError, json.JSONDecodeError, ValueError):
        return False

    entry_points = project.get("entryPoints") or []
    if not isinstance(entry_points, list):
        return False

    current_basename = os.path.basename(filepath)
    for ep in entry_points:
        if not isinstance(ep, dict):
            continue
        ep_path = ep.get("filePath") or ep.get("FilePath") or ""
        if os.path.basename(ep_path) == current_basename:
            return True
    return False


def lint_persistence_in_subworkflow(ctx, result):
    """AC-26: Persistence (wait-and-resume) activities must be in an entry point.

    Activities like WaitForFormTaskAndResume are persistence points that
    suspend/serialize the workflow. They only work in entry-point files —
    Main.xaml by default, plus any additional workflow declared in
    `project.json.entryPoints[]` (e.g. a HITL sample registered as a second
    entry point alongside Main).
    """
    try:
        content = ctx.active_content
    except Exception:
        return

    # Check x:Class — Main.xaml always passes (fast path + no project.json needed)
    class_match = re.search(r'x:Class="([^"]+)"', content)
    if class_match and class_match.group(1) == "Main":
        return

    # Secondary entry point declared in project.json → also passes
    if _current_file_is_entry_point(ctx):
        return

    persistence_activities = [
        "WaitForFormTaskAndResume",
        "WaitForFormTaskCompletion",
        "WaitForExternalTaskAndResume",
        "WaitForAppTaskAndResume",
        "WaitForJobAndResume",
        "WaitForQueueItemAndResume",
        "ResumeAfterDelay",
        "WaitForItemEvent",
        "ResumeBookmark",
    ]

    for activity in persistence_activities:
        # Match as XML element: <prefix:ActivityName or <ActivityName
        if re.search(rf'<\w*:?{activity}[\s/>]', content):
            result.error(
                f"[AC-26] Persistence activity '{activity}' found in non-entry-point workflow "
                f"(x:Class='{class_match.group(1) if class_match else '?'}'). "
                f"Wait-and-resume activities MUST be in an entry-point file — Main.xaml "
                f"or another workflow declared in project.json entryPoints[]. The persistence "
                f"bookmark context only exists in entry points. Move '{activity}' to an entry "
                f"point or register this file as one."
            )
