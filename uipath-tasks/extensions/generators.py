"""Tasks XAML generators.

Covers Form Tasks, External Tasks, and Task Management activities from
UiPath.Persistence.Activities. Uses shared helpers from utils.py (stable
public API), available because plugin_loader adds core scripts/ to sys.path.

Namespace prefixes used:
    upaf: UiPath.Persistence.Activities.FormTask   — CreateFormTask, WaitForFormTaskAndResume, GetFormTasks
    upae: UiPath.Persistence.Activities.ExternalTask — CreateExternalTask, WaitForExternalTaskAndResume
    upat: UiPath.Persistence.Activities.Tasks       — CompleteTask, AssignTasks
"""

import json
import os
import re

from utils import escape_xml_attr as _escape_xml_attr
from utils import escape_vb_expr as _escape_vb_expr
from utils import generate_uuid as _uuid


_FORM_SLUG_RE = re.compile(r"[^A-Za-z0-9]+")
_DEFAULT_FORM_DISPLAY_NAME = "Create Form Task"


def _derive_default_form_path(display_name, id_ref):
    """Return `Forms/<slug>.json` for a CreateFormTask with no explicit path.

    Uses sanitized ``display_name`` when the caller gave it a meaningful name;
    otherwise falls back to ``id_ref`` (always unique per workflow — comes from
    the IdRef counter, e.g. ``CreateFormTask_1``).
    """
    base = display_name if display_name and display_name != _DEFAULT_FORM_DISPLAY_NAME else id_ref
    slug = _FORM_SLUG_RE.sub("_", base).strip("_") or id_ref
    return f"Forms/{slug}.json"


def form_layout_to_external_file(form_layout_json, form_id=None):
    """Convert form.io schema to the UiPath external-form-file shape.

    form.io default: `{"components": [...], "display"?: "form", ...}`
    UiPath DynamicFormPath file: `{"id": "<guid-or-slug>", "form": [...]}`

    Critical differences (see form-tasks.md:298-316):
    - Root key is `form`, not `components`.
    - Root `id` is required (any string).
    - No `display`/`name`/`title` wrappers.

    Args:
        form_layout_json: Raw JSON string with form.io schema.
        form_id: Optional explicit id; generated UUID if omitted.

    Returns:
        JSON string ready to write as `<project>/<DynamicFormPath>`.

    Raises:
        ValueError: if input is not parseable JSON or missing `components`.
    """
    try:
        schema = json.loads(form_layout_json)
    except (TypeError, json.JSONDecodeError) as e:
        raise ValueError(f"form_layout_json is not valid JSON: {e}") from e

    if isinstance(schema, list):
        components = schema
    elif isinstance(schema, dict):
        if "form" in schema and isinstance(schema["form"], list):
            # Already UiPath shape — preserve, only fix missing id.
            if not schema.get("id"):
                schema["id"] = form_id or _uuid()
            return json.dumps(schema, indent=2)
        components = schema.get("components")
        if not isinstance(components, list):
            raise ValueError(
                "form_layout_json must contain a 'components' array (form.io) "
                "or a 'form' array (UiPath external file)."
            )
    else:
        raise ValueError("form_layout_json must be a JSON object or array.")

    return json.dumps(
        {"id": form_id or _uuid(), "form": components},
        indent=2,
    )


# ---------------------------------------------------------------------------
# CreateFormTask (Tasks)
# ---------------------------------------------------------------------------

