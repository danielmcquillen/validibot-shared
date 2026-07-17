"""Tests for validation envelope models."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from validibot_shared.canonicalization import sha256_hex_for_model
from validibot_shared.validations.envelopes import (
    ATTEMPT_CONTRACT_VERSION,
    ExecutionContext,
    InputFileItem,
    MessageLocation,
    ResourceFileItem,
    Severity,
    SupportedMimeType,
    ValidationCallback,
    ValidationInputEnvelope,
    ValidationMessage,
    ValidationOutputEnvelope,
    ValidationStatus,
    ValidatorType,
)


def _base_input_envelope_kwargs():
    return {
        "run_id": "run-42",
        "validator": {
            "id": "val-1",
            "type": ValidatorType.ENERGYPLUS,
            "version": "1.0",
        },
        "org": {"id": "org-1", "name": "ValidiBot"},
        "workflow": {"id": "wf-1", "step_id": "step-1", "step_name": "Validate"},
        "input_files": [
            InputFileItem(
                name="model.idf",
                mime_type=SupportedMimeType.ENERGYPLUS_IDF,
                role="primary-model",
                uri="gs://bucket/model.idf",
            )
        ],
        "context": ExecutionContext(
            callback_url="https://example.com/callback",
            execution_bundle_uri="gs://bucket/run-42/",
            execution_attempt_id="attempt-42",
            step_run_id="step-run-42",
            attempt_contract_version=ATTEMPT_CONTRACT_VERSION,
            expected_output_uri="gs://bucket/run-42/output.json",
        ),
    }


def _output_identity_kwargs():
    """Return the immutable execution-attempt identity required on outputs."""
    return {
        "step_run_id": "step-run-99",
        "execution_attempt_id": "attempt-99",
        "attempt_contract_version": ATTEMPT_CONTRACT_VERSION,
        "input_envelope_sha256": "a" * 64,
        "output_uri": "gs://bucket/run-99/output.json",
    }


def test_validation_input_envelope_defaults_schema_version():
    """ValidationInputEnvelope should have default schema version."""
    envelope = ValidationInputEnvelope(**_base_input_envelope_kwargs())

    assert envelope.schema_version == "validibot.input.v1"
    assert envelope.input_files[0].role == "primary-model"
    assert envelope.input_files[0].port_key is None
    assert envelope.inputs == {}


def test_strict_attempt_fixture_has_the_cross_repo_canonical_digest():
    """All producers and consumers must hash the same attempt fixture bytes."""
    envelope = ValidationInputEnvelope(
        run_id="run-fixture",
        validator={
            "id": "validator-fixture",
            "type": ValidatorType.FMU,
            "version": "1",
        },
        org={"id": "org-fixture", "name": "Fixture Org"},
        workflow={
            "id": "workflow-fixture",
            "step_id": "step-fixture",
            "step_name": "Fixture Step",
        },
        inputs={"alpha": 1},
        context={
            "execution_attempt_id": "attempt-fixture",
            "step_run_id": "step-run-fixture",
            "attempt_contract_version": ATTEMPT_CONTRACT_VERSION,
            "expected_output_uri": "gs://fixture/runs/run-fixture/output.json",
            "execution_bundle_uri": "gs://fixture/runs/run-fixture/",
            "skip_callback": True,
        },
    )

    assert sha256_hex_for_model(envelope) == (
        "0f4f7cd8b38a79dbc2c4ac66c1ed602cb4db59665d52b6df73cd409bdaf765c7"
    )


def test_input_file_item_accepts_optional_port_key():
    """InputFileItem should carry declared file-port identity when available."""
    item = InputFileItem(
        name="model.idf",
        mime_type=SupportedMimeType.ENERGYPLUS_IDF,
        role="primary-model",
        port_key="primary_model",
        uri="gs://bucket/model.idf",
    )

    assert item.port_key == "primary_model"


def test_resource_file_item_accepts_optional_port_key():
    """ResourceFileItem should carry declared file-port identity when available."""
    item = ResourceFileItem(
        id="resource-1",
        type="energyplus_weather",
        port_key="weather_file",
        uri="gs://bucket/weather.epw",
    )

    assert item.port_key == "weather_file"


def test_input_file_item_forbids_extra_fields():
    """InputFileItem should forbid extra fields."""
    with pytest.raises(ValidationError):
        InputFileItem(
            name="model.idf",
            mime_type=SupportedMimeType.ENERGYPLUS_IDF,
            role="primary-model",
            uri="gs://bucket/model.idf",
            extra_field="not-allowed",
        )


def test_validation_message_location_optional_fields():
    """MessageLocation should support optional fields."""
    location = MessageLocation(
        file_role="weather",
        line=10,
        column=2,
        path="/Objects/1",
    )
    assert location.file_role == "weather"


def test_validation_output_envelope_defaults_and_status_enum():
    """ValidationOutputEnvelope should have defaults and use status enum."""
    timing = {
        "queued_at": datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        "started_at": datetime(2024, 1, 1, 12, 1, 0, tzinfo=UTC),
        "finished_at": datetime(2024, 1, 1, 12, 2, 0, tzinfo=UTC),
    }

    envelope = ValidationOutputEnvelope(
        run_id="run-99",
        **_output_identity_kwargs(),
        validator={
            "id": "val-1",
            "type": ValidatorType.ENERGYPLUS,
            "version": "1.0",
        },
        status=ValidationStatus.SUCCESS,
        timing=timing,
    )

    assert envelope.schema_version == "validibot.output.v1"
    assert envelope.messages == []
    assert envelope.metrics == []
    assert envelope.outputs is None


def test_validation_output_envelope_rejects_invalid_status():
    """ValidationOutputEnvelope should reject invalid status."""
    timing = {"queued_at": None, "started_at": None, "finished_at": None}

    with pytest.raises(ValidationError):
        ValidationOutputEnvelope(
            run_id="run-100",
            **_output_identity_kwargs(),
            validator={
                "id": "val-1",
                "type": ValidatorType.ENERGYPLUS,
                "version": "1.0",
            },
            status="bad-status",  # type: ignore[arg-type]
            timing=timing,
        )


def test_validation_callback_serialization():
    """ValidationCallback should serialize correctly."""
    callback = ValidationCallback(
        run_id="run-101",
        status=ValidationStatus.FAILED_RUNTIME,
        result_uri="gs://bucket/run-101/output.json",
    )

    assert callback.status is ValidationStatus.FAILED_RUNTIME


def test_validation_message_enforces_severity_enum():
    """ValidationMessage should enforce severity enum."""
    message = ValidationMessage(
        severity=Severity.ERROR,
        code="E100",
        text="Something went wrong",
    )

    assert message.severity is Severity.ERROR

    with pytest.raises(ValidationError):
        ValidationMessage(severity="fatal", text="not allowed")  # type: ignore[arg-type]
