#!/usr/bin/env python3
"""Shared versioning model for UiPath package version bands.

Single source of truth for:
- ProjectVersion dataclass (tracks all dependency versions from project.json)
- Year-based vs independent package classification
- Independent package compatibility caps per band
- Minimum supported bands per package
- Band-to-profile-version mapping (which upstream doc version to use per band)

All version-aware modules (resolve_nuget, generate_workflow, scaffold_project,
validation) import from here. No version data is duplicated elsewhere.
"""

import dataclasses
import json
import re
from pathlib import Path


# ---------------------------------------------------------------------------
# NuGet version-range prefix regex
#
# Handles: "25.10.5", "[25.10.5]", "[25.10.5,)", ">=25.10", "~25.10.2", etc.
# Captures the leading integer (the band) after stripping range-prefix chars.
# ---------------------------------------------------------------------------

_RANGE_PREFIX_RE = re.compile(r"^[\[\(>=~\s]*(\d+)")

# ---------------------------------------------------------------------------
# Year-based packages — major version tracks the Studio release year
# (e.g., 25.x.x for 2025, 26.x.x for 2026)
# ---------------------------------------------------------------------------

YEAR_BASED_PACKAGES = frozenset({
    "UiPath.System.Activities",
    "UiPath.UIAutomation.Activities",
    "UiPath.Testing.Activities",
})

# Package name aliases (e.g., UiPath.Web.Activities -> UiPath.WebAPI.Activities)
# are defined in resolve_nuget.py:PACKAGE_ALIASES. If alias resolution is
# needed outside NuGet resolution, consider extracting to a shared location.

# ---------------------------------------------------------------------------
# Independent package compatibility caps per band
#
# Maps (package_name, band) → maximum compatible major version prefix.
# Used by fetch_latest_stable_in_band() to filter independent packages.
#
# Maintained as checked-in data — do not infer heuristically from the feed.
# ---------------------------------------------------------------------------

INDEPENDENT_PACKAGE_CAPS = {
    "UiPath.Excel.Activities":       {"25": "3.", "26": "3."},
    "UiPath.Mail.Activities":        {"25": "2.", "26": "2."},
    "UiPath.PDF.Activities":         {"25": "3.", "26": "3."},
    "UiPath.WebAPI.Activities":      {"25": "2.", "26": "2."},
    "UiPath.Database.Activities":    {"25": "2.", "26": "2."},
    "UiPath.Persistence.Activities": {"25": "1.", "26": "1."},
    "UiPath.FormActivityLibrary":    {"25": "2.", "26": "2."},
}

# ---------------------------------------------------------------------------
# Minimum supported bands — per package
#
# Only packages with confirmed version-sensitive generators are listed.
# Bands below these are rejected with a warning/error.
# ---------------------------------------------------------------------------

MIN_SUPPORTED_BANDS = {
    "UiPath.UIAutomation.Activities": "25",
}

# ---------------------------------------------------------------------------
# Band → profile version mapping
#
# Maps a target band to the specific upstream doc version for each package.
# Critical for non-year packages where the band string alone does not
# determine which profile/doc version to use.
# ---------------------------------------------------------------------------

