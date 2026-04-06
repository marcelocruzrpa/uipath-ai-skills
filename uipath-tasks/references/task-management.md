# Task Management Activities

GetFormTasks, CompleteTask, AssignTasks — programmatic task retrieval, completion, and assignment for Tasks workflows.

## Contents
- [Prerequisites](#prerequisites)
- [Get Form Tasks](#get-form-tasks)
- [Complete Task](#complete-task)
- [Assign Tasks](#assign-tasks)
- [Recovery Workflow Pattern](#recovery-workflow-pattern)
- [Escalation Pattern](#escalation-pattern)
- [Task Lifecycle States](#task-lifecycle-states)

## Prerequisites

**Required NuGet package:**
- `UiPath.Persistence.Activities`

**Note:** These activities are NOT persistence points — they make API calls to Orchestrator and return immediately. They can be used in sub-workflows (no Main.xaml constraint). `supportsPersistence` is only required if the same workflow also uses Wait*AndResume activities.

Requires namespaces:
```
xmlns:upaf="clr-namespace:UiPath.Persistence.Activities.FormTask;assembly=UiPath.Persistence.Activities"
xmlns:upat="clr-namespace:UiPath.Persistence.Activities.Tasks;assembly=UiPath.Persistence.Activities"
```

## Get Form Tasks

Retrieves existing form tasks from Orchestrator using OData query parameters. Used for recovery workflows (retrieve tasks created by another process), status monitoring, and cross-process orchestration.

→ **Use `gen_get_form_tasks()`** from this skill's `extensions/generators.py`.

### Generator JSON Spec
```json
{
  "gen": "get_form_tasks",
  "args": {
    "output_variable": "lstFormTasks",
    "filter_expr": "Status eq 'Pending'",
    "task_catalog_name_expr": "in_Config(\"ActionCatalogName\").ToString",
    "top_expr": "100",
    "order_by_expr": "CreationTime desc"
  }
}
```

### Key Properties
- `TaskObjects` — output variable receiving `List(FormTaskData)`
- `Filter` — OData filter expression (e.g., `"Status eq 'Pending'"`, `"Title eq 'Review_Invoice'"`)
- `TaskCatalogName` — filter by Action Catalog (optional)
- `Top` — limit number of results (OData `$top`)
- `Skip` — skip results for pagination (OData `$skip`)
- `OrderBy` — sort order (OData `$orderby`)
- `Expand` / `Select` / `Reference` — advanced OData parameters (usually `{x:Null}`)

### Generator Python API
```python
gen_get_form_tasks(
    output_variable,           # Variable receiving List(FormTaskData) (no brackets)
    id_ref,                    # Unique IdRef suffix (injected)
    filter_expr="",            # OData filter string
    task_catalog_name_expr="", # VB expression for catalog name
    top_expr="",               # OData $top
    skip_expr="",              # OData $skip
    order_by_expr="",          # OData $orderby
    display_name="Get Form Tasks",
    indent="    "
)
```

### OData Filter Examples
```
Status eq 'Pending'                              — pending tasks only
Status eq 'Unassigned'                           — unassigned tasks
Title eq 'Review_Invoice_001'                    — specific task by title
CreationTime gt 2024-01-01T00:00:00Z             — tasks created after date
Status eq 'Pending' and Title startswith 'JIRA'  — combined filters
```

Variable type: `<Variable x:TypeArguments="scg:List(upaf:FormTaskData)" Name="lstFormTasks" />`

## Complete Task

Programmatically completes an Tasks task. Works with any task type (form, external, app). Used for timeout handlers, automated escalation, and bulk operations.

→ **Use `gen_complete_task()`** from this skill's `extensions/generators.py`.

### Generator JSON Spec
```json
{
  "gen": "complete_task",
  "args": {
    "task_id_expr": "lstFormTasks(0).Id.Value",
    "action_expr": "Approved",
    "display_name": "Complete Task"
  }
}
```

### Key Properties
- `TaskId` — VB expression evaluating to the task ID (Long)
- `Action` — completion action string (e.g., `"Completed"`, `"Approved"`, `"Rejected"`)
- `Data` — optional additional data (usually `{x:Null}`)

### Generator Python API
```python
gen_complete_task(
    task_id_expr,          # VB expression for task ID (no brackets)
    id_ref,                # Unique IdRef suffix (injected)
    action_expr="Completed",  # Completion action string
    display_name="Complete Task",
    indent="    "
)
```

### Task ID Access Patterns
```vb
' From GetFormTasks result:
lstFormTasks(0).Id.Value

' From CreateFormTask output:
fdtTaskData.Id.Value

' From a stored variable:
longTaskId
```

## Assign Tasks

Assigns an Tasks task to a specific user or group.

→ **Use `gen_assign_tasks()`** from this skill's `extensions/generators.py`.

### Generator JSON Spec
```json
{
  "gen": "assign_tasks",
  "args": {
    "task_id_expr": "fdtTaskData.Id.Value",
    "user_name_or_email": "manager@company.com",
    "assignment_criteria": "SingleUser",
    "display_name": "Assign to Manager"
  }
}
```

### Key Properties
- `TaskId` — VB expression for task ID
- `UserNameOrEmail` — email or username of the assignee (for SingleUser)
- `TaskAssignmentType` — `"Assign"` (always Assign for new assignments)
- `EnableMultipleAssignments` — whether multiple users can be assigned (default False)
- `AssignmentCriteria` — child element specifying assignment strategy

### Assignment Criteria Options
| Criteria ID | Description | When to use |
|---|---|---|
| `SingleUser` | Assign to a specific user by email | Most common — direct assignment |
| `AllUsersInGroup` | Assign to all users in a group | Group-based routing, any member can pick up |

### Generator Python API
```python
gen_assign_tasks(
    task_id_expr,             # VB expression for task ID (no brackets)
    id_ref,                   # Unique IdRef suffix (injected)
    user_name_or_email="",    # Email/username (for SingleUser)
    group_expr="",            # VB expression for group name (for AllUsersInGroup)
    assignment_criteria="SingleUser",  # "SingleUser" or "AllUsersInGroup"
    display_name="Assign Tasks",
    indent="    "
)
```

## Recovery Workflow Pattern

When a process crashes after creating a form task but before waiting for it, the task is orphaned in Orchestrator. A recovery workflow retrieves and resumes processing:

```
1. GetFormTasks — Filter="Status eq 'Pending' and Title startswith 'Review_'"
     → [lstFormTasks]
2. ForEach task in lstFormTasks:
   a. GetTaskData (or access task properties directly)
   b. Process the task data
   c. CompleteTask — Action="Recovered"
3. LogMessage — "Recovered {lstFormTasks.Count} orphaned tasks"
```

**Key point:** GetFormTasks can be in a sub-workflow. Only WaitFor*AndResume activities must be in Main.xaml.

## Escalation Pattern

When a task exceeds its SLA or needs reassignment:

```
1. CreateFormTask → [fdtTaskData]
2. WaitForFormTaskAndResume → [fdtTaskData]
3. If user action = "Escalate":
   a. AssignTasks — forward to senior reviewer
      TaskId = fdtTaskData.Id.Value
      UserNameOrEmail = "senior.reviewer@company.com"
   b. WaitForFormTaskAndResume → [fdtTaskData] (wait again for senior)
4. Process final decision
```

## Task Lifecycle States

```
Unassigned ──→ Pending ──→ Completed
    │              │
    │              ├── (user submits form)
    │              ├── (external system calls API)
    │              └── (CompleteTask activity)
    │
    └── (AssignTasks activity or auto-assignment)
```

| State | Description |
|---|---|
| `Unassigned` | Task created but not yet assigned to a user |
| `Pending` | Task assigned to user, waiting for completion |
| `Completed` | Task completed (irreversible) |

**Note:** Task completion is irreversible. Once completed, a task cannot be reopened.
