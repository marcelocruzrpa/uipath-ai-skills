"""Data operation activity generators."""
from ._helpers import _hs, _uuid, _escape_xml_attr, _escape_vb_expr, _normalize_type_arg
from ._xml_utils import _viewstate_block


def gen_assign(to_variable, value_expression, id_ref, display_name="",
               value_type="x:String", indent="    "):
    """Generate Assign activity XAML.

    Args:
        to_variable: LHS variable (no brackets), e.g. "strResult"
        value_expression: RHS expression (no brackets), e.g. 'strInput.Trim'
        id_ref: Unique IdRef
        display_name: If empty, auto-generated as "Assign - {to_variable}"
        value_type: XAML type argument, e.g. "x:String", "x:Int32", "sd2:DataTable"
    """
    if not display_name:
        display_name = f"Assign - {to_variable}"
    dn = _escape_xml_attr(display_name)
    value_type = _normalize_type_arg(value_type)
    i, i2, i3 = indent, indent+"  ", indent+"    "
    return f"""{i}<Assign DisplayName="{dn}" {_hs("Assign")} sap2010:WorkflowViewState.IdRef="{id_ref}">
{i2}<Assign.To>
{i3}<OutArgument x:TypeArguments="{value_type}">[{to_variable}]</OutArgument>
{i2}</Assign.To>
{i2}<Assign.Value>
{i3}<InArgument x:TypeArguments="{value_type}">[{_escape_vb_expr(value_expression)}]</InArgument>
{i2}</Assign.Value>
{i}</Assign>"""


def gen_multiple_assign(assignments, id_ref, display_name="Multiple Assign",
                        indent="    "):
    """Generate MultipleAssign — batch variable assignments.

    Hallucination patterns prevented:
    - Attribute shorthand: To="[var]" Value="[expr]" (crash: x:String not assignable to OutArgument)
    - Missing scg:List wrapper with Capacity
    - Missing AssignOperation.To / AssignOperation.Value element syntax

    Args:
        assignments: List of (to_variable, value_expression, value_type) tuples.
                     e.g. [("strWIID", 'in_TransactionItem.SpecificContent("WIID").ToString', "x:String"),
                           ("intCount", "intCount + 1", "x:Int32")]
                     value_type defaults to "x:String" if tuple has only 2 elements.
        id_ref: Base IdRef number — generates MultipleAssign_{id_ref}, AssignOperation_{id_ref}_N
        display_name: Activity display name
    """
    dn = _escape_xml_attr(display_name)
    i, i2, i3, i4, i5, i6 = (indent, indent+"  ", indent+"    ",
                               indent+"      ", indent+"        ", indent+"          ")

    ops = []
    for idx, assign in enumerate(assignments, 1):
        to_var = assign[0]
        val_expr = assign[1]
        val_type = assign[2] if len(assign) > 2 else "x:String"
        val_type = _normalize_type_arg(val_type)
        ops.append(f"""{i4}<ui:AssignOperation sap2010:WorkflowViewState.IdRef="AssignOperation_{id_ref}_{idx}">
{i5}<ui:AssignOperation.To>
{i6}<OutArgument x:TypeArguments="{val_type}">[{to_var}]</OutArgument>
{i5}</ui:AssignOperation.To>
{i5}<ui:AssignOperation.Value>
{i6}<InArgument x:TypeArguments="{val_type}">[{_escape_vb_expr(val_expr)}]</InArgument>
{i5}</ui:AssignOperation.Value>
{i4}</ui:AssignOperation>""")

    ops_xml = "\n".join(ops)
    capacity = len(assignments)

    return f"""{i}<ui:MultipleAssign DisplayName="{dn}" {_hs("MultipleAssign")} sap2010:WorkflowViewState.IdRef="MultipleAssign_{id_ref}">
{i2}<ui:MultipleAssign.AssignOperations>
{i3}<scg:List x:TypeArguments="ui:AssignOperation" Capacity="{capacity}">
{ops_xml}
{i3}</scg:List>
{i2}</ui:MultipleAssign.AssignOperations>
{i}</ui:MultipleAssign>"""


