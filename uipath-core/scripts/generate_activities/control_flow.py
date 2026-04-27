"""Control flow activity generators."""
from ._helpers import _hs, _uuid, _escape_xml_attr, _escape_vb_expr, _normalize_type_arg
from ._xml_utils import _viewstate_block


def gen_if(condition_expression, id_ref, then_content,
           else_content="", display_name="If", indent="    "):
    """Generate If — conditional branching.

    Hallucination patterns prevented:
    - Missing InArgument x:TypeArguments="x:Boolean" wrapper on Condition
    - Condition attribute shorthand works but element syntax is golden-sample pattern
    - Then/Else content MUST be wrapped in Sequence (WF4 XAML: If.Then accepts
      exactly one Activity — multiple children crash with 'Then property already set')

    Args:
        condition_expression: VB.NET boolean expression (no brackets),
                              e.g. 'String.IsNullOrWhiteSpace(strWIID)'
        id_ref: Base IdRef number
        then_content: XAML string for Then branch (auto-wrapped in Sequence)
        else_content: XAML string for Else branch (optional, auto-wrapped)
    """
    dn = _escape_xml_attr(display_name)
    i, i2, i3 = indent, indent+"  ", indent+"    "

    # Always wrap in Sequence — matches Studio pattern, prevents crash
    then_seq_id = f"Sequence_IfThen_{id_ref}"
    then_block = f"""{i3}<Sequence DisplayName="Then" sap2010:WorkflowViewState.IdRef="{then_seq_id}">
{then_content}
{i3}</Sequence>"""

    else_block = ""
    if else_content:
        else_seq_id = f"Sequence_IfElse_{id_ref}"
        else_block = f"""
{i2}<If.Else>
{i3}<Sequence DisplayName="Else" sap2010:WorkflowViewState.IdRef="{else_seq_id}">
{else_content}
{i3}</Sequence>
{i2}</If.Else>"""

    return f"""{i}<If DisplayName="{dn}" {_hs("If")} sap2010:WorkflowViewState.IdRef="If_{id_ref}">
{i2}<If.Condition>
{i3}<InArgument x:TypeArguments="x:Boolean">[{_escape_xml_attr(condition_expression)}]</InArgument>
{i2}</If.Condition>
{i2}<If.Then>
{then_block}
{i2}</If.Then>{else_block}
{i}</If>"""


def gen_if_else_if(conditions, id_ref, else_content="",
                   display_name="Else If", indent="    "):
    """Generate IfElseIfV2 — multi-branch conditional.

    Hallucination patterns prevented:
    - Inventing Conditions property (doesn't exist)
    - Inventing IfElseIfV2Condition type (correct: IfElseIfBlock)
    - Using ElseBody (correct: Else)
    - Missing sc:BindingList wrapper with all required attributes
    - Missing BlockType="ElseIf"

    Requires namespace: xmlns:sc="clr-namespace:System.ComponentModel;assembly=System.ComponentModel.TypeConverter"

    Args:
        conditions: List of (condition_expression, then_content) tuples.
                    First is the primary If, rest become ElseIf branches.
                    e.g. [("intScore < 50", "<LogMessage .../>"),
                          ("intScore >= 50 AndAlso intScore < 80", "<LogMessage .../>")]
        else_content: XAML for final Else branch (optional)
    """
    dn = _escape_xml_attr(display_name)
    i, i2, i3, i4, i5, i6 = (indent, indent+"  ", indent+"    ",
                               indent+"      ", indent+"        ", indent+"          ")

    # Primary condition
    primary_cond = _escape_xml_attr(conditions[0][0])
    primary_then = conditions[0][1]

    # ElseIf blocks
    elseif_blocks = []
    for idx, (cond, content) in enumerate(conditions[1:], 1):
        elseif_blocks.append(f"""{i5}<ui:IfElseIfBlock BlockType="ElseIf" Condition="[{_escape_xml_attr(cond)}]">
{i6}<ui:IfElseIfBlock.Then>
{i6}  <Sequence DisplayName="Body" sap2010:WorkflowViewState.IdRef="Sequence_ElseIf_{id_ref}_{idx}">
{content}
{i6}  </Sequence>
{i6}</ui:IfElseIfBlock.Then>
{i5}</ui:IfElseIfBlock>""")

    elseifs_xml = "\n".join(elseif_blocks)
    elseifs_block = ""
    if elseif_blocks:
        elseifs_block = f"""
{i2}<ui:IfElseIfV2.ElseIfs>
{i3}<sc:BindingList x:TypeArguments="ui:IfElseIfBlock" AllowEdit="True" AllowNew="True" AllowRemove="True" RaiseListChangedEvents="True">
{elseifs_xml}
{i3}</sc:BindingList>
{i2}</ui:IfElseIfV2.ElseIfs>"""

    else_block = ""
    if else_content:
        else_block = f"""
{i2}<ui:IfElseIfV2.Else>
{i3}<Sequence DisplayName="Else" sap2010:WorkflowViewState.IdRef="Sequence_Else_{id_ref}">
{else_content}
{i3}</Sequence>
{i2}</ui:IfElseIfV2.Else>"""

    return f"""{i}<ui:IfElseIfV2 Condition="[{primary_cond}]" DisplayName="{dn}" {_hs("IfElseIfV2")} sap2010:WorkflowViewState.IdRef="IfElseIfV2_{id_ref}">
{i2}<ui:IfElseIfV2.Then>
{i3}<Sequence DisplayName="Then" sap2010:WorkflowViewState.IdRef="Sequence_Then_{id_ref}">
{primary_then}
{i3}</Sequence>
{i2}</ui:IfElseIfV2.Then>{elseifs_block}{else_block}
{i}</ui:IfElseIfV2>"""


