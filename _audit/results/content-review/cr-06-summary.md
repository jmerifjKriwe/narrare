# Content Review CR-06 – Gesamtbewertung & Roadmap

Audit date: 2026-06-12
Scope: final summary after updated CR-00, CR-01, CR-02, CR-03, CR-04, CR-05, CR-07, and CR-08.
Method: graph-first session context, mandatory Narrare context loaded, then existing review outputs and active finding files used as the primary evidence base.

## 1. Bewertungs-Übersicht

| Bereich | Review | Bewertung | Kritischster aktueller Befund |
|---|---|---|---|
| Prompt-Qualität | CR-01 | ⭐⭐⭐⭐ | Template-level consistency: user-content wrapping, generated-candidate precedence, canonical `writing_language`, evidence/confidence gates. |
| System-Prompt / KI-Persona | CR-02 | ⭐⭐⭐⭐ | Strong ADR-026 capability baseline; remaining drift in chat injection, worldbuilding phase2, temporal-consistency loader, and writing-graph fallback paths. |
| Feature-Adoption (mem0, runtime evidence, budgets) | CR-03 | ⭐⭐⭐ | Static/adoption infrastructure is strong, but runtime evidence can overstate production behavior; output limits are not enforced at model calls (FIND-001). |
| Cross-Feature-Kohärenz | CR-04 | ⭐⭐⭐ | Boundary-contract drift: KB/timeline/graph provenance, prompt-surface manifest drift, timeline template bypass. |
| Initiale Befunde / Konsolidierung | CR-05 | ⭐⭐⭐⭐ | Active formal findings consolidated; legacy resolved findings no longer listed as open. FIND-012 was added later by CR-08 and is included here. |
| UI/UX | CR-07 | ⭐⭐⭐⭐☆ | ADR-043 moved AI UX from systemic inconsistency to mostly shared primitives; remaining gaps are KB Field Suggest, KB Improve, Timeline Extraction, Ghost Text, and keyboard polish. |
| Hardcodierte Werte & Konfigurierbarkeit | CR-08 | ⭐⭐⭐ | Configuration vocabulary exists, but some controls do not affect runtime: output limits (FIND-001) and context tier percentages (FIND-012). |
| **Gesamt (inhaltlich)** | — | **⭐⭐⭐⭐** | Narrare has strong prompt, persona, UX, and settings infrastructure. The main risk is no longer missing architecture, but runtime binding: settings/evidence/templates must affect the same invocation users experience. |

---

## 2. Stärken (inhaltlich)

1. **ADR-026 identity and safety baseline is strong.** CR-00/CR-02 confirm every normal `NarrareAgent` path receives `NarrareMeta` and `NarrareUniversalRules`; meta/universal prompts are localized, while feature prompts remain correctly customizable through `PromptComposer`.
2. **Prompt quality improved materially.** CR-01 finds KB, writing, rewrite, inline-suggest, and analysis prompts generally have clear roles, output formats, Do-NOT rules, context sections, and XML separation for most user-authored manuscript/input content.
3. **Context infrastructure is mature.** CR-00/CR-03/CR-04 show writing context has tiered KB/recent/pinned/suggested sections, ProjectWritingProfile fields, relationship context, wiki compression, mem0 preference paths, and timeline events now reaching consistency prompts.
4. **AI UX has a shared foundation.** CR-07 confirms `useAIOperation`, structured SSE/REST error mapping, connection-loss handling, cancel support, and `aiActions` i18n are adopted by 11 of 15 audited AI flows; the old CR-07 systemic inconsistency is obsolete.
5. **Configuration and governance vocabulary exists.** CR-03/CR-08 show token profiles, model routing, token-limit services, adoption registry/evidence, prompt-surface manifest, and hardcoded-value checks are in place. The remaining work is wiring and enforcement, not inventing these concepts.

---

## 3. Kritische Lücken

Prioritized by user/content impact and active finding status:

1. **FIND-001 — Output token limits are configured/evidenced but not enforced.** Users and audits can believe output limits apply while `ModelRegistry`/agent calls may not honor them. This affects every long-form AI feature and undermines adoption evidence.
2. **FIND-012 — Context tier sliders are exposed but not applied.** Authors can adjust immediate/recent/KB/pinned context percentages, but production writing context still uses default tier allocations. This is a direct false-control issue.
3. **FIND-010 — Chat prompt surface drift.** Runtime chat uses `chat/en/system.md`; the manifest points at `writing/en/chat/system.md`; prompt management lacks explicit root-mode identity; CR-02 also found chat system content injected through the user channel.
4. **FIND-011 — Timeline analysis bypasses the governed template.** A reviewed `planning/en/timeline/system.md` exists, but runtime `TimelineAnalysisService.generate_timeline()` builds an inline service prompt. Template fixes may not affect production.
5. **FIND-009 — Timeline/graph consistency context is still lossy.** Timeline events now reach consistency prompts, but source/confidence/causality/stale-reference metadata and graph-edge provenance are dropped before reasoning.
6. **Runtime adoption evidence is not strict enough.** CR-03 showed default adoption checks can pass while reporting `0 runtime_verified` / `0 adopted`; component-level evidence can diverge from the prompt/model path.
7. **Template-level prompt safety/quality cleanup remains.** CR-01 tasks cover unwrapped `entity_name`, non-standard input tags, generated `kb_suggested` precedence labels, deprecated `language`, and confidence/evidence fields.
8. **Remaining §16 UX gaps are narrow but user-visible.** CR-07 tasks cover KB Field Suggest and KB Improve lifecycle/error/cancel handling, Timeline Extraction manual abort, Ghost Text status, KB Enhance cancel UI, deprecated i18n keys, and keyboard consistency.
9. **Prompt customization docs/runtime drift remains.** CR-00 found `PROMPT-002` describes DB-backed per-user templates, while current evidence points to project-level file overrides through prompt management.

