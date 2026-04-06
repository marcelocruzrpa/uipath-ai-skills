# XAML Generation & Object Repository

Object Repository, Workflow Generation CLI (JSON specs), and Activity Generators (94 core generators + additional from installed plugin skills). For project scaffolding see `scaffolding.md`. For decomposition rules see `decomposition.md`.

## Object Repository

When a process has UI automation, generate an Object Repository to centrally manage all UI element definitions. This makes the project match Studio's native object-based targeting — elements are stored once in `.objects/` and referenced from XAML via `Reference` + `ContentHash` attributes.

### Generation Flow

```python
from generate_object_repository import generate_object_repository

# 1. Define applications, screens, and elements from PDD analysis
apps = [{
    "name": "ACME System1",                              # App display name
    "selector": "<html app='msedge.exe' title='ACME' />", # Window selector
    "url": "https://acme.example.com/login",              # App URL
    "browser_type": "Edge",                               # Edge | Chrome | Firefox
    "screens": [{
        "name": "Login",
        "url": "https://acme.example.com/login",
        "elements": [
            {"name": "Username",  "taxonomy_type": "Input",    "selector": "<webctrl id='username' tag='INPUT' />"},
            {"name": "Password",  "taxonomy_type": "Password", "selector": "<webctrl id='password' tag='INPUT' />"},
            {"name": "Login Btn", "taxonomy_type": "Button",   "selector": "<webctrl id='loginBtn' tag='BUTTON' />"},
        ]
    }]
}]

# 2. Generate .objects/ tree (call AFTER scaffold_project)
refs = generate_object_repository(apps, project_dir)

# 3. Pass references to activity generators
elem_ref = refs["elements"]["ACME System1/Login/Username"]
gen_ntypeinto("Type Into 'Username'", "<webctrl id='username' tag='INPUT' />",
              "in_strUsername", "NTypeInto_1", scope_id, obj_repo=elem_ref)

app_ref = refs["apps"]["ACME System1"]
gen_napplicationcard_open("ACME System1", "strUrl", "elApp", scope_guid,
                          "NApplicationCard_1", body, body_seq,
                          target_app_selector="<html app='msedge.exe' title='ACME' />",
                          obj_repo_app=app_ref)
```

### Taxonomy Types

| TaxonomyType | ElementType       | Use for                    |
|-------------|-------------------|----------------------------|
| Input       | InputBox          | Text fields                |
| Password    | InputBoxPassword  | Password fields            |
| Button      | Button            | Buttons, submit controls   |
| Dropdown    | DropDown          | Select/dropdown controls   |
| Link        | Link              | Hyperlinks                 |
| CheckBox    | CheckBox          | Checkboxes                 |
| RadioButton | RadioButton       | Radio buttons              |
| Text        | Text              | Read-only text elements    |

### What Gets Generated

- `.objects/` — Full hierarchy: Library → App → AppVersion → Screen → Element
- `.entities/` — Empty (reserved for Studio)
- `.templates/` — Empty (reserved for Studio)
- `.tmh/config.json` — Test management hook config
- `.screenshots/` — Empty (Studio regenerates on first interaction)

### XAML Integration

Activities get two extra attributes on `TargetAnchorable`:
- `Reference="LibraryId/ElementId"` — links to Object Repository entry
- `ContentHash="..."` — integrity check against Object Repository XML

`NApplicationCard.TargetApp` gets the same attributes linking to the screen-level reference.

### Object Repository (Post-Generation)

After generating all workflow XAML files, if `selectors.json` exists in the project directory, generate the Object Repository:

```bash
python3 scripts/generate_object_repository.py --from-selectors <project>/selectors.json --project-dir <project>
```

This creates the `.objects/` directory tree matching UiPath Studio's Object Repository format. **This step is mandatory for UI automation projects** — lint 94 catches missing Object Repositories.

### Wiring Object Repository References into JSON Specs (MANDATORY)

After generating the Object Repository (Phase 2c), the returned `refs.json` contains reference paths and content hashes for every element. You MUST inject these into every UI activity's JSON spec `args` (Rule G-9):

