"""RFC 8785 / JCS canonical JSON helpers shared across Validibot packages.

The evidence manifest producer, workflow-definition digest, and Pro credential
signing path all need the same deterministic byte representation. Keeping the
canonicalizer in ``validibot-shared`` gives community evidence producers,
commercial signing code, and third-party verifiers one portable contract instead
of a Pro-owned implementation detail.
"""

from __future__ import annotations

import hashlib
from typing import Any

from pydantic import BaseModel

from validibot_shared._vendor.jcs import canonicalize as _jcs_canonicalize


def canonicalize_dict(data: dict[str, Any]) -> bytes:
    """Canonicalize a plain dictionary via RFC 8785 / JCS.

    Args:
        data: A JSON-serializable dictionary.

    Returns:
        Canonical UTF-8 encoded JSON bytes per RFC 8785.
    """
    return _jcs_canonicalize(data)


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
    "canonicalize_dict",
    "canonicalize_model",
    "sha256_hex_for_dict",
    "sha256_hex_for_model",
]
