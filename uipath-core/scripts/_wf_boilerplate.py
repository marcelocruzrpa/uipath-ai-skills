"""XML boilerplate builders for generate_workflow.

Extracted from generate_workflow.py to reduce file size.
"""

from utils import TYPE_MAP_BASE, escape_xml_attr as _escape_xml_attr
from _wf_types import DIRECTION_MAP, _normalize_argument_type


# ---------------------------------------------------------------------------
# XML boilerplate
# ---------------------------------------------------------------------------

def _build_namespaces(has_ui: bool, has_datatable: bool, has_securestring: bool = False,
                      has_http: bool = False,
                      extra_namespaces: dict[str, str] | None = None) -> str:
    """Build xmlns block with Option B namespace strategy.

    Key rule: any workflow with DataTable args gets sd=Data (framework compat).
    - UI only (no DataTable): sd=Drawing, sd1=Drawing.Primitives (matches Studio)
    - UI + DataTable: sd=Data, sdd=Drawing, sdd1=Drawing.Primitives (framework compat)
    - Non-UI: sd=Data

    Args:
        extra_namespaces: Optional dict of {prefix: uri} for plugin-registered
                          namespaces (e.g., upaf for Tasks, ucas for SAP).
    """
    if has_ui and has_datatable:
        # DataTable crosses framework boundary → sd must be Data
        # Drawing remapped to sdd/sdd1 (generator output post-processed)
        sd = ('  xmlns:sd="clr-namespace:System.Data;assembly=System.Data.Common"\n'
              '  xmlns:sdd="clr-namespace:System.Drawing;assembly=System.Drawing.Common"\n'
              '  xmlns:sdd1="clr-namespace:System.Drawing;assembly=System.Drawing.Primitives"\n')
    elif has_ui:
        # No DataTable → sd=Drawing matches Studio export convention
        sd = ('  xmlns:sd="clr-namespace:System.Drawing;assembly=System.Drawing.Common"\n'
              '  xmlns:sd1="clr-namespace:System.Drawing;assembly=System.Drawing.Primitives"\n')
    else:
        sd = '  xmlns:sd="clr-namespace:System.Data;assembly=System.Data.Common"\n'

    ss = '  xmlns:ss="clr-namespace:System.Security;assembly=System.Private.CoreLib"\n' if has_securestring else ''
    uix = '  xmlns:uix="http://schemas.uipath.com/workflow/activities/uix"\n' if has_ui else ''

    # HTTP activities (NetHttpRequest) require uwah: and uwahm: namespaces
    uwah = ''
    if has_http:
        uwah = ('  xmlns:uwah="clr-namespace:UiPath.Web.Activities.Http;assembly=UiPath.Web.Activities"\n'
                '  xmlns:uwahm="clr-namespace:UiPath.Web.Activities.Http.Models;assembly=UiPath.Web.Activities"\n')

    # Plugin-registered namespaces (Tasks, SAP, etc.)
    extra = ''
    if extra_namespaces:
        for prefix, uri in sorted(extra_namespaces.items()):
            extra += f'  xmlns:{prefix}="{uri}"\n'

    return (
        '  xmlns="http://schemas.microsoft.com/netfx/2009/xaml/activities"\n'
        '  xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"\n'
        '  xmlns:s="clr-namespace:System;assembly=System.Private.CoreLib"\n'
        '  xmlns:sap="http://schemas.microsoft.com/netfx/2009/xaml/activities/presentation"\n'
        '  xmlns:sap2010="http://schemas.microsoft.com/netfx/2010/xaml/activities/presentation"\n'
        '  xmlns:scg="clr-namespace:System.Collections.Generic;assembly=System.Private.CoreLib"\n'
        '  xmlns:sco="clr-namespace:System.Collections.ObjectModel;assembly=System.Private.CoreLib"\n'
        + sd + ss +
        '  xmlns:ui="http://schemas.uipath.com/workflow/activities"\n'
        + uix + uwah + extra +
        '  xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml">\n'
    )


def _build_arguments_xml(arguments: list, type_map: dict = None,
                         all_xmlns_prefixes: tuple = None) -> str:
    """Build x:Members block from argument definitions.

    Args:
        arguments: List of argument dicts with name, direction, type.
        type_map: Optional type map override. Defaults to TYPE_MAP_BASE.
        all_xmlns_prefixes: Tuple of all known xmlns prefixes (core + plugin).
            Passed through to _normalize_argument_type.
    """
    if not arguments:
        return ""
    tmap = type_map or TYPE_MAP_BASE
    lines = ["  <x:Members>"]
    for arg in arguments:
        name = arg["name"]
        direction = DIRECTION_MAP[arg["direction"]]
        raw_type = arg["type"]
        xaml_type = _normalize_argument_type(raw_type, tmap, all_xmlns_prefixes)
        lines.append(f'    <x:Property Name="{name}" Type="{direction}({xaml_type})" />')
    lines.append("  </x:Members>")
    return "\n".join(lines)


def _build_variables_xml(variables: list, indent: str = "        ", type_map: dict = None) -> str:
    """Build Sequence.Variables block."""
    if not variables:
        return ""
    lines = [f"{indent}<Sequence.Variables>"]
    for var in variables:
        name = var["name"]
        raw_type = var["type"]
        xaml_type = (type_map or TYPE_MAP_BASE).get(raw_type, raw_type)
        default = var.get("default", "")
        default_attr = f' Default="{_escape_xml_attr(default)}"' if default else ""
        lines.append(f'{indent}  <Variable x:TypeArguments="{xaml_type}" Name="{name}"{default_attr} />')
    lines.append(f"{indent}</Sequence.Variables>")
    return "\n".join(lines)
