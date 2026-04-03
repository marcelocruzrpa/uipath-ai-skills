"""Hallucination-catching lint rules."""

import os
import re

from ._registry import lint_rule
from ._context import FileContext, ValidationResult
from ._constants import (
    _RE_DISPLAY_NAME, _RE_NSELECTITEM_BLOCK,
)

# Pre-compiled placeholder patterns for desktop app FilePath detection (lint 17)
_PLACEHOLDER_FILEPATH_PATTERNS = [
    re.compile(r'FilePath="C:\\path\\', re.IGNORECASE),
    re.compile(r'FilePath="C:\\Program Files\\App\\', re.IGNORECASE),
    re.compile(r'FilePath="path[\\/]to[\\/]', re.IGNORECASE),
    re.compile(r'FilePath="app\.exe"', re.IGNORECASE),
    re.compile(r'FilePath="YOUR_', re.IGNORECASE),
    re.compile(r'FilePath="TODO', re.IGNORECASE),
]


@lint_rule(17)
def lint_desktop_app_card(ctx: FileContext, result: ValidationResult):
    """Lint 17: NApplicationCard for desktop apps must have FilePath in TargetApp."""
    try:
        content = ctx.active_content
    except Exception:
        return

    if "NApplicationCard" not in content:
        return

    # Check for placeholder FilePath values (AI-generated junk paths)
    for pattern in _PLACEHOLDER_FILEPATH_PATTERNS:
        if pattern.search(content):
            match = re.search(r'FilePath="([^"]*)"', content)
            path_val = match.group(1) if match else "?"
            result.error(
                f"NApplicationCard has placeholder FilePath='{path_val}' — "
                f"replace with the actual executable path before running"
            )
            break

    # Check OpenMode — if IfNotOpen or Always, FilePath or Url is needed
    # Note: omitting OpenMode defaults to IfNotOpen
    has_explicit_never = re.search(
        r'<uix:NApplicationCard[^>]*OpenMode="Never"', content
    )
    if has_explicit_never and 'OpenMode="IfNotOpen"' not in content and 'OpenMode="Always"' not in content:
        return  # All NApplicationCards are OpenMode=Never, no FilePath needed

    # Check if this is a desktop app (selector uses <wnd> not <html>)
    # Match both self-closing and non-self-closing TargetApp elements
    target_apps = re.findall(
        r'<uix:TargetApp\s[^>]*Selector="([^"]*)"', content
    )
    for target in target_apps:
        is_desktop = "&lt;wnd " in target or "<wnd " in target
        is_browser = "&lt;html " in target or "<html " in target

        if is_desktop:
            # Desktop app: must have FilePath (attribute or child element form)
            has_filepath_attr = bool(re.search(
                r'<uix:TargetApp[^>]*FilePath="[^"]+?"', content
            ))
            has_filepath_elem = bool(re.search(
                r'<uix:TargetApp\.FilePath>\s*<InArgument[^>]*>\[.+?\]</InArgument>',
                content
            ))
            if not has_filepath_attr and not has_filepath_elem:
                result.error(
                    "NApplicationCard targets a desktop app (wnd selector) with "
                    "OpenMode='IfNotOpen' or 'Always' but TargetApp is missing "
                    "FilePath — UiPath cannot launch the app without it"
                )
        elif is_browser:
            # Browser app: should have Url for IfNotOpen/Always
            has_url = re.search(
                r'<uix:TargetApp[^>]*Url="[^"]+?"', content
            )
            if not has_url:
                result.warn(
                    "NApplicationCard targets a browser with "
                    "OpenMode='IfNotOpen' or 'Always' but TargetApp has no Url — "
                    "consider adding Url so UiPath can navigate to the correct page"
                )

    # Check InteractionMode — DebuggerApi is browser-only
    for target in target_apps:
        is_desktop = "&lt;wnd " in target or "<wnd " in target
        if is_desktop:
            if 'InteractionMode="DebuggerApi"' in content:
                result.warn(
                    "NApplicationCard uses InteractionMode='DebuggerApi' for a desktop app — "
                    "this is browser-only. Use 'HardwareEvents', 'Simulate', or 'WindowMessages'"
                )


@lint_rule(23)
def lint_unresolved_activity(ctx: FileContext, result: ValidationResult):
    """Lint 23: Detect UnresolvedActivity — means a hallucinated activity name was used.
    
    Studio wraps unknown activities in ui:UnresolvedActivity. If this appears in
    generated XAML, Claude invented a non-existent activity instead of using the
    correct one (e.g. 'DeleteFile' instead of 'DeleteFileX').
    """
    try:
        content = ctx.active_content
    except Exception:
        return

    matches = re.findall(r'<ui:UnresolvedActivity\b', content)
    if matches:
        # Try to extract DisplayName for context
        names = re.findall(
            r'<ui:UnresolvedActivity[^>]*DisplayName="([^"]*)"', content
        )
        name_info = f" ({', '.join(names)})" if names else ""
        result.errors.append(
            f"{len(matches)} UnresolvedActivity element(s){name_info} — "
            f"Studio could not resolve the activity type. This means a "
            f"non-existent activity name was used. Check xaml-data.md or "
            f"xaml-*.md for the correct activity element name."
        )


