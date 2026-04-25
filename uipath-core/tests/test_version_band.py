"""Unit tests for uipath-core/scripts/version_band.py.

Tests cover current implemented behavior.  Cases where task #5 (P1-B) will
fix a known bug are marked xfail so they flip to passing automatically once
the fix lands.
"""

import json
import sys
from pathlib import Path
from types import MappingProxyType

import pytest

# Make the scripts package importable without installation.
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import version_band as _vb  # noqa: E402  (import after sys.path tweak)
from version_band import (
    BAND_PROFILE_VERSIONS,
    INDEPENDENT_PACKAGE_CAPS,
    MIN_SUPPORTED_BANDS,
    YEAR_BASED_PACKAGES,
    ProjectVersion,
    UnsupportedBandError,
    derive_band_from_deps,
    detect_project_version,
    disagreeing_year_based_bands,
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
    def test_band_for_range_prefix_supported(self, ver, expected):
        # Was previously named *_xfail; the regex now handles range prefixes
        # so it's been renamed and the marker dropped (R1 N2).
        pv = _pv(_UIA, ver)
        assert pv.band_for(_UIA) == expected

    @pytest.mark.parametrize("ver,expected", [
        ("(,26.0.0]",  "26"),  # open lower-bound NuGet range
        ("(*,26.0.0]", "26"),  # wildcard lower bound (seen in some manifests)
        ("[,26.0.0)",  "26"),  # malformed but observed in the wild
        ("(,26.0.0)",  "26"),  # open lower-bound, exclusive upper
    ])
    def test_band_for_open_lower_bound_ranges(self, ver, expected):
        # R1 M2 — regex must strip leading commas / wildcards so
        # open-lower-bound NuGet ranges resolve to a band.
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

    def test_effective_band_rejects_invalid_explicit_band(self):
        """R1 C1 / CRIT-1 — an in-memory caller passing a profile-version
        string as ``explicit_band`` must NOT mask a working derived band.

        ``"25.10"`` is a profile version, not a band. ``effective_band``
        should reject it via ``validate_band`` and fall through to the
        UIAutomation-derived band ``"25"``.
        """
        pv = ProjectVersion(
            package_versions={_UIA: "[25.10.0]"},
            explicit_band="25.10",
        )
        assert pv.effective_band() == "25"

    @pytest.mark.parametrize("bogus", ["", "25.10", "abc", "2025", "5"])
    def test_effective_band_falls_back_for_various_invalid_explicit(self, bogus):
        """Empty string, year-form, single-digit, etc. should all fall
        through to derivation rather than be returned verbatim."""
        pv = ProjectVersion(
            package_versions={_UIA: "[25.10.0]"},
            explicit_band=bogus,
        )
        assert pv.effective_band() == "25"

    def test_effective_band_falls_back_to_none_when_invalid_and_no_deps(self):
        """If explicit_band is invalid AND no year-based deps are present,
        effective_band returns None (rather than the invalid value)."""
        pv = ProjectVersion(
            package_versions={_EXL: "[3.5.0]"},
            explicit_band="25.10",
        )
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
    @pytest.mark.parametrize("band", ["20", "24", "25", "26", "99"])
    def test_accepts_numeric_year_bands(self, band):
        assert validate_band(band) == band

    @pytest.mark.parametrize("bad", ["", "25.10", "abc"])
    def test_raises_value_error_on_invalid(self, bad):
        with pytest.raises(ValueError):
            validate_band(bad)

    def test_raises_on_none(self):
        """R1 N3 — pin to ValueError (isinstance check rejects None
        before isdigit could raise AttributeError)."""
        with pytest.raises(ValueError):
            validate_band(None)

    @pytest.mark.parametrize("bad", [
        "2025",   # year-form (R1 M1) — looks plausible but bands are 2-digit
        "0",      # single digit
        "9",      # single digit, valid-looking
        "00",     # zero, two-digit but below MIN
        "01",     # below MIN
        "19",     # below MIN range [20, 99]
        "100",    # three digit, above MAX
    ])
    def test_rejects_out_of_range_or_year_form(self, bad):
        """R1 M1 — tighten validate_band to two-digit form within [20, 99]."""
        with pytest.raises(ValueError):
            validate_band(bad)

    @pytest.mark.parametrize("bad", [42, 25.0, ["25"], ("25",), {"25"}])
    def test_rejects_non_string_types(self, bad):
        """validate_band requires a string — int, float, list, etc. raise."""
        with pytest.raises(ValueError):
            validate_band(bad)


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

    def test_no_band_fixture_loads_cleanly(self, tmp_path):
        """R1 N1 — exercise the committed `no_band_project.json` fixture."""
        src = (FIXTURES / "no_band_project.json").read_text(encoding="utf-8")
        (tmp_path / "project.json").write_text(src, encoding="utf-8")
        pv = detect_project_version(tmp_path)
        assert pv.explicit_band is None
        assert pv.studio_version == "25.10.0"
        assert pv.package_versions["UiPath.System.Activities"] == "[25.10.5]"
        # Falls back to derivation from System.Activities band.
        assert pv.effective_band() == "25"

    def test_malformed_band_fixture_raises(self, tmp_path):
        """R1 N1 — exercise the committed `malformed_band_project.json` fixture."""
        src = (FIXTURES / "malformed_band_project.json").read_text(encoding="utf-8")
        (tmp_path / "project.json").write_text(src, encoding="utf-8")
        with pytest.raises(ValueError, match="versionBand"):
            detect_project_version(tmp_path)

    def test_dependencies_not_an_object_raises_value_error(self, tmp_path):
        """R1 M5 — malformed `dependencies` (list/string) must surface a clear
        ValueError, not a raw TypeError from `dict(deps)`."""
        data = {"name": "BadDeps", "dependencies": ["UiPath.System.Activities"]}
        (tmp_path / "project.json").write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="dependencies"):
            detect_project_version(tmp_path)

    def test_dependencies_string_raises_value_error(self, tmp_path):
        data = {"name": "BadDeps", "dependencies": "not-a-dict"}
        (tmp_path / "project.json").write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="dependencies"):
            detect_project_version(tmp_path)

    def test_dependencies_null_treated_as_empty(self, tmp_path):
        """`dependencies: null` is tolerated as an empty mapping — common in
        skeleton manifests written by other tools."""
        data = {"name": "NullDeps", "dependencies": None}
        (tmp_path / "project.json").write_text(json.dumps(data), encoding="utf-8")
        pv = detect_project_version(tmp_path)
        assert pv.package_versions == {}


