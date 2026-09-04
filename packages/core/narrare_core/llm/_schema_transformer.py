"""Universal JSON-Schema ``$ref``/``$defs`` inlining for OpenAI-compatible providers.

Structural defect fixed here
----------------------------
OpenAI's own API resolves JSON Schema ``$ref``/``$defs`` natively, so pydantic-ai's
``OpenAIJsonSchemaTransformer`` (the default for every ``OpenAIChatModel``) keeps
``$defs`` in place and only applies strict-mode transforms. OpenAI-*compatible*
endpoints (Z.AI, Ollama, OpenRouter, vLLM/llama.cpp) do not implement that
resolution: when an output schema like ``results.items.$ref: "#/$defs/ExtractionItem"``
reaches them, the referenced definition is never resolved and the model returns
degenerate structures (observed: empty ``items`` in KB extraction).

Why capability-preserving inlining — not a blanket swap
-------------------------------------------------------
Replacing the transformer with pydantic-ai's bare ``InlineDefsJsonSchemaTransformer``
everywhere would *discard* the OpenAI strict-mode transforms (``title`` removal,
``additionalProperties: false``, strict-compatibility tracking, oneOf handling).
This subclass keeps every ``OpenAIJsonSchemaTransformer`` behaviour and additionally
flips ``prefer_inlined_defs`` — the flag is read by ``walk()`` at call time, so
setting it after ``super().__init__`` composes both behaviours without re-implementing
the upstream ``__init__`` (upgrade-safe against signature changes).

Recursive definitions cannot be inlined (a self-reference has no finite expansion);
``JsonSchemaTransformer.walk()`` detects them and falls back to a ``$defs``/``$ref``
structure (verified lossless upstream, including OpenAI's ``"$ref": "#"`` root form).

Injection point
---------------
``Model.customize_request_parameters`` reads ``profile['json_schema_transformer']``
and applies it to ``function_tools``, ``output_tools`` AND ``output_object`` — so a
profile-level injection covers tool parameters and structured outputs alike.
``narrare_openai_compat_profile`` is the shared ``profile=`` callable for every
OpenAI-compatible factory: it receives the fully provider-resolved profile
(``DEFAULT_PROFILE`` + provider profile already merged) and replaces only the
transformer key, retaining all other provider capability facts.

Used by: ``narrare_core.llm._providers.zai`` (and future OpenAI-compat factories).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_ai.profiles.openai import OpenAIJsonSchemaTransformer

if TYPE_CHECKING:
    from pydantic_ai._json_schema import JsonSchema
    from pydantic_ai.profiles import ModelProfile

__all__ = [
    "NarrareOpenAICompatJsonSchemaTransformer",
    "narrare_openai_compat_profile",
]


class NarrareOpenAICompatJsonSchemaTransformer(OpenAIJsonSchemaTransformer):
    """OpenAI strict-mode transforms + universal ``$defs``/``$ref`` inlining.

    Instance contract of the model layer: the profile stores the *class* and the
    framework instantiates ``transformer(schema, strict=...)`` per tool/output —
    one instance per walk, so the flipped flag needs no shared state.
    """

    def __init__(self, schema: JsonSchema, *, strict: bool | None = None) -> None:
        super().__init__(schema, strict=strict)
        self.prefer_inlined_defs = True


def narrare_openai_compat_profile(resolved: ModelProfile) -> ModelProfile:
    """Profile-layer callable for every OpenAI-compatible model factory.

    Passed as ``OpenAIChatModel(..., profile=narrare_openai_compat_profile)``: the
    callable form receives the fully resolved profile (``DEFAULT_PROFILE`` merged
    with the provider's ``model_profile(model_name)`` result) and swaps in the
    inlining transformer while retaining every other provider capability key.
    """
    return {**resolved, "json_schema_transformer": NarrareOpenAICompatJsonSchemaTransformer}
