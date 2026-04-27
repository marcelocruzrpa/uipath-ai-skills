"""NApplicationCard generators — open/attach/close web and desktop apps."""
from ._helpers import _hs, _escape_xml_attr, _escape_vb_expr, _normalize_selector_quotes, _uuid
from ._xml_utils import _ocr_engine_block, _target_app_empty, _target_app_with_selector, _body_block, _viewstate_block
from utils import detect_browser_type


def gen_napplicationcard_open(display_name, url_variable, out_ui_element, scope_guid,
                              id_ref, body_content, body_sequence_idref,
                              target_app_selector="", browser_title="App",
                              obj_repo_app=None, indent="    "):
    """NApplicationCard for OPENING a web app. OpenMode=Always, CloseMode=Never."""
    selector = target_app_selector or f"<html app='msedge.exe' title='{_escape_xml_attr(browser_title)}' />"
    selector = _normalize_selector_quotes(selector)
    esc_sel = _escape_xml_attr(selector)
    hs = _hs("NApplicationCard")
    dn = _escape_xml_attr(display_name)
    i, i2, i3, i4, i5 = indent, indent+"  ", indent+"    ", indent+"      ", indent+"        "
    body = _body_block(body_content, body_sequence_idref, i2, i3, i4, i5)
    ocr = _ocr_engine_block(i2, i3, i4, i5)
    obj_repo_app_attrs = ""
    if obj_repo_app:
        if obj_repo_app.get("content_hash"):
            obj_repo_app_attrs += f' ContentHash="{obj_repo_app["content_hash"]}"'
        if obj_repo_app.get("reference"):
            obj_repo_app_attrs += f' Reference="{obj_repo_app["reference"]}"'
    # Detect BrowserType from selector — Studio requires this for browser targets
    # to resolve URL binding (without it: "File path is required" validation error)
    browser_type = detect_browser_type(selector)
    bt_attr = f' BrowserType="{browser_type}"' if browser_type else ""
    return f"""{i}<uix:NApplicationCard AttachMode="ByInstance" CloseMode="Never" DisplayName="{dn}" HealingAgentBehavior="Job" {hs} sap2010:WorkflowViewState.IdRef="{id_ref}" InteractionMode="Simulate" IsIncognito="True" OpenMode="Always" OutUiElement="[{_escape_vb_expr(out_ui_element)}]" ScopeGuid="{scope_guid}" Version="V2">
{body}
{ocr}
{i2}<uix:NApplicationCard.TargetApp>
{i3}<uix:TargetApp Area="0, 0, 0, 0"{bt_attr}{obj_repo_app_attrs} Selector="{esc_sel}" Url="[{_escape_vb_expr(url_variable)}]" Version="V2">
{i4}<uix:TargetApp.Arguments>
{i5}<InArgument x:TypeArguments="x:String" />
{i4}</uix:TargetApp.Arguments>
{i4}<uix:TargetApp.FilePath>
{i5}<InArgument x:TypeArguments="x:String" />
{i4}</uix:TargetApp.FilePath>
{i4}<uix:TargetApp.WorkingDirectory>
{i5}<InArgument x:TypeArguments="x:String" />
{i4}</uix:TargetApp.WorkingDirectory>
{i3}</uix:TargetApp>
{i2}</uix:NApplicationCard.TargetApp>
{i}</uix:NApplicationCard>"""


def gen_napplicationcard_attach(display_name, ui_element_variable, scope_guid,
                                id_ref, body_content, body_sequence_idref,
                                interaction_mode=None, desktop=False,
                                target_app_selector="", indent="    "):
    """NApplicationCard for ATTACHING. OpenMode=Never, CloseMode=Never.

    Args:
        desktop: If True, uses desktop defaults (ByInstance, Simulate, no IsIncognito).
                 If False, uses browser defaults (SingleWindow, DebuggerApi, IsIncognito).
        interaction_mode: Override interaction mode. If None, auto-selected from desktop flag.
        target_app_selector: Window selector for TargetApp (e.g. "<wnd app='desktopapp.exe' title='Desktop App*' />").
                             When provided, emitted on TargetApp for fallback identification.
    """
    if interaction_mode is None:
        interaction_mode = "Simulate" if desktop else "DebuggerApi"
    valid_modes = ("Simulate", "DebuggerApi", "HardwareEvents", "WindowMessages")
    if interaction_mode not in valid_modes:
        raise ValueError(f"Invalid interaction_mode: {interaction_mode}. Must be one of: {', '.join(valid_modes)}")
    attach_mode = "ByInstance" if desktop else "SingleWindow"
    incognito_attr = "" if desktop else ' IsIncognito="True"'
    hs = _hs("NApplicationCard")
    dn = _escape_xml_attr(display_name)
    i, i2, i3, i4, i5 = indent, indent+"  ", indent+"    ", indent+"      ", indent+"        "
    body = _body_block(body_content, body_sequence_idref, i2, i3, i4, i5)
    ocr = _ocr_engine_block(i2, i3, i4, i5)
    ta = (_target_app_with_selector(target_app_selector, i2, i3, i4, i5)
          if target_app_selector else _target_app_empty(i2, i3, i4, i5))
    return f"""{i}<uix:NApplicationCard AttachMode="{attach_mode}" CloseMode="Never" DisplayName="{dn}" HealingAgentBehavior="Job" {hs} sap2010:WorkflowViewState.IdRef="{id_ref}" InUiElement="[{_escape_vb_expr(ui_element_variable)}]" InteractionMode="{interaction_mode}"{incognito_attr} OpenMode="Never" OutUiElement="[{_escape_vb_expr(ui_element_variable)}]" ScopeGuid="{scope_guid}" Version="V2">
{body}
{ocr}
{ta}
{i}</uix:NApplicationCard>"""


