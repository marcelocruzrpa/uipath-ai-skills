"""Type and namespace lint rules."""

import re

from ._registry import lint_rule
from ._context import FileContext, ValidationResult


@lint_rule(24)
def lint_deprecated_assemblies(ctx: FileContext, result: ValidationResult):
    """Lint 24: Detect deprecated/renamed assembly references."""
    try:
        content = ctx.content
    except Exception:
        return

    DEPRECATED = {
    }
    for old, fix in DEPRECATED.items():
        count = content.count(old)
        if count:
            result.error(
                f"{count} reference(s) to deprecated '{old}' — "
                f"renamed to {fix}. Replace all occurrences."
            )


@lint_rule(40)
def lint_wrong_enum_namespace(ctx: FileContext, result: ValidationResult):
    """Lint 40: Detect wrong UIAutomation enum namespace (must be UIAutomationNext).

    The NuGet package is UiPath.UIAutomation.Activities but the CLR enum types
    kept the old namespace UiPath.UIAutomationNext.Enums. Using UIAutomation.Enums
    (without 'Next') causes compile errors because that namespace doesn't exist.
    """
    try:
        content = ctx.active_content
    except Exception:
        return

    # Check for wrong namespace in imports
    if "UiPath.UIAutomation.Enums" in content and "UiPath.UIAutomationNext.Enums" not in content:
        result.error(
            "[lint 40] Wrong enum namespace: 'UiPath.UIAutomation.Enums' does not exist. "
            "Use 'UiPath.UIAutomationNext.Enums' — the NuGet package was renamed but "
            "CLR enum types kept the old namespace. Fix both the namespace import and "
            "any fully-qualified enum expressions."
        )

    # Check for wrong namespace in expressions (even if import is correct)
    import re
    wrong_expr = re.findall(
        r'\[UiPath\.UIAutomation\.Enums\.\w+\.\w+\]', content
    )
    if wrong_expr:
        result.error(
            f"[lint 40] Wrong enum namespace in expression(s): {', '.join(wrong_expr[:3])}. "
            "Replace 'UiPath.UIAutomation.Enums' with 'UiPath.UIAutomationNext.Enums' "
            "in all enum expressions."
        )


@lint_rule(18)
def lint_namespace_conflicts(ctx: FileContext, result: ValidationResult):
    """Lint 18: Detect System.Drawing namespace/assembly conflicts.

    Common AI-generated bug: OCREngine delegate needs sd:Image from System.Drawing.Common
    but the prefix is bound to System.Drawing.Primitives (wrong assembly) or System.Data
    (wrong namespace entirely). Studio error:
    'Could not find type System.Drawing.Image in assembly System.Drawing.Primitives'
    """
    try:
        content = ctx.content
    except Exception:
        return

    if "OCREngine" not in content and "ActivityFunc" not in content:
        return

    # Find all xmlns declarations with sd-like prefixes
    all_ns = re.findall(r'xmlns:(\w+)\s*=\s*"([^"]*)"', content)
    prefix_map = {p: ns for p, ns in all_ns}

    # Check if OCREngine references use a prefix for Image type
    ocr_img_match = re.search(r'TypeArguments="(\w+):Image', content)
    if not ocr_img_match:
        return

    img_prefix = ocr_img_match.group(1)
    if img_prefix not in prefix_map:
        return  # prefix not declared, other checks will catch this

    bound_ns = prefix_map[img_prefix]

    # Case 1: prefix bound to System.Data — completely wrong namespace
    if "System.Data" in bound_ns:
        result.error(
            f"OCREngine delegate uses '{img_prefix}:Image' but xmlns:{img_prefix} "
            f"is bound to '{bound_ns}' (System.Data, not System.Drawing). "
            f"Use a separate prefix for System.Drawing.Common"
        )
    # Case 2: prefix bound to System.Drawing.Primitives — wrong assembly
    # Image class lives in System.Drawing.Common, not Primitives
    elif "System.Drawing.Primitives" in bound_ns:
        result.error(
            f"OCREngine delegate uses '{img_prefix}:Image' but xmlns:{img_prefix} "
            f"targets assembly 'System.Drawing.Primitives'. "
            f"Image requires 'System.Drawing.Common' — change to: "
            f'xmlns:{img_prefix}="clr-namespace:System.Drawing;assembly=System.Drawing.Common"'
        )
    # Case 3: prefix bound to System.Drawing.Common — correct
    elif "System.Drawing.Common" in bound_ns:
        pass  # correct
    # Case 4: unexpected binding
    elif "System.Drawing" not in bound_ns:
        result.warn(
            f"OCREngine delegate uses '{img_prefix}:Image' but xmlns:{img_prefix} "
            f"is '{bound_ns}' — verify this resolves to System.Drawing.Common"
        )


