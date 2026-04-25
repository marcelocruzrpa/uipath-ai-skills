# Activity routing index

Auto-generated from `references/annotations/*.json` by
`uipath-core/scripts/generate_routing_index.py`. Do not hand-edit — edit
the annotation entries instead, then regenerate.

**463 activities indexed** (supported: 445, wizard-only / unsupported: 18, routing wording review pending: 0).

## UI automation (69)

| Activity | Generator | Description | Use when |
|---|---|---|---|
| `Activate` | `gen_activate` | Bring an existing UI element's window to the foreground. | User wants to focus a window before interacting with it (classic activity). In modern projects prefer NApplicationCardAttach. |
| `CvExtractDataTableWithDescriptor` | `gen_cv_extract_data_table_with_descriptor` | Extract a tabular region from a Computer Vision capture using a saved descriptor. | User has a CV-anchored table descriptor and wants to scrape its rows. Must be inside CVScope. |
| `CvGetTextWithDescriptor` | `gen_cv_get_text_with_descriptor` | Read text from a Computer Vision target using a saved descriptor. | User wants to capture text from a CV-anchored region. Must be inside CVScope; for selector-based reads use NGetText. |
| `CvHighlightWithDescriptor` | `gen_cv_highlight_with_descriptor` | Briefly highlight a Computer Vision target using a saved descriptor (debug aid). | User wants to visually verify a CV anchor during development. Must be inside CVScope. |
| `CvHoverWithDescriptor` | `gen_cv_hover_with_descriptor` | Hover over a Computer Vision target using a saved descriptor. | User wants hover-only behaviour on a CV-anchored element. Must be inside CVScope. |
| `CVScope` | `gen_cv_scope` | Computer Vision scope that captures the screen once and serves child Cv* activities from the cached model. | User wants Computer Vision-based UI automation (OCR + CV anchors). All Cv* activities must run inside this scope. |
| `CvTypeIntoWithDescriptor` | `gen_cv_type_into_with_descriptor` | Type text into a Computer Vision target using a saved descriptor. | User wants to type into a CV-anchored field. Must be inside CVScope; for selector-based input use NTypeInto. |
| `FindChildren` | `gen_find_children` | Return all child UI elements of a parent that match a selector filter. | User wants to enumerate the children of a known container in classic UIA. In modern UIA prefer NFindElements / NForEachUiElement. |
| `GetActiveWindow` | `gen_get_active_window` | Return the UI element representing the currently focused foreground window. | User wants a handle to whatever window the user is currently looking at (classic activity). |
| `GetOCRText` | `gen_get_ocr_text` | Run OCR against a UI element or image region and return the recognised text. | User wants OCR text from a region without the modern engine wrappers. For modern OCR pick GoogleCloudOCR / GoogleOCR / MicrosoftAzureComputerVisionOCR. |
| `GoogleCloudOCR` | `GoogleCloudOCR` (data-driven) | OCR engine that calls Google Cloud Vision against the captured image region. | User wants OCR via Google Cloud and has an API key. For on-device OCR use GoogleOCR (Tesseract); for Azure use MicrosoftAzureComputerVisionOCR. |
| `GoogleOCR` | `GoogleOCR` (data-driven) | Tesseract-based on-device OCR engine (no cloud call). | User wants free, offline OCR. For higher accuracy on noisy images consider GoogleCloudOCR or MicrosoftAzureComputerVisionOCR. |
| `HideWindow` | `gen_hide_window` | Hide a UI element's window without closing it. | User wants to push a window off-screen but keep it running. To close use NWindowOperation with Close. |
| `LoadImage` | `gen_load_image` | Load an image file from disk into a UiPath.Core.Image variable for later CV/OCR use. | User wants to feed a saved screenshot into Computer Vision or OCR activities. To save instead use SaveImage. |
| `MicrosoftAzureComputerVisionOCR` | `MicrosoftAzureComputerVisionOCR` (data-driven) | OCR engine that calls Microsoft Azure Computer Vision against the captured image region. | User wants OCR via Azure Cognitive Services. For Google use GoogleCloudOCR; for offline use GoogleOCR. |
| `NApplicationCard` | `NApplicationCard` (data-driven) | Modern Use Application/Browser scope - opens or attaches to a target application or browser and runs nested activities against it. | User wants the modern Use Application/Browser container that nests all child UI activities under one target. For just opening without nesting use NApplicationCardOpen; for attaching use NApplicationCardAttach. |
| `NBlockUserInput` | `NBlockUserInput` (data-driven) | Block the user's mouse and keyboard input until a matching NUnblockUserInput runs. | User wants to prevent accidental human input during an automation. Always pair with NUnblockUserInput in a Try/Finally. |
| `NBrowserDialogScope` | `NBrowserDialogScope` (data-driven) | Pre-arm handling of a browser dialog (alert/confirm/prompt/beforeunload) that will appear inside the scope. | User wants to auto-accept/dismiss a JS dialog raised by activities inside the scope. For file pickers use NBrowserFilePickerScope. |
| `NBrowserFilePickerScope` | `NBrowserFilePickerScope` (data-driven) | Pre-arm a browser file-picker dialog so a triggered file chooser is fed a known file path. | User clicks a button inside the scope that opens a file-upload dialog. For JS alert/confirm dialogs use NBrowserDialogScope. |
| `NCheck` | `gen_ncheck` | Set a checkbox or radio button to a Check, Uncheck, or Toggle state. | User wants to set a checkbox/radio to a known state. For arbitrary clicks use NClick; for verifying current state without changing it use NCheckState. |
| `NCheckElement` | `NCheckElement` (data-driven) | Assert a property of a UI element (visible/enabled/text equals/contains) and return a Boolean result. | User wants to verify an element's property as a Boolean (e.g. for conditions or assertions). To set a checkbox use NCheck; to test presence only use NCheckState. |
| `NCheckState` | `gen_ncheckstate` | Inspect whether a UI element appears, disappears, or matches a state, returning the result without modifying the UI. | User wants to test the presence/state of an element as a Boolean. For deciding which branch runs use this together with If; to actively check a checkbox use NCheck. |
| `NClick` | `gen_nclick` | Click a UI element with configurable click type (Single/Double) and mouse button (Left/Right/Middle). | User wants a single left click on a button or element. For double-clicks prefer NDoubleClick; for right-clicks prefer NRightClick; for hold-and-drag use NDragAndDrop. |
| `NClickTrigger` | `NClickTrigger` (data-driven) | Trigger that fires when a configured UI element is clicked. | User wants an event-driven workflow that reacts to a click on a target UI element. For keyboard-event triggers use NKeyboardTrigger. |
| `NClosePopup` | `NClosePopup` (data-driven) | Close a transient popup window or notification by clicking its dismiss control. | User has a recurring popup blocking automation and wants it auto-dismissed. For ordinary windows use NWindowOperation. |
| `NDoubleClick` | `gen_ndoubleclick` | Double-click a UI element with the chosen mouse button. | User explicitly wants a double click. For single click use NClick; for right click use NRightClick. |
| `NDragAndDrop` | `NDragAndDrop` (data-driven) | Drag a UI element from a source location to a target location with the mouse held down. | User wants drag-and-drop semantics (reordering, moving items). For ordinary clicks use NClick. |
| `NElementScope` | `NElementScope` (data-driven) | Scope that pins a UI element as the parent target for nested activities, avoiding repeated selectors. | User runs several activities against the same element and wants to share its selector once. For application-level scoping use NApplicationCard. |
| `NFillForm` | `NFillForm` (data-driven) | Fill multiple form fields in a single call using an AI-powered field mapping. | User wants to populate several inputs at once given a dictionary of field-name to value. For one field at a time use NTypeInto. |
| `NFindElements` | `NFindElements` (data-driven) | Find all UI elements that match a selector and return them as a collection. | User wants to enumerate all matching elements (e.g. all rows or links). For a single element rely on the implicit find of NClick/NGetText; to iterate use NForEachUiElement. |
| `NForEachUiElement` | `NForEachUiElement` (data-driven) | Iterate over each UI element matching a selector and run a body sequence against it. | User wants to act on every element that matches (each row, each link). For non-UI collections use ForEach; to merely collect them use NFindElements. |
| `NGetBrowserData` | `NGetBrowserData` (data-driven) | Read structured data (tables, lists, attributes) from a browser DOM into a typed output. | User wants to scrape structured data out of a web page in modern UI Automation. For visible plain text use NGetText. |
| `NGetClipboard` | `NGetClipboard` (data-driven) | Read the current contents of the system clipboard into a string variable. | User wants to capture what was just copied. To set the clipboard use NSetClipboard. |
| `NGetText` | `gen_ngettext` | Read the visible text of a UI element into an output variable. | User wants to capture the text shown on screen for an element. For OCR-only surfaces use GetOCRText; for clipboard use NGetClipboard; for browser DOM data use NGetBrowserData. |
| `NHighlight` | `NHighlight` (data-driven) | Briefly draw a coloured outline around a UI element for debugging or demos. | User wants to visually highlight an element (debugging, screen recordings). Has no functional effect on the target. |
| `NHover` | `gen_nhover` | Hover the mouse over a UI element to trigger hover-only behaviours (tooltips, menus). | User wants to surface hover-triggered UI (tooltips, fly-out menus) without clicking. For clicking use NClick. |
| `NInjectJsScript` | `NInjectJsScript` (data-driven) | Execute a JavaScript snippet in the context of the active browser tab. | User wants to run custom JS against the page (set values, read DOM, fire events) when a UI activity is insufficient. For ordinary form fills use NTypeInto / NFillForm. |
| `NKeyboardShortcuts` | `gen_nkeyboardshortcuts` | Send a keyboard shortcut chord (modifier keys + key) to a UI element. | User wants to invoke a keyboard shortcut (Ctrl+S, Alt+F4, etc.) on the target element. For typing literal text use NTypeInto. |
| `NKeyboardTrigger` | `NKeyboardTrigger` (data-driven) | Trigger that fires when a configured keyboard shortcut is pressed. | User wants an event-driven workflow that reacts to a hotkey. For mouse-click triggers use NClickTrigger. |
| `NMouseScroll` | `gen_nmousescroll` | Scroll the mouse wheel on a UI element by a number of clicks in a given direction. | User wants to scroll a page or panel via mouse wheel. For keyboard-driven scrolling use NKeyboardShortcuts (PageDown / End). |
| `NNavigateBrowser` | `NNavigateBrowser` (data-driven) | Navigate the active browser to a URL or perform Back/Forward/Refresh/Home/Close commands. | User wants the current browser to change page or perform a navigation command. To open a brand-new browser use NApplicationCardOpen with a URL. |
| `NRightClick` | `gen_nrightclick` | Right-click a UI element to invoke its context menu. | User wants to open a context menu. For ordinary clicks use NClick; for double-clicks use NDoubleClick. |
| `NSAPCallTransaction` | `NSAPCallTransaction` (data-driven) | Invoke an SAP transaction code in the active SAP GUI session. | User wants to jump SAP to a transaction (e.g. /nVA01). Pair with NSAPLogin/NSAPLogon for session setup. |
| `NSAPClickPictureOnScreen` | `NSAPClickPictureOnScreen` (data-driven) | Click a picture/icon element rendered on screen by SAP GUI. | User has an SAP picture target that NClick cannot resolve. For ordinary controls prefer NClick. |
| `NSAPClickToolbarButton` | `NSAPClickToolbarButton` (data-driven) | Click a button on the SAP GUI toolbar by its accessible identifier. | User wants to invoke a toolbar action in SAP GUI by ID rather than by selector. For arbitrary clicks use NClick. |
| `NSAPExpandALVHierarchicalTable` | `NSAPExpandALVHierarchicalTable` (data-driven) | Expand all nodes of an SAP ALV hierarchical table for full-data scraping. | User wants to read every row of a collapsed SAP ALV hierarchical grid. For tree controls use NSAPExpandALVTree or NSAPExpandTree. |
| `NSAPExpandALVTree` | `NSAPExpandALVTree` (data-driven) | Expand all nodes in an SAP ALV tree control. | User wants every branch of an SAP ALV tree opened. For non-ALV trees use NSAPExpandTree. |
| `NSAPExpandTree` | `NSAPExpandTree` (data-driven) | Expand every node in an SAP GUI tree control. | User wants every branch of a generic SAP tree opened. For ALV trees use NSAPExpandALVTree. |
| `NSAPLogin` | `NSAPLogin` (data-driven) | Log in to an SAP system through the SAP GUI login screen. | User wants automated login against the SAP GUI logon screen. For session selection from SAP Logon Pad use NSAPLogon. |
| `NSAPLogon` | `NSAPLogon` (data-driven) | Open a session from the SAP Logon Pad by its connection name. | User wants to start an SAP session from SAP Logon by connection name. To enter credentials on the SAP login screen itself use NSAPLogin. |
| `NSAPReadStatusbar` | `NSAPReadStatusbar` (data-driven) | Read the SAP GUI status bar message (text and severity) into output variables. | User needs to capture the status-bar feedback after an SAP transaction (success/warning/error message). |
| `NSAPSelectDatesInCalendar` | `NSAPSelectDatesInCalendar` (data-driven) | Select a date range in the SAP GUI calendar control. | User wants to choose dates in an SAP calendar widget. For ordinary dropdowns use NSelectItem. |
| `NSAPSelectMenuItem` | `NSAPSelectMenuItem` (data-driven) | Select a menu entry from the SAP GUI menu bar by its menu path. | User wants to invoke a menu-bar action in SAP GUI by path. For toolbar buttons use NSAPClickToolbarButton. |
| `NSAPTableCellScope` | `NSAPTableCellScope` (data-driven) | Scope that pins an SAP table cell as the target for nested activities. | User wants to perform several actions against the same SAP table cell without repeating the row/column index. |
| `NSelectItem` | `gen_nselectitem` | Select an item from a combobox/dropdown by visible text. | User wants to pick a value from a dropdown/combobox. For multi-select lists use SelectMultipleItems; for typing into the field use NTypeInto. |
| `NSetBrowserData` | `NSetBrowserData` (data-driven) | Write a structured value (table/list/attribute) back into a browser DOM target. | User wants to push structured data into the page model. To read use NGetBrowserData. |
| `NSetClipboard` | `NSetClipboard` (data-driven) | Set the system clipboard contents to a given string. | User wants to seed the clipboard before a paste-style action. To read what is on the clipboard use NGetClipboard. |
| `NSetFocus` | `NSetFocus` (data-driven) | Move keyboard focus to a UI element without clicking it. | User wants the next typed input to land on a specific element without firing a click. For classic activities use SetFocus. |
| `NSetRuntimeBrowser` | `NSetRuntimeBrowser` (data-driven) | Switch the runtime browser used by subsequent UI Automation activities (Chrome, Edge, Firefox). | User wants to override the browser used by the current run (e.g. to force Edge for a specific flow). |
| `NSetText` | `NSetText` (data-driven) | Set the value of a text field directly (paste-style), bypassing per-character typing. | User wants to fill a long string into a field without keystroke simulation (faster, no IME issues). For per-character typing use NTypeInto. |
| `NTakeScreenshot` | `NTakeScreenshot` (data-driven) | Capture a screenshot of the target UI element or full screen and store it in a variable. | User wants to save a screen capture to disk or memory mid-run. For composite take-and-save flows consider gen_take_screenshot_and_save. |
| `NTypeInto` | `gen_ntypeinto` | Type a string into a UI element by simulating keystrokes, with optional secure-text masking and empty-field handling. | User wants to fill a single text input by typing characters one at a time. For checkboxes use NCheck; for dropdowns use NSelectItem; for clipboard-paste fills use NSetText. |
| `NUITask` | `NUITask` (data-driven) | Run a high-level UI task described in natural language using AI to choose actions (UITasksWithAI). | User wants AI to plan and execute a multi-step UI flow from a textual instruction. For deterministic single steps use the explicit modern verbs (NClick / NTypeInto). |
| `NUnblockUserInput` | `NUnblockUserInput` (data-driven) | Re-enable user mouse and keyboard input previously blocked by NBlockUserInput. | User wants to release input after an NBlockUserInput. Always run in a Finally to avoid stranding the user. |
| `NWindowOperation` | `NWindowOperation` (data-driven) | Apply a window operation (Maximize, Minimize, Restore, Close, Move, Resize) to a UI element's window. | User wants to manipulate a window's state. For just hiding use HideWindow; for popups use NClosePopup. |
| `SaveImage` | `gen_save_image` | Save a UiPath.Core.Image variable to disk as a PNG/JPG file. | User wants to persist a captured screenshot or CV image to disk. For the inverse use LoadImage; to capture in one step consider gen_take_screenshot_and_save. |
| `SelectMultipleItems` | `gen_select_multiple_items` | Select multiple items from a list-box or multi-select dropdown by visible text. | User wants to pick several values from a multi-select control. For single-value picks use NSelectItem. |
| `SetFocus` | `gen_set_focus` | Move keyboard focus to a UI element (classic activity) without clicking. | User wants to focus an element in classic UIA. In modern projects prefer NSetFocus. |
| `SetWebAttribute` | `gen_set_web_attribute` | Set the value of a named DOM attribute on a web UI element. | User wants to write directly to a DOM attribute (value, style) bypassing user-style interactions. For ordinary form fills use NTypeInto / NSetText. |