def gen_napplicationcard_close(ui_element_variable, scope_guid, id_ref,
                               body_content, body_sequence_idref,
                               display_name="Use Browser/App", desktop=False,
                               target_app_selector="", indent="    "):
    """NApplicationCard for CLOSING. OpenMode=Never, CloseMode=Always, AttachMode=ByInstance.

    Args:
        desktop: If True, no IsIncognito (desktop app). If False, IsIncognito=True (browser).
        target_app_selector: Window selector for TargetApp fallback identification.
    """
    hs = _hs("NApplicationCard")
    dn = _escape_xml_attr(display_name)
    incognito_attr = "" if desktop else ' IsIncognito="True"'
    i, i2, i3, i4, i5 = indent, indent+"  ", indent+"    ", indent+"      ", indent+"        "
    body = _body_block(body_content, body_sequence_idref, i2, i3, i4, i5)
    ocr = _ocr_engine_block(i2, i3, i4, i5)
    ta = (_target_app_with_selector(target_app_selector, i2, i3, i4, i5)
          if target_app_selector else _target_app_empty(i2, i3, i4, i5))
    return f"""{i}<uix:NApplicationCard AttachMode="ByInstance" CloseMode="Always" DisplayName="{dn}" HealingAgentBehavior="Job" {hs} sap2010:WorkflowViewState.IdRef="{id_ref}" InUiElement="[{_escape_vb_expr(ui_element_variable)}]" InteractionMode="Simulate"{incognito_attr} OpenMode="Never" OutUiElement="[{_escape_vb_expr(ui_element_variable)}]" ScopeGuid="{scope_guid}" Version="V2">
{body}
{ocr}
{ta}
{i}</uix:NApplicationCard>"""


def gen_napplicationcard_desktop_open(display_name, file_path_variable, out_ui_element,
                                      scope_guid, id_ref, body_content,
                                      body_sequence_idref,
                                      target_app_selector="",
                                      obj_repo_app=None,
                                      indent="    "):
    """NApplicationCard for OPENING a desktop app. OpenMode=Always, CloseMode=Never.

    FilePath uses the attribute form on TargetApp: FilePath="[expr]"
    (matches how Url="[expr]" works on napplicationcard_open for browsers).
    - NApplicationCard has NO InteractionMode attribute (Studio manages internally;
      child activities use SameAsCard to inherit the card's default)
    - No BrowserType/Url/IsIncognito (browser-only properties)
    - No DebuggerApi (browser-only)

    Args:
        file_path_variable: VB expression for .exe path (no brackets),
                            e.g. 'in_Config("ExcelPath").ToString' or 'strExePath'
        out_ui_element: UiElement output variable (no brackets)
        target_app_selector: Selector for the app window,
                             e.g. "<wnd app='desktopapp.exe' ctrlname='Form1' />"
        obj_repo_app: Optional Object Repository app reference dict with keys:
                      - reference: "LibraryId/AppId" (from generate_object_repository)
                      - content_hash: ContentHash string
    """
    selector = target_app_selector or "<wnd app='app.exe' />"
    selector = _normalize_selector_quotes(selector)
    esc_sel = _escape_xml_attr(selector)
    hs = _hs("NApplicationCard")
    dn = _escape_xml_attr(display_name)
    i, i2, i3, i4, i5 = indent, indent+"  ", indent+"    ", indent+"      ", indent+"        "
    body = _body_block(body_content, body_sequence_idref, i2, i3, i4, i5)
    ocr = _ocr_engine_block(i2, i3, i4, i5)
    obj_repo_app_attrs = ""
    if obj_repo_app:
        if obj_repo_app.get("content_hash"):
            obj_repo_app_attrs += f' ContentHash="{obj_repo_app["content_hash"]}"'
        if obj_repo_app.get("reference"):
            obj_repo_app_attrs += f' Reference="{obj_repo_app["reference"]}"'
    return f"""{i}<uix:NApplicationCard AttachMode="ByInstance" CloseMode="Never" DisplayName="{dn}" HealingAgentBehavior="Job" {hs} sap2010:WorkflowViewState.IdRef="{id_ref}" OpenMode="Always" OutUiElement="[{_escape_vb_expr(out_ui_element)}]" ScopeGuid="{scope_guid}" Version="V2">
{body}
{ocr}
{i2}<uix:NApplicationCard.TargetApp>
{i3}<uix:TargetApp Area="0, 0, 0, 0" FilePath="[{_escape_vb_expr(file_path_variable)}]"{obj_repo_app_attrs} Selector="{esc_sel}" Version="V2">
{i4}<uix:TargetApp.Arguments>
{i5}<InArgument x:TypeArguments="x:String" />
{i4}</uix:TargetApp.Arguments>
{i4}<uix:TargetApp.WorkingDirectory>
{i5}<InArgument x:TypeArguments="x:String" />
{i4}</uix:TargetApp.WorkingDirectory>
{i3}</uix:TargetApp>
{i2}</uix:NApplicationCard.TargetApp>
{i}</uix:NApplicationCard>"""
