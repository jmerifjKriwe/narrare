# Content Review CR-04 – Cross-Feature-Kohärenz

Audit date: 2026-06-12
Scope: cross-feature coherence of KB context formats, Storyboard/KB/Timeline consistency, prompt template/frontmatter/manifest contracts, feature contradictions, and ADR-026 prompt i18n policy.
Method: graph-first search for prompt routes, storyboard/timeline, KB context, and voice/profile paths; required Narrare context loaded; CR-00 through CR-03 reviewed; targeted reads of prompt registry/composer/manifest/checkers, writing context assembly, KB extraction/suggestion, storyboard/timeline, consistency, and i18n capability prompts. Validation commands run: `just check-architecture` and `just check-prompts`.

## Root Cause Summary

Narrare now has the core pieces for cross-feature coherence: RULE-22 precedence exists, prompt variables are registered, writing context is tiered, extracted KB entries carry provenance/review state, timeline events can reach the consistency prompt, and prompt structure checks pass. The remaining root cause is **contract granularity drift**: producers and consumers agree on many individual fields, but several cross-feature boundaries still lack one explicit integration contract that defines format, provenance, freshness, deletion/change behavior, and conflict surfacing.

**Architectural fit:** The sustainable solution is not a new ad-hoc formatter per feature. It is to formalize integration contracts at the feature boundary: KB context envelope/sections, Storyboard ↔ KB/Timeline deletion/change semantics, Prompt Surface manifest path/frontmatter validation, and typed conflict surfacing for high-impact contradictions.

**Alternatives considered:**

1. **Force one universal KB context string everywhere.** Rejected: writing, KB interview, graph relationships, and timeline checks have different token budgets and task needs.
2. **Leave formats feature-local because current prompts pass checks.** Rejected: this preserves invisible drift; `just check-architecture` currently passes even when the manifest validates the wrong chat template path.
3. **Keep feature-specific renderers but bind them to shared integration contracts.** Chosen: it preserves fit with `PromptComposer`, `PromptContext`, writing assemblers, and RULE-22.

---

## 1. KB-Context-Format-Standardisierung

### 1.1 Format-Analyse

**Format A – Generic `PromptContext.kb_context_entries` compact blocks:**

```markdown
### Character: Aria
Short accepted/candidate content block...
```

- **Erzeugt in:** `PromptContext._format_kb_entries()`.
- **Genutzt von:** generic PromptComposer paths that consume `{{kb_context_entries}}`.
- **Vorteile:** readable, compact, reusable.
- **Nachteile:** `KBContextEntry` has `source`, `evidence`, `confidence`, `review_status`, and `freshness`, but the formatter currently emits only type/name/content. Provenance is available in the model but lost in the prompt surface.

**Format B – Writing tiered KB fields:**

```markdown
### Character: Aria
Aria is the captain of the Night Watch.

### Location: Thornwall
Border fortress near the northern pass.
```

- **Erzeugt in:** `WritingContextAssembler.assemble()` and `format_entities()` / `format_entities_with_wiki()`.
- **Genutzt von:** writing prompts via `kb_characters`, `kb_locations`, `kb_factions`, `kb_systems`, `kb_timelines`, `kb_relationships`, `kb_suggested`, and `kb_pinned`.
- **Vorteile:** budget-tiered, supports pinned/referenced/connected/suggested separation, supports wiki compression, supports metadata counts for the Context Inspector.
- **Nachteile:** raw entity formatting drops provenance/confidence/review state; `kb_pinned` exists in `WritingContext` but is not a registered prompt variable and is not currently part of the audited templates; generated suggestions need consistent lower-priority wording (covered by CR-01/CR-03 tasks).

**Format C – Wiki-compressed entity context:**

```markdown
### Character: Aria
Aria leads the Night Watch and hides her royal ancestry.
Role: reluctant protector
Attributes: guarded, tactical, loyal
```