# ---------------------------------------------------------------------------
# disagreeing_year_based_bands  (HIGH-4 helper)
# ---------------------------------------------------------------------------

class TestDisagreeingYearBasedBands:
    def test_empty_when_no_year_based_deps(self):
        assert disagreeing_year_based_bands({}) == set()
        assert disagreeing_year_based_bands({_EXL: "[3.4.1]"}) == set()

    def test_single_band_returns_singleton(self):
        deps = {_SYS: "[25.10.5]", _UIA: "[25.10.30]"}
        assert disagreeing_year_based_bands(deps) == {"25"}

    def test_disagreement_returns_all_bands(self):
        """System at 26.x + UIA at 25.x → caller can warn about the spread."""
        deps = {_SYS: "[26.2.4]", _UIA: "[25.10.30]"}
        assert disagreeing_year_based_bands(deps) == {"25", "26"}

    def test_derive_picks_max_even_when_disagreement(self):
        """derive_band_from_deps still returns max(bands) for back-compat —
        callers must explicitly check `disagreeing_year_based_bands` to surface
        the disagreement (HIGH-4 contract)."""
        deps = {_SYS: "[26.2.4]", _UIA: "[25.10.30]"}
        assert derive_band_from_deps(deps) == "26"
        assert disagreeing_year_based_bands(deps) == {"25", "26"}


# ---------------------------------------------------------------------------
# Module-level constants are immutable shared state  (CRIT-2)
# ---------------------------------------------------------------------------

