# Workflow Decomposition Patterns

Naming conventions, decomposition rules, common process patterns, argument design, Login/Launch pattern, and REFramework Init/Close. For scaffolding see `scaffolding.md`. For XAML generation see `generation.md`.

**Every process must be decomposed into focused sub-workflows.** Main.xaml orchestrates via `InvokeWorkflowFile` — it should never contain business logic, UI interactions, or data processing directly.

### Naming Convention
Files follow `AppName_Action.xaml` pattern. All generated workflows go inside a `Workflows/` folder. **Subfolder name = the AppName prefix** from the file names (the actual application name, never generic categories like "App1" or "GenericApp"):
```
ProjectRoot/
├── Main.xaml                              # Orchestrator only — InvokeWorkflow calls
├── Workflows/
│   ├── WebApp/                              # Folder = app name "WebApp"
│   │   ├── WebApp_Launch.xaml               # Open browser + login + wait for home page
│   │   └── WebApp_DownloadReport.xaml       # Click download, wait, save file
│   ├── InventoryManager/                  # Folder = app name "InventoryManager"
│   │   ├── InventoryManager_Launch.xaml
│   │   ├── InventoryManager_EnterRecord.xaml
│   │   └── InventoryManager_Close.xaml
│   ├── Email/                             # Folder = "Email" (service, not an app)
│   │   ├── Email_GetMessages.xaml
│   │   └── Email_SaveAttachments.xaml
│   └── Utils/                             # Shared utilities (no UI, cross-app)
│       ├── Browser_NavigateToUrl.xaml         # Generic URL navigation (reusable across all browser apps)
│       ├── App_Close.xaml
│       ├── Process_TransformData.xaml
│       └── Process_ValidateReport.xaml
└── Framework/                             # REFramework or shared framework files
```

**Rules:** Main.xaml stays at project root. Every other workflow goes in `Workflows/<AppName>/` where `<AppName>` matches the file prefix. `Utils/` is for cross-app utilities. InvokeWorkflowFile paths: `"Workflows\\WebApp\\WebApp_Launch.xaml"`.

### Decomposition Rules