## Application & browser cards (4)

| Activity | Generator | Description | Use when |
|---|---|---|---|
| `NApplicationCardAttach` | `gen_napplicationcard_attach` | Attach the body to an already-running browser or desktop application via an existing UiElement. | The browser or app is already open (or was opened earlier in the workflow) and you want a scope around it without re-launching. Use NApplicationCardOpen when you must launch a browser URL, NApplicationCardDesktopOpen when launching a deskt… |
| `NApplicationCardClose` | `gen_napplicationcard_close` | Close the browser or app the body was scoped to once execution exits the card. | You explicitly want to shut down the browser or app at the end of an Open / Attach scope rather than leaving it running. Use NApplicationCardOpen / NApplicationCardAttach when you only need to enter a scope, not close one. |
| `NApplicationCardDesktopOpen` | `gen_napplicationcard_desktop_open` | Launch a Windows desktop executable (by file path) inside a UI scope and run the body against it. | The target is a desktop .exe that must be started before any UI step. Use NApplicationCardOpen for a browser URL instead, NApplicationCardAttach when the desktop app is already running. |
| `NApplicationCardOpen` | `gen_napplicationcard_open` | Open a browser to a URL inside a UI scope and run the body against that browser instance. | The workflow needs to launch (or re-launch) a browser at a known URL before any UI step. Use NApplicationCardAttach instead when the browser is already open, NApplicationCardDesktopOpen when launching a Windows .exe rather than a URL. |

## Navigation (4)

| Activity | Generator | Description | Use when |
|---|---|---|---|
| `NExtractDataGeneric` | `gen_nextractdata` | Wizard-only Extract Data Generic activity that emits a typed DataTable from a Studio-authored extraction definition. | Do not auto-generate; direct user to Studio's Extract Data Wizard (Modern UI Automation ribbon) to build the table definition interactively. |
| `NGetUrl` | `gen_ngeturl` | Reads the current URL of the active browser tab and assigns it to a variable. | User wants to capture the page URL for logging or routing decisions; to navigate to a URL use NGoToUrl. |
| `NGoToUrl` | `gen_ngotourl` | Navigates the active browser to the given URL within an NApplicationCard browser scope. | User wants to change the active page inside an already-open browser; for opening a new browser use NApplicationCard; to read the current URL use NGetUrl. |
| `PickLoginValidation` | `gen_pick_login_validation` | Pick activity with two branches that races a success selector against an error selector to detect login outcome. | User wants to validate that a form submission succeeded vs surfaced a visible error message; for general n-way racing use Pick directly; for sequential retry use RetryScope. |

## Control flow (13)

| Activity | Generator | Description | Use when |
|---|---|---|---|
| `Delay` | `Delay` (data-driven) | Pause workflow execution for a TimeSpan duration before continuing. | User explicitly asks for a fixed pause/sleep. Avoid in production loops (lint 109 flags it) - prefer ShouldStop checks or a retry-with-backoff pattern. |
| `DoWhile` | `gen_do_while` | Run a body sequence at least once, then repeat while a Boolean condition stays true. | User wants a post-test loop that always executes at least one pass. For zero-or-more iterations use While; for cancel-aware loops use InterruptibleDoWhile. |
| `Flowchart` | `gen_flowchart` | Author a flowchart container with FlowSteps, FlowDecisions, branching connectors, and a designated start node. | User wants an explicit graph-style workflow with multiple entry/exit paths and back-edges. For straight-line work use Sequence; for state-driven graphs use StateMachine. |
| `ForEach` | `gen_foreach` | Iterate over an in-memory collection (IEnumerable) running the body once per item with a typed loop variable. | User wants to loop over a list/array/IEnumerable. For DataTable rows use ForEachRow; for files in a folder use ForEachFileX; for parallel iteration use ParallelForEach. |
| `ForEachFileX` | `gen_foreach_file` | Iterate over files in a folder (StudioX FileInfo iterator) with optional recursion and ordering. | User wants to process every file in a directory. For folders use ForEachFolderX (data ops); for arbitrary collections use ForEach. |
| `ForEachRow` | `gen_foreach_row` | Iterate over the rows of a DataTable, exposing each row as a DataRow loop variable. | User wants to walk every row of a DataTable. For arbitrary collections use ForEach; for files use ForEachFileX. |
| `If` | `gen_if` | Branch execution based on a single Boolean condition with a Then branch and an optional Else branch. | User needs a binary decision on a Boolean expression. For three or more mutually-exclusive cases use IfElseIfV2 or Switch; for value-based dispatch use Switch. |
| `IfElseIfV2` | `gen_if_else_if` | Chain multiple Boolean conditions evaluated in order, with a Then branch per condition and an optional final Else. | User has three or more mutually-exclusive conditional branches keyed on Boolean expressions. For exactly two outcomes use If; for value-equality dispatch use Switch. |
| `Parallel` | `gen_parallel` | Run two or more branches concurrently, with an optional CompletionCondition that ends the activity once truthy. | User wants to fan out N independent pre-built branches and join them. For parallel iteration over a collection use ParallelForEach. |
| `ParallelForEach` | `gen_parallel_foreach` | Iterate over a collection in parallel, running the body concurrently for each item. | User wants concurrent iteration over a collection. For sequential iteration use ForEach; for fan-out of distinct branches use Parallel. |
| `StateMachine` | `gen_state_machine` | Author a state-machine container with named states, transitions, entry actions, and a designated initial state. | User wants explicit named states with guarded transitions (e.g. REFramework). For free-form graphs use Flowchart; for linear control flow use Sequence. |
| `Switch` | `gen_switch` | Dispatch on the value of an expression to one of N labelled case sequences plus an optional default. | User wants to choose a branch by the value of a single expression (string, integer, enum). For Boolean conditions use If or IfElseIfV2. |
| `While` | `gen_while` | Repeat a body sequence while a Boolean condition stays true, evaluating the condition before each iteration. | User wants a pre-test loop that may run zero times. For at-least-once execution use DoWhile; for cancel-aware loops use InterruptibleWhile. |

## Data tables & collections (128)

