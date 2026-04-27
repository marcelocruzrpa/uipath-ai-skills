"""UI automation activity generators."""
from ._helpers import _hs, _escape_xml_attr, _escape_vb_expr, _normalize_selector_quotes
from ._xml_utils import _selector_xml, _viewstate_block


def gen_ntypeinto(display_name, selector, text_variable, id_ref, scope_id,
                  is_secure=False, empty_field_mode="SingleLine",
                  obj_repo=None, indent="            "):
    if not (empty_field_mode in ("SingleLine", "MultiLine", "None")):
        raise ValueError(f"Invalid EmptyFieldMode '{empty_field_mode}'")
    text_attr = f'SecureText="[{_escape_vb_expr(text_variable)}]"' if is_secure else f'Text="[{_escape_vb_expr(text_variable)}]"'
    target = _selector_xml(selector, obj_repo=obj_repo)
    hs = _hs("NTypeInto")
    dn = _escape_xml_attr(display_name)
    i, i2, i3, i4, i5 = indent, indent+"  ", indent+"    ", indent+"      ", indent+"        "
    return f"""{i}<uix:NTypeInto ActivateBefore="True" ClickBeforeMode="None" ClipboardMode="Never" DisplayName="{dn}" EmptyFieldMode="{empty_field_mode}" HealingAgentBehavior="SameAsCard" {hs} sap2010:WorkflowViewState.IdRef="{id_ref}" InteractionMode="SameAsCard" ScopeIdentifier="{scope_id}" {text_attr} Version="V5">
{i2}<uix:NTypeInto.Target>
{i3}{target}
{i2}</uix:NTypeInto.Target>
{i2}<uix:NTypeInto.VerifyOptions>
{i3}<uix:VerifyExecutionTypeIntoOptions DisplayName="{{x:Null}}" Mode="Appears">
{i4}<uix:VerifyExecutionTypeIntoOptions.Retry>
{i5}<InArgument x:TypeArguments="x:Boolean" />
{i4}</uix:VerifyExecutionTypeIntoOptions.Retry>
{i4}<uix:VerifyExecutionTypeIntoOptions.Timeout>
{i5}<InArgument x:TypeArguments="x:Double" />
{i4}</uix:VerifyExecutionTypeIntoOptions.Timeout>
{i3}</uix:VerifyExecutionTypeIntoOptions>
{i2}</uix:NTypeInto.VerifyOptions>
{i}</uix:NTypeInto>"""


# ---------------------------------------------------------------------------
# NClick
# ---------------------------------------------------------------------------

def gen_nclick(display_name, selector, id_ref, scope_id,
               click_type="Single", mouse_button="Left",
               obj_repo=None, indent="            "):
    if not (click_type in ("Single", "Double")):
        raise ValueError(f"Invalid click_type: {click_type}. Must be one of: Single, Double")
    if not (mouse_button in ("Left", "Right", "Middle")):
        raise ValueError(f"Invalid mouse_button: {mouse_button}. Must be one of: Left, Right, Middle")
    target = _selector_xml(selector, obj_repo=obj_repo)
    hs = _hs("NClick")
    dn = _escape_xml_attr(display_name)
    i, i2, i3 = indent, indent+"  ", indent+"    "
    return f"""{i}<uix:NClick ActivateBefore="True" ClickType="{click_type}" DisplayName="{dn}" HealingAgentBehavior="SameAsCard" {hs} sap2010:WorkflowViewState.IdRef="{id_ref}" InteractionMode="SameAsCard" KeyModifiers="None" MouseButton="{mouse_button}" ScopeIdentifier="{scope_id}" Version="V5">
{i2}<uix:NClick.Target>
{i3}{target}
{i2}</uix:NClick.Target>
{i}</uix:NClick>"""


# ---------------------------------------------------------------------------
# NCheck  (Check / Uncheck / Toggle checkbox — idempotent)
# ---------------------------------------------------------------------------

