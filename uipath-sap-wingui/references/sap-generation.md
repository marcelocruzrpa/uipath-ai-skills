# SAP Generation Workflow

**⚠️ ALWAYS read this before generating any SAP XAML.**

How to generate SAP workflows using uipath-core's `generate_workflow.py` and the SAP plugin generators. **DO NOT** read golden samples, generator source code, or reference docs to understand XAML structure. The generators produce correct XAML. Trust them.

## Primary Approach: JSON Spec → generate_workflow.py (G-1)

SAP generators are registered with uipath-core's plugin system and work with `generate_workflow.py`. This is the same approach used for all other workflows — write a JSON spec to disk, run the CLI.

```bash
# Write spec.json first (Rule G-2), then:
python3 uipath-core/scripts/generate_workflow.py spec.json Workflows/SAP/SAP_Launch.xaml
```

**SAP-specific `"gen"` values for JSON specs:**
`sap_login`, `sap_call_transaction`, `sap_click_toolbar`, `sap_select_menu_item`, `sap_read_statusbar`, `sap_table_cell_scope`

These compose with ALL core generators (`log_message`, `retryscope`, `getrobotcredential`, `if`, `throw`, `napplicationcard_attach`, etc.) in a single JSON spec.

**Container generators** (`sap_logon`, `sap_table_cell_scope`) require `body_content` — use Python composition (Recipe 1/4 below) instead of JSON spec `children`.

**Python-only helpers** (not usable as JSON `"gen"` values): `gen_sap_status_bar_check`, `gen_sap_type_into_cell`

**Example JSON spec — SAP_FillPOHeader.xaml (action workflow):**

Action workflows attach to the existing SAP session via `napplicationcard_attach` (core container), then use SAP generators inside.

```json
{
  "class_name": "SAP_FillPOHeader",
  "arguments": [
    {"name": "io_uiSAP", "direction": "InOut", "type": "UiElement"},
    {"name": "in_strTransaction", "direction": "In", "type": "String"},
    {"name": "in_strVendor", "direction": "In", "type": "String"}
  ],
  "activities": [
    {"gen": "log_message", "args": {"message_expr": "\"[START] SAP_FillPOHeader\""}},
    {"gen": "napplicationcard_attach",
     "args": {"display_name": "SAP Easy Access", "ui_element_variable": "io_uiSAP", "desktop": true,
              "target_app_selector": "<wnd app='saplogon.exe' cls='SAP_FRONTEND_SESSION' />"},
     "children": [
       {"gen": "sap_call_transaction", "args": {"transaction": "in_strTransaction", "prefix": "/n"}},
       {"gen": "ntypeinto", "args": {"display_name": "Type Into 'Vendor'",
        "selector": "<sap id='usr/ctxtEKKO-LIFNR' />", "text_variable": "in_strVendor"}},
       {"gen": "sap_click_toolbar", "args": {"item": "Enter"}}
     ]},
    {"gen": "log_message", "args": {"message_expr": "\"[END] SAP_FillPOHeader\""}}
  ]
}
```

> **SAP_Launch.xaml** uses `sap_logon` (a container generator) — generate it via Python composition (Recipe 1 below).

**Validate:**
```bash
python3 uipath-core/scripts/validate_xaml <project> --lint
```

## Fallback: Python Composition

For complex scenarios where JSON specs are unwieldy (e.g., dynamic body assembly, conditional generator calls), the direct Python API is still available. See `sap-cheat-sheet.md` for function signatures and recipes.

```python
# Plugin generators — available because plugin_loader adds core scripts/ to sys.path
from extensions.generators import *
from generate_activities import gen_logmessage, gen_retryscope, gen_getrobotcredential
```

**What NOT to do:**
- ❌ Read generator source code — function signatures are in `sap-cheat-sheet.md`
- ❌ Read `golden-samples/*.xaml` — generators handle XAML structure
- ❌ Write a 10K+ custom generation script — keep it simple

**Target: ≤15 tool calls** for a Login + Navigate scenario. If you're exceeding 20, you're over-reading.

---

## Generator Code Patterns

These are COMPLETE, RUNNABLE patterns. Do not read golden samples or generator source code. Just use these patterns directly.

### Recipe 1: Generate SAP_Launch.xaml (Login Only)

Write this script and run it. Produces a complete SAP_Launch.xaml.

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.claude', 'skills', 'uipath-sap-wingui', 'extensions'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.claude', 'skills', 'uipath-core', 'scripts'))
from generators import *
from generate_activities import gen_logmessage, gen_retryscope, gen_getrobotcredential

PROJECT_DIR = 'SAP_ProjectName'  # adjust
scope_guid = _guid()

# RetryScope + GetRobotCredential — asset name from argument, NEVER hardcoded
get_cred = gen_getrobotcredential(
    asset_name='in_strCredentialAssetName',   # ARGUMENT
    username_var='strUsername',
    password_var='secstrPassword',
    id_ref='GetRobotCredential_1',
)
retry_cred = gen_retryscope(body_content=get_cred, id_ref='RetryScope_1')

