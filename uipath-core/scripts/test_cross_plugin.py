#!/usr/bin/env python3
"""Cross-plugin interaction test.

Tests that plugin-provided generators (Tasks) produce XAML that
passes both core lint rules and plugin-specific lint rules. Also verifies
that plugin registration doesn't break core functionality.

Usage:
    python3 scripts/test_cross_plugin.py
    python3 scripts/test_cross_plugin.py --verbose
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPTS_DIR.parent
GENERATOR = SCRIPTS_DIR / "generate_workflow.py"
VALIDATOR = SCRIPTS_DIR / "validate_xaml"
SCAFFOLD = SCRIPTS_DIR / "scaffold_project.py"

# SAP-WinGUI plugin lives only on `feature/sap-wingui-skill` and has never been
# merged to `main` or `feature/version-compatibility-v2`. Gate SAP-specific
# assertions on plugin presence (mirrors the pattern in test_plugin_version_profiles.py).
SAP_PLUGIN_DIR = SKILL_DIR.parent / "uipath-sap-wingui" / "extensions"
SAP_AVAILABLE = SAP_PLUGIN_DIR.exists()


class TestResult:
    def __init__(self, name: str):
        self.name = name
        self.passed = True
        self.messages = []

    def fail(self, msg: str):
        self.passed = False
        self.messages.append(f"FAIL: {msg}")

    def ok(self, msg: str):
        self.messages.append(f"  OK: {msg}")

    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        header = f"{'='*60}\n{status}  {self.name}\n{'='*60}"
        body = "\n".join(f"  {m}" for m in self.messages)
        return f"{header}\n{body}" if self.messages else header


def test_plugin_loader_integrity() -> TestResult:
    """Verify plugin_loader discovers and registers all expected extensions."""
    t = TestResult("Plugin loader integrity — all registries populated")

    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        # Force reload to get fresh state
        import importlib
        import plugin_loader
        importlib.reload(plugin_loader)

        # Reset state for clean test
        plugin_loader._loaded = False
        plugin_loader._generators.clear()
        plugin_loader._lint_rules.clear()
        plugin_loader._scaffold_hooks.clear()
        plugin_loader._extra_namespaces.clear()
        plugin_loader._extra_known_activities.clear()
        plugin_loader._extra_key_activities.clear()
        plugin_loader._load_failures.clear()
        plugin_loader._hallucination_patterns.clear()
        plugin_loader._common_packages.clear()
        plugin_loader._battle_test_graders.clear()
        plugin_loader._test_specs.clear()
        plugin_loader._lint_test_fixtures.clear()

        failures = plugin_loader.load_plugins()

        if failures:
            for name, err in failures:
                t.fail(f"Plugin '{name}' failed to load: {err}")
            return t
        t.ok("All plugins loaded without errors")

        # Check Tasks registrations
        gens = plugin_loader.get_generators()
        if "create_form_task" in gens:
            t.ok("Generator 'create_form_task' registered")
        else:
            t.fail("Generator 'create_form_task' not registered")

        if "wait_for_form_task" in gens:
            t.ok("Generator 'wait_for_form_task' registered")
        else:
            t.fail("Generator 'wait_for_form_task' not registered")

        lint_rules = plugin_loader.get_lint_rules()
        lint_names = [name for _, name in lint_rules]
        if any("tasks" in n for n in lint_names):
            t.ok(f"Tasks lint rule registered ({len(lint_rules)} total plugin lint rules)")
        else:
            t.fail(f"No Tasks lint rules found. Registered: {lint_names}")

        hooks = plugin_loader.get_scaffold_hooks()
        if hooks:
            t.ok(f"{len(hooks)} scaffold hook(s) registered")
        else:
            t.fail("No scaffold hooks registered (expected persistence support hook)")

        ns = plugin_loader.get_extra_namespaces()
        if "upaf" in ns:
            t.ok(f"Namespace 'upaf' registered: {ns['upaf']}")
        else:
            t.fail(f"Namespace 'upaf' not registered. Found: {list(ns.keys())}")

        activities = plugin_loader.get_extra_known_activities()
        for act in ("CreateFormTask", "WaitForFormTaskAndResume"):
            if act in activities:
                t.ok(f"Known activity '{act}' registered")
            else:
                t.fail(f"Known activity '{act}' not registered")

    except Exception as e:
        t.fail(f"Plugin loader error: {type(e).__name__}: {e}")

    return t


def test_plugin_generators_produce_valid_xml() -> TestResult:
    """Plugin generators produce structurally valid XML fragments."""
    t = TestResult("Plugin generators — valid XML output")

    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        from plugin_loader import load_plugins, get_generators
        load_plugins()
        gens = get_generators()

        gen_create = gens.get("create_form_task")
        gen_wait = gens.get("wait_for_form_task")
        if not gen_create or not gen_wait:
            t.fail("Plugin generators not available")
            return t

        # Generate CreateFormTask XAML
        create_xml = gen_create(
            task_title_expr='"Approval Request"',
            task_output_variable="taskObject",
            form_layout_json='{"components":[{"type":"textfield","key":"name","label":"Name"},{"type":"button","action":"submit","label":"Submit"}]}',
            id_ref="CreateFormTask_1",
        )
        if "<upaf:CreateFormTask" in create_xml:
            t.ok("CreateFormTask generator produces upaf:CreateFormTask element")
        else:
            t.fail(f"CreateFormTask output missing expected element. Got: {create_xml[:200]}")

        # Generate WaitForFormTask XAML
        wait_xml = gen_wait(
            task_input_variable="taskObject",
            id_ref="WaitForFormTaskAndResume_1",
        )
        if "<upaf:WaitForFormTaskAndResume" in wait_xml:
            t.ok("WaitForFormTask generator produces upaf:WaitForFormTaskAndResume element")
        else:
            t.fail(f"WaitForFormTask output missing expected element. Got: {wait_xml[:200]}")

        # Check XML wellformedness of fragments
        import xml.etree.ElementTree as ET
        for name, xml_str in [("CreateFormTask", create_xml), ("WaitForFormTask", wait_xml)]:
            try:
                # Fragments need a wrapper to be valid XML
                wrapped = f'<root xmlns:upaf="urn:test" xmlns:sap2010="urn:test2" xmlns:sap="urn:test3" xmlns:scg="urn:test4" xmlns:x="urn:test5">{xml_str}</root>'
                ET.fromstring(wrapped)
                t.ok(f"{name} output is well-formed XML")
            except ET.ParseError as e:
                t.fail(f"{name} output has XML parse error: {e}")

    except Exception as e:
        t.fail(f"Error testing plugin generators: {type(e).__name__}: {e}")

    return t


def test_core_generators_unaffected_by_plugins() -> TestResult:
    """Loading plugins doesn't break core generator imports or functionality."""
    t = TestResult("Core generators unaffected by plugin loading")

    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        from plugin_loader import load_plugins
        load_plugins()

        # Import core generators AFTER plugin loading
        from generate_activities import (
            gen_ntypeinto, gen_nclick, gen_logmessage, gen_throw,
            gen_assign, gen_try_catch, gen_if
        )

        # Quick smoke test on core generators
        log_xml = gen_logmessage('"Test"', "LogMessage_1", level="Info")
        if "<ui:LogMessage" in log_xml:
            t.ok("gen_logmessage works after plugin loading")
        else:
            t.fail("gen_logmessage output unexpected after plugin loading")

        click_xml = gen_nclick("Click Test", "<webctrl tag='A' />", "NClick_1", "scope-123")
        if "<uix:NClick" in click_xml:
            t.ok("gen_nclick works after plugin loading")
        else:
            t.fail("gen_nclick output unexpected after plugin loading")

        assign_xml = gen_assign(to_variable="strTest", value_expression='"Hello"', id_ref="Assign_1")
        if "<Assign" in assign_xml:
            t.ok("gen_assign works after plugin loading")
        else:
            t.fail("gen_assign output unexpected after plugin loading")

    except Exception as e:
        t.fail(f"Core generator error after plugin loading: {type(e).__name__}: {e}")

    return t