def gen_variables_block(variables, container="Sequence", indent="    "):
    """Generate a Variables block for Sequence or Flowchart.

    Args:
        variables: List of (name, type) tuples, e.g. [("strResult", "x:String"), ("arrLines", "s:String[]")]
                   Type is normalized — x:String[] automatically corrected to s:String[].
        container: "Sequence" or "Flowchart"
        indent: Base indentation level
    Returns:
        XAML string for <Sequence.Variables>...</Sequence.Variables>
        Empty string if variables list is empty.
    """
    if not variables:
        return ""
    i2, i3 = indent + "  ", indent + "    "
    lines = []
    for vname, vtype in variables:
        vtype = _normalize_type_arg(vtype)
        lines.append(f'{i3}<Variable x:TypeArguments="{vtype}" Name="{vname}" />')
    vars_xml = "\n".join(lines)
    return f"""{i2}<{container}.Variables>
{vars_xml}
{i2}</{container}.Variables>"""


def gen_build_data_table(datatable_variable, columns, id_ref,
                         initial_rows=None,
                         display_name="Build Data Table", indent="    "):
    """Generate BuildDataTable — schema-defined DataTable construction.

    Hallucination patterns prevented:
    - .Columns property (doesn't exist → causes Studio crash)
    - DataTableColumnInfo type (doesn't exist)
    - Child elements for columns (must be TableInfo XSD attribute)
    - Missing XSD schema wrapper (NewDataSet, xs:schema, xs:element nesting)
    - Using element syntax instead of self-closing tag

    CRITICAL: BuildDataTable is a SELF-CLOSING tag with NO child elements.
    All column definitions are inside the TableInfo attribute as an XML-escaped
    XSD schema string. This is the #1 hallucinated pattern (lint 48).

    Args:
        datatable_variable: Output variable name (no brackets), e.g. "dt_Output"
        columns: List of (column_name, column_type) tuples.
                 column_type: "String", "Int32", "Boolean", "Double", "DateTime"
                 e.g. [("Name", "String"), ("Age", "Int32"), ("Active", "Boolean")]
        initial_rows: Optional list of dicts mapping column_name → value.
                      e.g. [{"Name": "Sample", "Age": "30"}]
                      Values are always strings in the XSD data section.
        display_name: Activity display name
    """
    TYPE_MAP = {
        "String": ("xs:string", True),    # (xsd_type, needs_maxLength_restriction)
        "Int32": ("xs:int", False),
        "Boolean": ("xs:boolean", False),
        "Double": ("xs:double", False),
        "DateTime": ("xs:dateTime", False),
        "Decimal": ("xs:decimal", False),
    }

    dn = _escape_xml_attr(display_name)
    i = indent

    # Build column XSD elements
    col_lines = []
    for col_name, col_type in columns:
        if not (col_type in TYPE_MAP):
            raise ValueError(f"Invalid column type '{col_type}'. Valid: {list(TYPE_MAP.keys())}")
        xsd_type, needs_restriction = TYPE_MAP[col_type]
        if needs_restriction:
            col_lines.append(
                f'                &lt;xs:element name=&quot;{col_name}&quot; '
                f'msdata:Caption=&quot;&quot; minOccurs=&quot;0&quot;&gt;'
                f'&#xD;&#xA;'
                f'                  &lt;xs:simpleType&gt;'
                f'&#xD;&#xA;'
                f'                    &lt;xs:restriction base=&quot;{xsd_type}&quot;&gt;'
                f'&#xD;&#xA;'
                f'                      &lt;xs:maxLength value=&quot;100&quot; /&gt;'
                f'&#xD;&#xA;'
                f'                    &lt;/xs:restriction&gt;'
                f'&#xD;&#xA;'
                f'                  &lt;/xs:simpleType&gt;'
                f'&#xD;&#xA;'
                f'                &lt;/xs:element&gt;'
            )
        else:
            col_lines.append(
                f'                &lt;xs:element name=&quot;{col_name}&quot; '
                f'msdata:Caption=&quot;&quot; type=&quot;{xsd_type}&quot; '
                f'minOccurs=&quot;0&quot; /&gt;'
            )

    cols_xsd = ('&#xD;&#xA;').join(col_lines)

    # Build initial row data (after schema)
    rows_xsd = ""
    if initial_rows:
        row_parts = []
        for row in initial_rows:
            fields = []
            for col_name, _ in columns:
                if col_name in row:
                    fields.append(
                        f'    &lt;{col_name}&gt;{_escape_xml_attr(str(row[col_name]))}&lt;/{col_name}&gt;'
                    )
            row_xml = '&#xD;&#xA;'.join(fields)
            row_parts.append(
                f'  &lt;TableName&gt;&#xD;&#xA;{row_xml}&#xD;&#xA;  &lt;/TableName&gt;'
            )
        rows_xsd = '&#xD;&#xA;' + '&#xD;&#xA;'.join(row_parts) + '&#xD;&#xA;'

    table_info = (
        f'&lt;NewDataSet&gt;&#xD;&#xA;'
        f'  &lt;xs:schema id=&quot;NewDataSet&quot; xmlns=&quot;&quot; '
        f'xmlns:xs=&quot;http://www.w3.org/2001/XMLSchema&quot; '
        f'xmlns:msdata=&quot;urn:schemas-microsoft-com:xml-msdata&quot;&gt;&#xD;&#xA;'
        f'    &lt;xs:element name=&quot;NewDataSet&quot; msdata:IsDataSet=&quot;true&quot; '
        f'msdata:MainDataTable=&quot;TableName&quot; msdata:UseCurrentLocale=&quot;true&quot;&gt;&#xD;&#xA;'
        f'      &lt;xs:complexType&gt;&#xD;&#xA;'
        f'        &lt;xs:choice minOccurs=&quot;0&quot; maxOccurs=&quot;unbounded&quot;&gt;&#xD;&#xA;'
        f'          &lt;xs:element name=&quot;TableName&quot;&gt;&#xD;&#xA;'
        f'            &lt;xs:complexType&gt;&#xD;&#xA;'
        f'              &lt;xs:sequence&gt;&#xD;&#xA;'
        f'{cols_xsd}&#xD;&#xA;'
        f'              &lt;/xs:sequence&gt;&#xD;&#xA;'
        f'            &lt;/xs:complexType&gt;&#xD;&#xA;'
        f'          &lt;/xs:element&gt;&#xD;&#xA;'
        f'        &lt;/xs:choice&gt;&#xD;&#xA;'
        f'      &lt;/xs:complexType&gt;&#xD;&#xA;'
        f'    &lt;/xs:element&gt;&#xD;&#xA;'
        f'  &lt;/xs:schema&gt;{rows_xsd}'
        f'&lt;/NewDataSet&gt;'
    )

    return (
        f'{i}<ui:BuildDataTable DataTable="[{_escape_vb_expr(datatable_variable)}]" '
        f'DisplayName="{dn}" '
        f'sap:VirtualizedContainerService.HintSize="600,92" '
        f'sap2010:WorkflowViewState.IdRef="BuildDataTable_{id_ref}" '
        f'TableInfo="{table_info}" />'
    )


