# Golden Templates — Real Studio-Exported XAML

All templates are **real UiPath Studio exports** (Windows target, VB.NET). One clean REFramework template serves as the base for both Dispatcher and Performer variants — the `scaffold_project.py` script applies variant-specific transformations at scaffolding time.

## Contents
- Template Inventory (Simple Sequence, Sequence Template, REFramework, Sample Workflows, Selection Decision Tree)
- Key Differences: Dispatcher vs Performer (Transaction Item Types)
- Activities Not in Templates
- Modification Rules

## Template Inventory

### Simple Sequence (`assets/simple-sequence/`)

Non-REFramework starter project. Use as **golden reference samples** — these contain real Studio-exported XAML with correct namespaces, ViewState, and activity patterns. Do NOT scaffold from this folder directly; use `assets/simple-sequence-template/` for scaffolding.

### Simple Sequence Template (`assets/simple-sequence-template/`)

Clean scaffolding template for non-REFramework projects. Contains minimal Main.xaml with placeholder activities and project.json with only `UiPath.System.Activities`. Used by `scaffold_project.py --variant sequence`.

| File | Lines | Purpose | Best Template For |
|---|---|---|---|
| `Main.xaml` | — | Sequence with DataTable ops, Assign, Flowchart, Switch | **Non-REFramework projects**, activity pattern reference |
| `FormFilling_Main.xaml` | — | NApplicationCard (IfNotOpen, Maximize), ReadRange, ForEachRow, NTypeInto, NSelectItem, NClick, NCheckState (IfExists/IfNotExists), NGetText, MultipleAssign, WriteCell, Assign | **Web form filling** from Excel data, browser automation with conditional branching |
| `PDFExtraction_Main.xaml` | — | ForEachFileX, ReadPDFText, ReadPDFWithOCR (GoogleOCR/Tesseract), If (native vs scanned fallback), Regex extraction, BuildDataTable, MultipleAssign, AddDataRow (ArrayRow with variables), WriteRange, LogMessage | **PDF data extraction** with OCR fallback, bulk file processing to Excel |
| `WebScraping_Sequence1.xaml` | — | NApplicationCard (ByInstance, OCREngine delegate), NExtractDataGeneric (ExtractDataSettings, ExtractMetadata, NextLink pagination), TargetAnchorable (ImageBase64, BrowserURL) | **Web scraping** structured table data with pagination |

> **⚠️ NExtractDataGeneric note:** The golden sample was exported without `ExtractedData=` (no variable assignment). When generating XAML, you MUST add `ExtractedData="[dt_variable]"` to capture output. Do NOT use `DataTable=` or `Result=` — neither exists as a property. `DataTable` in `x:TypeArguments="sd2:DataTable"` is the generic type parameter, not a property name.

> **⚠️ Use stripped excerpts for reading.** The full Studio files contain verbose visual metadata (TargetAnchorable images, ViewState layout). Read from `assets/stripped/` instead:
> - `stripped/FormFilling_Main.xaml` (299 lines, 26KB) — vs original 94KB
> - `stripped/REFramework_Main.xaml` (595 lines, 47KB) — vs original 92KB
> - `stripped/SetTransactionStatus.xaml` (500 lines, 38KB) — vs original 66KB
>
> Full originals in `assets/simple-sequence/` and `assets/reframework/` are needed only for Studio validation (`--golden`).

These templates contain real examples of: `BuildDataTable` (with XSD schema), `AddDataRow`, `FilterDataTable`, `Assign`, `Flowchart` with `FlowDecision`, `Switch` with cases + default, `InvokeWorkflowFile` (modular decomposition), `NSelectItem` with Items list, `NCheckState` with IfExists/IfNotExists, `MultipleAssign` with AssignOperations, `WriteCell` (per-cell Excel write), `ForEachRow` inside `NApplicationCard`, loop-scoped variables.

### REFramework (`assets/reframework/`)

