"""End-to-end integration tests for version-compat lints (120, 121, 122).

These tests drive the real validate_project() pipeline against the on-disk
fixtures under assets/lint-test-cases/, asserting that:
- Lints 120/121/122 fire on bad_project_version_compat* projects.
- They stay silent on good_project_version_compat* projects.
- They no-op when versionBand is absent / malformed / unknown (project-level
  warnings only, no false errors).

Without these tests, the lint dispatcher / FileContext plumbing can break
(as it did pre-1.2.1) and the unit tests that import lints_version_compat
helpers directly would still pass while production lint runs go silent.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from validate_xaml import validate_project


_ASSETS = Path(__file__).parent.parent / "assets" / "lint-test-cases"


def _fire_numbers(results):
    """Return the set of lint numbers that fired as ERRORS across all results."""
    fired = set()
    for r in results:
        for msg in r.errors:
            for n in (120, 121, 122):
                if f"[lint {n}]" in msg:
                    fired.add(n)
    return fired


def _warn_numbers(results):
    fired = set()
    for r in results:
        for msg in r.warnings:
            for n in (120, 121, 122):
                if f"[lint {n}]" in msg:
                    fired.add(n)
    return fired


class TestLintsRegistered:
    def test_lints_120_121_122_in_registry_after_package_import(self):
        from validate_xaml._registry import _LINT_REGISTRY
        nums = {e.number for e in _LINT_REGISTRY}
        assert {120, 121, 122} <= nums


class TestBadFixturesFire:
    def test_band_25_fixture_triggers_120_and_121(self):
        results = validate_project(str(_ASSETS / "bad_project_version_compat"), lint=True)
        fired = _fire_numbers(results)
        assert 120 in fired, "lint 120 should fire on V5 below band 25"
        assert 121 in fired, "lint 121 should fire on HealingAgentBehavior below band 25"

    def test_band_26_fixture_triggers_122(self):
        results = validate_project(str(_ASSETS / "bad_project_version_compat_band26"), lint=True)
        fired = _fire_numbers(results)
        assert 122 in fired, "lint 122 should fire on Version mismatch vs band-26 profile"


class TestGoodFixturesSilent:
    def test_band_25_good_fixture_is_clean(self):
        results = validate_project(str(_ASSETS / "good_project_version_compat"), lint=True)
        assert not _fire_numbers(results), \
            "good band-25 fixture must not trigger version-compat errors"

    def test_band_26_good_fixture_is_clean(self):
        results = validate_project(str(_ASSETS / "good_project_version_compat_band26"), lint=True)
        assert not _fire_numbers(results), \
            "good band-26 fixture must not trigger version-compat errors"


class TestOptInInvariant:
    def test_no_band_means_no_version_compat_errors(self):
        # Same Main.xaml content as the bad band-25 fixture, but project.json
        # has no versionBand → lints must stay dormant.
        results = validate_project(str(_ASSETS / "bad_project_version_compat_no_band"), lint=True)
        assert not _fire_numbers(results), \
            "lints 120/121/122 must be opt-in — silent when versionBand is absent"


class TestEdgeCases:
    def test_malformed_band_emits_warnings_not_errors(self):
        # versionBand "25.10" is a profile version, not a band integer.
        # int("25.10") raises ValueError → lints emit warnings and skip.
        results = validate_project(str(_ASSETS / "bad_project_version_compat_malformed_band"), lint=True)
        assert not _fire_numbers(results), \
            "malformed band must not produce false-positive errors"
        warned = _warn_numbers(results)
        assert 120 in warned and 121 in warned, \
            "malformed band must surface warnings on lints 120 and 121"

    def test_unknown_band_99_no_ops(self):
        # Band "99" has no entry in BAND_PROFILE_VERSIONS → lint 122 expected
        # dict is empty and exits early. Lints 120/121 also exit because
        # int("99") >= 25.
        results = validate_project(str(_ASSETS / "bad_project_version_compat_unknown_band"), lint=True)
        assert not _fire_numbers(results), \
            "unknown band must no-op rather than emit false errors"

    def test_missing_profile_no_ops(self):
        # NHover has no version_attrs harvested in the band-25 profile.
        # Lint 122 must skip silently for activities not in the expected map.
        results = validate_project(str(_ASSETS / "bad_project_version_compat_missing_profile"), lint=True)
        assert not _fire_numbers(results), \
            "activity absent from profile must not trigger lint 122"
