"""Auto-fix logic for fixable lint rules."""
import os
import re


# --- Fix-specific constants (also used by lint 70) ---

VALID_EMPTY_FIELD_MODES = {"None", "SingleLine", "MultiLine"}

EMPTY_FIELD_MODE_FIXES = {
    "Clear": "SingleLine",
    "clear": "SingleLine",
    "Empty": "SingleLine",
    "empty": "SingleLine",
    "Reset": "SingleLine",
    "ClearField": "SingleLine",
    "ClearAll": "SingleLine",
    "Single": "SingleLine",
    "Multi": "MultiLine",
}


def auto_fix_file(filepath: str, dry_run: bool = False) -> list[str]:
    """Apply deterministic fixes for lints 7, 53, 54, 70, 71, 83, 87, 89, 90, 93, 99.

    Returns list of fix descriptions applied. Writes file in-place if any fixes
    made (unless dry_run=True, which reports fixes without writing).
    """
    with open(filepath, "rb") as f:
        raw = f.read()
    has_bom = raw.startswith(b'\xef\xbb\xbf')
    content = raw.decode("utf-8-sig")

    original = content
    fixes = []

    # Lint 83: Double-bracketed expressions [[...]] → [...]
    # Matches [[expression]] inside attribute values like Message="[[...]]"
    double_bracket_hits = list(re.finditer(
        r'\[\[(.+?)\]\]', content
    ))
    if double_bracket_hits:
        content = re.sub(r'\[\[(.+?)\]\]', r'[\1]', content)
        fixes.append(f"lint 83: removed {len(double_bracket_hits)} double-bracket(s)")

    # Lint 71: Double-escaped quotes &amp;quot; inside [bracket] expressions → &quot;
    # Only inside VB expression brackets [...], not in selector strings
    amp_quot_hits = list(re.finditer(r'\[([^\]]*?)&amp;quot;([^\]]*?)\]', content))
    if amp_quot_hits:
        def fix_amp_quot(m):
            inner = m.group(0)
            return inner.replace('&amp;quot;', '&quot;')
        content = re.sub(r'\[[^\]]*?&amp;quot;[^\]]*?\]', fix_amp_quot, content)
        fixes.append(f"lint 71: fixed {len(amp_quot_hits)} double-escaped quote(s)")

    # Lint 89: Selector double quotes → single quotes
    # Inside FullSelectorArgument="&lt;...tag=&quot;X&quot;...&gt;" → tag=&apos;X&apos; is wrong
    # Actually: selectors need tag='X' which in XML attribute becomes tag=&apos;X&apos;
    # But the real pattern is: raw double quotes inside selector strings
    # Pattern: find selector attributes, replace tag="val" with tag='val' inside them
    selector_attrs = ['FullSelectorArgument', 'FuzzySelectorArgument', 'Selector']
    for attr in selector_attrs:
        pattern = rf'({attr}=")(.*?)(")'
        for m in re.finditer(pattern, content):
            sel_value = m.group(2)
            # Inside the selector, find tag="value" patterns (already XML-escaped as &lt;...tag=&quot;value&quot;...&gt;)
            if '&quot;' in sel_value:
                # Check if these are selector attribute quotes (inside &lt;...&gt; tags)
                # Pattern: aaname=&quot;X&quot; or tag=&quot;X&quot;
                if re.search(r'\w+=&quot;', sel_value):
                    fixed_sel = re.sub(r'(\w+=)&quot;([^&]*)&quot;',
                                       r"\1'\2'", sel_value)
                    if fixed_sel != sel_value:
                        old_frag = f'{attr}="{sel_value}"'
                        new_frag = f'{attr}="{fixed_sel}"'
                        content = content.replace(old_frag, new_frag, 1)
                        fixes.append(f"lint 89: fixed double-quoted selector in {attr}")

    # Lint 90: Double-escaped selectors &amp;lt; → &lt;
    for attr in selector_attrs:
        pattern = rf'({attr}=")(.*?)(")'
        for m in re.finditer(pattern, content):
            sel_value = m.group(2)
            if '&amp;lt;' in sel_value or '&amp;gt;' in sel_value:
                fixed_sel = sel_value.replace('&amp;lt;', '&lt;').replace('&amp;gt;', '&gt;')
                old_frag = f'{attr}="{sel_value}"'
                new_frag = f'{attr}="{fixed_sel}"'
                content = content.replace(old_frag, new_frag, 1)
                fixes.append(f"lint 90: fixed double-escaped selector in {attr}")

    # Lint 93: Invalid array type x:String[] → s:String[]
    array_pattern = re.compile(r'x:(String|Int32|Boolean|Double|DateTime|Decimal)\[\]')
    array_hits = array_pattern.findall(content)
    if array_hits:
        content = array_pattern.sub(r's:\1[]', content)
        fixes.append(f"lint 93: fixed {len(array_hits)} x:Type[] → s:Type[] array type(s)")

    # Lint 87: Bare System.Data types in x:TypeArguments → prefixed form
    # Determine the correct prefix by reading xmlns declarations in the file header
    prefix_87 = None
    m_sd = re.search(r'xmlns:(\w+)="clr-namespace:System\.Data;', content[:3000])
    if m_sd:
        prefix_87 = m_sd.group(1)
    if prefix_87:
        bare_data_types = ['DataTable', 'DataRow', 'DataColumn']
        bare_87_count = 0
        for bdt in bare_data_types:
            # Match bare type inside x:TypeArguments (not already prefixed)
            pattern_87 = re.compile(
                rf'(x:TypeArguments="[^"]*?)(?<![:\w])\b{bdt}\b'
            )
            if pattern_87.search(content):
                content = pattern_87.sub(rf'\g<1>{prefix_87}:{bdt}', content)
                bare_87_count += 1
        if bare_87_count:
            fixes.append(
                f"lint 87: prefixed {bare_87_count} bare System.Data type(s) "
                f"with '{prefix_87}:'"
            )

    # Lint 7: Fix Throw expressions — C# syntax and FQ namespaces
    # MUST run BEFORE lint 99: lint 99 does global replace of FQ types to xmlns-prefixed
    # forms (e.g. System.Exception → s:Exception), which is correct for x:TypeArguments
    # but wrong inside Throw Exception="[New ...]" where the short form is needed.
    # Sub-fix A: C# syntax (throw new → New)
    throw_csharp = re.compile(
        r'(Exception="\[)(?:throw |Throw )[Nn]ew '
    )
    throw_csharp_hits = throw_csharp.findall(content)
    if throw_csharp_hits:
        content = throw_csharp.sub(r'\1New ', content)
        fixes.append(f"lint 7: fixed {len(throw_csharp_hits)} C# throw syntax → VB.NET New")
    # Sub-fix B: FQ namespaces scoped to Throw Exception="[...]" only
    THROW_FQ_FIX = {
        "UiPath.Core.Activities.BusinessRuleException": "BusinessRuleException",
        "UiPath.Core.Activities.ApplicationException": "ApplicationException",
        "System.Exception": "Exception",
    }
    for fqdn, short in THROW_FQ_FIX.items():
        # Match FQ type inside Throw Exception="[...FQ...]" attributes
        throw_fq_pattern = re.compile(
            rf'(Exception="\[[^\]]*){re.escape(fqdn)}([^\]]*\]")'
        )
        if throw_fq_pattern.search(content):
            content = throw_fq_pattern.sub(rf'\g<1>{short}\2', content)
            fixes.append(f"lint 7: replaced '{fqdn}' with '{short}' in Throw expression")

    # Lint 99: Fully-qualified CLR types → xmlns-prefixed form
    #
    # Applied as regex with a trailing non-identifier boundary so we do NOT
    # consume a longer name that starts with the same FQDN. In particular,
    # `System.Object` must not eat the `Model` in `System.ObjectModel`, which
    # appears verbatim inside `<AssemblyReference>System.ObjectModel</AssemblyReference>`
    # on every scaffolded XAML — Studio refuses to load the file when the
    # assembly name gets corrupted to `x:ObjectModel`.
    FQDN_FIX = {
        "System.Exception": "s:Exception",
        "System.String": "x:String",
        "System.Boolean": "x:Boolean",
        "System.Int32": "x:Int32",
        "System.Object": "x:Object",
        "System.Data.DataTable": "sd:DataTable",
        "System.Data.DataRow": "sd:DataRow",
        "System.Security.SecureString": "ss:SecureString",
        "UiPath.Core.Activities.BusinessRuleException": "ui:BusinessRuleException",
    }
    for fqdn, prefixed in FQDN_FIX.items():
        pattern = re.compile(rf'{re.escape(fqdn)}(?![A-Za-z0-9_.])')
        hits = pattern.findall(content)
        if hits:
            content = pattern.sub(prefixed, content)
            fixes.append(f"lint 99: replaced '{fqdn}' with '{prefixed}'")

    # Lint 54: QueueName → QueueType on AddQueueItem/GetQueueItem
    queue_fix = re.compile(r'(<ui:(?:AddQueueItem|GetQueueItem)\b[^>]*)\bQueueName=')
    queue_hits = queue_fix.findall(content)
    if queue_hits:
        content = queue_fix.sub(r'\1QueueType=', content)
        fixes.append(f"lint 54: renamed QueueName to QueueType ({len(queue_hits)} occurrence(s))")

    # Lint 53: Remove InteractionMode from activities that don't support it
    no_interaction = ["NGetText", "NCheckState", "NSelectItem",
                      "NGoToUrl", "NGetUrl", "NExtractDataGeneric"]
    for act in no_interaction:
        im_pattern = re.compile(rf'(<uix:{act}\b[^>]*?)\s+InteractionMode="[^"]*"')
        im_hits = im_pattern.findall(content)
        if im_hits:
            content = im_pattern.sub(r'\1', content)
            fixes.append(f"lint 53: removed InteractionMode from {act}")

    # Lint 70: Invalid EmptyFieldMode enum values → valid values
    efm_count = 0
    for m in re.finditer(r'EmptyFieldMode="([^"]*)"', content):
        value = m.group(1)
        if value not in VALID_EMPTY_FIELD_MODES:
            fix = EMPTY_FIELD_MODE_FIXES.get(value, "SingleLine")
            content = content.replace(f'EmptyFieldMode="{value}"',
                                      f'EmptyFieldMode="{fix}"', 1)
            efm_count += 1
    if efm_count:
        fixes.append(f"lint 70: fixed {efm_count} invalid EmptyFieldMode value(s)")

    if content != original and not dry_run:
        with open(filepath, "w", encoding="utf-8-sig" if has_bom else "utf-8") as f:
            f.write(content)

    return fixes