def gen_switch(expression_variable, id_ref, cases, default_content="",
               default_sequence_idref="", switch_type="x:String",
               display_name="Switch", indent="    "):
    """Generate Switch — multi-branch conditional.

    Hallucination patterns prevented:
    - Missing x:TypeArguments (required, unlike If)
    - Wrong case syntax (must be x:Key attribute on body element)
    - Missing backtick in IdRef (Switch`1_N)
    - Wrong Expression format

    Args:
        expression_variable: VB expression to switch on (no brackets),
                             e.g. 'strStatus', 'row("Type").ToString'
        id_ref: Base IdRef number
        cases: Dict of {case_label: case_content_xml},
               e.g. {"Completed": "<Assign .../>", "Rejected": "<Sequence>...</Sequence>"}
               case_content must be a single activity (wrap in Sequence for multiple)
        default_content: XAML for default case (optional)
        default_sequence_idref: IdRef for default Sequence
        switch_type: Type argument — "x:String" (most common), "x:Int32", etc.
    """
    dn = _escape_xml_attr(display_name)
    i, i2, i3 = indent, indent+"  ", indent+"    "

    # Default block
    default_block = ""
    if default_content:
        seq_id = default_sequence_idref or f"Sequence_Default_{id_ref}"
        default_block = f"""{i2}<Switch.Default>
{i3}<Sequence DisplayName="Default" sap2010:WorkflowViewState.IdRef="{seq_id}">
{i3}  {_viewstate_block(seq_id)}
{default_content}
{i3}</Sequence>
{i2}</Switch.Default>
"""

    # Case blocks — each is a direct child with x:Key
    case_blocks = []
    for label, content in cases.items():
        case_blocks.append(f"""{i2}<Sequence x:Key="{_escape_xml_attr(label)}" DisplayName="Body" sap2010:WorkflowViewState.IdRef="Sequence_Case_{id_ref}_{_escape_xml_attr(label).replace(' ', '_')}">
{content}
{i2}</Sequence>""")

    cases_xml = "\n".join(case_blocks)

    return f"""{i}<Switch x:TypeArguments="{switch_type}" DisplayName="{dn}" Expression="[{_escape_xml_attr(expression_variable)}]" {_hs("Switch")} sap2010:WorkflowViewState.IdRef="Switch`1_{id_ref}">
{default_block}{cases_xml}
{i}</Switch>"""



