# Scaffolding & Templates

Template selection, NuGet mapping, validation, and project scaffolding. Core rules are in SKILL.md.

## Template Selection

| Need | Template |
|---|---|
| **Non-REFramework project** | `simple-sequence/Main.xaml` (276 lines) |
| Assign, BuildDataTable, Switch, Flowchart | `simple-sequence/Main.xaml` — real exports of all these |
| Process cleanup (ForEach + TryCatch) | `reframework/Framework/KillAllProcesses.xaml` (155 lines) |
| CloseAllApplications orchestrator | `reframework/Framework/CloseAllApplications.xaml` (65 lines) — invokes `App_Close.xaml` per app |
| Clean process placeholder | `reframework/Framework/Process.xaml` (92 lines) |
| Sequence with arguments | `reframework/Framework/InitAllApplications.xaml` (75 lines) |
| App close/browser navigate | `samples/common-workflows/Workflows/Utils/App_Close.xaml`, `Workflows/Utils/Browser_NavigateToUrl.xaml` |
| App login (web or desktop) | `samples/common-workflows/Workflows/WebAppName/WebAppName_Launch.xaml` |
| HTTP/REST API, OAuth, queue dispatch | `samples/common-workflows/HttpApiDispatcher_Main.xaml` (orchestrator) + `Workflows/Api/Api_FetchInvoices.xaml` (credential+OAuth+fetch) |
| If/Else branching | `reframework/Framework/GetTransactionData.xaml` |
| ForEachRow + TryCatch | `reframework/Framework/InitAllSettings.xaml` |
| Multi-branch conditions | `stripped/SetTransactionStatus.xaml` |
| UI automation (modern) | `stripped/FormFilling_Main.xaml`, `samples/common-workflows/Workflows/WebAppName/WebAppName_Launch.xaml` |
| Email automation (Integration Service) | No golden template — follow `xaml-integrations.md` Email section |
| Web form filling, browser automation | `stripped/FormFilling_Main.xaml` |
| PDF extraction (native + OCR), file iteration | `simple-sequence/PDFExtraction_Main.xaml` |
| Web scraping, Extract Table Data, pagination | `simple-sequence/WebScraping_Sequence1.xaml` |
| StateMachine (REFramework) | `stripped/REFramework_Main.xaml` |

**No template?** If the user needs an activity not in any template (e.g., HTTP Request, Invoke Code), use the closest template for the overall structure, then insert activity XAML from the relevant `references/xaml-*.md` file (see SKILL.md routing table). For Tasks form tasks, see the **uipath-tasks** skill.

**Large template files:** Use stripped excerpts in `assets/stripped/` (visual metadata removed, 50-70% smaller). E.g., `stripped/FormFilling_Main.xaml` is 26KB vs 94KB original. Full originals needed only for `--golden` validation.

## Activity → NuGet Package Mapping

When generating XAML, auto-resolve required dependencies from activities used. `UiPath.System.Activities` is always required. Add others based on the activities present in the workflow:

