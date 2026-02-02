"""
FMI probe result models.

These models define the contract for FMU probing operations - extracting
metadata from modelDescription.xml to populate validator catalog entries.

Probing is done in-process in the Django worker (not in containers) since
it's just XML parsing with no FMU execution.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FMIVariableMeta(BaseModel):
    """Metadata extracted from modelDescription.xml."""

    model_config = ConfigDict(extra="forbid")

    name: str
    causality: str
    variability: str | None = None
    value_reference: int = 0
    value_type: str
    unit: str | None = None


class FMIProbeResult(BaseModel):
    """Result of a short probe run to vet an FMU before approval."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["success", "error"] = "error"
    variables: list[FMIVariableMeta] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    messages: list[str] = Field(default_factory=list)
    execution_seconds: float | None = None

    @classmethod
    def success(
        cls,
        *,
        variables: list[FMIVariableMeta],
        execution_seconds: float | None = None,
        messages: list[str] | None = None,
    ) -> FMIProbeResult:
        return cls(
            status="success",
            variables=variables,
            execution_seconds=execution_seconds,
            messages=messages or [],
            errors=[],
        )

    @classmethod
    def failure(
        cls,
        *,
        errors: list[str],
        messages: list[str] | None = None,
    ) -> FMIProbeResult:
        return cls(
            status="error",
            variables=[],
            errors=errors,
            messages=messages or [],
        )