def gen_ncheck(display_name, selector, id_ref, scope_id,
               action="Check",
               obj_repo=None, indent="            "):
    """Generate a Check/Uncheck (uix:NCheck) activity for checkboxes.

    Unlike NClick (which toggles), NCheck is idempotent:
    Action="Check" on an already-checked box does nothing.

    Args:
        action: "Check" (idempotent set), "Uncheck" (idempotent clear), or "Toggle".
    """
    if action not in ("Check", "Uncheck", "Toggle"):
        raise ValueError(f"Invalid action: {action}. Must be one of: Check, Uncheck, Toggle")
    target = _selector_xml(selector, obj_repo=obj_repo)
    hs = _hs("NCheck")
    dn = _escape_xml_attr(display_name)
    i, i2, i3 = indent, indent+"  ", indent+"    "
    return f"""{i}<uix:NCheck Action="{action}" DisplayName="{dn}" HealingAgentBehavior="SameAsCard" {hs} sap2010:WorkflowViewState.IdRef="{id_ref}" ScopeIdentifier="{scope_id}" Version="V5">
{i2}<uix:NCheck.Target>
{i3}{target}
{i2}</uix:NCheck.Target>
{i}</uix:NCheck>"""


# ---------------------------------------------------------------------------
# NHover
# ---------------------------------------------------------------------------

def gen_nhover(display_name, selector, id_ref, scope_id,
               hover_time=None, cursor_motion_type="Instant",
               obj_repo=None, indent="            "):
    """Generate a Hover (uix:NHover) activity.

    Args:
        display_name: DisplayName for the activity
        selector: UiPath selector string (single-quoted attributes)
        id_ref: IdRef for ViewState
        scope_id: ScopeIdentifier GUID from parent NApplicationCard
        hover_time: seconds to hold hover (int, omit for default)
        cursor_motion_type: 'Instant' or 'Smooth' — omit attr when 'Instant' (Studio default)
        indent: base indentation
    """
    if not (cursor_motion_type in ("Instant", "Smooth")):
        raise ValueError(f"Invalid cursor_motion_type: {cursor_motion_type}. Must be one of: Instant, Smooth")
    target = _selector_xml(selector, obj_repo=obj_repo)
    hs = _hs("NHover")
    dn = _escape_xml_attr(display_name)
    i, i2, i3 = indent, indent+"  ", indent+"    "

    # Optional attributes — only emit when non-default
    cmt_attr = ""
    if cursor_motion_type != "Instant":
        cmt_attr = (f' CursorMotionType="[UiPath.UIAutomationNext.Enums'
                    f'.CursorMotionType.{cursor_motion_type}]"')

    ht_attr = ""
    if hover_time is not None:
        ht_attr = f' HoverTime="{hover_time}"'

    return f"""{i}<uix:NHover{cmt_attr} DisplayName="{dn}" HealingAgentBehavior="SameAsCard" {hs}{ht_attr} sap2010:WorkflowViewState.IdRef="{id_ref}" InteractionMode="SameAsCard" ScopeIdentifier="{scope_id}" Version="V5">
{i2}<uix:NHover.Target>
{i3}{target}
{i2}</uix:NHover.Target>
{i}</uix:NHover>"""


# ---------------------------------------------------------------------------
# NKeyboardShortcuts
# ---------------------------------------------------------------------------

# Shortcut notation: [d(key)] = key down, [u(key)] = key up
# [d(hk)] / [u(hk)] = hotkey start/end marker
# Modifier keys: alt, ctrl, shift, win
# Special keys: enter, tab, esc, del, bksp, up, down, left, right,
#   home, end, pgup, pgdn, f1-f12, ins, prtsc, pause, numlock, scroll
# Letters/numbers: a-z, 0-9
#
# Common patterns:
#   Ctrl+C   = "[d(hk)][d(ctrl)d(c)][u(c)u(ctrl)][u(hk)]"
#   Ctrl+A   = "[d(hk)][d(ctrl)d(a)][u(a)u(ctrl)][u(hk)]"
#   Alt+F4   = "[d(hk)][d(alt)d(f4)][u(f4)u(alt)][u(hk)]"
#   Enter    = "[d(hk)][d(enter)][u(enter)][u(hk)]"
#   Ctrl+Shift+S = "[d(hk)][d(ctrl)d(shift)d(s)][u(s)u(shift)u(ctrl)][u(hk)]"

