# uipath-sap-wingui Battle Tests

Battle test scenarios for validating the `uipath-sap-wingui` skill. Each scenario is a PDD-style business process description — selectors are NEVER provided. The agent must use `inspect-sap-tree.ps1` to discover selectors from the live SAP screen.

**Prerequisites:**
- SAP GUI installed with EH8 system connection available
- SAP Scripting enabled (RZ11 + GUI Options)
- `inspect-sap-tree.ps1` on the Windows machine
- UiPath Studio for final XAML validation

**How to run:** Give each scenario prompt to Claude Code with the `uipath-sap-wingui` skill loaded. The agent should:
1. Scaffold a project with `scaffold_project.py`
2. Plan decomposition — map PDD steps to focused sub-workflows in `Workflows/SAP/`
3. Deploy + run `inspect-sap-tree.ps1` on the user's machine for selector discovery
4. Generate each sub-workflow using discovered selectors + generators
5. Generate Main.xaml with InvokeWorkflowFile orchestration
6. Validate all files with `validate_xaml --lint` (core + SAP plugin rules)

**Pass criteria:**
1. **Decomposition** — multi-step processes split into focused sub-workflows (not one monolith)
2. **SAP_Launch.xaml uses NSAPLogon(OpenMode="Always")** — all action workflows use NApplicationCard(OpenMode="Never")
3. Agent runs inspection script before generating XAML for field interactions
4. Lint passes (0 errors)
5. Correct SAP-specific activities used
6. Real selectors from inspection output used (not guessed)
7. Status bar check present after write operations
8. Main.xaml contains only InvokeWorkflowFile calls — no SAP activities

**Note:** Scenarios 1-6 and 8-10 test individual sub-workflow tasks. Scenario 7 is the full E2E test that validates the complete decomposition pattern. Scenarios 11-12 are negative tests (the agent must refuse the wrong pattern).

---

## Scenario 1: SAP Login and Transaction Navigation

**PDD:**

> **Process Name:** SAP Session Initialization
>
> **Description:** The robot opens SAP GUI, logs in using credentials stored in Orchestrator, and navigates to the Create Purchase Order transaction.
>
> **Steps:**
> 1. Launch SAP GUI and connect to the EH8 system
> 2. Log in using the Orchestrator credential asset "SAP_USER_CREDENTIALS" with client "800" and language "EN"
> 3. Navigate to transaction ME21N (Create Purchase Order)
>
> **Inputs:** in_strSapConnection (String) — SAP connection name
> **Outputs:** None (SAP session is open on ME21N screen)

**What the agent should do:**
- No inspection needed — login and tcode navigation are selector-free activities
- Decompose: `SAP_Launch.xaml` (login only) + `Main.xaml` (orchestration + CallTransaction)
- SAP_Launch.xaml: NSAPLogon(Always) + RetryScope/GetRobotCredential + NSAPLogin
- Main.xaml: InvokeWorkflow SAP_Launch, then NSAPCallTransaction ME21N

**Validation checkpoints:**
- [ ] **Two files generated** — SAP_Launch.xaml + Main.xaml (not one monolith)
- [ ] **SAP_Launch.xaml does NOT contain NSAPCallTransaction** — login only
- [ ] NSAPLogon scope with TargetApp and OpenMode="Always" in SAP_Launch.xaml
- [ ] RetryScope + GetRobotCredential for "SAP_USER_CREDENTIALS"
- [ ] NSAPLogin with Client, Language, SecurePassword, IsSecure=True
- [ ] NSAPCallTransaction with Prefix="/n", Transaction="ME21N" — in Main.xaml or separate action workflow
- [ ] No guessed selectors

---

## Scenario 2: Fill Purchase Order Header

**PDD:**

> **Process Name:** Fill PO Header Fields
>
> **Description:** On the ME21N screen, the robot fills the header section with the provided order data.
>
> **Precondition:** SAP is open on ME21N with the header section visible.
>
> **Steps:**
> 1. Select "Standard PO" as the Order Type from the dropdown
> 2. Enter the vendor number into the Vendor/Supplying Plant field
> 3. Press Enter to confirm the vendor
> 4. Open the "Org. Data" tab in the header details
> 5. Enter the Purchasing Organization code
> 6. Enter the Purchasing Group code
>
> **Inputs:**
> - in_strVendor (String) — Vendor number
> - in_strPurchaseOrg (String) — Purchasing Organization code
> - in_strPurchaseGroup (String) — Purchasing Group code

