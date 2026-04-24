#!/usr/bin/env python3
"""
annotate_profile_schema.py

Adds clr_namespace, source_package, namespace_match, harvestable fields to
every activity entry in each version-profile JSON.  Also adds hand-authored
xaml_template / namespace_prefix / child_elements for the 9 WF4 primitives
in UiPath.System.Activities/25.10.json, and removes CodedWorkflows /
VariablesAndScoping from that same profile.

Re-runnable: each run is idempotent — existing values are overwritten.
"""

import json
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[1]
PROFILES_DIR = REPO / "references" / "version-profiles"
GROUND_TRUTH_DIR = REPO / "references" / "studio-ground-truth"

# ---------------------------------------------------------------------------
# Ground-truth class_name lookup  (package -> version -> activity -> class)
# ---------------------------------------------------------------------------

def _load_gt_index(package: str, version: str) -> dict[str, str]:
    """Return {activity_name: class_name} from a ground-truth index.json."""
    path = GROUND_TRUTH_DIR / package / version / "index.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    result = {}
    for name, entry in data.get("activities", {}).items():
        cn = entry.get("class_name")
        if cn:
            result[name] = cn
    return result


# Pre-load all available ground-truth indexes
GT: dict[tuple[str, str], dict[str, str]] = {}
for pkg_dir in GROUND_TRUTH_DIR.iterdir():
    if not pkg_dir.is_dir():
        continue
    for ver_dir in pkg_dir.iterdir():
        if not ver_dir.is_dir():
            continue
        key = (pkg_dir.name, ver_dir.name)
        GT[key] = _load_gt_index(pkg_dir.name, ver_dir.name)


def _best_gt(package: str, profile_version: str) -> dict[str, str]:
    """
    Return the best ground-truth class_name map for a profile.
    First try exact version match; fall back to any version of the same package.
    """
    exact = GT.get((package, profile_version), {})
    if exact:
        return exact
    # Collect all versions for this package and pick the one whose version
    # string starts with the same major.minor prefix.
    prefix = ".".join(profile_version.split(".")[:2])
    candidates = {k: v for k, v in GT.items() if k[0] == package}
    for (pkg, ver), mapping in candidates.items():
        if ver.startswith(prefix):
            return mapping
    # Return whatever we have (first match)
    for (pkg, ver), mapping in candidates.items():
        return mapping
    return {}


# ---------------------------------------------------------------------------
# WF4 hand-authored XAML templates
# Namespace conventions taken from InvokeCode.xaml / LogMessage.xaml:
#   xmlns:sa="clr-namespace:System.Activities.Statements;assembly=System.Activities"
# ---------------------------------------------------------------------------