class TestModuleConstantsAreImmutable:
    """R1 C2 / CRIT-2 — top-level dicts must be MappingProxyType so a stray
    importer can't poison validation state for the whole process."""

    def test_band_profile_versions_is_mapping_proxy(self):
        assert isinstance(BAND_PROFILE_VERSIONS, MappingProxyType)

    def test_band_profile_versions_inner_dicts_are_mapping_proxy(self):
        for band, inner in BAND_PROFILE_VERSIONS.items():
            assert isinstance(inner, MappingProxyType), (
                f"BAND_PROFILE_VERSIONS[{band!r}] is not MappingProxyType"
            )

    def test_min_supported_bands_is_mapping_proxy(self):
        assert isinstance(MIN_SUPPORTED_BANDS, MappingProxyType)

    def test_independent_package_caps_is_mapping_proxy(self):
        assert isinstance(INDEPENDENT_PACKAGE_CAPS, MappingProxyType)

    def test_independent_package_caps_inner_dicts_are_mapping_proxy(self):
        for pkg, inner in INDEPENDENT_PACKAGE_CAPS.items():
            assert isinstance(inner, MappingProxyType), (
                f"INDEPENDENT_PACKAGE_CAPS[{pkg!r}] is not MappingProxyType"
            )

    def test_min_supported_bands_rejects_mutation(self):
        with pytest.raises(TypeError):
            MIN_SUPPORTED_BANDS["UiPath.Excel.Activities"] = "99"  # type: ignore[index]

    def test_band_profile_versions_rejects_top_level_mutation(self):
        with pytest.raises(TypeError):
            BAND_PROFILE_VERSIONS["27"] = {}  # type: ignore[index]

    def test_band_profile_versions_rejects_inner_mutation(self):
        with pytest.raises(TypeError):
            BAND_PROFILE_VERSIONS["25"]["UiPath.System.Activities"] = "00.00"  # type: ignore[index]

    def test_independent_package_caps_rejects_top_level_mutation(self):
        with pytest.raises(TypeError):
            INDEPENDENT_PACKAGE_CAPS["UiPath.Excel.Activities"] = {}  # type: ignore[index]

    def test_independent_package_caps_rejects_inner_mutation(self):
        with pytest.raises(TypeError):
            INDEPENDENT_PACKAGE_CAPS["UiPath.Excel.Activities"]["25"] = "9."  # type: ignore[index]


# ---------------------------------------------------------------------------
# Invariants drift guard  (HIGH-3)
# ---------------------------------------------------------------------------

class TestInvariants:
    """R1 H1 / HIGH-3 — drift guard between BAND_PROFILE_VERSIONS,
    MIN_SUPPORTED_BANDS, INDEPENDENT_PACKAGE_CAPS, and YEAR_BASED_PACKAGES."""

    def test_invariants_hold_at_import(self):
        """Re-invoke the import-time validator so any future drift produces a
        loud test failure, not silently-no-op lints in production."""
        # Should not raise.
        _vb._validate_invariants()

    def test_all_year_based_packages_in_every_band(self):
        for band, profile_map in BAND_PROFILE_VERSIONS.items():
            missing = YEAR_BASED_PACKAGES - frozenset(profile_map)
            assert not missing, (
                f"Band {band!r} is missing year-based packages: "
                f"{sorted(missing)}"
            )

    def test_min_supported_bands_reference_known_bands(self):
        for pkg, b in MIN_SUPPORTED_BANDS.items():
            assert b in BAND_PROFILE_VERSIONS, (
                f"MIN_SUPPORTED_BANDS[{pkg!r}]={b!r} not in BAND_PROFILE_VERSIONS"
            )

    def test_independent_caps_cover_every_band(self):
        bands = set(BAND_PROFILE_VERSIONS)
        for pkg, capmap in INDEPENDENT_PACKAGE_CAPS.items():
            assert set(capmap) == bands, (
                f"INDEPENDENT_PACKAGE_CAPS[{pkg!r}] band coverage mismatch: "
                f"{sorted(capmap)} vs {sorted(bands)}"
            )
