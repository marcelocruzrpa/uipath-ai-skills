#!/usr/bin/env python3
"""Battle-test every activity in every profile (programmatic, no Studio IPC)."""
from pathlib import Path
import argparse, json, sys, uuid
from collections import Counter

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from generate_workflow import _generate_activity, _IdRefCounter
try:
    from generate_activities._data_driven import WizardOnlyActivityError
except ImportError:
    # Fallback: define a local sentinel so except-clauses still work
    class WizardOnlyActivityError(Exception):  # type: ignore[misc]
        pass

from defusedxml.ElementTree import fromstring as _safe_fromstring, ParseError

PROFILES_DIR = SCRIPT_DIR.parent / "references" / "version-profiles"
ANNOTATIONS_DIR = SCRIPT_DIR.parent / "references" / "annotations"


def _iter_profiles():
    """Yield (package, version, profile_dict) for every profile — disk + plugin.

    Plugin-registered profiles take precedence over disk profiles with the same
    (package, version) key so plugins can shadow core data if needed.
    """
    seen: set[tuple[str, str]] = set()
    try:
        from plugin_loader import load_plugins, get_version_profiles
        load_plugins()
        for (pkg, ver), data in sorted(get_version_profiles().items()):
            seen.add((pkg, ver))
            yield pkg, ver, data
    except ImportError:
        pass

    if PROFILES_DIR.is_dir():
        for pkg_dir in sorted(PROFILES_DIR.iterdir()):
            if not pkg_dir.is_dir():
                continue
            for profile_file in sorted(pkg_dir.glob("*.json")):
                ver = profile_file.stem
                if (pkg_dir.name, ver) in seen:
                    continue
                try:
                    profile = json.loads(profile_file.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError) as e:
                    print(f"  [WARN] Cannot load {profile_file}: {e}", file=sys.stderr)
                    continue
                yield pkg_dir.name, ver, profile

# Namespaces used in UiPath XAML for XML validity wrapping.
# Harvested from every xmlns: declaration in references/studio-ground-truth/**/*.xaml.
_NS_WRAP_OPEN = (
    '<x '
    'xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml" '
    'xmlns:sap="http://schemas.microsoft.com/netfx/2009/xaml/activities/presentation" '
    'xmlns:sap2010="http://schemas.microsoft.com/netfx/2010/xaml/activities/presentation" '
    'xmlns:sa="clr-namespace:System.Activities;assembly=System.Activities" '
    'xmlns:s="clr-namespace:System;assembly=System.Private.CoreLib" '
    'xmlns:scg="clr-namespace:System.Collections.Generic;assembly=System.Private.CoreLib" '
    'xmlns:sco="clr-namespace:System.Collections.ObjectModel;assembly=System.Private.CoreLib" '
    'xmlns:sd="clr-namespace:System.Drawing;assembly=System.Drawing.Common" '
    'xmlns:sd1="clr-namespace:System.Drawing;assembly=System.Drawing.Primitives" '
    'xmlns:snm="clr-namespace:System.Net.Mail;assembly=System.Net.Mail" '
    'xmlns:njl="clr-namespace:Newtonsoft.Json.Linq;assembly=Newtonsoft.Json" '
    'xmlns:ui="http://schemas.uipath.com/workflow/activities" '
    'xmlns:uix="http://schemas.uipath.com/workflow/activities/uix" '
    'xmlns:uta="clr-namespace:UiPath.Testing.Activities;assembly=UiPath.Testing.Activities" '
    'xmlns:utam="clr-namespace:UiPath.Testing.Activities.Mocks;assembly=UiPath.Testing.Activities" '
    'xmlns:utat="clr-namespace:UiPath.Testing.Activities.TestData;assembly=UiPath.Testing.Activities" '
    'xmlns:ue="clr-namespace:UiPath.Excel;assembly=UiPath.Excel.Activities" '
    'xmlns:ueab="clr-namespace:UiPath.Excel.Activities.Business;assembly=UiPath.Excel.Activities" '
    'xmlns:um="clr-namespace:UiPath.Mail;assembly=UiPath.Mail.Activities" '
    'xmlns:umab="clr-namespace:UiPath.Mail.Activities.Business;assembly=UiPath.Mail.Activities" '
    'xmlns:umae="clr-namespace:UiPath.Mail.Activities.Enums;assembly=UiPath.Mail.Activities" '
    'xmlns:usau="clr-namespace:UiPath.Shared.Activities.Utils;assembly=UiPath.Mail.Activities" '
    'xmlns:upap="clr-namespace:UiPath.PDF.Activities.PDF;assembly=UiPath.PDF.Activities" '
    'xmlns:uuam="clr-namespace:UiPath.UIAutomationNext.Activities.Models;assembly=UiPath.UIAutomationNext.Activities" '
    'xmlns:uwah="clr-namespace:UiPath.Web.Activities.Http;assembly=UiPath.Web.Activities" '
    'xmlns:uwaj="clr-namespace:UiPath.Web.Activities.JSON;assembly=UiPath.Web.Activities">'
)
_NS_WRAP_CLOSE = "</x>"


