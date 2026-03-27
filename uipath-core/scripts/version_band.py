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
from pathlib import Path


# ---------------------------------------------------------------------------
# Year-based packages — major version tracks the Studio release year
# (e.g., 25.x.x for 2025, 26.x.x for 2026)
# ---------------------------------------------------------------------------

YEAR_BASED_PACKAGES = frozenset({
    "UiPath.System.Activities",
    "UiPath.UIAutomation.Activities",
    "UiPath.Testing.Activities",
})

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
    "25": {
        "UiPath.System.Activities":        "25.10",
        "UiPath.UIAutomation.Activities":  "26.2",
        "UiPath.Excel.Activities":         "3.5",
        "UiPath.Mail.Activities":          "2.8",
        "UiPath.Testing.Activities":       "25.10",
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
    """

    package_versions: dict[str, str]
    studio_version: str | None = None

    def band_for(self, package: str) -> str | None:
        """Return the major version band for *package*, or ``None`` if absent.

        Strips NuGet range brackets (``[25.12.2]`` → ``25``) and returns
        the first dot-separated segment as the band string.
        """
        ver = self.package_versions.get(package)
        if ver is None:
            return None
        return ver.strip("[]").split(".")[0]

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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

    return ProjectVersion(
        package_versions=dict(deps),
        studio_version=studio_ver,
    )