**For UI activities** (ntypeinto, nclick, ncheck, ncheckstate, nselectitem, ngettext, nhover, etc.):
```json
{"gen": "ntypeinto", "args": {
    "display_name": "Type Into 'Email'",
    "selector": "<webctrl id='email' tag='INPUT' />",
    "text_variable": "strEmail",
    "obj_repo": {
      "reference": "tDVvDluzTB-bqL3Nni6-OA/CY0fwCmbTAiwxY-rk6gyEQ",
      "content_hash": "j8tYRRS2SxtP12HUGLEwCw",
      "guid": "a9b0fa4c-20c2-4c3c-9b53-a77cb07b31bb"
    }
}}
```

Values come from `refs.json → elements → "AppName/ScreenName/ElementName"`.

**For NApplicationCard** (browser open or desktop open):
```json
{"gen": "napplicationcard_open", "args": {
    "display_name": "ACME",
    "url_variable": "in_strUrl",
    "out_ui_element": "out_uiACME",
    "target_app_selector": "<html app='msedge.exe' title='ACME' />",
    "obj_repo_app": {
      "reference": "tDVvDluzTB-bqL3Nni6-OA/XZmrq88iTjqxOKeVRByavw",
      "content_hash": "_qeOSAtNnm39HJig9mPTCg"
    }
}}
```

Values come from `refs.json → apps → "AppName"`.

