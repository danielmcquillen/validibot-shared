"""Tests for EnergyPlus simulation models."""

import pytest
from pydantic import ValidationError

from validibot_shared.energyplus.models import (
    LOG_TAIL_LINES,
    STDOUT_TAIL_CHARS,
    EnergyPlusSimulationLogs,
    EnergyPlusSimulationMetrics,
    EnergyPlusSimulationOutputs,
)

# Test constants
EXPECTED_STDOUT_TAIL_CHARS = 4000
EXPECTED_LOG_TAIL_LINES = 200
TEST_NATURAL_GAS_KWH = 15.2
TEST_EUI_KWH_M2 = 42.0


def test_log_tail_constants():
    """Log tail constants should have expected values."""
    assert STDOUT_TAIL_CHARS == EXPECTED_STDOUT_TAIL_CHARS
    assert LOG_TAIL_LINES == EXPECTED_LOG_TAIL_LINES


def test_simulation_outputs_forbids_extra_fields():
    """EnergyPlusSimulationOutputs should forbid extra fields."""
    with pytest.raises(ValidationError):
        EnergyPlusSimulationOutputs(unknown_field="not-allowed")


def test_simulation_metrics_rejects_negative_values():
    """EnergyPlusSimulationMetrics should reject negative values."""
    with pytest.raises(ValidationError):
        EnergyPlusSimulationMetrics(site_electricity_kwh=-1)


def test_simulation_metrics_accepts_non_negative_values():
    """EnergyPlusSimulationMetrics should accept non-negative values."""
    metrics = EnergyPlusSimulationMetrics(
        site_electricity_kwh=0.0,
        site_natural_gas_kwh=TEST_NATURAL_GAS_KWH,
        site_eui_kwh_m2=TEST_EUI_KWH_M2,
    )

    assert metrics.site_electricity_kwh == 0.0
    assert metrics.site_natural_gas_kwh == TEST_NATURAL_GAS_KWH
    assert metrics.site_eui_kwh_m2 == TEST_EUI_KWH_M2


def test_simulation_logs_forbids_extra_fields():
    """EnergyPlusSimulationLogs should forbid extra fields."""
    with pytest.raises(ValidationError):
        EnergyPlusSimulationLogs(stdout_tail="ok", extra_field="nope")
