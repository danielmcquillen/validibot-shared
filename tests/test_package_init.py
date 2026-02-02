"""Tests for package-level exports."""

from validibot_shared import (
    EnergyPlusSimulationLogs,
    EnergyPlusSimulationMetrics,
    EnergyPlusSimulationOutputs,
    FMIProbeResult,
    FMIVariableMeta,
    __all__,
)


def test_public_exports_match_symbols():
    """All __all__ exports should be importable and have correct names."""
    expected_exports = [
        "EnergyPlusSimulationLogs",
        "EnergyPlusSimulationMetrics",
        "EnergyPlusSimulationOutputs",
        "FMIProbeResult",
        "FMIVariableMeta",
    ]

    for name in expected_exports:
        assert name in __all__

    # Verify the classes are correctly imported
    assert EnergyPlusSimulationLogs.__name__ == "EnergyPlusSimulationLogs"
    assert EnergyPlusSimulationMetrics.__name__ == "EnergyPlusSimulationMetrics"
    assert EnergyPlusSimulationOutputs.__name__ == "EnergyPlusSimulationOutputs"
    assert FMIProbeResult.__name__ == "FMIProbeResult"
    assert FMIVariableMeta.__name__ == "FMIVariableMeta"
