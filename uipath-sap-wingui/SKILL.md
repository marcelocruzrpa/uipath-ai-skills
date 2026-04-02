---
name: uipath-sap-wingui
description: >
  Generates UiPath XAML workflows for SAP GUI for Windows (WinGUI) automation —
  NSAPLogon, NSAPLogin, NSAPCallTransaction, NSAPClickToolbarButton, NSAPSelectMenuItem,
  NSAPReadStatusbar, NSAPTableCellScope. Includes SAP tree inspection (inspect-sap-tree.ps1),
  9 deterministic generators, 30 SAP-specific lint rules, and decomposition patterns.
  Self-contained plugin with generators and lint rules loaded via uipath-core's plugin system
  (plugin_loader.py). Use when the user mentions SAP, SAP GUI, WinGUI, transaction codes,
  or SAP-specific activities.
---

# uipath-sap-wingui — SAP GUI for Windows Automation Skill

Generate production-ready UiPath XAML workflows that automate SAP GUI for Windows (WinGUI) transactions. This skill covers the modern `uix:NSAP*` activity set and works alongside `uipath-core` for project scaffolding and standard workflow activities.

**Requires:** `uipath-core` (REFramework, project structure, standard activities)

> **Plugin architecture:** This skill's `extensions/` directory is auto-discovered by uipath-core's `plugin_loader.py`. Generators, lint rules, namespaces, and known activities are registered at import time — no manual wiring needed. Core's `generate_workflow.py`, `validate_xaml`, and `scaffold_project.py` query the plugin registries at runtime.

## Extensions (Plugin System)

```
uipath-sap-wingui/
├── SKILL.md
├── references/
│   ├── sap-generation.md        ← ⚠ READ BEFORE GENERATING — JSON specs, code recipes
│   ├── sap-cheat-sheet.md       ← Generator signatures, selectors, patterns
│   └── sap-inspection-reference.md
├── evals/
├── golden-samples/
├── scripts/
│   └── inspect-sap-tree.ps1        ← PowerShell SAP tree inspection
└── extensions/
    ├── __init__.py          ← Registers all SAP components with plugin_loader
    ├── generators.py        ← 7 core + 2 convenience SAP activity generators
    └── lint_rules.py        ← lint_sap_wingui (SAP-001 through SAP-030)
```

**What gets registered:**
- 7 generators: `sap_logon`, `sap_login`, `sap_call_transaction`, `sap_click_toolbar`, `sap_select_menu_item`, `sap_read_statusbar`, `sap_table_cell_scope` (+ 2 Python-only helpers: `gen_sap_status_bar_check`, `gen_sap_type_into_cell` — importable but not JSON-spec-compatible)
- 1 lint rule: `lint_sap_wingui` (covers all 30 SAP rules: SAP-001 through SAP-030)
- 2 namespaces: `uix` → `UiPath.UIAutomationNext`, `ucas` → `UiPath.Core.Activities.SAP`
- 7 known activities: `NSAPLogon`, `NSAPLogin`, `NSAPCallTransaction`, `NSAPClickToolbarButton`, `NSAPSelectMenuItem`, `NSAPReadStatusbar`, `NSAPTableCellScope` (IdRef + DisplayName checks)

---

## Routing Table

Read the relevant reference BEFORE generating any SAP XAML.

| Task | Read |
|---|---|
| **⚠ ANY task involving SAP fields/tabs/tables** | **§Inspection Workflow below** → run `inspect-sap-tree.ps1` via PowerShell FIRST |
| **⚠ Generate SAP XAML (any activity)** | **`references/sap-generation.md`** → JSON spec approach, gen values, code recipes |
| Generator signatures, usage examples, common mistakes | `references/sap-cheat-sheet.md` |
| SAP selector syntax, field prefixes, patterns | `references/sap-cheat-sheet.md` → §SAP Selector Patterns |
| Common workflow patterns (login, status bar, table, popup) | `references/sap-cheat-sheet.md` → §Common SAP Workflow Patterns |
| SAP decomposition, folder structure, Launch/Action patterns | §SAP Workflow Decomposition below (inline) |
| Inspection script docs, output format | `references/sap-inspection-reference.md` |
| Fix a specific SAP lint rule | `extensions/lint_rules.py` → search by SAP-NNN |

---

## Ground Rules

