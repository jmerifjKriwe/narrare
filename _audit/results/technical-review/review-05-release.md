# Review 05 – Release, Packaging & Gesamtbewertung

> Aktualisiert am 2026-06-29 durch NarrarePlatformSpecialist. Finale
> Konsolidierung der Reviews 01–04 (alle am 2026-06-29 aktualisiert) plus
> frische Release-/Security-/Observability-Analyse. Alle alten AUFG-05-01
> bis AUFG-05-14 sind im `aufg-registry.md` als `resolved` bzw.
> `covered_by_existing_aufg` dokumentiert und werden nicht erneut als offen
> geführt.
> **Hinweis:** PyPI-Publishing ist absichtlich nicht integriert und soll hier
> NICHT als Aufgabe oder Empfehlung erscheinen.

## Methodik & ausgeführte Prüfungen

- **Graph-first ausgeführt:** `get_minimal_context` (26.084 Nodes, 185.730
  Edges, 2.777 Files, Risiko low), danach gezielte Reads/Greps auf Release-,
  Security- und Observability-relevante Dateien.
- **Keine destruktiven/langlaufenden Commands:** Kein `docker build`, kein
  `docker push`, kein `just dev`. Nur read-only Inspection von
  Konfigurationsdateien, Workflows, Dockerfiles, Compose-Dateien, CHANGELOG,
  Observability-Code, Security-Middleware und Rate-Limiter-Implementierung.
- **Geprüfte Quellen:** `release-please.yml`, `ci.yml`, `Dockerfile`,
  `docker-compose.{release,prod,dev}.yml`, `entrypoint.sh`, `CHANGELOG.md`,
  `.env.example`, `main.py`, `rate_limits.py`, `rate_limiter_dep.py`,
  `middleware.py`, `observability.py`, `cookie_helpers.py`,
  `settings_model.py`, `deployment-guide.md`, `aufg-registry.md`,
  `CONSTRAINTS.md`, `TECH_STACK.md`, alle Review-Ergebnisse 00–04.
- **AUFG-Registry-Verifikation:** `docs/architecture/governance/aufg-registry.md`
  systematisch gegen Code-Evidenz abgeglichen — AUFG-05-01 bis AUFG-05-14
  plus AE-05-01/02/03 und AR-05-02/03/04/05.
- **Trace-Propagation-Tests verifiziert:** `tests/integration/observability/
  test_trace_propagation.py` und `test_sse_trace_propagation.py` existieren
  und testen `x_trace_id`/`x_span_id` über den HTTP→SSE-Flow.

---

## 1. Release- & Packaging-Prozess

**Bewertung:** ⭐⭐⭐⭐ `Professionell automatisiert; Distribution bleibt Docker-only`

**Befunde:**
- **Release Please** auf `main` mit Conventional Commits: automatische Version-
  Bumps, CHANGELOG-Generierung, GitHub Release (`release-please.yml:1-27`).
  CHANGELOG.md folgt Keep a Changelog / SemVer.
- **Docker-Image** wird im selben Workflow gebaut und nach GHCR gepusht
  (`release-please.yml:36-76`): Multi-Stage Build, Version-Tag + `latest`,
  BuildKit Cache (`cache-from: type=gha, cache-to: type=gha,mode=max`).
- **Release Bundle** (`narrare-<version>.zip`): enthält `docker-compose.yml`,
  `.env.example`, SBOM-Dateien und ein ausführliches README mit Quick Start,
  Configuration, Verification und Provenance-Trust-Tabelle
  (`release-please.yml:110-251`).
- **SBOM** automatisch generiert: CycloneDX via Syft (best-effort) +
  `requirements.txt` via `uv export` (`release-please.yml:77-108`). SBOM
  wird als separates Release-Asset veröffentlicht.
- **Multi-Stage Dockerfile** (120 Zeilen, sauber strukturiert):
  `build-python` → `build-frontend` → `runtime`. Produziert schlankes
  Runtime-Image (`python:3.14-slim-bookworm`) mit Node 24 für Next.js
  standalone. HEALTHCHECK auf `/health`. Entrypoint mit Signal-Handling.
- **pnpm-Version konsistent:** `Dockerfile:53` nutzt `ARG PNPM_VERSION=11.5.2`
  (AUFG-05-04 resolved). Dockerfile, DevContainer, Root `package.json` und CI
  teilen eine pnpm-Version. CI-Gate `check_doc_drift.py` validiert das.
- **Keine Artefakt-Signierung:** Cosign ist als `accepted_enhancement`
  dokumentiert (AE-05-01, keyless signing via GitHub OIDC). SBOM + Digest
  + GitHub-automatic-signing als aktuelle Verification-Basis.
- **Rollback** ist nicht explizit dokumentiert. Docker-Semantik erlaubt
  impliziten Rollback via Image-Pull, aber es fehlt ein dedizierter Guide
  (bleibt als Aufgabe).
- **docker-compose.prod.yml** bietet pgBouncer-Overlay für Single-User-/
  Small-Self-Hosted — positiver Operations-Befund.
- **CI-Gate-Audit-Tabelle** in `ci.yml:3-43` ist vorbildlich dokumentiert:
  jeder Gate mit Tool, CI-Status und Notes aufgelistet.