def gen_create_form_task(task_title_expr, task_output_variable, form_layout_json,
                         id_ref, form_data=None,
                         task_catalog_expr="",
                         task_priority="Medium",
                         bucket_name_expr="",
                         dynamic_form_path="",
                         project_root=None,
                         form_id=None,
                         display_name="Create Form Task", indent="    "):
    """Generate CreateFormTask — human-in-the-loop form task.

    Hallucination patterns prevented:
    - TaskObject property (doesn't exist → use TaskOutput)
    - Missing {} escape prefix on FormLayout JSON value
    - Missing ~15 {x:Null} properties
    - Missing BulkFormLayoutGuid / FormLayoutGuid (generated UUIDs)
    - .DictionaryCollection on FormData (doesn't exist)
    - Wrong FormData argument direction types

    CRITICAL: FormLayout JSON starts with { which XAML interprets as markup
    extension. MUST prefix with {} (empty curly braces = literal escape).

    Requires namespace:
        xmlns:upaf="clr-namespace:UiPath.Persistence.Activities.FormTask;assembly=UiPath.Persistence.Activities"
    Requires variable: <Variable x:TypeArguments="upaf:FormTaskData" Name="{task_output_variable}" />
    Requires: "supportsPersistence": true in project.json runtimeOptions

    Args:
        task_title_expr: VB expression for task title (no brackets),
                         e.g. 'String.Format("Review_{0}", strDocName)'
        task_output_variable: Variable receiving FormTaskData (no brackets)
        form_layout_json: Raw JSON string for form.io schema. When
                          ``dynamic_form_path`` is empty, this is inlined in
                          the XAML FormLayout attribute (XML-escaped, `{}`
                          prefixed). When ``dynamic_form_path`` is set, the
                          schema is converted to the UiPath external-file
                          shape and optionally written to disk; the XAML
                          still carries the inline FormLayout as a fallback
                          (required — UiPath validates it at load time).
        form_data: Dict of {field_key: (direction, type, variable)}.
                   direction: "In", "Out", "InOut"
                   type: "x:String", "sd:DataTable", "x:Int32", etc.
                   e.g. {"file_url": ("In", "x:String", "strFileUrl"),
                         "in_dt_records": ("InOut", "sd:DataTable", "dt_Records")}
        task_catalog_expr: VB expression for catalog name, or empty
        task_priority: "Low", "Medium", "High", "Critical"
        bucket_name_expr: VB expression for storage bucket, or empty
        dynamic_form_path: Project-relative path for the external form file,
                           e.g. ``"Forms/InvoiceApproval.json"``. When set,
                           ``DynamicFormPath`` is emitted instead of
                           ``{x:Null}`` — Studio's form designer loads the
                           file for editing, and schema changes diff cleanly.
                           AC-32 will fire if the file is missing on disk.
                           When empty but ``project_root`` is set, a default
                           path is derived from ``display_name`` (or
                           ``id_ref`` if the display name is the default).
        project_root: Absolute path to the UiPath project directory. When
                      set together with ``dynamic_form_path`` (explicit or
                      auto-derived), the converted form schema is written
                      to ``<project_root>/<path>``. Omit to emit the
                      DynamicFormPath attribute without writing the file
                      (caller handles the write) — or emit ``{x:Null}`` if
                      no path was supplied either.
        form_id: Explicit id for the external form file. Generated UUID when
                 omitted. Ignored when ``dynamic_form_path`` is empty.
    """
    valid_priorities = ("Low", "Medium", "High", "Critical")
    if task_priority not in valid_priorities:
        raise ValueError(
            f"Invalid TaskPriority '{task_priority}' — must be one of: {', '.join(valid_priorities)}"
        )

    if not task_title_expr or not task_title_expr.strip():
        raise ValueError("task_title_expr is required — cannot be empty")

    if not task_output_variable or not task_output_variable.strip():
        raise ValueError("task_output_variable is required — cannot be empty")

    if not form_layout_json or not form_layout_json.strip():
        raise ValueError("form_layout_json is required — cannot be empty")

    dn = _escape_xml_attr(display_name)
    i, i2, i3 = indent, indent + "  ", indent + "    "

    # XML-escape the JSON and add {} prefix
    escaped_json = _escape_xml_attr(form_layout_json)
    form_layout_attr = f'{{}}{escaped_json}'

    catalog = f'TaskCatalog="[{_escape_xml_attr(task_catalog_expr)}]"' if task_catalog_expr else 'TaskCatalog="{x:Null}"'
    bucket = f'BucketName="[{_escape_xml_attr(bucket_name_expr)}]"' if bucket_name_expr else 'BucketName="{x:Null}"'

    form_layout_guid = _uuid()
    bulk_form_layout_guid = _uuid()

    # External form file: emit DynamicFormPath and (optionally) write the file.
    # Studio's form designer edits .json files at DynamicFormPath — inline
    # FormLayout is not editable from the designer. When writing, convert
    # form.io {"components":[…]} to UiPath {"id":…,"form":[…]} per
    # form-tasks.md:298–316.
    # Auto-extract when project_root is known but no path was given — gives
    # "it just works" sidecar emission to CLI callers who pass --project-dir.
    effective_form_path = dynamic_form_path
    if not effective_form_path and project_root:
        effective_form_path = _derive_default_form_path(display_name, id_ref)

    if effective_form_path:
        normalized_path = effective_form_path.replace("\\", "/")
        dynamic_form_attr = (
            f'DynamicFormPath="{_escape_xml_attr(normalized_path)}"'
        )
        if project_root:
            converted = form_layout_to_external_file(form_layout_json, form_id)
            abs_target = os.path.join(
                project_root, normalized_path.replace("/", os.sep)
            )
            os.makedirs(os.path.dirname(abs_target) or ".", exist_ok=True)
            with open(abs_target, "w", encoding="utf-8") as f:
                f.write(converted)
    else:
        dynamic_form_attr = 'DynamicFormPath="{x:Null}"'

    # FormData children
    valid_directions = ("In", "Out", "InOut")
    form_data_block = ""
    if form_data:
        if not isinstance(form_data, dict):
            raise TypeError(
                f"form_data must be a dict, got {type(form_data).__name__}"
            )
        dir_map = {"In": "InArgument", "Out": "OutArgument", "InOut": "InOutArgument"}
        fd_lines = []
        for key, (direction, ftype, fvar) in form_data.items():
            if direction not in valid_directions:
                raise ValueError(
                    f"Invalid FormData direction '{direction}' for key '{key}' "
                    f"— must be one of: {', '.join(valid_directions)}"
                )
            tag = dir_map[direction]
            fd_lines.append(
                f'{i3}<{tag} x:TypeArguments="{ftype}" x:Key="{_escape_xml_attr(key)}">[{fvar}]</{tag}>'
            )
        fd_xml = "\n".join(fd_lines)
        form_data_block = f"""\n{i2}<upaf:CreateFormTask.FormData>
{fd_xml}
{i2}</upaf:CreateFormTask.FormData>"""

    return (
        f'{i}<upaf:CreateFormTask BucketFolderPath="{{x:Null}}" BulkFormLayout="{{x:Null}}" '
        f'{dynamic_form_attr} ExternalTag="{{x:Null}}" Labels="{{x:Null}}" '
        f'TimeoutMs="{{x:Null}}" '
        f'{bucket} '
        f'BulkFormLayoutGuid="{bulk_form_layout_guid}" '
        f'DisplayName="{dn}" '
        f'EnableBulkEdit="False" EnableDynamicForms="True" EnableV2="False" '
        f'FormLayout="{form_layout_attr}" '
        f'FormLayoutGuid="{form_layout_guid}" '
        f'GenerateInputFields="True" '
        f'{catalog} '
        f'TaskOutput="[{task_output_variable}]" '
        f'TaskPriority="{task_priority}" '
        f'TaskTitle="[{_escape_vb_expr(task_title_expr)}]" '
        f'sap:VirtualizedContainerService.HintSize="600,300" '
        f'sap2010:WorkflowViewState.IdRef="{id_ref}">'
        f'{form_data_block}\n'
        f'{i}</upaf:CreateFormTask>'
    )