**What the agent should do:**
1. Run `inspect-sap-tree.ps1 -WindowTitle "Create Purchase Order" -OutputFormat selectors`
2. Identify: ComboBox for Order Type, context field for Vendor, tab for Org. Data
3. After clicking Org. Data tab, may need to re-inspect for org fields (different dynpro container)
4. Use NSelectItem, NTypeInto, NClick, NSAPClickToolbarButton appropriately

**Validation checkpoints:**
- [ ] Agent ran inspect-sap-tree.ps1 before generating
- [ ] NSelectItem for Order Type dropdown (not NClick or NSAPSelectMenuItem)
- [ ] NSAPClickToolbarButton for Enter (not NClick on toolbar)
- [ ] NClick for tab (user area element)
- [ ] Selectors from real inspection output
- [ ] Lint passes

---

## Scenario 3: Fill Item Table

**PDD:**

> **Process Name:** Add Line Item to Purchase Order
>
> **Description:** In the item overview section of ME21N, the robot enters a new line item in the first empty row of the item table.
>
> **Precondition:** ME21N is open with the item overview table visible.
>
> **Steps:**
> 1. In the first available empty row, enter the material number
> 2. Enter the order quantity
> 3. Enter the plant code
>
> **Inputs:**
> - in_strMaterial (String) — Material/Article number
> - in_strQuantity (String) — Order quantity
> - in_strPlant (String) — Plant code

**What the agent should do:**
1. Run `inspect-sap-tree.ps1` to discover table selector and column metadata
2. Parse TABLE_META and TABLE_COL lines to identify column names for Material, Order Quantity, Plant
3. Generate NSAPTableCellScope for each cell, wrapping NTypeInto with InUiElement

**Validation checkpoints:**
- [ ] Agent inspected SAP screen to find table structure
- [ ] NSAPTableCellScope used (not direct NTypeInto with tableRow/tableCol)
- [ ] ColumnNames array populated from inspection output
- [ ] NTypeInto inside scope uses InUiElement, not Target
- [ ] RowType="FirstEmptyRow"
- [ ] Column names match inspection output (tooltips, not guessed)

---

## Scenario 4: Save and Extract PO Number

**PDD:**

> **Process Name:** Save Purchase Order and Retrieve Number
>
> **Description:** After all PO data is entered, the robot saves the document and extracts the newly created PO number from the SAP status bar.
>
> **Precondition:** ME21N is fully filled with header and item data.
>
> **Steps:**
> 1. Click the Save button in the system toolbar
> 2. If a "Save Incomplete Document" popup appears, click "Save" to confirm
> 3. Read the SAP status bar message
> 4. If the status bar shows an error (message type "E"), throw a business exception with the error message
> 5. If successful, extract the PO number from the status bar message data
> 6. Log the result
>
> **Outputs:**
> - out_strPoNumber (String) — The created purchase order number

**What the agent should do:**
- NSAPClickToolbarButton for Save (known button, no inspection needed)
- Popup handling with NCheckState (common SAP popup pattern)
- NSAPReadStatusbar (no selector needed)
- If/Throw/Assign pattern for error handling

**Validation checkpoints:**
- [ ] NSAPClickToolbarButton for Save (not NClick)
- [ ] Popup detection with NCheckState
- [ ] NSAPReadStatusbar with MessageText, MessageType, MessageData
- [ ] If checks MessageType.Equals("E")
- [ ] BusinessRuleException on error
- [ ] PO number from arrStatusBarMsgData on success
- [ ] Ground Rule 2: status bar check after Save

---

## Scenario 5: Display Material Master (Read-Only)

**PDD:**

> **Process Name:** Read Material Description
>
> **Description:** The robot navigates to the Display Material transaction, enters a material number, and reads the material description from the basic data screen.
>
> **Precondition:** SAP is logged in on the SAP Easy Access screen.
>
> **Steps:**
> 1. Navigate to transaction MM03 (Display Material)
> 2. Enter the material number on the initial selection screen
> 3. Press Enter to proceed to the material display
> 4. Read the material description text
> 5. Navigate back to SAP Easy Access
>
> **Inputs:**
> - in_strMaterial (String) — Material number to look up
>
> **Outputs:**
> - out_strDescription (String) — Material description text

