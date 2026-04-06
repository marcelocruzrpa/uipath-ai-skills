# uipath-tasks Battle Tests

Battle test scenarios for validating the `uipath-tasks` skill. Each scenario tests form task creation, persistence constraints, and form.io schema design.

**Prerequisites:**
- `uipath-core` skill loaded (required dependency)
- Orchestrator with Tasks enabled (for runtime validation, optional)
- UiPath Studio for XAML validation

**How to run:** Give each scenario prompt to Claude Code with both `uipath-core` and `uipath-tasks` skills loaded. Grade against pass criteria.

**Universal pass criteria (all scenarios):**
1. XAML generated via `generate_workflow.py` with `create_form_task` / `wait_for_form_task` gen values (Rule G-1)
2. Persistence activities (`WaitForFormTaskAndResume`, `CreateFormTask`+wait) in Main.xaml ONLY (Rule A-2, Lint 26)
3. Both NuGet packages present: `UiPath.Persistence.Activities` AND `UiPath.FormActivityLibrary`
4. `supportsPersistence: true` in project.json `runtimeOptions`
5. FormData keys match form.io component keys
6. Submit button present in form schema
7. `CreateFormTask` wrapped in RetryScope (A-11)
8. `validate_xaml --lint` passes with 0 errors

---

## Scenario 1: Simple Approval Form

**PDD:**

> **Process Name:** Invoice Approval
>
> **Description:** The robot creates an Tasks task for a manager to approve or reject an invoice. The form displays invoice details (read-only) and captures the manager's decision and comments.
>
> **Form Fields:**
> - Invoice Number (read-only, pre-populated)
> - Vendor Name (read-only, pre-populated)
> - Amount (read-only, pre-populated)
> - Decision (dropdown: Approve / Reject / Escalate)
> - Comments (text area, optional)
>
> **Steps:**
> 1. Create the form task in Tasks
> 2. Wait for the manager to complete the task
> 3. Read the decision and comments
> 4. If Approved: proceed to payment
> 5. If Rejected: log reason and mark as rejected
> 6. If Escalated: create a new task for senior management

**What the agent should do:**
- Scaffold a project with Persistence.Activities + FormActivityLibrary
- Form.io schema with: 3 textfields (disabled, In direction), 1 select (Out), 1 textarea (Out)
- CreateFormTask + WaitForFormTaskAndResume in Main.xaml
- Business logic AFTER the wait (not in a sub-workflow that contains persistence)

**Validation checkpoints:**
- [ ] `supportsPersistence: true` in project.json
- [ ] Both NuGet packages in dependencies
- [ ] Form.io JSON schema valid — 5 components + submit button
- [ ] Invoice Number, Vendor Name, Amount: `"disabled": true`, FormData direction = In
- [ ] Decision: select component with Approve/Reject/Escalate options, FormData direction = Out
- [ ] Comments: textarea, FormData direction = Out
- [ ] `CreateFormTask` wrapped in RetryScope
- [ ] `WaitForFormTaskAndResume` in Main.xaml (not sub-workflow) — A-2
- [ ] If/IfElseIf on Decision value AFTER the wait
- [ ] Lint 10: Create/Wait count matches (1:1)
- [ ] Lint 26: no persistence in sub-workflows
- [ ] Lint passes with 0 errors

---

## Scenario 2: Editable DataGrid Form (DataTable ↔ Datagrid)

**PDD:**

> **Process Name:** Address Verification
>
> **Description:** The robot scrapes a list of customer addresses, presents them to a human operator in an Tasks form with an editable table, and receives corrected addresses back.
>
> **Form Fields:**
> - Customer Name (read-only column)
> - Street Address (editable)
> - City (editable)
> - State (editable)
> - ZIP Code (editable)
> - Verified checkbox (operator marks each verified row)
>
> **Steps:**
> 1. Scrape addresses from the source system
> 2. Create form task with pre-populated address table
> 3. Wait for operator to correct and verify addresses
> 4. Read back the corrected DataTable
> 5. Update source system with verified addresses

**What the agent should do:**
- Build a DataTable with address columns
- Form.io datagrid component with InOut direction (two-way DataTable binding)
- Datagrid columns map to DataTable columns

