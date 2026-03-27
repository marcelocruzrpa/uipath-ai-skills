# Overrides for UIAutomation activities where docs don't fully determine XAML.

OVERRIDES = {
    # NSelectItem must always be V1, not V5 — Studio crashes on any other value.
    # Lint 30 enforces this. The docs may show V5 but that's incorrect for this
    # specific activity.
    "nselectitem": {
        "force_version": "V1",
        "reason": "NSelectItem Version must be V1 (Studio crashes on V5). Lint 30.",
    },
}
