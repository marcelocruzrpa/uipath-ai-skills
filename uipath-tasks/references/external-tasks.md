# External Task Activities

CreateExternalTask, WaitForExternalTaskAndResume — system-in-the-loop tasks resolved by external systems (JIRA, Salesforce, ServiceNow, custom APIs).

## Contents
- [Prerequisites](#prerequisites)
- [Create External Task](#create-external-task)
- [Wait for External Task and Resume](#wait-for-external-task-and-resume)
- [External Task Pattern](#external-task-pattern)
- [TaskData Dictionary](#taskdata-dictionary)
- [Validation & Lint Rules](#validation--lint-rules)

## Prerequisites

**Same as Form Tasks:**
- `UiPath.Persistence.Activities` NuGet package
- `"supportsPersistence": true` in project.json `runtimeOptions`
- `WaitForExternalTaskAndResume` MUST be in Main.xaml only (persistence point)

**Differences from Form Tasks:**
- `UiPath.FormActivityLibrary` is NOT required (no form UI)
- No form.io schema — external tasks have no visual form in Tasks
- Tasks appear in Tasks as "External" type with no user-facing UI
- Completion happens via Orchestrator API from an external system

Requires namespace:
```
xmlns:upae="clr-namespace:UiPath.Persistence.Activities.ExternalTask;assembly=UiPath.Persistence.Activities"
```

Variable for task object: `<Variable x:TypeArguments="upae:ExternalTaskData" Name="edtTaskData" />`

## Create External Task

Creates an Tasks task that will be completed by an external system via the Orchestrator Tasks API.

→ **Use `gen_create_external_task()`** from this skill's `extensions/generators.py` (auto-loaded via plugin system).

### Generator JSON Spec
```json
{
  "gen": "create_external_task",
  "args": {
    "task_title_expr": "String.Format(\"JIRA_{0}\", strTicketId)",
    "task_output_variable": "edtTaskData",
    "task_priority": "High",
    "external_tag_expr": "strJiraTicketUrl",
    "task_catalog_expr": "in_Config(\"ActionCatalogName\").ToString",
    "task_data": {
      "ticketId": "strTicketId",
      "severity": "strSeverity"
    }
  }
}
```

### Key Properties
- `TaskTitle` — VB.NET expression for human-readable task name
- `TaskOutput` — `upae:ExternalTaskData` variable that receives the created task
- `TaskPriority`: `Low`, `Medium`, `High`, `Critical`
- `TaskCatalog` — Action Catalog name (optional, from config)
- `ExternalTag` — Tag for the external system reference (e.g., JIRA ticket URL)
- `Labels` — Optional labels for categorization
- `TaskData` — Dictionary of key-value pairs sent to the external system

**⚠️ WRONG property names (common hallucinations):**
- `TaskObject` does NOT exist — use `TaskOutput`
- `FormLayout` / `FormData` do NOT exist on external tasks — use `TaskData` dict

### Generator Python API
```python
gen_create_external_task(
    task_title_expr,        # VB expression for task title (no brackets)
    task_output_variable,   # Variable receiving ExternalTaskData (no brackets)
    id_ref,                 # Unique IdRef suffix (injected by dispatcher)
    task_data=None,         # Dict: {"key": "variable_name"} — optional
    task_catalog_expr="",   # VB expression for catalog name
    task_priority="Medium", # Low | Medium | High | Critical
    external_tag_expr="",   # VB expression for external tag
    display_name="Create External Task",
    indent="    "
)
```

## Wait for External Task and Resume

Suspends the workflow until the external system completes the task via the Orchestrator Tasks API (`POST /tasks/GenericTasks/CompleteTask`).

→ **Use `gen_wait_for_external_task()`** from this skill's `extensions/generators.py`.

### Generator JSON Spec
```json
{
  "gen": "wait_for_external_task",
  "args": {
    "task_input_variable": "edtTaskData",
    "task_action_variable": "strTaskAction",
    "task_output_variable": "edtUpdatedTask"
  }
}
```

### Key Properties
- `TaskInput` — `upae:ExternalTaskData` variable from `CreateExternalTask.TaskOutput`
- `TaskAction` — (optional) receives the action string from the external system
- `TaskOutput` — (optional) receives updated `ExternalTaskData` with completion data
- **This is a long-running activity** — the robot is freed while waiting

### Generator Python API
```python
gen_wait_for_external_task(
    task_input_variable,       # ExternalTaskData from CreateExternalTask.TaskOutput (no brackets)
    id_ref,                    # Unique IdRef suffix (injected by dispatcher)
    task_action_variable="",   # Optional — receives action string
    task_output_variable="",   # Optional — receives updated ExternalTaskData
    display_name="Wait for External Task and Resume",
    indent="    "
)
```

## External Task Pattern

```
1. Prepare external system data (ticket ID, severity, context)
2. LogMessage → "Creating external task for JIRA..."
3. RetryScope → CreateExternalTask
     TaskTitle = String.Format("JIRA_{0}", strTicketId)
     TaskData = {ticketId: strTicketId, severity: strSeverity}
     ExternalTag = strJiraTicketUrl
     → [edtTaskData]
4. (Optional) Send notification to external system with task ID
     e.g., POST to JIRA webhook with edtTaskData.Id
5. WaitForExternalTaskAndResume → [edtTaskData]
     (robot released — external system completes via API)
6. Process completion data from edtUpdatedTask
```

### How External Systems Complete Tasks

The external system calls the Orchestrator API:
```
POST /odata/Tasks/UiPath.Server.Configuration.OData.CompleteTask
{
    "taskId": <task_id>,
    "action": "Completed",
    "comment": "Resolved in JIRA"
}
```

The task ID is available from `ExternalTaskData.Id` after creation.

## TaskData Dictionary

Unlike Form Tasks (which use FormData with In/Out/InOut bindings), External Tasks use a simple `Dictionary(Of String, Argument)`:

```json
"task_data": {
  "ticketId": "strTicketId",
  "severity": "strSeverity",
  "description": "strDescription"
}
```

Each entry becomes an `InArgument` in the dictionary. The external system receives these key-value pairs and can include response data when completing the task.

## Validation & Lint Rules

| Lint | Severity | What it checks |
|---|---|---|
| AC-12 | Warning | CreateExternalTask count should match WaitForExternalTaskAndResume count |
| AC-26 | Error | WaitForExternalTaskAndResume must be in Main.xaml only |

Additional checks within AC-12:
- `TaskOutput="{x:Null}"` — warns that task data won't be captured

## Config.xlsx Keys (Typical)

- `ActionCatalogName` — Action Catalog name in Orchestrator
- `ExternalSystemWebhookUrl` — URL to notify the external system of new tasks
