# Contributing to uipath-ai-skills

Thanks for your interest in contributing. This guide covers how to set up the project, run tests, and submit changes.

For a project overview, see the [README](./README.md).

---

## Ways to contribute

- **Bug reports** - include the Studio error message and the generated `.xaml` if possible
- **Golden XAML samples** - real UiPath Studio exports that can serve as templates or test fixtures
- **New lint rules** - especially for hallucination patterns you've seen LLMs produce
- **New activity generators** - for UiPath activities not yet covered
- **New skills** - plugin skills that extend uipath-core (e.g., Document Understanding, SAP GUI for Windows) or standalone skills for non-Studio-dev domains (e.g., architecture design, process analysis)
- **Documentation** - reference docs, expression examples, selector patterns
- **Battle test scenarios** - new PDD-style test cases in `evals/`. See `evals/core-battle-tests.md` for format and `scripts/grade_battle_test.py` for semi-automated grading

---

## Development setup

```bash
git clone https://github.com/marcelocruzrpa/uipath-ai-skills.git
cd uipath-ai-skills
```

Requirements:
- Python 3.10+
- `pip install openpyxl` (optional - only for Config.xlsx operations)
- No other dependencies - all core scripts use Python stdlib

---

## Running tests

All test commands run from the `uipath-core` directory:

```bash
cd uipath-core

# Regression suite - validates templates and scaffolded projects (18 tests)
python3 scripts/regression_test.py

# Lint tests - verifies bad XAML triggers expected lint rules (81 cases)
python3 scripts/run_lint_tests.py

# Generator snapshots - detects structural changes in generator output
python3 scripts/test_generator_snapshots.py

# Cross-plugin integration - run when changing plugin code, scaffold hooks,
# or shared plugin-loading behavior
python3 scripts/test_cross_plugin.py

# Validate any project or file
python3 scripts/validate_xaml <project_or_file> --lint
```

For all changes, run the three core suites above. If your change touches plugin
registration/loading, plugin generators/lints/hooks, or shared plugin
infrastructure, also run `python3 scripts/test_cross_plugin.py`.

---

## Adding a generator

Generators live in `uipath-core/scripts/generate_activities/`. Each function produces deterministic XAML for a specific UiPath activity.

### Steps

1. **Add the function** in the appropriate module (e.g., `data_operations.py`, `ui_automation.py`). Follow the existing pattern:

```python
def gen_my_activity(display_name, some_arg, mode, id_ref, indent="    "):
    """Generate MyActivity XAML.

    Args:
        display_name: Activity display name in Studio
        some_arg: ...
        id_ref: Unique ID for ViewState (e.g., "MyActivity_1")
        indent: Base indentation level
    """
    # Validate enums before generating
    valid_modes = ("ModeA", "ModeB")
    if mode not in valid_modes:
        raise ValueError(f"Invalid mode '{mode}'. Valid: {valid_modes}")

    dn = _escape_xml_attr(display_name)
    i = indent

    return (
        f'{i}<Activity DisplayName="{dn}" ...>\n'
        f'{i}</Activity>\n'
    )
```

2. **Register** in `generate_activities/__init__.py`:
   - Add the import
   - Add to `__all__`
   - Add to `UI_GENERATORS` if it requires the `uix:` namespace

3. **Add a snapshot fixture** in `assets/generator-snapshots/`:
   - Write a minimal JSON spec that exercises the new generator
   - Run `python3 scripts/generate_workflow.py spec.json output.xaml` to produce the expected XAML
   - Copy the output to `assets/generator-snapshots/<generator_name>.xaml`
   - The snapshot test will compare future generator output against this fixture

4. **Run tests**:
   ```bash
   python3 scripts/test_generator_snapshots.py
   python3 scripts/regression_test.py
   ```

### Conventions

- Use `_escape_xml_attr()` for display names and string attributes
- Use `_hs(activity_name)` for `VirtualizedContainerService.HintSize`
- Use `_uuid()` for GUIDs (never hardcode)
- Validate enum values before generating XAML - raise `ValueError` for invalid inputs
- Pass `indent` as a parameter, increment per nesting level (`indent + "  "`)
- Document what hallucination patterns the generator prevents

---

## Adding a lint rule

Lint rules live in `uipath-core/scripts/validate_xaml/lints_*.py`. Each rule detects a specific error pattern in generated XAML.

### Steps

1. **Add the function** in the appropriate module:

```python
@lint_rule(99)  # Use the next available number (find it: rg "@lint_rule" scripts/validate_xaml/)
def lint_my_check(ctx, result):
    """Describe what this rule catches and why."""
    content = ctx.active_content

    if "SomePattern" not in content:
        return  # Early exit if not relevant

    # Check for the issue
    if bad_condition:
        result.error("Lint 99: Description of the problem. Fix: ...")
```