def _load_annotations() -> dict:
    """Load and merge all annotation JSON files into a single dict keyed by lowercase activity name."""
    merged = {}
    for p in sorted(ANNOTATIONS_DIR.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            for name, entry in data.get("activities", {}).items():
                merged[name.lower()] = entry
        except (json.JSONDecodeError, OSError):
            continue
    return merged


def _build_min_spec(activity_name: str, annotation: dict | None) -> dict:
    """Build a minimal spec with required params filled in with placeholder values.

    Activity parameters must live under spec["args"] — that is what _generate_activity
    reads via spec.get("args", {}).
    """
    args: dict = {"display_name": activity_name}
    if annotation:
        for pname, meta in annotation.get("params", {}).items():
            if meta.get("required"):
                low = pname.lower()
                if "selector" in low:
                    args[pname] = "<wnd app='test' />"
                elif "text" in low or "message" in low:
                    args[pname] = "test"
                elif "url" in low:
                    args[pname] = "https://example.com"
                elif "path" in low or "file" in low:
                    args[pname] = "C:\\temp\\test.txt"
                else:
                    args[pname] = "placeholder"
    return {"gen": activity_name.lower(), "args": args}


def _dispatch(activity_name: str, annotation: dict | None) -> tuple[bool, str, str]:
    """Run _generate_activity; return (ok, xaml_or_error, dispatched_via).

    via values: "ok" | "unknown" | "wizard-only" | "error"
    """
    spec = _build_min_spec(activity_name, annotation)
    counter = _IdRefCounter()
    try:
        xaml = _generate_activity(
            spec,
            scope_id=uuid.uuid4().hex,
            counter=counter,
            indent="      ",
        )
        return True, xaml, "ok"
    except WizardOnlyActivityError as e:
        return False, str(e), "wizard-only"
    except ValueError as e:
        if "Unknown generator" in str(e):
            return False, str(e), "unknown"
        return False, str(e), "error"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}", "error"


