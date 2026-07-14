"""Pydantic schema for validibot evidence manifests (``validibot.evidence.v1``).

ADR-2026-04-27 (Validibot Trust ADR), Phase 4: every completed
validation run produces a manifest documenting "these are the rules
and inputs run X was operating under." The manifest is the data
structure that makes evidence bundles, signed credentials, and
external verification possible.

Why this lives in ``validibot-shared``
======================================

The manifest is the contract between *manifest producers* (the
Validibot Django app) and *verifiers* (the validibot-pro signing /
verification flow, or any external party that receives an exported
bundle). Pinning the schema in the shared package:

1. Lets external verifiers depend on a single PyPI package without
   pulling in the Django stack.
2. Keeps producer and verifier locked to the same version of the
   shape — additive changes preserve v1 by policy; breaking changes
   require a v2 module beside this one.

Schema versioning policy
========================

The string ``validibot.evidence.v1`` in :data:`SCHEMA_VERSION` is the
*compatibility contract*. Additive changes (new optional fields,
loosened validators) preserve v1. Removing or renaming fields, or
tightening a validator in a way that rejects previously-valid input,
requires a v2 module placed alongside this one (``manifest_v2.py``).

What's in the schema (Phase 4 phasing)
======================================

Session A (this module): identity, workflow contract snapshot,
validator metadata per step, input contract, retention class, and
schema slots for fields Sessions B + C will populate.

Session B (deferred): the ``payload_digests`` slot gets populated
with input + output hashes; ``retention.redactions_applied`` lists
fields stripped under retention policy. The schema shape itself
does not change, only the values landing in optional fields.

Session C (deferred): credentials sign the canonical-JSON bytes of
this manifest externally. The signature does NOT live inside the
manifest — verifiers receive the manifest + a separate signature
file in the export bundle.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# The string consumers parse to know what manifest shape to expect.
# Bump only on breaking changes; additive changes stay v1.
SCHEMA_VERSION = "validibot.evidence.v1"


class StepValidatorRecord(BaseModel):
    """Per-step validator identity at run time.

    Pinned values: a step's validator is referenced by foreign key
    on the application side, but the *meaning* of that reference
    depends on the validator's ``semantic_digest`` at run time. We
    snapshot the digest into the manifest so future verifiers can
    prove "the validator behind this step had digest D when this run
    executed."
    """

    model_config = ConfigDict(frozen=True)

    step_id: int = Field(
        description="Producer-side WorkflowStep primary key at run time."
    )
    step_order: int = Field(description="Execution position (lower = earlier).")
    validator_slug: str = Field(description="Validator's stable slug.")
    validator_version: str = Field(description="Validator's version string.")
    # Optional because custom org validators have empty digests by
    # design (no ValidatorConfig to hash). Producers' auditors flag
    # this as a coverage gap.
    validator_semantic_digest: str | None = Field(
        default=None,
        description=(
            "SHA-256 hex of the validator's semantic config. None for "
            "custom validators that aren't synced from a "
            "ValidatorConfig — the manifest documents the absence so "
            "verifiers know to expect a legacy-versioning gap there."
        ),
    )
    # Trust ADR Phase 5 Session A — the *runtime* identity of the
    # validator backend container that actually executed this step.
    # ``validator_semantic_digest`` describes the validator's
    # *configuration* (slug, version, config bytes); this field
    # describes the *image bytes* that ran. The two are
    # complementary: one proves "the validator was configured this
    # way", the other proves "this exact container ran". Optional
    # because (a) simple-validator steps run inline without a
    # backend, and (b) historical step runs predate the field.
    validator_backend_image_digest: str | None = Field(
        default=None,
        description=(
            "Resolved sha256 digest of the validator backend image "
            "that executed this step (e.g. 'sha256:abc...' or "
            "'registry/...@sha256:abc...'). None for simple-validator "
            "steps that run inline without a container, or for runs "
            "captured before digest capture shipped."
        ),
    )


class ContractConstant(BaseModel):
    """A workflow Constant (the ``c.*`` namespace) recorded in the contract.

    A Constant (ADR-2026-06-18) is a workflow-defined *fixed literal*, so its
    name **and value** are always safe to publish in the contract snapshot —
    unlike a resolved ``s.*`` signal value, which is submission-derived and must
    stay in the retention-gated run record. ``value`` is the stored form: a
    canonical decimal *string* for NUMBER (so ``"0.40"`` keeps its precision), a
    ``str`` for STRING, a ``bool`` for BOOLEAN, and a ``list``/``dict`` for
    LIST/OBJECT.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    data_type: str = ""
    value: Any = None


