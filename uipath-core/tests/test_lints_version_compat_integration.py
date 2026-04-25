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
    def test_malformed_band_silent_no_op(self):
        # versionBand "25.10" is a profile version, not a band integer.
        # int("25.10") raises ValueError. Per R2a H2 the malformed-band path
        # is a SILENT no-op for all three lints; the user-visible signal
        # belongs at the scaffold/`ProjectVersion.effective_band()` boundary,
        # not duplicated per-XAML at lint time.
        results = validate_project(str(_ASSETS / "bad_project_version_compat_malformed_band"), lint=True)
        assert not _fire_numbers(results), \
            "malformed band must not produce false-positive errors"
        assert not _warn_numbers(results), \
            "malformed band must NOT emit per-XAML warnings (silent no-op contract)"

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


class TestProfileShapeHardening:
    """Regression tests for CRIT-3: malformed profile JSON must not break import."""

    def test_null_version_attrs_does_not_break_import(self):
        # A plugin (or harvested profile) carrying `"version_attrs": null` /
        # `"activities": null` would previously crash at module import via
        # `None.items()` and brick the entire `validate_xaml` package.
        # _detect_version_sensitive_activities() must skip such entries
        # gracefully and the dispatch must continue working.
        import importlib

        # Plugin loader is the supported registration surface. Use it to feed
        # a profile that has an explicit-null `activities` map and another
        # whose activity carries a null `version_attrs`.
        from plugin_loader import register_version_profile, register_band_profile_mapping

        bad_pkg = "Acme.Skill.Profiles.HardeningTest"
        register_version_profile(bad_pkg, "1.0", {"activities": None})
        register_version_profile(
            bad_pkg, "2.0",
            {"activities": {"FooActivity": {"version_attrs": None}}},
        )
        register_band_profile_mapping("25", bad_pkg, "1.0")
        register_band_profile_mapping("26", bad_pkg, "2.0")

        # Force a rebuild of the version-sensitive cache after registration.
        import validate_xaml.lints_version_compat as lvc
        importlib.reload(lvc)
        # Direct call to the rebuild path must not raise.
        rebuilt = lvc._safe_detect_version_sensitive_activities()
        assert isinstance(rebuilt, set)
        # And `_invalidate_cache` exposed for plugin reload paths must run
        # cleanly even with the bad profiles registered.
        lvc._invalidate_cache()

        # End-to-end: validate_project still imports + dispatches lints with
        # the bad plugin profiles registered.
        from validate_xaml import validate_project as vp
        results = vp(str(_ASSETS / "good_project_version_compat"), lint=True)
        # The good fixture must remain clean — bad plugin profiles must not
        # bleed errors into clean projects.
        assert not _fire_numbers(results)


class TestVersionRegexAcceptsDottedV5:
    """Regression test for R2a M3: dotted Version strings (V5.1) must be parseable."""

    def test_v5_dot_1_matches_version_any(self):
        from validate_xaml.lints_version_compat import _RE_VERSION_ANY, _RE_VERSION_V5_PLUS
        # _RE_VERSION_ANY (used by lint 122) must accept dotted variants.
        assert _RE_VERSION_ANY.match("V5") is not None
        assert _RE_VERSION_ANY.match("V5.1") is not None
        assert _RE_VERSION_ANY.match("V10") is not None
        assert _RE_VERSION_ANY.match("V10.2") is not None
        # _RE_VERSION_V5_PLUS (used by lint 120) must also accept dotted.
        assert _RE_VERSION_V5_PLUS.match("V5") is not None
        assert _RE_VERSION_V5_PLUS.match("V5.1") is not None
        assert _RE_VERSION_V5_PLUS.match("V10") is not None
        # And reject sub-V5.
        assert _RE_VERSION_V5_PLUS.match("V4") is None
        assert _RE_VERSION_V5_PLUS.match("V4.1") is None


class TestVersionBandIntCoercion:
    """Regression test for R2b M1: int versionBand coerced to str."""

    def test_int_version_band_is_coerced(self, tmp_path, capsys):
        from validate_xaml._orchestration import _read_version_band
        import json as _json
        proj = tmp_path / "intband"
        proj.mkdir()
        (proj / "project.json").write_text(_json.dumps({
            "name": "x", "projectId": "y", "main": "Main.xaml",
            "dependencies": {}, "targetFramework": "Windows",
            "versionBand": 25,
        }))
        result = _read_version_band(str(proj))
        assert result == "25", f"int 25 should coerce to '25', got {result!r}"
        captured = capsys.readouterr()
        assert "versionBand is an int" in captured.err

    def test_string_version_band_passthrough(self, tmp_path):
        from validate_xaml._orchestration import _read_version_band
        import json as _json
        proj = tmp_path / "strband"
        proj.mkdir()
        (proj / "project.json").write_text(_json.dumps({
            "name": "x", "projectId": "y", "main": "Main.xaml",
            "dependencies": {}, "targetFramework": "Windows",
            "versionBand": "25",
        }))
        assert _read_version_band(str(proj)) == "25"

    def test_unsupported_type_returns_none(self, tmp_path):
        from validate_xaml._orchestration import _read_version_band
        import json as _json
        proj = tmp_path / "listband"
        proj.mkdir()
        (proj / "project.json").write_text(_json.dumps({
            "name": "x", "projectId": "y", "main": "Main.xaml",
            "dependencies": {}, "targetFramework": "Windows",
            "versionBand": ["25"],
        }))
        assert _read_version_band(str(proj)) is None