@lint_rule(23)
def lint_hallucinated_property_names(ctx: FileContext, result: ValidationResult):
    """Lint 23: Detect hallucinated property names on UiPath activities.
    
    Maps known wrong property names to correct ones. Extensible — add entries
    as new hallucination patterns are discovered in battle tests.
    """
    try:
        content = ctx.active_content
    except Exception:
        return

    # Format: (wrong_attr, correct_attr, activity_context_hint)
    HALLUCINATED = [
        ("OrderByColumnName=", "ColumnName",  "SortDataTable"),
        ("OrderByType=",       "SortOrder",   "SortDataTable"),
        ("ClickBeforeTyping=", "ClickBeforeMode",  "NTypeInto — use ClickBeforeMode=\"Single\""),
    ]

    # Merge plugin-provided hallucination patterns (e.g. Action Center)
    try:
        from plugin_loader import get_hallucination_patterns
        HALLUCINATED.extend(get_hallucination_patterns())
    except ImportError:
        pass

    found = []
    for wrong, correct, context in HALLUCINATED:
        if wrong in content:
            count = content.count(wrong)
            found.append(f"'{wrong.rstrip('=')}' x{count} -> use '{correct}' ({context})")

    # EmptyField= but NOT EmptyFieldMode= — must avoid false positive
    ef_pattern = re.findall(r'\bEmptyField="[^"]*"', content)
    ef_mode_count = content.count('EmptyFieldMode=')
    ef_bare = len(ef_pattern) - ef_mode_count
    if ef_bare > 0:
        found.append(f"'EmptyField' x{ef_bare} -> use 'EmptyFieldMode' (NTypeInto — use EmptyFieldMode=\"SingleLine\")")

    if found:
        result.errors.append(
            "Hallucinated property name(s): " + "; ".join(found)
        )

    # .TargetAnchorable> child element — should be .Target>
    # The TYPE inside is TargetAnchorable, but the child element name is always .Target
    ta_child = re.findall(r'<uix:N\w+\.TargetAnchorable>', content)
    if ta_child:
        activities = set(re.findall(r'<(uix:N\w+)\.TargetAnchorable>', content))
        result.error(
            f"[lint 23] {len(ta_child)} use(s) of '.TargetAnchorable>' child element — "
            f"property does NOT exist on {', '.join(activities)}. "
            f"The child element is '.Target>' (the TYPE inside it is TargetAnchorable). "
            f"Example: <uix:NClick.Target> not <uix:NClick.TargetAnchorable>"
        )

    # NApplicationCard: Url= is hallucinated — URL belongs in TargetApp child element
    if re.search(r'<uix:NApplicationCard\b[^>]*\sUrl="', content):
        result.error(
            "[lint 23] NApplicationCard has 'Url' attribute — this property does NOT exist "
            "on NApplicationCard. URL belongs in the <uix:TargetApp Url=\"...\"> child element. "
            "See golden sample WebAppName_Launch.xaml."
        )

    # TargetAnchorable: bare Selector= is hallucinated — use FullSelectorArgument
    # Must not false-positive on FullSelectorArgument, ScopeSelectorArgument, FuzzySelectorArgument
    if 'TargetAnchorable' in content:
        for line in content.split('\n'):
            if 'TargetAnchorable' not in line:
                continue
            # Remove known valid *Selector* attributes to see if bare Selector= remains
            cleaned = re.sub(r'(Full|Scope|Fuzzy)SelectorArgument="[^"]*"', '', line)
            if re.search(r'\bSelector="', cleaned):
                result.error(
                    "[lint 23] TargetAnchorable has bare 'Selector' attribute — "
                    "property does NOT exist. Use FullSelectorArgument=\"...\" for "
                    "the element selector and ScopeSelectorArgument=\"...\" for app scope."
                )
                break

    # AnchorSelector= on TargetAnchorable — doesn't exist
    if re.search(r'<uix:TargetAnchorable\b[^>]*\sAnchorSelector="', content):
        result.error(
            "[lint 23] TargetAnchorable has 'AnchorSelector' attribute — property does NOT exist. "
            "Anchor-based targeting uses a separate <uix:TargetAnchorable> element "
            "inside an <ActivityAction> anchor delegate. See xaml-ui-automation.md Anchor-Based Targeting."
        )

    # uix:Selector element — doesn't exist as a type
    if "<uix:Selector " in content or "<uix:Selector>" in content:
        result.error(
            "[lint 23] <uix:Selector> element does NOT exist. "
            "Selectors are defined as attributes on <uix:TargetAnchorable> elements "
            "(FullSelectorArgument, ScopeSelectorArgument). "
            "If you need a Check App State, use <uix:NCheckState> with .Target child."
        )

    # NCheckState: Appears= is hallucinated — use IfExists/IfNotExists child elements
    if re.search(r'<uix:NCheckState\b[^>]*\sAppears="', content):
        result.error(
            "[lint 23] NCheckState has 'Appears' attribute — property does NOT exist. "
            "NCheckState uses <uix:NCheckState.IfExists> and <uix:NCheckState.IfNotExists> "
            "child Sequence elements. Mode=\"Appears\" exists only on VerifyExecutionOptions "
            "(NClick/NTypeInto verification), NOT on NCheckState."
        )

    # GetRobotAsset: Result= is hallucinated — correct property is .Value (element syntax)
    for match in re.finditer(r'<ui:GetRobotAsset\b[^>]*\bResult=', content):
        result.error(
            "[lint 23] GetRobotAsset has 'Result' — this property does NOT exist. "
            "Use element syntax: <ui:GetRobotAsset.Value>"
            "<OutArgument x:TypeArguments=\"x:String\">[var]</OutArgument>"
            "</ui:GetRobotAsset.Value>"
        )

    # GetRobotCredential: Result= is hallucinated — use Password= and Username= outputs
    for match in re.finditer(r'<ui:GetRobotCredential\b[^>]*\bResult=', content):
        result.error(
            "[lint 23] GetRobotCredential has 'Result' — this property does NOT exist. "
            "Use Password=\"[secstrPassword]\" and Username=\"[strUsername]\" attributes. "
            "Password outputs SecureString, Username outputs String."
        )

    # GetRobotCredential: password stored as String instead of SecureString
    if 'GetRobotCredential' in content:
        cred_password_vars = re.findall(
            r'<ui:GetRobotCredential\b[^>]*\bPassword="\[(\w+)\]"', content
        )
        for var_name in cred_password_vars:
            # Check if this variable is declared as String instead of SecureString
            string_decl = re.search(
                rf'<Variable x:TypeArguments="x:String" Name="{re.escape(var_name)}"',
                content
            )
            if string_decl:
                result.error(
                    f"[lint 23] GetRobotCredential Password bound to '{var_name}' "
                    f"which is declared as x:String — Password outputs SecureString. "
                    f"Change variable type to ss:SecureString and use SecureText= "
                    f"(not Text=) on NTypeInto for password fields."
                )

    # GetRobotAsset used for credentials (password, secret, key, token)
    CRED_PATTERNS = re.compile(
        r'<ui:GetRobotAsset\b[^>]*AssetName="[^"]*'
        r'(?:Password|Secret|Token|ApiKey|ClientSecret|PrivateKey)[^"]*"',
        re.IGNORECASE
    )
    for match in CRED_PATTERNS.finditer(content):
        asset = re.search(r'AssetName="([^"]*)"', match.group())
        name = asset.group(1) if asset else "unknown"
        result.error(
            f"[lint 23] GetRobotAsset used for credential-like asset '{name}' — "
            "use GetRobotCredential instead. It stores secrets as SecureString "
            "and returns username + password from a single Credential asset type."
        )

    # AddQueueItem: SpecificContent is hallucinated — correct XAML property is ItemInformation
    # SpecificContent is a RUNTIME property for READING queue items (TransactionItem.SpecificContent("Key"))
    # ItemInformation is the XAML property for WRITING queue items
    if re.search(r'AddQueueItem\.SpecificContent|SpecificContent>', content):
        result.error(
            "[lint 23] AddQueueItem uses 'SpecificContent' — this property does NOT exist in XAML. "
            "SpecificContent is a RUNTIME property for READING queue items "
            "(TransactionItem.SpecificContent(\"Key\")). "
            "For WRITING, use <ui:AddQueueItem.ItemInformation> with "
            "<InArgument x:TypeArguments=\"x:String\" x:Key=\"FieldName\">[value]</InArgument> entries. "
            "Use gen_add_queue_item() from scripts/generate_activities.py."
        )

    # AddQueueItem: DictionaryCollection is hallucinated — correct property is ItemInformation
    # Model invents .DictionaryCollection with scg:Dictionary(String, Argument) wrapper
    if re.search(r'AddQueueItem\.DictionaryCollection|DictionaryCollection>', content):
        result.error(
            "[lint 23] AddQueueItem uses hallucinated 'DictionaryCollection' — "
            "this member does NOT exist. Correct property is <ui:AddQueueItem.ItemInformation>. "
            "ItemInformation takes bare <InArgument> children directly — NO Dictionary wrapper needed. "
            "Use gen_add_queue_item() from scripts/generate_activities.py."
        )

    # AddQueueItem: Dictionary(String, Argument) wrapper is hallucinated
    # Model wraps ItemInformation entries in scg:Dictionary — not needed
    # IMPORTANT: Only check WITHIN AddQueueItem.ItemInformation blocks, not the whole file
    # (Config argument uses Dictionary(String,Object) which false-matches)
    item_info_blocks = re.findall(
        r'<ui:AddQueueItem\.ItemInformation>(.*?)</ui:AddQueueItem\.ItemInformation>',
        content, re.DOTALL
    )
    for block in item_info_blocks:
        if re.search(r'Dictionary.*String.*Argument|scg:Dictionary', block):
            result.error(
                "[lint 23] AddQueueItem.ItemInformation wrapped in Dictionary(String,Argument) — "
                "hallucinated structure. ItemInformation takes bare <InArgument> children directly, "
                "with NO scg:Dictionary wrapper. Also: 'ui:Argument' doesn't exist as a type. "
                "Use gen_add_queue_item() from scripts/generate_activities.py."
            )
            break

    # BuildDataTable: .Columns / DataTableColumnInfo are hallucinated
    # BuildDataTable has NO child elements — uses TableInfo attribute with XSD schema string
    if re.search(r'BuildDataTable\.Columns|DataTableColumnInfo', content):
        result.error(
            "[lint 23] BuildDataTable uses hallucinated '.Columns' child element with "
            "DataTableColumnInfo — this property does NOT exist. "
            "BuildDataTable is a SELF-CLOSING tag with a TableInfo=\"...\" attribute "
            "containing an XML-escaped XSD schema string. "
            "See xaml-data.md → BuildDataTable for correct pattern."
        )

    # FilterDataTable: .FilterRowsCollection, ColumnName=, Value= are hallucinated
    # Correct: .Filters, .Column child element, .Operand child element, Operator= attribute
    fdt_hallucinations = []
    if 'FilterRowsCollection' in content:
        fdt_hallucinations.append(
            "'.FilterRowsCollection' — does NOT exist, use '.Filters'"
        )
    if re.search(r'FilterOperationArgument[^>]*\bColumnName=', content):
        fdt_hallucinations.append(
            "'ColumnName' attribute — does NOT exist, use "
            "<ui:FilterOperationArgument.Column><InArgument x:TypeArguments=\"x:String\">"
            "[\"colName\"]</InArgument></ui:FilterOperationArgument.Column>"
        )
    if re.search(r'FilterOperationArgument[^>]*\bValue=', content):
        fdt_hallucinations.append(
            "'Value' attribute — does NOT exist, use "
            "<ui:FilterOperationArgument.Operand><InArgument x:TypeArguments=\"x:String\">"
            "[\"value\"]</InArgument></ui:FilterOperationArgument.Operand>"
        )
    # Operand="EQ" means the LLM put the operator in Operand (Operand is the value, Operator is the op)
    _ALL_OPS = "EQ|NE|LT|LE|GT|GE|CONTAINS|STARTS_WITH|ENDS_WITH|EMPTY|NOT_EMPTY|Contains|StartsWith|EndsWith|IsEmpty|IsNotEmpty"
    if re.search(rf'FilterOperationArgument[^>]*\bOperand="(?:{_ALL_OPS})"', content):
        fdt_hallucinations.append(
            "Operator value in 'Operand' attribute — Operand is the VALUE child element, "
            "the comparison operator goes in the 'Operator' attribute"
        )
    if fdt_hallucinations:
        result.error(
            "[lint 23] FilterDataTable uses hallucinated properties — Studio crash: "
            + "; ".join(fdt_hallucinations)
            + ". Use gen_filter_data_table() from scripts/generate_activities.py."
        )

    # Catch symbolic operators and wrong mixed-case enum values that crash Studio
    _VALID_FILTER_OPS = {"EQ", "NE", "LT", "LE", "GT", "GE",
                         "CONTAINS", "STARTS_WITH", "ENDS_WITH", "EMPTY", "NOT_EMPTY"}
    for m in re.finditer(r'FilterOperationArgument[^>]*\bOperator="([^"]*)"', content):
        op = m.group(1)
        if op in ('=', '==', '!=', '<>', '<', '<=', '>', '>='):
            result.error(
                f"[lint 23] FilterOperationArgument Operator=\"{op}\" — "
                f"'{op}' is not a valid FilterOperator enum value. "
                f"Use UiPath enum names: EQ, NE, LT, LE, GT, GE, CONTAINS, STARTS_WITH, "
                f"ENDS_WITH, EMPTY, NOT_EMPTY. Studio throws 'is not a valid value for FilterOperator'."
            )
        elif op not in _VALID_FILTER_OPS:
            result.warn(
                f"[lint 23] FilterOperationArgument Operator=\"{op}\" — "
                f"may not be a valid FilterOperator. Studio uses: "
                f"EQ, NE, LT, LE, GT, GE, CONTAINS, STARTS_WITH, ENDS_WITH, EMPTY, NOT_EMPTY. "
                f"Use gen_filter_data_table() to ensure correct enum values."
            )


