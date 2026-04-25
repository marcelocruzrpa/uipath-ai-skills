# Annotation schema

Each `annotations/<category>.json` file has a single top-level `activities`
object keyed by **CamelCase** activity name. The annotation cache in
`generate_activities/_data_driven.py` lower-cases the keys at load time, so
lookups are case-insensitive at runtime.

## Existing fields (used by the dispatch path)

| Field | Type | Required | Notes |
|---|---|---|---|
| `gen_function` | str | no | Hand-written generator name (e.g. `"gen_ntypeinto"`). When present and the function exists in `generate_activities/*.py`, dispatcher prefers it over the data-driven fallback. May be `null` for activities that route purely through `gen_from_annotation`. |
| `element_tag` | str | yes when `gen_function` is null | XAML tag with namespace prefix (e.g. `"uix:NTypeInto"`). When dispatch goes through a hand-written `gen_function` (composite/helper generators like `gen_variables_block`, `gen_take_screenshot_and_save`), this may be null. |
| `params` | object | yes | Map of parameter name → `{type, required, default, enum, description}`. |
| `fixed_attrs` | object | yes | Map of XAML attribute → literal string. Always emitted, never parameterized. |
| `conditional_attrs` | object | yes (may be `{}`) | Map of attribute → `{when, value}` where `when` references a param and `value` is emitted only when the param is truthy. |
| `child_elements` | object | yes (may be `{}`) | Map of child-element kind → spec. Recognised kinds: `selector`, `static_block`, `literal`, `activity_action`, `list`, `hint_size`, `sequence`. The dispatcher iterates `.items()` and emits each child in order. |
| `hint_size_key` | str | no | Param name whose value is forwarded as the activity's `HintSize` attribute. |
| `note` | str | no | Free-form authoring note (not consumed by the dispatcher). |
| `_unsupported_reason` | str | no | When set, `gen_from_annotation` raises `WizardOnlyActivityError`. The string explains why (e.g. `"wizard-only"`, `"requires Studio's interactive sequence editor"`). |
| `_unsupported_detail` | str | no | Longer explanation paired with `_unsupported_reason`. |
| `_review_needed` | bool | no | Heuristic backfill marker; opt-in via env var `UIPATH_ALLOW_REVIEW_NEEDED`. |
| `_sap_note` | str | no | Reserved for SAP-specific authoring notes. |

## Routing-metadata fields (Phase B)

These fields support LLM activity selection. They are **optional** during the
rollout (Phase E populates them), and become **required** for non-wizard
activities once `validate_annotations.py --strict` is wired into CI.

| Field | Type | Required (post-Phase-E) | Notes |
|---|---|---|---|
| `description` | str | yes | One sentence of what the activity does, written for an LLM. Seed from `version-profiles/*/<ver>.json` `doc_name`. Example: `"Type a string into a UI element on the desktop or web."` |
| `use_when` | str | yes | One sentence of the trigger that should make the LLM pick this activity. Example: `"User wants to fill a text input by typing characters one at a time."` |
| `category` | str enum | yes | One of: `ui_automation`, `excel`, `mail`, `data_operations`, `control_flow`, `error_handling`, `dialogs`, `file_system`, `http_json`, `integrations`, `invoke`, `logging_misc`, `navigation`, `orchestrator`, `testing`, `persistence`, `pdf`, `database`, `webapi`, `application_card`. Used to bucket the routing index. |
| `alternatives` | array of object | no | Each item: `{"activity": <name>, "use_instead_when": <one sentence>}`. Wires the comparison-matrix sub-sections of `routing-index.md`. |
| `examples` | array of object | no | Each item: `{"intent": <user-intent string>, "spec_args": <object>}`. The intent is what the LLM should match; `spec_args` shows the JSON spec that produces it. |
| `tags` | array of str | no | Free-form tags surfaced in the routing index. |
| `_routing_review_needed` | bool | no (default `true`) | Heuristic-seeded routing fields stay flagged until human-validated. |

## Wizard-only / unsupported entries

When `_unsupported_reason` is set, `description` + `use_when` are still useful so
the LLM can explain *why* the activity is unavailable. `category` is also
required (so wizard-only entries are listed in the routing index's "don't use"
section). `alternatives` is the most valuable field for these entries — it
points the LLM at the supported substitute (e.g.
`"ExcelApplicationCard → use ExcelProcessScope or hand-author the workbook scope in code"`).

## Versioning

The schema is implicitly v1 (the field set above). Breaking changes will
introduce a top-level `"_schema_version": 2` key on the JSON file. The
validator (`uipath-core/scripts/validate_annotations.py`) is the canonical
arbiter; treat its `--strict` mode as the contract.
