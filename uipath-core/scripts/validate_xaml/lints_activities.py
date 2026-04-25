"""Activity-specific lint rules."""

import os
import re
from collections import Counter

from ._registry import lint_rule
from ._context import FileContext, ValidationResult
from ._constants import _RE_XKEY, _RE_DISPLAY_NAME

# Pre-compiled re.DOTALL pattern for HTTP Request blocks (lint 11)
_RE_HTTP_BLOCK = re.compile(r'(<ui:HttpClient[\s>][^>]*>)(.*?)</ui:HttpClient>', re.DOTALL)


@lint_rule(11)
def lint_http_request(ctx: FileContext, result: ValidationResult):
    """Lint 11: HTTP Request activity validation."""
    content = ctx.active_content

    # Find complete HttpClient elements including their opening tags and content
    http_full = _RE_HTTP_BLOCK.findall(content)
    if not http_full:
        return

    for i, (header, block) in enumerate(http_full, 1):
        # Check ResponseContent is captured
        if 'ResponseContent="{x:Null}"' in header or 'ResponseContent' not in header:
            result.warn(
                f"HTTP Request #{i}: ResponseContent not captured — "
                f"response body won't be available for processing"
            )

        # Check ResponseStatusCode is captured (important for error handling)
        if 'ResponseStatus="{x:Null}"' in header or 'ResponseStatus' not in header:
            result.warn(
                f"HTTP Request #{i}: ResponseStatus not captured — "
                f"can't check HTTP status code for error handling"
            )

        # Check for OAuth token in Authorization header without variable
        if 'Authorization' in block and '&quot;Bearer ' in block:
            # Check if it's a hardcoded token (no expression bracket)
            bearer_vals = re.findall(r'Bearer ([^&]*?)&quot;', block)
            for val in bearer_vals:
                if not val.startswith('[') and not val.startswith('{{'):
                    result.warn(
                        f"HTTP Request #{i}: hardcoded Bearer token — "
                        f"use a variable (e.g., [strToken]) for security"
                    )

    result.ok(f"HTTP Request: {len(http_full)} request(s) found")


@lint_rule(12)
def lint_invoke_code(ctx: FileContext, result: ValidationResult):
    """Lint 12: Invoke Code activity validation."""
    content = ctx.active_content

    invoke_codes = re.findall(r'<ui:InvokeCode[\s>][^>]*>', content)
    if not invoke_codes:
        return

    for i, ic in enumerate(invoke_codes, 1):
        # Check Language attribute exists
        if 'Language="' not in ic:
            result.warn(
                f"Invoke Code #{i}: missing Language attribute — "
                f"specify Language=\"CSharp\" or Language=\"VBNet\""
            )
        else:
            lang = re.search(r'Language="([^"]*)"', ic)
            if lang and lang.group(1) not in ("CSharp", "VBNet"):
                result.error(
                    f"Invoke Code #{i}: Language=\"{lang.group(1)}\" — "
                    f"must be 'CSharp' or 'VBNet'"
                )

        # Check Code attribute exists (or Code child element)
        if 'Code="' not in ic and '<ui:InvokeCode.Code>' not in content:
            result.warn(f"Invoke Code #{i}: no Code attribute found — activity has no code to execute")

    # Check argument consistency: InvokeCode arguments should have matching types
    invoke_code_blocks = re.findall(
        r'<ui:InvokeCode\b[^>]*>(.*?)</ui:InvokeCode>', content, re.DOTALL
    )
    for i, block in enumerate(invoke_code_blocks, 1):
        in_args = re.findall(r'<InArgument[^>]*x:Key="([^"]*)"', block)
        out_args = re.findall(r'<OutArgument[^>]*x:Key="([^"]*)"', block)
        inout_args = re.findall(r'<InOutArgument[^>]*x:Key="([^"]*)"', block)

        # Check for empty key names
        all_keys = in_args + out_args + inout_args
        empty = [k for k in all_keys if not k.strip()]
        if empty:
            result.error(f"Invoke Code #{i}: {len(empty)} argument(s) with empty x:Key")

        # Check for duplicate keys
        counts = Counter(all_keys)
        dupes = {k: v for k, v in counts.items() if v > 1}
        if dupes:
            for key, count in dupes.items():
                result.error(f"Invoke Code #{i}: argument key '{key}' appears {count} times")

    result.ok(f"Invoke Code: {len(invoke_codes)} block(s)")

    # Check for overengineered patterns that have dedicated activities
    code_blocks = re.findall(r'Code="([^"]*)"', content)
    for i, code in enumerate(code_blocks, 1):
        if any(p in code for p in ("ContentStream.CopyTo", ".Attachments", "Attachment")):
            result.warn(
                f"Invoke Code #{i}: manual attachment saving detected — "
                f"use ui:SaveMailAttachments with Filter=\"*.pdf\" instead of "
                f"InvokeCode with FileStream (see xaml-integrations.md)"
            )
        if "Columns.Add" in code and "New DataTable" in code:
            result.warn(
                f"Invoke Code #{i}: DataTable creation with Columns.Add — "
                f"use variable default 'new DataTable' + ui:AddDataColumn "
                f"activities instead (see xaml-data.md)"
            )

    # Check for InvokeCode used as assignment (should be MultipleAssign)
    invoke_code_full = re.findall(
        r'<ui:InvokeCode\b[^>]*Code="([^"]*)"[^>]*>(.*?)</ui:InvokeCode>',
        content, re.DOTALL
    )
    for i, (code, body) in enumerate(invoke_code_full, 1):
        out_count = len(re.findall(r'<(?:p:)?OutArgument\b', body))
        # Procedural keywords that justify InvokeCode
        has_procedural = any(kw in code for kw in (
            "For ", "For&#xA;", "While ", "Do ", "Using ",
            "Try", "Loop", "foreach", "for ", "while ", "using ",
            "try", "loop", "switch", "Select Case",
        ))
        if out_count >= 2 and not has_procedural:
            result.warn(
                f"Invoke Code #{i}: {out_count} OutArguments but no procedural logic "
                f"(no loops/using/try) — consider MultipleAssign with inline "
                f"VB expressions instead (see xaml-error-invoke.md)"
            )


