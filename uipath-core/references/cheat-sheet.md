# UiPath XAML Cheat Sheet

Quick-reference for generator commands and rules. For XAML output, **always use generators** — never hand-write activity XAML. Full 95-generator API with all parameters: see `skill-guide.md` § Activity Generators.

## ⛔ Workflow Creation: JSON Spec → .xaml (PRIMARY)

```bash
python3 scripts/generate_workflow.py spec.json Workflows/ACME/ACME_Launch.xaml --project-dir <project>
```

`--project-dir` auto-wires Object Repository references (`Reference=`/`ContentHash=` on TargetAnchorable) from `.objects/refs.json`. **Always pass it** after Object Repository generation.

**Pre-validate specs** (catches hallucinated types like `Dictionary(String,Object)` before generation):
```bash
python3 scripts/generate_workflow.py --validate-spec spec1.json spec2.json spec3.json
```

⛔ Rules G-1, G-2 — write spec to disk first, never hand-write .xaml. See `rules.md` for rationale and `generation.md` for full spec format.

Minimal spec:
```json
{"class_name": "AppName_Action",
 "arguments": [{"name": "io_uiApp", "direction": "InOut", "type": "UiElement"}],
 "activities": [
   {"gen": "log_message", "args": {"message_expr": "\"[START] AppName_Action\""}},
   {"gen": "napplicationcard_attach",
    "args": {"display_name": "App", "ui_element_variable": "io_uiApp"},
    "children": [
      {"gen": "nclick", "args": {"display_name": "Click 'Submit'", "selector": "<webctrl id='btn' tag='BUTTON' />"}}
    ]},
   {"gen": "log_message", "args": {"message_expr": "\"[END] AppName_Action\""}}
]}
```

### Argument/Variable Type Keys (short forms — ALWAYS use these)

| Spec `"type"` | XAML output | ⛔ NEVER use |
|---|---|---|
| `"String"` | `x:String` | |
| `"Int32"` | `x:Int32` | |
| `"Int64"` | `x:Int64` | |
| `"Boolean"` | `x:Boolean` | |
| `"Double"` | `x:Double` | |
| `"Decimal"` | `x:Decimal` | |
| `"Object"` | `x:Object` | |
| `"DateTime"` | `s:DateTime` | |
| `"TimeSpan"` | `s:TimeSpan` | |
| `"SecureString"` | `ss:SecureString` | |
| `"UiElement"` | `ui:UiElement` | |
| `"QueueItem"` | `ui:QueueItem` | |
| `"GenericValue"` | `ui:GenericValue` | |
| `"DataTable"` | `sd:DataTable` | |
| `"DataRow"` | `sd:DataRow` | |
| `"Dictionary"` | `scg:Dictionary(x:String, x:Object)` | `Dictionary(String,Object)` |
| `"Array_String"` | `s:String[]` | |
| `"Array_Int32"` | `s:Int32[]` | |
| `"Array_Object"` | `s:Object[]` | |
| `"JObject"` | `njl:JObject` | |
| `"JArray"` | `njl:JArray` | |
| `"MailMessage"` | `snm:MailMessage` | |

The generator auto-maps these 22 shortcuts. Using long-form types like `Dictionary(String,Object)` crashes Studio.

### JSON Spec Patterns (common trip-ups)

**multiple_assign** — assignments is array of `[target, expression]` pairs:
```json
{"gen": "multiple_assign", "args": {
  "display_name": "Extract Fields",
  "assignments": [
    ["strClientID", "strRaw.Split({\"Client ID:\",\"Client Name:\"}, StringSplitOptions.None)(1).Trim()"],
    ["strHash", "strRawResult.Trim()"]
  ]
}}
```

**assign** — single assignment:
```json
{"gen": "assign", "args": {"to_variable": "strUrl", "value_expression": "String.Format(\"{0}/login\", in_strBaseUrl)"}}
```

**nselectitem** — `item_variable` is a VB expression (quoted string for literal):
```json
{"gen": "nselectitem", "args": {"display_name": "Select 'Completed'", "selector": "<webctrl id='status' tag='SELECT' />", "item_variable": "\"Completed\""}}
```