**Universal rules (all projects):**
1. **One UI scope per workflow** — each file works inside ONE `NApplicationCard` or one app window. If you need to switch apps, that's a new workflow.
2. **≤150 lines per file** — if a workflow exceeds this, split it. Long workflows are unreadable and untestable.
3. **Reusable navigation** — `Workflows/Utils/Browser_NavigateToUrl.xaml` takes `in_strUrl` and `io_uiBrowser` as arguments — always a FULL URL, never concatenated inside the workflow. URL-first: always navigate by URL (`NGoToUrl`) when possible, UI clicks as last resort. This is a shared utility used by all browser apps in the project — never create app-specific NavigateTo workflows.
   - **Config pattern:** Store base URL + path segments in Config.xlsx **Assets sheet** (environment-specific, fetched from Orchestrator):
     - `WebApp_BaseURL` = `https://webapp-example.com`
     - `WebApp_LoginPath` = `login`
     - `WebApp_WorkItemsPath` = `work-items`
   - **Caller assembles full URL** via `String.Format("{0}/{1}", in_Config("WebApp_BaseURL").ToString, in_Config("WebApp_LoginPath").ToString)` in InvokeWorkflowFile arguments (use `Config(` only in Main.xaml; everywhere else it's `in_Config(`)
   - **Workflow receives complete URL** in `in_strUrl` — ⛔ NEVER concatenate inside `Url=` attributes on NGoToUrl/TargetApp
4. **ALL apps open and ready in InitAllApplications** — every application the process interacts with (whether it requires login or just opening a URL) MUST be launched, logged in if needed, and in a ready-to-use state by the time InitAllApplications completes. Process.xaml and action workflows ONLY **attach** to already-open apps (`OpenMode="Never"`, `AttachMode="SingleWindow"`, `InUiElement="[io_uiAppName]"`). They NEVER open, launch, or log into anything. Lint 47 catches `OpenMode != "Never"` outside Launch workflows.
   - InitAllApplications delegates to `AppName_Launch.xaml` sub-workflows (one per app)
   - Each Launch workflow: opens the app (`OpenMode="Always"`), logs in if needed, validates login, outputs `out_uiAppName`
   - Simple apps (no login): Launch still opens the browser at the target URL — the UiElement must still flow through the chain
   - Desktop apps: Launch opens the application, waits for ready state (Check App State), outputs UiElement
   - Never inline app open/close inside business logic workflows — Launch/Close are shared across all processes using that app. **In REFramework: every app with UI interaction MUST be opened in `InitAllApplications.xaml` via a dedicated `AppName_Launch.xaml` workflow** (InvokeWorkflowFile). **Login stays inside Launch** — never create a separate `AppName_Login.xaml`. Launch handles: open app → login (if needed) → verify ready state. Process.xaml and action workflows use `OpenMode="Never"` + `AttachMode="SingleWindow"` to attach to the already-open app. Similarly, `CloseAllApplications.xaml` invokes `App_Close.xaml` or `AppName_Close.xaml` for each app.
5. **No UI in data workflows** — `Process_TransformData.xaml` does DataTable operations, regex, calculations. Zero UI activities.
6. **Persistence activities stay in Main.xaml** — `WaitForFormTaskAndResume`, `CreateFormTask`+wait pairs are persistence points. They ONLY work in the entry-point file.
7. **Log bookends on every workflow** — first and last activity: `LogMessage "[START/END] AppName_Action"`. Applies to Main.xaml AND all sub-workflows.
8. **Credentials retrieved where used, NEVER passed as arguments** — `GetRobotCredential` inside the workflow that uses them. Pass `in_strCredentialAssetName` (the asset name string) — NEVER pass `in_strUsername`/`in_strPassword`/`in_secPassword`.

**Browser-specific rules (web app automation):**
9. **Navigation is a separate workflow from page action** — first invoke `Browser_NavigateToUrl.xaml` (from Utils/), then invoke `AppName_DoAction.xaml`. Never combine "get there" and "do stuff" in one file. **Never create app-specific NavigateTo workflows** (`WebApp_NavigateTo.xaml` etc.) — the generic `Browser_NavigateToUrl.xaml` handles all URL navigation; the caller passes the full URL from Config. **Wrap navigation invocations in RetryScope with NCheckState condition** targeting the first element the next workflow will interact with (not a generic header) → see `xaml-error-handling.md` → NCheckState condition pattern.
10. **No logout workflow** — `IsIncognito="True"` is default, so closing the browser kills the session. Use generic `App_Close.xaml` (arg: `in_uiApp` InArgument(UiElement), `CloseMode="Always"`) for BOTH web and desktop apps. Do NOT generate `AppName_Logout.xaml` workflows. **App_Close.xaml is EXCLUSIVELY invoked from CloseAllApplications.xaml** — NEVER from Process.xaml or action workflows. Apps stay open across transactions; the End Process state handles closing. CloseAllApplications invokes App_Close once per app — it must NOT contain KillProcess activities (that's KillAllProcesses' job).
11. **One browser instance per web app** — each web app gets its own incognito browser with a distinct UiElement variable in Main (e.g., `uiWebApp`, `uiSHA1Online`). Never share tabs across apps. Close each separately via `App_Close.xaml` (pass `in_uiApp ← uiAppName`). Action workflows and Process.xaml use IN/OUT args (`io_uiWebApp`) to preserve updated references.
12. **Extraction workflows return ALL data — filtering is a separate step** — `AppName_ExtractData.xaml` scrapes/reads the full dataset and outputs the raw DataTable. Filtering (e.g., `Select("[Type] = 'WI5'")`, status checks, date ranges) belongs in the calling workflow or a dedicated `Process_FilterData.xaml`. This keeps extraction reusable across projects that need different filter criteria. Never embed business-specific filters inside a generic extraction workflow.
13. **Wrap API/network activities in RetryScope** — any activity that calls a web service can fail transiently. Wrap in `RetryScope` (3 retries, 5s interval). Activities: `AddQueueItem`, `BulkAddQueueItems`, `GetQueueItem`, `GetRobotAsset`, `GetRobotCredential`, `SetTransactionStatus`, `SetTransactionProgress`, `QueryEntityRecords`. **Exception: `NetHttpRequest` has built-in retry** (RetryCount, RetryPolicyType, RetryStatusCodes properties) — do NOT wrap in RetryScope (redundant double-retry). Exception: REFramework Framework/ files use transaction-level retry. See `cheat-sheet.md` → RetryScope for complete XAML sample.

**Desktop-specific rules (desktop app automation):**
14. **Desktop navigation is a separate workflow from screen action** — for desktop apps with tabs, menus, tree views, or multi-screen flows, navigate to the target screen in a dedicated `AppName_NavigateToScreen.xaml` workflow, then invoke the action workflow `AppName_FillScreen.xaml`. Never mix "get to the screen" with "fill the form" in one file. Unlike browser apps (which use a single generic `Browser_NavigateToUrl.xaml` for all URL navigation), desktop navigation is app-specific — each navigation step gets its own workflow named `AppName_NavigateTo<ScreenName>.xaml`. The navigation workflow clicks the tab/menu/tree node and waits for the target screen to load (use `NCheckState` to verify a field on the target screen is visible). The action workflow assumes the screen is already active and only fills/reads fields.
```
WRONG — tab navigation mixed with form filling:
  DesktopApp_FillPeopleTab.xaml
    ├── NClick 'People' Tab          ← navigation
    ├── Delay 500ms                  ← fragile wait
    ├── NTypeInto 'FirstName'        ← form action
    └── NTypeInto 'LastName'         ← form action

CORRECT — navigation and action are separate workflows:
Main.xaml (or Process.xaml)
  ├── InvokeWorkflow: DesktopApp_NavigateToPeopleTab.xaml  (io_uiDesktopApp)
  ├── InvokeWorkflow: DesktopApp_FillPeopleTab.xaml        (io_uiDesktopApp, in_strFirstName, in_strLastName)
```
Navigation is reusable (other workflows may also need to reach the People tab). Failures are pinpointed (tab click timeout vs field not found). Delays are replaced with `NCheckState` waits (reliable, not time-based).

#### WinForms Tab Detection Pitfall (Rule 14 supplement)

When inspecting a WinForms app with tabs via `inspect-ui-tree.ps1`, the tree shows ALL elements in the active tab's hierarchy. **Do not confuse GroupBox names inside tabs with tab names.**

The inspection tree shows:
```
[1] TabControl -> Click tab item
  [2] === People ===              <- TabItem (depth 2 = child of TabControl)
    [3] === Name: ===             <- GroupBox (depth 3 = INSIDE People tab)
    [3] === Phone ===             <- GroupBox (depth 3 = INSIDE People tab, NOT a tab)
    [3] === Address ===           <- GroupBox (depth 3 = INSIDE People tab, NOT a tab)
```

**Reading the hierarchy:**
- **Depth 2** under TabControl = **TabItems** (navigation targets). These are the actual tab names you click.
- **Depth 3** under a TabItem = **GroupBoxes/containers** (visual grouping inside that tab). Do NOT use these as tab names.

**Critical:** The PowerShell tree only expands the **active tab**. Other tabs appear as unexpanded TabItems at depth 2. If you only see one TabItem expanded with GroupBoxes inside, those GroupBoxes are containers inside that tab — not separate tabs.

**To get all tab names:** Look for ALL children of TabControl at depth 2, or ask the user to confirm the tab names listed in the application.

**Wrong decomposition** (used GroupBox names as tab names):
```
DesktopApp_NavigateToPhoneTab.xaml     <- "Phone" is a GroupBox inside Company tab
DesktopApp_NavigateToAddressTab.xaml   <- "Address" is a GroupBox inside Other tab
```

**Correct decomposition** (used actual TabItem names):
```
DesktopApp_NavigateToCompanyTab.xaml   <- "Company" is the actual tab name
DesktopApp_NavigateToOtherTab.xaml     <- "Other" is the actual tab name
```

The fill workflows can use descriptive names based on content: `DesktopApp_FillCompanyTab.xaml` fills phone fields that happen to be on the Company tab.

### Common Process Patterns

**Pattern: Web Report Download (simple sequence — NOT REFramework)**
```
Main.xaml  — variable: uiWebApp (type: UiElement)
  ├── InvokeWorkflow: Workflows\WebApp\WebApp_Launch.xaml              (in_strUrl, in_strCredentialAssetName, out_uiWebApp → uiWebApp)
  │     └── in_strUrl = Config("WebApp_Url").ToString — NEVER hardcode URLs
  ├── InvokeWorkflow: Workflows\Utils\Browser_NavigateToUrl.xaml      (in_strUrl, io_uiBrowser ← uiWebApp)
  │     └── in_strUrl = Config("WebApp_ReportsUrl").ToString
  ├── InvokeWorkflow: Workflows\WebApp\WebApp_DownloadReport.xaml      (in_strReportName, out_strFilePath, io_uiWebApp ← uiWebApp)
  ├── InvokeWorkflow: Workflows\Utils\Process_ValidateReport.xaml  (in_strFilePath, out_boolValid)
  └── InvokeWorkflow: Workflows\Utils\App_Close.xaml           (in_uiApp ← uiWebApp)
```
⚠️ App_Close in Main.xaml is ONLY valid for simple sequences. In REFramework, CloseAllApplications handles all app closing — NEVER invoke App_Close from Process.xaml or action workflows.

**Pattern: Multiple Web Apps (Rule 11 — simple sequence or REFramework Main-level view)**
```
Main.xaml  — variables: uiWebApp, uiSHA1Online (both type: UiElement)
  ├── InvokeWorkflow: WebApp_Launch.xaml         (in_strUrl, in_strCredentialAssetName, out_uiWebApp → uiWebApp)
  ├── InvokeWorkflow: Browser_NavigateToUrl.xaml  (in_strUrl, io_uiBrowser ← uiWebApp)     ← shared util
  ├── InvokeWorkflow: WebApp_GetWorkItems.xaml   (out_dt_WorkItems, io_uiWebApp ← uiWebApp)
  │
  ├── InvokeWorkflow: SHA1Online_Launch.xaml   (in_strUrl, out_uiSHA1Online → uiSHA1Online)  ← separate browser
  ├── InvokeWorkflow: SHA1Online_ComputeHash.xaml (in_strInput, out_strHash, io_uiSHA1Online ← uiSHA1Online)
  │
  ├── InvokeWorkflow: WebApp_UpdateRecord.xaml (in_strHash, io_uiWebApp ← uiWebApp)          ← back to WebApp browser
  └── CloseAllApplications handles all closing (REFramework) or App_Close per app (simple sequence)
```
Each web app gets its own incognito browser. Never share tabs across different apps.
**UiElement arg directions:** Launch = OUT (creates reference), action workflows = IN/OUT (preserves updates), App_Close = IN (just closes, CloseAllApplications ONLY).

**Pattern: Navigate then Act (Rule 9 — separate navigation from page action)**
```
WRONG — navigation mixed with page action in one workflow:
  WebApp_CreateTask.xaml
    ├── NGoToUrl → /create-task          ← navigation
    ├── NTypeInto → Task Name field      ← page action
    ├── NTypeInto → Description field    ← page action
    └── NClick → Submit button           ← page action

CORRECT — navigation and page action are separate invocations:
Main.xaml (or Process.xaml)
  ├── InvokeWorkflow: Browser_NavigateToUrl.xaml  (in_strUrl = in_Config("WebApp_CreateTaskUrl").ToString, io_uiBrowser)
  ├── InvokeWorkflow: WebApp_CreateTask.xaml     (in_strTaskName, in_strDescription, out_boolSuccess)
  ...
```
Navigation is reusable (other workflows may also need to reach /create-task). Failures are pinpointed (navigation timeout vs form field not found).

**Pattern: Desktop App Data Entry (from Excel)**
```
Main.xaml
  ├── InvokeWorkflow: Workflows\Utils\Excel_ReadInputData.xaml              (in_strFilePath, out_dt_Data)
  ├── ForEach row in dt_Data:
  │   ├── InvokeWorkflow: Workflows\InventoryManager\InventoryManager_Launch.xaml              (in_strExePath) — only if not running
  │   ├── InvokeWorkflow: Workflows\InventoryManager\InventoryManager_NavigateToNewRecord.xaml (io_uiApp) — navigate to entry screen
  │   ├── InvokeWorkflow: Workflows\InventoryManager\InventoryManager_EnterRecord.xaml         (in_strField1, in_strField2, ...)
  │   └── InvokeWorkflow: Workflows\InventoryManager\InventoryManager_SaveRecord.xaml          (out_boolSuccess)
  └── InvokeWorkflow: Workflows\InventoryManager\InventoryManager_Close.xaml                   ()
```

**Pattern: Desktop Multi-Tab Form (Rule 14 — navigate then fill per tab)**
```
Main.xaml  — variable: uiDesktopApp (type: UiElement)
  ├── InvokeWorkflow: DesktopApp_Launch.xaml                  (in_strAppPath, out_uiDesktopApp → uiDesktopApp)
  ├── InvokeWorkflow: DesktopApp_NavigateToPeopleTab.xaml     (io_uiDesktopApp ← uiDesktopApp)
  ├── InvokeWorkflow: DesktopApp_FillPeopleTab.xaml           (io_uiDesktopApp, in_strFirstName, in_strLastName, ...)
  ├── InvokeWorkflow: DesktopApp_NavigateToCompanyTab.xaml    (io_uiDesktopApp)
  ├── InvokeWorkflow: DesktopApp_FillCompanyTab.xaml          (io_uiDesktopApp, in_strCompanyName, ...)
  ├── InvokeWorkflow: DesktopApp_NavigateToOtherTab.xaml      (io_uiDesktopApp)
  ├── InvokeWorkflow: DesktopApp_FillOtherTab.xaml            (io_uiDesktopApp, in_strNotes, ...)
  └── InvokeWorkflow: Workflows\Utils\App_Close.xaml     (in_uiApp ← uiDesktopApp)
```
Each `NavigateTo` workflow clicks the tab and verifies it loaded (NCheckState). Each `Fill` workflow only types into fields — no tab clicks.

**Pattern: Email Processing (PO Approval with Tasks)**
```
Main.xaml
  ├── InvokeWorkflow: Workflows\Email\Email_GetMessages.xaml        (in_intTop, out_listMails)
  ├── ForEach mail in listMails:
  │   ├── InvokeWorkflow: Workflows\Email\Email_ExtractPOData.xaml (in_mmMail, out_strVendor, out_dblAmount)
  │   ├── InvokeWorkflow: Workflows\Email\Email_SaveAttachments.xaml (in_mmMail, in_strFolder, out_listFiles)
  │   ├── If dblAmount > threshold:
  │   │   ├── CreateFormTask (approval form)         ← persistence point, MUST be in Main
  │   │   └── WaitForFormTaskAndResume               ← persistence point, MUST be in Main
  │   └── LogMessage: "Processed email from {strVendor}"
  └── LogMessage: "Processed {listMails.Count} emails"
```
> **⚠️ Persistence constraint:** `CreateFormTask` and `WaitForFormTaskAndResume` are persistence points — the workflow suspends and resumes at these activities. They MUST remain in Main.xaml (the entry-point file). Never move them into invoked sub-workflows.

### Argument Design
Each sub-workflow communicates through typed arguments — never global variables:
- **Inputs (`in_`)**: Everything the workflow needs to do its job
- **Outputs (`out_`)**: Results, status flags, extracted data
- **In/Out (`io_`)**: Mutable objects passed through (DataTables, collections)
- **Keep argument count ≤ 7** per workflow. If you need more, consider a DataRow or Dictionary argument.

### When NOT to Decompose
- **Prototype/POC workflows** — single file is fine for quick testing
- **REFramework Process.xaml** — this IS the transaction workflow, keep it focused but complete. **NEVER create a wrapper** like `Performer_Process.xaml` that Process.xaml delegates to — Process.xaml directly invokes action workflows (WebApp_ExtractData.xaml, etc.). Lint 75.
- **Utility workflows** — small helpers (≤50 lines) don't need further splitting

### Login/Launch Workflow Pattern (Phase 3 — XAML Generation Only)

> ⛔ **This section is for XAML code generation (Phase 3). During Playwright inspection (Phase 2), NEVER type credentials, fill login forms, or click submit. See "ui-inspection.md" section below.**

**Login always lives inside `AppName_Launch.xaml` — NEVER create a separate `AppName_Login.xaml`.** Whether the app requires login or not, the Launch workflow handles everything: open browser/app → login (if needed) → verify ready state. This keeps one workflow per app for InitAllApplications to invoke.

**When generating ANY launch workflow, COPY the structure from `assets/samples/common-workflows/Workflows/WebAppName/WebAppName_Launch.xaml`.** Do NOT invent a login pattern from scratch. The golden sample contains every required element:

**Required XAML structure (in this exact order):**
1. `LogMessage` → `[START]`
2. `NApplicationCard` (Use App/Browser) — URL from `in_strUrl` argument, NEVER hardcoded. **MUST have `OutUiElement="[out_uiAppName]"`** to capture the browser/app instance for downstream workflows
3. → INSIDE the NApplicationCard.Body (minimal credential scope):
   - Variables: `strUsername` (String), `secstrPassword` (**SecureString**, NOT String)
   - `RetryScope` → `GetRobotCredential` with `AssetName="[in_strCredentialAssetName]"`, `Username="[strUsername]"`, `Password="[secstrPassword]"`
   - `NTypeInto` username field → `Text="[strUsername]"`
   - `NTypeInto` password field → `SecureText="[secstrPassword]"` (**NOT** `Text=` — passwords use `SecureText`)
   - `NClick` login button
   - **`Pick` with two `PickBranch` for login validation** (MANDATORY — never skip this):
     - Branch 1 (Success): trigger = `NCheckState` waiting for dashboard/home element → `LogMessage` success
     - Branch 2 (Failure): trigger = `NCheckState` waiting for error element → `NGetText` error message → `Throw` with error details
     - **Error element selector:** Must come from Playwright inspection (ask user to simulate failed login). If not available, use placeholder: `<webctrl tag='DIV' class='PLACEHOLDER_ERROR_SELECTOR' />` with `<!-- TODO: Replace with real error selector -->`
4. `LogMessage` → `[END]`

**Arguments:** `in_strUrl` (from Config), `in_strCredentialAssetName` (Orchestrator Credential asset name from Config), `out_uiAppName` (OutArgument(UiElement) — e.g., `out_uiWebApp`. Captured by NApplicationCard OutUiElement, flowed up through InitAllApplications to Main)

**UiElement reference chain (CRITICAL — preserves browser/app instance across workflows):**
```
Launch (out_uiWebApp — OUT)
  → InitAllApplications (out_uiWebApp — OUT) → outputs to Main.xaml
    → Main.xaml (variable: uiWebApp)
      → Process.xaml (io_uiWebApp — IN/OUT) → preserves updated reference
        → Action workflows (io_uiWebApp — IN/OUT) → preserves updated reference
        → Browser_NavigateToUrl (io_uiBrowser — IN/OUT) → generic util
      → CloseAllApplications (in_uiWebApp — IN)
        → App_Close.xaml (in_uiApp — IN) → just closes
```
Key rule: **Process.xaml and all action workflows MUST use InOut direction** for UiElement args. The browser reference can get updated (page refresh, navigation) and the updated reference must flow back to Main.
⛔ **Process.xaml and action workflows NEVER invoke App_Close.** Apps stay open across all transactions. Only CloseAllApplications (End Process state) closes apps.
⛔ **Process.xaml available arguments:** `in_TransactionItem`, `in_Config`, and `io_ui*` (UiElement args wired by `modify_framework.py`). **`in_TransactionNumber` is NOT available** — it lives in Main.xaml's state machine scope and is forwarded only to GetTransactionData.xaml and SetTransactionStatus.xaml. To reference transaction identity in Process.xaml, use fields from `in_TransactionItem` (e.g., `in_TransactionItem("WIID").ToString` for DataRow dispatchers, `in_TransactionItem.SpecificContent("Key").ToString` for QueueItem performers). Lint 100 catches this.

**Common mistakes the model makes (all caught by golden sample comparison):**
- ❌ `GetRobotCredential ... Result="[strPassword]"` — `Result` property does NOT exist. Use `Password=` and `Username=`
- ❌ `Variable x:TypeArguments="x:String" Name="strPassword"` — password MUST be SecureString (`ss:SecureString`)
- ❌ `NTypeInto ... Text="[strPassword]"` for password — use `SecureText="[secstrPassword]"`
- ❌ Credential retrieval OUTSIDE NApplicationCard — keep at minimal scope, INSIDE the browser session
- ❌ No login validation after clicking Login — ALWAYS use `Pick`/`PickBranch` to verify success or catch errors
- ❌ Missing `OutUiElement="[out_uiAppName]"` on NApplicationCard — without this, downstream workflows have no UiElement reference. Declare as `OutArgument(ui:UiElement)` (e.g., `out_uiWebApp`). Process.xaml and action workflows must use `io_` (InOut) direction to preserve updated references
- ❌ **UiElement typed as `x:Object`** — causes Option Strict BC30512 crash. All UiElement variables/arguments MUST use `ui:UiElement` type, never `x:Object`. Same applies to ALL typed arguments: `str*` → `x:String`, `int*` → `x:Int32`, `dt_*` → `sd:DataTable`, `bool*` → `x:Boolean`. Lint 76 catches both single-file (naming conventions) and cross-file (caller vs target x:Property type) mismatches.
- ❌ `NGoToUrl` inside Launch — redundant. `NApplicationCard` with `OpenMode="Always"` and `TargetApp Url=` already opens the browser at the target URL. NGoToUrl is for mid-session navigation (Browser_NavigateToUrl.xaml), not initial launch.
- ❌ Separate `AppName_Login.xaml` — login belongs INSIDE `AppName_Launch.xaml`, not in a separate file
- ❌ App-specific `AppName_NavigateTo.xaml` — use the generic `Browser_NavigateToUrl.xaml` from Utils/. The caller passes the full URL from Config. Never clone navigation per app
- ❌ Hardcoded `Url="https://..."` in TargetApp — use `Url="[in_strUrl]"` from argument
- ❌ URL concatenation `Url="[in_strUrl + &quot;/login&quot;]"` — assemble full URL at caller level with `String.Format`, workflow receives complete `in_strUrl`
- ❌ **Undeclared variables** — model writes `[strSomething]` in expressions but forgets to add `<Variable x:TypeArguments="..." Name="strSomething" />`. This causes Studio compile errors or silent runtime failures. EVERY variable referenced in `[brackets]` MUST have a matching `<Variable>` or `<x:Property>` declaration. Lint 67 catches this.
- ❌ **App_Close in Process.xaml or action workflows** — apps stay open across transactions. Closing mid-process kills the browser for transaction 2+. App_Close is EXCLUSIVELY invoked from CloseAllApplications.xaml (End Process state). Lint 68 catches this.
- ❌ **Redundant Process wrapper** (e.g. `Performer_Process.xaml`, `WebApp_Process.xaml`) — Process.xaml IS the process orchestrator. Creating a wrapper file that Process.xaml delegates to adds an unnecessary argument-passing layer (UiElement args get lost) and folder clutter. Process.xaml should directly invoke action workflows. Lint 75 catches this.
- ❌ **UiElement stored in Config dictionary** (`in_Config("app_WebApp") = uiWebApp`) — Config is `Dictionary(String, Object)`, losing type safety and breaking the typed argument chain. UiElement MUST flow via typed arguments: Launch (`out_uiWebApp` OutArgument) → InitAllApplications (`out_uiWebApp` OutArgument) → Main.xaml (variable `uiWebApp`) → Process.xaml (`io_uiWebApp` InOutArgument) → action workflows (`io_uiWebApp` InOutArgument). The REFramework template's InitAllApplications only has `in_Config` by default — you MUST add `out_ui*` OutArgument x:Property declarations for each launched app. Lint 77/78 catch this.
- ❌ **InitAllApplications captures UiElement as Variable instead of Argument** — if `out_uiWebApp` from Launch lands in a local Variable inside InitAllApplications, it dead-ends there and never reaches Main.xaml. It must be declared as an OutArgument (`<x:Property Name="out_uiWebApp" Type="OutArgument(ui:UiElement)" />`), and Main.xaml's invoke of InitAllApplications must wire `out_uiWebApp` with Direction=Out to a Main variable. Lint 77 catches this.

### REFramework Init/Close — Delegate to Sub-Workflows
`InitAllApplications.xaml` and `CloseAllApplications.xaml` are orchestrators — they should use `InvokeWorkflowFile` to call dedicated launch/close workflows, NOT inline `NApplicationCard` or UI activities directly:

⛔ **InitAllApplications.xaml scope: Launch + Login ONLY.** This workflow opens applications and authenticates — nothing else. Navigation to specific pages, data extraction (scraping tables, reading files), filtering, and any business logic do NOT belong here. Common violation: dispatcher puts `NavigateToWorkItems` + `ExtractWorkItems` + `FilterDataTable` in InitAllApplications — this bloats Init with business logic that fails independently of app launch.

**Dispatcher data loading belongs in `GetTransactionData.xaml`** — on first call (`in_TransactionNumber = 1`), navigate to the data source, extract records into `io_dt_TransactionData`, then index. On subsequent calls, just index into the already-populated DataTable:
```
GetTransactionData.xaml (dispatcher pattern)
  ├── If io_dt_TransactionData Is Nothing OrElse io_dt_TransactionData.Rows.Count = 0
  │   ├── InvokeWorkflow: Browser_NavigateToUrl.xaml   (in_strUrl = in_Config("WebApp_WorkItemsUrl").ToString, io_uiBrowser)
  │   ├── InvokeWorkflow: WebApp_ExtractData.xaml   (extraction)
  │   └── Assign: Filter io_dt_TransactionData         (filtering)
  ├── If in_TransactionNumber <= io_dt_TransactionData.Rows.Count
  │   ├── Then: out_TransactionItem = Rows(in_TransactionNumber - 1)
  │   └── Else: out_TransactionItem = Nothing          (end process)
```
This keeps InitAllApplications clean and puts data loading where the framework expects it — inside the transaction data retrieval logic, with proper retry handling from the surrounding RetryScope.

```
InitAllApplications.xaml  — ⛔ NO GetRobotCredential, NO SecureString, NO navigation, NO extraction
  ├── Log [START]
  ├── InvokeWorkflow: Workflows\HRPortal\HRPortal_Launch.xaml
  │   Arguments:
  │     in_strUrl = String.Format("{0}/{1}", in_Config("HRPortal_BaseURL").ToString, in_Config("HRPortal_LoginPath").ToString)
  │     in_strCredentialAssetName = in_Config("HRPortal_CredentialAsset").ToString
  │     out_uiHRPortal → out_uiHRPortal          ← Launch OUTPUT, flows up to Main
  │   ⛔ Pass ONLY in_strCredentialAssetName (String) — NEVER in_secstrPassword (SecureString)
  │   ⛔ GetRobotCredential lives INSIDE HRPortal_Launch.xaml, NOT here
  │   ⛔ **Variable name in the invoke = InitAllApplications' OWN argument name (`out_uiHRPortal`), NOT Main's variable name (`uiHRPortal`).** Writing `[uiHRPortal]` here causes BC30451 "not declared" because `uiHRPortal` is Main's variable, not InitAllApplications'.
  │   Correct XAML:  `<OutArgument x:Key="out_uiHRPortal">[out_uiHRPortal]</OutArgument>`
  │   Wrong XAML:    `<OutArgument x:Key="out_uiHRPortal">[uiHRPortal]</OutArgument>` ← BC30451 crash
  ├── InvokeWorkflow: Workflows\SAP\SAP_Launch.xaml            (in_strConnection)
  └── Log [END]

Main.xaml  — variable: uiHRPortal (type: UiElement)
  ├── InitAllApplications.xaml  (out_uiHRPortal → uiHRPortal)
  ├── Process.xaml              (io_uiHRPortal ← uiHRPortal)   ← IN/OUT preserves updated ref
  └── CloseAllApplications.xaml (in_uiHRPortal ← uiHRPortal)

CloseAllApplications.xaml
  ├── Log [START]
  ├── InvokeWorkflow: Workflows\Utils\App_Close.xaml       (in_uiApp ← in_uiHRPortal)
  ├── InvokeWorkflow: Workflows\SAP\SAP_Close.xaml             ()
  └── Log [END]
```
⛔ **Common violation:** Model puts `GetRobotCredential` in InitAllApplications, then passes `SecureString` password as argument to Launch workflow. This is WRONG — credential retrieval belongs INSIDE the Launch workflow at minimal scope. InitAllApplications passes only the Orchestrator asset NAME (a plain String), not the actual credentials. **Second common violation (dispatchers):** Model puts navigation + extraction + filtering in InitAllApplications instead of GetTransactionData — this overloads Init with business logic and loses retry protection.

**UiElement argument direction rules:**

⚠️ **XAML type is `ui:UiElement`, NEVER `x:Object`.** Using `x:Object` causes Option Strict BC30512: "disallows implicit conversions from 'Object' to 'UiElement'". Lint 76.

| Workflow | Arg direction | XAML type | Reason |
|---|---|---|---|
| `AppName_Launch.xaml` | `out_uiAppName` (OUT) | `OutArgument(ui:UiElement)` | Creates the browser/app reference |
| `InitAllApplications.xaml` | `out_uiAppName` (OUT) | `OutArgument(ui:UiElement)` | Passes reference up to Main |
| `Process.xaml` | `io_uiAppName` (IN/OUT) | `InOutArgument(ui:UiElement)` | **Must be IN/OUT** — reference can update |
| Action workflows | `io_uiAppName` (IN/OUT) | `InOutArgument(ui:UiElement)` | **Must be IN/OUT** — preserves updated ref |
| `Browser_NavigateToUrl.xaml` | `io_uiBrowser` (IN/OUT) | `InOutArgument(ui:UiElement)` | Generic util, preserves ref |
| `CloseAllApplications.xaml` | `in_uiAppName` (IN) | `InArgument(ui:UiElement)` | Just passes to App_Close |
| `App_Close.xaml` | `in_uiApp` (IN) | `InArgument(ui:UiElement)` | Just closes |

For InvokeWorkflowFile argument bindings: `<OutArgument x:TypeArguments="ui:UiElement" x:Key="out_uiWebApp">[uiWebApp]</OutArgument>`
For Variable declarations: `<Variable x:TypeArguments="ui:UiElement" Name="uiWebApp" />`

**Variable/argument name prefix → XAML type (lint 76 enforces this):**

| Prefix | XAML type | xmlns required | Example |
|---|---|---|---|
| `ui`, `uiEl` | `ui:UiElement` | `xmlns:ui="http://schemas.uipath.com/workflow/activities"` | `uiWebApp`, `out_uiSHA1Online` |
| `str` | `x:String` | (built-in) | `strName`, `in_strUrl` |
| `int` | `x:Int32` | (built-in) | `intRetry`, `out_intCount` |
| `dt_` | `sd:DataTable` | `xmlns:sd="clr-namespace:System.Data;assembly=System.Data.Common"` (already in framework templates) | `dt_Report`, `io_dt_WorkItems` |
| `bool` | `x:Boolean` | (built-in) | `boolSuccess`, `out_boolFound` |
| `dbl` | `x:Double` | (built-in) | `dblAmount` |
| `secstr` | `ss:SecureString` | `xmlns:ss="clr-namespace:System.Security;assembly=System.Private.CoreLib"` | `secstrPassword` |

⚠️ **NEVER use `x:Object`** — Option Strict BC30512 crash. Always use the specific type.

This follows Rule #4 (Launch/Close always separate), Rule #1 (one UI scope per workflow), Rule #8 (credentials inside workflow), and Rule #10 (no logout for browser apps).