def gen_add_data_row(datatable_variable, array_values, id_ref,
                     display_name="Add Data Row", indent="    "):
    """Generate AddDataRow — add a row to a DataTable.

    Hallucination patterns prevented:
    - Using element syntax for ArrayRow (must be attribute)
    - Missing DataRow="{x:Null}" when using ArrayRow
    - Wrong escaping in array literal
    - Bare VB array literal {"a", 4, 4.0} — Studio rejects mixed-type rows
      with compile error BC36915 ("cannot infer element type"). Wrapped
      here with New Object() so heterogeneous rows compile.

    Args:
        datatable_variable: Variable name (no brackets), e.g. "dt_Output"
        array_values: VB expression for array literal (no outer brackets),
                      e.g. '{strCol1, strCol2}' or '{&quot;literal&quot;, intVar}'
    """
    dn = _escape_xml_attr(display_name)
    i = indent

    # Normalise bare VB array literals to New Object() {...} so Studio doesn't
    # throw BC36915 on heterogeneous row values. Leaves properly-typed
    # expressions like `New String() {...}` or variable references alone.
    raw = (array_values or "").strip()
    if raw.startswith("{") and not raw.lower().startswith("new "):
        raw = f"New Object() {raw}"
    arr = _escape_xml_attr(raw)

    return f'{i}<ui:AddDataRow DataRow="{{x:Null}}" ArrayRow="[{arr}]" DataTable="[{_escape_vb_expr(datatable_variable)}]" DisplayName="{dn}" sap2010:WorkflowViewState.IdRef="AddDataRow_{id_ref}" />'


