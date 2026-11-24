"""HTTP surface for the prompts. Parses, delegates, returns; no logic here.

The save-time gate's refusals are 422s that name their reason — the render's
own (``syntax``, ``undefined-variable``, ``include-cycle``, …) beside the
scope rules' (``novel-scope``, ``unknown-novel``, ``contract``) — and an
unknown key is a 404 on every route. The save answers with the fresh detail;
the reset is the house's no-content 204, idempotent for a scope with no row.

The preview is the sandbox without the save: a 422 names what the save
would, a contract failure rides the 200 as a diagnostic. The live test
streams after the chat precedent — the context frame first, then the
deltas, then done or the one error frame — and answers its pre-stream
failures with coded faces: the no-context and embedding 409s, the rate
limit's 429 with its Retry-After, a lost key the 503, a provider that dies
before its first token the 502.
"""

import json
from collections.abc import AsyncGenerator
from logging import getLogger
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.prompts.schemas import (
    PromptCodedError,
    PromptDetail,
    PromptDiff,
    PromptKeyNotFound,
    PromptLiveTestBody,
    PromptPreview,
    PromptPreviewBody,
    PromptRefusal,
    PromptSave,
    PromptSummary,
    ValidationBody,
)
from app.capabilities.prompts.service import (
    LiveTestPrepared,
    LiveTestRateLimitedError,
    PromptNotFoundError,
    PromptRefusedError,
    PromptService,
)
from app.kernel.auth import current_user_id
from app.kernel.db.session import get_session
from app.kernel.embeddings import EmbeddingProvider, get_embedding_provider
from app.kernel.errors import coded_detail
from app.kernel.llm.audit import audited_stream
from app.kernel.llm.contract import CompletionEvent, CompletionRequest, Delta, Message, error_code
from app.kernel.llm.streaming import (
    DONE_FRAME,
    FinalizingStreamingResponse,
    failure_frame,
)
from app.kernel.prompts import LiveContextMissingError
from app.kernel.retrieval import EmbeddingMismatchError
from app.kernel.secrets import KeyUnavailableError

router = APIRouter(prefix="/api/prompts", tags=["prompts"])

logger = getLogger("narrare")

SSE_HEADERS = {"Cache-Control": "no-cache"}

SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserDep = Annotated[UUID, Depends(current_user_id)]
EmbeddingsDep = Annotated[EmbeddingProvider, Depends(get_embedding_provider)]


def _service(session: SessionDep, user_id: UserDep) -> PromptService:
    return PromptService(session, user_id)


ServiceDep = Annotated[PromptService, Depends(_service)]

# The declared failure contracts, shared by every route that can hit them.
# The 422 model is a union: the gate's refusal body beside the framework's
# own request-validation body — a declared model replaces the canned
# validation schema, so the union keeps both honest for the typed client.
# The list route takes no key, so it documents no 404. The annotation is
# the framework's own parameter type — ``Any`` carries its model-or-schema
# slot, nothing else.
_REFUSED_RESPONSES: dict[int | str, dict[str, Any]] = {
    422: {
        "description": "Refused by name — or the request failed validation.",
        "model": PromptRefusal | ValidationBody,
    },
}
_NOT_FOUND_RESPONSES: dict[int | str, dict[str, Any]] = {
    404: {"description": "No bundled prompt carries this key.", "model": PromptKeyNotFound},
}
_KEY_RESPONSES = _NOT_FOUND_RESPONSES | _REFUSED_RESPONSES


def _refused(error: PromptRefusedError) -> HTTPException:
    """The gate's refusal as a 422 naming its reason and its detail."""
    return HTTPException(status_code=422, detail={"reason": error.reason, "detail": str(error)})


def _errors(error: Exception) -> HTTPException:
    """The service vocabulary's mapping, shared by every route."""
    if isinstance(error, PromptNotFoundError):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, PromptRefusedError):
        return _refused(error)
    return HTTPException(status_code=500, detail=str(error))


@router.get("", response_model=list[PromptSummary], responses=_REFUSED_RESPONSES)
async def list_prompts(service: ServiceDep, novel_id: UUID | None = None) -> list[PromptSummary]:
    """Every bundled prompt with its facts and its two override tiers."""
    try:
        return await service.list(novel_id)
    except PromptRefusedError as error:
        raise _refused(error) from None


