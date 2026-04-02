"""SAP WinGUI XAML generators — deterministic XAML for uix:NSAP* activities.

Moved from uipath-sap-wingui/scripts/generate_sap_activities.py into the
extensions plugin system. Uses SAP-specific helpers locally (not core utils)
because SAP selectors require distinct escaping rules (single-quote preservation).

Activities covered:
  1. NSAPLogon             - SAP GUI scope/container (open + attach)
  2. NSAPLogin             - SAP authentication
  3. NSAPCallTransaction   - Transaction navigation (/n, /o prefix)
  4. NSAPClickToolbarButton - System toolbar buttons (Enter, Save, Back, etc.)
  5. NSAPSelectMenuItem     - Menu path selection
  6. NSAPReadStatusbar      - Status bar read (message text, type, data)
  7. NSAPTableCellScope     - Table cell scope for row/column targeting

Convenience composites:
  8. gen_sap_status_bar_check - ReadStatusbar + If-error condition
  9. gen_sap_type_into_cell   - TableCellScope wrapping NTypeInto
"""

import html

from utils import generate_uuid as _guid
from utils import escape_xml_attr as _escape


# ═══════════════════════════════════════════════════════════════════════════
# SHARED UTILITIES
# ═══════════════════════════════════════════════════════════════════════════


def _escape_selector(selector):
    """XML-escape a selector for use inside FullSelectorArgument attributes.
    Escapes < > & " — single quotes are preserved as-is per UiPath convention.
    Double quotes must be escaped because the result is placed inside a
    double-quoted XML attribute (FullSelectorArgument="...")."""
    if selector is None:
        return ""
    return html.escape(str(selector), quote=True)


def _hint(w=452, h=200):
    """Generate VirtualizedContainerService.HintSize attribute."""
    return f'sap:VirtualizedContainerService.HintSize="{w},{h}"'


def indent_xml(xml_str, level=0, spaces=2):
    """Re-indent an XML string by prepending spaces to each line.
    Use when composing multiple generator outputs into a body_content.

    Args:
        xml_str: The XML string to indent
        level: Number of indentation levels to add
        spaces: Spaces per level (default 2)

    Example:
        login = gen_sap_login(...)
        navigate = gen_sap_call_transaction(...)
        body = indent_xml(login, 4) + '\\n' + indent_xml(navigate, 4)
        full = gen_sap_logon(body_content=body)
    """
    if not xml_str or not xml_str.strip():
        return xml_str
    prefix = ' ' * (level * spaces)
    lines = xml_str.split('\n')
    return '\n'.join(prefix + line if line.strip() else line for line in lines)


def _idref(name):
    """Generate WorkflowViewState.IdRef attribute."""
    return f'sap2010:WorkflowViewState.IdRef="{name}"'



# ═══════════════════════════════════════════════════════════════════════════
# 1. NSAPLogon — SAP GUI Scope/Container
# ═══════════════════════════════════════════════════════════════════════════