def gen_add_data_column(datatable_variable, column_name, id_ref,
                        column_type="x:Object",
                        display_name="", indent="    "):
    """Generate AddDataColumn — add a column to a DataTable.

    Args:
        datatable_variable: Variable name (no brackets)
        column_name: Column name string
        column_type: XAML type: "x:Object", "x:String", "x:Int32", "x:Decimal", "x:Boolean"
    """
    if not display_name:
        display_name = f"Add Data Column - {column_name}"
    dn = _escape_xml_attr(display_name)
    cn = _escape_xml_attr(column_name)
    i = indent

    return (
        f'{i}<ui:AddDataColumn x:TypeArguments="{column_type}" '
        f'AllowDBNull="{{x:Null}}" AutoIncrement="{{x:Null}}" Column="{{x:Null}}" '
        f'DefaultValue="{{x:Null}}" MaxLength="{{x:Null}}" Unique="{{x:Null}}" '
        f'ColumnName="{cn}" DataTable="[{_escape_vb_expr(datatable_variable)}]" '
        f'DisplayName="{dn}" sap2010:WorkflowViewState.IdRef="AddDataColumn_{id_ref}" />'
    )


def gen_remove_data_column(datatable_variable, column_name, id_ref,
                           display_name="", indent="    "):
    """Generate RemoveDataColumn — remove a column from a DataTable by name.

    Hallucination patterns prevented:
    - Using Column property (DataColumn object) instead of ColumnName (string)
    - Using ColumnIndex instead of ColumnName (fragile — columns shift)
    - Missing explicit null on Column and ColumnIndex properties

    Args:
        datatable_variable: Variable name (no brackets)
        column_name: Column name string to remove
    """
    if not display_name:
        display_name = f"Remove Data Column - {column_name}"
    dn = _escape_xml_attr(display_name)
    cn = _escape_xml_attr(column_name)
    i = indent

    return (
        f'{i}<ui:RemoveDataColumn Column="{{x:Null}}" ColumnIndex="{{x:Null}}" '
        f'ColumnName="{cn}" DataTable="[{_escape_vb_expr(datatable_variable)}]" '
        f'DisplayName="{dn}" {_hs("RemoveDataColumn")} '
        f'sap2010:WorkflowViewState.IdRef="RemoveDataColumn_{id_ref}" />'
    )


