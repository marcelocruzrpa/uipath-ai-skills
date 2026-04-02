"""XML building blocks for activity generators — selectors, viewstate, OCR, target app, and body blocks.

Extracted from generate_activities.py. These functions produce reusable XAML
fragments consumed by the individual activity generator modules.
"""

from ._helpers import _uuid, _escape_xml_attr, _normalize_selector_quotes, _hs


def _selector_xml(selector: str, obj_repo: dict = None, scope_selector: str = None) -> str:
    """Generate TargetAnchorable XML element.

    Args:
        selector: Raw UiPath selector string.
        obj_repo: Optional Object Repository reference dict with keys:
            - reference: "LibraryId/ElementId" (from generate_object_repository)
            - content_hash: ContentHash string
            - guid: Fixed GUID (must match Object Repository entry)
        scope_selector: Optional window/app selector for ScopeSelectorArgument.
            Required for SAP selectors (<sap id='...'/>)  inside NApplicationCard —
            without it, UiPath can't resolve which application the element belongs to.
            Example: "<wnd app='saplogon.exe' cls='SAP_FRONTEND_SESSION' />"
    """
    selector = _normalize_selector_quotes(selector)
    escaped = _escape_xml_attr(selector)
    guid = obj_repo["guid"] if obj_repo else _uuid()
    extra_attrs = ""
    if obj_repo:
        ch = obj_repo.get("content_hash", "")
        ref = obj_repo.get("reference", "")
        if ch:
            extra_attrs += f' ContentHash="{ch}"'
        if ref:
            extra_attrs += f' Reference="{ref}"'
    scope_attr = ""
    if scope_selector:
        scope_sel = _normalize_selector_quotes(scope_selector)
        scope_attr = f' ScopeSelectorArgument="{_escape_xml_attr(scope_sel)}"'
    return f'<uix:TargetAnchorable{extra_attrs} ElementVisibilityArgument="Interactive" FullSelectorArgument="{escaped}" Guid="{guid}"{scope_attr} SearchSteps="Selector" Version="V6" WaitForReadyArgument="Interactive" />'


def _viewstate_block(id_ref: str, is_expanded: bool = True) -> str:
    lines = ['<sap:WorkflowViewStateService.ViewState>',
             '  <scg:Dictionary x:TypeArguments="x:String, x:Object">',
             f'    <x:Boolean x:Key="IsExpanded">{str(is_expanded)}</x:Boolean>',
             '  </scg:Dictionary>', '</sap:WorkflowViewStateService.ViewState>']
    return "\n".join(lines)


def _ocr_engine_block(i2, i3, i4, i5):
    return f"""{i2}<uix:NApplicationCard.OCREngine>
{i3}<ActivityFunc x:TypeArguments="sd:Image, scg:IEnumerable(scg:KeyValuePair(sd1:Rectangle, x:String))">
{i4}<ActivityFunc.Argument>
{i5}<DelegateInArgument x:TypeArguments="sd:Image" Name="Image" />
{i4}</ActivityFunc.Argument>
{i3}</ActivityFunc>
{i2}</uix:NApplicationCard.OCREngine>"""


def _target_app_empty(i2, i3, i4, i5):
    return f"""{i2}<uix:NApplicationCard.TargetApp>
{i3}<uix:TargetApp Area="0, 0, 0, 0">
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
{i2}</uix:NApplicationCard.TargetApp>"""


def _target_app_with_selector(selector, i2, i3, i4, i5):
    """TargetApp block with a window selector for desktop attach/close."""
    sel = _normalize_selector_quotes(selector)
    esc_sel = _escape_xml_attr(sel)
    return f"""{i2}<uix:NApplicationCard.TargetApp>
{i3}<uix:TargetApp Area="0, 0, 0, 0" Selector="{esc_sel}">
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
{i2}</uix:NApplicationCard.TargetApp>"""


def _body_block(body_content, body_seq_idref, i2, i3, i4, i5):
    # NOTE: Do NOT add _viewstate_block here. The body_content passed by the caller
    # already contains its own ViewState block. Adding one here causes
    # XamlDuplicateMemberException: 'ViewState' property has already been set on 'Sequence'.
    return f"""{i2}<uix:NApplicationCard.Body>
{i3}<ActivityAction x:TypeArguments="x:Object">
{i4}<ActivityAction.Argument>
{i5}<DelegateInArgument x:TypeArguments="x:Object" Name="WSSessionData" />
{i4}</ActivityAction.Argument>
{i4}<Sequence DisplayName="Do" sap2010:WorkflowViewState.IdRef="{body_seq_idref}">
{body_content}
{i4}</Sequence>
{i3}</ActivityAction>
{i2}</uix:NApplicationCard.Body>"""