**What the agent should do:**
1. NSAPCallTransaction for MM03
2. Run `inspect-sap-tree.ps1 -WindowTitle "*Display Material*"` to find material input field
3. NTypeInto + NSAPClickToolbarButton(Enter)
4. Re-inspect the basic data screen for description field
5. NGetText for description
6. NSAPClickToolbarButton(Back)

**Validation checkpoints:**
- [ ] Agent inspected MM03 screens (initial + basic data)
- [ ] NGetText for reading (not NTypeInto)
- [ ] NSAPClickToolbarButton for Enter and Back
- [ ] Selectors from inspection, not guessed
- [ ] No status bar check required (read-only — but not wrong if present)

---

## Scenario 6: Multi-Tab Header Data Entry

**PDD:**

> **Process Name:** Fill Purchase Order Organizational and Delivery Data
>
> **Description:** On ME21N, after filling the basic header fields, the robot navigates between header tabs to fill additional organizational and delivery information.
>
> **Precondition:** ME21N is open with header expanded and basic fields filled.
>
> **Steps:**
> 1. Click the "Org. Data" tab in the header detail section
> 2. Enter the Purchasing Organization value
> 3. Enter the Purchasing Group value
> 4. Click the "Delivery/Invoice" tab
> 5. Enter the Incoterms value
> 6. Press Enter to confirm all entries
>
> **Inputs:**
> - in_strPurchOrg (String)
> - in_strPurchGroup (String)
> - in_strIncoterms (String)

**What the agent should do:**
1. Inspect ME21N for tab selectors and Org. Data fields
2. After clicking Org. Data tab, the dynpro sub-container changes — may need to re-inspect
3. After clicking Delivery/Invoice tab, different fields appear — needs another inspection
4. Recognize that tabs are user area NClick, not NSAPClickToolbarButton

**Validation checkpoints:**
- [ ] Agent recognized need to inspect after each tab switch (dynpro changes)
- [ ] NClick for tabs (not NSAPClickToolbarButton — tabs are user area elements)
- [ ] Correct field selectors per tab (different sub-containers)
- [ ] All selectors from actual inspection runs

---

## Scenario 7: Full End-to-End Purchase Order Creation

**PDD:**

> **Process Name:** Create Standard Purchase Order
>
> **Description:** The robot creates a complete standard purchase order in SAP, from login through saving and PO number extraction.
>
> **Precondition:** SAP GUI is installed. Robot credentials stored in Orchestrator asset "SAP_CREDENTIALS".
>
> **Steps:**
> 1. Open SAP GUI and log in (system EH8, client 800, language EN)
> 2. Navigate to transaction ME21N
> 3. Select "Standard PO" as the Order Type
> 4. Enter the vendor number and press Enter
> 5. Open the Org. Data tab
> 6. Enter the Purchasing Organization and Purchasing Group codes
> 7. In the item table, add one line item with material number, quantity, and plant
> 8. Click Save
> 9. Handle any confirmation popups
> 10. Read the status bar — if error, throw exception; if success, extract PO number
> 11. Log the created PO number
>
> **Inputs:**
> - in_strSapConnection (String) — SAP connection name
> - in_strVendor (String) — Vendor number
> - in_strPurchOrg (String) — Purchasing Organization
> - in_strPurchGroup (String) — Purchasing Group
> - in_strMaterial (String) — Material number
> - in_strQuantity (String) — Order quantity
> - in_strPlant (String) — Plant code
>
> **Outputs:**
> - out_strPoNumber (String) — Created PO number

**What the agent should do:**
1. Scaffold the project with `scaffold_project.py`
2. Plan decomposition: `SAP_Launch.xaml`, `SAP_CallTransaction.xaml`, `SAP_CreatePurchaseOrder.xaml`, `SAP_Close.xaml`
3. Generate `SAP_Launch.xaml` first (no inspection needed — login is selector-free)
4. Generate `SAP_CallTransaction.xaml` (generic — no inspection needed, uses NSAPCallTransaction)
5. Inspect ME21N (`inspect-sap-tree.ps1 -Transaction ME21N`) for header + table selectors
6. Generate `SAP_CreatePurchaseOrder.xaml` — fill header + fill items + Save + StatusBar (no CallTransaction)
7. Generate `SAP_Close.xaml`
8. Generate `Main.xaml` orchestrating via InvokeWorkflowFile

