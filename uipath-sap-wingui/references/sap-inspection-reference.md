# SAP GUI Inspection Reference

Reference documentation for the `inspect-sap-tree.ps1` PowerShell script.

## Quick Start

```powershell
# Inspect SAP transaction by window title (selectors output)
.\inspect-sap-tree.ps1 -WindowTitle "Create Purchase Order" -OutputFormat selectors

# Inspect by process name (tree output)
.\inspect-sap-tree.ps1 -ProcessName "saplogon.exe" -OutputFormat tree

# JSON output for programmatic consumption
.\inspect-sap-tree.ps1 -WindowTitle "*ME21N*" -OutputFormat json
```

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `-WindowTitle` | `""` | Title or wildcard pattern of the SAP window |
| `-WindowClass` | `""` | Window ClassName (typically `SAP_FRONTEND_SESSION`) |
| `-ProcessName` | `saplogon.exe` | Process name with extension. Supports wildcards |
| `-MaxElements` | `300` | Maximum SAP controls to output |
| `-OutputFormat` | `selectors` | `tree`, `flat`, `selectors`, or `json` |

## Prerequisites

1. **SAP Scripting enabled on server**: Transaction `RZ11` → parameter `sapgui/user_scripting` = `TRUE`
2. **SAP GUI client scripting enabled**: SAP GUI Options → Accessibility & Scripting → Enable scripting

## SAP Selector Pattern

SAP selectors use a two-level structure:

```xml
<!-- Window selector -->
<wnd app='saplogon.exe' cls='SAP_FRONTEND_SESSION' title='Create Purchase Order' />

<!-- SAP element selector -->
<sap id='usr/subSUB0:.../txtMEPO_TOPLINE-EBELN' />
```

The `<sap id='...'>` path mirrors the SAP GUI scripting object hierarchy:
- `tbar[0]/btn[N]` — System toolbar buttons
- `tbar[1]/btn[N]` — Application toolbar buttons
- `usr/sub.../txtFIELD` — Text fields in user area
- `usr/sub.../ctxtFIELD` — Context-sensitive text fields (date, search help)
- `usr/sub.../cmbFIELD` — ComboBox (dropdown)
- `usr/sub.../lblFIELD` — Labels
- `usr/sub.../btnFIELD` — Buttons
- `usr/sub.../tblTABLE_NAME` — Table controls

## SAP Type to UiPath Activity Mapping

| SAP Type | UiPath Activity | Notes |
|----------|----------------|-------|
| `GuiTextField` | Type Into / Get Text | Standard text input |
| `GuiCTextField` | Type Into / Get Text | Context-sensitive (has search help F4) |
| `GuiPasswordField` | Type Into (Secure) | Password entry |
| `GuiComboBox` | Select Item | Dropdown selection |
| `GuiButton` | Click | Standard button |
| `GuiLabel` | Get Text | Read-only label |
| `GuiCheckBox` | Check / Uncheck | Toggle checkbox |
| `GuiRadioButton` | Select | Radio button selection |
| `GuiTab` | Click (Select Tab) | Tab strip navigation |
| `GuiTableControl` | For Each Row / Get Cell | Table with row/column addressing |
| `GuiShell` | Click / Select Cell (ALV Grid) | ALV Grid (skipped during BFS) |
| `GuiStatusbar` | Get Text (Status) | Status bar message |
| `GuiSimpleContainer` | (container) | Layout container — not interactive |
| `GuiCustomControl` | (container) | Custom control wrapper |
| `GuiContainerShell` | (container) | Shell container |

## Table Cell Addressing

SAP tables support two addressing modes in UiPath:

```xml
<!-- By row/column index -->
<sap id='usr/sub.../tblSAPLMEGUITC_1211' tableRow='{row}' tableCol='{col}' />

<!-- By column tooltip (more stable) -->
<sap colTooltip='{tooltip}' id='usr/sub.../tblSAPLMEGUITC_1211' tableRow='{row}' />
```

The script outputs full column metadata including field names, tooltips, titles, and cell types for each column — use this mapping to build table automation without manual UI Explorer inspection.

## Dynpro Volatility

SAP sub-container paths contain dynpro numbers that can change:

```
usr/subSUB0:SAPLMEGUI:0016/subSUB1:SAPLMEGUI:1105/txtMEPO_TOPLINE-EBELN
         ^^^^              ^^^^
         These numbers may change when sections expand/collapse
```

**Stable identifiers:**
- Field names: `txtMEPO_TOPLINE-EBELN`, `cmbMEPO_TOPLINE-BSART` — always stable
- Table IDs: `tblSAPLMEGUITC_1211` — always stable
- Toolbar buttons: `tbar[0]/btn[11]` — indices are SAP-internal IDs, not positional

**Volatile identifiers:**
- Sub-container dynpro numbers: `subSUB0:SAPLMEGUI:0016` — changes when header/item sections expand/collapse
- Table cell row indices: change with scrolling position

## How It Works

1. The script finds the SAP GUI window via UIA (for window handle only)
2. Validates the target is SAP (ClassName `SAP_*` or process `saplogon.exe`)
3. Generates a VBScript file that connects to the SAP Scripting API via COM:
   - `GetObject("SAPGUI")` → `GetScriptingEngine` → `connection.Children(0)` → `session`
