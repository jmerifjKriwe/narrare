# Content Review CR-05 – Resolution Record

> **Ursprung:** 2026-07-11 (CR-05 Initial Findings, kompiliert aus cr-00, cr-01,
> cr-02, cr-03, cr-04, cr-07, cr-08)
> **Resolution-Datum:** 2026-07-15
> **Reviewer:** NarrareCoreSpecialist (Content Review Audit)
> **Methode:** Jeder der 21 materialen Befunde (P1/P2) wurde am 2026-07-15
> erneut gegen echten Code (Datei:Zeile) verifiziert — nicht gegen Behauptungen
> oder Templates. Cross-Referenzen waren dedupliziert; jeder Befund hatte genau
> eine FIND-Datei bei seinem Ursprungs-Review.
>
> **Status:** Alle 21 FIND-Scratchdateien unter `findings/` wurden retiret.
> Dieser Index ist nun der alleinige Lifecycle-Record (Finding-Lifecycle SSOT:
> Exit-Evidenz lebt hier). `findings/README.md` ist ein reiner Pointer-Stub.

---

## Zusammenfassung

Alle **21 materialen Befunde** (3× P1, 18× P2) wurden am **2026-07-15** gegen
echten Code verifiziert und sind `✅ Resolved` (Implementation + Enforcement
gemäß `docs/development/finding-lifecycle.md` §2). Es verbleiben **keine offenen
Befunde** in diesem Review.

Die 21 FIND-Scratchdateien unter `findings/` wurden retiret; dieser Index ist
nun der alleinige Lifecycle-Record mit Exit-Evidenz. Der einstige Adoption-Score-Honesty- und §7-Stub-Folgeschritt ist inzwischen
**vollständig resolviert** (Detektion + Closing aller 12 Gaps +
Pre-commit-/CI-Enforcement) — siehe Abschnitt *Folgeschritt (resolviert)*
weiter unten.

### Prioritäts-Verteilung (alle resolviert)

| Priorität | Anzahl | Status |
|---|---|---|
| 🔴 Kritisch (P0) | 0 | — |
| 🔴 Hoch (P1) | 3 | ✅ Resolved |
| 🟡 Mittel (P2) | 18 | ✅ Resolved |

---

## Resolution-Tabelle

> Evidenz ist die verifizierte `Datei:Zeile` auf Disk (Stand 2026-07-15).
> `✅ Resolved` = Implementation existiert + Enforcement vorhanden.