@lint_rule(13)
def lint_file_operations(ctx: FileContext, result: ValidationResult):
    """Lint 13: File system activity validation."""
    content = ctx.active_content

    file_ops = []
    for activity in ("ui:CopyFile", "ui:MoveFile", "ui:DeleteFileX"):
        matches = re.findall(rf'<{re.escape(activity)}\b[^>]*/>', content)
        file_ops.extend((activity, m) for m in matches)

    if not file_ops:
        return

    for activity, match in file_ops:
        short_name = activity.split(":")[-1]

        # Check for hardcoded absolute paths (not expressions)
        path_val = re.search(r'\bPath="([^"]*)"', match)
        if path_val:
            p = path_val.group(1)
            # Hardcoded absolute path (not an expression [var], not relative Data\)
            if not p.startswith("[") and (p.startswith("C:\\") or p.startswith("D:\\") or p.startswith("/")):
                result.warn(
                    f"{short_name}: hardcoded absolute path \"{p[:60]}\" — "
                    f"use a variable or config value for portability"
                )

        # CopyFile/MoveFile: check destination exists
        if activity in ("ui:CopyFile", "ui:MoveFile"):
            dest_val = re.search(r'Destination="([^"]*)"', match)
            if not dest_val or dest_val.group(1) in ("{x:Null}", ""):
                result.warn(f"{short_name}: missing or null Destination — file will have no target")

            # Check Overwrite attribute
            if 'Overwrite=' not in match:
                result.warn(
                    f"{short_name}: no Overwrite attribute — "
                    f"defaults to False, will throw if destination exists"
                )

    result.ok(f"File operations: {len(file_ops)} activit(ies)")


@lint_rule(27)
def lint_invoke_code_datatable_setup(ctx: FileContext, result: ValidationResult):
    """Lint 27/33/34: InvokeCode anti-patterns.
    
    27: DataTable creation + Columns.Add → use Variable Default + AddDataColumn
    33: SqlConnection/SqlClient → use DatabaseConnect + ExecuteQuery/ExecuteNonQuery
    34: CopyFromScreen/Graphics screenshot → use TakeScreenshot + SaveImage activities
    """
    try:
        content = ctx.active_content
    except Exception:
        return
    
    # Find all InvokeCode Code attributes
    code_blocks = re.findall(r'Code="([^"]*)"', content)
    for code in code_blocks:
        # Decode XML entities for analysis
        decoded = code.replace("&#xA;", "\n").replace("&quot;", '"').replace("&lt;", "<").replace("&gt;", ">").replace("&#x9;", "\t")
        has_new_dt = bool(re.search(r'New\s+DataTable', decoded))
        has_col_add = bool(re.search(r'\.Columns\.Add\(', decoded))
        if has_new_dt and has_col_add:
            result.warn(
                "[lint 27] InvokeCode creates a DataTable AND adds columns — "
                "use Variable Default='new DataTable' + AddDataColumn activities instead. "
                "Reserve InvokeCode for procedural logic only (LINQ, GroupBy, loops). "
                "See xaml-data.md → 'Add Data Column' section."
            )
        
        # Lint 33: Database operations via InvokeCode
        has_sql = bool(re.search(r'SqlConnection|SqlCommand|\.Open\(\)|\.ExecuteNonQuery\(\)|\.ExecuteReader\(\)', decoded))
        if has_sql:
            result.error(
                "[lint 33] InvokeCode contains SqlConnection/SqlCommand — "
                "use DatabaseConnect + ExecuteQuery/ExecuteNonQuery activities from "
                "UiPath.Database.Activities instead. They handle connection pooling, "
                "parameterized queries, and proper disposal. "
                "See xaml-integrations.md → 'Database Activities' section."
            )
        
        # Lint 34: Screenshot via InvokeCode
        has_screenshot = bool(re.search(r'CopyFromScreen|Graphics\.FromImage|PrimaryScreenWidth|PrimaryScreenHeight', decoded))
        if has_screenshot:
            result.error(
                "[lint 34] InvokeCode captures screenshot via System.Drawing — "
                "use TakeScreenshot + SaveImage activities instead. They handle "
                "DPI scaling, multi-monitor setups, and memory disposal correctly. "
                "In REFramework, call Framework/TakeScreenshot.xaml. "
                "See xaml-integrations.md → 'Screenshot Activities' section."
            )
        
        # Lint 35: File.Delete via InvokeCode
        has_file_delete = bool(re.search(r'File\.Delete\(|IO\.File\.Delete', decoded))
        if has_file_delete:
            result.error(
                "[lint 35] InvokeCode uses File.Delete — "
                "use DeleteFileX activity instead: "
                "<ui:DeleteFileX Path=\"[strFilePath]\" />. "
                "See xaml-data.md → 'Delete File' section."
            )


