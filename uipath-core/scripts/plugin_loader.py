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

PLUGIN_API_VERSION = 1

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
_version_generators = {}    # {band: {gen_name: callable}} — band-specific overrides
_package_dependencies = set()  # plugin-declared package dependencies
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


def get_version_generators(band: str) -> dict:
    """Return {gen_name: callable} for generators registered for *band*.

    Falls back to an empty dict if no overrides exist for the band.
    """
    return dict(_version_generators.get(band, {}))


def get_package_dependencies() -> set:
    """Return the set of all plugin-declared package dependencies."""
    return set(_package_dependencies)


# ---------------------------------------------------------------------------
# Plugin API v2 registration (additive — v1 plugins still work unchanged)
# ---------------------------------------------------------------------------

def register_version_generators(package: str, band: str, generators: dict):
    """Register band-specific generator overrides.

    Args:
        package: The UiPath package these generators belong to
            (e.g., "UiPath.UIAutomation.Activities").
        band: The version band (e.g., "24").
        generators: Dict of {gen_name: callable} overrides.
    """
    band_gens = _version_generators.setdefault(band, {})
    for name, fn in generators.items():
        if name in band_gens:
            warnings.warn(f"[plugin_loader] Duplicate version generator for band {band}: '{name}'")
        band_gens[name] = fn


def register_package_dependencies(*packages: str):
    """Declare UiPath package dependencies for a plugin skill.

    Called by plugins so that sync_upstream_docs.py can discover
    which upstream docs to mirror.

    Args:
        *packages: One or more UiPath package names
            (e.g., "UiPath.Persistence.Activities").
    """
    _package_dependencies.update(packages)


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
    # Skills like uipath-action-center live alongside core in the parent
    # directory (e.g. uipath-ai-skills/uipath-action-center/).
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
