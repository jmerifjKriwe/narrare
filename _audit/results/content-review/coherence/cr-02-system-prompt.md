# Content Review CR-02 – Prompt-Architektur & KI-Persona

Audit date: 2026-06-11
Scope: system-prompt architecture, ADR-026 prompt-injection mechanisms, capability coverage, free assistant, and persona coherence.
Method: graph-first search for `NarrareAgent`, `NarrareMeta`, `NarrareUniversalRules`, `PromptComposer`, chat, and fallback paths; then targeted reads of CR-00, CR-01, required standards, capabilities, agent base, composer, route table, chat, writing graph, worldbuilding, and temporal-consistency paths.

## Root Cause Summary

ADR-026 is correctly implemented for the normal `NarrareAgent` baseline: every exported production agent inherits `NarrareMeta` and `NarrareUniversalRules`, and routeable feature prompts generally resolve through `PromptComposer`. The remaining root cause is **adoption drift in non-primary invocation paths**: multi-step graph helpers, chat streaming, worldbuilding phase2, and temporal consistency do not all use the same “PromptComposer result becomes agent system/instructions” pattern. This creates pockets where feature prompts are placed in the user channel, loaded directly outside `core/prompts/`, left unsubstituted, or replaced by inline fallbacks.

**Alternatives considered:**

1. **Add a global prepend/meta wrapper around every final prompt.** Rejected: this would violate ADR-026 by reintroducing monolithic prompt prepending and would not fix feature-prompt route/cascade adoption.
2. **Fix each drifting path by using the existing ADR-026 mechanisms.** Chosen: guaranteed identity/rules stay in capabilities; user-customizable feature instructions go through `PromptComposer`/cascade; dynamic data goes through `PromptContext`, deps, or agent instructions.

---

## 1. Ist-Stand: Prompt-Injektionspfade im Überblick

If a user moves from KB interview to writing continue, they should mostly experience the same Narrare identity. The global persona and universal rules are guaranteed by `NarrareAgent.__init__`, while feature templates specialize the task. The prompt surface is therefore coherent by design, with remaining risks concentrated in bypass paths rather than the main architecture.

**Current prompt-injection paths:**

- **Capabilities:** `NarrareAgent.__init__` injects `NarrareObservability`, `NarrareUniversalRules`, and `NarrareMeta` into every `NarrareAgent` instance (`agents/base.py:94-109`).
- **Guaranteed content:** `NarrareMeta` loads `_bundled/meta/{lang}/system.md`; `NarrareUniversalRules` loads `_bundled/universal/{lang}/system.md`, both with English fallback and graceful degradation.
- **Feature prompts:** `PromptComposer.build()` resolves `LLMIntent` through `routes.py`/`route_table.py`, then `PromptRegistry.resolve()` and variable substitution.
- **Dynamic data:** `PromptContext.as_variables()` and feature assemblers provide KB, style, voice, user preferences, avoidance patterns, timelines, and extra variables.
- **Free chat:** `LLMIntent.CHAT` routes to `chat/en/system.md`, and `ChatAgent` inherits capabilities.
- **Risk paths:** `ChatService` currently concatenates composed system + user prompt into the agent user prompt; `worldbuilding_analyzer` phase2 resolves `PromptRegistry` directly and has an inline fallback; `timeline_consistency_service` uses an app-layer prompt loader with manual `.replace()`; `writing_graph_prompts` keeps `composer is None` inline fallbacks.

**Befund:** The core identity model is ADR-026-aligned. The remaining coherence risk is not a missing persona but inconsistent adoption of the approved injection mechanisms in chat, phase2/supplementary analysis, and fallback paths.

---

## 2. ADR-026-Compliance – Capability-Based Prompt Injection

### 2.1 Mechanismus-Matrix