| Activity | Generator | Description | Use when |
|---|---|---|---|
| `AddDataColumn` | `gen_add_data_column` | Adds a new typed column to an existing DataTable. | User wants to extend a DataTable's schema after construction; the cleaner pattern is to declare all columns in BuildDataTable upfront. |
| `AddDataRow` | `gen_add_data_row` | Appends a new row to a DataTable, taking values either as an array (positional) or a DataRow object. | User wants to add one row to a DataTable; for many rows from another DataTable use MergeDataTable. |
| `AddOrSubtractFromDate` | `gen_add_or_subtract_from_date` | Returns a DateTime offset by N seconds/minutes/hours/days/months/years from an input date. | User wants date arithmetic; for formatting a date use FormatDateAsText; for parsing a string into DateTime use ExtractDateTime. |
| `AddTransactionItem` | `gen_add_transaction_item` | Adds a new transaction item to an Orchestrator queue inside a long-running job context. | User wants to enqueue mid-process; for dispatcher-style bulk loading use BulkAddQueueItems. |
| `AppendLine` | `gen_append_line` | Appends a line of text to an existing text file, creating it if missing. | User wants incremental log/audit writes; for one-shot text writes use Write Text File. |
| `Assign` | `gen_assign` | Assigns the result of a single VB expression to a single variable / argument. | User wants to set one value; for multiple assignments in one block use MultipleAssign; for declaring new variables in scope use VariablesBlock. |
| `Beep` | `gen_beep` | Plays a system beep at a given frequency and duration. | User wants an audible cue (developer/test only); avoid in unattended automations. |
| `BeginProcess` | `gen_begin_process` | Marks the start of a logical process for tracking and analytics in Insights / Process Mining. | User wants to time a logical process span; pair with the corresponding end-of-process tracking. |
| `BuildDataTable` | `gen_build_data_table` | Constructs a typed DataTable from a column schema and optional initial rows. | User wants an empty/seeded DataTable to fill via AddDataRow or to pass to ForEachRow; for reading a CSV/Excel into a DataTable use ReadCsvFile / ReadRange. |
| `ChangeCase` | `gen_change_case` | Returns a string converted to upper, lower, or title case. | User wants a case transformation; for find/replace use Replace; for trim/split use ModifyText. |
| `CheckFalse` | `gen_check_false` | Asserts that a condition is False, throwing on True. | User wants an inline negative assertion; for truthy assertion use CheckTrue; in tests prefer the Verify* family. |
| `CheckTrue` | `gen_check_true` | Asserts that a condition is True, throwing on False. | User wants an inline positive assertion; for negative assertion use CheckFalse; in tests prefer the Verify* family. |
| `ClearDataTable` | `gen_clear_data_table` | Removes all rows from a DataTable while preserving its column schema. | User wants to reset a DataTable for reuse; to drop the schema entirely just rebuild with BuildDataTable. |
| `CombineText` | `gen_combine_text` | Concatenates multiple strings with an optional separator. | User wants to join strings (String.Join equivalent in activity form); for in-place expression use VB's String.Join. |
| `CompressFiles` | `gen_compress_files` | Compresses one or more files / folders into a ZIP archive. | User wants to bundle artifacts for upload or email; for extraction use ExtractFiles. |
| `CopyFolderX` | `gen_copy_folder_x` | Copies a folder (recursive) from source to destination, optionally overwriting. | User wants to duplicate a folder tree; for a single file use Copy File; for moving (not copying) use MoveFolderX. |
| `CreateFile` | `gen_create_file` | Creates an empty file at the given path. | User wants a placeholder file; to write content use Write Text File or AppendLine. |
| `CustomInput` | `gen_custom_input` | Displays a custom HTML form dialog and captures the user's response. | User wants a richer prompt than InputDialog; for simple text input use InputDialog. |
| `Delete` | `gen_delete` | Deletes a file or folder at the given path. | User wants to remove a filesystem entry; for ZIP-and-delete patterns use CompressFiles then Delete. |
| `DeleteFolderX` | `gen_delete_folder_x` | Deletes a folder (recursive). | User wants to remove a directory tree; for single files use Delete. |
| `DeleteQueueItems` | `gen_delete_queue_items` | Deletes queue items from an Orchestrator queue by ID list or filter. | User wants to purge stale or successful items; pair with GetQueueItems to enumerate first. |
| `DeleteStorageFile` | `gen_delete_storage_file` | Deletes a file from an Orchestrator Storage Bucket. | User wants to remove a bucket-stored file; pair with ListStorageFiles to enumerate first. |
| `DisableTrigger` | `gen_disable_trigger` | Disables an Orchestrator trigger by name. | User wants to pause scheduled or queue-driven triggers temporarily; re-enable with EnableTrigger. |
| `DownloadFileFromUrl` | `gen_download_file_from_url` | Downloads a file from an HTTP(S) URL to a local path. | User wants a file fetched by URL; for authenticated APIs use NetHttpRequest with response-to-file. |
| `DownloadStorageFile` | `gen_download_storage_file` | Downloads a file from an Orchestrator Storage Bucket to a local path. | User wants a bucket-stored file locally; pair with UploadStorageFile for the inverse. |
| `EnableTrigger` | `gen_enable_trigger` | Enables a previously disabled Orchestrator trigger by name. | User wants to resume a paused trigger; pair with DisableTrigger. |
| `EvaluateBusinessRule` | `gen_evaluate_business_rule` | Evaluates a Business Rule from the Rules Catalog and returns its outcome / actions. | User wants to delegate decisioning to a centrally-managed rule; for inline VB conditions use If. |
| `ExecutePowerShell` | `gen_execute_power_shell` | Runs a PowerShell script and captures its output. | User wants to invoke Windows-side admin tasks; prefer dedicated activities (filesystem/registry) when one exists. |
| `ExtractDateTime` | `gen_extract_date_time` | Parses a string into a DateTime using a culture-aware format pattern. | User wants to convert a string to DateTime; for the inverse use FormatDateAsText. |
| `ExtractFiles` | `gen_extract_files` | Extracts the contents of a ZIP archive to a target folder. | User wants to unpack a ZIP; for compression use CompressFiles. |
| `ExtractText` | `gen_extract_text` | Extracts a substring from a source string by regex or position. | User wants a piece of a larger string; for find/replace use Replace; for splitting use SplitText. |
| `FileChangeTrigger` | `gen_file_change_trigger` | Trigger that fires when a watched file is created/modified/deleted. | User wants to react to filesystem changes; v3 (FileChangeTriggerV3) is the latest stable. |
| `FileChangeTriggerV2` | `gen_file_change_trigger_v2` | v2 of FileChangeTrigger — superseded by FileChangeTriggerV3 in modern projects. | User has a legacy spec referencing v2; new specs should use FileChangeTriggerV3. |
| `FileChangeTriggerV3` | `gen_file_change_trigger_v3` | v3 of FileChangeTrigger — current stable file-watch trigger with extended event types. | User wants to react to filesystem changes in a modern project; v1/v2 remain for backwards compatibility only. |
| `FileExistsX` | `gen_file_exists_x` | Returns True if a file exists at the given path. | User wants a simple existence check; for folders use FolderExistsX. |
| `FilterDataTable` | `gen_filter_data_table` | Filters a DataTable in place using a list of column / operator / value rules. | User wants to keep or remove rows by column criteria; for joins across tables use JoinDataTables; for a single-row lookup use LookupDataTable. |
| `FindAndReplace` | `gen_find_and_replace` | Finds and replaces text in a file in place, optionally using regex. | User wants to mutate file contents; for in-memory string replacement use Replace. |
| `FolderExistsX` | `gen_folder_exists_x` | Returns True if a folder exists at the given path. | User wants a simple folder existence check; for files use FileExistsX. |
| `ForEachFolderX` | `gen_for_each_folder_x` | Iterates over folders matching a pattern under a root directory. | User wants to walk a directory tree of folders; for files use ForEachFileX; for in-memory collections use ForEach. |
| `FormatDateAsText` | `gen_format_date_as_text` | Formats a DateTime as a string using a culture-aware format pattern. | User wants a stringified date; for parsing the inverse use ExtractDateTime. |
| `FormatValue` | `gen_format_value` | Formats a numeric value using a format pattern (currency, decimal, percent). | User wants a stringified number with explicit formatting; VB's String.Format suffices in expressions. |
| `GenerateDataTable` | `gen_generate_data_table` | Builds a DataTable by parsing a delimited string (e.g. raw text scraped from a UI element). | User has captured tabular text from screen scraping and wants a typed DataTable; for proper CSV files use ReadCsvFile; for Excel use ReadRange. |
| `GetCurrentJobInfo` | `gen_get_current_job_info` | Returns Orchestrator metadata about the currently-running job (id, robot, folder). | User wants to read job-context properties for logging or correlation. |
| `GetEnvironmentFolder` | `gen_get_environment_folder` | Returns the path of a Windows special folder (Desktop, MyDocuments, etc.). | User wants to write to a known user folder; for an environment variable use GetEnvironmentVariable. |
| `GetEnvironmentVariable` | `gen_get_environment_variable` | Returns the value of a process-, user-, or machine-scoped environment variable. | User wants to read a configured env var; for setting use SetEnvironmentVariable. |
| `GetFileInfoX` | `gen_get_file_info_x` | Returns metadata (size, created, modified) for a file as a FileInfo object. | User wants file metadata for routing decisions; for folder metadata use GetFolderInfoX. |
| `GetFolderInfoX` | `gen_get_folder_info_x` | Returns metadata (size, created, modified) for a folder as a DirectoryInfo object. | User wants folder metadata; for file metadata use GetFileInfoX. |
| `GetJobs` | `gen_get_jobs` | Queries Orchestrator for jobs matching given filters. | User wants to enumerate or correlate Orchestrator jobs; for the current job only use GetCurrentJobInfo. |
| `GetLastDownloadedFile` | `gen_get_last_downloaded_file` | Returns the path of the most recently downloaded file from the active browser context. | User wants to capture a download triggered by a browser interaction; pair with NClick on the download link. |
| `GetProcesses` | `gen_get_processes` | Returns a list of currently-running Windows processes. | User wants to enumerate processes for diagnostics or detect a running app; to terminate one use KillProcess. |
| `GetQueueItems` | `gen_get_queue_items` | Queries Orchestrator for queue items matching given filters (status, reference, dates). | User wants to inspect or audit queue contents; for popping the next work item use GetQueueItem. |
| `GetRowItem` | `gen_get_row_item` | Reads a single column value from a DataRow by column name or index. | User wants a typed cell value from a DataRow; usually the inline expression `row("Col")` is more idiomatic. |
| `GetSecret` | `gen_get_secret` | Reads a secret value from a configured secret store (Orchestrator credentials, vault, etc.). | User wants a secret without storing it in code or config; for credential pairs use GetRobotCredential. |
| `GetTransactionItem` | `gen_get_transaction_item` | Pops the next transaction from a queue, mirroring REFramework's Get Transaction Data step. | User is hand-authoring a Performer; in REFramework this is wired automatically. |
| `GetUsernamePasswordX` | `gen_get_username_password_x` | Reads a username/password pair from a Windows Credential Manager entry by name. | User wants OS-level credentials; for Orchestrator-managed credentials use GetRobotCredential. |
| `GlobalVariableChangedTrigger` | `gen_global_variable_changed_trigger` | Trigger that fires when a workflow Global Variable's value changes. | User wants reactive flow on global state mutations; pair with NotifyGlobalVariableChanged from the producer side. |
| `InterruptibleDoWhile` | `gen_interruptible_do_while` | DoWhile loop that yields to interrupts (Stop, signals) at safe checkpoints between iterations. | User wants long-running iteration that honors cooperative cancellation; for non-interruptible loops use DoWhile. |
| `InterruptibleWhile` | `gen_interruptible_while` | While loop that yields to interrupts at safe checkpoints between iterations. | User wants long-running iteration with cooperative cancellation; for non-interruptible loops use While. |
| `InvokeComMethod` | `gen_invoke_com_method` | Invokes a COM method on a registered COM object (e.g. Office automation). | User wants to call COM-based APIs; for VB.NET methods use InvokeMethod; for inline code use InvokeCode. |
| `InvokeProcess` | `gen_invoke_process` | Launches an external Windows process and optionally waits for its exit / captures stdout. | User wants to run a CLI tool or executable; for PowerShell scripts use ExecutePowerShell. |
| `InvokeVBScript` | `gen_invoke_vb_script` | Runs a VBScript file with optional arguments and captures its output. | User has a legacy .vbs script to call; for new scripting prefer ExecutePowerShell or InvokeCode. |
| `InvokeWorkflowInteractive` | `gen_invoke_workflow_interactive` | Invokes a subworkflow in an interactive session (Picture-in-Picture / unattended elevation). | User wants to run a child workflow with elevated UI access; for standard subworkflow calls use InvokeWorkflowFile. |
| `IsMatch` | `gen_is_match` | Returns True if a string matches a regex pattern. | User wants a boolean regex check; for capturing matches use Matches; VB's Regex.IsMatch suffices in expressions. |
| `JoinDataTables` | `gen_join_data_tables` | Joins two DataTables on equality of specified columns (Inner / Left / Full join). | User wants relational-style joins between two tables; for filtering one table by criteria from another, FilterDataTable in a loop is simpler when one side is small. |
| `ListStorageFiles` | `gen_list_storage_files` | Lists files in an Orchestrator Storage Bucket, optionally filtered by prefix. | User wants to enumerate bucket contents; pair with DownloadStorageFile / DeleteStorageFile. |
| `LookupDataTable` | `gen_lookup_data_table` | Looks up a single matching row in a DataTable by a key column value. | User wants one row by key (Excel VLOOKUP-equivalent); for many matching rows use FilterDataTable. |
| `ManualTrigger` | `gen_manual_trigger` | Trigger that fires when invoked manually (debug / dev-time only). | User wants a hand-fired trigger for testing; production should use FileChange/Time/Queue triggers. |
| `Matches` | `gen_matches` | Returns the list of regex matches against a string. | User wants captured matches; for a boolean check use IsMatch; VB's Regex.Matches suffices in expressions. |
| `MergeDataTable` | `gen_merge_data_table` | Merges rows from a source DataTable into a destination DataTable, preserving the destination schema. | User wants to append rows from another table with matching schema; for a single row use AddDataRow. |
| `ModifyDate` | `gen_modify_date` | Returns a DateTime with selected components replaced (year, month, day, hour, etc.). | User wants component-level date editing; for offset-based shifts use AddOrSubtractFromDate. |
| `ModifyText` | `gen_modify_text` | Applies a sequence of text transformations (trim, replace, case, encode) in one activity. | User wants several string transforms in one step; for a single transform pick the specific activity (Replace, ChangeCase, etc.). |
| `MoveFolderX` | `gen_move_folder_x` | Moves a folder (recursive) from source to destination. | User wants to relocate a folder; for non-destructive copy use CopyFolderX. |
| `MultipleAssign` | `gen_multiple_assign` | Assigns a list of (target, expression) pairs in one activity, evaluated top-to-bottom. | User wants to set several variables together (e.g. zeroing counters at start of a loop); for a single assignment use Assign. |
| `NotifyGlobalVariableChanged` | `gen_notify_global_variable_changed` | Signals to subscribers that a Global Variable's value changed. | User wants to manually fire a change notification; pair with GlobalVariableChangedTrigger on the consumer side. |
| `OrchestratorHttpRequest` | `gen_orchestrator_http_request` | Performs an authenticated HTTP request against the Orchestrator API. | User wants Orchestrator API calls without managing auth headers; for arbitrary REST APIs use NetHttpRequest. |
| `OutputDataTable` | `gen_output_data_table` | Renders a DataTable as a formatted string (CSV-like) for logging or display. | User wants a human-readable preview of a DataTable; for persisting to disk use WriteCsvFile. |
| `Placeholder` | `gen_placeholder` | Empty placeholder activity used as a generator stub during scaffolding. | User wants to mark a TODO spot in a workflow; should be replaced with the real activity before publish. |
| `PostponeTransactionItem` | `gen_postpone_transaction_item` | Reschedules a queue transaction item to a later deadline. | User wants to defer a transaction (rate-limit, retry-window); for outright failure use SetTransactionStatus(Failed). |
| `ProcessEndTrigger` | `gen_process_end_trigger` | Trigger that fires when a Windows process exits. | User wants reactive flow on process termination; v2 (ProcessEndTriggerV2) is the latest stable. |
| `ProcessEndTriggerV2` | `gen_process_end_trigger_v2` | v2 of ProcessEndTrigger — current stable process-exit trigger. | User wants modern process-end watching; v1 remains for backwards compatibility. |
| `ProcessStartTrigger` | `gen_process_start_trigger` | Trigger that fires when a Windows process starts. | User wants reactive flow on process launch; v2 (ProcessStartTriggerV2) is the latest stable. |
| `ProcessStartTriggerV2` | `gen_process_start_trigger_v2` | v2 of ProcessStartTrigger — current stable process-start trigger. | User wants modern process-start watching; v1 remains for backwards compatibility. |
| `ProcessTrackingScope` | `gen_process_tracking_scope` | Scope wrapper that emits Process Mining tracking events for activities executed within. | User wants Process Mining instrumentation; for ad-hoc analytics emission use TrackObject. |
| `QueueTrigger` | `gen_queue_trigger` | Trigger that fires when a queue item is added to a watched Orchestrator queue. | User wants reactive Performers; for time-based use TimeTrigger. |
| `RaiseAlert` | `gen_raise_alert` | Raises a Process Insights alert with a severity / message. | User wants to surface a problem to ops dashboards; for plain log writes use LogMessage. |
| `ReadStorageText` | `gen_read_storage_text` | Reads the text content of a file in an Orchestrator Storage Bucket. | User wants bucket-stored text without downloading first; for binary or large files use DownloadStorageFile. |
| `RemoveDataColumn` | `gen_remove_data_column` | Removes a column from a DataTable by name or DataColumn object. | User wants to drop a column before exporting; for projecting to a new schema entirely consider Filter Data Table or LINQ. |
| `RemoveDataRow` | `gen_remove_data_row` | Removes a row from a DataTable by index or DataRow object. | User wants to drop one row; for many-row removal by criteria use FilterDataTable. |
| `RemoveDuplicateRows` | `gen_remove_duplicate_rows` | Removes duplicate rows from a DataTable (full-row equality across all columns). | User wants a deduped table; for column-subset deduplication use a Filter Data Table chain or LINQ. |
| `RenameFileX` | `gen_rename_file_x` | Renames a file (or moves it) preserving content. | User wants to change a file's name; for moving across drives use Move File. |
| `RenameFolderX` | `gen_rename_folder_x` | Renames a folder (or moves it) preserving content. | User wants to change a folder's name; for moving across drives use MoveFolderX. |
| `RepeatNumberOfTimesX` | `gen_repeat_number_of_times_x` | Loops a fixed number of times. | User wants N-iteration repetition; for collection iteration use ForEach; for condition-driven use While. |
| `RepeatTrigger` | `gen_repeat_trigger` | Trigger that fires on a fixed cadence relative to a base time. | User wants periodic execution (e.g. every 5 minutes); for cron-style absolute times use TimeTrigger. |
| `Replace` | `gen_replace` | Replaces occurrences of a substring or regex with a replacement value. | User wants string find/replace; for file in-place edits use FindAndReplace; VB's Replace / Regex.Replace suffices in expressions. |
| `ReportStatus` | `gen_report_status` | Reports an interim status for the running job to Orchestrator dashboards. | User wants progress visibility on long jobs; for terminal status use SetTransactionStatus. |
| `ResetTimer` | `gen_reset_timer` | Resets a named Timer activity's elapsed counter to zero. | User wants to restart a timing measurement; pair with StartTimer / StopTimer. |
| `ResumeTimer` | `gen_resume_timer` | Resumes a paused Timer activity. | User wants to continue a paused measurement; pair with StartTimer / StopTimer / ResetTimer. |
| `Return` | `gen_return` | Returns from the current workflow / scope, propagating an optional value. | User wants an early exit from a subworkflow; for terminating the entire job use TerminateWorkflow. |
| `RunJob` | `gen_run_job` | Triggers a job run against an Orchestrator process and optionally waits for completion. | User wants to invoke another process from the current workflow; for fire-and-forget use StartJob. |
| `SelectFile` | `gen_select_file` | Opens an OS file-picker dialog and returns the chosen path. | User wants user-driven file selection (attended only); unattended runs should source paths from config. |
| `SelectFolder` | `gen_select_folder` | Opens an OS folder-picker dialog and returns the chosen path. | User wants user-driven folder selection (attended only); unattended runs should source paths from config. |
| `SendEmailNotification` | `gen_send_email_notification` | Sends a templated email notification (Orchestrator-configured SMTP) to one or more recipients. | User wants ops-style notification email; for full mail control use SendOutlookMail / SendSMTPMail. |
| `SetAsset` | `gen_set_asset` | Writes a value to a named Orchestrator asset. | User wants to update a centrally-managed value; for credentials use SetCredential. |
| `SetCredential` | `gen_set_credential` | Writes a username/password pair to a named Orchestrator credential asset. | User wants to rotate or seed a credential asset; for non-credential values use SetAsset. |
| `SetEnvironmentVariable` | `gen_set_environment_variable` | Sets a process- or user-scoped environment variable. | User wants to inject env state for downstream tools; reads use GetEnvironmentVariable. |
| `SetSecret` | `gen_set_secret` | Writes a secret value to a configured secret store. | User wants to seed or rotate a secret; reads use GetSecret. |
| `SetTaskStatus` | `gen_set_task_status` | Updates the status of a tracked task (Tasks app integration). | User wants to mark a task complete / cancelled; for queue items use SetTransactionStatus. |
| `SetTraceStatus` | `gen_set_trace_status` | Sets a trace breadcrumb for distributed tracing of the current job. | User wants OpenTelemetry-style traces in Insights; for ad-hoc logs use LogMessage. |
| `SetTransactionProgress` | `gen_set_transaction_progress` | Updates the progress percentage of a long-running queue transaction. | User wants progress visibility on a transaction; for terminal status use SetTransactionStatus. |
| `SetTransactionStatus` | `gen_set_transaction_status` | Marks a queue transaction Successful / Failed (with reason) at the end of processing. | User wants to close out a Performer transaction; in REFramework the End Transaction state wires this automatically. |
| `SortDataTable` | `gen_sort_data_table` | Sorts a DataTable by one or more columns in ascending/descending order. | User wants ordered rows for output or deduplication; pair with RemoveDuplicateRows to canonicalize before persisting. |
| `SplitText` | `gen_split_text` | Splits a string into a list of substrings on a delimiter or regex. | User wants tokenized string output; for joining the inverse use CombineText. |
| `StartJob` | `gen_start_job` | Triggers a job run against an Orchestrator process and returns immediately (fire-and-forget). | User wants asynchronous process invocation; for synchronous use RunJob. |
| `StartTimer` | `gen_start_timer` | Starts a named Timer activity for measuring elapsed time. | User wants to measure how long a region takes; pair with StopTimer / ResetTimer. |
| `StartTriggers` | `gen_start_triggers` | Starts all (or named) Orchestrator triggers attached to the current process. | User wants to enable a trigger set; pair with StopTriggers. |
| `StopJob` | `gen_stop_job` | Stops a running Orchestrator job by ID (cooperative). | User wants to abort a running job from another job; the target job should call ShouldStop at safe points. |
| `StopTimer` | `gen_stop_timer` | Stops a named Timer activity and returns the elapsed time. | User wants to capture a region's duration; pair with StartTimer. |
| `StopTriggers` | `gen_stop_triggers` | Stops all (or named) Orchestrator triggers attached to the current process. | User wants to pause a trigger set; pair with StartTriggers. |
| `TextToLeftRight` | `gen_text_to_left_right` | Splits a string at the first occurrence of a delimiter into (left, right) parts. | User wants a one-shot split into two pieces; for n-way splits use SplitText. |
| `TimeoutScope` | `gen_timeout_scope` | Aborts the activities inside the scope after a configurable timeout. | User wants a hard upper bound on a region's duration; for retry-with-timeout use RetryScope. |
| `TimeTrigger` | `gen_time_trigger` | Trigger that fires at scheduled times (cron-style). | User wants scheduled execution; for relative cadence use RepeatTrigger. |
| `TrackObject` | `gen_track_object` | Emits an analytics event with a named object payload to Insights / Process Mining. | User wants to record a typed event for analytics; for whole-process spans use ProcessTrackingScope. |
| `TriggerScope` | `gen_trigger_scope` | Scope wrapper hosting one or more triggers and their reactive bodies. | User wants to author trigger-driven workflows; the scope manages start/stop lifecycle. |
| `UpdateRowItem` | `gen_update_row_item` | Sets a single column value on a DataRow. | User wants to mutate one cell in a DataTable; the inline expression `row("Col") = value` is also idiomatic. |
| `UploadStorageFile` | `gen_upload_storage_file` | Uploads a local file to an Orchestrator Storage Bucket. | User wants to publish artifacts to a bucket; pair with DownloadStorageFile / ListStorageFiles. |
| `VariablesBlock` | `gen_variables_block` | Helper composite that emits a Sequence/Flowchart Variables declaration block. | User is hand-authoring a generator and needs to declare local variables; the standard scaffolder does this automatically. |
| `WaitQueueItem` | `gen_wait_queue_item` | Waits until a matching item appears on a watched Orchestrator queue. | User wants to block until queue input is available; for non-blocking polling use GetQueueItems. |
| `WriteStorageText` | `gen_write_storage_text` | Writes a text payload to a file in an Orchestrator Storage Bucket. | User wants to persist generated text directly to a bucket; for binary or large files use UploadStorageFile. |

