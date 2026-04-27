"""Integration activity generators — Excel, PDF, Email, Database."""
from ._helpers import _hs, _uuid, _escape_xml_attr, _escape_vb_expr
from ._xml_utils import _viewstate_block


def gen_read_range(workbook_path_variable, sheet_name, output_variable, id_ref,
                   range_str="", add_headers=True,
                   display_name="Read Range Workbook", indent="    "):
    """Generate Excel ReadRange (Classic Workbook — no Excel app needed).

    Args:
        workbook_path_variable: VB expression for file path (no brackets)
        sheet_name: Sheet name (literal string or variable). Literal: use quoted string.
        range_str: Cell range, e.g. "A1:D100". Empty = entire sheet.
        output_variable: Output DataTable variable (no brackets)
    """
    dn = _escape_xml_attr(display_name)
    i = indent
    range_attr = f'Range="{range_str}"' if range_str else 'Range="{x:Null}"'
    # Sheet can be literal or expression
    sheet = f'[{sheet_name}]' if not sheet_name.startswith('"') else f'[{sheet_name}]'

    return (
        f'{i}<ui:ReadRange {range_attr} WorkbookPathResource="{{x:Null}}" '
        f'AddHeaders="{add_headers}" DataTable="[{_escape_vb_expr(output_variable)}]" '
        f'DisplayName="{dn}" '
        f'sap2010:WorkflowViewState.IdRef="ReadRange_{id_ref}" '
        f'SheetName="{_escape_xml_attr(sheet)}" WorkbookPath="[{_escape_vb_expr(workbook_path_variable)}]" />'
    )


# ---------------------------------------------------------------------------
# WriteRange (Excel Workbook)
# ---------------------------------------------------------------------------

def gen_write_range(workbook_path_variable, sheet_name, datatable_variable, id_ref,
                    starting_cell="", display_name="Write Range Workbook",
                    indent="    "):
    """Generate Excel WriteRange (Classic Workbook).

    Args:
        starting_cell: Start cell, e.g. "A1", "B2". Empty = A1.
    """
    dn = _escape_xml_attr(display_name)
    i = indent
    cell = f'StartingCell="{starting_cell}"' if starting_cell else 'StartingCell="{x:Null}"'

    return (
        f'{i}<ui:WriteRange {cell} WorkbookPathResource="{{x:Null}}" '
        f'DataTable="[{_escape_vb_expr(datatable_variable)}]" DisplayName="{dn}" '
        f'sap2010:WorkflowViewState.IdRef="WriteRange_{id_ref}" '
        f'SheetName="{_escape_xml_attr(sheet_name)}" WorkbookPath="[{_escape_vb_expr(workbook_path_variable)}]" />'
    )


# ---------------------------------------------------------------------------
# WriteCell (Excel Workbook)
# ---------------------------------------------------------------------------

def gen_write_cell(workbook_path_variable, sheet_name, cell_expression,
                   text_variable, id_ref,
                   display_name="Write Cell", indent="    "):
    """Generate Excel WriteCell.

    Args:
        cell_expression: VB expression for cell address (no brackets),
                         e.g. '&quot;F&quot;+intRow.ToString' or '"A1"'
    """
    dn = _escape_xml_attr(display_name)
    i = indent
    return (
        f'{i}<ui:WriteCell Cell="[{_escape_xml_attr(cell_expression)}]" '
        f'DisplayName="{dn}" '
        f'sap2010:WorkflowViewState.IdRef="WriteCell_{id_ref}" '
        f'SheetName="{_escape_xml_attr(sheet_name)}" '
        f'Text="[{_escape_vb_expr(text_variable)}]" WorkbookPath="[{_escape_vb_expr(workbook_path_variable)}]" />'
    )


# ---------------------------------------------------------------------------
# AppendRange (Excel Workbook)
# ---------------------------------------------------------------------------