def gen_sap_logon(
    display_name="SAP Logon",
    sap_connection="in_strConnection",
    sap_exe_path="in_strSapLogonPath",
    scope_guid=None,
    close_mode="Never",
    attach_mode="ByInstance",
    window_resize="Maximize",
    retries=5,
    delay_between_retries=0.5,
    body_content="",
    body_variables=None,
    id_ref="NSAPLogon_1",
):
    """Generate NSAPLogon scope — the SAP GUI container activity (launch ONLY).

    NSAPLogon is used exclusively for SAP_Launch.xaml (opening SAP GUI).
    Action workflows that attach to existing sessions use NApplicationCard instead.

    Args:
        display_name: Activity display name
        sap_connection: Variable/argument name holding SAP connection/system name
        sap_exe_path: Variable/argument name for path to saplogon.exe.
                      Pass a variable name (e.g., "in_strSapLogonPath") — the generator
                      wraps it in brackets: FilePath="[in_strSapLogonPath]".
        scope_guid: GUID for this scope (auto-generated if None)
        close_mode: Always (close when done), Never (leave open)
        attach_mode: ByInstance, BySelector
        window_resize: Maximize, None, Minimize
        retries: Number of retries for connection
        delay_between_retries: Seconds between retries
        body_content: XAML content to place inside the scope body
        body_variables: List of (name, type) tuples for Sequence.Variables, e.g.:
                       [("in_strClient", "x:String"), ("secstrPassword", "ss:SecureString"),
                        ("arr_Data", "s:String[]")]
                       SecureString requires xmlns:ss="clr-namespace:System.Security;assembly=System.Private.CoreLib"
                       on the root Activity element.
                       Or a raw XAML string (for backward compat)
        id_ref: ViewState IdRef
    """
    if scope_guid is None:
        scope_guid = _guid()

    selector_escaped = _escape_selector(
        f"<wnd app='saplogon.exe' cls='SAP_FRONTEND_SESSION' />"
    )

    # Build Sequence.Variables block
    vars_block = ""
    if body_variables:
        if isinstance(body_variables, list):
            # List of (name, type) tuples
            var_lines = []
            for var_name, var_type in body_variables:
                var_lines.append(f'          <Variable x:TypeArguments="{var_type}" Name="{var_name}" />')
            vars_block = "        <Sequence.Variables>\n" + "\n".join(var_lines) + "\n        </Sequence.Variables>\n"
        elif isinstance(body_variables, str) and body_variables.strip():
            # Raw XAML string (backward compat) — wrap in Sequence.Variables if not already wrapped
            if '<Sequence.Variables>' not in body_variables:
                vars_block = f"        <Sequence.Variables>\n{body_variables}\n        </Sequence.Variables>\n"
            else:
                vars_block = body_variables + "\n"

    xml = f'''<uix:NSAPLogon AttachMode="{attach_mode}" CloseMode="{close_mode}" \
DelayBetweenRetries="{delay_between_retries}" \
DisplayName="{_escape(display_name)}" \
HealingAgentBehavior="Job" \
{_hint(488, 989)} \
{_idref(id_ref)} \
Retries="{retries}" \
ScopeGuid="{scope_guid}" \
Version="V2" \
WindowResize="{window_resize}">
  <uix:NSAPLogon.Body>
    <ActivityAction x:TypeArguments="x:Object">
      <ActivityAction.Argument>
        <DelegateInArgument x:TypeArguments="x:Object" Name="WSSessionData" />
      </ActivityAction.Argument>
      <Sequence DisplayName="Do" {_hint(486, 815)}>
{vars_block}        <sap:WorkflowViewStateService.ViewState>
          <scg:Dictionary x:TypeArguments="x:String, x:Object">
            <x:Boolean x:Key="IsExpanded">True</x:Boolean>
          </scg:Dictionary>
        </sap:WorkflowViewStateService.ViewState>
{body_content}
      </Sequence>
    </ActivityAction>
  </uix:NSAPLogon.Body>
  <uix:NSAPLogon.OCREngine>
    <ActivityFunc x:TypeArguments="sd:Image, scg:IEnumerable(scg:KeyValuePair(sd1:Rectangle, x:String))">
      <ActivityFunc.Argument>
        <DelegateInArgument x:TypeArguments="sd:Image" Name="Image" />
      </ActivityFunc.Argument>
    </ActivityFunc>
  </uix:NSAPLogon.OCREngine>
  <uix:NSAPLogon.TargetApp>
    <uix:TargetApp Area="0, 0, 0, 0" Arguments="[{sap_connection}]" \
FilePath="[{sap_exe_path}]" \
Selector="{selector_escaped}" Version="V2">
      <uix:TargetApp.WorkingDirectory>
        <InArgument x:TypeArguments="x:String" />
      </uix:TargetApp.WorkingDirectory>
    </uix:TargetApp>
  </uix:NSAPLogon.TargetApp>
</uix:NSAPLogon>'''
    return xml


# ═══════════════════════════════════════════════════════════════════════════
# 2. NSAPLogin — SAP Authentication
# ═══════════════════════════════════════════════════════════════════════════

