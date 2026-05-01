"""Tests for ``validibot_shared.evidence`` schema (validibot.evidence.v1).

ADR-2026-04-27 Phase 4 Session A: pin the schema's contract at the
shared-package boundary. The Validibot Django app is one consumer;
external verifiers (validibot-pro, third-party tools) are others.
These tests verify the shape stays stable across releases.

What this file covers
=====================

1. ``schema_version`` is pinned to ``validibot.evidence.v1`` and
   rejected if other values are passed (Literal type-narrows).
2. The model rejects unknown top-level keys (``extra="forbid"``).
3. Frozen Pydantic models — instances cannot be mutated after
   construction, which is the property the producer's hash
   computation depends on.
4. Optional fields default sensibly so producers can build a
   minimal Session-A manifest without populating Session-B fields.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from validibot_shared.evidence import (
    SCHEMA_VERSION,
    EvidenceManifest,
    ManifestPayloadDigests,
    ManifestRetentionInfo,
    StepValidatorRecord,
    WorkflowContractSnapshot,
)


def _minimal_manifest_kwargs():
    """Build the smallest set of kwargs that produces a valid manifest."""
    return {
        "run_id": "abc-123",
        "workflow_id": 1,
        "workflow_slug": "compliance",
        "workflow_version": "1.0",
        "org_id": 42,
        "executed_at": "2026-05-02T12:00:00+00:00",
        "status": "SUCCEEDED",
        "workflow_contract": WorkflowContractSnapshot(
            allowed_file_types=["json"],
        ),
        "retention": ManifestRetentionInfo(retention_class="STORE_30_DAYS"),
    }


# ──────────────────────────────────────────────────────────────────────
# Schema version contract
# ──────────────────────────────────────────────────────────────────────


class TestSchemaVersion:
    def test_default_schema_version_is_v1(self):
        manifest = EvidenceManifest(**_minimal_manifest_kwargs())
        assert manifest.schema_version == "validibot.evidence.v1"

    def test_schema_version_constant_matches(self):
        assert SCHEMA_VERSION == "validibot.evidence.v1"

    def test_rejects_other_schema_versions(self):
        """Literal narrowing — passing a non-v1 string fails validation."""
        with pytest.raises(ValidationError):
            EvidenceManifest(
                **_minimal_manifest_kwargs(),
                schema_version="validibot.evidence.v2",
            )


# ──────────────────────────────────────────────────────────────────────
# Strict shape (extra="forbid") and frozen instances
# ──────────────────────────────────────────────────────────────────────


class TestStrictShape:
    def test_unknown_top_level_keys_rejected(self):
        """Producers can't accidentally smuggle in undocumented data."""
        with pytest.raises(ValidationError):
            EvidenceManifest(
                **_minimal_manifest_kwargs(),
                extra_undeclared_field="oops",
            )

    def test_manifest_is_frozen(self):
        """Instances cannot be mutated post-construction.

        The hash producers compute over canonical JSON depends on
        the fact that you can't tweak a field after the model is
        built. ``frozen=True`` enforces that at the Pydantic level.
        """
        manifest = EvidenceManifest(**_minimal_manifest_kwargs())
        with pytest.raises(ValidationError):
            manifest.run_id = "tampered"


# ──────────────────────────────────────────────────────────────────────
# Optional fields and defaults (Session A vs Session B distinction)
# ──────────────────────────────────────────────────────────────────────


class TestOptionalFields:
    def test_payload_digests_defaults_to_all_none(self):
        """Session A: producers leave digests empty."""
        manifest = EvidenceManifest(**_minimal_manifest_kwargs())
        assert manifest.payload_digests.input_sha256 is None
        assert manifest.payload_digests.output_envelope_sha256 is None

    def test_session_b_can_populate_digests(self):
        """Session B's redaction path drops in real hashes."""
        manifest = EvidenceManifest(
            **_minimal_manifest_kwargs(),
            payload_digests=ManifestPayloadDigests(
                input_sha256="a" * 64,
                output_envelope_sha256="b" * 64,
            ),
        )
        assert manifest.payload_digests.input_sha256 == "a" * 64

    def test_input_schema_optional(self):
        """Workflows without structured input contract leave it None."""
        manifest = EvidenceManifest(**_minimal_manifest_kwargs())
        assert manifest.input_schema is None

    def test_steps_default_to_empty_list(self):
        """A workflow with no steps still produces a valid manifest."""
        manifest = EvidenceManifest(**_minimal_manifest_kwargs())
        assert manifest.steps == []


# ──────────────────────────────────────────────────────────────────────
# StepValidatorRecord — semantic_digest can be None for legacy validators
# ──────────────────────────────────────────────────────────────────────


class TestStepValidatorRecord:
    def test_semantic_digest_optional(self):
        """Custom validators with no digest -> None in the manifest."""
        record = StepValidatorRecord(
            step_id=1,
            step_order=0,
            validator_slug="custom-validator",
            validator_version="1.0",
        )
        assert record.validator_semantic_digest is None

    def test_records_are_frozen(self):
        """Step records cannot be mutated after construction."""
        record = StepValidatorRecord(
            step_id=1,
            step_order=0,
            validator_slug="x",
            validator_version="1.0",
        )
        with pytest.raises(ValidationError):
            record.validator_slug = "tampered"