@router.get("/{key}", response_model=PromptDetail, responses=_KEY_RESPONSES)
async def get_prompt(
    service: ServiceDep,
    key: Annotated[str, Path(min_length=1)],
    novel_id: UUID | None = None,
) -> PromptDetail:
    """One prompt as the editor shows it: bundled source, legend, override."""
    try:
        return await service.detail(key, novel_id)
    except (PromptNotFoundError, PromptRefusedError) as error:
        raise _errors(error) from None


@router.put("/{key}", response_model=PromptDetail, responses=_KEY_RESPONSES)
async def put_prompt(
    service: ServiceDep,
    key: Annotated[str, Path(min_length=1)],
    payload: PromptSave,
) -> PromptDetail:
    """Validate and save the override for the scope; the fresh detail answers."""
    try:
        return await service.save(key, payload.content, payload.novel_id)
    except (PromptNotFoundError, PromptRefusedError) as error:
        raise _errors(error) from None


@router.delete("/{key}", status_code=204, responses=_KEY_RESPONSES)
async def delete_prompt(
    service: ServiceDep,
    key: Annotated[str, Path(min_length=1)],
    novel_id: UUID | None = None,
) -> None:
    """Reset the override for the scope; the other tier is untouched."""
    try:
        await service.delete(key, novel_id)
    except (PromptNotFoundError, PromptRefusedError) as error:
        raise _errors(error) from None


@router.get("/{key}/diff", response_model=PromptDiff, responses=_KEY_RESPONSES)
async def get_prompt_diff(
    service: ServiceDep,
    key: Annotated[str, Path(min_length=1)],
    novel_id: UUID | None = None,
) -> PromptDiff:
    """The bundled template against the override in force for the scope."""
    try:
        return await service.diff(key, novel_id)
    except (PromptNotFoundError, PromptRefusedError) as error:
        raise _errors(error) from None


@router.post("/{key}/preview", response_model=PromptPreview, responses=_KEY_RESPONSES)
async def preview_prompt(
    service: ServiceDep,
    key: Annotated[str, Path(min_length=1)],
    novel_id: UUID | None = None,
    body: PromptPreviewBody | None = None,
) -> PromptPreview:
    """Render the draft (or the scope's saved effective) at sample scope.

    A POST, not a GET: the draft rides the body, and a browser's ``fetch``
    refuses a GET body outright — the editor's preview loop would die at
    runtime. A render computation is no cacheable resource; the query's
    ``novel_id`` and the optional-body semantics stay the reads' shape.

    No model call, nothing persisted; a draft the sandbox refuses is the
    named 422, a contract failure the diagnostic inside the 200.
    """
    try:
        return await service.preview(key, novel_id, body.content if body is not None else None)
    except (PromptNotFoundError, PromptRefusedError) as error:
        raise _errors(error) from None


def _coded(status: int, code: str, detail: str) -> HTTPException:
    """The live test's coded face: the code the surfaces localize, the detail."""
    return HTTPException(status_code=status, detail=coded_detail(code, detail))


def _live_test_responses() -> dict[int | str, dict[str, Any]]:
    """The live test's declared contract: the shared 404/422 plus its faces."""
    coded = {"description": "A coded face names the failure.", "model": PromptCodedError}
    return _KEY_RESPONSES | {
        200: {
            "content": {
                "text/event-stream": {
                    "schema": {"type": "string"},
                    "description": (
                        "Server-sent events: one context frame, then the answer's"
                        " deltas, then one terminal event: done or error."
                    ),
                }
            }
        },
        409: coded | {"description": "No real context to assemble, or a corpus mismatch."},
        429: coded
        | {
            "description": "The user's live-test window is still closed.",
            "headers": {
                "Retry-After": {
                    "schema": {"type": "integer"},
                    "description": "The remaining seconds, whole, until the next test.",
                }
            },
        },
        502: coded | {"description": "The provider failed before its first token."},
        503: coded | {"description": "The key store cannot produce the provider's key."},
    }


