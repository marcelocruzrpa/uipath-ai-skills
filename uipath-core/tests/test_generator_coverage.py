"""Tests for the data-driven generator engine (_data_driven.py).

Covers Stage-3 SAP scope-detection heuristic and basic annotation-driven
XAML generation.  GEN-4 will extend this file with additional coverage.
"""

from __future__ import annotations

import sys
from io import StringIO
from pathlib import Path

import pytest

# Make the scripts package importable without installation.
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from generate_activities._data_driven import (
    gen_from_annotation,
    _ANNOTATIONS_CACHE,
    WizardOnlyActivityError,
    MissingScopeError,
    ReviewNeededError,
    _ROOT_SCOPE_SENTINEL,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _capture_stderr(fn, *args, **kwargs):
    """Run *fn* and return (result, stderr_text)."""
    buf = StringIO()
    old = sys.stderr
    sys.stderr = buf
    try:
        result = fn(*args, **kwargs)
    finally:
        sys.stderr = old
    return result, buf.getvalue()


# ---------------------------------------------------------------------------
# SAP scope enforcement — hard-fail when the activity is emitted at root
# (no NSAPLogon / NSAPLogoff wrapper).
# ---------------------------------------------------------------------------

class TestSAPScopeEnforcement:
    """gen_from_annotation hard-fails on SAP activities without a real scope.

    Previously emitted a stderr warning and returned bogus XAML; that was a
    silent-corruption path. A SAP activity without a real parent scope now
    raises ``MissingScopeError`` so the caller sees the problem immediately.
    """

    def test_hardfail_when_scope_id_empty_string(self):
        with pytest.raises(MissingScopeError) as excinfo:
            gen_from_annotation(
                "nsapcalltransaction",
                {"display_name": "Call Transaction"},
                id_ref="NSAPCallTransaction_1",
                scope_id="",
            )
        assert "NSAPLogon" in str(excinfo.value)

    def test_hardfail_when_scope_id_none(self):
        with pytest.raises(MissingScopeError):
            gen_from_annotation(
                "nsapcalltransaction",
                {"display_name": "Call Transaction"},
                id_ref="NSAPCallTransaction_1",
                scope_id=None,
            )

    def test_hardfail_when_scope_id_is_root_sentinel(self):
        """Emitting a SAP activity with the root-scope sentinel means it's at
        the top of the workflow body — hard-fail, do not emit bogus XAML."""
        with pytest.raises(MissingScopeError):
            gen_from_annotation(
                "nsapcalltransaction",
                {"display_name": "Call Transaction"},
                id_ref="NSAPCallTransaction_1",
                scope_id=_ROOT_SCOPE_SENTINEL,
            )

    def test_success_when_scope_id_is_real_uuid(self):
        """When a real (non-sentinel) scope UUID is supplied, the activity
        generates without raising and with no stderr noise."""
        result, stderr = _capture_stderr(
            gen_from_annotation,
            "nsapcalltransaction",
            {"display_name": "Call Transaction"},
            id_ref="NSAPCallTransaction_1",
            scope_id="6644ba5d-ce7e-499b-9da1-957ca5b1da51",
        )
        assert "NSAPCallTransaction" in result
        assert "WARNING" not in stderr

    def test_non_sap_activity_does_not_require_scope(self):
        """A non-SAP annotation entry must never trigger scope enforcement,
        even with an empty scope_id or the root sentinel."""
        try:
            result = gen_from_annotation(
                "delay",
                {"duration": "00:00:01"},
                id_ref="Delay_1",
                scope_id="",
            )
        except KeyError:
            pytest.skip("'delay' not found in annotations — skipping non-SAP check")
        assert result  # non-SAP at empty scope returns XAML, no exception


# ---------------------------------------------------------------------------
# GEN-4: Backfilled annotation coverage — parametrized xfail suite
# ---------------------------------------------------------------------------
# All 44 entries that GEN-2 added carry _review_needed: true.  The engine
# should produce XAML without raising for most of them; a small number surface
# real bugs in the heuristic backfill (ValueError from unsupported child_element
# types).  All are marked xfail(strict=False) so:
#   - entries that pass cleanly  → reported as XPASS (no failure, free signal)
#   - entries that raise         → reported as xfail (expected, bug noted below)
#
# Known bugs surfaced by this suite (do NOT fix here — file follow-up tasks):
#   NApplicationCard, NForEachUiElement, NSAPLogon, NSAPTableCellScope
#   all raise ValueError: unsupported child_element type 'activity_action'
# ---------------------------------------------------------------------------

_REVIEW_NEEDED_ACTIVITIES = [
    "GoogleCloudOCR",
    "GoogleOCR",
    "MicrosoftAzureComputerVisionOCR",
    "NBlockUserInput",
    "NBrowserDialogScope",
    "NBrowserFilePickerScope",
    "NCheckElement",
    "NClickTrigger",
    "NClosePopup",
    "NDragAndDrop",
    "NElementScope",
    "NFillForm",
    "NFindElements",
    "NGetBrowserData",
    "NGetClipboard",
    "NGetUrl",
    "NGoToUrl",
    "NHighlight",
    "NInjectJsScript",
    "NKeyboardTrigger",
    "NNavigateBrowser",
    "NSAPCallTransaction",
    "NSAPClickPictureOnScreen",
    "NSAPClickToolbarButton",
    "NSAPExpandALVHierarchicalTable",
    "NSAPExpandALVTree",
    "NSAPExpandTree",
    "NSAPLogin",
    "NSAPReadStatusbar",
    "NSAPSelectDatesInCalendar",
    "NSAPSelectMenuItem",
    "NSetBrowserData",
    "NSetClipboard",
    "NSetFocus",
    "NSetRuntimeBrowser",
    "NSetText",
    "NTakeScreenshot",
    "NUITask",
    "NUnblockUserInput",
    "NWindowOperation",
]

assert len(_REVIEW_NEEDED_ACTIVITIES) == 40, (
    f"Expected 40 _review_needed activities, got {len(_REVIEW_NEEDED_ACTIVITIES)}"
)

# Activities fixed by GEN-5 (task #27) — activity_action child_element support added.
# These were previously xfail; they now pass cleanly.
_ACTIVITY_ACTION_FIXED = [
    "NApplicationCard",
    "NForEachUiElement",
    "NSAPLogon",
    "NSAPTableCellScope",
]


class TestBackfilledAnnotationCoverage:
    """Parametrized smoke-test for all 40 heuristic-backfill annotation entries.

    Each test calls gen_from_annotation with a minimal spec (only display_name)
    and a dummy scope_id. Every entry currently generates a non-empty XAML
    string without raising; these were previously xfail(strict=False) while
    the backfill was in review, but that allowed regressions through silently.
    They now assert unconditionally — if a future annotation change breaks one
    of these, the test must fail loudly. Move any genuinely-broken entry to
    its own `xfail(strict=True)` with a specific reason.
    """

    @pytest.mark.parametrize("activity_name", _REVIEW_NEEDED_ACTIVITIES)
    def test_gen_from_annotation_does_not_raise(self, activity_name):
        """gen_from_annotation must return a non-empty XAML string."""
        result = gen_from_annotation(
            activity_name,
            {"display_name": f"Test {activity_name}"},
            id_ref=f"{activity_name}_1",
            scope_id="aaaabbbb-cccc-dddd-eeee-ffffffffffff",
        )
        assert result, f"Expected non-empty XAML for {activity_name!r}"
        # Basic structural check: output should look like an XML element
        assert "<" in result and ">" in result, (
            f"Output for {activity_name!r} does not look like XAML: {result!r}"
        )


class TestActivityActionFixed:
    """Genuine passing tests for the 4 activities whose activity_action
    child_element type was fixed by GEN-5 (task #27).

    These were previously xfail; they now pass cleanly without any xfail marker.
    """

    @pytest.mark.parametrize("activity_name", _ACTIVITY_ACTION_FIXED)
    def test_gen_from_annotation_does_not_raise(self, activity_name):
        """gen_from_annotation must return a non-empty XAML string containing
        the ActivityAction body structure."""
        result = gen_from_annotation(
            activity_name,
            {"display_name": f"Test {activity_name}"},
            id_ref=f"{activity_name}_1",
            scope_id="aaaabbbb-cccc-dddd-eeee-ffffffffffff",
        )
        assert result, f"Expected non-empty XAML for {activity_name!r}"
        assert "<" in result and ">" in result, (
            f"Output for {activity_name!r} does not look like XAML: {result!r}"
        )
        assert "ActivityAction" in result, (
            f"Expected ActivityAction body in XAML for {activity_name!r}: {result!r}"
        )
        assert "DelegateInArgument" in result, (
            f"Expected DelegateInArgument in XAML for {activity_name!r}: {result!r}"
        )


class TestSequenceChildElement:
    """The 'sequence' child_type in _data_driven.py emits an empty Sequence
    placeholder for annotation entries whose child_elements include a sequence
    body (e.g. CommentOut.Body, TryCatch.Try). Previously this path fell
    through to ValueError: unsupported child_element type 'sequence'.
    """

    @pytest.mark.parametrize("activity_name", ["CommentOut", "TryCatch"])
    def test_sequence_branch_does_not_raise(self, activity_name):
        """gen_from_annotation must return XAML containing an empty Sequence
        placeholder with the expected IdRef scheme for activities whose
        child_elements include a 'sequence' entry."""
        result = gen_from_annotation(
            activity_name,
            {"display_name": f"Test {activity_name}"},
            id_ref=f"{activity_name}_1",
            scope_id="aaaabbbb-cccc-dddd-eeee-ffffffffffff",
        )
        assert result, f"Expected non-empty XAML for {activity_name!r}"
        assert "<Sequence " in result, (
            f"Expected a Sequence child element in XAML for {activity_name!r}: "
            f"{result!r}"
        )
        assert "DisplayName=\"Do\"" in result, (
            f"Expected DisplayName=\"Do\" on the placeholder sequence for "
            f"{activity_name!r}: {result!r}"
        )
        assert f"Sequence_{activity_name}_1_" in result, (
            f"Expected IdRef prefixed with 'Sequence_{activity_name}_1_' for "
            f"{activity_name!r}: {result!r}"
        )


# ---------------------------------------------------------------------------
# GEN-4: Wizard-only stub coverage
# ---------------------------------------------------------------------------
# Wizard-only entries have element_tag=None and no params.  gen_from_annotation
# currently raises KeyError('element_tag') for these.  This is a follow-up
# item — the engine should either raise a clear UnsupportedActivityError or
# return a documented stub.  Tests are xfail until that work is done.
# ---------------------------------------------------------------------------

_WIZARD_ONLY_ACTIVITIES = [
    "ApplicationEventTrigger",
    "ExtractUIData",
    "GetAttribute",
    "NAccessibilityCheck",
    "NExtractFormDataGeneric",
    "NSetValue",
]


class TestWizardOnlyStubs:
    """Wizard-only activities have _unsupported_reason: 'wizard-only' and no
    element_tag.  gen_from_annotation currently raises KeyError on element_tag.
    These tests are xfail — they document the current gap and will flip to
    passing once the engine surfaces a clear error or supported stub.

    Follow-up: engine should raise a descriptive UnsupportedActivityError
    (or similar) instead of a bare KeyError on 'element_tag'.
    """

    @pytest.mark.parametrize("activity_name", _WIZARD_ONLY_ACTIVITIES)
    def test_wizard_only_raises_wizard_only_error(self, activity_name):
        """Calling gen_from_annotation on a wizard-only entry raises
        WizardOnlyActivityError with a descriptive message."""
        with pytest.raises(WizardOnlyActivityError, match="wizard-only"):
            gen_from_annotation(
                activity_name,
                {},
                id_ref=f"{activity_name}_1",
                scope_id="",
            )


# ---------------------------------------------------------------------------
# GEN-4: Hand-written-wins — registry takes priority over annotation fallback
# ---------------------------------------------------------------------------

class TestHandWrittenWins:
    """The dispatch in generate_workflow.py checks _REGISTRY before falling
    through to gen_from_annotation.  For the 11 original hand-written entries
    the registry entry's fn must be the dedicated gen_* function, NOT the
    annotation fallback."""

    def test_ntypeinto_registry_uses_hand_written_function(self):
        """_REGISTRY['ntypeinto'].fn must be gen_ntypeinto — the dedicated
        hand-written generator — not the annotation fallback."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        import generate_workflow as gw

        entry = gw._REGISTRY.get("ntypeinto")
        assert entry is not None, (
            "'ntypeinto' not found in _REGISTRY — hand-written dispatch is broken"
        )
        assert entry.fn.__name__ == "gen_ntypeinto", (
            f"Expected fn name 'gen_ntypeinto', got {entry.fn.__name__!r}"
        )

    def test_ntypeinto_annotation_entry_exists_but_is_not_used_by_dispatch(self):
        """NTypeInto has a full annotation entry (no _review_needed flag), but
        the dispatch must hit the registry path first.  Verify by calling
        gen_from_annotation directly — it works — then confirm the registry
        entry points to the *different* hand-written function.

        This proves the two paths are independent and the registry wins."""
        # Direct annotation call must succeed (entry is fully specified)
        result = gen_from_annotation(
            "NTypeInto",
            {"display_name": "Hand-written test", "selector": "<webctrl/>",
             "text_variable": "strVal"},
            id_ref="NTypeInto_HW_1",
            scope_id="scope-guid-hw",
        )
        assert "NTypeInto" in result, (
            f"Direct annotation call for NTypeInto failed: {result!r}"
        )

        # Registry entry uses a different code path (hand-written gen_ntypeinto)
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        import generate_workflow as gw
        entry = gw._REGISTRY["ntypeinto"]
        # gen_ntypeinto is imported from ui_automation.py, not _data_driven
        assert entry.fn.__module__ != "generate_activities._data_driven", (
            "Registry fn should come from hand-written module, not _data_driven"
        )

    def test_all_eleven_hand_written_are_in_registry(self):
        """All 11 original hand-written entries must have _REGISTRY entries so
        the annotation fallback is never reached for them."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        import generate_workflow as gw

        # Lower-case generator names for the 11 hand-written UI activities
        hand_written_gens = [
            "ntypeinto", "nclick", "ncheck", "nhover", "nkeyboardshortcuts",
            "ndoubleclick", "nrightclick", "ngettext", "ncheckstate",
            "nselectitem", "nmousescroll",
        ]
        missing = [g for g in hand_written_gens if g not in gw._REGISTRY]
        assert not missing, (
            f"Hand-written activities missing from _REGISTRY: {missing}"
        )


# ---------------------------------------------------------------------------
# Quarantine: entries flagged _review_needed: true must refuse generation
# unless the UIPATH_ALLOW_REVIEW_NEEDED opt-in is set.
# ---------------------------------------------------------------------------

import os


_REVIEW_NEEDED_QUARANTINED = [
    "DeserializeJsonArray",
    "DeserializeXml",
    "ExecuteXPath",
    "GetNodes",
    "GetXMLNodes",
    "GetXMLNodeAttributes",
    "SerializeJson",
    "HttpClient",
    "BulkInsert",
    "BulkUpdate",
    "InsertDataTable",
    "DatabaseDisconnect",
    "DatabaseTransaction",
    "ExportPDFPageAsImage",
    "ExtractImagesFromPDF",
    "ExtractPDFPageRange",
    "GetPDFPageCount",
    "JoinPDF",
    "ManagePDFPassword",
    "ReadXPSText",
]


class TestReviewNeededQuarantine:
    """Heuristically-backfilled annotation entries flagged ``_review_needed: true``
    must raise :class:`ReviewNeededError` unless the caller opts in."""

    def setup_method(self, method):
        self._prev_opt_in = os.environ.pop("UIPATH_ALLOW_REVIEW_NEEDED", None)

    def teardown_method(self, method):
        os.environ.pop("UIPATH_ALLOW_REVIEW_NEEDED", None)
        if self._prev_opt_in is not None:
            os.environ["UIPATH_ALLOW_REVIEW_NEEDED"] = self._prev_opt_in

    @pytest.mark.parametrize("activity_name", _REVIEW_NEEDED_QUARANTINED)
    def test_raises_without_opt_in(self, activity_name):
        with pytest.raises(ReviewNeededError, match="review"):
            gen_from_annotation(
                activity_name,
                {"display_name": f"Test {activity_name}"},
                id_ref=f"{activity_name}_1",
                scope_id="aaaabbbb-cccc-dddd-eeee-ffffffffffff",
            )

    @pytest.mark.parametrize("truthy", ["1", "true", "yes", "TRUE"])
    def test_opt_in_truthy_allows_generation(self, truthy):
        os.environ["UIPATH_ALLOW_REVIEW_NEEDED"] = truthy
        result = gen_from_annotation(
            "HttpClient",
            {"display_name": "Quarantine opt-in"},
            id_ref="HttpClient_1",
            scope_id="aaaabbbb-cccc-dddd-eeee-ffffffffffff",
        )
        assert result and "<" in result

    @pytest.mark.parametrize("falsy", ["", "0", "false", "FALSE"])
    def test_opt_in_falsy_still_quarantines(self, falsy):
        os.environ["UIPATH_ALLOW_REVIEW_NEEDED"] = falsy
        with pytest.raises(ReviewNeededError):
            gen_from_annotation(
                "HttpClient",
                {"display_name": "Quarantine falsy env"},
                id_ref="HttpClient_1",
                scope_id="aaaabbbb-cccc-dddd-eeee-ffffffffffff",
            )

    @pytest.mark.xfail(
        reason="generate_workflow dispatcher routes 'httpclient' through the "
               "Unknown-generator path before reaching the data-driven "
               "_review_needed wrapper. Wiring gap to address when the "
               "dispatcher learns to fall through to gen_from_annotation.",
        strict=False,
    )
    def test_dispatch_wraps_review_needed_as_valueerror(self):
        """generate_workflow dispatch must catch ReviewNeededError and re-raise
        as a user-friendly ValueError with the original message prefixed."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        import generate_workflow as gw

        spec = {
            "class_name": "Q_Test",
            "arguments": [],
            "variables": [],
            "activities": [
                {"gen": "httpclient", "args": {"display_name": "Q"}},
            ],
        }
        with pytest.raises(ValueError, match="Cannot generate"):
            gw.generate_workflow(spec)