4. The VBScript performs:
   - Toolbar probing: iterates `tbar[0]/btn[0..50]` and `tbar[1]/btn[0..50]`
   - BFS queue walk of `wnd[0]/usr` (user area) up to MaxElements
   - `GuiTableControl` detection with `Columns.Item()` and `GetCell(0, col)` metadata
   - Status bar capture via `wnd[0]/sbar`
5. Output is piped through `cscript.exe` and parsed by PowerShell into the selected format

### Why VBScript?

PowerShell cannot directly call `GetObject("SAPGUI")` — the SAP GUI Scripting Engine uses a COM ROT (Running Object Table) entry that requires the VBScript/WScript runtime. The VBScript bridge outputs pipe-delimited lines that PowerShell parses into structured output.

## Sample Output: ME21N (Create Purchase Order)

Transaction ME21N on system EH8, captured February 2026.

### Selectors format (abbreviated)

```
=== SAP GUI INSPECTION ===

Window:
  Title         = Create Purchase Order
  ClassName     = SAP_FRONTEND_SESSION
  ProcessName   = saplogon.exe

UiPath Window Selector:  <wnd app='saplogon.exe' cls='SAP_FRONTEND_SESSION' title='Create Purchase Order' />

Connecting to SAP Scripting API via COM...
  Transaction: ME21N | System: EH8

# Standard PO (ComboBox) [editable]
<wnd app='saplogon.exe' cls='SAP_FRONTEND_SESSION' title='Create Purchase Order' />
<sap id='usr/subSUB0:.../cmbMEPO_TOPLINE-BSART' tooltip='Order Type' />
# Activity: Select Item

# (TextField) [editable]
<wnd app='saplogon.exe' cls='SAP_FRONTEND_SESSION' title='Create Purchase Order' />
<sap id='usr/subSUB0:.../txtMEPO_TOPLINE-EBELN' tooltip='Purchasing Document' />
# Activity: Type Into / Get Text

# Vendor (TextField)
<wnd app='saplogon.exe' cls='SAP_FRONTEND_SESSION' title='Create Purchase Order' />
<sap id='usr/subSUB0:.../txtMEPO_TOPLINE-SCRTEXT' />
# Activity: Type Into / Get Text

# Doc. date (Label)
<wnd app='saplogon.exe' cls='SAP_FRONTEND_SESSION' title='Create Purchase Order' />
<sap id='usr/subSUB0:.../lblMEPO_TOPLINE-BEDAT' />
# Activity: Get Text

# === TABLE: tblSAPLMEGUITC_1211 ===
# Rows: 43 (visible: 43) | Columns: 45
# Base selector:
<wnd app='saplogon.exe' cls='SAP_FRONTEND_SESSION' title='Create Purchase Order' />
<sap id='usr/sub.../tblSAPLMEGUITC_1211' tableRow='{row}' tableCol='{col}' />
# Activity: For Each Row / Get Cell / Set Cell
```

### Key controls found

| Control | SAP Type | Field Name | Activity |
|---------|----------|------------|----------|
| Order Type | GuiComboBox | MEPO_TOPLINE-BSART | Select Item |
| PO Number | GuiTextField | MEPO_TOPLINE-EBELN | Type Into / Get Text |
| Vendor | GuiTextField | MEPO_TOPLINE-SCRTEXT | Get Text |
| Vendor Field | GuiCTextField | MEPO_TOPLINE-SUPERFIELD | Type Into / Get Text |
| Doc. Date | GuiCTextField | MEPO_TOPLINE-BEDAT | Type Into / Get Text |
| Expand Header | GuiButton | DYN_4000-BUTTON | Click |
| Collapse Items | GuiButton | DYN_4000-BUTTON | Click |
| Item Table | GuiTableControl | SAPLMEGUITC_1211 | For Each Row / Get Cell |
| Choose PO Item | GuiButton | DETAIL | Click |
| Delete | GuiButton | DELETE | Click |
| Sort Ascending | GuiButton | SORTUP | Click |
| Sort Descending | GuiButton | SORTDOWN | Click |

## Troubleshooting

**SAP Scripting connection failed** — Check these in order:
1. Transaction `RZ11` → `sapgui/user_scripting` must be `TRUE`
2. SAP GUI Options → Accessibility & Scripting → Enable scripting
3. Close and reopen the SAP transaction after enabling
4. Ensure only one SAP GUI session is connected (script uses `Children(0)`)
5. Run from an elevated PowerShell if COM access is blocked

**Limited output / missing fields** — SAP Scripting only exposes controls in the current dynpro. Scroll down or expand sections to reveal hidden fields, then re-run.

**Dynpro numbers changed** — Expected. Sub-container dynpro numbers (e.g., `subSUB0:SAPLMEGUI:0016`) change when header/item sections expand/collapse. Use field names (`txtMEPO_TOPLINE-EBELN`) which remain stable.

**GuiShell / ALV Grid not detailed** — ALV Grid (`GuiShell`) containers are skipped during BFS to avoid explosion. Use UiPath UI Explorer to inspect ALV Grid columns.

**Window not found** — The script lists all available windows when no match is found. Ensure SAP GUI is open with the target transaction visible. Try wildcards: `-WindowTitle "*Purchase Order*"`.

**Table cell explosion in raw output** — The VBScript BFS skips `GuiTableControl` children and instead emits `TABLE_META` + `TABLE_COL` lines with column metadata. This avoids the hundreds of individual cell elements that SAP table controls contain.
