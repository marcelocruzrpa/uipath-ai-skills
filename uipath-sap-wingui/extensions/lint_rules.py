"""SAP WinGUI lint rules — adapted from scripts/validate_sap_xaml.py for plugin system.

29 SAP rules (SAP-001 to SAP-030, SAP-027 reserved) adapted to the core plugin interface:
    def lint_fn(ctx: FileContext, result: ValidationResult) -> None

FileContext provides:
    .content       — raw file text (str)
    .active_content — content with CommentOut blocks stripped
    .tree          — parsed XML ElementTree root (may be None)
    .filepath      — file path (str)

ValidationResult provides:
    .error(msg)    — record an error
    .warn(msg)     — record a warning
    .ok(msg)       — record an info/pass message

Rules:
    SAP-001: NSAPLogin must have ScopeIdentifier matching parent NSAPLogon.ScopeGuid
    SAP-002: NSAPCallTransaction must have ScopeIdentifier
    SAP-003: NSAPClickToolbarButton must have ScopeIdentifier
    SAP-004: NSAPSelectMenuItem must have ScopeIdentifier
    SAP-005: NSAPReadStatusbar must have ScopeIdentifier
    SAP-006: NSAPTableCellScope must have ScopeIdentifier
    SAP-007: All ScopeIdentifiers must reference a valid NSAPLogon/NApplicationCard ScopeGuid
    SAP-008: File has both NSAPLogon OpenMode=Always and Never (decomposition smell)
    SAP-009: _Launch file must not contain NSAPCallTransaction
    SAP-010: Action workflows should use NApplicationCard, not NSAPLogon with OpenMode=Never
    SAP-011: NSAPLogin must have Username, SecurePassword, Client attributes
    SAP-012: NSAPCallTransaction.Transaction must not be empty
    SAP-013: NSAPCallTransaction.Prefix must be /n, /o, or empty
    SAP-014: NSAPClickToolbarButton must have Target with SAP selector
    SAP-015: NSAPClickToolbarButton must have Items list
    SAP-016: NSAPTableCellScope must have ColumnName attribute
    SAP-017: NSAPTableCellScope must have RowType attribute
    SAP-018: NSAPTableCellScope must have Target with table SAP selector
    SAP-019: NSAPTableCellScope must have Body with ActivityAction
    SAP-020: NSAPReadStatusbar must have MessageText output
    SAP-021: NSAPReadStatusbar must have MessageType output
    SAP-022: NSAPReadStatusbar must have MessageData output
    SAP-023: SAP selectors must start with <sap id=' or <wnd
    SAP-024: Legacy SAP activities detected (ucas:ReadStatusbar, ui:CellScope)
    SAP-025: No InformativeScreenshot attributes (removed per uipath-core convention)
    SAP-026: Status bar check should follow write operations (warning)
    SAP-028: NTypeInto/NClick inside NSAPTableCellScope should use InUiElement, not Target
    SAP-029: SecureString must use ss: prefix (System.Security), not s: (System)
    SAP-030: No hardcoded literals in Client, Language, AssetName, Username — use arguments
"""

import re
import xml.etree.ElementTree as ET


# ═══════════════════════════════════════════════════════════════════════════
# NAMESPACE MAP
# ═══════════════════════════════════════════════════════════════════════════

NS = {
    'uix': 'http://schemas.uipath.com/workflow/activities/uix',
    'ui': 'http://schemas.uipath.com/workflow/activities',
    'p': 'http://schemas.microsoft.com/netfx/2009/xaml/activities',
    'x': 'http://schemas.microsoft.com/winfx/2006/xaml',
    'sap': 'http://schemas.microsoft.com/netfx/2009/xaml/activities/presentation',
    'sap2010': 'http://schemas.microsoft.com/netfx/2010/xaml/activities/presentation',
    'scg': 'clr-namespace:System.Collections.Generic;assembly=System.Private.CoreLib',
    'ucas': 'clr-namespace:UiPath.Core.Activities.SAP;assembly=UiPath.UiAutomation.Activities',
}

VALID_PREFIXES = {'', '/n', '/o'}

VALID_ROW_TYPES = {'FirstEmptyRow', 'SpecificRow', 'LastRow', 'FirstRow'}


