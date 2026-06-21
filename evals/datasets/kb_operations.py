"""KB operations Pydantic Evals dataset.

Covers four KB operation agents (Tier 3 of the eval-expansion plan):

- KBAgent        — KB intent routing and tool operation schema
- KBAssistAgent — assisted entity creation session output modes
- KBImproveAgent— improvement suggestions for existing KB entries
- KBMergeAgent  — duplicate-pair merge decisions

Three cases per agent, plus one extra KBAssist mode case (13 total). Metadata
tags ``agent_type`` so the metadata-aware evaluators select the right validator
per case (mirrors the ``planning_structure`` suite pattern).
"""

from __future__ import annotations

from typing import Any

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import IsInstance

from evals.evaluators import (
    KBAgentOperationSchemaValidator,
    KBAssistSchemaValidator,
    KBImproveSchemaValidator,
    KBMergeSchemaValidator,
)
from evals.models import KBOperationsInput, KBOperationsResult


def build_dataset() -> Dataset[KBOperationsInput, KBOperationsResult, dict[str, Any]]:
    """Build the KB operations eval dataset.

    Cases exercise deterministic smoke routing and the real output schema
    invariants for each KB operation agent.
    """

    return Dataset(
        name="kb_operations",
        cases=[
            # --- KBAgent tool operation cases ---
            Case(
                name="kb-agent-search-intent",
                inputs=KBOperationsInput(
                    agent_type="kb_agent",
                    prompt_text="Search the KB for Iron Guild factions.",
                    entity_type="faction",
                ),
                expected_output=None,
                metadata={"agent_type": "kb_agent"},
            ),
            Case(
                name="kb-agent-lookup-intent",
                inputs=KBOperationsInput(
                    agent_type="kb_agent",
                    prompt_text="Get details for Mara Silverwood before the council scene.",
                    entity_type="character",
                ),
                expected_output=None,
                metadata={"agent_type": "kb_agent"},
            ),
            Case(
                name="kb-agent-related-intent",
                inputs=KBOperationsInput(
                    agent_type="kb_agent",
                    prompt_text="Find related entities for Iron Guild allies.",
                    entity_type="faction",
                ),
                expected_output=None,
                metadata={"agent_type": "kb_agent"},
            ),
            # --- KBAssistAgent mode cases ---
            Case(
                name="kb-assist-question-mode",
                inputs=KBOperationsInput(
                    agent_type="kb_assist",
                    prompt_text="Ask the next question about Mara's motivation.",
                    entity_type="character",
                    field_key="motivation",
                ),
                expected_output=None,
                metadata={"agent_type": "kb_assist"},
            ),
            Case(
                name="kb-assist-suggestion-mode",
                inputs=KBOperationsInput(
                    agent_type="kb_assist",
                    prompt_text="Suggest a value for the role field.",
                    entity_type="character",
                    field_key="role",
                ),
                expected_output=None,
                metadata={"agent_type": "kb_assist"},
            ),
            Case(
                name="kb-assist-draft-mode",
                inputs=KBOperationsInput(
                    agent_type="kb_assist",
                    prompt_text="Draft a partial entry for Mara Silverwood.",
                    entity_type="character",
                    field_key="role",
                ),
                expected_output=None,
                metadata={"agent_type": "kb_assist"},
            ),
            Case(
                name="kb-assist-complete-mode",
                inputs=KBOperationsInput(
                    agent_type="kb_assist",
                    prompt_text="Complete the entry for Mara Silverwood.",
                    entity_type="character",
                    field_key="role",
                ),
                expected_output=None,
                metadata={"agent_type": "kb_assist"},
            ),
            # --- KBImproveAgent cases ---
            Case(
                name="kb-improve-missing-field",
                inputs=KBOperationsInput(
                    agent_type="kb_improve",
                    prompt_text="Improve a sparse character entry and add missing motivation.",
                    entity_type="character",
                    field_key="motivation",
                ),
                expected_output=None,
                metadata={"agent_type": "kb_improve"},
            ),
            Case(
                name="kb-improve-connect-entity",
                inputs=KBOperationsInput(
                    agent_type="kb_improve",
                    prompt_text="Connect this entry to Iron Guild allies from world context.",
                    entity_type="character",
                    field_key="allies",
                ),
                expected_output=None,
                metadata={"agent_type": "kb_improve"},
            ),
            Case(
                name="kb-improve-reorganize-entry",
                inputs=KBOperationsInput(
                    agent_type="kb_improve",
                    prompt_text="Reorganize scattered notes into clearer character sections.",
                    entity_type="character",
                    field_key="notes",
                ),
                expected_output=None,
                metadata={"agent_type": "kb_improve"},
            ),
            # --- KBMergeAgent cases ---
            Case(
                name="kb-merge-duplicate-pair",
                inputs=KBOperationsInput(
                    agent_type="kb_merge",
                    prompt_text="Mara Silverwood and Mara of Silverwood are the same person.",
                    entity_type="character",
                ),
                expected_output=None,
                metadata={"agent_type": "kb_merge"},
            ),
            Case(
                name="kb-merge-distinct-pair",
                inputs=KBOperationsInput(
                    agent_type="kb_merge",
                    prompt_text="Mara Silverwood and Captain Ilya are not duplicate people.",
                    entity_type="character",
                ),
                expected_output=None,
                metadata={"agent_type": "kb_merge"},
            ),
            Case(
                name="kb-merge-uncertain-pair",
                inputs=KBOperationsInput(
                    agent_type="kb_merge",
                    prompt_text="Mara and the masked captain may overlap but evidence is unclear.",
                    entity_type="character",
                ),
                expected_output=None,
                metadata={"agent_type": "kb_merge"},
            ),
        ],
        evaluators=[
            IsInstance(type_name="KBOperationsResult"),
            KBAgentOperationSchemaValidator(),
            KBAssistSchemaValidator(),
            KBImproveSchemaValidator(),
            KBMergeSchemaValidator(),
        ],
    )