## Excel (103)

| Activity | Generator | Description | Use when |
|---|---|---|---|
| `AddSensitivityLabelX` | `gen_add_sensitivity_label_x` | StudioX activity that applies a Microsoft 365 sensitivity label to the active workbook. | User wants to set/replace a sensitivity label on a workbook. To read the current label use GetSensitivityLabelX. |
| `AppendCsvFile` | `gen_append_csv_file` | Append rows from a DataTable to an existing CSV file (or create the file with headers). | User wants to grow a CSV without rewriting it. To overwrite use WriteCsvFile. |
| `AppendRangeX` | `gen_append_range_x` | StudioX 'Append Range' - append a DataTable to the end of an existing sheet/table in the active Excel scope. | User wants to add rows below existing data without overwriting. To overwrite from row 1 use WriteRangeX. |
| `AutoFillX` | `AutoFillX` (data-driven) | StudioX 'Auto Fill Range' - extend a formula or value across a destination range using Excel's auto-fill. | User wants to drag-fill a formula/value across cells. For row-based fill use FillRangeX; for one-off writes use WriteRangeX. |
| `AutoFitX` | `gen_auto_fit_x` | StudioX 'Auto Fit' - auto-size columns or rows in a sheet or range. | User wants Excel to auto-size widths after writing data. |
| `ChangePivotTableDataSourceX` | `gen_change_pivot_table_data_source_x` | StudioX activity that re-points a PivotTable to a different source range. | User wants to redirect a PivotTable's data source. To refresh after underlying data changed use RefreshPivotTableX. |
| `ClearRangeX` | `gen_clear_range_x` | StudioX 'Clear Range' - clear contents and/or formatting from a worksheet range. | User wants to wipe values from cells without deleting the rows/columns. To remove rows use DeleteRowsX. |
| `CloseWorkbook` | `gen_close_workbook` | Close an open workbook in the current Excel scope, optionally saving first. | User wants to close a workbook explicitly. For modern projects this is rarely needed - the Excel scope auto-closes. |
| `CopyChartToClipboardX` | `gen_copy_chart_to_clipboard_x` | StudioX activity that copies an Excel chart image to the system clipboard. | User wants the chart in clipboard form (e.g. to paste into a slide deck or email). |
| `CopyPasteRangeX` | `gen_copy_paste_range_x` | StudioX 'Copy/Paste Range' - copy a source range and paste it to a destination, with paste-special options. | User wants to duplicate a range with native Excel paste semantics. For classic projects use ExcelCopyPasteRange. |
| `CreateNewWorkbook` | `gen_create_new_workbook` | Create a new empty workbook on disk at the given path. | User wants to scaffold a new .xlsx file before writing data. To open an existing workbook use OpenWorkbook. |
| `CreatePivotTable` | `gen_create_pivot_table` | Create a PivotTable in the workbook (classic Excel API) bound to a source range. | User wants a PivotTable in classic projects. In StudioX use CreatePivotTableX or CreatePivotTableXv2. |
| `CreatePivotTableX` | `gen_create_pivot_table_x` | StudioX 'Create Pivot Table' - create a PivotTable bound to a sheet/table range. | User wants a PivotTable in StudioX. The newer variant CreatePivotTableXv2 supports additional layout options. |
| `CreatePivotTableXv2` | `gen_create_pivot_table_xv2` | StudioX 'Create Pivot Table (v2)' - newer variant with additional row/column/value field configuration. | User wants the newer PivotTable creator with explicit field layout. Otherwise CreatePivotTableX works. |
| `CreateTableX` | `gen_create_table_x` | StudioX 'Create Table' - convert a sheet range into a named Excel table (ListObject). | User wants a structured named table over a range so other StudioX activities can reference it by name. |
| `DeleteColumnX` | `gen_delete_column_x` | StudioX 'Delete Column' - remove one or more columns from a sheet or table. | User wants to drop columns. To clear cell values without deleting columns use ClearRangeX. |
| `DeleteRowsX` | `gen_delete_rows_x` | StudioX 'Delete Rows' - remove one or more rows from a sheet or table. | User wants to drop rows. To clear cell values without deleting rows use ClearRangeX. |
| `DeleteSheetX` | `gen_delete_sheet_x` | StudioX 'Delete Sheet' - delete a worksheet from the active workbook. | User wants to remove a worksheet. To rename use RenameSheetX; to add use InsertSheetX. |
| `DuplicateSheetX` | `gen_duplicate_sheet_x` | StudioX 'Duplicate Sheet' - copy an existing worksheet to a new sheet in the same workbook. | User wants a copy of an existing sheet (template duplication). To insert a blank sheet use InsertSheetX. |
| `ExcelAppendRange` | `gen_excel_append_range` | Classic 'Append Range' - append a DataTable to an existing sheet inside an ExcelApplicationScope. | User wants to append rows in classic Excel projects. For StudioX use AppendRangeX. |
| `ExcelApplicationScope` | `gen_excel_application_scope` | Classic Excel Application Scope - open a workbook and run nested classic Excel activities against it. | User wants the classic Excel container with explicit Open/Save semantics. For StudioX use ExcelApplicationCard (wizard-only). |
| `ExcelAutoFillRange` | `gen_excel_auto_fill_range` | Classic 'Auto Fill Range' - extend a formula or value across a destination range. | User wants drag-fill in a classic project. For StudioX use AutoFillX. |
| `ExcelCloseWorkbook` | `gen_excel_close_workbook` | Classic 'Close Workbook' - close the workbook of the surrounding ExcelApplicationScope. | User wants explicit close semantics in classic projects. |
| `ExcelCopyPasteRange` | `gen_excel_copy_paste_range` | Classic 'Copy/Paste Range' - copy a range to a destination with paste-special options. | User wants copy-paste in a classic project. For StudioX use CopyPasteRangeX. |
| `ExcelCopySheet` | `gen_excel_copy_sheet` | Classic 'Copy Sheet' - copy a worksheet to another workbook or position. | User wants to clone a sheet in classic projects. For StudioX use DuplicateSheetX. |
| `ExcelCreatePivotTable` | `gen_excel_create_pivot_table` | Classic 'Create Pivot Table' - create a PivotTable bound to a source range. | User wants a PivotTable in classic projects. For StudioX use CreatePivotTableX or CreatePivotTableXv2. |
| `ExcelCreateTable` | `gen_excel_create_table` | Classic 'Create Table' - convert a range into a named Excel table. | User wants a structured table in classic projects. For StudioX use CreateTableX. |
| `ExcelDeleteColumn` | `gen_excel_delete_column` | Classic 'Delete Column' - remove a column from a sheet. | User wants to drop columns in classic projects. For StudioX use DeleteColumnX. |
| `ExcelDeleteRange` | `gen_excel_delete_range` | Classic 'Delete Range' - delete a range of cells, shifting neighbouring cells. | User wants to remove a sub-range and shift cells. To clear values use ClearRangeX. |
| `ExcelFilterTable` | `gen_excel_filter_table` | Classic 'Filter Table' - apply or clear an AutoFilter on a named table. | User wants table filtering in classic projects. For StudioX use FilterX. |
| `ExcelForEachRow` | `gen_excel_for_each_row` | Classic 'For Each Row in Excel' - iterate the rows of a sheet/range from a classic Excel scope. | User wants row iteration in classic projects. For DataTable iteration use ForEachRow; for StudioX use ExcelForEachRowX (wizard-only). |
| `ExcelGetCellColor` | `gen_excel_get_cell_color` | Classic 'Get Cell Color' - read the background colour of a cell into a Color variable. | User needs the cell's colour value. For StudioX use GetCellColorX. |
| `ExcelGetSelectedRange` | `gen_excel_get_selected_range` | Classic 'Get Selected Range' - read the currently selected range address into a string. | User wants the user's current Excel selection. For StudioX use GetSelectedRangeX. |
| `ExcelGetTableRange` | `gen_excel_get_table_range` | Classic 'Get Table Range' - return the address of a named Excel table. | User needs the address (e.g. A1:D20) of a named table for downstream activities. |
| `ExcelGetWorkbookSheet` | `gen_excel_get_workbook_sheet` | Classic 'Get Workbook Sheet' - return a worksheet by name or index from a workbook. | User wants a sheet handle. For all sheet names use ExcelGetWorkbookSheets / GetSheets. |
| `ExcelGetWorkbookSheets` | `gen_excel_get_workbook_sheets` | Classic 'Get Workbook Sheets' - list the sheet names of the active workbook. | User wants every sheet name for iteration or display. For StudioX use GetSheets. |
| `ExcelInsertColumn` | `gen_excel_insert_column` | Classic 'Insert Column' - insert a column at a given position. | User wants to add a column in classic projects. For StudioX use InsertColumnX. |
| `ExcelInsertDeleteColumns` | `gen_excel_insert_delete_columns` | Classic 'Insert/Delete Columns' - insert or delete N columns in one call. | User wants to add or drop multiple columns at once. |
| `ExcelInsertDeleteRows` | `gen_excel_insert_delete_rows` | Classic 'Insert/Delete Rows' - insert or delete N rows in one call. | User wants to add or drop multiple rows at once. |
| `ExcelLookUpRange` | `gen_excel_look_up_range` | Classic 'Lookup Range' - find the address of a cell containing a given value within a range. | User wants the cell address that holds a value. For VLOOKUP-style data lookup use VLookupX. |
| `ExcelReadCell` | `gen_excel_read_cell` | Classic 'Read Cell' - read a single cell value into a string. | User wants one cell's value in classic projects. For StudioX use ReadCellValueX or ReadCell. |
| `ExcelReadCellFormula` | `gen_excel_read_cell_formula` | Classic 'Read Cell Formula' - read the underlying formula text of a cell. | User wants the formula (=SUM(A1:A10)) rather than its evaluated value. For value use ExcelReadCell. |
| `ExcelReadColumn` | `gen_excel_read_column` | Classic 'Read Column' - read a single column starting at a cell into an IEnumerable<object>. | User wants one column of data without building a DataTable. |
| `ExcelReadRange` | `gen_excel_read_range` | Classic 'Read Range' - read a worksheet range into a DataTable from a classic Excel scope. | User wants to read into a DataTable in classic projects. For StudioX use ReadRangeX. |
| `ExcelReadRow` | `gen_excel_read_row` | Classic 'Read Row' - read a single row starting at a cell into an IEnumerable<object>. | User wants one row of data without building a DataTable. |
| `ExcelRefreshPivotTable` | `gen_excel_refresh_pivot_table` | Classic 'Refresh Pivot Table' - refresh a PivotTable after its source data changes. | User wants to refresh a PivotTable in classic projects. For StudioX use RefreshPivotTableX. |
| `ExcelRemoveDuplicatesRange` | `gen_excel_remove_duplicates_range` | Classic 'Remove Duplicates' - remove duplicate rows from a sheet range. | User wants Excel to dedupe rows. For DataTable dedupe use RemoveDuplicateRows. |
| `ExcelSaveWorkbook` | `gen_excel_save_workbook` | Classic 'Save Workbook' - save the workbook of the surrounding ExcelApplicationScope. | User wants to persist changes in classic projects. |
| `ExcelSelectRange` | `gen_excel_select_range` | Classic 'Select Range' - select a range so subsequent activities act on the user's selection. | User wants to set the active selection in classic projects. For StudioX use SelectRangeX. |
| `ExcelSetRangeColor` | `gen_excel_set_range_color` | Classic 'Set Range Color' - set the background colour of cells in a range. | User wants to colour cells in classic projects. For StudioX use FormatRangeX. |
| `ExcelSortTable` | `gen_excel_sort_table` | Classic 'Sort Table' - sort a named Excel table by one or more columns. | User wants table sorting in classic projects. For StudioX use SortX. |
| `ExcelWriteCell` | `gen_excel_write_cell` | Classic 'Write Cell' - write a value or formula into a single cell. | User wants to set one cell in classic projects. For StudioX use WriteCellX. |
| `ExcelWriteRange` | `gen_excel_write_range` | Classic 'Write Range' - write a DataTable into a worksheet range from a classic Excel scope. | User wants to write a DataTable in classic projects. For StudioX use WriteRangeX; to append use ExcelAppendRange / AppendRangeX. |
| `ExecuteMacro` | `gen_execute_macro` | Classic 'Execute Macro' - run a VBA macro defined in the active workbook with optional parameters. | User wants to invoke an existing VBA macro. For StudioX use ExecuteMacroX. To run inline VBA code use InvokeVBA / InvokeVBAX. |
| `ExecuteMacroX` | `gen_execute_macro_x` | StudioX 'Run Macro' - run a VBA macro defined in the active workbook with optional parameters. | User wants to invoke an existing VBA macro in a StudioX project. For inline VBA code use InvokeVBAX. |
| `ExportExcelToCsvX` | `gen_export_excel_to_csv_x` | StudioX 'Export to CSV' - export a sheet of the active workbook to a CSV file. | User wants a CSV from an Excel sheet directly. For DataTable -> CSV use WriteCsvFile. |
| `FillRangeX` | `gen_fill_range_x` | StudioX 'Fill Range' - fill a range with a value or formula. | User wants every cell in a range set to the same value/formula. For drag-fill behaviour use AutoFillX. |
| `FilterPivotTableX` | `FilterPivotTableX` (data-driven) | StudioX 'Filter Pivot Table' - apply or clear filters on a PivotTable's pivot fields. | User wants to filter a PivotTable. For ordinary range/table filtering use FilterX. |
| `FilterX` | `FilterX` (data-driven) | StudioX 'Filter' - apply or clear an AutoFilter on a sheet range or table. | User wants AutoFilter applied to a range/table. For PivotTable filtering use FilterPivotTableX; for classic projects use ExcelFilterTable. |
| `FindFirstLastDataRowX` | `gen_find_first_last_data_row_x` | StudioX activity that returns the first/last data row index in a sheet or table. | User wants to compute where data starts/ends so they can append correctly. |
| `FindReplaceValueX` | `gen_find_replace_value_x` | StudioX 'Find/Replace Value' - search and replace values across a sheet, table, or range. | User wants Excel-native find/replace. For DataTable-side replace use FindAndReplace. |
| `FormatRangeX` | `gen_format_range_x` | StudioX 'Format Range' - set font, alignment, borders, fill, and number format on a range. | User wants comprehensive cell formatting (not just colour). For colour-only use SetRangeColor / ExcelSetRangeColor. |
| `GetCellColor` | `gen_get_cell_color` | Modern 'Get Cell Color' - read the background colour of a cell. | User wants the cell's colour value in modern projects. For classic use ExcelGetCellColor; for StudioX use GetCellColorX. |
| `GetCellColorX` | `gen_get_cell_color_x` | StudioX 'Get Cell Color' - read the background colour of a cell. | User wants the cell's colour value in StudioX. For classic use ExcelGetCellColor. |
| `GetSelectedRangeX` | `gen_get_selected_range_x` | StudioX 'Get Selected Range' - read the currently selected range address into a string. | User wants the user's current Excel selection in StudioX. For classic use ExcelGetSelectedRange. |
| `GetSensitivityLabelX` | `gen_get_sensitivity_label_x` | StudioX activity that reads the current Microsoft 365 sensitivity label of the active workbook. | User wants to read the workbook's sensitivity label. To set/replace one use AddSensitivityLabelX. |
| `GetSheets` | `gen_get_sheets` | List the sheet names of the active workbook in StudioX/modern Excel. | User wants every sheet name for iteration. For classic use ExcelGetWorkbookSheets. |
| `GetTableRange` | `gen_get_table_range` | Return the address (e.g. A1:D20) of a named Excel table. | User needs a table's range address for downstream activities. |
| `InsertColumnX` | `gen_insert_column_x` | StudioX 'Insert Column' - insert a new column into a sheet or table. | User wants to add a column in StudioX. For classic use ExcelInsertColumn. |
| `InsertExcelChartX` | `InsertExcelChartX` (data-driven) | StudioX 'Insert Chart' - insert a chart of a chosen type bound to a sheet range. | User wants to add a new chart in a StudioX Excel project. To modify an existing chart use UpdateChartX (wizard-only). |
| `InsertRowsX` | `gen_insert_rows_x` | StudioX 'Insert Rows' - insert one or more rows into a sheet or table. | User wants to add rows at a position in StudioX. |
| `InsertSheetX` | `gen_insert_sheet_x` | StudioX 'Insert Sheet' - add a new worksheet to the active workbook. | User wants to add a new sheet. To clone an existing sheet use DuplicateSheetX. |
| `InvokeVBA` | `gen_invoke_vba` | Run inline VBA code against the active workbook (classic Excel projects). | User wants to execute custom VBA without saving a macro first. For StudioX use InvokeVBAX; for an existing macro use ExecuteMacro. |
| `InvokeVBAX` | `gen_invoke_vbax` | Run inline VBA code against the active workbook (StudioX Excel projects). | User wants to execute custom VBA inline in StudioX. For an existing named macro use ExecuteMacroX. |
| `LookupX` | `gen_lookup_x` | StudioX 'Lookup' - find a value in a range and return the corresponding cell address. | User wants the address of a found value. For VLOOKUP-style data return use VLookupX. |
| `MatchFunctionX` | `gen_match_function_x` | StudioX 'Match' - return the position (index) of a value within a range. | User wants the relative index of a matched value (Excel MATCH semantics). |
| `OpenWorkbook` | `gen_open_workbook` | Open an existing .xlsx workbook on disk and return a workbook variable. | User wants to load an existing workbook. To create a new one use CreateNewWorkbook; to use a scope-style container use ExcelApplicationScope or ExcelApplicationCard. |
| `ProtectSheetX` | `gen_protect_sheet_x` | StudioX 'Protect Sheet' - apply password protection to a worksheet. | User wants to lock a sheet against edits. To remove protection use UnprotectSheetX. |
| `ReadCell` | `gen_read_cell` | Modern 'Read Cell' - read a single cell value (string) using the active Excel scope. | User wants a single cell's text in modern Excel. For typed value use ReadCellValueX; for formula use ReadCellFormulaX. |
| `ReadCellFormula` | `gen_read_cell_formula` | Modern 'Read Cell Formula' - read the formula text of a cell. | User wants the formula not the result. For just the value use ReadCell or ReadCellValueX. |
| `ReadCellFormulaX` | `gen_read_cell_formula_x` | StudioX 'Read Cell Formula' - read the formula text of a cell. | User wants the formula (=SUM(A1:A10)) rather than its evaluated value. For just the value use ReadCellValueX or ReadCell. |
| `ReadCellValueX` | `gen_read_cell_value_x` | StudioX 'Read Cell Value' - read a single cell value (typed) using the active Excel scope. | User wants one cell's typed value in StudioX. For string-only use ReadCell; for formula text use ReadCellFormulaX. |
| `ReadColumn` | `gen_read_column` | Modern 'Read Column' - read one column of values into an IEnumerable<object>. | User wants a single column of data. For a row use ReadRow; for full range use ReadRangeX. |
| `ReadRangeX` | `ReadRangeX` (data-driven) | StudioX 'Read Range' - read a worksheet range into a DataTable using the active Excel scope. | User wants to read a sheet/range into a DataTable in a modern (StudioX) Excel project. For classic projects use ExcelReadRange; for a single cell use ReadCellValueX or ExcelReadCell. |
| `ReadRow` | `gen_read_row` | Modern 'Read Row' - read one row of values into an IEnumerable<object>. | User wants a single row. For a column use ReadColumn; for a full range use ReadRangeX. |
| `RefreshDataConnectionsX` | `gen_refresh_data_connections_x` | StudioX activity that refreshes all (or named) data connections in the active workbook. | User wants to pull fresh data from external connections (Power Query, ODBC). For PivotTables alone use RefreshPivotTableX. |
| `RefreshPivotTableX` | `gen_refresh_pivot_table_x` | StudioX 'Refresh Pivot Table' - refresh a PivotTable after its source data changes. | User wants to refresh a single PivotTable. For all data connections use RefreshDataConnectionsX. |
| `RemoveDuplicatesX` | `gen_remove_duplicates_x` | StudioX 'Remove Duplicates' - remove duplicate rows from a sheet range or table. | User wants in-place dedupe in StudioX. For classic use ExcelRemoveDuplicatesRange; for DataTable dedupe use RemoveDuplicateRows. |
| `RenameSheetX` | `gen_rename_sheet_x` | StudioX 'Rename Sheet' - rename an existing worksheet. | User wants to rename a sheet in StudioX. |
| `SaveAsPdfX` | `gen_save_as_pdf_x` | StudioX 'Save as PDF' - export the workbook (or a sheet/range) to a PDF file. | User wants a PDF output of an Excel file. To save as a different Excel file use SaveExcelFileAsX. |
| `SaveExcelFileAsX` | `gen_save_excel_file_as_x` | StudioX 'Save Excel File As' - save the active workbook to a new path. | User wants to save under a different filename or folder. For in-place save use SaveExcelFileX. |
| `SaveExcelFileX` | `gen_save_excel_file_x` | StudioX 'Save Excel File' - save the active workbook to its existing path. | User wants to persist changes in place. To save as a new file use SaveExcelFileAsX. |
| `SelectRangeX` | `gen_select_range_x` | StudioX 'Select Range' - set the active selection in a sheet so subsequent activities act on it. | User wants to mark a range as the active selection. |
| `SequenceX` | `gen_sequence_x` | StudioX Sequence container that groups Excel-related child activities under a logical step. | User wants to group StudioX Excel steps in a labelled container. |
| `SetRangeColor` | `gen_set_range_color` | Modern 'Set Range Color' - set the background colour of cells in a range. | User wants to colour cells in modern projects. For wider formatting use FormatRangeX. |
| `SortX` | `gen_sort_x` | StudioX 'Sort' - sort a sheet range or table by one or more columns. | User wants Excel-side sorting. For classic table sort use ExcelSortTable. |
| `TextToColumnsX` | `gen_text_to_columns_x` | StudioX 'Text to Columns' - split a column by a delimiter into multiple columns. | User wants Excel's Text-to-Columns feature applied to a range. |
| `UnprotectSheetX` | `gen_unprotect_sheet_x` | StudioX 'Unprotect Sheet' - remove password protection from a worksheet. | User wants to unlock a previously protected sheet. To protect use ProtectSheetX. |
| `VLookupX` | `gen_v_lookup_x` | StudioX 'VLookup' - perform an Excel-style VLOOKUP against a range and return the matched value. | User wants VLOOKUP semantics. For arbitrary cell-address lookup use ExcelLookUpRange / LookupX; for general matching use MatchFunctionX. |
| `WithWorkbook` | `gen_with_workbook` | Project Notebook scope that opens a workbook and runs nested activities against it (StudioX project notebook). | User is using the StudioX Project Notebook pattern and wants the implicit workbook scope. |
| `WriteCellX` | `gen_write_cell_x` | StudioX 'Write Cell' - write a value or formula into a single cell. | User wants to set one cell in StudioX. For classic use ExcelWriteCell. |
| `WriteCsvFile` | `gen_write_csv_file` | Write a DataTable to a CSV file (overwriting any existing file). | User wants a CSV from a DataTable. To grow an existing CSV use AppendCsvFile. |
| `WriteRangeX` | `WriteRangeX` (data-driven) | StudioX 'Write Range' - write a DataTable into a worksheet range using the active Excel scope. | User wants to push a DataTable into a sheet in StudioX. For appending instead of overwriting use AppendRangeX; for classic projects use ExcelWriteRange. |