**Checkliste Release-Qualität:**
- [x] Versionierung klar und automatisiert via release-please (Conventional
      Commits / SemVer)
- [x] Release-Notes automatisch aus Commit-History generiert
- [ ] Binaries / Installer für alle Zielplattformen (bewusst nicht angestrebt —
      Docker-only)
- [x] Docker-Image vorhanden und in GHCR gepusht
- [x] Release-Prozess in CI komplett automatisiert (Release Please + Docker
      Build + Bundle + SBOM)
- [ ] Rollback-Prozess dokumentiert (nur implizit via Docker-Image-Pull;
      AUFG-05-06 folgt unten)
- [x] SBOM automatisch generiert und als Release-Asset veröffentlicht
- [ ] Artefakt-Signierung (Cosign dokumentiert als AE-05-01 accepted
      enhancement, nicht implementiert)

---

## 2. Nutzerfreundliche Bereitstellung

**Bewertung:** ⭐⭐⭐ `Docker-Self-Hosted gut dokumentiert; für Nicht-Techniker hohe Hürde`

**Befunde:**
- **Release-Bundle-README** ist detailliert: Quick Start (4 Schritte),
  Configuration-Tabelle mit allen Pflicht-Variablen, Docker-Networking-
  Hinweise, Update-Anleitung, Stop-Anleitung und vollständige Verification-
  Sektion mit SBOM/Digest/Provenance (`release-please.yml:128-249`).
- **`install.sh` existiert nicht mehr** im Repository — alter Befund obsolet.
- **Update-Mechanismus** ist simpel: `docker compose pull && docker compose
  up -d`. Alembic-Migrationen laufen automatisch beim Startup (`lifespan.py`).
- **Einstiegshürde** bleibt für die Zielgruppe (kreative Schreiber) hoch:
  Nutzer benötigen Docker-Kenntnisse, müssen `.env` manuell konfigurieren,
  mindestens einen AI-Provider-Key eintragen und `NARRARE_ENCRYPTION_KEY` +
  `SECRET_KEY` generieren. Das Deployment Guide enthält die Generierungs-
  Befehle, aber der Prozess ist nicht ein-Klick-fähig.
- **Kein Desktop-App/Installer, kein One-Liner-Setup, kein Auto-Update.**
- **docker-compose.release.yml** ist sauber strukturiert: Health Checks für
  alle drei Services (Narrare, Postgres, Redis), `depends_on` mit
  `service_healthy`, `restart: unless-stopped`, benannte Volumes für
  Persistenz.
- **Q-011** (Distribution für Nicht-Techniker) bleibt eine offene
  Architekturfrage, als AE-05-02 (Managed Hosting Strategy Exploration)
  `accepted_enhancement` im Registry geführt.

**Vergleich mit zeitgemäßen Alternativen:**
- `pipx install narrare` — für diese Architektur (FastAPI + Next.js +
  Postgres + Redis) nicht praktikabel.
- Electron/Tauri-Wrapper — würde die Docker-Anforderung eliminieren,
  erfordert aber signifikanten Implementierungsaufwand.
- Managed Hosting (Railway, Fly.io, Render) — `docker-compose.release.yml`
  ist kompatibel; ein One-Click-Deploy-Template wäre mittelfristig machbar
  (AE-05-02).

---

## 3. Security, Privacy & Compliance

**Bewertung:** ⭐⭐⭐⭐ `Starke Security-Grundlage; Rate-Limiting, CSRF und Secret-Scanning seit letztem Audit implementiert`

**Befunde:**

### Auth & Token-Handling
- **httpOnly Refresh Cookie** mit korrekten Attributen: `httponly=True`,
  `secure=settings.is_production`, `samesite="lax"`, `path="/api/v1/auth"`
  (`cookie_helpers.py`). Kein localStorage für Tokens.
- **Access Token** in-memory im Frontend (`client.ts`). Frontend dokumentiert
  explizit „never localStorage" für Access Token.
- **Key-Rotation** für `NARRARE_ENCRYPTION_KEY` ist dokumentiert: Decrypt mit
  altem Key, Re-encrypt mit neuem Key (`deployment-guide.md`). Backup-Warnung
  ist prominent platziert.

### API-Key-Verschlüsselung
- User API Keys werden via Fernet (`core/shared/crypto.py`) verschlüsselt
  gespeichert und nur bei Provider-Instanziierung entschlüsselt. Keys werden
  nicht geloggt oder via API zurückgegeben.
- `NARRARE_ENCRYPTION_KEY` ist Pflicht-Variable; Verlust-Warnung ist in
  `.env.example` und Deployment Guide prominent dokumentiert.

### Rate-Limiting (AUFG-05-12 resolved)
- **Umfassend implementiert:** `apps/api/narrare/_app/rate_limits.py`
  definiert 5 module-level `RateLimiter`-Instanzen:
  `AI_WRITE_LIMITER` (3/min), `AI_ANALYSIS_LIMITER` (5/min),
  `AI_LIGHT_LIMITER` (10/min), `SETUP_MODELS_LIMITER` (10/min, IP-based),
  `AI_PROMPT_LIVE_TEST_LIMITER` (5/min). WebSocket: `AI_WS_LIMITER` (3/min).