Resolved legacy findings are intentionally not listed as open: old missing route targets, production consistency/extraction fallbacks, mem0 DI, sparse output-profile mapping, variable registry gaps, `kb_suggested` non-consumption, ProjectWritingProfile absence, and precedence-rule absence are closed or superseded.

---

## 4. Roadmap

### Sofort (1–2 Wochen)
> Highest user impact; closes false-control and prompt-source-of-truth risks.

- **CR-AUFG-03-06 / CR-AUFG-08-01 — FIND-001:** Enforce resolved output limits at the LLM gateway/agent boundary for both run and stream paths; evidence must bind to the same invocation that reaches the model.
- **CR-AUFG-08-02 — FIND-012:** Wire `TokenLimitOverrides.tier_percentages` through writing dependency factories into `WritingContextAssembler` / `TokenBudgetManager`; add tests proving UI/API tier changes alter emitted tier budgets.
- **CR-AUFG-04-04 / CR-AUFG-04-05 / CR-AUFG-02-04 — FIND-010:** Choose the canonical chat prompt location, fix the manifest path, support root-mode prompt management or rename to an explicit mode, strengthen checker validation, and inject chat feature prompt as system/instructions rather than user text.
- **CR-AUFG-04-08 — FIND-011:** Route timeline analysis through `PromptComposer` and the governed planning timeline template, or explicitly mark that template non-routeable and move runtime instructions to an ADR-026-compliant prompt path.
- **CR-AUFG-03-01:** Make runtime evidence semantics explicit in default/CI adoption gates: no silent static PASS for runtime-required modes, or clearly label static-only runs.

### Kurzfristig (4–6 Wochen)
> Completes runtime adoption alignment and closes visible content-quality gaps.

- **CR-AUFG-03-02 / CR-AUFG-03-03 / CR-AUFG-03-04:** Ensure invocation-pipeline enrichment reaches the actual `PromptComposer` input; align `kb_suggested` evidence with the production assembler path; wire interactive WebSocket writing sessions into the same user/project/preference/budget/final-validation contract.
- **CR-AUFG-01-01 through CR-AUFG-01-05:** Apply prompt-template cleanup: user-content wrappers, standardized analysis input tags, generated-candidate precedence boilerplate, `writing_language` migration, and evidence/confidence fields for subjective analysis outputs.
- **CR-AUFG-04-01 / CR-AUFG-04-06 / CR-AUFG-04-07 — FIND-009:** Ratify KB/timeline/graph context envelopes and Storyboard ↔ KB ↔ Timeline integration contracts for rename/deletion/deprecation/stale refs/tombstones/typed consistency issues.
- **CR-AUFG-07-07 through CR-AUFG-07-13:** Close remaining CR-07 UX gaps: KB Field Suggest, KB Improve, Timeline Extraction, Ghost Text status, KB Enhance cancel, deprecated i18n-key prevention, and cross-flow keyboard shortcuts.
- **CR-AUFG-08-03 / CR-AUFG-08-04 / CR-AUFG-08-05:** Unify token profile vocabulary (`custom`, `comprehensive`, stale `conservative`), replace inline suggest raw `60` with a named cap or documented immutable UX cap, and decide whether consistency caps are user/project or operator-only.
- **PROMPT-002 doc/runtime decision:** Either implement the documented DB-backed user prompt template path or correct the feature documentation/status to match project-level file overrides.

### Mittelfristig (3–6 Monate)
> Structural improvements after runtime binding and prompt-source fixes are complete.

- **CR-AUFG-03-05 / CR-AUFG-01-06:** Promote KG/timeline context from formatted text to a reasoning substrate for consistency/planning, including staged fact extraction/timeline normalization before contradiction comparison.
- **CR-AUFG-04-09:** Unify voice-profile context for generation and checking through shared profile/provider contracts, preserving freshness/confidence where voice affects output.
- **CR-AUFG-08-06 / CR-AUFG-08-07 / CR-AUFG-08-08:** Move setup fallback model catalogs and repeated provider defaults behind settings/catalog abstractions; add model-limit calibration/warnings; route system/background model defaults through a named resolver.
- **PROMPT-003:** Finish Prompt Customization UX: variable explanation, preview/test mode, and reset-to-default semantics that match the actual prompt storage model.
- **Quarterly calibration program:** Re-run CR-00–CR-08, compare current model output windows/cost data, review stale fallback catalogs, verify token/context controls affect runtime, and age active findings.

