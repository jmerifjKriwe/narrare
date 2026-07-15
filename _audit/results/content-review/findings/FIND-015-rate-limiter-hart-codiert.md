# FIND-015: Rate-Limiter hart codiert, nicht operator-konfigurierbar
Priorität: 🟡 Mittel
Status: ✅ Resolved (2026-07-15)
Review: cr-08
CR-AUFG: CR-AUFG-08-16
Scope: erweitert auf alle 6 Modul-Level-Limiter (FIND-015 listete 5; der 6.
`SETUP_MODELS_LIMITER` wurde der Konsistenz halber mit aufgenommen).

> **Hinweis:** Kein `configuration-effect`-Marker, da die Rate-Limiter nie als
> konfigurierbar dokumentiert waren (keine False-Control-Lüge). Reiner
> Konfigurierbarkeits-FIND.

## Befund

Fünf Rate-Limiter sind hardcodiert ohne Env/Settings-Override:

- `AI_WRITE_LIMITER = Rate(3, 1min)` — `apps/api/narrare/_app/rate_limits.py:54`
- `AI_ANALYSIS_LIMITER = Rate(5, 1min)` — `rate_limits.py:60`
- `AI_LIGHT_LIMITER = Rate(10, 1min)` — `rate_limits.py:67`
- `AI_WS_LIMITER = Rate(3, 1min)` — `rate_limits.py:92`
- `AI_PROMPT_LIVE_TEST_LIMITER = Rate(5, 1min)` — `rate_limits.py:82`

Dies ist die einzige verbleibende Magic-Number-Gruppe mit hohem Änderungsrisiko
ohne Config-Pfad.

## Evidenz

- `apps/api/narrare/_app/rate_limits.py:54-92` — 5 hardcodierte `Rate(N, 1min)`.
- Keine Env-Var-Override, keine Settings-Integration.
- Vergleich: `TRANSPORT_MAX_RETRIES_DEFAULT` hat Env `NARRARE_LLM_TRANSPORT_MAX_RETRIES`
  (ADR-060) — Rate-Limiter haben kein Analogon.

## Auswirkung

Self-Hoster mit anderer Hardware (stärkere/schwächere Maschine) oder
Managed-Hosting-Profile (Multi-User) können Limits nicht anpassen. Bei
Managed-Hosting (Q-011 offen) sind 3 Write-Requests/Minute für mehrere
gleichzeitige Nutzer zu restriktiv.

## Empfehlung

Klassifiziere Rate-Limiter als `operator_default` mit Env-Vars
(`NARRARE_RATE_LIMIT_WRITE`, `NARRARE_RATE_LIMIT_ANALYSIS`, etc.), analog zu
`NARRARE_LLM_TRANSPORT_MAX_RETRIES` (ADR-060).

**Owner:** Backend + Platform.

## Verifikation

- [x] Rate-Limiter über Env-Vars konfigurierbar (`NARRARE_RATE_LIMIT_*`) — alle 6 Limiter
- [x] Defaults bleiben erhalten (backwards-kompatibel — 3/5/10/10/5/3, identisch mit bisher hartcodierten Werten)
- [x] Dokumentation der Env-Vars — kanonisch im Modul-Docstring `apps/api/narrare/_app/rate_limits.py` (Abschnitt "Operator configuration (governed defaults)", alle 6 Vars + Defaults). _Deployment-Guide-Env-Var-Tabelle: Follow-up_ — der Guide führt eine Operator-Env-Tabelle (`NARRARE_ENCRYPTION_KEY`, `NARRARE_CSRF_TRUSTED_ORIGINS`, `NARRARE_OTEL_INCLUDE_CONTENT` …), listet `NARRARE_RATE_LIMIT_*` aber noch nicht (siehe Follow-up-Notiz unten).

## Resolution evidence

**Status:** ✅ Resolved (2026-07-15) — Implementation + Enforcement vorhanden (per
`docs/development/finding-lifecycle.md` §5). Scope erweitert auf alle 6
Modul-Level-Limiter (FIND-015 listete 5; der 6. `SETUP_MODELS_LIMITER` wurde der
Konsistenz halber mit aufgenommen).

**Design —** Folgt dem governed-default-Pattern aus ADR-060 (LLM-Transport-Retry,
`packages/core/narrare_core/llm/_transport_retry.py`). Kein neuer ADR erforderlich.

**Implementation —** `apps/api/narrare/_app/rate_limits.py`: alle 6 Limiter
(Write / Analysis / Light / Setup-Models / Prompt-Live-Test / WebSocket) lösen ihre
Request-Anzahl nun über `NARRARE_RATE_LIMIT_*`-Env-Vars auf
(`NARRARE_RATE_LIMIT_WRITE/ANALYSIS/LIGHT/SETUP_MODELS/PROMPT_LIVE_TEST/WS`) mit
gepinnten governed Defaults (3/5/10/10/5/3). Der Resolver
`_resolve_rate_limit_count` validiert (weist Nicht-Integer / `< 1` zurück, warnt via
structlog — RULE-11, analog zu `_transport_retry.get_transport_max_retries`). Window
bleibt fix auf 1 min (`LONG_WINDOW_MS`); öffentliche Limiter-Namen/-Typen
unverändert. Defaults identisch mit den bisher hartcodierten Werten
(backwards-kompatibel).

**Enforcement —** `tests/unit/api/_app/test_rate_limits.py`:
`TestGovernedDefaults` pinnt alle 6 Defaults (Regression-Guard gegen versehentliche
Default-Änderung — RULE-18b); `TestResolveRateLimitCount` deckt den Resolver ab
(gültig / ungültig / unter Minimum); ein Verhaltenstest beweist
env→count→acquire ohne globale Modul-Mutation. Lokal verifiziert:
**9.226 Unit-Tests passed (0 failed)**; Voll-Suite inkl. Integration
**9.894 passed (0 failed)**.

## Follow-up-Notiz

Deployment-Guide `docs/development/deployment-guide.md` führt eine Operator-Env-Tabelle,
listet die neuen `NARRARE_RATE_LIMIT_*`-Vars aber noch nicht (out of scope dieses
Findings — Datei liegt außerhalb des 4-Dateien-Sets dieses Resolution-Schritts). Die
kanonische Dokumentation ist das Modul-Docstring. Ein Tabellen-Eintrag pro Var
(Write/Analysis/Light/Setup-Models/Prompt-Live-Test/WS) mit jeweiligem Default
bleibt als Docs-Follow-up offen und wurde an den Coordinator gemeldet.