1. **I-3** — ⛔ NEVER guess SAP selectors. Run `inspect-sap-tree.ps1` via PowerShell FIRST. See §Inspection Workflow below.
2. **S-2** — Status bar check after EVERY write operation. `NSAPReadStatusbar` → check `MessageType.Equals("E")` → Throw.
3. **S-1** — SAP activities MUST be inside NSAPLogon scope. All SAP activities require `ScopeIdentifier` referencing parent `NSAPLogon.ScopeGuid`.
4. **S-3** — Toolbar buttons are NOT regular NClick. System toolbar → `NSAPClickToolbarButton`. User area buttons → `NClick` with selectors.
5. **S-4** — Table cells use NSAPTableCellScope (ColumnName + RowType). Inner activities use `InUiElement`.
6. **S-5** — Dynpro numbers are volatile — field names are stable. Use the full path from inspection output.
7. **S-6** — NEVER hardcode values. Every value from arguments or variables. `Client="[in_strClient]"` not `Client="[&quot;800&quot;]"`.
8. **A-5** — Follow uipath-core decomposition rules. See §SAP Workflow Decomposition below.
9. Use `uipath-core` generators for standard activities — `NTypeInto`, `NClick`, `NGetText`, `NSelectItem`, `NCheckState` work unchanged inside SAP scope with `<sap id='...' />` selectors.

---

## SAP Workflow Decomposition

**This section enforces uipath-core decomposition rules applied to SAP.** All rules from `uipath-core/references/skill-guide.md` → Decomposition Rules apply. This section covers SAP-specific adaptations.

### Core Principles
1. **Main.xaml orchestrates only** — InvokeWorkflowFile calls, no SAP activities, no business logic
2. **Same transaction = same workflow** — all steps within a single SAP transaction belong in ONE action workflow. E.g., `SAP_CreatePurchaseOrder.xaml` contains: CallTransaction → fill header → fill items → Save → StatusBar check. Only split when switching transactions or apps.
3. **≤150 lines per file** — if a workflow exceeds this, split it
4. **Credentials retrieved where used** — GetRobotCredential goes inside `SAP_Launch.xaml`, pass only `in_strCredentialAssetName` (the Orchestrator asset name string)
5. **Log bookends + intermediate logs** — first/last activity: `LogMessage "[START/END] SAP_ActionName"`. Also add log messages **between each logical step** (e.g., "Filling PO header...", "Filling item table...", "Saving purchase order..."). SAP transactions are long-running — intermediate logs pinpoint where failures occur.

### SAP Folder Structure
```
ProjectRoot/
├── Main.xaml                               # Orchestration only
├── Workflows/
│   ├── SAP/                                # All SAP workflows in SAP/ subfolder
│   │   ├── SAP_Launch.xaml                  # NSAPLogon(Always) + NSAPLogin ONLY
│   │   ├── SAP_CallTransaction.xaml        # Generic: NApplicationCard(Never) + NSAPCallTransaction
│   │   ├── SAP_CreatePurchaseOrder.xaml    # NApplicationCard(Never) + header + items + Save + StatusBar
│   │   └── SAP_Close.xaml                  # NApplicationCard(CloseMode=Always)
│   └── Utils/
│       └── Process_ValidateData.xaml       # No UI — data validation only
└── Framework/                              # REFramework files (if applicable)
```

> **Same transaction = same workflow.** All field interactions within ME21N (fill header, fill table, save, status bar) belong in `SAP_CreatePurchaseOrder.xaml`. Do NOT split into `SAP_FillPOHeader.xaml` + `SAP_FillItemTable.xaml` + `SAP_SaveAndExtractPO.xaml`.

> **Navigation is a separate orchestration step.** `SAP_CallTransaction.xaml` is a generic reusable workflow that takes `in_strTransaction` as an argument. Main.xaml calls it before the action workflow. The action workflow assumes it's already on the correct screen.

### SAP Launch Pattern (Login Inside Launch)
`SAP_Launch.xaml` is the SAP equivalent of `AppName_Launch.xaml`. It handles ONLY:
- `NSAPLogon` with `OpenMode="Always"` — opens SAP GUI
- `RetryScope` + `GetRobotCredential` — retrieves SAP credentials from Orchestrator
- `NSAPLogin` — authenticates with Client, Language, SecurePassword
- Outputs nothing (SAP session is open and ready on SAP Easy Access screen)

**SAP_Launch does NOT navigate to a transaction.** Transaction navigation is a separate step — either in Main.xaml or in the first action workflow. This keeps Launch reusable across processes that use different transactions.