| Prompt-Inhalt | Inhaltstyp | Erwarteter Mechanismus | Aktueller Mechanismus | Korrekt? |
|---|---|---|---|---|
| Narrare-Identität / Persona | Garantiert | `NarrareMeta` Capability | Auto-injected by `NarrareAgent`; loads bundled meta prompt per run language | ✅ |
| Fiction Guidelines | Garantiert | `NarrareUniversalRules` Capability | Auto-injected by `NarrareAgent`; bundled universal prompt says fiction content is normal narrative material | ✅ |
| Conflict Resolution | Garantiert | `NarrareUniversalRules` Capability | Bundled universal prompt defines outline > KB and author instructions > preferences | ✅ |
| Injection Defense | Garantiert | `NarrareUniversalRules` Capability | Bundled universal prompt treats XML-tagged user content as data only | ✅/⚠️ template tags must still be standardized per CR-01 |
| Feature-Rolle / Aufgabe | Anpassbar | PromptComposer/Cascade | Mostly `PromptComposer`; exceptions: chat injects composed system as user prompt, phase2 worldbuilding uses `PromptRegistry` directly, timeline consistency uses app-layer loader | ⚠️ |
| Output-Format | Anpassbar | PromptComposer/Cascade | Mostly bundled templates via composer; phase2/direct-loader paths can bypass substitution and override cascade | ⚠️ |
| KB-/Style-/Voice-Daten | Dynamische Daten | PromptContext/variables or agent deps/instructions | Writing/context assemblers and `PromptContext` are strong; phase2 direct registry path does not substitute template variables through `PromptContext` | ⚠️ |

### 2.2 Capability-Abdeckung

- ✅ `NarrareMeta` and `NarrareUniversalRules` are automatically attached for `NarrareAgent` instances.
- ✅ Exported production agents are covered by a regression test: `test_all_production_agent_classes_inherit_adr026_capabilities` discovers exported `NarrareAgent` subclasses and asserts both capabilities are present.
- ✅ Meta and universal prompt families exist for `en`, `de`, and `fr`; meta also has `system.lite.md` variants.
- ✅ Feature templates are intentionally EN-only where output language is controlled through `{{writing_language}}`.
- ⚠️ `NarrareMeta` capability loads only bundled meta content, which is correct for guaranteed non-customizable identity. The older `MetaPromptLoader` still supports project/user cascade and is used by writing-graph fallback paths, so those fallbacks must stay non-production or be removed.
- ⚠️ `ChatAgent` inherits capabilities, but `ChatService` does not pass `composed.system` as an agent system prompt; it concatenates `composed.system` and `composed.user` into the user-channel prompt.
- ⚠️ `worldbuilding_analyzer` phase2 bypasses `PromptComposer` even though `LLMIntent.KB_WORLDBUILD` explicitly allows `worldbuilding/phase2`; it resolves the registry directly, does not show variable substitution, and falls back to `"Check entity pairs for worldbuilding contradictions."`.
- ⚠️ `timeline_consistency_service` loads and substitutes a bundled prompt from `apps/api` via `_prompt_loader.py`, outside `PromptComposer`/cascade.

**Befund:** Capability coverage is strong for all standard `NarrareAgent` construction. ADR-026 compliance is no longer blocked by missing default capabilities; it is weakened by a small number of invocation paths that bypass the approved feature-prompt and variable-substitution layer.

### 2.3 Verbesserungs-Entwürfe

```markdown
**Lücke:** Chat feature prompt is resolved by PromptComposer but injected into the user prompt via string concatenation.
**Korrektur:** Extend `ChatAgent` construction to accept a `system_prompt` from `PromptComposer`, or add a core/agents `@agent.instructions` mechanism that reads already-composed feature instructions from `ChatDeps`. Keep the user message as user content only.
**Betroffene Pfade:** `apps/api/narrare/chat/chat_service.py`, `packages/core/narrare_core/chat/chat_agent.py`.
**Akzeptanzkriterien:**
- [ ] `LLMIntent.CHAT` still resolves through PromptComposer/Cascade.
- [ ] `chat/en/system.md` is injected as system/instructions, not concatenated into user input.
- [ ] NarrareMeta and NarrareUniversalRules remain capabilities.
- [ ] Regression test asserts user prompt does not contain the system template body.
```