def gen_append_range(workbook_path_variable, sheet_name, datatable_variable, id_ref,
                     display_name="Append Range Workbook", indent="    "):
    """Generate Excel AppendRange — append DataTable rows to an existing sheet.

    Hallucination patterns prevented:
    - Using WriteCsvFile or WriteRange instead of AppendRange (different behavior)
    - Missing WorkbookPathResource="{x:Null}" (required explicit null)
    - Using StartingCell (AppendRange doesn't have it — it always appends after last row)

    Args:
        workbook_path_variable: Variable name for workbook path (no brackets)
        sheet_name: Sheet name expression — can be a variable name (no brackets)
                    or a quoted literal like '&quot;Sheet1&quot;'
        datatable_variable: DataTable variable name (no brackets)
    """
    dn = _escape_xml_attr(display_name)
    i = indent

    return (
        f'{i}<ui:AppendRange WorkbookPathResource="{{x:Null}}" '
        f'DataTable="[{_escape_vb_expr(datatable_variable)}]" DisplayName="{dn}" '
        f'{_hs("AppendRange")} '
        f'sap2010:WorkflowViewState.IdRef="AppendRange_{id_ref}" '
        f'SheetName="[{_escape_xml_attr(sheet_name)}]" WorkbookPath="[{_escape_vb_expr(workbook_path_variable)}]" />'
    )


def gen_read_pdf_text(filename_variable, output_variable, id_ref,
                      page_range="All", display_name="Read PDF Text",
                      indent="    "):
    """Generate ReadPDFText — extract text from native digital PDFs.

    Hallucination patterns prevented:
    - Wrong property name (FilePath vs FileName)
    - Wrong output property (Result vs Text)
    - Missing PreserveFormatting="{x:Null}"

    Args:
        filename_variable: VB expression for PDF path (no brackets)
        output_variable: Variable to receive extracted text (no brackets)
        page_range: "All", "1", "1-3", "1,3,5"
    """
    dn = _escape_xml_attr(display_name)
    i = indent
    return (
        f'{i}<ui:ReadPDFText PreserveFormatting="{{x:Null}}" '
        f'DisplayName="{dn}" FileName="[{_escape_vb_expr(filename_variable)}]" '
        f'{_hs("ReadPDFText")} '
        f'sap2010:WorkflowViewState.IdRef="ReadPDFText_{id_ref}" '
        f'Range="{page_range}" Text="[{_escape_vb_expr(output_variable)}]" />'
    )


# ---------------------------------------------------------------------------
# ReadPDFWithOCR (scanned/image PDFs)
# ---------------------------------------------------------------------------

def gen_read_pdf_with_ocr(filename_variable, output_variable, id_ref,
                           page_range="All", image_dpi=150,
                           display_name="Read PDF With OCR", indent="    "):
    """Generate ReadPDFWithOCR — extract text from scanned PDFs using Tesseract OCR.

    Hallucination patterns prevented:
    - Missing ActivityFunc delegate with exact TypeArguments
    - Missing DelegateInArgument for Image
    - Wrong OCR engine element (must be ui:GoogleOCR even for Tesseract)
    - Missing System.Drawing namespaces (sd: and sd1:)
    - Wrong Image binding (must reference delegate arg name)
    - Adding custom OCR engine types that don't exist

    Requires namespaces:
        xmlns:sd="clr-namespace:System.Drawing;assembly=System.Drawing.Common"
        xmlns:sd1="clr-namespace:System.Drawing;assembly=System.Drawing.Primitives"
    Also requires packages: UiPath.PDF.Activities AND UiPath.UIAutomation.Activities

    Args:
        filename_variable: VB expression for PDF path (no brackets)
        output_variable: Variable to receive extracted text (no brackets)
        image_dpi: DPI for rendering pages (150 = fast, 300 = accurate)
    """
    dn = _escape_xml_attr(display_name)
    i, i2, i3, i4, i5 = (indent, indent+"  ", indent+"    ",
                           indent+"      ", indent+"        ")

    return f"""{i}<ui:ReadPDFWithOCR DegreeOfParallelism="-1" DisplayName="{dn}" FileName="[{_escape_vb_expr(filename_variable)}]" {_hs("ReadPDFWithOCR")} sap2010:WorkflowViewState.IdRef="ReadPDFWithOCR_{id_ref}" ImageDpi="{image_dpi}" Range="{page_range}" Text="[{_escape_vb_expr(output_variable)}]">
{i2}<ui:ReadPDFWithOCR.OCREngine>
{i3}<ActivityFunc x:TypeArguments="sd:Image, scg:IEnumerable(scg:KeyValuePair(sd1:Rectangle, x:String))">
{i4}<ActivityFunc.Argument>
{i5}<DelegateInArgument x:TypeArguments="sd:Image" Name="Image" />
{i4}</ActivityFunc.Argument>
{i4}<ui:GoogleOCR AllowedCharacters="{{x:Null}}" DeniedCharacters="{{x:Null}}" FilterRegion="{{x:Null}}" Invert="{{x:Null}}" Language="{{x:Null}}" Output="{{x:Null}}" Text="{{x:Null}}" ComputeSkewAngle="False" DisplayName="Tesseract OCR" ExtractWords="False" sap2010:WorkflowViewState.IdRef="GoogleOCR_{id_ref}" Image="[Image]" Profile="None" Scale="0" />
{i3}</ActivityFunc>
{i2}</ui:ReadPDFWithOCR.OCREngine>
{i}</ui:ReadPDFWithOCR>"""


