"""The one writer of llm_calls (plan §3.4).

It adds to the caller's session and never commits: the job handler's terminal
commit or the stream finalizer's own short session owns that (D14). The two
text columns are capped at 64 KB with a truncated flag, so a runaway prompt
cannot bloat the audit while the row still proves the call happened.
"""

from collections.abc import AsyncGenerator  # noqa: TC003
from logging import getLogger
from time import monotonic
from typing import TYPE_CHECKING

from anyio import CancelScope
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.kernel.db.session import Session
from app.kernel.llm import provider_facts
from app.kernel.llm.contract import (
    CompletionEvent,
    CompletionRequest,
    Delta,
    TextProvider,
    Usage,
)
from app.kernel.llm.models import ERROR, OK, LlmCall

if TYPE_CHECKING:
    from uuid import UUID

logger = getLogger("narrare")

CAP = 65_536
"""The width of each text column: 64 KB of characters bounds the audit without
losing an ordinary prompt or answer."""


def _capped(text: str) -> tuple[str, bool]:
    """The text clipped to CAP, and whether it was clipped at all."""
    if len(text) <= CAP:
        return text, False
    return text[:CAP], True


async def record_call(
    session: AsyncSession,
    *,
    user_id: UUID,
    task_key: str,
    provider_kind: str,
    model: str,
    latency_ms: int,
    status: str,
    prompt_text: str,
    response_text: str,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    novel_id: UUID | None = None,
    prompt_key: str | None = None,
    error: str | None = None,
) -> None:
    """Add one audit row on the caller's session; the caller's commit lands it.

    Prompt and response are each limited to 65,536 characters; ``truncated``
    is true if either was shortened. Text exactly at the limit is preserved.
    ``latency_ms`` is the caller's elapsed time in milliseconds; absent token
    counts remain NULL. This function neither flushes nor commits the session.

    cost_usd is never set here: WP2's catalog prices the call, and until then
    the column stays NULL — an unknown price is not a free call (D5).
    """
    prompt_text, prompt_clipped = _capped(prompt_text)
    response_text, response_clipped = _capped(response_text)
    session.add(
        LlmCall(
            user_id=user_id,
            task_key=task_key,
            provider_kind=provider_kind,
            model=model,
            latency_ms=latency_ms,
            status=status,
            prompt_text=prompt_text,
            response_text=response_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            novel_id=novel_id,
            prompt_key=prompt_key,
            error=error,
            truncated=prompt_clipped or response_clipped,
        )
    )


async def audited_stream(
    provider: TextProvider,
    request: CompletionRequest,
    *,
    user_id: UUID,
    task_key: str,
    novel_id: UUID | None = None,
) -> AsyncGenerator[CompletionEvent]:
    """Yield the provider's events and audit the call however the stream ends.

    One finalizer for every streaming capability. The row is written in a
    ``finally`` under a shielded cancel scope, so a disconnecting client or a
    cancelled task cannot take it with it; a failed audit is logged, never
    raised into a finished response (§3.4 — a log row, not user data).
    Status names the call, not the delivery: ``ok`` once the provider ended
    cleanly, ``error`` when the provider raised (the error text rides along),
    and ``error`` with "stream interrupted" when the consumer went away
    before either happened.
    """
    pieces: list[str] = []
    usage: Usage | None = None
    started = monotonic()
    status = ERROR
    error: str | None = "stream interrupted"
    try:
        async for event in provider.stream(request):
            if isinstance(event, Delta):
                pieces.append(event.text)
            elif isinstance(event, Usage):
                usage = event
            yield event
    except Exception as failure:
        error = str(failure)
        raise
    else:
        status, error = OK, None
    finally:
        with CancelScope(shield=True):
            try:
                kind, model = provider_facts()
                async with Session() as session:
                    await record_call(
                        session,
                        user_id=user_id,
                        task_key=task_key,
                        provider_kind=kind,
                        model=model,
                        latency_ms=round((monotonic() - started) * 1000),
                        status=status,
                        prompt_text="".join(message.content for message in request.messages),
                        response_text="".join(pieces),
                        input_tokens=usage.input_tokens if usage else None,
                        output_tokens=usage.output_tokens if usage else None,
                        novel_id=novel_id,
                        error=error,
                    )
                    await session.commit()
            except Exception:
                logger.exception("%s audit failed", task_key)