def gen_sap_login(
    username="strUsername",
    secure_password="secstrPassword",
    client="strClient",
    language="strLanguage",
    option="Single",
    is_secure=True,
    out_ui_element=None,
    scope_id=None,
    display_name="SAP Login",
    id_ref="NSAPLogin_1",
):
    """Generate NSAPLogin activity — SAP authentication.

    Args:
        username: Variable name for SAP username
        secure_password: Variable name for SecureString password
        client: Variable name for SAP client number
        language: Variable name for SAP language (EN, DE, etc.)
        option: Single (one session), Multi (allow multiple)
        is_secure: True to use SecurePassword, False for plain text
        out_ui_element: Output variable name for SAP session UiElement reference
                        (e.g., "out_UISAP"). Passed to action workflows for attach.
                        If None, OutUiElement is omitted.
        scope_id: Parent NSAPLogon scope GUID
        display_name: Activity display name
        id_ref: ViewState IdRef
    """
    scope_identifier = scope_id or _guid()

    out_ui_attr = f' OutUiElement="[{out_ui_element}]"' if out_ui_element else ""

    xml = f'''<uix:NSAPLogin Client="[{client}]" \
DisplayName="{_escape(display_name)}" \
{_hint(452, 328)} \
{_idref(id_ref)} \
IsSecure="{str(is_secure)}" \
Language="[{language}]" \
Option="{option}"{out_ui_attr} \
ScopeIdentifier="{scope_identifier}" \
SecurePassword="[{secure_password}]" \
Username="[{username}]" \
Version="V5" />'''
    return xml


# ═══════════════════════════════════════════════════════════════════════════
# 3. NSAPCallTransaction — Transaction Navigation
# ═══════════════════════════════════════════════════════════════════════════

def gen_sap_call_transaction(
    transaction="strTransactionCode",
    prefix="/n",
    scope_id=None,
    display_name="Call Transaction",
    id_ref="NSAPCallTransaction_1",
):
    """Generate NSAPCallTransaction activity — navigate to SAP transaction.

    Args:
        transaction: Variable name or literal tcode (e.g., "ME21N")
        prefix: /n (same session), /o (new session), "" (navigate only)
        scope_id: Parent NSAPLogon scope GUID
        display_name: Activity display name
        id_ref: ViewState IdRef
    """
    scope_identifier = scope_id or _guid()

    # Handle transaction value:
    # - Variable name (e.g., "strTCode") → wrap in brackets: [strTCode]
    # - Already bracketed (e.g., "[strTCode]") → use as-is
    # - Literal tcode (e.g., "ME21N") → wrap as VB literal: [&quot;ME21N&quot;]
    # Detection: if it contains no brackets and looks like a tcode (uppercase+digits, ≤20 chars)
    # treat as literal; otherwise treat as variable
    if transaction.startswith("["):
        tx_value = transaction
    elif transaction.startswith('"') and transaction.endswith('"'):
        # Already quoted literal — escape for XML attribute
        tx_value = f"[{_escape(transaction)}]"
    elif len(transaction) <= 20 and transaction.replace("_", "").isalnum() and transaction == transaction.upper():
        # Looks like a literal tcode (ME21N, VA01, SE16, MM03) — wrap as VB string literal
        tx_value = f'[&quot;{transaction}&quot;]'
    else:
        # Variable name — just wrap in brackets
        tx_value = f"[{transaction}]"

    xml = f'''<uix:NSAPCallTransaction \
DisplayName="{_escape(display_name)}" \
{_hint(452, 166)} \
{_idref(id_ref)} \
Prefix="{_escape(prefix)}" \
ScopeIdentifier="{scope_identifier}" \
Transaction="{tx_value}" \
Version="V5" />'''
    return xml


# ═══════════════════════════════════════════════════════════════════════════
# 4. NSAPClickToolbarButton — System/Application Toolbar Buttons
# ═══════════════════════════════════════════════════════════════════════════