# ---------------------------------------------------------------------------
# SendMail (Integration Service SMTP)
# ---------------------------------------------------------------------------

def gen_send_mail(to_variable, subject_variable, body_variable, id_ref,
                  cc_variable="", bcc_variable="",
                  is_body_html=False,
                  attachments_variable="",
                  display_name="Send SMTP Email", indent="    "):
    """Generate SendMail — send email via Integration Service.

    Hallucination patterns prevented:
    - Missing ~15 {x:Null} properties
    - Missing AttachmentsBackup boilerplate (BackupSlot with umame:AttachmentInputMode)
    - Missing ConnectionDetailsBackupSlot boilerplate (BackupSlot with umae:ConnectionDetails)
    - Missing Files child element (scg:List even when empty)
    - Using Outlook activities instead of Integration Service
    - Wrong ConnectionMode (must be "IntegrationService")
    - Wrong property names (Recipients vs To, Content vs Body)

    Requires namespaces:
        xmlns:umae="clr-namespace:UiPath.Mail.Activities.Enums;assembly=UiPath.Mail.Activities"
        xmlns:umame="clr-namespace:UiPath.MicrosoftOffice365.Activities.Mail.Enums;assembly=UiPath.Mail.Activities"
        xmlns:usau="clr-namespace:UiPath.Shared.Activities.Utils;assembly=UiPath.Mail.Activities"
    Also requires package: UiPath.Mail.Activities

    Args:
        to_variable: VB expression for recipient (no brackets), e.g. "strRecipient"
        subject_variable: VB expression for subject (no brackets)
        body_variable: VB expression for body (no brackets)
        cc_variable: VB expression for CC (optional, empty for {x:Null})
        bcc_variable: VB expression for BCC (optional, empty for {x:Null})
        is_body_html: True for HTML body content
        attachments_variable: VB expression for String[] of file paths (optional)
    """
    dn = _escape_xml_attr(display_name)
    i, i2, i3, i4, i5 = (indent, indent+"  ", indent+"    ",
                           indent+"      ", indent+"        ")

    cc = f'Cc="[{_escape_vb_expr(cc_variable)}]"' if cc_variable else 'Cc="{x:Null}"'
    bcc = f'Bcc="[{_escape_vb_expr(bcc_variable)}]"' if bcc_variable else 'Bcc="{x:Null}"'
    attach = f'ResourceAttachments="[{_escape_vb_expr(attachments_variable)}]"' if attachments_variable else 'ResourceAttachments="{x:Null}"'

    return f"""{i}<ui:SendMail {bcc} {cc} ContinueOnError="{{x:Null}}" Email="{{x:Null}}" From="{{x:Null}}" IgnoreCRL="{{x:Null}}" MailMessage="{{x:Null}}" Name="{{x:Null}}" Password="{{x:Null}}" Port="{{x:Null}}" ReplyTo="{{x:Null}}" ResourceAttachmentList="{{x:Null}}" Result="{{x:Null}}" SecurePassword="{{x:Null}}" Server="{{x:Null}}" TimeoutMS="{{x:Null}}" UseOAuth="{{x:Null}}" AttachmentInputMode="Existing" Body="[{_escape_vb_expr(body_variable)}]" ConnectionMode="IntegrationService" DisplayName="{dn}" EnableSSL="True" IsBodyHtml="{is_body_html}" {attach} SecureConnection="Auto" Subject="[{_escape_vb_expr(subject_variable)}]" To="[{_escape_vb_expr(to_variable)}]" UseISConnection="True" UseRichTextEditor="True" sap2010:WorkflowViewState.IdRef="SendMail_{id_ref}">
{i2}<ui:SendMail.AttachmentsBackup>
{i3}<usau:BackupSlot x:TypeArguments="umame:AttachmentInputMode" StoredValue="Existing">
{i4}<usau:BackupSlot.BackupValues>
{i5}<scg:Dictionary x:TypeArguments="umame:AttachmentInputMode, scg:List(x:Object)" />
{i4}</usau:BackupSlot.BackupValues>
{i3}</usau:BackupSlot>
{i2}</ui:SendMail.AttachmentsBackup>
{i2}<ui:SendMail.ConnectionDetailsBackupSlot>
{i3}<usau:BackupSlot x:TypeArguments="umae:ConnectionDetails" StoredValue="IntegrationService">
{i4}<usau:BackupSlot.BackupValues>
{i5}<scg:List x:TypeArguments="x:Object" x:Key="IntegrationService" Capacity="1">
{i5}  <x:Null />
{i5}</scg:List>
{i5}<scg:List x:TypeArguments="x:Object" x:Key="LegacyConfiguration" Capacity="7">
{i5}  <x:Null /><x:Null /><x:Null /><x:Null /><x:Null /><x:Null />
{i5}  <p:InArgument x:TypeArguments="x:Boolean">False</p:InArgument>
{i5}</scg:List>
{i4}</usau:BackupSlot.BackupValues>
{i3}</usau:BackupSlot>
{i2}</ui:SendMail.ConnectionDetailsBackupSlot>
{i2}<ui:SendMail.Files>
{i3}<scg:List x:TypeArguments="p:InArgument(x:String)" Capacity="0" />
{i2}</ui:SendMail.Files>
{i}</ui:SendMail>"""