| FIND | Titel | Review | Evidenz (Datei:Zeile) | Status |
|---|---|---|---|---|
| FIND-001 | Consistency-Check ohne KG-Relationships | cr-03 | `apps/api/narrare/consistency/checker_context.py:160-197` lädt `kb_relationships_text = rel_context.text` und übergibt `kb_relationships=…`; `consistency/prompt_builder.py:43` liest `deps.kb_relationships` | ✅ Resolved |
| FIND-002 | Coreference ohne Charakter-Liste | cr-03 | `analysis/coreference_service.py:106` akzeptiert `kb_repo`, L176 `fetch_kb_characters(...)`, L193/L208 relationships; neues Modul `analysis/coreference_kb.py` | ✅ Resolved |
| FIND-003 | Analysis-ContextAssembler ohne TokenBudget | cr-03 | `AnalysisContextAssembler` in `packages/core/narrare_core/analysis/assembler.py`; `analysis/beta_reader_service.py:150` nutzt `build_budgeted_prompt(deps, self._budget_assembler)`; `analysis/context_assembler.py:206-210` reicht KB-Bodies voll durch | ✅ Resolved |
| FIND-004 | KBConsistencyAnalyzer Body-Truncation hardcoded | cr-03 | `kb/consistency_analyzer.py:95` `max_body_tokens=1500` parametrisiert; L212 `cap_to_budget(entity.body, max_body_tokens)` (token-aware, ersetzt hartcodierte 5000-Zeichen-Grenze) | ✅ Resolved |
| FIND-005 | mem0-Preference-Injection-Gate | cr-03 | `packages/core/narrare_core/prompts/composer.py:94-113` Gate auf `not context.user_preferences` + `user_id`/`project_id`; `_app/dependencies_prompts.py:128` verdrahtet `preference_service`; `_app/dependencies_pipeline.py:54-59` zusätzlicher `PreferenceContextEnricherImpl` | ✅ Resolved |
| FIND-006 | Adoption-Scorer token_budget ohne Code-Nachweis | cr-03 | siehe eigene Sektion unten (besondere Dokumentation) | ✅ Resolved |
| FIND-007 | Worldbuilding Phase 1 Defizite | cr-01 | `prompts/_bundled/kb/en/worldbuilding/phase1/system.md` v1.2.0: JSON-Codeblock (L51-86) + Constraints mit `{{writing_language}}` (L102) | ✅ Resolved |
| FIND-008 | Worldbuilding Phase 2 JSON-Schema | cr-01 | `prompts/_bundled/kb/en/worldbuilding/phase2/system.md` v1.3.1: JSON-Codeblock (L80-100) | ✅ Resolved |
| FIND-009 | summarize Do-NOT + JSON-Format | cr-01 | `prompts/_bundled/analysis/en/summarize/system.md` v1.3.0: 4 Do-NOT-Items, JSON-Format (L19-31) | ✅ Resolved |
| FIND-010 | kb/extract Runtime-Input Contract | cr-01 | `prompts/_bundled/kb/en/extract/system.md` v1.2.0: `### Runtime Input`-Sektion (L32-36) | ✅ Resolved |
| FIND-011 | style_profile in Writing-Prompts | cr-01 | `{{style_profile}}` jetzt in allen 8 EN-Writing-Prompts vorhanden (inkl. der 4 ehemals fehlenden: scene_by_scene, interactive_session, story_suggest, chat) | ✅ Resolved |
| FIND-012 | candidate_pairs Wrapping | cr-01 | `prompts/variable_registry.py:51` — `candidate_pairs` in `USER_CONTENT_VARS`; `prompts/_bundled/kb/en/merge/system.md:33` wrappt `<user_provided_data>{{candidate_pairs}}</user_provided_data>` | ✅ Resolved |
| FIND-013 | Injection Defense Duplikat | cr-02 | meta {en,de,fr} alle v3.1.0 **ohne** XML-Tag-Defense; `universal/en/system.md:17` behält sie (Eigentümer der Injection-Defense) | ✅ Resolved |
| FIND-014 | RULE-18b-Enforcement-Toolchain entfernt `[configuration-effect]` | cr-08 | `scripts/doc_drift/removed_governance_refs_checks.py` (WARNING-Only, geratchette Baseline); gelöschte Governance-Artefakte entfernt; CONSTRAINTS.md RULE-18b auf Realität umgeschrieben | ✅ Resolved |
| FIND-015 | Rate-Limiter hart codiert | cr-08 | `_app/rate_limits.py`: alle 6 `NARRARE_RATE_LIMIT_*`-Env-Vars mit governed Defaults (3/5/10/10/5/3); `tests/unit/api/_app/test_rate_limits.py` | ✅ Resolved |
| FIND-016 | Writing de/fr Legacy-Templates | cr-02 | `prompts/_bundled/writing/de/` und `writing/fr/` leer/entfernt → ADR-026 Phase 5 Option 1 (Entfernen) umgesetzt; Output-Sprache via `{{writing_language}}` | ✅ Resolved |
| FIND-017 | Provenance-annotated KB-Rendering | cr-04 | `context/_provenance_annotation.py` `compute_provenance_annotation()` (Trigger/Suppress-Logik); `context/_render_options.py` `RenderOptions(annotate_provenance=)`; Render-Pfade akzeptieren `preserved_fields` | ✅ Resolved |
| FIND-018 | ChatPanel generische Fehlermeldung | cr-07 | `packages/web/components/studio/editor/ChatPanel.tsx:144-160` rendert `error.userMessage` (statt generischer Konstante) + Retry-Button bei `error.retryable` | ✅ Resolved |
| FIND-019 | Consistency Ignorieren-Markierung | cr-07 | `packages/web/lib/api/consistency.ts` (dismiss/undismiss/list), `lib/hooks/useDismissedFindings.ts`; Backend-Endpoints `POST/GET/DELETE /novels/{id}/kb/consistency/dismiss[ed]`; Tests vorhanden | ✅ Resolved |
| FIND-020 | Emotionale Intensitätskurve _(Enhancement)_ | cr-07 | `packages/web/components/studio/analysis/SentimentArcGraph.tsx`, `SentimentChart.tsx`, `SentimentPanel.tsx`, `analysis/intensity.ts` (Enhancement umgesetzt) | ✅ Resolved |
| FIND-021 | Demo-Projekt Beispiel-KB _(Enhancement)_ | cr-07 | `apps/api/narrare/setup/demo_loader.py` (3 Demos: fantasy/scifi/german), `setup/contracts.py`, `/setup/demos`-Endpoint, `packages/web/types/wizard.ts` `DemoProjectInfo`, RULE-17-Contract-Test `test_demo_contract.py` | ✅ Resolved |

---

## FIND-006 — Besondere Dokumentation (Adoption-Scorer)

**Status:** ✅ Resolved (2026-07-15) — mit dokumentierter Ablehnung der statischen Code-Verifikation.

**Implementation:** `scripts/adoption/scorer_checks.py` führt für
`token_budget`/`injection_defense` ein `unverified=has_prompts`-Flag plus Note
("no code-level evidence") ein. `audit_report.py` stellt unverified-Infrastruktur
in einem eigenen Report-Abschnitt ("Unverified infrastructure assumptions") dar;
`scorer.py:353` zählt `unverified_count`. Tests: `tests/unit/scripts/test_scorer_checks.py`,
`test_audit_report_build.py`, `test_adoption_unverified_count.py`.

