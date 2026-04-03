# Action Center Activities (Form Tasks)

CreateFormTask, WaitForFormTaskAndResume — human-in-the-loop form approval via UiPath Action Center.

## Contents
- [Prerequisites](#prerequisites)
- [Create Form Task](#create-form-task)
- [FormData Bindings](#formdata-bindings)
- [Form.io Component Reference](#formio-component-reference)
- [Wait for Form Task and Resume](#wait-for-form-task-and-resume)
- [Typical Action Center Pattern](#typical-action-center-pattern)
- [Shadow Task Pattern](#shadow-task-pattern)

## Prerequisites

**Required NuGet packages (add ALL to project.json via `resolve_nuget.py`):**
- `UiPath.Persistence.Activities` — runtime activities (CreateFormTask, WaitForFormTaskAndResume)
- `UiPath.FormActivityLibrary` (2.0.7+) — form designer UI in Studio. Without this, Studio shows "Install UiPath.FormActivityLibrary (2.0.7 or above) to enable form designer" and the form designer button does nothing. Note: `UiPath.Form.Activities` does NOT transitively install `FormActivityLibrary` — you must add it explicitly.

**project.json requirement:** `"supportsPersistence": true` must be set in `runtimeOptions` for WaitForFormTaskAndResume (long-running activity that persists state). The scaffold script sets this automatically when `UiPath.Persistence.Activities` is in deps. If adding to an existing project manually, ensure this flag is `true`.

**⚠️ Main.xaml constraint:** All wait-and-resume activities (`WaitForFormTaskAndResume`, `CreateFormTask`+wait pairs) are persistence points — the workflow suspends, serializes to the database, and later resumes. **These MUST be in Main.xaml (the entry-point file), never in invoked sub-workflows.** The persistence bookmark context is only available in the entry-point. Move data prep, UI, and API logic into sub-workflows; keep orchestration + persistence activities in Main.

Requires namespace:
```
xmlns:upaf="clr-namespace:UiPath.Persistence.Activities.FormTask;assembly=UiPath.Persistence.Activities"
```

Variable for task object: `<Variable x:TypeArguments="upaf:FormTaskData" Name="taskObj" />`

## Create Form Task

Creates an Action Center task with a form.io-based form layout that a human user can fill in.

→ **Use `gen_create_form_task()`** from this skill's `extensions/generators.py` (auto-loaded via uipath-core's plugin system) — generates correct XAML deterministically.

### Generator JSON Spec
```json
{
  "gen": "create_form_task",
  "args": {
    "task_title_expr": "String.Format(&quot;DataReview_{0}_{1}&quot;, FileName, DateTime.now.ToString(&quot;ddMMyyyyhhmmss&quot;))",
    "task_output_variable": "taskObj",
    "form_layout_json": "{\"components\":[...]}",
    "task_catalog_expr": "in_Config(&quot;ActionCatalogName&quot;).ToString",
    "task_priority": "Medium",
    "bucket_name_expr": "in_Config(&quot;DUStorageBucket&quot;).ToString",
    "form_data": {
      "in_dt_records": ["InOut", "sd:DataTable", "dt_recordsForReview"],
      "file_url": ["In", "x:String", "StorageBucketUrl"],
      "businessPartnerName": ["In", "x:String", "strBusinessPartnerName"],
      "fileName": ["In", "x:String", "FileName"]
    }
  }
}
```

### Key Properties
- `FormLayout` — JSON string containing form.io schema (see Form.io Component Reference below)
- `FormLayoutGuid` / `BulkFormLayoutGuid` — GUIDs identifying the form layout in Orchestrator
- `TaskCatalog` — Action Catalog name from Orchestrator (typically from config dictionary)
- `TaskTitle` — VB.NET expression for human-readable task name
- `TaskPriority`: `Low`, `Medium`, `High`, `Critical`
- `TaskOutput` — `upaf:FormTaskData` variable that receives the created task object
- `BucketName` — storage bucket for attached files (optional)
- `GenerateInputFields="True"` — auto-generate input fields from FormData
- `EnableBulkEdit` — feature flag for bulk editing (usually False)
- `EnableDynamicForms="True"` — **MUST be True** to enable the form designer in Studio. When False, the "Open Form Designer" button does nothing even with FormActivityLibrary installed.
- `EnableV2` — V2 form engine (usually False)

**⚠️ WRONG property name (common hallucination):** `TaskObject` does NOT exist. Use `TaskOutput` on CreateFormTask and `TaskInput` on WaitForFormTaskAndResume.

### Generator Python API
```python
from extensions.generators import gen_create_form_task  # auto-loaded via plugin system
gen_create_form_task(
    task_title_expr,        # VB.NET expression for task title
    task_output_variable,   # Variable receiving FormTaskData (no brackets)
    form_layout_json,       # form.io JSON schema string
    id_ref,                 # Unique IdRef suffix
    form_data=None,         # Dict: {"fieldKey": ["direction", "type", "variable"]}
    task_catalog_expr="",   # VB.NET expression for Action Catalog name
    task_priority="Medium", # Low | Medium | High | Critical
    bucket_name_expr="",    # VB.NET expression for storage bucket name
    display_name="Create Form Task",
    indent="    "           # String of spaces (default: 4 spaces)
)
```

## FormData Bindings

The `form_data` dict in `gen_create_form_task()` maps form field keys to workflow variables. Each entry is `"fieldKey": ["direction", "type", "variable"]`:
- `"In"` — workflow → form (read-only, pre-populated)
- `"Out"` — form → workflow (user-entered data returned after submission)
- `"InOut"` — two-way binding (pre-populated AND user-editable, common for DataTable ↔ datagrid)

The generator handles the `{}` XAML escape prefix on `FormLayout` (required because JSON starts with `{` which the XAML parser would interpret as a markup extension).

## Form.io Component Reference

### Component Types
```
textfield   — single-line text input
textarea    — multi-line text input
number      — numeric input
select      — dropdown
checkbox    — boolean checkbox
datagrid    — editable table (maps to DataTable via InOutArgument)
htmlelement — static HTML content (e.g., links, labels)
columns     — layout: side-by-side columns
button      — submit/action button
```

### Basic Component Structure
```json
{
  "label": "Field Label",
  "key": "fieldKey",           // Must match FormData key
  "type": "textfield",
  "input": true,
  "disabled": true,            // Read-only when true
  "tableView": true,
  "validate": {"required": true}  // Optional validation
}
```

**⚠️ Always include a submit button as the last component:**
```json
{"type": "button", "label": "Submit", "key": "submit", "action": "submit", "input": true, "tableView": false}
```

### Datagrid (Editable Table → DataTable)
```json
{
  "label": "Records",
  "key": "in_dt_records",    // Must match InOutArgument key
  "type": "datagrid",
  "input": true,
  "disableAddingRemovingRows": true,
  "reorder": false,
  "hideLabel": true,
  "components": [
    {"label": "Raw Input", "key": "rawInput", "type": "textarea", "disabled": true},
    {"label": "City", "key": "ville", "type": "textfield", "validate": {"required": true}}
  ]
}
```

### HTML Element with Dynamic Data Binding
```json
{
  "label": "HTML",
  "key": "file_url",
  "type": "htmlelement",
  "input": false,
  "content": "<a href=\"{{data.file_url}}\">{{data.fileName}}</a>"
}
```
- `{{data.fieldKey}}` — Mustache template syntax referencing other form field values

## Wait for Form Task and Resume

Suspends the workflow (releases the robot) until a human user submits the form in Action Center.
The workflow resumes automatically after submission.

→ **Use `gen_wait_for_form_task()`** from this skill's `extensions/generators.py` (auto-loaded via uipath-core's plugin system) — generates correct XAML deterministically.

### Generator JSON Spec
```json
{
  "gen": "wait_for_form_task",
  "args": {
    "task_input_variable": "taskObj",
    "task_action_variable": "strTaskAction",
    "task_output_variable": "taskObjUpdated"
  }
}
```

### Key Properties
- `task_input_variable` — the `upaf:FormTaskData` variable from `gen_create_form_task()`'s `task_output_variable`
- `task_action_variable` — (optional) receives the action taken by user (e.g., "submit", "reject")
- `task_output_variable` — (optional) receives updated FormTaskData after submission
- **This is a long-running activity** — the robot is freed while waiting. Workflow state is persisted to Orchestrator.

### Generator Python API
```python
from extensions.generators import gen_wait_for_form_task  # auto-loaded via plugin system
gen_wait_for_form_task(
    task_input_variable,       # FormTaskData variable from CreateFormTask.TaskOutput (no brackets)
    id_ref,                    # Unique IdRef suffix
    task_action_variable="",   # Optional — receives action string
    task_output_variable="",   # Optional — receives updated FormTaskData
    display_name="Wait for Form Task and Resume",
    indent="    "           # String of spaces (default: 4 spaces)
)
```

## Typical Action Center Pattern
```
1. Check if task is needed (If condition)
2. LogMessage → "Creating AC task..."
3. RetryScope → CreateFormTask (resilience against transient failures)
     TaskCatalog = config("ActionCatalogName")
     TaskTitle = String.Format("TaskType_{0}_{1}", docName, timestamp)
     FormData binds workflow variables to form fields
     → [taskObj]
4. WaitForFormTaskAndResume → [taskObj]
     (robot released — human completes form in Action Center)
5. Process user input from InOutArgument/OutArgument variables
```

## Shadow Task Pattern

Advanced pattern from real production workflows:
```
1. Create "shadow" task first (a lightweight form for preliminary data)
2. Create main review task (with full form + datagrid of records)
3. WaitForFormTaskAndResume → main task
4. After main task completes, WaitForFormTaskAndResume → shadow task
   (shadow task was already submitted by user earlier — bot just catches up)
```
This avoids blocking: the shadow task doesn't delay creation of the main task.

## Validation & Lint Rules

These lint rules live in uipath-core's `validate_xaml` and apply to Action Center workflows:

| Lint | Severity | What it checks |
|---|---|---|
| 10 | Warning | CreateFormTask count must match WaitForFormTaskAndResume count |
| 26 | Error | Persistence activities (WaitForFormTaskAndResume) must be in Main.xaml only |

Additional checks within lint 10:
- `TaskOutput="{x:Null}"` — warns that task data won't be captured
- `EnableDynamicForms="False"` — warns that form designer won't work

## Config.xlsx Keys (Typical)

Action Center workflows commonly need these keys in Config.xlsx (Settings sheet):
- `ActionCatalogName` — Action Catalog name in Orchestrator
- `DUStorageBucket` — Document Understanding storage bucket (if using file attachments)