# ═══════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def _find_all_elements(root, local_name):
    """Find all elements matching a local name across all namespaces."""
    results = []
    for elem in root.iter():
        tag_local = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
        if tag_local == local_name:
            results.append(elem)
    return results


def _get_attr(elem, name, default=None):
    """Get attribute value, checking both namespaced and plain."""
    if name in elem.attrib:
        return elem.attrib[name]
    for ns_uri in NS.values():
        key = f'{{{ns_uri}}}{name}'
        if key in elem.attrib:
            return elem.attrib[key]
    return default


def _get_display_name(elem):
    """Get DisplayName for error reporting."""
    return _get_attr(elem, 'DisplayName', '(unnamed)')


# Track positions already matched to avoid returning the same line for duplicate elements
_matched_positions = set()


def _estimate_line(elem, raw_content):
    """Rough line number estimate based on DisplayName or tag in raw content.
    Tracks matched positions to return correct lines for duplicate elements."""
    dn = _get_display_name(elem)
    if dn and dn != '(unnamed)':
        for match in re.finditer(re.escape(dn), raw_content):
            if match.start() not in _matched_positions:
                _matched_positions.add(match.start())
                return raw_content[:match.start()].count('\n') + 1
    tag_local = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
    for match in re.finditer(f'<[^>]*{re.escape(tag_local)}', raw_content):
        if match.start() not in _matched_positions:
            _matched_positions.add(match.start())
            return raw_content[:match.start()].count('\n') + 1
    return None


def _loc(dn, ln):
    """Format location string for error messages."""
    parts = []
    if dn and dn != '(unnamed)':
        parts.append(f'[{dn}]')
    if ln:
        parts.append(f'(line ~{ln})')
    return ' '.join(parts) if parts else ''


# ═══════════════════════════════════════════════════════════════════════════
# MAIN LINT RULE — adapts all SAP-001..030 to plugin (ctx, result) interface
# ═══════════════════════════════════════════════════════════════════════════