@lint_rule(34)
def lint_credential_arguments(ctx: FileContext, result: ValidationResult):
    """Lint 34: Detect credentials passed as InvokeWorkflowFile arguments.
    
    Credentials (username, password, SecureString) should NEVER be passed between
    workflows as arguments. Login/Launch workflows must retrieve their own
    credentials internally via GetRobotCredential. Pass only the Orchestrator
    credential asset name (e.g. in_strCredentialAssetName) instead.
    """
    try:
        content = ctx.active_content
    except Exception:
        return

    # Check 1: SecureString x:Property arguments = credential passing violation
    # SecureString should only ever be a LOCAL VARIABLE inside login workflows,
    # never an argument (InArgument/OutArgument/InOutArgument)
    secstr_args = re.findall(
        r'<x:Property\s+[^>]*Name="([^"]*)"[^>]*Type="(?:In|Out|InOut)Argument\([^)]*SecureString[^)]*\)"',
        content
    )
    if not secstr_args:
        # Also check reversed attribute order
        secstr_args = re.findall(
            r'<x:Property\s+[^>]*Type="(?:In|Out|InOut)Argument\([^)]*SecureString[^)]*\)"[^>]*Name="([^"]*)"',
            content
        )
    if secstr_args:
        result.error(
            f"[lint 34] SecureString argument(s) declared: {', '.join(secstr_args)}. "
            f"SecureString passwords must NEVER be passed as workflow arguments. "
            f"Use GetRobotCredential INSIDE the login workflow with a local SecureString variable. "
            f"Pass only the credential asset name (in_strCredentialAssetName) as a String argument."
        )

    if "InvokeWorkflowFile" not in content:
        return

    # Check 2: Credential-like argument keys in InvokeWorkflowFile.Arguments
    CRED_ARG_PATTERNS = re.compile(
        r'x:Key="((?:in_|io_)?(?:str|secstr|sec|ss_)?'
        r'(?:Password|Username|UserName|Email|Login|Credential|SecurePassword'
        r'|SecureString|ApiKey|Token|Secret))"',
        re.IGNORECASE
    )

    found = []
    for match in CRED_ARG_PATTERNS.finditer(content):
        key = match.group(1)
        # Skip asset name arguments (these are fine — they're just the name string)
        if re.search(r'(?:Asset|Orch|Config).*Name', key, re.IGNORECASE):
            continue
        if re.search(r'CredentialAssetName|CredentialName|AssetName', key, re.IGNORECASE):
            continue
        found.append(key)

    if found:
        result.error(
            f"[lint 34] Credential-like argument(s) passed via InvokeWorkflowFile: "
            f"{', '.join(found)}. Credentials should be retrieved inside the "
            f"target workflow via GetRobotCredential, not passed as arguments. "
            f"Pass the Orchestrator asset name (in_strCredentialAssetName) instead."
        )


@lint_rule(36, golden_suppressed=True)
def lint_api_without_retry(ctx: FileContext, result: ValidationResult):
    """Lint 36: API/network activities should be wrapped in RetryScope.
    
    Any activity that makes a network call can fail due to transient issues.
    These must be inside a RetryScope for production resilience.
    
    REFramework's transaction-level retry (RetryCurrentTransaction) is NOT
    a substitute — it retries the entire transaction which is expensive.
    Individual API calls should still have granular RetryScope.
    
    Exception: Framework/ template files (not user-generated).
    """
    # Skip REFramework framework files — template code, not user-generated
    parent_dir = os.path.basename(os.path.dirname(ctx.filepath))
    if parent_dir in ("Framework", "Tests"):
        return
    
    try:
        content = ctx.active_content
    except Exception:
        return

    # Activities that interact with APIs/network and need RetryScope.
    # NOTE: NetHttpRequest is EXCLUDED — it has built-in RetryCount/RetryPolicyType/RetryStatusCodes.
    API_ACTIVITIES = [
        ("AddQueueItem", "Add Queue Item (Orchestrator API)"),
        ("BulkAddQueueItems", "Bulk Add Queue Items (Orchestrator API)"),
        ("GetQueueItem", "Get Queue Item (Orchestrator API)"),
        ("GetRobotAsset", "Get Robot Asset (Orchestrator API)"),
        ("GetRobotCredential", "Get Robot Credential (Orchestrator API)"),
        ("SetTransactionStatus", "Set Transaction Status (Orchestrator API)"),
        ("SetTransactionProgress", "Set Transaction Progress (Orchestrator API)"),
        ("QueryEntityRecords", "Data Service query (Orchestrator API)"),
    ]

    if "RetryScope" not in content:
        # No RetryScope at all — check if any API activities are present
        found = []
        for activity, label in API_ACTIVITIES:
            if f"<ui:{activity}" in content or f":{activity}" in content:
                found.append(label)
        if found:
            result.error(
                f"[lint 36] API activity without RetryScope: {', '.join(found)}. "
                f"Network/API calls can fail due to transient issues (timeouts, rate limits, "
                f"DNS). Wrap in RetryScope for production resilience. "
                f"See xaml-error-invoke.md → RetryScope."
            )


