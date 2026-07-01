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
    ContractConstant,
    ContractSignalMapping,
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

    # ── Manifest source field ───────────────────────────────────
    #
    # ``source`` documents which auth channel produced the run.  It's
    # additive and optional — older producers set None, newer
    # producers populate it from the authenticated route (NOT from a
    # client header).  The schema-version contract still reads ``v1``
    # because the change is purely additive.
    def test_source_defaults_to_none(self):
        """Older producers and producers that don't track source leave it None."""
        manifest = EvidenceManifest(**_minimal_manifest_kwargs())
        assert manifest.source is None

    def test_source_can_be_populated(self):
        """Newer producers populate source from the authenticated route."""
        manifest = EvidenceManifest(
            **_minimal_manifest_kwargs(),
            source="X402_AGENT",
        )
        assert manifest.source == "X402_AGENT"

    def test_source_addition_preserves_v1_schema(self):
        """Manifests carrying ``source`` still report schema_version v1.

        Adding an optional field is explicitly an additive change per
        the schema-versioning policy in ``manifest.py``. Bumping to v2
        would only be required for breaking changes.
        """
        manifest = EvidenceManifest(
            **_minimal_manifest_kwargs(),
            source="MCP",
        )
        assert manifest.schema_version == "validibot.evidence.v1"


# ──────────────────────────────────────────────────────────────────────
# WorkflowContractSnapshot — constants, signal-mapping defs, definition hash
# ──────────────────────────────────────────────────────────────────────
#
# ADR-2026-06-18. These three fields are additive and optional: a producer
# predating them (or a workflow with none) leaves them empty, and the schema
# stays ``validibot.evidence.v1``. Recording constants + signal-mapping
# *definitions* + the definition hash is the transparency half of the constants
# feature — it lets EVERY run (not just Pro-signed ones) carry "checked against
# these constants". Resolved ``s.*`` values are deliberately NOT here (they are
# submission-derived and retention-gated); only the definition is.


class TestWorkflowContractPrimitives:
    def test_new_fields_default_to_empty(self):
        """A producer predating this change (or a bare workflow) leaves them empty.

        Back-compat is the whole reason these are additive-optional: an older
        manifest that never set them must still validate.
        """
        snap = WorkflowContractSnapshot(allowed_file_types=["json"])
        assert snap.constants == []
        assert snap.signal_mappings == []
        assert snap.workflow_definition_hash == ""

    def test_constant_value_is_preserved_verbatim(self):
        """A NUMBER constant's decimal string is stored exactly (no float coercion).

        The attested precision (``"0.40"``) must survive into the snapshot, or the
        credential's "checked against c.energy_price = 0.40" claim would drift
        from the value actually recorded.
        """
        snap = WorkflowContractSnapshot(
            constants=[
                ContractConstant(
                    name="energy_price",
                    data_type="NUMBER",
                    value="0.40",
                ),
                ContractConstant(
                    name="allowed_currencies",
                    data_type="LIST",
                    value=["EUR", "GBP"],
                ),
            ],
        )
        assert snap.constants[0].value == "0.40"
        assert snap.constants[1].value == ["EUR", "GBP"]

    def test_signal_mapping_records_definition_not_value(self):
        """The snapshot carries a signal's DEFINITION, never a resolved value.

        Publishing ``source_path``/``on_missing``/``default`` is safe; a resolved
        ``s.*`` value is submission-derived and must not appear in the
        always-publishable contract.
        """
        snap = WorkflowContractSnapshot(
            signal_mappings=[
                ContractSignalMapping(
                    name="reported_total",
                    source_path="$.total",
                    on_missing="error",
                ),
            ],
        )
        mapping = snap.signal_mappings[0]
        assert mapping.name == "reported_total"
        assert mapping.source_path == "$.total"
        # There is no place to smuggle a resolved value in — the model has no
        # such field.
        assert not hasattr(mapping, "resolved_value")

    def test_primitives_survive_json_round_trip(self):
        """The fields serialize and re-validate identically (canonical evidence).

        The manifest is hashed and signed as JSON, so the new fields must
        round-trip through ``model_dump``/``model_validate`` unchanged.
        """
        snap = WorkflowContractSnapshot(
            constants=[ContractConstant(name="p", data_type="NUMBER", value="0.40")],
            signal_mappings=[ContractSignalMapping(name="t", source_path="$.t")],
            workflow_definition_hash="sha256:deadbeef",
        )
        restored = WorkflowContractSnapshot.model_validate(
            snap.model_dump(mode="json"),
        )
        assert restored == snap

    def test_additive_fields_preserve_v1_schema(self):
        """A manifest carrying constants still reports schema_version v1.

        Additive optional fields preserve v1 per the module's own policy;
        bumping SCHEMA_VERSION here would be wrong.
        """
        manifest = EvidenceManifest(
            **{
                **_minimal_manifest_kwargs(),
                "workflow_contract": WorkflowContractSnapshot(
                    allowed_file_types=["json"],
                    constants=[
                        ContractConstant(name="p", data_type="NUMBER", value="0.40"),
                    ],
                    workflow_definition_hash="sha256:abc",
                ),
            },
        )
        assert manifest.schema_version == "validibot.evidence.v1"
        assert manifest.workflow_contract.constants[0].name == "p"


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
