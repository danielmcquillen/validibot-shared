"""Tests for FMI model classes."""

import pytest
from pydantic import ValidationError

from validibot_shared.fmi.models import FMIProbeResult, FMIVariableMeta


def test_fmi_variable_meta_forbids_extra_fields():
    """FMIVariableMeta should forbid extra fields."""
    with pytest.raises(ValidationError):
        FMIVariableMeta(
            name="x",
            causality="input",
            value_type="Real",
            extra_field=True,
        )


def test_fmi_probe_result_builders():
    """FMIProbeResult builders should work correctly."""
    variable = FMIVariableMeta(name="x", causality="input", value_type="Real")
    success = FMIProbeResult.success(variables=[variable])
    failure = FMIProbeResult.failure(errors=["bad fmu"])

    assert success.status == "success"
    assert len(success.variables) == 1
    assert failure.status == "error"
    assert failure.errors == ["bad fmu"]
