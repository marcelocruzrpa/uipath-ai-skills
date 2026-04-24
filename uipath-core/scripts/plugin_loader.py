#!/usr/bin/env python3
"""Plugin loader — discovers and loads skill extensions.

Skills can register generators, lint rules, scaffold hooks, namespaces,
and known activities via this module's registration API. Core scripts
query the registries at runtime to incorporate plugin-provided functionality.

Discovery: scans subdirectories of the core skill root for `extensions/`
folders containing an `__init__.py`. Each extension's __init__.py is
imported, and its top-level code should call the register_* functions.

Usage from core scripts:
    from plugin_loader import load_plugins, get_generators, get_lint_rules, ...
    load_plugins()  # call once at module level or in main()
"""

import importlib.util
import sys
import warnings
from pathlib import Path

# ---------------------------------------------------------------------------
# Plugin API version — bump when registration API signatures change
# ---------------------------------------------------------------------------

PLUGIN_API_VERSION = 2

# ---------------------------------------------------------------------------
# Registries
# ---------------------------------------------------------------------------

_generators = {}            # gen_name -> callable
_display_name_map = {}      # gen_name -> Studio display name
_ui_generators = set()      # gen names that require uix: namespace (UI activities)
_lint_rules = []            # list of (callable, name_str)
_scaffold_hooks = []        # list of callables
_extra_namespaces = {}      # prefix -> xmlns URI
_extra_known_activities = set()  # activity local names for IdRef checks
_extra_key_activities = []  # prefixed activity names for DisplayName checks
_hallucination_patterns = []    # list of (wrong_attr, correct_attr, context_hint)
_common_packages = []           # list of NuGet package ID strings
_battle_test_graders = {}       # suite_name -> callable(scenario, project_dir) -> GradeResult
_test_specs = {}                # spec_name -> spec dict (generator integration tests)
_lint_test_fixtures = []        # list of (filename, expected_substr, severity, fixture_dir)
_type_mappings = {}             # short_type -> xaml_type (e.g. "FormTaskData" -> "upaf:FormTaskData")
_variable_prefixes = {}         # xaml_type -> expected variable-name prefix (e.g. "upaf:FormTaskData" -> "fdt")
_version_profiles = {}          # (package, profile_version) -> profile dict (consumed by lints_version_compat)
_band_profile_mappings = {}     # band (e.g. "25") -> dict(package -> profile_version)
_loaded = False
_load_failures = []  # list of (skill_name, error_str) tuples


# ---------------------------------------------------------------------------
# Registration API (called by skill extensions)
# ---------------------------------------------------------------------------

def register_generator(name, fn, display_name=None, requires_ui_namespace=False):
    """Register a XAML activity generator.

    Args:
        name: JSON spec "gen" value (e.g. "create_form_task")
        fn: Generator function matching gen_* signature
        display_name: Studio display name for id_ref counting (e.g. "CreateFormTask")
        requires_ui_namespace: If True, this generator requires uix: namespace
                               (UI automation activities like SAP WinGUI)
    """
    if name in _generators:
        warnings.warn(f"[plugin_loader] Duplicate generator registration: '{name}' "
                       f"(overwriting {_generators[name].__module__}.{_generators[name].__name__})")
    _generators[name] = fn
    if display_name:
        _display_name_map[name] = display_name
    if requires_ui_namespace:
        _ui_generators.add(name)


def register_lint(fn, name=None):
    """Register a lint rule function.

    The function must accept (ctx: FileContext, result: ValidationResult).
    """
    _lint_rules.append((fn, name or fn.__name__))


def register_scaffold_hook(fn):
    """Register a scaffold post-processing hook.

    The function receives the project.json dict and can modify it in place.
    """
    _scaffold_hooks.append(fn)


def register_namespace(prefix, xmlns):
    """Register an XML namespace prefix → URI mapping for validation."""
    if prefix in _extra_namespaces and _extra_namespaces[prefix] != xmlns:
        warnings.warn(f"[plugin_loader] Duplicate namespace prefix: '{prefix}' "
                       f"(overwriting {_extra_namespaces[prefix]})")
    _extra_namespaces[prefix] = xmlns


def register_known_activities(*names):
    """Register activity local names that require IdRef attributes."""
    _extra_known_activities.update(names)


def register_key_activities(*names):
    """Register prefixed activity names that should have DisplayName."""
    _extra_key_activities.extend(names)


