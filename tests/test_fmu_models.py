"""Tests for FMU model classes."""

import pytest
from pydantic import ValidationError

from validibot_shared.fmu.models import FMUProbeResult, FMUVariableMeta


def test_fmu_variable_meta_forbids_extra_fields():
    """FMUVariableMeta should forbid extra fields."""
    with pytest.raises(ValidationError):
        FMUVariableMeta(
            name="x",
            causality="input",
            value_type="Real",
            extra_field=True,
        )


def test_fmu_probe_result_builders():
    """FMUProbeResult builders should work correctly."""
    variable = FMUVariableMeta(name="x", causality="input", value_type="Real")
    success = FMUProbeResult.success(variables=[variable])
    failure = FMUProbeResult.failure(errors=["bad fmu"])

    assert success.status == "success"
    assert len(success.variables) == 1
    assert failure.status == "error"
    assert failure.errors == ["bad fmu"]