class ContractSignalMapping(BaseModel):
    """A workflow signal-mapping *definition* recorded in the contract.

    The workflow-defined config for an ``s.<name>`` signal — NOT its resolved
    runtime value. Publishing the definition (how the signal is sourced) is safe
    and lets a verifier see the contract; the *resolved* value is
    submission-derived and belongs only in the retention-gated run record
    (ADR-2026-06-18).
    """

    model_config = ConfigDict(frozen=True)

    name: str
    source_path: str = ""
    on_missing: str = ""
    default_value: Any = None
    data_type: str = ""


class WorkflowContractSnapshot(BaseModel):
    """Frozen snapshot of the workflow's launch-contract fields.

    These are the fields that determine *what the workflow does*
    when it runs (file types accepted, retention policy, agent
    publication state). Pinning them in the manifest lets a future
    verifier answer "what rules was this run operating under?"
    without consulting the live producer database (which may have
    moved on to a newer workflow version).
    """

    model_config = ConfigDict(frozen=True)

    allowed_file_types: list[str] = Field(default_factory=list)
    # ``input_retention`` was named ``data_retention`` in shared
    # 0.5.x. The rename (shared 0.6.0+) makes the parallel with
    # ``output_retention`` obvious — both fields carry the workflow
    # author's retention choices, one for the user's input bytes and
    # one for the validator's output bytes. The schema-version
    # string stays ``validibot.evidence.v1`` because the field's
    # semantics are unchanged; only the name is clearer.
    input_retention: str = ""
    output_retention: str = ""
    agent_billing_mode: str = ""
    agent_price_cents: int | None = None
    agent_max_launches_per_hour: int | None = None
    agent_public_discovery: bool = False
    agent_access_enabled: bool = False

    # ── Workflow contract primitives (ADR-2026-06-18) ────────────────────────
    # Additive, optional fields — the schema stays ``validibot.evidence.v1``
    # (additive changes preserve v1 by the policy documented at the top of this
    # module; a bump would be wrong here). Producers that predate this change
    # simply leave them empty, and older consumers ignore unknown-to-them fields.
    constants: list[ContractConstant] = Field(
        default_factory=list,
        description=(
            "Workflow Constants (c.* namespace) with their fixed values — the "
            "named thresholds this run was judged against. Empty for workflows "
            "with no constants or for producers predating this field."
        ),
    )
    signal_mappings: list[ContractSignalMapping] = Field(
        default_factory=list,
        description=(
            "Workflow signal-mapping DEFINITIONS (name + source_path + "
            "on_missing + default + type) — never resolved s.* runtime values, "
            "which are submission-derived and retention-gated."
        ),
    )
    workflow_definition_hash: str = Field(
        default="",
        description=(
            "The workflow-definition digest (e.g. 'sha256:...') covering the "
            "semantic contract — constants, signal-mapping definitions, and "
            "per-step validator + effective-ruleset + assertions. Lets a "
            "verifier confirm the run's contract matches a claimed version. "
            "Empty for producers predating this field."
        ),
    )


class ManifestRetentionInfo(BaseModel):
    """Retention class + applied-redaction summary.

    Session A populates ``retention_class`` from the workflow's
    ``data_retention`` so consumers know what the run agreed to.
    Session B will populate ``redactions_applied`` with the list of
    fields the retention policy stripped before serialisation. For
    Session A the field is empty.
    """

    model_config = ConfigDict(frozen=True)

    retention_class: str = Field(
        description=(
            "Workflow data-retention setting at run time "
            "(e.g. 'DO_NOT_STORE', 'STORE_30_DAYS')."
        ),
    )
    redactions_applied: list[str] = Field(
        default_factory=list,
        description=(
            "Names of manifest fields that were redacted under this "
            "retention class. Session A leaves this empty; Session B "
            "fills it in when the redaction policy lands."
        ),
    )


class ManifestPayloadDigests(BaseModel):
    """Hashes of the run's payload data.

    Session A leaves these as None — the field exists in the schema
    so consumers can write code that handles both the Session A
    ("not yet computed") and Session B ("populated from the run's
    submission and output envelope") cases without a v2 bump.
    """

    model_config = ConfigDict(frozen=True)

    input_sha256: str | None = Field(
        default=None,
        description=(
            "SHA-256 hex of the submission's primary file bytes at run "
            "time. Always present in Session B — even when "
            "DO_NOT_STORE purges the bytes themselves, the hash is "
            "the immutable proof the run consumed input matching it."
        ),
    )
    output_envelope_sha256: str | None = Field(
        default=None,
        description=(
            "SHA-256 hex of the canonical output envelope JSON. None "
            "for runs whose retention policy excludes outputs."
        ),
    )


