# Q-005 — Does pydantic-ai support GLM-5.1 via z.ai natively?

> **Status:** ✅ Resolved
> **Resolved:** project-init+1
> **Resolution:** Z.AI exposes OpenAI-compatible endpoints. pydantic-ai supports
>                these via `OpenAIModel(base_url=...)`. No custom adapter needed.
> **ADR created:** None needed — this is a configuration decision, not an
>                 architectural one. Documented in `TECH_STACK.md` and
>                 `core/llm/_providers/zai.py`.

---

## Context

The primary development LLM is GLM-5.1 accessed via z.ai.
pydantic-ai is the LLM agent runtime.

## Resolution

Z.AI exposes **two** OpenAI-compatible API endpoints:

| Endpoint | URL | Use case |
|----------|-----|----------|
| General API | `https://api.z.ai/api/paas/v4` | Chat, writing, analysis |
| Coding API | `https://api.z.ai/api/coding/paas/v4` | Code generation agents |

Both are OpenAI-compatible (`/v1/chat/completions` protocol).
pydantic-ai's `OpenAIModel` accepts a `base_url` parameter for exactly this case.

## Implementation

```python
# core/llm/_providers/zai.py

from pydantic_ai.models.openai import OpenAIModel
from narrare_core.config import Settings

def make_zai_model(model_id: str, *, coding: bool = False) -> OpenAIModel:
    """
    Create a pydantic-ai model for Z.AI endpoints.

    Args:
        model_id: Z.AI model identifier (e.g. "glm-z1-32b").
        coding: If True, uses the Coding API endpoint optimised for
                code generation tasks.

    Returns:
        Configured OpenAIModel pointing at the appropriate Z.AI endpoint.
    """
    base_url = (
        "https://api.z.ai/api/coding/paas/v4"
        if coding
        else "https://api.z.ai/api/paas/v4"
    )
    return OpenAIModel(
        model_id,
        base_url=base_url,
        api_key=settings.zai_api_key,
    )
```

The `LLMIntent` → provider routing in `core/llm/intents.py` can route
code-adjacent intents (e.g. future `LLMIntent.CODE`) to the Coding API
automatically.

## Impact on Architecture

- No custom provider adapter needed beyond the factory function above
- Z.AI is registered in `core/llm/_providers/registry.py` as `"zai"`
- Setup Wizard Step 4 exposes Z.AI as a provider option
- `ZAI_API_KEY` env var required (documented in `.env.example`)

## Reference

- Z.AI API docs: https://docs.z.ai/api-reference/introduction
- pydantic-ai OpenAI-compatible providers: https://ai.pydantic.dev/models/openai/