@lint_rule(37, golden_suppressed=True)
def lint_hardcoded_urls(ctx: FileContext, result: ValidationResult):
    """Lint 37: URLs must come from Config, never hardcoded in XAML.
    
    Detects hardcoded http/https URLs in NGoToUrl Url=, NApplicationCard TargetApp Url=,
    and NetHttpRequest EndPoint=. Also detects URL concatenation (e.g. in_strUrl + "/path")
    — full URLs should be stored in Config.xlsx, not assembled in XAML.
    """
    try:
        content = ctx.active_content
    except Exception:
        return

    # Check 1: Hardcoded http/https URLs
    URL_ATTRS = re.compile(
        r'(?:Url|EndPoint|Endpoint)\s*=\s*"(https?://[^"]+)"',
        re.IGNORECASE
    )

    found = []
    for match in URL_ATTRS.finditer(content):
        url = match.group(1)
        found.append(url)

    if found:
        display = [u[:60] + "..." if len(u) > 60 else u for u in found[:3]]
        extra = f" (and {len(found) - 3} more)" if len(found) > 3 else ""
        result.warn(
            f"[lint 37] Hardcoded URL(s) in XAML: {', '.join(display)}{extra}. "
            f"URLs must be stored in Config.xlsx and retrieved via "
            f'Config("KeyName").ToString. Pass to workflows as arguments from Config, '
            f"never as string literals. See SKILL.md → URL-first navigation."
        )

    # Check 2: URL concatenation in Url= attributes (e.g. Url="[in_strUrl + &quot;/login&quot;]")
    # Full URLs should come from Config, not be assembled by appending paths
    URL_CONCAT = re.compile(
        r'Url="[^"]*(?:\+|&amp;|\&quot;/)[^"]*"',
    )
    concat_matches = URL_CONCAT.findall(content)
    if concat_matches:
        result.error(
            f"[lint 37] URL concatenation detected in Url attribute. "
            f"Do NOT build URLs inside Url= attributes on NGoToUrl/TargetApp. "
            f"Store base URL + path segments in Config.xlsx, assemble with "
            f'String.Format("{{0}}/{{1}}", Config("BaseURL"), Config("Path")) '
            f"at the CALLER level (InvokeWorkflowFile arguments), and pass the "
            f"full URL as in_strUrl to the workflow."
        )


@lint_rule(38, golden_suppressed=True)
def lint_browser_incognito(ctx: FileContext, result: ValidationResult):
    """Lint 38: Browser NApplicationCard should have IsIncognito='True'.
    
    Incognito mode prevents cached sessions, cookies, and saved credentials
    from interfering with automation. This is the default for all browser XAML.
    """
    try:
        content = ctx.active_content
    except Exception:
        return

    if "NApplicationCard" not in content:
        return

    # Find browser NApplicationCards (have BrowserType or DebuggerApi or html selector)
    is_browser = (
        "BrowserType=" in content
        or 'InteractionMode="DebuggerApi"' in content
        or "app='msedge.exe'" in content
        or "app='chrome.exe'" in content
        or "app='firefox.exe'" in content
    )

    if not is_browser:
        return

    if 'IsIncognito="True"' not in content and "IsIncognito=" not in content:
        result.warn(
            "[lint 38] Browser NApplicationCard missing IsIncognito=\"True\". "
            "Always use incognito/private mode for browser automation to prevent "
            "cached sessions, cookies, and saved credentials from interfering. "
            "Add IsIncognito=\"True\" to the NApplicationCard element."
        )


@lint_rule(49, golden_suppressed=True)
def lint_browser_closemode_always(ctx: FileContext, result: ValidationResult):
    """Lint 49: CloseMode='Always' on browser NApplicationCard in non-close workflow.
    
    Browser NApplicationCards should use CloseMode='Never' in all workflows EXCEPT
    the dedicated App_Close.xaml. Using CloseMode='Always' kills the browser
    after the activity completes, breaking subsequent workflows that expect the
    browser to remain open (e.g. navigation → action → update sequences).
    """
    try:
        content = ctx.active_content
    except Exception:
        return

    if "NApplicationCard" not in content:
        return

    basename = os.path.basename(ctx.filepath).lower()
    # Skip close workflows — CloseMode="Always" is correct there
    if basename.startswith("browser_close") or basename.endswith("_close.xaml"):
        return

    for match in re.finditer(r'<uix:NApplicationCard\b([^>]*)/?>', content):
        attrs = match.group(1)
        if 'CloseMode="Always"' in attrs:
            result.warn(
                '[lint 49] Browser NApplicationCard has CloseMode="Always" in non-close workflow. '
                'This kills the browser after the activity completes, breaking subsequent workflows. '
                'Use CloseMode="Never" — only App_Close.xaml should use CloseMode="Always".'
            )
            break  # One warning per file is enough


@lint_rule(53)
def lint_interaction_mode_wrong_activity(ctx: FileContext, result: ValidationResult):
    """Lint 53: InteractionMode on activities that don't support it.

    Only NClick and NTypeInto have InteractionMode. These activities do NOT:
    NGetText, NCheckState, NSelectItem, NGoToUrl, NGetUrl, NExtractDataGeneric.
    Adding InteractionMode to them causes 'Could not find member' crash.
    """
    try:
        content = ctx.active_content
    except Exception:
        return

    if "InteractionMode" not in content:
        return

    # Activities that do NOT have InteractionMode
    no_interaction = [
        "NGetText", "NCheckState", "NSelectItem",
        "NGoToUrl", "NGetUrl", "NExtractDataGeneric",
    ]
    for act in no_interaction:
        # Match pattern: <uix:NGetText ... InteractionMode=
        # Use simple heuristic: find activity open tag, check if InteractionMode
        # appears before its closing > or next activity
        pattern = rf'<uix:{act}\b[^>]*InteractionMode='
        match = re.search(pattern, content)
        if match:
            result.error(
                f"[lint 53] '{act}' has InteractionMode — this property does NOT exist "
                f"on {act}. Only NClick and NTypeInto support InteractionMode. "
                f"Remove it to fix 'Could not find member' crash."
            )