- 17 Router-Dateien via `dependencies=[Depends(CONSTANT)]` verdrahtet.
- 14 Unit-Tests (`test_rate_limits.py`) + Auth-Rate-Limit-Tests
  (`test_auth_rate_limits.py`).
- **In-Memory statt Redis** (AR-05-02 accepted_risk): funktionell für
  Single-Instance-Deployment.

### CORS
- **Production: keine CORS-Origins erlaubt** (`allow_origins=[]`).
  Development: nur `["http://localhost:3000"]` (`main.py:54`). Same-origin
  Proxy-Setup ist sicher.
- AE-05-03 (CORS Origins als Settings-Feld) ist `accepted_enhancement` für
  zukünftige Deployment-Szenarien.

### CSRF (AUFG-05-13 resolved)
- **OriginValidationMiddleware** in `_app/middleware.py` validiert
  Origin/Referer auf allen POST/PUT/PATCH/DELETE-Requests. Bearer-
  authentifizierte Requests ohne Origin sind exempt (programmatic clients).
- WebSocket Origin-Check in `router_sessions.py` (close code 4001).
- `Settings.csrf_trusted_origins` (`NARRARE_CSRF_TRUSTED_ORIGINS`,
  Default `["http://localhost:3000"]`).
- 12 Unit-Tests (`test_csrf_middleware.py`): same-origin (200), cross-origin
  (403), Bearer-exempt (200), WebSocket (4001), Referer-Fallback.
- AR-05-05 (No Double-Submit-CSRF-Token) ist `accepted_risk` mit klarer
  Begründung (Bearer-token auth macht CSRF strukturell inapplicable).

### CI-Security
- **Gitleaks** (Secret Scanning, v8.30.1) läuft blocking in CI
  (`ci.yml:257-266`, AUFG-05-09 resolved). `fetch-depth: 0` für full git
  history.
- **Bandit** + **pip-audit** laufen blocking (`ci.yml:268-274`).
  Ignorierte Vulnerabilities: `PYSEC-2025-183`, `GHSA-rrmf-rvhw-rf47` —
  explizit dokumentiert.
- Unit-Tests nutzen Dummy-API-Keys (`sk-test-dummy`), keine echten
  Provider-Secrets.
- **CI-Permissions:** global `contents: read`, `pull-requests: read`
  (`ci.yml:72-74`). `test-unit` hat zusätzlich `pull-requests: write`
  für Coverage-Kommentare. Release-Workflow scoped auf `publish`-Job
  (`contents: write`, `packages: write`).

### Privacy
- **KB-Interview-Resume** nutzt `sessionStorage` statt `localStorage`.
  `localStorage` bleibt nur für den Opt-out-Flag.
- **OTel Content-Capture** ist production-safe:
  `NARRARE_OTEL_INCLUDE_CONTENT` defaultet auf `false` in Production,
  `true` nur in Development (`telemetry.py`). Verhindert Prompt/User-Prose-
  Exfiltration in Traces.

### Accepted Risks (bewusst dokumentiert im Registry)
- AR-05-02: In-Memory Rate-Limiting (Multi-Instance → Redis nötig).
- AR-05-03: Auth Non-Brute-Force Endpoints ohne Rate Limit (refresh/logout/
  me).
- AR-05-04: State-Changing CRUD ohne Rate Limit (Local-First, auth-protected).
- AR-05-05: No Double-Submit-CSRF-Token (Bearer-token auth macht CSRF
  strukturell inapplicable).

### Offene Punkte
- Keine neuen Security-Aufgaben. Alle AUFG-05-07/08/09/12/13 sind resolved.
- Accepted Risks haben klare Owner, Review-Trigger und Controls (abgedeckt durch AR-05-02, AR-05-03, AR-05-04, AR-05-05).

---

## 4. Observability & Operations

**Bewertung:** ⭐⭐⭐⭐ `ADR-031 Phase 1 vollständig; Trace-Chain mit Integrationstests, Health-Severity-Policy implementiert`

**Befunde:**

### Tracing (ADR-031)
- **OpenTelemetry-only** als Trace-Standard. Langfuse entfernt, Logfire nicht
  für Core-Observability.
- **`telemetry.py`** konfiguriert TracerProvider, OTLP-gRPC-Exporter,
  FastAPI-Instrumentation und Pydantic-AI native Instrumentation
  (`Agent.instrument_all`). No-op wenn `OTEL_EXPORTER_OTLP_ENDPOINT` nicht
  gesetzt — graceful degradation.
- **Trace-Context für SSE:** `get_current_trace_context()` extrahiert
  `x_trace_id`/`x_span_id`; `enrich_sse_data()` merged sie in SSE-Event-
  Payloads (`observability.py`). Deckt HTTP → FastAPI → Agent/LLM → SSE.
- **Integrationstests vorhanden** (AUFG-05-03 effectively covered):
  `tests/integration/observability/test_trace_propagation.py` und
  `test_sse_trace_propagation.py` testen `x_trace_id`/`x_span_id`-Propagation
  über HTTP- und SSE-Flows.

### OTel Health-Severity (AUFG-05-10/05-14 resolved)
- **Health-Severity-Policy** dokumentiert unter
  `docs/architecture/governance/otel-health-severity-policy.md`.
