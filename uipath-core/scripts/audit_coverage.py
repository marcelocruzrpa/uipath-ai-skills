#!/usr/bin/env python3
"""Audit generator coverage for every activity shipped in profiles + ground-truth.

Builds a single source of truth for the "every activity has a generator"
effort. For each (package, profile_version, activity) triple, classifies
its dispatch status and emits:
  * .omc/analysis/coverage-manifest.json  (machine-readable)
  * .omc/analysis/coverage-report.md      (per-package counts + tables)

Verdicts (mutually exclusive):
  covered                    - hand-written gen_* OR annotation that resolves
  wizard-only                - annotation _unsupported_reason or profile flag
  broken-annotation          - annotation present but gen_function missing
  uncovered-but-harvestable  - no gen, no annotation, harvestable + harvested
  uncovered-not-harvestable  - no gen, no annotation, no harvest available

Usage:
  python uipath-core/scripts/audit_coverage.py             # write manifest + report
  python uipath-core/scripts/audit_coverage.py --check     # compare to baseline; exit 1 on drift
  python uipath-core/scripts/audit_coverage.py --baseline  # write current state as baseline
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent  # repo root
CORE = ROOT / "uipath-core"
PROFILES_DIR = CORE / "references" / "version-profiles"
GT_DIR = CORE / "references" / "studio-ground-truth"
ANNOT_DIR = CORE / "references" / "annotations"
GEN_DIR = CORE / "scripts" / "generate_activities"
ANALYSIS_DIR = ROOT / ".omc" / "analysis"
MANIFEST_PATH = ANALYSIS_DIR / "coverage-manifest.json"
REPORT_PATH = ANALYSIS_DIR / "coverage-report.md"
# Baseline is checked into the repo so --check can run in CI; the
# manifest + report under .omc/analysis/ are regenerated artifacts.
BASELINE_PATH = CORE / "references" / "coverage-baseline.json"


@dataclass
class ActivityRow:
    package: str
    profile_version: str
    activity: str
    has_hand_written_gen: bool
    hand_written_gen_loc: str | None  # "file:line" or None
    has_annotation: bool
    annotation_file: str | None
    gen_function: str | None
    gen_function_resolves: bool
    harvestable: bool
    harvested: bool
    unsupported_reason: str | None
    review_needed: bool
    class_name: str | None
    clr_namespace: str | None
    verdict: str = ""


def collect_hand_written_gens() -> dict[str, str]:
    """Walk generate_activities/*.py for `def gen_*(` definitions.

    Returns: dict mapping the bare gen_function name (e.g. "gen_ntypeinto")
    to "<filename>:<lineno>".
    """
    found: dict[str, str] = {}
    for py in sorted(GEN_DIR.glob("*.py")):
        if py.name.startswith("_"):
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except (SyntaxError, OSError) as exc:
            print(f"  [WARN] could not parse {py}: {exc}", file=sys.stderr)
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("gen_"):
                found[node.name] = f"{py.relative_to(ROOT).as_posix()}:{node.lineno}"
    # _data_driven also exports a gen_from_annotation
    dd = GEN_DIR / "_data_driven.py"
    if dd.exists():
        try:
            tree = ast.parse(dd.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.FunctionDef)
                    and node.name == "gen_from_annotation"
                ):
                    found[node.name] = f"{dd.relative_to(ROOT).as_posix()}:{node.lineno}"
        except (SyntaxError, OSError):
            pass
    return found


def collect_annotations() -> dict[str, tuple[str, dict]]:
    """Read every annotations/*.json. Returns lower-case activity name -> (file, entry)."""
    out: dict[str, tuple[str, dict]] = {}
    for path in sorted(ANNOT_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"  [WARN] could not read {path}: {exc}", file=sys.stderr)
            continue
        for name, entry in (data.get("activities") or {}).items():
            if not isinstance(entry, dict):
                continue
            out[name.lower()] = (path.relative_to(ROOT).as_posix(), entry)
    return out


def collect_profiles() -> list[tuple[str, str, str, dict]]:
    """Walk version-profiles/<pkg>/<ver>.json. Returns (package, version, activity, entry) tuples."""
    rows: list[tuple[str, str, str, dict]] = []
    for pkg_dir in sorted(PROFILES_DIR.iterdir()):
        if not pkg_dir.is_dir():
            continue
        package = pkg_dir.name
        for ver_path in sorted(pkg_dir.glob("*.json")):
            version = ver_path.stem
            try:
                data = json.loads(ver_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                print(f"  [WARN] could not read {ver_path}: {exc}", file=sys.stderr)
                continue
            for act, entry in (data.get("activities") or {}).items():
                if not isinstance(entry, dict):
                    continue
                rows.append((package, version, act, entry))
    return rows


def collect_ground_truth_index() -> dict[tuple[str, str], set[str]]:
    """Read every studio-ground-truth/<pkg>/<ver>/index.json. Returns set of harvested activity names."""
    out: dict[tuple[str, str], set[str]] = {}
    for pkg_dir in sorted(GT_DIR.iterdir()):
        if not pkg_dir.is_dir():
            continue
        for ver_dir in sorted(pkg_dir.iterdir()):
            if not ver_dir.is_dir():
                continue
            idx = ver_dir / "index.json"
            if not idx.exists():
                continue
            try:
                data = json.loads(idx.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            names: set[str] = set()
            acts = data.get("activities")
            if isinstance(acts, dict):
                for name, entry in acts.items():
                    # only count harvested entries with status=ok
                    if isinstance(entry, dict) and entry.get("status") in (None, "ok"):
                        names.add(str(name))
                    elif not isinstance(entry, dict):
                        names.add(str(name))
            elif isinstance(acts, list):
                for entry in acts:
                    if isinstance(entry, dict):
                        name = entry.get("name") or entry.get("class_name")
                        if name:
                            names.add(str(name))
            out[(pkg_dir.name, ver_dir.name)] = names
    return out


def classify(row: ActivityRow) -> str:
    if row.has_hand_written_gen:
        return "covered"
    if row.unsupported_reason:
        return "wizard-only"
    if row.has_annotation:
        if row.gen_function_resolves:
            return "covered"
        # Annotation present but gen_function refers to something that doesn't exist.
        # Could still dispatch via gen_from_annotation if element_tag + params present.
        return "broken-annotation"
    if row.harvestable and row.harvested:
        return "uncovered-but-harvestable"
    return "uncovered-not-harvestable"


def build_rows(
    profiles: list[tuple[str, str, str, dict]],
    annotations: dict[str, tuple[str, dict]],
    hand_written: dict[str, str],
    gt_index: dict[tuple[str, str], set[str]],
) -> list[ActivityRow]:
    rows: list[ActivityRow] = []
    for package, version, activity, prof_entry in profiles:
        ann = annotations.get(activity.lower())
        ann_file = ann[0] if ann else None
        ann_entry = ann[1] if ann else {}
        gen_function = ann_entry.get("gen_function") if ann else None
        # gen_from_annotation fallback: an annotation entry without gen_function
        # but with element_tag is still dispatchable.
        has_dispatchable_annotation = bool(ann_entry) and (
            (gen_function and gen_function in hand_written)
            or (ann_entry.get("element_tag") and not ann_entry.get("_unsupported_reason"))
        )
        gen_function_resolves = bool(
            (gen_function and gen_function in hand_written)
            or (
                ann_entry
                and ann_entry.get("element_tag")
                and not ann_entry.get("_unsupported_reason")
            )
        )
        # Hand-written: a gen_<lower(activity)> exists?
        guess = f"gen_{activity.lower()}"
        hand_loc = hand_written.get(guess) or (
            hand_written.get(gen_function) if gen_function else None
        )
        harvested_set = gt_index.get((package, version), set())
        unsupported = ann_entry.get("_unsupported_reason") if ann_entry else None
        if not unsupported and prof_entry.get("harvestable") is False:
            unsupported = "non-harvestable (profile flag)"
        row = ActivityRow(
            package=package,
            profile_version=version,
            activity=activity,
            has_hand_written_gen=hand_loc is not None,
            hand_written_gen_loc=hand_loc,
            has_annotation=bool(ann_entry),
            annotation_file=ann_file,
            gen_function=gen_function,
            gen_function_resolves=gen_function_resolves,
            harvestable=bool(prof_entry.get("harvestable", True)),
            harvested=activity in harvested_set,
            unsupported_reason=unsupported,
            review_needed=bool(ann_entry.get("_review_needed")) if ann_entry else False,
            class_name=prof_entry.get("class_name"),
            clr_namespace=prof_entry.get("clr_namespace"),
        )
        row.verdict = classify(row)
        rows.append(row)
    return rows


def per_package_summary(rows: list[ActivityRow]) -> dict[tuple[str, str], dict[str, int]]:
    out: dict[tuple[str, str], dict[str, int]] = {}
    for r in rows:
        key = (r.package, r.profile_version)
        bucket = out.setdefault(
            key,
            {
                "total": 0,
                "covered": 0,
                "wizard-only": 0,
                "broken-annotation": 0,
                "uncovered-but-harvestable": 0,
                "uncovered-not-harvestable": 0,
            },
        )
        bucket["total"] += 1
        bucket[r.verdict] += 1
    return out


def write_manifest(rows: list[ActivityRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = per_package_summary(rows)
    payload = {
        "schema": 1,
        "totals": {
            "rows": len(rows),
            "covered": sum(1 for r in rows if r.verdict == "covered"),
            "wizard-only": sum(1 for r in rows if r.verdict == "wizard-only"),
            "broken-annotation": sum(1 for r in rows if r.verdict == "broken-annotation"),
            "uncovered-but-harvestable": sum(
                1 for r in rows if r.verdict == "uncovered-but-harvestable"
            ),
            "uncovered-not-harvestable": sum(
                1 for r in rows if r.verdict == "uncovered-not-harvestable"
            ),
        },
        "per_package": {
            f"{pkg}/{ver}": counts for (pkg, ver), counts in sorted(summary.items())
        },
        "rows": [asdict(r) for r in rows],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def write_report(rows: list[ActivityRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = per_package_summary(rows)
    lines: list[str] = []
    lines.append("# Generator coverage report\n")
    lines.append(
        f"Total rows: **{len(rows)}** across "
        f"{len({(r.package, r.profile_version) for r in rows})} (package, version) pairs.\n"
    )
    lines.append("")
    lines.append("| Verdict | Count |")
    lines.append("|---|---|")
    for verdict in (
        "covered",
        "wizard-only",
        "broken-annotation",
        "uncovered-but-harvestable",
        "uncovered-not-harvestable",
    ):
        n = sum(1 for r in rows if r.verdict == verdict)
        lines.append(f"| {verdict} | {n} |")
    lines.append("")
    lines.append("## Per-package breakdown\n")
    lines.append(
        "| Package / Version | Total | covered | wizard-only | broken-annotation | uncovered-harvestable | uncovered-not |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    for (pkg, ver), c in sorted(summary.items()):
        lines.append(
            f"| {pkg}/{ver} | {c['total']} | {c['covered']} | {c['wizard-only']} | "
            f"{c['broken-annotation']} | {c['uncovered-but-harvestable']} | {c['uncovered-not-harvestable']} |"
        )
    lines.append("")
    # Per-verdict tables (excluding 'covered' which is the bulk)
    for verdict in ("broken-annotation", "uncovered-but-harvestable", "uncovered-not-harvestable", "wizard-only"):
        bucket = [r for r in rows if r.verdict == verdict]
        if not bucket:
            continue
        lines.append(f"## {verdict} ({len(bucket)})\n")
        lines.append("| Package | Version | Activity | Annotation | gen_function | Notes |")
        lines.append("|---|---|---|---|---|---|")
        for r in sorted(bucket, key=lambda r: (r.package, r.profile_version, r.activity)):
            note_bits: list[str] = []
            if r.unsupported_reason:
                note_bits.append(r.unsupported_reason)
            if r.review_needed:
                note_bits.append("review_needed")
            if r.harvested:
                note_bits.append("harvested")
            elif not r.harvestable:
                note_bits.append("not-harvestable")
            note = "; ".join(note_bits) or "—"
            ann = "yes" if r.has_annotation else "—"
            gf = r.gen_function or "—"
            lines.append(f"| {r.package} | {r.profile_version} | {r.activity} | {ann} | {gf} | {note} |")
        lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def manifest_summary_for_check(payload: dict) -> dict:
    """Reduce manifest to the bits we want to baseline-compare (counts only)."""
    return {"totals": payload.get("totals"), "per_package": payload.get("per_package")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare to baseline; exit 1 on drift")
    parser.add_argument("--baseline", action="store_true", help="overwrite baseline with current state")
    args = parser.parse_args()

    profiles = collect_profiles()
    annotations = collect_annotations()
    hand_written = collect_hand_written_gens()
    gt_index = collect_ground_truth_index()
    rows = build_rows(profiles, annotations, hand_written, gt_index)

    write_manifest(rows, MANIFEST_PATH)
    write_report(rows, REPORT_PATH)

    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    summary = manifest_summary_for_check(payload)

    if args.baseline:
        BASELINE_PATH.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(f"baseline written to {BASELINE_PATH.relative_to(ROOT).as_posix()}")
        return 0

    print(f"manifest written: {MANIFEST_PATH.relative_to(ROOT).as_posix()}")
    print(f"report  written: {REPORT_PATH.relative_to(ROOT).as_posix()}")
    print()
    totals = summary["totals"]
    print(
        f"totals: {totals['rows']} rows  "
        f"covered={totals['covered']}  wizard={totals['wizard-only']}  "
        f"broken={totals['broken-annotation']}  uncov-h={totals['uncovered-but-harvestable']}  "
        f"uncov={totals['uncovered-not-harvestable']}"
    )

    if args.check:
        if not BASELINE_PATH.exists():
            print(f"--check: baseline missing at {BASELINE_PATH}; run with --baseline first", file=sys.stderr)
            return 2
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        if baseline != summary:
            print("--check: drift detected vs baseline", file=sys.stderr)
            for k, v in summary["totals"].items():
                bv = baseline.get("totals", {}).get(k)
                if bv != v:
                    print(f"  totals.{k}: baseline={bv} current={v}", file=sys.stderr)
            for k, v in summary["per_package"].items():
                bv = baseline.get("per_package", {}).get(k)
                if bv != v:
                    print(f"  per_package[{k}]: baseline={bv} current={v}", file=sys.stderr)
            return 1
        print("--check: matches baseline")
    return 0


if __name__ == "__main__":
    sys.exit(main())