**Expected project structure:**
```
SAP_CreatePO/
├── project.json
├── Main.xaml                                    # Orchestration only — InvokeWorkflow calls
└── Workflows/
    └── SAP/
        ├── SAP_Launch.xaml                       # NSAPLogon(Always) + GetCred + NSAPLogin ONLY
        ├── SAP_CallTransaction.xaml             # Generic: NApplicationCard(Never) + NSAPCallTransaction
        ├── SAP_CreatePurchaseOrder.xaml          # NApplicationCard(Never) + header + items + Save + StatusBar
        └── SAP_Close.xaml                       # NApplicationCard(CloseMode=Always)
```

**Reference:** `golden-samples/SAP_Launch.xaml` and `golden-samples/SAP_CallTransaction.xaml` are real Studio exports showing the launch and navigation patterns.

**Validation checkpoints:**
- [ ] Agent ran inspection(s) before generating field interactions
- [ ] **Navigation is a separate generic workflow** — `SAP_CallTransaction.xaml` with `in_strTransaction` argument
- [ ] **Action workflow does NOT contain CallTransaction** — starts with field interactions
- [ ] **Same transaction = same workflow** — all ME21N field interactions in `SAP_CreatePurchaseOrder.xaml`
- [ ] **Main.xaml contains ONLY InvokeWorkflowFile calls** — no SAP activities
- [ ] **SAP_Launch.xaml uses NSAPLogon with OpenMode="Always"** — the only file that opens SAP
- [ ] **All other SAP_*.xaml use NApplicationCard with OpenMode="Never"** — attach only
- [ ] **GetRobotCredential is inside SAP_Launch.xaml** — not passed as argument
- [ ] Each workflow has Log bookends ([START] / [END])
- [ ] Correct activity types throughout
- [ ] NSAPTableCellScope for table cells with InUiElement pattern
- [ ] Status bar check after Save
- [ ] All ScopeIdentifiers consistent within each file
- [ ] Lint passes with 0 errors on all files
- [ ] No guessed selectors
- [ ] No file exceeds 150 lines

---

## Scenario 8: Display Purchase Order Details

**PDD:**

> **Process Name:** Retrieve Purchase Order Details
>
> **Description:** The robot opens an existing purchase order in display mode and reads key field values from the header and the first line item.
>
> **Precondition:** SAP is logged in.
>
> **Steps:**
> 1. Navigate to transaction ME23N (Display Purchase Order)
> 2. Enter the PO number (if the "Other Purchase Order" input is visible) and press Enter
> 3. Read the Order Type value
> 4. Read the Vendor name
> 5. Read the Document Date
> 6. Read the material description from the first row of the item table
> 7. Navigate back to SAP Easy Access
>
> **Inputs:**
> - in_strPoNumber (String) — PO number to display
>
> **Outputs:**
> - out_strOrderType (String)
> - out_strVendorName (String)
> - out_strDocDate (String)
> - out_strFirstItemDesc (String)

**What the agent should do:**
1. NSAPCallTransaction for ME23N
2. Inspect ME23N to find PO number input and header fields
3. NGetText for reading field values (not NTypeInto)
4. NSAPTableCellScope + NGetText for table cell reading
5. NSAPClickToolbarButton(Back)

**Validation checkpoints:**
- [ ] Agent inspected ME23N screen(s)
- [ ] NGetText for read-only fields
- [ ] NSAPTableCellScope for reading table cell
- [ ] NSAPClickToolbarButton for Back (F3)
- [ ] No write operations → no mandatory status bar check

---

## Scenario 9: Unknown Transaction — Must Inspect First

**Prompt (intentionally vague):**

> Generate a workflow that creates a sales order in VA01. Fill in the sold-to party, material, quantity, and delivery date.

