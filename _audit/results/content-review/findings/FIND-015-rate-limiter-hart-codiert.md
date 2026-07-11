# FIND-015: Rate-Limiter hart codiert, nicht operator-konfigurierbar
Priorität: 🟡 Mittel
Status: Offen
Review: cr-08
CR-AUFG: CR-AUFG-08-16

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

- [ ] Rate-Limiter über Env-Vars konfigurierbar (`NARRARE_RATE_LIMIT_*`)
- [ ] Defaults bleiben erhalten ( backwards-kompatibel)
- [ ] Dokumentation der Env-Vars in Deployment-Guide
