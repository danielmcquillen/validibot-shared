"""
Pydantic envelopes for FMI Advanced validator jobs.

FMI is an Advanced validator - it runs in a separate container/service rather
than within the Django app. These schemas define the contract between Django
and the FMI validator container:
- Input envelope: FMU URI plus resolved input values and simulation config
- Output envelope: FMI outputs, metrics, messages, and artifacts

Inputs/outputs are keyed by validator catalog slugs. Workflow authors cannot
remap signals; bindings live on catalog entries (input_binding_path) and
default to slug-name lookups.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from validibot_shared.validations.envelopes import (
    ExecutionContext,
    InputFileItem,
    SupportedMimeType,
    ValidationInputEnvelope,
    ValidationOutputEnvelope,
    ValidatorType,
)


class FMISimulationConfig(BaseModel):
    """Simulation configuration for FMI runs."""

    start_time: float = Field(
        default=0.0,
        description="Simulation start time (seconds).",
        ge=0,
    )
    stop_time: float = Field(
        default=1.0,
        description="Simulation stop time (seconds).",
        gt=0,
    )
    step_size: float = Field(
        default=0.01,
        description="Communication step size (seconds).",
        gt=0,
    )
    tolerance: float | None = Field(
        default=None,
        description="Solver tolerance, if supported by the FMU.",
        gt=0,
    )


class FMIInputs(BaseModel):
    """Resolved inputs plus simulation config, keyed by catalog slugs."""

    input_values: dict[str, Any] = Field(
        default_factory=dict,
        description="Input values keyed by catalog slugs.",
    )
    simulation: FMISimulationConfig = Field(
        default_factory=FMISimulationConfig,
        description="Simulation time/step configuration.",
    )
    output_variables: list[str] = Field(
        default_factory=list,
        description=(
            "Catalog slugs to capture as outputs. Empty means all output slugs."
        ),
    )


class FMIOutputs(BaseModel):
    """FMI execution results keyed by catalog slugs."""

    output_values: dict[str, Any] = Field(
        default_factory=dict,
        description="Output values keyed by catalog slugs.",
    )
    fmu_guid: str | None = Field(default=None, description="FMU GUID, if reported.")
    fmi_version: str | None = Field(default=None, description="FMI version.")
    model_name: str | None = Field(default=None, description="FMU model name.")
    execution_seconds: float = Field(
        description="Wall-clock execution time (seconds).",
        ge=0,
    )
    simulation_time_reached: float = Field(
        description="Simulation time reached before completion/stop.",
        ge=0,
    )
    fmu_log: str | None = Field(
        default=None,
        description="Optional FMU log output.",
    )


class FMIInputEnvelope(ValidationInputEnvelope):
    """Input envelope for FMI validator containers."""

    inputs: FMIInputs


class FMIOutputEnvelope(ValidationOutputEnvelope):
    """Output envelope from FMI validator containers.

    Note: outputs can be None for failure cases where simulation didn't complete.
    """

    outputs: FMIOutputs | None = None


def build_fmi_input_envelope(
    *,
    run_id: str,
    validator,
    org_id: str,
    org_name: str,
    workflow_id: str,
    step_id: str,
    step_name: str | None,
    fmu_uri: str,
    input_values: dict[str, Any],
    callback_url: str,
    execution_bundle_uri: str,
    simulation: FMISimulationConfig | None = None,
    output_variables: list[str] | None = None,
) -> FMIInputEnvelope:
    """
    Build an FMIInputEnvelope from Django validation data.

    Args:
        run_id: ValidationRun ID
        validator: Validator-like object (id/type/version attrs)
        org_id: Organization ID
        org_name: Organization name
        workflow_id: Workflow ID
        step_id: Workflow step ID
        step_name: Optional step name
        fmu_uri: FMU storage URI (gs://... or local path in dev)
        input_values: Resolved inputs keyed by catalog slug
        callback_url: URL to POST callback
        execution_bundle_uri: Base URI/path for this run's files
        simulation: Optional FMISimulationConfig
        output_variables: Optional list of catalog slugs to capture (empty=all outputs)
    """

    input_files = [
        InputFileItem(
            name="model.fmu",
            mime_type=SupportedMimeType.FMU,
            role="fmu",
            uri=fmu_uri,
        )
    ]

    envelope_inputs = FMIInputs(
        input_values=input_values,
        simulation=simulation or FMISimulationConfig(),
        output_variables=output_variables or [],
    )

    context = ExecutionContext(
        callback_url=callback_url,
        execution_bundle_uri=execution_bundle_uri,
    )

    envelope = FMIInputEnvelope(
        run_id=run_id,
        validator={
            "id": str(validator.id),
            "type": ValidatorType(validator.validation_type),
            "version": getattr(validator, "version", "1.0.0"),
        },
        org={
            "id": org_id,
            "name": org_name,
        },
        workflow={
            "id": workflow_id,
            "step_id": step_id,
            "step_name": step_name,
        },
        input_files=input_files,
        inputs=envelope_inputs,
        context=context,
    )

    return envelope
