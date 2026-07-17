"""Shared artifact references and file-port contract vocabulary.

These schemas are control-plane objects. They describe files, resources, and
artifact references that Django materializes into validator envelopes; they do
not contain file bytes or Django workflow models.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

ARTIFACT_REF_SCHEMA_VERSION = "validibot.artifact_ref.v1"


class ArtifactKind(str, Enum):
    """Storage-backed artifact kind."""

    FILE = "file"
    DIRECTORY = "directory"
    ARCHIVE = "archive"
    DATASET = "dataset"
    REPORT = "report"
    LOG = "log"
    OTHER = "other"


class StepIODirection(str, Enum):
    """Whether a step port is consumed or produced."""

    INPUT = "input"
    OUTPUT = "output"


class StepIOMedium(str, Enum):
    """Whether a step port carries a JSON value or artifact reference."""

    VALUE = "value"
    ARTIFACT = "artifact"


class EnvelopeChannel(str, Enum):
    """Wire-level envelope location for a resolved file port."""

    INPUT_FILES = "input_files"
    RESOURCE_FILES = "resource_files"
    OUTPUT_ARTIFACTS = "output_artifacts"


class BindingSourceScope(str, Enum):
    """Source scopes available to file-port and value bindings."""

    SUBMISSION_PAYLOAD = "submission_payload"
    SUBMISSION_METADATA = "submission_metadata"
    SUBMISSION_FILE = "submission_file"
    UPSTREAM_STEP = "upstream_step"
    UPSTREAM_ARTIFACT = "upstream_artifact"
    SIGNAL = "signal"
    CONSTANT = "constant"
    WORKFLOW_RESOURCE = "workflow_resource"
    SYSTEM = "system"


class DefaultSourceStrategy(str, Enum):
    """Automatic or suggested source-selection behavior for a file port."""

    SUBMITTED_FILE_FIRST = "submitted_file_first"
    SUBMITTED_FILE_THEN_DEFAULT_RESOURCE = "submitted_file_then_default_resource"
    WORKFLOW_RESOURCE_DEFAULT = "workflow_resource_default"
    UPSTREAM_ARTIFACT_SUGGESTION = "upstream_artifact_suggestion"
    MANUAL = "manual"
    NONE = "none"


class FilePortContract(BaseModel):
    """Shared description of a file-like step input or output port."""

    contract_key: str = Field(
        description="Stable Validibot port key, e.g. primary_model."
    )
    label: str = Field(default="", description="Human-facing port label.")
    direction: StepIODirection = Field(description="Whether this port is input/output.")
    io_medium: StepIOMedium = Field(
        default=StepIOMedium.ARTIFACT,
        description="File ports carry artifact references.",
    )
    envelope_channel: EnvelopeChannel = Field(
        description="Envelope channel this port renders into."
    )
    role: str = Field(
        default="",
        description="Backend-facing role for input_files or output artifacts.",
    )
    resource_type: str = Field(
        default="",
        description="Backend-facing resource type for resource_files.",
    )
    artifact_kind: ArtifactKind = Field(
        default=ArtifactKind.FILE,
        description="Expected kind for artifact references.",
    )
    min_items: int = Field(default=0, ge=0, description="Minimum item count.")
    max_items: int | None = Field(
        default=1,
        ge=1,
        description="Maximum item count; None means deliberately unbounded.",
    )
    accepted_data_formats: list[str] = Field(default_factory=list)
    accepted_media_types: list[str] = Field(default_factory=list)
    allowed_source_scopes: list[BindingSourceScope] = Field(default_factory=list)
    default_source_strategy: DefaultSourceStrategy = DefaultSourceStrategy.NONE
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class ArtifactRef(BaseModel):
    """Small JSON-safe pointer to a run-scoped artifact."""

    schema_version: Literal["validibot.artifact_ref.v1"] = ARTIFACT_REF_SCHEMA_VERSION

    artifact_id: str
    run_id: str
    step_run_id: str
    producer_step_key: str

    contract_key: str
    name: str
    role: str = ""
    kind: ArtifactKind = ArtifactKind.FILE

    media_type: str = ""
    data_format: str = ""
    filename: str = ""
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    storage_version: str = Field(min_length=1, max_length=512)

    uri: str = Field(
        min_length=1,
        description="Internal storage URI; not a public download URL.",
    )
    manifest_uri: str = ""
    manifest_sha256: str = ""

    producer_validator_type: str = ""
    producer_validator_version: str = ""
    producer_backend_image_digest: str = ""

    retention_class: str = ""
    labels: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}

    @field_validator("name")
    @classmethod
    def _validate_safe_name(cls, value: str) -> str:
        """Artifact refs carry logical names, never materialization paths."""
        if (
            not value
            or value in {".", ".."}
            or "/" in value
            or "\\" in value
            or "\x00" in value
        ):
            msg = f"Artifact name must be a safe logical leaf name: {value!r}"
            raise ValueError(msg)
        return value
