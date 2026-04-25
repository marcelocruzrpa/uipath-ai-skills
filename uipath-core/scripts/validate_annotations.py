#!/usr/bin/env python3
"""Validate every annotations/*.json against the schema in
references/annotations/SCHEMA.md.

Default mode: structural validation only (well-formed JSON, expected
field types). Reports warnings (does not fail) for entries missing the
Phase-B routing fields.

--strict: fail when any non-wizard entry is missing description /
use_when / category. Use this in CI once Phase E completes.

--report: write a machine-readable JSON summary to
.omc/analysis/annotation-validation.json.

Exit codes:
  0  all checks pass
  1  structural errors found, OR --strict failures
  2  baseline / IO problem
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
ANNOT_DIR = ROOT / "uipath-core" / "references" / "annotations"
ANALYSIS_DIR = ROOT / ".omc" / "analysis"
REPORT_PATH = ANALYSIS_DIR / "annotation-validation.json"

VALID_CATEGORIES = frozenset(
    {
        "ui_automation",
        "excel",
        "mail",
        "data_operations",
        "control_flow",
        "error_handling",
        "dialogs",
        "file_system",
        "http_json",
        "integrations",
        "invoke",
        "logging_misc",
        "navigation",
        "orchestrator",
        "testing",
        "persistence",
        "pdf",
        "database",
        "webapi",
        "application_card",
    }
)

REQUIRED_DISPATCH_FIELDS = ("element_tag", "params", "fixed_attrs", "conditional_attrs", "child_elements")
ROUTING_REQUIRED = ("description", "use_when", "category")


def _is_str(v: Any) -> bool:
    return isinstance(v, str) and bool(v.strip())


def validate_entry(name: str, entry: dict, strict: bool) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for one annotation entry."""
    errs: list[str] = []
    warns: list[str] = []

    if not isinstance(entry, dict):
        errs.append(f"{name}: entry is not an object (got {type(entry).__name__})")
        return errs, warns

    is_wizard = bool(entry.get("_unsupported_reason"))
    has_hand_written = _is_str(entry.get("gen_function"))

    # Structural checks (always)
    if not is_wizard:
        for field in REQUIRED_DISPATCH_FIELDS:
            if field not in entry:
                errs.append(f"{name}: missing required field {field!r}")
            elif field in ("params", "fixed_attrs", "conditional_attrs"):
                if not isinstance(entry.get(field), dict):
                    errs.append(f"{name}.{field}: expected object, got {type(entry.get(field)).__name__}")
            elif field == "child_elements":
                if not isinstance(entry.get(field), dict):
                    errs.append(f"{name}.{field}: expected object, got {type(entry.get(field)).__name__}")
        # element_tag is required only when the entry dispatches via
        # gen_from_annotation. Composite/helper entries with a hand-written
        # gen_function (e.g. gen_variables_block, gen_take_screenshot_and_save)
        # are allowed to keep element_tag = null.
        if not has_hand_written:
            if not _is_str(entry.get("element_tag")):
                errs.append(f"{name}.element_tag: must be a non-empty string when gen_function is null")
        elif "element_tag" in entry and entry["element_tag"] is not None and not _is_str(entry["element_tag"]):
            errs.append(f"{name}.element_tag: must be a non-empty string or null")
    else:
        if not _is_str(entry["_unsupported_reason"]):
            errs.append(f"{name}._unsupported_reason: must be a non-empty string")

    # Type checks for optional structural bits
    if "gen_function" in entry and entry["gen_function"] is not None:
        if not _is_str(entry["gen_function"]):
            errs.append(f"{name}.gen_function: must be a non-empty string or null")

    # Routing-metadata checks
    for field in ROUTING_REQUIRED:
        present = field in entry and entry[field] not in (None, "")
        if not present:
            msg = f"{name}: missing routing field {field!r}"
            (errs if strict else warns).append(msg)
    if "category" in entry and entry["category"] is not None:
        if entry["category"] not in VALID_CATEGORIES:
            errs.append(
                f"{name}.category: {entry['category']!r} is not in the allowed enum"
            )
    if "alternatives" in entry and entry["alternatives"] is not None:
        if not isinstance(entry["alternatives"], list):
            errs.append(f"{name}.alternatives: expected array, got {type(entry['alternatives']).__name__}")
        else:
            for i, alt in enumerate(entry["alternatives"]):
                if not isinstance(alt, dict):
                    errs.append(f"{name}.alternatives[{i}]: expected object, got {type(alt).__name__}")
                    continue
                if not _is_str(alt.get("activity")):
                    errs.append(f"{name}.alternatives[{i}].activity: required non-empty string")
                if not _is_str(alt.get("use_instead_when")):
                    errs.append(f"{name}.alternatives[{i}].use_instead_when: required non-empty string")
    if "examples" in entry and entry["examples"] is not None:
        if not isinstance(entry["examples"], list):
            errs.append(f"{name}.examples: expected array, got {type(entry['examples']).__name__}")
        else:
            for i, ex in enumerate(entry["examples"]):
                if not isinstance(ex, dict):
                    errs.append(f"{name}.examples[{i}]: expected object, got {type(ex).__name__}")
                    continue
                if not _is_str(ex.get("intent")):
                    errs.append(f"{name}.examples[{i}].intent: required non-empty string")
                if not isinstance(ex.get("spec_args"), dict):
                    errs.append(f"{name}.examples[{i}].spec_args: required object")
    if "tags" in entry and entry["tags"] is not None:
        if not isinstance(entry["tags"], list) or not all(_is_str(t) for t in entry["tags"]):
            errs.append(f"{name}.tags: expected array of non-empty strings")

    return errs, warns