@lint_rule(25)
def lint_banned_outlook_activities(ctx: FileContext, result: ValidationResult):
    """Lint 25: Detect Outlook-specific activities that should not be used.
    
    These activities require Outlook Desktop installed and are not portable.
    Use Integration Service activities instead (GetIMAPMailMessages, SendMail).
    """
    try:
        content = ctx.active_content
    except Exception:
        return

    banned = [
        ("OutlookApplicationCard", "Use GetIMAPMailMessages (Integration Service)"),
        ("ForEachEmailX", "Use ui:ForEach x:TypeArguments=\"snm:MailMessage\""),
        ("GetOutlookMailMessages", "Use GetIMAPMailMessages (Integration Service)"),
        ("MoveOutlookMessage", "Not portable — Outlook Desktop only"),
        ("MoveMailMessage", "Not portable — Outlook Desktop only"),
        ("SendOutlookMailMessage", "Use ui:SendMail (SMTP via Integration Service)"),
    ]

    for activity_name, replacement in banned:
        # Match as element name or in UnresolvedActivity DisplayName
        if re.search(rf'<(?:\w+:)?{activity_name}\b', content) or \
           re.search(rf'DisplayName="[^"]*\({activity_name}\)', content) or \
           re.search(rf'DisplayName="[^"]*{activity_name}[^"]*"', content, re.IGNORECASE):
            result.error(
                f"Banned Outlook activity '{activity_name}' detected. "
                f"{replacement}. Outlook activities require Outlook Desktop "
                f"and are not portable across environments."
            )