2. **Add a test case** in `assets/lint-test-cases/`:
   - Create a minimal `.xaml` file that triggers the rule
   - Add the expected assertion to `scripts/run_lint_tests.py`
   - Update the appropriate test list there (`TESTS`, `FILENAME_SENSITIVE_TESTS`,
     `PROJECT_TESTS`, or `PLUGIN_TESTS`) based on how the rule is exercised

3. **Run lint tests**:
   ```bash
   python3 scripts/run_lint_tests.py
   ```

4. **Document** the rule in `references/lint-reference.md`

Rules can optionally implement auto-fix. To test: `python3 scripts/validate_xaml <file> --lint --fix`

### Severity guidelines

- **ERROR** - Studio crash or compile failure (hallucinated enums, missing xmlns, wrong child elements)
- **WARN** - Runtime failure or silent data loss (type mismatches, empty bindings, wrong namespace prefix)
- **INFO** - Best practice violation (hardcoded URLs, missing log bookends, credentials as arguments)

---

## Creating a new skill

There are two skill types. Choose based on what the skill does:

### A) Plugin skill (UiPath Studio development)

Use this when the skill generates XAML, adds lint rules, or modifies scaffolded projects. All UiPath Studio dev skills should extend uipath-core. See `uipath-tasks` and `uipath-sap-wingui` for reference.

**Directory structure:**

```
uipath-my-plugin/
|-- SKILL.md                    # Routing table (YAML frontmatter + instructions)
|-- extensions/
|   |-- __init__.py             # Registration (required)
|   |-- generators.py           # Custom activity generators
|   |-- lint_rules.py           # Custom lint rules
|   \-- scaffold_hooks.py       # Post-scaffold modifications (optional)
|-- references/                 # Domain-specific docs
\-- evals/                      # Battle test scenarios
```

**Registration (`extensions/__init__.py`):**

```python
from .generators import gen_my_activity
from .lint_rules import lint_my_rules

# Top-level registration calls (executed on import)
# plugin_loader.py auto-discovers plugins by importing this module -
# all registration happens via the register_* calls below.
from plugin_loader import (
    register_generator,
    register_lint,
    register_scaffold_hook,
    register_namespace,
    register_known_activities,
    register_key_activities,
)

register_generator("my_activity", gen_my_activity, display_name="MyActivity")
register_lint(lint_my_rules, "lint_my_rules")
register_namespace("mypfx", "clr-namespace:My.Namespace;assembly=My.Assembly")
register_known_activities("MyActivity")
register_key_activities("mypfx:MyActivity")
```

The core auto-discovers plugins in sibling directories that contain `extensions/__init__.py`.

### B) Standalone skill (non-Studio-dev)

Use this when the skill provides guidance, analysis, or tooling that doesn't produce or validate XAML. Examples: architecture design, process analysis, compliance review.

**Directory structure:**

```
uipath-my-skill/
|-- SKILL.md                    # Routing table, ground rules, reference file index
|-- references/                 # Domain-specific docs
|-- scripts/                    # Skill-specific tooling (optional)
\-- evals/                      # Battle test scenarios (optional)
```

No `extensions/` directory needed. The skill is fully self-contained — `SKILL.md` is the entry point that routes the AI to the right reference docs and scripts.

---

## Code style

- **Python 3.10+**, stdlib only for core scripts
- **PEP 8** - 4-space indents, snake_case functions, UPPER_CASE constants
- **f-strings** for string formatting
- **pathlib** for file paths (`Path` over `os.path`)
- **Early returns** and guard clauses over deep nesting
- **No external linter config** - follow existing patterns in the codebase
- **Naming**: `_private_function()`, `PUBLIC_CONSTANT`, `local_variable`
- **XAML generators**: Use multiline f-strings with explicit `indent` parameter for nesting. Pass `indent + "  "` for each child level
- **Lint messages**: Follow the format `"Lint NN: Description. Fix: ..."` where NN matches the `@lint_rule()` number
- **ViewState**: Always generate `VirtualizedContainerService.HintSize` via `_hs()` helper - never hardcode pixel values

---

## Pull request process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-change`)
3. Make your changes
4. Run the required test suites:
   ```bash
   # Core suites (run for all changes)
   python3 scripts/regression_test.py
   python3 scripts/run_lint_tests.py
   python3 scripts/test_generator_snapshots.py

   # Also run when changing plugin code, scaffold hooks, or plugin loading
   python3 scripts/test_cross_plugin.py
   ```
5. If you modified generators, update snapshot fixtures: `python3 scripts/test_generator_snapshots.py --update`
6. Submit a pull request with a clear description of what changed and why

---

## Ground rules

The skill enforces strict rules about how XAML is generated. Before contributing, familiarize yourself with:

- **G-1**: XAML files are created ONLY via `generate_workflow.py` - never hand-written
- **G-8**: Never use Edit/Write tools on `.xaml` files - all modifications go through scripts
- **G-5**: Never guess NuGet versions - use `resolve_nuget.py`

Full rule definitions with rationale: [`references/rules.md`](./uipath-core/references/rules.md)