**Validation checkpoints:**
- [ ] `BuildDataTable` with columns: CustomerName, StreetAddress, City, State, ZIPCode, Verified
- [ ] Form.io schema: `datagrid` component (not a regular table or HTML)
- [ ] FormData direction = InOut for the datagrid (two-way binding)
- [ ] Datagrid column keys match DataTable column names exactly
- [ ] CustomerName column: `"disabled": true` inside datagrid
- [ ] Verified column: checkbox component inside datagrid
- [ ] Persistence activities in Main.xaml only
- [ ] Lint passes with 0 errors

---

## Scenario 3: Shadow Task Pattern (Non-Blocking Multi-Task)

**PDD:**

> **Process Name:** Parallel Document Review
>
> **Description:** The robot creates multiple Tasks tasks simultaneously — one for each document in a batch — and does NOT wait for each individually. Instead, it creates all tasks, then processes completions as they come in.
>
> **Steps:**
> 1. Read list of documents to review (from Excel)
> 2. For each document: create a form task (title, summary, accept/reject)
> 3. After ALL tasks created: wait for each task to complete
> 4. Collect all decisions
> 5. Generate summary report

**What the agent should do:**
- Shadow task pattern — create all tasks in a loop, store task objects
- Wait in a separate loop (still in Main.xaml — A-2)
- This is an advanced pattern — the agent should reference the shadow task section in `tasks.md`

**Validation checkpoints:**
- [ ] Multiple `CreateFormTask` calls in a ForEach loop
- [ ] Task objects stored in a collection (List or Array)
- [ ] Separate ForEach loop for `WaitForFormTaskAndResume`
- [ ] ALL persistence activities in Main.xaml (A-2)
- [ ] Lint 10: Create count = Wait count (N:N via loops, not literal 1:1)
- [ ] Lint passes with 0 errors

---

## Scenario 4: Form with Conditional Display (Mustache Templates)

**PDD:**

> **Process Name:** Exception Handler
>
> **Description:** The robot creates an Tasks task to handle a processing exception. The form shows the error details, a screenshot of the error, and asks the operator to select a resolution action.
>
> **Form Fields:**
> - Error Summary (read-only HTML with Mustache template showing transaction details)
> - Screenshot (HTML element displaying base64 image, if available)
> - Resolution Action (dropdown: Retry / Skip / Manual Fix / Escalate)
> - Manual Fix Notes (textarea, only needed if "Manual Fix" selected)
>
> **Steps:**
> 1. Capture error details and optional screenshot
> 2. Create form task with error context
> 3. Wait for operator resolution
> 4. Execute chosen resolution

**What the agent should do:**
- Form.io `htmlelement` with Mustache `{{ }}` template syntax for dynamic content
- Conditional display using form.io `conditional` property on Manual Fix Notes
- FormData In direction for error details, Out direction for resolution fields

**Validation checkpoints:**
- [ ] `htmlelement` component with Mustache template (e.g., `{{ data.errorSummary }}`)
- [ ] FormData In direction for error details
- [ ] `select` component for Resolution Action
- [ ] `textarea` for Manual Fix Notes with `"conditional"` property referencing Resolution Action value
- [ ] FormData Out direction for resolution fields
- [ ] Persistence in Main.xaml only
- [ ] Lint passes with 0 errors

---

## Scenario 5: Persistence Constraint Violation (Negative Test)

**Prompt:** "Create a sub-workflow called `Approval_GetDecision.xaml` that creates a form task and waits for the user to respond."

**What the agent should do:**
- Recognize this violates A-2 (persistence in sub-workflow)
- Explain the constraint to the user
- Propose the correct pattern: CreateFormTask + WaitForFormTaskAndResume in Main.xaml, with the sub-workflow handling only pre/post-processing
- If user insists: generate it BUT warn that Lint 26 will fire and runtime will fail

**Validation checkpoints:**
- [ ] Agent identifies the persistence constraint violation
- [ ] Agent explains WHY (bookmark context, serialization to Orchestrator)
- [ ] Agent proposes correct alternative architecture
- [ ] Agent does NOT silently generate the wrong pattern
- [ ] If generated anyway: Lint 26 fires as expected

---

## Scenario 6: External Task Integration (JIRA)

**PDD:**

> **Process Name:** JIRA Issue Escalation
>
> **Description:** The robot detects a critical error in a monitored system, creates a JIRA ticket via API, then creates an Tasks external task linked to the JIRA ticket. The workflow suspends until the JIRA ticket is resolved (completed via Orchestrator API by a webhook). After resolution, the robot reads the resolution details and updates the monitoring system.
>
> **Steps:**
> 1. Detect critical error (read from queue or trigger)
> 2. Create JIRA ticket via HTTP Request (get ticket ID and URL)
> 3. Create external task in Tasks with ticket details
> 4. Wait for external task completion (JIRA webhook calls Orchestrator API)
> 5. Read resolution action and updated task data
> 6. Update monitoring system with resolution status