def gen_foreach(collection_variable, id_ref, body_content, body_sequence_idref,
                item_variable="currentItem", item_type="x:String",
                display_name="For Each item", indent="    "):
    """Generate ForEach — iterate over a generic collection.

    Hallucination patterns prevented:
    - Using default ns <ForEach> instead of <ui:ForEach> (wrong activity — lint catches)
    - Missing ActivityAction/DelegateInArgument wrapper
    - Missing CurrentIndex="{x:Null}"
    - Wrong TypeArguments

    Args:
        collection_variable: Variable name (no brackets), e.g. "listItems"
        item_variable: Iterator variable name (default "currentItem")
        item_type: XAML type, e.g. "x:String", "x:Int32", "njl:JToken".
                   Short forms (e.g. "String") are normalized to prefixed form (e.g. "x:String").
    """
    item_type = _normalize_type_arg(item_type)
    dn = _escape_xml_attr(display_name)
    i, i2, i3, i4, i5, i6 = (indent, indent+"  ", indent+"    ",
                               indent+"      ", indent+"        ", indent+"          ")

    return f"""{i}<ui:ForEach x:TypeArguments="{item_type}" CurrentIndex="{{x:Null}}" DisplayName="{dn}" {_hs("ForEach")} Values="[{_escape_vb_expr(collection_variable)}]" sap2010:WorkflowViewState.IdRef="ForEach_{id_ref}">
{i2}<ui:ForEach.Body>
{i3}<ActivityAction x:TypeArguments="{item_type}">
{i4}<ActivityAction.Argument>
{i5}<DelegateInArgument x:TypeArguments="{item_type}" Name="{item_variable}" />
{i4}</ActivityAction.Argument>
{i4}<Sequence DisplayName="Body" sap2010:WorkflowViewState.IdRef="{body_sequence_idref}">
{i5}{_viewstate_block(body_sequence_idref)}
{body_content}
{i4}</Sequence>
{i3}</ActivityAction>
{i2}</ui:ForEach.Body>
{i}</ui:ForEach>"""


def gen_foreach_row(datatable_variable, id_ref, body_content,
                    body_sequence_idref, row_variable="row",
                    display_name="For Each Row", indent="    "):
    """Generate ForEachRow in DataTable.

    Hallucination patterns prevented:
    - Missing ActivityAction wrapper with x:TypeArguments="sd:DataRow"
    - Missing DelegateInArgument declaration
    - Wrong TypeArguments (x:Object instead of sd:DataRow)
    - Using <ForEach> instead of <ui:ForEach> (wrong activity entirely — lint catches this)

    Args:
        datatable_variable: Variable name (no brackets), e.g. "dt_WorkItems"
        id_ref: Base IdRef number
        body_content: XAML string for loop body (indented to body level)
        body_sequence_idref: IdRef for inner Sequence
        row_variable: Iterator variable name (default "row")
    """
    dn = _escape_xml_attr(display_name)
    i, i2, i3, i4, i5, i6 = (indent, indent+"  ", indent+"    ",
                               indent+"      ", indent+"        ", indent+"          ")

    return f"""{i}<ui:ForEachRow DisplayName="{dn}" DataTable="[{_escape_vb_expr(datatable_variable)}]" {_hs("ForEachRow")} sap2010:WorkflowViewState.IdRef="ForEachRow_{id_ref}">
{i2}<ui:ForEachRow.Body>
{i3}<ActivityAction x:TypeArguments="sd:DataRow">
{i4}<ActivityAction.Argument>
{i5}<DelegateInArgument x:TypeArguments="sd:DataRow" Name="{row_variable}" />
{i4}</ActivityAction.Argument>
{i4}<Sequence DisplayName="Body" sap2010:WorkflowViewState.IdRef="{body_sequence_idref}">
{i5}{_viewstate_block(body_sequence_idref)}
{body_content}
{i4}</Sequence>
{i3}</ActivityAction>
{i2}</ui:ForEachRow.Body>
{i}</ui:ForEachRow>"""