# NSAPLogin — Client/Language from scope variables, outputs UiElement session reference
login = gen_sap_login(
    username='strUsername',
    secure_password='secstrPassword',
    client='in_strClient',          # SCOPE VARIABLE
    language='in_strLanguage',      # SCOPE VARIABLE
    out_ui_element='out_UISAP',     # OUTPUT — session reference for action workflows
    scope_id=scope_guid,
)

log_start = gen_logmessage('"[START] SAP_Launch"', 'LogMessage_1')
log_end = gen_logmessage('"[END] SAP_Launch"', 'LogMessage_2')

body = '\n'.join([indent_xml(retry_cred, 4), indent_xml(login, 4)])

sap_scope = gen_sap_logon(
    sap_connection='in_strConnection',
    sap_exe_path='in_strSapLogonPath',
    scope_guid=scope_guid,
    body_content=body,
    body_variables=[
        ('in_strClient', 'x:String'),
        ('in_strLanguage', 'x:String'),
        ('strUsername', 'x:String'),
        ('secstrPassword', 'ss:SecureString'),
    ],
)

# Arguments: in_strCredentialAssetName, in_strConnection, in_strSapLogonPath, out_UISAP (UiElement)
```

### Recipe 2: Generate Action Workflow (Attach + Navigate + Field Interactions)

Action workflows use `NApplicationCard` (from uipath-core) — NOT `NSAPLogon`. `NSAPLogon` is only for the launch/open scenario.

```python
# SAP_FillPOHeader.xaml — attaches via NApplicationCard, navigates to tcode, fills fields
from generate_activities import gen_napplicationcard
scope_guid = _guid()

navigate = gen_sap_call_transaction(
    transaction='in_strTransaction',     # ARGUMENT — never hardcode
    prefix='/n',
    scope_id=scope_guid,
)

# NTypeInto, NSelectItem from uipath-core generators — use selectors from inspection
# type_vendor = gen_ntypeinto(text='in_strVendor', selector=SELECTOR_FROM_INSPECTION, ...)
# enter = gen_sap_click_toolbar(item='Enter', scope_id=scope_guid)

body = '\n'.join([indent_xml(navigate, 4), indent_xml(type_vendor, 4), indent_xml(enter, 4)])

sap_scope = gen_napplicationcard(
    display_name='SAP Easy Access',
    open_mode='Never',           # ATTACH ONLY — SAP_Launch.xaml already opened it
    close_mode='Never',
    scope_guid=scope_guid,
    selector="<wnd app='saplogon.exe' cls='SAP_FRONTEND_SESSION' />",
    body_content=body,
)
```

### Recipe 3: Save + Status Bar + Error Handling

```python
scope_guid = 'existing_scope_guid'  # same scope as the action workflow

save = gen_sap_click_toolbar(item='Save', scope_id=scope_guid)
read_sb = gen_sap_read_statusbar(
    message_text='strStatusBarMsg',
    message_type='strStatusBarMsgType',
    message_data='arr_StatusBarMsgData',
    scope_id=scope_guid,
)
# Then gen_if + gen_throw from uipath-core:
#   Condition: strStatusBarMsgType.Equals("E")
#   Then: Throw New BusinessRuleException(strStatusBarMsg)
```

### Recipe 4: Table Cell Type Into

```python
cell_xml = gen_sap_type_into_cell(
    column_name='Order Quantity',           # from inspection output
    text_variable='in_strQuantity',         # ARGUMENT — never hardcode
    sap_table_selector="<sap id='usr/sub.../tblSAPLMEGUITC_1211' />",  # from inspection
    column_names=['Status', 'Short Text', 'Order Quantity', 'Order Unit', 'Plant'],
    scope_id=scope_guid,
)
```

### Required xmlns for Variable Types
| Type | Prefix | xmlns Declaration |
|---|---|---|
| `x:String`, `x:Boolean`, `x:Int32` | `x:` | Already in default template |
| `s:String[]`, `s:Int32`, `s:DateTime` | `s:` | `xmlns:s="clr-namespace:System;assembly=System.Private.CoreLib"` |
| `ss:SecureString` | `ss:` | `xmlns:ss="clr-namespace:System.Security;assembly=System.Private.CoreLib"` |
| `sd:DataTable` | `sd:` | `xmlns:sd="clr-namespace:System.Data;assembly=System.Data.Common"` |
| `ui:UiElement` | `ui:` | Already in default template |

**⚠ SecureString is NOT `s:SecureString`** — that resolves to `System.SecureString` which doesn't exist. Must be `ss:SecureString`. Root Activity also needs `<x:String>System.Security</x:String>` in NamespacesForImplementation.

### Key Rules When Composing
- **`indent_xml(xml, 4)`** — use level 4 for activities inside NSAPLogon or NApplicationCard body
- **`indent_xml(xml, 6)`** — use level 6 for activities inside NSAPTableCellScope body
- **`scope_guid`** — generate ONCE per file, pass to ALL activities via `scope_id`
- **NSAPLogon** — ONLY for `SAP_Launch.xaml` (OpenMode="Always"). All action workflows use `NApplicationCard` (OpenMode="Never")
- **Selectors** — always from `inspect-sap-tree.ps1` output, NEVER guessed
- **Standard activities** (NTypeInto, NClick, NGetText, NSelectItem) — use uipath-core generators, just pass `<sap id='...' />` selectors