# Standard system toolbar buttons (tbar[0]) — these are the same across all SAP transactions
SYSTEM_TOOLBAR_ITEMS = [
    "Enter",
    "Close Command Field",
    "Save   (Ctrl+S)",
    "Back   (F3)",
    "Exit   (Shift+F3)",
    "Cancel   (F12)",
    "Print   (Ctrl+P)",
    "Find   (Ctrl+F)",
    "New GUI Window",
    "Generates shortcut",
    "Help   (F1)",
    "Customize Local Layout (Alt+F12)",
]

# Mapping from common short names to full toolbar item labels + tbar[0] btn indices
TOOLBAR_BUTTON_MAP = {
    "Enter":   {"item": "Enter",               "btn_id": "tbar[0]/btn[0]"},
    "Save":    {"item": "Save   (Ctrl+S)",      "btn_id": "tbar[0]/btn[11]"},
    "Back":    {"item": "Back   (F3)",           "btn_id": "tbar[0]/btn[3]"},
    "Exit":    {"item": "Exit   (Shift+F3)",     "btn_id": "tbar[0]/btn[15]"},
    "Cancel":  {"item": "Cancel   (F12)",        "btn_id": "tbar[0]/btn[12]"},
    "Print":   {"item": "Print   (Ctrl+P)",      "btn_id": "tbar[0]/btn[86]"},
    "Find":    {"item": "Find   (Ctrl+F)",       "btn_id": "tbar[0]/btn[71]"},
    "Help":    {"item": "Help   (F1)",           "btn_id": "tbar[0]/btn[2]"},
}


def gen_sap_click_toolbar(
    item="Enter",
    sap_selector=None,
    scope_selector=None,
    scope_id=None,
    items=None,
    display_name=None,
    id_ref="NSAPClickToolbarButton_1",
):
    """Generate NSAPClickToolbarButton activity — click system/app toolbar button.

    Args:
        item: Button label (e.g., "Enter", "Save", "Back") or full label with shortcut
        sap_selector: Full SAP selector for the button (e.g., "<sap id='tbar[0]/btn[11]' />")
                      If None, auto-resolved from TOOLBAR_BUTTON_MAP for known buttons
        scope_selector: Window selector (auto-generated if None)
        scope_id: Parent NSAPLogon scope GUID
        items: List of toolbar items (defaults to SYSTEM_TOOLBAR_ITEMS)
        display_name: Activity display name (auto-generated from item if None)
        id_ref: ViewState IdRef
    """
    scope_identifier = scope_id or _guid()
    if items is None:
        items = SYSTEM_TOOLBAR_ITEMS

    # Resolve short names to full labels + selectors
    if item in TOOLBAR_BUTTON_MAP:
        resolved = TOOLBAR_BUTTON_MAP[item]
        full_item = resolved["item"]
        if sap_selector is None:
            sap_selector = f"<sap id='{resolved['btn_id']}' />"
    else:
        full_item = item
        if sap_selector is None:
            sap_selector = f"<sap id='tbar[0]/btn[0]' />"

    if display_name is None:
        display_name = f"Click Toolbar Button '{full_item}'"

    if scope_selector is None:
        scope_selector = "<wnd app='saplogon.exe' cls='SAP_FRONTEND_SESSION' />"

    items_xml = '\n'.join(
        f'      <x:String xml:space="preserve">{_escape(i)}</x:String>'
        if '  ' in i else
        f'      <x:String>{_escape(i)}</x:String>'
        for i in items
    )

    xml = f'''<uix:NSAPClickToolbarButton \
DisplayName="{_escape(display_name)}" \
HealingAgentBehavior="SameAsCard" \
{_hint(452, 195)} \
{_idref(id_ref)} \
Item="{_escape(full_item)}" \
ScopeIdentifier="{scope_identifier}" \
Version="V5">
  <uix:NSAPClickToolbarButton.Items>
    <scg:List x:TypeArguments="x:String" Capacity="{len(items)}">
{items_xml}
    </scg:List>
  </uix:NSAPClickToolbarButton.Items>
  <uix:NSAPClickToolbarButton.Target>
    <uix:TargetAnchorable \
ElementType="Button" \
ElementVisibilityArgument="Interactive" \
FullSelectorArgument="{_escape_selector(sap_selector)}" \
Guid="{_guid()}" \
ScopeSelectorArgument="{_escape_selector(scope_selector)}" \
SearchSteps="Selector" \
Version="V6" \
WaitForReadyArgument="Interactive" />
  </uix:NSAPClickToolbarButton.Target>
</uix:NSAPClickToolbarButton>'''
    return xml


