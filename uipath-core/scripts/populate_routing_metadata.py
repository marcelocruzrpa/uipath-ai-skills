#!/usr/bin/env python3
"""Phase E: seed routing metadata across every annotation entry.

For every entry in references/annotations/*.json:
  * `category`   — derived from the filename (definitive).
  * `description` — seeded from version-profile `doc_name` when
                    available; otherwise from the activity name.
  * `use_when`   — placeholder phrasing keyed on category + name.
                    Reviewers refine this; entries that come out of
                    this script carry `_routing_review_needed: true`.

The script is idempotent — re-running it never overwrites a routing
field that has been edited away from its placeholder. The placeholder
sentinel is the bool `_routing_review_needed: true`. Once a human flips
that to `false`, the entry is locked.

Usage:
    python uipath-core/scripts/populate_routing_metadata.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
ANNOT_DIR = ROOT / "uipath-core" / "references" / "annotations"
PROFILES_DIR = ROOT / "uipath-core" / "references" / "version-profiles"

FILE_TO_CATEGORY = {
    "application_card.json": "application_card",
    "control_flow.json": "control_flow",
    "data_operations.json": "data_operations",
    "dialogs.json": "dialogs",
    "error_handling.json": "error_handling",
    "excel_extended.json": "excel",
    "file_system.json": "file_system",
    "http_json.json": "http_json",
    "integrations.json": "integrations",
    "invoke.json": "invoke",
    "logging_misc.json": "logging_misc",
    "mail_extended.json": "mail",
    "navigation.json": "navigation",
    "orchestrator.json": "orchestrator",
    "persistence_extended.json": "persistence",
    "system_extended.json": "data_operations",  # heterogeneous; default to broadest bucket
    "testing.json": "testing",
    "ui_automation.json": "ui_automation",
}

CATEGORY_USE_WHEN_TEMPLATE = {
    "application_card": "User wants to open or attach to an application or browser context.",
    "control_flow": "User wants to control workflow execution flow with {label}.",
    "data_operations": "User wants to manipulate a DataTable or collection via {label}.",
    "dialogs": "User wants to display a UI dialog ({label}) and read its result.",
    "error_handling": "User wants to handle exceptions or retries via {label}.",
    "excel": "User wants to interact with Excel using {label}.",
    "file_system": "User wants to perform a filesystem operation: {label}.",
    "http_json": "User wants to perform an HTTP or JSON operation: {label}.",
    "integrations": "User wants to integrate with an external system using {label}.",
    "invoke": "User wants to invoke another workflow or piece of code via {label}.",
    "logging_misc": "User wants to log or perform a miscellaneous helper task: {label}.",
    "mail": "User wants to send or process email using {label}.",
    "navigation": "User wants to navigate within the host application: {label}.",
    "orchestrator": "User wants to interact with UiPath Orchestrator via {label}.",
    "persistence": "User wants to persist or resume a long-running workflow via {label}.",
    "testing": "User wants to author or run a test via {label}.",
    "ui_automation": "User wants to interact with a UI element via {label}.",
    "pdf": "User wants to read or process a PDF document via {label}.",
    "database": "User wants to query or modify a database via {label}.",
    "webapi": "User wants to call a web API or work with structured XML/JSON via {label}.",
}


def _humanize(name: str) -> str:
    """ApplicationEventTrigger -> 'Application Event Trigger'."""
    s = re.sub(r"(.)([A-Z][a-z]+)", r"\1 \2", name)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", s)
    return s.strip()


def _load_doc_names() -> dict[str, str]:
    """Map lower-cased activity name -> doc_name from any profile."""
    out: dict[str, str] = {}
    for pkg_dir in PROFILES_DIR.iterdir():
        if not pkg_dir.is_dir():
            continue
        for ver in pkg_dir.glob("*.json"):
            try:
                d = json.loads(ver.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            for name, e in (d.get("activities") or {}).items():
                if not isinstance(e, dict):
                    continue
                doc = e.get("doc_name")
                if isinstance(doc, str) and doc.strip():
                    out.setdefault(name.lower(), doc.strip())
    return out


def _seed_entry(name: str, entry: dict, category: str, doc_names: dict[str, str]) -> bool:
    """Mutate entry in place. Return True if any field changed."""
    changed = False
    is_wizard = bool(entry.get("_unsupported_reason"))
    label = doc_names.get(name.lower()) or _humanize(name)

    # category — write only if missing or different
    if entry.get("category") != category:
        entry["category"] = category
        changed = True

    # description — only seed when missing AND placeholder (review-needed) state
    if not entry.get("description"):
        if is_wizard:
            entry["description"] = (
                f"{label} (wizard-only) — must be configured through UiPath Studio's interactive wizard."
            )
        else:
            entry["description"] = f"{label} activity from the {category.replace('_', ' ')} category."
        changed = True

    # use_when — only seed when missing
    if not entry.get("use_when"):
        if is_wizard:
            entry["use_when"] = (
                f"Do not auto-generate {label}. Direct the user to author it in UiPath Studio."
            )
        else:
            tmpl = CATEGORY_USE_WHEN_TEMPLATE.get(
                category, "User wants to perform {label}."
            )
            entry["use_when"] = tmpl.format(label=label)
        changed = True

    # _routing_review_needed — set to True for any entry whose description
    # or use_when was just seeded (i.e. has the placeholder shape). Don't
    # overwrite a False (locked-by-human) marker.
    if changed and entry.get("_routing_review_needed") is None:
        entry["_routing_review_needed"] = True

    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="report changes; don't write")
    args = parser.parse_args()

    doc_names = _load_doc_names()
    total_changed = 0
    total_entries = 0
    per_file: list[tuple[str, int, int]] = []

    for jf in sorted(ANNOT_DIR.glob("*.json")):
        category = FILE_TO_CATEGORY.get(jf.name)
        if category is None:
            print(f"  [SKIP] no category mapping for {jf.name}", file=sys.stderr)
            continue
        d = json.loads(jf.read_text(encoding="utf-8"))
        n_changed = 0
        n_total = 0
        for name, entry in (d.get("activities") or {}).items():
            if not isinstance(entry, dict):
                continue
            n_total += 1
            if _seed_entry(name, entry, category, doc_names):
                n_changed += 1
        if n_changed and not args.dry_run:
            jf.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        per_file.append((jf.name, n_changed, n_total))
        total_changed += n_changed
        total_entries += n_total

    print(f"Routing metadata seed{' (dry-run)' if args.dry_run else ''}:")
    for fname, chg, tot in per_file:
        print(f"  {fname}: {chg}/{tot} entries seeded")
    print(f"Totals: changed={total_changed}  entries={total_entries}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