def gen_nkeyboardshortcuts(display_name, shortcuts, id_ref, scope_id,
                           selector="",
                           activate_before=True,
                           click_before_mode="None",
                           interaction_mode="HardwareEvents",
                           obj_repo=None, indent="            "):
    """Generate a Keyboard Shortcuts (uix:NKeyboardShortcuts) activity.

    Args:
        display_name: DisplayName for the activity
        shortcuts: shortcut string in UiPath notation, e.g.
            '[d(hk)][d(ctrl)d(c)][u(c)u(ctrl)][u(hk)]' for Ctrl+C
        id_ref: IdRef for ViewState
        scope_id: ScopeIdentifier GUID from parent NApplicationCard
        selector: optional UiPath selector — when provided, shortcut targets
            that element (expands to NKeyboardShortcuts.Target); when empty,
            activity is self-closing and targets the active window
        activate_before: bring window to front before sending keys (default True)
        click_before_mode: 'None' or 'Single' — click element before shortcut
        interaction_mode: 'HardwareEvents' (default), 'SimulateClick',
            'ChromiumApi', 'SameAsCard'
        indent: base indentation
    """
    if not (click_before_mode in ("None", "Single")):
        raise ValueError(f"Invalid click_before_mode: {click_before_mode}. Must be one of: None, Single")
    if not (interaction_mode in ("HardwareEvents", "SimulateClick", "ChromiumApi", "SameAsCard")):
        raise ValueError(f"Invalid interaction_mode: {interaction_mode}. Must be one of: HardwareEvents, SimulateClick, ChromiumApi, SameAsCard")
    hs = _hs("NKeyboardShortcuts")
    dn = _escape_xml_attr(display_name)
    ab = "True" if activate_before else "False"
    attrs = (
        f'ActivateBefore="{ab}" '
        f'ClickBeforeMode="{click_before_mode}" '
        f'DisplayName="{dn}" HealingAgentBehavior="SameAsCard" {hs} '
        f'sap2010:WorkflowViewState.IdRef="{id_ref}" '
        f'InteractionMode="{interaction_mode}" '
        f'ScopeIdentifier="{scope_id}" '
        f'Shortcuts="{shortcuts}" Version="V5"'
    )

    if not selector:
        return f'{indent}<uix:NKeyboardShortcuts {attrs} />'

    target = _selector_xml(selector, obj_repo=obj_repo)
    i2, i3 = indent + "  ", indent + "    "
    return f"""{indent}<uix:NKeyboardShortcuts {attrs}>
{i2}<uix:NKeyboardShortcuts.Target>
{i3}{target}
{i2}</uix:NKeyboardShortcuts.Target>
{indent}</uix:NKeyboardShortcuts>"""


# ---------------------------------------------------------------------------
# NDoubleClick / NRightClick — convenience wrappers over gen_nclick
# ---------------------------------------------------------------------------

def gen_ndoubleclick(display_name, selector, id_ref, scope_id,
                     mouse_button="Left", obj_repo=None, indent="            "):
    """Generate a Double Click activity (NClick with ClickType='Double')."""
    return gen_nclick(display_name, selector, id_ref, scope_id,
                      click_type="Double", mouse_button=mouse_button,
                      obj_repo=obj_repo, indent=indent)


def gen_nrightclick(display_name, selector, id_ref, scope_id,
                    obj_repo=None, indent="            "):
    """Generate a Right Click activity (NClick with MouseButton='Right')."""
    return gen_nclick(display_name, selector, id_ref, scope_id,
                      click_type="Single", mouse_button="Right",
                      obj_repo=obj_repo, indent=indent)


# ---------------------------------------------------------------------------
# NGetText
# ---------------------------------------------------------------------------

