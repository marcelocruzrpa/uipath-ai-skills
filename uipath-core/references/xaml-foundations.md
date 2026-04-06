# XAML Foundations

File structure, namespaces, core activities (Assign, Log, InputDialog, MessageBox, Delay), variables & arguments.

## Contents
- [XAML File Structure](#xaml-file-structure)
  - [C# vs VB.NET Expression Mode](#c#-vs-vb.net-expression-mode)
- [Namespace Declarations](#namespace-declarations)
- [Core Activities](#core-activities)
  - [Assign](#assign)
  - [Multiple Assign](#multiple-assign)
  - [Log Message](#log-message)
  - [Input Dialog (Text)](#input-dialog-text)
  - [Input Dialog (Dropdown)](#input-dialog-dropdown)
  - [Message Box](#message-box)
  - [Comment Out](#comment-out)
  - [Delay](#delay)
  - [Comment](#comment)
- [Variable and Argument Declarations](#variable-and-argument-declarations)
  - [Variables (inside Sequence.Variables or Flowchart.Variables)](#variables-inside-sequence.variables-or-flowchart.variables)
  - [Arguments (at Activity level, before the main Sequence)](#arguments-at-activity-level-before-the-main-sequence)
- [Control Flow Activities](#control-flow-activities)

## XAML File Structure

Every UiPath XAML workflow has: root `<Activity>` element with `x:Class` and xmlns declarations, optional `TextExpression.NamespacesForImplementation` / `ReferencesForImplementation`, then a `<Sequence>` body with variables and activities. `generate_workflow.py` builds this entire structure from a JSON spec — never hand-write the skeleton.

**⚠️ CRITICAL — Sequence child element order:** Inside any `<Sequence>`, the order MUST be: (1) `<sap:WorkflowViewStateService.ViewState>` (optional), (2) `<Sequence.Variables>` (optional), (3) child activities. Placing `<Sequence.Variables>` **after** any child activity causes `XamlDuplicateMemberException: 'Activities' property has already been set on 'Sequence'` because the XAML parser opens the implicit Activities collection for the first child and cannot reopen it after Variables. Same rule applies to `<Flowchart.Variables>` inside `<Flowchart>`.

**Collection type variants:** Studio exports use two interchangeable collection types for namespace/reference lists:
- `sco:Collection x:TypeArguments="x:String"` — `xmlns:sco="clr-namespace:System.Collections.ObjectModel;assembly=System.Private.CoreLib"` (more common)
- `scg:List x:TypeArguments="x:String" Capacity="N"` — `xmlns:scg="clr-namespace:System.Collections.Generic;assembly=System.Private.CoreLib"` (includes `Capacity` hint)

Both work identically at runtime. Note the assembly may be `mscorlib` or `System.Private.CoreLib` depending on the .NET version — both are valid. Match what the project's existing files use.

### C# vs VB.NET Expression Mode

For **VB.NET** (legacy default), expressions use `VisualBasicValue`/`VisualBasicReference`. For **C#**, use `CSharpValue`/`CSharpReference` with `xmlns:mca="clr-namespace:Microsoft.CSharp.Activities;assembly=System.Activities"`. The generators handle expression mode internally.

## XAML Attribute Encoding Rules

**XML encoding in attribute values:**
- `"` → `&quot;` (inside VB.NET string literals)
- `&` → `&amp;`  
- `<` → `&lt;`, `>` → `&gt;`
- Newlines → `&#xA;`, tabs → `&#x9;`

**⚠️ CRITICAL — Curly brace escape for JSON/literal values:**
When an attribute value starts with `{`, XAML interprets it as a markup extension (like `{x:Null}`, `{Binding}`). If the value is actually a literal string (e.g., JSON), Studio crashes with:
`Quote characters ' or " are only allowed at the start of values`

**Fix:** Prefix with `{}` (empty curly braces = "treat rest as literal"):
```xml
<!-- WRONG — XAML parser crash -->
FormLayout="{&quot;components&quot;:[...]}"

<!-- CORRECT — {} escape prefix -->
FormLayout="{}{&quot;components&quot;:[...]}"
```
This applies to ANY attribute whose value starts with `{` but is NOT a XAML markup extension. Most commonly: `FormLayout` (Tasks forms) and any attribute holding inline JSON.

## Namespace Declarations

`generate_workflow.py` handles all xmlns declarations automatically based on which activities are used. The `sd:` prefix is resolved via Option B strategy: `sd=Data` when DataTable is present, `sd=Drawing` for UI-only, `sd=Data + sdd=Drawing` when both are needed. Never hand-write namespace declarations.

## Core Activities

### Assign

→ **Use `gen_assign()`** — generates correct XAML deterministically.

Note: `DisplayName` is optional on Assign. Type in `x:TypeArguments` must match the variable type.

**⚠️ CRITICAL — Assign.Value and Assign.To child types:** `<Assign.Value>` MUST contain `<InArgument x:TypeArguments="...">` and `<Assign.To>` MUST contain `<OutArgument x:TypeArguments="...">`. Never use a bare `<x:String>`, `<x:Int32>`, `<Literal>`, or plain text. Doing so causes: `Type 'x:String' is not assignable to type 'InArgument' of member 'Value'`. Always use `gen_assign()` to avoid this.

### Multiple Assign
Assigns multiple variables in a single activity. Uses `ui:AssignOperation` list.
→ **Use `gen_multiple_assign()`** — generates correct XAML deterministically.

Properties:
- Each `ui:AssignOperation` has `.To` (OutArgument) and `.Value` (InArgument), same structure as regular Assign
- **⚠️ MUST use element syntax** — `<ui:AssignOperation.To><OutArgument x:TypeArguments="x:String">[var]</OutArgument></ui:AssignOperation.To>`. The attribute shorthand `To="[var]" Value="[expr]"` does NOT work — Studio throws `x:String is not assignable to OutArgument`.
- `Capacity` attribute on the list should match or exceed the number of operations
- More compact than multiple separate Assign activities — good for initializing or resetting several variables at once
- **⛔ HALLUCINATION TRAP:** `MultipleAssign.Body`, `ActivityAction`, `AssignOperationSet`, `MultipleAssignBody`, `AssignItem` do NOT exist. The ONLY valid child is `.AssignOperations` > `scg:List` > `ui:AssignOperation`. Lint 52 catches this.

#### Nullable Types in AssignOperations
Data Service entity fields use `Nullable(Of T)` with `s:` prefix in the `value_type` param of `gen_multiple_assign()`: `s:Nullable(x:Boolean)`, `s:Nullable(x:Decimal)`, `s:Nullable(x:Int32)`, `s:Nullable(x:Int64)`, `s:Nullable(x:DateTime)`.

#### Literal Empty String (Explicit Empty Value)
Studio serializes explicit `""` as a `Literal` child inside `InArgument`. The `gen_multiple_assign()` generator handles this when the value expression is `""`.

### Log Message
→ **Use `gen_logmessage()`** — generates correct XAML deterministically.


### Input Dialog (Text)

Shows a dialog with a text field. Result is always `String`.

→ **Use `gen_input_dialog()`** — generates correct XAML deterministically.


### Input Dialog (Dropdown)

Shows a dialog with a dropdown list. Options are **semicolon-separated** in `OptionsString`. `Options` stays `{x:Null}` (do NOT use VB arrays).

→ **Use `gen_input_dialog()`** — generates correct XAML deterministically.


Properties:
- `Label` — prompt text displayed to the user
- `Title` — dialog window title
- `IsPassword` — masks input (True/False)
- `OptionsString` — semicolon-separated dropdown options; `{x:Null}` for text input
- `Options` — always `{x:Null}` (legacy, do NOT use VB array expressions)
- `TopMost` — keep dialog above other windows (True/False)
- `Result` — **must** use child element syntax (not inline attribute). Generator handles this.

### Message Box
→ **Use `gen_message_box()`** — generates correct XAML deterministically.

Properties:
- `Caption` — window title (optional, null for default)
- `Text` — body text (VB.NET expression)
- `ChosenButton` — OutArgument to capture which button was clicked
- `AutoCloseAfter` — TimeSpan, "00:00:00" = no auto-close

### Comment Out
Wraps activities to disable them without deleting. The wrapped activities are not executed.
→ **Use `gen_comment_out()`** — generates correct XAML deterministically.


### Delay
→ **Use `gen_delay()`** — pass seconds as integer. Expression: `TimeSpan.FromSeconds(N)`.

### Comment
→ **Use `gen_comment()`** — generates correct XAML deterministically.


## Variable and Argument Declarations

### Variables (inside Sequence.Variables or Flowchart.Variables)

Naming: camelCase with type prefix. See SKILL.md → Naming Conventions for full prefix table. Use the `variables` array in the JSON spec for `generate_workflow.py` — type shortcuts: `String`, `Int32`, `Boolean`, `DataTable`, `SecureString`, `UiElement`, `Dictionary`, `Array_String`, `QueueItem`.

**⚠️ CRITICAL — Array types:** `x:String[]` is INVALID — the `x:` namespace has no array support. Use `s:String[]`. The generators auto-normalize these types. Lint 93 catches this.

```xml
<!-- WRONG: x:String[] does not exist -->
<Variable x:TypeArguments="x:String[]" Name="arrLines" />

<!-- CORRECT: s:String[] with xmlns:s declared on root Activity -->
<Variable x:TypeArguments="s:String[]" Name="arrLines" />
```

**Complex defaults** — pass a `default` value in the variables spec (e.g., `"new DataTable"`, `"new List(Of String)"`). The generator wraps it in `VisualBasicValue`.

### Arguments (at Activity level, before the main Sequence)

Naming: `{direction}_{typePrefix}{Name}` — direction prefix (`in_`, `out_`, `io_`) + type prefix + descriptive name. Use the `arguments` array in the JSON spec for `generate_workflow.py`.

> **⚠️ DataTable prefix is NOT always `sd`.** The prefix depends on the file's xmlns declarations. `generate_workflow.py` resolves this automatically via Option B strategy. Lint 87 catches wrong prefix usage.

## Control Flow Activities
