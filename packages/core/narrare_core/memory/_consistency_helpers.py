"""Helpers for the consistency-feedback service (CR-AUFG-03-10).

Pure transformations between :class:`ConsistencyDismissalRecord` /
:class:`DismissalMatch` and mem0 memory/message shapes. Extracted into a
private module so the service file stays focused on mem0 orchestration and
under the RULE-04 file-size limit (one responsibility per module): this
module owns *shape mapping*, the service owns *I/O + degradation*.

Privacy (ADR-045 Decision 8, RULE-22): only the finding *description* (a
structural analysis output) and linkage metadata are encoded — never raw
draft prose. Mirrors ``SessionMemoryService``'s structural-metadata rule.
"""

from __future__ import annotations

from typing import Any

from narrare_core.memory.consistency_models import (
    ConsistencyDismissalRecord,
    DismissalMatch,
)

# mem0 metadata marker identifying a consistency-dismissal memory. Distinguishes
# dismissal memories from other memory kinds (feedback, writing session) stored
# under the same user+project scope, so the retrieve filter is type-safe.
DISMISSAL_TYPE = "consistency_dismissal"


def build_dismissal_message(record: ConsistencyDismissalRecord) -> str:
    """Build a natural-language memory message from the structured record.

    Privacy-safe: includes the finding *description* (structural analysis
    output) and entity names — never raw draft prose.
    """
    parts: list[str] = [f"category: {record.category}"]
    if record.entity_names:
        parts.insert(0, f"entities: {', '.join(record.entity_names)}")
    message = (
        f"Consistency finding dismissed as false positive: "
        f"{record.finding_description} ({', '.join(parts)})"
    )
    if record.reason:
        message += f" — reason: {record.reason}"
    return message


def build_dismissal_metadata(record: ConsistencyDismissalRecord) -> dict[str, Any]:
    """Build the mem0 metadata payload for a dismissal memory.

    Beyond the linkage keys (type/novel_id/user_id/fingerprint/category/
    severity), the finding *description* and user *reason* are stored so a
    retrieved ``DismissalMatch`` can be reconstructed faithfully — mem0's
    extraction LLM may rephrase the memory text, so metadata is the lossless
    source for these fields.
    """
    return {
        "type": DISMISSAL_TYPE,
        "novel_id": str(record.project_id),
        "user_id": str(record.user_id),
        "fingerprint": record.fingerprint,
        "category": record.category,
        "severity": record.severity,
        "finding_description": record.finding_description,
        "reason": record.reason,
    }


def normalise_score(raw: Any) -> float:
    """Normalise a mem0 similarity score to a clamped 0..1 float.

    mem0's pgvector hybrid search returns scores in 0..1 (cosine similarity).
    Clamped defensively so an unexpected value can never violate the
    ``DismissalMatch.similarity`` 0..1 contract.
    """
    try:
        score = float(raw)  # type: ignore[arg-type]
    except TypeError, ValueError:
        return 0.0
    if score < 0.0:
        return 0.0
    if score > 1.0:
        return 1.0
    return score


def to_dismissal_match(
    memory: dict[str, Any],
    expected_novel_id: str,
) -> DismissalMatch | None:
    """Map a mem0 search result to a ``DismissalMatch``, or None if ineligible.

    Returns None when the memory is not a consistency dismissal or belongs to a
    different novel (cross-novel bleed guard on top of ``agent_id`` scoping).
    The finding description prefers the lossless metadata copy and falls back
    to the mem0 memory text when metadata is absent.
    """
    metadata: dict[str, Any] = memory.get("metadata") or {}
    if metadata.get("type") != DISMISSAL_TYPE:
        return None
    if metadata.get("novel_id") != expected_novel_id:
        return None
    description = metadata.get("finding_description")
    if not description:
        description = memory.get("memory", "") or memory.get("text", "")
    return DismissalMatch(
        fingerprint=metadata.get("fingerprint", ""),
        finding_description=description,
        similarity=normalise_score(memory.get("score")),
        reason=metadata.get("reason"),
    )
