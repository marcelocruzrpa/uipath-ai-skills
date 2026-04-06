# UiPath Skill Guide

Task-specific workflows and examples. The core rules are in `SKILL.md`. Detailed reference content has been split into focused files — read only the one you need.

## Reference Files

| Task | Read |
|---|---|
| Template selection, NuGet mapping, scaffolding, project generation checklist | `scaffolding.md` |
| Naming conventions, decomposition rules, Login/Launch pattern, Init/Close, UiElement chain | `decomposition.md` |
| Object Repository, Workflow Generation CLI (JSON specs), Activity Generators (94 core + plugin extensions) | `generation.md` |
| Playwright MCP inspection, desktop inspection (PowerShell), selector mapping | `ui-inspection.md` |

## Examples

### Example 1: "Create a UiPath workflow that reads an Excel file and logs each row"

1. Write a JSON spec using `read_range`, `foreach_row`, and `log_message` generators:
```json
{"class_name": "Excel_ReadAndLog",
 "arguments": [{"name": "in_strFilePath", "direction": "In", "type": "String"}],
 "variables": [{"name": "dt_Data", "type": "DataTable"}],
 "activities": [
   {"gen": "log_message", "args": {"message_expr": "\"[START] Excel_ReadAndLog\""}},
   {"gen": "read_range", "args": {"workbook_path_variable": "in_strFilePath", "output_variable": "dt_Data", "sheet_name": "\"Sheet1\"", "range": "\"\""}},
   {"gen": "foreach_row", "args": {"datatable_variable": "dt_Data", "row_variable": "row"},
    "children": [
      {"gen": "log_message", "args": {"message_expr": "\"Row: \" & row(0).ToString"}}
    ]},
   {"gen": "log_message", "args": {"message_expr": "\"[END] Excel_ReadAndLog\""}}
]}
```
2. Save spec to disk → `python3 scripts/generate_workflow.py spec.json Excel_ReadAndLog.xaml` (Rules G-1, G-2)
3. Validate: `python3 scripts/validate_xaml Excel_ReadAndLog.xaml --lint`

**Output:** Single `.xaml` file

### Example 2: "Scaffold a performer REFramework project for processing invoices"

1. Run `scaffold_project.py --name "InvoiceProcessor" --variant performer --output /path`
2. Tell user: edit `Framework/Process.xaml` for invoice logic, set `OrchestratorQueueName` in `Data/Config.xlsx`
3. Validate project

**Output:** Full project directory

### Example 3: "Write the VB.NET expression to filter a DataTable where Amount > 1000"

1. Read `expr-datatable.md` → LINQ on DataTable section
2. Answer directly — no XAML needed:
```vb
(From row In dt_Input.AsEnumerable()
Where CDbl(row("Amount")) > 1000
Select row).CopyToDataTable()
```

### Example 4: "Create a workflow that calls an API with OAuth and retries on failure"

1. Read `xaml-orchestrator.md` → HTTP Request section for OAuth property reference
2. Write a JSON spec using `getrobotcredential`, `net_http_request`, and `deserialize_json` generators:
```json
{"class_name": "Api_FetchData",
 "arguments": [
   {"name": "in_strCredentialAssetName", "direction": "In", "type": "String"},
   {"name": "in_strApiUrl", "direction": "In", "type": "String"},
   {"name": "out_joResponse", "direction": "Out", "type": "Object"}
 ],
 "variables": [
   {"name": "strUsername", "type": "String"},
   {"name": "secstrPassword", "type": "SecureString"},
   {"name": "strResponse", "type": "String"}
 ],
 "activities": [
   {"gen": "log_message", "args": {"message_expr": "\"[START] Api_FetchData\""}},
   {"gen": "retryscope", "children": [
     {"gen": "getrobotcredential", "args": {"asset_name_variable": "in_strCredentialAssetName",
      "username_variable": "strUsername", "password_variable": "secstrPassword"}}
   ]},
   {"gen": "net_http_request", "args": {"url_variable": "in_strApiUrl", "method": "GET",
    "response_variable": "strResponse", "retry_count": 3}},
   {"gen": "deserialize_json", "args": {"json_string_variable": "strResponse", "output_variable": "out_joResponse"}},
   {"gen": "log_message", "args": {"message_expr": "\"[END] Api_FetchData\""}}
 ]}
```
3. Save spec to disk → `python3 scripts/generate_workflow.py spec.json Api_FetchData.xaml` (Rules G-1, G-2)
4. Validate: `python3 scripts/validate_xaml Api_FetchData.xaml --lint`