| Activities | NuGet Package |
|---|---|
| Sequence, If, ForEach, While, Switch, Assign, MultipleAssign, TryCatch, Throw, Rethrow, RetryScope, InvokeWorkflowFile, InvokeCode, InvokeMethod, LogMessage, Comment, Break, Continue, MessageBox, InputDialog, DeserializeJson, AddDataRow, AddDataColumn, BuildDataTable, FilterDataTable, ForEachRow, JoinDataTables, LookupDataTable, MergeDataTable, OutputDataTable, RemoveDuplicateRows, SortDataTable, GenerateDataTable, CopyFile, MoveFile, DeleteFileX, CreateDirectory, PathExists, ForEachFileX, GetRobotAsset, GetRobotCredential, AddQueueItem, GetQueueItem, SetTransactionStatus, IfElseIfV2 | `UiPath.System.Activities` (always) |
| UseApplicationBrowser, NClick, NTypeInto, NSelectItem, NGetText, NGetAttribute, NCheckAppState, ElementExists, TakeScreenshot, NHoverElement, NHighlightElement, any `uix:` prefixed activity | `UiPath.UIAutomation.Activities` |
| UseExcelFile, ReadRange (modern), WriteRange (modern), ForEachSheetRow, ExcelApplicationScope (legacy) | `UiPath.Excel.Activities` |
| HttpClient (HTTP Request) | `UiPath.WebAPI.Activities` (NOT Web.Activities — that package doesn't exist) |
| GetIMAPMailMessages, SendMail, SaveMailAttachments | `UiPath.Mail.Activities` |
| CreateFormTask, WaitForFormTaskAndResume | `UiPath.Persistence.Activities` + `UiPath.FormActivityLibrary` (form designer — must be added explicitly, NOT a transitive dependency of Form.Activities) |
| VerifyExpression, VerifyControlAttribute | `UiPath.Testing.Activities` |
| DatabaseConnect, ExecuteQuery, ExecuteNonQuery | `UiPath.Database.Activities` |
| ReadPDFText, ReadPDFWithOCR, ExtractPDFPageRange, MergePDFs | `UiPath.PDF.Activities` |
| GoogleOCR (Tesseract OCR engine) | `UiPath.UIAutomation.Activities` |

When scaffolding a project, inspect the workflows being generated, identify which packages are needed from the table above, then query the NuGet API for their latest stable versions and include them all via `--deps`.

### Adding Dependencies to an Existing Project

When generating a workflow INSIDE an existing project (project.json already exists):

1. Identify which packages are needed from the Activity → NuGet Package Mapping table above
2. Add them in one command:
   ```bash
   # Single package
   python3 scripts/resolve_nuget.py --add /path/to/project UiPath.UIAutomation.Activities

   # Multiple packages
   python3 scripts/resolve_nuget.py --add /path/to/project UiPath.Excel.Activities UiPath.Mail.Activities
   ```
   This resolves the latest stable version and updates project.json automatically.
   Packages already at the latest version are skipped. Existing packages are updated if newer versions are available.

**Common missed dependencies (causes "activity not found" in Studio):**
- HTTP/REST API workflows → `UiPath.WebAPI.Activities`
- Email workflows → `UiPath.Mail.Activities`
- Tasks / Form tasks → `UiPath.Persistence.Activities` + `UiPath.FormActivityLibrary` (both required — Persistence for runtime, FormActivityLibrary for form designer)
- Database queries → `UiPath.Database.Activities`
- UI automation (clicks, types) → `UiPath.UIAutomation.Activities`

## Workflow: Validating XAML

> **Environment note:** All `python3` commands below target Claude's Linux container (Claude Code, claude.ai compute). On Windows/PowerShell, substitute `python` for `python3`.

```bash
# Single file
python3 scripts/validate_xaml path/to/workflow.xaml

# Entire project
python3 scripts/validate_xaml path/to/project/

# Strict mode (naming convention warnings)
python3 scripts/validate_xaml path/to/project/ --strict

# Lint mode (semantic / best-practice checks)
python3 scripts/validate_xaml path/to/project/ --lint

# Both
python3 scripts/validate_xaml path/to/project/ --lint --strict

# Golden template mode (suppress Studio export noise: naming, Config .ToString, DisplayName, hardcoded idx, FuzzySelector)
python3 scripts/validate_xaml assets/ --lint --golden

# Regression test (validates golden templates + scaffolds all variants)
python3 scripts/regression_test.py
```

**Structural checks** (always run): well-formed XML, root Activity element, x:Class, xmlns declarations vs usage, unique IdRefs, HintSize attributes, argument types/naming, ViewState dictionaries, InvokeWorkflowFile path resolution, expression language consistency.

**Lint checks** (`--lint`) — 71 numbered lint rules (+ plugin lint rules). See `lint-reference.md` for the full table searchable by lint number.

## Workflow: Scaffolding a UiPath Project

Three project types are supported:

| Variant | Use case | Template | Base dependencies |
|---|---|---|---|
| `sequence` | Simple linear automation, no transactions | `simple-sequence-template/` | System only (add others per mapping table) |
| `dispatcher` | REFramework — reads data, creates queue items | `reframework/` | System + UIAutomation + Excel + Testing |
| `performer` | REFramework — processes queue items | `reframework/` | System + UIAutomation + Excel + Testing |

### Choosing the Right Variant

**Decision tree — ask these questions in order:**

1. **Does the PDD/requirements describe BOTH (a) reading items from a list/table/web page AND (b) processing each item individually with status updates?** → **`dispatcher` + `performer` pair** (two separate projects). This is the production-standard pattern. The Dispatcher scrapes/reads the source data and populates an Orchestrator Queue; the Performer consumes queue items one by one. **This is the correct choice for any PDD that describes iterating through work items, cases, records, or transactions from a source system.**
2. **Does the process ONLY consume items from an Orchestrator Queue that already exists?** → `performer` only
3. **Does the process ONLY read bulk data and push to a Queue (no per-item processing)?** → `dispatcher` only
4. **Does the process read bulk data and process each item in a loop WITH per-item retry/status tracking, but without Orchestrator Queues?** → `dispatcher` with DataRow transaction type (single project, self-contained)
5. **Everything else** → `sequence`

**⚠️ Common mistake: choosing `performer`-only when Dispatcher + Performer is correct.** If the PDD describes both data extraction and per-item processing (e.g., "access Work Items listing" + "for each activity, perform steps"), the answer is almost always a **Dispatcher + Performer pair**, not a single Performer that assumes queue items magically exist. Ask yourself: "Who puts the items in the queue?" — if the answer is "the robot needs to scrape them from a web page/Excel/DB", you need a Dispatcher.

**Keyword signals from the user's request:**

| User says... | Variant |
|---|---|
| PDD with "for each item/activity, perform steps" + list/table scraping | **`dispatcher` + `performer` pair** |
| "work items listing", "for each WI5", "scrape table and process each row" | **`dispatcher` + `performer` pair** |
| "queue item", "Orchestrator queue", "transaction item", "SetTransactionStatus" | `performer` |
| "read from Excel/DB and add to queue", "dispatcher", "bulk upload to queue" | `dispatcher` |
| "REFramework", "Config.xlsx", "retry failed transactions", "InitAllSettings" | `dispatcher` or `performer` (ask which) |
| "just automate X", "fill a form", "run a script", "attended bot", "simple process" | `sequence` |
| "input dialog", "message box", "one-shot", "no queue" | `sequence` |

**When in doubt:** Start with `sequence`. REFramework adds significant complexity (StateMachine, Config.xlsx, 8+ framework files). Only use it when the process genuinely needs transaction-level retry, queue integration, or the structured init/process/end lifecycle.

**PDD adherence:** When a PDD or requirements document specifies a particular approach, tool, or method — implement it as specified. Do NOT substitute alternatives you consider superior without proposing them to the user first. If you want to suggest an alternative, present it as an option alongside the PDD-specified approach, explain the tradeoff, and let the user choose. Never label your preferred alternative as "(Recommended)" when it deviates from what the PDD says.

**Dispatcher + Performer pairs:** Many production processes use both — a Dispatcher reads source data and populates the queue, a Performer consumes and processes items. If the user describes an end-to-end pipeline, scaffold both projects.

**CRITICAL — Dependency versions:** Template project.json files contain baseline versions that go stale. Before scaffolding, query the UiPath Official NuGet feed for current stable versions of all required packages.

**NuGet v3 flat2 API** — fetch all versions for a package:
```
https://pkgs.dev.azure.com/uipath/5b98d55c-1b14-4a03-893f-7a59746f1246/_packaging/1c781268-d43d-45ab-9dfc-0151a1c740b7/nuget/v3/flat2/{package-id-lowercase}/index.json
```
Returns `{"versions": [...]}` sorted **oldest-first** (ascending). The array contains ALL versions including prereleases.

**Filtering — MUST follow these steps:**
1. Fetch the JSON response
2. Filter OUT any version containing `-` (this catches `-preview`, `-beta`, `-rc`, `-alpha`, etc.)
3. Take the **LAST** remaining entry = latest stable version
4. If no stable versions remain (all are prerelease), report the issue to the user

**Example script (Linux/macOS — on Windows use `resolve_nuget.py` instead):**
```bash
curl -s "https://pkgs.dev.azure.com/uipath/5b98d55c-1b14-4a03-893f-7a59746f1246/_packaging/1c781268-d43d-45ab-9dfc-0151a1c740b7/nuget/v3/flat2/uipath.uiautomation.activities/index.json" \
  | python3 -c "import json,sys; vs=[v for v in json.load(sys.stdin)['versions'] if '-' not in v]; print(vs[-1] if vs else 'ERROR: no stable version found')"
```

**Common mistake:** Grabbing the last entry WITHOUT filtering → picks up `26.1.0-preview` instead of `25.10.26`. Always filter out versions with `-` in the string before selecting.

```bash
# Step 1: Resolve latest stable versions (ALWAYS do this first — Rule G-5)
python3 scripts/resolve_nuget.py UiPath.System.Activities UiPath.UIAutomation.Activities

# Step 2: Use resolved versions in scaffold command
# Simple sequence project (e.g. attended automation with UI + dialogs)
python3 scripts/scaffold_project.py \
  --name "MyProject" \
  --variant sequence \
  --attended \
  --output /path/to/output \
  --deps "UiPath.System.Activities:[<version>],UiPath.UIAutomation.Activities:[<version>]"

# REFramework performer
python3 scripts/resolve_nuget.py UiPath.System.Activities UiPath.UIAutomation.Activities UiPath.Excel.Activities UiPath.Testing.Activities
python3 scripts/scaffold_project.py \
  --name "MyProject" \
  --variant performer \
  --output /path/to/output \
  --queue-name "MyProjectQueue" \
  --queue-folder "Shared" \
  --deps "UiPath.System.Activities:[<version>],UiPath.UIAutomation.Activities:[<version>],UiPath.Excel.Activities:[<version>],UiPath.Testing.Activities:[<version>]"
```

**⚠️ Do NOT create the project folder before running scaffold.** The script creates `<output>/<name>/` automatically. If you `mkdir MyProject` then run `--output MyProject --name MyProject`, you get `MyProject/MyProject/`. Use `--output <parent_dir>` (e.g. `/home/claude` on Linux, `$env:USERPROFILE\Desktop` on Windows) and let the script create the folder.

### Dispatcher vs Performer

- **Dispatcher** reads source data (Excel, DB, API), creates Orchestrator Queue Items for each transaction, then exits
- **Performer** picks Queue Items one by one, processes each, and sets status (Success/Failed/Retry)

⛔ **Never modify `SetTransactionStatus.xaml`** — the default Framework implementation handles all cases correctly. Do NOT generate custom logic in this file.

**Dispatcher gotcha:** `in_TransactionItem` must be `Nothing` in the Dispatcher's Main.xaml calls to SetTransactionStatus, because the Dispatcher creates queue items — it does NOT consume them, so there is no QueueItem to pass.

⛔ **Process.xaml scope:** `in_TransactionNumber` is NOT passed to Process.xaml — it lives in Main.xaml's state machine and flows only to GetTransactionData.xaml and SetTransactionStatus.xaml. In Process.xaml, reference transaction fields via `in_TransactionItem` (e.g., `in_TransactionItem("WIID").ToString` for DataRow, `in_TransactionItem.SpecificContent("Key").ToString` for QueueItem). Lint 100 catches this.

#### Transaction Item Types

By default, REFramework templates use `QueueItem` as the transaction type. For dispatchers that process data directly (without Orchestrator Queues), the transaction type is typically `DataRow`.

**To switch from QueueItem to DataRow:** Use `scaffold_project.py --variant dispatcher --transaction-type DataRow` which handles all files automatically, including test cases (`Tests/GetTransactionDataTestCase.xaml`, `Tests/ProcessTestCase.xaml`).

If manually switching (not recommended), change these files:
1. `TransactionItem` variable declaration in Main.xaml
2. All `OutArgument`/`InArgument` referencing TransactionItem in Main.xaml
3. `out_TransactionItem` argument in GetTransactionData.xaml
4. `in_TransactionItem` argument in Process.xaml (⛔ NOT SetTransactionStatus.xaml)
5. Test case files: `Tests/GetTransactionDataTestCase.xaml`, `Tests/ProcessTestCase.xaml`
6. Add the required xmlns if not already present

⛔ **GetTransactionData.xaml body MUST also change for dispatchers.** The performer template body contains `RetryScope → GetQueueItem` which fetches from an Orchestrator queue. Dispatchers iterate a local DataTable — they MUST replace the entire RetryScope+GetQueueItem block with DataTable row indexing:

```
If in_TransactionNumber <= io_dt_TransactionData.Rows.Count
  Then: out_TransactionItem = io_dt_TransactionData.Rows(in_TransactionNumber - 1)
  Else: out_TransactionItem = Nothing   ← triggers End Process state
```

**Why this matters:** `GetQueueItem.TransactionItem` outputs `QueueItem`, but a dispatcher's `out_TransactionItem` is `DataRow`. Studio will throw a type mismatch compile error. The scaffold script (`--variant dispatcher`) handles this automatically. If writing GetTransactionData manually, NEVER leave `GetQueueItem` in a dispatcher project. Lint rule 51 catches this.


### Generating a Full Project

Copy this checklist and track progress. See `decomposition.md` for detailed rules, folder structure examples, naming conventions, and argument design. See `golden-templates.md` → "Sample Workflows" for a real example project. See `xaml-invoke.md` for InvokeWorkflowFile XAML structure.

```
Project Generation:
- [ ] Phase 0: If implementing from a PDD — read it fully, implement EXACTLY as specified
        Do NOT substitute alternative approaches without proposing to the user first
        Technical improvements (selectors, error handling, retry) are OK — functional changes are NOT
        - PDD says "use website X to do Y" → automate website X. Do NOT replace with InvokeCode/programmatic alternative
        - PDD says "use application X" → automate application X. Do NOT substitute a different tool
        - If you think an alternative is better → implement the PDD way FIRST, then PROPOSE the alternative
        ARCHITECTURE CHECK: Does the PDD describe BOTH reading/scraping items AND processing each one?
          → YES = Dispatcher + Performer (two separate projects). ALWAYS recommend this split to the user.
          → See "CRITICAL: Architecture Selection for PDDs" section above.
          → Do NOT default to a single project. If unsure, ask the user.
- [ ] Phase 1: Plan decomposition — list workflows, map to Workflows/ subfolders, define arguments
        For each workflow: verify it matches the PDD's specified approach (not a substitution)
        If any workflow deviates from PDD (e.g. InvokeCode SHA1 instead of browser SHA1Online) → STOP and ask
        ⛔ CREDENTIAL CHECK: No workflow may accept username/password/SecureString as arguments.
          Credentials are retrieved via GetRobotCredential INSIDE the workflow that uses them.
          Pass only `in_strCredentialAssetName` (the Orchestrator asset name string). See `decomposition.md` Rule 8.

PLAN SELF-CHECK — answer BEFORE presenting your plan to the user:
  □ For EACH workflow in my plan: does it implement the PDD's specified approach, or did I substitute
    a "better" alternative? (e.g., InvokeCode SHA1 instead of browser automation of sha1-online.com)
    → If ANY substitution exists: REMOVE it and implement the PDD way. Propose alternative AFTER.
  □ Does my plan include an explicit inspection step for EVERY target app?
    → Browser apps: "Inspect [app] with Playwright" (if Playwright MCP available)
    → Desktop apps: "Inspect [app] with PowerShell" (if PowerShell available on Windows)
    → If ANY app lacks an inspection step and the tool is available: ADD it now.
If you cannot answer YES to all checks, revise your plan before presenting it.

PLAN OUTPUT FORMAT — present your plan using this structure:
  Phase 0: [Architecture decision]  Phase 1: [Workflows + arguments]
  Phase 2: [EACH app to inspect — e.g. "Inspect WebApp with Playwright"]  Phase 3-6: [Generate → Wire → Validate → Config]
If Phase 2 is empty or missing, you are violating the skill rules.

- [ ] Phase 2: Inspect target applications BEFORE generating any XAML — MANDATORY when inspection tools are available
        If Playwright MCP is available → use it. Do NOT skip to Phase 3 with guessed selectors.
        Browser apps → Playwright MCP: navigate to each page, snapshot/inspect elements, record real selectors
        LOGIN PAGES: snapshot for selectors → ask user to simulate failed login (capture error element) → then ask user to log in correctly
        Wait for user confirmation that they've logged in before inspecting authenticated pages
        Desktop apps → PowerShell: run inspect-ui-tree.ps1, record real selectors
        Fallback (no MCP tools available): use PDD screenshots/descriptions — but never guess selectors for dynamic elements
        See `ui-inspection.md` for detailed Playwright and desktop inspection workflows.
- [ ] Phase 2b: Write `selectors.json` — structured output of ALL Playwright inspection results
        Write to project root (shared across Dispatcher+Performer if same apps).
        Format: `{"apps": [{"name": "...", "selector": "...", "browser_type": "Edge", "screens": [{"name": "...", "url": "...", "elements": [{"name": "...", "selector": "...", "taxonomy_type": "Input|Button|..."}]}]}]}`
        taxonomy_type values: Input, Password, Button, Dropdown, Link, CheckBox, RadioButton, Text
        Screen = one page/URL. Group elements by the page they were inspected on.
        This file is consumed by BOTH generate_object_repository.py AND workflow JSON specs (selectors).
- [ ] Phase 2c: Generate Object Repository — `python3 scripts/generate_object_repository.py --from-selectors selectors.json --project-dir <project>`
        Run for EACH project (Dispatcher + Performer). Lint 94 is ERROR — project CANNOT pass validation without this.
- [ ] Phase 2d: **`--project-dir` auto-wires Object Repository (Rule G-9)** — Phase 2c wrote `.objects/refs.json`. When you pass `--project-dir <project>` to `generate_workflow.py` in Phase 3, the script automatically injects `obj_repo`/`obj_repo_app` into every matching activity. No manual `refs.json` reading needed. See `generation.md` § "Wiring Object Repository References" for the manual approach if needed.
- [ ] Phase 3: Generate sub-workflows ONE AT A TIME, Main.xaml LAST. For EACH file:
        ⛔ **SEQUENTIAL ONLY — NEVER generate multiple .xaml files in parallel.** Each file depends on the previous (argument names, variable types, UiElement reference chain). Parallel generation = guaranteed mismatches.
        ⛔ **SPEC FILES ONLY** — Rule G-2 in `rules.md`. Write spec → disk → run generator. Never inline in Agent prompts.
        a) Write a JSON spec → `python3 scripts/generate_workflow.py spec.json output.xaml --project-dir <project>`. Rules G-1, I-3 — never hand-write XAML, never guess selectors.
        b) **Validate immediately:** `python3 scripts/validate_xaml path/to/file.xaml --lint` — **fix all errors before the next file.**
        ⛔ When copying from golden templates: do NOT rename/fix namespaces. `UIAutomationNext` is CORRECT — see CRASH PREVENTION
- [ ] Phase 3b: **Wire UiElement chain** — for EACH app with UI: `python3 scripts/modify_framework.py wire-uielement <project_dir> <AppName>` (e.g., `WebApp`, `SHA1Online`). This adds typed arguments across InitAllApplications → Main → Process → CloseAllApplications. Run BEFORE Phase 4.
        ⛔ **Framework namespace rule:** Framework files already declare `xmlns:sd="...System.Data.Common"`. When inserting DataTable references into framework files (GetTransactionData, Process), use `sd:DataTable` — NEVER add `xmlns:sd2`. All DataTable references across the entire project use `sd:DataTable`. The `sd2` prefix does not exist in generate_workflow.py output.
- [ ] Phase 3c (Dispatcher only): **Wire GetTransactionData.xaml body** — replace SCAFFOLD.DISPATCHER_GET_ITEM marker.
        ⛔ Rule G-3 — generate snippet first, then wire. `modify_framework.py` rejects hallucinated patterns.
        ⛔ The `<xaml_snippet>` argument must be **actual XAML content**, not a file path. Passing a path like `C:/path/to/snippet.json` inserts it as text → Studio crash: *"Collection does not support text content"*.
        1. Create JSON spec → `generate_workflow.py spec.json /tmp/gtd_body.xaml`
        2. Extract inner activities → pass to `modify_framework.py replace-marker <GTD_path> DISPATCHER_GET_ITEM '<generator_output>'`
- [ ] Phase 4: Wire Main.xaml — orchestration only, InvokeWorkflowFile calls, log bookends **(A-7)**. Then validate Main.xaml immediately.
        ⛔ Rule G-3 applies here too — all snippets from generator output.
- [ ] Phase 5: Final project-level validation — `python3 scripts/validate_xaml <project_folder> --lint` (catches cross-file issues: lint 50/60/61/63)
- [ ] Phase 6: Output required Config.xlsx keys **grouped by sheet** — run `validate_xaml --config-keys <project_folder>`. See `config-sample.md` for sheet placement decision flowchart.
```

**Key rules:** Sequential generation only — one file at a time, validate after each. Sub-workflows first, Main.xaml last. Every .xaml gets `LogMessage "[START/END] AppName_Action"` bookends. Copy from golden templates, never from scratch. Unique `IdRef` per activity.

## Key project.json Configuration Fields

### runtimeOptions
- `isAttended: false` — unattended robot (typical for REFramework)
- `isAttended: true` — attended robot
- `requiresUserInteraction: true` — needs UI interaction
- `isPausable: true` — can be paused from Orchestrator

### designOptions
- `outputType: "Process"` — standard process
- `outputType: "Library"` — reusable library
- `projectProfile: "Developement"` — note the typo, this is how Studio spells it

### expressionLanguage
- `"VisualBasic"` — VB.NET expressions (default, most common)
- `"CSharp"` — C# expressions