@lint_rule(30)
def lint_nselectitem_hallucinations(ctx: FileContext, result: ValidationResult):
    """Lint 30: Detect hallucinated properties/patterns on NSelectItem.
    
    Common hallucinations:
    - InteractionMode (exists on NTypeInto/NClick, NOT on NSelectItem)
    - Items wrapped in InArgument (must be scg:List with x:String elements)
    """
    try:
        content = ctx.active_content
    except Exception:
        return
    
    if "NSelectItem" not in content:
        return
    
    # Check for InteractionMode on NSelectItem
    # Find NSelectItem elements and check if they have InteractionMode
    for match in _RE_NSELECTITEM_BLOCK.finditer(content):
        attrs = match.group(1)
        if 'InteractionMode' in attrs:
            result.error(
                "[lint 30] NSelectItem has 'InteractionMode' — this property does NOT exist "
                "on NSelectItem (only on NTypeInto/NClick). Studio crashes with "
                "'Could not find member InteractionMode'. Remove it."
            )
    
    # Check for Items wrapped in InArgument instead of scg:List
    if re.search(r'NSelectItem\.Items[^<]*<InArgument', content):
        result.error(
            "[lint 30] NSelectItem.Items wrapped in InArgument — wrong format. "
            "Must be <scg:List x:TypeArguments=\"x:String\"><x:String>Option</x:String>...</scg:List>. "
            "Studio crashes with 'InArgument(List) is not assignable to item type x:String'."
        )
    
    # Check for x:List instead of scg:List (x:List doesn't exist in XAML namespace)
    if re.search(r'<x:List\b', content):
        result.error(
            "[lint 30] Found <x:List> — type 'List' does not exist in the x: (XAML) namespace. "
            "Use <scg:List x:TypeArguments=\"x:String\" Capacity=\"N\"> instead. "
            "Studio crashes with 'Could not find type List(String) in namespace'."
        )
    
    # Check for wrong Version on NSelectItem (must be V1, not V5)
    for match in _RE_NSELECTITEM_BLOCK.finditer(content):
        attrs = match.group(1)
        ver_match = re.search(r'Version="(V\d+)"', attrs)
        if ver_match and ver_match.group(1) != "V1":
            result.error(
                f"[lint 30] NSelectItem Version=\"{ver_match.group(1)}\" — must be \"V1\". "
                "Use gen_nselectitem() from scripts/generate_activities.py to avoid version hallucinations."
            )


