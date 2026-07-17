"""Tests for the strict callback nonce portion of the attempt contract.

Asynchronous validator callbacks need both delivery idempotency and proof that
the sender received the exact input envelope for one execution attempt. The
callback ID supplies the first property; the per-attempt nonce supplies the
second. These tests keep raw secrets out of model representations, require a
matching public commitment, preserve synchronous no-callback operation, and
reject the older attempt-v1 contract instead of silently accepting weaker
authentication.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from validibot_shared.canonicalization import compute_callback_nonce_commitment
from validibot_shared.validations.envelopes import (
    ATTEMPT_CONTRACT_VERSION,
    ExecutionContext,
    ValidationCallback,
    ValidationOutputEnvelope,
    ValidationStatus,
)

CALLBACK_NONCE = "A" * 43
CALLBACK_COMMITMENT = compute_callback_nonce_commitment(CALLBACK_NONCE)


def _context_kwargs() -> dict[str, object]:
    """Return the non-secret fields required by one asynchronous attempt."""
    return {
        "execution_attempt_id": "attempt-1",
        "step_run_id": "step-run-1",
        "attempt_contract_version": ATTEMPT_CONTRACT_VERSION,
        "expected_output_uri": "gs://bucket/attempt-1/output.json",
        "callback_url": "https://example.com/callback",
        "execution_bundle_uri": "gs://bucket/attempt-1/",
    }


def test_async_context_requires_callback_id_and_nonce_pair() -> None:
    """An enabled callback must not validate with only public routing metadata."""
    with pytest.raises(ValidationError, match="callback_id is required"):
        ExecutionContext(**_context_kwargs())

    with pytest.raises(ValidationError, match="required when callbacks are enabled"):
        ExecutionContext(
            **_context_kwargs(),
            callback_id="execution-attempt-attempt-1",
        )


def test_context_requires_nonce_and_commitment_together() -> None:
    """Neither half of the binding is meaningful without its matching partner."""
    with pytest.raises(ValidationError, match="must be provided together"):
        ExecutionContext(
            **_context_kwargs(),
            callback_id="execution-attempt-attempt-1",
            callback_nonce=CALLBACK_NONCE,
        )


def test_context_rejects_commitment_unrelated_to_nonce() -> None:
    """A mismatched commitment must fail before an envelope can be dispatched."""
    with pytest.raises(ValidationError, match="does not match"):
        ExecutionContext(
            **_context_kwargs(),
            callback_id="execution-attempt-attempt-1",
            callback_nonce=CALLBACK_NONCE,
            callback_nonce_commitment="0" * 64,
        )


def test_async_context_accepts_matching_pair_without_displaying_secret() -> None:
    """A valid pair binds dispatch while keeping ordinary diagnostics redacted."""
    context = ExecutionContext(
        **_context_kwargs(),
        callback_id="execution-attempt-attempt-1",
        callback_nonce=CALLBACK_NONCE,
        callback_nonce_commitment=CALLBACK_COMMITMENT,
    )

    assert context.callback_nonce_commitment == CALLBACK_COMMITMENT
    assert CALLBACK_NONCE not in repr(context)


def test_sync_context_does_not_require_an_unused_callback_secret() -> None:
    """Local synchronous execution remains valid when callback delivery is skipped."""
    context = ExecutionContext(
        **_context_kwargs(),
        callback_id="execution-attempt-attempt-1",
        skip_callback=True,
    )

    assert context.callback_nonce is None
    assert context.callback_nonce_commitment is None


def test_attempt_v1_is_rejected_after_the_strict_contract_cutover() -> None:
    """Mixed runtime versions must fail explicitly instead of losing nonce fields."""
    with pytest.raises(ValidationError, match="validibot.attempt.v2"):
        ExecutionContext(
            **(
                _context_kwargs() | {"attempt_contract_version": "validibot.attempt.v1"}
            ),
            callback_id="execution-attempt-attempt-1",
            callback_nonce=CALLBACK_NONCE,
            callback_nonce_commitment=CALLBACK_COMMITMENT,
        )


def test_callback_payload_transports_secret_without_displaying_it() -> None:
    """The backend must send the nonce, while ordinary repr output stays redacted."""
    callback = ValidationCallback(
        run_id="run-1",
        callback_id="execution-attempt-attempt-1",
        callback_nonce=CALLBACK_NONCE,
        status=ValidationStatus.SUCCESS,
        result_uri="gs://bucket/attempt-1/output.json",
    )

    assert callback.model_dump()["callback_nonce"] == CALLBACK_NONCE
    assert CALLBACK_NONCE not in repr(callback)


def test_callback_payload_rejects_missing_or_short_nonce() -> None:
    """A callback without a full-strength attempt secret is not authenticated."""
    base = {
        "run_id": "run-1",
        "callback_id": "execution-attempt-attempt-1",
        "status": ValidationStatus.SUCCESS,
        "result_uri": "gs://bucket/attempt-1/output.json",
    }

    with pytest.raises(ValidationError, match="callback_nonce"):
        ValidationCallback(**base)
    with pytest.raises(ValidationError, match="at least 43 characters"):
        ValidationCallback(**base, callback_nonce="too-short")


def test_output_envelope_has_no_callback_secret_field() -> None:
    """Public results must never expose the live secret used for callback auth."""
    assert "callback_nonce" not in ValidationOutputEnvelope.model_fields
