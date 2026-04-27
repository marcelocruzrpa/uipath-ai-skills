"""Regression tests for uipath-core/scripts/validate_xaml/_fixes.py.

Focus: guardrails on string replacements so longer FQDNs that share a prefix
with a FQDN_FIX entry don't get mid-consumed. The motivating bug was
`System.Object` → `x:Object` corrupting `<AssemblyReference>System.ObjectModel</AssemblyReference>`
(the Model suffix survived, leaving the unloadable `x:ObjectModel`).
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from validate_xaml._fixes import auto_fix_file
from generate_activities.ui_automation import gen_ntypeinto, gen_ngettext
from generate_activities.application_card import (
    gen_napplicationcard_open,
    gen_napplicationcard_desktop_open,
)
from generate_activities.dialogs import gen_message_box
from generate_activities.file_system import gen_delete_file, gen_write_text_file
from generate_activities.control_flow import gen_foreach, gen_foreach_row, gen_foreach_file
from generate_activities.navigation import gen_ngotourl
from generate_activities.http_json import gen_net_http_request, gen_deserialize_json
from generate_activities.data_operations import (
    gen_output_data_table,
    gen_join_data_tables,
    gen_lookup_data_table,
    gen_merge_data_table,
)
from generate_activities.integrations import (
    gen_write_cell,
    gen_send_mail,
    gen_save_mail_attachments,
    gen_database_connect,
)
from generate_activities.orchestrator import (
    gen_getrobotcredential,
    gen_bulk_add_queue_items,
)
from generate_activities.logging_misc import gen_should_stop, gen_take_screenshot_and_save


def _write_xaml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "Main.xaml"
    p.write_text(content, encoding="utf-8")
    return p


class TestLint99FqdnBoundary:
    """Lint 99 must stop at identifier boundaries so it doesn't eat longer names."""

    def test_system_objectmodel_assembly_ref_preserved(self, tmp_path):
        """<AssemblyReference>System.ObjectModel</AssemblyReference> must NOT become x:ObjectModel."""
        xaml = (
            '<Activity xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml">\n'
            '  <TextExpression.ReferencesForImplementation>\n'
            '    <AssemblyReference>System.ObjectModel</AssemblyReference>\n'
            '  </TextExpression.ReferencesForImplementation>\n'
            '</Activity>\n'
        )
        p = _write_xaml(tmp_path, xaml)
        auto_fix_file(str(p))
        out = p.read_text(encoding="utf-8")
        assert "<AssemblyReference>System.ObjectModel</AssemblyReference>" in out
        assert "x:ObjectModel" not in out

    def test_system_object_bare_still_fixed(self, tmp_path):
        """Bare `System.Object` (followed by non-identifier char) should still be rewritten."""
        xaml = (
            '<Activity xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml">\n'
            '  <Sequence>\n'
            '    <ForEach x:TypeArguments="System.Object" />\n'
            '  </Sequence>\n'
            '</Activity>\n'
        )
        p = _write_xaml(tmp_path, xaml)
        auto_fix_file(str(p))
        out = p.read_text(encoding="utf-8")
        assert 'x:TypeArguments="x:Object"' in out
        assert "System.Object" not in out

    def test_system_string_prefix_safety(self, tmp_path):
        """`System.StringBuilder` and `System.StringComparer` must survive the rewrite."""
        xaml = (
            '<Activity xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml">\n'
            '  <TextExpression.NamespacesForImplementation>\n'
            '    <x:String>System.StringBuilder</x:String>\n'
            '  </TextExpression.NamespacesForImplementation>\n'
            '</Activity>\n'
        )
        p = _write_xaml(tmp_path, xaml)
        auto_fix_file(str(p))
        out = p.read_text(encoding="utf-8")
        assert "System.StringBuilder" in out

    def test_system_int32_dot_suffix_safety(self, tmp_path):
        """`System.Int32.MaxValue` in expressions must not be chopped to `x:Int32.MaxValue`."""
        xaml = (
            '<Activity xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml">\n'
            '  <Sequence>\n'
            '    <Assign>[System.Int32.MaxValue]</Assign>\n'
            '  </Sequence>\n'
            '</Activity>\n'
        )
        p = _write_xaml(tmp_path, xaml)
        auto_fix_file(str(p))
        out = p.read_text(encoding="utf-8")
        assert "System.Int32.MaxValue" in out
        assert "x:Int32.MaxValue" not in out

    def test_system_data_datatable_preserved_precedence(self, tmp_path):
        """`System.Data.DataTable` still maps to `sd:DataTable` (longer entry wins)."""
        # dict ordering preserves insertion, so Exception runs before the Data.* entries —
        # but the Data.* entries don't overlap with Exception/String/etc., so ordering
        # within the set matters only within the Data family. This test guards the
        # DataTable mapping still fires.
        xaml = (
            '<Activity xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml">\n'
            '  <Sequence>\n'
            '    <ForEach x:TypeArguments="System.Data.DataTable" />\n'
            '  </Sequence>\n'
            '</Activity>\n'
        )
        p = _write_xaml(tmp_path, xaml)
        auto_fix_file(str(p))
        out = p.read_text(encoding="utf-8")
        assert 'x:TypeArguments="sd:DataTable"' in out


