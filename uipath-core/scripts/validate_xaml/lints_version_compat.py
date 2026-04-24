"""Version-compatibility lint rules.

These lints fire ONLY when a concrete target_version_band is set on
FileContext. They detect content mismatches between the generated XAML
and the target band — for example, Version="V5" attributes that don't
exist in UIAutomation 24.x.

Project-level unsupported-band warnings are handled separately by
ProjectVersion.unsupported_packages(), not by these file-level lints.
"""

import json
import re
import sys
from pathlib import Path

from ._registry import lint_rule
from ._context import FileContext, ValidationResult


_PROFILES_DIR = Path(__file__).resolve().parents[2] / "references" / "version-profiles"

_MAX_JSON_SIZE = 10_000_000  # 10 MB cap for profile/cache JSON files

# Import-safety flag: if version_band can't be imported, lints 120/121/122
# degrade to silent no-ops so the rest of the validator keeps working.
try:
    from version_band import BAND_PROFILE_VERSIONS as _BAND_PROFILE_VERSIONS
    _VERSION_BAND_AVAILABLE = True
except ImportError:
    _BAND_PROFILE_VERSIONS = {}
    _VERSION_BAND_AVAILABLE = False
    print(
        "warning: version_band module not importable; "
        "version-compat lints 120/121/122 disabled.",
        file=sys.stderr,
    )


def _safe_read_json(path):
    if not path.is_file():
        return None
    if path.stat().st_size > _MAX_JSON_SIZE:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _get_plugin_profiles():
    """Return dict of (package, profile_version) -> profile from plugins, or empty on failure."""
    try:
        from plugin_loader import get_version_profiles
        return get_version_profiles()
    except ImportError:
        return {}


def _get_plugin_band_mappings():
    """Return dict of band -> dict(package -> profile_version) from plugins, or empty on failure."""
    try:
        from plugin_loader import get_band_profile_mappings
        return get_band_profile_mappings()
    except ImportError:
        return {}


def _merged_band_profile_versions():
    """Return BAND_PROFILE_VERSIONS merged with plugin-registered band mappings.

    Plugin entries are overlaid per-band so plugins can extend a band's package
    list without overwriting core entries for the same band.
    """
    merged = {b: dict(pkgs) for b, pkgs in _BAND_PROFILE_VERSIONS.items()}
    for band, pkg_map in _get_plugin_band_mappings().items():
        merged.setdefault(band, {}).update(pkg_map)
    return merged


def _load_profile_data(package, profile_version):
    """Return profile dict for (package, profile_version).

    Plugin-registered profiles win over on-disk profiles so plugins can shadow
    core profile data for their own packages if needed. Returns None if neither
    source has the requested profile.
    """
    plugin_profiles = _get_plugin_profiles()
    key = (package, profile_version)
    if key in plugin_profiles:
        return plugin_profiles[key]
    profile_path = _PROFILES_DIR / package / f"{profile_version}.json"
    return _safe_read_json(profile_path)

# Fallback set used when version_band profiles are unavailable. Only
# top-level activities belong here; child elements like TargetApp /
# TargetAnchorable are handled separately (future lint needed).
_FALLBACK_VERSION_SENSITIVE = {
    "NTypeInto", "NClick", "NCheck", "NGetText",
    "NCheckState", "NKeyboardShortcuts",
    "NApplicationCard",
    "NGoToUrl", "NExtractDataGeneric",
    "NHover", "NMouseScroll", "NGetUrl",  # NOTE: lint 122 is blind to these until profile version_attrs is populated; lint 120 still fires (catches V5+ below band 25)
}


def _detect_version_sensitive_activities() -> set[str]:
    """Detect activities whose Version attr differs across bands.

    Loads version profiles for each band defined in BAND_PROFILE_VERSIONS,
    compares version_attrs per activity, and returns the set of activity
    names whose Version value differs between any two bands.

    When ``version_band`` is unavailable, returns the fallback set so lint
    wiring does not crash at import time (the lints themselves still no-op
    via ``_VERSION_BAND_AVAILABLE``).
    """
    if not _VERSION_BAND_AVAILABLE:
        return set(_FALLBACK_VERSION_SENSITIVE)

    activity_versions: dict[str, dict[str, str]] = {}

    for band, packages in _merged_band_profile_versions().items():
        for package, profile_version in packages.items():
            if profile_version is None:
                continue
            data = _load_profile_data(package, profile_version)
            if data is None:
                continue

            for act_name, act_data in data.get("activities", {}).items():
                for tag, version in act_data.get("version_attrs", {}).items():
                    entry = activity_versions.setdefault(tag, {})
                    entry[band] = version

    sensitive = set()
    for act_name, band_versions in activity_versions.items():
        if len(set(band_versions.values())) > 1:
            sensitive.add(act_name)

    for act_name, band_versions in activity_versions.items():
        for version in band_versions.values():
            match = re.match(r"V(\d+)", version)
            if match and int(match.group(1)) >= 5:
                sensitive.add(act_name)
                break

    return sensitive if sensitive else set(_FALLBACK_VERSION_SENSITIVE)


_VERSION_SENSITIVE_ACTIVITIES = _detect_version_sensitive_activities()

_BAND_EXPECTED_CACHE: dict[str, dict[str, str]] = {}


def _version_key(ver: str) -> tuple[int, ...]:
    """Return a sortable tuple-of-ints for a dotted profile version string."""
    try:
        return tuple(int(x) for x in ver.split("."))
    except ValueError:
        return ()