@lint_rule(87)
def lint_wrong_type_xmlns_prefix(ctx: FileContext, result: ValidationResult):
    """Lint 87: Type reference uses wrong or missing xmlns prefix — type cannot be resolved.

    The xmlns prefix for DataTable depends on the file's namespace declarations:
    - If sd = System.Data → use sd:DataTable
    - If sd = System.Drawing and sd2 = System.Data → use sd2:DataTable

    Claude often hardcodes 'sd:DataTable' without checking what 'sd' maps to.
    This causes: "The type 'OutArgument(sd:DataTable)' could not be resolved."

    Also catches BARE (unprefixed) System.Data types — e.g., x:TypeArguments="DataRow"
    instead of x:TypeArguments="sd:DataRow". Studio cannot resolve the type without
    the namespace prefix.

    Also checks SecureString (ss vs other prefixes).
    """
    import re as _re
    try:
        content = ctx.content
    except Exception:
        return

    # Build xmlns prefix map from first line
    prefix_map = {}  # prefix -> namespace
    for m in _re.finditer(r'xmlns:(\w+)="clr-namespace:([^;]+);', content[:3000]):
        prefix_map[m.group(1)] = m.group(2)

    if not prefix_map:
        return

    # Find which prefix maps to System.Data
    data_prefix = None
    for p, ns in prefix_map.items():
        if ns == 'System.Data':
            data_prefix = p
            break

    if not data_prefix:
        return  # no System.Data import, skip

    # --- Check 1: wrong prefix on DataTable (existing) ---
    errors = []
    for m in _re.finditer(r'(\w+):DataTable', content):
        used_prefix = m.group(1)
        if used_prefix == 'x':
            continue  # x:TypeArguments context, skip
        if used_prefix != data_prefix:
            # Check if the used prefix maps to something else (like System.Drawing)
            actual_ns = prefix_map.get(used_prefix, 'unknown')
            if actual_ns != 'System.Data':
                # Find context (what line, what attribute)
                pos = m.start()
                line_num = content[:pos].count('\n') + 1
                errors.append(
                    f"line {line_num}: '{used_prefix}:DataTable' but "
                    f"'{used_prefix}' maps to {actual_ns}, "
                    f"not System.Data — use '{data_prefix}:DataTable'"
                )

    if errors:
        result.error(
            f"[lint 87] Wrong xmlns prefix for DataTable type — causes "
            f"'type could not be resolved' crash. "
            f"In this file, DataTable requires prefix '{data_prefix}' "
            f"(mapped to System.Data). "
            f"Found: {'; '.join(errors[:3])}"
        )

    # --- Check 2: bare (unprefixed) System.Data types in x:TypeArguments ---
    # Catches: x:TypeArguments="DataRow", x:TypeArguments="DataTable",
    #          x:TypeArguments="DataColumn" — all need the sd: (or equivalent) prefix.
    _BARE_DATA_TYPES = ('DataTable', 'DataRow', 'DataColumn')
    bare_errors = []
    for m in _re.finditer(r'x:TypeArguments="([^"]*)"', content):
        type_val = m.group(1)
        for bare_type in _BARE_DATA_TYPES:
            # Match bare type name NOT preceded by a prefix (word:)
            # Must match: "DataRow", "DataTable" but NOT "sd:DataRow"
            if _re.search(rf'(?<!\w:)\b{bare_type}\b', type_val):
                pos = m.start()
                line_num = content[:pos].count('\n') + 1
                bare_errors.append(
                    f"line {line_num}: bare '{bare_type}' in "
                    f"x:TypeArguments — use '{data_prefix}:{bare_type}'"
                )

    if bare_errors:
        result.error(
            f"[lint 87] Unprefixed System.Data type in x:TypeArguments — causes "
            f"'type could not be resolved' in Studio. "
            f"Types like DataRow, DataTable, DataColumn require the namespace "
            f"prefix '{data_prefix}:' (mapped to System.Data in this file). "
            f"Found: {'; '.join(bare_errors[:5])}"
        )


_RE_X_ARRAY_TYPE = re.compile(
    r'x:(String|Int32|Boolean|Double|DateTime|Decimal)\[\]'
)

# FQ CLR types that should appear xmlns-prefixed (s:, x:, sd:, ss:, ui:).
_FQDN_TYPES = (
    "System.Exception",
    "System.String",
    "System.Boolean",
    "System.Int32",
    "System.Object",
    "System.Data.DataTable",
    "System.Data.DataRow",
    "System.Security.SecureString",
    "UiPath.Core.Activities.BusinessRuleException",
)


@lint_rule(93)
def lint_invalid_x_array_type(ctx: FileContext, result: ValidationResult):
    """Lint 93: x:String[] / x:Int32[] (and other ``x:Primitive[]``)
    array types are invalid in XAML.

    The ``x`` xmlns is the XAML namespace, not the System CLR namespace.
    Primitive arrays must use the ``s:`` prefix (mapped to System) —
    e.g. ``s:String[]``, ``s:Int32[]``. Using ``x:String[]`` causes
    Studio to fail with "The type x:String[] could not be resolved".
    Auto-fix (--fix) rewrites the prefix.
    """
    try:
        content = ctx.active_content
    except Exception:
        return

    hits = _RE_X_ARRAY_TYPE.findall(content)
    if hits:
        types = sorted(set(hits))
        result.error(
            f"[lint 93] {len(hits)} invalid x:Type[] array reference(s): "
            f"{', '.join('x:' + t + '[]' for t in types)} — the 'x' "
            f"xmlns is the XAML namespace, not System. Use the 's:' "
            f"prefix (s:String[], s:Int32[], …). Auto-fix (--fix) "
            f"rewrites them."
        )