BAND_PROFILE_VERSIONS = {
    # Profile versions track the LATEST STABLE NuGet package major.minor per
    # band. Entries MUST match an actually-shipped stable version on the Studio
    # feed — never a prerelease. When a package's band has no stable promotion
    # yet, this maps to the latest stable that DOES exist (usually the prior
    # band's version), so band-aware lints run against real-world XAML rather
    # than aspirational profiles. See memory: policy_stable_only_harvests.md.
    "25": {
        "UiPath.System.Activities":        "25.10",
        "UiPath.UIAutomation.Activities":  "25.10",  # 26.x is prerelease-only
        "UiPath.Excel.Activities":         "3.4",    # 3.5 is prerelease-only
        "UiPath.Mail.Activities":          "2.8",
        "UiPath.Testing.Activities":       "25.10",
        # packages without upstream docs yet:
        "UiPath.WebAPI.Activities":        None,
        "UiPath.PDF.Activities":           None,
        "UiPath.Database.Activities":      None,
        "UiPath.Persistence.Activities":   None,
        "UiPath.FormActivityLibrary":      None,
    },
    "26": {
        # Band-26 packages without a band-26 stable release fall back to the
        # latest band-25 stable. Update these mappings when UiPath promotes a
        # 26.x stable to the feed.
        "UiPath.System.Activities":        "26.2",   # stable 26.2.4 on feed
        "UiPath.UIAutomation.Activities":  "25.10",  # no 26.x stable yet
        "UiPath.Excel.Activities":         "3.4",    # no 3.5 stable yet
        "UiPath.Mail.Activities":          "2.8",
        "UiPath.Testing.Activities":       "25.10",  # no 26.x stable yet
        # packages without upstream docs yet:
        "UiPath.WebAPI.Activities":        None,
        "UiPath.PDF.Activities":           None,
        "UiPath.Database.Activities":      None,
        "UiPath.Persistence.Activities":   None,
        "UiPath.FormActivityLibrary":      None,
    },
}


# ---------------------------------------------------------------------------
# ProjectVersion — tracks all dependency versions from a project.json
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class ProjectVersion:
    """Represents the resolved version state of a UiPath project.

    Attributes:
        package_versions: All dependencies from project.json.
            Keys are package names, values are version strings
            (may include NuGet range brackets like ``[25.12.2]``).
        studio_version: The ``studioVersion`` field from project.json,
            or ``None`` if absent.
        explicit_band: The ``versionBand`` field from project.json,
            or ``None`` if absent. Takes priority over dependency-derived
            bands when present.
    """

    package_versions: dict[str, str]
    studio_version: str | None = None
    explicit_band: str | None = None

    def band_for(self, package: str) -> str | None:
        """Return the major version band for *package*, or ``None`` if absent.

        Strips NuGet range brackets (``[25.12.2]`` → ``25``) and returns
        the first dot-separated segment as the band string.
        """
        ver = self.package_versions.get(package)
        if not ver:
            return None
        m = _RANGE_PREFIX_RE.match(ver)
        if not m:
            return None
        band = m.group(1)
        try:
            validate_band(band)
            return band
        except ValueError:
            return None

    def is_supported(self, package: str) -> bool | None:
        """Check whether *package*'s band meets the minimum.

        Returns ``True`` if supported, ``False`` if below minimum,
        or ``None`` if the package is absent or has no minimum defined.
        """
        band = self.band_for(package)
        if band is None:
            return None
        min_band = MIN_SUPPORTED_BANDS.get(package)
        if min_band is None:
            return None
        try:
            return int(band) >= int(min_band)
        except ValueError:
            return None

    def effective_band(self) -> str | None:
        """Return the best-known version band for this project.

        Priority: explicit ``versionBand`` > UIAutomation dependency band >
        System.Activities dependency band.
        """
        if self.explicit_band is not None:
            return self.explicit_band
        return (self.band_for("UiPath.UIAutomation.Activities")
                or self.band_for("UiPath.System.Activities"))

    def unsupported_packages(self) -> list[tuple[str, str, str]]:
        """Return a list of ``(package, detected_band, min_band)`` tuples
        for every package whose band falls below its minimum."""
        results = []
        for package, min_band in MIN_SUPPORTED_BANDS.items():
            band = self.band_for(package)
            if band is None:
                continue
            try:
                if int(band) < int(min_band):
                    results.append((package, band, min_band))
            except ValueError:
                continue
        return results

    def disagreeing_packages(self) -> list[tuple[str, str]]:
        """Return year-based packages whose bands disagree with the effective band.

        Returns a list of ``(package, detected_band)`` tuples for any
        year-based package whose major version differs from
        :meth:`effective_band`.  An empty list means all year-based
        dependencies are consistent.
        """
        eff = self.effective_band()
        if eff is None:
            return []
        results = []
        for package in YEAR_BASED_PACKAGES:
            band = self.band_for(package)
            if band is not None and band != eff:
                results.append((package, band))
        return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class UnsupportedBandError(ValueError):
    """Raised when a version band is below the minimum supported."""
    pass