def gen_get_imap_mail(messages_variable, id_ref,
                      filter_expression_variable="",
                      mail_folder="Inbox", top=30,
                      only_unread=True, order_by_date="NewestFirst",
                      display_name="Get IMAP Email List", indent="    "):
    """Generate GetIMAPMailMessages — retrieve emails via Integration Service.

    Hallucination patterns prevented:
    - Missing ~12 {x:Null} properties
    - Missing ConnectionDetailsBackupSlot boilerplate
    - Wrong ConnectionMode (must be IntegrationService + UseISConnection=True)
    - Missing FilterExpressionCharacterSet
    - Wrong output type (must be List(MailMessage))

    Requires namespaces:
        xmlns:umae="clr-namespace:UiPath.Mail.Activities.Enums;assembly=UiPath.Mail.Activities"
        xmlns:usau="clr-namespace:UiPath.Shared.Activities.Utils;assembly=UiPath.Mail.Activities"
    Requires variable: <Variable x:TypeArguments="scg:List(snm:MailMessage)" Name="{messages_variable}" />
    Requires xmlns:snm="clr-namespace:System.Net.Mail;assembly=System.Net.Mail"

    Args:
        messages_variable: Output variable for List(MailMessage) (no brackets)
        filter_expression_variable: VB expression for IMAP filter (no brackets), or empty
        mail_folder: IMAP folder name
        top: Max emails to retrieve
        only_unread: Filter to unread only
        order_by_date: "NewestFirst" or "OldestFirst"
    """
    if not (order_by_date in ("NewestFirst", "OldestFirst")):
        raise ValueError(f"Invalid OrderByDate: {order_by_date}")

    dn = _escape_xml_attr(display_name)
    i, i2, i3, i4, i5 = indent, indent+"  ", indent+"    ", indent+"      ", indent+"        "

    filter_attr = f'FilterExpression="[{_escape_vb_expr(filter_expression_variable)}]"' if filter_expression_variable else 'FilterExpression="{x:Null}"'

    return f"""{i}<ui:GetIMAPMailMessages ClientName="{{x:Null}}" ClientVersion="{{x:Null}}" DeleteMessages="{{x:Null}}" Email="{{x:Null}}" MarkAsRead="{{x:Null}}" Password="{{x:Null}}" Port="{{x:Null}}" SecurePassword="{{x:Null}}" Server="{{x:Null}}" TimeoutMS="{{x:Null}}" UseOAuth="{{x:Null}}" ConnectionMode="IntegrationService" DisplayName="{dn}" EnableSSL="True" {filter_attr} FilterExpressionCharacterSet="US-ASCII" IgnoreCRL="False" MailFolder="{_escape_xml_attr(mail_folder)}" Messages="[{_escape_vb_expr(messages_variable)}]" OnlyUnreadMessages="{only_unread}" OrderByDate="{order_by_date}" SecureConnection="Auto" Top="{top}" UseISConnection="True" sap2010:WorkflowViewState.IdRef="GetIMAPMailMessages_{id_ref}">
{i2}<ui:GetIMAPMailMessages.ConnectionDetailsBackupSlot>
{i3}<usau:BackupSlot x:TypeArguments="umae:ConnectionDetails" StoredValue="IntegrationService">
{i4}<usau:BackupSlot.BackupValues>
{i5}<scg:Dictionary x:TypeArguments="umae:ConnectionDetails, scg:List(x:Object)" />
{i4}</usau:BackupSlot.BackupValues>
{i3}</usau:BackupSlot>
{i2}</ui:GetIMAPMailMessages.ConnectionDetailsBackupSlot>
{i}</ui:GetIMAPMailMessages>"""


