#!/usr/bin/env python3
"""Generator → Lint integration test.

Generates complete workflows via generate_workflow.py from JSON specs,
then validates the output through validate_xaml to ensure generators
produce lint-clean XAML.

This closes the gap where generators and lint rules are tested separately
but never tested together — a generator regression could produce XAML that
passes generator unit tests but fails lint.

Usage:
    python3 scripts/test_generator_lint_integration.py
    python3 scripts/test_generator_lint_integration.py --verbose
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPTS_DIR.parent
GENERATOR = SCRIPTS_DIR / "generate_workflow.py"
VALIDATOR = SCRIPTS_DIR / "validate_xaml"


# ---------------------------------------------------------------------------
# Test specs — representative workflows exercising major generator paths
# ---------------------------------------------------------------------------

SPECS = {
    "simple_log": {
        "class_name": "Test_SimpleLog",
        "arguments": [],
        "variables": [],
        "activities": [
            {"gen": "log_message", "args": {"message_expr": "\"[START] Test\"", "level": "Info"}},
            {"gen": "log_message", "args": {"message_expr": "\"[END] Test\"", "level": "Info"}},
        ]
    },

    "ui_automation_login": {
        "class_name": "TestApp_Launch",
        "arguments": [
            {"name": "in_strUrl", "direction": "In", "type": "String"},
            {"name": "in_strCredentialAssetName", "direction": "In", "type": "String"},
            {"name": "out_uiApp", "direction": "Out", "type": "UiElement"},
        ],
        "variables": [
            {"name": "strUsername", "type": "String"},
            {"name": "secstrPassword", "type": "SecureString"},
        ],
        "activities": [
            {"gen": "log_message", "args": {"message_expr": "\"[START] TestApp_Launch\"", "level": "Info"}},
            {
                "gen": "napplicationcard_open",
                "args": {
                    "display_name": "TestApp",
                    "url_variable": "in_strUrl",
                    "out_ui_element": "out_uiApp",
                    "target_app_selector": "<html app='msedge.exe' title='TestApp' />",
                },
                "children": [
                    {"gen": "getrobotcredential", "args": {
                        "asset_name_variable": "in_strCredentialAssetName",
                        "username_variable": "strUsername",
                        "password_variable": "secstrPassword",
                    }},
                    {"gen": "ntypeinto", "args": {
                        "display_name": "Type Into 'Email'",
                        "selector": "<webctrl id='email' tag='INPUT' />",
                        "text_variable": "strUsername",
                    }},
                    {"gen": "ntypeinto", "args": {
                        "display_name": "Type Into 'Password'",
                        "selector": "<webctrl id='password' tag='INPUT' />",
                        "text_variable": "secstrPassword",
                        "is_secure": True,
                    }},
                    {"gen": "nclick", "args": {
                        "display_name": "Click 'Login'",
                        "selector": "<webctrl tag='BUTTON' aaname='Login' />",
                    }},
                ],
            },
            {"gen": "log_message", "args": {"message_expr": "\"[END] TestApp_Launch\"", "level": "Info"}},
        ]
    },

    "try_catch_with_retry": {
        "class_name": "Test_TryCatchRetry",
        "arguments": [
            {"name": "in_strUrl", "direction": "In", "type": "String"},
        ],
        "variables": [
            {"name": "strResult", "type": "String"},
        ],
        "activities": [
            {"gen": "log_message", "args": {"message_expr": "\"[START] Test_TryCatchRetry\"", "level": "Info"}},
            {
                "gen": "try_catch",
                "args": {
                    "display_name": "Try API Call",
                    "catches": [
                        {
                            "exception_type": "System.Exception",
                            "name": "exception",
                            "children": [
                                {"gen": "log_message", "args": {"message_expr": "exception.Message", "level": "Error"}},
                                {"gen": "rethrow", "args": {}},
                            ]
                        }
                    ]
                },
                "try_children": [
                    {
                        "gen": "retryscope",
                        "args": {"display_name": "Retry HTTP", "number_of_retries": 3},
                        "children": [
                            {"gen": "net_http_request", "args": {
                                "request_url_variable": "in_strUrl",
                                "method": "GET",
                                "result_variable": "strResult",
                                "display_name": "HTTP GET Data",
                            }},
                        ]
                    }
                ],
                "finally_children": [
                    {"gen": "log_message", "args": {"message_expr": "\"API call complete\"", "level": "Info"}},
                ]
            },
            {"gen": "log_message", "args": {"message_expr": "\"[END] Test_TryCatchRetry\"", "level": "Info"}},
        ]
    },

    "data_operations": {
        "class_name": "Test_DataOps",
        "arguments": [
            {"name": "in_dt_Source", "direction": "In", "type": "DataTable"},
            {"name": "out_dt_Result", "direction": "Out", "type": "DataTable"},
        ],
        "variables": [
            {"name": "intCount", "type": "Int32"},
            {"name": "strOutput", "type": "String"},
        ],
        "activities": [
            {"gen": "log_message", "args": {"message_expr": "\"[START] Test_DataOps\"", "level": "Info"}},
            {"gen": "multiple_assign", "args": {
                "display_name": "Initialize Variables",
                "assignments": {
                    "intCount": "0",
                    "strOutput": "\"\"",
                }
            }},
            {
                "gen": "foreach_row",
                "args": {
                    "datatable_variable": "in_dt_Source",
                    "display_name": "Process Each Row",
                },
                "children": [
                    {"gen": "assign", "args": {
                        "to_variable": "intCount",
                        "value_expression": "intCount + 1",
                    }},
                    {"gen": "log_message", "args": {
                        "message_expr": "\"Processing row \" & intCount.ToString",
                        "level": "Trace",
                    }},
                ]
            },
            {"gen": "output_data_table", "args": {
                "datatable_variable": "in_dt_Source",
                "output_variable": "strOutput",
            }},
            {"gen": "log_message", "args": {"message_expr": "\"[END] Test_DataOps\"", "level": "Info"}},
        ]
    },

    "if_else_control_flow": {
        "class_name": "Test_ControlFlow",
        "arguments": [
            {"name": "in_intValue", "direction": "In", "type": "Int32"},
            {"name": "out_strCategory", "direction": "Out", "type": "String"},
        ],
        "variables": [],
        "activities": [
            {"gen": "log_message", "args": {"message_expr": "\"[START] Test_ControlFlow\"", "level": "Info"}},
            {
                "gen": "if",
                "args": {
                    "condition_expression": "in_intValue > 100",
                    "display_name": "Check Value Range",
                },
                "then_children": [
                    {"gen": "assign", "args": {"to_variable": "out_strCategory", "value_expression": "\"High\""}},
                ],
                "else_children": [
                    {"gen": "assign", "args": {"to_variable": "out_strCategory", "value_expression": "\"Low\""}},
                ],
            },
            {"gen": "log_message", "args": {"message_expr": "\"[END] Test_ControlFlow\"", "level": "Info"}},
        ]
    },

    "queue_dispatcher": {
        "class_name": "Test_QueueDispatch",
        "arguments": [],
        "variables": [
            {"name": "strReference", "type": "String"},
        ],
        "activities": [
            {"gen": "log_message", "args": {"message_expr": "\"[START] Test_QueueDispatch\"", "level": "Info"}},
            {"gen": "add_queue_item", "args": {
                "queue_name_config": "in_Config(\"OrchestratorQueueName\").ToString",
                "display_name": "Add Queue Item",
                "item_fields": {
                    "OrderId": "\"ORD-001\"",
                    "Amount": "\"100.50\""
                },
                "reference_variable": "strReference",
                "folder_path_config": "in_Config(\"OrchestratorQueueFolder\").ToString",
            }},
            {"gen": "log_message", "args": {"message_expr": "\"[END] Test_QueueDispatch\"", "level": "Info"}},
        ]
    },

    "attach_and_navigate": {
        "class_name": "TestApp_NavigateToPage",
        "arguments": [
            {"name": "io_uiApp", "direction": "InOut", "type": "UiElement"},
            {"name": "in_strTargetUrl", "direction": "In", "type": "String"},
        ],
        "variables": [],
        "activities": [
            {"gen": "log_message", "args": {"message_expr": "\"[START] TestApp_NavigateToPage\"", "level": "Info"}},
            {
                "gen": "napplicationcard_attach",
                "args": {
                    "display_name": "Attach TestApp",
                    "ui_element_variable": "io_uiApp",
                },
                "children": [
                    {"gen": "ngotourl", "args": {
                        "url_variable": "in_strTargetUrl",
                        "display_name": "Navigate To Target",
                    }},
                ],
            },
            {"gen": "log_message", "args": {"message_expr": "\"[END] TestApp_NavigateToPage\"", "level": "Info"}},
        ]
    },

    "misc_activities": {
        "class_name": "Test_Misc",
        "arguments": [],
        "variables": [],
        "activities": [
            {"gen": "log_message", "args": {"message_expr": "\"[START] Test_Misc\"", "level": "Info"}},
            {"gen": "comment", "args": {"text": "This is a placeholder comment"}},
            {"gen": "comment_out", "args": {"body_content": "", "display_name": "Disabled block"}},
            {"gen": "log_message", "args": {"message_expr": "\"[END] Test_Misc\"", "level": "Info"}},
        ]
    },

    "pdf_extraction": {
        "class_name": "Test_PDF",
        "arguments": [
            {"name": "in_strFilePath", "direction": "In", "type": "String"},
            {"name": "out_strText", "direction": "Out", "type": "String"},
        ],
        "variables": [],
        "activities": [
            {"gen": "log_message", "args": {"message_expr": "\"[START] Test_PDF\"", "level": "Info"}},
            {"gen": "read_pdf_text", "args": {
                "filename_variable": "in_strFilePath",
                "output_variable": "out_strText",
                "display_name": "Read PDF Text",
            }},
            {"gen": "log_message", "args": {"message_expr": "\"[END] Test_PDF\"", "level": "Info"}},
        ]
    },

    "file_operations": {
        "class_name": "Test_FileOps",
        "arguments": [
            {"name": "in_strSourcePath", "direction": "In", "type": "String"},
            {"name": "in_strDestPath", "direction": "In", "type": "String"},
        ],
        "variables": [
            {"name": "boolExists", "type": "Boolean"},
            {"name": "strContent", "type": "String"},
        ],
        "activities": [
            {"gen": "log_message", "args": {"message_expr": "\"[START] Test_FileOps\"", "level": "Info"}},
            {"gen": "path_exists", "args": {
                "path_variable": "in_strSourcePath",
                "result_variable": "boolExists",
                "display_name": "Check Source Exists",
            }},
            {"gen": "read_text_file", "args": {
                "path_variable": "in_strSourcePath",
                "output_variable": "strContent",
                "display_name": "Read Source File",
            }},
            {"gen": "copy_file", "args": {
                "source_path": "in_strSourcePath",
                "destination_path": "in_strDestPath",
                "display_name": "Copy File",
            }},
            {"gen": "log_message", "args": {"message_expr": "\"[END] Test_FileOps\"", "level": "Info"}},
        ]
    },

    "while_loop": {
        "class_name": "Test_WhileLoop",
        "arguments": [
            {"name": "in_intMax", "direction": "In", "type": "Int32"},
        ],
        "variables": [
            {"name": "intCounter", "type": "Int32"},
        ],
        "activities": [
            {"gen": "log_message", "args": {"message_expr": "\"[START] Test_WhileLoop\"", "level": "Info"}},
            {"gen": "assign", "args": {"to_variable": "intCounter", "value_expression": "0"}},
            {
                "gen": "while",
                "args": {
                    "condition_expression": "intCounter < in_intMax",
                    "display_name": "Process Loop",
                },
                "children": [
                    {"gen": "assign", "args": {"to_variable": "intCounter", "value_expression": "intCounter + 1"}},
                    {"gen": "log_message", "args": {"message_expr": "\"Iteration \" & intCounter.ToString", "level": "Trace"}},
                ]
            },
            {"gen": "log_message", "args": {"message_expr": "\"[END] Test_WhileLoop\"", "level": "Info"}},
        ]
    },

    "excel_read_write": {
        "class_name": "Test_Excel",
        "arguments": [
            {"name": "in_strFilePath", "direction": "In", "type": "String"},
            {"name": "out_dt_Data", "direction": "Out", "type": "DataTable"},
        ],
        "variables": [],
        "activities": [
            {"gen": "log_message", "args": {"message_expr": "\"[START] Test_Excel\"", "level": "Info"}},
            {"gen": "read_range", "args": {
                "workbook_path_variable": "in_strFilePath",
                "sheet_name": "Sheet1",
                "output_variable": "out_dt_Data",
                "display_name": "Read Excel Data",
            }},
            {"gen": "log_message", "args": {"message_expr": "\"[END] Test_Excel\"", "level": "Info"}},
        ]
    },

    "sap_wingui_workflow": {
        "class_name": "Test_SAPWinGUI",
        "arguments": [
            {"name": "in_strSapConnection", "direction": "In", "type": "String"},
        ],
        "variables": [
            {"name": "strStatusMessage", "type": "String"},
            {"name": "strStatusType", "type": "String"},
        ],
        "activities": [
            {"gen": "log_message", "args": {"message_expr": "\"[START] Test_SAPWinGUI\"", "level": "Info"}},
            {"gen": "sap_logon", "args": {
                "display_name": "SAP Logon",
                "sap_connection": "in_strSapConnection",
                "body_content": "",
            }},
            {"gen": "sap_read_statusbar", "args": {
                "display_name": "Read Status Bar",
                "message_text": "strStatusMessage",
                "message_type": "strStatusType",
            }},
            {"gen": "log_message", "args": {"message_expr": "\"[END] Test_SAPWinGUI\"", "level": "Info"}},
        ]
    },

    "message_box_dialog": {
        "class_name": "Test_Dialogs",
        "arguments": [
            {"name": "in_strMessage", "direction": "In", "type": "String"},
        ],
        "variables": [
            {"name": "strUserInput", "type": "String"},
        ],
        "activities": [
            {"gen": "log_message", "args": {"message_expr": "\"[START] Test_Dialogs\"", "level": "Info"}},
            {"gen": "input_dialog", "args": {
                "title": "\"Enter Value\"",
                "label": "in_strMessage",
                "result_variable": "strUserInput",
                "display_name": "Prompt User",
            }},
            {"gen": "message_box", "args": {
                "text_variable": "strUserInput",
                "display_name": "Show Result",
            }},
            {"gen": "log_message", "args": {"message_expr": "\"[END] Test_Dialogs\"", "level": "Info"}},
        ]
    },
}

# Merge plugin-provided test specs (e.g. Tasks)
try:
    from plugin_loader import load_plugins, get_test_specs
    load_plugins()
    SPECS.update(get_test_specs())
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

class TestResult:
    def __init__(self, name: str):
        self.name = name
        self.passed = True
        self.messages = []

    def fail(self, msg: str):
        self.passed = False
        self.messages.append(f"FAIL: {msg}")

    def ok(self, msg: str):
        self.messages.append(f"  OK: {msg}")

    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        header = f"{'='*60}\n{status}  {self.name}\n{'='*60}"
        body = "\n".join(f"  {m}" for m in self.messages)
        return f"{header}\n{body}" if self.messages else header


def run_generate_and_lint(spec_name: str, spec: dict, tmpdir: str, verbose: bool) -> TestResult:
    """Generate a workflow from spec, then lint it."""
    t = TestResult(f"gen→lint: {spec_name}")

    spec_path = os.path.join(tmpdir, f"{spec_name}.json")
    xaml_path = os.path.join(tmpdir, f"{spec_name}.xaml")

    # Write spec
    with open(spec_path, "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=2)

    # Generate
    gen_proc = subprocess.run(
        [sys.executable, str(GENERATOR), spec_path, xaml_path],
        capture_output=True, text=True
    )
    if gen_proc.returncode != 0:
        t.fail(f"Generation failed: {gen_proc.stderr.strip()}")
        return t
    t.ok(f"Generated {os.path.getsize(xaml_path):,} bytes")

    # Validate (structural only — lint needs project context for some rules)
    val_proc = subprocess.run(
        [sys.executable, str(VALIDATOR), xaml_path],
        capture_output=True, text=True
    )

    # Parse validation output
    error_count = 0
    warning_count = 0
    for line in val_proc.stdout.splitlines():
        if "[ERROR]" in line:
            error_count += 1
            t.fail(f"  {line.strip()}")
        if "[WARN]" in line:
            warning_count += 1

    if error_count == 0:
        t.ok(f"Validation passed (0 errors, {warning_count} warnings)")
    else:
        t.fail(f"{error_count} validation errors")

    # Check XML wellformedness
    try:
        import xml.etree.ElementTree as ET
        ET.parse(xaml_path)
        t.ok("XML is well-formed")
    except ET.ParseError as e:
        t.fail(f"XML parse error: {e}")

    return t


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generator → Lint integration test")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--tmpdir", default=None,
                        help="Base directory for scratch files")
    args = parser.parse_args()

    tmpdir = tempfile.mkdtemp(prefix="gen_lint_test_", dir=args.tmpdir)
    results = []

    try:
        for spec_name, spec in SPECS.items():
            result = run_generate_and_lint(spec_name, spec, tmpdir, args.verbose)
            results.append(result)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    for r in results:
        if args.verbose or not r.passed:
            print(r.summary())
        else:
            status = "PASS" if r.passed else "FAIL"
            print(f"{status}  {r.name}")

    print(f"\n{'='*60}")
    print(f"GENERATOR→LINT: {passed}/{total} passed" +
          (f", {failed} FAILED" if failed else " — all clear"))
    print(f"{'='*60}")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
