"""Type mapping and validation helpers for generate_workflow.

Extracted from generate_workflow.py to reduce file size.
"""

import re
from utils import TYPE_MAP_BASE, KNOWN_XMLNS_PREFIXES


# ---------------------------------------------------------------------------
# Direction mapping for XAML argument types
# ---------------------------------------------------------------------------

DIRECTION_MAP = {
    "In": "InArgument",
    "Out": "OutArgument",
    "InOut": "InOutArgument",
}


# ---------------------------------------------------------------------------
# Type mappings (canonical source: utils.TYPE_MAP_BASE)
# ---------------------------------------------------------------------------

def _type_map() -> dict:
    """Get type map. DataTable/DataRow now in TYPE_MAP_BASE (utils.py)."""
    return dict(TYPE_MAP_BASE)


def _normalize_argument_type(raw_type: str, type_map: dict,
                             all_xmlns_prefixes: tuple = None) -> str:
    """Normalize an argument type to its fully-qualified XAML form.

    Catches common LLM mistakes:
    - 'Dictionary(String,Object)' -> 'scg:Dictionary(x:String, x:Object)'
    - 'Dictionary(x:String, x:Object)' -> 'scg:Dictionary(x:String, x:Object)'
    - Already-correct types pass through

    Args:
        raw_type: The raw type string from the spec.
        type_map: Mapping of short type names to XAML types.
        all_xmlns_prefixes: Tuple of all known xmlns prefixes (core + plugin).
            Falls back to KNOWN_XMLNS_PREFIXES if not provided.
    """
    if all_xmlns_prefixes is None:
        all_xmlns_prefixes = KNOWN_XMLNS_PREFIXES

    # Direct map match (shortest path)
    if raw_type in type_map:
        return type_map[raw_type]

    # Normalize Dictionary variants — the #1 hallucinated type
    dict_match = re.match(
        r'^(?:scg:)?Dictionary\s*\(\s*'
        r'(?:x:)?String\s*,\s*(?:x:)?Object\s*\)$',
        raw_type
    )
    if dict_match:
        return "scg:Dictionary(x:String, x:Object)"

    # Normalize bare DataTable / DataRow (missing sd: prefix)
    if raw_type == "DataTable":
        return type_map.get("DataTable", "sd:DataTable")
    if raw_type == "DataRow":
        return type_map.get("DataRow", "sd:DataRow")

    # Reject unknown unprefixed types — they produce invalid XAML
    if raw_type and not any(raw_type.startswith(p) for p in all_xmlns_prefixes):
        valid_shorts = sorted(type_map.keys())
        if "(" in raw_type:
            raise ValueError(
                f"Unprefixed generic type '{raw_type}'. "
                f"Use a TYPE_MAP short form: {valid_shorts}"
            )
        raise ValueError(
            f"Unknown bare type '{raw_type}'. "
            f"Use a prefixed form (e.g. 'sd:DataTable') or a short form: "
            f"{valid_shorts}"
        )

    return raw_type


def _check_type_field(raw_type: str, location: str, valid_shorts: set, errors: list,
                      all_xmlns_prefixes: tuple = None):
    """Validate a type field in a spec, catching hallucinated long-form types.

    Args:
        all_xmlns_prefixes: Optional extended prefix tuple (core + plugin).
            Falls back to KNOWN_XMLNS_PREFIXES if not provided.
    """
    if all_xmlns_prefixes is None:
        all_xmlns_prefixes = KNOWN_XMLNS_PREFIXES
    if not isinstance(raw_type, str) or not raw_type.strip():
        errors.append(f"{location}: 'type' must be a non-empty string")
        return
    # Short forms are always fine (they go through TYPE_MAP)
    if raw_type in valid_shorts:
        return
    # Already-prefixed types are fine (x:String, sd:DataTable, upaf:FormTaskData, etc.)
    if any(raw_type.startswith(p) for p in all_xmlns_prefixes):
        return
    # Catch hallucinated Dictionary long forms
    if re.match(r'(?:scg:)?Dictionary\s*\(', raw_type):
        errors.append(
            f"{location}: type '{raw_type}' is a hallucinated long form. "
            f"Use type='Dictionary' (short form) — the generator maps it to "
            f"scg:Dictionary(x:String, x:Object) automatically."
        )
        return
    # Catch other unprefixed generics
    if "(" in raw_type:
        errors.append(
            f"{location}: type '{raw_type}' looks like an unprefixed generic type. "
            f"Use short-form keys from TYPE_MAP: {sorted(valid_shorts)}"
        )