def register_hallucination_pattern(wrong_attr, correct_attr, context_hint):
    """Register a hallucinated-property detection pattern.

    Args:
        wrong_attr: Wrong attribute string to detect (e.g. "TaskObject=")
        correct_attr: Correct attribute name (e.g. "TaskOutput/TaskInput")
        context_hint: Activity context (e.g. "CreateFormTask/WaitForFormTask")
    """
    _hallucination_patterns.append((wrong_attr, correct_attr, context_hint))


def register_common_packages(*package_ids):
    """Register NuGet package IDs for resolve_nuget --all resolution."""
    _common_packages.extend(package_ids)


def register_battle_test_grader(suite_name, grader_fn):
    """Register a battle test grading function for a suite (e.g. 'ac').

    The grader_fn must accept (scenario: int, project_dir: Path) -> GradeResult.
    """
    _battle_test_graders[suite_name] = grader_fn


def register_test_spec(name, spec):
    """Register a generator integration test spec.

    Args:
        name: Spec name (e.g. "tasks_form_task")
        spec: Dict with class_name, arguments, variables, activities
    """
    _test_specs[name] = spec


def register_lint_test_fixture(filename, expected_substr, severity, fixture_dir):
    """Register a lint test fixture file provided by this plugin.

    Args:
        filename: XAML fixture filename (e.g. "bad_persistence_subworkflow.xaml")
        expected_substr: Expected substring in lint output (e.g. "AC-26")
        severity: Expected severity (e.g. "ERROR")
        fixture_dir: Absolute path to the directory containing the fixture file
    """
    _lint_test_fixtures.append((filename, expected_substr, severity, str(fixture_dir)))


def register_type_mapping(short_type, xaml_type):
    """Register a short type name → XAML type mapping for variable/argument declarations.

    Allows plugin types to use short names in JSON specs (e.g. "FormTaskData")
    that get resolved to prefixed XAML types (e.g. "upaf:FormTaskData").

    Args:
        short_type: Short type name used in JSON specs (e.g. "FormTaskData")
        xaml_type: Full XAML type with namespace prefix (e.g. "upaf:FormTaskData")
    """
    _type_mappings[short_type] = xaml_type


def register_version_profile(package, profile_version, profile):
    """Register a per-version activity profile for a NuGet package.

    Profiles describe each activity's expected Version attribute, properties,
    and xaml_template. lint_version_band_mismatch (lint 122) loads them via
    get_version_profiles() and merges them with on-disk profiles under
    references/version-profiles/. Plugin-registered profiles win over disk
    entries with the same (package, profile_version) key.

    Args:
        package: NuGet package ID (e.g. "UiPath.Persistence.Activities").
        profile_version: Profile-file version string (e.g. "1.4"); this is
                         the *profile* version, not necessarily the package
                         version installed in a project.
        profile: Profile dict, same shape as
                 references/version-profiles/<pkg>/<ver>.json.
    """
    _version_profiles[(package, profile_version)] = profile


def register_band_profile_mapping(band, package, profile_version):
    """Map a (band, package) pair to a profile_version for lint 122.

    A project on band "25" with UiPath.Persistence.Activities installed needs
    to know which Persistence profile to validate against. Plugins call this
    once per (band, package) pair; the lint reads the merged map at runtime.

    Args:
        band: Band string (e.g. "25", "26").
        package: NuGet package ID.
        profile_version: Profile-file version registered via
                         register_version_profile.
    """
    _band_profile_mappings.setdefault(band, {})[package] = profile_version


def register_variable_prefix(xaml_type, prefix):
    """Register an expected variable-name prefix for a plugin XAML type.

    The variable-naming lint rule (`lint_naming_conventions`, rule 16) checks
    that each declared variable starts with a recognised type prefix (str,
    int, dt_, list_, etc.). Plugin types like `upaf:FormTaskData` aren't in
    the core prefix table — registering one here teaches the rule that
    variables of that type should start with the given prefix, and widens
    the fallback prefix list so other variables are still accepted.

    Args:
        xaml_type: Full XAML type with namespace prefix, matching the value
                   emitted in `<Variable x:TypeArguments="...">`
                   (e.g. "upaf:FormTaskData", "scg:List(upaf:FormTaskData)")
        prefix: Expected variable-name prefix string (e.g. "fdt", "edt").
                Case-sensitive substring used with `startswith`.
    """
    _variable_prefixes[xaml_type] = prefix


