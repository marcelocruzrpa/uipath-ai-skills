"""File system activity generators."""
from ._helpers import _hs, _uuid, _escape_xml_attr, _escape_vb_expr
from ._xml_utils import _viewstate_block


def gen_copy_file(source_path, destination_path, id_ref,
                  overwrite=True, display_name="Copy File", indent="    "):
    """Generate CopyFile.

    Args:
        source_path: VB expression or literal path (no brackets for variable, quoted for literal)
        destination_path: VB expression for destination (no brackets)
    """
    dn = _escape_xml_attr(display_name)
    i = indent
    # Always wrap source_path in VB expression brackets.
    # For literal paths, caller must pass as VB string: '"C:\\temp\\file.txt"'
    # For variables, caller passes: 'strFilePath'
    return (
        f'{i}<ui:CopyFile ContinueOnError="{{x:Null}}" DestinationResource="{{x:Null}}" '
        f'PathResource="{{x:Null}}" Destination="[{_escape_vb_expr(destination_path)}]" '
        f'DisplayName="{dn}" Overwrite="{overwrite}" '
        f'Path="[{_escape_vb_expr(source_path)}]" sap2010:WorkflowViewState.IdRef="CopyFile_{id_ref}" />'
    )


# ---------------------------------------------------------------------------
# MoveFile
# ---------------------------------------------------------------------------

def gen_move_file(source_variable, destination_variable, id_ref,
                  overwrite=True, display_name="Move File", indent="    "):
    """Generate MoveFile."""
    dn = _escape_xml_attr(display_name)
    i = indent
    return (
        f'{i}<ui:MoveFile ContinueOnError="{{x:Null}}" DestinationResource="{{x:Null}}" '
        f'PathResource="{{x:Null}}" Destination="[{_escape_vb_expr(destination_variable)}]" '
        f'DisplayName="{dn}" Overwrite="{overwrite}" '
        f'Path="[{_escape_vb_expr(source_variable)}]" sap2010:WorkflowViewState.IdRef="MoveFile_{id_ref}" />'
    )


# ---------------------------------------------------------------------------
# DeleteFileX
# ---------------------------------------------------------------------------

def gen_delete_file(path_variable, id_ref,
                    display_name="Delete File", indent="    "):
    """Generate DeleteFileX.

    ⚠️ DeleteFileX does NOT have ContinueOnError — model adds it, Studio crashes.
    Wrap in TryCatch if error suppression is needed.
    """
    dn = _escape_xml_attr(display_name)
    i = indent
    return f'{i}<ui:DeleteFileX DisplayName="{dn}" Path="[{_escape_vb_expr(path_variable)}]" sap2010:WorkflowViewState.IdRef="DeleteFileX_{id_ref}" />'


# ---------------------------------------------------------------------------
# PathExists
# ---------------------------------------------------------------------------

def gen_path_exists(path_variable, result_variable, id_ref,
                    path_type="File", display_name="Path Exists", indent="    "):
    """Generate PathExists.

    Args:
        path_type: "File" or "Folder"
    """
    if not (path_type in ("File", "Folder")):
        raise ValueError(f"Invalid PathType: {path_type}")
    dn = _escape_xml_attr(display_name)
    i = indent
    return (
        f'{i}<ui:PathExists DisplayName="{dn}" Path="[{_escape_vb_expr(path_variable)}]" '
        f'PathType="{path_type}" Result="[{_escape_vb_expr(result_variable)}]" '
        f'sap2010:WorkflowViewState.IdRef="PathExists_{id_ref}" />'
    )


# ---------------------------------------------------------------------------
# CreateDirectory
# ---------------------------------------------------------------------------