# ---------------------------------------------------------------------------
# SaveMailAttachments
# ---------------------------------------------------------------------------

def gen_save_mail_attachments(message_variable, folder_path_variable, id_ref,
                              attachments_variable="",
                              file_filter="*.*",
                              overwrite=True,
                              display_name="Save Mail Attachments", indent="    "):
    """Generate SaveMailAttachments — save email attachments to disk.

    Hallucination patterns prevented:
    - Wrong Attachments type (must be IEnumerable(x:String), NOT List(String))
    - Using InvokeCode with FileStream (wrong approach entirely)
    - Missing ResourceAttachments={x:Null}

    Requires variable (if using attachments output):
        <Variable x:TypeArguments="scg:IEnumerable(x:String)" Name="{attachments_variable}" />

    Args:
        message_variable: MailMessage variable (no brackets)
        folder_path_variable: Destination folder (no brackets)
        attachments_variable: Optional output for saved file paths (no brackets)
        file_filter: Wildcard filter, e.g. "*.pdf", "*.xlsx", "*.*"
    """
    dn = _escape_xml_attr(display_name)
    i = indent

    attach = f'Attachments="[{_escape_vb_expr(attachments_variable)}]"' if attachments_variable else 'Attachments="{x:Null}"'

    return (
        f'{i}<ui:SaveMailAttachments ResourceAttachments="{{x:Null}}" '
        f'{attach} '
        f'DisplayName="{dn}" '
        f'ExcludeInlineAttachments="False" '
        f'Filter="{_escape_xml_attr(file_filter)}" '
        f'FolderPath="[{_escape_vb_expr(folder_path_variable)}]" '
        f'Message="[{_escape_vb_expr(message_variable)}]" '
        f'OverwriteExisting="{overwrite}" '
        f'sap2010:WorkflowViewState.IdRef="SaveMailAttachments_{id_ref}" />'
    )


# ---------------------------------------------------------------------------
# DatabaseConnect
# ---------------------------------------------------------------------------

def gen_database_connect(connection_variable, output_variable, id_ref,
                         provider="Microsoft.Data.SqlClient",
                         display_name="Connect to Database", indent="    "):
    """Generate DatabaseConnect.

    Hallucination patterns prevented:
    - Using ConnectionString instead of ConnectionSecureString
    - Wrong provider names

    Args:
        connection_variable: SecureString variable for connection string (no brackets)
        output_variable: DatabaseConnection output variable (no brackets)
        provider: "Microsoft.Data.SqlClient", "System.Data.Odbc", "Oracle.ManagedDataAccess.Client"
    """
    dn = _escape_xml_attr(display_name)
    i = indent
    return (
        f'{i}<ui:DatabaseConnect DisplayName="{dn}" '
        f'ProviderName="{provider}" '
        f'ConnectionSecureString="[{_escape_vb_expr(connection_variable)}]" '
        f'DatabaseConnection="[{_escape_vb_expr(output_variable)}]" '
        f'sap2010:WorkflowViewState.IdRef="DatabaseConnect_{id_ref}" />'
    )


# ---------------------------------------------------------------------------
# ExecuteQuery (SELECT → DataTable)
# ---------------------------------------------------------------------------