**if** — uses `then_children` / `else_children` (not `then_content`):
```json
{"gen": "if", "args": {"condition_expression": "String.IsNullOrEmpty(strValue)"},
 "then_children": [{"gen": "throw", "args": {"exception_expression": "New BusinessRuleException(\"Empty value\")"}}],
 "else_children": [{"gen": "log_message", "args": {"message_expr": "\"Value: \" & strValue"}}]}
```

**try_catch** — uses `try_children`, catches array with `children`:
```json
{"gen": "try_catch", "args": {"catches": [{"exception_type": "System.Exception", "name": "ex"}]},
 "try_children": [{"gen": "log_message", "args": {"message_expr": "\"Trying...\""}}]}
```

**foreach_row** — uses `children` for body:
```json
{"gen": "foreach_row", "args": {"datatable_variable": "dt_WorkItems", "row_variable": "row"},
 "children": [{"gen": "log_message", "args": {"message_expr": "row(\"WIID\").ToString"}}]}
```

**pick_login_validation** — inside napplicationcard_open children. **REQUIRED**: spec must declare variables `strErrorText` (String) and `uiErrorElement` (UiElement) — the generator references them internally:
```json
{"gen": "pick_login_validation", "args": {
  "success_selector": "<webctrl tag='H1' aaname='Dashboard' />",
  "error_selector": "<webctrl tag='DIV' class='alert alert-danger' />"
}}
```
Spec `variables` must include: `{"name": "strErrorText", "type": "String"}` and `{"name": "uiErrorElement", "type": "UiElement"}`.

**nextractdata** — `extract_metadata` is **REQUIRED** (UiPath throws 'Value for required activity argument Extract metadata was not supplied' without it). Must contain `<extract>` XML with `<row>` and `<column>` definitions:
```json
{"gen": "nextractdata", "args": {
  "display_name": "Extract Data 'Work Items'",
  "output_variable": "dt_WorkItems",
  "extract_metadata": "<extract><row exact='1'><column exact='1' name='WIID' attr='innertext' tag='TD' /><column exact='1' name='Description' attr='innertext' tag='TD' /><column exact='1' name='Type' attr='innertext' tag='TD' /></row></extract>",
  "extract_data_settings": "<extractSettings><setting name='TextProcessing' value='Exact text' /></extractSettings>",
  "table_selector": "<webctrl tag='TABLE' id='theTable' />",
  "next_link_selector": "<webctrl tag='A' aaname='Next' />",
  "max_results": 0
}}
```

**filter_data_table** — `datatable_variable` (NOT source_datatable), filters are `[col, op, value, bool_op]` or `[col, op, value, bool_op, type]`.
**op** must be a UiPath `FilterOperator` enum value (ALL CAPS): `EQ`, `NE`, `LT`, `LE`, `GT`, `GE`, `CONTAINS`, `STARTS_WITH`, `ENDS_WITH`, `EMPTY`, `NOT_EMPTY`. **NOT** symbolic operators (`=`, `!=`, `<`, `>` — crash) or mixed-case (`Contains`, `IsEmpty` — auto-normalized but use CAPS). For `EMPTY`/`NOT_EMPTY`: value is ignored. For numeric comparisons: add 5th element `"x:Int32"`:
```json
{"gen": "filter_data_table", "args": {
  "datatable_variable": "dt_WorkItems",
  "filters": [["Type", "EQ", "WI5", "And"], ["Status", "EMPTY", "", "And"], ["Count", "GT", "10", "And", "x:Int32"]],
  "output_variable": "dt_Filtered"
}}
```

**add_queue_item** — `queue_name_config` (NOT queue_name_variable), `item_fields` is a **dict** `{key: vb_expression}`:
```json
{"gen": "add_queue_item", "args": {
  "queue_name_config": "in_Config(\"OrchestratorQueueName\").ToString",
  "folder_path_config": "in_Config(\"OrchestratorQueueFolder\").ToString",
  "item_fields": {"WIID": "strWIID", "ClientID": "strClientID"},
  "reference_variable": "strWIID"
}}
```

### Desktop App Launch (with path from argument)

```json
{"gen": "napplicationcard_desktop_open", "args": {
    "display_name": "Open AppName",
    "file_path_variable": "in_strAppPath",
    "out_ui_element": "out_uiAppName",
    "target_app_selector": "<wnd app='appname.exe' title='App Title*' />"
  },
  "children": [...]
}
```
**Important:** Use `in_strAppPath` argument (not hardcoded path). Lint 104 warns on `C:\Users\...` paths.