def gen_foreach_file(folder_variable, id_ref, body_content, body_sequence_idref,
                     include_subdirs=True, order_by="NameAscFirst",
                     display_name="For Each File in Folder", indent="    "):
    """Generate ForEachFileX — iterate files in a directory.

    Hallucination patterns prevented:
    - Missing dual DelegateInArguments (FileInfo + Int32)
    - Wrong TypeArguments on ActivityAction (must be "si:FileInfo, x:Int32")
    - Using Argument1/Argument2 instead of Argument
    - Missing si: namespace requirement
    - Adding ContinueOnError (doesn't exist on X-suffix activities)

    Requires namespace: xmlns:si="clr-namespace:System.IO;assembly=System.Private.CoreLib"

    Args:
        folder_variable: VB expression for folder path (no brackets)
        order_by: NameAscFirst, NameDescFirst, DateAscFirst, DateDescFirst,
                  SizeAscFirst, SizeDescFirst
    """
    if not (order_by in ("NameAscFirst", "NameDescFirst", "DateAscFirst", "DateDescFirst", "SizeAscFirst", "SizeDescFirst")):
        raise ValueError(f"Invalid OrderBy: {order_by}")

    dn = _escape_xml_attr(display_name)
    i, i2, i3, i4, i5, i6 = (indent, indent+"  ", indent+"    ",
                               indent+"      ", indent+"        ", indent+"          ")

    return f"""{i}<ui:ForEachFileX DisplayName="{dn}" Folder="[{_escape_vb_expr(folder_variable)}]" {_hs("ForEachFileX")} sap2010:WorkflowViewState.IdRef="ForEachFileX_{id_ref}" IncludeSubDirectories="{include_subdirs}" OrderBy="{order_by}">
{i2}<ui:ForEachFileX.Body>
{i3}<ActivityAction x:TypeArguments="si:FileInfo, x:Int32">
{i4}<ActivityAction.Argument1>
{i5}<DelegateInArgument x:TypeArguments="si:FileInfo" Name="CurrentFile" />
{i4}</ActivityAction.Argument1>
{i4}<ActivityAction.Argument2>
{i5}<DelegateInArgument x:TypeArguments="x:Int32" Name="CurrentIndex" />
{i4}</ActivityAction.Argument2>
{i4}<Sequence DisplayName="Do" sap2010:WorkflowViewState.IdRef="{body_sequence_idref}">
{i5}{_viewstate_block(body_sequence_idref)}
{body_content}
{i4}</Sequence>
{i3}</ActivityAction>
{i2}</ui:ForEachFileX.Body>
{i}</ui:ForEachFileX>"""


def gen_while(condition_expression, id_ref, body_content, body_sequence_idref,
              display_name="While", indent="    "):
    """Generate While loop.

    Args:
        condition_expression: VB.NET boolean expression (no brackets),
                              e.g. 'intCounter < maxRetries'
    """
    dn = _escape_xml_attr(display_name)
    i, i2, i3 = indent, indent+"  ", indent+"    "

    return f"""{i}<While Condition="[{_escape_xml_attr(condition_expression)}]" DisplayName="{dn}" {_hs("While")} sap2010:WorkflowViewState.IdRef="While_{id_ref}">
{i2}<Sequence DisplayName="Body" sap2010:WorkflowViewState.IdRef="{body_sequence_idref}">
{i3}{_viewstate_block(body_sequence_idref)}
{body_content}
{i2}</Sequence>
{i}</While>"""


def gen_do_while(condition_expression, id_ref, body_content, body_sequence_idref,
                 display_name="Do While", indent="    "):
    """Generate DoWhile loop — executes body at least once.

    Args:
        condition_expression: VB.NET boolean (no brackets), evaluated after each iteration
    """
    dn = _escape_xml_attr(display_name)
    i, i2, i3 = indent, indent+"  ", indent+"    "

    return f"""{i}<DoWhile Condition="[{_escape_xml_attr(condition_expression)}]" DisplayName="{dn}" {_hs("DoWhile")} sap2010:WorkflowViewState.IdRef="DoWhile_{id_ref}">
{i2}<Sequence DisplayName="Body" sap2010:WorkflowViewState.IdRef="{body_sequence_idref}">
{i3}{_viewstate_block(body_sequence_idref)}
{body_content}
{i2}</Sequence>
{i}</DoWhile>"""