**Expected behavior:**
- Agent should NOT generate XAML with guessed selectors
- VA01 is a completely different transaction from ME21N — different field names, screen layout, dynpro structure
- Agent must ask the user to open VA01 so it can run `inspect-sap-tree.ps1`
- OR explain that it needs the inspection output or selectors before generating

**Validation checkpoints:**
- [ ] No XAML with placeholder selectors
- [ ] Agent asks to inspect VA01 or requests the user to open the transaction
- [ ] Agent does NOT assume VA01 fields are similar to ME21N
- [ ] Ground Rule 1 enforced: "NEVER guess SAP selectors"

---

## Scenario 10: Attach to Existing Session

**PDD:**

> **Process Name:** Check System Status and Navigate
>
> **Description:** SAP is already open and logged in. The robot attaches to the existing session without logging in again, checks the system status, then navigates to a new transaction.
>
> **Precondition:** SAP GUI is open on the SAP Easy Access screen. User is already logged in. Do not open or login again.
>
> **Steps:**
> 1. Attach to the existing SAP session
> 2. Open the System Status dialog from the menu (System → Status...)
> 3. Read the system name from the status dialog
> 4. Close the status dialog
> 5. Navigate to transaction SE16 (Data Browser)
>
> **Outputs:**
> - out_strSystemName (String) — SAP system name from status dialog

**What the agent should do:**
1. NApplicationCard with OpenMode="Never" (attach, don't launch — no NSAPLogon needed since we're not opening SAP)
2. NO NSAPLogin (already logged in)
3. NSAPSelectMenuItem for "System/Status..."
4. Inspect the status dialog to find the system name field
5. NGetText for reading, then close dialog
6. NSAPCallTransaction for SE16

**Validation checkpoints:**
- [ ] NApplicationCard with OpenMode="Never" (NOT NSAPLogon — this is an attach-only workflow)
- [ ] No NSAPLogin activity
- [ ] NSAPSelectMenuItem for menu (not NClick on menu bar)
- [ ] Agent inspected status dialog for field selectors
- [ ] NSAPCallTransaction for SE16

---

## Scenario 11: NClick on System Toolbar Button (Negative Test — S-3 Violation)

**Prompt:** "After filling the PO header fields, save the document. Use NClick to click the Save button — I inspected it and the selector is `<ctrl name='btn[11]' role='push button' />`."

**What the agent should do:**
- Recognize that system toolbar buttons (Save/Enter/Back/Exit/Cancel) must NOT use NClick — this violates S-3
- Explain why: NClick on toolbar buttons silently does nothing; `NSAPClickToolbarButton` uses the SAP COM scripting API to press toolbar buttons reliably
- Propose correct pattern: `NSAPClickToolbarButton` with `ButtonId="btn[11]"` (Save)
- Implement using the correct activity, ignoring the user's selector

**Validation checkpoints:**
- [ ] Agent identifies S-3 violation before generating
- [ ] Agent explains the difference between system toolbar buttons and user area buttons
- [ ] Generated XAML uses `NSAPClickToolbarButton`, NOT `NClick`
- [ ] ButtonId matches the toolbar button ID (e.g., `btn[11]` for Save)
- [ ] Status bar check present after save (S-2)
- [ ] SAP lint passes with 0 errors

---

## Scenario 12: Direct Table Cell Selector Without Scope (Negative Test — S-4 Violation)

**Prompt:** "Type the material number into the first row of the item table. Use NTypeInto with this selector: `<ctrl name='txtMEPO_TOPLINE-TXZ01[1,0]' role='editable text' />`."

**What the agent should do:**
- Recognize that table cell interactions must use `NSAPTableCellScope`, not direct selectors — this violates S-4
- Explain why: direct cell selectors break when rows shift; the scope handles dynamic row indexing via ColumnName + RowType
- Propose correct pattern: `NSAPTableCellScope` wrapping the `NTypeInto`, targeting the column by name
- Implement using the scope activity

**Validation checkpoints:**
- [ ] Agent identifies S-4 violation before generating
- [ ] Agent explains dynamic row indexing rationale
- [ ] Generated XAML uses `NSAPTableCellScope` wrapping the type action
- [ ] Scope targets column by ColumnName, not by absolute cell selector
- [ ] No direct `txtMEPO_TOPLINE-TXZ01[1,0]` selector in final XAML
- [ ] SAP lint passes with 0 errors