**Arguments:**
```
in_strCredentialAssetName (String, In)  — Orchestrator credential asset name (e.g., "SAP_CREDENTIALS")
in_strConnection          (String, In)  — SAP system connection name
in_strSapLogonPath        (String, In)  — Path to saplogon.exe
out_UISAP                 (UiElement, Out) — SAP session reference for action workflows
```
**Scope body variables** (not exposed as arguments):
```
in_strClient              (String)    — SAP client number
in_strLanguage            (String)    — SAP language code
strUsername               (String)    — from GetRobotCredential
secstrPassword            (SecureString) — from GetRobotCredential
```
All input values come from the caller — **nothing is hardcoded in the workflow**. `out_UISAP` is the session UiElement reference output by `NSAPLogin.OutUiElement`, passed to action workflows.

### SAP Action Workflow Pattern (Attach Only)
All action workflows (e.g., `SAP_CreatePurchaseOrder.xaml`) use `NApplicationCard` with `OpenMode="Never"` — they attach to the already-open SAP session, never launch it.

**Why NApplicationCard, not NSAPLogon?** Real UiPath Studio uses `NApplicationCard` for attach-to-existing-session workflows. `NSAPLogon` is reserved for the launch/open scenario (with `OpenMode="Always"`). SAP activities (`NSAPCallTransaction`, `NSAPClickToolbarButton`, etc.) work correctly inside `NApplicationCard` — they reference the scope via `ScopeIdentifier` matching `NApplicationCard.ScopeGuid`.

```python
# Action workflow: NApplicationCard with OpenMode="Never" (from uipath-core)
full = gen_napplicationcard(
    display_name="SAP Easy Access",
    open_mode="Never",    # ATTACH ONLY — SAP_Launch.xaml already opened it
    close_mode="Never",
    scope_guid=scope_guid,
    selector="<wnd app='saplogon.exe' cls='SAP_FRONTEND_SESSION' />",
    body_content=body,
)
```

**Each action workflow covers field interactions only (already on correct screen):**

| Workflow | Does | Does NOT |
|---|---|---|
| `SAP_CallTransaction.xaml` | Generic: NSAPCallTransaction with `in_strTransaction` arg + Enter | Field interactions, Login, Close |
| `SAP_CreatePurchaseOrder.xaml` | Fill header → fill items → Save → StatusBar check → extract PO# | Navigate (CallTransaction), Login, Close |
| `SAP_ReadMaterial.xaml` | Read Basic Data fields → Back | Navigate, Login, Close |
| `SAP_DisplaySalesOrder.xaml` | Read header + items → Back | Navigate, Login, Close |

### SAP Close Pattern
`SAP_Close.xaml` uses `NApplicationCard` (from uipath-core) with `CloseMode="Always"`, `OpenMode="Never"`. This is the SAP equivalent of `App_Close.xaml`.

In REFramework: `SAP_Close.xaml` is invoked from `CloseAllApplications.xaml` only — never from Process.xaml or action workflows.

### Scope Activity Summary

| Workflow type | Scope activity | OpenMode | CloseMode |
|---|---|---|---|
| `SAP_Launch.xaml` | `NSAPLogon` | Always | Never |
| Action workflows (e.g., `SAP_CreatePurchaseOrder.xaml`) | `NApplicationCard` | Never | Never |
| `SAP_Close.xaml` | `NApplicationCard` | Never | Always |

**Key rule:** `NSAPLogon` is ONLY for launch/open. All attach-to-existing-session workflows use `NApplicationCard`. SAP activities (`NSAPCallTransaction`, `NSAPClickToolbarButton`, etc.) work inside both — they reference the scope via `ScopeIdentifier` matching the parent's `ScopeGuid`.

### Orchestration Example (Main.xaml or Process.xaml)
```
Main.xaml
  ├── InvokeWorkflow: Workflows\SAP\SAP_Launch.xaml                (NSAPLogon scope)
  │     (in_strSapConnection, in_strCredentialAssetName, in_strSapLogonPath, out_uiSAP)
  ├── InvokeWorkflow: Workflows\SAP\SAP_CallTransaction.xaml       (NApplicationCard scope)
  │     (io_uiSAP, in_strTransaction="ME21N")
  │     ↑ Generic — reusable for any transaction code
  ├── InvokeWorkflow: Workflows\SAP\SAP_CreatePurchaseOrder.xaml   (NApplicationCard scope)
  │     (io_uiSAP, in_strVendor, in_strMaterial, in_strQuantity, in_strPlant, out_strPONumber)
  │     ↑ Already on ME21N screen — fills header → items → Save → StatusBar
  └── InvokeWorkflow: Workflows\SAP\SAP_Close.xaml                 (NApplicationCard scope)
```