class TestVbExprQuoteEscaping:
    """Generators that emit `[expr]` from a VB-expression argument must escape
    embedded `"` to `&quot;` so the XML attribute parser does not close at the
    first inner quote. The regression: literal-with-quotes input produced
    `Text="["Hello"]"` which Studio compiled but executed as DynamicActivity
    with Implementation=null.
    """

    def test_ntypeinto_text_literal_with_quotes(self):
        out = gen_ntypeinto(
            display_name="Type",
            selector="<webctrl tag='INPUT' />",
            text_variable='"Hello"',
            id_ref="abc",
            scope_id="scope-1",
        )
        assert 'Text="[&quot;Hello&quot;]"' in out
        assert 'Text="["Hello"]"' not in out

    def test_ntypeinto_securetext_literal_with_quotes(self):
        out = gen_ntypeinto(
            display_name="Type Secret",
            selector="<webctrl tag='INPUT' />",
            text_variable='"Secret"',
            id_ref="abc",
            scope_id="scope-1",
            is_secure=True,
        )
        assert 'SecureText="[&quot;Secret&quot;]"' in out
        assert 'SecureText="["Secret"]"' not in out

    def test_ntypeinto_variable_name_unchanged(self):
        out = gen_ntypeinto(
            display_name="Type",
            selector="<webctrl tag='INPUT' />",
            text_variable="strFoo",
            id_ref="abc",
            scope_id="scope-1",
        )
        assert 'Text="[strFoo]"' in out

    def test_napplicationcard_open_url_literal_with_quotes_and_amp(self):
        out = gen_napplicationcard_open(
            display_name="Open Browser",
            url_variable='"https://x.example/?a=1&b=2"',
            out_ui_element="uiBrowser",
            scope_guid="guid-1",
            id_ref="card-1",
            body_content="",
            body_sequence_idref="seq-1",
        )
        assert 'Url="[&quot;https://x.example/?a=1&amp;b=2&quot;]"' in out
        assert '&amp;quot;' not in out  # no double-escape

    def test_napplicationcard_desktop_open_filepath_literal_with_quotes(self):
        out = gen_napplicationcard_desktop_open(
            display_name="Open App",
            file_path_variable='"C:\\Tools\\my app.exe"',
            out_ui_element="uiApp",
            scope_guid="guid-1",
            id_ref="card-1",
            body_content="",
            body_sequence_idref="seq-1",
        )
        assert 'FilePath="[&quot;C:\\Tools\\my app.exe&quot;]"' in out
        assert '&amp;quot;' not in out  # no double-escape from outer _escape_xml_attr

    def test_napplicationcard_desktop_open_filepath_variable_unchanged(self):
        out = gen_napplicationcard_desktop_open(
            display_name="Open App",
            file_path_variable="strExePath",
            out_ui_element="uiApp",
            scope_guid="guid-1",
            id_ref="card-1",
            body_content="",
            body_sequence_idref="seq-1",
        )
        assert 'FilePath="[strExePath]"' in out


