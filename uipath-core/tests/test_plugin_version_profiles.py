"""Plugin-registered version profile integration tests.

Verifies that plugins can supply their own version profiles + band mappings
through plugin_loader, and that lints_version_compat picks them up.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import plugin_loader
from plugin_loader import (
    get_band_profile_mappings,
    get_version_profiles,
    register_band_profile_mapping,
    register_version_profile,
)


@pytest.fixture
def loaded_plugins():
    plugin_loader.load_plugins()
    yield


@pytest.fixture
def isolated_registries():
    """Snapshot + restore the plugin registries so tests don't leak state."""
    snap_profiles = dict(plugin_loader._version_profiles)
    snap_bands = {b: dict(pkgs) for b, pkgs in plugin_loader._band_profile_mappings.items()}
    yield
    plugin_loader._version_profiles.clear()
    plugin_loader._version_profiles.update(snap_profiles)
    plugin_loader._band_profile_mappings.clear()
    plugin_loader._band_profile_mappings.update(snap_bands)


class TestTasksPluginRegistration:
    """The uipath-tasks plugin ships a Persistence.Activities profile."""

    def test_persistence_profile_is_registered(self, loaded_plugins):
        profiles = get_version_profiles()
        assert ("UiPath.Persistence.Activities", "1.4") in profiles

    def test_persistence_profile_has_expected_activities(self, loaded_plugins):
        profiles = get_version_profiles()
        activities = profiles[("UiPath.Persistence.Activities", "1.4")]["activities"]
        expected = {
            "CreateFormTask", "WaitForFormTaskAndResume", "GetFormTasks",
            "CreateExternalTask", "WaitForExternalTaskAndResume",
            "CompleteTask", "AssignTasks",
        }
        assert expected <= set(activities.keys())

    def test_persistence_band_mappings_cover_25_and_26(self, loaded_plugins):
        mappings = get_band_profile_mappings()
        assert mappings.get("25", {}).get("UiPath.Persistence.Activities") == "1.4"
        assert mappings.get("26", {}).get("UiPath.Persistence.Activities") == "1.4"


class TestMergedBandProfileVersions:
    """lints_version_compat merges core BAND_PROFILE_VERSIONS with plugin entries."""

    def test_merged_includes_plugin_package(self, loaded_plugins):
        from validate_xaml.lints_version_compat import _merged_band_profile_versions
        merged = _merged_band_profile_versions()
        assert merged["25"].get("UiPath.Persistence.Activities") == "1.4"
        assert merged["26"].get("UiPath.Persistence.Activities") == "1.4"

    def test_merged_preserves_core_packages(self, loaded_plugins):
        from validate_xaml.lints_version_compat import _merged_band_profile_versions
        merged = _merged_band_profile_versions()
        assert merged["25"]["UiPath.System.Activities"] == "25.10"
        assert merged["26"]["UiPath.System.Activities"] == "26.2"


class TestProfileLookup:
    """_load_profile_data prefers plugin-registered profiles over on-disk."""

    def test_plugin_profile_wins_over_disk(self, isolated_registries):
        from validate_xaml.lints_version_compat import _load_profile_data
        shadow = {"activities": {"_Sentinel": {"version_attrs": {}}}}
        register_version_profile("UiPath.System.Activities", "25.10", shadow)
        data = _load_profile_data("UiPath.System.Activities", "25.10")
        assert data is shadow

    def test_disk_used_when_plugin_absent(self, loaded_plugins):
        from validate_xaml.lints_version_compat import _load_profile_data
        data = _load_profile_data("UiPath.System.Activities", "25.10")
        assert data is not None
        assert "activities" in data

    def test_returns_none_when_neither_source_has_profile(self, isolated_registries):
        from validate_xaml.lints_version_compat import _load_profile_data
        assert _load_profile_data("NonExistent.Package", "99.99") is None


class TestDynamicRegistration:
    """Round-trip: plugins can add profiles at runtime and see them."""

    def test_register_and_read_back(self, isolated_registries):
        profile = {"activities": {"DummyActivity": {"version_attrs": {"DummyActivity": "V9"}}}}
        register_version_profile("Test.Package", "9.9", profile)
        register_band_profile_mapping("99", "Test.Package", "9.9")

        profiles = get_version_profiles()
        assert profiles[("Test.Package", "9.9")] is profile

        mappings = get_band_profile_mappings()
        assert mappings["99"]["Test.Package"] == "9.9"

    def test_band_mapping_reaches_lint_122_expected_map(self, isolated_registries):
        profile = {"activities": {"_PluginAct": {"version_attrs": {"_PluginTag": "V7"}}}}
        register_version_profile("Test.BandPkg", "1.0", profile)
        register_band_profile_mapping("25", "Test.BandPkg", "1.0")

        from validate_xaml.lints_version_compat import (
            _BAND_EXPECTED_CACHE,
            _build_band_expected_versions,
        )
        _BAND_EXPECTED_CACHE.pop("25", None)
        expected = _build_band_expected_versions("25")
        assert expected.get("_PluginTag") == "V7"