# ---------------------------------------------------------------------------
# WaitForFormTaskAndResume (Tasks)
# ---------------------------------------------------------------------------

def gen_wait_for_form_task(task_input_variable, id_ref,
                           task_action_variable="", task_output_variable="",
                           display_name="Wait for Form Task and Resume",
                           indent="    "):
    """Generate WaitForFormTaskAndResume — suspend workflow until human submits.

    Hallucination patterns prevented:
    - TaskObject (doesn't exist → use TaskInput)
    - Missing {x:Null} for unused properties
    - Placing in sub-workflow (MUST be in Main.xaml — persistence point)

    Requires namespace:
        xmlns:upaf="clr-namespace:UiPath.Persistence.Activities.FormTask;assembly=UiPath.Persistence.Activities"

    Args:
        task_input_variable: FormTaskData variable from CreateFormTask.TaskOutput (no brackets)
        task_action_variable: Optional — receives user action string (no brackets)
        task_output_variable: Optional — receives updated FormTaskData (no brackets)
    """
    if not task_input_variable or not task_input_variable.strip():
        raise ValueError("task_input_variable is required — cannot be empty")

    dn = _escape_xml_attr(display_name)
    i = indent

    action = f'TaskAction="[{task_action_variable}]"' if task_action_variable else 'TaskAction="{x:Null}"'
    output = f'TaskOutput="[{task_output_variable}]"' if task_output_variable else 'TaskOutput="{x:Null}"'

    return (
        f'{i}<upaf:WaitForFormTaskAndResume StatusMessage="{{x:Null}}" '
        f'{action} '
        f'{output} '
        f'TimeoutMs="{{x:Null}}" WaitItemDataObject="{{x:Null}}" '
        f'DisplayName="{dn}" '
        f'TaskInput="[{task_input_variable}]" '
        f'sap:VirtualizedContainerService.HintSize="400,100" '
        f'sap2010:WorkflowViewState.IdRef="{id_ref}" />'
    )


# ---------------------------------------------------------------------------
# CreateExternalTask (Tasks — system-in-the-loop)
# ---------------------------------------------------------------------------

