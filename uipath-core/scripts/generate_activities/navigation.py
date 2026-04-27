"""Navigation and data extraction generators."""
from ._helpers import _hs, _uuid, _escape_xml_attr, _escape_vb_expr
from ._xml_utils import _selector_xml, _viewstate_block


def gen_ngotourl(url_variable, id_ref, scope_id, display_name="Go To URL", indent="            "):
    hs = _hs("NGoToUrl")
    dn = _escape_xml_attr(display_name)
    i, i2 = indent, indent+"  "
    return f"""{i}<uix:NGoToUrl DisplayName="{dn}" {hs} sap2010:WorkflowViewState.IdRef="{id_ref}" ScopeIdentifier="{scope_id}" Url="[{_escape_vb_expr(url_variable)}]" Version="V3">
{i2}{_viewstate_block(id_ref, is_expanded=True)}
{i}</uix:NGoToUrl>"""


def gen_ngeturl(output_variable, id_ref, display_name="Get URL", indent="    "):
    """Generate NGetUrl — get current browser URL.

    Must be inside an NApplicationCard scope.
    """
    dn = _escape_xml_attr(display_name)
    i = indent
    return (
        f'{i}<uix:NGetUrl CurrentUrl="[{_escape_vb_expr(output_variable)}]" DisplayName="{dn}" '
        f'sap2010:WorkflowViewState.IdRef="NGetUrl_{id_ref}" Version="V4" />'
    )


def gen_nextractdata(display_name, output_variable, id_ref, scope_id,
                     extract_data_settings="", extract_metadata="",
                     table_selector="", next_link_selector="",
                     scope_selector="", max_results=0,
                     limit_extraction_to="None",
                     indent="            "):
    """Generate NExtractDataGeneric — the most hallucination-prone activity.

    CRITICAL: The real activity is NExtractDataGeneric (NOT NExtractData).
    It uses x:TypeArguments="sd2:DataTable" and backtick IdRef notation.
    ExtractDataSettings and ExtractMetadata are XML-encoded STRING ATTRIBUTES,
    NOT child elements. There is NO NExtractMetadata or NExtractColumn type.

    Args:
        display_name: e.g. "Extract Data 'Work Items'"
        output_variable: DataTable variable (no brackets), e.g. "dt_WorkItems"
        id_ref: Unique suffix, e.g. "1" → becomes "NExtractDataGeneric`1_1"
        scope_id: Parent NApplicationCard ScopeGuid
        extract_data_settings: XML-encoded column schema (from Studio export or built manually)
        extract_metadata: XML-encoded row/column selectors
        table_selector: FullSelector for the table/list element
        next_link_selector: FullSelector for pagination "Next" link (empty = no pagination)
        scope_selector: Scope selector (e.g. "<html app='msedge.exe' title='...' />")
        max_results: 0 = unlimited
        limit_extraction_to: "None" (all pages) or "CurrentPage"
    """
    from ._helpers import _normalize_selector_quotes

    if not (limit_extraction_to in ("None", "CurrentPage")):
        raise ValueError(f"Invalid LimitExtractionTo: {limit_extraction_to}")
    if not (extract_metadata):
        raise ValueError("extract_metadata is REQUIRED — UiPath throws 'Value for a required activity argument " "'Extract metadata' was not supplied' without it. Must contain <extract> XML with " "<row> and <column> definitions.")
    if not (extract_data_settings):
        raise ValueError("extract_data_settings is REQUIRED — must contain <Table> XML with <Column> definitions " "matching the column names in extract_metadata.")

    dn = _escape_xml_attr(display_name)
    i = indent
    i2 = indent + "  "
    i3 = indent + "    "

    # Backtick IdRef notation for generic types
    idref = f"NExtractDataGeneric`1_{id_ref}"
    guid_next = _uuid()
    guid_target = _uuid()

    # Build attribute strings
    settings_attr = f' ExtractDataSettings="{_escape_xml_attr(extract_data_settings)}"' if extract_data_settings else ""
    meta_attr = f' ExtractMetadata="{_escape_xml_attr(extract_metadata)}"' if extract_metadata else ""

    # NextLink section (pagination)
    if next_link_selector:
        esc_next = _escape_xml_attr(_normalize_selector_quotes(next_link_selector))
        esc_scope = _escape_xml_attr(_normalize_selector_quotes(scope_selector)) if scope_selector else ""
        scope_attr = f' ScopeSelectorArgument="{esc_scope}"' if esc_scope else ""
        next_link = f"""{i2}<uix:NExtractDataGeneric.NextLink>
{i3}<uix:TargetAnchorable ElementVisibilityArgument="Interactive" FullSelectorArgument="{esc_next}" Guid="{guid_next}"{scope_attr} SearchSteps="Selector" Version="V6" WaitForReadyArgument="Interactive" />
{i2}</uix:NExtractDataGeneric.NextLink>"""
    else:
        next_link = ""

    # Target section (required — the table/list element)
    if table_selector:
        esc_table = _escape_xml_attr(_normalize_selector_quotes(table_selector))
        esc_scope = _escape_xml_attr(_normalize_selector_quotes(scope_selector)) if scope_selector else ""
        scope_attr = f' ScopeSelectorArgument="{esc_scope}"' if esc_scope else ""
        target = f"""{i2}<uix:NExtractDataGeneric.Target>
{i3}<uix:TargetAnchorable ElementVisibilityArgument="Interactive" FullSelectorArgument="{esc_table}" Guid="{guid_target}"{scope_attr} SearchSteps="Selector" Version="V6" WaitForReadyArgument="Interactive" />
{i2}</uix:NExtractDataGeneric.Target>"""
    else:
        target = ""

    # Build children
    children = "\n".join(filter(None, [next_link, target]))

    if children:
        return f"""{i}<uix:NExtractDataGeneric x:TypeArguments="sd2:DataTable" ContinueOnError="True" DisplayName="{dn}"{settings_attr} ExtractedData="[{_escape_vb_expr(output_variable)}]"{meta_attr} HealingAgentBehavior="SameAsCard" sap:VirtualizedContainerService.HintSize="416,138" sap2010:WorkflowViewState.IdRef="{idref}" LimitExtractionTo="{limit_extraction_to}" MaximumResults="{max_results}" ScopeIdentifier="{scope_id}" Version="V5">
{children}
{i}</uix:NExtractDataGeneric>"""
    else:
        return f'{i}<uix:NExtractDataGeneric x:TypeArguments="sd2:DataTable" ContinueOnError="True" DisplayName="{dn}"{settings_attr} ExtractedData="[{_escape_vb_expr(output_variable)}]"{meta_attr} HealingAgentBehavior="SameAsCard" sap:VirtualizedContainerService.HintSize="416,138" sap2010:WorkflowViewState.IdRef="{idref}" LimitExtractionTo="{limit_extraction_to}" MaximumResults="{max_results}" ScopeIdentifier="{scope_id}" Version="V5" />'


