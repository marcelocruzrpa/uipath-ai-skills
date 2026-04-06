"""Spec validation for generate_workflow.

Extracted from generate_workflow.py to reduce file size.
Validation functions accept the registry and child keys as parameters
to avoid circular imports with generate_workflow.py.
"""

from utils import TYPE_MAP_BASE, KNOWN_XMLNS_PREFIXES
from _wf_types import _check_type_field


def _validate_activities(activities: list, path: str, errors: list,
                         registry: dict, log_message_required: tuple,
                         all_child_keys: tuple):
    """Recursively validate activity specs — structure + per-generator required args.

    Args:
        activities: List of activity spec dicts.
        path: JSON path prefix for error messages (e.g. "activities").
        errors: Accumulator list for error strings.
        registry: The _REGISTRY dict mapping gen names to _GenEntry objects.
        log_message_required: Tuple of required arg names for log_message.
        all_child_keys: Tuple of all child key names for recursive traversal.
    """
    for i, act in enumerate(activities):
        loc = f"{path}[{i}]"
        if not isinstance(act, dict):
            errors.append(f"{loc}: must be a JSON object, got {type(act).__name__}")
            continue
        if "gen" not in act:
            errors.append(f"{loc}: missing required field 'gen'")
            continue
        gen = act["gen"]
        if not isinstance(gen, str):
            errors.append(f"{loc}: 'gen' must be a string, got {type(gen).__name__}")
            continue

        # Check per-generator required args (from unified _REGISTRY)
        args = act.get("args", {})
        entry = registry.get(gen)
        required = entry.required if entry else (
            log_message_required if gen in ("log_message", "logmessage") else ()
        )
        if required:
            for arg_key in required:
                if arg_key not in args:
                    errors.append(f"{loc}: gen='{gen}' missing required arg '{arg_key}'")

        # Validate invoke_workflow arguments inner structure
        if gen == "invoke_workflow" and "arguments" in args:
            inv_args = args["arguments"]
            if isinstance(inv_args, dict):
                for arg_key, arg_val in inv_args.items():
                    if isinstance(arg_val, dict):
                        errors.append(
                            f"{loc}: invoke_workflow argument '{arg_key}' is a dict "
                            f"{{direction, type, value}} — must be an array "
                            f"[direction, type, value_expr]. "
                            f'Example: "{arg_key}": ["In", "String", "\\"John\\""]'
                        )
                    elif isinstance(arg_val, (list, tuple)):
                        if len(arg_val) != 3:
                            errors.append(
                                f"{loc}: invoke_workflow argument '{arg_key}' has "
                                f"{len(arg_val)} elements, expected 3: "
                                f"[direction, type, value_expr]"
                            )
                        elif arg_val[0] not in ("In", "Out", "InOut"):
                            errors.append(
                                f"{loc}: invoke_workflow argument '{arg_key}' "
                                f"direction must be In/Out/InOut, got '{arg_val[0]}'"
                            )

        # Recurse into child activity lists
        for key in all_child_keys:
            children = act.get(key, [])
            if children:
                _validate_activities(children, f"{loc}.{key}", errors,
                                     registry, log_message_required, all_child_keys)
        # Switch cases
        for ci, case in enumerate(args.get("cases", [])):
            case_children = case.get("children", [])
            if case_children:
                _validate_activities(case_children, f"{loc}.args.cases[{ci}].children", errors,
                                     registry, log_message_required, all_child_keys)
        # IfElseIf conditions
        for ci, cond in enumerate(args.get("conditions", [])):
            cond_children = cond.get("children", [])
            if cond_children:
                _validate_activities(cond_children, f"{loc}.args.conditions[{ci}].children", errors,
                                     registry, log_message_required, all_child_keys)
        # TryCatch catches
        for ci, catch in enumerate(args.get("catches", [])):
            catch_children = catch.get("children", [])
            if catch_children:
                _validate_activities(catch_children, f"{loc}.args.catches[{ci}].children", errors,
                                     registry, log_message_required, all_child_keys)


def _validate_spec(spec: dict, registry: dict, log_message_required: tuple,
                   all_child_keys: tuple) -> list:
    """Validate JSON spec structure before generation. Returns list of error strings.

    Args:
        spec: The JSON spec dict to validate.
        registry: The _REGISTRY dict mapping gen names to _GenEntry objects.
        log_message_required: Tuple of required arg names for log_message.
        all_child_keys: Tuple of all child key names for recursive traversal.
    """
    errors = []
    if not isinstance(spec, dict):
        errors.append(f"Spec must be a JSON object, got {type(spec).__name__}")
        return errors  # Can't check further

    if "class_name" not in spec:
        errors.append("Missing required field 'class_name'")
    elif not isinstance(spec["class_name"], str) or not spec["class_name"].strip():
        errors.append("'class_name' must be a non-empty string")

    if "activities" not in spec:
        errors.append("Missing required field 'activities'")
    elif not isinstance(spec["activities"], list):
        errors.append("'activities' must be an array")
    else:
        _validate_activities(spec["activities"], "activities", errors,
                             registry, log_message_required, all_child_keys)

    for field in ("arguments", "variables"):
        if field in spec and not isinstance(spec[field], list):
            errors.append(f"'{field}' must be an array if present")

    # --- Argument type validation ---
    _VALID_SHORT_TYPES = set(TYPE_MAP_BASE.keys()) | {"DataTable", "DataRow"}
    _all_xmlns = KNOWN_XMLNS_PREFIXES
    try:
        from plugin_loader import get_type_mappings, get_extra_namespaces
        _VALID_SHORT_TYPES |= set(get_type_mappings().keys())
        plugin_prefixes = tuple(f"{p}:" for p in get_extra_namespaces())
        if plugin_prefixes:
            _all_xmlns = KNOWN_XMLNS_PREFIXES + plugin_prefixes
    except ImportError:
        pass
    if "arguments" in spec and isinstance(spec["arguments"], list):
        for i, arg in enumerate(spec["arguments"]):
            if not isinstance(arg, dict):
                errors.append(f"arguments[{i}]: must be a JSON object")
                continue
            for req in ("name", "direction", "type"):
                if req not in arg:
                    errors.append(f"arguments[{i}]: missing required field '{req}'")
            if "direction" in arg and arg["direction"] not in ("In", "Out", "InOut"):
                errors.append(f"arguments[{i}]: direction must be In/Out/InOut, got '{arg['direction']}'")
            if "type" in arg:
                _check_type_field(arg["type"], f"arguments[{i}]", _VALID_SHORT_TYPES, errors,
                                  all_xmlns_prefixes=_all_xmlns)

    if "variables" in spec and isinstance(spec["variables"], list):
        for i, var in enumerate(spec["variables"]):
            if not isinstance(var, dict):
                errors.append(f"variables[{i}]: must be a JSON object")
                continue
            for req in ("name", "type"):
                if req not in var:
                    errors.append(f"variables[{i}]: missing required field '{req}'")
            if "type" in var:
                _check_type_field(var["type"], f"variables[{i}]", _VALID_SHORT_TYPES, errors,
                                  all_xmlns_prefixes=_all_xmlns)

    return errors