**Skip obj_repo for:** NCheckState activities that verify non-tracked elements (e.g., waiting for a group box label to appear — if the element isn't in selectors.json, it has no OR entry).

⛔ **Without obj_repo bindings, selectors are hardcoded in every activity — the Object Repository exists but is unused. Refactoring a selector requires finding every inline copy across the project.**

## Workflow Generation CLI

**`scripts/generate_workflow.py` is the PRIMARY way to create .xaml workflow files.** The agent writes a JSON spec describing arguments, variables, and activities — the script calls all deterministic generators internally and outputs a complete, validated .xaml file.

⛔ **Rule G-1** — Never write .xaml by hand. See `rules.md` for rationale.

### Usage

```bash
python3 scripts/generate_workflow.py spec.json Workflows/ACME/ACME_Launch.xaml --project-dir <project>
```

The `--project-dir` flag enables **automatic Object Repository wiring**: the script loads `.objects/refs.json` and injects `Reference=` and `ContentHash=` attributes into every TargetAnchorable whose selector matches an Object Repository element. This replaces the need for manual `obj_repo` injection in JSON specs. **Always pass `--project-dir` after the Object Repository has been generated** (Phase 2c).

### JSON Spec Format

```json
{
  "class_name": "ACME_Launch",
  "arguments": [
    {"name": "in_strUrl", "direction": "In", "type": "String"},
    {"name": "out_uiACME", "direction": "Out", "type": "UiElement"}
  ],
  "variables": [
    {"name": "strUsername", "type": "String"},
    {"name": "secstrPassword", "type": "SecureString"}
  ],
  "activities": [
    {"gen": "log_message", "args": {"message_expr": "\"[START] ACME_Launch\""}},
    {
      "gen": "napplicationcard_open",
      "args": {"display_name": "ACME", "url_variable": "in_strUrl",
               "out_ui_element": "out_uiACME",
               "target_app_selector": "<html app='msedge.exe' title='ACME' />",
               "obj_repo_app": {"reference": "LIB_ID/APP_ID", "content_hash": "HASH"}},
      "children": [
        {"gen": "ntypeinto", "args": {"display_name": "Type Into 'Email'",
         "selector": "<webctrl id='email' tag='INPUT' />", "text_variable": "strUsername",
         "obj_repo": {"reference": "LIB_ID/ELEM_ID", "content_hash": "HASH", "guid": "GUID"}}},
        {"gen": "nclick", "args": {"display_name": "Click 'Login'",
         "selector": "<webctrl tag='BUTTON' aaname='Login' />",
         "obj_repo": {"reference": "LIB_ID/ELEM_ID", "content_hash": "HASH", "guid": "GUID"}}}
      ]
    },
    {"gen": "log_message", "args": {"message_expr": "\"[END] ACME_Launch\""}}
  ]
}
```

### Supported Generators (gen field) — 94 core + plugin extensions

UI: `ntypeinto`, `nclick`, `nhover`, `ndoubleclick`, `nrightclick`, `ngettext`, `ncheckstate`, `nselectitem`, `nkeyboardshortcuts`, `nmousescroll`, `ngotourl`, `ngeturl`, `nextractdata`, `pick_login_validation`, `napplicationcard_open`, `napplicationcard_attach`, `napplicationcard_close`, `napplicationcard_desktop_open`

Control flow: `if`, `if_else_if`, `switch`, `foreach`, `foreach_row`, `foreach_file`, `while`, `do_while`, `flowchart`, `state_machine`, `parallel`, `parallel_foreach`

Error/invoke: `try_catch`, `throw`, `rethrow`, `retryscope`, `invoke_workflow`, `invoke_code`, `invoke_method`

Data: `assign`, `multiple_assign`, `build_data_table`, `add_data_row`, `add_data_column`, `filter_data_table`, `sort_data_table`, `remove_duplicate_rows`, `output_data_table`, `join_data_tables`, `lookup_data_table`, `merge_data_table`, `generate_data_table`, `deserialize_json`

Orchestrator: `add_queue_item`, `get_queue_item`, `getrobotcredential`, `get_robot_asset`, `net_http_request`

File: `copy_file`, `move_file`, `delete_file`, `path_exists`, `create_directory`, `read_text_file`, `write_text_file`, `read_csv`, `write_csv`

Excel/PDF/Email: `read_range`, `write_range`, `write_cell`, `read_pdf_text`, `read_pdf_with_ocr`, `send_mail`, `get_imap_mail`, `save_mail_attachments`

Database: `database_connect`, `execute_query`, `execute_non_query`

Tasks: `create_form_task`, `wait_for_form_task`

SAP WinGUI: `sap_logon`, `sap_login`, `sap_call_transaction`, `sap_click_toolbar`, `sap_select_menu_item`, `sap_read_statusbar`, `sap_table_cell_scope`, `sap_status_bar_check`, `sap_type_into_cell`

Dialogs/misc: `input_dialog`, `message_box`, `log_message`, `comment`, `comment_out`, `delay`, `break`, `continue`, `kill_process`, `terminate_workflow`, `should_stop`, `add_log_fields`, `remove_log_fields`, `take_screenshot_and_save`

Containers (with `children`): `napplicationcard_open`, `napplicationcard_attach`, `napplicationcard_close`, `napplicationcard_desktop_open`, `retryscope`, `comment_out`, `while`, `do_while`, `foreach`, `foreach_row`, `foreach_file`, `parallel`, `parallel_foreach`

Containers (named children): `try_catch` (`try_children`, `finally_children`, `args.catches[].children`), `if` (`then_children`, `else_children`), `if_else_if` (`args.conditions[].children`, `else_children`), `switch` (`args.cases[].children`, `default_children`), `ncheckstate` (`if_exists_children`, `if_not_exists_children`)

### Type Shortcuts

| JSON type | XAML type |
|---|---|
| String | x:String |
| Int32 | x:Int32 |
| Boolean | x:Boolean |
| DataTable | sd:DataTable |
| SecureString | ss:SecureString |
| UiElement | ui:UiElement |
| Dictionary | scg:Dictionary(x:String, x:Object) |
| QueueItem | ui:QueueItem |

## Activity Generators (MANDATORY for UI activities)

**ALWAYS use `scripts/generate_activities` for UI automation activities.** These generators produce structurally correct XAML with hardcoded enums, versions, and child elements from golden Studio 24.10 exports. Hand-writing these activities leads to hallucinated enum values, missing child elements, and Studio crashes.

### Available Generators

| Generator | Activity | Key properties locked down |
|---|---|---|
| `gen_ntypeinto()` | NTypeInto | EmptyFieldMode (SingleLine/MultiLine/None), ClickBeforeMode enum, VerifyOptions block, Version=V5 |
| `gen_nclick()` | NClick | ClickType, MouseButton, KeyModifiers, Version=V5 |
| `gen_ngettext()` | NGetText | selector OR InUiElement (mutually exclusive), Version=V5 |
| `gen_ncheckstate()` | NCheckState | IfExists/IfNotExists Sequence blocks with ViewState, Version=V5 |
| `gen_ngotourl()` | NGoToUrl | Version=V3 with ViewState |
| `gen_napplicationcard_open()` | NApplicationCard | OpenMode=Always, CloseMode=Never, full OCR+TargetApp blocks |
| `gen_napplicationcard_attach()` | NApplicationCard | OpenMode=Never, CloseMode=Never, AttachMode=SingleWindow |
| `gen_napplicationcard_close()` | NApplicationCard | OpenMode=Never, CloseMode=Always |
| `gen_nselectitem()` | NSelectItem | Item= binding (dynamic or {x:Null}), Items list, Version=V1 |
| `gen_nextractdata()` | NExtractDataGeneric | ExtractedData (not Result!), Version=V5, backtick IdRef |
| `gen_add_queue_item()` | AddQueueItem | .ItemInformation (not .DictionaryCollection!), bare InArguments, QueueType (not QueueName!) |
| `gen_getrobotcredential()` | GetRobotCredential | CacheStrategy=None, TimeoutMS null |
| `gen_logmessage()` | LogMessage | Level validation (Info/Warn/Error/Trace) |
| `gen_throw()` | Throw | Exception expression |
| `gen_invoke_workflow()` | InvokeWorkflowFile | Arguments block with direction/type/key |
| `gen_retryscope()` | RetryScope | ActivityBody + Condition blocks |
| `gen_pick_login_validation()` | Pick (2-branch) | Complete login validation with NCheckState triggers |
| `gen_assign()` | Assign | To/Value with configurable TypeArguments |
| `gen_variables_block()` | Sequence.Variables / Flowchart.Variables | Auto-normalizes array types (x:String[] → s:String[]) |
| `gen_multiple_assign()` | MultipleAssign | scg:List > AssignOperation > To/Value element syntax, Capacity |
| `gen_foreach_row()` | ForEachRow | ActivityAction(sd:DataRow), DelegateInArgument, body Sequence |
| `gen_net_http_request()` | NetHttpRequest | uwah: namespace, all {x:Null} props, FormDataParts, built-in RetryCount/RetryPolicyType/RetryStatusCodes (NO RetryScope) |
| `gen_try_catch()` | TryCatch | ActivityAction per Catch, DelegateInArgument, specific→generic ordering |
| `gen_if()` | If | InArgument x:TypeArguments="x:Boolean" Condition element syntax |
| `gen_get_queue_item()` | GetQueueItem + RetryScope | QueueType (not QueueName!), .Reference/.TimeoutMS children, auto-wrapped |
| `gen_deserialize_json()` | DeserializeJson | ui: prefix, njl:JObject type, JsonString/JsonObject (not JsonInput/Output) |
| `gen_switch()` | Switch | x:TypeArguments, backtick IdRef, x:Key case labels, Switch.Default |
| `gen_foreach()` | ForEach | ui: prefix (not default ns!), ActivityAction, DelegateInArgument, CurrentIndex={x:Null} |
| `gen_foreach_file()` | ForEachFileX | Dual DelegateInArguments (FileInfo+Int32), si: namespace, no ContinueOnError |
| `gen_if_else_if()` | IfElseIfV2 | sc:BindingList, IfElseIfBlock (not IfElseIfV2Condition!), Else (not ElseBody!) |
| `gen_add_data_row()` | AddDataRow | ArrayRow attribute (not element), DataRow={x:Null} when using ArrayRow |
| `gen_add_data_column()` | AddDataColumn | TypeArguments for column type, all {x:Null} optional props |
| `gen_filter_data_table()` | FilterDataTable | `.Filters` (NOT FilterRowsCollection!), `Operator="EQ"` attr (NOT Operand!), `.Column`/`.Operand` child elements with InArgument (NOT ColumnName/Value attrs!). Operators: ALL CAPS — `EQ NE LT LE GT GE CONTAINS STARTS_WITH ENDS_WITH EMPTY NOT_EMPTY`. EMPTY/NOT_EMPTY use `Operand="{x:Null}"`. Supports typed operands (5-tuple with `x:Int32`). **NEVER hand-write** — structure is complex and 100% hallucinated every time |
| `gen_get_robot_asset()` | GetRobotAsset + RetryScope | .Value element syntax (not Result!), auto-wrapped |
| `gen_output_data_table()` | OutputDataTable | Text property (not Output!) |
| `gen_sort_data_table()` | SortDataTable | ColumnName (not OrderByColumnName!), SortOrder (not OrderByType!) |
| `gen_remove_duplicate_rows()` | RemoveDuplicateRows | In-place or new output variable |
| `gen_while()` | While | Condition with XML entity encoding |
| `gen_do_while()` | DoWhile | Executes body at least once |
| `gen_delay()` | Delay | TimeSpan.FromSeconds expression |
| `gen_rethrow()` | Rethrow | Preserves stack trace |
| `gen_copy_file()` | CopyFile | Overwrite flag, {x:Null} resource props |
| `gen_move_file()` | MoveFile | Same structure as CopyFile |
| `gen_delete_file()` | DeleteFileX | NO ContinueOnError (X-suffix activity!) |
| `gen_path_exists()` | PathExists | PathType="File" or "Folder" |
| `gen_create_directory()` | CreateDirectory | Safe on existing dirs |
| `gen_input_dialog()` | InputDialog | Result element syntax, Options={x:Null} (use OptionsString!) |
| `gen_message_box()` | MessageBox | Caption/ChosenButton {x:Null} defaults |
| `gen_comment()` | Comment | Simple text annotation |
| `gen_comment_out()` | CommentOut | Wraps activities in disabled scope |
| `gen_invoke_code()` | InvokeCode | XML-encoded code string, In/Out/InOut arguments, Language="VBNet"/"CSharp" |
| `gen_invoke_method()` | InvokeMethod | Instance (TargetObject) vs static (TargetType), positional params |
| `gen_join_data_tables()` | JoinDataTables | JoinOperationArgument with Column1/Column2 (not Column!) |
| `gen_lookup_data_table()` | LookupDataTable | VLOOKUP-style: LookupColumnName + TargetColumnName |
| `gen_merge_data_table()` | MergeDataTable | MissingSchemaAction enum |
| `gen_generate_data_table()` | GenerateDataTable | ColumnSeparators as VB char array |
| `gen_ngeturl()` | NGetUrl | Version="V4", inside NApplicationCard scope |
| `gen_read_range()` | ReadRange (Excel) | Workbook classic, no Excel app needed |
| `gen_write_range()` | WriteRange (Excel) | Creates file if not exists |
| `gen_write_cell()` | WriteCell (Excel) | Dynamic cell address via VB expression |
| `gen_database_connect()` | DatabaseConnect | ConnectionSecureString (not ConnectionString!) |
| `gen_execute_query()` | ExecuteQuery | Parameterized @params, scg:Dictionary for params |
| `gen_execute_non_query()` | ExecuteNonQuery | Parameterized INSERT/UPDATE/DELETE |
| `gen_take_screenshot_and_save()` | TakeScreenshot+SaveImage | Paired pattern, ui:Image variable type, Target element |
| `gen_flowchart()` | Flowchart | av: namespace, __ReferenceID naming, StartNode, FlowDecision VisualBasicValue, x:Reference list |
| `gen_read_pdf_text()` | ReadPDFText | FileName (not FilePath), Text (not Result), PreserveFormatting={x:Null} |
| `gen_read_pdf_with_ocr()` | ReadPDFWithOCR | ActivityFunc delegate with sd:Image/sd1:Rectangle types, ui:GoogleOCR engine, Image=[Image] binding |
| `gen_send_mail()` | SendMail | Integration Service connection, AttachmentsBackup/ConnectionDetailsBackupSlot boilerplate, ~15 {x:Null} props |
| `gen_build_data_table()` | BuildDataTable | XSD schema in TableInfo attribute (NOT child elements!), self-closing tag. Prevents lint 48 hallucinations |
| `gen_create_form_task()` | CreateFormTask | Tasks form with {} JSON escape, FormData direction-typed bindings, TaskOutput (NOT TaskObject!), ~15 {x:Null} props |
| `gen_wait_for_form_task()` | WaitForFormTaskAndResume | Persistence point — MUST be in Main.xaml. TaskInput (NOT TaskObject!), paired with CreateFormTask |
| `gen_get_imap_mail()` | GetIMAPMailMessages | Integration Service email, ConnectionDetailsBackupSlot boilerplate, ~12 {x:Null} props |
| `gen_save_mail_attachments()` | SaveMailAttachments | Correct IEnumerable(x:String) output type (NOT List(String)!), filter wildcard |
| `gen_napplicationcard_desktop_open()` | NApplicationCard (desktop) | TargetApp.FilePath (NOT Url!), no IsIncognito/BrowserType, Simulate or HardwareEvents (NOT DebuggerApi!) |
| `gen_nhover()` | NHover | HoverTime (seconds), CursorMotionType (Instant/Smooth), Version=V5 |
| `gen_ndoubleclick()` | NClick (ClickType=Double) | Same as gen_nclick with ClickType="Double" |
| `gen_nrightclick()` | NClick (MouseButton=Right) | Same as gen_nclick with MouseButton="Right" |
| `gen_nkeyboardshortcuts()` | NKeyboardShortcuts | Shortcuts string (hotkey notation), optional selector target, InteractionMode=HardwareEvents |
| `gen_nmousescroll()` | NMouseScroll | Direction (Down/Up/Left/Right), MovementUnits, InteractionMode |
| `gen_parallel()` | Parallel | Multiple branches executing concurrently, CompletionCondition |
| `gen_parallel_foreach()` | ParallelForEach | Concurrent iteration, DelegateInArgument, ActivityAction |
| `gen_state_machine()` | StateMachine | States with Transitions, InitialState x:Reference, FinalState support |
| `gen_break()` | Break | Exit innermost ForEach/While/DoWhile loop |
| `gen_continue()` | Continue | Skip to next iteration of loop |
| `gen_kill_process()` | KillProcess | ProcessName string — use in KillAllProcesses only |
| `gen_terminate_workflow()` | TerminateWorkflow | Exception expression, Reason string |
| `gen_add_log_fields()` | AddLogFields | Dict of field name → expression, custom structured logging |
| `gen_remove_log_fields()` | RemoveLogFields | List of field names to remove from log context |
| `gen_should_stop()` | ShouldStop | Result bool variable, checks Orchestrator stop signal |
| `gen_read_csv()` | ReadCsvFile | FilePath or PathResource, Delimitator enum, HasHeaders, Encoding |
| `gen_write_csv()` | AppendWriteCsvFile | CsvAction (Write/Append), Delimitator, ShouldQuote, AddHeaders |
| `gen_read_text_file()` | ReadTextFile | File or FileName (path variable), Content output, Encoding |
| `gen_write_text_file()` | WriteTextFile | File or FileName (path variable), Text input, Encoding |

### Usage Pattern

```python
from scripts.generate_activities import *

scope_guid = "..."  # from NApplicationCard ScopeGuid
# Each call returns complete XAML string — just concatenate
body = gen_ntypeinto("Type Into 'Email'", "<webctrl tag='INPUT' id='email' />",
                     "strEmail", "NTypeInto_1", scope_guid)
body += "\n" + gen_nclick("Click 'Submit'", "<webctrl tag='BUTTON' />",
                          "NClick_1", scope_guid)
```

### What the model still provides
- `display_name`: Human-readable name
- `selector`: From Playwright MCP inspection
- `variable names`: Following UiPath naming conventions
- `id_ref`: Unique IdRef per file (NTypeInto_1, NClick_1, etc.)
- `scope_id`: UUID matching parent NApplicationCard's ScopeGuid
- Composition: wrapping in RetryScope, ordering activities, building workflow structure

### What the generators lock down (model CANNOT override)
- Enum values (EmptyFieldMode, ClickBeforeMode, OpenMode, CloseMode, etc.)
- Version numbers (V5 for activities, V6 for TargetAnchorable, V2 for NApplicationCard)
- Child element structures (VerifyOptions, OCREngine, TargetApp, IfExists/IfNotExists)
- HintSize attributes (from golden samples)
- Property names (EmptyFieldMode not EmptyField, ClickBeforeMode not ClickBeforeTyping)