# ═══════════════════════════════════════════════════════════════════════════
# 5. NSAPSelectMenuItem — Menu Path Selection
# ═══════════════════════════════════════════════════════════════════════════

def gen_sap_select_menu_item(
    item="System/Status...",
    scope_id=None,
    items=None,
    display_name=None,
    id_ref="NSAPSelectMenuItem_1",
):
    """Generate NSAPSelectMenuItem activity — select a menu item by path.

    Args:
        item: Menu path using forward slashes (e.g., "System/Status...", "Edit/Execute")
        scope_id: Parent NSAPLogon scope GUID
        items: Full list of available menu items (optional, for design-time reference)
        display_name: Activity display name
        id_ref: ViewState IdRef
    """
    scope_identifier = scope_id or _guid()
    if display_name is None:
        display_name = f"Select Menu Item '{item}'"

    items_block = ""
    if items:
        items_entries = '\n'.join(
            f'      <x:String>{_escape(i)}</x:String>'
            for i in items
        )
        items_block = f'''
  <uix:NSAPSelectMenuItem.Items>
    <scg:List x:TypeArguments="x:String" Capacity="{len(items)}">
{items_entries}
    </scg:List>
  </uix:NSAPSelectMenuItem.Items>'''

    xml = f'''<uix:NSAPSelectMenuItem \
DisplayName="{_escape(display_name)}" \
{_hint(452, 123)} \
{_idref(id_ref)} \
Item="{_escape(item)}" \
ScopeIdentifier="{scope_identifier}" \
Version="V5">{items_block}
</uix:NSAPSelectMenuItem>'''
    return xml


# ═══════════════════════════════════════════════════════════════════════════
# 6. NSAPReadStatusbar — Read Status Bar Message
# ═══════════════════════════════════════════════════════════════════════════

def gen_sap_read_statusbar(
    message_text="strStatusBarMsg",
    message_type="strStatusBarMsgType",
    message_data="arrStatusBarMsgData",
    message_id=None,
    message_number=None,
    scope_id=None,
    display_name="Read Status Bar",
    id_ref="NSAPReadStatusbar_1",
):
    """Generate NSAPReadStatusbar activity — read SAP status bar.

    Args:
        message_text: Output variable for status bar text (String)
        message_type: Output variable for message type: S/E/W/A/I (String)
        message_data: Output variable for message parameters (String[])
        message_id: Output variable for SAP message class (String, optional)
        message_number: Output variable for SAP message number (String, optional)
        scope_id: Parent NSAPLogon scope GUID
        display_name: Activity display name
        id_ref: ViewState IdRef
    """
    scope_identifier = scope_id or _guid()

    msg_id_attr = 'MessageId="{x:Null}" ' if message_id is None else f'MessageId="[{message_id}]" '
    msg_num_attr = 'MessageNumber="{x:Null}" ' if message_number is None else f'MessageNumber="[{message_number}]" '

    xml = f'''<uix:NSAPReadStatusbar \
{msg_id_attr}\
{msg_num_attr}\
DisplayName="{_escape(display_name)}" \
{_hint(452, 227)} \
{_idref(id_ref)} \
MessageData="[{message_data}]" \
MessageText="[{message_text}]" \
MessageType="[{message_type}]" \
ScopeIdentifier="{scope_identifier}" \
Version="V5" />'''
    return xml


# ═══════════════════════════════════════════════════════════════════════════
# 7. NSAPTableCellScope — Table Cell Targeting Scope
# ═══════════════════════════════════════════════════════════════════════════