## Email (38)

| Activity | Generator | Description | Use when |
|---|---|---|---|
| `ArchiveMailX` | `gen_archive_mail_x` | StudioX activity that moves an email to the configured Archive folder of the active mail account. | User wants the StudioX 'Archive Email' button equivalent. For arbitrary moves use MoveOutlookMessage / MoveMessageToFolder. |
| `CreateDraft` | `gen_create_draft` | Create a draft email in the chosen mail account without sending it. | User wants to stage an email for human review or later send. To send immediately use SendOutlookMail / SendExchangeMail / SendMailX. |
| `CreateHtmlContent` | `gen_create_html_content` | Build an HTML body string from a template and variables for use as an email body. | User wants to compose a templated HTML email body before sending. Pair with SendOutlookMail / SendMailX. |
| `DeleteImapMailMessage` | `gen_delete_imap_mail_message` | Delete a MailMessage from an IMAP server. | User wants to remove a message via IMAP. For Outlook use DeleteOutlookMailMessage; for Exchange use DeleteMail; for Lotus Notes use DeleteLotusNotesMailMessage. |
| `DeleteLotusNotesMailMessage` | `gen_delete_lotus_notes_mail_message` | Delete a MailMessage from an IBM/HCL Lotus Notes mailbox. | User automates Lotus Notes mail and wants to delete a message. For other providers use DeleteImapMailMessage / DeleteOutlookMailMessage / DeleteMail. |
| `DeleteMail` | `gen_delete_mail` | Delete a MailMessage through Exchange (EWS) using the active scope. | User wants to delete an Exchange message inside an ExchangeScope. For Outlook desktop use DeleteOutlookMailMessage; for IMAP use DeleteImapMailMessage. |
| `DeleteMailX` | `gen_delete_mail_x` | StudioX 'Delete Email' activity for the active mail account. | User wants the StudioX delete-email button equivalent. For provider-specific calls use DeleteOutlookMailMessage / DeleteImapMailMessage / DeleteMail. |
| `DeleteOutlookMailMessage` | `gen_delete_outlook_mail_message` | Delete a MailMessage from the local desktop Outlook profile. | User wants to delete a message in desktop Outlook. For IMAP use DeleteImapMailMessage; for Exchange use DeleteMail. |
| `ExchangeScope` | `gen_exchange_scope` | Connect to Exchange Web Services (EWS) and run nested Exchange mail activities under that connection. | User wants EWS-based mail automation in a single scope. For Microsoft 365 Graph use the plugin scope; for desktop Outlook none - use the activities directly. |
| `ForwardMailX` | `gen_forward_mail_x` | StudioX 'Forward Email' activity for the active mail account. | User wants to forward the current StudioX email. For provider-specific forwarding use the underlying Outlook/Exchange activities. |
| `GetEmailById` | `gen_get_email_by_id` | Fetch a single mail message by its provider-specific identifier. | User already knows the message ID (e.g. from a trigger) and wants the full MailMessage. For folder enumeration use the provider's Get*Mail* activity. |
| `GetExchangeMailMessages` | `gen_get_exchange_mail_messages` | Read mail messages from an Exchange folder via Exchange Web Services (EWS). | User automates Exchange via EWS and wants to fetch messages. For desktop Outlook use GetOutlookMailMessages; for IMAP use GetPOP3MailMessages or an IMAP variant. |
| `GetLotusNotesMailMessages` | `gen_get_lotus_notes_mail_messages` | Read mail messages from an IBM/HCL Lotus Notes mailbox. | User automates Lotus Notes mail. For other providers use GetOutlookMailMessages / GetExchangeMailMessages / GetPOP3MailMessages. |
| `GetMailMessageFromFile` | `gen_get_mail_message_from_file` | Load a saved .eml or .msg file from disk into a MailMessage variable. | User has previously saved an email to disk and wants to re-load it for processing. To save use SaveMail / SaveMailX. |
| `GetOutlookMailMessages` | `GetOutlookMailMessages` (data-driven) | Read mail messages from a desktop Outlook folder using the local Outlook profile. | User has Outlook installed and wants to fetch messages from a local mailbox folder. For Exchange Web Services use GetExchangeMailMessages; for Microsoft 365 Graph use plugin activities. |
| `GetPOP3MailMessages` | `gen_get_pop3_mail_messages` | Read mail messages from a POP3 server. | User must use POP3 (legacy). Prefer IMAP or Exchange where available; use GetExchangeMailMessages or GetOutlookMailMessages instead. |
| `MarkMailAsReadX` | `gen_mark_mail_as_read_x` | StudioX 'Mark Email as Read' activity for the active mail account. | User wants the StudioX mark-as-read button equivalent. For provider-specific control use MarkOutlookMailAsRead. |
| `MarkOutlookMailAsRead` | `gen_mark_outlook_mail_as_read` | Mark a desktop Outlook MailMessage as read or unread. | User wants to flip the read flag on an Outlook message. For StudioX use MarkMailAsReadX. |
| `MoveIMAPMailMessageToFolder` | `gen_move_imap_mail_message_to_folder` | Move a MailMessage to another folder on an IMAP server. | User automates IMAP and wants to file a message. For Outlook use MoveOutlookMessage; for Exchange use MoveMessageToFolder; for StudioX use MoveMailX. |
| `MoveLotusNotesMailMessage` | `gen_move_lotus_notes_mail_message` | Move a Lotus Notes MailMessage to another mailbox folder. | User automates Lotus Notes and wants to file a message. |
| `MoveMailX` | `gen_move_mail_x` | StudioX 'Move Email' activity for the active mail account. | User wants the StudioX move-email button equivalent. For provider-specific calls use MoveOutlookMessage / MoveIMAPMailMessageToFolder / MoveMessageToFolder. |
| `MoveMessageToFolder` | `gen_move_message_to_folder` | Move an Exchange MailMessage to another folder via EWS inside an ExchangeScope. | User automates Exchange via EWS. For Outlook use MoveOutlookMessage; for IMAP use MoveIMAPMailMessageToFolder. |
| `MoveOutlookMessage` | `MoveOutlookMessage` (data-driven) | Move a desktop Outlook MailMessage to another folder in the same store. | User wants to file an Outlook message to another folder (Archive, Done). For IMAP use MoveIMAPMailMessageToFolder; for Exchange use MoveMessageToFolder. |
| `NewIMAPEmailReceivedTrigger` | `gen_new_imap_email_received_trigger` | Trigger that fires when a new email arrives on an IMAP server. | User wants an event-driven workflow that reacts to new IMAP mail. For Outlook event triggers use OutlookMailMessagesTrigger. |
| `OutlookMailMessagesTrigger` | `gen_outlook_mail_messages_trigger` | Trigger that fires when a new email arrives in a desktop Outlook folder. | User wants an event-driven workflow that reacts to new Outlook mail. For IMAP use NewIMAPEmailReceivedTrigger. |
| `ReplyToMailX` | `gen_reply_to_mail_x` | StudioX 'Reply to Email' activity for the active mail account. | User wants the StudioX reply button equivalent. For provider-specific replies use ReplyToOutlookMailMessage. |
| `ReplyToOutlookMailMessage` | `gen_reply_to_outlook_mail_message` | Reply (or Reply All) to a desktop Outlook MailMessage with new body and optional attachments. | User wants to compose a reply to an Outlook message. For Exchange/IMAP, reply via the underlying provider's send activity with appropriate headers. |
| `SaveExchangeAttachements` | `gen_save_exchange_attachements` | Save all attachments from an Exchange MailMessage to a folder on disk. | User wants to extract attachments from an Exchange message. For other providers use SaveMailAttachmentsX. |
| `SaveMail` | `gen_save_mail` | Save a MailMessage to disk as an .eml/.msg file. | User wants to persist an email for archival or later re-import. For attachments only use SaveMailAttachmentsX; to re-load use GetMailMessageFromFile. |
| `SaveMailAttachmentsX` | `gen_save_mail_attachments_x` | StudioX activity that saves all attachments of the current email to a folder. | User wants the StudioX 'Save Attachments' button equivalent. For Exchange specifically use SaveExchangeAttachements. |
| `SaveMailX` | `gen_save_mail_x` | StudioX 'Save Email' activity that writes the current email to disk. | User wants the StudioX save-email button equivalent. For provider-agnostic saving use SaveMail. |
| `SaveOutlookMailMessage` | `gen_save_outlook_mail_message` | Save a desktop Outlook MailMessage to disk as a .msg file. | User wants to persist an Outlook message in native .msg format. For provider-agnostic .eml use SaveMail. |
| `SendCalendarInviteX` | `gen_send_calendar_invite_x` | StudioX activity that sends a calendar invitation through the active mail account. | User wants to send a meeting invite, not a plain email. For ordinary mail use SendOutlookMail / SendMailX. |
| `SendExchangeMail` | `gen_send_exchange_mail` | Send an email through Exchange Web Services (EWS) inside an ExchangeScope. | User wants to send via EWS. For desktop Outlook use SendOutlookMail; for SMTP use SendMailX. |
| `SendLotusNotesMailMessage` | `gen_send_lotus_notes_mail_message` | Send an email through an IBM/HCL Lotus Notes session. | User automates Lotus Notes outbound mail. |
| `SendMailX` | `gen_send_mail_x` | Send an email via SMTP (configurable host/port/credentials). | User wants to send through a generic SMTP server (Gmail SMTP, custom relay). For Outlook use SendOutlookMail; for Exchange use SendExchangeMail. |
| `SendOutlookMail` | `SendOutlookMail` (data-driven) | Send an email through the local desktop Outlook profile. | User has Outlook installed and wants to send through that profile. For Exchange use SendExchangeMail; for SMTP/Gmail use SendMailX. |
| `SetOutlookMailCategories` | `gen_set_outlook_mail_categories` | Apply or replace one or more Outlook category labels on a desktop Outlook MailMessage. | User wants to tag an Outlook message with category colours/labels. |

