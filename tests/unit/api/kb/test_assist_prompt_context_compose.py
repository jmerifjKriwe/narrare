"""Real-composer regression tests for KB assist prompt-context feeds (F9-2).

Wave-fix slice for the e2e FINDING (tests/e2e/test_kb_ai.py): every KB
assist interview/suggest/enhance call 400s with MISSING_VARIABLE — the
bundled ``kb/en/{interview,suggest,enhance}`` templates declare
``{{template_structure}}`` (+ ``{{world_context}}`` everywhere, plus
``{{target_field}}`` / ``{{target_field_description}}`` for suggest),
while ``build_prompt_context`` fed only ``entity_type`` +
``existing_answers``. The kb routes declare NO ``optional_variables``
(route_table.py), so ``prepare_variables_for_template`` raises
``PromptVariableError`` (code MISSING_VARIABLE → 400) on the first unfed
placeholder — on BOTH the pipeline compose and the fallback
``composer.build``. ``build_assist_deps`` already computed
``template_structure``/``world_context`` for the agent deps; the
asymmetry between the two assemblies was the bug.

Contract pinned here: chaining the REAL builders the service uses
(``build_assist_deps`` → ``build_prompt_context``) into the REAL
``PromptComposer(PromptRegistry())`` must compose for all three assist
intents with every template slot fed from the deps — the exact compose
stage that raised MISSING_VARIABLE pre-fix (mocked-composer service
tests stayed green through the outage).
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from narrare.kb._assist_context import build_assist_deps, build_prompt_context
from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts import PromptComposer, PromptRegistry
from narrare_core.prompts.context import PromptContext
from narrare_core.shared.errors import PromptVariableError

from ._assist_fakes import FakeKBContextProvider

_ENTITY_TYPE = "character"
#: Session-realistic answered field — the session store only ever feeds
#: values for template fields (see ``KBSessionService._extract_existing_fields``).
_EXISTING = {"role": "Protagonist"}

#: intent → governed template mode (route_table.py, kb category) — the
#: three assist intents share the ``build_prompt_context`` builder.
_ASSIST_INTENTS: list[LLMIntent] = [
    LLMIntent.KB_INTERVIEW,
    LLMIntent.KB_SUGGEST,
    LLMIntent.KB_ENHANCE,
]


@pytest.fixture(scope="module")
def composer() -> PromptComposer:
    """Real composer over the real bundled-prompt registry (no mocks)."""
    return PromptComposer(PromptRegistry())


@pytest.fixture
def provider() -> FakeKBContextProvider:
    """Empty-KB provider — the RULE-11 degradation path the service runs on."""
    return FakeKBContextProvider(world_context="")


async def _build_deps(provider: FakeKBContextProvider):
    """Assemble the agent deps exactly as ``KBAssistService`` does."""
    return await build_assist_deps(provider, uuid4(), _ENTITY_TYPE, _EXISTING)


@pytest.mark.asyncio
@pytest.mark.parametrize("intent", _ASSIST_INTENTS)
async def test_assist_prompt_context_composes_through_real_composer(
    intent: LLMIntent,
    composer: PromptComposer,
    provider: FakeKBContextProvider,
) -> None:
    """Every assist intent composes when the context is built from deps.

    Pre-fix this raised ``PromptVariableError`` MISSING_VARIABLE
    ('template_structure' in kb/en/<mode>) — the production 400.
    """
    deps = await _build_deps(provider)

    # Guard: the character schema registry actually carries fields, so
    # the feed assertions below are not vacuous.
    assert deps.template_structure
    field_label = next(iter(deps.template_structure.values()))

    ctx = build_prompt_context(intent, deps)
    composed = await composer.build(intent, ctx)

    assert composed.system.strip(), "Assist compose produced an empty system prompt."
    # No template placeholder may survive unfed.
    assert "{{" not in composed.system, (
        f"Unfed placeholder in kb assist system prompt: "
        f"{[seg for seg in composed.system.split() if seg.startswith('{{')]}",
    )
    # existing_answers feed actually rendered (user_provided_data slot).
    assert "Protagonist" in composed.system
    # template_structure feed actually rendered (field labels from the
    # character schema registry, rendered from deps.template_structure).
    assert field_label in composed.system


@pytest.mark.asyncio
async def test_suggest_prompt_context_feeds_target_field(
    composer: PromptComposer,
    provider: FakeKBContextProvider,
) -> None:
    """The suggest template's target-field slots are fed, not left blank.

    ``kb/en/suggest/system.md`` is the only assist template declaring
    ``{{target_field}}`` / ``{{target_field_description}}`` — fed from
    the requested field key + its template label.
    """
    deps = await _build_deps(provider)
    assert deps.template_structure
    field_key, field_label = next(iter(deps.template_structure.items()))

    ctx = build_prompt_context(LLMIntent.KB_SUGGEST, deps, target_field=field_key)
    composed = await composer.build(LLMIntent.KB_SUGGEST, ctx)

    assert "{{" not in composed.system
    assert field_key in composed.system  # target field key rendered
    assert field_label in composed.system  # target field description (label) rendered


@pytest.mark.asyncio
async def test_bare_context_without_deps_feeds_still_fails_compose(
    composer: PromptComposer,
) -> None:
    """Mechanism pin: the pre-F9-2 context shape must keep failing loudly.

    A context mirroring the old builder output (entity_type +
    existing_answers only) still raises MISSING_VARIABLE with
    ``template_structure`` as the first unfed placeholder — this pins the
    variable engine's strict preflight that surfaced the 400s, so a
    future regression cannot silently degrade to an unfed prompt.
    """
    bare = PromptContext(
        language="en",
        mode="interview",
        extra={
            "entity_type": _ENTITY_TYPE,
            "existing_answers": str(_EXISTING),
        },
    )
    with pytest.raises(PromptVariableError) as excinfo:
        await composer.build(LLMIntent.KB_INTERVIEW, bare)
    assert excinfo.value.code == "MISSING_VARIABLE"
    assert excinfo.value.variable == "template_structure"