def gen_pick_login_validation(
    success_selector, error_selector, error_ui_variable, error_text_variable,
    scope_id, pick_idref, success_branch_idref, failure_branch_idref,
    success_checkstate_idref, failure_checkstate_idref,
    success_if_exists_idref, success_if_not_exists_idref,
    failure_if_exists_idref, failure_if_not_exists_idref,
    success_action_idref, failure_action_idref,
    gettext_idref, throw_idref, success_log_idref,
    indent="            ",
):
    from .logging_misc import gen_logmessage
    from .error_handling import gen_throw
    from .ui_automation import gen_ngettext, gen_ncheckstate
    from ._helpers import _normalize_selector_quotes

    hs_pick = _hs("Pick")
    hs_branch = _hs("PickBranch")
    success_selector = _normalize_selector_quotes(success_selector)
    error_selector = _normalize_selector_quotes(error_selector)
    i, i2, i3, i4, i5 = indent, indent+"  ", indent+"    ", indent+"      ", indent+"        "

    success_log = gen_logmessage('&quot;Login was successful.&quot;', success_log_idref,
                                  "Log Message Login Success", indent=i5)
    gettext = gen_ngettext("Get Text (Fetch error message text)", error_text_variable,
                           gettext_idref, scope_id, in_ui_element=error_ui_variable, indent=i5)
    throw = gen_throw(
        f'new Exception(String.Format(&quot;Login failed. Reason: {{0}}&quot;, {error_text_variable}))',
        throw_idref, "Throw SE (Login failed)", indent=i5)

    success_cs = gen_ncheckstate("Check App State (Login Success Element)", success_selector,
                                 success_checkstate_idref, scope_id,
                                 success_if_exists_idref, success_if_not_exists_idref, indent=i4)
    failure_cs = gen_ncheckstate("Check App State (Login Error Msg)", error_selector,
                                 failure_checkstate_idref, scope_id,
                                 failure_if_exists_idref, failure_if_not_exists_idref,
                                 out_ui_element=error_ui_variable, indent=i4)

    return f"""{i}<Pick DisplayName="Pick (Validate login state)" {hs_pick} sap2010:WorkflowViewState.IdRef="{pick_idref}">
{i2}<PickBranch DisplayName="PickBranch (Login Success)" {hs_branch} sap2010:WorkflowViewState.IdRef="{success_branch_idref}">
{i3}<PickBranch.Trigger>
{success_cs}
{i3}</PickBranch.Trigger>
{i4}<Sequence DisplayName="Login succeeded" sap2010:WorkflowViewState.IdRef="{success_action_idref}">
{i5}{_viewstate_block(success_action_idref)}
{success_log}
{i4}</Sequence>
{i2}</PickBranch>
{i2}<PickBranch DisplayName="PickBranch (Login Failed)" {hs_branch} sap2010:WorkflowViewState.IdRef="{failure_branch_idref}">
{i3}<PickBranch.Trigger>
{failure_cs}
{i3}</PickBranch.Trigger>
{i4}<Sequence DisplayName="Login failed - get error + throw" sap2010:WorkflowViewState.IdRef="{failure_action_idref}">
{i5}{_viewstate_block(failure_action_idref)}
{gettext}
{throw}
{i4}</Sequence>
{i2}</PickBranch>
{i}</Pick>"""
