"""Logging and miscellaneous activity generators."""
from ._helpers import _hs, _uuid, _escape_xml_attr, _escape_vb_expr
from ._xml_utils import _viewstate_block


def gen_logmessage(message, id_ref, display_name="", level="Info", indent="    "):
    if not (level in ("Info", "Warn", "Error", "Trace")):
        raise ValueError(f"Invalid level: {level}. Must be one of: Info, Warn, Error, Trace")
    if not display_name:
        clean = message.replace("&quot;", "").replace('"', "").replace("[START]", "Start").replace("[END]", "End")
        display_name = f"Log Message {clean[:40]}"
    hs = _hs("LogMessage")
    dn = _escape_xml_attr(display_name)
    # Message is a VB expression inside [...] — quotes must be &quot; in XML
    esc_msg = _escape_vb_expr(message)
    i = indent
    return f'{i}<ui:LogMessage DisplayName="{dn}" {hs} sap2010:WorkflowViewState.IdRef="{id_ref}" Level="{level}" Message="[{esc_msg}]" />'


def gen_comment(text, id_ref, display_name="Comment", indent="    "):
    """Generate Comment annotation."""
    dn = _escape_xml_attr(display_name)
    i = indent
    return f'{i}<ui:Comment DisplayName="{dn}" Text="{_escape_xml_attr(text)}" sap2010:WorkflowViewState.IdRef="Comment_{id_ref}" />'


# ---------------------------------------------------------------------------
# CommentOut
# ---------------------------------------------------------------------------

def gen_comment_out(body_content, body_sequence_idref, id_ref,
                    display_name="Comment Out", indent="    "):
    """Generate CommentOut — wraps activities to disable without deleting."""
    dn = _escape_xml_attr(display_name)
    i, i2, i3, i4 = indent, indent+"  ", indent+"    ", indent+"      "

    return f"""{i}<ui:CommentOut DisplayName="{dn}" sap2010:WorkflowViewState.IdRef="CommentOut_{id_ref}">
{i2}<ui:CommentOut.Body>
{i3}<Sequence DisplayName="Ignored Activities" sap2010:WorkflowViewState.IdRef="{body_sequence_idref}">
{i4}{_viewstate_block(body_sequence_idref)}
{body_content}
{i3}</Sequence>
{i2}</ui:CommentOut.Body>
{i}</ui:CommentOut>"""


def gen_break(id_ref, display_name="Break", indent="    "):
    """Generate ui:Break — exits the innermost ForEach/ForEachRow/While/DoWhile loop."""
    dn = _escape_xml_attr(display_name)
    return (
        f'{indent}<ui:Break DisplayName="{dn}" '
        f'sap:VirtualizedContainerService.HintSize="434,48" '
        f'sap2010:WorkflowViewState.IdRef="{id_ref}" />'
    )


def gen_continue(id_ref, display_name="Continue", indent="    "):
    """Generate ui:Continue — skips to next iteration of the innermost loop."""
    dn = _escape_xml_attr(display_name)
    return (
        f'{indent}<ui:Continue DisplayName="{dn}" '
        f'sap:VirtualizedContainerService.HintSize="434,48" '
        f'sap2010:WorkflowViewState.IdRef="{id_ref}" />'
    )


# ---------------------------------------------------------------------------
# KillProcess
# ---------------------------------------------------------------------------

def gen_kill_process(process_name, id_ref, display_name="", indent="    "):
    """Generate ui:KillProcess — terminates a process by name.

    Args:
        process_name: Process name WITHOUT extension (e.g., "iexplore", "excel").
                      Use VB expression in brackets for variable: [strProcessName].
    """
    dn = _escape_xml_attr(display_name or f"Kill Process ({process_name})")
    pn = _escape_xml_attr(process_name)
    return f"""{indent}<ui:KillProcess DisplayName="{dn}" ProcessName="{pn}" {_hs("KillProcess")} sap2010:WorkflowViewState.IdRef="{id_ref}" />"""


# ---------------------------------------------------------------------------
# TerminateWorkflow
# ---------------------------------------------------------------------------

def gen_terminate_workflow(reason_expression, id_ref, display_name="Terminate Workflow",
                          indent="    "):
    """Generate TerminateWorkflow — terminates the workflow with exception.

    Args:
        reason_expression: VB expression for the exception, e.g.:
            'New Exception(&quot;Fatal error&quot;)'
    """
    return f"""{indent}<TerminateWorkflow DisplayName="{_escape_xml_attr(display_name)}" {_hs("TerminateWorkflow")} sap2010:WorkflowViewState.IdRef="{id_ref}">
{indent}  {_viewstate_block(id_ref)}
{indent}  <TerminateWorkflow.Exception>
{indent}    <InArgument x:TypeArguments="s:Exception">[{reason_expression}]</InArgument>
{indent}  </TerminateWorkflow.Exception>
{indent}</TerminateWorkflow>"""


