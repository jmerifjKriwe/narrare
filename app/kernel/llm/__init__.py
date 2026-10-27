"""The LLM boundary: one streaming contract, entries picked per user and task.

The contract and its prompt markers live in :mod:`app.kernel.llm.contract`;
the entries live in their own modules — the fake, the openai-chat adapter
over the official SDK — and :mod:`app.kernel.llm.resolution` decides which one serves a
call: per user and per task, down the assignment cascade, with the
environment (``NARRE_LLM_PROVIDER``, defaulting to the fake) as the tier a
fresh clone runs on. The fake is a normal entry, not a test branch: routing,
prompt composition, streaming and persistence run the same code whichever
entry a call resolves to.

pydantic-ai is deliberately absent. One streaming completion over a fixed prompt
needs a single async method; an agent layer would add tools, retries and
structured output that nothing in v2 asks for. Revisit this module if tool use or
agent orchestration appears — not before.
"""

from app.kernel.llm.contract import PURPOSE_PREFIX, SOURCE_PREFIX, TextProvider

__all__ = [
    "PURPOSE_PREFIX",
    "SOURCE_PREFIX",
    "TextProvider",
]
