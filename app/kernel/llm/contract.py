"""The provider boundary: what an entry offers, real or fake.

One method streams the completion. The other two let the kernel report what a
configured entry is and what it still needs, so a half-configured real provider
fails at startup instead of with the first prompt.
"""

from collections.abc import AsyncIterator  # noqa: TC003
from dataclasses import dataclass
from typing import Protocol

SOURCE_PREFIX = "SOURCE: "
"""A prompt that wants its answer to quote a supplied passage marks it with this
prefix, one passage per line. The fake reads it; a real provider reads the
sentence above it. The marker is a kernel constant because the prompt builder
and the providers must agree on it and live in different trees."""

PURPOSE_PREFIX = "PURPOSE: "
"""A prompt that asks for a machine-checked answer shape declares its purpose
with this prefix, one marked line naming it. The fake reads the line and
derives the answer that purpose contracts; a real provider reads it as part
of the instruction. A kernel constant for the same reason the source marker
is: prompt builders and providers must agree on it and live in different
trees."""


@dataclass(frozen=True)
class Message:
    """One turn of the conversation. The builders send a single user turn
    today; the shape leaves room for a system turn without another swap."""

    role: str  # "system" | "user"
    content: str


@dataclass(frozen=True)
class CompletionRequest:
    """What a consumer asks of the provider: the conversation and its limits.

    ``temperature``, ``max_tokens`` and ``response_schema`` travel to a real
    endpoint only when set — a local server that rejects an unknown field
    still receives the request a plain prompt always sent.
    """

    messages: tuple[Message, ...]
    temperature: float | None = None
    max_tokens: int | None = None
    response_schema: dict[str, object] | None = None

    @classmethod
    def user(cls, prompt: str) -> CompletionRequest:
        """The one-turn request every consumer builds today."""
        return cls(messages=(Message(role="user", content=prompt),))


@dataclass(frozen=True)
class Delta:
    """One piece of the answer, in order."""

    text: str


@dataclass(frozen=True)
class Usage:
    """The token counts the provider reports for the call."""

    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class Done:
    """The terminal event: nothing follows it, whatever the wire said."""


DONE = Done()
"""The singleton terminal event, so ``is DONE`` identifies it."""


type CompletionEvent = Delta | Usage | Done


class TextProvider(Protocol):
    """What every entry offers, real or fake."""

    def describe(self) -> str:
        """One line for the startup log, naming what is configured."""
        ...

    def configuration_problems(self) -> list[str]:
        """What this entry needs but does not have; empty when it is ready."""
        ...

    def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionEvent]:
        """Yield the completion's events: Delta pieces in order, one Usage, then DONE."""
        ...