def test_scaffold_with_persistence(tmpdir: str) -> TestResult:
    """Scaffold hook correctly sets supportsPersistence when AC deps present."""
    t = TestResult("Scaffold + AC persistence hook")

    out_dir = os.path.join(tmpdir, "TestACProject")
    cmd = [
        sys.executable, str(SCAFFOLD),
        "--name", "TestACProject",
        "--variant", "performer",
        "--output", out_dir,
        "--deps", "UiPath.Persistence.Activities:[3.0.3],UiPath.FormActivityLibrary:[1.0.0]",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        t.fail(f"Scaffold failed: {proc.stderr.strip()}")
        return t
    t.ok("Scaffold completed")

    # Check project.json for supportsPersistence
    pj_path = os.path.join(out_dir, "TestACProject", "project.json")
    if not os.path.exists(pj_path):
        pj_path = os.path.join(out_dir, "project.json")
    if not os.path.exists(pj_path):
        t.fail(f"project.json not found in scaffolded output")
        return t

    with open(pj_path, "r", encoding="utf-8") as f:
        pj = json.load(f)

    runtime_opts = pj.get("runtimeOptions", {})
    if runtime_opts.get("supportsPersistence") is True:
        t.ok("supportsPersistence = true (set by AC scaffold hook)")
    else:
        t.fail(f"supportsPersistence not set. runtimeOptions: {runtime_opts}")

    # Validate the scaffolded project
    rc_proc = subprocess.run(
        [sys.executable, str(VALIDATOR), os.path.dirname(pj_path), "--lint"],
        capture_output=True, text=True
    )
    errors = sum(1 for line in rc_proc.stdout.splitlines() if "[ERROR]" in line)
    if errors == 0:
        t.ok("Scaffolded AC project passes lint")
    else:
        t.fail(f"{errors} lint errors in scaffolded AC project")
        for line in rc_proc.stdout.splitlines():
            if "[ERROR]" in line:
                t.messages.append(f"       {line.strip()}")

    return t


def test_sap_plugin_integrity() -> TestResult:
    """Verify SAP WinGUI plugin registers generators, lints, and namespaces."""
    if not SAP_AVAILABLE:
        t = TestResult("SAP WinGUI plugin integrity — SKIPPED (uipath-sap-wingui not on this branch)")
        t.ok("Skipped — SAP plugin source not present at uipath-sap-wingui/extensions")
        return t

    t = TestResult("SAP WinGUI plugin integrity — registries populated")

    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        from plugin_loader import load_plugins, get_generators, get_lint_rules, get_extra_namespaces, get_extra_known_activities
        load_plugins()

        # Check SAP generators
        gens = get_generators()
        expected_sap_gens = [
            "sap_logon", "sap_login", "sap_call_transaction",
            "sap_click_toolbar", "sap_select_menu_item",
            "sap_read_statusbar", "sap_table_cell_scope",
        ]
        for gen_name in expected_sap_gens:
            if gen_name in gens:
                t.ok(f"Generator '{gen_name}' registered")
            else:
                t.fail(f"Generator '{gen_name}' not registered")

        # Convenience helpers should NOT be registered (tuple return / Python-only)
        for helper in ("sap_status_bar_check", "sap_type_into_cell"):
            if helper in gens:
                t.fail(f"Helper '{helper}' should NOT be registered as a generator")
            else:
                t.ok(f"Helper '{helper}' correctly not registered")

        # Check SAP lint rule
        lint_rules = get_lint_rules()
        lint_names = [name for _, name in lint_rules]
        if any("sap" in n.lower() for n in lint_names):
            t.ok(f"SAP lint rule registered")
        else:
            t.fail(f"No SAP lint rules found. Registered: {lint_names}")

        # Check ucas namespace (SAP-specific)
        ns = get_extra_namespaces()
        if "ucas" in ns:
            t.ok(f"Namespace 'ucas' registered: {ns['ucas']}")
        else:
            t.fail(f"Namespace 'ucas' not registered. Found: {list(ns.keys())}")

        # Check SAP known activities
        activities = get_extra_known_activities()
        for act in ("NSAPLogon", "NSAPLogin", "NSAPCallTransaction"):
            if act in activities:
                t.ok(f"Known activity '{act}' registered")
            else:
                t.fail(f"Known activity '{act}' not registered")

    except Exception as e:
        t.fail(f"SAP plugin error: {type(e).__name__}: {e}")

    return t


def test_sap_generators_produce_valid_xml() -> TestResult:
    """SAP generators produce structurally valid XML fragments."""
    if not SAP_AVAILABLE:
        t = TestResult("SAP generators — SKIPPED (uipath-sap-wingui not on this branch)")
        t.ok("Skipped — SAP plugin source not present at uipath-sap-wingui/extensions")
        return t

    t = TestResult("SAP generators — valid XML output")

    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        from plugin_loader import load_plugins, get_generators
        load_plugins()
        gens = get_generators()

        gen_logon = gens.get("sap_logon")
        gen_login = gens.get("sap_login")
        if not gen_logon or not gen_login:
            t.fail("SAP generators not available")
            return t

        # Generate NSAPLogon XAML
        logon_xml = gen_logon(
            display_name="Test SAP Logon",
            sap_connection="strConn",
        )
        if "<uix:NSAPLogon" in logon_xml:
            t.ok("gen_sap_logon produces uix:NSAPLogon element")
        else:
            t.fail(f"gen_sap_logon output missing expected element")

        # Generate NSAPLogin XAML
        login_xml = gen_login(
            username="strUser",
            secure_password="secstrPwd",
            client="strClient",
            language="strLang",
        )
        if "<uix:NSAPLogin" in login_xml:
            t.ok("gen_sap_login produces uix:NSAPLogin element")
        else:
            t.fail(f"gen_sap_login output missing expected element")

        # Check XML wellformedness
        import xml.etree.ElementTree as ET
        for name, xml_str in [("NSAPLogin", login_xml)]:
            try:
                wrapped = (
                    f'<root xmlns:uix="urn:test" xmlns:sap2010="urn:test2" '
                    f'xmlns:sap="urn:test3" xmlns:scg="urn:test4" '
                    f'xmlns:x="urn:test5" xmlns:sd="urn:test6" '
                    f'xmlns:sd1="urn:test7">{xml_str}</root>'
                )
                ET.fromstring(wrapped)
                t.ok(f"{name} output is well-formed XML")
            except ET.ParseError as e:
                t.fail(f"{name} output has XML parse error: {e}")

    except Exception as e:
        t.fail(f"Error testing SAP generators: {type(e).__name__}: {e}")

    return t


def test_create_form_task_emits_external_file(tmpdir: str) -> TestResult:
    """CLI --project-dir reaches create_form_task → Forms/<slug>.json written."""
    t = TestResult("CreateFormTask auto-emits external form file when --project-dir is set")

    project_dir = os.path.join(tmpdir, "FormTaskExtract")
    os.makedirs(project_dir, exist_ok=True)

    # Realistic ~600-char form.io schema (above AC-33's 500-char soft limit).
    form_layout = json.dumps({
        "components": [
            {"label": "Supplier", "key": "supplier", "type": "textfield",
             "input": True, "disabled": True, "tableView": True},
            {"label": "Invoice Number", "key": "invoiceNumber", "type": "textfield",
             "input": True, "disabled": True, "tableView": True},
            {"label": "Amount (EUR)", "key": "amount", "type": "number",
             "input": True, "disabled": True, "tableView": True},
            {"label": "Decision", "key": "decision", "type": "select",
             "input": True,
             "data": {"values": [
                 {"label": "Approve", "value": "approve"},
                 {"label": "Reject", "value": "reject"},
             ]},
             "validate": {"required": True}},
            {"type": "button", "label": "Submit", "key": "submit",
             "action": "submit", "input": True, "tableView": False},
        ]
    }, separators=(",", ":"))

    spec = {
        "class_name": "Main",
        "arguments": [],
        "variables": [
            {"name": "fdtTask", "type": "FormTaskData"},
        ],
        "activities": [
            {"gen": "create_form_task", "args": {
                "task_title_expr": '"Approve Invoice"',
                "task_output_variable": "fdtTask",
                "form_layout_json": form_layout,
                "display_name": "Approve Invoice Task",
            }},
        ],
    }
    spec_path = os.path.join(project_dir, "spec.json")
    xaml_path = os.path.join(project_dir, "Main.xaml")
    with open(spec_path, "w", encoding="utf-8") as f:
        json.dump(spec, f)

    cmd = [sys.executable, str(GENERATOR), spec_path, xaml_path,
           "--project-dir", project_dir]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        t.fail(f"generate_workflow failed: {proc.stderr.strip()}")
        return t
    t.ok("generate_workflow completed with --project-dir")

    expected_form_path = os.path.join(project_dir, "Forms", "Approve_Invoice_Task.json")
    if not os.path.isfile(expected_form_path):
        forms_dir = os.path.join(project_dir, "Forms")
        existing = os.listdir(forms_dir) if os.path.isdir(forms_dir) else []
        t.fail(f"Expected sidecar file {expected_form_path} was not written. "
               f"Forms/ contents: {existing}")
        return t
    t.ok("Forms/Approve_Invoice_Task.json written to project dir")

    with open(expected_form_path, "r", encoding="utf-8") as f:
        schema = json.load(f)
    if not isinstance(schema.get("id"), str) or not schema["id"]:
        t.fail(f"External form file missing string 'id' at root: {schema}")
        return t
    if not isinstance(schema.get("form"), list) or not schema["form"]:
        t.fail(f"External form file missing 'form' array at root: {schema}")
        return t
    t.ok(f"External form file has UiPath shape (id + {len(schema['form'])} components)")

    with open(xaml_path, "r", encoding="utf-8") as f:
        xaml = f.read()
    if 'DynamicFormPath="Forms/Approve_Invoice_Task.json"' not in xaml:
        t.fail('XAML missing expected DynamicFormPath="Forms/Approve_Invoice_Task.json"')
        return t
    t.ok('XAML CreateFormTask element carries DynamicFormPath="Forms/Approve_Invoice_Task.json"')

    # Sanity: the CreateFormTask element must NOT still claim {x:Null}
    m = re.search(r'<upaf:CreateFormTask\b[^>]*?(/>|>)', xaml, flags=re.DOTALL)
    if m and 'DynamicFormPath="{x:Null}"' in m.group(0):
        t.fail("CreateFormTask element still has DynamicFormPath={x:Null}")
        return t
    t.ok("CreateFormTask no longer emits DynamicFormPath={x:Null}")

    return t


def test_create_form_task_without_project_dir_stays_inline() -> TestResult:
    """Without --project-dir, CreateFormTask keeps today's inline-form behavior."""
    t = TestResult("CreateFormTask stays inline when project_root is absent")

    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        from plugin_loader import load_plugins, get_generators
        load_plugins()
        gens = get_generators()
        gen_create = gens.get("create_form_task")
        if not gen_create:
            t.fail("create_form_task generator not registered")
            return t

        xml = gen_create(
            task_title_expr='"X"',
            task_output_variable="fdtTask",
            form_layout_json='{"components":[{"type":"textfield","key":"a","label":"A"}]}',
            id_ref="CreateFormTask_1",
            display_name="Some Task",
            # no project_root → must not try to write anything
        )
        if 'DynamicFormPath="{x:Null}"' in xml:
            t.ok("DynamicFormPath={x:Null} preserved when project_root is None")
        else:
            t.fail(f"Expected DynamicFormPath={{x:Null}} when project_root is None. Got: {xml[:300]}")

        if 'DynamicFormPath="Forms/' in xml:
            t.fail("Generator wrote a DynamicFormPath even though project_root was None")

    except Exception as e:
        t.fail(f"Error testing no-project-root path: {type(e).__name__}: {e}")

    return t


def test_plugin_load_failure_propagation() -> TestResult:
    """Plugin load failures are properly tracked and retrievable."""
    t = TestResult("Plugin load failure propagation")

    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        from plugin_loader import get_load_failures, load_plugins
        load_plugins()
        failures = get_load_failures()

        # In a healthy environment, there should be no failures
        if len(failures) == 0:
            t.ok("No plugin load failures (all extensions healthy)")
        else:
            for name, err in failures:
                t.fail(f"Plugin '{name}' has a load failure: {err}")

        # Verify the return type is correct
        if isinstance(failures, list):
            t.ok("get_load_failures() returns a list")
        else:
            t.fail(f"get_load_failures() returned {type(failures).__name__}, expected list")

    except Exception as e:
        t.fail(f"Error testing failure propagation: {type(e).__name__}: {e}")

    return t


def test_api_version_mismatch() -> TestResult:
    """A plugin declaring an incompatible REQUIRED_API_VERSION is rejected."""
    t = TestResult("API version mismatch — plugin rejected and rolled back")

    sys.path.insert(0, str(SCRIPTS_DIR))
    fake_plugin_dir = None
    try:
        import importlib
        import plugin_loader
        importlib.reload(plugin_loader)

        # Reset state for a clean test
        plugin_loader._loaded = False
        plugin_loader._generators.clear()
        plugin_loader._lint_rules.clear()
        plugin_loader._scaffold_hooks.clear()
        plugin_loader._extra_namespaces.clear()
        plugin_loader._extra_known_activities.clear()
        plugin_loader._extra_key_activities.clear()
        plugin_loader._load_failures.clear()
        plugin_loader._hallucination_patterns.clear()
        plugin_loader._common_packages.clear()
        plugin_loader._battle_test_graders.clear()
        plugin_loader._test_specs.clear()
        plugin_loader._lint_test_fixtures.clear()

        # Remove cached plugin modules so load_plugins() re-discovers them
        for key in list(sys.modules):
            if key.startswith("_skill_ext_"):
                del sys.modules[key]

        # Create a fake plugin with an incompatible API version.
        # Plugins live as siblings of uipath-core under .claude/skills/.
        skill_root = Path(__file__).resolve().parent.parent.parent  # .claude/skills/
        fake_plugin_dir = skill_root / "fake-bad-version"
        ext_dir = fake_plugin_dir / "extensions"
        ext_dir.mkdir(parents=True, exist_ok=True)

        init_content = (
            "REQUIRED_API_VERSION = 999\n"
            "\n"
            "from plugin_loader import register_generator\n"
            "\n"
            "def _fake_gen(**kwargs):\n"
            "    return '<Fake />'\n"
            "\n"
            "register_generator('fake_bad_version_gen', _fake_gen)\n"
        )
        (ext_dir / "__init__.py").write_text(init_content, encoding="utf-8")

        # Load plugins — the fake one should be discovered and rejected
        failures = plugin_loader.load_plugins()

        # 1. The fake plugin must appear in load failures with "API version"
        fake_failures = [
            (name, err) for name, err in plugin_loader.get_load_failures()
            if name == "fake-bad-version"
        ]
        if len(fake_failures) == 1 and "API version" in fake_failures[0][1]:
            t.ok(f"Fake plugin rejected: {fake_failures[0][1]}")
        else:
            t.fail(f"Expected fake-bad-version in load failures with 'API version' error. "
                   f"Got: {plugin_loader.get_load_failures()}")

        # 2. No generators from the fake plugin leaked into registries
        gens = plugin_loader.get_generators()
        if "fake_bad_version_gen" not in gens:
            t.ok("Fake generator correctly rolled back (not in registries)")
        else:
            t.fail("Fake generator 'fake_bad_version_gen' leaked into registries")

        # 3. Real plugins still loaded successfully
        if "create_form_task" in gens:
            t.ok("Tasks generator 'create_form_task' still present")
        else:
            t.fail("Tasks generator 'create_form_task' missing after mismatch test")

        if SAP_AVAILABLE:
            if "sap_logon" in gens:
                t.ok("SAP WinGUI generator 'sap_logon' still present")
            else:
                t.fail("SAP WinGUI generator 'sap_logon' missing after mismatch test")
        else:
            t.ok("SAP WinGUI presence check skipped — uipath-sap-wingui not on this branch")

    except Exception as e:
        t.fail(f"Error during API version mismatch test: {type(e).__name__}: {e}")
    finally:
        # Clean up the fake plugin directory
        if fake_plugin_dir and fake_plugin_dir.exists():
            shutil.rmtree(str(fake_plugin_dir), ignore_errors=True)

    return t


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Cross-plugin interaction test")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--tmpdir", default=None)
    args = parser.parse_args()

    tmpdir = tempfile.mkdtemp(prefix="cross_plugin_test_", dir=args.tmpdir)
    results = []

    try:
        results.append(test_plugin_loader_integrity())
        results.append(test_plugin_generators_produce_valid_xml())
        results.append(test_core_generators_unaffected_by_plugins())
        results.append(test_scaffold_with_persistence(tmpdir))
        results.append(test_create_form_task_emits_external_file(tmpdir))
        results.append(test_create_form_task_without_project_dir_stays_inline())
        results.append(test_sap_plugin_integrity())
        results.append(test_sap_generators_produce_valid_xml())
        results.append(test_plugin_load_failure_propagation())
        results.append(test_api_version_mismatch())
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    for r in results:
        if args.verbose or not r.passed:
            print(r.summary())
        else:
            status = "PASS" if r.passed else "FAIL"
            print(f"{status}  {r.name}")

    print(f"\n{'='*60}")
    print(f"CROSS-PLUGIN: {passed}/{total} passed" +
          (f", {failed} FAILED" if failed else " — all clear"))
    print(f"{'='*60}")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