def gen_flowchart(steps, decisions, start_ref_id, id_ref,
                  variables=None, display_name="Flowchart", indent="    "):
    """Generate Flowchart — graph-based workflow alternative to Sequence.

    Hallucination patterns prevented:
    - Missing av: namespace for Point/Size/PointCollection
    - Missing Flowchart.StartNode with x:Reference
    - Missing x:Reference list at end of Flowchart
    - Wrong __ReferenceID naming convention
    - Missing ShapeLocation/ShapeSize ViewState per node
    - Using Expression instead of VisualBasicValue for FlowDecision conditions

    Requires namespace: xmlns:av="http://schemas.microsoft.com/winfx/2006/xaml/presentation"

    Args:
        steps: List of dicts defining FlowSteps:
               [{"ref_id": "__ReferenceID0", "content": "<Sequence>...</Sequence>",
                 "next_ref": "__ReferenceID1",  # or None for terminal
                 "location": "245,135", "size": "110,70",
                 "connector": "300,205 300,250"}]
        decisions: List of dicts defining FlowDecisions:
                   [{"ref_id": "__ReferenceID1", "condition": "boolSuccess",
                     "true_ref": "__ReferenceID2", "false_ref": "__ReferenceID3",
                     "display_name": "Success?",
                     "location": "270,250", "size": "60,60",
                     "true_connector": "270,280 175,280",
                     "false_connector": "330,280 405,280"}]
        start_ref_id: Reference ID of the starting node (e.g. "__ReferenceID0")
        variables: Optional list of (name, type) tuples for flowchart-scoped variables
    """
    dn = _escape_xml_attr(display_name)
    i, i2, i3, i4, i5, i6 = (indent, indent+"  ", indent+"    ",
                               indent+"      ", indent+"        ", indent+"          ")

    # Variables
    vars_block = ""
    if variables:
        var_lines = []
        for vname, vtype in variables:
            vtype = _normalize_type_arg(vtype)
            var_lines.append(f'{i3}<Variable x:TypeArguments="{vtype}" Name="{vname}" />')
        vars_xml = "\n".join(var_lines)
        vars_block = f"""{i2}<Flowchart.Variables>
{vars_xml}
{i2}</Flowchart.Variables>
"""

    # Flowchart ViewState
    fc_viewstate = f"""{i2}<sap:WorkflowViewStateService.ViewState>
{i3}<scg:Dictionary x:TypeArguments="x:String, x:Object">
{i4}<x:Boolean x:Key="IsExpanded">True</x:Boolean>
{i4}<av:Point x:Key="ShapeLocation">275,35</av:Point>
{i4}<av:Size x:Key="ShapeSize">50,50</av:Size>
{i4}<av:PointCollection x:Key="ConnectorLocation">300,85 300,135</av:PointCollection>
{i3}</scg:Dictionary>
{i2}</sap:WorkflowViewStateService.ViewState>"""

    # StartNode
    start_block = f"""{i2}<Flowchart.StartNode>
{i3}<x:Reference>{start_ref_id}</x:Reference>
{i2}</Flowchart.StartNode>"""

    # Build FlowDecision elements (keyed by ref_id for lookup)
    decision_map = {}
    for dec in decisions:
        dec_vs = f"""{i5}<sap:WorkflowViewStateService.ViewState>
{i6}<scg:Dictionary x:TypeArguments="x:String, x:Object">
{i6}  <av:Point x:Key="ShapeLocation">{dec["location"]}</av:Point>
{i6}  <av:Size x:Key="ShapeSize">{dec["size"]}</av:Size>
{i6}  <av:PointCollection x:Key="TrueConnector">{dec.get("true_connector", "")}</av:PointCollection>
{i6}  <av:PointCollection x:Key="FalseConnector">{dec.get("false_connector", "")}</av:PointCollection>
{i6}</scg:Dictionary>
{i5}</sap:WorkflowViewStateService.ViewState>"""

        true_branch = f'{i5}<FlowDecision.True>\n{i6}<x:Reference>{dec["true_ref"]}</x:Reference>\n{i5}</FlowDecision.True>' if dec.get("true_ref") else ""
        false_branch = f'{i5}<FlowDecision.False>\n{i6}<x:Reference>{dec["false_ref"]}</x:Reference>\n{i5}</FlowDecision.False>' if dec.get("false_ref") else ""

        decision_map[dec["ref_id"]] = f"""{i4}<FlowDecision x:Name="{dec["ref_id"]}" DisplayName="{_escape_xml_attr(dec.get("display_name", "Flow Decision"))}" {_hs("FlowDecision")} sap2010:WorkflowViewState.IdRef="FlowDecision_{id_ref}_{dec["ref_id"]}">
{i5}<FlowDecision.Condition>
{i6}<VisualBasicValue x:TypeArguments="x:Boolean" ExpressionText="{_escape_xml_attr(dec["condition"])}" />
{i5}</FlowDecision.Condition>
{dec_vs}
{true_branch}
{false_branch}
{i4}</FlowDecision>"""

    # Build FlowStep elements
    all_refs = set()
    step_blocks = []
    for step in steps:
        ref = step["ref_id"]
        all_refs.add(ref)

        step_vs = f"""{i4}<sap:WorkflowViewStateService.ViewState>
{i5}<scg:Dictionary x:TypeArguments="x:String, x:Object">
{i5}  <av:Point x:Key="ShapeLocation">{step["location"]}</av:Point>
{i5}  <av:Size x:Key="ShapeSize">{step["size"]}</av:Size>
{i5}  <av:PointCollection x:Key="ConnectorLocation">{step.get("connector", "")}</av:PointCollection>
{i5}</scg:Dictionary>
{i4}</sap:WorkflowViewStateService.ViewState>"""

        # Next can be a FlowStep ref, a FlowDecision inline, or None
        next_block = ""
        next_ref = step.get("next_ref")
        if next_ref:
            if next_ref in decision_map:
                next_block = f"""{i3}<FlowStep.Next>
{decision_map[next_ref]}
{i3}</FlowStep.Next>"""
                all_refs.add(next_ref)
                # Also track true/false refs
                for dec in decisions:
                    if dec["ref_id"] == next_ref:
                        if dec.get("true_ref"): all_refs.add(dec["true_ref"])
                        if dec.get("false_ref"): all_refs.add(dec["false_ref"])
            else:
                next_block = f"""{i3}<FlowStep.Next>
{i4}<x:Reference>{next_ref}</x:Reference>
{i3}</FlowStep.Next>"""
                all_refs.add(next_ref)

        step_blocks.append(f"""{i2}<FlowStep x:Name="{ref}">
{step_vs}
{step["content"]}
{next_block}
{i2}</FlowStep>""")

    steps_xml = "\n".join(step_blocks)

    # Trailing refs make nested nodes (FlowDecisions inlined into FlowStep.Next)
    # discoverable as Flowchart children. Top-level FlowSteps are already direct
    # children via their <FlowStep x:Name=> declaration — listing them again
    # here would make WPF add the same Visual twice and crash the FlowchartDesigner
    # with "Specified Visual is already a child of another Visual".
    top_level_step_refs = {step["ref_id"] for step in steps}
    ref_lines = []
    for ref in sorted(all_refs):
        if ref in top_level_step_refs:
            continue
        ref_lines.append(f'{i2}<x:Reference>{ref}</x:Reference>')
    refs_xml = "\n".join(ref_lines)

    return f"""{i}<Flowchart DisplayName="{dn}" {_hs("Flowchart")} sap2010:WorkflowViewState.IdRef="Flowchart_{id_ref}">
{vars_block}{fc_viewstate}
{start_block}
{steps_xml}
{refs_xml}
{i}</Flowchart>"""


