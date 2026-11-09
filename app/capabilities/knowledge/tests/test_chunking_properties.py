"""Property-based tests for the passage chunker (Hypothesis).

These complement the example-based tests: they state invariants that must hold
for *every* input, which example tests cannot cover exhaustively.
"""

from hypothesis import given
from hypothesis import strategies as st

from app.capabilities.knowledge.chunking import chunk_text


@given(st.text(min_size=0, max_size=2000), st.integers(min_value=1, max_value=500))
def test_chunks_reconstruct_non_empty_content(text: str, size: int) -> None:
    chunks = chunk_text(text, size=size)
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    # Every chunk is non-empty.
    assert all(chunk.strip() for chunk in chunks)
    # Reassembling the chunks recovers every non-empty paragraph of the input.
    if paragraphs:
        assert len(chunks) >= 1
        rejoined = "\n\n".join(chunks)
        for paragraph in paragraphs:
            assert paragraph in rejoined
    # No chunk exceeds size by more than a single paragraph (the documented
    # "stay whole" rule).
    for chunk in chunks:
        assert len(chunk) <= size + max((len(p) for p in paragraphs), default=0)


@given(st.text(min_size=0, max_size=500))
def test_empty_or_whitespace_input_yields_no_chunks(text: str) -> None:
    if not text.strip():
        assert chunk_text(text) == []
