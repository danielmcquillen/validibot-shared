"""
Reusable EnergyPlus output models.

These models represent EnergyPlus simulation outputs and are used as components
within the typed envelope classes (see envelopes.py).

They are kept separate from envelopes to follow the single responsibility principle:
- These models: What data EnergyPlus produces (files, metrics, logs)
- Envelope classes: How that data is packaged for Django ↔ validator communication
"""

from __future__ import annotations

from pathlib import Path  # noqa: TC003
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

# Useful constants for log tailing
STDOUT_TAIL_CHARS = 4000
LOG_TAIL_LINES = 200

# Type alias for invocation modes
InvocationMode = Literal["python_api", "cli"]

# Type aliases for non-negative numbers
NonNegFloat = Annotated[float, Field(ge=0)]
NonNegInt = Annotated[int, Field(ge=0)]


class EnergyPlusSimulationOutputs(BaseModel):
    """
    EnergyPlus output file paths.

    Tracks the standard EnergyPlus output files produced by a simulation.
    Used within EnergyPlusOutputs (in envelopes.py) to preserve file locations.
    """

    model_config = ConfigDict(extra="forbid")
    eplusout_sql: Path | None = None
    eplusout_err: Path | None = None
    eplusout_csv: Path | None = None
    eplusout_eso: Path | None = None


class EnergyPlusSimulationMetrics(BaseModel):
    """
    Extracted EnergyPlus simulation metrics.

    These are the core output signals extracted from EnergyPlus simulation results.
    Field names here must match the binding_config["key"] values in the EnergyPlus
    provider catalog (see validibot/validations/providers/energyplus.py).

    The validator extracts these values from the EnergyPlus SQL database
    (eplusout.sql) and they become available as output signals for assertions.
    """

    model_config = ConfigDict(extra="forbid")

    # ==========================================================================
    # Energy Consumption (from EnergyPlus meters)
    # ==========================================================================

    # Total site electricity consumption
    site_electricity_kwh: NonNegFloat | None = None

    # Total natural gas consumption
    site_natural_gas_kwh: NonNegFloat | None = None

    # District cooling energy (if present in model)
    site_district_cooling_kwh: NonNegFloat | None = None

    # District heating energy (if present in model)
    site_district_heating_kwh: NonNegFloat | None = None

    # ==========================================================================
    # Energy Use Intensity
    # ==========================================================================

    # Site EUI (total energy / floor area)
    site_eui_kwh_m2: NonNegFloat | None = None

    # ==========================================================================
    # End-Use Breakdown (all fuels combined)
    # ==========================================================================

    # Space heating energy
    heating_energy_kwh: NonNegFloat | None = None

    # Space cooling energy
    cooling_energy_kwh: NonNegFloat | None = None

    # Interior lighting energy
    interior_lighting_kwh: NonNegFloat | None = None

    # Fan energy (supply, return, exhaust)
    fans_energy_kwh: NonNegFloat | None = None

    # Pump energy (chilled water, hot water, condenser)
    pumps_energy_kwh: NonNegFloat | None = None

    # Domestic hot water energy
    water_systems_kwh: NonNegFloat | None = None

    # ==========================================================================
    # Comfort / Performance
    # ==========================================================================

    # Hours heating setpoint not met
    unmet_heating_hours: NonNegFloat | None = None

    # Hours cooling setpoint not met
    unmet_cooling_hours: NonNegFloat | None = None

    # Peak electric demand
    peak_electric_demand_w: NonNegFloat | None = None

    # ==========================================================================
    # Building Characteristics (from IDF/SQL)
    # ==========================================================================

    # Total conditioned floor area
    floor_area_m2: NonNegFloat | None = None

    # Number of thermal zones
    zone_count: NonNegInt | None = None


class EnergyPlusSimulationLogs(BaseModel):
    """
    EnergyPlus execution logs.

    Tails of stdout, stderr, and the eplusout.err file for debugging failed simulations.
    Tails are used instead of full logs to keep envelope sizes reasonable.
    """

    model_config = ConfigDict(extra="forbid")
    stdout_tail: str | None = None
    stderr_tail: str | None = None
    err_tail: str | None = None
