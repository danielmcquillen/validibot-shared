"""RFC 8785 / JCS canonical JSON helpers shared across Validibot packages.

The evidence manifest producer, workflow-definition digest, and Pro credential
signing path all need the same deterministic byte representation. Keeping the
canonicalizer in ``validibot-shared`` gives community evidence producers,
commercial signing code, and third-party verifiers one portable contract instead
of a Pro-owned implementation detail.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

from pydantic import BaseModel

from validibot_shared._vendor.jcs import canonicalize as _jcs_canonicalize

CALLBACK_NONCE_DOMAIN_SEPARATOR = b"validibot-callback-nonce\0"
CALLBACK_NONCE_FIELD = "callback_nonce"
CALLBACK_NONCE_COMMITMENT_FIELD = "callback_nonce_commitment"


def compute_callback_nonce_commitment(nonce: str) -> str:
    """Return the public domain-separated commitment for a callback nonce.

    The raw nonce authenticates the eventual callback and must not become part
    of evidence or output-envelope hashes. Its commitment safely binds the
    canonical input envelope to that secret without revealing the secret.

    Args:
        nonce: Raw callback nonce transported only in the input envelope and
            callback payload.

    Returns:
        Lowercase SHA-256 hexadecimal commitment.

    Raises:
        ValueError: If ``nonce`` is empty.
    """
    if not nonce:
        msg = "Callback nonce cannot be empty"
        raise ValueError(msg)
    preimage = CALLBACK_NONCE_DOMAIN_SEPARATOR + nonce.encode("utf-8")
    return hashlib.sha256(preimage).hexdigest()


def _commit_callback_nonces(value: Any) -> Any:
    """Recursively replace raw callback nonces with public commitments."""
    if isinstance(value, list):
        return [_commit_callback_nonces(item) for item in value]
    if not isinstance(value, dict):
        return value

    raw_nonce = value.get(CALLBACK_NONCE_FIELD)
    transformed = {
        key: _commit_callback_nonces(item)
        for key, item in value.items()
        if key != CALLBACK_NONCE_FIELD
    }
    if raw_nonce is None:
        return transformed
    if not isinstance(raw_nonce, str):
        msg = "Callback nonce must be a string before canonicalization"
        raise TypeError(msg)

    expected_commitment = compute_callback_nonce_commitment(raw_nonce)
    declared_commitment = value.get(CALLBACK_NONCE_COMMITMENT_FIELD)
    if declared_commitment is not None and (
        not isinstance(declared_commitment, str)
        or not hmac.compare_digest(declared_commitment, expected_commitment)
    ):
        msg = "Callback nonce commitment does not match the raw nonce"
        raise ValueError(msg)
    transformed[CALLBACK_NONCE_COMMITMENT_FIELD] = expected_commitment
    return transformed


def canonicalize_dict(data: dict[str, Any]) -> bytes:
    """Canonicalize a plain dictionary via RFC 8785 / JCS.

    Any ``callback_nonce`` key is removed recursively and replaced by its
    domain-separated ``callback_nonce_commitment``. A supplied commitment must
    match, which lets a verifier canonicalize either the live-secret form or a
    redacted commitment-only form to the same bytes.

    Args:
        data: A JSON-serializable dictionary.

    Returns:
        Canonical UTF-8 encoded JSON bytes per RFC 8785.

    Raises:
        TypeError: If a callback nonce is not a string.
        ValueError: If a callback nonce is empty or its declared commitment
            does not match.
    """
    return _jcs_canonicalize(_commit_callback_nonces(data))


def sha256_hex_for_dict(data: dict[str, Any]) -> str:
    """Compute the SHA-256 hex digest of a plain dict's canonical bytes."""
    return hashlib.sha256(canonicalize_dict(data)).hexdigest()


def canonicalize_model(schema_obj: BaseModel) -> bytes:
    """Canonicalize a Pydantic model via ``model_dump(mode="json")`` + JCS.

    ``mode="json"`` converts UUIDs, datetimes, and other Pydantic-native values
    to JSON-compatible scalars before canonicalization. ``by_alias=True`` keeps
    wire aliases such as ``@context`` intact.
    """
    return canonicalize_dict(schema_obj.model_dump(mode="json", by_alias=True))


def sha256_hex_for_model(schema_obj: BaseModel) -> str:
    """Compute the SHA-256 hex digest of a Pydantic model's canonical bytes."""
    return hashlib.sha256(canonicalize_model(schema_obj)).hexdigest()


__all__ = [
    "CALLBACK_NONCE_COMMITMENT_FIELD",
    "CALLBACK_NONCE_DOMAIN_SEPARATOR",
    "CALLBACK_NONCE_FIELD",
    "canonicalize_dict",
    "canonicalize_model",
    "compute_callback_nonce_commitment",
    "sha256_hex_for_dict",
    "sha256_hex_for_model",
]