def gen_create_external_task(task_title_expr, task_output_variable, id_ref,
                              task_data=None,
                              task_catalog_expr="",
                              task_priority="Medium",
                              external_tag_expr="",
                              display_name="Create External Task",
                              indent="    "):
    """Generate CreateExternalTask — task resolved by an external system.

    External tasks have no UI form. They are completed
    programmatically via the Orchestrator API by an external system
    (JIRA, Salesforce, ServiceNow, etc.).

    Hallucination patterns prevented:
    - TaskObject property (doesn't exist → use TaskOutput)
    - FormLayout / FormData properties (don't exist on external tasks)

    Requires namespace:
        xmlns:upae="clr-namespace:UiPath.Persistence.Activities.ExternalTask;assembly=UiPath.Persistence.Activities"
    Requires variable: <Variable x:TypeArguments="upae:ExternalTaskData" Name="{task_output_variable}" />
    Requires: "supportsPersistence": true in project.json runtimeOptions

    Args:
        task_title_expr: VB expression for task title (no brackets),
                         e.g. '"JIRA_" & strTicketId'
        task_output_variable: Variable receiving ExternalTaskData (no brackets)
        task_data: Optional dict of {key: variable_name} pairs for task data.
                   Each entry becomes an entry in the Dictionary(Of String, Argument).
                   Pass None or empty dict for no task data.
        task_catalog_expr: VB expression for catalog name, or empty
        task_priority: "Low", "Medium", "High", "Critical"
        external_tag_expr: VB expression for external tag, or empty
    """
    valid_priorities = ("Low", "Medium", "High", "Critical")
    if task_priority not in valid_priorities:
        raise ValueError(
            f"Invalid TaskPriority '{task_priority}' — must be one of: {', '.join(valid_priorities)}"
        )

    if not task_title_expr or not task_title_expr.strip():
        raise ValueError("task_title_expr is required — cannot be empty")

    if not task_output_variable or not task_output_variable.strip():
        raise ValueError("task_output_variable is required — cannot be empty")

    dn = _escape_xml_attr(display_name)
    i, i2 = indent, indent + "  "

    catalog = f'TaskCatalog="[{_escape_xml_attr(task_catalog_expr)}]"' if task_catalog_expr else 'TaskCatalog="{x:Null}"'
    ext_tag = f'ExternalTag="[{_escape_xml_attr(external_tag_expr)}]"' if external_tag_expr else 'ExternalTag="{x:Null}"'

    # TaskData child element — Dictionary<String, Argument>
    task_data_block = ""
    if task_data and isinstance(task_data, dict):
        td_entries = []
        for key, var_name in task_data.items():
            td_entries.append(
                f'{i2}  <InArgument x:TypeArguments="x:String" x:Key="{_escape_xml_attr(key)}">[{var_name}]</InArgument>'
            )
        td_xml = "\n".join(td_entries)
        task_data_block = (
            f'\n{i2}<upae:CreateExternalTask.TaskData>\n'
            f'{i2}  <scg:Dictionary x:TypeArguments="x:String, Argument">\n'
            f'{td_xml}\n'
            f'{i2}  </scg:Dictionary>\n'
            f'{i2}</upae:CreateExternalTask.TaskData>'
        )
    else:
        task_data_block = (
            f'\n{i2}<upae:CreateExternalTask.TaskData>\n'
            f'{i2}  <scg:Dictionary x:TypeArguments="x:String, Argument" />\n'
            f'{i2}</upae:CreateExternalTask.TaskData>'
        )

    return (
        f'{i}<upae:CreateExternalTask '
        f'{ext_tag} '
        f'Labels="{{x:Null}}" '
        f'{catalog} '
        f'TimeoutMs="{{x:Null}}" '
        f'DisplayName="{dn}" '
        f'sap:VirtualizedContainerService.HintSize="600,300" '
        f'sap2010:WorkflowViewState.IdRef="{id_ref}" '
        f'TaskOutput="[{task_output_variable}]" '
        f'TaskPriority="{task_priority}" '
        f'TaskTitle="[{_escape_vb_expr(task_title_expr)}]">'
        f'{task_data_block}\n'
        f'{i}</upae:CreateExternalTask>'
    )


# ---------------------------------------------------------------------------
# WaitForExternalTaskAndResume (Tasks)
# ---------------------------------------------------------------------------