class TestVbExprQuoteEscapingDefensiveSweep:
    """Defensive `_escape_vb_expr` wrap across remaining generator families.

    For each family, two cases:
    - Literal-with-quotes input must produce `&quot;...&quot;` inside `[expr]`.
    - Variable-name input must round-trip unchanged.

    `_escape_vb_expr` is idempotent for variable names, so both cases pass
    on the same wrap.
    """

    # ---- dialogs ----
    def test_message_box_text_literal_with_quotes(self):
        out = gen_message_box(text_variable='"hi"', id_ref="1")
        assert 'Text="[&quot;hi&quot;]"' in out

    # ---- file_system ----
    def test_delete_file_path_literal_with_quotes(self):
        out = gen_delete_file(path_variable='"a.txt"', id_ref="1")
        assert 'Path="[&quot;a.txt&quot;]"' in out

    def test_write_text_file_text_literal_with_quotes(self):
        out = gen_write_text_file(
            text_variable='"hello"', id_ref="1", path_variable="strPath"
        )
        assert 'Text="[&quot;hello&quot;]"' in out
        assert 'FileName="[strPath]"' in out

    # ---- control_flow ----
    def test_foreach_values_literal_with_quotes(self):
        out = gen_foreach(
            collection_variable='"items"',
            id_ref="1",
            body_content="",
            body_sequence_idref="seq",
        )
        assert 'Values="[&quot;items&quot;]"' in out

    def test_foreach_row_datatable_variable_unchanged(self):
        out = gen_foreach_row(
            datatable_variable="dtRows",
            id_ref="1",
            body_content="",
            body_sequence_idref="seq",
        )
        assert 'DataTable="[dtRows]"' in out

    def test_foreach_file_folder_literal_with_quotes(self):
        out = gen_foreach_file(
            folder_variable='"C:\\d"',
            id_ref="1",
            body_content="",
            body_sequence_idref="seq",
        )
        assert 'Folder="[&quot;C:\\d&quot;]"' in out

    # ---- navigation ----
    def test_ngotourl_literal_with_quotes_and_amp(self):
        out = gen_ngotourl(
            url_variable='"https://x.example/?a=1&b=2"',
            id_ref="1",
            scope_id="scope",
        )
        assert 'Url="[&quot;https://x.example/?a=1&amp;b=2&quot;]"' in out

    # ---- http_json ----
    def test_net_http_request_url_literal_with_quotes(self):
        out = gen_net_http_request(
            method="GET",
            request_url_variable='"https://x.example/api"',
            result_variable="resp",
            id_ref="1",
        )
        assert 'RequestUrl="[&quot;https://x.example/api&quot;]"' in out
        assert 'Result="[resp]"' in out

    def test_deserialize_json_string_literal_with_quotes(self):
        out = gen_deserialize_json(
            json_string_variable='"{""k"":1}"',
            output_variable="jObj",
            id_ref="1",
        )
        assert 'JsonObject="[jObj]"' in out
        assert "&quot;" in out  # the literal got escaped

    # ---- data_operations ----
    def test_output_data_table_text_variable_unchanged(self):
        out = gen_output_data_table(
            datatable_variable="dt", output_variable="strCsv", id_ref="1"
        )
        assert 'DataTable="[dt]"' in out
        assert 'Text="[strCsv]"' in out

    def test_lookup_data_table_lookup_value_literal_with_quotes(self):
        out = gen_lookup_data_table(
            datatable_variable="dt",
            lookup_value_variable='"key"',
            lookup_column_name="Id",
            target_column_name="Val",
            cell_value_variable="strOut",
            row_index_variable="intIdx",
            id_ref="1",
        )
        assert 'LookupValue="[&quot;key&quot;]"' in out
        assert 'CellValue="[strOut]"' in out

    def test_merge_data_table_source_destination_unchanged(self):
        out = gen_merge_data_table(
            source_variable="dtSrc", destination_variable="dtDest", id_ref="1"
        )
        assert 'Source="[dtSrc]"' in out
        assert 'Destination="[dtDest]"' in out

    def test_join_data_tables_unchanged(self):
        out = gen_join_data_tables(
            datatable1_variable="dt1",
            datatable2_variable="dt2",
            output_variable="dtOut",
            join_rules=[("ID", "ID", "EQ", "And")],
            id_ref="1",
        )
        assert 'DataTable1="[dt1]"' in out
        assert 'DataTable2="[dt2]"' in out
        assert 'OutputDataTable="[dtOut]"' in out

    # ---- integrations ----
    def test_write_cell_text_literal_with_quotes(self):
        out = gen_write_cell(
            workbook_path_variable='"C:\\book.xlsx"',
            sheet_name="Sheet1",
            cell_expression='"A1"',
            text_variable='"hello"',
            id_ref="1",
        )
        assert 'Text="[&quot;hello&quot;]"' in out
        assert 'WorkbookPath="[&quot;C:\\book.xlsx&quot;]"' in out

    def test_send_mail_to_literal_with_quotes(self):
        out = gen_send_mail(
            to_variable='"x@y.com"',
            subject_variable='"hi"',
            body_variable='"body"',
            id_ref="1",
        )
        assert 'To="[&quot;x@y.com&quot;]"' in out
        assert 'Subject="[&quot;hi&quot;]"' in out
        assert 'Body="[&quot;body&quot;]"' in out

    def test_save_mail_attachments_message_unchanged(self):
        out = gen_save_mail_attachments(
            message_variable="mailMsg",
            folder_path_variable="strFolder",
            id_ref="1",
        )
        assert 'Message="[mailMsg]"' in out
        assert 'FolderPath="[strFolder]"' in out

    def test_database_connect_secure_string_unchanged(self):
        out = gen_database_connect(
            connection_variable="ssConnStr",
            output_variable="dbConn",
            id_ref="1",
        )
        assert 'ConnectionSecureString="[ssConnStr]"' in out
        assert 'DatabaseConnection="[dbConn]"' in out

    # ---- orchestrator ----
    def test_getrobotcredential_unchanged(self):
        out = gen_getrobotcredential(
            asset_name_variable='"my_asset"',
            username_variable="strUser",
            password_variable="ssPass",
            id_ref="GetCred_1",
        )
        assert 'AssetName="[&quot;my_asset&quot;]"' in out
        assert 'Username="[strUser]"' in out
        assert 'Password="[ssPass]"' in out

    def test_bulk_add_queue_items_datatable_unchanged(self):
        out = gen_bulk_add_queue_items(
            queue_name='"MyQueue"',
            datatable_variable="dtItems",
            id_ref="1",
        )
        assert 'QueueItemsDataTable="[dtItems]"' in out
        assert 'QueueName="[&quot;MyQueue&quot;]"' in out

    # ---- logging_misc ----
    def test_should_stop_result_unchanged(self):
        out = gen_should_stop(result_variable="boolStop", id_ref="1")
        assert 'Result="[boolStop]"' in out

    def test_take_screenshot_and_save_unchanged(self):
        out = gen_take_screenshot_and_save(
            screenshot_variable="imgScreen",
            save_path_variable="strPath",
            id_ref="1",
        )
        assert 'Screenshot="[imgScreen]"' in out
        assert 'FileName="[strPath]"' in out
        assert 'Image="[imgScreen]"' in out

    # ---- ui_automation (NGetText) ----
    def test_ngettext_textstring_unchanged(self):
        out = gen_ngettext(
            display_name="Get Text",
            output_variable="strOut",
            id_ref="1",
            scope_id="scope",
            in_ui_element="uiEl",
        )
        assert 'TextString="[strOut]"' in out
        assert 'InUiElement="[uiEl]"' in out