@lint_rule(33)
def lint_napplicationcard_enums(ctx: FileContext, result: ValidationResult):
    """Lint 33: Detect invalid enum values on NApplicationCard.
    
    Catches hallucinated AttachMode, OpenMode, CloseMode, InteractionMode values
    that will crash Studio with 'is not a valid value for NApp*' errors.
    """
    try:
        content = ctx.active_content
    except Exception:
        return

    if "NApplicationCard" not in content:
        return

    VALID_ENUMS = {
        "AttachMode": {"SingleWindow", "ByInstance"},
        "OpenMode": {"Always", "IfNotOpen", "Never"},
        "CloseMode": {"Always", "Never", "IfOpenedByAppBrowser"},
        "InteractionMode": {"DebuggerApi", "Simulate", "WindowMessages", "HardwareEvents"},
        "WindowResize": {"None", "Maximize", "Minimize", "Restore"},
        "Version": {"V1", "V2"},
    }

    # Only check attributes on NApplicationCard elements, not child activities
    # (child activities like NClick/NTypeInto can use "SameAsCard" for InteractionMode)
    card_pattern = re.compile(
        r'<uix:NApplicationCard\s([^>]*?)(?:>|/>)', re.DOTALL
    )
    for card_match in card_pattern.finditer(content):
        card_attrs = card_match.group(1)
        for attr, valid_values in VALID_ENUMS.items():
            attr_pattern = re.compile(rf'{attr}="([^"\[\]]*)"')
            for match in attr_pattern.finditer(card_attrs):
                value = match.group(1)
                # Skip fully qualified enums like UiPath.UIAutomationNext.Enums...
                if value.startswith("UiPath."):
                    continue
                if value not in valid_values:
                    result.error(
                        f"[lint 33] NApplicationCard has {attr}=\"{value}\" — "
                        f"'{value}' is NOT a valid enum value. "
                        f"Valid values: {', '.join(sorted(valid_values))}"
                    )


