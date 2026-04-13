"""Tasks XAML generators.

Covers Form Tasks, External Tasks, and Task Management activities from
UiPath.Persistence.Activities. Uses shared helpers from utils.py (stable
public API), available because plugin_loader adds core scripts/ to sys.path.

Namespace prefixes used:
    upaf: UiPath.Persistence.Activities.FormTask   — CreateFormTask, WaitForFormTaskAndResume, GetFormTasks
    upae: UiPath.Persistence.Activities.ExternalTask — CreateExternalTask, WaitForExternalTaskAndResume
    upat: UiPath.Persistence.Activities.Tasks       — CompleteTask, AssignTasks
"""

from utils import escape_xml_attr as _escape_xml_attr
from utils import escape_vb_expr as _escape_vb_expr
from utils import generate_uuid as _uuid


# ---------------------------------------------------------------------------
# CreateFormTask (Tasks)
# ---------------------------------------------------------------------------

def gen_create_form_task(task_title_expr, task_output_variable, form_layout_json,
                         id_ref, form_data=None,
                         task_catalog_expr="",
                         task_priority="Medium",
                         bucket_name_expr="",
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
        form_layout_json: Raw JSON string for form.io schema. Will be XML-escaped
                          and {} prefixed automatically.
        form_data: Dict of {field_key: (direction, type, variable)}.
                   direction: "In", "Out", "InOut"
                   type: "x:String", "sd:DataTable", "x:Int32", etc.
                   e.g. {"file_url": ("In", "x:String", "strFileUrl"),
                         "in_dt_records": ("InOut", "sd:DataTable", "dt_Records")}
        task_catalog_expr: VB expression for catalog name, or empty
        task_priority: "Low", "Medium", "High", "Critical"
        bucket_name_expr: VB expression for storage bucket, or empty
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
        f'DynamicFormPath="{{x:Null}}" ExternalTag="{{x:Null}}" Labels="{{x:Null}}" '
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