class ManifestProducedArtifact(BaseModel):
    """Public, durable projection of an artifact produced by a run step.

    This deliberately omits storage locations (``storage_uri`` and
    ``manifest_uri`` in the Django model / ArtifactRef). Evidence consumers need
    stable identity, hashes, producer coordinates, and file descriptors; private
    bucket paths stay inside the producer.
    """

    model_config = ConfigDict(frozen=True)

    artifact_id: str = Field(description="Producer-side Artifact primary key.")
    run_id: str = Field(description="Run UUID that owns the artifact.")
    step_run_id: str | None = Field(
        default=None,
        description="Step-run UUID/primary key that produced the artifact.",
    )
    producer_step_id: int | None = Field(
        default=None,
        description="Producer-side WorkflowStep primary key, if step-scoped.",
    )
    producer_step_key: str = Field(
        default="",
        description="Stable workflow-local key of the producer step.",
    )
    producer_step_name: str = Field(
        default="",
        description="Human-facing producer step name at run time.",
    )
    contract_key: str = Field(description="Stable artifact output contract key.")
    item_key: str = Field(
        default="",
        description="Stable collection item key, empty for scalar artifact ports.",
    )
    filename: str = Field(default="", description="Original/public filename.")
    label: str = Field(default="", description="Human-facing artifact label.")
    role: str = Field(default="", description="Validator-facing artifact role.")
    kind: str = Field(default="", description="Artifact kind.")
    media_type: str = Field(default="", description="Media/MIME type.")
    data_format: str = Field(default="", description="Domain data format.")
    size_bytes: int | None = Field(default=None, description="Artifact byte size.")
    sha256: str = Field(default="", description="SHA-256 of artifact bytes.")
    manifest_sha256: str = Field(
        default="",
        description="SHA-256 of the validator output manifest, if present.",
    )
    producer_validator_type: str = Field(
        default="",
        description="Validator type that produced the artifact.",
    )
    producer_validator_version: str = Field(
        default="",
        description="Validator version that produced the artifact.",
    )
    producer_backend_image_digest: str = Field(
        default="",
        description="Backend image digest that produced the artifact.",
    )
    retention_class: str = Field(
        default="",
        description="Output-retention class attached to the artifact.",
    )


class ManifestArtifactInputBinding(BaseModel):
    """Runtime file-port binding consumed by a step.

    Each row records what artifact-like source satisfied a declared input port:
    submitted file, workflow resource, or upstream artifact. URI-bearing runtime
    traces are projected into filename/hash/ID fields only.
    """

    model_config = ConfigDict(frozen=True)

    target_step_id: int = Field(description="WorkflowStep primary key consuming it.")
    target_step_key: str = Field(description="Stable key of the consumer step.")
    target_step_name: str = Field(default="", description="Consumer step name.")
    target_step_run_id: str = Field(default="", description="Consumer step-run id.")
    target_port_key: str = Field(description="Declared artifact input port key.")
    target_port_role: str = Field(default="", description="Backend-facing port role.")
    target_envelope_channel: str = Field(
        default="",
        description="Envelope channel used by the port.",
    )
    source_scope: str = Field(
        description="Runtime source scope used to resolve the binding.",
    )
    source_data_path: str = Field(
        default="",
        description="Runtime source path used to resolve the binding.",
    )
    resolved: bool = Field(description="Whether runtime resolution succeeded.")
    used_default: bool = Field(
        default=False,
        description="Whether a default satisfied the input.",
    )
    source_artifact_id: str = Field(
        default="",
        description="Upstream Artifact id, for upstream_artifact bindings.",
    )
    source_submission_file_id: str = Field(
        default="",
        description="SubmissionInputFile id, for submitted artifact-port files.",
    )
    source_submission_id: str = Field(
        default="",
        description="Submission id for the primary submitted file, when used.",
    )
    source_resource_id: str = Field(
        default="",
        description="Workflow/resource id, for workflow_resource bindings.",
    )
    source_filename: str = Field(default="", description="Resolved source filename.")
    source_media_type: str = Field(
        default="",
        description="Resolved source media type.",
    )
    source_data_format: str = Field(
        default="",
        description="Resolved source data format or resource type.",
    )
    source_size_bytes: int | None = Field(default=None)
    source_sha256: str = Field(default="", description="Resolved source SHA-256.")
    producer_step_key: str = Field(
        default="",
        description="Producer step key for upstream_artifact bindings.",
    )
    producer_contract_key: str = Field(
        default="",
        description="Producer artifact contract key for upstream_artifact bindings.",
    )
    error_message: str = Field(
        default="",
        description="Resolution error when resolved=false.",
    )