def validate_file(path: Path, strict: bool) -> tuple[list[str], list[str], int]:
    """Returns (errors, warnings, entry_count)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return ([f"{path.name}: cannot read ({exc})"], [], 0)
    errs: list[str] = []
    warns: list[str] = []
    activities = data.get("activities")
    if not isinstance(activities, dict):
        return ([f"{path.name}: top-level 'activities' must be an object"], [], 0)
    for name, entry in activities.items():
        e, w = validate_entry(f"{path.name}/{name}", entry, strict)
        errs.extend(e)
        warns.extend(w)
    return errs, warns, len(activities)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="fail on missing routing fields")
    parser.add_argument("--report", action="store_true", help="write .omc/analysis/annotation-validation.json")
    parser.add_argument("--quiet", action="store_true", help="only print errors, suppress per-file noise")
    args = parser.parse_args()

    if not ANNOT_DIR.exists():
        print(f"annotations dir missing: {ANNOT_DIR}", file=sys.stderr)
        return 2

    files = sorted(ANNOT_DIR.glob("*.json"))
    total_entries = 0
    total_errs: list[str] = []
    total_warns: list[str] = []
    per_file: list[dict] = []
    for p in files:
        errs, warns, n = validate_file(p, args.strict)
        total_entries += n
        total_errs.extend(errs)
        total_warns.extend(warns)
        per_file.append({"file": p.name, "entries": n, "errors": len(errs), "warnings": len(warns)})
        if not args.quiet:
            tag = "OK" if not errs else "FAIL"
            print(f"  [{tag}] {p.name}  entries={n}  errors={len(errs)}  warnings={len(warns)}")

    if args.report:
        ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(
            json.dumps(
                {
                    "strict": args.strict,
                    "total_entries": total_entries,
                    "total_errors": len(total_errs),
                    "total_warnings": len(total_warns),
                    "per_file": per_file,
                    "errors": total_errs,
                    "warnings": total_warns,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"report: {REPORT_PATH.relative_to(ROOT).as_posix()}")

    print()
    print(
        f"summary: {len(files)} files  {total_entries} entries  "
        f"errors={len(total_errs)}  warnings={len(total_warns)}  "
        f"strict={'yes' if args.strict else 'no'}"
    )

    if total_errs:
        for e in total_errs[:30]:
            print(f"  ERR {e}", file=sys.stderr)
        if len(total_errs) > 30:
            print(f"  ... and {len(total_errs) - 30} more errors", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
