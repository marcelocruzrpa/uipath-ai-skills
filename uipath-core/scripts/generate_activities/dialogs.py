"""Dialog activity generators."""
from ._helpers import _hs, _uuid, _escape_xml_attr, _escape_vb_expr
from ._xml_utils import _viewstate_block


def gen_input_dialog(label, title, result_variable, id_ref,
                     options_string="", is_password=False,
                     display_name="Input Dialog", indent="    "):
    """Generate InputDialog — text input or dropdown.

    Hallucination patterns prevented:
    - Using Options with VB array expression (lint catches — must use OptionsString)
    - Using Result as inline attribute (must be element syntax with OutArgument)
    - Generating VB array for Options (stays {x:Null})

    Args:
        label: Prompt text
        title: Dialog window title
        result_variable: Output String variable (no brackets)
        options_string: Semicolon-separated options for dropdown, or "" for text input
    """
    dn = _escape_xml_attr(display_name)
    lbl = _escape_xml_attr(label)
    ttl = _escape_xml_attr(title)
    i, i2, i3 = indent, indent+"  ", indent+"    "

    opts_attr = f'OptionsString="{_escape_xml_attr(options_string)}"' if options_string else 'OptionsString="{x:Null}"'

    return f"""{i}<ui:InputDialog Options="{{x:Null}}" {opts_attr} DisplayName="{dn}" sap2010:WorkflowViewState.IdRef="InputDialog_{id_ref}" IsPassword="{is_password}" Label="{lbl}" Title="{ttl}" TopMost="False">
{i2}<ui:InputDialog.Result>
{i3}<OutArgument x:TypeArguments="x:String">[{result_variable}]</OutArgument>
{i2}</ui:InputDialog.Result>
{i}</ui:InputDialog>"""


# ---------------------------------------------------------------------------
# MessageBox
# ---------------------------------------------------------------------------

def gen_message_box(text_variable, id_ref, display_name="Message Box", indent="    "):
    """Generate MessageBox."""
    dn = _escape_xml_attr(display_name)
    i = indent
    return (
        f'{i}<ui:MessageBox Caption="{{x:Null}}" ChosenButton="{{x:Null}}" '
        f'AutoCloseAfter="00:00:00" DisplayName="{dn}" '
        f'sap2010:WorkflowViewState.IdRef="MessageBox_{id_ref}" '
        f'Text="[{_escape_vb_expr(text_variable)}]" />'
    )
