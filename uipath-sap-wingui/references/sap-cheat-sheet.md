# SAP WinGUI XAML Cheat Sheet

Quick-reference for SAP generator commands and rules. **Always use generators** — never hand-write SAP activity XAML. For standard activities (NTypeInto, NClick, NGetText, etc.) use `uipath-core`'s `generate_activities`.

## SAP Generator Quick Reference

```python
from extensions.generators import *
```

| Function | Activity | Key params |
|---|---|---|
| `gen_sap_logon()` | NSAPLogon (launch ONLY) | `sap_connection`, `sap_exe_path`, `scope_guid`, `body_content`, `body_variables` |
| `gen_sap_login()` | NSAPLogin | `username`, `secure_password`, `client`, `language`, `out_ui_element`, `scope_id` |
| `gen_sap_call_transaction()` | NSAPCallTransaction | `transaction`, `prefix` (/n /o ""), `scope_id` |
| `gen_sap_click_toolbar()` | NSAPClickToolbarButton | `item` (Enter/Save/Back/Exit/Cancel), `scope_id` |
| `gen_sap_select_menu_item()` | NSAPSelectMenuItem | `item` (path with /), `scope_id` |
| `gen_sap_read_statusbar()` | NSAPReadStatusbar | `message_text`, `message_type`, `message_data`, `scope_id` |
| `gen_sap_table_cell_scope()` | NSAPTableCellScope | `column_name`, `row_type`, `sap_table_selector`, `column_names`, `scope_id`, `body_content` |
| `gen_sap_type_into_cell()` | TableCellScope + NTypeInto | `column_name`, `text_variable`, `sap_table_selector`, `column_names`, `scope_id` |
| `gen_sap_status_bar_check()` | ReadStatusbar + condition | Returns `(xml, condition_expr)` tuple |
| `indent_xml()` | (utility) | `xml_str`, `level`, `spaces=2` — re-indent for body composition |

**Variable names:** Pass BARE names (no brackets). Generators wrap automatically: `"strClient"` → `Client="[strClient]"`

**Selectors:** Pass raw selector strings from `inspect-sap-tree.ps1` output: `"<sap id='usr/.../txtFIELD' />"` → XML-escaped in TargetAnchorable

## Toolbar Button Shortcuts

| Short name | Full label | Selector |
|---|---|---|
| `"Enter"` | Enter | `tbar[0]/btn[0]` |
| `"Save"` | Save   (Ctrl+S) | `tbar[0]/btn[11]` |
| `"Back"` | Back   (F3) | `tbar[0]/btn[3]` |
| `"Exit"` | Exit   (Shift+F3) | `tbar[0]/btn[15]` |
| `"Cancel"` | Cancel   (F12) | `tbar[0]/btn[12]` |

## Usage Examples

```python
from extensions.generators import *
# For uipath-core activities:
from generate_activities import gen_logmessage, gen_retryscope, gen_getrobotcredential, gen_if, gen_throw, gen_invoke_workflow

scope_guid = _guid()

# ── SAP_Launch.xaml body ──
get_cred = gen_getrobotcredential("in_strCredentialAssetName", "strUsername", "secstrPassword", "GetRobotCredential_1")
retry_cred = gen_retryscope(body_content=get_cred, id_ref="RetryScope_1")
login = gen_sap_login(username="strUsername", secure_password="secstrPassword",
                      client="in_strClient", language="in_strLanguage",
                      out_ui_element="out_UISAP", scope_id=scope_guid)

body = indent_xml(retry_cred, 4) + "\n" + indent_xml(login, 4)
launch = gen_sap_logon(sap_connection="in_strConnection", sap_exe_path="in_strSapLogonPath",
                       scope_guid=scope_guid, body_content=body,
                       body_variables=[("in_strClient", "x:String"), ("in_strLanguage", "x:String"),
                                       ("strUsername", "x:String"), ("secstrPassword", "ss:SecureString")])

# ── Action workflow body (attach only — uses NApplicationCard, NOT NSAPLogon) ──
from generate_activities import gen_napplicationcard
scope2 = _guid()
navigate = gen_sap_call_transaction(transaction="in_strTransaction", prefix="/n", scope_id=scope2)
enter = gen_sap_click_toolbar(item="Enter", scope_id=scope2)
# NTypeInto from uipath-core — selector from inspection:
# type_vendor = gen_ntypeinto("Type Vendor", "<sap id='usr/.../ctxtMEPO_TOPLINE-SUPERFIELD' />",
#                             "in_strVendor", "NTypeInto_1", scope2)

body2 = indent_xml(navigate, 4) + "\n" + indent_xml(enter, 4)
action = gen_napplicationcard(display_name="SAP Easy Access", open_mode="Never", close_mode="Never",
                              scope_guid=scope2,
                              selector="<wnd app='saplogon.exe' cls='SAP_FRONTEND_SESSION' />",
                              body_content=body2)

# ── Save + Status Bar ──
save = gen_sap_click_toolbar(item="Save", scope_id=scope2)
read_sb = gen_sap_read_statusbar(message_text="strStatusBarMsg", message_type="strStatusBarMsgType",
                                 message_data="arr_StatusBarMsgData", scope_id=scope2)
# Then gen_if + gen_throw for error handling

# ── Table cell ──
cell = gen_sap_type_into_cell(column_name="Order Quantity", text_variable="in_strQuantity",
                               sap_table_selector="<sap id='usr/.../tblSAPLMEGUITC_1211' />",
                               column_names=["Status", "Short Text", "Order Quantity", "Plant"],
                               scope_id=scope2)
```