- **Erzeugt in:** `format_entities_with_wiki()`.
- **Genutzt von:** writing Tier 3 for referenced/connected entities.
- **Vorteile:** good long-project compression; fresh/stale counts are tracked.
- **Nachteile:** fallback raw content is silent in the prompt; stale/pending summaries are counted in metadata but not labelled in the context block.

**Format D – Proactive suggestions / `kb_suggested`:**

```markdown
### Character: Aria
Entity content selected by relevance ranking...
```

or KB Assist world context:

```markdown
- Aria (character): relevance 0.82
- Thornwall (location): relevance 0.74
```

- **Erzeugt in:** `ProactiveContextService.suggest()`, `KBSuggestService`, and `KBAssistService._build_deps()`.
- **Genutzt von:** writing `kb_suggested`, KB assist `world_context`, suggestion APIs.
- **Vorteile:** structured score/reason exists at API boundary (`mentioned_in_text` vs `semantically_similar`).
- **Nachteile:** score/reason often degrade into raw text before prompt use; “suggested/unaccepted” status depends on template wording, not on a common envelope.

**Format E – Graph relationship context:**

```markdown
Aria → [ally of] → Marcus
Aria → [member of] → Night Watch
Marcus → [rival of] → Elena
```

- **Erzeugt in:** `format_relationships()` via `fetch_formatted_relationships()`.
- **Genutzt von:** writing services and prompts through `kb_relationships`.
- **Vorteile:** deterministic and compact.
- **Nachteile:** loses edge provenance, direction semantics beyond display, confidence, and “why this edge matters for this scene”.

**Format F – Timeline / temporal context:**

```markdown
## Timeline Events
- [Day 5] "Aria arrives at Thornwall" — Aria; Thornwall
- [?] "Marcus disappears"
```

- **Erzeugt in:** `fetch_timeline_events()` and `_format_timeline_events()`.
- **Genutzt von:** consistency prompt as `timeline_position`.
- **Vorteile:** confirmed timeline events now reach consistency analysis, updating the old FIND-009 baseline.
- **Nachteile:** compact output omits `source`, `confidence`, `chapter_id`, `temporal_order`, causes/consequences, confirmation status, and stale KB-reference handling.

### 1.2 Empfehlung: Einheitlicher Standard

Keep feature-specific presentation, but define a shared **KB Context Envelope Contract** that every renderer must preserve:

1. `priority`: author instruction / project profile / current scene / curated KB / memory / generated suggestion.
2. `provenance`: manual, imported, auto-extraction, wiki-generated, graph-derived, timeline-derived.
3. `review_state`: canon/reviewed/draft/deprecated and approved/pending/rejected where applicable.
4. `freshness`: fresh/stale/pending for summaries and profiles.
5. `evidence`: reason included, relationship edge, source chapter/event, confidence if inferred.
6. `deletion/change behavior`: skip, tombstone, stale marker, or block depending on integration contract.

Writing can still render compact tiered blocks, consistency can render timeline lines, and graph context can stay arrow-formatted — but each must preserve or explicitly omit envelope fields by contract.

**Bewertung KB-Format-Konsistenz:** ⭐⭐⭐
**Befunde:** format infrastructure is strong, but provenance/review/freshness is inconsistently carried from model to prompt text. This refreshes the old `CR-AUFG-04-01` instead of creating a duplicate.

---

## 2. Storyboard ↔ Knowledge Base – Konsistenzprüfung

**Analyse:**

- Storyboard currently reads chapters, outlines, and novel structure; it does not read KB entities directly.
- Chapter/frontmatter ↔ KB coherence exists in the writing context assembler: references in frontmatter are extracted, deprecated entries are excluded, and orphan references produce warnings.
- Timeline events persist character/location references as hybrid JSON `{id, name}` data and can be fetched into consistency analysis when confirmed.
- Consistency checking now consumes KB summaries and timeline events, so the previous “timeline not consumed at all” finding is stale. The remaining gap is richer graph/timeline provenance and explicit change/deletion semantics.
- No evidence was found of a Storyboard ↔ KB integration contract that defines what happens when a referenced KB character/location is renamed, deprecated, deleted, or contradicted by planned beats.

