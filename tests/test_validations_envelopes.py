"""Tests for validation envelope models."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from validibot_shared.validations.envelopes import (
    ExecutionContext,
    InputFileItem,
    MessageLocation,
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
        ),
    }


def test_validation_input_envelope_defaults_schema_version():
    """ValidationInputEnvelope should have default schema version."""
    envelope = ValidationInputEnvelope(**_base_input_envelope_kwargs())

    assert envelope.schema_version == "validibot.input.v1"
    assert envelope.input_files[0].role == "primary-model"
    assert envelope.inputs == {}


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