- **`get_observability_status()`** in `observability.py` liefert `state`
  (`not_configured` | `configured_ok` | `configured_failed` |
  `package_unavailable`) und `severity` (`healthy` | `degraded` | `critical`).
- **`record_otel_setup_outcome()`** wird von `setup_telemetry` auf allen
  drei Pfaden aufgerufen (no-endpoint, success, failure) — RULE-11 silent-
  failure-Gap geschlossen.
- **`/health`-Endpoint** spiegelt OTel-Severity-Vocabulary statt hardcoded
  `"ok"`. DEGRADED returns HTTP 200 (liveness).
- 13 Unit-Tests (`test_observability_health.py`) decken T1–T5 ab.

### Metriken
- **Prometheus-kompatible LLM-Metriken** in `core/llm/metrics.py`: Requests,
  Tokens, Cache, Duration, Retries, Cost Estimates.
- **Health Endpoint** (`/health`) mit OTel-Verfügbarkeitsstatus (severity)
  und Migrationsversion.
- Kein eigenständiger Metriken-Exporter konfiguriert; OTLP-Exporter sendet
  nur Traces. Metriken sind in-process via `Counter`/`Histogram` verfügbar,
  aber nicht aktiv nach außen exportiert.

### Logs
- **structlog** breit eingesetzt; JSON-Output in Produktion.
- **RequestLoggingMiddleware** bindet Request-/Trace-Context für structlog.
- Logs sind strukturiert und enthalten keine API-Keys/Secrets.
- Privacy-Safe Fehlerattribute: `NARRARE_OTEL_INCLUDE_CONTENT=false` in
  Produktion verhindert Prompt-/User-Prose-Leaks.

### Trace-Kette (aktuell dokumentierter Stand)
```
HTTP Request
  → FastAPI OTel Instrumentation (span)
  → RequestLoggingMiddleware (structlog context)
  → Service Layer (active OTel context)
  → Pydantic-AI Agent/Model/Tool spans (native OTel)
  → SSE: enrich_sse_data() adds x_trace_id/x_span_id to events
  → Integrationstests validieren die Korrelation (test_*_trace_propagation.py)
```

### Operations
- **Startup-Migration** automatisch via `lifespan.py`; Migration-Failure
  verhindert App-Start.
- **Health Check** in CI und Docker Compose konfiguriert (`/health` auf Port
  8000).
- **Docker Compose Release** mit `service_healthy`-Conditions und
  `restart: unless-stopped`.
- **pgBouncer-Overlay** in `docker-compose.prod.yml` für Small-Self-Hosted.

### Offene Punkte
- **Memory/Embedding-Spans** nicht als durchgängige Trace-Kette dokumentiert
  (AUFG-05-03 `covered_by_existing_aufg`; Trace-Correlation-Integrationstests
  decken HTTP→SSE, aber nicht Memory/Embedding-Boundary explizit).
- **Metriken-Exporter** nicht operationalisiert (in-process Metriken
  vorhanden, aber kein OTLP-Metrik-Export konfiguriert). Kein Release-Blocker
  (ADR-031 local-first). (AE-05-04)

---

## 5. Gesamtbewertung des Projekts

> Fassung der Erkenntnisse aus allen Reviews 00–04 (Stand 2026-06-29).

### Stärken des Projekts

1. **Herausragende Architektur-Governance:** 23 RULE-XX-Regeln (inkl. RULE-23),
   automatisierte Architektur-Checks in CI (25+ Gates), Exception-Baseline
   mit maschineller pyproject↔CONSTRAINTS-Synchronisation, ADR-getriebene
   Entscheidungen (56+ ADRs), Contract-first-Muster und ratcheted Governance
   für Schuldenabbau. Das AUFG-Registry mit 8 Lifecycle-States (open →
   resolved/accepted_risk/accepted_enhancement) ist industry-leading für ein
   Projekt dieser Größe.

2. **Modernster Tech-Stack durchgehend konsistent:** Python 3.14, FastAPI,
   uv workspace, pyright strict (0 Errors), Next.js 16, React 19, TipTap v3,
   Tailwind v4, Vitest 4, pnpm 11.5.2 (Dockerfile/DevContainer/CI/Root-Pin
   synchron), Docker BuildKit. Kein veraltetes Tool im Stack; alle Versionen
   sind aktuell und konsistent gepinnt.

3. **Massiv gewachsene und reife Testbasis:** 9.043 gesammelte Tests (Backend),
   2.287 Frontend-Tests, 88.94% Backend-Coverage (global 80% blockierend +
   module ratchet), Service-Test-Gap-Check grün, Fake-Conformance
   institutionalisiert, 9 Pydantic-Eval-Suites (Smoke in PR-CI, Runtime
   nightly). Trace-Propagation-Integrationstests für Observability.

4. **Ausgereifte AI-Infrastruktur:** 26 NarrareAgents mit Capabilities
   (ADR-026), Invocation-Pipeline (ADR-038–042), Output-Validatoren für alle
   strukturierten Agents (ADR-035), PromptComposer-Cascade, ModelRegistry,
   Memory/mem0 mit Graceful-Degradation, SSE-Streaming mit
   `useAIOperation`-Primitive (ADR-043, 17 Operationen, 14 compliant),
   `AIAnnotation`-Mark-System, `GhostText`-Dekorationen, Slash-Commands.
   Prompt-Governance mit 48 validierten System-Prompts, Route-Table als SSOT.

