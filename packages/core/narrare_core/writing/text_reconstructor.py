"""Reine Funktion zur Textrekonstruktion aus Original + Changes.

Pure function — kein I/O, keine Side Effects. Deterministic.
Zustandslos: Braucht nur original text + accepted changes.

See ADR-023 and ADR-023-Restimplementierung Phase 1.
"""

from __future__ import annotations

__all__: list[str] = [
    "reconstruct_text",
]


def reconstruct_text(original: str, accepted: list[dict[str, str]]) -> str:
    """Reconstruct text from original by applying accepted changes.

    Args:
        original: Full original text.
        accepted: List of dicts with ``original_text`` and ``revised_text`` keys.

    Returns:
        Reconstructed text with all accepted changes applied.

    Edge cases:
        - Change text not found in current state → skip (tolerant).
        - Overlapping changes → apply in order (last wins).
        - Empty accepted list → returns original unchanged.
    """
    result = original
    for change in accepted:
        orig_seg = change.get("original_text", "")
        rev_seg = change.get("revised_text", "")
        if not orig_seg:
            continue
        # Apply first occurrence only (changes should be non-overlapping
        # sentences — applying more than once could corrupt the text).
        if orig_seg in result:
            result = result.replace(orig_seg, rev_seg, 1)
    return result
