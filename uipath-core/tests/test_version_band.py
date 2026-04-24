"""Unit tests for uipath-core/scripts/version_band.py.

Tests cover current implemented behavior.  Cases where task #5 (P1-B) will
fix a known bug are marked xfail so they flip to passing automatically once
the fix lands.
"""

import json
import sys
from pathlib import Path

import pytest

# Make the scripts package importable without installation.
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from version_band import (
    YEAR_BASED_PACKAGES,
    ProjectVersion,
    UnsupportedBandError,
    derive_band_from_deps,
    detect_project_version,
    independent_cap,
    is_year_based,
    profile_version_for,
    validate_band,
)

FIXTURES = Path(__file__).parent / "fixtures"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pv(pkg: str, ver: str, **kwargs) -> ProjectVersion:
    """Shortcut: single-package ProjectVersion."""
    return ProjectVersion(package_versions={pkg: ver}, **kwargs)


_UIA = "UiPath.UIAutomation.Activities"
_SYS = "UiPath.System.Activities"
_TST = "UiPath.Testing.Activities"
_EXL = "UiPath.Excel.Activities"
_MAIL = "UiPath.Mail.Activities"


# ---------------------------------------------------------------------------
# ProjectVersion.band_for
# ---------------------------------------------------------------------------

class TestBandFor:
    """band_for strips NuGet range syntax and returns the major-version band."""

    @pytest.mark.parametrize("ver,expected", [
        ("[25.10.5]",        "25"),   # pinned exact bracket form
        ("[25.10.5,)",       "25"),   # half-open range (no upper bound)
        ("[25.10.5, 26.0.0)", "25"),  # range with upper bound
        ("25.10.5",          "25"),   # plain version, no brackets
        ("25.10.5-preview",  "25"),   # pre-release suffix
    ])
    def test_band_for_current_working(self, ver, expected):
        pv = _pv(_UIA, ver)
        assert pv.band_for(_UIA) == expected

    @pytest.mark.parametrize("ver,expected", [
        (">=25.10",   "25"),  # inequality prefix
        ("~25.10.2",  "25"),  # tilde prefix
    ])
    def test_band_for_range_prefix_xfail(self, ver, expected):
        pv = _pv(_UIA, ver)
        assert pv.band_for(_UIA) == expected

    def test_band_for_missing_package(self):
        pv = ProjectVersion(package_versions={})
        assert pv.band_for(_UIA) is None

    def test_band_for_empty_string(self):
        pv = _pv(_UIA, "")
        assert pv.band_for(_UIA) is None

    def test_band_for_non_numeric(self):
        pv = _pv(_UIA, "abc")
        assert pv.band_for(_UIA) is None


# ---------------------------------------------------------------------------
# ProjectVersion.effective_band
# ---------------------------------------------------------------------------

class TestEffectiveBand:
    def test_explicit_band_wins_over_uia(self):
        """explicit_band takes priority over any dependency-derived band."""
        pv = ProjectVersion(
            package_versions={_UIA: "[26.2.0]"},
            explicit_band="25",
        )
        assert pv.effective_band() == "25"

    def test_uia_wins_over_system(self):
        """UIAutomation band takes priority when no explicit band is set."""
        pv = ProjectVersion(package_versions={
            _UIA: "[26.2.0]",
            _SYS: "[25.10.5]",
        })
        assert pv.effective_band() == "26"

    def test_fallback_to_system(self):
        """Falls back to System.Activities band when UIAutomation absent."""
        pv = ProjectVersion(package_versions={_SYS: "[25.10.5]"})
        assert pv.effective_band() == "25"

    def test_returns_none_when_no_year_based(self):
        """Returns None when no year-based packages are present."""
        pv = ProjectVersion(package_versions={_EXL: "[3.5.0]"})
        assert pv.effective_band() is None


# ---------------------------------------------------------------------------
# ProjectVersion.disagreeing_packages
# ---------------------------------------------------------------------------

class TestDisagreeingPackages:
    def test_empty_when_all_agree(self):
        pv = ProjectVersion(package_versions={
            _UIA: "[25.10.5]",
            _SYS: "[25.10.5]",
            _TST: "[25.10.0]",
        })
        assert pv.disagreeing_packages() == []

    def test_returns_list_on_disagreement(self):
        """System at 25.x disagrees with effective band 26 (from UIAutomation)."""
        pv = ProjectVersion(package_versions={
            _UIA: "[26.2.0]",
            _SYS: "[25.10.5]",
        })
        result = pv.disagreeing_packages()
        # effective_band is "26"; System band is "25" → disagreement
        assert (_SYS, "25") in result

    def test_empty_when_no_year_based(self):
        """When effective_band is None, no disagreement can exist."""
        pv = ProjectVersion(package_versions={_EXL: "[3.5.0]"})
        assert pv.disagreeing_packages() == []