def gen_create_directory(path_variable, id_ref,
                         display_name="Create Directory", indent="    "):
    """Generate CreateDirectory."""
    dn = _escape_xml_attr(display_name)
    i = indent
    return (
        f'{i}<ui:CreateDirectory ContinueOnError="{{x:Null}}" Output="{{x:Null}}" '
        f'DisplayName="{dn}" Path="[{_escape_vb_expr(path_variable)}]" '
        f'sap2010:WorkflowViewState.IdRef="CreateDirectory_{id_ref}" />'
    )


def gen_read_text_file(output_variable, id_ref, display_name="Read Text File",
                       file_path="", path_variable="",
                       encoding="", indent="    "):
    """Generate a Read Text File (ui:ReadTextFile) activity.

    Args:
        output_variable: variable name to store file content (String)
        id_ref: IdRef for ViewState
        display_name: DisplayName
        file_path: literal file path string (use one of file_path or path_variable)
        path_variable: VB variable for path (use one of file_path or path_variable)
        encoding: optional encoding string, e.g. 'utf-8', 'utf-16' — omit for default
        indent: base indentation
    """
    if not (bool(file_path) != bool(path_variable)):
        raise ValueError("Provide exactly one of file_path or path_variable")

    hs = _hs("ReadTextFile")
    dn = _escape_xml_attr(display_name)

    if path_variable:
        f_attr = 'File="{x:Null}"'
        fn_attr = f' FileName="[{_escape_vb_expr(path_variable)}]"'
    else:
        f_attr = f'File="{_escape_xml_attr(file_path)}"'
        fn_attr = ""

    enc_attr = ""
    if encoding:
        enc_attr = f' Encoding="{encoding}"'

    return (
        f'{indent}<ui:ReadTextFile {f_attr} Content="[{_escape_vb_expr(output_variable)}]" '
        f'DisplayName="{dn}"{enc_attr}{fn_attr} {hs} '
        f'sap2010:WorkflowViewState.IdRef="{id_ref}" />'
    )


def gen_write_text_file(text_variable, id_ref, display_name="Write Text File",
                        file_path="", path_variable="",
                        encoding="", indent="    "):
    """Generate a Write Text File (ui:WriteTextFile) activity.

    Args:
        text_variable: variable name containing text to write (String)
        id_ref: IdRef for ViewState
        display_name: DisplayName
        file_path: literal file path string (use one of file_path or path_variable)
        path_variable: VB variable for path (use one of file_path or path_variable)
        encoding: optional encoding string — omit for default
        indent: base indentation
    """
    if not (bool(file_path) != bool(path_variable)):
        raise ValueError("Provide exactly one of file_path or path_variable")

    hs = _hs("WriteTextFile")
    dn = _escape_xml_attr(display_name)

    if path_variable:
        f_attr = 'File="{x:Null}"'
        fn_attr = f' FileName="[{_escape_vb_expr(path_variable)}]"'
    else:
        f_attr = f'File="{_escape_xml_attr(file_path)}"'
        fn_attr = ""

    enc_attr = ""
    if encoding:
        enc_attr = f' Encoding="{encoding}"'

    return (
        f'{indent}<ui:WriteTextFile {f_attr} Output="{{x:Null}}" '
        f'DisplayName="{dn}"{enc_attr}{fn_attr} {hs} '
        f'sap2010:WorkflowViewState.IdRef="{id_ref}" Text="[{_escape_vb_expr(text_variable)}]" />'
    )