@lint_rule(71)
def lint_double_escaped_quotes(ctx: FileContext, result: ValidationResult):
    """Lint 71: Detect double-escaped quotes in VB.NET expressions.

    When the model writes &amp;quot; in XML text nodes (InArgument values),
    the XML parser renders it as literal &quot; — VB.NET then sees 'quot' as
    a variable name, producing:
      BC30451: 'quot' is not declared
      BC30037: Character is not valid (the & and ; characters)
      BC30201: Expression expected

    Correct: In text nodes, use literal " (valid XML in text content).
    In attributes, use &quot; (XML parser resolves to ").

    The generator gen_invoke_workflow() prevents this by handling escaping
    correctly. This lint catches hand-written InvokeWorkflowFile arguments.
    """
    try:
        content = ctx.active_content
    except Exception:
        return

    # Pattern 1: &amp;quot; in text content (double-escaped)
    # After XML parse, this becomes literal &quot; which VB.NET can't handle
    for match in re.finditer(r'&amp;quot;', content):
        pos = match.start()
        # Get line number for context
        line_num = content[:pos].count('\n') + 1
        # Check if inside an expression context (near [...])
        context_start = max(0, pos - 100)
        context = content[context_start:pos + 50]
        if '[' in context:
            result.error(
                f"[lint 71] Double-escaped quote '&amp;quot;' at line {line_num} — "
                f"VB.NET sees literal '&quot;' producing BC30451: 'quot' is not declared. "
                f"In text nodes (InArgument values), use literal \" instead. "
                f"In attributes, use &quot; (XML parser resolves it). "
                f"Use gen_invoke_workflow() from generate_activities.py to avoid this."
            )
            return  # One error is enough to flag the file


@lint_rule(78)
def lint_uielement_stored_in_config(ctx: FileContext, result: ValidationResult):
    """Lint 78: UiElement must NOT be stored in Config dictionary.

    Anti-pattern: in_Config("app_WebApp") = uiWebApp or Assign to Config("...") with
    a UiElement variable. Config is Dictionary(String, Object) — storing UiElement
    there loses type safety, breaks the typed argument chain, and makes downstream
    workflows unable to use InOut direction (which requires typed UiElement args).

    Correct: UiElement flows via typed OutArgument/InOutArgument through the chain:
    Launch → InitAllApplications → Main → Process → action workflows.
    """
    content = ctx.active_content

    # Extract each <Assign ...>...</Assign> block and check if it assigns
    # a UiElement variable to in_Config(...)
    assign_blocks = re.findall(
        r'<Assign[^>]*>.*?</Assign>', content, re.DOTALL
    )

    for block in assign_blocks:
        # Check if Assign.To targets in_Config("...")
        has_config_target = bool(re.search(
            r'Assign\.To.*?in_Config\s*\(', block, re.DOTALL
        ))
        # Check if Assign.Value contains a UiElement variable
        has_ui_value = bool(re.search(
            r'Assign\.Value.*?(?:\[(?:ui[A-Z]\w+|out_ui\w+|io_ui\w+)\])',
            block, re.DOTALL
        ))
        if has_config_target and has_ui_value:
            result.error(
                f"[lint 78] UiElement appears to be stored in the Config dictionary "
                f"(e.g., in_Config(\"app_...\") = uiVar). This is an anti-pattern — "
                f"Config is Dictionary(String, Object), losing type safety. UiElement "
                f"references MUST flow via typed arguments: Launch (out_ui*) → "
                f"InitAllApplications (out_ui*) → Main (variable) → Process (io_ui*) → "
                f"action workflows (io_ui*). See skill-guide.md → UiElement reference chain."
            )
            return  # One error is enough

    # Also check MultipleAssign — AssignOperation with To/Value pattern
    multi_blocks = re.findall(
        r'<ui:AssignOperation[^>]*>.*?</ui:AssignOperation>', content, re.DOTALL
    )
    for block in multi_blocks:
        if re.search(r'in_Config\s*\(', block) and re.search(
            r'(?:ui[A-Z]\w+|out_ui\w+|io_ui\w+)', block
        ):
            result.error(
                f"[lint 78] UiElement appears to be stored in the Config dictionary "
                f"via MultipleAssign. This is an anti-pattern — use typed arguments "
                f"instead. See skill-guide.md → UiElement reference chain."
            )
            return