def gen_state_machine(states: list[dict], initial_state_ref: str,
                      id_ref: str = "StateMachine_1",
                      display_name: str = "State Machine",
                      indent: str = "    ") -> str:
    """Generate a StateMachine activity.

    Args:
        states: list of dicts with keys:
            - ref: str — x:Reference for this state
            - display_name: str — DisplayName
            - is_final: bool — if True, this is a FinalState
            - entry_xml: str — XAML for Entry action (optional)
            - transitions: list of dicts with keys:
                - to_ref: str — x:Reference of target state
                - display_name: str — transition DisplayName
                - condition: str — VB expression (optional)
                - action_xml: str — XAML for transition action (optional)
        initial_state_ref: x:Reference of the initial state
        id_ref: IdRef for ViewState
        display_name: DisplayName
        indent: base indentation

    Returns: XAML string for the StateMachine activity
    """
    i2 = indent + "  "
    i3 = i2 + "  "
    i4 = i3 + "  "
    i5 = i4 + "  "

    lines = [
        f'{indent}<StateMachine DisplayName="{_escape_xml_attr(display_name)}" '
        f'{_hs("StateMachine")} sap2010:WorkflowViewState.IdRef="{id_ref}">'
    ]

    # InitialState reference
    lines.append(f'{i2}<StateMachine.InitialState>')
    lines.append(f'{i3}<x:Reference>{initial_state_ref}</x:Reference>')
    lines.append(f'{i2}</StateMachine.InitialState>')

    for state in states:
        ref = state["ref"]
        sdn = _escape_xml_attr(state["display_name"])
        is_final = state.get("is_final", False)

        if is_final:
            lines.append(
                f'{i2}<FinalState x:Name="{ref}" DisplayName="{sdn}" '
                f'{_hs("FinalState")}>'
            )
            entry = state.get("entry_xml", "")
            if entry:
                lines.append(f'{i3}<FinalState.Entry>')
                lines.append(entry)
                lines.append(f'{i3}</FinalState.Entry>')
            lines.append(f'{i2}</FinalState>')
        else:
            lines.append(
                f'{i2}<State x:Name="{ref}" DisplayName="{sdn}" '
                f'{_hs("State")}>'
            )
            entry = state.get("entry_xml", "")
            if entry:
                lines.append(f'{i3}<State.Entry>')
                lines.append(entry)
                lines.append(f'{i3}</State.Entry>')

            transitions = state.get("transitions", [])
            if transitions:
                lines.append(f'{i3}<State.Transitions>')
                for tr in transitions:
                    cond = ""
                    if tr.get("condition"):
                        cond = f' Condition="[{_escape_vb_expr(tr["condition"])}]"'
                    lines.append(
                        f'{i4}<Transition DisplayName="{_escape_xml_attr(tr["display_name"])}"{cond} '
                        f'{_hs("Transition")}>'
                    )
                    lines.append(f'{i5}<Transition.To>')
                    lines.append(f'{i5}  <x:Reference>{tr["to_ref"]}</x:Reference>')
                    lines.append(f'{i5}</Transition.To>')
                    if tr.get("action_xml"):
                        lines.append(f'{i5}<Transition.Action>')
                        lines.append(tr["action_xml"])
                        lines.append(f'{i5}</Transition.Action>')
                    lines.append(f'{i4}</Transition>')
                lines.append(f'{i3}</State.Transitions>')

            lines.append(f'{i2}</State>')

    lines.append(f'{indent}</StateMachine>')
    return "\n".join(lines)


