"""Structured answers: demand JSON, repair it, retry once, then fail with the reason.

The two knowledge handlers need a JSON array from a model that occasionally
answers in prose. This module owns that exchange for both of them — one call
shape, one repair attempt, one retry that carries the validation error, and a
failure that names what the parser refused so the job row can repeat it.

Every call, the retry included, goes through the caller's audit callback: the
rows still ride the handler's terminal commit, so a job that fails writes none
of them (D3).
"""

from dataclasses import dataclass
from time import monotonic
from typing import TYPE_CHECKING

from json_repair import repair_json

from app.kernel.llm.contract import CompletionRequest, Delta, Message, TextProvider, Usage

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


class MalformedAnswerError(ValueError):
    """The provider's answer is not the JSON the caller asked for.

    Its message is the parse reason: the lane writes it to ``Job.error``, so
    the user reads what the model sent rather than "the job failed".
    """


@dataclass(frozen=True)
class AuditedCall:
    """One provider call as the handler audits it: what was asked, what came back."""

    prompt: str
    answer: str
    latency_ms: int
    usage: Usage | None


async def _ask(provider: TextProvider, request: CompletionRequest) -> tuple[str, int, Usage | None]:
    """Run one streaming call to its end and report what it produced."""
    pieces: list[str] = []
    usage: Usage | None = None
    started = monotonic()
    async for event in provider.stream(request):
        if isinstance(event, Delta):
            pieces.append(event.text)
        elif isinstance(event, Usage):
            usage = event
    return "".join(pieces), round((monotonic() - started) * 1000), usage


def _read[T](answer: str, parse: Callable[[str], list[T]]) -> tuple[list[T] | None, str]:
    """Parse the answer, then its repair; report the reason the last attempt refused."""
    try:
        return parse(answer), ""
    except ValueError as error:
        reason = str(error) or "not the contracted JSON"
    repaired = repair_json(answer, return_objects=False)
    if repaired != answer:
        try:
            return parse(repaired), ""
        except ValueError as error:
            reason = str(error) or reason
    return None, reason


async def ask_structured[T](
    provider: TextProvider,
    prompt: str,
    *,
    schema: dict[str, object],
    parse: Callable[[str], list[T]],
    audit: Callable[[AuditedCall], Awaitable[None]],
) -> list[T]:
    """Ask for a schema-bound answer; repair, retry once, then raise the reason.

    ``parse`` raises ``ValueError`` with a message a writer can act on; that
    message is what the retry sends back and what ``MalformedAnswerError``
    carries when even the retry cannot be read.
    """
    first = CompletionRequest(messages=(Message("user", prompt),), response_schema=schema)
    answer, latency_ms, usage = await _ask(provider, first)
    await audit(AuditedCall(prompt=prompt, answer=answer, latency_ms=latency_ms, usage=usage))
    parsed, reason = _read(answer, parse)
    if parsed is not None:
        return parsed

    correction = (
        f"The previous answer was invalid: {reason}. "
        "Answer again with the JSON only, no prose and no code fences."
    )
    retry = CompletionRequest(
        messages=(Message("user", prompt), Message("user", correction)),
        response_schema=schema,
    )
    answer, latency_ms, usage = await _ask(provider, retry)
    await audit(
        AuditedCall(
            prompt=f"{prompt}\n\n{correction}",
            answer=answer,
            latency_ms=latency_ms,
            usage=usage,
        )
    )
    parsed, reason = _read(answer, parse)
    if parsed is not None:
        return parsed
    raise MalformedAnswerError(reason)