# ---------------------------------------------------------------------------
# Query API (called by core scripts)
# ---------------------------------------------------------------------------

def get_generators():
    """Return dict of gen_name -> callable for all plugin generators."""
    return dict(_generators)


def get_display_name_map():
    """Return dict of gen_name -> Studio display name for plugin generators."""
    return dict(_display_name_map)


def get_lint_rules():
    """Return list of (callable, name) tuples for all plugin lint rules."""
    return list(_lint_rules)


def get_scaffold_hooks():
    """Return list of callables for scaffold post-processing."""
    return list(_scaffold_hooks)


def get_extra_namespaces():
    """Return dict of prefix -> xmlns URI for plugin-registered namespaces."""
    return dict(_extra_namespaces)


def get_extra_known_activities():
    """Return set of activity local names that require IdRef."""
    return set(_extra_known_activities)


def get_extra_key_activities():
    """Return list of prefixed activity names that need DisplayName."""
    return list(_extra_key_activities)


def get_ui_generators():
    """Return set of gen names that require uix: namespace (UI activities)."""
    return set(_ui_generators)


def get_hallucination_patterns():
    """Return list of (wrong_attr, correct_attr, context_hint) from plugins."""
    return list(_hallucination_patterns)


def get_common_packages():
    """Return list of NuGet package ID strings from plugins."""
    return list(_common_packages)


def get_battle_test_graders():
    """Return dict of suite_name -> grader callable from plugins."""
    return dict(_battle_test_graders)


def get_test_specs():
    """Return dict of spec_name -> spec dict from plugins."""
    return dict(_test_specs)


def get_lint_test_fixtures():
    """Return list of (filename, expected_substr, severity, fixture_dir) from plugins."""
    return list(_lint_test_fixtures)


def get_type_mappings():
    """Return dict of short_type -> xaml_type from plugins."""
    return dict(_type_mappings)


def get_variable_prefixes():
    """Return dict of xaml_type -> variable-name prefix from plugins."""
    return dict(_variable_prefixes)


def get_version_profiles():
    """Return dict of (package, profile_version) -> profile from plugins."""
    return dict(_version_profiles)


def get_band_profile_mappings():
    """Return dict of band -> dict(package -> profile_version) from plugins."""
    return {b: dict(pkgs) for b, pkgs in _band_profile_mappings.items()}


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def get_load_failures():
    """Return list of (skill_name, error_str) for plugins that failed to load.

    Call after load_plugins() to check if any extensions had errors.
    Returns an empty list if all plugins loaded successfully.
    """
    return list(_load_failures)


