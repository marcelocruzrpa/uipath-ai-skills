"""Shared helpers for activity generators — constants, escaping, UUID, and type normalization.

Extracted from generate_activities.py. These utilities are used across all
activity generator modules.
"""

import uuid
import re

from utils import (
    escape_xml_attr,
    escape_vb_expr,
    generate_uuid,
    normalize_selector_quotes,
    detect_browser_type,
    TYPE_MAP_BASE,
)


# ---------------------------------------------------------------------------
# Default HintSize per activity type (from golden Studio 24.10 exports)
# ---------------------------------------------------------------------------
HINT_SIZES = {
    "NTypeInto": "1058,250",
    "NClick": "1058,198",
    "NGetText": "416,127",
    "NCheckState": "334,297",
    "NGoToUrl": "416,114",
    "NApplicationCard": "1094,2802",
    "GetRobotCredential": "416,171",
    "LogMessage": "1058,179",
    "Throw": "416,118",
    "InvokeWorkflowFile": "400,100",
    "Pick": "1058,1060",
    "PickBranch": "424,986",
    "RetryScope": "382,487",
    "NSelectItem": "400,200",
    "NExtractDataGeneric": "400,200",
    "Assign": "600,175",
    "AddQueueItem": "334,194",
    "MultipleAssign": "400,200",
    "ForEachRow": "600,400",
    "NetHttpRequest": "662,420",
    "TryCatch": "600,400",
    "If": "400,200",
    "GetQueueItem": "334,275",
    "DeserializeJson": "382,163",
    "Switch": "600,702",
    "Sequence": "450,94",
    "Flowchart": "600,657",
    "FlowDecision": "60,60",
    "ReadPDFText": "797,59",
    "ReadPDFWithOCR": "334,131",
    "SendMail": "600,300",
    "AppendRange": "450,139",
    "BulkAddQueueItems": "450,229",
    "RemoveDataColumn": "450,223",
}


def _hs(activity_type: str) -> str:
    """Return sap:VirtualizedContainerService.HintSize attribute string."""
    size = HINT_SIZES.get(activity_type, "400,200")
    return f'sap:VirtualizedContainerService.HintSize="{size}"'


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _uuid() -> str:
    """Generate a random UUID. Delegates to utils.generate_uuid()."""
    return generate_uuid()


def _escape_xml_attr(s: str) -> str:
    """Escape for XML attribute values. Delegates to utils.escape_xml_attr()."""
    return escape_xml_attr(s)


def _escape_vb_expr(s: str) -> str:
    """Escape VB expression for XML. Delegates to utils.escape_vb_expr()."""
    return escape_vb_expr(s)


def _normalize_selector_quotes(selector: str) -> str:
    """Normalize selector quotes. Delegates to utils.normalize_selector_quotes()."""
    return normalize_selector_quotes(selector)


# Map of invalid x: array types to their correct CLR-prefixed equivalents.
# The x: (XAML language) namespace has no array support.
# Correct prefix is s: -> xmlns:s="clr-namespace:System;assembly=System.Private.CoreLib"
_ARRAY_TYPE_FIXES = {
    "x:String[]": "s:String[]",
    "x:Int32[]": "s:Int32[]",
    "x:Boolean[]": "s:Boolean[]",
    "x:Double[]": "s:Double[]",
    "x:Int64[]": "s:Int64[]",
    "x:Object[]": "s:Object[]",
    "x:Byte[]": "s:Byte[]",
}

def _normalize_type_arg(type_arg: str) -> str:
    """Normalize x:TypeArguments value -- fix unresolved shortnames and invalid array types.

    Handles three classes of issues:
    1. Unresolved shortnames from specs (e.g. "Dictionary" -> "scg:Dictionary(x:String, x:Object)")
    2. Invalid x: array types (e.g. "x:String[]" -> "s:String[]")
    3. Plugin type mappings (e.g. "FormTaskData" -> "upaf:FormTaskData")
    """
    if type_arg in TYPE_MAP_BASE:
        return TYPE_MAP_BASE[type_arg]
    # Check plugin type mappings
    try:
        from plugin_loader import get_type_mappings
        plugin_types = get_type_mappings()
        if type_arg in plugin_types:
            return plugin_types[type_arg]
    except ImportError:
        pass
    return _ARRAY_TYPE_FIXES.get(type_arg, type_arg)