WF4_TEMPLATES = {
    "Assign": {
        "namespace_prefix": "sa",
        "child_elements": ["To", "Value"],
        "xaml_template": (
            '<sa:Assign DisplayName="Assign">\n\n'
            '  <sa:Assign.To>\n\n'
            '    <OutArgument x:TypeArguments="x:Object" />\n\n'
            '  </sa:Assign.To>\n\n'
            '  <sa:Assign.Value>\n\n'
            '    <InArgument x:TypeArguments="x:Object" />\n\n'
            '  </sa:Assign.Value>\n\n'
            '</sa:Assign>'
        ),
    },
    "Delay": {
        "namespace_prefix": "sa",
        "child_elements": [],
        "xaml_template": '<sa:Delay DisplayName="Delay" Duration="[TimeSpan.FromSeconds(1)]" />',
    },
    "If": {
        "namespace_prefix": "sa",
        "child_elements": ["Then", "Else"],
        "xaml_template": (
            '<sa:If DisplayName="If" Condition="[True]">\n\n'
            '  <sa:If.Then>\n\n'
            '    <Sequence DisplayName="Then" />\n\n'
            '  </sa:If.Then>\n\n'
            '  <sa:If.Else>\n\n'
            '    <Sequence DisplayName="Else" />\n\n'
            '  </sa:If.Else>\n\n'
            '</sa:If>'
        ),
    },
    "Throw": {
        "namespace_prefix": "sa",
        "child_elements": [],
        "xaml_template": (
            '<sa:Throw DisplayName="Throw"'
            ' Exception="[New Exception(&quot;message&quot;)]" />'
        ),
    },
    "TryCatch": {
        "namespace_prefix": "sa",
        "child_elements": ["Try", "Catches", "Finally"],
        "xaml_template": (
            '<sa:TryCatch DisplayName="Try Catch">\n\n'
            '  <sa:TryCatch.Try>\n\n'
            '    <Sequence DisplayName="Try" />\n\n'
            '  </sa:TryCatch.Try>\n\n'
            '  <sa:TryCatch.Catches>\n\n'
            '    <sa:Catch x:TypeArguments="x:Exception">\n\n'
            '      <sa:Catch.Action>\n\n'
            '        <ActivityAction x:TypeArguments="x:Exception">\n\n'
            '          <ActivityAction.Argument>\n\n'
            '            <DelegateInArgument x:TypeArguments="x:Exception" Name="exception" />\n\n'
            '          </ActivityAction.Argument>\n\n'
            '          <Sequence DisplayName="Catch" />\n\n'
            '        </ActivityAction>\n\n'
            '      </sa:Catch.Action>\n\n'
            '    </sa:Catch>\n\n'
            '  </sa:TryCatch.Catches>\n\n'
            '  <sa:TryCatch.Finally>\n\n'
            '    <Sequence DisplayName="Finally" />\n\n'
            '  </sa:TryCatch.Finally>\n\n'
            '</sa:TryCatch>'
        ),
    },
    "DoWhile": {
        "namespace_prefix": "sa",
        "child_elements": ["Body"],
        "xaml_template": (
            '<sa:DoWhile DisplayName="Do While" Condition="[False]">\n\n'
            '  <sa:DoWhile.Body>\n\n'
            '    <Sequence DisplayName="Body" />\n\n'
            '  </sa:DoWhile.Body>\n\n'
            '</sa:DoWhile>'
        ),
    },
    "ForEach": {
        "namespace_prefix": "sa",
        "child_elements": ["Body"],
        "xaml_template": (
            '<sa:ForEach x:TypeArguments="x:Object" DisplayName="For Each">\n\n'
            '  <sa:ForEach.Body>\n\n'
            '    <ActivityAction x:TypeArguments="x:Object">\n\n'
            '      <ActivityAction.Argument>\n\n'
            '        <DelegateInArgument x:TypeArguments="x:Object" Name="item" />\n\n'
            '      </ActivityAction.Argument>\n\n'
            '      <Sequence DisplayName="Body" />\n\n'
            '    </ActivityAction>\n\n'
            '  </sa:ForEach.Body>\n\n'
            '</sa:ForEach>'
        ),
    },
    "Switch": {
        "namespace_prefix": "sa",
        "child_elements": ["Cases", "Default"],
        "xaml_template": (
            '<sa:Switch x:TypeArguments="x:Int32" DisplayName="Switch">\n\n'
            '  <sa:Switch.Cases>\n\n'
            '  </sa:Switch.Cases>\n\n'
            '  <sa:Switch.Default>\n\n'
            '    <Sequence DisplayName="Default" />\n\n'
            '  </sa:Switch.Default>\n\n'
            '</sa:Switch>'
        ),
    },
    "While": {
        "namespace_prefix": "sa",
        "child_elements": ["Body"],
        "xaml_template": (
            '<sa:While DisplayName="While" Condition="[True]">\n\n'
            '  <sa:While.Body>\n\n'
            '    <Sequence DisplayName="Body" />\n\n'
            '  </sa:While.Body>\n\n'
            '</sa:While>'
        ),
    },
}

# WF4 class names (Bucket A + B2)
WF4_CLASS_NAMES = {
    "Assign": "System.Activities.Statements.Assign",
    "Delay": "System.Activities.Statements.Delay",
    "DoWhile": "System.Activities.Statements.DoWhile",
    "ForEach": "System.Activities.Statements.ForEach`1",
    "If": "System.Activities.Statements.If",
    "Switch": "System.Activities.Statements.Switch`1",
    "Throw": "System.Activities.Statements.Throw",
    "TryCatch": "System.Activities.Statements.TryCatch",
    "While": "System.Activities.Statements.While",
}