@lint_rule(99)
def lint_fqdn_type_arguments(ctx: FileContext, result: ValidationResult):
    """Lint 99: Fully-qualified CLR type names appear inside XAML
    type-resolution contexts where a xmlns-prefixed shortname is required.

    XAML cannot resolve dotted CLR FQ names like
    ``x:TypeArguments=\"System.Exception\"`` — Studio expects the
    xmlns-prefixed shortname (``s:Exception``, ``x:String``,
    ``sd:DataTable``, ``ss:SecureString``, ``ui:BusinessRuleException``).
    Hand-written or model-generated XAML often pastes the FQ name and
    Studio rejects it with 'type ... could not be resolved'.
    Auto-fix (--fix) rewrites the FQ name to the prefixed form.

    Detection is intentionally scoped to:
      - ``x:TypeArguments=\"...\"`` attribute values, and
      - ``<Catch x:TypeArguments=\"FQ\">`` / ``<ActivityAction
        x:TypeArguments=\"FQ\">`` / ``<DelegateInArgument
        x:TypeArguments=\"FQ\">`` shapes.
    Dotted FQ names inside VB expression brackets (e.g.
    ``[New System.Net.NetworkCredential(...)]`` or
    ``Dictionary(Of System.String, System.String)``) are valid VB and
    are not flagged.
    """
    try:
        content = ctx.active_content
    except Exception:
        return

    # Collect the contents of every x:TypeArguments="..." attribute.
    type_arg_blocks = [m.group(1) for m in re.finditer(
        r'x:TypeArguments="([^"]*)"', content
    )]
    if not type_arg_blocks:
        return

    found = []
    for fqdn in _FQDN_TYPES:
        # Word-boundary match so 'System.Exception' doesn't shadow
        # 'System.ExceptionDispatchInfo'. Trailing lookahead avoids
        # matching 'System.Data.DataTableExtensions' etc.
        pattern = re.compile(rf'\b{re.escape(fqdn)}\b(?!\w)')
        n = sum(len(pattern.findall(blk)) for blk in type_arg_blocks)
        if n:
            found.append((fqdn, n))

    if found:
        breakdown = ", ".join(f"{fqdn} x{n}" for fqdn, n in found)
        result.error(
            f"[lint 99] {sum(n for _, n in found)} fully-qualified CLR "
            f"type reference(s) inside x:TypeArguments ({breakdown}) — "
            f"XAML cannot resolve dotted FQ names in type-arg contexts. "
            f"Use the xmlns-prefixed shortname (System.Exception → "
            f"s:Exception, System.String → x:String, System.Data.DataTable "
            f"→ sd:DataTable, etc.). Auto-fix (--fix) rewrites them."
        )


@lint_rule(95)
def lint_unprefixed_argument_types(ctx: FileContext, result: ValidationResult):
    """Lint 95: Detect unprefixed generic types in x:Property declarations.

    Studio crash: 'The type X of property Y could not be resolved.'
    Common LLM mistake: Dictionary(String,Object) instead of scg:Dictionary(x:String, x:Object).
    """
    content = ctx.active_content
    violations = []

    for m in re.finditer(
        r'<x:Property\s+[^>]*Type="(?:In|Out|InOut)Argument\(([^"]*)\)"',
        content
    ):
        inner_type = m.group(1)
        # Check for Dictionary without scg: prefix
        if re.match(r'Dictionary\s*\(', inner_type) and not inner_type.startswith('scg:'):
            violations.append(
                f"'{inner_type}' → use 'scg:Dictionary(x:String, x:Object)' "
                f"(or type='Dictionary' in JSON spec)"
            )
        # Check for bare String, Object, Int32 etc. inside generics (missing x: prefix)
        elif '(' in inner_type:
            # Has generic params — check if any are unprefixed
            bare = re.findall(r'(?<![:\w])(?:String|Object|Int32|Boolean|Double)\b', inner_type)
            if bare:
                violations.append(
                    f"'{inner_type}' has unprefixed type(s): {', '.join(bare)}. "
                    f"Use x:String, x:Object, x:Int32, etc."
                )

    if violations:
        result.error(
            f"[lint 95] Unprefixed generic type in argument declaration — "
            f"Studio crash 'type could not be resolved': "
            f"{'; '.join(violations)}. "
            f"In JSON spec, use short names like 'Dictionary', 'String', 'DataTable' — "
            f"generate_workflow.py adds the correct namespace prefixes."
        )


