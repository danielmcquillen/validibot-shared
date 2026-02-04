<div align="center">

# Validibot Shared

**Shared Pydantic models for Validibot Advanced Validator containers**

[![PyPI version](https://badge.fury.io/py/validibot-shared.svg)](https://pypi.org/project/validibot-shared/)
[![Python versions](https://img.shields.io/pypi/pyversions/validibot-shared.svg)](https://pypi.org/project/validibot-shared/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[Installation](#installation) •
[Core Concepts](#core-concepts) •
[Usage](#usage-examples) •
[API Reference](#api-reference)

</div>

---

> [!NOTE]
> This library is part of the [Validibot](https://github.com/danielmcquillen/validibot) open-source data validation platform. It defines the data interchange contract between the core platform and advanced validator containers.

---

## Part of the Validibot Project

| Repository | Description |
|------------|-------------|
| **[validibot](https://github.com/danielmcquillen/validibot)** | Core platform — web UI, REST API, workflow engine |
| **[validibot-cli](https://github.com/danielmcquillen/validibot-cli)** | Command-line interface |
| **[validibot-validators](https://github.com/danielmcquillen/validibot-validators)** | Advanced validator containers (EnergyPlus, FMI) |
| **[validibot-shared](https://github.com/danielmcquillen/validibot-shared)** (this repo) | Shared Pydantic models for data interchange |

---

## What is Validibot Shared?

Validibot Shared provides the Pydantic models that define how the Validibot core platform communicates with advanced validator containers. When Validibot needs to run a complex validation (like an EnergyPlus simulation or FMU probe), it:

1. **Creates an input envelope** containing the files to validate and configuration
2. **Launches a validator container** with the envelope as input
3. **Receives an output envelope** with validation results, metrics, and artifacts

This library ensures both sides speak the same language with full type safety and runtime validation.

## Features

- **Type-safe envelopes** — Pydantic models with full IDE autocomplete and type checking
- **Runtime validation** — Automatic validation of all data at serialization boundaries
- **Domain-specific extensions** — Typed subclasses for EnergyPlus, FMI, and custom validators
- **Lightweight** — Only depends on Pydantic, no heavy dependencies

## Installation

```bash
# Using pip
pip install validibot-shared

# Using uv (recommended)
uv add validibot-shared

# Using poetry
poetry add validibot-shared
```

### Requirements

- Python 3.10 or later
- Pydantic 2.8.0 or later

## Core Concepts

### The Envelope Pattern

Validibot uses an "envelope" pattern for validator communication. Every validation job is wrapped in a standardized envelope that carries:

- **Job metadata** — Run ID, validator info, execution context
- **Input files** — References to files being validated (URIs, not raw data)
- **Configuration** — Validator-specific settings
- **Results** — Status, messages, metrics, and artifacts (output only)

```
┌─────────────────────────────────────────────────────────────────┐
│                    Validibot Core Platform                      │
│                                                                 │
│  1. Creates ValidationInputEnvelope with:                       │
│     • run_id, validator info                                    │
│     • input_files[] (GCS/S3 URIs)                               │
│     • inputs (validator-specific config)                        │
│     • callback_url for async notification                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ JSON
┌─────────────────────────────────────────────────────────────────┐
│                    Validator Container                          │
│                    (EnergyPlus, FMI, etc.)                      │
│                                                                 │
│  1. Parses input envelope                                       │
│  2. Downloads input files from URIs                             │
│  3. Runs validation/simulation                                  │
│  4. Creates ValidationOutputEnvelope with results               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ JSON (callback or response)
┌─────────────────────────────────────────────────────────────────┐
│                    Validibot Core Platform                      │
│                                                                 │
│  1. Receives output envelope                                    │
│  2. Parses and validates with Pydantic                          │
│  3. Stores findings, metrics, artifacts                         │
└─────────────────────────────────────────────────────────────────┘
```

### Base Envelope Classes

The library provides these base classes in `validibot_shared.validations.envelopes`:

| Class | Purpose |
|-------|---------|
| `ValidationInputEnvelope` | Standard input format for validation jobs |
| `ValidationOutputEnvelope` | Standard output format with results |
| `ValidationCallback` | Callback payload for async job completion |

Supporting models include:

| Class | Purpose |
|-------|---------|
| `InputFileItem` | File reference with URI, MIME type, and role |
| `ValidatorInfo` | Validator identification (ID, type, version) |
| `ExecutionContext` | Callback URL, execution bundle URI, timeout |
| `ValidationMessage` | Individual finding (error, warning, info) |
| `ValidationMetric` | Named numeric metric with optional unit |
| `ValidationArtifact` | Output file reference (reports, logs, etc.) |

### Typed Subclassing Pattern

Domain-specific validators extend the base envelopes with typed fields. This gives you:

- **Type safety** — mypy/pyright catch errors at compile time
- **Runtime validation** — Pydantic validates all data
- **IDE support** — Full autocomplete for domain-specific fields

```python
from validibot_shared.energyplus import EnergyPlusInputEnvelope, EnergyPlusInputs

# The envelope has typed inputs instead of dict[str, Any]
envelope = EnergyPlusInputEnvelope(
    run_id="abc-123",
    inputs=EnergyPlusInputs(timestep_per_hour=4),
    # ... other fields
)

# IDE autocomplete and type checking work
timestep = envelope.inputs.timestep_per_hour  # ✓ Known to be int
```

## Package Structure

```
validibot_shared/
├── validations/           # Base validation envelope schemas
│   └── envelopes.py      # Input/output envelopes for all validators
├── energyplus/           # EnergyPlus-specific models and envelopes
│   ├── models.py         # Simulation output models (metrics, results)
│   └── envelopes.py      # Typed envelope subclasses
└── fmi/                  # FMI/FMU-specific models
    ├── models.py         # Probe result models
    └── envelopes.py      # FMI envelope subclasses
```

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

# Serialize to JSON for the validator container
json_payload = envelope.model_dump_json()
```

### Deserializing Results

```python
from validibot_shared.energyplus import EnergyPlusOutputEnvelope

# Parse JSON response from validator
envelope = EnergyPlusOutputEnvelope.model_validate_json(response_json)

# Check status
if envelope.status == "success":
    # Access typed outputs with full autocomplete
    if envelope.outputs and envelope.outputs.metrics:
        print(f"EUI: {envelope.outputs.metrics.eui_kbtu_per_sqft} kBtu/sqft")

# Iterate over validation messages
for message in envelope.messages:
    print(f"[{message.severity}] {message.text}")
```

### FMI Probe Results

```python
from validibot_shared.fmi.models import FMIProbeResult, FMIVariableMeta

# Create a successful probe result
result = FMIProbeResult.success(
    variables=[
        FMIVariableMeta(name="temperature", causality="output", value_type="Real"),
        FMIVariableMeta(name="pressure", causality="output", value_type="Real"),
    ],
    execution_seconds=0.5,
)

# Create a failure result
result = FMIProbeResult.failure(
    errors=["Invalid FMU: missing modelDescription.xml"]
)

# Serialize for response
json_response = result.model_dump_json()
```

### Creating a Custom Validator

If you're building a custom validator, create typed envelope subclasses:

```python
from pydantic import BaseModel
from validibot_shared.validations.envelopes import (
    ValidationInputEnvelope,
    ValidationOutputEnvelope,
)

# Define your validator's input configuration
class MyValidatorInputs(BaseModel):
    strict_mode: bool = False
    max_errors: int = 100

# Define your validator's output data
class MyValidatorOutputs(BaseModel):
    items_checked: int
    items_passed: int

# Create typed envelope subclasses
class MyValidatorInputEnvelope(ValidationInputEnvelope):
    inputs: MyValidatorInputs

class MyValidatorOutputEnvelope(ValidationOutputEnvelope):
    outputs: MyValidatorOutputs | None = None
```

## API Reference

### ValidationInputEnvelope

```python
class ValidationInputEnvelope(BaseModel):
    run_id: str                      # Unique identifier for this validation run
    validator: ValidatorInfo         # Validator identification
    input_files: list[InputFileItem] # Files to validate
    inputs: dict[str, Any]           # Validator-specific configuration
    context: ExecutionContext        # Callback URL, bundle URI, etc.
```

### ValidationOutputEnvelope

```python
class ValidationOutputEnvelope(BaseModel):
    run_id: str                          # Matches input run_id
    status: str                          # "success", "failure", "error"
    messages: list[ValidationMessage]    # Validation findings
    metrics: list[ValidationMetric]      # Numeric metrics
    artifacts: list[ValidationArtifact]  # Output files
    outputs: dict[str, Any] | None       # Validator-specific results
    execution_seconds: float | None      # Execution time
```

### ValidationMessage

```python
class ValidationMessage(BaseModel):
    severity: str    # "error", "warning", "info"
    code: str | None # Machine-readable code
    text: str        # Human-readable message
    location: str | None  # File/line reference
```

## Part of the Validibot Project

This library is one component of the Validibot open-source data validation platform:

| Repository | Description |
|------------|-------------|
| **[validibot](https://github.com/danielmcquillen/validibot)** | Core platform — web UI, REST API, workflow engine |
| **[validibot-cli](https://github.com/danielmcquillen/validibot-cli)** | Command-line interface |
| **[validibot-validators](https://github.com/danielmcquillen/validibot-validators)** | Advanced validator containers (EnergyPlus, FMI) |
| **[validibot-shared](https://github.com/danielmcquillen/validibot-shared)** (this repo) | Shared Pydantic models for data interchange |

### How It Fits Together

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              End Users                                       │
│                    (Web UI, CLI, REST API clients)                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         validibot (core platform)                            │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Web UI  │  REST API  │  Workflow Engine  │  Built-in Validators   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│            Triggers Docker containers for advanced validations              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         ▼                          ▼                          ▼
┌─────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│ validibot-cli   │    │ validibot-validators│    │ validibot-shared    │
│                 │    │                     │    │  (this repo)        │
│ Terminal access │    │ EnergyPlus, FMI     │    │                     │
│ to API          │    │ containers          │    │ Pydantic models     │
│                 │    │        │            │    │ (shared contract)   │
└─────────────────┘    └────────┼────────────┘    └─────────────────────┘
                                │                          ▲
                                └──────────────────────────┘
                                   validators import shared
                                   models for type safety
```

## Development

```bash
# Clone the repository
git clone https://github.com/danielmcquillen/validibot-shared.git
cd validibot-shared

# Install with dev dependencies
uv sync --extra dev

# Run tests
uv run pytest

# Run linter
uv run ruff check .

# Run type checker
uv run mypy src/
```

## License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

[Validibot Platform](https://github.com/danielmcquillen/validibot) •
[Documentation](https://docs.validibot.com) •
[Report Issues](https://github.com/danielmcquillen/validibot-shared/issues)

</div>