def gen_parallel(branches_xml: list[str], completion_condition: str = "",
                 id_ref: str = "Parallel_1", display_name: str = "Parallel",
                 indent: str = "    ") -> str:
    """Generate a Parallel activity with N branches.

    Args:
        branches_xml: list of pre-built XAML strings for each branch body
        completion_condition: optional VB expression; when True, remaining branches cancel
        id_ref: IdRef for ViewState
        display_name: DisplayName
        indent: base indentation

    Returns: XAML string for the Parallel activity
    """
    i2 = indent + "  "
    cc = ""
    if completion_condition:
        cc = f' CompletionCondition="[{_escape_vb_expr(completion_condition)}]"'

    lines = [
        f'{indent}<Parallel DisplayName="{_escape_xml_attr(display_name)}"{cc} '
        f'{_hs("Parallel")} sap2010:WorkflowViewState.IdRef="{id_ref}">'
    ]
    for branch in branches_xml:
        lines.append(branch)
    lines.append(f'{indent}</Parallel>')
    return "\n".join(lines)


def gen_parallel_foreach(type_argument: str, values_expression: str,
                         body_xml: str, argument_name: str = "item",
                         id_ref: str = "ParallelForEach_1",
                         display_name: str = "Parallel For Each",
                         indent: str = "    ") -> str:
    """Generate a ParallelForEach<T> activity.

    Args:
        type_argument: CLR type for iteration, e.g. 'x:String', 'sd:DataRow'
        values_expression: VB expression for the collection, e.g. 'dt_Input.AsEnumerable()'
        body_xml: pre-built XAML for the loop body
        argument_name: name of the DelegateInArgument (default 'item')
        id_ref: IdRef for ViewState
        display_name: DisplayName
        indent: base indentation

    Returns: XAML string for the ParallelForEach activity
    """
    i2 = indent + "  "
    i3 = i2 + "  "
    i4 = i3 + "  "
    return "\n".join([
        f'{indent}<ParallelForEach x:TypeArguments="{type_argument}" '
        f'DisplayName="{_escape_xml_attr(display_name)}" Values="[{_escape_vb_expr(values_expression)}]" '
        f'{_hs("ParallelForEach")} sap2010:WorkflowViewState.IdRef="{id_ref}">',
        f'{i2}<ParallelForEach.Body>',
        f'{i3}<ActivityAction x:TypeArguments="{type_argument}">',
        f'{i4}<ActivityAction.Argument>',
        f'{i4}  <DelegateInArgument x:TypeArguments="{type_argument}" Name="{argument_name}" />',
        f'{i4}</ActivityAction.Argument>',
        body_xml,
        f'{i3}</ActivityAction>',
        f'{i2}</ParallelForEach.Body>',
        f'{indent}</ParallelForEach>',
    ])