def gen_filter_data_table(datatable_variable, filters, id_ref,
                          output_variable="", filter_rows_mode="Keep",
                          select_columns_mode="Remove",
                          display_name="Filter Data Table", indent="    "):
    """Generate FilterDataTable — filter rows/columns of a DataTable.

    Hallucination patterns prevented:
    - Missing scg:List wrapper for FilterOperationArgument
    - Wrong property names on FilterOperationArgument
    - Missing SelectColumns list (even when empty)

    Args:
        datatable_variable: Input DataTable variable (no brackets)
        filters: List of tuples. Supports two formats:
                 4-tuple: (column_name, operator, operand_value, bool_op)
                 5-tuple: (column_name, operator, operand_value, bool_op, operand_type)
                 operator: "EQ","NE","LT","LE","GT","GE","CONTAINS","STARTS_WITH","ENDS_WITH","EMPTY","NOT_EMPTY"
                           (also accepts mixed-case: "Contains"→"CONTAINS", "IsEmpty"→"EMPTY", etc.)
                 bool_op: "And" or "Or"
                 operand_type: XAML type for operand (default "x:String"), e.g. "x:Int32" for numeric
                 For EMPTY/NOT_EMPTY operators: operand_value is ignored (Studio uses Operand="{x:Null}")
                 e.g. [("Status", "EQ", "Completed", "And"),
                       ("Age", "GT", "18", "And", "x:Int32"),
                       ("Notes", "EMPTY", "", "And")]
        output_variable: Output variable (no brackets). If empty, same as input (in-place).
        filter_rows_mode: "Keep" or "Remove"
        select_columns_mode: "Keep" or "Remove"
    """
    dn = _escape_xml_attr(display_name)
    out_var = output_variable or datatable_variable
    i, i2, i3, i4, i5 = indent, indent+"  ", indent+"    ", indent+"      ", indent+"        "

    # Normalize symbolic and mixed-case operators to Studio's actual FilterOperator enum values.
    # Source of truth: real Studio clipboard export uses ALL-CAPS for text operators.
    _OP_NORMALIZE = {
        "=": "EQ", "==": "EQ", "!=": "NE", "<>": "NE",
        "<": "LT", "<=": "LE", ">": "GT", ">=": "GE",
        # Mixed-case → Studio's actual UPPER-CASE enum names
        "Contains": "CONTAINS", "contains": "CONTAINS",
        "StartsWith": "STARTS_WITH", "startswith": "STARTS_WITH", "Startswith": "STARTS_WITH",
        "EndsWith": "ENDS_WITH", "endswith": "ENDS_WITH", "Endswith": "ENDS_WITH",
        "IsEmpty": "EMPTY", "isEmpty": "EMPTY", "isempty": "EMPTY", "Empty": "EMPTY", "empty": "EMPTY",
        "IsNotEmpty": "NOT_EMPTY", "isNotEmpty": "NOT_EMPTY", "isnotempty": "NOT_EMPTY",
        "NotEmpty": "NOT_EMPTY", "notempty": "NOT_EMPTY",
    }
    _VALID_OPS = {"EQ", "NE", "LT", "LE", "GT", "GE",
                  "CONTAINS", "STARTS_WITH", "ENDS_WITH", "EMPTY", "NOT_EMPTY"}

    # Detect operand type — supports (col, op, operand, bool_op) and
    # (col, op, operand, bool_op, operand_type) for typed comparisons
    _OPERAND_NO_VALUE_OPS = {"EMPTY", "NOT_EMPTY"}

    filter_entries = []
    for filter_tuple in filters:
        if len(filter_tuple) == 5:
            col, op, operand, bool_op, operand_type = filter_tuple
        else:
            col, op, operand, bool_op = filter_tuple
            operand_type = "x:String"

        op = _OP_NORMALIZE.get(op, op)
        if op not in _VALID_OPS:
            raise ValueError(
                f"Invalid FilterOperator '{op}'. Must be one of: {', '.join(sorted(_VALID_OPS))}. "
                f"Use 'EQ' not '=', 'NE' not '!=' etc."
            )

        if op in _OPERAND_NO_VALUE_OPS:
            # EMPTY / NOT_EMPTY: no operand value — use Operand="{x:Null}" attribute
            filter_entries.append(f"""{i4}<ui:FilterOperationArgument Operand="{{x:Null}}" BooleanOperator="{bool_op}" Operator="{op}">
{i5}<ui:FilterOperationArgument.Column>
{i5}  <InArgument x:TypeArguments="x:String">["{_escape_xml_attr(col)}"]</InArgument>
{i5}</ui:FilterOperationArgument.Column>
{i4}</ui:FilterOperationArgument>""")
        else:
            # String operands: ["value"], non-string: [value]
            if operand_type == "x:String":
                operand_expr = f'["{_escape_xml_attr(str(operand))}"]'
            else:
                operand_expr = f'[{_escape_xml_attr(str(operand))}]'
            filter_entries.append(f"""{i4}<ui:FilterOperationArgument BooleanOperator="{bool_op}" Operator="{op}">
{i5}<ui:FilterOperationArgument.Column>
{i5}  <InArgument x:TypeArguments="x:String">["{_escape_xml_attr(col)}"]</InArgument>
{i5}</ui:FilterOperationArgument.Column>
{i5}<ui:FilterOperationArgument.Operand>
{i5}  <InArgument x:TypeArguments="{operand_type}">{operand_expr}</InArgument>
{i5}</ui:FilterOperationArgument.Operand>
{i4}</ui:FilterOperationArgument>""")

    filters_xml = "\n".join(filter_entries)
    capacity = max(len(filters), 4)

    return f"""{i}<ui:FilterDataTable DataTable="[{_escape_vb_expr(datatable_variable)}]" DisplayName="{dn}" FilterRowsMode="{filter_rows_mode}" sap2010:WorkflowViewState.IdRef="FilterDataTable_{id_ref}" OutputDataTable="[{_escape_vb_expr(out_var)}]" SelectColumnsMode="{select_columns_mode}">
{i2}<ui:FilterDataTable.Filters>
{i3}<scg:List x:TypeArguments="ui:FilterOperationArgument" Capacity="{capacity}">
{filters_xml}
{i3}</scg:List>
{i2}</ui:FilterDataTable.Filters>
{i2}<ui:FilterDataTable.SelectColumns>
{i3}<scg:List x:TypeArguments="InArgument" Capacity="4">
{i4}<x:Null />
{i3}</scg:List>
{i2}</ui:FilterDataTable.SelectColumns>
{i}</ui:FilterDataTable>"""