### invoke_workflow — JSON spec arguments format

Arguments is a dict of `{arg_name: [direction, type, value_expression]}` **arrays** (NOT dicts):
```json
{"gen": "invoke_workflow", "args": {
    "workflow_path": "Workflows\\AppName\\AppName_FillForm.xaml",
    "display_name": "Invoke AppName_FillForm",
    "arguments": {
        "io_uiApp":       ["InOut", "UiElement", "uiApp"],
        "in_strFirstName": ["In",   "String",    "\"John\""],
        "in_boolActive":   ["In",   "Boolean",   "True"],
        "out_strResult":   ["Out",  "String",    "strResult"]
    }
}}
```
⛔ NOT `{"in_strName": {"direction": "In", "type": "String", "value": "..."}}` — dict-of-dicts crashes at generation time.

### Object Repository Binding in JSON Specs (Rule G-9)

After `generate_object_repository.py` produces `refs.json`, inject references into every UI activity spec:

```json
{"gen": "nclick", "args": {
    "display_name": "Click 'Login'",
    "selector": "<webctrl tag='BUTTON' aaname='Login' />",
    "obj_repo": {"reference": "LIB/ELEM", "content_hash": "HASH", "guid": "GUID"}
}}
```

- `obj_repo` keys: `reference`, `content_hash`, `guid` — from `refs.json → elements → "App/Screen/Element"`
- `obj_repo_app` keys: `reference`, `content_hash` — from `refs.json → apps → "AppName"` (for napplicationcard_open/desktop_open)
- Skip `obj_repo` for NCheckState targeting elements NOT in selectors.json (e.g., group box labels used as wait conditions)

## selectors.json (Phase 2b — write after Playwright inspection)

```bash
python3 scripts/generate_object_repository.py --from-selectors selectors.json --project-dir ./CCSH_Dispatcher
```

```json
{"apps": [{
  "name": "ACME System 1",
  "selector": "<html app='msedge.exe' title='ACME System 1*' />",
  "browser_type": "Edge",
  "screens": [
    {"name": "Login", "url": "https://acme-test.example.com/login", "elements": [
      {"name": "Email",        "selector": "<webctrl id='email' tag='INPUT' />",  "taxonomy_type": "Input"},
      {"name": "Password",     "selector": "<webctrl id='password' tag='INPUT' />","taxonomy_type": "Password"},
      {"name": "LoginButton",  "selector": "<webctrl tag='BUTTON' aaname='Login' />","taxonomy_type": "Button"},
      {"name": "Dashboard",    "selector": "<webctrl tag='H1' aaname='Dashboard' />","taxonomy_type": "Text"},
      {"name": "ErrorMessage", "selector": "<webctrl tag='DIV' class='alert' />", "taxonomy_type": "Text"}
    ]},
    {"name": "WorkItems", "url": "https://acme-test.example.com/work-items", "elements": [
      {"name": "Table",     "selector": "<webctrl tag='TABLE' />",           "taxonomy_type": "Text"},
      {"name": "NextPage",  "selector": "<webctrl tag='A' aaname='>' />",    "taxonomy_type": "Link"}
    ]}
  ]
}]}
```

taxonomy_type: `Input` | `Password` | `Button` | `Dropdown` | `Link` | `CheckBox` | `RadioButton` | `Text`

**Desktop app selectors.json** — use `<ctrl>` selectors with `name` and `role` for WinForms desktop controls:
```json
{"apps": [{
  "name": "MyCRM",
  "selector": "<wnd app='mycrm.exe' title='My CRM*' />",
  "screens": [
    {"name": "PeopleTab", "elements": [
      {"name": "FirstName", "selector": "<ctrl name='First' role='editable text' />", "taxonomy_type": "Input"},
      {"name": "SaveButton", "selector": "<ctrl name='Save' role='push button' />", "taxonomy_type": "Button"}
    ]}
  ]
}]}
```
App `type` is auto-detected from selector prefix: `<wnd>` → desktop, `<html>` → browser. Override with `"type": "desktop"` or `"type": "browser"` if needed.

**Tag-attribute mapping for desktop apps:**
- `<wnd>` tag: `aaname`, `ctrlname`, `ctrlid`, `cls`, `app`, `title`, `idx`
- `<ctrl>` tag: `name`, `role`, `automationid`, `labeledby`, `text`, `idx`
- `<uia>` tag: `name`, `role`, `automationid`, `cls`, `idx`

