# validibot-shared

Shared Pydantic models for [Validibot](https://validibot.com) validator containers.

This library defines the data interchange types used between Validibot and its advanced validator services, ensuring type safety and contract consistency.

## Installation

```bash
pip install validibot-shared
```

Or with uv:

```bash
uv add validibot-shared
```

## Package Structure

```
validibot_shared/
├── validations/          # Base validation envelope schemas
│   └── envelopes.py     # Input/output envelopes for all validators
├── energyplus/          # EnergyPlus-specific models and envelopes
│   ├── models.py        # Simulation output models
│   └── envelopes.py     # Typed envelope subclasses
└── fmi/                 # FMI/FMU-specific models
    ├── models.py        # Probe result models
    └── envelopes.py     # FMI envelope subclasses
```

## Core Concepts

### Validation Envelopes

The library provides base envelope classes for validator communication:

- `ValidationInputEnvelope` - Standard input format for validation jobs
- `ValidationOutputEnvelope` - Standard output format with results
- `ValidationCallback` - Callback payload for async job completion

Supporting classes include `InputFileItem`, `ValidatorInfo`, `ExecutionContext`, `ValidationMessage`, `ValidationMetric`, and `ValidationArtifact`.

### Typed Subclassing Pattern

Domain-specific validators extend the base envelopes with typed fields:

```python
from validibot_shared.energyplus import EnergyPlusInputEnvelope, EnergyPlusInputs

# The envelope has typed inputs instead of dict[str, Any]
envelope = EnergyPlusInputEnvelope(
    run_id="abc-123",
    inputs=EnergyPlusInputs(timestep_per_hour=4),
    # ... other fields
)

# IDE autocomplete and type checking work
timestep = envelope.inputs.timestep_per_hour
```

This provides:

- **Type safety** - mypy/pyright catch errors at compile time
- **Runtime validation** - Pydantic validates all data
- **IDE support** - Full autocomplete for domain-specific fields

## Usage Examples

### Creating an Input Envelope

```python
from validibot_shared.energyplus import EnergyPlusInputEnvelope, EnergyPlusInputs
from validibot_shared.validations.envelopes import (
    InputFileItem,
    ValidatorInfo,
    ExecutionContext,
)

envelope = EnergyPlusInputEnvelope(
    run_id="run-123",
    validator=ValidatorInfo(id="v1", type="energyplus", version="24.2.0"),
    input_files=[
        InputFileItem(
            name="model.idf",
            mime_type="application/vnd.energyplus.idf",
            role="primary-model",
            uri="gs://bucket/model.idf",
        ),
    ],
    inputs=EnergyPlusInputs(timestep_per_hour=4),
    context=ExecutionContext(
        callback_url="https://api.example.com/callback",
        execution_bundle_uri="gs://bucket/run-123/",
    ),
)
```

### Deserializing Results

```python
from validibot_shared.energyplus import EnergyPlusOutputEnvelope

# Parse JSON response from validator
envelope = EnergyPlusOutputEnvelope.model_validate_json(response_json)

# Access typed outputs
if envelope.outputs:
    print(f"EUI: {envelope.outputs.metrics.eui_kbtu_per_sqft}")
```

### FMI Probe Results

```python
from validibot_shared.fmi.models import FMIProbeResult, FMIVariableMeta

# Create a successful probe result
result = FMIProbeResult.success(
    variables=[
        FMIVariableMeta(name="temperature", causality="output", value_type="Real"),
    ],
    execution_seconds=0.5,
)

# Create a failure result
result = FMIProbeResult.failure(errors=["Invalid FMU: missing modelDescription.xml"])
```

## Dependencies

- `pydantic>=2.8.0`

## License

MIT License - see [LICENSE](LICENSE) for details.
