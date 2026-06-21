"""Deterministic smoke task for the kb_operations eval suite.

Mirrors ``planning_structure_smoke.py``: a standalone module with the
CI-safe task function and its producer helpers, imported lazily by
``SmokeTaskFactory.kb_operations_task`` so that ``evals/tasks/smoke.py``
stays within RULE-04 file-size limits.

Four KB operation agents are covered (KBAgent, KBAssistAgent,
KBImproveAgent, KBMergeAgent). Each producer derives a schema-valid
result section from the input prompt — no LLM is called. The output
mirrors the real agent's output shape so the metadata-aware evaluators
assert genuine schema/range/count properties, not stubs.

Routing is keyword-based and deterministic so the same input always
yields the same operation/mode/decision. This guarantees the smoke
eval scores are reproducible in CI.
"""

from __future__ import annotations

import re

from evals.models import (
    KBAgentOperationSection,
    KBAssistSection,
    KBImproveSection,
    KBImproveSuggestionSection,
    KBMergeDecisionSection,
    KBMergeSection,
    KBMergeStrategySection,
    KBOperationsInput,
    KBOperationsResult,
)


async def kb_operations_task(inputs: object) -> object:
    """Run the CI-safe kb_operations smoke task."""

    return await kb_operations(KBOperationsInput.model_validate(inputs))


async def kb_operations(inputs: KBOperationsInput) -> KBOperationsResult:
    """Produce deterministic, schema-valid KB operation output without LLM calls.

    Routes to a per-agent deterministic producer based on ``agent_type``.
    Each producer yields a result whose section matches the real agent's
    output shape and satisfies the metadata-aware validators (so smoke
    asserts REAL schema/range/count behaviour, not stubs).
    """

    if inputs.agent_type == "kb_agent":
        return KBOperationsResult(kb_agent=_kb_agent_smoke(inputs.prompt_text, inputs.entity_type))
    if inputs.agent_type == "kb_assist":
        return KBOperationsResult(kb_assist=_kb_assist_smoke(inputs.prompt_text, inputs.field_key))
    if inputs.agent_type == "kb_improve":
        return KBOperationsResult(
            kb_improve=_kb_improve_smoke(inputs.prompt_text, inputs.field_key)
        )
    return KBOperationsResult(kb_merge=_kb_merge_smoke(inputs.prompt_text))


# ---------------------------------------------------------------------------
# Text-extraction helpers (shared across producers)
# ---------------------------------------------------------------------------

# Order matters: the most specific prefix must come first so a shorter
# generic prefix (e.g. ``"get "``) does not shadow ``"get details for "``.
_KB_AGENT_PREFIXES: tuple[str, ...] = (
    "find related entities for ",
    "get details for ",
    "search the kb for ",
    "search kb for ",
    "search for ",
    "look up ",
    "get ",
    "find ",
)


def _strip_command_prefix(prompt: str) -> str:
    """Strip a known KB-agent command prefix (case-insensitive)."""

    lowered = prompt.lower()
    for prefix in _KB_AGENT_PREFIXES:
        if lowered.startswith(prefix):
            return prompt[len(prefix) :].strip()
    return prompt.strip()


def _first_capitalized_phrase(text: str) -> str:
    """Return the first run of consecutive capitalised words, or empty string."""

    match = re.search(r"\b[A-Z][\w']+(?:\s+[A-Z][\w']+)*", text)
    return match.group(0).strip() if match else ""


def _all_capitalized_phrases(text: str) -> list[str]:
    """Return every run of consecutive capitalised words in *text*."""

    return [
        match.group(0).strip() for match in re.finditer(r"\b[A-Z][\w']+(?:\s+[A-Z][\w']+)*", text)
    ]


# ---------------------------------------------------------------------------
# KBAgent
# ---------------------------------------------------------------------------