## File system (9)

| Activity | Generator | Description | Use when |
|---|---|---|---|
| `AppendWriteCsvFile` | `gen_write_csv` | Write or append a DataTable to a delimited file (CSV / TSV) with configurable delimiter, headers, and quoting. | You have a DataTable to persist as CSV / TSV (one-shot write or row-append). Use WriteTextFile when the payload is unstructured text; use ReadCsvFile to load a CSV back into a DataTable. |
| `CopyFile` | `gen_copy_file` | Copy a file from a source path to a destination path, optionally overwriting an existing target. | You want a duplicate of a file at a new location and need the original to remain in place. Use MoveFile when the source should be removed after the transfer. |
| `CreateDirectory` | `gen_create_directory` | Create a directory at the given path, including any missing parent directories; succeeds silently if the folder already exists. | You need an output / archive folder to exist before writing files into it. Use PathExists when you only want to test for a folder, not ensure one. |
| `DeleteFileX` | `gen_delete_file` | Permanently delete the file at the given path; raises if the path does not exist. | You want to remove a file from disk after processing. Use PathExists first when the path may not exist and you do not want an exception; use MoveFile when the file should be archived rather than discarded. |
| `MoveFile` | `gen_move_file` | Move a file from a source path to a destination path, optionally overwriting an existing target; the source no longer exists after the call. | You want to relocate a file (e.g. archive a processed item) and the source path should be empty afterwards. Use CopyFile when the source must remain in place. |
| `PathExists` | `gen_path_exists` | Check whether a file or folder exists at the given path and write the boolean result to a variable. | You want to branch on a path's presence before deleting, copying, or reading it. Use CreateDirectory when the goal is to ensure a folder exists rather than just test for it. |
| `ReadCsvFile` | `gen_read_csv` | Parse a delimited CSV / TSV file from disk into a DataTable, optionally treating the first row as headers. | The file is column-oriented data (CSV, TSV, pipe-delimited) you want as a DataTable for ForEachRow / DataTable activities. Use ReadTextFile for unstructured text; use AppendWriteCsvFile to write a DataTable back out. |
| `ReadTextFile` | `gen_read_text_file` | Read the entire contents of a text file into a string variable. | You want raw text (config, template, log) handed back as one string. Use ReadCsvFile when the file is delimited and should be parsed into a DataTable; use WriteTextFile to push text the other direction. |
| `WriteTextFile` | `gen_write_text_file` | Write a string variable to a text file at the given path, overwriting any existing file. | You have generated text (a report, config, JSON payload as text) and want it persisted as a single file. Use AppendWriteCsvFile when the data is tabular and should be written column-aware; use ReadTextFile to load text the other direction. |

## HTTP & JSON (10)

| Activity | Generator | Description | Use when |
|---|---|---|---|
| `DeserializeJson` | `gen_deserialize_json` | Parses a JSON object string into a JObject for property access via VB expressions. | User has a JSON object and wants typed access to its fields; for JSON arrays use DeserializeJsonArray; for outbound serialization use SerializeJson. |
| `DeserializeJsonArray` | `DeserializeJsonArray` (data-driven) | Parses a JSON array string into a JArray for iteration with ForEach<JToken>. | User has a JSON array and wants to iterate elements; for JSON objects use DeserializeJson. |
| `DeserializeXml` | `DeserializeXml` (data-driven) | Parses an XML document string into an XDocument for LINQ to XML access. | User has XML text and wants to query nodes via XPath/LINQ; for XPath-only queries use ExecuteXPath; for HTML scraping prefer browser activities. |
| `ExecuteXPath` | `ExecuteXPath` (data-driven) | Runs an XPath query against an XDocument and returns the matching node value. | User has XML and wants a single node value via XPath; for multi-node sets use GetNodes. |
| `GetNodes` | `GetNodes` (data-driven) | Returns the list of XElement nodes matching an XPath expression against an XDocument. | User wants every matching XML node; for a single value use ExecuteXPath; for attribute values use GetXMLNodeAttributes. |
| `GetXMLNodeAttributes` | `GetXMLNodeAttributes` (data-driven) | Returns the attribute values of the XML nodes matching an XPath expression. | User wants attribute values from XML nodes; for the node text content use GetNodes. |
| `GetXMLNodes` | `GetXMLNodes` (data-driven) | Alias of GetNodes for legacy spec compatibility — returns matching XElement nodes. | User wrote an older spec referencing GetXMLNodes; new specs should use GetNodes. |
| `HttpClient` | `HttpClient` (data-driven) | Legacy WebAPI HTTP client scope from UiPath.WebAPI.Activities; performs request with cookie / connection persistence inside the scope body. | User has an existing WebAPI workflow that uses HttpClient; for new work prefer NetHttpRequest from UiPath.WebAPI.Activities (supports OAuth and modern auth). |
| `NetHttpRequest` | `gen_net_http_request` | Performs an HTTP request to a REST endpoint with configurable method, headers, body, and OAuth/Basic auth. | User wants to call a REST API from a workflow; for SOAP/XPath responses also see ExecuteXPath; for the legacy WebAPI scope use HttpClient. |
| `SerializeJson` | `SerializeJson` (data-driven) | Serializes a JObject / dictionary / typed object into a JSON string. | User wants to produce a JSON payload to send to a REST API; for parsing inbound JSON use DeserializeJson / DeserializeJsonArray. |

## Dialogs (2)

| Activity | Generator | Description | Use when |
|---|---|---|---|
| `InputDialog` | `gen_input_dialog` | Show an interactive prompt that asks the user for a string (or one of a fixed set of options) and returns the response. | An attended workflow needs a value supplied by the human at runtime (free text, password, or a dropdown choice). Use MessageBox when you only need to display information without collecting input; use orchestrator forms / Action Center when… |
| `MessageBox` | `gen_message_box` | Display a modal message box to the attended user and block the workflow until they dismiss it. | An attended workflow needs to surface information or pause for confirmation. Prefer LogMessage for unattended logging that should not interrupt execution; use InputDialog when you actually need a typed response back. |

## Error handling & retry (4)

| Activity | Generator | Description | Use when |
|---|---|---|---|
| `Rethrow` | `gen_rethrow` | Re-emit the exception that the enclosing TryCatch is currently handling, preserving its original type and stack. | You are inside a Catch and want to do partial work (logging, cleanup) before letting the same exception bubble up unchanged. Use Throw when you want to raise a different / new exception instead. |
| `RetryScope` | `gen_retryscope` | Run the body and re-execute it up to N times when it fails or its condition stays unmet, then surface the final exception. | The activity inside is calling something flaky (network call, slow UI, eventual-consistency lookup) where the right response to a transient failure is just to try again. Use TryCatch when the failure has a meaningful alternative code path;… |
| `Throw` | `gen_throw` | Raise a new exception built from a VB expression, aborting the current branch with a typed reason. | A business-rule violation or unrecoverable condition must stop execution and surface a specific exception type to the caller. Use Rethrow when you want to re-emit the exception that the surrounding TryCatch already caught; use TryCatch whe… |
| `TryCatch` | `gen_try_catch` | Run a Try block and route any exception to one of several typed Catch handlers, with an optional Finally block that always executes. | An expected exception type has a meaningful recovery path (log, fall back, swallow) that should keep the workflow running. Use RetryScope when the failure is a transient external glitch you simply want to retry; use Throw when you want to … |

## Invoke (workflow / code) (3)

| Activity | Generator | Description | Use when |
|---|---|---|---|
| `InvokeCode` | `gen_invoke_code` | Executes an inline VB.NET or C# code block with read/write access to declared In/Out arguments. | User wants a short fragment of imperative code without authoring a full subworkflow; for shared subroutines use InvokeWorkflowFile; for calling existing CLR methods use InvokeMethod. |
| `InvokeMethod` | `gen_invoke_method` | Reflectively calls a static or instance method on a CLR object, passing parameters and capturing the return value. | User wants to call a single .NET method (e.g. String.Format, list.Add) without writing a full code block; for multi-statement logic use InvokeCode; for subworkflow reuse use InvokeWorkflowFile. |
| `InvokeWorkflowFile` | `gen_invoke_workflow` | Invokes a separate .xaml workflow file as a subroutine, marshalling InArgument/OutArgument values across the boundary. | User wants to call a reusable subworkflow stored on disk; for inline business logic in a single language use InvokeCode; for reflective static/instance method calls use InvokeMethod. |

## Orchestrator (5)

| Activity | Generator | Description | Use when |
|---|---|---|---|
| `AddQueueItem` | `gen_add_queue_item` | Enqueues a single transaction item into an Orchestrator queue, optionally with reference, deadline, priority, and SpecificContent. | User wants to push one item to a queue from a dispatcher; for many items in a batch use BulkAddQueueItems to avoid per-item HTTP overhead. |
| `BulkAddQueueItems` | `gen_bulk_add_queue_items` | Enqueues multiple transaction items in a single Orchestrator request from a list of SpecificContent dictionaries. | User wants to push many items at once (faster than looping AddQueueItem); for a single item use AddQueueItem. |
| `GetQueueItem` | `gen_get_queue_item` | Pops the next available queue item from an Orchestrator queue and assigns it to a QueueItem variable. | User wants the next transaction in a Performer; for adding items use AddQueueItem; in REFramework use the built-in Get Transaction Data state instead of calling this directly. |
| `GetRobotAsset` | `gen_get_robot_asset` | Reads a typed asset (text, integer, boolean, json) from Orchestrator and assigns its value to a local variable. | User wants a configuration value held centrally in Orchestrator; for username+password pairs use GetRobotCredential. |
| `GetRobotCredential` | `gen_getrobotcredential` | Reads a credential asset from Orchestrator and outputs username + secure password into local variables. | User wants to retrieve a credential by asset name; for non-credential assets (text/int/bool/json) use GetRobotAsset. |

## Logging & helpers (11)

| Activity | Generator | Description | Use when |
|---|---|---|---|
| `AddLogFields` | `gen_add_log_fields` | Attaches structured key/value fields to every subsequent LogMessage call within the workflow scope. | User wants to enrich logs with correlation IDs / business keys for downstream filtering; remove with RemoveLogFields when scope ends. |
| `Break` | `gen_break` | Exits the enclosing loop (ForEach / While / DoWhile) immediately. | User wants to terminate iteration once a condition is met; for skipping the rest of the current iteration only use Continue. |
| `Comment` | `gen_comment` | Inserts an inline comment annotation in the workflow surface — no runtime effect. | User wants to document intent inline next to activities; for disabling a block of activities use CommentOut. |
| `CommentOut` | `gen_comment_out` | Disables a block of activities at design-time without deleting them — they remain visible but are skipped at runtime. | User wants to temporarily disable activities while keeping them visible for context; for inline notes use Comment. |
| `Continue` | `gen_continue` | Skips to the next iteration of the enclosing loop, bypassing remaining activities in the current iteration. | User wants to skip the rest of the current iteration; for terminating the loop entirely use Break. |
| `KillProcess` | `gen_kill_process` | Forcibly terminates a Windows process by name or process object. | User wants to close a hung application that won't respond to graceful shutdown; for graceful close use NApplicationCard's CloseDialog action when available. |
| `LogMessage` | `gen_logmessage` | Writes a message to the robot log at the chosen level (Trace/Info/Warn/Error/Fatal). | User wants to record progress or a diagnostic message; for permanent log enrichment use AddLogFields; for raising alerts use RaiseAlert. |
| `RemoveLogFields` | `gen_remove_log_fields` | Removes previously-added structured log fields by key list. | User wants to clear log context attached by AddLogFields when leaving a scope. |
| `ShouldStop` | `gen_should_stop` | Returns True if the user has requested the job to stop via Orchestrator's Stop button. | User wants to honor cooperative stop signals at safe checkpoints; long loops should check ShouldStop and exit cleanly. |
| `TakeScreenshotAndSave` | `gen_take_screenshot_and_save` | Composite that captures a screenshot and persists it to the supplied path in one step. | User wants a quick capture-and-save in error handlers or evidence trails; for take-only into a variable use NTakeScreenshot then SaveImage. |
| `TerminateWorkflow` | `gen_terminate_workflow` | Terminates the running workflow with a status (Successful / Faulted / Cancelled) and optional exception. | User wants to abort the workflow with a definitive outcome; for raising a recoverable exception use Throw inside a TryCatch. |

## External integrations (24)

