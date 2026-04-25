"""Data-driven generator engine for UiPath activities.

Reads annotation entries from references/annotations/*.json and produces
XAML for activities that do not have hand-written gen_* functions.

Hand-written functions always take priority; this module is only invoked as
a fallback when no matching entry exists in generate_workflow._REGISTRY.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from ._helpers import _hs, _escape_xml_attr
from ._xml_utils import _selector_xml


# ---------------------------------------------------------------------------
# Root scope sentinel — kept in sync with generate_workflow.ROOT_SCOPE_SENTINEL.
# Duplicated here so _data_driven.py can be imported without pulling in the
# top-level generator module (which depends on this one).
# ---------------------------------------------------------------------------
_ROOT_SCOPE_SENTINEL = "00000000-0000-0000-0000-000000000000"


# ---------------------------------------------------------------------------
# Prefix → namespace URI table for inline xmlns binding.
#
# When an annotation entry's element_tag uses a prefix that is *not* declared
# by the standard project Main.xaml header (see _STANDARD_XMLNS_PREFIXES below),
# the dispatcher emits an inline ``xmlns:<prefix>="..."`` declaration on the
# opening tag of the activity element. This keeps generated fragments XML-valid
# in any host document, even when the host's <Activity> root has not been
# pre-augmented via scaffold_project._ensure_xmlns().
#
# Rationale: Studio's hand-authored XAML always declares package-specific
# prefixes (``ueawb``, ``uasd``, ``uascw``, ``upap`` …) at the file root.
# When our scaffolds inject backfilled activities into a Sequence body of a
# pre-existing Main.xaml that lacks those declarations, the file becomes ill-
# formed. Emitting xmlns inline on the activity tag is valid XAML and means
# every dispatched activity is self-contained — no cross-file coupling.
#
# Source: harvested from every ``xmlns:<prefix>="..."`` declaration across
# uipath-core/references/studio-ground-truth/**/*.xaml and the version-profile
# packages.
# ---------------------------------------------------------------------------
_KNOWN_PREFIX_NAMESPACES: dict[str, str] = {
    # UiPath core / uix
    "ui": "http://schemas.uipath.com/workflow/activities",
    "uix": "http://schemas.uipath.com/workflow/activities/uix",
    # CV / OCR shared 'p' prefix — Studio rebinds per-file; default to CV here
    # since it is the more common usage in our annotation corpus.
    "p": "http://schemas.uipath.com/workflow/activities/cv",
    # System.Activities sub-packages
    "uas": "clr-namespace:UiPath.Activities.System;assembly=UiPath.System.Activities",
    "uast": "clr-namespace:UiPath.Activities.System.Text;assembly=UiPath.System.Activities",
    "uasd": "clr-namespace:UiPath.Activities.System.Date;assembly=UiPath.System.Activities",
    "uasf": "clr-namespace:UiPath.Activities.System.FileOperations;assembly=UiPath.System.Activities",
    "uasj": "clr-namespace:UiPath.Activities.System.Jobs;assembly=UiPath.System.Activities",
    "uasom": "clr-namespace:UiPath.Activities.System.Orchestrator.Mail;assembly=UiPath.System.Activities",
    "uascw": "clr-namespace:UiPath.Activities.System.Compression.Workflow;assembly=UiPath.System.Activities",
    "ucap": "clr-namespace:UiPath.Core.Activities.ProcessTracking;assembly=UiPath.System.Activities",
    "ucas": "clr-namespace:UiPath.Core.Activities.Storage;assembly=UiPath.System.Activities",
    # Excel
    "ue": "clr-namespace:UiPath.Excel;assembly=UiPath.Excel.Activities",
    "ueab": "clr-namespace:UiPath.Excel.Activities.Business;assembly=UiPath.Excel.Activities",
    "ueawb": "clr-namespace:UiPath.Excel.Activities.Windows.Business;assembly=UiPath.Excel.Activities",
    # Mail
    "um": "clr-namespace:UiPath.Mail;assembly=UiPath.Mail.Activities",
    "umab": "clr-namespace:UiPath.Mail.Activities.Business;assembly=UiPath.Mail.Activities",
    "umae": "clr-namespace:UiPath.Mail.Activities.Enums;assembly=UiPath.Mail.Activities",
    "umai": "clr-namespace:UiPath.Mail.Activities.IMAP;assembly=UiPath.Mail.Activities",
    "umao": "clr-namespace:UiPath.Mail.Activities.Outlook;assembly=UiPath.Mail.Activities",
    "umla": "clr-namespace:UiPath.Mail.LotusNotes.Activities;assembly=UiPath.Mail.Activities",
    "umabh": "clr-namespace:UiPath.Mail.Activities.Business.HtmlEditor;assembly=UiPath.Mail.Activities",
    "usau": "clr-namespace:UiPath.Shared.Activities.Utils;assembly=UiPath.Mail.Activities",
    # CV cache container + System.ComponentModel
    "uc": "clr-namespace:UiPath.CV;assembly=UiPath.CV",
    "sc": "clr-namespace:System.ComponentModel;assembly=System.ComponentModel.TypeConverter",
    # PDF
    "upap": "clr-namespace:UiPath.PDF.Activities.PDF;assembly=UiPath.PDF.Activities",
    # Testing
    "uta": "clr-namespace:UiPath.Testing.Activities;assembly=UiPath.Testing.Activities",
    "utam": "clr-namespace:UiPath.Testing.Activities.Mocks;assembly=UiPath.Testing.Activities",
    "utat": "clr-namespace:UiPath.Testing.Activities.TestData;assembly=UiPath.Testing.Activities",
    # UIAutomationNext models
    "uuam": "clr-namespace:UiPath.UIAutomationNext.Activities.Models;assembly=UiPath.UIAutomationNext.Activities",
    # Web
    "uwah": "clr-namespace:UiPath.Web.Activities.Http;assembly=UiPath.Web.Activities",
    "uwaj": "clr-namespace:UiPath.Web.Activities.JSON;assembly=UiPath.Web.Activities",
    # System.Activities builtins
    "sa": "clr-namespace:System.Activities;assembly=System.Activities",
    # System.Data alt prefix (used by NExtractDataGeneric / persistence)
    "sd2": "clr-namespace:System.Data;assembly=System.Data.Common",
}

# Prefixes always declared by the canonical project Main.xaml scaffold header.
# Element tags using these prefixes never need inline xmlns binding.
_STANDARD_XMLNS_PREFIXES: frozenset[str] = frozenset({
    "x",        # XAML core (always)
    "mc",       # markup-compatibility
    "sap",      # WF presentation 2009
    "sap2010",  # WF presentation 2010
    "s",        # System
    "scg",      # System.Collections.Generic
    "sco",      # System.Collections.ObjectModel
    "sd",       # System.Data / System.Drawing (handled per-template)
    "ui",       # UiPath core activities
})


# ---------------------------------------------------------------------------
# Public exceptions
# ---------------------------------------------------------------------------

class WizardOnlyActivityError(Exception):
    """Raised when gen_from_annotation is called on a wizard-only activity stub.

    Wizard-only activities have ``_unsupported_reason: "wizard-only"`` in the
    annotations corpus and cannot be generated programmatically — they require
    UiPath Studio's interactive wizard to configure.
    """


class MissingScopeError(ValueError):
    """Raised when a scope-requiring activity is generated outside its scope wrapper.

    Currently fires for SAP activities (element_tag starts with ``uix:NSAP``)
    when ``scope_id`` is falsy or equal to the root-scope sentinel. Such
    activities must be nested inside an ``NSAPLogon`` / ``NSAPLogoff`` container
    so their ``ScopeIdentifier`` attribute can bind to a live SAP session.
    """


class ReviewNeededError(Exception):
    """Raised when gen_from_annotation targets a heuristically-backfilled entry
    flagged ``_review_needed: true`` and no opt-in override is set.

    Opt-in via env var ``UIPATH_ALLOW_REVIEW_NEEDED`` (any truthy value) or
    the ``--allow-review-needed`` CLI flag routed through that env var.
    """


def _review_needed_opt_in() -> bool:
    """Return True when the UIPATH_ALLOW_REVIEW_NEEDED opt-in is active."""
    val = os.environ.get("UIPATH_ALLOW_REVIEW_NEEDED", "")
    if not val:
        return False
    return val.strip().lower() not in ("0", "false")


_PREFIX_REF_RE = re.compile(r"\b([a-zA-Z][a-zA-Z0-9_]*):[A-Za-z_]")


def _collect_referenced_prefixes(*texts: str) -> list[str]:
    """Return the de-duplicated, declaration-order list of prefix tokens
    referenced anywhere in ``texts`` (element tag, fixed-attr values, ...).

    Standard prefixes are filtered out; only prefixes that need an inline
    xmlns binding survive. Order is preserved so the resulting xmlns
    declarations are stable across invocations (helps test-snapshot diffs).
    """
    seen: dict[str, None] = {}
    for text in texts:
        if not text:
            continue
        for m in _PREFIX_REF_RE.finditer(text):
            pfx = m.group(1)
            if pfx in _STANDARD_XMLNS_PREFIXES:
                continue
            if pfx in _KNOWN_PREFIX_NAMESPACES and pfx not in seen:
                seen[pfx] = None
    return list(seen)


def _xmlns_decls_for_tag(element_tag: str, *extra_texts: str) -> str:
    """Return inline ``xmlns:<prefix>="..."`` declarations needed by element_tag.

    The element tag drives the primary prefix; ``extra_texts`` (fixed-attr
    values, child-element static blocks) are scanned for additional prefix
    references such as ``x:TypeArguments="sd2:DataTable"``.

    A prefix gets an inline binding only when it:
      1. is *not* one of the project Main.xaml standard prefixes
         (``_STANDARD_XMLNS_PREFIXES``), AND
      2. has a known URI in ``_KNOWN_PREFIX_NAMESPACES``.

    Unknown prefixes are silently skipped — the resulting XAML will fail XML
    parse, surfacing the missing mapping in battle tests so we can register it.

    Returns an empty string when no inline binding is needed (the common case
    for ``ui:`` and ``uix:`` activities).
    """
    prefixes = _collect_referenced_prefixes(element_tag, *extra_texts)
    if not prefixes:
        return ""
    return "".join(
        f' xmlns:{p}="{_KNOWN_PREFIX_NAMESPACES[p]}"' for p in prefixes
    )

# ---------------------------------------------------------------------------
# Module-level annotation cache — one load per process
# ---------------------------------------------------------------------------

_ANNOTATIONS_CACHE: dict[str, dict] | None = None


def _load_annotations() -> dict[str, dict]:
    """Load all annotations/*.json files and return a merged activity dict.

    Keys are activity names in canonical lower-case form, e.g. "ntypeinto".
    The raw dict value is the annotation entry for that activity.
    """
    global _ANNOTATIONS_CACHE
    if _ANNOTATIONS_CACHE is not None:
        return _ANNOTATIONS_CACHE

    annotations_dir = (
        Path(__file__).resolve().parent.parent.parent
        / "references" / "annotations"
    )
    merged: dict[str, dict] = {}
    for path in sorted(annotations_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"  [WARN] _data_driven: could not read {path}: {exc}", file=sys.stderr)
            continue
        activities = data.get("activities", {})
        for name, entry in activities.items():
            merged[name.lower()] = entry

    _ANNOTATIONS_CACHE = merged
    return merged


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def gen_from_annotation(
    activity_name: str,
    spec_args: dict[str, Any],
    id_ref: str,
    scope_id: str,
    indent: str = "            ",
    obj_repo: dict | None = None,
) -> str:
    """Generate XAML for an activity described in the annotations corpus.

    Args:
        activity_name: Lower-case generator name, e.g. "nsapcalltransaction".
        spec_args:     Dict of arguments from the JSON workflow spec.
        id_ref:        IdRef string for WorkflowViewState.
        scope_id:      ScopeIdentifier GUID from the parent NApplicationCard
                       (or containing NSAPLogon scope).  Pass a non-empty
                       string when the activity is known to be nested inside an
                       NSAPLogon/NSAPLogoff scope; pass an empty string or
                       ``None`` when the scope is absent.
        indent:        Base indentation string (spaces).
        obj_repo:      Optional Object Repository reference dict.

    Returns:
        XAML string for the activity.

    Raises:
        KeyError:   No annotation entry found for activity_name.
        ValueError: Unsupported child_element type encountered.

    SAP scope enforcement
    ~~~~~~~~~~~~~~~~~~~~~~
    Activities whose ``element_tag`` starts with ``"uix:NSAP"`` must be nested
    inside an ``NSAPLogon``/``NSAPLogoff`` scope in the final XAML so that
    UiPath Studio can bind the ``ScopeIdentifier`` attribute to a live SAP
    session. The function raises :class:`MissingScopeError` when ``scope_id``
    is empty, ``None``, or equal to the root-scope sentinel
    (``00000000-0000-0000-0000-000000000000``) — meaning the activity is being
    emitted at the top level, not inside an SAP scope. Callers must wrap SAP
    activities in an ``NSAPLogon`` container so the parent's ``ScopeGuid``
    propagates to ``scope_id``. Emitting an SAP activity with no valid scope
    used to print a stderr warning and produce bogus XAML; it is now a hard
    failure to prevent silent corruption.
    """
    annotations = _load_annotations()
    entry = annotations.get(activity_name.lower())
    if entry is None:
        raise KeyError(
            f"No annotation entry found for activity '{activity_name}'. "
            "Add an entry to references/annotations/*.json or write a "
            "hand-coded gen_* function."
        )

    if entry.get("_unsupported_reason") == "wizard-only":
        raise WizardOnlyActivityError(
            f"'{activity_name}' is a wizard-only activity and cannot be generated "
            "programmatically. Use UiPath Studio's interactive wizard to configure it."
        )

    if entry.get("_review_needed", False) and not _review_needed_opt_in():
        raise ReviewNeededError(
            f"Activity {activity_name!r} is backfilled and needs human review before "
            "generation. Set UIPATH_ALLOW_REVIEW_NEEDED=1 or pass --allow-review-needed "
            "to opt in."
        )

    element_tag = entry["element_tag"]
    params_meta = entry.get("params", {})
    fixed_attrs = entry.get("fixed_attrs", {})
    child_elements = entry.get("child_elements", {})
    hint_size_key = entry.get("hint_size_key")
    is_sap = element_tag.startswith("uix:NSAP")

    if is_sap and (not scope_id or scope_id == _ROOT_SCOPE_SENTINEL):
        raise MissingScopeError(
            f"SAP activity '{element_tag}' must be nested inside an NSAPLogon or "
            f"NSAPLogoff scope so its ScopeIdentifier binds to a live SAP session. "
            f"Wrap the spec in an NSAPLogon container (which supplies ScopeGuid to "
            f"its children) before emitting this activity."
        )

    # ------------------------------------------------------------------
    # Build attribute string
    # ------------------------------------------------------------------
    attrs_parts: list[str] = []

    # 1. Params (ordered by their declaration order in annotation)
    for param_name, pmeta in params_meta.items():
        attr_name = pmeta.get("attr")
        if not attr_name:
            # Types like selector_param, obj_repo_param, id_ref, scope_id
            # are handled specially below.
            continue

        ptype = pmeta.get("type", "string")
        # id_ref and scope_id are injected from call-site args, not spec_args
        if ptype == "id_ref":
            attrs_parts.append(f'{attr_name}="{id_ref}"')
            continue
        if ptype == "scope_id":
            attrs_parts.append(f'{attr_name}="{scope_id}"')
            continue

        value = spec_args.get(param_name)
        if value is None:
            default = pmeta.get("default")
            if default is not None:
                # Skip emitting default values explicitly (Studio applies them)
                continue
            # No value, no default — skip (required check is caller's job)
            continue

        escape = pmeta.get("escape")
        bracket_wrap = pmeta.get("bracket_wrap", False)

        if escape == "xml":
            value_str = _escape_xml_attr(str(value))
        elif bracket_wrap:
            value_str = f"[{value}]"
        else:
            value_str = str(value)

        attrs_parts.append(f'{attr_name}="{value_str}"')

    # 2. HintSize (from hint_size_key or element simple-name)
    hs_key = hint_size_key or element_tag.split(":")[-1]
    attrs_parts.append(_hs(hs_key))

    # 3. Fixed attrs
    for fa_name, fa_val in fixed_attrs.items():
        attrs_parts.append(f'{fa_name}="{fa_val}"')

    attrs_str = " ".join(attrs_parts)

    # ------------------------------------------------------------------
    # Build child elements XAML
    # ------------------------------------------------------------------
    i = indent
    i2 = i + "  "
    i3 = i2 + "  "

    children_xml_parts: list[str] = []

    # Find selector param (if any) to build the .Target child
    selector_value: str | None = None
    for param_name, pmeta in params_meta.items():
        if pmeta.get("type") == "selector_param":
            selector_value = spec_args.get(param_name)
            break

    for child_key, child_meta in child_elements.items():
        child_type = child_meta.get("type")
        # Child elements belong to the parent activity's namespace. Default
        # "uix:" matches UIAutomation activities; other modules (ui:, upap:,
        # uwaj:, ...) supply tag_prefix explicitly.
        tag_prefix = child_meta.get("tag_prefix", "uix:")
        tag_name = f"{tag_prefix}{child_key}"

        if child_type == "selector":
            sel = selector_value or ""
            target_xml = _selector_xml(sel, obj_repo=obj_repo)
            children_xml_parts.append(
                f"{i2}<{tag_name}>\n{i3}{target_xml}\n{i2}</{tag_name}>"
            )

        elif child_type in ("static_block", "literal"):
            raw_content = child_meta.get("content") or ""
            if raw_content:
                # Indent the raw content block
                indented = "\n".join(f"{i3}{line}" if line.strip() else line
                                     for line in raw_content.split("\n"))
                children_xml_parts.append(
                    f"{i2}<{tag_name}>\n{indented}\n{i2}</{tag_name}>"
                )

        elif child_type == "activity_action":
            arg_type = child_meta.get("arg_type", "x:Object")
            arg_name = child_meta.get("arg_name", "WSSessionData")
            i4 = i3 + "  "
            i5 = i4 + "  "
            i6 = i5 + "  "
            children_xml_parts.append(
                f"{i2}<{tag_name}>\n"
                f"{i3}<ActivityAction x:TypeArguments=\"{arg_type}\">\n"
                f"{i4}<ActivityAction.Argument>\n"
                f"{i5}<DelegateInArgument x:TypeArguments=\"{arg_type}\" Name=\"{arg_name}\" />\n"
                f"{i4}</ActivityAction.Argument>\n"
                f"{i4}<Sequence DisplayName=\"Do\" />\n"
                f"{i3}</ActivityAction>\n"
                f"{i2}</{tag_name}>"
            )

        elif child_type == "list":
            # Optional tag_prefix overrides the default "uix:" namespace prefix.
            # Use when the element belongs to "ui:" or another namespace.
            tag_prefix = child_meta.get("tag_prefix", "uix:")
            list_tag = f"{tag_prefix}{child_key}"
            # items_key allows the annotation to specify a custom spec_args key;
            # defaults to the child_key lowercased (e.g. "invokecode.arguments").
            items_key = child_meta.get("items_key") or child_key.lower()
            items = spec_args.get(items_key) or []
            # empty_content: a literal XML snippet to embed when the list is
            # empty (no items supplied).  When absent, the wrapper self-closes.
            empty_content = child_meta.get("empty_content")
            if items:
                item_tag = child_meta.get("item_tag", "x:String")
                item_lines = "\n".join(
                    f"{i3}<{item_tag}>{_escape_xml_attr(str(item))}</{item_tag}>"
                    for item in items
                )
                children_xml_parts.append(
                    f"{i2}<{list_tag}>\n{item_lines}\n{i2}</{list_tag}>"
                )
            elif empty_content:
                children_xml_parts.append(
                    f"{i2}<{list_tag}>\n{i3}{empty_content}\n{i2}</{list_tag}>"
                )
            else:
                children_xml_parts.append(f"{i2}<{list_tag} />")

        elif child_type == "hint_size":
            pass  # _hs() is already emitted as an attribute; skip child

        elif child_type == "sequence":
            # Minimal empty Sequence placeholder. The IdRef is derived from the
            # parent activity's id_ref plus the child_key to stay unique within
            # the file. Callers that need to embed real content into this body
            # should use a hand-coded gen_* function instead.
            display_name = child_meta.get("display_name", "Do")
            seq_key = child_key.replace(".", "_").replace(":", "_")
            seq_idref = f"Sequence_{id_ref}_{seq_key}"
            children_xml_parts.append(
                f"{i2}<{tag_name}>\n"
                f"{i3}<Sequence DisplayName=\"{display_name}\" "
                f"sap2010:WorkflowViewState.IdRef=\"{seq_idref}\" />\n"
                f"{i2}</{tag_name}>"
            )

        else:
            raise ValueError(
                f"_data_driven: unsupported child_element type '{child_type}' "
                f"in '{activity_name}'.{child_key}. "
                "Extend _data_driven.py to handle this type."
            )

    # ------------------------------------------------------------------
    # Assemble final XAML
    # ------------------------------------------------------------------
    # Inline xmlns binding for any non-standard prefix referenced by the
    # element tag, fixed_attr values, or static child-element blocks. This
    # lets the dispatcher emit XAML that parses standalone — without the host
    # Main.xaml having to pre-declare every package-specific prefix at root.
    fixed_value_blob = " ".join(str(v) for v in fixed_attrs.values())
    static_block_blob = " ".join(
        str(c.get("content") or "") for c in child_elements.values()
        if isinstance(c, dict)
    )
    xmlns_inline = _xmlns_decls_for_tag(element_tag, fixed_value_blob, static_block_blob)

    if not children_xml_parts:
        return f"{i}<{element_tag}{xmlns_inline} {attrs_str} />"

    children_block = "\n".join(children_xml_parts)
    return (
        f"{i}<{element_tag}{xmlns_inline} {attrs_str}>\n"
        f"{children_block}\n"
        f"{i}</{element_tag}>"
    )