def _kb_agent_smoke(prompt_text: str, entity_type: str) -> KBAgentOperationSection:
    """Route a KB request to ``search_kb`` / ``get_entity`` / ``get_related_entities``.

    Detection is keyword-based and deterministic. The extracted entity name
    or search query mirrors what the real ``KBAgent`` tool dispatcher would
    produce, so the operation-specific validator checks fire on real fields.
    """

    lowered = prompt_text.lower()
    if "related" in lowered:
        entity_name = (
            _first_capitalized_phrase(_strip_command_prefix(prompt_text)) or "Unknown Entity"
        )
        return KBAgentOperationSection(
            operation="get_related_entities",
            entity_name=entity_name,
            entity_type=entity_type,
            formatted_response=(f"Entities related to {entity_name} (deterministic smoke)."),
        )
    if "search" in lowered:
        query = _strip_command_prefix(prompt_text) or prompt_text
        return KBAgentOperationSection(
            operation="search_kb",
            query=query,
            entity_type=entity_type,
            formatted_response=f"Search results for '{query}' (deterministic smoke).",
        )
    entity_name = _first_capitalized_phrase(_strip_command_prefix(prompt_text)) or "Unknown Entity"
    return KBAgentOperationSection(
        operation="get_entity",
        entity_name=entity_name,
        entity_type=entity_type,
        formatted_response=f"Entity: {entity_name} details (deterministic smoke).",
    )


# ---------------------------------------------------------------------------
# KBAssistAgent
# ---------------------------------------------------------------------------


def _kb_assist_smoke(prompt_text: str, field_key: str) -> KBAssistSection:
    """Pick a KBAssist mode from prompt keywords and emit the mode's required fields.

    Mirrors ``KBAssistAgent._validate_output`` mode invariants: question mode
    needs ``question`` + ``field_key``; suggestion needs ``suggestion`` +
    ``field_key``; draft and complete modes need non-empty dict entries.
    """

    lowered = prompt_text.lower()
    if "complete" in lowered:
        return KBAssistSection(
            mode="complete",
            field_key=field_key,
            final_entry={
                "name": "Mara Silverwood",
                field_key: f"Completed {field_key} value (deterministic smoke).",
            },
            reasoning="Smoke completion assembles deterministic key/value pairs.",
            progress=1.0,
        )
    if "suggest" in lowered:
        return KBAssistSection(
            mode="suggestion",
            field_key=field_key,
            suggestion=(f"Suggested value for '{field_key}': a concise, story-driven default."),
            reasoning="Smoke suggestion picks a deterministic placeholder value.",
            progress=0.7,
        )
    if "draft" in lowered:
        return KBAssistSection(
            mode="draft",
            field_key=field_key,
            draft_entry={
                "name": "Mara Silverwood",
                field_key: f"Drafted {field_key} value (deterministic smoke).",
            },
            reasoning="Smoke draft assembles a partial entry dict.",
            progress=0.4,
        )
    # Default mode is "question".
    return KBAssistSection(
        mode="question",
        field_key=field_key,
        question=_build_question(field_key),
        reasoning="Smoke question asks for the next missing field.",
        progress=0.5,
    )


def _build_question(field_key: str) -> str:
    """Build a deterministic question that ends with '?'."""

    return f"What value should the '{field_key}' field have for this entity?"


# ---------------------------------------------------------------------------
# KBImproveAgent
# ---------------------------------------------------------------------------