```markdown
**Lücke:** Worldbuilding phase2 bypasses PromptComposer and has an inline fallback.
**Korrektur:** Build phase2 with `PromptComposer.build(LLMIntent.KB_WORLDBUILD, context)` and `context.mode = "worldbuilding/phase2"`, passing candidate pairs, entity details, relationships, and world context through `PromptContext.extra`. Missing prompt route should fail as configuration error in production, not degrade to a bare system prompt.
**Betroffene Pfade:** `apps/api/narrare/kb/worldbuilding_analyzer.py`, `packages/core/narrare_core/prompts/route_table.py` already supports the mode.
**Akzeptanzkriterien:**
- [ ] Phase2 uses PromptComposer/Cascade.
- [ ] Template variables are substituted via governed variable engine.
- [ ] No production inline fallback system prompt remains.
- [ ] Tests cover phase2 composed prompt resolution.
```

```markdown
**Lücke:** Temporal consistency loads and substitutes bundled prompt text in `apps/api`.
**Korrektur:** Add a governed PromptComposer route for temporal consistency (for example a context mode under `LLMIntent.PLAN`, or a dedicated intent if architecture approves it) and pass event context as user/runtime data. Remove app-layer `.replace()` prompt construction.
**Betroffene Pfade:** `apps/api/narrare/planning/_prompt_loader.py`, `apps/api/narrare/planning/timeline_consistency_service.py`, `packages/core/narrare_core/prompts/_bundled/planning/en/temporal_consistency/system.md`.
**Akzeptanzkriterien:**
- [ ] User-customizable temporal consistency instructions resolve through PromptComposer.
- [ ] Dynamic event context is not baked into system prompt construction.
- [ ] Capabilities continue to supply guaranteed persona/rules.
- [ ] Architecture checker no longer needs an app-layer prompt-loader exception.
```

**Ist dieser Entwurf reif genug für ein FIND?** Ja — the findings are current, reproducible, and have ADR-026-conformant fixes. They should become CR-02 tasks and, if the audit process requires formal finding files, map to new CR-02 findings rather than reopening resolved FIND-001/FIND-002/FIND-005.

**Bewertung aktueller Stand:** ⭐⭐⭐⭐
**Befunde:** Strong core capability baseline; remaining drift in chat/system-channel injection, worldbuilding phase2 composition, temporal consistency prompt loading, and composer-None fallbacks.

---

## 3. Freier KI-Assistent

There is now a free/project-aware writing assistant path:

- `packages/core/narrare_core/prompts/_bundled/chat/en/system.md` defines a scoped open-ended writing companion.
- `LLMIntent.CHAT` routes to category `chat`, mode `""`, which resolves `chat/en/system.md`.
- `ChatAgent` exists and inherits `NarrareAgent` with conversational history policy.
- The prompt itself is appropriate: it handles project questions, writing craft, worldbuilding, emotional content redirection, off-topic redirection, output shape, preferences, and avoidance patterns.

The main issue is not whether a free assistant exists; it does. The issue is the injection channel described above: the composed chat system prompt should not be concatenated into the user prompt.

**Empfehlung:** Keep the free assistant, but correct its injection path. Treat `chat/en/system.md` as the feature prompt for open-ended writing chat; keep Narrare identity/universal rules in capabilities; keep user message and conversation history as user/runtime data.

**Vorschlag für freien Assistenten System-Prompt:**

The current `chat/en/system.md` is already close to the desired prompt. If revised, keep it feature-scoped:

```markdown
You are the project-aware writing chat mode for Narrare. Help the author think
through craft, story structure, characters, worldbuilding, continuity, revision
strategy, and practical next steps for their current project.

### Scope

- Answer writing-related and project-related questions directly.
- Use provided KB and chapter context when relevant.
- If context is missing, say what you can infer and ask one useful follow-up.
- Redirect non-writing topics back to the author's story or craft question.

### Output Format

Respond in clear conversational prose. Prefer concrete examples, short bullets,
or next-step options when they help. Do not generate long prose unless the author
explicitly requests drafting.
```