def _check_xml(xaml: str) -> tuple[bool, str]:
    """Verify generated XAML is well-formed XML."""
    wrapped = _NS_WRAP_OPEN + xaml + _NS_WRAP_CLOSE
    try:
        _safe_fromstring(wrapped)
        return True, ""
    except ParseError as e:
        return False, f"{type(e).__name__}: {e}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def _check_gt(xaml: str, profile_entry: dict) -> tuple[str, str]:
    """Ground-truth alignment: root tag match. Return (status, reason) where status in pass|fail|n/a."""
    tmpl = profile_entry.get("xaml_template")
    if not tmpl:
        return "n/a", ""
    try:
        # Both template and generated XAML use namespace-prefixed tags without
        # declarations, so wrap both in the full namespace context before parsing.
        tmpl_children = list(_safe_fromstring(_NS_WRAP_OPEN + tmpl + _NS_WRAP_CLOSE))
        if not tmpl_children:
            return "n/a", "template has no root element"
        tmpl_tag = tmpl_children[0].tag.split("}")[-1]

        gen_children = list(_safe_fromstring(_NS_WRAP_OPEN + xaml + _NS_WRAP_CLOSE))
        if not gen_children:
            return "fail", "generated XAML has no root element"
        gen_tag = gen_children[0].tag.split("}")[-1]

        if gen_tag != tmpl_tag:
            return "fail", f"root tag mismatch: {gen_tag} vs {tmpl_tag}"
        return "pass", ""
    except Exception as e:
        return "fail", f"gt-parse-err: {e}"