5. **Professionelle Release-Pipeline:** Release Please + Docker Multi-Stage-
   Build + GHCR + SBOM (CycloneDX + requirements.txt) + Release-Bundle mit
   Verification-README. CI-Gate-Audit-Tabelle in `ci.yml` ist vorbildlich
   dokumentiert. pnpm-Versionen konsistent gesichert durch CI-Gate.

6. **Starke Security-Grundlage (sehr stark verbessert seit letztem Audit):**
   httpOnly Refresh Cookies, in-memory Access Tokens, Fernet-verschlüsselte
   API-Keys, restriktive CI-Permissions (`contents: read`), Bandit +
   pip-audit blocking in CI, **Gitleaks Secret-Scanning blocking**
   (AUFG-05-09 resolved), **5 Rate-Limiter für AI-/SSE-/WebSocket-Endpoints**
   (AUFG-05-12 resolved), **OriginValidationMiddleware CSRF defense-in-depth**
   (AUFG-05-13 resolved), production-safe OTel-Content-Capture-Defaults,
   CORS empty in production. 4 dokumentierte Accepted Risks mit Owner +
   Review-Trigger.

7. **Erstklassige Developer-Dokumentation & DX:** Ein-Befehl-Onboarding
   (`just dev-setup`), 35 extrahierte Kontextdateien in `.opencode/`,
   27 installierte Skills, 6 spezialisierte Subagents, `AGENTS.md` als
   Orchestrator-Guide, DevContainer ADR-029-konform mit Digest-Locked
   Features, justfile mit 607 Zeilen vollständiger Befehlsoberfläche.

8. **Observability mit Health-Severity-Policy:** OTel-only Tracing mit
   `record_otel_setup_outcome()` (RULE-11-Konform), `/health`-Endpoint
  reflektiert severity vocabulary, Trace-Correlation-Integrationstests,
  structlog JSON-Output, Prometheus-kompatible in-process LLM-Metriken.

### Schwächen & Risiken (priorisiert nach Dringlichkeit)

1. **Aktuelle CI-Blocker (Hoch, sofort):** `check_module_coverage.py --fail`
   regressiert für Prompt-Modul (93.4% < Baseline 97.1%) und
   `check-testid.ts --fail` ist rot für `StyleVariantPicker.tsx` wegen
   Lookahead-Heuristik. Diese blocken den `test-unit`- bzw. `frontend`-CI-Pfad
   und müssen vor Merge behoben werden (AUFG-02-01, AUFG-02-02).

2. **Retry-Settings als mögliche false controls (Hoch):** `retry_max_attempts`
   und `retry_base_delay` sind exposed/resolved und in der Config-Matrix als
   adopted geführt, aber `with_retry` hat laut Graph nur Test-Caller — kein
   Produktions-Consumer gefunden. RULE-18b verlangt Runtime-Consumer +
   Effect-Evidence pro material setting (AUFG-01-01).

3. **TECH_STACK.md SSOT-Drift (Hoch):** Die autoritative Technologie-Doku
   hinkt pyproject.toml deutlich hinterher: pydantic-ai 1.93 vs. 2.0.0,
   mem0 1.0 vs. 2.0.10, fastapi-limiter aktiv vs. pyrate-limiter direkt,
   9 pre-commit hooks vs. 27, GLM-5.1 vs. GLM-5.2. Neueinsteiger und
   AI-Agenten treffen Fehlannahmen (AUFG-04-08).

4. **Adoption-/Health-Semantik-Drift (Mittel):** `CURRENT_STATE.md` und
   Feature-Index führen `character_voice` teils noch als governed debt,
   während `check-adoption` runtime ✅ adopted ✅ meldet. `check-health`
   bewertet Feature Adoption mit 0.50 wegen 121 baseline items, obwohl
   `check-adoption` nur noch 1 current item meldet. Governance-Konsistenz
   muss geklärt werden (AUFG-01-02). — Hinweis: AUFG-01-07/AUFG-03-05
   aus dem vorherigen Zyklus sind resolved, aber die Reviews 01/02
   identifizieren frische Drift-Punkte.

5. **Zentrale Editor-/Writing-Hotspots (Mittel):** `TipTapEditorController.ts`
   ist auf 400 Zeilen gewachsen (Graph-Degree 117); `WritingPipeline.generate`
   ist 206 Zeilen. Keine aktuellen RULE-04-Verstöße (Gate klassifiziert nach
   Dateiname, AUFG-03-04), aber zentrale Blast-Radius-Knoten vor weiterer
   Feature-Anlagerung (AUFG-01-03, AUFG-03-04).

6. **Nutzerfreundliche Distribution (Niedrig-Mittelfristig):** Docker-only
   Self-Hosting für kreative Schreiber ist eine hohe Einstiegshürde. Kein
   Installer, keine Desktop-App. Q-011 bleibt offen (AE-05-02
   accepted_enhancement).

7. **Frontend-Test-Laufzeit & React-Warnings (Mittel):** `pnpm test` läuft
   181.98s (CI warning-only Schwellwert 130s) und produziert viele React-
   `act(...)`/controlled-input-Warnings. Kein funktionaler Failure, aber
   DX-/CI-Minuten-Regression (AUFG-02-03).