## Common Mistakes the Model Makes

| ❌ Wrong | ✅ Correct | Rule |
|---|---|---|
| `Client="[&quot;800&quot;]"` | `Client="[in_strClient]"` | Rule 9: no hardcoded values |
| `AssetName="[&quot;SAP_CREDS&quot;]"` | `AssetName="[in_strCredentialAssetName]"` | Rule 9 |
| `s:SecureString` | `ss:SecureString` (xmlns:ss=System.Security) | SAP-029 |
| `<p:ActivityAction>` | `<ActivityAction>` (no p: prefix) | Generator fixed |
| `Transaction="[ME21N]"` | `Transaction="[&quot;ME21N&quot;]"` or `Transaction="[in_strTransaction]"` | Generator handles escaping |
| Everything in one workflow | Decompose: SAP_Launch, SAP_FillHeader, SAP_FillTable, SAP_Save | Rule 8 |
| `NSAPLogon(Never)` for attach | `NApplicationCard(Never)` for attach — NSAPLogon is ONLY for launch/open | SKILL.md §Scope |
| CallTransaction inside SAP_Launch | CallTransaction in action workflow | Launch = login ONLY |
| `NClick` on toolbar Save button | `gen_sap_click_toolbar(item="Save")` | Rule 7 |
| Guessed selectors `<sap id='usr/txtFIELD' />` | Run `inspect-sap-tree.ps1` first | Rule 1 |
| Reading generator source / golden samples | Just use generators — trust them | `sap-generation.md` |
| Writing 10K+ generation script | Direct composition: `body = indent_xml(a, 4) + "\n" + indent_xml(b, 4)` | Keep it simple |
| `NTypeInto` with Target inside TableCellScope | `NTypeInto` with `InUiElement` inside TableCellScope | SAP-028 |
| Credential retrieval outside Launch | `GetRobotCredential` inside SAP_Launch.xaml only | Rule 4 |
| `SAP_Login.xaml` | `SAP_Launch.xaml` (core lint 72 requires _Launch) | Naming |
| Pick/NCheckState login validation | Not needed for SAP — NSAPLogin throws on auth failure | False positive lint 69 |

## Naming Quick Reference (SAP-specific)

| Type | Variable | Argument |
|---|---|---|
| String | `strUsername` | `in_strVendor`, `out_strPoNumber` |
| SecureString | `secstrPassword` | — (never passed as arg) |
| String[] | `arr_StatusBarMsgData` | — |
| UiElement (table cell) | `uiElOrderQuantityCell` | — |

## Selector-Free Activities (no inspection needed)

- `gen_sap_logon()` — NSAPLogon scope (launch ONLY)
- `gen_napplicationcard()` — NApplicationCard scope (attach — from uipath-core)
- `gen_sap_login()` — NSAPLogin auth
- `gen_sap_call_transaction()` — NSAPCallTransaction
- `gen_sap_click_toolbar()` — NSAPClickToolbarButton (standard system toolbar)
- `gen_sap_select_menu_item()` — NSAPSelectMenuItem
- `gen_sap_read_statusbar()` — NSAPReadStatusbar

## Activities Requiring Selectors from Inspection

- `NTypeInto` — SAP text/context fields
- `NClick` — SAP buttons, tabs, labels in user area
- `NGetText` — read SAP field values
- `NSelectItem` — SAP ComboBox dropdowns
- `gen_sap_table_cell_scope()` — needs table selector + column names

---

## SAP Selector Patterns

### Window Selector
```xml
<wnd app='saplogon.exe' cls='SAP_FRONTEND_SESSION' title='Create Purchase Order' />
```
Use wildcards for dynamic titles: `title='*/* Create Purchase Order'`

### Field Selectors
```xml
<!-- Text field -->
<sap id='usr/subSUB0:SAPLMEGUI:0016/.../txtMEPO_TOPLINE-EBELN' />

<!-- Context field (has search help F4) -->
<sap id='usr/subSUB0:SAPLMEGUI:0016/.../ctxtMEPO_TOPLINE-SUPERFIELD' />

<!-- ComboBox -->
<sap id='usr/subSUB0:SAPLMEGUI:0016/.../cmbMEPO_TOPLINE-BSART' />

<!-- Label -->
<sap id='usr/subSUB0:SAPLMEGUI:0016/.../lblMEPO_TOPLINE-BEDAT' />

<!-- Button in user area -->
<sap id='usr/subSUB0:SAPLMEGUI:0016/.../btnDETAIL' />

<!-- Tab -->
<sap id='usr/.../tabsHEADER_DETAIL/tabpTABHDT11' />
```

