# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.5.1] - 2026-05-02

### Changed

- Loosened the `pydantic` dependency from the strict `==2.13.3` pin
  to a `>=2.13,<3` range. Strict pins on shared-library dependencies
  break universal resolution for downstream projects whose
  `requires-python` window extends past pydantic's classifier
  range. Libraries should pin a band, not a point.

## [0.5.0] - 2026-05-02

### Added

- ``validibot_shared.evidence`` module exposing the
  ``validibot.evidence.v1`` Pydantic schema for run-completion
  evidence manifests. Public symbols: ``EvidenceManifest``,
  ``WorkflowContractSnapshot``, ``StepValidatorRecord``,
  ``ManifestRetentionInfo``, ``ManifestPayloadDigests``,
  ``SCHEMA_VERSION``. Lives in shared so external verifiers can
  depend on a single PyPI package without pulling in the Django
  application stack. See ADR-2026-04-27 (Validibot Trust ADR),
  Phase 4 Session A.

## [0.4.4] - 2026-03-25

### Changed

- Updated dependencies. 

## [0.4.3] - 2026-03-25

### Changed

- Updated dependencies. 
- Renaming validibot-validators project.

## [0.4.2] - 2026-03-25

### Fixed

- Pinned the runtime and development dependencies to exact versions so shared package installs stay reproducible across rebuilds.

## [0.4.1] - 2026-03-20

### Fixed

- Updated the README EnergyPlus input-envelope example to use the current
  enum values and required `org`/`workflow` fields.
- Corrected the documented developer test command to
  `uv run python -m pytest` and removed the stale `mypy src/` command.

## 0.4.0

### Changed

- **FMU envelopes**: Clarified that `input_values`, `output_variables`,
  and `output_values` are keyed by native FMU variable names (from
  modelDescription.xml), not internal catalog slugs. No wire format
  change — this documents the contract that was already in practice.
- **FMU models**: Probe results now feed into `SignalDefinition` rows
  in the core Django app (previously documented as "catalog entries").
- **EnergyPlus models**: `EnergyPlusSimulationMetrics` field names are
  now documented as the canonical EnergyPlus signal names expected by
  core Validibot, mapped to `SignalDefinition` rows.

## [0.3.1] - 2026-03-10

### Added

- Window envelope metrics on `EnergyPlusSimulationMetrics`: `window_heat_gain_kwh`,
  `window_heat_loss_kwh`, `window_transmitted_solar_kwh`. These are extracted from
  EnergyPlus output variables (`Surface Window Heat Gain Energy`, etc.) and will be
  `None` when the corresponding `Output:Variable` objects are not present in the IDF.

## [0.3.0] - 2026-02-25

### Changed

- **BREAKING**: Renamed `fmi` module to `fmu` throughout the library
  - `validibot_shared.fmi` -> `validibot_shared.fmu`
  - All class names: `FMIInputEnvelope` -> `FMUInputEnvelope`, `FMIOutputEnvelope` -> `FMUOutputEnvelope`, `FMISimulationConfig` -> `FMUSimulationConfig`, `FMIInputs` -> `FMUInputs`, `FMIOutputs` -> `FMUOutputs`, `FMIProbeResult` -> `FMUProbeResult`, `FMIVariableMeta` -> `FMUVariableMeta`
  - Function: `build_fmi_input_envelope()` -> `build_fmu_input_envelope()`
  - Enum: `ValidatorType.FMI` -> `ValidatorType.FMU`
  - The `fmi_version` field on `FMUOutputs` is unchanged (refers to the FMI standard version)

## [0.2.1] - 2026-02-16

### Added

- Pre-commit hooks with TruffleHog secret scanning, detect-private-key, and Ruff linting
- Dependabot configuration for GitHub Actions and Python dependency updates
- Hardened .gitignore to exclude key material and credential files
- pip-audit dependency auditing in CI
- Sigstore attestations for PyPI publish (provenance verification)

### Changed

- Pinned all GitHub Actions to commit SHAs and uv to exact version in publish and test workflows