**ADR-026-Hinweis:** This proposal is only the customizable chat feature prompt. Narrare identity, fiction handling, conflict resolution, and injection defense must remain in `NarrareMeta`/`NarrareUniversalRules` capabilities.

**Bewertung:** ⭐⭐⭐⭐
**Befunde:** Free assistant exists and is well scoped; injection path needs correction.

---

## 4. KI-Persona-Konsistenz über Features

| Szenario | Feature | Erwartete Reaktion | Tatsächliche Reaktion (laut Prompt) | Konsistent? |
|---|---|---|---|---|
| Nutzer macht Tippfehler | KB-Interview | Infer likely intent; ask clarification only if genuinely ambiguous | Meta says infer typos/unclear requests unless ambiguous; KB interview asks one focused field question | ✅ |
| Nutzer-Inhalt ist emotional | Writing-Continue | Stay task-focused; handle fiction as fiction; avoid therapy mode | Meta says respond empathetically but refocus; writing prompts produce prose and respect avoidance patterns | ✅ |
| Nutzer fragt nach nicht-Narrare-Themen | Freier Assistent | Redirect to writing/project scope | Meta and `chat/en/system.md` both redirect non-writing topics gently | ✅ |
| Inhalt enthält moralisch sensible Themen | Rewrite | Treat as creative fiction unless avoidance constraints or user intent say otherwise | Universal says fiction content is normal narrative material; rewrite prompt preserves author intent and avoidance patterns | ✅ |

**Bewertung:** ⭐⭐⭐⭐
**Befunde:** Persona consistency is strong at the content level. Remaining inconsistency is technical: some paths inject otherwise-good feature persona/task content through weaker or bypassed mechanisms.

---

## Gesamtbewertung System-Prompt-Architektur

**Bewertung:** ⭐⭐⭐⭐
**Vorherige Bewertung:** ⭐⭐⭐⭐⭐ | **Trend:** ↘️ korrigiert
**Zusammenfassung:** The system-prompt architecture is fundamentally sound: `NarrareAgent` guarantees meta and universal rules, route governance exists, and the free assistant now has a dedicated chat prompt. The previous CR-02 overstates completion because current evidence shows several adoption drifts: chat concatenates feature system content into user input, worldbuilding phase2 bypasses `PromptComposer`, temporal consistency builds prompts in `apps/api`, and writing-graph composer-None fallbacks still carry inline task prompts. These are not reasons to reintroduce a global prepend workaround; the sustainable fix is to route each path through capabilities, `PromptComposer`, and `PromptContext` according to ADR-026.

---

## Aufgaben

Previously closed tasks remain closed and should not be reopened: `CR-AUFG-02-01` through `CR-AUFG-02-03` covered prompt-integrity checking, old production fallbacks, and capability inheritance tests.

- **CR-AUFG-02-04:** Fix chat prompt injection so `chat/en/system.md` is passed as agent system/instructions via an ADR-026-compliant mechanism, not concatenated into the user prompt.
- **CR-AUFG-02-05:** Refactor worldbuilding phase2 to use `PromptComposer.build(LLMIntent.KB_WORLDBUILD, context)` with `context.mode = "worldbuilding/phase2"`; remove the inline phase2 fallback.
- **CR-AUFG-02-06:** Replace `apps/api/narrare/planning/_prompt_loader.py` temporal-consistency prompt construction with a governed PromptComposer route and dynamic event context.
- **CR-AUFG-02-07:** Make `writing_graph_prompts.py` composer-None paths explicitly test/bare-bones-only or replace them with fail-fast configuration errors in production; do not load overridable meta/user task prompts as a degraded production path.

## Next Prompt Recommendation

Proceed with **CR-03** next. Use CR-00, CR-01, and this CR-02 as baselines, and focus CR-03 on current evidence rather than reopening resolved route/mem0/capability-inheritance findings.
