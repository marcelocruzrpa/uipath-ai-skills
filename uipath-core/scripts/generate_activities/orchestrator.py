"""Orchestrator activity generators."""
from ._helpers import _hs, _uuid, _escape_xml_attr, _escape_vb_expr
from ._xml_utils import _viewstate_block
from .error_handling import gen_retryscope


def gen_add_queue_item(queue_name_config, id_ref, item_fields=None,
                       reference_variable="", folder_path_config="",
                       priority="Normal", display_name="Add Queue Item",
                       number_of_retries=3,
                       indent="    "):
    """Generate AddQueueItem wrapped in RetryScope (Rule 13: API calls must be retried).

    CRITICAL hallucination patterns this generator prevents:
    - .DictionaryCollection (doesn't exist → use .ItemInformation)
    - scg:Dictionary wrapper around InArguments (not needed — bare InArgument children)
    - ui:Argument / ui:InArgument (wrong namespace → use plain InArgument)
    - x:String elements instead of InArgument (wrong element type)
    - QueueName property (doesn't exist → use QueueType)
    - Missing RetryScope (API call without retry = transient failure crash)

    Args:
        queue_name_config: VB expression for queue name, e.g. 'in_Config("OrchestratorQueueName").ToString'
        id_ref: Base IdRef — generates AddQueueItem_{id_ref}, RetryScope_{id_ref}, Sequence_{id_ref}
        item_fields: Dict of {field_name: vb_expression}, e.g. {"WIID": "strWIID", "Description": "strDesc"}
                     All values are wrapped in [brackets] and typed as x:String
        reference_variable: Variable for unique reference (no brackets), e.g. "strReference"
        folder_path_config: VB expression for folder, or empty for {x:Null}
        priority: "Normal", "High", or "Low"
        number_of_retries: RetryScope retry count (default 3)
    """
    if not (priority in ("Normal", "High", "Low")):
        raise ValueError(f"Invalid Priority: {priority}")

    dn = _escape_xml_attr(display_name)
    # Inner indent is deeper because it sits inside RetryScope > Sequence
    ii = indent + "        "  # 8 extra spaces inside retry body
    ii2 = ii + "  "
    ii3 = ii + "    "

    folder = f'FolderPath="[{_escape_xml_attr(folder_path_config)}]"' if folder_path_config else 'FolderPath="{x:Null}"'
    ref = f'Reference="[{_escape_vb_expr(reference_variable)}]"' if reference_variable else ""
    queue = f'QueueType="[{_escape_xml_attr(queue_name_config)}]"'

    # ItemInformation children — bare InArgument elements, NO Dictionary wrapper
    # Defensive: accept both dict and list-of-tuples/lists
    if item_fields and not isinstance(item_fields, dict):
        item_fields = dict(item_fields)
    item_lines = []
    if item_fields:
        for key, expr in item_fields.items():
            item_lines.append(
                f'{ii3}<InArgument x:TypeArguments="x:String" x:Key="{_escape_xml_attr(key)}">[{_escape_vb_expr(expr)}]</InArgument>'
            )

    items_block = ""
    if item_lines:
        items_xml = "\n".join(item_lines)
        items_block = f"""
{ii2}<ui:AddQueueItem.ItemInformation>
{items_xml}
{ii2}</ui:AddQueueItem.ItemInformation>"""

    ref_attr = f' {ref}' if ref else ""

    add_queue_xml = f"""{ii}<ui:AddQueueItem ServiceBaseAddress="{{x:Null}}" TimeoutMS="{{x:Null}}" DisplayName="{dn}" {folder} {_hs("AddQueueItem")} sap2010:WorkflowViewState.IdRef="AddQueueItem_{id_ref}" Priority="{priority}" {queue}{ref_attr}>{items_block}
{ii}</ui:AddQueueItem>"""

    return gen_retryscope(
        display_name=f"Retry - {display_name}",
        id_ref=f"RetryScope_{id_ref}",
        body_content=add_queue_xml,
        body_sequence_idref=f"Sequence_Retry_{id_ref}",
        number_of_retries=number_of_retries,
        indent=indent,
    )


# ---------------------------------------------------------------------------
# BulkAddQueueItems
# ---------------------------------------------------------------------------

def gen_bulk_add_queue_items(queue_name, datatable_variable, id_ref,
                             display_name="Bulk Add Queue Items",
                             number_of_retries=3,
                             indent="    "):
    """Generate BulkAddQueueItems wrapped in RetryScope — bulk-add a DataTable to a queue.

    Hallucination patterns prevented:
    - Using QueueName instead of QueueName (correct prop name, but model often uses QueueType
      from AddQueueItem — BulkAddQueueItems uses QueueName)
    - Using DataTable instead of QueueItemsDataTable
    - Missing TimeoutMS="{x:Null}" explicit null
    - Missing RetryScope wrapper (Orchestrator API call)

    Args:
        queue_name: Variable or expression for queue name (no brackets),
                    e.g. 'in_Config("OrchestratorQueueName").ToString' or 'strQueueName'
        datatable_variable: DataTable variable name (no brackets)
    """
    dn = _escape_xml_attr(display_name)
    ii = indent + "        "  # inside RetryScope > Sequence

    bulk_xml = (
        f'{ii}<ui:BulkAddQueueItems TimeoutMS="{{x:Null}}" '
        f'DisplayName="{dn}" '
        f'{_hs("BulkAddQueueItems")} '
        f'sap2010:WorkflowViewState.IdRef="BulkAddQueueItems_{id_ref}" '
        f'QueueItemsDataTable="[{_escape_vb_expr(datatable_variable)}]" '
        f'QueueName="[{_escape_vb_expr(queue_name)}]" />'
    )

    return gen_retryscope(
        display_name=f"Retry - {display_name}",
        id_ref=f"RetryScope_{id_ref}",
        body_content=bulk_xml,
        body_sequence_idref=f"Sequence_Retry_{id_ref}",
        number_of_retries=number_of_retries,
        indent=indent,
    )