def gen_wait_for_external_task(task_input_variable, id_ref,
                                task_action_variable="",
                                task_output_variable="",
                                display_name="Wait for External Task and Resume",
                                indent="    "):
    """Generate WaitForExternalTaskAndResume — suspend until external system completes task.

    Hallucination patterns prevented:
    - TaskObject (doesn't exist → use TaskInput)
    - Missing {x:Null} for unused properties
    - Placing in sub-workflow (MUST be in Main.xaml — persistence point)

    Requires namespace:
        xmlns:upae="clr-namespace:UiPath.Persistence.Activities.ExternalTask;assembly=UiPath.Persistence.Activities"

    Args:
        task_input_variable: ExternalTaskData variable from CreateExternalTask.TaskOutput (no brackets)
        task_action_variable: Optional — receives action string (no brackets)
        task_output_variable: Optional — receives updated ExternalTaskData (no brackets)
    """
    if not task_input_variable or not task_input_variable.strip():
        raise ValueError("task_input_variable is required — cannot be empty")

    dn = _escape_xml_attr(display_name)
    i = indent

    action = f'TaskAction="[{task_action_variable}]"' if task_action_variable else 'TaskAction="{x:Null}"'
    output = f'TaskOutput="[{task_output_variable}]"' if task_output_variable else 'TaskOutput="{x:Null}"'

    return (
        f'{i}<upae:WaitForExternalTaskAndResume StatusMessage="{{x:Null}}" '
        f'{action} '
        f'{output} '
        f'TimeoutMs="{{x:Null}}" WaitItemDataObject="{{x:Null}}" '
        f'DisplayName="{dn}" '
        f'TaskInput="[{task_input_variable}]" '
        f'sap:VirtualizedContainerService.HintSize="400,100" '
        f'sap2010:WorkflowViewState.IdRef="{id_ref}" />'
    )


# ---------------------------------------------------------------------------
# GetFormTasks (Tasks — recovery / cross-process retrieval)
# ---------------------------------------------------------------------------

def gen_get_form_tasks(output_variable, id_ref,
                       filter_expr="",
                       task_catalog_name_expr="",
                       top_expr="", skip_expr="",
                       order_by_expr="",
                       display_name="Get Form Tasks",
                       indent="    "):
    """Generate GetFormTasks — retrieve existing form tasks from Orchestrator.

    Used for recovery workflows (retrieve tasks created by another process),
    cross-process orchestration, and task status monitoring. This is NOT a
    persistence point — it can be used in sub-workflows.

    Requires namespace:
        xmlns:upaf="clr-namespace:UiPath.Persistence.Activities.FormTask;assembly=UiPath.Persistence.Activities"
    Requires variable: <Variable x:TypeArguments="scg:List(upaf:FormTaskData)" Name="{output_variable}" />

    Args:
        output_variable: Variable receiving List(FormTaskData) (no brackets)
        filter_expr: OData filter string, e.g. "Status eq 'Pending'"
        task_catalog_name_expr: VB expression for catalog name filter, or empty
        top_expr: OData $top value (string or VB expression), or empty
        skip_expr: OData $skip value (string or VB expression), or empty
        order_by_expr: OData $orderby value, or empty
    """
    if not output_variable or not output_variable.strip():
        raise ValueError("output_variable is required — cannot be empty")

    dn = _escape_xml_attr(display_name)
    i = indent

    filt = f'Filter="{_escape_xml_attr(filter_expr)}"' if filter_expr else 'Filter="{x:Null}"'
    catalog = f'TaskCatalogName="[{_escape_xml_attr(task_catalog_name_expr)}]"' if task_catalog_name_expr else 'TaskCatalogName="{x:Null}"'
    top = f'Top="{_escape_xml_attr(top_expr)}"' if top_expr else 'Top="{x:Null}"'
    skip = f'Skip="{_escape_xml_attr(skip_expr)}"' if skip_expr else 'Skip="{x:Null}"'
    order = f'OrderBy="{_escape_xml_attr(order_by_expr)}"' if order_by_expr else 'OrderBy="{x:Null}"'

    return (
        f'{i}<upaf:GetFormTasks Expand="{{x:Null}}" '
        f'{order} '
        f'Reference="{{x:Null}}" '
        f'Select="{{x:Null}}" '
        f'{skip} '
        f'{catalog} '
        f'TimeoutMs="{{x:Null}}" '
        f'{top} '
        f'DisplayName="{dn}" '
        f'{filt} '
        f'sap:VirtualizedContainerService.HintSize="400,200" '
        f'sap2010:WorkflowViewState.IdRef="{id_ref}" '
        f'TaskObjects="[{output_variable}]" />'
    )


# ---------------------------------------------------------------------------
# CompleteTask (Task Management)
# ---------------------------------------------------------------------------

