<!-- Context: narrare-dev/examples/testing-patterns | Priority: P2 | Source: docs/development/testing-standards.md | Updated: 2026-06-12 -->

# Testing Patterns

Code patterns for writing tests. Fake classes for domain deps, TestModel/FunctionModel for LLM deps.

## Fake Class Pattern

Every domain dependency gets a Fake implementing its Protocol. Structure: `__init__` with store → `seed()` for setup → Protocol methods → call tracking.

```python
class FakeChapterRepository:
    def __init__(self) -> None:
        self._store: dict[UUID, Chapter] = {}
        self.calls: list[CallRecord] = []

    def seed(self, *chapters: Chapter) -> None:
        for ch in chapters:
            self._store[ch.id] = ch

    async def get_by_id(self, chapter_id: UUID, novel_id: UUID) -> Chapter | None:
        self.calls.append(CallRecord("get_by_id", chapter_id=chapter_id))
        return self._store.get(chapter_id)

    def call_count(self, method: str) -> int:
        return sum(1 for c in self.calls if c.method == method)
```

**What IS allowed**: Fakes, `TestModel`, `patch()` for external functions, `AsyncMock()` on Fake objects for overrides.
**What is FORBIDDEN**: Bare `MagicMock()` without `spec=`, `MagicMock` as domain dep replacement, nested mock chains.

## TestModel — Deterministic LLM Responses

```python
from pydantic_ai.models.test import TestModel

async def test_summary_agent():
    model = TestModel(custom_output_text="A short summary.")
    agent = ChapterSummaryAgent(model=model)
    result = await agent.run(prompt="Summarize.", deps=SummaryDeps(language="en"))
    assert result.summary == "A short summary."
```

## FunctionModel — Scenario-Specific Behavior

Use when different inputs need different responses. Requires `stream_function` for streaming tests.

```python
from pydantic_ai.models.function import FunctionModel

def smart_mock(messages, info):
    if "error" in str(messages[-1]).lower():
        raise ModelHTTPError(status_code=500, model_name="test")
    return ModelResponse(parts=[TextPart("All good.")])

async def smart_mock_stream(messages, info):
    raise ModelHTTPError(status_code=500, model_name="test")
    yield  # makes this an async generator

model = FunctionModel(smart_mock, stream_function=smart_mock_stream)
```

## capture_run_messages — Tool Call Assertions

```python
from pydantic_ai import capture_run_messages

with capture_run_messages() as messages:
    with agent.override(model=test_model):
        result = await agent.run("Write about Anna")
tool_calls = [p for m in messages for p in m.parts if hasattr(p, "tool_name")]
assert any(tc.tool_name == "lookup_character" for tc in tool_calls)
```

## RULE-01 Exception Comment Pattern

Standalone comment on line **before** the import (ruff format may wrap end-of-line comments):

```python
# narrare: allow reason="gateway tests use TestModel instead of real LLM"
from pydantic_ai.models.test import TestModel
```

## Global Guard

Set in `tests/conftest.py`: `models.ALLOW_MODEL_REQUESTS = False`. Prevents all real LLM API calls — `RuntimeError` if accidentally triggered.

## Fixture Pattern

Constructor injection only. **Never** use `__new__()` to bypass `__init__`.

```python
@pytest.fixture
def test_model() -> TestModel:
    return TestModel(custom_output_text="Default response.")

@pytest.fixture
def service(fake_chapter_repo, test_model, registry, config):
    return ChapterSummaryService(registry=registry, config=config, chapter_repo=fake_chapter_repo)
```

**Reference**: `docs/development/testing-standards.md` (1224 lines)
**Related**: narrare-dev/guides/testing · narrare-dev/examples/python-patterns
