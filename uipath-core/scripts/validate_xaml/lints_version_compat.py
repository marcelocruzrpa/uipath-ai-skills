"""Version-compatibility lint rules.

These lints fire ONLY when a concrete target_version_band is set on
FileContext. They detect content mismatches between the generated XAML
and the target band — for example, Version="V5" attributes that don't
exist in UIAutomation 24.x.

Project-level unsupported-band warnings are handled separately by
ProjectVersion.unsupported_packages(), not by these file-level lints.
"""

import re

from ._registry import lint_rule
from ._context import FileContext, ValidationResult


# Activities whose Version attribute changed between bands
_VERSION_SENSITIVE_ACTIVITIES = {
    "NTypeInto", "NClick", "NCheck", "NHover", "NGetText",
    "NCheckState", "NKeyboardShortcuts", "NMouseScroll",
    "NApplicationCard", "TargetApp", "TargetAnchorable",
    "NGoToUrl", "NGetUrl", "NExtractDataGeneric",
}

# Attributes introduced in UIAutomation 25.10+
_V25_ONLY_ATTRIBUTES = {
    "HealingAgentBehavior",
    "ClipboardMode",
}

# Pattern to find Version="V5" or Version="V6" on UI activities
_RE_VERSION_V5_V6 = re.compile(
    r'<uix:(' + '|'.join(_VERSION_SENSITIVE_ACTIVITIES) + r')\s[^>]*Version="(V[5-9]|V\d{2,})"'
)

# Pattern to find HealingAgentBehavior or ClipboardMode
_RE_V25_ATTRS = re.compile(
    r'\b(' + '|'.join(_V25_ONLY_ATTRIBUTES) + r')='
)


@lint_rule(120)
def lint_version_v5_below_25(ctx: FileContext, result: ValidationResult):
    """Lint 120: Version="V5"+ attributes are invalid below band 25."""
    band = ctx.target_version_band
    if band is None:
        return
    try:
        if int(band) >= 25:
            return
    except ValueError:
        return

    for m in _RE_VERSION_V5_V6.finditer(ctx.active_content):
        activity = m.group(1)
        version = m.group(2)
        result.error(
            f"[lint 120] {activity} Version=\"{version}\" requires UIAutomation 25.10+, "
            f"but target band is {band}"
        )


@lint_rule(121)
def lint_healing_agent_below_25(ctx: FileContext, result: ValidationResult):
    """Lint 121: HealingAgentBehavior/ClipboardMode don't exist below band 25."""
    band = ctx.target_version_band
    if band is None:
        return
    try:
        if int(band) >= 25:
            return
    except ValueError:
        return

    for m in _RE_V25_ATTRS.finditer(ctx.active_content):
        attr = m.group(1)
        result.error(
            f"[lint 121] {attr} does not exist in UIAutomation band {band} "
            f"(introduced in 25.10+)"
        )