def gen_sort_data_table(datatable_variable, column_name, id_ref,
                        sort_order="Ascending", output_variable="",
                        display_name="Sort Data Table", indent="    "):
    """Generate SortDataTable.

    Hallucination patterns prevented:
    - OrderByColumnName (doesn't exist → use ColumnName)
    - OrderByType (doesn't exist → use SortOrder)
    - Missing ColumnIndex="{x:Null}" DataColumn="{x:Null}"
    """
    dn = _escape_xml_attr(display_name)
    cn = _escape_xml_attr(column_name)
    out_var = output_variable or datatable_variable
    if not (sort_order in ("Ascending", "Descending")):
        raise ValueError(f"Invalid SortOrder: {sort_order}")
    i = indent

    return (
        f'{i}<ui:SortDataTable ColumnIndex="{{x:Null}}" DataColumn="{{x:Null}}" '
        f'ColumnName="{cn}" SortOrder="{sort_order}" '
        f'DataTable="[{_escape_vb_expr(datatable_variable)}]" OutputDataTable="[{_escape_vb_expr(out_var)}]" '
        f'DisplayName="{dn}" sap2010:WorkflowViewState.IdRef="SortDataTable_{id_ref}" />'
    )


def gen_remove_duplicate_rows(datatable_variable, id_ref,
                               output_variable="",
                               display_name="Remove Duplicate Rows",
                               indent="    "):
    """Generate RemoveDuplicateRows."""
    dn = _escape_xml_attr(display_name)
    out_var = output_variable or datatable_variable
    i = indent
    return f'{i}<ui:RemoveDuplicateRows DataTable="[{_escape_vb_expr(datatable_variable)}]" DisplayName="{dn}" OutputDataTable="[{_escape_vb_expr(out_var)}]" sap2010:WorkflowViewState.IdRef="RemoveDuplicateRows_{id_ref}" />'


def gen_output_data_table(datatable_variable, output_variable, id_ref,
                          display_name="Output Data Table", indent="    "):
    """Generate OutputDataTable — DataTable to CSV string.

    Hallucination patterns prevented:
    - Wrong property name (Output vs Text)
    """
    dn = _escape_xml_attr(display_name)
    i = indent
    return f'{i}<ui:OutputDataTable DataTable="[{_escape_vb_expr(datatable_variable)}]" DisplayName="{dn}" Text="[{_escape_vb_expr(output_variable)}]" sap2010:WorkflowViewState.IdRef="OutputDataTable_{id_ref}" />'


def gen_join_data_tables(datatable1_variable, datatable2_variable, output_variable,
                         join_rules, id_ref, join_type="Inner",
                         display_name="Join Data Tables", indent="    "):
    """Generate JoinDataTables — SQL-style joins between DataTables.

    Hallucination patterns prevented:
    - Missing scg:List wrapper for JoinOperationArgument
    - Wrong property names on JoinOperationArgument (Column vs Column1/Column2)
    - Missing BooleanOperator

    Args:
        join_rules: List of (column1, column2, operator, bool_op) tuples.
                    e.g. [("ID", "ID", "EQ", "And")]
        join_type: "Inner", "Left", "Full"
    """
    if not (join_type in ("Inner", "Left", "Full")):
        raise ValueError(f"Invalid JoinType: {join_type}")
    dn = _escape_xml_attr(display_name)
    i, i2, i3, i4, i5 = indent, indent+"  ", indent+"    ", indent+"      ", indent+"        "

    rule_entries = []
    for col1, col2, op, bool_op in join_rules:
        rule_entries.append(f"""{i4}<ui:JoinOperationArgument BooleanOperator="{bool_op}" Operator="{op}">
{i5}<ui:JoinOperationArgument.Column1>
{i5}  <InArgument x:TypeArguments="x:String">["{_escape_xml_attr(col1)}"]</InArgument>
{i5}</ui:JoinOperationArgument.Column1>
{i5}<ui:JoinOperationArgument.Column2>
{i5}  <InArgument x:TypeArguments="x:String">["{_escape_xml_attr(col2)}"]</InArgument>
{i5}</ui:JoinOperationArgument.Column2>
{i4}</ui:JoinOperationArgument>""")

    rules_xml = "\n".join(rule_entries)
    capacity = max(len(join_rules), 4)

    return f"""{i}<ui:JoinDataTables DataTable1="[{_escape_vb_expr(datatable1_variable)}]" DataTable2="[{_escape_vb_expr(datatable2_variable)}]" DisplayName="{dn}" JoinType="{join_type}" OutputDataTable="[{_escape_vb_expr(output_variable)}]" sap2010:WorkflowViewState.IdRef="JoinDataTables_{id_ref}">
{i2}<ui:JoinDataTables.JoinRules>
{i3}<scg:List x:TypeArguments="ui:JoinOperationArgument" Capacity="{capacity}">
{rules_xml}
{i3}</scg:List>
{i2}</ui:JoinDataTables.JoinRules>
{i}</ui:JoinDataTables>"""


