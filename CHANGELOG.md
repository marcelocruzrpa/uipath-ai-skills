# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [1.2.1] - 2026-04-25

### Added

**uipath-core — version-band-aware lints and scaffolding** (branch `feature/version-compatibility-v2`)
- `version_band.py` single-source versioning model — `ProjectVersion`, band parsing, year-based vs independent package classification, band-to-profile-version mapping
- Lint 120 (error): Version="V5"+ attributes on UiX activities are invalid below band 25
- Lint 121 (error): HealingAgentBehavior / ClipboardMode attributes don't exist below band 25 (introduced in 25.10+)
- Lint 122 (error): cross-band `Version` attribute mismatch — activity Version attr does not match the target band's profile
- Lints 120-122 are opt-in: they fire only when `project.json` contains an explicit `"versionBand"` field
- `scaffold_project.py` auto-stamps `versionBand` when year-based dependencies are supplied via `--deps` — the band is derived from the resolved deps by `derive_band_from_deps()` in `version_band.py` (returns the max year-based band present, falls back to `None` when no year-based dep is resolved). Keeps the opt-in contract for bare scaffolds while closing the gap where downstream lints 120-122 stayed dormant on every freshly scaffolded project.
- Project-level warning: whenever a declared `versionBand` + a dependency in that band lacks a usable profile JSON, the validator warns that lint 122 will silently no-op for that package until the profile is harvested
- **Plugin API v2 in `plugin_loader.py`** — new `register_version_profile` / `register_band_profile_mapping` / `get_version_profiles` / `get_band_profile_mappings`; `PLUGIN_API_VERSION` bumped 1 → 2. Plugins can now ship per-band activity profiles that lint 122 enforces. `uipath-tasks` registers `UiPath.Persistence.Activities/1.4` for bands 25 and 26.
- **`generate_workflow.py` dispatcher fall-through** — the dispatcher now tries `gen_from_annotation` before raising `Unknown generator`, so activities described purely in `references/annotations/*.json` can be emitted without a hand-written `gen_*` function. `WizardOnlyActivityError`, `MissingScopeError`, and `ReviewNeededError` are wrapped as `ValueError("Cannot generate ...")`.
- Version profiles for UIAutomation 25.10, System 25.10 and 26.2, Excel 3.4, Mail 2.8, Testing 25.10 (uipath-core) and Persistence 1.4 (uipath-tasks)
- Annotation corpus (`references/annotations/*.json`) — 202 activity entries across 16 annotation files; data-driven generator engine in `generate_activities/_data_driven.py`
- Studio harvest tooling under `scripts/tools/`: `harvest_studio_xaml.py`, `compare_to_ground_truth.py`, `validate_with_studio.py`, `battle_test_activities.py`, `battle_test_studio.py`, `annotate_profile_schema.py`, `backfill_annotations.py`, `backfill_profile_templates.py`

### Fixed

- `WizardOnlyActivityError` raised by `gen_from_annotation` for wizard-only stubs instead of bare `KeyError('element_tag')` — callers can now distinguish "activity not found" from "activity exists but requires Studio wizard"

### Security

- `defusedxml` safe-fallback pattern applied across the new harvest/backfill tooling (`backfill_annotations.py`, `backfill_profile_templates.py`, `compare_to_ground_truth.py`, `battle_test_activities.py`) for defense-in-depth against XXE/billion-laughs in XAML parsing (consistent with `validate_xaml/_structural.py`)

### Internal

- Lint test suite expanded with 8 new `*_project_version_compat*` fixtures (105 fixtures total under `uipath-core/assets/lint-test-cases/`)
- `pytest uipath-core/tests/` now reports **157 passed** (no skips, no xfails)

---

## [1.2.0] - 2026-04-21

### Added

