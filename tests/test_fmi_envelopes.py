"""Tests for FMI envelope models."""

import pytest
from pydantic import ValidationError

from validibot_shared.fmi.envelopes import (
    FMIInputEnvelope,
    FMIOutputs,
    FMISimulationConfig,
    build_fmi_input_envelope,
)
from validibot_shared.validations.envelopes import ExecutionContext, ValidatorType

# Test constants
TEST_EXECUTION_SECONDS = 2.5
TEST_STOP_TIME = 10


def _base_kwargs():
    return {
        "run_id": "run-123",
        "validator": {"id": "val-1", "type": ValidatorType.FMI, "version": "1.0"},
        "org": {"id": "org-1", "name": "ValidiBot"},
        "workflow": {"id": "wf-1", "step_id": "step-1", "step_name": "FMI"},
        "context": ExecutionContext(
            callback_url="https://example.com/cb",
            execution_bundle_uri="gs://bucket/run-123/",
        ),
    }


def test_fmi_outputs_validation():
    """FMIOutputs should validate correctly."""
    outputs = FMIOutputs(
        output_values={"y": 1.0},
        execution_seconds=TEST_EXECUTION_SECONDS,
        simulation_time_reached=1.5,
    )

    assert outputs.output_values["y"] == 1.0
    assert outputs.execution_seconds == TEST_EXECUTION_SECONDS

    with pytest.raises(ValidationError):
        FMIOutputs(
            output_values={},
            execution_seconds=-1,
            simulation_time_reached=0,
        )


def test_fmi_input_envelope_requires_typed_inputs():
    """FMIInputEnvelope should require typed inputs."""
    envelope = FMIInputEnvelope(
        **_base_kwargs(),
        input_files=[],
        inputs={
            "input_values": {"setpoint": 22},
            "simulation": {
                "start_time": 0,
                "stop_time": TEST_STOP_TIME,
                "step_size": 1,
            },
            "output_variables": ["y"],
        },
    )

    assert envelope.inputs.simulation.stop_time == TEST_STOP_TIME
    assert envelope.inputs.output_variables == ["y"]

    with pytest.raises(ValidationError):
        FMIInputEnvelope(
            **_base_kwargs(),
            input_files=[],
            inputs={"simulation": {"stop_time": -1}},
        )


def test_build_fmi_input_envelope_constructs_expected_payload():
    """build_fmi_input_envelope should construct the expected payload."""
    envelope = build_fmi_input_envelope(
        run_id="run-1",
        validator=type(
            "Validator",
            (),
            {"id": 1, "validation_type": ValidatorType.FMI, "version": "0.1.0"},
        )(),
        org_id="org-1",
        org_name="ValidiBot",
        workflow_id="wf-1",
        step_id="step-1",
        step_name="Simulate",
        fmu_uri="gs://bucket/model.fmu",
        input_values={"u1": 1.0},
        callback_url="https://example.com/callback",
        execution_bundle_uri="gs://bucket/run-1/",
        output_variables=["y"],
    )

    assert envelope.inputs.output_variables == ["y"]
    assert envelope.input_files[0].role == "fmu"
    assert str(envelope.context.callback_url) == "https://example.com/callback"


def test_simulation_config_enforces_positive_values():
    """FMISimulationConfig should enforce positive values."""
    with pytest.raises(ValidationError):
        FMISimulationConfig(stop_time=0)