# Keys to remove from System.Activities profile (Bucket B1)
SYSTEM_ACTIVITIES_REMOVE = {"CodedWorkflows", "VariablesAndScoping"}


# ---------------------------------------------------------------------------
# Core annotation logic
# ---------------------------------------------------------------------------

def _clr_namespace(class_name: str) -> str:
    """Extract CLR namespace from a fully-qualified class name (rsplit last dot)."""
    parts = class_name.rsplit(".", 1)
    return parts[0] if len(parts) == 2 else class_name


def _namespace_match(clr_ns: str, source_package: str) -> bool:
    """
    True when the root namespace token of clr_ns matches the root of source_package.
    E.g. clr_ns='UiPath.Core.Activities' vs source_package='UiPath.System.Activities'
    -> root token 'UiPath' matches, but second token 'Core' != 'System' => False
    Actually use: first two dot-segments must match.
    Special case: UiPath.WebAPI.Activities package / UiPath.Web.Activities CLR -> False.
    """
    def _root(s: str) -> str:
        return ".".join(s.split(".")[:2])

    return _root(clr_ns) == _root(source_package)


def _harvestable(class_name: str) -> bool:
    return not class_name.startswith("System.Activities.")


def annotate_profile(profile_path: pathlib.Path) -> int:
    """Annotate one profile JSON in-place. Returns count of activities annotated."""
    data = json.loads(profile_path.read_text(encoding="utf-8"))
    package = profile_path.parent.name        # e.g. UiPath.System.Activities
    version = profile_path.stem               # e.g. 25.10
    activities = data.get("activities", {})

    gt_map = _best_gt(package, version)

    # --- Remove concept entries (Bucket B1) for System.Activities ---
    if package == "UiPath.System.Activities":
        for key in SYSTEM_ACTIVITIES_REMOVE:
            activities.pop(key, None)

    count = 0
    for name, entry in activities.items():
        # Determine class_name: from ground-truth first, then WF4 lookup, then existing
        class_name = gt_map.get(name) or WF4_CLASS_NAMES.get(name) or entry.get("class_name")

        if class_name:
            entry["class_name"] = class_name
            ns = _clr_namespace(class_name)
            entry["clr_namespace"] = ns
            entry["source_package"] = package
            entry["namespace_match"] = _namespace_match(ns, package)
            entry["harvestable"] = _harvestable(class_name)
        else:
            # No class_name available — conservative defaults
            entry.setdefault("clr_namespace", None)
            entry["source_package"] = package
            entry.setdefault("namespace_match", None)
            entry["harvestable"] = True

        # WF4: inject XAML template fields (only if not already set by backfill)
        if name in WF4_TEMPLATES and package == "UiPath.System.Activities":
            tpl = WF4_TEMPLATES[name]
            entry.setdefault("namespace_prefix", tpl["namespace_prefix"])
            entry.setdefault("child_elements", tpl["child_elements"])
            entry.setdefault("xaml_template", tpl["xaml_template"])
            # Override with authoritative values regardless
            entry["namespace_prefix"] = tpl["namespace_prefix"]
            entry["child_elements"] = tpl["child_elements"]
            entry["xaml_template"] = tpl["xaml_template"]

        count += 1

    data["activities"] = activities
    profile_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return count


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    total_activities = 0
    total_harvestable_false = 0
    total_ns_mismatch = 0

    for profile_json in sorted(PROFILES_DIR.rglob("*.json")):
        n = annotate_profile(profile_json)
        total_activities += n
        # Re-read to count
        data = json.loads(profile_json.read_text(encoding="utf-8"))
        for entry in data.get("activities", {}).values():
            if entry.get("harvestable") is False:
                total_harvestable_false += 1
            if entry.get("namespace_match") is False:
                total_ns_mismatch += 1
        print(f"  annotated {n:3d} activities in {profile_json.relative_to(PROFILES_DIR)}")

    print()
    print(f"Total activities annotated : {total_activities}")
    print(f"harvestable=false          : {total_harvestable_false}")
    print(f"namespace_match=false      : {total_ns_mismatch}")


if __name__ == "__main__":
    main()