@lint_rule(70)
def lint_invalid_empty_field_mode(ctx: FileContext, result: ValidationResult):
    """Lint 70: NTypeInto EmptyFieldMode has an invalid enum value.

    The EmptyFieldMode property accepts only the enum values 'None',
    'SingleLine', and 'MultiLine'. Hallucinated values like 'Clear',
    'Empty', 'Reset', 'ClearField', 'ClearAll', 'Single', 'Multi'
    cause Studio to reject the XAML with 'Cannot convert string to
    UiPath.UIAutomationNext.Enums.NEmptyFieldMode'. Auto-fix maps
    common hallucinations to the closest valid value.
    """
    try:
        content = ctx.active_content
    except Exception:
        return

    if "EmptyFieldMode=" not in content:
        return

    valid = {"None", "SingleLine", "MultiLine"}
    bad = []
    for m in re.finditer(r'EmptyFieldMode="([^"]*)"', content):
        value = m.group(1)
        if value not in valid:
            bad.append(value)

    if bad:
        result.error(
            f"[lint 70] {len(bad)} invalid EmptyFieldMode value(s): "
            f"{sorted(set(bad))} — only 'None', 'SingleLine', 'MultiLine' "
            f"are accepted. Studio rejects with 'Cannot convert string to "
            f"NEmptyFieldMode'. Auto-fix (--fix) maps common hallucinations "
            f"like 'Clear' or 'Empty' to 'SingleLine'."
        )


@lint_rule(54)
def lint_queue_name_property(ctx: FileContext, result: ValidationResult):
    """Lint 54: AddQueueItem/GetQueueItem uses QueueName instead of QueueType.

    The XAML property is QueueType, NOT QueueName. QueueName does not exist
    and causes 'Could not find member' crash. Common hallucination because
    the Config key is OrchestratorQueueName and the model field is queue_name.
    """
    try:
        content = ctx.active_content
    except Exception:
        return

    pattern = r'<ui:(AddQueueItem|GetQueueItem)\b[^>]*\bQueueName='
    match = re.search(pattern, content)
    if match:
        activity = match.group(1)
        result.error(
            f"[lint 54] {activity} uses QueueName= — this property does NOT exist. "
            f"The correct property is QueueType=. Studio crashes with "
            f"'Could not find member QueueName'. "
            f"Use gen_invoke_workflow() from scripts/generate_activities.py"
        )


@lint_rule(55)
def lint_invoke_empty_arguments(ctx: FileContext, result: ValidationResult):
    """Lint 55: InvokeWorkflowFile Out/InOut arguments with no variable binding.

    Out and InOut arguments MUST have a variable binding [varName] or the
    output is silently lost. Common when Claude hand-writes XAML and forgets
    to bind the argument to a variable. Also catches '[]' (empty brackets).
    """
    try:
        content = ctx.active_content
    except Exception:
        return

    if "InvokeWorkflowFile" not in content:
        return

    # Match OutArgument or InOutArgument that are self-closing (no value)
    # or contain only [] (empty brackets)
    patterns = [
        # Self-closing: <OutArgument ... x:Key="io_var" />
        (r'<(OutArgument|InOutArgument)\s[^>]*x:Key="([^"]*)"[^>]*/>', "empty (self-closing)"),
        # Empty brackets: <OutArgument ...>[]\</OutArgument>
        (r'<(OutArgument|InOutArgument)\s[^>]*x:Key="([^"]*)"[^>]*>\[\]</\1>', "empty brackets []"),
    ]
    for pattern, desc in patterns:
        for match in re.finditer(pattern, content):
            arg_type = match.group(1)
            key = match.group(2)
            result.warn(
                f"[lint 55] InvokeWorkflowFile {arg_type} '{key}' has no variable "
                f"binding ({desc}). Out/InOut args should bind to a variable "
                f"(e.g. [{key}]) or the output is silently lost."
            )


@lint_rule(56)
def lint_invoke_direction_mismatch(ctx: FileContext, result: ValidationResult):
    """Lint 56: InvokeWorkflowFile argument direction tag doesn't match key prefix.

    UiPath naming convention: io_ prefix = InOutArgument, out_ = OutArgument,
    in_ = InArgument. When Claude hand-writes XAML it often uses OutArgument
    for io_ keys (losing the inbound value) or InArgument for out_ keys
    (losing the outbound value). Both compile but cause silent data loss.
    """
    try:
        content = ctx.active_content
    except Exception:
        return

    if "InvokeWorkflowFile" not in content:
        return

    # Match any argument inside InvokeWorkflowFile.Arguments with direction + key
    pattern = r'<(InArgument|OutArgument|InOutArgument)\s[^>]*x:Key="([^"]*)"'
    for match in re.finditer(pattern, content):
        tag = match.group(1)
        key = match.group(2)

        # Determine expected direction from prefix
        if key.startswith("io_"):
            expected = "InOutArgument"
        elif key.startswith("out_"):
            expected = "OutArgument"
        elif key.startswith("in_"):
            expected = "InArgument"
        else:
            continue  # No prefix convention to check

        if tag != expected:
            result.error(
                f"[lint 56] InvokeWorkflowFile argument '{key}' uses {tag} "
                f"but prefix '{key.split('_')[0]}_' requires {expected}. "
                f"Wrong direction causes silent data loss."
            )