def gen_complete_task(task_id_expr, id_ref,
                      action_expr="Completed",
                      display_name="Complete Task",
                      indent="    "):
    """Generate CompleteTask — programmatically complete a task.

    Used for escalation handlers, timeout completion, and automated resolution.
    Works with any task type (form, external, app).

    Requires namespace:
        xmlns:upat="clr-namespace:UiPath.Persistence.Activities.Tasks;assembly=UiPath.Persistence.Activities"

    Args:
        task_id_expr: VB expression evaluating to the task ID (no brackets),
                      e.g. 'formTasks(0).Id.Value' or 'taskIdVariable'
        action_expr: Completion action string, e.g. "Completed", "Approved", "Rejected"
    """
    if not task_id_expr or not task_id_expr.strip():
        raise ValueError("task_id_expr is required — cannot be empty")

    dn = _escape_xml_attr(display_name)
    i = indent

    return (
        f'{i}<upat:CompleteTask Data="{{x:Null}}" TimeoutMs="{{x:Null}}" '
        f'Action="{_escape_xml_attr(action_expr)}" '
        f'DisplayName="{dn}" '
        f'sap:VirtualizedContainerService.HintSize="400,200" '
        f'sap2010:WorkflowViewState.IdRef="{id_ref}" '
        f'TaskId="[{_escape_vb_expr(task_id_expr)}]" />'
    )


# ---------------------------------------------------------------------------
# AssignTasks (Task Management)
# ---------------------------------------------------------------------------

_VALID_CRITERIA = {
    "SingleUser": ("SingleUser", "SingleUserDescription",
                   "Activity_AssignTasks_AssignmentCriteria_SingleUserName"),
    "AllUsersInGroup": ("AllUsersInGroup", "AllUsersInGroupDescription",
                        "Activity_AssignTasks_AssignmentCriteria_AllUsersInGroupName"),
}


def gen_assign_tasks(task_id_expr, id_ref,
                     user_name_or_email="",
                     group_expr="",
                     assignment_criteria="SingleUser",
                     display_name="Assign Tasks",
                     indent="    "):
    """Generate AssignTasks — assign a task to a user or group.

    Requires namespace:
        xmlns:upat="clr-namespace:UiPath.Persistence.Activities.Tasks;assembly=UiPath.Persistence.Activities"

    Args:
        task_id_expr: VB expression evaluating to the task ID (no brackets)
        user_name_or_email: Email or username to assign to (for SingleUser criteria)
        group_expr: VB expression for group name (for AllUsersInGroup criteria)
        assignment_criteria: "SingleUser" or "AllUsersInGroup"
    """
    if not task_id_expr or not task_id_expr.strip():
        raise ValueError("task_id_expr is required — cannot be empty")

    if assignment_criteria not in _VALID_CRITERIA:
        raise ValueError(
            f"Invalid assignment_criteria '{assignment_criteria}' — "
            f"must be one of: {', '.join(_VALID_CRITERIA)}"
        )

    if assignment_criteria == "SingleUser" and not user_name_or_email:
        raise ValueError("user_name_or_email is required when assignment_criteria is 'SingleUser'")

    if assignment_criteria == "AllUsersInGroup" and not group_expr:
        raise ValueError("group_expr is required when assignment_criteria is 'AllUsersInGroup'")

    dn = _escape_xml_attr(display_name)
    i, i2 = indent, indent + "  "

    crit_id, crit_desc, crit_name = _VALID_CRITERIA[assignment_criteria]

    group = f'Group="[{_escape_xml_attr(group_expr)}]"' if group_expr else 'Group="{x:Null}"'
    user_attr = f'UserNameOrEmail="{_escape_xml_attr(user_name_or_email)}"' if user_name_or_email else 'UserNameOrEmail="{x:Null}"'

    return (
        f'{i}<upat:AssignTasks '
        f'FailedTaskAssignments="{{x:Null}}" '
        f'{group} '
        f'TaskUserAssignments="{{x:Null}}" '
        f'TimeoutMs="{{x:Null}}" '
        f'UserId="{{x:Null}}" '
        f'DisplayName="{dn}" '
        f'EnableMultipleAssignments="False" '
        f'sap:VirtualizedContainerService.HintSize="400,200" '
        f'sap2010:WorkflowViewState.IdRef="{id_ref}" '
        f'MigrateV144="False" '
        f'TaskAssignmentType="Assign" '
        f'TaskId="[{_escape_vb_expr(task_id_expr)}]" '
        f'{user_attr}>\n'
        f'{i2}<upat:AssignTasks.AssignmentCriteria>\n'
        f'{i2}  <upat:Criteria Description="{crit_desc}" Id="{crit_id}" Name="{crit_name}" />\n'
        f'{i2}</upat:AssignTasks.AssignmentCriteria>\n'
        f'{i}</upat:AssignTasks>'
    )