def load_plugins():
    """Discover and load skill extensions from subdirectories of core root.

    Scans <core_root>/**/extensions/__init__.py. Each extension is imported
    under a unique module name to avoid collisions between skills.

    Safe to call multiple times — only loads once.

    Returns:
        list of (skill_name, error_str) for any plugins that failed to load.
        Empty list means all plugins loaded successfully.
    """
    global _loaded
    if _loaded:
        return list(_load_failures)
    _loaded = True

    core_root = Path(__file__).resolve().parent.parent  # uipath-core-alpha/

    # Ensure core scripts/ is on sys.path so extensions can import helpers
    scripts_dir = str(core_root / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    # Scan sibling directories at the same level as uipath-core-alpha.
    # Skills like uipath-tasks live alongside core in the parent
    # directory (e.g. uipath-ai-skills/uipath-tasks/).
    skill_root = core_root.parent  # e.g. uipath-ai-skills/

    for child in sorted(skill_root.iterdir()):
        if not child.is_dir():
            continue
        ext_init = child / "extensions" / "__init__.py"
        if not ext_init.exists():
            continue

        # Sanitize module name — replace all non-identifier chars
        sanitized = child.name.replace('-', '_').replace(' ', '_').replace('.', '_')
        pkg_name = f"_skill_ext_{sanitized}"
        if pkg_name in sys.modules:
            continue

        # Load the extensions/ dir as a proper Python package.
        # This enables relative imports (.generators, .lint_rules, etc.)
        # without polluting sys.path — each plugin is isolated.
        ext_dir = child / "extensions"

        # Snapshot registry state so we can roll back on failure
        snap_generators = dict(_generators)
        snap_display = dict(_display_name_map)
        snap_ui_gens = set(_ui_generators)
        snap_lint = list(_lint_rules)
        snap_hooks = list(_scaffold_hooks)
        snap_ns = dict(_extra_namespaces)
        snap_known = set(_extra_known_activities)
        snap_key = list(_extra_key_activities)
        snap_hallucination = list(_hallucination_patterns)
        snap_packages = list(_common_packages)
        snap_graders = dict(_battle_test_graders)
        snap_specs = dict(_test_specs)
        snap_lint_fixtures = list(_lint_test_fixtures)
        snap_type_mappings = dict(_type_mappings)
        snap_variable_prefixes = dict(_variable_prefixes)
        snap_version_profiles = dict(_version_profiles)
        snap_band_mappings = {b: dict(pkgs) for b, pkgs in _band_profile_mappings.items()}

        def _restore_registries():
            """Roll back all registries to pre-load snapshot."""
            _generators.clear(); _generators.update(snap_generators)
            _display_name_map.clear(); _display_name_map.update(snap_display)
            _ui_generators.clear(); _ui_generators.update(snap_ui_gens)
            _lint_rules.clear(); _lint_rules.extend(snap_lint)
            _scaffold_hooks.clear(); _scaffold_hooks.extend(snap_hooks)
            _extra_namespaces.clear(); _extra_namespaces.update(snap_ns)
            _extra_known_activities.clear(); _extra_known_activities.update(snap_known)
            _extra_key_activities.clear(); _extra_key_activities.extend(snap_key)
            _hallucination_patterns.clear(); _hallucination_patterns.extend(snap_hallucination)
            _common_packages.clear(); _common_packages.extend(snap_packages)
            _battle_test_graders.clear(); _battle_test_graders.update(snap_graders)
            _test_specs.clear(); _test_specs.update(snap_specs)
            _lint_test_fixtures.clear(); _lint_test_fixtures.extend(snap_lint_fixtures)
            _type_mappings.clear(); _type_mappings.update(snap_type_mappings)
            _variable_prefixes.clear(); _variable_prefixes.update(snap_variable_prefixes)
            _version_profiles.clear(); _version_profiles.update(snap_version_profiles)
            _band_profile_mappings.clear(); _band_profile_mappings.update(snap_band_mappings)

        try:
            # Register the package first so relative imports resolve
            pkg_spec = importlib.util.spec_from_file_location(
                pkg_name, str(ext_init),
                submodule_search_locations=[str(ext_dir)]
            )
            pkg_module = importlib.util.module_from_spec(pkg_spec)
            sys.modules[pkg_name] = pkg_module  # must be in sys.modules BEFORE exec for relative imports

            # Pre-register submodules so `from .generators import X` works.
            # Scan for .py files in extensions/ and create lazy specs.
            for py_file in ext_dir.glob("*.py"):
                if py_file.name == "__init__.py":
                    continue
                sub_name = f"{pkg_name}.{py_file.stem}"
                if sub_name not in sys.modules:
                    sub_spec = importlib.util.spec_from_file_location(sub_name, str(py_file))
                    sub_module = importlib.util.module_from_spec(sub_spec)
                    sys.modules[sub_name] = sub_module
                    sub_spec.loader.exec_module(sub_module)

            # Now execute __init__.py — relative imports will find the submodules
            pkg_spec.loader.exec_module(pkg_module)

            # Check API version compatibility — mismatch is a hard failure
            required = getattr(pkg_module, "REQUIRED_API_VERSION", None)
            if required is not None and required != PLUGIN_API_VERSION:
                error_msg = (f"API version mismatch: plugin wants v{required}, "
                             f"core provides v{PLUGIN_API_VERSION}")
                _load_failures.append((child.name, error_msg))
                # Roll back module imports and registry entries
                _restore_registries()
                for key in list(sys.modules):
                    if key.startswith(pkg_name):
                        del sys.modules[key]
                print(f"[plugin_loader] ERROR: {child.name}: {error_msg}",
                      file=sys.stderr)

        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            _load_failures.append((child.name, error_msg))
            # Clean up partial registrations and registry entries
            _restore_registries()
            for key in list(sys.modules):
                if key.startswith(pkg_name):
                    del sys.modules[key]
            print(f"[plugin_loader] Warning: failed to load extension from {child.name}: {error_msg}",
                  file=sys.stderr)

    return list(_load_failures)
