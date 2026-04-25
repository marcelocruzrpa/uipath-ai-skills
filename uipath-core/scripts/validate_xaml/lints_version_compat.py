"""Version-compatibility lint rules.

These lints fire ONLY when a concrete target_version_band is set on
FileContext. They detect content mismatches between the generated XAML
and the target band — for example, Version="V5" attributes that don't
exist in UIAutomation 24.x.

Project-level unsupported-band warnings are handled separately by
ProjectVersion.unsupported_packages(), not by these file-level lints.
"""

import json
import logging
import re
import sys
from pathlib import Path

from ._registry import lint_rule
from ._context import FileContext, ValidationResult


_LOG = logging.getLogger(__name__)

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

    Hardened against malformed profile data: each `dict.get(...)` is paired
    with an isinstance check so a profile carrying ``"version_attrs": null``
    or ``"activities": null`` (valid JSON, common in the corpus for sparsely
    annotated activities) is skipped rather than crashing module import.
    """
    if not _VERSION_BAND_AVAILABLE:
        return set(_FALLBACK_VERSION_SENSITIVE)

    activity_versions: dict[str, dict[str, str]] = {}

    for band, packages in _merged_band_profile_versions().items():
        if not isinstance(packages, dict):
            continue
        for package, profile_version in packages.items():
            if profile_version is None:
                continue
            data = _load_profile_data(package, profile_version)
            if not isinstance(data, dict):
                continue

            activities = data.get("activities") or {}
            if not isinstance(activities, dict):
                continue
            for act_name, act_data in activities.items():
                if not isinstance(act_data, dict):
                    continue
                vattrs = act_data.get("version_attrs") or {}
                if not isinstance(vattrs, dict):
                    continue
                for tag, version in vattrs.items():
                    if not isinstance(version, str):
                        continue
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


def _safe_detect_version_sensitive_activities() -> set[str]:
    """Wrap :func:`_detect_version_sensitive_activities` in a hard fail-safe.

    Module import-time work walks the on-disk profile corpus and merges plugin
    registrations. Any uncaught exception there would brick the entire
    ``validate_xaml`` package import (every consumer crashes, not just lints
    120/121/122). We swallow unexpected errors here and fall back to the
    static set so import always succeeds.
    """
    try:
        return _detect_version_sensitive_activities()
    except Exception as exc:  # pragma: no cover — defensive only
        _LOG.warning(
            "lints_version_compat: _detect_version_sensitive_activities failed "
            "(%s: %s); using fallback set.",
            type(exc).__name__, exc,
        )
        return set(_FALLBACK_VERSION_SENSITIVE)


_VERSION_SENSITIVE_ACTIVITIES = _safe_detect_version_sensitive_activities()

_BAND_EXPECTED_CACHE: dict[str, dict[str, str]] = {}


def _invalidate_cache() -> None:
    """Reset module-level caches so the next lint call rebuilds them.

    Intended for callers (e.g. ``plugin_loader.load_plugins`` post-reload) that
    register new version profiles or band mappings after this module was first
    imported. Without invalidation, ``_VERSION_SENSITIVE_ACTIVITIES`` and
    ``_BAND_EXPECTED_CACHE`` would carry stale entries from the initial scan.

    The plugin loader does NOT currently call this — wiring is up to F3 — but
    exposing the helper unblocks that work and is safe to call at any time.
    """
    global _VERSION_SENSITIVE_ACTIVITIES
    _VERSION_SENSITIVE_ACTIVITIES = _safe_detect_version_sensitive_activities()
    _BAND_EXPECTED_CACHE.clear()


def _version_key(ver: str) -> tuple[int, ...]:
    """Return a sortable tuple-of-ints for a dotted profile version string.

    Unparseable strings (typos like ``"25.10."``, prerelease tags like
    ``"25.10-rc1"``) are returned as ``()`` so callers can filter them out.
    A debug log line records the drop so developers can spot a corrupt entry
    when tracing why a lint went silent. (R2a M2.)
    """
    try:
        return tuple(int(x) for x in ver.split("."))
    except (ValueError, AttributeError):
        _LOG.debug(
            "lints_version_compat: dropping unparseable profile version %r", ver,
        )
        return ()


def _build_band_expected_versions(band: str) -> dict[str, str]:
    """Return {activity_xml_tag: expected_Version} for a specific band.

    For each package in BAND_PROFILE_VERSIONS[band], loads every available
    profile version <= the canonical profile_version, oldest-first. Because
    the canonical version is loaded last, its version_attrs overwrite any
    earlier ones — activities present only in earlier profiles keep their
    earlier version_attrs (fallback), but conflicts resolve in favor of the
    band's canonical profile.

    Hardened against malformed profile data the same way
    ``_detect_version_sensitive_activities`` is — an explicit ``null`` for
    ``activities`` or ``version_attrs`` is skipped rather than crashing.
    """
    if band in _BAND_EXPECTED_CACHE:
        return _BAND_EXPECTED_CACHE[band]
    expected: dict[str, str] = {}
    plugin_profiles = _get_plugin_profiles()
    band_packages = _merged_band_profile_versions().get(band) or {}
    if not isinstance(band_packages, dict):
        _BAND_EXPECTED_CACHE[band] = expected
        return expected
    for package, profile_version in band_packages.items():
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
            if not isinstance(data, dict):
                continue
            activities = data.get("activities") or {}
            if not isinstance(activities, dict):
                continue
            for act_name, act_data in activities.items():
                if not isinstance(act_data, dict):
                    continue
                vattrs = act_data.get("version_attrs") or {}
                if not isinstance(vattrs, dict):
                    continue
                for tag, version in vattrs.items():
                    if not isinstance(version, str):
                        continue
                    expected[tag] = version
    _BAND_EXPECTED_CACHE[band] = expected
    return expected


# ---------------------------------------------------------------------------
# Lint 121 — band-25-only attribute set
# ---------------------------------------------------------------------------
# Schema field: each profile entry under ``activities[<name>]`` MAY carry an
# ``attrs_introduced_in: {attr_name: band_string}`` map declaring which band
# first introduced a given XAML attribute. When populated across the merged
# profile corpus, lint 121 derives its v25-only set from that data so adding
# a new 25.10 attribute is a one-line profile edit, not a code change.
# When no profile carries the marker (today's corpus has it as null), the
# hard-coded fallback below applies. (R2a H1.)

# Fallback set used when no profile ships ``attrs_introduced_in`` data.
# Update only if every profile JSON omits the marker for the given attr.
_V25_ONLY_ATTRIBUTES_FALLBACK: tuple[str, ...] = (
    "HealingAgentBehavior",
    "ClipboardMode",
)


def _build_v25_only_attributes() -> set[str]:
    """Derive the band-25-only attribute set from profile metadata.

    Walks every band/package profile and collects attributes whose
    ``attrs_introduced_in[attr]`` value parses as ``>= 25``. If no profile
    carries the marker, returns the static fallback tuple verbatim.
    """
    if not _VERSION_BAND_AVAILABLE:
        return set(_V25_ONLY_ATTRIBUTES_FALLBACK)

    derived: set[str] = set()
    saw_marker = False
    try:
        for band, packages in _merged_band_profile_versions().items():
            if not isinstance(packages, dict):
                continue
            for package, profile_version in packages.items():
                if profile_version is None:
                    continue
                data = _load_profile_data(package, profile_version)
                if not isinstance(data, dict):
                    continue
                activities = data.get("activities") or {}
                if not isinstance(activities, dict):
                    continue
                for act_data in activities.values():
                    if not isinstance(act_data, dict):
                        continue
                    introduced = act_data.get("attrs_introduced_in") or {}
                    if not isinstance(introduced, dict):
                        continue
                    saw_marker = saw_marker or bool(introduced)
                    for attr_name, intro_band in introduced.items():
                        if not isinstance(attr_name, str):
                            continue
                        if not isinstance(intro_band, str):
                            continue
                        try:
                            if int(intro_band.split(".")[0]) >= 25:
                                derived.add(attr_name)
                        except (ValueError, AttributeError):
                            continue
    except Exception as exc:  # pragma: no cover — defensive only
        _LOG.warning(
            "lints_version_compat: _build_v25_only_attributes failed "
            "(%s: %s); using fallback set.",
            type(exc).__name__, exc,
        )
        return set(_V25_ONLY_ATTRIBUTES_FALLBACK)

    if not saw_marker:
        return set(_V25_ONLY_ATTRIBUTES_FALLBACK)
    return derived or set(_V25_ONLY_ATTRIBUTES_FALLBACK)


_V25_ONLY_ATTRIBUTES: set[str] = _build_v25_only_attributes()

# Namespace URI for UiPath UIAutomation Next activities.
# ElementTree uses Clark notation: {uri}LocalName
_UIX_NAMESPACE_URI = "http://schemas.uipath.com/workflow/activities/uiautomationnext"

# Pre-compiled version patterns for lint 120 and 122
# Accept dotted variants like "V5.1" as well as canonical "V5" (R2a M3) so a
# future Studio emission shape doesn't silently disable the lint.
_RE_VERSION_V5_PLUS = re.compile(r"^V([5-9]|\d{2,})(\.\d+)*$")
_RE_VERSION_ANY = re.compile(r"^V\d+(\.\d+)*$")


# UX choice (R2a H2): all three lints SILENTLY no-op on a malformed band.
# The user-visible signal for an unparseable band belongs upstream — at the
# scaffold/`ProjectVersion.effective_band()` boundary, not at file-level lint
# evaluation. Emitting per-file warnings on every XAML traversed produces N
# duplicates per project for a single root-cause problem. Lint 120/121 used
# to emit warnings; that path was dropped to align with lint 122.


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
    except (ValueError, TypeError):
        # Malformed band — silent no-op (see comment above).
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
    except (ValueError, TypeError):
        # Malformed band — silent no-op (see comment above).
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