class ManifestArtifactLineageEdge(BaseModel):
    """Explicit upstream-artifact edge from producer output to consumer input."""

    model_config = ConfigDict(frozen=True)

    source_artifact_id: str = Field(description="Produced Artifact id.")
    source_step_key: str = Field(default="", description="Producer step key.")
    source_contract_key: str = Field(
        default="",
        description="Producer artifact contract key.",
    )
    source_sha256: str = Field(default="", description="Produced artifact SHA-256.")
    target_step_key: str = Field(description="Consumer step key.")
    target_port_key: str = Field(description="Consumer artifact input port key.")
    target_step_run_id: str = Field(default="", description="Consumer step-run id.")


class EvidenceManifest(BaseModel):
    """Top-level evidence manifest for a single validation run.

    The canonical JSON form of this model — produced by serialising
    the dict from ``model_dump(mode="json")`` via ``json.dumps`` with
    ``sort_keys=True`` and ``separators=(",",":")`` — is what gets
    hashed and persisted by the producer.

    Producers store ``SHA-256(canonical_json_bytes)`` alongside the
    file. Tampering with the manifest after persistence is detectable
    via re-fetch + re-hash.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["validibot.evidence.v1"] = Field(
        default=SCHEMA_VERSION,
        description="Pinned schema-version string. Verifiers reject other values.",
    )
    run_id: str = Field(description="Producer-side run UUID (hex string).")
    workflow_id: int = Field(description="Workflow primary key at run time.")
    workflow_slug: str = Field(description="Workflow slug at run time.")
    workflow_version: str = Field(description="Workflow version at run time.")
    org_id: int = Field(description="Organization primary key that owned the run.")
    executed_at: str = Field(
        description=(
            "ISO 8601 UTC timestamp of run completion. String rather "
            "than datetime so canonical-JSON bytes are stable across "
            "Python versions and timezone-aware/naïve serialisation "
            "differences."
        ),
    )
    status: str = Field(
        description=("Run status at completion (SUCCEEDED / FAILED / CANCELED)."),
    )
    workflow_contract: WorkflowContractSnapshot
    steps: list[StepValidatorRecord] = Field(
        default_factory=list,
        description="Per-step validator records, ordered by step.order.",
    )
    input_schema: dict | None = Field(
        default=None,
        description=(
            "Workflow's structured input contract (canonical JSON Schema) "
            "at run time. None when the workflow has no structured input "
            "contract. The schema itself is the contract; the input "
            "hash in payload_digests is the proof of conformance."
        ),
    )
    retention: ManifestRetentionInfo
    payload_digests: ManifestPayloadDigests = Field(
        default_factory=ManifestPayloadDigests,
        description="Session A: empty. Session B: input + output hashes.",
    )
    produced_artifacts: list[ManifestProducedArtifact] = Field(
        default_factory=list,
        description=(
            "Artifacts produced by this run, projected without private storage "
            "URIs. Empty for runs with no artifacts or producers predating "
            "artifact lineage evidence."
        ),
    )
    artifact_input_bindings: list[ManifestArtifactInputBinding] = Field(
        default_factory=list,
        description=(
            "Runtime artifact file-port inputs consumed by steps: submitted "
            "files, workflow resources, and upstream artifacts."
        ),
    )
    artifact_lineage_edges: list[ManifestArtifactLineageEdge] = Field(
        default_factory=list,
        description=(
            "Producer artifact -> consumer port edges for upstream_artifact "
            "bindings. Submitted files and workflow resources are recorded in "
            "artifact_input_bindings but do not create producer-step edges."
        ),
    )
    # The auth channel that initiated the run.  Pinning it in the
    # manifest lets verifiers answer "what surface produced this
    # run?" without consulting the producer database (the run row
    # may be purged under DO_NOT_STORE retention).  Optional because
    # (a) older producers persist runs without populating
    # ``source``, and (b) the field is additive — a missing value
    # preserves the v1 schema-version contract.  Producers MUST
    # derive this from the authenticated route, NEVER from a
    # caller-controlled header.
    source: str | None = Field(
        default=None,
        description=(
            "Run source identifier — one of LAUNCH_PAGE, API, MCP, "
            "X402_AGENT, CLI, SCHEDULE.  Derived from the "
            "authenticated route on the producer side and propagated "
            "into the manifest verbatim.  None when the run was "
            "captured before P2 #2 shipped or by a producer that does "
            "not yet emit the field."
        ),
    )


__all__ = [
    "SCHEMA_VERSION",
    "EvidenceManifest",
    "ManifestArtifactInputBinding",
    "ManifestArtifactLineageEdge",
    "ManifestPayloadDigests",
    "ManifestProducedArtifact",
    "ManifestRetentionInfo",
    "StepValidatorRecord",
    "WorkflowContractSnapshot",
]
