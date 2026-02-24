# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