### Toolbar Selectors
```xml
<!-- System toolbar (tbar[0]) -->
<sap id='tbar[0]/btn[0]' />   <!-- Enter -->
<sap id='tbar[0]/btn[11]' />  <!-- Save (Ctrl+S) -->
<sap id='tbar[0]/btn[3]' />   <!-- Back (F3) -->
<sap id='tbar[0]/btn[15]' />  <!-- Exit (Shift+F3) -->
<sap id='tbar[0]/btn[12]' />  <!-- Cancel (F12) -->
```

### Table Selectors
```xml
<!-- Table control -->
<sap id='usr/subSUB0:.../tblSAPLMEGUITC_1211' />

<!-- Table cell (used by NSAPTableCellScope internally) -->
<sap id='usr/subSUB0:.../tblSAPLMEGUITC_1211' tableRow='0' tableCol='4' />
```

### Modal/Popup Selectors
```xml
<!-- Popup windows use wnd[1], wnd[2], etc. -->
<wnd app='saplogon.exe' cls='#32770' title='*/* Save Incomplete Document' idx='*' />
<sap id='usr/btnSPOP-VAROPTION1' />  <!-- First option button in popup -->
```

### SAP Field Name Prefixes
| Prefix | Control Type | Example |
|---|---|---|
| `txt` | GuiTextField | `txtMEPO_TOPLINE-EBELN` |
| `ctxt` | GuiCTextField (context/search help) | `ctxtMEPO_TOPLINE-SUPERFIELD` |
| `cmb` | GuiComboBox | `cmbMEPO_TOPLINE-BSART` |
| `lbl` | GuiLabel | `lblMEPO_TOPLINE-BEDAT` |
| `btn` | GuiButton | `btnDETAIL` |
| `chk` | GuiCheckBox | `chkFIELD_NAME` |
| `rad` | GuiRadioButton | `radFIELD_NAME` |
| `tab` | GuiTab (in tabstrip) | `tabpTABHDT11` |
| `tabs` | GuiTabStrip (container) | `tabsHEADER_DETAIL` |
| `tbl` | GuiTableControl | `tblSAPLMEGUITC_1211` |
| `sub` | GuiSimpleContainer | `subSUB0:SAPLMEGUI:0016` |
| `ssub` | Sub-tabstrip container | `ssubTABSTRIPCONTROL2SUB:SAPLMEGUI:1221` |
| `cntl` | GuiCustomControl | `cntlCONTROL` |
| `shell` | GuiShell (ALV Grid) | `shell` |

---

## Common SAP Workflow Patterns

### Pattern 1a: Launch (SAP_Launch.xaml only)
```
NSAPLogon (scope, OpenMode=Always)
  └─ RetryScope + GetRobotCredential
  └─ NSAPLogin (authenticate)
```

### Pattern 1b: Action Workflow (attach to existing session)
```
NApplicationCard (scope, OpenMode=Never)
  └─ NSAPCallTransaction (navigate to tcode)
  └─ ... (workflow actions — NTypeInto, NClick, etc.)
```

### Pattern 2: Status Bar Validation (after every write)
```
NClick (Save button) OR NSAPClickToolbarButton (Save)
NSAPReadStatusbar → strStatusBarMsg, strStatusBarMsgType
If strStatusBarMsgType.Equals("E")
  Then: Throw BusinessRuleException(strStatusBarMsg)
  Else: Continue
```

### Pattern 3: Table Cell Interaction
```
NSAPTableCellScope (ColumnName="Order Quantity", RowType="FirstEmptyRow")
  └─ NTypeInto (InUiElement=[uiElCell], Text=[strQuantity])
```
The scope outputs a `UiElement` reference that child activities use via `InUiElement`.

### Pattern 4: Conditional Section (Header open/closed)
```
Pick
  ├─ PickBranch: NCheckState (target=expanded section element) → already open
  └─ PickBranch: NCheckState (target=toggle button) → Click to expand
```

### Pattern 5: Popup/Modal Handling
```
NCheckState (target=popup button, using popup window selector)
  IfExists: NClick (handle popup)
  IfNotExists: (continue)
```
Popup selectors use `cls='#32770'` and `idx='*'` for the window, with `wnd[1]` scope.

### Pattern 6: Close SAP
```
NApplicationCard (OpenMode=Never, CloseMode=Always)
  Target: <wnd app='saplogon.exe' cls='SAP_FRONTEND_SESSION' title='SAP Easy Access' />
  Body: (empty)
```