# ---------------------------------------------------------------------------
# Inline xmlns declarations
#
# battle_test_activities.py wraps each generated fragment in a fixed namespace
# header that does NOT declare the Persistence-package prefixes (upat / upau).
# The other tasks generators above (CreateFormTask, etc.) are declared
# `harvestable: false` in the version profile and skipped, so they never hit
# the XML well-formedness check. The three activities introduced below
# (ForwardTask, GetAppTasks, WaitForUserActionAndResume) are `harvestable: true`,
# so their fragments must self-declare any non-standard prefix. Mirrors the
# inline-xmlns convention used by uipath-core/scripts/generate_activities/
# _data_driven.py for prefixes outside _STANDARD_XMLNS_PREFIXES.
# ---------------------------------------------------------------------------
_UPAT_XMLNS = (
    'xmlns:upat="clr-namespace:UiPath.Persistence.Activities.Tasks;'
    'assembly=UiPath.Persistence.Activities"'
)
_UPAU_XMLNS = (
    'xmlns:upau="clr-namespace:UiPath.Persistence.Activities.UserAction;'
    'assembly=UiPath.Persistence.Activities"'
)


# ---------------------------------------------------------------------------
# ForwardTask (Task Management) — re-route a task to another user/group
# ---------------------------------------------------------------------------

def gen_forward_task(id_ref,
                     task_id_expr="",
                     user_name_or_email="",
                     comments_expr="",
                     timeout_ms_expr="",
                     display_name="Forward Task",
                     indent="    "):
    """Generate ForwardTask — reassign an existing task to a different user.

    Used in escalation flows when the originally-assigned user cannot complete
    the task. Reassigns by user name or email; optional comment is shown to
    the new assignee.

    Requires namespace:
        xmlns:upat="clr-namespace:UiPath.Persistence.Activities.Tasks;assembly=UiPath.Persistence.Activities"

    Args:
        task_id_expr: VB expression evaluating to the task ID (no brackets).
                      Empty → emitted as `{x:Null}`.
        user_name_or_email: Email or username of the new assignee.
                            Empty → emitted as `{x:Null}`.
        comments_expr: Optional VB expression with a comment for the new
                       assignee. Empty → `{x:Null}`.
        timeout_ms_expr: Optional VB expression for request timeout. Empty
                        → `{x:Null}`.
    """
    dn = _escape_xml_attr(display_name)
    i = indent

    task_id = (
        f'TaskId="[{_escape_vb_expr(task_id_expr)}]"'
        if task_id_expr else 'TaskId="{x:Null}"'
    )
    user = (
        f'UserNameOrEmail="[{_escape_vb_expr(user_name_or_email)}]"'
        if user_name_or_email else 'UserNameOrEmail="{x:Null}"'
    )
    comments = (
        f'Comments="[{_escape_vb_expr(comments_expr)}]"'
        if comments_expr else 'Comments="{x:Null}"'
    )
    timeout = (
        f'TimeoutMs="[{_escape_vb_expr(timeout_ms_expr)}]"'
        if timeout_ms_expr else 'TimeoutMs="{x:Null}"'
    )

    return (
        f'{i}<upat:ForwardTask {_UPAT_XMLNS} '
        f'{comments} '
        f'{task_id} '
        f'{timeout} '
        f'{user} '
        f'DisplayName="{dn}" '
        f'sap:VirtualizedContainerService.HintSize="400,200" '
        f'sap2010:WorkflowViewState.IdRef="{id_ref}" />'
    )


# ---------------------------------------------------------------------------
# GetAppTasks (User-Action / App-Task retrieval)
# ---------------------------------------------------------------------------