8. **Dokumentationsdrift in abgeleiteten Kontextdateien (Mittel):** 507 Doc-
   Drift-Warnungen in `check-governance`. Extrahierte Kontextdateien
   (`lookup/*`, `guides/deployment.md`, `processes/quality-gates.md`) sind
   stellenweise deutlich hinter Code/CI/pyproject.toml zurückgeblieben.
   Überschneidet mit AUFG-02-04, AUFG-04-08, AUFG-04-09, AUFG-04-11.

### Bewertungs-Übersicht

| Bereich | Bewertung | Wichtigster Handlungsbedarf |
|---|---|---|
| Architektur & Code-Qualität | ⭐⭐⭐⭐ | Retry-Settings-Wirkung belegen, Adoption-Semantik klären, Editor-/Writing-Hotspots modularisieren |
| Testing & CI/CD | ⭐⭐⭐ | Prompt-Modul-Coverage-Ratchet + Komponenten-Marker-Checker (CI-Blocker), Frontend-Performance |
| AI-Features & Prompting | ⭐⭐⭐⭐⭐ | Writing-Interview-Agent-Pfad, KB-Assist-Fallback-Verhärtung, File-Size-Gate-Hook-Klassifikation |
| Developer Experience | ⭐⭐⭐⭐ | TECH_STACK-/CURRENT_STATE-/Lookup-Drift, Layer-AGENTS.md aktualisieren |
| Release & Packaging | ⭐⭐⭐⭐ | Rollback-Doku, Nicht-Techniker-Distribution bleibt langfristig offen |
| Security & Privacy | ⭐⭐⭐⭐ | Accepted Risks (in-memory rate limiting, no double-submit CSRF) sind dokumentiert und Review-getriggert |
| Observability & Operations | ⭐⭐⭐⭐ | Memory/Embedding-Spans erweitern, Metriken-Exporter operationalisieren (mittelfristig) |
| **Gesamt** | **⭐⭐⭐⭐** | CI-Blocker lösen, Retry-Settings belegen, SSOT-Drift beheben |

**Gesamtbewertung:** ⭐⭐⭐⭐
**Vorherige Bewertung:** ⭐⭐⭐½ | **Trend:** ↗️ Besser
**Fazit:** Narrare hat seit dem letzten Audit substantielle Fortschritte gemacht.
Die Security-Position ist von „solide Grundabsicherung mit offenen Rate-Limiting-/
CSRF-/Secret-Scanning-Punkten" auf „umfassend abgesichert mit dokumentierten
Accepted Risks" gestiegen: 5 Rate-Limiter, OriginValidationMiddleware, Gitleaks,
OTel-Health-Severity-Policy — alle CI-blocking. Die Testbasis ist von ~4.273 auf
9.043+2.287 Tests gewachsen, Coverage bei 88.94%, Health 0.88–0.93 HEALTHY, alle
alten AUFG-05-01 bis AUFG-05-14 sind resolved. Die Release-Pipeline produziert
verifizierbare SBOMs und ein ausführliches Bundle-README. Die Architektur-
Governance mit 23 Regeln, 56+ ADRs, maschineller Exception-Synchronisation und
ratcheted Governance-Health ist bemerkenswert reif. Offen bleiben vor allem die
aktuellen CI-Blocker (Prompt-Modul-Coverage-Regression, Komponenten-Marker-
Checker), die Retry-Settings-Runtime-Wirkung, die TECH_STACK.md-SSOT-Drift und
die zentralen Editor-/Writing-Hotspots. Das Projekt hat das Niveau von „gut mit
gezieltem Optimierungsbedarf" auf „sehr gut mit diszipliniert befolgtem
Governance-Lifecycle" gehoben. Der wichtigste nächste Schritt ist die Behebung
der zwei CI-Blocker, damit der Merge-Pfad wieder grün ist.

---

## 6. Roadmap-Empfehlung

> Priorisierte Liste aller Aufgaben aus den Reviews 01–05 nach Dringlichkeit.
> Alte AUFG-05-01 bis AUFG-05-14 sind resolved/covered und nicht erneut
> aufgeführt. Accepted Enhancements (AE-05-XX) und Accepted Risks (AR-05-XX)
> erscheinen unter Langfristig.

### Sofort (nächste 1–2 Wochen)

- **[AUFG-02-01]** Prompt-Modul-Coverage-Ratchet-Regression beheben (Hoch, CI-
  Blocker — `check_module_coverage.py --fail` rot für Prompts 93.4% < 97.1%)
- **[AUFG-02-02]** Komponenten-Marker-Checker robust gegen mehrzeilige JSX-
  Attribute machen (Hoch, CI-Blocker — `check-testid.ts --fail` rot wegen
  `LOOKAHEAD = 3`-Heuristik für `StyleVariantPicker.tsx`)

### Kurzfristig (nächste 4–6 Wochen)

- **[AUFG-01-01]** Retry-Settings auf echte Runtime-Wirkung prüfen und
  governance-sicher klassifizieren (Hoch — RULE-18b Effect Integrity)