def gen_get_queue_item(queue_name_config, transaction_item_variable, id_ref,
                       folder_path_config="",
                       display_name="Get transaction item",
                       number_of_retries=3,
                       indent="    "):
    """Generate GetQueueItem wrapped in RetryScope (Rule 13).

    Hallucination patterns prevented:
    - QueueName property (doesn't exist → use QueueType, same as AddQueueItem)
    - Missing .Reference and .TimeoutMS child elements (even when empty)
    - Wrong TransactionItem type (must be ui:QueueItem)
    - Missing RetryScope wrapper

    Note: REFramework's GetTransactionData.xaml already handles this.
    Only use this generator for custom queue retrieval outside REFramework.

    Requires variable: <Variable x:TypeArguments="ui:QueueItem" Name="{transaction_item_variable}" />

    Args:
        queue_name_config: VB expression for queue name
        transaction_item_variable: Output variable name (no brackets)
        id_ref: Base IdRef number
        folder_path_config: VB expression for folder, or empty for {x:Null}
    """
    dn = _escape_xml_attr(display_name)
    ii = indent + "        "  # inside RetryScope body
    ii2 = ii + "  "
    ii3 = ii + "    "

    folder = f'FolderPath="[{_escape_xml_attr(folder_path_config)}]"' if folder_path_config else 'FolderPath="{x:Null}"'
    queue = f'QueueType="[{_escape_xml_attr(queue_name_config)}]"'

    get_xml = f"""{ii}<ui:GetQueueItem ContinueOnError="{{x:Null}}" DisplayName="{dn}" {folder} {_hs("GetQueueItem")} sap2010:WorkflowViewState.IdRef="GetQueueItem_{id_ref}" {queue} TransactionItem="[{_escape_vb_expr(transaction_item_variable)}]">
{ii2}<ui:GetQueueItem.Reference>
{ii3}<InArgument x:TypeArguments="x:String" />
{ii2}</ui:GetQueueItem.Reference>
{ii2}<ui:GetQueueItem.TimeoutMS>
{ii3}<InArgument x:TypeArguments="x:Int32" />
{ii2}</ui:GetQueueItem.TimeoutMS>
{ii}</ui:GetQueueItem>"""

    return gen_retryscope(
        display_name=f"Retry - {display_name}",
        id_ref=f"RetryScope_{id_ref}",
        body_content=get_xml,
        body_sequence_idref=f"Sequence_Retry_{id_ref}",
        number_of_retries=number_of_retries,
        indent=indent,
    )


def gen_getrobotcredential(asset_name_variable, username_variable, password_variable,
                           id_ref, display_name="Get Credential", indent="            "):
    hs = _hs("GetRobotCredential")
    dn = _escape_xml_attr(display_name)
    i = indent
    return f'{i}<ui:GetRobotCredential TimeoutMS="{{x:Null}}" AssetName="[{_escape_vb_expr(asset_name_variable)}]" CacheStrategy="None" DisplayName="{dn}" {hs} sap2010:WorkflowViewState.IdRef="{id_ref}" Password="[{_escape_vb_expr(password_variable)}]" Username="[{_escape_vb_expr(username_variable)}]" />'


def gen_get_robot_asset(asset_name, output_variable, id_ref,
                        output_type="x:String", cache_strategy="None",
                        display_name="",
                        number_of_retries=3,
                        indent="    "):
    """Generate GetRobotAsset wrapped in RetryScope (Rule 13).

    Hallucination patterns prevented:
    - Using Result property (doesn't exist → use .Value element syntax)
    - Using VB expression for AssetName (must be string literal)
    - Missing RetryScope wrapper

    Args:
        asset_name: Orchestrator asset name (string literal, NOT variable)
        output_variable: Variable name (no brackets)
        output_type: "x:String", "x:Int32", "x:Boolean"
        cache_strategy: "None", "PerRobot", "Global"
    """
    if not display_name:
        display_name = f"Get Asset - {asset_name}"
    dn = _escape_xml_attr(display_name)
    an = _escape_xml_attr(asset_name)
    ii = indent + "        "
    ii2 = ii + "  "
    ii3 = ii + "    "

    asset_xml = f"""{ii}<ui:GetRobotAsset TimeoutMS="{{x:Null}}" AssetName="{an}" CacheStrategy="{cache_strategy}" DisplayName="{dn}" sap2010:WorkflowViewState.IdRef="GetRobotAsset_{id_ref}">
{ii2}<ui:GetRobotAsset.Value>
{ii3}<OutArgument x:TypeArguments="{output_type}">[{output_variable}]</OutArgument>
{ii2}</ui:GetRobotAsset.Value>
{ii}</ui:GetRobotAsset>"""

    return gen_retryscope(
        display_name=f"Retry - {display_name}",
        id_ref=f"RetryScope_{id_ref}",
        body_content=asset_xml,
        body_sequence_idref=f"Sequence_Retry_{id_ref}",
        number_of_retries=number_of_retries,
        indent=indent,
    )