def gen_ngettext(display_name, output_variable, id_ref, scope_id,
                 selector="", in_ui_element="",
                 obj_repo=None, indent="            "):
    if not (bool(selector) != bool(in_ui_element)):
        raise ValueError("Provide exactly one of selector or in_ui_element")
    hs = _hs("NGetText")
    dn = _escape_xml_attr(display_name)
    i, i2, i3 = indent, indent+"  ", indent+"    "
    if in_ui_element:
        return f'{i}<uix:NGetText DisplayName="{dn}" HealingAgentBehavior="SameAsCard" {hs} sap2010:WorkflowViewState.IdRef="{id_ref}" InUiElement="[{_escape_vb_expr(in_ui_element)}]" ScopeIdentifier="{scope_id}" TextString="[{_escape_vb_expr(output_variable)}]" Version="V5" />'
    target = _selector_xml(selector, obj_repo=obj_repo)
    return f"""{i}<uix:NGetText DisplayName="{dn}" HealingAgentBehavior="SameAsCard" {hs} sap2010:WorkflowViewState.IdRef="{id_ref}" ScopeIdentifier="{scope_id}" TextString="[{_escape_vb_expr(output_variable)}]" Version="V5">
{i2}<uix:NGetText.Target>
{i3}{target}
{i2}</uix:NGetText.Target>
{i}</uix:NGetText>"""


# ---------------------------------------------------------------------------
# NCheckState
# ---------------------------------------------------------------------------

def gen_ncheckstate(display_name, selector, id_ref, scope_id,
                    if_exists_idref, if_not_exists_idref,
                    if_exists_body="", if_not_exists_body="",
                    out_ui_element="",
                    obj_repo=None, indent="            "):
    target = _selector_xml(selector, obj_repo=obj_repo)
    out_attr = f' OutUiElement="[{_escape_vb_expr(out_ui_element)}]"' if out_ui_element else ""
    hs = _hs("NCheckState")
    dn = _escape_xml_attr(display_name)
    i, i2, i3, i4 = indent, indent+"  ", indent+"    ", indent+"      "
    return f"""{i}<uix:NCheckState DisplayName="{dn}" EnableIfExists="False" EnableIfNotExists="False" HealingAgentBehavior="Disabled" {hs} sap2010:WorkflowViewState.IdRef="{id_ref}"{out_attr} ScopeIdentifier="{scope_id}" Version="V5">
{i2}<uix:NCheckState.IfExists>
{i3}<Sequence DisplayName="Target appears" sap2010:WorkflowViewState.IdRef="{if_exists_idref}">
{i4}{_viewstate_block(if_exists_idref)}
{if_exists_body}
{i3}</Sequence>
{i2}</uix:NCheckState.IfExists>
{i2}<uix:NCheckState.IfNotExists>
{i3}<Sequence DisplayName="Target does not appear" sap2010:WorkflowViewState.IdRef="{if_not_exists_idref}">
{i4}{_viewstate_block(if_not_exists_idref)}
{if_not_exists_body}
{i3}</Sequence>
{i2}</uix:NCheckState.IfNotExists>
{i2}<uix:NCheckState.Target>
{i3}{target}
{i2}</uix:NCheckState.Target>
{i}</uix:NCheckState>"""


# ---------------------------------------------------------------------------
# NSelectItem
# ---------------------------------------------------------------------------

def gen_nselectitem(display_name, selector, item_variable, id_ref, scope_id,
                    static_items=None,
                    obj_repo=None, indent="            "):
    """Generate NSelectItem — dropdown selection.

    Args:
        item_variable: VB expression for the item to select. Can be:
          - Variable name: "strStatus" → Item="[strStatus]"
          - Literal string: '"Completed"' → Item="[&quot;Completed&quot;]"
          Item is REQUIRED — UiPath rejects {x:Null}.
        static_items: List of static option strings for the Items list, e.g. ["Completed"]
    """
    if not (item_variable is not None and item_variable != ""):
        raise ValueError("item_variable is REQUIRED — NSelectItem rejects Item={x:Null}. "
                         "Use a variable name or a quoted literal like 'Completed'")
    target = _selector_xml(selector, obj_repo=obj_repo)
    dn = _escape_xml_attr(display_name)
    i, i2, i3, i4 = indent, indent+"  ", indent+"    ", indent+"      "

    # Item attribute: ALWAYS required
    item_attr = f'Item="[{_escape_vb_expr(item_variable)}]"'

    # Items list: static values (always present even if empty)
    items_xml = ""
    if static_items:
        items_entries = "\n".join(f"{i4}<x:String>{_escape_xml_attr(s)}</x:String>" for s in static_items)
        items_xml = f"""{i2}<uix:NSelectItem.Items>
{i3}<scg:List x:TypeArguments="x:String" Capacity="4">
{items_entries}
{i3}</scg:List>
{i2}</uix:NSelectItem.Items>"""
    else:
        import sys as _sys
        print(f"  [NOTE] NSelectItem '{display_name}' has empty Items list — "
              f"dropdown options won't show in Studio. Consider passing "
              f"static_items=['Option1', 'Option2'] for better UX.",
              file=_sys.stderr)
        items_xml = f"""{i2}<uix:NSelectItem.Items>
{i3}<scg:List x:TypeArguments="x:String" Capacity="4" />
{i2}</uix:NSelectItem.Items>"""

    return f"""{i}<uix:NSelectItem DisplayName="{dn}" HealingAgentBehavior="SameAsCard" {item_attr} sap:VirtualizedContainerService.HintSize="416,195" sap2010:WorkflowViewState.IdRef="{id_ref}" ScopeIdentifier="{scope_id}" Version="V1">
{items_xml}
{i2}<uix:NSelectItem.Target>
{i3}{target}
{i2}</uix:NSelectItem.Target>
{i}</uix:NSelectItem>"""