**uipath-tasks — local form file emission** (PR #18, #19, #20)
- `gen_create_form_task` accepts new `dynamic_form_path` and `project_root` kwargs. When set, the generator emits `DynamicFormPath="<path>"` instead of `{x:Null}` and writes the schema to `<project_root>/<path>` in UiPath's external-file shape — `{"id": "<guid>", "form": [...]}` — per `form-tasks.md`
- When `project_root` is set but `dynamic_form_path` is empty, the generator derives `Forms/<sanitized-display-name>.json` automatically (falls back to `id_ref` when display name is the default)
- New exported helper `form_layout_to_external_file()` converts form.io `{"components": [...]}` to the UiPath shape for callers that write files themselves
- `generate_workflow.py` now threads `--project-dir` through to plugin generators via a new `_PROJECT_ROOT` module global forwarded in `_auto_dispatch`; core generators without a `project_root` parameter are unaffected because `_auto_dispatch` filters kwargs by signature

**uipath-tasks — new lint rules** (PRs #15, #17, #18)
- **AC-27** (error): `Wait*AndResume` nested in `ForEach` / `ForEachRow` / `RetryScope` / `TryCatch` / `Parallel` / `Pick` / `While` / `DoWhile`. Studio rejects with "the scope does not offer support for it". Complements file-level AC-26 with intra-file ancestor walking (commit 605f59e, fixes #14)
- **AC-28** (warn): `CreateFormTask` / `CreateExternalTask` missing or `{x:Null}` `FolderPath` — runtime error 1101
- **AC-29** (error): `<ui:InvokeMethod>` belongs in the default activities namespace, not `ui:`; Studio refuses to load the XAML
- **AC-30** (warn): `<InvokeMethod TargetObject="[expr]">` attribute form — `TargetObject` needs element form with typed `InArgument`
- **AC-31** (warn): `fdt*.Data("key")` / `edt*.Data("key")` / `FormTaskData*.Data(...)` default-indexer access — late-bound, fails under Option Strict On (BC30574). Recommends `Title` property or typed `OutArgument` variable (AC-28/29/30/31 from commit 937ca74, refs #16)
- **AC-32** (error): `DynamicFormPath` points to a file that is missing, unparseable, has wrong root key (`components` / bare array / `display: "form"` instead of `form`), or lacks the required `id`
- **AC-33** (warn): inline `FormLayout` exceeds ~500 chars of raw JSON while `DynamicFormPath` is null — large inline schemas aren't editable from Studio's form designer and poison XAML diffs (AC-32/33 from commit 87084e0)

**Documentation — form-tasks reference expansion** (commit 47c9215)
- `references/form-tasks.md` — new subsections on external form file schema (DynamicFormPath), typed output (`FormTaskData.Title` and typed `OutArgument` over `.Data("key")`), Orchestrator folder requirement, and InvokeMethod placement and element-form rules
- `references/external-tasks.md` — mirrored FolderPath and typed-output notes; Shadow Task Pattern example updated to correct InvokeMethod namespace and element form

### Fixed

- `uipath-core` Image type mapping (PR #13, #12) — `TYPE_MAP_BASE` gained `"Image": "ui:Image"`. Variables declared with `type: "Image"` (e.g. `img_Screenshot`) were previously emitted as bare `x:TypeArguments="Image"` and Studio failed with "Cannot create unknown type ... Image". The fix cascades to the variable emitter, argument normalizer, and spec validator via `TYPE_MAP_BASE`

### Internal

- New cross-plugin test file `uipath-core/scripts/test_cross_plugin.py` covers both the subprocess emit path (asserts sidecar JSON shape plus XAML attribute) and the no-project-root inline fallback for local form-file emission
- Lint test suite expanded to 92/92 with new fixtures under `uipath-tasks/assets/lint-test-cases/` covering AC-27 through AC-33

---

## [1.1.0] - 2026-04-14

### Added

**uipath-tasks plugin** (PR #11)
- New plugin covering Form Tasks, External Tasks, and Task Management — for human-in-the-loop, system-in-the-loop, and recovery patterns
- Form Task generators: `CreateFormTask`, `WaitForFormTaskAndResume`, `GetFormTasks`
- External Task generators: `CreateExternalTask`, `WaitForExternalTaskAndResume`
- Task Management generators: `CompleteTask`, `AssignTasks`
- Form.io schema design — textfield, textarea, number, select, checkbox, datagrid (DataTable binding), htmlelement (Mustache templates), columns, button
- FormData direction bindings — In (read-only), Out (user-entered), InOut (editable pre-populated, DataTable ↔ datagrid)
- Shadow Task pattern for non-blocking multi-task orchestration
- Lint rules — AC-10 (Form Create/Wait mismatch), AC-11 (FormData key mismatch), AC-12 (External Create/Wait mismatch), AC-26 (persistence activities must stay in Main.xaml)
- Scaffold hook auto-enables `supportsPersistence: true` when `UiPath.Persistence.Activities` is in project dependencies
- Battle test scenarios in `uipath-tasks/evals/tasks-battle-tests.md` with `ac` grader suite
- Registered in `.claude-plugin/marketplace.json` for Claude Code marketplace install

**Plugin loader extensions** (commits fe1454e, e598c5d)
- New registration types in `plugin_loader.py`: `register_known_activities`, `register_key_activities`, `register_hallucination_pattern`, `register_common_packages`, `register_type_mapping`, `register_variable_prefix`, `register_battle_test_grader`, `register_test_spec`, `register_lint_test_fixture`
- Plugin-registered namespaces and known activities are merged into `validate_xaml`'s `PREFIX_TO_XMLNS` and `NEEDS_IDREF` tables at load time
- xmlns validation and namespace detection extended to recognize plugin-registered prefixes

**Documentation**
- Contributors section in README with auto-generated avatar grid (commit 500ed80)
- README rewritten — qualitative descriptions instead of hardcoded counts; fixed CLI paths (`uipath-core/scripts/...`); new Plugin Architecture and Plugin Development sections; complete walkthrough video; "Using the skill" guide

### Changed

- Action Center-specific code moved out of `uipath-core` into the `uipath-tasks` plugin (commit 0dca38c)
- `uipath-action-center` renamed to `uipath-tasks` with scope expanded to include external tasks (commit 41ebaf0)

### Fixed

- `validate_snippet()` now rejects file paths and non-XAML input that previously could slip through (PR #4)
- `modify_framework` now rejects snippets containing top-level `ViewState` that produced broken framework wiring (PR #6)
- Generator output prevents Studio BC36915 compile error on `AddDataRow` with mixed-type rows (PR #10, commit 4bc31fd)
- Battle-test cleanup — xmlns pruning, plugin variable prefixes, HintSize emission on plugin generators, Assign type inference (PR #10, commit 37c6296)
- HITL battle test findings in `uipath-tasks` (commit 26d6e7c, issue #7)
- Critical issues found in version-band review (PR #2)

### Internal

- Local OMC state directory added to `.gitignore` (commit 730c11c)

---

## [1.0.0] - 2026-03-25

Initial release of **uipath-core** — the foundational skill for generating production-quality UiPath Studio projects from natural language.

### Added

**XAML Generation**
- Deterministic Python generators across UI automation, control flow, data operations, error handling, integrations, orchestrator, file system, HTTP/JSON, invoke, logging, dialogs, navigation, and application card
- JSON spec intermediate format — LLMs write JSON, generators produce structurally correct XAML
- Generators anchored to real UiPath Studio 24.10 exports
- Enum validation, namespace locking, and child element enforcement on every generated activity

**Validation Pipeline**
- Lint rules targeting LLM hallucination patterns in UiPath XAML
- Severity tiers — ERROR (Studio crash), WARN (runtime failure), INFO (best practice)
- Auto-fix support for common issues (`--fix` flag)
- Catches hallucinated properties, invalid enum values, missing xmlns declarations, placeholder paths, wrong child elements

**Project Scaffolding**
- Three project variants — simple sequence, REFramework dispatcher, REFramework performer
- Config.xlsx generation with three-sheet structure (Settings, Constants, Assets)
- Customized GetTransactionData for dispatcher (DataTable row indexing) vs performer (queue item)

**Framework Wiring**
- `modify_framework.py` — insert InvokeWorkflowFile calls, inject variables, replace scaffold markers, wire UiElement argument chains, replace placeholder expressions
- `generate_object_repository.py` — build `.objects/` tree from captured selectors
- `resolve_nuget.py` — resolve real NuGet package versions against UiPath feed, add/update deps in `project.json`
- `config_xlsx_manager.py` — add, list, and validate Config.xlsx keys against XAML references

**UI Inspection**
- Desktop inspection via PowerShell (`inspect-ui-tree.ps1`) — UIA tree capture for WPF, Win32, WinForms, DirectUI, UWP
- Web inspection workflow via Playwright MCP — multi-step process with login gate safety
- Playwright-to-UiPath selector mapping

**Plugin Architecture**
- `plugin_loader.py` API v1 — register generators, lint rules, scaffold hooks, namespaces, known activities
- Auto-discovery of sibling skill directories with `extensions/__init__.py`

**Reference Documentation**
- Reference documents covering XAML structure, expressions, selectors, decomposition, scaffolding, generation, UI inspection, and lint rules

**Test Infrastructure**
- Lint test suite, regression suite, generator snapshot tests
- Semi-automated battle test grading (`grade_battle_test.py`)
