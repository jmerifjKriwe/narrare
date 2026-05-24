"""Content hash computation for embedding dirty detection.

Uses SHA-256 for deterministic, collision-resistant hashing of text content.
Replaces boolean ``embeddings_dirty`` flags with content-hash comparison:
if the hash of the current content matches the stored hash, no re-embedding
is needed.

See: openspec/changes/infra-004-embedding-store/design.md (D4: content-hash)
"""

from __future__ import annotations

import hashlib


def compute_content_hash(content: str) -> str:
    """Compute SHA-256 hash of content for dirty detection.

    The hash is deterministic: identical content always produces the same
    hash. This enables idempotent batch processing (skip already-embedded
    content by hash comparison) without touching the source table schema.

    Args:
        content: Text content to hash. May be empty.

    Returns:
        Hex-encoded SHA-256 digest (64 characters).
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