def gen_execute_query(sql, output_variable, id_ref, connection_variable="",
                      connection_string_variable="",
                      provider="Microsoft.Data.SqlClient",
                      parameters=None,
                      display_name="Run Query", indent="    "):
    """Generate ExecuteQuery — parameterized SELECT.

    Hallucination patterns prevented:
    - Missing parameter dictionary structure
    - Inline SQL values instead of @paramName parameters (SQL injection)
    - Mixing ExistingDbConnection and ConnectionSecureString

    Args:
        sql: SQL query with @paramName placeholders
        parameters: Dict of {param_name: (type, variable)},
                    e.g. {"status": ("x:String", "strStatus")}
        connection_variable: ExistingDbConnection variable (from DatabaseConnect)
        connection_string_variable: Or direct SecureString (mutually exclusive)
    """
    dn = _escape_xml_attr(display_name)
    sql_esc = _escape_xml_attr(sql)
    i, i2, i3 = indent, indent+"  ", indent+"    "

    conn = f'ExistingDbConnection="[{_escape_vb_expr(connection_variable)}]" ConnectionSecureString="{{x:Null}}"' if connection_variable else \
           f'ExistingDbConnection="{{x:Null}}" ConnectionSecureString="[{_escape_vb_expr(connection_string_variable)}]"'

    if parameters:
        param_lines = []
        for key, (ptype, pvar) in parameters.items():
            param_lines.append(
                f'{i3}<InArgument x:TypeArguments="{ptype}" x:Key="{key}">[{pvar}]</InArgument>'
            )
        params_xml = "\n".join(param_lines)
        return f"""{i}<ui:ExecuteQuery ContinueOnError="{{x:Null}}" {conn} TimeoutMS="{{x:Null}}" DataTable="[{_escape_vb_expr(output_variable)}]" DisplayName="{dn}" ProviderName="{provider}" Sql="{sql_esc}" sap2010:WorkflowViewState.IdRef="ExecuteQuery_{id_ref}">
{i2}<ui:ExecuteQuery.Parameters>
{i3}<scg:Dictionary x:TypeArguments="x:String, p:Argument">
{params_xml}
{i3}</scg:Dictionary>
{i2}</ui:ExecuteQuery.Parameters>
{i}</ui:ExecuteQuery>"""
    else:
        return (
            f'{i}<ui:ExecuteQuery ContinueOnError="{{x:Null}}" {conn} TimeoutMS="{{x:Null}}" '
            f'DataTable="[{_escape_vb_expr(output_variable)}]" DisplayName="{dn}" '
            f'ProviderName="{provider}" Sql="{sql_esc}" '
            f'sap2010:WorkflowViewState.IdRef="ExecuteQuery_{id_ref}" />'
        )


# ---------------------------------------------------------------------------
# ExecuteNonQuery (INSERT/UPDATE/DELETE)
# ---------------------------------------------------------------------------

def gen_execute_non_query(sql, id_ref, connection_variable="",
                          connection_string_variable="",
                          provider="Microsoft.Data.SqlClient",
                          parameters=None, affected_records_variable="",
                          display_name="Run Command", indent="    "):
    """Generate ExecuteNonQuery — parameterized INSERT/UPDATE/DELETE.

    Args:
        sql: SQL statement with @paramName placeholders
        parameters: Dict of {param_name: (type, variable)}
        affected_records_variable: Optional Int32 variable for rows affected
    """
    dn = _escape_xml_attr(display_name)
    sql_esc = _escape_xml_attr(sql)
    i, i2, i3 = indent, indent+"  ", indent+"    "

    conn = f'ExistingDbConnection="[{_escape_vb_expr(connection_variable)}]"' if connection_variable else \
           f'ConnectionSecureString="[{_escape_vb_expr(connection_string_variable)}]"'
    affected = f'AffectedRecords="[{_escape_vb_expr(affected_records_variable)}]"' if affected_records_variable else 'AffectedRecords="{x:Null}"'

    if parameters:
        param_lines = []
        for key, (ptype, pvar) in parameters.items():
            param_lines.append(
                f'{i3}<InArgument x:TypeArguments="{ptype}" x:Key="{key}">[{pvar}]</InArgument>'
            )
        params_xml = "\n".join(param_lines)
        return f"""{i}<ui:ExecuteNonQuery {affected} ContinueOnError="{{x:Null}}" TimeoutMS="{{x:Null}}" DisplayName="{dn}" {conn} Sql="{sql_esc}" sap2010:WorkflowViewState.IdRef="ExecuteNonQuery_{id_ref}">
{i2}<ui:ExecuteNonQuery.Parameters>
{i3}<scg:Dictionary x:TypeArguments="x:String, p:Argument">
{params_xml}
{i3}</scg:Dictionary>
{i2}</ui:ExecuteNonQuery.Parameters>
{i}</ui:ExecuteNonQuery>"""
    else:
        return (
            f'{i}<ui:ExecuteNonQuery {affected} ContinueOnError="{{x:Null}}" TimeoutMS="{{x:Null}}" '
            f'DisplayName="{dn}" {conn} Sql="{sql_esc}" '
            f'sap2010:WorkflowViewState.IdRef="ExecuteNonQuery_{id_ref}" />'
        )