def validate_band(band: str) -> str:
    """Validate that *band* is a numeric version band string.

    Returns the band unchanged if valid.
    Raises ``ValueError`` if *band* is not a non-negative integer string.
    """
    if not band or not band.isdigit():
        raise ValueError(
            f"Invalid version band {band!r}: must be a numeric string (e.g., '25', '26')"
        )
    return band


def is_year_based(package: str) -> bool:
    """Return ``True`` if *package* uses year-based versioning."""
    return package in YEAR_BASED_PACKAGES


def profile_version_for(package: str, band: str) -> str | None:
    """Return the upstream doc profile version for *package* in *band*,
    or ``None`` if no mapping exists."""
    band_map = BAND_PROFILE_VERSIONS.get(band)
    if band_map is None:
        return None
    return band_map.get(package)


def independent_cap(package: str, band: str) -> str | None:
    """Return the version prefix cap for an independent *package* in *band*,
    or ``None`` if uncapped / unknown."""
    caps = INDEPENDENT_PACKAGE_CAPS.get(package)
    if caps is None:
        return None
    return caps.get(band)


def derive_band_from_deps(deps: dict[str, str]) -> str | None:
    """Derive the minimum version band that accommodates every year-based
    dependency in *deps*.

    Inspects each :data:`YEAR_BASED_PACKAGES` entry present in *deps* and
    returns the maximum detected band as a string. When no year-based package
    appears, returns ``None`` (caller cannot commit to a band).

    The returned band is always present in :data:`BAND_PROFILE_VERSIONS`;
    otherwise returns ``None`` so the caller can skip stamping ``versionBand``
    rather than emit an unvalidated value.

    Raises :class:`UnsupportedBandError` if any package's detected band is
    below its entry in :data:`MIN_SUPPORTED_BANDS`.
    """
    pv = ProjectVersion(package_versions=dict(deps))
    detected: list[int] = []
    for pkg in YEAR_BASED_PACKAGES:
        band = pv.band_for(pkg)
        if band is not None:
            detected.append(int(band))
    if not detected:
        return None

    for pkg, min_band in MIN_SUPPORTED_BANDS.items():
        pkg_band = pv.band_for(pkg)
        if pkg_band is not None and int(pkg_band) < int(min_band):
            raise UnsupportedBandError(
                f"{pkg} band {pkg_band} is below minimum supported band {min_band}"
            )

    band = str(max(detected))
    if band not in BAND_PROFILE_VERSIONS:
        return None
    return band


def detect_project_version(project_dir: str | Path) -> ProjectVersion:
    """Read ``project.json`` from *project_dir* and return a ProjectVersion.

    Raises ``FileNotFoundError`` if ``project.json`` does not exist.
    Raises ``ValueError`` if ``project.json`` is not valid JSON.
    """
    project_dir = Path(project_dir)
    pj_path = project_dir / "project.json"
    if not pj_path.exists():
        raise FileNotFoundError(f"project.json not found in {project_dir}")

    with pj_path.open("r", encoding="utf-8-sig") as f:
        data = json.load(f)

    deps = data.get("dependencies", {})
    studio_ver = data.get("studioVersion")
    version_band = data.get("versionBand")

    if version_band is not None:
        try:
            validate_band(version_band)
        except ValueError as e:
            raise ValueError(
                f"Invalid versionBand {version_band!r} in {pj_path}: "
                f"{e}. Use a plain band number like '25' or '26', not a profile version like '25.10'."
            ) from e

    return ProjectVersion(
        package_versions=dict(deps),
        studio_version=studio_ver,
        explicit_band=version_band,
    )
