"""Tests for shared artifact references and file-port contracts.

These schemas form the cross-repo contract between Django, validator
backends, evidence builders, and future UI/API projections. The tests focus
on JSON shape stability and enum serialization because those are the pieces
that must remain portable across repos.
"""

import pytest
from pydantic import ValidationError

from validibot_shared.validations.artifacts import (
    ArtifactKind,
    ArtifactRef,
    BindingSourceScope,
    DefaultSourceStrategy,
    EnvelopeChannel,
    FilePortContract,
    StepIODirection,
    StepIOMedium,
)


def test_artifact_ref_serializes_as_json_safe_control_plane_object():
    """ArtifactRef should carry lineage metadata without embedding bytes."""
    ref = ArtifactRef(
        artifact_id="artifact-1",
        run_id="run-1",
        step_run_id="step-run-1",
        producer_step_key="build_model",
        contract_key="generated_model",
        name="model.epjson",
        role="primary-model",
        kind=ArtifactKind.FILE,
        media_type="application/vnd.energyplus.epjson",
        data_format="energyplus_epjson",
        filename="model.epjson",
        size_bytes=1234,
        sha256="a" * 64,
        uri="gs://bucket/runs/run-1/model.epjson",
        producer_validator_type="BUILDINGSYNC_TO_ENERGYPLUS",
        producer_validator_version="1",
        producer_backend_image_digest="repo/image@sha256:" + "b" * 64,
        retention_class="standard",
    )

    dumped = ref.model_dump(mode="json")

    assert dumped["schema_version"] == "validibot.artifact_ref.v1"
    assert dumped["kind"] == "file"
    assert dumped["producer_step_key"] == "build_model"
    assert dumped["uri"].startswith("gs://")


def test_file_port_contract_serializes_shared_vocabulary():
    """File-port contracts should expose stable enum values to every repo."""
    contract = FilePortContract(
        contract_key="primary_model",
        label="Primary Model",
        direction=StepIODirection.INPUT,
        io_medium=StepIOMedium.ARTIFACT,
        envelope_channel=EnvelopeChannel.INPUT_FILES,
        role="primary-model",
        artifact_kind=ArtifactKind.FILE,
        min_items=1,
        max_items=1,
        accepted_data_formats=["energyplus_idf", "energyplus_epjson"],
        accepted_media_types=[
            "application/vnd.energyplus.idf",
            "application/vnd.energyplus.epjson",
        ],
        allowed_source_scopes=[
            BindingSourceScope.SUBMISSION_FILE,
            BindingSourceScope.UPSTREAM_ARTIFACT,
            BindingSourceScope.SIGNAL,
        ],
        default_source_strategy=DefaultSourceStrategy.SUBMITTED_FILE_FIRST,
    )

    dumped = contract.model_dump(mode="json")

    assert dumped["contract_key"] == "primary_model"
    assert dumped["io_medium"] == "artifact"
    assert dumped["envelope_channel"] == "input_files"
    assert dumped["allowed_source_scopes"] == [
        "submission_file",
        "upstream_artifact",
        "signal",
    ]
    assert dumped["default_source_strategy"] == "submitted_file_first"


def test_file_port_contract_rejects_extra_fields():
    """The contract should stay explicit rather than absorbing typos."""
    with pytest.raises(ValidationError):
        FilePortContract(
            contract_key="primary_model",
            direction=StepIODirection.INPUT,
            envelope_channel=EnvelopeChannel.INPUT_FILES,
            unknown=True,
        )
