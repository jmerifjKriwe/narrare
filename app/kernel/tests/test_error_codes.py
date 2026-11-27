"""The kernel's error codes: one typed list the generator writes to TypeScript.

A code serializes as its own string on the wire — in a refusal's detail and in
the stream's terminal frame — and every stream failure maps to the closed set
rather than prose. The types are the contract; the bytes are pinned in
``test_llm_streaming.py``.
"""

import json

from app.kernel.errors import ErrorCode, coded
from app.kernel.llm.contract import ModelNotFoundError, ProviderAuthError, error_code
from app.kernel.llm.streaming import error_frame


def test_a_code_serializes_as_its_string() -> None:
    assert (
        json.dumps(coded(ErrorCode.ORDER_MISMATCH, chapter_ids=["a"]))
        == '{"code": "order_mismatch", "chapter_ids": ["a"]}'
    )


def test_the_stream_error_frame_carries_the_code() -> None:
    assert error_frame(ErrorCode.KEY_UNAVAILABLE) == (
        'event: error\ndata: {"code": "key-unavailable"}\n\n'
    )


def test_the_three_stream_failures_map_to_their_codes() -> None:
    assert error_code(ModelNotFoundError("m")) is ErrorCode.MODEL_NOT_FOUND
    assert error_code(ProviderAuthError()) is ErrorCode.PROVIDER_AUTH
    assert error_code(RuntimeError("x")) is ErrorCode.UNKNOWN