**What the agent should do:**
- Use `gen_create_external_task()` with task_data containing ticket context
- Use `gen_wait_for_external_task()` to suspend until JIRA resolves
- ExternalTag should reference the JIRA ticket URL
- Wrap CreateExternalTask in RetryScope
- All persistence activities in Main.xaml

**Validation checkpoints:**
- [ ] `CreateExternalTask` used (not CreateFormTask — no form needed)
- [ ] `WaitForExternalTaskAndResume` in Main.xaml only (A-2)
- [ ] `ExternalTag` set to JIRA ticket URL variable
- [ ] `TaskData` dict includes relevant context (ticketId, severity, etc.)
- [ ] `TaskOutput` captured to variable (not {x:Null})
- [ ] `supportsPersistence: true` in project.json
- [ ] `UiPath.Persistence.Activities` in NuGet deps
- [ ] `CreateExternalTask` wrapped in RetryScope
- [ ] Lint AC-12: Create/Wait count matches (1:1)
- [ ] Lint AC-26: no persistence in sub-workflows
- [ ] Lint passes with 0 errors

---

## Scenario 7: Recovery Workflow (GetFormTasks)

**PDD:**

> **Process Name:** Orphaned Task Recovery
>
> **Description:** A companion process that runs on a schedule to find and recover orphaned Tasks tasks. If the main process crashes after creating form tasks but before processing their results, these tasks remain in "Pending" state. The recovery process retrieves them, processes the completed ones, and reassigns stale ones.
>
> **Steps:**
> 1. Get all form tasks with status "Pending" from a specific Action Catalog
> 2. For each retrieved task:
>    a. If task was completed (check status): Complete it programmatically
>    b. If task is stale (created > 48 hours ago): Reassign to fallback user
> 3. Log summary of recovered and reassigned tasks

**What the agent should do:**
- Use `gen_get_form_tasks()` with OData filter for Pending status
- Use `gen_complete_task()` for programmatic completion
- Use `gen_assign_tasks()` for reassignment
- This workflow does NOT need WaitFor*AndResume (it's a batch processor)
- `supportsPersistence` is NOT required (no persistence points)

**Validation checkpoints:**
- [ ] `GetFormTasks` with Filter for Pending status
- [ ] `CompleteTask` with task ID from retrieved tasks
- [ ] `AssignTasks` with user email for stale task reassignment
- [ ] NO `WaitFor*AndResume` activities (this is a batch recovery process)
- [ ] ForEach loop over retrieved tasks
- [ ] Task ID accessed via `lstFormTasks(i).Id.Value` pattern
- [ ] Lint passes with 0 errors

---

## Scenario 8: Programmatic Escalation (Assign + Complete)

**PDD:**

> **Process Name:** Tiered Approval
>
> **Description:** The robot creates a form task for a first-level approver. If the approver selects "Escalate", the robot reassigns the task to a senior manager. If the senior manager doesn't respond within the expected window, the robot programmatically completes the task with a "Timeout" action and sends a notification.
>
> **Steps:**
> 1. Create form task with approval form (Approve / Reject / Escalate)
> 2. Wait for first-level approver
> 3. If "Escalate": Assign task to senior manager, wait again
> 4. If timeout condition met: Complete task programmatically with "Timeout"
> 5. Process final decision

**What the agent should do:**
- Use `gen_create_form_task()` for the approval form
- Use `gen_wait_for_form_task()` for first wait
- Use `gen_assign_tasks()` to reassign on escalation
- Use `gen_complete_task()` for timeout completion
- Mix of Form Task and Task Management generators in one workflow

**Validation checkpoints:**
- [ ] `CreateFormTask` with approval form (Approve/Reject/Escalate dropdown)
- [ ] `WaitForFormTaskAndResume` in Main.xaml (A-2)
- [ ] `AssignTasks` with senior manager email on escalation path
- [ ] `CompleteTask` on timeout path with "Timeout" action
- [ ] If/Switch on task action to branch between Approve/Reject/Escalate
- [ ] Persistence activities in Main.xaml only
- [ ] Task ID pattern: `fdtTaskData.Id.Value` for Assign/Complete
- [ ] Lint passes with 0 errors
