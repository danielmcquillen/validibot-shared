"""Tests for the Schematron container contract (ADR-2026-07-01, D4b/D9).

The Schematron validator ships an **artefact reference** (staged URI +
checksums) rather than inlined rule text, and its outputs carry an
``engine_status`` failure taxonomy where ``passed`` is *tri-state* —
True/False when the engine ran, ``None`` (unknown) when it could not. These
tests pin those contract properties so a refactor cannot silently weaken
them: the Django side and the validator backend both program against exactly
this shape.
"""

import pytest
from pydantic import ValidationError

from validibot_shared.schematron.envelopes import (
    ENGINE_STATUS_OK,
    ENGINE_STATUS_TIMEOUT,
    SchematronFinding,
    SchematronInputEnvelope,
    SchematronInputs,
    SchematronOutputEnvelope,
    SchematronOutputs,
    build_schematron_input_envelope,
)
from validibot_shared.validations.envelopes import (
    SupportedMimeType,
    ValidationStatus,
    ValidatorType,
)

# Test constants to avoid magic values
DEFAULT_MAX_FINDINGS = 500
DEFAULT_XSLT_TIMEOUT = 60
TEST_ERROR_COUNT = 3
ARTIFACT_SHA = "b" * 64


class _ValidatorStub:
    """Duck-typed validator (id/validation_type/version) for the builder."""

    id = "val-1"
    validation_type = "SCHEMATRON"
    version = "1"


def _inputs(**overrides) -> SchematronInputs:
    base = {
        "pack_id": "en16931-ubl",
        "pack_version": "1.3.16",
        "artifact_uri": "gs://bucket/run-1/pack.xslt",
        "artifact_sha256": ARTIFACT_SHA,
        "query_binding": "xslt2",
    }
    base.update(overrides)
    return SchematronInputs(**base)


def test_schematron_inputs_carry_artifact_reference_and_limit_defaults():
    """Inputs pin the staged artefact + checksum and default the D8 limits.

    The container MUST be able to verify what it fetched before executing —
    so the artefact URI and sha256 are required — while the resource limits
    default to the ADR's table values for direct consumers.
    """
    inputs = _inputs()

    assert inputs.artifact_uri == "gs://bucket/run-1/pack.xslt"
    assert inputs.artifact_sha256 == ARTIFACT_SHA
    assert inputs.max_findings == DEFAULT_MAX_FINDINGS
    assert inputs.xslt_timeout_seconds == DEFAULT_XSLT_TIMEOUT


def test_schematron_inputs_require_the_artifact_fields():
    """Omitting the artefact reference is a validation error, not a default.

    An input envelope without a verifiable artefact would force the container
    to either refuse (good, but late) or trust an unpinned path (never).
    """
    with pytest.raises(ValidationError):
        SchematronInputs(pack_id="x", pack_version="1")


def test_outputs_default_to_unknown_passed_not_false():
    """``passed`` defaults to None — unknown, not failed (D9).

    A default of False would make an unpopulated envelope read as "the
    invoice failed the rules"; None forces every consumer to distinguish
    "engine didn't run" from "rules failed".
    """
    outputs = SchematronOutputs()
    assert outputs.passed is None
    assert outputs.engine_status == ENGINE_STATUS_OK


def test_engine_failure_shape_round_trips():
    """A timeout outputs object serializes and re-validates losslessly.

    The callback path deserializes output.json with this model; the D9
    fields must survive the JSON round trip exactly.
    """
    outputs = SchematronOutputs(
        engine_status=ENGINE_STATUS_TIMEOUT,
        engine_message="Transform exceeded 60s",
        passed=None,
        error_count=0,
    )
    envelope = SchematronOutputEnvelope(
        run_id="run-1",
        validator={"id": "v1", "type": ValidatorType.SCHEMATRON, "version": "1"},
        status=ValidationStatus.FAILED_RUNTIME,
        timing={},
        outputs=outputs,
    )

    restored = SchematronOutputEnvelope.model_validate(
        envelope.model_dump(mode="json"),
    )
    assert restored.outputs.engine_status == ENGINE_STATUS_TIMEOUT
    assert restored.outputs.passed is None


def test_findings_and_rule_id_map_round_trip():
    """Findings keep native ids/locations and the map keeps its D2 shape."""
    outputs = SchematronOutputs(
        engine_status=ENGINE_STATUS_OK,
        passed=False,
        error_count=TEST_ERROR_COUNT,
        finding_rule_ids_by_severity={"BR-CO-15": "ERROR", "BR-05": "WARNING"},
        findings=[
            SchematronFinding(
                rule_id="BR-CO-15",
                message="Totals must reconcile.",
                severity="ERROR",
                location_xpath="/Invoice/LegalMonetaryTotal",
                flag="fatal",
            ),
        ],
    )

    restored = SchematronOutputs.model_validate(outputs.model_dump(mode="json"))
    assert restored.finding_rule_ids_by_severity["BR-CO-15"] == "ERROR"
    assert restored.findings[0].rule_id == "BR-CO-15"
    assert restored.findings[0].location_xpath == "/Invoice/LegalMonetaryTotal"


def test_outputs_forbid_unknown_fields():
    """extra="forbid" holds — a typo'd field fails loudly, not silently.

    Contract models must reject unknown keys so a mismatched backend/Django
    version pair surfaces as an explicit error instead of dropped data.
    """
    with pytest.raises(ValidationError):
        SchematronOutputs(engine_status="ok", not_a_field=1)


def test_build_schematron_input_envelope_assembles_the_xml_submission():
    """The builder produces a valid envelope with an XML primary input.

    Pins the file-item conventions (name/mime/role) the container reads and
    that ``ValidatorType.SCHEMATRON`` exists — the builder would crash
    without the enum member.
    """
    envelope = build_schematron_input_envelope(
        run_id="run-1",
        validator=_ValidatorStub(),
        org_id="org-1",
        org_name="ValidiBot",
        workflow_id="wf-1",
        step_id="step-1",
        step_name="Peppol rules",
        submission_uri="gs://bucket/run-1/submission.xml",
        inputs=_inputs(),
        callback_url="https://example.com/callback",
        execution_bundle_uri="gs://bucket/run-1/",
    )

    assert isinstance(envelope, SchematronInputEnvelope)
    assert envelope.validator.type == ValidatorType.SCHEMATRON
    file_item = envelope.input_files[0]
    assert file_item.name == "submission.xml"
    assert file_item.mime_type == SupportedMimeType.APPLICATION_XML
    assert file_item.role == "primary-model"
    assert envelope.inputs.pack_id == "en16931-ubl"
