# Ground-truth diff: UiPath.Excel.Activities @ 3.4

- Harvested: `references/studio-ground-truth/UiPath.Excel.Activities/3.4/`
- Profile: `uipath-core\references\version-profiles\UiPath.Excel.Activities\3.4.json`

## Summary
- match: 15
- divergent: 0
- profile_template_missing: 0
- profile_element_not_found: 0
- profile_template_unparseable: 0

## Match

### `AppendRange`
- attrs: `DataTable, SheetName`

### `AutoFillX`
- attrs: `StartRange`

### `ExcelApplicationCard`
- attrs: `ReadFormatting, ResizeWindow, SensitivityLabel, SensitivityOperation, WorkbookPath`

### `ExcelForEachRowX`
- attrs: `EmptyRowBehavior, HasHeaders, Range, SaveAfterEachRow`

### `ExcelProcessScopeX`
- attrs: `DisplayAlerts, ExistingProcessAction, FileConflictResolution, LaunchMethod, LaunchTimeout, MacroSettings, ProcessMode, ShowExcelWindow`

### `FilterPivotTableX`
- attrs: `ClearFilter, ColumnName, FilterArgument, Table`

### `FilterX`
- attrs: `ClearFilter, ColumnName, FilterArgument, HasHeaders, Range`

### `ForEachRow`
- attrs: `ColumnNames, CurrentIndex, DataTable`

### `ForEachSheetX`
- attrs: `Workbook`

### `InsertExcelChartX`
- attrs: `ChartCategory, ChartHeight, ChartType, ChartWidth, InsertIntoSheet, InsertedChart, Left, Range, Top`

### `ReadRange`
- attrs: `AddHeaders, DataTable, Range, SheetName`

### `ReadRangeX`
- attrs: `Range, SaveTo`

### `UpdateChartX`
- attrs: `Chart`

### `WriteRange`
- attrs: `DataTable, SheetName, StartingCell`

### `WriteRangeX`
- attrs: `Destination, IgnoreEmptySource, Source`