# ---------------------------------------------------------------------------
# ProjectVersion.unsupported_packages
# ---------------------------------------------------------------------------

class TestUnsupportedPackages:
    def test_empty_when_all_meet_minimum(self):
        pv = _pv(_UIA, "[25.10.5]")
        assert pv.unsupported_packages() == []

    def test_returns_entry_below_minimum(self):
        pv = _pv(_UIA, "[24.10.0]")
        result = pv.unsupported_packages()
        assert len(result) == 1
        pkg, detected, min_band = result[0]
        assert pkg == _UIA
        assert detected == "24"
        assert min_band == "25"

    def test_package_not_in_min_supported_treated_as_unknown(self):
        """Packages absent from MIN_SUPPORTED_BANDS are not reported."""
        pv = _pv(_EXL, "[3.5.0]")
        assert pv.unsupported_packages() == []


# ---------------------------------------------------------------------------
# ProjectVersion.is_supported
# ---------------------------------------------------------------------------

class TestIsSupported:
    """is_supported returns True/False when a minimum applies, None otherwise."""

    def test_true_when_band_meets_minimum(self):
        """UIAutomation @ 25 meets the min-supported band (25) → True."""
        pv = _pv(_UIA, "[25.10.5]")
        assert pv.is_supported(_UIA) is True

    def test_true_when_band_exceeds_minimum(self):
        """UIAutomation @ 26 exceeds the min-supported band (25) → True."""
        pv = _pv(_UIA, "[26.2.0]")
        assert pv.is_supported(_UIA) is True

    def test_false_when_band_below_minimum(self):
        """UIAutomation @ 24 is below the min-supported band (25) → False."""
        pv = _pv(_UIA, "[24.10.0]")
        assert pv.is_supported(_UIA) is False

    def test_none_when_package_absent(self):
        """Package missing from package_versions → None (band_for returns None)."""
        pv = ProjectVersion(package_versions={})
        assert pv.is_supported(_UIA) is None

    def test_none_when_no_minimum_defined(self):
        """Excel has no MIN_SUPPORTED_BANDS entry → None regardless of band."""
        pv = _pv(_EXL, "[3.5.0]")
        assert pv.is_supported(_EXL) is None

    def test_none_when_band_non_numeric(self):
        """Non-numeric version string → band_for returns None → is_supported None."""
        pv = _pv(_UIA, "abc")
        assert pv.is_supported(_UIA) is None


# ---------------------------------------------------------------------------
# validate_band
# ---------------------------------------------------------------------------

class TestValidateBand:
    @pytest.mark.parametrize("band", ["24", "25", "26"])
    def test_accepts_numeric_year_bands(self, band):
        assert validate_band(band) == band

    @pytest.mark.parametrize("bad", ["", "25.10", "abc"])
    def test_raises_value_error_on_invalid(self, bad):
        with pytest.raises(ValueError):
            validate_band(bad)

    def test_raises_on_none(self):
        """validate_band(None) raises ValueError (via isdigit on None)."""
        with pytest.raises((ValueError, AttributeError)):
            validate_band(None)


# ---------------------------------------------------------------------------
# is_year_based
# ---------------------------------------------------------------------------

class TestIsYearBased:
    @pytest.mark.parametrize("pkg", [
        "UiPath.System.Activities",
        "UiPath.UIAutomation.Activities",
        "UiPath.Testing.Activities",
    ])
    def test_true_for_year_based(self, pkg):
        assert is_year_based(pkg) is True

    @pytest.mark.parametrize("pkg", [
        "UiPath.Excel.Activities",
        "UiPath.Mail.Activities",
    ])
    def test_false_for_independent(self, pkg):
        assert is_year_based(pkg) is False


# ---------------------------------------------------------------------------
# profile_version_for
# ---------------------------------------------------------------------------

class TestProfileVersionFor:
    def test_system_activities_band25(self):
        assert profile_version_for("UiPath.System.Activities", "25") == "25.10"

    def test_unknown_package_returns_none(self):
        assert profile_version_for("UiPath.Unknown.Package", "25") is None

    def test_webapi_activities_band25_is_none(self):
        """WebAPI.Activities has no profile doc for band 25 (known-None mapping)."""
        assert profile_version_for("UiPath.WebAPI.Activities", "25") is None

    def test_unknown_band_returns_none(self):
        assert profile_version_for("UiPath.System.Activities", "99") is None


