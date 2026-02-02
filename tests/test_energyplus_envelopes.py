from pathlib import Path

import pytest
from pydantic import ValidationError

from validibot_shared.energyplus.envelopes import (
    EnergyPlusInputEnvelope,
    EnergyPlusInputs,
    EnergyPlusOutputEnvelope,
    EnergyPlusOutputs,
)
from validibot_shared.validations.envelopes import (
    ExecutionContext,
    InputFileItem,
    SupportedMimeType,
    ValidationStatus,
    ValidatorType,
)

# Test constants to avoid magic values
DEFAULT_TIMESTEP_PER_HOUR = 4
TEST_TIMESTEP_PER_HOUR = 6
TEST_ELECTRICITY_KWH = 123.4
TEST_EXECUTION_SECONDS = 12.5
TEST_EUI_KWH_M2 = 10.5


def _base_input_envelope_kwargs():
    return {
        "run_id": "run-1",
        "validator": {
            "id": "val-1",
            "type": ValidatorType.ENERGYPLUS,
            "version": "1.0",
        },
        "org": {"id": "org-1", "name": "ValidiBot"},
        "workflow": {"id": "wf-1", "step_id": "step-1", "step_name": "EnergyPlus"},
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
            execution_bundle_uri="gs://bucket/run-1/",
            timeout_seconds=600,
            tags=["smoke"],
        ),
    }


def test_energyplus_inputs_defaults():
    """EnergyPlusInputs should have sensible defaults."""
    inputs = EnergyPlusInputs()

    assert inputs.timestep_per_hour == DEFAULT_TIMESTEP_PER_HOUR
    assert inputs.run_period_days is None
    assert inputs.invocation_mode == "cli"


def test_energyplus_inputs_validation():
    """EnergyPlusInputs should reject invalid values."""
    with pytest.raises(ValidationError):
        EnergyPlusInputs(timestep_per_hour=0)

    with pytest.raises(ValidationError):
        EnergyPlusInputs(invocation_mode="invalid-mode")


def test_energyplus_input_envelope_uses_typed_inputs():
    """EnergyPlusInputEnvelope should parse inputs into EnergyPlusInputs."""
    data = _base_input_envelope_kwargs()
    envelope = EnergyPlusInputEnvelope(
        **data,
        inputs={"timestep_per_hour": TEST_TIMESTEP_PER_HOUR},
    )

    assert isinstance(envelope.inputs, EnergyPlusInputs)
    assert envelope.inputs.timestep_per_hour == TEST_TIMESTEP_PER_HOUR


def test_energyplus_input_envelope_rejects_invalid_inputs():
    """EnergyPlusInputEnvelope should reject invalid input configurations."""
    data = _base_input_envelope_kwargs()

    with pytest.raises(ValidationError):
        EnergyPlusInputEnvelope(
            **data,
            inputs={"timestep_per_hour": 1, "invocation_mode": "bad"},
        )


def test_energyplus_outputs_compose_nested_models():
    """EnergyPlusOutputs should compose nested models correctly."""
    outputs = EnergyPlusOutputs(
        outputs={"eplusout_sql": "outputs/eplusout.sql", "eplusout_err": None},
        metrics={"site_electricity_kwh": TEST_ELECTRICITY_KWH},
        logs={"stdout_tail": "log tail"},
        energyplus_returncode=0,
        execution_seconds=TEST_EXECUTION_SECONDS,
        invocation_mode="python_api",
    )

    assert isinstance(outputs.outputs.eplusout_sql, Path)
    assert outputs.metrics.site_electricity_kwh == TEST_ELECTRICITY_KWH
    assert outputs.logs.stdout_tail == "log tail"
    assert outputs.execution_seconds == TEST_EXECUTION_SECONDS


def test_energyplus_outputs_forbid_extra_fields():
    """EnergyPlusOutputs should forbid extra fields."""
    with pytest.raises(ValidationError):
        EnergyPlusOutputs(
            energyplus_returncode=0,
            execution_seconds=1.0,
            invocation_mode="cli",
            unknown="nope",
        )


def test_energyplus_output_envelope_accepts_typed_outputs():
    """EnergyPlusOutputEnvelope should accept typed outputs."""
    envelope = EnergyPlusOutputEnvelope(
        run_id="run-2",
        validator={
            "id": "val-1",
            "type": ValidatorType.ENERGYPLUS,
            "version": "1.0",
        },
        status=ValidationStatus.SUCCESS,
        timing={"queued_at": None, "started_at": None, "finished_at": None},
        outputs={
            "outputs": {"eplusout_sql": "outputs/eplusout.sql"},
            "metrics": {"site_eui_kwh_m2": TEST_EUI_KWH_M2},
            "energyplus_returncode": 0,
            "execution_seconds": 3.2,
            "invocation_mode": "cli",
        },
    )

    assert isinstance(envelope.outputs, EnergyPlusOutputs)
    assert envelope.outputs.outputs.eplusout_sql.name == "eplusout.sql"
    assert envelope.outputs.metrics.site_eui_kwh_m2 == TEST_EUI_KWH_M2