⚠️ `aaname` is ONLY valid on `<wnd>` tags. `<ctrl>` and `<uia>` use `name` instead.

## Generator Quick Reference (for single-activity insertion into existing files)

```python
from scripts.generate_activities import *
```

**Most-used generators (top 10):**

| Function | Activity | Key params |
|---|---|---|
| `gen_napplicationcard_open()` | NApplicationCard (Launch) | `display_name`, `url_variable`, `out_ui_element`, `scope_guid`, `body_content` |
| `gen_napplicationcard_attach()` | NApplicationCard (Action) | `display_name`, `ui_element_variable`, `scope_guid`, `body_content` |
| `gen_napplicationcard_desktop_open()` | NApplicationCard (Desktop) | `display_name`, `file_path_variable`, `out_ui_element`, `scope_guid`, `body_content` |
| `gen_ntypeinto()` | NTypeInto | `display_name`, `selector`, `text_variable`, `id_ref`, `scope_id`, `is_secure=False` |
| `gen_nclick()` | NClick | `display_name`, `selector`, `id_ref`, `scope_id` |
| `gen_ncheck()` | NCheck (checkbox) | `display_name`, `selector`, `id_ref`, `scope_id`, `action="Check"/"Uncheck"/"Toggle"` |
| `gen_ngettext()` | NGetText | `display_name`, `output_variable`, `id_ref`, `scope_id`, `selector=` OR `in_ui_element=` |
| `gen_getrobotcredential()` | GetRobotCredential | `asset_name_variable`, `username_variable`, `password_variable`, `id_ref` |
| `gen_invoke_workflow()` | InvokeWorkflowFile | `workflow_path`, `display_name`, `id_ref`, `arguments={}` |
| `gen_pick_login_validation()` | Pick (2-branch) | `success_selector`, `error_selector`, `error_ui_variable`, `scope_id`, + idref params |
| `gen_try_catch()` | TryCatch | `try_content`, `try_sequence_idref`, `id_ref`, `catches` |
| `gen_logmessage()` | LogMessage | `message`, `id_ref`, `level="Info"` |
| `gen_build_data_table()` | BuildDataTable | `datatable_variable`, `columns=[(name, type)]`, `id_ref`, `initial_rows=` |
| `gen_create_form_task()` | CreateFormTask | `task_title_expr`, `task_output_variable`, `form_layout_json`, `id_ref`, `form_data=` |
| `gen_wait_for_form_task()` | WaitForFormTaskAndResume | `task_input_variable`, `id_ref` |
| `gen_get_imap_mail()` | GetIMAPMailMessages | `messages_variable`, `id_ref`, `filter_expression_variable=`, `mail_folder=` |
| `gen_save_mail_attachments()` | SaveMailAttachments | `message_variable`, `folder_path_variable`, `id_ref`, `file_filter=` |

For all 95 core generators + plugin extensions → `generation.md` § Activity Generators.

## Framework Wiring (modify_framework.py)

⛔ **Rule G-3** — all XAML snippets passed to insert-invoke/replace-marker MUST come from generator output. Never hand-write, especially for FilterDataTable, AddQueueItem, BuildDataTable, NExtractData, or TryCatch.

⛔ **Snippet argument = XAML content, never a file path.** `modify_framework.py` validates that the snippet is actual XML and rejects file paths, JSON, or other non-XAML text.