def _build_band_expected_versions(band: str) -> dict[str, str]:
    """Return {activity_xml_tag: expected_Version} for a specific band.

    For each package in BAND_PROFILE_VERSIONS[band], loads every available
    profile version <= the canonical profile_version, oldest-first. Because
    the canonical version is loaded last, its version_attrs overwrite any
    earlier ones — activities present only in earlier profiles keep their
    earlier version_attrs (fallback), but conflicts resolve in favor of the
    band's canonical profile.
    """
    if band in _BAND_EXPECTED_CACHE:
        return _BAND_EXPECTED_CACHE[band]
    expected: dict[str, str] = {}
    plugin_profiles = _get_plugin_profiles()
    for package, profile_version in _merged_band_profile_versions().get(band, {}).items():
        if profile_version is None:
            continue
        canonical_key = _version_key(profile_version)
        if not canonical_key:
            continue
        pkg_dir = _PROFILES_DIR / package
        disk_versions = (
            [p.stem for p in pkg_dir.glob("*.json") if _version_key(p.stem)]
            if pkg_dir.is_dir() else []
        )
        plugin_versions = [ver for (pkg, ver) in plugin_profiles if pkg == package and _version_key(ver)]
        available = sorted(set(disk_versions + plugin_versions), key=_version_key)
        # Only include profiles up to and including the canonical version,
        # so newer-than-canonical profiles cannot overwrite canonical values.
        available = [v for v in available if _version_key(v) <= canonical_key]
        for ver in available:
            data = _load_profile_data(package, ver)
            if data is None:
                continue
            for act_name, act_data in data.get("activities", {}).items():
                for tag, version in act_data.get("version_attrs", {}).items():
                    expected[tag] = version
    _BAND_EXPECTED_CACHE[band] = expected
    return expected


# Attributes introduced in UIAutomation 25.10+
_V25_ONLY_ATTRIBUTES = {
    "HealingAgentBehavior",
    "ClipboardMode",
}

# Namespace URI for UiPath UIAutomation Next activities.
# ElementTree uses Clark notation: {uri}LocalName
_UIX_NAMESPACE_URI = "http://schemas.uipath.com/workflow/activities/uiautomationnext"

# Pre-compiled version patterns for lint 120 and 122
_RE_VERSION_V5_PLUS = re.compile(r"^V([5-9]|\d{2,})$")
_RE_VERSION_ANY = re.compile(r"^V\d+$")


@lint_rule(120)
def lint_version_v5_below_25(ctx: FileContext, result: ValidationResult):
    """Lint 120: Version="V5"+ attributes are invalid below band 25."""
    if not _VERSION_BAND_AVAILABLE:
        return
    band = ctx.target_version_band
    if band is None:
        return
    try:
        if int(band) >= 25:
            return
    except ValueError:
        result.warn(
            f"[lint 120] versionBand {band!r} is not parseable as an integer; "
            f"version-compat checks skipped"
        )
        return

    if ctx.tree is None:
        return
    for element in ctx.tree.iter():
        tag = element.tag
        if not tag.startswith(f"{{{_UIX_NAMESPACE_URI}}}"):
            continue
        localname = tag[len(_UIX_NAMESPACE_URI) + 2:]  # strip {uri}
        if localname not in _VERSION_SENSITIVE_ACTIVITIES:
            continue
        version = element.get("Version")
        if version and _RE_VERSION_V5_PLUS.match(version):
            result.error(
                f"[lint 120] {localname} Version=\"{version}\" requires UIAutomation 25.10+, "
                f"but target band is {band}"
            )


@lint_rule(121)
def lint_healing_agent_below_25(ctx: FileContext, result: ValidationResult):
    """Lint 121: HealingAgentBehavior/ClipboardMode don't exist below band 25."""
    if not _VERSION_BAND_AVAILABLE:
        return
    band = ctx.target_version_band
    if band is None:
        return
    try:
        if int(band) >= 25:
            return
    except ValueError:
        result.warn(
            f"[lint 121] versionBand {band!r} is not parseable as an integer; "
            f"version-compat checks skipped"
        )
        return

    if ctx.tree is None:
        return
    for element in ctx.tree.iter():
        tag = element.tag
        if not tag.startswith(f"{{{_UIX_NAMESPACE_URI}}}"):
            continue
        for attr in _V25_ONLY_ATTRIBUTES:
            if element.get(attr) is not None:
                result.error(
                    f"[lint 121] {attr} does not exist in UIAutomation band {band} "
                    f"(introduced in 25.10+)"
                )


@lint_rule(122)
def lint_version_band_mismatch(ctx: FileContext, result: ValidationResult):
    """Lint 122: Activity Version attributes must match the target band's profile."""
    if not _VERSION_BAND_AVAILABLE:
        return
    band = ctx.target_version_band
    if band is None:
        return
    expected = _build_band_expected_versions(band)
    if not expected:
        return

    if ctx.tree is None:
        return
    for element in ctx.tree.iter():
        tag = element.tag
        if not tag.startswith(f"{{{_UIX_NAMESPACE_URI}}}"):
            continue
        localname = tag[len(_UIX_NAMESPACE_URI) + 2:]  # strip {uri}
        actual = element.get("Version")
        if actual is None or not _RE_VERSION_ANY.match(actual):
            continue
        exp = expected.get(localname)
        if exp is None:
            continue
        if actual != exp:
            result.error(
                f'[lint 122] {localname} Version="{actual}" does not match '
                f'band {band} profile (expected "{exp}")'
            )