# ---------------------------------------------------------------------------
# NMouseScroll
# ---------------------------------------------------------------------------

def gen_nmousescroll(display_name, selector, id_ref, scope_id,
                     direction="Down", movement_units=3,
                     interaction_mode="HardwareEvents",
                     obj_repo=None, indent="            "):
    """Generate a Mouse Scroll (uix:NMouseScroll) activity.

    Args:
        display_name: DisplayName for the activity
        selector: UiPath selector string (single-quoted attributes)
        id_ref: IdRef for ViewState
        scope_id: ScopeIdentifier GUID from parent NApplicationCard
        direction: 'Down', 'Up', 'Left', 'Right'
        movement_units: number of scroll units (int, default 3)
        interaction_mode: 'HardwareEvents' (default), 'SimulateClick',
            'ChromiumApi', 'SameAsCard'
        indent: base indentation
    """
    if not (direction in ("Down", "Up", "Left", "Right")):
        raise ValueError(f"Invalid direction: {direction}. Must be one of: Down, Up, Left, Right")
    if not (interaction_mode in ("HardwareEvents", "SimulateClick", "ChromiumApi", "SameAsCard")):
        raise ValueError(f"Invalid interaction_mode: {interaction_mode}. Must be one of: HardwareEvents, SimulateClick, ChromiumApi, SameAsCard")
    target = _selector_xml(selector, obj_repo=obj_repo)
    hs = _hs("NMouseScroll")
    dn = _escape_xml_attr(display_name)
    i = indent
    i2 = i + "  "
    i3 = i2 + "  "
    i4 = i3 + "  "
    i5 = i4 + "  "
    i6 = i5 + "  "

    return f"""{i}<uix:NMouseScroll KeyModifiers="{{x:Null}}" Direction="{direction}" DisplayName="{dn}" HealingAgentBehavior="SameAsCard" {hs} sap2010:WorkflowViewState.IdRef="{id_ref}" InteractionMode="{interaction_mode}" MovementUnits="{movement_units}" ScopeIdentifier="{scope_id}" Version="V5">
{i2}<uix:NMouseScroll.SearchedElement>
{i3}<uix:SearchedElement>
{i4}<uix:SearchedElement.InUiElement>
{i5}<InArgument x:TypeArguments="ui:UiElement" />
{i4}</uix:SearchedElement.InUiElement>
{i4}<uix:SearchedElement.OutUiElement>
{i5}<OutArgument x:TypeArguments="ui:UiElement" />
{i4}</uix:SearchedElement.OutUiElement>
{i4}<uix:SearchedElement.Target>
{i5}{target}
{i4}</uix:SearchedElement.Target>
{i4}<uix:SearchedElement.Timeout>
{i5}<InArgument x:TypeArguments="x:Double" />
{i4}</uix:SearchedElement.Timeout>
{i3}</uix:SearchedElement>
{i2}</uix:NMouseScroll.SearchedElement>
{i}</uix:NMouseScroll>"""