Single clean template for both Dispatcher and Performer. The `scaffold_project.py` script applies dispatcher-specific transformations (TransactionItem type swap to `sd:DataRow`, Process.xaml dispatcher comments) when `--variant dispatcher` is used.

**Performer (default):** Transaction type `ui:QueueItem` — processes Orchestrator queue items.
**Dispatcher:** Transaction type swapped to `sd:DataRow` (or other type depending on data source) — reads data and creates queue items.

| File | Lines | Purpose | Best Template For |
|---|---|---|---|
| `Main.xaml` | — | StateMachine (4 states: Init, GetTransaction, Process, EndProcess) | REFramework StateMachine |
| `Framework/Process.xaml` | — | **Clean placeholder** — LogMessage + Comment | **Starting point for business logic** |
| `Framework/SetTransactionStatus.xaml` | — | 3-branch Flowchart status handling | Multi-branch Flowchart |
| `Framework/InitAllSettings.xaml` | — | Config reader with ForEach + TryCatch | ForEachRow, TryCatch, config patterns |
| `Framework/RetryCurrentTransaction.xaml` | — | Retry counter logic | Counter manipulation, conditionals |
| `Framework/GetTransactionData.xaml` | — | Gets next transaction item | If/Else branching, counter logic |
| `Framework/TakeScreenshot.xaml` | — | Screenshot utility | File/directory operations |
| `Framework/InitAllApplications.xaml` | — | Sequence with In argument | Placeholder with arguments |
| `Framework/CloseAllApplications.xaml` | — | Simple sequence + annotation | **Simplest sequence** |
| `Framework/KillAllProcesses.xaml` | — | ForEach + KillProcess with TryCatch per process, arg: `in_arrProcessesToKill` | **Process cleanup template** |
| `Tests/*.xaml` | 6 files | Unit test cases for each framework file | **Test workflow patterns** |
| `project.json` | — | Core deps: System, UIAutomation, Excel, Testing | REFramework project configuration |

### Sample Workflows (`assets/samples/common-workflows/`)

Clean, generic workflow patterns extracted from real projects. NOT scaffolded — use `grep` to extract specific activity patterns.

**⚠️ This sample project models the mandatory folder structure.** Main stays at project root, all sub-workflows are organized inside `Workflows/` by application or utility. Replicate this structure in every generated project:
```
common-workflows/
├── HttpApiDispatcher_Main.xaml          # Main — orchestration only
└── Workflows/
    ├── Api/
    │   └── Api_FetchInvoices.xaml       # Credential + OAuth + HTTP fetch
    ├── Dispatcher/
    │   └── ExcelDispatcher_Process.xaml # Excel row → AddQueueItem dispatch
    ├── Performer/
    │   └── Performer_Process.xaml       # QueueItem extraction + invoke sub-workflows
    ├── WebAppName/
    │   └── WebAppName_Launch.xaml       # App launch + login
    └── Utils/
        ├── App_Close.xaml             # Generic app/browser close
        └── Browser_NavigateToUrl.xaml      # Generic browser navigation
```