@lint_rule(83)
def lint_double_bracketed_expression(ctx: FileContext, result: ValidationResult):
    """Lint 83: Double-bracketed expressions [[...]] are invalid VB.NET syntax.

    UiPath uses single brackets [expr] as the expression delimiter. Wrapping an
    expression inside another pair of brackets [[expr]] is a hallucination pattern
    where the model treats the inner brackets as part of the expression syntax.

    Examples of the bad pattern:
      Message="[[String.Format(&quot;...&quot;, strVar)]]"
      Message="[[strSomething + &quot; text&quot;]]"

    Studio shows a compile error: Expression expected / Unexpected token '['.
    The fix is to remove the outer bracket pair: [String.Format(...)]
    """
    content = ctx.active_content

    # Detect [[...]] in attribute values (handles both raw and &quot;-encoded)
    double_bracket_attrs = re.findall(r'="\[\[', content)
    # Also in text nodes (rare but possible)
    double_bracket_text = re.findall(r'>\[\[', content)

    hits = len(double_bracket_attrs) + len(double_bracket_text)
    if hits:
        result.error(
            f"[lint 83] {hits} double-bracketed expression(s) [[...]] found. "
            f"UiPath uses single brackets [expr] as the expression delimiter — "
            f"[[String.Format(...)]] is invalid VB.NET and causes a compile error. "
            f"Remove the outer bracket pair: [[expr]] → [expr]."
        )


@lint_rule(88)
def lint_sequence_variables_after_children(ctx: FileContext, result: ValidationResult):
    """Lint 88: Sequence.Variables placed after child activities — XamlDuplicateMemberException.

    In XAML, <Sequence.Variables> must appear before any child activities inside
    a <Sequence>. If a child activity appears first, the XAML parser opens the
    implicit 'Activities' collection. When <Sequence.Variables> then appears,
    the parser tries to close and reopen 'Activities', causing:
      'Activities' property has already been set on 'Sequence'.

    Correct order inside <Sequence>:
      1. <sap:WorkflowViewStateService.ViewState> (optional)
      2. <Sequence.Variables> (optional)
      3. Child activities
    """
    try:
        content = ctx.content
    except Exception:
        return

    errors = []
    # Find every <Sequence.Variables> and check if any child activity precedes it
    # within the same <Sequence> scope
    for m in re.finditer(r'<Sequence\.Variables>', content):
        var_pos = m.start()
        # Walk backwards to find the opening <Sequence that owns this .Variables
        # Find the nearest preceding <Sequence (not <Sequence.Variables)
        search_region = content[:var_pos]
        seq_open = -1
        for sm in re.finditer(r'<Sequence[\s>]', search_region):
            # Exclude <Sequence.Variables itself
            tag_end = sm.end()
            if tag_end < len(search_region) and search_region[sm.start():].startswith('<Sequence.'):
                continue
            seq_open = sm.start()

        if seq_open == -1:
            continue

        # Get the content between <Sequence ...> closing bracket and <Sequence.Variables>
        # Find end of the opening Sequence tag
        seq_tag_end = content.index('>', seq_open) + 1
        between = content[seq_tag_end:var_pos]

        # Strip ViewState blocks and whitespace — anything else is a child activity
        cleaned = re.sub(
            r'<sap:WorkflowViewStateService\.ViewState>.*?</sap:WorkflowViewStateService\.ViewState>',
            '', between, flags=re.DOTALL
        )
        cleaned = cleaned.strip()

        if cleaned:
            # There's content (child activities) before Sequence.Variables
            line_num = content[:var_pos].count('\n') + 1
            # Try to identify what activity came first
            first_tag = re.search(r'<(\w+:?\w+)', cleaned)
            tag_name = first_tag.group(1) if first_tag else 'unknown'
            errors.append(f"line {line_num}: <Sequence.Variables> appears after "
                          f"child activity <{tag_name}>")

    if errors:
        result.error(
            f"[lint 88] Sequence.Variables placed after child activities — "
            f"causes XamlDuplicateMemberException: 'Activities property has "
            f"already been set on Sequence'. Move <Sequence.Variables> block "
            f"before any child activities. {'; '.join(errors[:3])}"
        )

    # Also detect bare <Variable> tags that are direct children of <Sequence>
    # but NOT wrapped in <Sequence.Variables>. These cause:
    #   "Type 'Variable(String)' is not assignable to item type 'Activity'"
    # because the XAML parser tries to add Variable to the Activities collection.
    bare_errors = []
    for m in re.finditer(r'<Variable\s+x:TypeArguments=', content):
        var_pos = m.start()
        # Check if this Variable is inside a <Sequence.Variables> block
        # Find the nearest preceding opening tag
        before = content[:var_pos]
        # Look for the nearest unclosed <Sequence.Variables> or </Sequence.Variables>
        last_open = before.rfind('<Sequence.Variables>')
        last_close = before.rfind('</Sequence.Variables>')
        last_sm_open = before.rfind('<StateMachine.Variables>')
        last_sm_close = before.rfind('</StateMachine.Variables>')
        last_fc_open = before.rfind('<Flowchart.Variables>')
        last_fc_close = before.rfind('</Flowchart.Variables>')
        last_pb_open = before.rfind('<PickBranch.Variables>')
        last_pb_close = before.rfind('</PickBranch.Variables>')
        last_st_open = before.rfind('<State.Variables>')
        last_st_close = before.rfind('</State.Variables>')

        in_wrapper = (
            (last_open > last_close) or
            (last_sm_open > last_sm_close) or
            (last_fc_open > last_fc_close) or
            (last_pb_open > last_pb_close) or
            (last_st_open > last_st_close)
        )
        if not in_wrapper:
            line_num = content[:var_pos].count('\n') + 1
            # Extract variable name
            name_match = re.search(r'Name="([^"]+)"', content[var_pos:var_pos+200])
            var_name = name_match.group(1) if name_match else 'unknown'
            bare_errors.append(f"line {line_num}: bare <Variable> '{var_name}' "
                               f"not wrapped in <Sequence.Variables>")

    if bare_errors:
        result.error(
            f"[lint 88] Bare <Variable> tag outside <Sequence.Variables> wrapper — "
            f"causes 'Type Variable(String) is not assignable to item type Activity'. "
            f"Wrap in <Sequence.Variables>...</Sequence.Variables>. "
            f"{'; '.join(bare_errors[:3])}"
        )


