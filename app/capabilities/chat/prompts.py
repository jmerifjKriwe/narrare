"""The chat prompt. Chat owns its prompt text, per the spec.

The source prefix is a kernel constant: the fake provider quotes such a line,
so a test can see that retrieval reached the model boundary. A real provider
reads the instruction above it and ignores the marker. The passage lines
arrive pre-joined behind the marker (`sources_block`) — the template never
writes the marker itself, and the contract refuses a template that drops
`{{ sources }}`, so a re-voiced frame cannot lose the sources.
"""

from collections.abc import Sequence  # noqa: TC003
from typing import Final

from app.kernel.llm import SOURCE_PREFIX
from app.kernel.prompts import get_registry, render_source
from app.kernel.retrieval import Passage  # noqa: TC001

CHAT_KEY: Final = "chat.ask"

CHAT_TEMPLATE = (
    "Answer the question using only the sources below. Quote the passage that "
    "carries the answer verbatim, and do not add knowledge from outside them.\n\n"
    "Question: {{ question }}\n\n"
    "Sources:\n{{ sources }}\n"
)


def sources_block(passages: Sequence[Passage]) -> str:
    """The source lines, each behind the kernel's marker — today's join."""
    return "\n".join(f"{SOURCE_PREFIX}{passage.text}" for passage in passages)


def sample_variables() -> dict[str, object]:
    """The sample the editor's legend and the save-time validation render.

    The sources arrive as the marker-carrying block an override receives —
    what its author may reorder, never rewrite.
    """
    return {
        "question": "Wo war der Leuchtturm?",
        "sources": f"{SOURCE_PREFIX}Der Leuchtturm am Horizont war seit Jahren dunkel.",
    }


def chat_contract(rendered: str) -> bool:
    """A re-voice may reorder the frame, never drop the marked sources."""
    return SOURCE_PREFIX in rendered


def chat_prompt(*, question: str, passages: Sequence[Passage]) -> str:
    """The bundled chat prompt, rendered offline through the registry's template.

    The same arrangement the chain render runs; no production caller remains —
    the service renders through the registry, and the golden pins this path
    byte for byte.
    """

    def no_includes(key: str) -> str:
        raise KeyError(key)

    return render_source(
        CHAT_TEMPLATE,
        {"question": question, "sources": sources_block(passages)},
        include=no_includes,
    )


get_registry().register(
    CHAT_KEY,
    template=CHAT_TEMPLATE,
    sample_variables=sample_variables,
    contract=chat_contract,
    novel_scopable=False,
)
