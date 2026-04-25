# Lint Reference

Validation rules for `scripts/validate_xaml --lint`. Search by lint number to find the fix.

**Lint checks** (`--lint`) — 80 numbered lint rules (+ plugin lint rules), grouped by severity. When fixing a lint warning, find its number below for the fix reference.

**🔴 Studio crash (file won't open or activity crashes Studio on load):**

| Lint | What it catches | Fix reference |
|---|---|---|
| 17 | NExtractDataGeneric uses `DataTable=` attribute (doesn't exist) | Use `ExtractedData="[dt_variable]"`. The `x:TypeArguments="sd2:DataTable"` is the generic type param, NOT a property |
| 23 | `.TargetAnchorable>` child element (doesn't exist) | Use `.Target>` — the TYPE inside is TargetAnchorable, but the element name is always `.Target` |
| 28 | Invalid ElementType enum (DataGrid, ComboBox, InputBoxText) | Use `Table`, `DropDown`, `InputBox`. See `xaml-ui-automation.md` |
| 57 | `ReferencesForImplementation` with `x:String` TypeArguments | Use `AssemblyReference` type+elements |
| 73 | Hallucinated NExtractData types/properties | Use `ExtractedData=` (not `DataTable=` or `Result=`). See `gen_nextractdata()` |
| 76 | InvokeWorkflowFile argument type mismatch (BC30512 crash) | Match caller `x:TypeArguments` to target `x:Property Type=`. See `skill-guide.md` → UiElement arg rules |
| 87 | Wrong or missing xmlns prefix on DataTable/DataRow type reference | Use `sd:DataTable`, `sd:DataRow` — never bare `DataTable`/`DataRow`. Check which prefix maps to System.Data in the file's xmlns declarations. **Auto-fixable via `--fix`.** |
| 88 | Variable declaration errors in Sequence: (a) `<Sequence.Variables>` after children, (b) bare `<Variable>` without wrapper | Variables MUST be inside `<Sequence.Variables>`, placed before any child activities |

**🟡 Compile error / runtime failure / silent data loss:**

| Lint | What it catches | Fix reference |
|---|---|---|
| 7 | Throw uses fully-qualified BRE/SysEx instead of short form | Use `New BusinessRuleException("msg")` not `New UiPath.Core.Activities.BusinessRuleException(...)` |
| 20 | AddQueueItem.ItemInformation uses `<x:String>` child elements | Use `<InArgument>` child elements with proper key-value pairs |
| 30 | NSelectItem has `InteractionMode` (doesn't exist on NSelectItem) | Only NClick and NTypeInto support InteractionMode. Remove it |
| 31 | ContinueOnError on X-suffix activities (doesn't exist) | X-activities don't have ContinueOnError. Wrap in TryCatch instead |
| 32 | `Environment.SpecialFolder.Temp` (not a valid enum) | Use `Path.GetTempPath()` instead |
| 33 | InvokeCode contains SqlConnection/SqlCommand | Use DatabaseConnect + ExecuteQuery activities instead |
| 34 | InvokeCode captures screenshot via System.Drawing | Use TakeScreenshot + SaveImage activities instead |
| 35 | InvokeCode uses File.Delete | Use `<ui:DeleteFileX Path="[strPath]" />` instead |
| 40 | Wrong enum namespace (`UIAutomation.Enums` instead of `UIAutomationNext.Enums`) | `UIAutomationNext.Enums` is the correct CLR namespace |
| 50 | InvokeWorkflowFile passes argument key not declared in target's x:Members | Check for typos — Studio error: 'Property matching [key] not found' |
| 51 | `GetQueueItem` in dispatcher's GetTransactionData (type mismatch) | Replace with DataTable row indexing. Scaffold `--variant dispatcher` handles this |
| 53 | `InteractionMode` on activities that don't support it (NGetText, NCheckState, etc.) | Only NClick and NTypeInto have InteractionMode |
| 54 | `QueueName=` instead of `QueueType=` on AddQueueItem/GetQueueItem | Property is `QueueType` |
| 55 | Out/InOut arguments with empty bindings (`[]` or self-closing) → silent data loss | Must have `[variable]` binding |
| 56 | Argument direction tag doesn't match key prefix (`io_` ≠ OutArgument) → silent data loss | `io_` → InOutArgument, `out_` → OutArgument, `in_` → InArgument |
| 60 | InvokeWorkflowFile missing required io_/out_ arguments from target | Target declares these but caller doesn't pass them — output silently lost |
| 67 | Variables used in expressions but never declared | Add `<Variable>` or `<x:Property>` declaration |
| 70 | Invalid `EmptyFieldMode` enum on NTypeInto (Clear, Empty, Reset, …) | Only `None`, `SingleLine`, `MultiLine` are valid. **Auto-fixable via `--fix`** (maps common hallucinations to `SingleLine`). |
| 71 | Double-escaped quotes `&amp;quot;` in VB.NET expressions | Use `""` not `&amp;quot;` inside `[brackets]`. **Auto-fixable via `--fix`.** |
| 81 | Undeclared variable bound in InvokeWorkflowFile Out/InOut argument in Main.xaml | Declare the variable in Main.xaml's Variables panel |
| 83 | Double-bracketed expression `[[...]]` | UiPath uses single brackets `[expr]`. **Auto-fixable via `--fix`.** |
| 89 | Selector inner attributes use double quotes (`tag=&quot;H1&quot;`) | UiPath selectors require single-quoted values (`tag='H1'`). **Auto-fixable via `--fix`.** |
| 90 | Selector contents double-XML-escaped (`&amp;lt;` instead of `&lt;`) | Selector engine sees literal `&lt;` and never matches a real element. **Auto-fixable via `--fix`.** |
| 93 | Invalid `x:Type[]` array reference (e.g. `x:String[]`) | The `x` xmlns is the XAML namespace, not System. Use the `s:` prefix (`s:String[]`, `s:Int32[]`, …). **Auto-fixable via `--fix`.** |
| 99 | Fully-qualified CLR type name inside `x:TypeArguments` (e.g. `System.Exception`) | XAML cannot resolve dotted FQ names in type-arg contexts. Use the xmlns-prefixed shortname (`s:Exception`, `x:String`, `sd:DataTable`, …). **Auto-fixable via `--fix`.** |

**🟢 Best practice / architecture / security:**

| Lint | What it catches | Fix reference |
|---|---|---|
| 26 | Persistence activities in sub-workflows *(uipath-tasks plugin)* | Move to Main.xaml — persistence bookmarks only work in entry-point |
| 27 | InvokeCode creates DataTable AND adds columns | Use Variable Default + AddDataColumn activities instead. Reserve InvokeCode for LINQ/GroupBy |
| 36 | API/network activities without RetryScope | Wrap in RetryScope (Rule 13). Exception: NetHttpRequest has built-in retry |
| 37 | Hardcoded URLs in NGoToUrl/NApplicationCard/NetHttpRequest | URLs from Config.xlsx (Rule 3) |
| 38 | Browser NApplicationCard missing `IsIncognito="True"` | Always set `IsIncognito="True"` (Rule 10) |
| 39 | Config.xlsx key extraction summary | Informational — lists all Config keys referenced |
| 41 | FuzzySelector as default search step | Default to `SearchSteps="Selector"` (strict) |
| 45 | App-specific navigation workflow exists | Delete it. Use generic `Browser_NavigateToUrl.xaml` from Utils/ (Rule 3) |
| 46 | Generic `uiBrowser`/`io_uiBrowser` in orchestrator file | Use app-specific names: `uiWebApp`, `io_uiWebApp` (Rule 11) |
| 47 | NApplicationCard with `OpenMode` ≠ `Never` in action workflow | Apps open in Launch only. Actions use `OpenMode="Never"` + attach (Rule 4) |
| 49 | Browser NApplicationCard with `CloseMode` set | Use `CloseMode="Never"` except in App_Close workflows |
| 58 | Modern UI activities outside NApplicationCard scope | Wrap in NApplicationCard |
| 59 | NApplicationCard attach-mode without `InUiElement` reference | Provide `InUiElement="[uiApp]"` for attach |
| 61 | Config.xlsx cross-reference (XAML keys vs actual sheets) | Add missing keys to Config.xlsx |
| 62 | Missing log bookends (START/END LogMessage) | Add `LogMessage "[START/END] WorkflowName"` (Rule 7) |
| 63 | InitAllApplications / CloseAllApplications asymmetry | Every app opened in Init must be closed in CloseAll |
| 64 | Login workflow missing Pick/PickBranch validation | Add `Pick` with success + failure branches. See `gen_pick_login_validation()` |
| 65 | CloseAllApplications contains KillProcess | Remove — KillProcess belongs in KillAllProcesses only |
| 66 | Launch workflow missing `OutUiElement` on NApplicationCard | Add `OutUiElement="[out_uiAppName]"` to capture opened instance |
| 68 | App_Close invoked from Process.xaml or action workflows | Move to CloseAllApplications only. Apps stay open across transactions |
| 69 | Launch workflow has login but no Pick validation | Add Pick with NCheckAppState success/failure branches after login click |
| 72 | Separate `AppName_Login.xaml` file | Merge login into `AppName_Launch.xaml` |
| 74 | InitAllApplications contains non-launch activities (navigation/extraction) | Move to GetTransactionData. Init = Launch + Login only |
| 75 | Redundant Process wrapper (Performer_Process.xaml delegating from Process.xaml) | Put business logic directly in Process.xaml |
| 77 | InitAllApplications missing UiElement OutArgument for launched apps | Add `out_uiXxx` OutArgument for each app. Wire through Main → Process → actions |
| 78 | UiElement stored in Config dictionary instead of typed argument chain | Use typed OutArgument/InOutArgument flow: Launch → InitAllApps → Main → Process → actions |
| 79 | Duplicate Arguments on InvokeWorkflowFile (XamlDuplicateMemberException) | Remove inline `Arguments="..."` attribute — use ONLY `<ui:InvokeWorkflowFile.Arguments>` child element |
| 80 | NSelectItem with `Item={x:Null}` — required field | Use variable `Item="[strStatus]"` or literal `Item="[&quot;Completed&quot;]"` |
| 82 | Bare `Config(...)` reference outside Main.xaml | Outside Main.xaml, use `in_Config("Key").ToString` |
| 94 | UI automation project missing/empty Object Repository | Write `selectors.json` during Playwright inspection, then run `python3 generate_object_repository.py --from-selectors selectors.json --project-dir <project>` |
| 95 | Wrong xmlns URL (e.g. `activities/next` instead of `activities/uix`) | Use `generate_workflow.py` — correct URLs built-in. Never hand-write namespace declarations |
| 97 | `css-selector=` attribute in selector (fragile) | `css-selector` is valid but CSS selectors break when page structure changes. Prefer `id=`, `aaname=`, or `parentid=` for reliable matching |
| 100 | `in_TransactionNumber` referenced in Process.xaml or action workflows | This argument lives in Main.xaml scope only, forwarded to GetTransactionData/SetTransactionStatus. Use `in_TransactionItem` fields instead (e.g., `in_TransactionItem("WIID").ToString` for DataRow, `in_TransactionItem.SpecificContent("Key").ToString` for QueueItem) |
| 101 | Circular dependency between workflows | Remove cycle — A invokes B invokes A is never valid |
| 102 | Orphaned workflow not reachable from entry point | Remove unused file or add InvokeWorkflowFile call from a reachable workflow |
| 103 | UI-heavy workflow (>5 interactions) without TryCatch | Wrap UI block in TryCatch for graceful error handling. See `desktop-form-filling.md` |
| 104 | Hardcoded user-specific path (`C:\Users\...`) in FilePath | Use variable from Config or InArgument: `FilePath="[in_Config(\"AppPath\").ToString]"` |
| 105 | Tab NClick immediately followed by NTypeInto without sync | Add 500ms Delay or NCheckAppState after tab click. See `desktop-form-filling.md` |