def gen_read_csv(output_datatable, id_ref, display_name="Read CSV",
                 file_path="", path_variable="",
                 delimiter="Comma", encoding="UTF8",
                 has_headers=True, indent="    "):
    """Generate a Read CSV (ui:ReadCsvFile) activity.

    Args:
        output_datatable: variable name to store result DataTable
        id_ref: IdRef for ViewState
        display_name: DisplayName
        file_path: literal file path string (use one of file_path or path_variable)
        path_variable: VB variable for path (use one of file_path or path_variable)
        delimiter: 'Comma', 'Tab', 'Semicolon', 'Caret', 'Pipe', 'Custom'
        encoding: 'UTF8', 'Unicode', 'ASCII', 'Default'
        has_headers: whether first row is header (default True)
        indent: base indentation
    """
    if not (delimiter in ("Comma", "Tab", "Semicolon", "Caret", "Pipe", "Custom")):
        raise ValueError(f"Invalid delimiter: {delimiter}. Must be one of: Comma, Tab, Semicolon, Caret, Pipe, Custom")
    if not (bool(file_path) != bool(path_variable)):
        raise ValueError("Provide exactly one of file_path or path_variable")

    hs = _hs("ReadCsvFile")
    dn = _escape_xml_attr(display_name)

    if path_variable:
        fp_attr = 'FilePath="{x:Null}"'
        pr_attr = f' PathResource="[{_escape_vb_expr(path_variable)}]"'
    else:
        fp_attr = f'FilePath="{_escape_xml_attr(file_path)}"'
        pr_attr = ""

    hh_attr = ""
    if not has_headers:
        hh_attr = ' IncludeColumnNames="False"'

    enc_attr = ""
    if encoding != "UTF8":
        enc_attr = f' Encoding="{encoding}"'

    return (
        f'{indent}<ui:ReadCsvFile {fp_attr} DataTable="[{_escape_vb_expr(output_datatable)}]" '
        f'Delimitator="{delimiter}" DelimitatorForViewModel="{delimiter}" '
        f'DisplayName="{dn}"{enc_attr}{hh_attr} {hs} '
        f'sap2010:WorkflowViewState.IdRef="{id_ref}"{pr_attr} />'
    )


def gen_write_csv(input_datatable, id_ref, display_name="Write CSV",
                  file_path="", path_variable="",
                  csv_action="Write", delimiter="Comma",
                  add_headers=True, should_quote=True,
                  indent="    "):
    """Generate a Write/Append CSV (ui:AppendWriteCsvFile) activity.

    Args:
        input_datatable: variable name of the DataTable to write
        id_ref: IdRef for ViewState
        display_name: DisplayName
        file_path: literal file path string (use one of file_path or path_variable)
        path_variable: VB variable for path (use one of file_path or path_variable)
        csv_action: 'Write' (overwrite) or 'Append'
        delimiter: 'Comma', 'Tab', 'Semicolon', 'Caret', 'Pipe', 'Custom'
        add_headers: write column headers (default True)
        should_quote: quote fields (default True)
        indent: base indentation
    """
    if not (delimiter in ("Comma", "Tab", "Semicolon", "Caret", "Pipe", "Custom")):
        raise ValueError(f"Invalid delimiter: {delimiter}. Must be one of: Comma, Tab, Semicolon, Caret, Pipe, Custom")
    if not (csv_action in ("Write", "Append")):
        raise ValueError(f"Invalid csv_action: {csv_action}. Must be one of: Write, Append")
    if not (bool(file_path) != bool(path_variable)):
        raise ValueError("Provide exactly one of file_path or path_variable")

    hs = _hs("AppendWriteCsvFile")
    dn = _escape_xml_attr(display_name)

    if path_variable:
        fp_attr = 'FilePath="{x:Null}"'
        pr_attr = f' PathResource="[{_escape_vb_expr(path_variable)}]"'
    else:
        fp_attr = f'FilePath="{_escape_xml_attr(file_path)}"'
        pr_attr = ""

    ah = "True" if add_headers else "False"
    sq = "True" if should_quote else "False"

    return (
        f'{indent}<ui:AppendWriteCsvFile {fp_attr} AddHeaders="{ah}" '
        f'CsvAction="{csv_action}" DataTable="[{_escape_vb_expr(input_datatable)}]" '
        f'Delimitator="{delimiter}" DelimitatorForViewModel="{delimiter}" '
        f'DisplayName="{dn}" {hs} '
        f'sap2010:WorkflowViewState.IdRef="{id_ref}"{pr_attr} ShouldQuote="{sq}" />'
    )
