---
name: uipath-action-center
description: >
  Generates UiPath Action Center form task workflows — CreateFormTask with
  form.io schemas, WaitForFormTaskAndResume, FormData bindings (In/Out/InOut),
  datagrid↔DataTable mapping, shadow task patterns, and persistence constraints.
  Self-contained skill with its own generators, lint rules, and scaffold hooks
  loaded via uipath-core's plugin system (plugin_loader.py). Use when the user
  mentions Action Center, form tasks, human-in-the-loop approval, form.io forms,
  or CreateFormTask/WaitForFormTaskAndResume activities.
---

# UiPath Action Center Skill

Generate Action Center form task workflows for human-in-the-loop approval patterns in UiPath.

> **Plugin architecture:** This skill's `extensions/` directory is auto-discovered by uipath-core's `plugin_loader.py`. Generators, lint rules, scaffold hooks, namespaces, and known activities are registered at import time — no manual wiring needed. Core's `generate_workflow.py`, `validate_xaml`, and `scaffold_project.py` query the plugin registries at runtime.

## Extensions (Plugin System)

```
uipath-action-center/
├── SKILL.md
├── references/
│   └── action-center.md
└── extensions/
    ├── __init__.py          ← Registers all AC components with plugin_loader
    ├── generators.py        ← gen_create_form_task, gen_wait_for_form_task
    ├── lint_rules.py        ← lint_action_center (AC-10), lint_formdata_key_mismatch (AC-11), lint_persistence_in_subworkflow (AC-26)
    └── scaffold_hooks.py    ← enable_persistence_support (supportsPersistence flag)
```

**What gets registered:**
- 2 generators: `create_form_task`, `wait_for_form_task`
- 3 lint rules: AC-10 (Create/Wait count mismatch), AC-11 (FormData key mismatch), AC-26 (persistence in sub-workflow)
- 1 scaffold hook: auto-enables `supportsPersistence` when Persistence.Activities is in deps
- 1 namespace: `upaf` → `UiPath.Persistence.Activities.FormTask`
- 2 known activities: `CreateFormTask`, `WaitForFormTaskAndResume` (IdRef + DisplayName checks)

## When To Read Which Reference

| Task | Read |
|---|---|
| Create a form task workflow | `references/action-center.md` → Create Form Task + FormData Bindings |
| Design a form.io form schema | `references/action-center.md` → Form.io Component Reference |
| Wait for human approval / resume | `references/action-center.md` → Wait for Form Task and Resume |
| Shadow task or multi-task patterns | `references/action-center.md` → Shadow Task Pattern |
| Understand persistence constraints | `references/action-center.md` → Prerequisites (Main.xaml constraint) |
| Lint issues on AC workflows | `references/action-center.md` → Validation & Lint Rules |
| Generate XAML for AC activities | Generators in `extensions/generators.py` — auto-loaded by core's `generate_workflow.py` via plugin system |
| Scaffold a project with persistence | Scaffold hook in `extensions/scaffold_hooks.py` — auto-runs via core's `scaffold_project.py` |
| Validate AC workflow XAML | Lint rules in `extensions/lint_rules.py` — auto-run via core's `validate_xaml --lint` |
| Resolve NuGet versions | Use uipath-core's `resolve_nuget.py` for `UiPath.Persistence.Activities` + `UiPath.FormActivityLibrary` |

## Ground Rules

- **AC-1: Always use generators.** Never write CreateFormTask or WaitForFormTaskAndResume XAML by hand. Use `gen_create_form_task()` and `gen_wait_for_form_task()` via JSON specs or Python API (auto-loaded from `extensions/generators.py`).
- **AC-2: Persistence activities MUST stay in Main.xaml.** `WaitForFormTaskAndResume` and `CreateFormTask`+wait pairs are persistence points — they serialize workflow state to Orchestrator. They ONLY work in the entry-point file. AC-26 enforces this.
- **AC-3: Both NuGet packages are required.** `UiPath.Persistence.Activities` (runtime) AND `UiPath.FormActivityLibrary` (form designer UI). Missing FormActivityLibrary = form designer button does nothing in Studio.
- **AC-4: `supportsPersistence: true`** must be in project.json `runtimeOptions`. Scaffold sets this automatically when Persistence.Activities is in deps.
- **AC-5: FormData keys must match form.io component keys.** A mismatch means data won't bind — the form field stays empty or the output variable stays null. AC-10 validates key presence.
- **AC-6: Always include a submit button** as the last form.io component. Without it the user has no way to complete the task.
- **AC-7: Wrap CreateFormTask in RetryScope.** Orchestrator API calls can transiently fail.

## Capabilities

1. **CreateFormTask** — Action Center task with form.io schema, FormData bindings (In/Out/InOut), storage bucket, task catalog, priority levels
2. **WaitForFormTaskAndResume** — Long-running persistence activity, task action capture, updated FormTaskData output
3. **Form.io schema design** — textfield, textarea, number, select, checkbox, datagrid (DataTable binding), htmlelement (Mustache templates), columns, button
4. **FormData direction bindings** — In (read-only), Out (user-entered), InOut (editable pre-populated, DataTable ↔ datagrid)
5. **Shadow task pattern** — Non-blocking multi-task orchestration
6. **Validation** — AC-10 (Create/Wait count mismatch), AC-11 (FormData key mismatch), AC-26 (persistence in sub-workflow)

## Reference Files

| File | Coverage |
|---|---|
| `references/action-center.md` | Full Action Center reference — prerequisites, CreateFormTask, FormData bindings, form.io components, WaitForFormTaskAndResume, patterns, lint rules, Config keys |

## Quick Generator Reference

| Generator | Activity | Key Args |
|---|---|---|
| `gen_create_form_task()` | CreateFormTask | `task_title_expr`, `task_output_variable`, `form_layout_json`, `id_ref`, `form_data=` |
| `gen_wait_for_form_task()` | WaitForFormTaskAndResume | `task_input_variable`, `id_ref` |

JSON spec `"gen"` values: `create_form_task`, `wait_for_form_task`

## Common Hallucinations

| Wrong | Right | Impact |
|---|---|---|
| `TaskObject=` | `TaskOutput=` (Create) / `TaskInput=` (Wait) | Studio crash — property doesn't exist |
| `EnableDynamicForms="False"` | `EnableDynamicForms="True"` | Form designer button does nothing |
| Persistence activity in sub-workflow | Move to Main.xaml | Runtime error — bookmark context unavailable |
| Missing `UiPath.FormActivityLibrary` | Add explicitly alongside Persistence.Activities | "Install FormActivityLibrary" error in Studio |
| `"supportsPersistence": false` | Set to `true` in project.json runtimeOptions | WaitForFormTaskAndResume fails at runtime |