| File | Lines | Purpose | Best Template For |
|---|---|---|---|
| `HttpApiDispatcher_Main.xaml` | — | Orchestration-only Main: InvokeWorkflowFile to Api_FetchInvoices, ForEach JToken, AddQueueItem with ItemInformation | **Dispatcher orchestration**, InvokeWorkflowFile, queue dispatch, modular decomposition |
| `Workflows/Api/Api_FetchInvoices.xaml` | — | Dedicated API workflow: GetRobotCredential, NetHttpRequest (OAuth POST + GET), DeserializeJson, RetryScope with HTTP status check | **HTTP/REST API calls**, OAuth2 client_credentials, GetRobotCredential, RetryScope, JSON parsing |
| `Workflows/WebAppName/WebAppName_Launch.xaml` | — | App launch + login: NApplicationCard, GetRobotCredential (RetryScope), NTypeInto (username + SecureText password), NClick login, Pick with dual PickBranch for success/failure validation, NGetText + Throw on error | **App login (web or desktop)**, GetRobotCredential, Pick/PickBranch, SecureString password, login validation |
| `Workflows/Utils/App_Close.xaml` | — | NApplicationCard with CloseMode=Always, arg: in_uiApp (UiElement). Works for both web and desktop apps. No logout needed (incognito kills browser session) | **App/browser close** |
| `Workflows/Utils/Browser_NavigateToUrl.xaml` | — | NApplicationCard + GoToUrl | **Browser navigation** |
| `Workflows/Performer/Performer_Process.xaml` | — | QueueItem SpecificContent extraction, MultipleAssign, If + Throw BRE validation, InvokeWorkflowFile with Config args | **Performer Process.xaml body**, QueueItem field extraction, input validation, sub-workflow invocation |
| `Workflows/Dispatcher/ExcelDispatcher_Process.xaml` | — | DataRow column extraction, MultipleAssign, If + Throw BRE validation, AddQueueItem with ItemInformation fields | **Excel Dispatcher Process.xaml body**, DataRow to QueueItem dispatch, field mapping |

> **Incognito mode:** `WebAppName_Launch.xaml` uses `IsIncognito="True"`. No explicit logout needed — closing the browser destroys the session. See `skill-guide.md` Rule 10.

### Template Selection Decision Tree

```
What type of project?
├─ Simple automation (no queues/retries) → simple-sequence/
├─ Dispatcher (reads data, creates queue items) → reframework/ (--variant dispatcher)
└─ Performer (processes queue items) → reframework/ (--variant performer)

What type of workflow?
├─ Process cleanup (ForEach + TryCatch) → KillAllProcesses.xaml
├─ Simple sequence + annotation → CloseAllApplications.xaml
├─ Clean process placeholder → reframework/Framework/Process.xaml
├─ Sequence with In arguments → InitAllApplications.xaml
├─ App login (credentials + validation) → samples/common-workflows/Workflows/WebAppName/WebAppName_Launch.xaml
├─ Dispatcher orchestration → samples/common-workflows/HttpApiDispatcher_Main.xaml
├─ API credential + OAuth + fetch → samples/common-workflows/Workflows/Api/Api_FetchInvoices.xaml
├─ App/browser close (CloseMode=Always) → samples/common-workflows/Workflows/Utils/App_Close.xaml
├─ Browser navigate to URL → samples/common-workflows/Workflows/Utils/Browser_NavigateToUrl.xaml
├─ Performer Process.xaml (QueueItem → invoke sub-workflows) → samples/common-workflows/Workflows/Performer/Performer_Process.xaml
├─ Excel Dispatcher Process.xaml (DataRow → AddQueueItem) → samples/common-workflows/Workflows/Dispatcher/ExcelDispatcher_Process.xaml
├─ If/Else branching → GetTransactionData.xaml
├─ ForEachRow + TryCatch → InitAllSettings.xaml
├─ Retry/counter logic → RetryCurrentTransaction.xaml
├─ Multi-branch Flowchart → stripped/SetTransactionStatus.xaml
├─ UI automation (click, type, form fill) → stripped/FormFilling_Main.xaml + samples/common-workflows/Workflows/WebAppName/WebAppName_Launch.xaml
└─ StateMachine (REFramework) → stripped/REFramework_Main.xaml
```

## Key Differences: Dispatcher vs Performer

Both use the same `assets/reframework/` base template. `scaffold_project.py --variant dispatcher` applies type transformations automatically.

| Aspect | Dispatcher | Performer |
|---|---|---|
| scaffold variant | `--variant dispatcher` | `--variant performer` |
| TransactionItem type | `sd:DataRow` (default, configurable) | `ui:QueueItem` (standard) |
| Typical data source | DataTable (Excel, DB, API), email inbox, file list | Orchestrator Queue |
| Process.xaml purpose | Extract data → AddQueueItem | Process queue item → business logic |
| GetTransactionData.xaml | Returns next row/item from local data source | Returns next QueueItem from Orchestrator |