- **[AUFG-04-08]** TECH_STACK.md SSOT-Versionen mit pyproject.toml
  synchronisieren (Hoch — pydantic-ai 1.x vs 2.x, fastapi-limiter vs
  pyrate-limiter, 9 vs 27 pre-commit hooks)
- **[AUFG-01-02]** `character_voice` Adoption-Status und Health-Baseline
  synchronisieren (Mittel — Docs vs Checker-Semantik-Drift)
- **[AUFG-02-03]** Frontend-Vitest-Laufzeit und React-Test-Warnings
  reduzieren (Mittel — 182s > 130s warning-only)
- **[AUFG-02-04]** Testing-/Deployment-Dokumentation gegen aktuelle CI
  synchronisieren (Mittel — Vitest 3→4, 60→80% Coverage, 7→9 CI-Jobs)
- **[AUFG-03-01]** Writing-Interview-Pfad von `ModelRegistry.run()` auf
  `NarrareAgent` umstellen (Mittel — ADR-026 Capability-Injection)
- **[AUFG-03-02]** KB-Assist Invocation-Fallback semantisch verhärten oder
  als gouvernierte Ausnahme klassifizieren (Mittel — ADR-048)
- **[AUFG-03-04]** Frontend-File-Size-Gate Hook-Klassifikation für ohne-
  `use`-Präfix benannte Controller-Dateien (Mittel — `TipTapEditorController`
  = 400 Zeilen als typescript statt hook klassifiziert)
- **[AUFG-04-09]** Layer-AGENTS.md mit aktueller Architektur synchronisieren
  (Mittel — 6 vs 26 Agents, MagicMock vs Fake, `Base.metadata.create_all`)
- **[AUFG-04-11]** Lookup-Kontextdateien synchronisieren oder automatisch aus
  SSOT generieren (Mittel — 507 Doc-Drift-Warnungen)

### Mittelfristig (nächste 3–6 Monate)

- **[AUFG-01-03]** Editor-/Writing-Hotspots vor weiterer Feature-Anlagerung
  modularisieren (Mittel — `TipTapEditorController` 400 Zeilen degree 117,
  `WritingPipeline.generate` 206 Zeilen)
- **[AUFG-03-03]** A2A/MCP-Feature-Dateien: Status- und Pfadgenauigkeit
  korrigieren (Niedrig — Phantom-Pfade, `in progress` ohne Code)
- **[AUFG-04-10]** ADR-Dateinamen-Konvention vereinheitlichen (Niedrig —
  7 von 57 Dateien ohne `ADR-`-Präfix)
- **[AUFG-05-06]** Rollback-Prozess dokumentieren (Niedrig — aktuell nur
  implizit via Docker-Image-Pull)
- Observability: Memory/Embedding-Spans erweitern, Metriken-Exporter
  operationalisieren (mittelfristig, AE-05-04 äquivalent)

### Langfristig / Optional

- **AE-05-01** Cosign/SLSA Release Provenance Hardening (accepted_enhancement
  — vor Public Release oder Supply-Chain-Anforderung)
- **AE-05-02** Managed Hosting Strategy Exploration (accepted_enhancement —
  Q-011, vor aktiver Nicht-Entwickler-Onboarding-Phase)
- **AE-05-03** CORS Origins als Settings-Feld (accepted_enhancement — bei
  Deployment-Szenario mit custom Origins)
- **AR-05-02** In-Memory Rate-Limiting (accepted_risk — bei Multi-Instance-
  Deployment → Redis-basiert)
- MCP/A2A als geplante Adapter konkretisieren (gated auf Q-001/Q-002
  Entscheidung)

---

## 7. Weitere Anmerkungen

- **Audit ohne Netzwerk-/Secret-abhängige Tests.** Pydantic-Eval Runtime-Suites
  wurden nicht ausgeführt, weil sie echte API Keys benötigen. Smoke-Evals
  wurden in Review 02 grün bestätigt.
- **Docker Build/Release Build wurde nicht ausgeführt**, da teuer und
  potentiell netzwerkabhängig. Dockerfile-Struktur wurde read-only inspiziert.
- **Keine destruktiven Commands ausgeführt; keine Commits erstellt; kein
  `--no-verify`.**
- **Code-Graph-MCP** war in dieser Session stabil (`get_minimal_context` →
  26.084 Nodes). Graph-basierte Befunde sind reproduzierbar.
- **AUFG-Registry als Governance-SSOT:** Das `aufg-registry.md` mit 8
  Lifecycle-States, Acceptance Criteria, Definition of Done und Exit Evidence
  ist ein herausragendes Governance-Instrument. Die maschinelle Durchsetzung
  via `check_governance_health.py` (ADR-047, CI-blocking) macht Review-Findings
  zu actionable Lifecycle-Einträgen statt Prosa-only-Notizen.
- **Security-Verbesserungen seit letztem Audit (substanziell):** Rate-Limiting
  (5 Limiters), CSRF OriginValidationMiddleware, Gitleaks Secret-Scanning,
  OTel-Health-Severity-Policy mit `/health`-Integration — alle mit Tests und
  CI-blocking. Das hebt die Security-Bewertung von ⭐⭐⭐½ auf ⭐⭐⭐⭐.