def gen_lookup_data_table(datatable_variable, lookup_value_variable,
                          lookup_column_name, target_column_name,
                          cell_value_variable, row_index_variable,
                          id_ref, display_name="Lookup Data Table",
                          indent="    "):
    """Generate LookupDataTable — VLOOKUP equivalent.

    Args:
        lookup_value_variable: Value to search for (no brackets)
        lookup_column_name: Column to search in
        target_column_name: Column to return value from
        cell_value_variable: Output variable for found value (no brackets)
        row_index_variable: Output Int32 for row index, -1 if not found
    """
    dn = _escape_xml_attr(display_name)
    i = indent
    return (
        f'{i}<ui:LookupDataTable CellValue="[{_escape_vb_expr(cell_value_variable)}]" '
        f'DataTable="[{_escape_vb_expr(datatable_variable)}]" DisplayName="{dn}" '
        f'LookupValue="[{_escape_vb_expr(lookup_value_variable)}]" '
        f'RowIndex="[{_escape_vb_expr(row_index_variable)}]" '
        f'TargetColumnName="{_escape_xml_attr(target_column_name)}" '
        f'LookupColumnName="{_escape_xml_attr(lookup_column_name)}" '
        f'sap2010:WorkflowViewState.IdRef="LookupDataTable_{id_ref}" />'
    )


def gen_merge_data_table(source_variable, destination_variable, id_ref,
                         missing_schema_action="Add",
                         display_name="Merge Data Table", indent="    "):
    """Generate MergeDataTable.

    Args:
        missing_schema_action: "Add", "Ignore", "Error", "AddWithKey"
    """
    _VALID_SCHEMA_ACTIONS = ("Add", "Ignore", "Error", "AddWithKey")
    if missing_schema_action not in _VALID_SCHEMA_ACTIONS:
        raise ValueError(f"Invalid MissingSchemaAction '{missing_schema_action}'. Must be one of: {', '.join(_VALID_SCHEMA_ACTIONS)}")
    dn = _escape_xml_attr(display_name)
    i = indent
    return (
        f'{i}<ui:MergeDataTable Destination="[{_escape_vb_expr(destination_variable)}]" '
        f'DisplayName="{dn}" MissingSchemaAction="{missing_schema_action}" '
        f'Source="[{_escape_vb_expr(source_variable)}]" '
        f'sap2010:WorkflowViewState.IdRef="MergeDataTable_{id_ref}" />'
    )


def gen_generate_data_table(input_variable, output_variable, id_ref,
                            column_separator=",", use_column_header=True,
                            display_name="Generate Data Table From Text",
                            indent="    "):
    """Generate GenerateDataTable — parse text/CSV into DataTable."""
    dn = _escape_xml_attr(display_name)
    sep = _escape_xml_attr(column_separator)
    i = indent
    return (
        f'{i}<ui:GenerateDataTable ColumnSeparators="[{{&quot;{sep}&quot;c}}]" '
        f'DataTable="[{_escape_vb_expr(output_variable)}]" DisplayName="{dn}" '
        f'Input="[{_escape_vb_expr(input_variable)}]" NewLineSeparator="\\n" '
        f'UseColumnHeader="{use_column_header}" AutoDetect="True" '
        f'sap2010:WorkflowViewState.IdRef="GenerateDataTable_{id_ref}" />'
    )