def gen_should_stop(result_variable, id_ref, display_name="Should Stop", indent="    "):
    """Generate ui:ShouldStop — checks if Orchestrator requested the robot to stop.

    Args:
        result_variable: Boolean variable to store result, e.g. "boolShouldStop".
    """
    return (
        f'{indent}<ui:ShouldStop DisplayName="{_escape_xml_attr(display_name)}" '
        f'Result="[{_escape_vb_expr(result_variable)}]" {_hs("ShouldStop")} '
        f'sap2010:WorkflowViewState.IdRef="{id_ref}" />'
    )


# ---------------------------------------------------------------------------
# AddLogFields / RemoveLogFields
# ---------------------------------------------------------------------------

def gen_add_log_fields(fields, id_ref, display_name="Add Log Fields", indent="    "):
    """Generate ui:AddLogFields — adds custom fields to all subsequent log messages.

    Args:
        fields: dict of field_name -> VB expression value pairs, e.g.:
            {"BusinessProcessName": '[in_Config("logF_BusinessProcessName").ToString]',
             "TransactionID": '[strTransactionID]'}
    """
    i2 = indent + "  "
    i3 = indent + "    "
    field_lines = []
    for fname, fvalue in fields.items():
        field_lines.append(
            f'{i3}<ui:AddLogField FieldName="{fname}" '
            f'FieldValue="{_escape_xml_attr(fvalue)}" />'
        )
    fields_xml = "\n".join(field_lines)
    return f"""{indent}<ui:AddLogFields DisplayName="{_escape_xml_attr(display_name)}" {_hs("AddLogFields")} sap2010:WorkflowViewState.IdRef="{id_ref}">
{i2}{_viewstate_block(id_ref)}
{i2}<ui:AddLogFields.LogFields>
{i3}<scg:List x:TypeArguments="ui:AddLogField" Capacity="4">
{fields_xml}
{i3}</scg:List>
{i2}</ui:AddLogFields.LogFields>
{indent}</ui:AddLogFields>"""


def gen_remove_log_fields(field_names, id_ref, display_name="Remove Log Fields", indent="    "):
    """Generate ui:RemoveLogFields — removes custom log fields.

    Args:
        field_names: list of field name strings to remove.
    """
    i2 = indent + "  "
    i3 = indent + "    "
    field_lines = []
    for fname in field_names:
        field_lines.append(f'{i3}<x:String>{fname}</x:String>')
    fields_xml = "\n".join(field_lines)
    return f"""{indent}<ui:RemoveLogFields DisplayName="{_escape_xml_attr(display_name)}" {_hs("RemoveLogFields")} sap2010:WorkflowViewState.IdRef="{id_ref}">
{i2}{_viewstate_block(id_ref)}
{i2}<ui:RemoveLogFields.LogFields>
{i3}<scg:List x:TypeArguments="x:String" Capacity="4">
{fields_xml}
{i3}</scg:List>
{i2}</ui:RemoveLogFields.LogFields>
{indent}</ui:RemoveLogFields>"""


# ---------------------------------------------------------------------------
# TakeScreenshot + SaveImage (paired pattern)
# ---------------------------------------------------------------------------

def gen_take_screenshot_and_save(screenshot_variable, save_path_variable, id_ref,
                                 display_name_screenshot="Take Screenshot",
                                 display_name_save="Save Screenshot",
                                 indent="    "):
    """Generate TakeScreenshot + SaveImage pair.

    Hallucination patterns prevented:
    - Using InvokeCode with CopyFromScreen (wrong approach)
    - Missing Target element structure
    - Wrong variable type (must be ui:Image)

    Requires variable: <Variable x:TypeArguments="ui:Image" Name="{screenshot_variable}" />
    """
    dn1 = _escape_xml_attr(display_name_screenshot)
    dn2 = _escape_xml_attr(display_name_save)
    i, i2, i3 = indent, indent+"  ", indent+"    "

    take = f"""{i}<ui:TakeScreenshot WaitBefore="{{x:Null}}" DisplayName="{dn1}" Screenshot="[{_escape_vb_expr(screenshot_variable)}]" sap2010:WorkflowViewState.IdRef="TakeScreenshot_{id_ref}">
{i2}<ui:TakeScreenshot.Target>
{i3}<ui:Target ClippingRegion="{{x:Null}}" Element="{{x:Null}}" Selector="{{x:Null}}" WaitForReady="INTERACTIVE" />
{i2}</ui:TakeScreenshot.Target>
{i}</ui:TakeScreenshot>"""

    save = (
        f'{i}<ui:SaveImage DisplayName="{dn2}" '
        f'FileName="[{_escape_vb_expr(save_path_variable)}]" Image="[{_escape_vb_expr(screenshot_variable)}]" '
        f'sap2010:WorkflowViewState.IdRef="SaveImage_{id_ref}" />'
    )

    return take + "\n" + save