**Test-Szenarien:**

| Szenario | Datenquelle 1 | Datenquelle 2 | Möglicher Konflikt | Handling |
|---|---|---|---|---|
| Charakter stirbt in Kapitel 5 / Timeline, KB keeps character as active | Timeline/storyboard/chapter | Curated KB | The generator may treat the character as available after death. | Partially handled by consistency timeline context; should surface as a typed conflict, not silently choose. |
| Ort has description in KB but outline notes/planned beat describes incompatible geography | KB | Storyboard outline | Scene generation may use the wrong location constraints. | No direct Storyboard↔KB check found; needs integration contract and consistency issue. |
| Chapter frontmatter references a deleted/deprecated KB entity | Chapter frontmatter | KB | Missing or stale entity enters writing context. | Deprecated entries become orphan warnings in `WritingContextAssembler`; deletion/tombstone UX contract still needed. |
| Timeline event references KB entity name/id after KB rename/delete | TimelineEvent JSON refs | KB entries | Stored name becomes stale or id points nowhere. | No FK for JSON refs; `fetch_timeline_events()` emits stored names only. Needs stale/tombstone behavior. |
| Story structure remap changes stage assignment after chapters already have timeline positions | Storyboard | Chapter timeline/timeline events | Structural stage and diegetic chronology diverge. | Remap updates outlines; no timeline reconciliation contract found. |

**Bewertung:** ⭐⭐⭐
**Befunde:** Storyboard/content structure is coherent inside its own domain, and writing now detects orphan KB refs. Cross-feature coherence with KB and Timeline still depends on downstream consistency checks rather than an explicit integration contract.

---

## 3. Templates ↔ Frontmatter – Schema-Konsistenz

Validation baseline:

- `just check-prompts` passed: `46/46 system prompts valid`; `18` non-system snippets skipped (tones/name-styles).
- `just check-architecture` passed, but approved exceptions aside, it did not catch the chat manifest/template-path drift described below.
- All audited system prompt files use required frontmatter fields `prompt_type`, `prompt_language`, `prompt_version`.
- Tone snippets intentionally use `tone_id`/`tone_version`; name-style snippets intentionally use `style_id`, `style_name`, `language`, `version`. These are not full prompt templates.

### Schema-Gap-Analyse

| Feld / Contract | In Template | In Frontmatter/Manifest | Im Code erwartet | Konsistent? |
|---|---|---|---|---|
| `prompt_type` | Yes for system prompts | Required by standards/checker | Parsed as metadata; prompt checker validates | ✅ |
| `prompt_language` | Yes for system prompts | Required by standards/checker | Registry uses path language, metadata retained | ✅ |
| `prompt_version` | Yes for system prompts | Required by standards/checker | Prompt management reads for override drift | ✅ |
| Tone snippet schema | In `writing/tones/*.md` | `tone_id`, `tone_version` | Tone snippets are content snippets, not routeable prompts | ✅ |
| Name-style schema | In `generation/name-styles/*/*.md` | `style_id`, `style_name`, `language`, `version` | `resolve_name_style()` strips frontmatter and returns body | ✅ |
| CHAT route template | Runtime route is category `chat`, mode `""` | Manifest template points to `writing/en/chat/system.md` | `PromptRegistry` resolves `chat/en/system.md`; PromptManagement assumes 3-part prompt IDs and mishandles root-mode `chat/en/system.md` | ❌ FIND-010 |
| Planning timeline template | `planning/en/timeline/system.md` exists | Manifest has only `PLAN` default `outline` route | `TimelineAnalysisService` builds an inline f-string runtime prompt instead of using the template | ❌ FIND-011 |
| `kb_pinned` writing context | Produced by `WritingContext` | Not registered in `variable_registry.py` and not in manifest | Not currently consumed by audited templates | ⚠️ producer-only field; document or register before template use |
| Generated suggestion labels | Manifest requires labels for `kb_suggested` in writing routes | Checker validates declared manifest template path | Runtime chat path is not the manifest path, so the root chat prompt is not covered by generated-label checks | ⚠️ part of FIND-010 |

