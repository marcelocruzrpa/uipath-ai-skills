"""Shared constants — regex patterns, enum sets, fix maps used across lint modules."""

import re

# --- Pre-compiled regex patterns (avoid recompilation per lint call) ---
_RE_INVOKE_BLOCK = re.compile(
    r'<ui:InvokeWorkflowFile[^>]*WorkflowFileName="([^"]*)"[^>]*>.*?</ui:InvokeWorkflowFile>',
    re.DOTALL,
)
_RE_INVOKE_ARGS = re.compile(
    r'<ui:InvokeWorkflowFile\.Arguments>(.*?)</ui:InvokeWorkflowFile\.Arguments>',
    re.DOTALL,
)
_RE_XKEY = re.compile(r'x:Key="([^"]*)"')
_RE_BINDING_DIRECTION = re.compile(
    r'<(?:In|Out|InOut)Argument\s+x:TypeArguments="([^"]*)"\s+x:Key="([^"]*)"'
)
_RE_XPROPERTY = re.compile(
    r'<x:Property\s+Name="([^"]*)"\s+Type="(?:In|Out|InOut)Argument\(([^)]*)\)"'
)
_RE_VARIABLE_DECL = re.compile(r'<Variable\s[^>]*Name="([^"]*)"')
_RE_SCOPE_GUID = re.compile(r'NApplicationCard[^>]*ScopeGuid="([^"]*)"')
_RE_SCOPE_ID = re.compile(r'ScopeIdentifier="([^"]*)"')
_RE_IDREF = re.compile(r'WorkflowViewState\.IdRef="([^"]*)"')
_RE_DISPLAY_NAME = re.compile(r'DisplayName="([^"]*)"')
_RE_WORKFLOW_FILENAME = re.compile(r'WorkflowFileName="([^"]*)"')
_RE_CATCH_TYPE = re.compile(r'<Catch\s+x:TypeArguments="([^"]*)"')
_RE_HTTPCLIENT_BLOCK = re.compile(
    r'(<ui:HttpClient[\s>][^>]*>)(.*?)</ui:HttpClient>', re.DOTALL
)
_RE_NSELECTITEM_BLOCK = re.compile(r'<uix:NSelectItem\b([^>]*)/?>')
_RE_CONFIG_KEYS_SUMMARY = re.compile(r'Config\.xlsx keys referenced: (.+?)\.')
_RE_COMMENT_OUT_BLOCK = re.compile(
    r'<ui:CommentOut[\s>].*?</ui:CommentOut>', re.DOTALL
)
_RE_XPROPERTY_NAME = re.compile(r'<x:Property\b[^>]*Name="([^"]*)"')


# --- Namespace constants ---
NS = {
    "": "http://schemas.microsoft.com/netfx/2009/xaml/activities",
    "x": "http://schemas.microsoft.com/winfx/2006/xaml",
    "sap": "http://schemas.microsoft.com/netfx/2009/xaml/activities/presentation",
    "sap2010": "http://schemas.microsoft.com/netfx/2010/xaml/activities/presentation",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "ui": "http://schemas.uipath.com/workflow/activities",
    "uix": "http://schemas.uipath.com/workflow/activities/uix",
    "scg": "clr-namespace:System.Collections.Generic;assembly=System.Private.CoreLib",
    "sco": "clr-namespace:System.Collections.ObjectModel;assembly=System.Private.CoreLib",
}

# Required xmlns for all UiPath XAML
REQUIRED_XMLNS = {"x", "sap", "sap2010", "mc"}

# Activity prefix -> required xmlns URI (subset of common ones)
PREFIX_TO_XMLNS = {
    "ui": "http://schemas.uipath.com/workflow/activities",
    "uix": "http://schemas.uipath.com/workflow/activities/uix",
    "umab": "clr-namespace:UiPath.Mail.Activities.Business;assembly=UiPath.Mail.Activities",
    "isactr": "http://schemas.uipath.com/workflow/integration-service-activities/isactr",
    # "upaf" (Tasks) -- loaded via plugin_loader
}