- **Trend-Bewertung** (⭐⭐⭐½ → ⭐⭐⭐⭐) reflektiert die substantiellen
  Verbesserungen: Security-Position massiv gestärkt, Observability-Health-
  Severity implementiert, Trace-Correlation-Integrationstests vorhanden,
  alle 14 alten AUFG-05 resolved, Release-pnpm-Drift behoben, Coverage 88.94%,
  pyright 0 Errors.

---

## Erledigte / ersetzte Altaufgaben aus vorherigem Review

- **[AUFG-05-01] Release-Artefakte verifizierbar machen:** ✅ Resolved. SBOM
  (CycloneDX + requirements.txt) wird automatisch generiert und veröffentlicht.
- **[AUFG-05-02] CI-Permissions weiter minimieren:** ✅ Resolved. Global
  `contents: read`; Release scoped auf `publish`-Job.
- **[AUFG-05-03] Operations-Trace-Kette mit Integrationstest:** ✅ Covered.
  Trace-Propagation-Integrationstests vorhanden
  (`test_trace_propagation.py`, `test_sse_trace_propagation.py`).
- **[AUFG-05-04] pnpm-Version im Dockerfile:** ✅ Resolved. `Dockerfile:53`
  nutzt `ARG PNPM_VERSION=11.5.2`.
- **[AUFG-05-07] CORS-/Rate-Limiting-Security-Audit:** ✅ Resolved. Security-
  Audit dokumentiert; Rate-Limiting (AUFG-05-12), CORS (AE-05-03).
- **[AUFG-05-08] CSRF-Strategie:** ✅ Resolved. CSRF-Strategy dokumentiert;
  OriginValidationMiddleware (AUFG-05-13) + AR-05-05 (accepted risk).
- **[AUFG-05-09] Secret-Scanning als CI-Gate:** ✅ Resolved. Gitleaks v8.30.1
  blocking in CI.
- **[AUFG-05-10] OTel-Health-Severity-Semantik:** ✅ Resolved. Policy
  dokumentiert; Implementierung in AUFG-05-14.
- **[AUFG-05-11] CURRENT_STATE Volatile Stats:** ✅ Resolved. 14 volatile
  counts entfernt; `check_current_state_facts.py` enforce policy.
- **[AUFG-05-12] Rate-Limiting für AI-Endpoints:** ✅ Resolved. 5 Limiters
  + WebSocket; 14 Unit-Tests; 17 Router verdrahtet.
- **[AUFG-05-13] CSRF Origin/Referer Validation:** ✅ Resolved.
  OriginValidationMiddleware + WebSocket-Check; 12 Unit-Tests.
- **[AUFG-05-14] OTel-Health-Severity Implementierung:** ✅ Resolved.
  `get_observability_status()` mit severity; `/health` reflektiert state;
  13 Unit-Tests.
- **[AUFG-01-04] useExtractionPhase RULE-04:** ✅ Resolved (vorheriger Zyklus).
- **[AUFG-01-05] NameGenerator AI-UX-Test:** ✅ Resolved (vorheriger Zyklus).
- **[AUFG-02-08] CI-Blocker aus Review 01:** ✅ Resolved (vorheriger Zyklus).
- **[AUFG-02-02 alt] Coverage-Gate auf RULE-10:** ✅ Resolved (vorheriger
  Zyklus). Hinweis: AUFG-02-02 wurde im neuen Zyklus für den Komponenten-
  Marker-Checker wiederverwendet.

## Aufgaben

> Alle Release-/Security-/Observability-relevanten Findings aus diesem Review
> sind bereits durch AUFG-05-01 bis AUFG-05-14 (resolved), AE-05-01/02/03
> (accepted_enhancement) und AR-05-02/03/04/05 (accepted_risk) im
> `aufg-registry.md` abgedeckt. Es entstehen keine neuen AUFG-05-XX aus diesem
> Review — die Release-/Security-/Observability-Lage ist professionell
> abgesichert. Der verbleibende Rollback-Doku-Punkt wird als AUFG-05-06
> fortgeführt (mittelfristig, Priorität Niedrig).

### [AUFG-05-06] Rollback-Prozess dokumentieren
**Priorität:** Niedrig
**Bereich:** Release / Operations
**Kontext:** Aktuell ist Rollback nur implizit über `docker compose pull
  <alte-version>` möglich. Ein dokumentierter Rollback-Prozess würde Self-
  Hostern Sicherheit geben. Die Release-Pipeline produziert versionierte
  Docker-Tags (SemVer + `latest`) und unveränderliche Digests — die
  technische Basis für Rollback ist vorhanden, aber nicht dokumentiert.
**Akzeptanzkriterien:**
- [ ] Deployment Guide enthält einen Rollback-Abschnitt mit konkreten
      Befehlen (Pull alte Version, `docker compose up -d`).
- [ ] Rollback-Strategie deckt Datenbank-Migrationen ab (Alembic `downgrade`
      oder Version-Pinning — mit Hinweis auf Migrations-Risiken bei
      Schema-Änderungen, die nicht rückgängig zu machen sind).
- [ ] Mindestens ein Szenario dokumentiert: Rollback auf vorherige
      Minor-Version.
- [ ] Hinweis auf Digest-basiertes Pullen für unveränderliche Referenzen.
**Geschätzter Aufwand:** S