@lint_rule(103)
def lint_ui_heavy_no_trycatch(ctx: FileContext, result: ValidationResult):
    """Lint 103: UI-heavy workflow (>5 UI interaction activities) without TryCatch.

    Desktop form-filling workflows are fragile — a single selector miss
    cascades through all remaining activities. Wrap the UI block in TryCatch
    for graceful error handling.
    """
    content = ctx.active_content
    ui_activity_count = sum(
        len(re.findall(pattern, content))
        for pattern in [
            r'<uix:NClick\b',
            r'<uix:NTypeInto\b',
            r'<uix:NSelectItem\b',
            r'<uix:NDoubleClick\b',
        ]
    )
    if ui_activity_count <= 5:
        return
    if '<TryCatch' in content or '<TryCatch ' in content:
        return
    # Pick/PickBranch with NCheckState is valid error handling for Login
    # workflows — the Pick pattern validates success vs failure outcomes
    if '<Pick ' in content or '<Pick>' in content:
        return
    result.warn(
        f"[lint 103] Workflow has {ui_activity_count} UI interaction activities "
        f"(NClick/NTypeInto/NSelectItem) but no TryCatch — a single selector "
        f"failure will cascade. Wrap the UI block in TryCatch for graceful "
        f"error handling and logging."
    )


@lint_rule(73)
def lint_hallucinated_extract_data(ctx: FileContext, result: ValidationResult):
    """Lint 73: Hallucinated NExtractData types — Studio crash.

    The model invents plausible-looking child element types that don't exist:
    - uix:NExtractData (should be NExtractDataGeneric with x:TypeArguments)
    - uix:NExtractMetadata (doesn't exist — ExtractMetadata is a string attribute)
    - uix:NExtractColumn (doesn't exist — columns defined in ExtractDataSettings attribute)
    - NExtractData.ExtractMetadata (wrong parent type name)

    The real activity uses NExtractDataGeneric with two opaque XML string attributes
    (ExtractDataSettings, ExtractMetadata) plus .NextLink and .Target child elements.
    """
    try:
        content = ctx.active_content
    except Exception:
        return

    if "NExtractData" not in content:
        return

    hallucinations = []

    # Check for wrong activity name (NExtractData instead of NExtractDataGeneric)
    # Match <uix:NExtractData but NOT <uix:NExtractDataGeneric
    wrong_name = re.findall(r'<uix:NExtractData(?!Generic)\b', content)
    if wrong_name:
        hallucinations.append(
            f"'uix:NExtractData' ({len(wrong_name)}x) — correct name is "
            f"'uix:NExtractDataGeneric' with x:TypeArguments=\"sd2:DataTable\""
        )

    # Check for hallucinated child types
    if "NExtractMetadata" in content:
        hallucinations.append(
            "'uix:NExtractMetadata' — this type doesn't exist. "
            "ExtractMetadata is a string ATTRIBUTE on NExtractDataGeneric, "
            "not a child element"
        )

    if "NExtractColumn" in content:
        hallucinations.append(
            "'uix:NExtractColumn' — this type doesn't exist. "
            "Columns are defined inside the ExtractDataSettings string attribute, "
            "not as child elements"
        )

    # Check for hallucinated ExtractMetadataArgument type
    if "ExtractMetadataArgument" in content:
        hallucinations.append(
            "'uix:ExtractMetadataArgument' — this type doesn't exist. "
            "ExtractMetadata is a string ATTRIBUTE on NExtractDataGeneric "
            "containing XML-encoded selector rules, not a child element type"
        )

    # Check for NExtractDataGeneric missing x:TypeArguments (generic type requires it)
    # Only match opening element tags, not child property elements like .NextLink
    generic_no_typeargs = re.findall(
        r'<uix:NExtractDataGeneric\s(?!.*x:TypeArguments)[^>]*(?:/>|>)', content
    )
    if generic_no_typeargs:
        hallucinations.append(
            "NExtractDataGeneric missing x:TypeArguments=\"sd2:DataTable\" — "
            "it's a generic type; without TypeArguments Studio cannot resolve it"
        )

    if hallucinations:
        result.error(
            f"[lint 73] Hallucinated NExtractData types — Studio crash: "
            + "; ".join(hallucinations)
            + ". See xaml-ui-automation.md § Extract Table Data for the correct pattern. "
            "Use gen_nextractdata() from scripts/generate_activities.py."
        )