| Activity | Generator | Description | Use when |
|---|---|---|---|
| `AppendRange` | `gen_append_range` | Classic Workbook 'Append Range' — append a DataTable below the existing data in a sheet without opening Excel. | User wants to add rows under existing data via the classic Workbook API. To overwrite from row 1 use WriteRange; for modern Excel (X) projects use AppendRangeX. |
| `BulkInsert` | `BulkInsert` (data-driven) | Bulk-load every row of a DataTable into a target database table using the provider's bulk-copy API. | User has a DataTable whose schema matches an existing table and needs the fastest insert path. Requires a prior DatabaseConnect. For row-by-row inserts use ExecuteNonQuery; to update existing rows use BulkUpdate; to insert one DataTable th… |
| `BulkUpdate` | `BulkUpdate` (data-driven) | Bulk-update existing rows in a target database table from a DataTable matched on primary key. | User has a DataTable whose rows already exist in the target table and need their non-key columns refreshed. Requires a prior DatabaseConnect. To insert new rows use BulkInsert. |
| `DatabaseConnect` | `gen_database_connect` | Open a database connection from a connection string and return a DatabaseConnection variable for reuse. | User wants to share one connection across multiple subsequent ExecuteQuery / ExecuteNonQuery / BulkInsert / DatabaseTransaction calls. Always pair with DatabaseDisconnect; for one-off queries skip this and pass the connection string direct… |
| `DatabaseDisconnect` | `DatabaseDisconnect` (data-driven) | Close a previously opened DatabaseConnection and release its underlying resources. | User wants to release a connection opened by DatabaseConnect (typically in a Finally block). To open the connection use DatabaseConnect. |
| `DatabaseTransaction` | `DatabaseTransaction` (data-driven) | Scope that runs nested database activities inside a single transaction (commit on success, rollback on error). | User wants several ExecuteNonQuery / ExecuteQuery / BulkInsert calls to commit or roll back atomically. For one-off statements skip the transaction wrapper. |
| `ExecuteNonQuery` | `gen_execute_non_query` | Run a SQL statement that does not return rows (INSERT/UPDATE/DELETE/DDL) and return the affected-row count. | User wants to mutate the database (insert/update/delete) or run DDL. For SELECT use ExecuteQuery; for batched loads use BulkInsert; to wrap several statements atomically use DatabaseTransaction. |
| `ExecuteQuery` | `gen_execute_query` | Run a SELECT query against a database and return the rows as a DataTable. | User wants result rows from a SQL SELECT (or any query that returns a row set). For INSERT/UPDATE/DELETE without a result set use ExecuteNonQuery; for high-volume bulk loads use BulkInsert. |
| `ExportPDFPageAsImage` | `ExportPDFPageAsImage` (data-driven) | Render one page of a PDF to a PNG/JPG image file at the requested DPI. | User wants a single PDF page as a raster image (for thumbnails, OCR pre-processing, embedding in reports). For all images embedded inside the PDF use ExtractImagesFromPDF; for OCR text use ReadPDFWithOCR. |
| `ExtractImagesFromPDF` | `ExtractImagesFromPDF` (data-driven) | Save every embedded image in a PDF to files in an output folder. | User wants the original images embedded inside a PDF (logos, photographs, charts). For rasterised page snapshots use ExportPDFPageAsImage. |
| `ExtractPDFPageRange` | `ExtractPDFPageRange` (data-driven) | Extracts a contiguous page range from a PDF into a new PDF file. | User wants a subset of pages saved as a separate PDF; for the entire page count use GetPDFPageCount; for OCR on extracted pages use ReadPDFWithOCR. |
| `GetIMAPMailMessages` | `gen_get_imap_mail` | Read email messages from an IMAP mailbox folder into a List<MailMessage>. | User wants to fetch mail from an IMAP server (folders, server-side flags). For POP3 use GetPOP3MailMessages; for Exchange/EWS use GetExchangeMailMessages; for an Outlook desktop client use GetOutlookMailMessages. |
| `GetPDFPageCount` | `GetPDFPageCount` (data-driven) | Returns the total number of pages in a PDF document. | User wants to size a loop or validate document length; for content extraction use ReadPDFText / ReadPDFWithOCR. |
| `InsertDataTable` | `InsertDataTable` (data-driven) | Insert every row of a DataTable into a target database table via parameterised INSERTs. | User wants to push a DataTable into a table without the provider-specific bulk-copy fast path. For high-volume loads use BulkInsert; for hand-written SQL use ExecuteNonQuery. |
| `JoinPDF` | `JoinPDF` (data-driven) | Concatenates multiple PDF files into a single output PDF. | User wants to merge several PDFs end-to-end; for a page-range subset of a single PDF use ExtractPDFPageRange. |
| `ManagePDFPassword` | `ManagePDFPassword` (data-driven) | Adds or removes the owner/user password on a PDF document. | User wants to apply or strip a password from a PDF; the password value should come from a credential asset (GetRobotCredential), not be hardcoded. |
| `ReadPDFText` | `gen_read_pdf_text` | Extract embedded text from a PDF file into a String variable. | User wants the text layer of a digitally-generated PDF. For scanned/image PDFs use ReadPDFWithOCR; for the page count use GetPDFPageCount. |
| `ReadPDFWithOCR` | `gen_read_pdf_with_ocr` | Run OCR over a PDF (page-by-page rasterisation) and return the recognised text. | User wants text from a scanned or image-only PDF. For PDFs with an embedded text layer use ReadPDFText (faster, lossless). |
| `ReadRange` | `gen_read_range` | Classic Workbook 'Read Range' — read a worksheet range into a DataTable without opening Excel. | User wants to read a sheet/range into a DataTable via the classic Workbook API (no ExcelApplicationScope). For modern Excel (X) projects use ReadRangeX; for classic-with-Excel use ExcelReadRange. |
| `ReadXPSText` | `ReadXPSText` (data-driven) | Reads text content from an XPS document into a string variable. | User wants the text body of an XPS file; for PDF text use ReadPDFText; for OCR on scanned XPS use ReadXPSWithOCR. |
| `SaveMailAttachments` | `gen_save_mail_attachments` | Save the attachments of a MailMessage to a folder on disk, optionally filtered by extension. | User has a MailMessage from any Get*MailMessages activity and wants its attachments written to disk. Pair with GetIMAPMailMessages, GetOutlookMailMessages, or GetExchangeMailMessages. |
| `SendMail` | `gen_send_mail` | Send an email through an SMTP server (or Integration Service connection). | User wants to send mail via plain SMTP or an Integration Service mail connection. For Outlook desktop use SendOutlookMail; for Exchange Web Services use SendExchangeMail. |
| `WriteCell` | `gen_write_cell` | Classic Workbook 'Write Cell' — write a single value or formula into one cell without opening Excel. | User wants to set one cell via the classic Workbook API. For a whole DataTable use WriteRange; for modern Excel (X) projects use WriteCellX. |
| `WriteRange` | `gen_write_range` | Classic Workbook 'Write Range' — write a DataTable into a worksheet range without opening Excel. | User wants to push a DataTable to a sheet via the classic Workbook API (no ExcelApplicationScope). For modern Excel (X) projects use WriteRangeX; to append rather than overwrite use AppendRange. |

## Testing (18)

| Activity | Generator | Description | Use when |
|---|---|---|---|
| `Address` | `Address` (data-driven) | Returns a random plausible street address from a built-in dataset for test data. | User wants realistic address input; pair with GivenName / LastName for a synthetic person record. |
| `AttachDocument` | `AttachDocument` (data-driven) | Attaches a file artifact (screenshot, log, evidence) to the current test result. | User wants to include evidence in a Test Manager run; for inline log messages use LogMessage; for screenshots specifically use TakeScreenshotAndSave first. |
| `BulkAddTestDataQueue` | `BulkAddTestDataQueue` (data-driven) | Inserts many rows into a Test Data Queue from a DataTable in a single Orchestrator request. | User wants to seed a Test Data Queue from an Excel sheet; for one row at a time use NewAddTestDataQueueItem. |
| `ComparePdfDocuments` | `ComparePdfDocuments` (data-driven) | Compares two PDF documents and reports per-page differences using a comparison rule. | User wants to verify that a generated PDF matches a baseline; for plain text comparison use CompareText. |
| `CompareText` | `CompareText` (data-driven) | Compares two strings using a comparison rule (case-insensitive, whitespace-normalized, regex-aware). | User wants to assert string equivalence with normalization options; for raw equality use VerifyExpressionWithOperator with the Equals operator. |
| `CreateComparisonRule` | `CreateComparisonRule` (data-driven) | Builds a reusable comparison rule object for ComparePdfDocuments / CompareText. | User wants to share a normalization configuration (ignore whitespace, case-insensitive, regex masks) across multiple comparisons. |
| `DeleteTestDataQueueItems` | `DeleteTestDataQueueItems` (data-driven) | Deletes test data items from a Test Data Queue by ID list or filter. | User wants to clear a queue between test runs; pair with BulkAddTestDataQueue to refresh test data. |
| `GetTestDataQueueItem` | `GetTestDataQueueItem` (data-driven) | Pops one test data row from a Test Data Queue and binds its fields to local variables. | User wants the next row of test data in a data-driven test; for many rows in one call use GetTestDataQueueItems. |
| `GetTestDataQueueItems` | `GetTestDataQueueItems` (data-driven) | Returns a batch of test data rows from a Test Data Queue as a list. | User wants several rows in one call (faster than looping GetTestDataQueueItem); for a single row use GetTestDataQueueItem. |
| `GivenName` | `GivenName` (data-driven) | Returns a random plausible given (first) name from a built-in dataset for test data. | User wants realistic first-name input; pair with LastName + Address for a synthetic person record. |
| `LastName` | `LastName` (data-driven) | Returns a random plausible family (last) name from a built-in dataset for test data. | User wants realistic last-name input; pair with GivenName + Address for a synthetic person record. |
| `RandomDate` | `RandomDate` (data-driven) | Generates a random DateTime within a specified [from, to] range. | User wants synthetic date input; for a calendar-aware business-day variant authoring is custom. |
| `RandomNumber` | `RandomNumber` (data-driven) | Generates a random integer or decimal within a specified range for test data. | User wants synthetic numeric input; for a value drawn from an enum-like set use RandomValue. |
| `RandomString` | `RandomString` (data-driven) | Generates a random string of given length and character class for test data. | User wants synthetic string input for a test; for numbers use RandomNumber; for human-shaped values (names, addresses) use GivenName / LastName / Address. |
| `RandomValue` | `RandomValue` (data-driven) | Returns a random element from a supplied list of candidate values. | User wants a value picked from a fixed set (e.g. a category enum); for free-form strings use RandomString. |
| `VerifyExpression` | `VerifyExpression` (data-driven) | Asserts that a boolean expression evaluates to True; fails the test step otherwise. | User wants a simple True/False assertion; for comparator-based assertions (eq/lt/gt/contains) use VerifyExpressionWithOperator; for numeric-range checks use VerifyRange. |
| `VerifyExpressionWithOperator` | `VerifyExpressionWithOperator` (data-driven) | Asserts that two expressions satisfy a comparator (Equals, NotEquals, GreaterThan, LessThan, Contains). | User wants a typed comparator assertion; for raw boolean expressions use VerifyExpression; for numeric ranges use VerifyRange. |
| `VerifyRange` | `VerifyRange` (data-driven) | Asserts that a numeric value falls within an inclusive [min, max] range. | User wants to verify a number is between two bounds; for equality / comparator checks use VerifyExpressionWithOperator. |

## Don't auto-generate (18)

These activities require UiPath Studio's interactive wizard or otherwise
cannot be reliably emitted programmatically. Direct the user to author
them in Studio rather than calling the dispatcher.

| Activity | Reason | Description |
|---|---|---|
| `ApplicationEventTrigger` | wizard-only | Trigger that fires when a configured application event occurs (wizard-only). |
| `ChangeDataRangeModification` | wizard-only | Internal Excel range-modification helper without a stable XAML namespace (wizard-only). |
| `ExcelApplicationCard` | wizard-only | Modern Use Excel File scope (wizard-only) - opens a workbook and runs nested Excel activities against it. |
| `ExcelForEachRowX` | wizard-only | StudioX For Each Row in Excel (wizard-only) - iterates over rows in a sheet/table with a CurrentRow + CurrentIndex body. |
| `ExcelProcessScopeX` | wizard-only | Modern Excel Process Scope (wizard-only) - controls a single Excel process instance for nested activities. |
| `ExtractUIData` | wizard-only | Classic Data Scraping wizard output - extracts tabular UI data based on a recorded pattern (wizard-only). |
| `ForEachEmailX` | wizard-only | StudioX For Each Email iterator (wizard-only) over a mailbox folder. |
| `ForEachSheetX` | wizard-only | StudioX For Each Sheet (wizard-only) - iterates over each worksheet of the workbook with a CurrentSheet + CurrentIndex body. |
| `GetAttribute` | wizard-only | Read a named UI element attribute (innertext, aaname, etc.) into an output variable (wizard-only). |
| `MockActivity` | wizard-only | Substitutes a mocked implementation for a wrapped activity at test time, returning a canned output. |
| `NAccessibilityCheck` | wizard-only | Run an accessibility audit (axe-core) against the current browser/app state (wizard-only). |
| `NewAddTestDataQueueItem` | wizard-only | Inserts a single row into a Test Data Queue with the given field values. |
| `NExtractFormDataGeneric` | wizard-only | Extract form-field values from a captured form using AI (wizard-only). |
| `NSetValue` | wizard-only | Update a UI element value using AI-driven element resolution (wizard-only). |
| `OutlookApplicationCard` | wizard-only | Modern Use Outlook scope (wizard-only) - pins an Outlook account for nested mail activities. |
| `ReadXPSWithOCR` | wizard-only | Reads text from an XPS document using an OCR engine for image-based pages. |
| `UpdateChartX` | wizard-only | StudioX 'Update Chart' (wizard-only) - updates the data range or properties of an existing chart. |
| `VerifyControlAttribute` | wizard-only | Asserts that a UI element's attribute (Text, Enabled, Visible, etc.) matches an expected value. |

## Alternatives (84)

Each row pairs an activity with its documented substitutes and the
trigger that picks the substitute over the canonical activity.

