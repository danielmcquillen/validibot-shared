# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.7.3] - 2026-05-03

### Fixed

- PyPI OIDC build attestations are now correctly generated and
  recorded against published wheels. The 0.7.2 release published
  successfully but PyPI's trusted-publisher binding was missing
  the workflow filename, so PyPI couldn't match the OIDC token's
  ``workflow_ref`` claim and skipped attestation generation. The
  binding has been corrected on PyPI's side; this release verifies
  the fix end-to-end. No library code changes between 0.7.2 and
  0.7.3 — only the upstream PyPI configuration.

### Note on 0.7.2

0.7.2 is on PyPI and functionally equivalent to 0.7.3, but lacks
the OIDC attestation in PyPI's provenance UI because the
trusted-publisher binding was incomplete at upload time. PyPI
doesn't allow re-attestation of already-uploaded files, so 0.7.2
will permanently show no provenance link. Operators who care about
the PyPI-side attestation should use 0.7.3 or later.

## [0.7.2] - 2026-05-03

### Fixed

- Publish workflow no longer collides with twine's pre-flight check.
  In 0.7.1 the CycloneDX SBOMs were generated into ``dist/``
  alongside the wheel; ``pypa/gh-action-pypi-publish`` treats every
  file in ``dist/`` as a candidate for PyPI upload and rejected the
  ``.cdx.json`` / ``.cdx.xml`` files as ``InvalidDistribution``,
  failing the publish step before the wheel reached PyPI. SBOMs now
  generate into ``sbom/`` so PyPI publish only sees wheels.

### Note on 0.7.1

0.7.1 was tagged and a GitHub release was created, but the wheel did
NOT reach PyPI due to the workflow bug fixed above. The 0.7.1 git
tag remains as a record of the failed release attempt; the v0.7.1
GitHub release retains the SBOM artifacts that were generated before
the publish step failed. Use 0.7.2 for the actual release content
(no library code changed between 0.7.1 and 0.7.2 — only the
workflow).

## [0.7.1] - 2026-05-03

### Added

- CycloneDX SBOM generation in the publish workflow (Trust ADR
  Phase 5 Session D). Each release uploads ``validibot-shared.cdx.json``
  and ``validibot-shared.cdx.xml`` as workflow artifacts and
  attaches them to the GitHub Release alongside the wheel. Combined
  with the OIDC build attestation that PyPI already records via
  ``attestations: true``, this gives downstream operators two
  independent layers of provenance: "did this come from where I
  think?" (OIDC) plus "what's inside it?" (SBOM).
- Signed-tag release flow via ``just release X.Y.Z``. The recipe
  enforces preconditions (clean working tree, on ``main``, version
  bumped, tag doesn't already exist) and signs the tag with the
  maintainer's SSH key before pushing. The ``.allowed_signers``
  file in the repo root carries the maintainer's public key so
  ``git verify-tag`` works out of the box for downstream operators.

## [0.7.0] - 2026-05-02

### Added

- ``StepValidatorRecord.validator_backend_image_digest``: optional
  field carrying the resolved sha256 digest of the validator backend
  container image that executed each step (e.g. ``sha256:abc...`` or
  ``registry/...@sha256:abc...``). Complements the existing
  ``validator_semantic_digest`` field — one describes the validator's
  *configuration*, the other describes the *image bytes that ran*.
  Optional because (a) simple-validator steps run inline without a
  backend, and (b) historical step runs predate the field. Producers
  source the value from a new ``ValidationStepRun.validator_backend_image_digest``
  column populated at execution time (Docker SDK ``RepoDigests`` for
  local runs; Cloud Run Execution metadata for hosted runs). The
  schema-version string stays ``validibot.evidence.v1`` because the
  change is additive — verifiers running an older shared version
  silently ignore the unknown key. ADR-2026-04-27 Trust ADR Phase 5
  Session A.

### Why this is a minor bump (not patch)

Optional additive fields are technically backwards-compatible at
parse time (an old verifier sees an extra key it ignores), but they
*do* extend the public surface — a verifier built against 0.7.0 can
expect the field to exist on records produced by ≥0.7.0 manifests.
Per the project's pre-1.0 SemVer practice, additive surface changes
get a minor bump so downstream consumers' resolvers can express
"I need a producer that emits this field" via ``>=0.7.0`` constraints.

## [0.6.0] - 2026-05-02

### Changed (BREAKING)

- ``WorkflowContractSnapshot.data_retention`` renamed to
  ``input_retention``. Mirrors the existing ``output_retention``
  field name and removes the long-running ambiguity ("data" could
  mean input or output) that caused real reasoning bugs in
  consuming code. The rename is *clarification only* — same
  retention values, same enforcement behaviour. The schema-version
  string stays ``validibot.evidence.v1`` because no semantic
  property changed; only the field name is clearer.
- Consumers reading manifests produced by this version see
  ``input_retention`` instead of ``data_retention``. There are no
  external consumers yet (Phase 4 of the Validibot Trust ADR
  hasn't shipped publicly), so the rename is safe to land before
  any verifier writes to the field name.

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