def main():
    parser = argparse.ArgumentParser(description="Battle-test activity code generators.")
    parser.add_argument("--package", default=None, help="Filter to a single package name")
    parser.add_argument("--fail-only", action="store_true", help="Print only failed rows")
    parser.add_argument("--verbose", action="store_true", help="Print each row as processed")
    args = parser.parse_args()

    annotations = _load_annotations()
    rows = []

    for pkg_name, ver, profile in _iter_profiles():
        if args.package and pkg_name != args.package:
            continue
        for name, entry in sorted(profile.get("activities", {}).items()):
            # Skip explicitly non-harvestable
            if entry.get("harvestable") is False:
                rows.append({
                    "pkg": pkg_name, "ver": ver, "act": name,
                    "dispatch": "skip", "xml": "-", "gt": "-",
                    "reason": "harvestable=false",
                })
                continue
            # Skip wizard-only activities
            if entry.get("_unsupported_reason") == "wizard-only":
                rows.append({
                    "pkg": pkg_name, "ver": ver, "act": name,
                    "dispatch": "skip", "xml": "-", "gt": "-",
                    "reason": "wizard-only",
                })
                continue

            ann = annotations.get(name.lower())
            ok, out, via = _dispatch(name, ann)
            if args.verbose:
                status = "OK" if ok else f"FAIL({via})"
                print(f"  {pkg_name}/{ver}/{name}: {status}")

            # wizard-only raised at runtime — treat same as profile-declared skip
            if not ok and via == "wizard-only":
                rows.append({
                    "pkg": pkg_name, "ver": ver, "act": name,
                    "dispatch": "skip", "xml": "-", "gt": "-",
                    "reason": "wizard-only (runtime)",
                })
                continue

            if not ok:
                rows.append({
                    "pkg": pkg_name, "ver": ver, "act": name,
                    "dispatch": "fail", "xml": "-", "gt": "-",
                    "reason": f"dispatch-{via}: {out[:120]}",
                })
                continue

            xml_ok, xml_err = _check_xml(out)
            if not xml_ok:
                rows.append({
                    "pkg": pkg_name, "ver": ver, "act": name,
                    "dispatch": "pass", "xml": "fail", "gt": "-",
                    "reason": xml_err[:120],
                })
                continue

            gt_status, gt_reason = _check_gt(out, entry)
            rows.append({
                "pkg": pkg_name, "ver": ver, "act": name,
                "dispatch": "pass", "xml": "pass", "gt": gt_status,
                "reason": gt_reason,
            })

    # Compute summary stats
    total = len(rows)
    skipped = sum(1 for r in rows if r["dispatch"] == "skip")
    tested = total - skipped
    dispatch_pass = sum(1 for r in rows if r["dispatch"] == "pass")
    xml_pass = sum(1 for r in rows if r["xml"] == "pass")
    gt_pass = sum(1 for r in rows if r["gt"] == "pass")
    gt_na = sum(1 for r in rows if r["gt"] == "n/a")
    failures = [r for r in rows if r["dispatch"] == "fail" or r["xml"] == "fail" or r["gt"] == "fail"]

    # Print summary to stdout
    print(f"\n=== Battle-Test Summary ===")
    print(f"Total activities scanned : {total}")
    print(f"Skipped (not harvestable): {skipped}")
    print(f"Tested                   : {tested}")
    print(f"Dispatch pass            : {dispatch_pass}/{tested}")
    print(f"XML well-formed          : {xml_pass}/{tested}")
    print(f"Ground-truth pass        : {gt_pass} pass, {gt_na} n/a (no template)")
    print(f"Failures                 : {len(failures)}")

    # Build report
    report = ["# Battle-Test Programmatic Report", ""]
    report.append(f"Total activities scanned: **{total}**")
    report.append(f"- Skipped (harvestable=false or wizard-only): {skipped}")
    report.append(f"- Tested: {tested}")
    report.append(f"- Dispatch: {dispatch_pass}/{tested} pass")
    report.append(f"- XML well-formed: {xml_pass}/{tested}")
    report.append(f"- Ground-truth alignment: {gt_pass} pass, {gt_na} n/a (no template)")
    report.append(f"- Failures: {len(failures)}")
    report.append("")

    # Per-profile breakdown
    report.append("## Per-profile pass rates")
    report.append("")
    report.append("| Package / Version | Total | Skip | Dispatch | XML | GT |")
    report.append("|---|---|---|---|---|---|")
    for key in sorted({(r["pkg"], r["ver"]) for r in rows}):
        sub = [r for r in rows if (r["pkg"], r["ver"]) == key]
        sk = sum(1 for r in sub if r["dispatch"] == "skip")
        d = sum(1 for r in sub if r["dispatch"] == "pass")
        x = sum(1 for r in sub if r["xml"] == "pass")
        g = sum(1 for r in sub if r["gt"] == "pass")
        report.append(f"| {key[0]}/{key[1]} | {len(sub)} | {sk} | {d} | {x} | {g} |")
    report.append("")

    # Failures section
    report.append(f"## Failures ({len(failures)})")
    report.append("")
    report.append("| Pkg | Ver | Activity | Dispatch | XML | GT | Reason |")
    report.append("|---|---|---|---|---|---|---|")
    for r in sorted(failures, key=lambda r: (r["pkg"], r["ver"], r["act"])):
        reason = r["reason"][:100].replace("|", "\\|")
        report.append(
            f"| {r['pkg']} | {r['ver']} | {r['act']} | {r['dispatch']} | {r['xml']} | {r['gt']} | {reason} |"
        )
    report.append("")

    # Top failure reason buckets
    c = Counter(r["reason"].split(":")[0][:60] for r in failures)
    report.append("## Top failure reason buckets")
    report.append("")
    if c:
        for reason, ct in c.most_common(10):
            report.append(f"- **{ct}x** {reason}")
    else:
        report.append("- (none — all activities dispatched and validated successfully)")
    report.append("")

    # Harness limitations
    report.append("## Harness limitations")
    report.append("")
    report.append("- Minimal specs only: required params are filled with typed placeholders (selector, text, url, path, or 'placeholder').")
    report.append("- No runtime Studio validation: XML well-formedness is checked but not XAML schema compliance.")
    report.append("- Ground-truth check is root-tag-only (no fixed_attrs or child structure verification).")
    report.append("- Container activities (scope handlers) may fail dispatch if children are required — not modeled here.")
    report.append("- Activities with `harvestable=false` are skipped without dispatch attempt.")
    report.append("- No cross-version regression detection: each profile version is tested independently.")
    report.append("")

    out_path = SCRIPT_DIR.parent.parent / ".omc" / "analysis" / "battle-test-programmatic.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(report), encoding="utf-8")
    print(f"\nWrote report to: {out_path}")

    # Return non-zero if any dispatch failures (not GT failures — GT n/a is expected)
    dispatch_failures = sum(1 for r in rows if r["dispatch"] == "fail")
    return 0 if dispatch_failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