### Transaction Item Types

The `TransactionItem` variable type is **configurable for dispatchers** — it depends on the data source. For **performers**, the standard type is `ui:QueueItem`:

| Type | XAML TypeArguments | xmlns required | When to use |
|---|---|---|---|
| `sd:DataRow` | `x:TypeArguments="sd:DataRow"` | `xmlns:sd="clr-namespace:System.Data;assembly=System.Data.Common"` | Processing rows from DataTable (Excel, DB, CSV) |
| `ui:QueueItem` | `x:TypeArguments="ui:QueueItem"` | `xmlns:ui="http://schemas.uipath.com/workflow/activities"` (already included) | Processing Orchestrator queue items |
| `x:String` | `x:TypeArguments="x:String"` | (built-in, no extra xmlns) | Simple string values (file paths, URLs, IDs) |
| `scg3:MailMessage` | `x:TypeArguments="scg3:MailMessage"` | `xmlns:scg3="clr-namespace:System.Net.Mail;assembly=System.Net.Mail"` | Processing email messages |

When changing the type, update ALL occurrences: `TransactionItem` variable in Main.xaml, all `OutArgument`/`InArgument` referencing it, and the corresponding arguments in GetTransactionData.xaml, Process.xaml, and SetTransactionStatus.xaml.

## Activities Not in Templates

The templates above cover structural patterns (sequences, branching, loops, TryCatch, StateMachine, UI automation). For activities that don't appear in any template, get the XAML from the relevant reference file:

| Activity | Reference file |
|---|---|
| InputDialog (text input + dropdown) | `xaml-foundations.md` |
| If, ForEach, Flowchart, State Machine | `xaml-control-flow.md` |
| BuildDataTable, FilterDataTable, DeserializeJSON | `xaml-data.md` |
| CopyFile, MoveFile, CreateDirectory, DeleteFile, PathExists | `xaml-data.md` |
| TryCatch, RetryScope, Throw/Rethrow | `xaml-error-handling.md` |
| Invoke Code (inline C#/VB.NET), Invoke Method | `xaml-invoke.md` |
| HTTP Request (OAuth, retry, query params) | `xaml-orchestrator.md` |
| GetRobotAsset, GetRobotCredential, AddQueueItem | `xaml-orchestrator.md` |
| CreateFormTask, WaitForFormTaskAndResume | **uipath-tasks** skill → `references/tasks.md` |
| Data Service (Entity, Query, Create, Update) | `xaml-orchestrator.md` |
| Excel ReadRange, WriteRange, WriteCell | `xaml-integrations.md` |
| Email (Integration Service), PDF ReadPDFText/ReadPDFWithOCR | `xaml-integrations.md` |
| NApplicationCard, NClick, NTypeInto, selectors | `xaml-ui-automation.md` |

**Pattern:** Use the closest template for the overall file structure (namespaces, ViewState, root element), then insert activity-specific XAML from the relevant reference file.

## Modification Rules

1. Change `x:Class` and root `DisplayName`
2. Update `sap2010:WorkflowViewState.IdRef` on root element
3. Modify `x:Members` for arguments
4. Modify `Sequence.Variables` for variables
5. Replace business logic activities
6. Every new activity gets `sap:VirtualizedContainerService.HintSize` + unique `IdRef`
7. **Keep namespace/assembly sections from template UNCHANGED** — especially `UiPath.UIAutomationNext.Enums` (correct CLR namespace despite package rename). See `cheat-sheet.md` → Quick Rules.
8. Add xmlns declarations only if using activities from new packages
9. Validate well-formed XML

## Config.xlsx Structure

See `config-sample.md` for the full Config.xlsx reference (Settings/Constants/Assets sheets, key naming conventions, output format).

Config.xlsx has 3 sheets (Settings, Constants, Assets), all with **Name | Value | Description** columns. The scaffold script creates framework defaults. After generating workflows, always output required Config.xlsx keys — lint 39 extracts them automatically via `validate_xaml --lint`.