**Warum die volle statische Code-Verifikation bewusst NICHT umgesetzt wurde:**
Die angestrebte Runtime-Eigenschaft ("der gebaute Prompt-Kontext ist
token-begrenzt") lässt sich nicht zuverlässig statisch prüfen. Ein
Name-/Import-basierter Scanner hätte systematische **False Positives** (Dead
Imports: Klasse importiert, aber nicht in den Prompt-Pfad verkabelt) UND
**False Negatives** — belegt direkt an den Fixes von FIND-003
(`AnalysisContextAssembler`) und FIND-004 (`cap_to_budget()`), die
token-bewusst sind, ohne wörtlich `TokenBudgetManager` zu referenzieren, und die
ein solcher Scanner fälschlich als "not adopted" fehlschlagen würde. Eine
Prüfung, die in beide Richtungen systematisch falsch liegt, ist kein Gate,
sondern Rauschen und ein neues False Control. Die `unverified`-Markierung ist der
ehrlichere Endzustand. Das wirksame Enforcement für "Budget angewendet" liegt in
den **Per-Service-Regressionstests auf Runtime-Ebene** (dort wo FIND-003/004
ihre echte Evidenz haben), nicht in einer statischen Bezeichner-Suche.

---

## Folgeschritt (✅ resolviert): Adoption-Score-Honesty + §7-Stub-Closing

**Status:** ✅ Vollständig resolviert (2026-07-16/17). Keine offenen Folgeschritte mehr in diesem Strang.

**Ursprung:** Der Adoption-Scorer kreditierte `unverified`-Items als `adopted=1.0` (FIND-006-Rest-False-Control); kombiniert mit einem Consumer-biasierten Evidence-Mapping schien kbs reale Adoption < 0.85. Beides entpuppte sich als Scorer- bzw. §7-Lücken, nicht als kb-Defizit.

**Lösungsbogen (Commits als Evidenz):**

- **Scorer-Modell α + Option A** (`8f4f0637`) — `_INFRA_VAR_EVIDENCE` zu `dict[(category, infra_dim), set[var]]` restrukturiert (kb→Owner-Vocab, Consumer-Bias-Fix: kb 0.87→1.00); `unverified` aus dem verified-Aggregat ausgeschlossen (overall 0.97→0.9985).
- **kb-Debt** (`238200ad`) — merge/extract `world_context` genuin populiert; redundanter `{{avoidance_patterns}}`-Slot entfernt (`{{user_preferences}}` erhalten).
- **Mapping-Audit-Closure** (`e0589bdf`) — F1: kanonische `{{kb_entities}}`-Var in der analysis-Cell; F3: `kb_relationships` für kb deklariert (Adoption sichtbar).
- **§7-Stub-Detector** (`7725f899`) — neu, WARNING-only mit geratchetter Baseline; dann (`828ac3d4`) auf `critical`/CI-blockierend geschärft UND in pre-commit (Source-Dateien) verdrahtet.
- **§7-Closing, 5 Wellen** — alle 12 §7-Stub-Gaps (Template deklariert Slot, Runtime leer) geschlossen:
  - W1 (`29fac339`) — 4 tote `culture_guidelines`-Slots entfernt (Composer auto-inject).
  - W2 (`144c5ad5`) — wiederverwendbarer `KBContextProvider` (Contract+Impl) + timeline KB-Kontext; ADR-067 Proposed→Accepted.
  - W3 (`b2c43c04`) — `entity_events`/`existing_plot_points`/`chapter_outline` per Existing-Repos.
  - W4a (`6749753e`) — coreference per Provider; Detector auf `critical` gekippt (§7-Stubs → 0).
  - W4b (`c8bc88d7`) — beta-reader dict→Envelope (β-str; Provenance fließt).
- **`_world_context`-Konsolidierung** (`690c94a6`) — assist/improve via `KBContextProvider` (eine Quelle, Inline-Duplikation entfernt).

**Ergebnis:** Die §7-Anti-Pattern-Klasse ist **strukturell geschlossen und CI-+pre-commit-erzwungen** (Regressionen blockieren ab sofort). Provenance (FIND-017) fließt einheitlich über `KBContextProvider`/ADR-050-Envelope (timeline, coreference, beta-reader). `check_adoption` durchgehend **1.00** (ehrlich + grün). Zwei unabhängige Scorer-Honesty-Bugs (FIND-006 `unverified`-Kredit + Consumer-Bias) sind addressiert; das Evidence-Mapping wurde nach Modell α audittet.

---

## Abschluss

Alle 21 materialen Befunde (P1/P2) sind resolviert; die Remediations-Arbeit zu
CR-05 ist abgeschlossen. Die **15 P3-Aufgaben und 3 Stale-Items** aus dem
ursprünglichen Index waren nie Teil dieses Resolution-Passes — sie bleiben in
ihren Ursprungs-Reviews (cr-00 bis cr-04, cr-07, cr-08) eigenständig getrackt
und fallen nicht unter diesen Record.

Pointer: [`findings/README.md`](findings/README.md) (Stub, verweist hierher).