@lint_rule(50, golden_suppressed=True, needs_project_dir=True)
def lint_invoke_argument_mismatch(ctx: FileContext, result: ValidationResult,
                                   project_dir: str | None = None):
    """Lint 50: Cross-validate InvokeWorkflowFile argument keys against target x:Members.
    
    When x:Key in caller's .Arguments doesn't match any x:Property Name in the
    target workflow, Studio gives: 'Property matching [key] not found'.
    This catches argument name typos like in_strTargetUrl vs in_strUrl.
    Only runs when project_dir is known and target file exists.
    """
    if not project_dir:
        return

    try:
        content = ctx.active_content
    except Exception:
        return

    if "InvokeWorkflowFile" not in content:
        return


    # Extract all InvokeWorkflowFile blocks with their arguments
    # Pattern: find WorkflowFileName and then nearby x:Key values
    invoke_pattern = re.compile(
        r'<ui:InvokeWorkflowFile[^>]*WorkflowFileName="([^"]*)"[^>]*>.*?</ui:InvokeWorkflowFile>',
        re.DOTALL
    )
    args_pattern = re.compile(
        r'<ui:InvokeWorkflowFile\.Arguments>(.*?)</ui:InvokeWorkflowFile\.Arguments>',
        re.DOTALL
    )
    key_pattern = _RE_XKEY

    for invoke_match in invoke_pattern.finditer(content):
        workflow_file = invoke_match.group(1)
        invoke_block = invoke_match.group(0)

        # Skip dynamic paths like [variable]
        if workflow_file.startswith("["):
            continue

        # Resolve target path
        normalized = workflow_file.replace("\\", os.sep).replace("/", os.sep)
        target_path = os.path.join(project_dir, normalized)
        if not os.path.exists(target_path):
            continue  # Check 9 already reports missing files

        # Read target file's x:Members
        try:
            with open(target_path, "r", encoding="utf-8-sig") as f:
                target_content = f.read()
        except Exception:
            continue

        declared_args = set(re.findall(
            r'<x:Property[^>]*Name="([^"]*)"', target_content
        ))
        if not declared_args:
            continue

        # Extract x:Key values ONLY from .Arguments block (not ViewState)
        args_match = args_pattern.search(invoke_block)
        if not args_match:
            continue
        args_block = args_match.group(1)
        caller_keys = set(key_pattern.findall(args_block))
        if not caller_keys:
            continue

        # Find mismatches
        unknown_keys = caller_keys - declared_args
        if unknown_keys:
            target_name = os.path.basename(workflow_file)
            result.error(
                f"[lint 50] InvokeWorkflowFile → {target_name}: argument key(s) "
                f"{', '.join(sorted(unknown_keys))} not declared in target's x:Members. "
                f"Declared arguments: {', '.join(sorted(declared_args))}. "
                f"Check for typos — Studio error: 'Property matching [key] not found'."
            )


@lint_rule(60, golden_suppressed=True, needs_project_dir=True)
def lint_invoke_missing_arguments(ctx: FileContext, result: ValidationResult,
                                   project_dir: str | None = None):
    """Lint 60: InvokeWorkflowFile caller doesn't pass arguments declared in target.

    When a target workflow declares x:Property arguments that the caller's
    InvokeWorkflowFile.Arguments block doesn't include, Studio shows:
    'argument(s) missing or misconfigured: <name>'.

    For io_ and out_ arguments, the missing binding means the workflow runs
    but output is silently lost. For in_ arguments, the target gets
    Nothing/default which is usually a bug.

    This is the reverse of lint 50 (which catches extra/unknown keys).
    """
    if not project_dir:
        return

    try:
        content = ctx.active_content
    except Exception:
        return

    if "InvokeWorkflowFile" not in content:
        return

    invoke_pattern = re.compile(
        r'<ui:InvokeWorkflowFile[^>]*WorkflowFileName="([^"]*)"[^>]*>.*?</ui:InvokeWorkflowFile>',
        re.DOTALL
    )
    args_pattern = re.compile(
        r'<ui:InvokeWorkflowFile\.Arguments>(.*?)</ui:InvokeWorkflowFile\.Arguments>',
        re.DOTALL
    )
    key_pattern = _RE_XKEY

    for invoke_match in invoke_pattern.finditer(content):
        workflow_file = invoke_match.group(1)
        invoke_block = invoke_match.group(0)

        if workflow_file.startswith("["):
            continue

        normalized = workflow_file.replace("\\", os.sep).replace("/", os.sep)
        target_path = os.path.join(project_dir, normalized)
        if not os.path.exists(target_path):
            continue

        try:
            with open(target_path, "r", encoding="utf-8-sig") as f:
                target_content = f.read()
        except Exception:
            continue

        declared_args = set(re.findall(
            r'<x:Property[^>]*Name="([^"]*)"', target_content
        ))
        if not declared_args:
            continue

        # Get caller's argument keys
        args_match = args_pattern.search(invoke_block)
        caller_keys = set()
        if args_match:
            caller_keys = set(key_pattern.findall(args_match.group(1)))

        missing = declared_args - caller_keys
        if not missing:
            continue

        # Separate by severity: io_/out_ are data-loss bugs, in_ are likely bugs
        data_loss = sorted(k for k in missing if k.startswith(("io_", "out_")))
        input_missing = sorted(k for k in missing if k.startswith("in_"))

        target_name = os.path.basename(workflow_file)
        if data_loss:
            result.warn(
                f"[lint 60] InvokeWorkflowFile → {target_name}: missing "
                f"io/out argument(s) {', '.join(data_loss)}. "
                f"Target declares these but caller doesn't pass them — "
                f"output silently lost. Studio warning: "
                f"'argument(s) missing or misconfigured'."
            )
        if input_missing:
            result.warn(
                f"[lint 60] InvokeWorkflowFile → {target_name}: missing "
                f"input argument(s) {', '.join(input_missing)}. "
                f"Target declares these but caller doesn't pass them — "
                f"target receives Nothing/default. Studio warning: "
                f"'argument(s) missing or misconfigured'."
            )