def gen_sap_table_cell_scope(
    column_name="Short Text",
    row_index=0,
    row_type="FirstEmptyRow",
    sap_table_selector=None,
    scope_selector=None,
    column_names=None,
    out_ui_element="uiElTableCell",
    scope_id=None,
    body_content="",
    display_name=None,
    id_ref="NSAPTableCellScope_1",
):
    """Generate NSAPTableCellScope activity — scope targeting a specific table cell.

    Standard activities (NTypeInto, NGetText, NClick) can be placed inside the body
    and will operate on the targeted cell via the OutUiElement reference.

    Args:
        column_name: Column name or tooltip to target (from inspect-sap-tree.ps1 output)
        row_index: Row number (0-based)
        row_type: FirstEmptyRow, SpecificRow, LastRow
        sap_table_selector: Full SAP selector for the table control
                           (e.g., "<sap id='usr/sub.../tblSAPLMEGUITC_1211' />")
        scope_selector: Window selector
        column_names: List of all column names/tooltips in the table (from inspection)
        out_ui_element: Variable name for the cell UiElement reference
        scope_id: Parent NSAPLogon scope GUID
        body_content: XAML for activities inside the cell scope
        display_name: Activity display name
        id_ref: ViewState IdRef
    """
    scope_identifier = scope_id or _guid()
    if display_name is None:
        display_name = f"Table Cell Scope '{column_name}'"
    if scope_selector is None:
        scope_selector = "<wnd app='saplogon.exe' cls='SAP_FRONTEND_SESSION' />"
    if sap_table_selector is None:
        sap_table_selector = "<sap id='usr/tblTABLE_NAME' />"

    # Column names array
    col_names_xml = ""
    if column_names:
        col_entries = []
        for cn in column_names:
            escaped_cn = _escape(cn)
            col_entries.append(f'      <x:String>{escaped_cn}</x:String>')
        col_names_xml = f'''
  <uix:NSAPTableCellScope.ColumnNames>
    <x:Array Type="x:String">
{chr(10).join(col_entries)}
    </x:Array>
  </uix:NSAPTableCellScope.ColumnNames>'''

    xml = f'''<uix:NSAPTableCellScope \
ColumnName="{_escape(column_name)}" \
DisplayName="{_escape(display_name)}" \
HealingAgentBehavior="SameAsCard" \
{_hint(452, 532)} \
{_idref(id_ref)} \
OutUiElement="[{out_ui_element}]" \
RowIndex="{row_index}" \
RowType="{row_type}" \
ScopeIdentifier="{scope_identifier}" \
Version="V5">
  <uix:NSAPTableCellScope.Body>
    <ActivityAction x:TypeArguments="x:Object">
      <ActivityAction.Argument>
        <DelegateInArgument x:TypeArguments="x:Object" Name="ContextTarget" />
      </ActivityAction.Argument>
      <Sequence DisplayName="Do" {_hint(450, 277)}>
        <sap:WorkflowViewStateService.ViewState>
          <scg:Dictionary x:TypeArguments="x:String, x:Object">
            <x:Boolean x:Key="IsExpanded">True</x:Boolean>
          </scg:Dictionary>
        </sap:WorkflowViewStateService.ViewState>
{body_content}
      </Sequence>
    </ActivityAction>
  </uix:NSAPTableCellScope.Body>{col_names_xml}
  <uix:NSAPTableCellScope.Target>
    <uix:TargetAnchorable \
ElementType="Table" \
ElementVisibilityArgument="Interactive" \
FullSelectorArgument="{_escape_selector(sap_table_selector)}" \
Guid="{_guid()}" \
ScopeSelectorArgument="{_escape_selector(scope_selector)}" \
SearchSteps="Selector" \
Version="V6" \
WaitForReadyArgument="Interactive" />
  </uix:NSAPTableCellScope.Target>
</uix:NSAPTableCellScope>'''
    return xml



# ═══════════════════════════════════════════════════════════════════════════
# CONVENIENCE: Common SAP Workflow Patterns
# ═══════════════════════════════════════════════════════════════════════════