**Note:** `SAP_CallTransaction.xaml` is generic — it takes `in_strTransaction` and navigates via NSAPCallTransaction. The action workflow does NOT contain CallTransaction — it starts with field interactions. A different process using VA01 would pass a different transaction code to the same `SAP_CallTransaction.xaml`.

### What NOT To Do
```
WRONG — everything in one workflow:
  SAP_CreatePO.xaml (400 lines)
    ├── NSAPLogon (Open)
    ├── GetRobotCredential
    ├── NSAPLogin
    ├── NSAPCallTransaction
    ├── NSelectItem (Order Type)
    ├── NTypeInto (Vendor)
    ├── NSAPClickToolbarButton (Enter)
    ├── NClick (Org Data tab)
    ├── NTypeInto (Purch Org)
    ├── NTypeInto (Purch Group)
    ├── NSAPTableCellScope (Material) + NTypeInto
    ├── NSAPTableCellScope (Quantity) + NTypeInto
    ├── NSAPTableCellScope (Plant) + NTypeInto
    ├── NSAPClickToolbarButton (Save)
    ├── NSAPReadStatusbar
    ├── If (error check)
    └── NApplicationCard (Close)

ALSO WRONG — using NSAPLogon for attach:
  SAP_ActionWorkflow.xaml
    ├── NSAPLogon (OpenMode="Never")   ← WRONG: use NApplicationCard for attach
    ├── NTypeInto (fields)
    └── ...

CORRECT — decomposed by concern:
  Main.xaml (orchestration only — ~25 lines)
    ├── InvokeWorkflow: SAP_Launch.xaml                (~50 lines — NSAPLogon open + login ONLY)
    ├── InvokeWorkflow: SAP_CallTransaction.xaml       (~30 lines — generic, in_strTransaction="ME21N")
    ├── InvokeWorkflow: SAP_CreatePurchaseOrder.xaml   (~100 lines — NApplicationCard + header + items + Save + StatusBar)
    └── InvokeWorkflow: SAP_Close.xaml                 (~20 lines — NApplicationCard close)
```

---

## Activity Reference

### SAP-Specific Activities (this skill)

| Activity | Generator | Purpose |
|---|---|---|
| `uix:NSAPLogon` | `gen_sap_logon()` | SAP GUI scope — open/attach to SAP session |
| `uix:NSAPLogin` | `gen_sap_login()` | Authenticate with Client, Username, SecurePassword |
| `uix:NSAPCallTransaction` | `gen_sap_call_transaction()` | Navigate to tcode (`/n` same session, `/o` new) |
| `uix:NSAPClickToolbarButton` | `gen_sap_click_toolbar()` | System toolbar: Enter, Save, Back, Exit, Cancel, F-keys |
| `uix:NSAPSelectMenuItem` | `gen_sap_select_menu_item()` | Menu path selection (e.g., "System/Status...") |
| `uix:NSAPReadStatusbar` | `gen_sap_read_statusbar()` | Read status bar: MessageText, MessageType (S/E/W/A/I) |
| `uix:NSAPTableCellScope` | `gen_sap_table_cell_scope()` | Target table cell by ColumnName + RowType |

### Standard Activities from uipath-core (work with SAP selectors)

| Activity | Use For |
|---|---|
| `uix:NTypeInto` | Type into SAP text fields, context fields |
| `uix:NClick` | Click user area buttons, tabs, labels |
| `uix:NGetText` | Read field values |
| `uix:NSelectItem` | Select ComboBox/dropdown items |
| `uix:NCheckState` | Check if SAP element exists (Pick/conditional patterns) |
| `uix:NApplicationCard` | Close SAP session (CloseMode=Always, OpenMode=Never) |

---

## File Reference

