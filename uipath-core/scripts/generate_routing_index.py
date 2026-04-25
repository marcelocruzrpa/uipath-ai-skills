#!/usr/bin/env python3
"""Phase F: generate references/routing-index.md from the annotation corpus.

The index is the LLM-facing activity-selection reference. Per-category
sections list every activity with its description + use_when. A
"Don't use" section gathers wizard-only / unsupported entries with
the reason and any documented alternative. An "Alternatives" section
follows the per-category tables, derived from `alternatives` graphs.

Idempotent: re-running on the same input produces a byte-identical
file. regression_test.py runs this and `git diff --exit-code`s the
output, so drift = test failure.

Usage:
    python uipath-core/scripts/generate_routing_index.py
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
ANNOT_DIR = ROOT / "uipath-core" / "references" / "annotations"
INDEX_PATH = ROOT / "uipath-core" / "references" / "routing-index.md"

CATEGORY_ORDER = [
    "ui_automation",
    "application_card",
    "navigation",
    "control_flow",
    "data_operations",
    "excel",
    "mail",
    "file_system",
    "http_json",
    "dialogs",
    "error_handling",
    "invoke",
    "orchestrator",
    "persistence",
    "logging_misc",
    "integrations",
    "testing",
    "pdf",
    "database",
    "webapi",
]

CATEGORY_TITLES = {
    "ui_automation": "UI automation",
    "application_card": "Application & browser cards",
    "navigation": "Navigation",
    "control_flow": "Control flow",
    "data_operations": "Data tables & collections",
    "excel": "Excel",
    "mail": "Email",
    "file_system": "File system",
    "http_json": "HTTP & JSON",
    "dialogs": "Dialogs",
    "error_handling": "Error handling & retry",
    "invoke": "Invoke (workflow / code)",
    "orchestrator": "Orchestrator",
    "persistence": "Persistence (long-running)",
    "logging_misc": "Logging & helpers",
    "integrations": "External integrations",
    "testing": "Testing",
    "pdf": "PDF",
    "database": "Database",
    "webapi": "Web API",
}


def _load_entries() -> list[tuple[str, str, dict]]:
    """Return list of (file, activity_name, entry) sorted by category then name."""
    entries: list[tuple[str, str, dict]] = []
    for jf in sorted(ANNOT_DIR.glob("*.json")):
        try:
            d = json.loads(jf.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for name, e in (d.get("activities") or {}).items():
            if isinstance(e, dict):
                entries.append((jf.name, name, e))
    return entries


def _short(text: str | None, limit: int = 240) -> str:
    if not text:
        return "—"
    t = " ".join(text.split())
    if len(t) > limit:
        t = t[: limit - 1] + "…"
    return t


def _esc(text: str) -> str:
    return text.replace("|", "\\|")


def _generator_label(entry: dict, name: str) -> str:
    gen = entry.get("gen_function")
    if gen:
        return f"`{gen}`"
    return f"`{name}` (data-driven)"


def render() -> str:
    entries = _load_entries()
    by_category: dict[str, list[tuple[str, str, dict]]] = defaultdict(list)
    unsupported: list[tuple[str, str, dict]] = []
    for fname, name, e in entries:
        if e.get("_unsupported_reason"):
            unsupported.append((fname, name, e))
            continue
        cat = e.get("category") or "uncategorized"
        by_category[cat].append((fname, name, e))

    lines: list[str] = []
    lines.append("# Activity routing index\n")
    lines.append(
        "Auto-generated from `references/annotations/*.json` by\n"
        "`uipath-core/scripts/generate_routing_index.py`. Do not hand-edit — edit\n"
        "the annotation entries instead, then regenerate.\n"
    )

    # Top-level counts
    total = sum(len(v) for v in by_category.values()) + len(unsupported)
    review_pending = sum(
        1
        for fname, name, e in entries
        if not e.get("_unsupported_reason") and e.get("_routing_review_needed")
    )
    lines.append(
        f"**{total} activities indexed** "
        f"(supported: {sum(len(v) for v in by_category.values())}, "
        f"wizard-only / unsupported: {len(unsupported)}, "
        f"routing wording review pending: {review_pending}).\n"
    )

    # Per-category tables
    for cat in CATEGORY_ORDER:
        bucket = by_category.get(cat) or []
        if not bucket:
            continue
        title = CATEGORY_TITLES.get(cat, cat.replace("_", " ").title())
        lines.append(f"## {title} ({len(bucket)})\n")
        lines.append("| Activity | Generator | Description | Use when |")
        lines.append("|---|---|---|---|")
        for fname, name, e in sorted(bucket, key=lambda r: r[1].lower()):
            gen = _generator_label(e, name)
            desc = _short(e.get("description"))
            uw = _short(e.get("use_when"))
            review = " 🛈" if e.get("_routing_review_needed") else ""
            lines.append(f"| `{name}`{review} | {gen} | {_esc(desc)} | {_esc(uw)} |")
        lines.append("")

    # Any uncategorized leftovers
    leftover = sorted(
        (e for cat, items in by_category.items() if cat not in CATEGORY_ORDER for e in items),
        key=lambda r: r[1].lower(),
    )
    if leftover:
        lines.append(f"## Uncategorized ({len(leftover)})\n")
        lines.append("| Activity | Description | Use when |")
        lines.append("|---|---|---|")
        for fname, name, e in leftover:
            lines.append(
                f"| `{name}` | {_esc(_short(e.get('description')))} | {_esc(_short(e.get('use_when')))} |"
            )
        lines.append("")

    # Unsupported / wizard-only
    if unsupported:
        lines.append(f"## Don't auto-generate ({len(unsupported)})\n")
        lines.append(
            "These activities require UiPath Studio's interactive wizard or otherwise\n"
            "cannot be reliably emitted programmatically. Direct the user to author\n"
            "them in Studio rather than calling the dispatcher.\n"
        )
        lines.append("| Activity | Reason | Description |")
        lines.append("|---|---|---|")
        for fname, name, e in sorted(unsupported, key=lambda r: r[1].lower()):
            reason = _short(e.get("_unsupported_reason"))
            desc = _short(e.get("description"))
            lines.append(f"| `{name}` | {_esc(reason)} | {_esc(desc)} |")
        lines.append("")

    # Alternatives matrix — only for entries that have alternatives populated
    alts: list[tuple[str, str, list[dict]]] = []
    for fname, name, e in entries:
        a = e.get("alternatives")
        if isinstance(a, list) and a:
            alts.append((fname, name, a))
    if alts:
        lines.append(f"## Alternatives ({len(alts)})\n")
        lines.append(
            "Each row pairs an activity with its documented substitutes and the\n"
            "trigger that picks the substitute over the canonical activity.\n"
        )
        lines.append("| Activity | Alternative | Use alternative when |")
        lines.append("|---|---|---|")
        for fname, name, alist in sorted(alts, key=lambda r: r[1].lower()):
            for alt in alist:
                if not isinstance(alt, dict):
                    continue
                act = alt.get("activity", "—")
                trig = _short(alt.get("use_instead_when"))
                lines.append(f"| `{name}` | `{act}` | {_esc(trig)} |")
        lines.append("")

    lines.append(
        f"\n---\n"
        f"_Index footer:_ {total} activities, {len(by_category)} categories, "
        f"{len(unsupported)} unsupported, {review_pending} review-pending. "
        f"Regenerate with `python uipath-core/scripts/generate_routing_index.py`.\n"
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if the file on disk differs from the regenerated content",
    )
    args = parser.parse_args()

    out = render()
    if args.check:
        existing = INDEX_PATH.read_text(encoding="utf-8") if INDEX_PATH.exists() else ""
        if existing != out:
            print(
                f"--check: {INDEX_PATH.relative_to(ROOT)} is out of date; re-run "
                "generate_routing_index.py to refresh.",
                file=sys.stderr,
            )
            return 1
        print(f"--check: {INDEX_PATH.relative_to(ROOT)} is up to date.")
        return 0

    INDEX_PATH.write_text(out, encoding="utf-8")
    print(f"wrote {INDEX_PATH.relative_to(ROOT)} ({len(out)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
