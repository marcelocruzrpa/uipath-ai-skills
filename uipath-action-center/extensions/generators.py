"""Action Center XAML generators — CreateFormTask and WaitForFormTaskAndResume.

Moved from uipath-core generate_activities.py into the uipath-action-center
skill extension. Uses shared helpers from utils.py (stable public API),
available because plugin_loader adds core scripts/ to sys.path.
"""

from utils import escape_xml_attr as _escape_xml_attr
from utils import escape_vb_expr as _escape_vb_expr
from utils import generate_uuid as _uuid


# ---------------------------------------------------------------------------
# CreateFormTask (Action Center)
# ---------------------------------------------------------------------------

def gen_create_form_task(task_title_expr, task_output_variable, form_layout_json,
                         id_ref, form_data=None,
                         task_catalog_expr="",
                         task_priority="Medium",
                         bucket_name_expr="",
                         display_name="Create Form Task", indent="    "):
    """Generate CreateFormTask — Action Center human-in-the-loop form.

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
# WaitForFormTaskAndResume (Action Center)
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