def gen_sap_status_bar_check(
    message_text_var="strStatusBarMsg",
    message_type_var="strStatusBarMsgType",
    message_data_var="arrStatusBarMsgData",
    scope_id=None,
    read_id_ref="NSAPReadStatusbar_1",
):
    """Generate the standard SAP status bar check pattern:
    ReadStatusbar + If type='E' pattern.

    Returns tuple: (read_statusbar_xml, if_condition_expression)
    The caller should use the expression in an If activity.
    """
    read_xml = gen_sap_read_statusbar(
        message_text=message_text_var,
        message_type=message_type_var,
        message_data=message_data_var,
        scope_id=scope_id,
        id_ref=read_id_ref,
    )
    condition = f'Not {message_type_var}.Equals("E")'
    return read_xml, condition


def gen_sap_type_into_cell(
    column_name,
    text_variable,
    sap_table_selector,
    scope_selector=None,
    column_names=None,
    row_type="FirstEmptyRow",
    row_index=0,
    scope_id=None,
    cell_var_name=None,
    display_name=None,
    id_ref="NSAPTableCellScope_1",
    cell_scope_id_ref=None,
    type_into_id_ref=None,
):
    """Convenience: Generate NSAPTableCellScope wrapping an NTypeInto.

    This is the most common SAP table interaction pattern — scope a cell,
    then type into it using the OutUiElement reference.

    Args:
        column_name: Column to target
        text_variable: Variable name containing text to type
        sap_table_selector: Table SAP selector
        scope_selector: Window selector
        column_names: Full column list from inspection
        row_type: FirstEmptyRow, SpecificRow, etc.
        row_index: Row number
        scope_id: Parent scope GUID
        cell_var_name: Variable for cell reference (auto-generated)
        display_name: Cell scope display name
        cell_scope_id_ref: IdRef for cell scope
        type_into_id_ref: IdRef for type into
    """
    if cell_scope_id_ref is None:
        cell_scope_id_ref = id_ref
    if type_into_id_ref is None:
        # Derive from id_ref: NSAPTableCellScope_3 → NTypeInto_Cell_3
        # Uses "Cell" prefix to avoid collision with standalone NTypeInto IdRefs
        suffix = id_ref.rsplit("_", 1)[-1] if "_" in id_ref else "1"
        type_into_id_ref = f"NTypeInto_Cell_{suffix}"

    if cell_var_name is None:
        safe_col = column_name.replace(" ", "").replace(".", "")[:20]
        cell_var_name = f"uiEl{safe_col}Cell"

    # Build inner NTypeInto using InUiElement (no Target needed — cell scope provides it)
    # Includes VerifyOptions block to match core gen_ntypeinto structure
    si = scope_id or _guid()
    type_into_xml = f'''        <uix:NTypeInto ActivateBefore="True" \
ClickBeforeMode="Single" \
ClipboardMode="Never" \
DisplayName="Type Into ({column_name})" \
EmptyFieldMode="SingleLine" \
HealingAgentBehavior="SameAsCard" \
{_hint(416, 217)} \
{_idref(type_into_id_ref)} \
InUiElement="[{cell_var_name}]" \
ScopeIdentifier="{si}" \
Text="[{text_variable}]" \
Version="V5">
          <uix:NTypeInto.VerifyOptions>
            <uix:VerifyExecutionTypeIntoOptions DisplayName="{{x:Null}}" Mode="Appears">
              <uix:VerifyExecutionTypeIntoOptions.Retry>
                <InArgument x:TypeArguments="x:Boolean" />
              </uix:VerifyExecutionTypeIntoOptions.Retry>
              <uix:VerifyExecutionTypeIntoOptions.Timeout>
                <InArgument x:TypeArguments="x:Double" />
              </uix:VerifyExecutionTypeIntoOptions.Timeout>
            </uix:VerifyExecutionTypeIntoOptions>
          </uix:NTypeInto.VerifyOptions>
        </uix:NTypeInto>'''

    return gen_sap_table_cell_scope(
        column_name=column_name,
        row_index=row_index,
        row_type=row_type,
        sap_table_selector=sap_table_selector,
        scope_selector=scope_selector,
        column_names=column_names,
        out_ui_element=cell_var_name,
        scope_id=scope_id,
        body_content=type_into_xml,
        display_name=display_name or f"Table Cell Scope '{column_name}'",
        id_ref=cell_scope_id_ref,
    )