### Example 5: "Create an Tasks task with a form for address parsing"

1. Read **uipath-tasks** skill → `references/tasks.md`
2. Copy CreateFormTask pattern, define form.io JSON schema with datagrid for addresses
3. Add WaitForFormTaskAndResume after creation
4. Bind DataTable via InOutArgument for two-way data flow

### Example 6: User uploads a .xaml file and asks "Fix this workflow"

1. Run `validate_xaml` on uploaded file — report errors
2. Read the file to understand structure
3. For fixes: copy correct activity patterns from the relevant `xaml-*.md` reference file
4. Preserve user's existing structure — add/fix only what's needed
5. Validate modified file

### Anti-Example: What NOT To Do

**WRONG:** Writing XAML from memory — e.g., a bare `<Activity><Sequence><Assign .../></Sequence></Activity>` without xmlns declarations, IdRefs, HintSize, ViewState, or namespace/assembly blocks. This fails immediately.

**CORRECT:** Use `generate_workflow.py` with a JSON spec, or copy from a golden template (e.g. `Browser_NavigateToUrl.xaml`), keep ALL boilerplate intact, only modify business logic.

**Do NOT:** Generate xmlns blocks from memory. Rewrite the user's entire file when they ask for a small change. Generate a full XAML when the user only needs an expression.

### Example 7: "Build a browser automation for the target web application login and work item processing"

**Phase 1:** Plan decomposition → WebApp_Launch, Browser_NavigateToUrl (Utils), WebApp_GetWorkItems, WebApp_UpdateRecord, App_Close (Utils)

**Phase 2:** Inspect with Playwright MCP (this phase is MANDATORY before generating any XAML — see `ui-inspection.md`):
```
1. Check available tools → find playwright_navigate, playwright_snapshot
2. Navigate to https://webapp-example.com → redirects to login page
3. Snapshot login page → find: input#email, input#password, button#loginButton
4. Map to UiPath:
   - ScopeSelectorArgument: <html app='msedge.exe' title='the target web application - Login' />
   - Email field:    <webctrl id='email' tag='INPUT' />
   - Password field: <webctrl id='password' tag='INPUT' type='password' />
   - Login button:   <webctrl id='loginButton' tag='BUTTON' />
5. Ask user: "I've reached the WebApp login page. Could you first enter wrong credentials
      and click Login so I can capture the error message? Then log in with your real credentials.
      I'll wait here — I cannot and will not type anything into the login form."
6. User enters bad credentials → error appears → snapshot → get error element selector
      If no error or user can't simulate: use placeholder selector with TODO comment
7. User logs in correctly → confirms → now on dashboard/home page
8. Click "Work Items" menu → lands on /work-items → copy URL → navigate directly →
   page loads OK → URL is stable → use NGoToUrl in workflow
9. Snapshot work items page → record selectors for table rows, links
10. Click work item "WI-123" → lands on /work-item/WI-123 → copy URL → navigate directly →
   page loads OK → URL pattern /work-item/{WIID} is stable → use NGoToUrl with dynamic URL
11. Snapshot detail page → record selectors for form fields, status dropdown, update button
```

**Phase 3:** Generate XAML files **ONE AT A TIME, sequentially** — never in parallel. For each file: (a) write JSON spec → `python3 scripts/generate_workflow.py spec.json output.xaml`, (b) insert real selectors from Phase 2, (c) **validate immediately:** `python3 scripts/validate_xaml path/to/file.xaml --lint`, (d) fix all errors before starting the next file. Use `NGoToUrl` for all page navigation (URLs confirmed stable in Phase 2). Use NClick only for in-page actions (buttons, form submits).
**Phase 4:** Wire Main.xaml — validate immediately after.
**Phase 5:** Final project-level validation: `python3 scripts/validate_xaml <project_folder> --lint` (catches cross-file issues: argument mismatches, Config.xlsx sync, Init/Close symmetry).