| File | Purpose |
|---|---|
| `SKILL.md` | Routing table, ground rules, decomposition, inspection workflow |
| **`references/sap-generation.md`** | **⚠ READ BEFORE GENERATING — JSON spec approach, gen values, code recipes, xmlns reference** |
| **`references/sap-cheat-sheet.md`** | **Generator signatures, usage examples, common mistakes, selector patterns, workflow patterns** |
| `references/sap-inspection-reference.md` | Inspection script documentation |
| `scripts/inspect-sap-tree.ps1` | SAP GUI COM inspection script |
| `golden-samples/SAP_Launch.xaml` | Real Studio export — NSAPLogon + NSAPLogin |
| `golden-samples/SAP_CallTransaction.xaml` | Real Studio export — NApplicationCard attach + NSAPCallTransaction |
| `golden-samples/VA03_DisplaySalesOrder/` | Read-only pattern — header + item table (real EH8 selectors) |
| `golden-samples/SE16N_DataBrowser/` | Query + results pattern — enter table, execute, read hits |
| `golden-samples/MM03_DisplayMaterial/` | Multi-tab read pattern — navigate, read Basic Data 1 fields |

## Known Core Lint False Positives

When running `uipath-core`'s `validate_xaml` on SAP workflows, these are expected:

| Core Lint | Trigger | Why False | Action |
|---|---|---|---|
| lint 58 | NTypeInto/NGetText "orphaned" | Doesn't recognize NSAPLogon as valid scope | SAP plugin lint rules (loaded via `validate_xaml --lint`) validate SAP scope hierarchy |
| lint 45 | "navigate" in filename | Browser heuristic, not SAP | Ignore, or avoid "navigate" in filename |
| lint 69 | `_Launch.xaml` missing Pick/NCheckState login validation | Browser-specific pattern — SAP's NSAPLogin throws on auth failure natively via COM | Ignore — add NSAPReadStatusbar after NSAPCallTransaction instead |

> **lint 94 (Object Repository) is NOT a false positive for SAP.** SAP selectors (`<sap id='...'/>`) belong in `.objects/`. Write `selectors.json` during inspection, then run `generate_object_repository.py`.

---

## Inspection Workflow

### How to Run Inspection from Claude Code

The inspection script is bundled with this skill at `scripts/inspect-sap-tree.ps1`. Deploy it to the user's Windows machine and run it there. SAP GUI must be open on the target transaction.

**Step 1: Deploy the script to Windows**
Read the script from the skill folder and write it to the Windows machine:
```
bash_tool → cat <skill_path>/scripts/inspect-sap-tree.ps1  (get the content)
bash_tool → powershell -Command "Set-Content -Path '$env:USERPROFILE\inspect-sap-tree.ps1' -Value (Get-Content '<skill_path>/scripts/inspect-sap-tree.ps1' -Raw)"
```
Or if already deployed, skip to Step 2.

**Step 2: Run inspection**
```
bash_tool → powershell -Command "Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force; & '$env:USERPROFILE\inspect-sap-tree.ps1' -WindowTitle '*Create Purchase Order*' -OutputFormat selectors"
```
Use wildcards in WindowTitle. Set timeout to 45 seconds (SAP COM bridge takes time).

**Step 3: Parse output**
The output contains:
- `<sap id='usr/sub.../txtFIELD_NAME' />` — field selectors for NTypeInto/NGetText
- `<sap id='usr/sub.../cmbFIELD_NAME' />` — ComboBox selectors for NSelectItem
- `<sap id='tbar[0]/btn[N]' />` — toolbar button selectors
- `TABLE_META` + `TABLE_COL` lines — table structure and column names
- `<wnd app='saplogon.exe' cls='SAP_FRONTEND_SESSION' title='...' />` — window selector

**Step 4: Re-inspect after tab/section changes**
SAP dynpro numbers change when tabs are clicked or sections expand/collapse. After generating a tab click activity, you may need to re-inspect to discover the fields that appear under the new tab.

### Decision Gate

Before generating XAML with SAP field selectors:

```
Does the workflow interact with SAP fields, tabs, or table cells?
├── NO (login + navigate + toolbar only) → Generate directly, no inspection needed
└── YES
    ├── Do I have selectors from inspection output or user? → Generate
    └── No selectors available
        ├── Is PowerShell available?
        │   ├── YES → Deploy scripts/inspect-sap-tree.ps1 to Windows → Run it → Parse selectors → Generate
        │   └── NO → Ask user to run inspect-sap-tree.ps1 manually and provide the output
        └── SAP not open? → Ask user to open the target transaction first
```

**NEVER generate with placeholder/guessed selectors.** There is no "placeholder approach", no "TODO: VERIFY SELECTOR" markers, no "well-known field names" — either you have real selectors from inspection/user or you don't generate. HALT. END YOUR RESPONSE. STOP GENERATING TEXT.

---