def _kb_improve_smoke(prompt_text: str, field_key: str) -> KBImproveSection:
    """Emit one improvement suggestion per detected signal in the prompt.

    Keyword detection maps to ``SuggestionType`` values so the validator's
    type-set check fires on real values. Guarantees at least one suggestion.
    """

    lowered = prompt_text.lower()
    suggestions: list[KBImproveSuggestionSection] = []

    if "missing" in lowered or "add " in lowered:
        suggestions.append(
            KBImproveSuggestionSection(
                type="add_field",
                target=field_key,
                description=f"Add the missing '{field_key}' field to this entry.",
                proposed_content=f"Suggested {field_key} content (deterministic smoke).",
                confidence=0.8,
                reasoning="Field absent from the source entry.",
            )
        )
    if "sparse" in lowered or "expand" in lowered:
        suggestions.append(
            KBImproveSuggestionSection(
                type="expand",
                target=field_key,
                description=f"Expand the sparse '{field_key}' field with more detail.",
                proposed_content=f"Expanded {field_key} content (deterministic smoke).",
                confidence=0.75,
                reasoning="Existing field content is too brief.",
            )
        )
    if "connect" in lowered:
        suggestions.append(
            KBImproveSuggestionSection(
                type="connect",
                target="Iron Guild",
                description="Connect this entry to the Iron Guild faction.",
                related_entity_name="Iron Guild",
                confidence=0.7,
                reasoning="World context references Iron Guild as a related faction.",
            )
        )
    if "reorganize" in lowered or "reorganise" in lowered or "scattered" in lowered:
        suggestions.append(
            KBImproveSuggestionSection(
                type="reorganize",
                target=field_key,
                description=f"Reorganize the scattered {field_key} notes into clearer sections.",
                confidence=0.65,
                reasoning="Notes are scattered across the entry without structure.",
            )
        )

    if not suggestions:
        suggestions.append(
            KBImproveSuggestionSection(
                type="expand",
                target=field_key,
                description=f"Expand the '{field_key}' field with more detail.",
                confidence=0.6,
                reasoning="Default smoke suggestion when no keyword signal is present.",
            )
        )

    completeness = max(0.1, 0.9 - 0.15 * len(suggestions))
    return KBImproveSection(
        suggestions=suggestions,
        overall_assessment=(
            f"Smoke analysis: {len(suggestions)} suggestion(s) derived from prompt keywords. "
            "Deterministic — no model called."
        ),
        completeness_score=completeness,
        context_used=[],
    )


# ---------------------------------------------------------------------------
# KBMergeAgent
# ---------------------------------------------------------------------------


def _kb_merge_smoke(prompt_text: str) -> KBMergeSection:
    """Classify a duplicate-pair prompt into merge / distinct / uncertain.

    Keyword detection drives the decision so the merge validator's value-set
    check fires on a real value. ``merge_strategy`` is emitted only for
    ``merge`` decisions, mirroring ``MergeDecision`` semantics.
    """

    lowered = prompt_text.lower()
    if (
        "not duplicate" in lowered
        or "are not" in lowered
        or "not the same" in lowered
        or "distinct" in lowered
        or "different" in lowered
    ):
        decision = "distinct"
        confidence = 0.9
    elif (
        "unclear" in lowered
        or "uncertain" in lowered
        or "may overlap" in lowered
        or "may be" in lowered
        or "might be" in lowered
    ):
        decision = "uncertain"
        confidence = 0.55
    else:
        decision = "merge"
        confidence = 0.9

    names = _all_capitalized_phrases(prompt_text)
    keep_name = names[0] if names else "Unknown Entity"

    merge_strategy: KBMergeStrategySection | None = None
    if decision == "merge":
        preserve_aliases = [names[1]] if len(names) > 1 else []
        merge_strategy = KBMergeStrategySection(
            keep_name=keep_name,
            merge_fields={},
            preserve_aliases=preserve_aliases,
            merge_relationships=True,
        )

    decision_section = KBMergeDecisionSection(
        pair_id="pair-1",
        decision=decision,
        confidence=confidence,
        reasoning=(
            f"Smoke merge analysis derived '{decision}' from prompt keywords. "
            "Deterministic — no model called."
        ),
        merge_strategy=merge_strategy,
    )

    return KBMergeSection(
        merge_decisions=[decision_section],
        overall_notes=(
            f"Smoke merge: 1 decision emitted ({decision}). Deterministic — no model called."
        ),
        metadata={"smoke": True},
    )