@lint_rule(79)
def lint_duplicate_invoke_arguments(ctx: FileContext, result: ValidationResult):
    """Lint 79: InvokeWorkflowFile must not have both Arguments attribute and child element.

    XamlDuplicateMemberException: 'Arguments' property has already been set.
    This happens when the model writes Arguments="..." as an inline attribute
    AND also adds <ui:InvokeWorkflowFile.Arguments> as a child element.
    Use ONLY the child element syntax (generator output).
    """
    content = ctx.active_content

    # Find each InvokeWorkflowFile element
    for match in re.finditer(
        r'<ui:InvokeWorkflowFile\b([^>]*)>(.*?)</ui:InvokeWorkflowFile>',
        content, re.DOTALL
    ):
        attrs = match.group(1)
        body = match.group(2)
        # Check for inline Arguments attribute (NOT ArgumentsVariable)
        has_attr = bool(re.search(r'\bArguments="(?!Variable)', attrs))
        has_child = 'InvokeWorkflowFile.Arguments' in body
        child_count = body.count('InvokeWorkflowFile.Arguments')
        # Each pair of open+close tags = 2 occurrences per Arguments block
        dn_match = _RE_DISPLAY_NAME.search(attrs)
        dn = dn_match.group(1) if dn_match else "unknown"
        if has_attr and has_child:
            result.error(
                f"[lint 79] InvokeWorkflowFile '{dn}' has BOTH an inline "
                f"Arguments=\"...\" attribute AND a <ui:InvokeWorkflowFile.Arguments> "
                f"child element. This causes XamlDuplicateMemberException. "
                f"Remove the inline Arguments attribute — use only the child element "
                f"syntax (which is what gen_invoke_workflow produces)."
            )
        elif child_count > 2:
            # More than one open+close pair = duplicate Arguments blocks
            result.error(
                f"[lint 79] InvokeWorkflowFile '{dn}' has DUPLICATE "
                f"<ui:InvokeWorkflowFile.Arguments> child elements. "
                f"This causes XamlDuplicateMemberException. "
                f"Merge all arguments into a single Arguments block."
            )
        elif has_child:
            # Check for args outside Dictionary but inside Arguments block
            args_match = re.search(
                r'<ui:InvokeWorkflowFile\.Arguments>(.*?)</ui:InvokeWorkflowFile\.Arguments>',
                body, re.DOTALL
            )
            if args_match:
                args_body = args_match.group(1)
                has_dict = 'scg:Dictionary' in args_body
                # Find InArgument/OutArgument/InOutArgument that are direct
                # children of Arguments (not inside Dictionary)
                if has_dict and '</scg:Dictionary>' in args_body:
                    after_dict = args_body.split('</scg:Dictionary>', 1)[1]
                    stray = re.search(r'<(?:In|Out|InOut)Argument\b', after_dict)
                    if stray:
                        result.error(
                            f"[lint 79] InvokeWorkflowFile '{dn}' has argument(s) "
                            f"outside the <scg:Dictionary> wrapper but inside "
                            f"<ui:InvokeWorkflowFile.Arguments>. This causes "
                            f"XamlDuplicateMemberException. Move all arguments "
                            f"inside the Dictionary element."
                        )


@lint_rule(80)
def lint_nselectitem_missing_item(ctx: FileContext, result: ValidationResult):
    """Lint 80: NSelectItem requires Item attribute — {x:Null} causes runtime error.

    UiPath requires the 'Item to select' field to have a value. Use either
    a variable like Item="[strStatus]" or a literal like Item="[&quot;Completed&quot;]".
    """
    content = ctx.active_content
    if "NSelectItem" not in content:
        return

    nulls = re.findall(r'<uix:NSelectItem\b[^>]*Item="\{x:Null\}"', content)
    if nulls:
        result.error(
            f"[lint 80] NSelectItem has Item=\"{{x:Null}}\" ({len(nulls)}x) — "
            f"'Item to select' is REQUIRED. Use a variable: Item=\"[strStatus]\" "
            f"or a literal: Item=\"[&quot;Completed&quot;]\". "
            f"The Items list is for autocomplete hints only, not the selected value."
        )