async def _live_test_events(
    prepared: LiveTestPrepared,
    events: AsyncGenerator[CompletionEvent],
    first: CompletionEvent,
) -> AsyncGenerator[str]:
    """The context frame, then the answer, then done — or the one error frame.

    The context goes out before the first delta so the reader sees what the
    test rode — the fake's kind among it, the honest mark — while the answer
    is still arriving. A provider that dies mid-stream ends with the error
    frame instead of done, the chat precedent's spelling.
    """
    context = {
        "key": prepared.key,
        "source": prepared.source_mode,
        "provider": prepared.resolved.kind,
        "novel_id": str(prepared.novel_id) if prepared.novel_id is not None else None,
        "facts": prepared.facts,
    }
    yield f"data: {json.dumps({'context': context})}\n\n"
    try:
        if isinstance(first, Delta):
            yield f"data: {json.dumps({'delta': first.text})}\n\n"
        async for event in events:
            if isinstance(event, Delta):
                yield f"data: {json.dumps({'delta': event.text})}\n\n"
    except Exception as failure:
        logger.exception("live test stream failed")
        yield failure_frame(failure)
    else:
        yield DONE_FRAME
    finally:
        # The inner finalizer must run deterministically: relying on the
        # loop's async-generator finalizer would lose the audit row on a
        # disconnect.
        await events.aclose()


@router.post(
    "/{key}/live-test",
    response_class=FinalizingStreamingResponse,
    status_code=200,
    responses=_live_test_responses(),
)
async def live_test_prompt(
    service: ServiceDep,
    key: Annotated[str, Path(min_length=1)],
    user_id: UserDep,
    embeddings: EmbeddingsDep,
    payload: PromptLiveTestBody | None = None,
) -> FinalizingStreamingResponse:
    """Test the draft against the live wire over the capability's real context.

    Absent body (or content) tests the saved effective. The draft passes the
    save gate before any provider call and is never persisted; the call
    rides the key's task assignment and its own real context assembly; the
    answer streams and lands only in the audit row the task's calls share.
    """
    try:
        prepared = await service.prepare_live_test(
            key,
            payload.content if payload is not None else None,
            payload.novel_id if payload is not None else None,
            embeddings,
        )
    except PromptNotFoundError as error:
        raise _errors(error) from None
    except PromptRefusedError as error:
        raise _refused(error) from None
    except LiveContextMissingError as error:
        # The capability's real assembly found nothing to ride: the named
        # 409, never a sample swap.
        raise _coded(409, "no-context", str(error)) from None
    except LiveTestRateLimitedError as error:
        raise HTTPException(
            status_code=429,
            detail=coded_detail("rate-limited", str(error)),
            headers={"Retry-After": str(error.retry_after)},
        ) from None
    except KeyUnavailableError as error:
        # The message names the row, never the key — safe to carry.
        raise _coded(503, "key-unavailable", str(error)) from None
    except EmbeddingMismatchError as error:
        raise _coded(
            409,
            "embedding-mismatch",
            f"the stored corpus is embedded at width {error.stored}; "
            f"this request embeds at {error.found}",
        ) from None
    # Resolution and assembly read the request's session; the stream's only
    # write is the audit's own short session. The pooled connection goes back
    # before the provider stream holds the response open.
    await service.session.close()

    request = CompletionRequest(
        messages=(Message(role="user", content=prepared.prompt),),
        temperature=prepared.resolved.temperature,
        max_tokens=prepared.resolved.resolved_output_tokens,
    )
    events = audited_stream(
        prepared.resolved,
        request,
        user_id=user_id,
        task_key=prepared.key,
        novel_id=prepared.novel_id,
        prompt_key=prepared.key,
    )
    # Prime the stream: the first event decides the face. A provider that
    # fails before its first byte never starts a 200 — the coded 502 carries
    # the failure instead, and the audit's own row (the call ran) is already
    # written by the generator's finalizer.
    try:
        first = await anext(events)
    except StopAsyncIteration:
        await events.aclose()
        raise _coded(502, "unknown", "the provider answered nothing") from None
    except Exception as failure:
        await events.aclose()
        logger.exception("live test provider failed before its first token")
        raise _coded(502, error_code(failure), str(failure)) from None
    return FinalizingStreamingResponse(
        _live_test_events(prepared, events, first),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