| Activity | Alternative | Use alternative when |
|---|---|---|
| `AddQueueItem` | `BulkAddQueueItems` | You have many items to enqueue at once; bulk uploads are dramatically faster than a per-item loop. |
| `AppendRange` | `WriteRange` | The destination is empty (or you want to overwrite) rather than append below existing data. |
| `AppendRange` | `AppendRangeX` | The workflow uses the modern Excel (X) suite rather than classic Workbook activities. |
| `AppendRangeX` | `AppendRange` | You are using the classic ExcelApplicationScope rather than a modern Use Excel File scope. |
| `AppendRangeX` | `WriteRangeX` | The destination is empty (or you want to overwrite) rather than append below existing rows. |
| `AppendWriteCsvFile` | `ReadCsvFile` | You actually want to load a CSV from disk into a DataTable, not write one out. |
| `AppendWriteCsvFile` | `WriteTextFile` | The payload is unstructured text rather than a DataTable that needs delimiter-aware formatting. |
| `Assign` | `MultipleAssign` | You need to set two or more variables in one node; one MultipleAssign keeps related writes together. |
| `Assign` | `BuildDataTable` | You are creating a DataTable with a fixed schema rather than assigning a scalar value. |
| `BuildDataTable` | `Assign` | You only need to set a single variable; BuildDataTable is for constructing a tabular value with explicit columns/rows. |
| `BuildDataTable` | `GenerateDataTable` | The source is a delimited string (CSV/TSV-style) that should be parsed into a table rather than typed in column-by-column. |
| `BulkAddQueueItems` | `AddQueueItem` | You only have a single item to enqueue; the bulk path is overkill. |
| `BulkInsert` | `BulkUpdate` | The DataTable rows already exist and need to be updated by primary key rather than appended. |
| `BulkInsert` | `InsertDataTable` | You want a generic DataTable insert without the provider's bulk-copy fast path. |
| `BulkInsert` | `ExecuteNonQuery` | Only a handful of rows; parameterised INSERTs are simpler than wiring DatabaseConnect+BulkInsert. |
| `BulkUpdate` | `BulkInsert` | The rows are new and should be appended rather than matched and updated. |
| `CopyFile` | `MoveFile` | The source should not remain at the original location after the transfer. |
| `DatabaseConnect` | `DatabaseDisconnect` | You already have an open connection and want to close it instead of opening a new one. |
| `DatabaseDisconnect` | `DatabaseConnect` | You need to open a new connection rather than close an existing one. |
| `Delay` | `RetryScope` | You actually need to wait for a condition to succeed (with retry/backoff) rather than burn a fixed amount of time. |
| `DeleteFileX` | `MoveFile` | The file should be archived to another folder rather than destroyed. |
| `ExcelApplicationCard` | `ExcelApplicationScope` | You are using classic (non-modern-design) activities and just need a workbook scope around them. |
| `ExcelApplicationCard` | `ExcelProcessScopeX` | You need a process-wide configuration covering multiple workbooks rather than a card around one Excel session. |
| `ExcelApplicationScope` | `ExcelProcessScopeX` | The workflow runs the modern (X) Excel activities and you want a process-level scope that covers multiple workbooks rather than per-file. |
| `ExcelApplicationScope` | `ExcelApplicationCard` | You are authoring inside a Modern Design experience (Application Card) rather than the classic scope. |
| `ExcelProcessScopeX` | `ExcelApplicationScope` | You only need to open and operate on a single workbook with classic activities, not configure a process-wide Excel runtime. |
| `ExcelProcessScopeX` | `ExcelApplicationCard` | You are authoring inside the Modern Design Application Card pattern rather than a process-level scope. |
| `ExcelReadColumn` | `ReadRangeX` | You need a rectangular range with multiple columns, not a single column of values. |
| `ExcelReadColumn` | `ReadCellValueX` | You only need one cell from the column. |
| `ExecuteNonQuery` | `ExecuteQuery` | The statement is a SELECT and you need the result rows. |
| `ExecuteNonQuery` | `BulkInsert` | You are loading a large DataTable into a single target table. |
| `ExecuteNonQuery` | `DatabaseTransaction` | Several statements must commit or roll back together. |
| `ExecuteQuery` | `ExecuteNonQuery` | The statement is INSERT/UPDATE/DELETE/DDL and you only need the affected-row count, not a result set. |
| `ExecuteQuery` | `BulkInsert` | You are loading a large DataTable into a single table; BulkInsert is faster than parameterised inserts. |
| `ExportPDFPageAsImage` | `ExtractImagesFromPDF` | You want the images that are already embedded in the PDF (not rasterised page snapshots). |
| `ExtractImagesFromPDF` | `ExportPDFPageAsImage` | You want a rasterised snapshot of an entire page rather than the embedded image objects. |
| `FilterDataTable` | `LookupDataTable` | You need a single matching row's value for a key, not a full filtered subset. |
| `FilterDataTable` | `JoinDataTables` | You need to combine columns from two tables on a key rather than filter rows of one table. |
| `Flowchart` | `StateMachine` | The graph has long-lived states with entry/exit actions and explicit triggers; StateMachine models that better than free-form arrows. |
| `ForEach` | `ForEachRow` | You are iterating the rows of a DataTable; ForEachRow exposes the row item directly without indexing. |
| `ForEach` | `NForEachUiElement` | You are iterating a live collection of UI elements found on screen rather than a generic collection. |
| `ForEach` | `ForEachFileX` | You are iterating files (or folders) under a path; ForEachFileX handles enumeration, filtering, and recursion natively. |
| `ForEachFileX` | `ForEach` | You already have an in-memory collection of file paths; do not re-enumerate the filesystem. |
| `ForEachFileX` | `ForEachRow` | You are iterating rows of a DataTable, not files on disk. |
| `ForEachRow` | `ForEach` | The collection is a generic IEnumerable (List, Array) rather than a DataTable. |
| `ForEachRow` | `ForEachFileX` | You are walking files on disk rather than rows of an in-memory table. |
| `ForEachRow` | `NForEachUiElement` | You are iterating UI elements on screen rather than tabular data. |
| `GetExchangeMailMessages` | `GetOutlookMailMessages` | You want to use the locally-installed Outlook desktop client instead of talking to Exchange Web Services directly. |
| `GetExchangeMailMessages` | `GetIMAPMailMessages` | The server only exposes IMAP, or you need vendor-neutral folder access without Exchange credentials. |
| `GetExchangeMailMessages` | `GetPOP3MailMessages` | The server only exposes POP3 for a one-shot download. |
| `GetIMAPMailMessages` | `GetPOP3MailMessages` | The mailbox only exposes POP3 (one-shot download) rather than IMAP (folders, server-side state). |
| `GetIMAPMailMessages` | `GetExchangeMailMessages` | You can talk to the Exchange Web Services / EWS endpoint directly with credentials rather than going through a generic IMAP gateway. |
| `GetIMAPMailMessages` | `GetOutlookMailMessages` | The robot has a logged-in Outlook desktop client and you want to read from the local profile rather than hit the server over IMAP. |
| `GetOutlookMailMessages` | `GetExchangeMailMessages` | There is no locally-installed Outlook profile and you must hit Exchange Web Services directly. |
| `GetOutlookMailMessages` | `GetIMAPMailMessages` | The mailbox is non-Exchange (e.g. Gmail, generic IMAP) and there is no Outlook client to drive. |
| `GetOutlookMailMessages` | `GetPOP3MailMessages` | The server only exposes POP3 and you just need a one-shot download of new mail. |
| `GetPOP3MailMessages` | `GetIMAPMailMessages` | The server supports IMAP and you need folder navigation or server-side flags rather than a one-shot POP3 download. |
| `GetPOP3MailMessages` | `GetExchangeMailMessages` | You can use the Exchange Web Services endpoint directly for richer querying than POP3. |
| `GetPOP3MailMessages` | `GetOutlookMailMessages` | You want to read from a logged-in Outlook desktop profile rather than poll a POP3 server. |
| `GetRobotAsset` | `GetRobotCredential` | The asset is a Credential type and you need both username and password (as SecureString) returned. |
| `GetRobotCredential` | `GetRobotAsset` | The asset is a non-credential value (text, integer, bool, JSON) rather than a username/password pair. |
| `If` | `Switch` | You are branching on a single value across three or more discrete cases (use Switch for n-way dispatch). |
| `If` | `IfElseIfV2` | You have a chain of mutually exclusive boolean conditions and want explicit else-if branches rather than nested If activities. |
| `IfElseIfV2` | `If` | You only have one boolean branch (with optional else); the chained form is unnecessary. |
| `IfElseIfV2` | `Switch` | Every branch tests the same value against a constant; Switch is clearer for n-way dispatch on one expression. |
| `InputDialog` | `MessageBox` | You only need to show information or get an OK acknowledgement, not collect typed input. |
| `InsertDataTable` | `BulkInsert` | The DataTable is large and the provider supports a bulk-copy API. |
| `InsertDataTable` | `ExecuteNonQuery` | You want explicit SQL/parameter control rather than the implicit column mapping. |
| `InvokeCode` | `InvokeWorkflowFile` | The behavior is reusable and worth modeling as its own XAML workflow with named arguments. |
| `InvokeCode` | `InvokeMethod` | You just need to call one method on an existing object; reflection is lighter than a code block. |
| `InvokeMethod` | `InvokeCode` | You need more than one statement, control flow, or local variables; a code block is more natural than reflection. |
| `InvokeMethod` | `InvokeWorkflowFile` | The behavior is reusable enough to warrant its own XAML workflow with explicit arguments. |
| `InvokeWorkflowFile` | `InvokeCode` | The logic is short, language-level (VB.NET / C#) snippets that do not warrant a separate XAML file. |
| `InvokeWorkflowFile` | `InvokeMethod` | You only need to call a single method on an existing .NET object via reflection, not run a whole workflow. |
| `JoinDataTables` | `FilterDataTable` | You only need to subset one table by a condition, not combine columns from a second table. |
| `JoinDataTables` | `LookupDataTable` | You only need to fetch a single value for a key rather than produce a joined result table. |
| `LookupDataTable` | `FilterDataTable` | You need every matching row, not just the first hit's value. |
| `LookupDataTable` | `JoinDataTables` | You want all matching rows merged with their right-side columns, not just one looked-up scalar. |
| `MessageBox` | `InputDialog` | You need to read a value typed by the user, not just show information. |
| `MessageBox` | `LogMessage` | The workflow is unattended or you only want a log entry rather than a blocking UI prompt. |
| `MoveFile` | `CopyFile` | The original file must remain at its source location after the operation. |
| `MultipleAssign` | `Assign` | You are only setting a single variable; one Assign is simpler than the multi-row form. |
| `MultipleAssign` | `BuildDataTable` | The target is a tabular value with a fixed schema, not a set of scalars. |
| `NApplicationCardAttach` | `NApplicationCardOpen` | You need to launch a browser at a URL rather than attach to an existing one. |
| `NApplicationCardAttach` | `NApplicationCardDesktopOpen` | You need to launch a desktop executable rather than attach to an open window. |
| `NApplicationCardClose` | `NApplicationCardAttach` | You want to keep the app running after the scope ends rather than close it. |
| `NApplicationCardDesktopOpen` | `NApplicationCardOpen` | The target is a URL opened in a browser rather than a desktop executable. |
| `NApplicationCardDesktopOpen` | `NApplicationCardAttach` | The desktop application is already running and you only need to attach to its window. |
| `NApplicationCardOpen` | `NApplicationCardAttach` | The browser or app is already running and you only need to attach to its window. |
| `NApplicationCardOpen` | `NApplicationCardDesktopOpen` | The target is a desktop executable launched by file path, not a URL in a browser. |
| `NCheck` | `NClick` | The target is a generic button or link rather than a checkbox/radio; a raw click is enough. |
| `NCheck` | `NSelectItem` | The control is a dropdown/list rather than a check or radio toggle. |
| `NCheck` | `NCheckState` | You only need to read whether the box is checked, not change it. |
| `NCheckState` | `NClick` | You need to act on the element rather than just observe its state. |
| `NCheckState` | `NCheck` | You need to actually toggle the checkbox/radio rather than read its state. |
| `NCheckState` | `NCheckElement` | You need to assert the element's existence/visibility rather than its checked state. |
| `NClick` | `NCheck` | The target is a checkbox or radio button and you need to set its state instead of just clicking. |
| `NClick` | `NSelectItem` | The target is a combo-box or list and you need to choose an item by visible text rather than firing a click. |
| `NClick` | `NCheckState` | You only need to verify the element's state without interacting; this just observes, NClick acts. |
| `NGetBrowserData` | `NGetText` | The data is rendered text on a UI element rather than browser storage/cookies/form values. |
| `NGetBrowserData` | `NGetClipboard` | The data has already been copied to the clipboard rather than living in browser state. |
| `NGetClipboard` | `NGetText` | The value lives inside a specific UI element rather than on the system clipboard. |
| `NGetClipboard` | `NGetBrowserData` | You need browser-side data (storage, cookies) instead of generic clipboard contents. |
| `NGetText` | `NGetClipboard` | The source already lives on the system clipboard (e.g. user-copied text) rather than inside a UI element. |
| `NGetText` | `NGetBrowserData` | The source is structured browser data (cookies, storage, form values) rather than rendered text on an element. |
| `NHighlight` | `NHover` | You need to actually trigger hover-state UI (tooltip, dropdown) rather than just outline the element for debugging. |
| `NHighlight` | `NTakeScreenshot` | You want a captured image artifact for evidence/logging rather than a live on-screen overlay. |
| `NHover` | `NHighlight` | You only want a visual debug outline, not a real mouse hover that fires the application's hover handlers. |
| `NHover` | `NTakeScreenshot` | You need a saved image of the element rather than to interact with it. |
| `NSelectItem` | `NClick` | The control is a free button or link, not a combo-box/list with named options. |
| `NSelectItem` | `NCheck` | The control is a checkbox or radio button rather than a multi-option selector. |
| `NSelectItem` | `NSetText` | The dropdown is editable and the value is free-form text rather than one of the predefined items. |
| `NSetClipboard` | `NTypeInto` | You want the value entered keystroke-by-keystroke into a specific UI field rather than parked on the system clipboard. |
| `NSetClipboard` | `NSetText` | You want the value committed directly to a specific element without a paste step. |
| `NSetText` | `NTypeInto` | The target requires real keystrokes (e.g. fires onkeypress handlers, has masking, or rejects programmatic value assignment). |
| `NSetText` | `NSetClipboard` | You will paste the value yourself and just need to load the clipboard, without writing into a specific element. |
| `NTakeScreenshot` | `NHighlight` | You only need an ephemeral on-screen indicator for debugging, not a saved image. |
| `NTakeScreenshot` | `NHover` | You need to trigger the application's hover behavior rather than capture the screen. |
| `NTypeInto` | `NSetText` | The field already accepts a direct value-set and you do not need keystroke-level fidelity (faster, no focus needed). |
| `NTypeInto` | `NSetClipboard` | The value is large or contains characters the target does not accept via keystrokes; paste from the clipboard instead. |
| `PathExists` | `CreateDirectory` | You actually want to ensure the folder exists, not merely test it. |
| `ReadCell` | `ReadRange` | You need more than a single cell; ReadRange returns a rectangular block as a DataTable. |
| `ReadCell` | `ReadCellValueX` | The workflow uses the modern Excel (X) suite rather than the classic Workbook activities. |
| `ReadCsvFile` | `ReadTextFile` | The file is plain text without delimited columns; you want the raw string, not a parsed DataTable. |
| `ReadPDFText` | `ReadPDFWithOCR` | The PDF is scanned or image-based and has no embedded text layer. |
| `ReadPDFWithOCR` | `ReadPDFText` | The PDF already has an embedded text layer; ReadPDFText is faster and lossless. |
| `ReadRange` | `ReadRangeX` | The workflow uses the modern Modern Excel (X) suite with Use Excel File scope rather than the classic ExcelApplicationScope. |
| `ReadRange` | `ReadCell` | You only need a single cell, not a rectangular range. |
| `ReadRangeX` | `ReadRange` | You are inside a classic ExcelApplicationScope/Workbook scope rather than a modern Use Excel File context. |
| `ReadRangeX` | `ReadCellValueX` | You only need the value of one cell; ReadRangeX is for rectangular ranges. |
| `ReadRangeX` | `ExcelReadColumn` | You want every cell in one column without specifying the row count. |
| `ReadTextFile` | `ReadCsvFile` | The file is a delimited CSV/TSV that should be parsed into a DataTable rather than handed back as a string. |
| `Rethrow` | `Throw` | You want to raise a new exception (different type or message), not forward the one you caught. |
| `RetryScope` | `TryCatch` | On failure you want a different code path (log, fall back, swallow) rather than another attempt. |
| `SendExchangeMail` | `SendOutlookMail` | There is a logged-in Outlook desktop client; let it deliver the mail so it follows local Outlook rules. |
| `SendExchangeMail` | `SendMail` | You do not have Exchange credentials and only need to push through a generic SMTP relay. |
| `SendMail` | `SendOutlookMail` | There is a logged-in Outlook desktop client and you want messages to be sent through it (so they land in Sent Items, follow Outlook rules, etc.). |
| `SendMail` | `SendExchangeMail` | You can authenticate to Exchange Web Services directly rather than relying on a generic SMTP relay. |
| `SendOutlookMail` | `SendExchangeMail` | There is no locally-installed Outlook profile and you must talk to Exchange Web Services directly. |
| `SendOutlookMail` | `SendMail` | You only have a generic SMTP relay (no Outlook client, no Exchange credentials). |
| `StateMachine` | `Flowchart` | The graph is a one-shot decision tree with no persistent states; Flowchart is lighter weight than a state machine. |
| `Switch` | `If` | You only need a binary true/false branch on a boolean expression. |
| `Switch` | `IfElseIfV2` | The branches depend on different boolean expressions (not values of one expression) and you want labeled else-if clauses. |
| `Throw` | `Rethrow` | You are inside a Catch block and want to forward the original exception unchanged rather than construct a new one. |
| `TryCatch` | `RetryScope` | The failure is a transient external problem and the right response is to retry the same activity, not to handle a different code path. |
| `TryCatch` | `Throw` | You actually want to raise a new exception, not catch one. |
| `WriteCell` | `WriteRange` | You are writing a DataTable or multiple cells, not a single cell. |
| `WriteCell` | `WriteCellX` | The workflow uses the modern Excel (X) suite rather than classic Workbook activities. |
| `WriteCellX` | `WriteCell` | You are using the classic Workbook activities rather than the modern Excel (X) suite. |
| `WriteCellX` | `WriteRangeX` | You are writing a DataTable or multiple cells rather than a single value. |
| `WriteRange` | `WriteRangeX` | The workflow uses the modern Excel (X) suite with Use Excel File scope rather than classic Workbook scope. |
| `WriteRange` | `WriteCell` | You are writing a single value, not a DataTable's worth of rows. |
| `WriteRange` | `AppendRange` | The destination already has data and you want to append below it instead of overwriting from the start cell. |
| `WriteRangeX` | `WriteRange` | You are using the classic ExcelApplicationScope/Workbook scope, not a modern Use Excel File scope. |
| `WriteRangeX` | `WriteCellX` | You are writing a single cell value rather than a DataTable. |
| `WriteRangeX` | `AppendRangeX` | You want to append below the existing data instead of overwriting from the start cell. |
| `WriteTextFile` | `AppendWriteCsvFile` | The data is tabular (DataTable) and needs delimiter-aware CSV formatting. |
| `WriteTextFile` | `ReadTextFile` | You actually want to load text from disk, not write it. |


---
_Index footer:_ 463 activities, 16 categories, 18 unsupported, 0 review-pending. Regenerate with `python uipath-core/scripts/generate_routing_index.py`.

