"""The one writer of llm_calls (plan §3.4).

It adds to the caller's session and never commits: the job handler's terminal
commit or the stream finalizer's own short session owns that (D14). The two
text columns are capped at 64 KB with a truncated flag, so a runaway prompt
cannot bloat the audit while the row still proves the call happened.
"""

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.kernel.llm.models import LlmCall

if TYPE_CHECKING:
    from uuid import UUID

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
