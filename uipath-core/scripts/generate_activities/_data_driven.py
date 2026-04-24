"""Data-driven generator engine for UiPath activities.

Reads annotation entries from references/annotations/*.json and produces
XAML for activities that do not have hand-written gen_* functions.

Hand-written functions always take priority; this module is only invoked as
a fallback when no matching entry exists in generate_workflow._REGISTRY.
"""
from __future__ import annotations

import json
import os
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
    if not children_xml_parts:
        return f"{i}<{element_tag} {attrs_str} />"

    children_block = "\n".join(children_xml_parts)
    return (
        f"{i}<{element_tag} {attrs_str}>\n"
        f"{children_block}\n"
        f"{i}</{element_tag}>"
    )