# Activities that must have IdRef
NEEDS_IDREF = {
    "Sequence", "Flowchart", "StateMachine", "State", "Transition",
    "If", "TryCatch", "Catch", "While", "DoWhile", "Switch", "ForEach",
    "Assign", "Rethrow", "Throw",
    # ui: prefixed (matched by local name after strip)
    "LogMessage", "InvokeWorkflowFile", "Comment", "ForEachRow",
    "MultipleAssign", "RetryScope", "AddQueueItem", "GetQueueItem",
    "SetTransactionStatus", "FilterDataTable", "GetRobotAsset",
    "ReadRange", "WriteRange", "WriteCell",
    # uix: prefixed
    "NApplicationCard", "NClick", "NTypeInto", "NGoToUrl", "NSelectItem",
    "NCheckState", "NGetText", "NGetUrl",
    # Tasks (CreateFormTask, WaitForFormTaskAndResume) -- loaded via plugin_loader
    # HTTP
    "HttpClient",
    # File system
    "CopyFile", "MoveFile", "DeleteFileX", "CreateDirectory", "PathExists",
    # Invoke
    "InvokeCode", "InvokeMethod",
}

# --- Plugin system: merge plugin-registered namespaces and activities ---
from plugin_loader import load_plugins, get_extra_namespaces, get_extra_known_activities, get_extra_key_activities
load_plugins()
PREFIX_TO_XMLNS.update(get_extra_namespaces())
NEEDS_IDREF.update(get_extra_known_activities())
# Note: key_activities list (for DisplayName checks) is merged at call site in lint_display_names


# Exception type ordering: most specific → least specific
EXCEPTION_SPECIFICITY = {
    "ui:BusinessRuleException": 1,
    "s:ApplicationException": 2,
    "s:TimeoutException": 2,
    "s:NullReferenceException": 2,
    "s:ArgumentException": 2,
    "s:FormatException": 2,
    "s:IO.IOException": 2,
    "s:Net.WebException": 2,
    "s:InvalidOperationException": 2,
    "s:Exception": 10,  # catch-all, must be last
}


# --- Enum/fix constants used by hallucination lints ---

VALID_EMPTY_FIELD_MODES = {"None", "SingleLine", "MultiLine"}

EMPTY_FIELD_MODE_FIXES = {
    "Clear": "SingleLine",
    "clear": "SingleLine",
    "Empty": "SingleLine",
    "empty": "SingleLine",
    "Reset": "SingleLine",
    "ClearField": "SingleLine",
    "ClearAll": "SingleLine",
    "Single": "SingleLine",
    "Multi": "MultiLine",
}

VALID_ELEMENT_TYPES = {
    "Button", "CheckBox", "Document", "DropDown", "Group",
    "Image", "InputBox", "InputBoxPassword", "List", "ListItem",
    "Menu", "MenuItem", "None", "ProgressBar", "RadioButton", "Slider",
    "Tab", "Table", "Text", "ToolBar", "ToolTip", "Tree", "TreeItem", "Window",
}

ELEMENT_TYPE_FIXES = {
    "DataGrid": "Table",
    "Datagrid": "Table",
    "datagrid": "Table",
    "Grid": "Table",
    "TextBox": "InputBox",
    "Textbox": "InputBox",
    "InputBoxText": "InputBox",
    "Edit": "InputBox",
    "Password": "InputBoxPassword",
    "Select": "DropDown",
    "ComboBox": "DropDown",
    "Combobox": "DropDown",
    "Combo": "DropDown",
    "Link": "Text",
    "Anchor": "Text",
    "Hyperlink": "Text",
    "Dialog": "Window",
    "Label": "Text",
    "Span": "Text",
}

# Activities with "X" suffix that do NOT support ContinueOnError
X_ACTIVITIES_NO_CONTINUE_ON_ERROR = {
    "DeleteFileX", "ForEachFileX",
}