@lint_rule(76, needs_project_dir=True)
def lint_argument_type_mismatch(ctx: FileContext, result: ValidationResult,
                                project_dir: str | None = None):
    """Lint 76: InvokeWorkflowFile argument type mismatch — BC30512 crash.

    Option Strict On (default) disallows implicit conversions between types.
    The model frequently uses x:Object as a lazy catch-all that crashes at
    compile time when the target expects a specific type.

    Two detection modes:
    1. Cross-file (project_dir available): Compare caller's x:TypeArguments
       with target workflow's x:Property Type. Catches ANY type discrepancy.
    2. Single-file fallback: Use naming conventions to infer expected types
       and flag x:Object mismatches.
    """
    try:
        content = ctx.active_content
    except Exception:
        return

    if "InvokeWorkflowFile" not in content:
        return

    violations = []

    # --- Cross-file type checking ---
    if project_dir:
        invoke_pattern = re.compile(
            r'<ui:InvokeWorkflowFile[^>]*WorkflowFileName="([^"]*)"[^>]*>.*?</ui:InvokeWorkflowFile>',
            re.DOTALL
        )
        args_pattern = re.compile(
            r'<ui:InvokeWorkflowFile\.Arguments>(.*?)</ui:InvokeWorkflowFile\.Arguments>',
            re.DOTALL
        )
        # Capture: direction tag, type, key
        binding_pattern = re.compile(
            r'<(?:In|Out|InOut)Argument\s+x:TypeArguments="([^"]*)"\s+x:Key="([^"]*)"'
        )
        # From x:Property: extract name and inner type from Type="Direction(type)"
        prop_pattern = re.compile(
            r'<x:Property\s+Name="([^"]*)"\s+Type="(?:In|Out|InOut)Argument\(([^)]*)\)"'
        )

        for invoke_match in invoke_pattern.finditer(content):
            workflow_file = invoke_match.group(1)
            invoke_block = invoke_match.group(0)

            if workflow_file.startswith("["):
                continue

            # Resolve target
            normalized = workflow_file.replace("\\", os.sep).replace("/", os.sep)
            target_path = os.path.join(project_dir, normalized)
            if not os.path.exists(target_path):
                continue

            try:
                with open(target_path, "r", encoding="utf-8-sig") as f:
                    target_content = f.read()
            except Exception:
                continue

            # Build target type map: {arg_name: declared_type}
            target_types = {}
            for prop_match in prop_pattern.finditer(target_content):
                target_types[prop_match.group(1)] = prop_match.group(2)

            if not target_types:
                continue

            # Extract caller bindings
            args_match = args_pattern.search(invoke_block)
            if not args_match:
                continue

            for bind_match in binding_pattern.finditer(args_match.group(1)):
                caller_type = bind_match.group(1)
                arg_key = bind_match.group(2)

                if arg_key in target_types:
                    expected_type = target_types[arg_key]
                    if caller_type != expected_type:
                        target_name = workflow_file.replace("\\", "/").split("/")[-1]
                        violations.append(
                            f"'{arg_key}' in {target_name}: caller uses "
                            f"'{caller_type}' but target declares '{expected_type}'"
                        )

    # --- Single-file fallback: naming convention + x:Object check ---
    # Even without cross-file, flag x:Object on any prefixed name
    # These conventions are enforced by naming rules
    PREFIX_TYPES = {
        "ui": "ui:UiElement",
        "uiEl": "ui:UiElement",
        "str": "x:String",
        "int": "x:Int32",
        "dt_": "sd2:DataTable",
        "bool": "x:Boolean",
        "dbl": "x:Double",
        "secstr": "System.Security.SecureString",
    }

    def _expected_type(name: str) -> str | None:
        """Infer expected type from variable name prefix."""
        # Strip direction prefix (in_, out_, io_)
        bare = re.sub(r'^(?:in|out|io)_', '', name)
        for prefix, expected in PREFIX_TYPES.items():
            if bare.startswith(prefix):
                return expected
        return None

    # Check x:Property declarations with x:Object
    for m in re.finditer(
        r'<x:Property\s+Name="([^"]*)"\s+Type="(?:In|Out|InOut)Argument\(x:Object\)"',
        content
    ):
        name = m.group(1)
        expected = _expected_type(name)
        if expected:
            violations.append(
                f"x:Property '{name}' declared as x:Object, expected '{expected}'"
            )

    # Check argument bindings with x:Object
    for m in re.finditer(
        r'<(?:In|Out|InOut)Argument\s+x:TypeArguments="x:Object"\s+x:Key="([^"]*)"',
        content
    ):
        key = m.group(1)
        expected = _expected_type(key)
        if expected:
            # Avoid duplicate if cross-file already caught it
            dupe = any(f"'{key}'" in v for v in violations)
            if not dupe:
                violations.append(
                    f"argument '{key}' uses x:Object, expected '{expected}'"
                )

    # Check Variable declarations with x:Object
    for m in re.finditer(
        r'<Variable\s+x:TypeArguments="x:Object"\s+Name="([^"]*)"',
        content
    ):
        name = m.group(1)
        expected = _expected_type(name)
        if expected:
            violations.append(
                f"Variable '{name}' uses x:Object, expected '{expected}'"
            )

    if violations:
        result.error(
            f"[lint 76] Argument type mismatch — Option Strict BC30512 crash: "
            f"{'; '.join(violations)}. "
            f"Option Strict On disallows implicit type conversions. "
            f"Use the exact type declared in the target workflow's x:Property."
        )


@lint_rule(109)
def lint_delay_activity(ctx: FileContext, result: ValidationResult):
    """Lint 109: Delay activity should not be used — use NCheckState/NCheckAppState."""
    try:
        content = ctx.active_content
    except Exception:
        return
    delay_hits = re.findall(r'<Delay\b', content)
    if delay_hits:
        result.warn(
            f"[lint 109] Workflow contains {len(delay_hits)} Delay activit{'y' if len(delay_hits) == 1 else 'ies'}. "
            f"Use NCheckState/NCheckAppState for synchronization instead of Delay."
        )