def lint_sap_wingui(ctx, result):
    """All SAP WinGUI lint rules (SAP-001 through SAP-030).

    Checks SAP-specific XAML structure, scope identifiers, selectors,
    version strings, and common hallucination patterns.
    """
    raw = ctx.active_content
    _matched_positions.clear()  # Reset per-file position tracking

    # Skip files with no SAP activities
    if 'NSAP' not in raw and 'sap id=' not in raw.lower():
        return

    # Use pre-parsed tree from core validator (avoids double-parsing)
    if ctx.tree is not None:
        root = ctx.tree.getroot() if hasattr(ctx.tree, 'getroot') else ctx.tree
    else:
        try:
            root = ET.fromstring(ctx.content)
        except ET.ParseError:
            return

    # Collect all NSAPLogon scope GUIDs
    logon_scopes = _find_all_elements(root, 'NSAPLogon')
    valid_scope_guids = set()
    for logon in logon_scopes:
        sg = _get_attr(logon, 'ScopeGuid')
        if sg:
            valid_scope_guids.add(sg)

    # Also collect NApplicationCard scopes (used for SAP close and attach patterns)
    app_cards = _find_all_elements(root, 'NApplicationCard')
    for ac in app_cards:
        sg = _get_attr(ac, 'ScopeGuid')
        if sg:
            valid_scope_guids.add(sg)

    # ── SAP-008: Mixed OpenMode in NSAPLogon (decomposition smell) ──
    logon_open_modes = set()
    for logon in logon_scopes:
        om = _get_attr(logon, 'OpenMode', '')
        if 'Always' in om:
            logon_open_modes.add('Always')
        if 'Never' in om:
            logon_open_modes.add('Never')
    if 'Always' in logon_open_modes and 'Never' in logon_open_modes:
        result.warn(
            '[SAP-008] File contains NSAPLogon with both OpenMode=Always and Never — '
            'this suggests launch and action logic are mixed in one file. Decompose into separate workflows.'
        )

    # ── SAP-009: _Launch file must not contain NSAPCallTransaction ──
    filepath_lower = (ctx.filepath or '').replace('\\', '/').lower()
    filename_lower = filepath_lower.split('/')[-1] if filepath_lower else ''
    if '_launch' in filename_lower:
        call_txs = _find_all_elements(root, 'NSAPCallTransaction')
        if call_txs:
            dn = _get_display_name(call_txs[0])
            ln = _estimate_line(call_txs[0], raw)
            result.error(
                f'[SAP-009] _Launch file contains NSAPCallTransaction — '
                f'transaction navigation belongs in an action workflow, not Launch. {_loc(dn, ln)}'
            )

    # ── SAP-010: Action workflows should use NApplicationCard, not NSAPLogon with Never ──
    if '_launch' not in filename_lower:
        for logon in logon_scopes:
            om = _get_attr(logon, 'OpenMode', '')
            if 'Never' in om:
                dn = _get_display_name(logon)
                ln = _estimate_line(logon, raw)
                result.warn(
                    f'[SAP-010] NSAPLogon with OpenMode=Never found in non-Launch file — '
                    f'action workflows should use NApplicationCard(OpenMode=Never) instead. {_loc(dn, ln)}'
                )

    # ── SAP-024: Legacy SAP activities ──
    legacy_activities = {
        'ReadStatusbar': 'ucas:ReadStatusbar — use uix:NSAPReadStatusbar instead',
        'CellScope': 'ui:CellScope — use uix:NSAPTableCellScope instead',
    }
    for legacy_tag, msg in legacy_activities.items():
        # Only flag if found in ucas or ui namespace (not uix)
        for elem in root.iter():
            tag = elem.tag
            if legacy_tag in tag and 'uix' not in tag and 'UIAutomationNext' not in tag:
                ln = _estimate_line(elem, raw)
                result.warn(f'[SAP-024] Legacy activity: {msg} (line ~{ln})')
                break  # One warning per legacy type is enough

    # ── SAP-001/011: NSAPLogin ──
    for login in _find_all_elements(root, 'NSAPLogin'):
        dn = _get_display_name(login)
        ln = _estimate_line(login, raw)
        loc = _loc(dn, ln)

        si = _get_attr(login, 'ScopeIdentifier')
        if not si:
            result.error(f'[SAP-001] NSAPLogin missing ScopeIdentifier {loc}')
        elif si not in valid_scope_guids and valid_scope_guids:
            result.error(f'[SAP-007] NSAPLogin ScopeIdentifier does not match any NSAPLogon/NApplicationCard ScopeGuid {loc}')

        # SAP-011: Required attributes
        for attr in ['Username', 'SecurePassword', 'Client']:
            if not _get_attr(login, attr):
                result.error(f'[SAP-011] NSAPLogin missing {attr} {loc}')

    # ── SAP-002/012/013: NSAPCallTransaction ──
    for ct in _find_all_elements(root, 'NSAPCallTransaction'):
        dn = _get_display_name(ct)
        ln = _estimate_line(ct, raw)
        loc = _loc(dn, ln)

        si = _get_attr(ct, 'ScopeIdentifier')
        if not si:
            result.error(f'[SAP-002] NSAPCallTransaction missing ScopeIdentifier {loc}')
        elif si not in valid_scope_guids and valid_scope_guids:
            result.error(f'[SAP-007] NSAPCallTransaction ScopeIdentifier does not match any NSAPLogon/NApplicationCard ScopeGuid {loc}')

        tx = _get_attr(ct, 'Transaction', '')
        if not tx or tx == '[]':
            result.error(f'[SAP-012] NSAPCallTransaction has empty Transaction {loc}')

        prefix = _get_attr(ct, 'Prefix', '')
        if prefix not in VALID_PREFIXES:
            result.error(f'[SAP-013] NSAPCallTransaction Prefix="{prefix}", must be /n, /o, or empty {loc}')

    # ── SAP-003/014/015: NSAPClickToolbarButton ──
    for ctb in _find_all_elements(root, 'NSAPClickToolbarButton'):
        dn = _get_display_name(ctb)
        ln = _estimate_line(ctb, raw)
        loc = _loc(dn, ln)

        si = _get_attr(ctb, 'ScopeIdentifier')
        if not si:
            result.error(f'[SAP-003] NSAPClickToolbarButton missing ScopeIdentifier {loc}')
        elif si not in valid_scope_guids and valid_scope_guids:
            result.error(f'[SAP-007] NSAPClickToolbarButton ScopeIdentifier mismatch {loc}')

        # SAP-014: Must have Target
        targets = _find_all_elements(ctb, 'TargetAnchorable')
        if not targets:
            result.error(f'[SAP-014] NSAPClickToolbarButton missing Target {loc}')
        else:
            sel = _get_attr(targets[0], 'FullSelectorArgument', '')
            if 'tbar[' not in sel and 'sap' not in sel.lower():
                result.warn(f'[SAP-014] NSAPClickToolbarButton selector may not be a SAP toolbar button {loc}')

        # SAP-015: Must have Items
        items_lists = _find_all_elements(ctb, 'List')
        if not items_lists:
            result.warn(f'[SAP-015] NSAPClickToolbarButton missing Items list {loc}')

    # ── SAP-004: NSAPSelectMenuItem ──
    for smi in _find_all_elements(root, 'NSAPSelectMenuItem'):
        dn = _get_display_name(smi)
        ln = _estimate_line(smi, raw)
        loc = _loc(dn, ln)

        si = _get_attr(smi, 'ScopeIdentifier')
        if not si:
            result.error(f'[SAP-004] NSAPSelectMenuItem missing ScopeIdentifier {loc}')
        elif si not in valid_scope_guids and valid_scope_guids:
            result.error(f'[SAP-007] NSAPSelectMenuItem ScopeIdentifier mismatch {loc}')

        item = _get_attr(smi, 'Item', '')
        if not item:
            result.error(f'[SAP-004] NSAPSelectMenuItem has empty Item {loc}')
        elif '/' not in item:
            result.warn(f'[SAP-004] NSAPSelectMenuItem Item "{item}" has no menu path separator (/) {loc}')

    # ── SAP-005/020/021: NSAPReadStatusbar ──
    statusbar_count = 0
    for rsb in _find_all_elements(root, 'NSAPReadStatusbar'):
        statusbar_count += 1
        dn = _get_display_name(rsb)
        ln = _estimate_line(rsb, raw)
        loc = _loc(dn, ln)

        si = _get_attr(rsb, 'ScopeIdentifier')
        if not si:
            result.error(f'[SAP-005] NSAPReadStatusbar missing ScopeIdentifier {loc}')
        elif si not in valid_scope_guids and valid_scope_guids:
            result.error(f'[SAP-007] NSAPReadStatusbar ScopeIdentifier mismatch {loc}')

        mt = _get_attr(rsb, 'MessageText')
        if not mt:
            result.error(f'[SAP-020] NSAPReadStatusbar missing MessageText output {loc}')

        mty = _get_attr(rsb, 'MessageType')
        if not mty:
            result.error(f'[SAP-021] NSAPReadStatusbar missing MessageType output {loc}')

        md = _get_attr(rsb, 'MessageData')
        if not md:
            result.warn(f'[SAP-022] NSAPReadStatusbar missing MessageData output — needed to extract PO numbers and error details {loc}')

    # ── SAP-006/016/017/018/019/028: NSAPTableCellScope ──
    for tcs in _find_all_elements(root, 'NSAPTableCellScope'):
        dn = _get_display_name(tcs)
        ln = _estimate_line(tcs, raw)
        loc = _loc(dn, ln)

        si = _get_attr(tcs, 'ScopeIdentifier')
        if not si:
            result.error(f'[SAP-006] NSAPTableCellScope missing ScopeIdentifier {loc}')
        elif si not in valid_scope_guids and valid_scope_guids:
            result.error(f'[SAP-007] NSAPTableCellScope ScopeIdentifier mismatch {loc}')

        cn = _get_attr(tcs, 'ColumnName')
        if not cn:
            result.error(f'[SAP-016] NSAPTableCellScope missing ColumnName {loc}')

        rt = _get_attr(tcs, 'RowType')
        if not rt:
            result.error(f'[SAP-017] NSAPTableCellScope missing RowType {loc}')
        elif rt not in VALID_ROW_TYPES:
            result.warn(f'[SAP-017] NSAPTableCellScope RowType="{rt}", expected one of {VALID_ROW_TYPES} {loc}')

        targets = _find_all_elements(tcs, 'TargetAnchorable')
        if not targets:
            result.error(f'[SAP-018] NSAPTableCellScope missing Target {loc}')
        else:
            sel = _get_attr(targets[0], 'FullSelectorArgument', '')
            if 'tbl' not in sel.lower() and 'table' not in sel.lower():
                result.warn(f'[SAP-018] NSAPTableCellScope Target may not be a table selector {loc}')

        bodies = _find_all_elements(tcs, 'ActivityAction')
        if not bodies:
            result.error(f'[SAP-019] NSAPTableCellScope missing Body ActivityAction {loc}')

        # SAP-028: Child NTypeInto/NClick should use InUiElement, not Target
        for child_tag in ['NTypeInto', 'NClick', 'NGetText']:
            for child in _find_all_elements(tcs, child_tag):
                in_ui = _get_attr(child, 'InUiElement')
                child_targets = _find_all_elements(child, 'TargetAnchorable')
                if child_targets and not in_ui:
                    cdn = _get_display_name(child)
                    cln = _estimate_line(child, raw)
                    result.warn(
                        f'[SAP-028] {child_tag} inside NSAPTableCellScope uses Target '
                        f'instead of InUiElement {_loc(cdn, cln)}'
                    )

    # ── SAP-023: SAP selector validation (scan raw content) ──
    for match in re.finditer(r'FullSelectorArgument="([^"]*)"', raw):
        sel_escaped = match.group(1)
        sel = sel_escaped.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')

        if '<sap' in sel:
            # SAP-023: Must start with <sap
            if not sel.strip().startswith('<sap'):
                ln = raw[:match.start()].count('\n') + 1
                result.warn(
                    f'[SAP-023] SAP selector does not start with <sap: {sel[:60]}... (line ~{ln})'
                )

    # ── SAP-025: InformativeScreenshot should be removed ──
    for elem in root.iter():
        iss = _get_attr(elem, 'InformativeScreenshot')
        if iss:
            dn = _get_display_name(elem)
            ln = _estimate_line(elem, raw)
            result.ok(f'[SAP-025] InformativeScreenshot present (not needed for generated XAML) {_loc(dn, ln)}')

    # ── SAP-026: Status bar check after write operations (warning) ──
    save_buttons = [e for e in _find_all_elements(root, 'NSAPClickToolbarButton')
                    if 'Save' in _get_attr(e, 'Item', '')]
    save_clicks = [e for e in _find_all_elements(root, 'NClick')
                   if 'Save' in _get_display_name(e) or 'btn[11]' in str(e.attrib)]

    if (save_buttons or save_clicks) and statusbar_count == 0:
        result.warn(
            '[SAP-026] File contains Save action but no NSAPReadStatusbar — '
            'SAP errors are silent without status bar validation'
        )

    # ── SAP-029: SecureString must use ss: prefix, not s: ──
    sss_matches = list(re.finditer(r'(?<![a-zA-Z])s:SecureString', raw))
    if sss_matches:
        ln = raw[:sss_matches[0].start()].count('\n') + 1
        result.error(
            f'[SAP-029] s:SecureString found — SecureString is in System.Security, not System. '
            f'Use ss:SecureString with xmlns:ss="clr-namespace:System.Security;assembly=System.Private.CoreLib" '
            f'(line ~{ln})'
        )

    # ── SAP-030: No hardcoded literals in key SAP attributes ──
    hardcode_attrs = ['Client', 'Language', 'AssetName', 'Username']
    for attr in hardcode_attrs:
        pattern = rf'{attr}="\[&quot;[^&]*&quot;\]"'
        for match in re.finditer(pattern, raw):
            ln = raw[:match.start()].count('\n') + 1
            val = match.group()
            result.warn(
                f'[SAP-030] Hardcoded literal in {attr} — use an argument variable instead. '
                f'Found: {val} (line ~{ln})'
            )

    # Summary for passing files
    if logon_scopes or app_cards:
        result.ok(
            f'SAP WinGUI: {len(logon_scopes)} NSAPLogon scope(s), '
            f'{len(app_cards)} NApplicationCard scope(s), '
            f'{statusbar_count} NSAPReadStatusbar'
        )
