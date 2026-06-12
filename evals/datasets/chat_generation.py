"""Chat generation Pydantic Evals dataset."""

from __future__ import annotations

from typing import Any

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import IsInstance

from evals.evaluators import ChatDraftStructureMatch, ChatGenerationOutputValidator
from evals.models import ChatGenerationInput, ChatGenerationResult


def build_dataset() -> Dataset[ChatGenerationInput, ChatGenerationResult, dict[str, Any]]:
    """Build the chat generation eval dataset.

    Three cases per agent type (9 total) with realistic fantasy fiction text.
    Metadata tags the ``agent_type`` for evaluator filtering.
    """

    return Dataset(
        name="chat_generation",
        cases=[
            # --- ChatAgent cases ---
            Case(
                name="chat-mood-and-atmosphere",
                inputs=ChatGenerationInput(
                    agent_type="chat",
                    prompt_text="Describe walking through a misty graveyard at midnight.",
                    genre="Fantasy",
                ),
                expected_output=None,
                metadata={"agent_type": "chat"},
            ),
            Case(
                name="chat-character-backstory",
                inputs=ChatGenerationInput(
                    agent_type="chat",
                    prompt_text="Three backstories for a blacksmith who finds a magical anvil.",
                    genre="Fantasy",
                ),
                expected_output=None,
                metadata={"agent_type": "chat"},
            ),
            Case(
                name="chat-worldbuilding-question",
                inputs=ChatGenerationInput(
                    agent_type="chat",
                    prompt_text="Explain how a floating city collects rainwater and grows food.",
                    genre="Fantasy",
                ),
                expected_output=None,
                metadata={"agent_type": "chat"},
            ),
            # --- DraftAgent cases ---
            Case(
                name="draft-chapter-opening",
                inputs=ChatGenerationInput(
                    agent_type="draft",
                    prompt_text=(
                        "The city of Aethra was not built so much as grown — "
                        "coral-like spires of obsidian and pearl that rose from "
                        "the desert floor over centuries. Kaelen pressed his palm "
                        "against the gate, and the stone remembered him."
                    ),
                    genre="Fantasy",
                ),
                expected_output=None,
                metadata={"agent_type": "draft"},
            ),
            Case(
                name="draft-dialogue-scene",
                inputs=ChatGenerationInput(
                    agent_type="draft",
                    prompt_text=(
                        '"You cannot cross the Veil," said the ferryman, his voice '
                        'like dry leaves scraping stone. "Not without payment." '
                        'Lyra held up a single silver coin. "Will this suffice?" '
                        "The ferryman's hollow eyes gleamed."
                    ),
                    genre="Fantasy",
                ),
                expected_output=None,
                metadata={"agent_type": "draft"},
            ),
            Case(
                name="draft-action-sequence",
                inputs=ChatGenerationInput(
                    agent_type="draft",
                    prompt_text=(
                        "The wyrm's tail smashed through the colonnade, sending "
                        "pillars of veined marble crashing into the courtyard. "
                        "Sera rolled sideways, came up with her blade glowing "
                        "white-hot, and charged before the beast could reorient."
                    ),
                    genre="Fantasy",
                ),
                expected_output=None,
                metadata={"agent_type": "draft"},
            ),
            # --- InlineSuggestAgent cases ---
            Case(
                name="suggest-forest-description",
                inputs=ChatGenerationInput(
                    agent_type="inline_suggest",
                    prompt_text="The ancient forest was silent except for the",
                    genre="Fantasy",
                ),
                expected_output=None,
                metadata={"agent_type": "inline_suggest"},
            ),
            Case(
                name="suggest-dialogue-beat",
                inputs=ChatGenerationInput(
                    agent_type="inline_suggest",
                    prompt_text='"I never meant to betray you," she whispered, her voice',
                    genre="Fantasy",
                ),
                expected_output=None,
                metadata={"agent_type": "inline_suggest"},
            ),
            Case(
                name="suggest-transition",
                inputs=ChatGenerationInput(
                    agent_type="inline_suggest",
                    prompt_text="Days turned into weeks, and the mountain pass showed no",
                    genre="Fantasy",
                ),
                expected_output=None,
                metadata={"agent_type": "inline_suggest"},
            ),
        ],
        evaluators=[
            IsInstance(type_name="ChatGenerationResult"),
            ChatGenerationOutputValidator(),
            ChatDraftStructureMatch(),
        ],
    )