def gen_get_app_tasks(id_ref,
                      task_objects_variable="tasks",
                      task_catalog_name_expr="",
                      filter_expr="",
                      order_by_expr="",
                      select_expr="",
                      expand_expr="",
                      top_expr="",
                      skip_expr="",
                      timeout_ms_expr="",
                      display_name="Get App Tasks",
                      indent="    "):
    """Generate GetAppTasks — retrieve App Tasks (user-action tasks) from Orchestrator.

    Counterpart of GetFormTasks for App Tasks (a.k.a. user-action tasks). Used
    by recovery flows and for monitoring queues of app-task work items.

    Requires namespace:
        xmlns:upau="clr-namespace:UiPath.Persistence.Activities.UserAction;assembly=UiPath.Persistence.Activities"
    Requires variable: <Variable x:TypeArguments="..." Name="{task_objects_variable}" />

    Args:
        task_objects_variable: Variable receiving the retrieved task objects
                               (no brackets). Defaults to ``"tasks"`` so the
                               minimal-spec battle-test path produces valid
                               XAML; production callers should pass an
                               explicit variable name.
        task_catalog_name_expr: Optional catalog filter VB expression.
        filter_expr: OData filter string, e.g. "Status eq 'Pending'".
        order_by_expr / select_expr / expand_expr: OData modifiers.
        top_expr / skip_expr: OData paging.
        timeout_ms_expr: Optional VB expression for request timeout.
    """
    dn = _escape_xml_attr(display_name)
    i = indent

    catalog = (
        f'TaskCatalogName="[{_escape_vb_expr(task_catalog_name_expr)}]"'
        if task_catalog_name_expr else 'TaskCatalogName="{x:Null}"'
    )
    filt = (
        f'Filter="{_escape_xml_attr(filter_expr)}"'
        if filter_expr else 'Filter="{x:Null}"'
    )
    order = (
        f'OrderBy="{_escape_xml_attr(order_by_expr)}"'
        if order_by_expr else 'OrderBy="{x:Null}"'
    )
    sel = (
        f'Select="{_escape_xml_attr(select_expr)}"'
        if select_expr else 'Select="{x:Null}"'
    )
    expand = (
        f'Expand="{_escape_xml_attr(expand_expr)}"'
        if expand_expr else 'Expand="{x:Null}"'
    )
    top = (
        f'Top="{_escape_xml_attr(top_expr)}"'
        if top_expr else 'Top="{x:Null}"'
    )
    skip = (
        f'Skip="{_escape_xml_attr(skip_expr)}"'
        if skip_expr else 'Skip="{x:Null}"'
    )
    timeout = (
        f'TimeoutMs="[{_escape_vb_expr(timeout_ms_expr)}]"'
        if timeout_ms_expr else 'TimeoutMs="{x:Null}"'
    )

    return (
        f'{i}<upau:GetAppTasks {_UPAU_XMLNS} '
        f'{expand} {filt} {order} {sel} {skip} {catalog} {timeout} {top} '
        f'DisplayName="{dn}" '
        f'TaskObjects="[{task_objects_variable}]" '
        f'sap:VirtualizedContainerService.HintSize="400,200" '
        f'sap2010:WorkflowViewState.IdRef="{id_ref}" />'
    )


# ---------------------------------------------------------------------------
# WaitForUserActionAndResume (User-Action persistence point)
# ---------------------------------------------------------------------------

def gen_wait_for_user_action_and_resume(id_ref,
                                        task_input_expr="tasks.First",
                                        task_action_variable="",
                                        task_output_variable="",
                                        status_message_expr="",
                                        timeout_ms_expr="",
                                        display_name="Wait For App Task and Resume",
                                        indent="    "):
    """Generate WaitForUserActionAndResume — suspend workflow until App Task completes.

    Counterpart of WaitForFormTaskAndResume / WaitForExternalTaskAndResume for
    App Tasks (user-action tasks). MUST live in Main.xaml — this is a
    persistence point and Studio refuses sub-workflow placement.

    Requires namespace:
        xmlns:upau="clr-namespace:UiPath.Persistence.Activities.UserAction;assembly=UiPath.Persistence.Activities"

    Args:
        task_input_expr: VB expression for the input task object — typically
                         the first item of a GetAppTasks result, e.g.
                         ``"tasks.First"`` (the default mirrors the
                         ground-truth template) or
                         ``"appTasks.FirstOrDefault()"``.
        task_action_variable: Optional — receives the user-supplied action
                              string (no brackets). Empty → `{x:Null}`.
        task_output_variable: Optional — receives the updated task object
                              (no brackets). Empty → `{x:Null}`.
        status_message_expr: Optional VB expression for a status message
                             shown while waiting.
        timeout_ms_expr: Optional VB expression for resume timeout.
    """
    dn = _escape_xml_attr(display_name)
    i = indent

    status = (
        f'StatusMessage="[{_escape_vb_expr(status_message_expr)}]"'
        if status_message_expr else 'StatusMessage="{x:Null}"'
    )
    action = (
        f'TaskAction="[{task_action_variable}]"'
        if task_action_variable else 'TaskAction="{x:Null}"'
    )
    output = (
        f'TaskOutput="[{task_output_variable}]"'
        if task_output_variable else 'TaskOutput="{x:Null}"'
    )
    timeout = (
        f'TimeoutMs="[{_escape_vb_expr(timeout_ms_expr)}]"'
        if timeout_ms_expr else 'TimeoutMs="{x:Null}"'
    )

    return (
        f'{i}<upau:WaitForUserActionAndResume {_UPAU_XMLNS} '
        f'{status} '
        f'{action} '
        f'{output} '
        f'{timeout} '
        f'WaitItemDataObject="{{x:Null}}" '
        f'DisplayName="{dn}" '
        f'TaskInput="[{_escape_vb_expr(task_input_expr)}]" '
        f'sap:VirtualizedContainerService.HintSize="400,100" '
        f'sap2010:WorkflowViewState.IdRef="{id_ref}" />'
    )
