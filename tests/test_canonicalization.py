"""Tests for shared RFC 8785 / JCS canonicalization helpers.

The workflow-definition hash and Pro credential signing path both depend on
these helpers producing stable bytes from the same logical JSON. Keeping these
tests in ``validibot-shared`` pins the contract at the package boundary used by
community evidence producers, commercial signing code, and third-party
verifiers.
"""

from __future__ import annotations

import hashlib
import json

import pytest
from pydantic import BaseModel, ConfigDict

from validibot_shared.canonicalization import (
    canonicalize_dict,
    canonicalize_model,
    compute_callback_nonce_commitment,
    sha256_hex_for_dict,
    sha256_hex_for_model,
)

UNSAFE_INTEGER = 9007199254740993
FIXED_CALLBACK_NONCE = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8"
FIXED_CALLBACK_NONCE_COMMITMENT = (
    "c3ce1f94c76a98b82472f8611c2a56ff24ce2dc318a09c6b4972286ca5fae512"
)


class SampleSchema(BaseModel):
    """Small frozen schema matching the credential-builder model pattern."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    alpha: str
    beta: int
    gamma: str | None = None


# ── RFC 8785 ordering and scalar handling ───────────────────────────────────
# These tests protect the cross-language JSON contract that hashes/signatures
# depend on: same logical object, same canonical bytes everywhere.


def test_dict_keys_are_sorted_recursively() -> None:
    """Object keys must be sorted at every level of the JSON tree."""
    result = canonicalize_dict(
        {"outer_z": {"inner_b": 2, "inner_a": 1}, "outer_a": 0},
    )
    decoded = result.decode("utf-8")
    assert decoded.index('"outer_a"') < decoded.index('"outer_z"')
    assert decoded.index('"inner_a"') < decoded.index('"inner_b"')


def test_large_integer_is_preserved_exactly() -> None:
    """Integers larger than 2**53 must not be rounded through ``float``.

    Credential signatures may include large identifiers or nonces. If JCS casts
    them to IEEE-754 doubles, the canonical bytes silently change and a
    standards-compliant verifier computes a different digest.
    """
    result = canonicalize_dict({"n": UNSAFE_INTEGER})
    assert result == b'{"n":9007199254740993}'
    assert b"9007199254740992" not in result


def test_bool_still_serializes_as_json_literals() -> None:
    """``bool`` must remain JSON ``true``/``false`` despite subclassing ``int``."""
    assert canonicalize_dict({"yes": True, "no": False}) == (b'{"no":false,"yes":true}')


def test_unicode_strings_are_preserved() -> None:
    """Non-ASCII text must round-trip through canonical bytes unchanged."""
    result = canonicalize_dict({"name": "Prüfung", "description": "日本語テスト"})
    parsed = json.loads(result)
    assert parsed["name"] == "Prüfung"
    assert parsed["description"] == "日本語テスト"


# ── Pydantic integration and digest wrappers ────────────────────────────────
# Producers build Pydantic models, while external verifiers often reconstruct
# plain dictionaries. Both paths must canonicalize to identical bytes.


def test_model_produces_same_bytes_as_equivalent_dict() -> None:
    """Pydantic model dumping must match an equivalent JSON dictionary."""
    schema = SampleSchema(alpha="hello", beta=42, gamma=None)
    plain = {"alpha": "hello", "beta": 42, "gamma": None}
    assert canonicalize_model(schema) == canonicalize_dict(plain)


def test_sha256_for_dict_matches_manual_hash() -> None:
    """The dict digest helper must hash the canonical byte preimage exactly."""
    data = {"key": "value", "number": 7}
    expected = hashlib.sha256(canonicalize_dict(data)).hexdigest()
    assert sha256_hex_for_dict(data) == expected


def test_sha256_for_model_matches_manual_hash() -> None:
    """The model digest helper must hash the canonical byte preimage exactly."""
    schema = SampleSchema(alpha="test", beta=99, gamma="yes")
    expected = hashlib.sha256(canonicalize_model(schema)).hexdigest()
    assert sha256_hex_for_model(schema) == expected


# ── Callback nonce commitments ──────────────────────────────────────────────
# Input envelopes transport a live authentication secret, but evidence and
# output identity must hash only its public domain-separated commitment.


def test_callback_nonce_commitment_matches_fixed_cross_repo_vector() -> None:
    """The domain separator and UTF-8 preimage must remain byte-for-byte stable."""
    assert (
        compute_callback_nonce_commitment(FIXED_CALLBACK_NONCE)
        == FIXED_CALLBACK_NONCE_COMMITMENT
    )


def test_canonicalization_replaces_raw_nonce_with_commitment() -> None:
    """Canonical bytes must bind the nonce without exposing its secret value."""
    canonical = canonicalize_dict(
        {
            "context": {
                "callback_nonce": FIXED_CALLBACK_NONCE,
                "callback_nonce_commitment": FIXED_CALLBACK_NONCE_COMMITMENT,
            },
        },
    )

    assert FIXED_CALLBACK_NONCE.encode() not in canonical
    assert FIXED_CALLBACK_NONCE_COMMITMENT.encode() in canonical
    assert b'"callback_nonce"' not in canonical


def test_secret_and_public_forms_have_the_same_canonical_identity() -> None:
    """A verifier retaining only the commitment must reproduce the input digest."""
    secret_form = {
        "context": {
            "callback_nonce": FIXED_CALLBACK_NONCE,
            "callback_nonce_commitment": FIXED_CALLBACK_NONCE_COMMITMENT,
        },
    }
    public_form = {
        "context": {
            "callback_nonce_commitment": FIXED_CALLBACK_NONCE_COMMITMENT,
        },
    }

    assert canonicalize_dict(secret_form) == canonicalize_dict(public_form)


def test_canonicalization_rejects_a_false_declared_commitment() -> None:
    """A producer cannot bind the digest to a commitment unrelated to its nonce."""
    with pytest.raises(ValueError, match="does not match"):
        canonicalize_dict(
            {
                "callback_nonce": FIXED_CALLBACK_NONCE,
                "callback_nonce_commitment": "0" * 64,
            },
        )
