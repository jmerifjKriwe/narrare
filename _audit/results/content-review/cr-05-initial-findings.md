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
nun der alleinige Lifecycle-Record mit Exit-Evidenz. Ein verbleibender
Folgeschritt zur Adoption-Score-Honesty ist unten als bekanntes Known-Unknown
registriert — er trägt bewusst **keine** eigene FIND-Nummer (siehe
[Offener Folgeschritt](#offener-folgeschritt-adoption-score-honesty-kein-neues-find)).

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

## Offener Folgeschritt: Adoption-Score-Honesty (kein neues FIND)

**Status:** ✅ Resolved (2026-07-16) — Score-Honesty + kb-Debt implementiert; das Mapping-Audit bleibt als definite Folgeaufgabe offen.

Die `unverified`-Markierung war bisher per Test bewusst aus der Score-Berechnung ausgeschlossen, sodass der `overall_score` (`scripts/check_adoption.py`, CI-Gate G8, Schwelle ≥ 0.85) `token_budget`/`injection_defense` als `adopted=1.0` kreditierte — der dokumentierte Rest-False-Control.

**Implementation (beides shipped, Gate grün UND ehrlich):**

- **Scorer-Modell α + Option A** — Commit `8f4f0637` *fix(adoption): per-category evidence vocab and exclude unverified from score*. `_INFRA_VAR_EVIDENCE` zu `dict[(category, infra_dim), set[var]]` restrukturiert; `kb→kb_entities` mit Owner-Vocab (`existing_entity_names`/`entity_summaries`/`entity_details`) statt Konsumenten-Vocab → kb **0.87 → 1.00** (Consumer-Bias-Fix; das war ein Scorer-Bug, kein kb-Defizit). `unverified` an beiden Aggregationsstellen (`scorer.py`, `scorer_modes.py`) aus Zähler **und** Nenner ausgeschlossen → overall **0.97 → 0.9985** (Inflation entfernt). `unverified_count==7` bleibt im separaten Audit-Abschnitt sichtbar und ist nun konsistent zur Schlagzahl.
- **kb-Debt** — Commit `238200ad` *fix(kb): populate world_context for extract/merge and remove dead avoidance slot*. merge/extract `world_context` genuin populiert (echter `KBRepositoryProtocol.list_entries`-Fetch, single-read, RULE-11-Graceful-Degradation auf `""`); redundanter `{{avoidance_patterns}}`-Slot aus `kb/merge` + `kb/extract` entfernt (die Avoidance-Daten laufen über `{{user_preferences}}`, das in beiden Templates erhalten bleibt); Helper `_world_context.py` (RULE-04).

**Enforcement:** Regressionstest `test_unverified_never_enters_verified_aggregate` sowie der gekippte `test_unverified_excluded_from_verified_score` (Invariante kehrt sich um: `unverified` darf nicht in den verified-Aggregat einfließen); `check_adoption`-Gate jetzt ehrlich; kb-`world_context`-Tests asserten Nicht-Leere zur Runtime.

**Definite Folgeaufgabe (mit Owner, nicht optional — bleibt offen):** Mapping-Audit — jedes `(category, dim)`-Paar unter Modell α auf Korrektheit und Vollständigkeit prüfen. Beobachtung: der Scorer offenbarte zwei unabhängige Honesty-Bugs (FIND-006 `unverified`-Kredit + der hier behobene Consumer-Bias) → strukturelle Fragilität des Evidence-Mappings; der Audit verifiziert, dass die neue per-`(category, dim)`-Matrix vollständig und korrekt ist.

---

## Abschluss

Alle 21 materialen Befunde (P1/P2) sind resolviert; die Remediations-Arbeit zu
CR-05 ist abgeschlossen. Die **15 P3-Aufgaben und 3 Stale-Items** aus dem
ursprünglichen Index waren nie Teil dieses Resolution-Passes — sie bleiben in
ihren Ursprungs-Reviews (cr-00 bis cr-04, cr-07, cr-08) eigenständig getrackt
und fallen nicht unter diesen Record.

Pointer: [`findings/README.md`](findings/README.md) (Stub, verweist hierher).