# ---------------------------------------------------------------------------
# independent_cap
# ---------------------------------------------------------------------------

class TestIndependentCap:
    def test_excel_activities_band25(self):
        assert independent_cap("UiPath.Excel.Activities", "25") == "3."

    def test_year_based_package_returns_none(self):
        """Year-based packages are not in INDEPENDENT_PACKAGE_CAPS."""
        assert independent_cap("UiPath.System.Activities", "25") is None

    def test_unknown_package_returns_none(self):
        assert independent_cap("UiPath.Unknown.Package", "25") is None


# ---------------------------------------------------------------------------
# derive_band_from_deps
# ---------------------------------------------------------------------------

class TestDeriveBandFromDeps:
    def test_pure_band_25(self):
        deps = {_SYS: "[25.10.5]", _UIA: "[25.10.30]"}
        assert derive_band_from_deps(deps) == "25"

    def test_pure_band_26(self):
        deps = {_SYS: "[26.2.4]", _UIA: "[26.2.0]"}
        assert derive_band_from_deps(deps) == "26"

    def test_mixed_picks_max(self):
        """WI5 scaffold shape: System 26.2 + UIAutomation 25.10 must land on band 26."""
        deps = {_SYS: "[26.2.4]", _UIA: "[25.10.30]"}
        assert derive_band_from_deps(deps) == "26"

    def test_only_system_activities(self):
        deps = {_SYS: "[25.10.5]"}
        assert derive_band_from_deps(deps) == "25"

    def test_no_year_based_deps_returns_none(self):
        deps = {_EXL: "[3.4.1]", _MAIL: "[2.8.0]"}
        assert derive_band_from_deps(deps) is None

    def test_empty_deps_returns_none(self):
        assert derive_band_from_deps({}) is None

    def test_unknown_band_returns_none(self):
        """Year-based dep pinned to a band we don't know about → caller skips stamping."""
        deps = {_SYS: "[99.1.0]"}
        assert derive_band_from_deps(deps) is None

    def test_below_minimum_raises(self):
        """UIAutomation 24.x is below MIN_SUPPORTED_BANDS (25). Surface the failure."""
        deps = {_UIA: "[24.10.0]"}
        with pytest.raises(UnsupportedBandError):
            derive_band_from_deps(deps)

    def test_ignores_independent_packages(self):
        """Excel 3.4 is independent — should not influence band derivation."""
        deps = {_SYS: "[26.2.4]", _EXL: "[3.4.1]"}
        assert derive_band_from_deps(deps) == "26"


# ---------------------------------------------------------------------------
# detect_project_version
# ---------------------------------------------------------------------------

class TestDetectProjectVersion:
    def test_reads_good_fixture(self, tmp_path):
        data = json.loads((FIXTURES / "good_project.json").read_text(encoding="utf-8"))
        (tmp_path / "project.json").write_text(json.dumps(data), encoding="utf-8")
        pv = detect_project_version(tmp_path)
        # good_project.json has explicit versionBand "25"
        assert pv.explicit_band == "25"
        assert pv.studio_version == "25.10.0"
        assert pv.package_versions["UiPath.UIAutomation.Activities"] == "[26.2.0]"

    def test_raises_file_not_found_for_missing_dir(self, tmp_path):
        empty_dir = tmp_path / "no_project"
        empty_dir.mkdir()
        with pytest.raises(FileNotFoundError):
            detect_project_version(empty_dir)

    def test_no_explicit_band_when_key_absent(self, tmp_path):
        """When project.json has no 'versionBand' key, explicit_band is None."""
        data = {
            "name": "Inline",
            "dependencies": {"UiPath.System.Activities": "[25.10.5]"},
        }
        (tmp_path / "project.json").write_text(json.dumps(data), encoding="utf-8")
        pv = detect_project_version(tmp_path)
        assert pv.explicit_band is None
        assert pv.package_versions["UiPath.System.Activities"] == "[25.10.5]"

    def test_malformed_band_raises_value_error(self, tmp_path):
        """'versionBand': '25.10' (profile version used as band) should raise ValueError."""
        data = {
            "name": "Malformed",
            "dependencies": {},
            "versionBand": "25.10",
        }
        (tmp_path / "project.json").write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="versionBand"):
            detect_project_version(tmp_path)