---

## 5. Prozess-Empfehlungen

### 5.1 AI Content Review Gate

Add or update the AI-feature merge gate with checks that verify runtime effect, not only configuration presence:

```markdown
## AI Content Review Gate

Before merging any AI feature:

- [ ] Feature-specific system/task prompt resolves through `PromptComposer`/cascade, or has an ADR-026-approved non-routeable rationale.
- [ ] Guaranteed identity/safety content stays in `NarrareMeta` / `NarrareUniversalRules`; user-customizable content is not duplicated as code strings.
- [ ] Prompt-surface manifest category/mode/path/frontmatter match the runtime route and prompt-management surface.
- [ ] User-authored variables are registered and wrapped; generated/unaccepted candidates are labelled with lower precedence.
- [ ] `writing_language` / output-language variables are present for EN-only feature prompts.
- [ ] mem0/preferences are used only where semantically appropriate and never override explicit author/project context.
- [ ] Runtime adoption evidence is tied to the invocation that reaches the model, not only component-level placeholders.
- [ ] Resolved output limits and input context budgets are applied at runtime; UI/settings controls demonstrably affect execution or are not exposed.
- [ ] Cross-feature data has an integration contract for provenance, freshness, deletion/change behavior, and typed conflict surfacing.
- [ ] AI UX follows §16: shared operation lifecycle or documented exception, visible cancel where useful, actionable errors, partial-output recovery, canonical labels, and keyboard paths where appropriate.
- [ ] User-facing prompt customization docs/UI match the actual storage and cascade implementation.
```

### 5.2 Sprint-Review Template

```markdown
## Sprint Content Review – KW [XX]

New/changed AI prompts or AI runtime paths:
- [ ] [Feature/path] — Prompt route, variables, output language, context envelope, token limits, and UX lifecycle checked.

Settings/configuration changes:
- [ ] [Setting] — Verified that the setting affects the runtime consumer, not only UI/API state.

Known findings status:
- FIND-001 — [status]
- FIND-009 — [status]
- FIND-010 — [status]
- FIND-011 — [status]
- FIND-012 — [status]

New findings: [No / Yes: create FIND-XXX with root cause, evidence, user impact, sustainable fix, CR tasks]
```

### 5.3 Quarterly Major Review

Re-run CR-00 through CR-08. Keep CR-07 current with the frontend specialist and do not treat EN-only feature prompts as localization failures unless ADR-026/RULE-22 changes.

Mandatory quarterly review points:

- [ ] **Token limits and model calibration:** Compare selected output profiles/user limits against current provider/model output windows where `models.dev` or provider catalogs are available; label unknown/stale data.
- [ ] **Settings-to-runtime binding:** For every new setting, verify the runtime consumer uses it. Include token tiers, output limits, consistency caps, model routing, retry/timeouts, and prompt customization.
- [ ] **Hardcoded values and fallback catalogs:** Re-check setup fallback model lists, provider URLs, cost-rate defaults, timeout/retry constants, low-latency caps, and background-task retry values.
- [ ] **Prompt-surface integrity:** Confirm route table, manifest, template paths, frontmatter, PromptManagement IDs, and runtime injection channel agree.
- [ ] **Cross-feature contracts:** Re-check KB/storyboard/timeline/wiki/mem0/profile data boundaries for rename/deletion/freshness/provenance behavior.
- [ ] **Finding aging:** Re-prioritize any open finding older than two quarters; either close with evidence, schedule remediation, or escalate explicitly.

---

## 6. Offene Fragen für Design-Entscheidungen

Current unresolved decisions only:

1. **Output-limit enforcement mechanism:** Which pydantic-ai/provider setting is the canonical enforcement path for output tokens across `run()` and `run_stream()`, and how should that be represented in runtime evidence?
2. **Chat prompt identity:** Should root-mode prompts (`chat/en/system.md`) be supported as first-class prompt-management IDs, or should chat move to an explicit mode such as `chat/en/default/system.md`?
3. **Timeline prompt route:** Should timeline analysis be a mode under `LLMIntent.PLAN`, a dedicated intent, or explicitly non-routeable with agent-owned ADR-026 instructions?
4. **KB/timeline/graph envelope:** Which provenance/freshness/confidence/deletion fields are mandatory in prompt context, and which may be omitted under token pressure with recorded omission metadata?
5. **Model-limit calibration behavior:** When provider/model limits are unknown or stale, should Narrare warn, block high-output selections, or allow with a visible “uncalibrated” label?
6. **PROMPT-002 storage contract:** Is the product direction real DB-backed per-user prompt templates, or should documentation and feature status be corrected to project/user file-based overrides only?