**Bewertung:** ⭐⭐⭐
**Befunde:** template frontmatter quality is good and prompt checks pass. The main schema problem is not missing frontmatter; it is route/manifest/management drift for root-mode chat plus an unused planning timeline template while timeline analysis constructs its own prompt.

---

## 4. Funktionen, die sich gegenseitig widersprechen

| Feature A | Feature B | Potenzieller Widerspruch | Schwere | Empfehlung |
|---|---|---|---|---|
| Manual project writing profile / author instruction | mem0 learned preferences | Learned style can contradict explicit current/project settings. | 🟡 | RULE-22 precedence already says explicit/current wins; ensure all high-impact templates state or inherit this and CR-03 enrichment merges obey it. |
| KB auto-extraction | Manual/curated KB entries | Auto-extracted entries are created as `source="auto_extraction"`, `review_status="pending"`; updates can propose metadata changes that diverge from curated body/facts. | 🟡 | Keep review gate, preserve source/confidence in prompt context, and surface conflicts instead of auto-overwriting curated facts. |
| Voice profile extraction/checkers | Writing continue/rewrite | Writing extracts voice profiles from KB metadata and warns on staleness; other voice analysis paths may not feed the same profile contract. | 🟡 | Use a central `VoiceProfileProvider/ProfileAssembler` contract for both generation and analysis, with freshness/confidence surfaced. |
| Storyboard stages | Chapter timeline positions / timeline events | Structural stage sync is position/summary based; diegetic time can contradict `timeline_position` or confirmed events. | 🟡 | Define Storyboard ↔ Timeline contract for remap/change behavior; include timeline conflict warnings in remap previews. |
| Root chat prompt | Prompt management / manifest checker | Runtime uses `chat/en/system.md`; manifest/checker validates `writing/en/chat/system.md`; prompt management’s 3-segment prompt IDs cannot retrieve `chat/en/system.md` correctly. | 🔴 | Fix prompt-surface route contract and management representation. See FIND-010. |
| Timeline analysis service | Planning timeline template | A governed planning prompt exists, but service builds the actual task prompt inline; template/frontmatter can drift unused. | 🔴 | Route timeline analysis through PromptComposer or remove/mark template non-routeable. See FIND-011. |

**Bewertung:** ⭐⭐⭐
**Befunde:** RULE-22 precedence now gives the right policy, but not every feature boundary has an integration contract that turns the policy into concrete change/deletion behavior and typed conflict output.

---

## 5. i18n-Konsistenz in Prompts

Current ADR-026/RULE-22 strategy:

- Bundled feature prompts are EN-only by default.
- Output/writing language must be controlled through variables/context/deps, primarily `{{writing_language}}`.
- Declared localized families (`meta`, `universal`) require en/de/fr parity.
- UI i18n remains separate from prompt-template localization.

**Evidence:**

- Meta prompts exist in en/de/fr at version `3.0.0`.
- Universal prompts exist in en/de/fr at version `1.0.0`.
- The i18n checker explicitly treats feature prompts as EN-only by default and limits prompt parity checks to localized-required categories.
- Feature templates generally use `{{writing_language}}`, but some existing templates and manifest optional-variable lists still retain deprecated `language` for backward compatibility. This is already covered by CR-01 task `CR-AUFG-01-04`.
- Minor localized tone drift exists in universal DE/FR (`folge`/`folgen Sie`, `suis`/`suivez`) but the semantic rules are equivalent.