**CLI commands** (use these — don't import Python functions directly):
```bash
# Wire UiElement chain (adds arguments across Init→Main→Process→Close)
python3 scripts/modify_framework.py wire-uielement <project_dir> <AppName>

# Insert XAML snippet before </Sequence> in framework file
python3 scripts/modify_framework.py insert-invoke <filepath> <xaml_snippet>

# Replace a SCAFFOLD marker with XAML content
python3 scripts/modify_framework.py replace-marker <filepath> <marker_name> <xaml_snippet>

# Add variables to a framework file (creates Sequence.Variables block if needed)
python3 scripts/modify_framework.py add-variables <filepath> varName1:x:String varName2:x:Int32 ...

# List available markers in a file
python3 scripts/modify_framework.py list-markers <filepath>
```

⛔ **NEVER add variables to framework files via Write/Edit tool.** Use `add-variables` — it handles indent, creates the `<Sequence.Variables>` block if missing, and skips duplicates.

**Python API** (only if CLI isn't enough — use correct names):
```python
from scripts.modify_framework import cmd_insert_invoke, cmd_replace_marker, cmd_wire_uielement, cmd_add_variables
# ⛔ NOT insert_invoke_before_close, NOT replace_marker (these don't exist)
```

**Generator Python API gotchas** (when calling from helper scripts):
```python
# gen_if: condition_expression (NOT condition), NO then_sequence_idref
gen_if(condition_expression='x > 0', id_ref='If_1', then_content=body, else_content='')

# gen_multiple_assign: assignments is list of [target, expression] ARRAYS
gen_multiple_assign(assignments=[["strA", "row(\"Col\").ToString"]], id_ref='MA_1')

# gen_invoke_workflow: use raw strings for Windows paths, types need x: prefix
# arguments is a DICT: {arg_name: (direction, type, value_expression)}
gen_invoke_workflow(workflow_path=r'Workflows\Utils\App_Close.xaml', ...,
    arguments={"in_strUrl": ("In", "x:String", "in_Config(\"Url\").ToString"), "io_uiApp": ("InOut", "ui:UiElement", "io_uiApp")})
# ⛔ NOT "String" → must be "x:String". NOT "UiElement" → must be "ui:UiElement"
# ⛔ NOT a list of tuples → must be a dict keyed by argument name

# gen_filter_data_table: datatable_variable (NOT source_datatable)
gen_filter_data_table(datatable_variable='dt_Data', filters=[...], id_ref='FDT_1')

# gen_add_queue_item: queue_name_config (NOT queue_name_variable), item_fields is a DICT (NOT list/fields/items)
gen_add_queue_item(queue_name_config='in_Config("OrchestratorQueueName").ToString', id_ref='AQI_1',
    item_fields={"WIID": "strWIID", "ClientID": "strClientID"})
```

**Variable names:** Pass BARE names (no brackets). Generators wrap automatically: `"strEmail"` → `Text="[strEmail]"`
**Selectors:** Pass raw selector strings: `"<webctrl tag='INPUT' id='email' />"` → XML-escaped in TargetAnchorable
**Object Repository:** Pass `obj_repo=refs["elements"]["AppName/ScreenName/ElementName"]` to bind activities to the Object Repository. Pass `obj_repo_app=refs["apps"]["AppName"]` to `gen_napplicationcard_open()`. Call `generate_object_repository(apps, project_dir)` after `scaffold_project()` to create `.objects/` tree.

### Usage Examples

```python
# Login workflow body
body = gen_getrobotcredential("in_strCredentialName", "strUsername", "secstrPassword", "GetRobotCredential_1")
body += "\n" + gen_ntypeinto("Type Into 'Email'", "<webctrl tag='INPUT' type='email' />", "strUsername", "NTypeInto_1", scope)
body += "\n" + gen_ntypeinto("Type Into 'Password'", "<webctrl tag='INPUT' type='password' />", "secstrPassword", "NTypeInto_2", scope, is_secure=True)
body += "\n" + gen_nclick("Click 'Login'", "<webctrl tag='BUTTON' aaname='Login' />", "NClick_1", scope)
# Wrap in NApplicationCard
card = gen_napplicationcard_open("Edge WebApp", "in_strAppUrl", "out_uiWebApp", scope, "NApplicationCard_1", body, "Sequence_2")
```

## Valid Enum Values (crash if wrong)

| Attribute | Valid | ❌ Hallucinated |
|---|---|---|
| `AttachMode` | `SingleWindow`, `ByInstance` | ~~`ByUrl`~~ |
| `OpenMode` | `Always`, `IfNotOpen`, `Never` | |
| `CloseMode` | `Always`, `Never`, `IfOpenedByAppBrowser` | |
| `InteractionMode` | `DebuggerApi`, `Simulate`, `WindowMessages`, `HardwareEvents`, `SameAsCard` | ~~`Hardware`~~ |
| `Version` (NApplicationCard) | `V2`, `V1` | ~~`V3`, `V4`~~ (crash) |
| `Version` (NClick/NCheck/NTypeInto/NGetText/NCheckState) | `V5` | |
| `Version` (TargetAnchorable) | `V6` | |

## Naming Quick Reference

| Type | Variable | In Arg | Out Arg |
|---|---|---|---|
| String | `strName` | `in_strName` | `out_strName` |
| Int32 | `intCount` | `in_intCount` | `out_intCount` |
| Boolean | `boolSuccess` | `in_boolFlag` | `out_boolSuccess` |
| DataTable | `dt_Report` | `in_dt_Data` | `out_dt_Report` |
| DataRow | `dr_Row` | `in_dr_Row` | `out_dr_Row` |
| Array/List | `arr_Files` / `list_Items` | `in_arr_Files` | `out_list_Items` |
| Dictionary | `dict_Config` | `in_dict_Config` | `out_dict_Config` |
| DateTime | `dtmStart` | `in_dtmDeadline` | `out_dtmStart` |
| Double/Decimal | `dblAmount` / `decPrice` | `in_dblAmount` | `out_decPrice` |
| JObject/JArray | `jo_Response` / `ja_Results` | `in_jo_Data` | `out_ja_Results` |
| SecureString | `secstrPassword` | — | — |
| UiElement | `uiWebApp` | `in_uiApp` | `out_uiWebApp` |
| MailMessage | `mm_Mail` | `in_mmMail` | — |
| QueueItem | `qi_Item` | — | — |

**Workflow files:** PascalCase with underscores — `WebApp_CreateRecord.xaml`, `App_Close.xaml`, `Api_FetchInvoices.xaml`

## Quick Rules

**XAML syntax (crash if wrong):**
- Enum namespace: `UiPath.UIAutomationNext.Enums` — NOT `UIAutomation.Enums`. Do NOT "fix" `UIAutomationNext` when copying templates
- Child element for target: `.Target>` — NEVER `.TargetAnchorable>` (that's the TYPE, not the element name)
- NTypeInto: `ClickBeforeMode` (not `ClickBeforeTyping`), `EmptyFieldMode` valid values: `None`, `SingleLine`, `MultiLine` (NOT `Clear` — crashes Studio)
- Child activity `InteractionMode`: `SameAsCard` — NOT a specific mode like `Simulate`
- SearchSteps: default `"Selector"` (strict). `"FuzzySelector"` only when strict proven unreliable
- Throw: `[New BusinessRuleException("msg")]` (VB.NET) — NOT C# `throw new`
- Passwords: `SecureText=` — never `Text=`
- AddQueueItem: `.ItemInformation` — NEVER `.SpecificContent`
- BuildDataTable: `TableInfo="..."` XSD — NEVER `.Columns` / `DataTableColumnInfo`
- Launch workflows: NO NGoToUrl — `NApplicationCard OpenMode="Always"` + `TargetApp Url=` opens the browser at the URL

**Architecture** (full definitions: `rules.md` § A-1 through A-12, P-1 through P-3, I-1 through I-4)**:**
- Browser defaults: `IsIncognito="True"`, `InteractionMode="Simulate"`, `AttachMode="SingleWindow"` **(A-9)**
- Desktop defaults: NO IsIncognito, `Simulate` or `HardwareEvents`, `AttachMode="ByInstance"` **(A-9)**
- URLs from Config **(A-8)**, credentials inside workflow **(A-3)**, API/network RetryScope **(A-11)**
- Navigation: generic `Browser_NavigateToUrl.xaml` **(A-6)**. One browser per web app **(A-10)**
- App close: `App_Close.xaml` ONLY from CloseAllApplications. CloseAll ≠ KillAll (lint 65)
- REFramework: never modify SetTransactionStatus **(A-4)**. PDD adherence **(P-1)**
- Playwright: READ-ONLY **(I-1)**, login gate → HALT **(I-2)**
- After generating: Config.xlsx keys grouped by sheet, run `validate_xaml --lint`

## Desktop Form-Filling Patterns

Patterns for automating WinForms/WPF desktop apps. For web automation see `xaml-ui-automation.md`.

**Tab Navigation (Rule 14):** Desktop navigation is a **separate workflow** from screen action — same principle as browser rule 9. Create `AppName_NavigateToScreen.xaml` (clicks tab/menu + waits) and `AppName_FillScreen.xaml` (fills fields only). Use `ncheckstate` to verify the target tab loaded — never use Delay.

Navigate workflow (`DesktopApp_NavigateToCompanyTab.xaml`):
```json
{"gen": "nclick", "args": {"display_name": "Click 'Company' Tab", "selector": "<ctrl name='Company' role='tab item' />"}},
{"gen": "ncheckstate", "args": {"display_name": "Wait for Company tab fields", "selector": "<ctrl name='CompanyName' role='editable text' />", "if_exists_children": [{"gen": "log_message", "args": {"message_expr": "\"Company tab loaded\"", "level": "Trace"}}], "if_not_exists_children": [{"gen": "throw", "args": {"exception_expression": "New TimeoutException(\"Company tab did not load within timeout\")"}}]}}
```
**IMPORTANT:** Always provide `if_not_exists_children` with a Throw in navigation/wait NCheckState patterns. Empty IfNotExists = silent failure (lint 111).

Fill workflow (`DesktopApp_FillCompanyTab.xaml`) — no tab click, just fields:
```json
{"gen": "ntypeinto", "args": {"display_name": "Type Into 'CompanyName'", "selector": "...", "text_variable": "in_strCompanyName"}}
```

**CheckBox Handling:** Use `ncheck` (NOT `nclick`) for checkboxes. NCheck is idempotent: `Action="Check"` on an already-checked box does nothing. NClick toggles state and is not deterministic (lint 112). When `taxonomy_type` is `"CheckBox"`, always use the `ncheck` generator.
```json
{"gen": "ncheck", "args": {"display_name": "Check Active", "selector": "<ctrl name='Active' role='check box' />", "action": "Check"}}
```

**Index-Based Selector Mitigation:** WinForms often doesn't expose `ctrlname`/`AutomationId`. Use UI Explorer in Studio to find them, scope with parent container `title`, document fragile selectors, test on different data states.

**Save/Submit Verification:** Click Save → NCheckState for error dialog → Throw on error, log on success. Lint 103 warns on UI-heavy workflows without TryCatch.

**Desktop App Launch:** Use `napplicationcard_desktop_open` with `file_path_variable` from InArgument — never hardcode `C:\Users\...`. Lint 104 catches this.

**Desktop Scaffold:** When scaffolding a desktop-only project, always pass `target="desktop"` to `scaffold_project.py` to exclude browser utilities (Browser_NavigateToUrl.xaml). The default `target="both"` includes browser utils that will be flagged by lint 102 (orphaned workflow).

**Error Handling:** Wrap the entire UI block in TryCatch (Lint 103). Catch block should log the error and take a screenshot via `take_screenshot_and_save`.

## Hallucinated Properties (Common LLM Mistakes)

These property names look plausible but crash Studio. Generators avoid all of these automatically.

- `NApplicationCard Url=` → use `<uix:TargetApp Url=...>` child. `TargetAnchorable Selector=` → use `FullSelectorArgument=`. `<uix:Selector>` → doesn't exist
- `NCheckState Appears=` → use `.IfExists`/`.IfNotExists` children. `<uix:NClick.TargetAnchorable>` → child is `.Target>` not `.TargetAnchorable>`
- `NTypeInto ClickBeforeTyping=`/`EmptyField=` → use `ClickBeforeMode`/`EmptyFieldMode`
- `AddQueueItem.SpecificContent` → `.ItemInformation`. `.ItemInformation` with single `InArgument x:TypeArguments="scg:Dictionary(...)"` → crash. Use flat `<InArgument x:TypeArguments="x:String" x:Key="Name">[value]</InArgument>` entries directly under `.ItemInformation`
- `BuildDataTable.Columns`/`DataTableColumnInfo` → don't exist, use `TableInfo` XSD. `MultipleAssign.Body`/`AssignOperationSet`/`MultipleAssignBody`/`AssignItem` → don't exist. Correct: `.AssignOperations` > `scg:List x:TypeArguments="ui:AssignOperation"` > `ui:AssignOperation` (lint 52)
- `FilterDataTable.FilterRowsCollection` → `.Filters`. `FilterOperationArgument ColumnName=` → doesn't exist, use `.Column` child element with `InArgument`. `FilterOperationArgument Value=` → doesn't exist, use `.Operand` child element with `InArgument`. `FilterOperationArgument Operand="EQ"` (operator as Operand attr) → wrong, `Operator="EQ"` is the attribute for the comparison operator, `.Operand` is the child element for the value being compared against. **ALWAYS use `gen_filter_data_table()` — never hand-write FilterDataTable XAML.**
