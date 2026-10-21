"""The chat prompt. Chat owns its prompt text, per the spec.

The source prefix is a kernel constant: the fake provider quotes such a line, so
a test can see that retrieval reached the model boundary. A real provider reads
the instruction above it and ignores the marker.
"""

from collections.abc import Sequence  # noqa: TC003

from app.kernel.llm import SOURCE_PREFIX
from app.kernel.retrieval import Passage  # noqa: TC002


def chat_prompt(*, question: str, passages: Sequence[Passage]) -> str:
    sources = "\n".join(f"{SOURCE_PREFIX}{passage.text}" for passage in passages)
    return (
        "Answer the question using only the sources below. Quote the passage that "
        "carries the answer verbatim, and do not add knowledge from outside them.\n\n"
        f"Question: {question}\n\n"
        f"Sources:\n{sources}\n"
    )