**Bewertung i18n-Qualität in Prompts:** ⭐⭐⭐⭐
**Befunde:** Locale strategy is coherent and current. Do not treat missing DE/FR feature prompt copies as errors. Remaining work is canonical output-language cleanup and minor localized-family tone consistency, not a localization architecture redesign.

---

## Gesamtbewertung Cross-Feature-Kohärenz

**Bewertung:** ⭐⭐⭐
**Vorherige Bewertung:** ⭐⭐⭐ | **Trend:** ↗️ Better infrastructure, still medium coherence risk
**Zusammenfassung:** Narrare’s cross-feature coherence is materially stronger than the stale CR-04 baseline: RULE-22 precedence exists, variable taxonomy exists, writing context carries richer KB/profile/timeline fields, and consistency checks now receive confirmed timeline events. The remaining risks are boundary-contract risks: KB context renderers drop provenance, Storyboard/KB/Timeline change/deletion semantics are not explicit, the chat prompt surface has route/manifest/management drift, and timeline analysis bypasses its own governed template. These should be fixed through integration contracts and manifest/checker strengthening, not per-feature prompt workarounds.

---

## Aufgaben

Prior CR-04 status:

- `CR-AUFG-04-02` remains closed: cross-feature precedence is now defined in RULE-22 and prompt standards. Do not create a standalone ADR unless the rule changes.
- Previous generic `CR-AUFG-04-03` output-language work is covered more precisely by `CR-AUFG-01-04`; do not duplicate it here.

Current CR-04 task list:

- **CR-AUFG-04-01:** Define/ratify the KB Context Envelope Contract for compact KB entries, writing tiers, wiki summaries, proactive suggestions, graph relationships, and timeline context. The contract must preserve or explicitly omit priority/provenance/review/freshness/evidence fields.
- **CR-AUFG-04-04:** Fix CHAT prompt-surface drift: align `scripts/architecture/prompt-surface-manifest.yaml`, runtime route `LLMIntent.CHAT`, bundled template location, and PromptManagementService prompt IDs so the template users edit is the template runtime uses.
- **CR-AUFG-04-05:** Strengthen the Prompt Surface checker so a routeable template path must match route category/mode and template frontmatter (`prompt_type`, language, version), not merely point to an existing file.
- **CR-AUFG-04-06:** Add a Storyboard ↔ KB ↔ Timeline integration contract covering rename, deletion, deprecation, remap, stale JSON refs, tombstones, and when contradictions become typed consistency issues.
- **CR-AUFG-04-07:** Update FIND-009 implementation scope: timeline events now reach consistency; remaining work is graph-edge/timeline provenance, stale/deleted reference handling, and richer temporal reasoning.
- **CR-AUFG-04-08:** Route `TimelineAnalysisService.generate_timeline()` through `PromptComposer`/the planning timeline template, or explicitly mark the template non-routeable and move task instructions to an ADR-026-compliant agent instruction path.
- **CR-AUFG-04-09:** Unify voice profile context for generation and checking through the existing profile contracts, including freshness/confidence labels in prompt context where voice affects output.

## FINDs

- **Updated:** `_audit/results/content-review/findings/FIND-009-timeline-consistency-gap.md` — refreshed from “timeline not consumed” to “timeline consumed, graph/provenance/deletion semantics still incomplete”.
- **New:** `_audit/results/content-review/findings/FIND-010-chat-prompt-surface-drift.md` — runtime chat prompt, manifest template, and prompt-management IDs disagree.
- **New:** `_audit/results/content-review/findings/FIND-011-timeline-analysis-bypasses-template.md` — timeline analysis bypasses the governed planning timeline template.

## Next Prompt Recommendation

Proceed with **CR-05 – Initial Findings / Finding Consolidation** next. Use CR-04 to reconcile stale/resolved finding files (`FIND-003`, `FIND-004`, `FIND-007`, old FIND-009 wording) and ensure new FIND-010/FIND-011 are tracked without duplicating CR-01/CR-02/CR-03 tasks.
