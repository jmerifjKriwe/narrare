# Review 05 – Release, Packaging & Gesamtbewertung

> **Voraussetzung:** Lies zuerst `_audit/results/technical-review/review-00-kontext.md` und stelle sicher,
> dass er vollständig ausgefüllt ist. Referenziere die dort dokumentierten Pfade und den Tech-Stack.
> Sollte `_audit/results/technical-review/review-00-kontext.md` nicht existieren, erstelle ihn
> zunächst auf Basis von `_audit/review-prompts/technical-review-prompts/review-00-kontext.md`
>
> **Routing:** Führe diesen Prompt mit `NarrarePlatformSpecialist` aus.
>
> **Ausgabe:** Schreibe das Ergebnis nach `_audit/results/technical-review/review-05-release.md`.
>
> **Hinweis:** PyPI-Publishing ist absichtlich nicht integriert und soll hier
> NICHT als Aufgabe oder Empfehlung erscheinen.

---

> **Methodik-Hinweis:** Evidenz für §1–§4 wurde primär via Read/Glob/Grep auf
> `.github/workflows/`, `Dockerfile`, `docker-compose.release.yml`,
> `scripts/entrypoint.sh`, `release-please-config.json`, `apps/api/narrare/auth/`,
> `apps/api/narrare/_app/{middleware,observability,telemetry,lifespan,settings_model}.py`,
> `.env.example` sowie `docs/development/{deployment-guide,observability-guide}.md`
> erhoben. Code-Struktur-Aussagen wurden am `code-review-graph` verifiziert
> (26.940 Knoten, 0 Embeddings → keine semantic search; `query_graph` + Read
> genutzt). `codebase-memory-mcp` war laut Vorgabe nicht indiziert. Alle
> Quotes sind live aus dem Repository verifiziert.
>
> **Wichtige Konventions-Beobachtung:** Das Template schlägt `AUFG-05-01, …`
> vor, doch ein **vorangegangenes (archiviertes) Security-Audit**
> (`docs/archive/architecture/governance/security-audit-cors-rate-limiting.md`)
> hat die IDs **AUFG-05-07, AUFG-05-12, AUFG-05-13, AUFG-05-14** bereits
> vergeben und (laut `CURRENT_STATE.md` + Inline-Kommentaren im Code) auch
> abgearbeitet. Um keine Kollision mit diesen realen, abgeschlossenen Tasks
> zu erzeugen, beginnen die *neuen* Aufgaben dieses Reviews bei
> **AUFG-05-15**. Dies ist als Diskrepanz in §7 dokumentiert.

---

## 1. Release- & Packaging-Prozess

**Analysiere:**

Der Release-Prozess ist **vollständig automatisiert** über Conventional Commits
+ [release-please](https://github.com/googleapis/release-please) und in
`docs/development/deployment-guide.md` (§Release Process, §Self-Hosted
Deployment) dokumentiert.

- **Wie wird ein Release erstellt?** Merge nach `main` triggert
  `.github/workflows/release-please.yml`. release-please parst die
  Conventional-Commits (`feat:`/`fix:`/`perf:`/…), erzeugt einen
  „chore: release vX.Y.Z"-Release-PR (inkrementiert die Version in
  `.release-please-manifest.json`, schreibt `CHANGELOG.md`), und nach Merge
  dieses PRs erstellt es den GitHub-Release-Tag. Konfiguration in
  `release-please-config.json` (`release-type: python`,
  `include-component-in-tag: false`, benannte changelog-sections).
  `scripts/check_version_consistency.py` existiert zusätzlich als
  Versions-Drift-Prüfer.
- **Welche Artefakte werden erzeugt?** Der `publish`-Job (läuft nur bei
  tatsächlich erstelltem Release) baut via `docker/build-push-action@v7` das
  **Single-Image** (`Dockerfile`, multi-stage: uv Python-Dependencies +
  Next.js-standalone-Build + `python:3.14-slim`-Runtime), das **gleichzeitig**
  FastAPI (uvicorn, intern 127.0.0.1:8000) und Next.js (standalone, extern
  0.0.0.0:3000) ausliefert (`scripts/entrypoint.sh` mit Signal-Trap für beide
  Prozesse). Push nach GHCR mit **zwei Tags** (`:<version>` + `:latest`) und
  dem **immutable Digest** (im GitHub-Release-Summary gelistet). Zusätzlich
  entsteht ein **Release-Bundle-ZIP** (`narrare-<version>.zip`) bestehend aus
  `docker-compose.yml` (Kopie von `docker-compose.release.yml`),
  `.env.example`, `requirements.txt` (via `uv export`) und einer
  **CycloneDX-SBOM** (`sbom.cyclonedx.json`, via Syft, Fallback Docker-SBOM).
  Das Bundle-README ist vorbildlich detailliert (Digest-Pinning, SBOM-Scan mit
  Grype/Trivy, Cosign-Verifikations-Pfad).
- **Semantic Versioning?** Ja, konsequent. release-please leitet Major/Minor/
  Patch aus Conventional-Commits ab; `CHANGELOG.md` hält „Keep a Changelog" +
  „Semantic Versioning" im Header explizit fest.
- **Automatisierter Release-Workflow?** Ja — der gesamte Pfad (Version-Bump →
  CHANGELOG → GitHub-Release → Docker-Build → GHCR-Push → SBOM →
  Bundle-Upload) läuft ohne manuellen Eingriff in einem GHA-Job.
- **CHANGELOG automatisch oder manuell?** **Automatisch** via release-please
  (Header: „⚠️ Auto-generated … DO NOT edit manually").
- **Artefakte signiert oder verifizierbar?** Teilweise. GitHub-Release-Artefakte
  sind automatisch durch GitHub signiert (high-trust). Das Docker-Image ist
  **nicht** kryptographisch signiert — das Bundle-README führt Cosign-Keyless-
  Signing explizit als **„Optional: Future Enhancement"** (L235–248), ist also
  *geplant*, aber **nicht implementiert**. Verifizierbarkeit erfolgt über
  Digest-Pinning (operator-seitig).
- **Wie wird das Tool verteilt? Aktuell nutzerfreundlich/zeitgemäß?** Via
  GHCR-Docker-Image + Release-Bundle-ZIP. Docker-First ist für eine Multi-
  Service-App (FastAPI + Next.js + PostgreSQL+pgvector + Redis) sachgerecht.
  Es gibt **keine** nativen Binaries, Installer oder Paketmanager-Integration
  (bewusst kein PyPI gemäß Prompt-Header; siehe §2 zu Distribution-Friction).

**Checkliste Release-Qualität:**
- [x] Versionierung klar und automatisiert (`bump2version`, `tbump`, commitizen, …)
      — via release-please + Conventional Commits (auto-bump).
- [x] Release-Notes automatisch aus Commit-History generiert — release-please
      schreibt `CHANGELOG.md` aus Conventional-Commits.
- [ ] Binaries / Installer für alle Zielplattformen — **nicht vorhanden**;
      Docker-Only (siehe §2). Bewusste Entscheidung, behindert aber nicht-
      technische Nutzer (Q-011 offen).
- [x] Docker-Image vorhanden und im Registry — GHCR, `:version`+`:latest`+
      digest.
- [x] Release-Prozess in CI komplett automatisiert — `release-please.yml`.
- [x] Rollback-Prozess dokumentiert — deployment-guide.md §Rollback (Image-
      Replacement + Alembic-Migrations-Caveat: `alembic upgrade head` läuft
      beim Startup automatisch; schema-übergreifender Rollback braucht
      expliziten Downgrade-Schritt).

**Bewertung:** ⭐⭐⭐⭐⭐ `⭐⭐⭐⭐`
**Befunde:** Vorhanden, durchgängig automatisiert und dokumentiert: release-please
erzeugt SemVer-Tags + auto-CHANGELOG aus Conventional-Commits, der `publish`-Job
baut das Single-Image (FastAPI+Next.js, multi-stage), pusht mit `:version`+
`:latest`+digest nach GHCR, generiert CycloneDX-SBOM (Syft) und ein Release-
Bundle-ZIP. Rollback-Prozess ist dokumentiert (Image-Tag-Replace +
Migrations-Caveat). Abzüge: (1) **Docker-Only-Distribution** (keine nativen
Installer/Binaries — siehe §2 / Q-011); (2) SBOM-Generierung ist
**best-effort** (`continue-on-error: true` in `release-please.yml` L84 — kann
still ausfallen, ohne den Release zu blockieren); (3) **Cosign-Image-Signing**
ist explizit nur „Future Enhancement" (L235), nicht implementiert — der
einzige Kryptographie-Pfad ist GitHub's automatische Release-Artefakt-Signatur;
(4) keine automatisierte Rollback-Variante (nur manuelle Schritte). Kein
akuter Blocker, aber Supply-Chain-Härte hinter dem Möglichen.

---

## 2. Nutzerfreundliche Bereitstellung

**Analysiere aus Nutzerperspektive:**

Der dokumentierte Pfad für Endnutzer (deployment-guide.md §Quick Start (End User))
lautet:

1. Release-Bundle herunterladen und entpacken (`unzip narrare-0.2.0.zip`)
2. `.env.example` → `.env` kopieren und **vier Variablen** setzen:
   `SECRET_KEY` (via `python -c "import secrets; …"`), `NARRARE_ENCRYPTION_KEY`
   (via `python -c "from cryptography.fernet import Fernet; …"`), Datenbank-/
   Redis-URLs auf Docker-Service-Namen (`@postgres:5432/`, `redis://redis:…`),
   mindestens einen AI-Provider-Key
3. **`docker login ghcr.io`** (Image ist standardmäßig *private*, erbt Repo-
   Visibility — deployment-guide L406)
4. `docker compose up -d`
5. Browser auf `http://localhost:3000`

- **Wie einfach ist die Installation für einen nicht-technischen Nutzer?**
  **Nicht trivial.** Vorausgesetzt werden: Docker Engine 24+ mit Compose v2,
  Kommandozeilenbedienung, manuelles Editieren einer `.env`-Datei, Generierung
  zweier kryptographischer Keys via Python-One-Liner, GHCR-Auth. Für einen
  technischen Self-Hoster ist das Standard; für den in `docs/reference/
  project-vision.md` anvisierten Romanautor („local-first, vollständig
  anpassbar") ist das eine signifikante Hürde. Q-011 („Distributions-Strategie
  für nicht-technische Nutzer") ist explizit 🟡 **Open** — das Projekt kennt
  die Lücke selbst.
- **One-Liner-Installer?** **Nein.** Es gibt kein `curl … | bash`-Setup, kein
  Guided-Installer-Skript, das `.env` interaktiv befüllt. (`just dev-setup`
  existiert, ist aber ein *Developer*-Setup, kein Endnutzer-Pfad und erfordert
  die volle Dev-Toolchain.)
- **Abhängigkeiten automatisch verwaltet?** **Teilweise.** Docker Compose
  zieht Postgres (`pgvector/pgvector:pg17`) + Redis (`redis:8-alpine`)
  automatisch; der Narrare-Container bringt API+Frontend gebündelt. **Aber:**
  Docker selbst, GHCR-Login und AI-Provider-Key sind manuelle Prämissen.
- **Update-Mechanismus?** **Ja, sauber:** `docker compose pull && docker
  compose up -d` (deployment-guide §Updates). Migrationen laufen beim Startup
  automatisch (`lifespan.py` → `_run_pending_migrations()`). Das ist der am
  besten gelungene Teil der Endnutzer-Experience.
- **Erste Nutzung nach Installation intuitiv?** In-App gibt es einen Setup-
  Wizard (`app/(auth)/` → `/wizard`, 3-Shell-Taxonomie aus ui-principles.md);
  die *Self-Host*-Initiierung davor ist aber reine CLI-Arbeit. Kein Onboarding
  für „wie komme ich überhaupt zum Wizard".

**Vergleich mit zeitgemäßen Alternativen:**

| Alternative | Fit für Narrare? | Begründung |
|---|---|---|
| `pipx install narrare` / PyPI | **Nein** (bewusst nicht vorgesehen) | Narrare ist eine Multi-Service-App (API+Frontend+DB+Cache+Worker), kein CLI-Tool. PyPI-Publishing ist per Prompt-Header explizit ausgeschlossen. |
| Homebrew Tap | Teilweise | Könnte Docker-Setup wrappen (`brew install narrare` → installiert Docker-Erkennung + `narrare up`), aber nur für macOS/Linux, löst nicht das `.env`-/Key-Problem. |
| winget / Windows-Store | Nein | Windows ohne WSL bricht bereits am bash-basierten `entrypoint.sh`/justfile (siehe review-04 §1). |
| AppImage / Electron-Wrapper | **Nein** | Benötigt externen Postgres+pgvector+Redis-Prozess; Desktop-Wrapper bringt keinen Mehrheit über Docker-Compose. |
| 1-Click-Cloud-Deploy (Railway/Render/Fly) | Mittel | Könnte die `.env`-Reibung reduzieren, widerspricht aber dem „local-first"-Ethos und erfordere Cloud-DB (Kosten). |
| **Verbesserungspotenzial (passt):** Guided-Setup-Skript (`./install.sh` mit interaktivem `.env`-Wizard, Docker-Vorhandenheits-Check, Key-Generierung, optionaler Reverse-Proxy/Hint) ODER eine `narrare`-CLI mit `narrare init/up/update/backup`. Beides kompatibel mit Docker-First und local-first. | — | Größter Hebel für Q-011. |

**Bewertung:** ⭐⭐⭐⭐⭐ `⭐⭐⭐`
**Befunde:** Der Self-Host-Pfad ist **funktional und dokumentiert**, das
Release-Bundle-README ist vorbildlich instruiert (Digest-Pinning, SBOM-Scan,
Cosign-Pfad skizziert). Der Update-Mechanismus (`docker compose pull && up -d`
mit Auto-Migration) ist der stärkste Teil. **Aber für nicht-technische Nutzer
bleibt erhebliche Reibung**: Docker-Prämissen, manuelle `.env`-Bearbeitung,
zwei kryptographische Key-Generierungen, GHCR-Login wegen *private-by-default*-
Image. Es gibt weder einen One-Liner-Installer noch einen interaktiven Guided-
Setup-Skript. Q-011 (Distributions-Strategie) ist 🟡 Open — das Projekt sieht
die Lücke selbst. Für die lokal-first-Architektur ist Docker die richtige Wahl;
der Hebel liegt in *Guided-Friction-Reduktion*, nicht in einem anderen
Paketformat.

---

## 3. Security, Privacy & Compliance

**Analysiere:**

- **Entspricht Auth dem aktuellen Security-Stack (Argon2id, httpOnly Refresh
  Cookie, Access Token nicht in localStorage)?** **Ja, vollständig verifiziert.**
  - `apps/api/narrare/auth/security.py`: Argon2id via `argon2.PasswordHasher`
    mit OWASP-Empfehlungs-Parametern (`time_cost=3`, `memory_cost=65536`=64MB,
    `parallelism=4`, `hash_len=32`, `salt_len=16`). Backward-Kompat mit
    bcrypt (`$2b$`/`$2a$`) + `needs_rehash()` für lazy Migration. HS256-JWT:
    Access-Token 60 min, Refresh-Token 30 d, typ-getagged.
  - `apps/api/narrare/auth/cookie_helpers.py`: Refresh-Token in **httpOnly**
    Cookie (`httponly=True`), `secure=settings.is_production` (HTTPS-only in
    prod), `samesite="lax"` (CSRF-resistent, Top-Level-Navigation erlaubt),
    `path="/api/v1/auth"` (scoped — nur an Auth-Endpoints gesendet). Access-
    Token wird als `Authorization: Bearer …` gesendet, **nicht** in
    localStorage persistiert (Frontend-Proxy `proxy.ts`, review-00).
- **Sind API Keys verschlüsselt gespeichert (`NARRARE_ENCRYPTION_KEY`) und nie
  in Logs/API-Responses sichtbar?** **Ja, dokumentiert und implementiert.**
  Fernet-Verschlüsselung (deployment-guide.md L657 wörtlich: „Keys are never
  logged or returned via API"). `.env.example` warnt: „If this key is lost,
  all user API keys are unrecoverable." `core/shared/crypto.py` verschlüsselt
  vor Persistenz in `user_providers`, entschlüsselt nur bei Provider-
  Instanziierung.
- **Rate Limiting, CORS, CSRF-relevante Cookie-Einstellungen und sichere
  Defaults dokumentiert und umgesetzt?** **Ja, defense-in-depth.**
  - **Rate-Limiting:** `pyrate-limiter` (`>=4.0,<5`) pro Endpoint-Gruppe
    (`apps/api/narrare/_app/rate_limits.py`, z. B. `AI_WRITE_LIMITER`). Laut
    archiviertem Security-Audit wurde **AUFG-05-12** (Rate-Limiting für **alle
    14 AI-/SSE-/WebSocket-Endpoint-Klassen**) als ✅ resolved geschlossen.
  - **CORS:** Dev-spezifischer Origin (`["http://localhost:3000"]`), in prod
    leer (reverse-proxy über Next.js); `allow_credentials=True` bei spezifischer
    Origin (sicher, kein `*`+Credentials).
  - **CSRF:** `OriginValidationMiddleware` (`_app/middleware.py`,
    AUFG-05-13) als Defense-in-Depth neben primärem Bearer-Auth: Safe-Methods
    passieren; State-Change-Methods prüfen Origin → Referer → Bearer-JWT-
    Gültigkeit; configurable trusted origins
    (`NARRARE_CSRF_TRUSTED_ORIGINS`, default `["http://localhost:3000"]`).
  - **Defaults dokumentiert:** deployment-guide.md §Env-Vars listet
    `SECRET_KEY` („change-me…" als Platzhalter mit `just generate-secret`-
    Hinweis), `NARRARE_ENCRYPTION_KEY`, `NARRARE_CSRF_TRUSTED_ORIGINS`,
    Dev-Login-Gating (`DEV_LOGIN_ENABLED=true` nur in dev) sauber.
- **Dependency- und Secret-Scanning in CI (`bandit`, Dependency Audit, keine
  `.env`-Leaks)?** **Ja, mit Lücken.**
  - `gitleaks` (Secret-Scan, `fetch-depth: 0`), `bandit` (SAST),
    `pip-audit` (Dependency-Audit) — alle in CI `security`-Job, blockierend.
  - **Lücken** (bereits in review-02/04 notiert): kein `github/codeql-action`,
    kein `github/dependency-review-action` für PRs (AUFG-02-06), **kein
    Container-Image-Vulnerability-Scan** in CI (Trivy/Grype auf das *gebaute
    Image*, nicht nur auf die SBOM — nur als User-Facing-Kommando im Bundle-
    README). 2 pip-audit-Vuln-Suppressions (`PYSEC-2025-183`,
    `GHSA-rrmf-rvhw-rf47`) sind **unkommentiert** (AUFG-04-10). `.env` ist
    via Gitleaks + `.gitignore` abgedeckt.
- **Wie werden persistierte Memories, Projektinhalte und Exportdaten
  datenschutzfreundlich behandelt?** **Local-first, gut.** Alle Nutzerdaten
  (Manuskripte, KB, Memories via mem0, Embeddings) liegen in der **eigenen**
  PostgreSQL+pgvector-Instanz des Nutzers — keine Cloud-Abhängigkeit außer dem
  LLM-Provider selbst. `NullMemoryClient`-Fallback bei deaktiviertem mem0/
  Embeddings (graceful degradation). KB-Interview-Antworten persistieren in
  der KB-Session des Nutzers. Keine Telemetrie-Phone-Home erkennbar (OTel ist
  Opt-in über `OTEL_EXPORTER_OTLP_ENDPOINT`, default deaktiviert).
- **Key-Rotation-/Backup-Hinweis für `NARRARE_ENCRYPTION_KEY`?** **Dokumentiert,
  aber manuell und ohne Automation.** deployment-guide.md L655: „To rotate:
  generate new key, decrypt all keys with old key, re-encrypt with new key,
  update env var" + „If this key is lost, all user API keys are unrecoverable.
  Store securely and back up." Es gibt **kein Skript** für die Rotation und
  **kein Backup-Mechanismus** über die Operator-Verantwortung hinaus.

**Bewertung:** ⭐⭐⭐⭐⭐ `⭐⭐⭐⭐`
**Befunde:** Solider, moderner Security-Stack vollständig implementiert:
Argon2id (OWASP-Params) + httpOnly/secure/samesite-lax/scoped Refresh-Cookie +
Bearer-Access-Token (nicht localStorage) + CSRF-Defense-in-Depth-Middleware
(AUFG-05-13) + Rate-Limiting auf allen 14 AI/SSE/WS-Klassen (AUFG-05-12) +
Fernet-verschlüsselte API-Keys (never logged/returned, deployment-guide
explizit) + local-first Privacy (pgvector in eigener DB, NullMemoryClient-
Fallback, Opt-in-Telemetrie). CI hat gitleaks+bandit+pip-audit. Abzüge:
(1) **kein Container-Image-Scan** in CI (nur SBOM-as-Asset); (2) **kein
`dependency-review-action`** für PRs (AUFG-02-06); (3) **Cosign-Image-Signing**
ungeplant-implementiert (nur „Future Enhancement", §1); (4) 2 unkommentierte
pip-audit-Suppressions (AUFG-04-10); (5) **Key-Rotation nur manuell** ohne
Automation/Script. Kein akuter Kritischer-Pfad-Defekt, aber die Supply-Chain-
und Operations-Härte ist hinter dem sonstigen Standard.

---

## 4. Observability & Operations

**Analysiere:**

- **Entspricht die Instrumentierung ADR-010 (OpenTelemetry/Langfuse bzw.
  aktueller dokumentierter Stand)?** **Ja — ADR-031 ist der aktuelle Stand.**
  ADR-010 ist **⛔ Superseded by ADR-031** (Local-First OpenTelemetry
  Observability, 2026-06-04, ✅ Phase 1 implemented). Langfuse wurde **entfernt**;
  reines OTel. `apps/api/narrare/_app/telemetry.py::setup_telemetry()`:
  FastAPIInstrumentor + Pydantic-AI-Instrumentation + OTLP-gRPC-Exporter,
  aktiviert nur wenn `OTEL_EXPORTER_OTLP_ENDPOINT` gesetzt. Graceful-
  Degradation (no-op tracer) bei fehlendem Endpoint/Package + health-severity-
  state (`get_observability_status()` mit `healthy`/`degraded`/`critical`,
  AUFG-05-14, ✅ implementiert laut CURRENT_STATE L171). Vollständige
  Doku-Kette in `docs/development/observability-guide.md`.
- **Sind LLM-Aufrufe nach Intent, Modell, Provider, Tokenkosten, Latenz und
  Fehlerursache nachvollziehbar?** **Ja, zweigleisig (structlog + Prometheus).**
  `packages/core/narrare_core/llm/gateway.py` loggt für **sowohl `run()` als
  auch `stream()`** via structlog: `intent` (LLMIntent.value), `model`
  (config.model_id), `provider` (config.provider_name), `tokens`
  (total_tokens), `duration_ms`, `cost_estimate` (USD). Zusätzlich
  `packages/core/narrare_core/llm/metrics.py`: Prometheus-Counters/Histograms
  (`narrare_llm_requests_total`, `narrare_llm_tokens_total`,
  `narrare_llm_request_duration_seconds`, `narrare_llm_cost_usd_total`,
  `narrare_llm_retry_attempts_total`, `narrare_llm_cache_{hit,miss,read,
  creation}_total`) gelabelt mit `intent`/`model`/`provider`. Fehlerursache:
  über structlog-Exception-Logging + `model_registry_*`-Events abdeckbar.
- **Gibt es Trace-/Correlation-IDs über HTTP Request → Service → Agent/LLM →
  SSE-Streaming → Memory/Embedding hinweg?** **Ja, dokumentiert und
  implementiert.** `RequestLoggingMiddleware` (`_app/middleware.py`) bindet
  `request_id` (UUID oder `X-Request-ID`-Header vom Upstream-Proxy),
  `trace_id`, `span_id` via `structlog.contextvars.bind_contextvars`.
  `get_current_trace_context()` (`_app/observability.py`) liefert die OTel-
  IDs; `enrich_sse_data()` merget `x_trace_id`/`x_span_id` in SSE-Event-
  Payloads (Single-Source-of-Truth für Middleware + SSE-Router). Response-
  Header `X-Request-ID` + `X-Trace-ID`. Die Kette HTTP → Service → LLM → SSE
  ist in `observability-guide.md` §4 (Trace Context and SSE) durchgezeichnet.
- **Sind Logs strukturiert, ohne Secrets oder Nutzerinhalte unnötig zu leaken?**
  **Ja.** `structlog` durchgängig (konfiguriert in `_app/logging.py`,
  JSON-Renderer in prod). `NARRARE_OTEL_INCLUDE_CONTENT` (default `false` in
  prod, `true` in dev) steuert, ob Pydantic-AI-Spans Prompt-/Completion-
  Content inkludieren — Produktion scrubbed Content per Default. API-Keys
  werden nie geloggt (§3).
- **Health Checks, Startup-Migration-Logging, operational sinnvolle
  Fehlerdiagnose?** **Ja, vorbildlich.**
  - `/health` (kein Prefix) liefert `{"status": obs["severity"],
    "observability": {...}}` (`metrics/router.py` L32–33) — integriert OTel-
    Health direkt in den Liveness-Check.
  - `/ready` für Readiness; `Dockerfile`-`HEALTHCHECK` auf `/health` (30s
    Interval, 15s start-period).
  - `_app/lifespan.py`: strukturierte Startup-Logs `db_schema_version` (vor
    Migration), `db_migrations_applied` (mit `from`→`to`)/`db_schema_up_to_date`
    (nachher), `narrare_api_starting`/`narrare_api_ready`, sowie
    `db_migration_failed` mit `logger.exception` bei Fehlschlag. Worker-
    Broker-, Event-Bus-, Wiki-Listener-Startup jeweils geloggt.
  - Operational Diagnosis: durchgängig strukturierte Events + Correlation-IDs
    ermöglichen Self-Hosting-Diagnose ohne Application-Log-Scraping-Hacks.

**Beobachtung (kein Defekt, aber Design-Folge):** Da OTel Opt-in ist
(`OTEL_EXPORTER_OTLP_ENDPOINT` default leer → `setup_telemetry` loggt
`otel_disabled_no_endpoint` und returned), hat eine Out-of-the-Box-Installation
**keine persistente Telemetrie** — alle Structlog-Events landen nur im
Container-Stdout. Das ist dem Local-First-Prinzip geschuldet und korrekt, aber
ein Self-Hoster ohne OTel-Collector verliert die Trace-/LLM-Kosten-Persistenz.
Die Prometheus-`/metrics`-Exposed-Behauptung (metrics.py Docstring L7: „exposed
at /metrics by the API") ist im lifespan/telemetry-Setup nicht als Route-
Registrierung verifiziert worden — das wäre ein „documented ≠ implemented"-
Kandidat für AUFG-05-19.

**Bewertung:** ⭐⭐⭐⭐⭐ `⭐⭐⭐⭐`
**Befunde:** ADR-031-konforme, durchgängige Observability-Instrumentierung:
OTel (FastAPI + Pydantic-AI) mit Graceful-Degradation + health-severity-state,
LLM-Aufrufe vollständig observierbar (intent/model/provider/tokens/duration/cost
via structlog **und** Prometheus-Metrics), vollständige Trace-Correlation-
Kette (Request-ID + Trace-ID über HTTP→Service→LLM→SSE, Response-Header,
SSE-Enrichment), Content-Scrubbing in prod via `NARRARE_OTEL_INCLUDE_CONTENT`,
Health-Check mit OTel-Severity-Integration, strukturiertes Startup-Migration-
Logging. Abzüge: (1) **Opt-in-Telemetrie-Default** = Out-of-the-Box keine
persistente Trace-/Kosten-Speicherung (Design-Folge, kein Defekt); (2) die
Prometheus-`/metrics`-Exposed-Behauptung in `metrics.py` Docstring ist in der
lifespan/telemetry-Setup-Verdrahtung nicht als Route-Registrierung verifiziert
(AUFG-05-19). Insgesamt ein vorbildliches Setup für eine local-first-App.

---

## 5. Gesamtbewertung des Projekts

> Fasse hier die Erkenntnisse aus allen Reviews (01–05) zusammen.

### Stärken des Projekts

1. **Maschinell erzwungene Architektur-Verfassung (23 RULE-XX) mit 16 echten,
   blockierenden Quality Gates.** `check_architecture.py` (pre-commit + CI)
   prüft 1.984 Dateien, 0 echte Verletzungen, 16 sauber registrierte +
   ratcheted Ausnahmen (Implementierung + Enforcement, nicht nur Doku).
   Disziplin auf einem Niveau, das in Projekten dieser Größe selten ist
   (review-01, review-02).
2. **Ausgereiftes Test- und Eval-Fundament (~9.500 Tests + ADR-032 Pydantic-
   Evals).** 3-Level-Architektur (unit/integration/e2e), konsequente Fake-
   Klassen-Disziplin (RULE-TEST-01), ratcheted per-Modul-Coverage (meist
   84–100 %, Floor 80 %), Smoke-(blocking)+Runtime-(nightly)-Eval-Trennung.
   Pytest-Collect 11,8 s für 9.471 Tests (review-02).
3. **TipTap/GhostText-AI-Integration als herausragendes Herzstück (⭐⭐⭐⭐⭐).**
   ProseMirror-konforme nicht-mutierende `Decoration.widget(side:1)`-Architektur,
   4-Phasen-Evolution (LRU-Cache, Auto-Trigger, Typing-Mismatch-Detection),
   AIAnnotation-Mark mit Transaction-Survival, sauberste Komponententrennung,
   volle §16-SSE-Lifecycle-Compliance via `connectSSE()`+`useAIOperation()`
   (review-03 §8).
4. **30+ spezialisierte NarrareAgents mit sauberer Capability-Vererbung +
   ModelRegistry-Auflösung.** RULE-01b (Agents-First) konsistent gelebt,
   ADR-026-Dreiteilung (Capability/Cascade/Dynamic) umgesetzt, Modelle
   ausschließlich via `registry.get_model(config)`, nie direkte Provider-
   Instanzierung (review-03 §3).
5. **Single-Command-Setup + durchgängig modernster Tool-Stack (⭐⭐⭐⭐⭐ Tooling).**
   `just dev-setup` orchestriert das komplette Setup; uv + Ruff + pyright +
   just + Biome + Vitest + Next 16 + TS 6 + Tailwind v4 — kein einziges
   wechselwürdiges Werkzeug; vorbildlich zentralisierte Tool-Konfig;
   DevContainer optional (ADR-029) (review-04 §1, §4).
6. **Automatisierter, reproduzierbarer Release-Prozess.** release-please +
   Conventional-Commits → SemVer → auto-CHANGELOG → Single-Docker-Image →
   GHCR (`:version`+`:latest`+digest) → CycloneDX-SBOM → Release-Bundle-ZIP
   mit instruiertem README; dokumentierter Rollback-Pfad (review-05 §1).
7. **Starker Security-Baseline + local-first-Privacy.** Argon2id +
   httpOnly/scoped Refresh-Cookie + CSRF-Defense-in-Depth + Rate-Limiting
   (14 AI/SSE/WS-Klassen) + Fernet-verschlüsselte API-Keys (never logged) +
   alle Nutzerdaten (Memories, KB, Embeddings) in eigener pgvector-DB; Opt-in-
   Telemetrie (review-05 §3).
8. **ADR-031-konforme, durchgängige Observability mit LLM-Kosten-Tracking.**
   Vollständige Trace-Correlation-Kette (Request-ID/Trace-ID über HTTP→Service
   →LLM→SSE), intent-/model-/provider-gelabelte Prometheus-Metrics +
   structlog-Events für run()+stream(), Content-Scrubbing in prod, Health-
   Check mit OTel-Severity-Integration (review-05 §4).

### Schwächen & Risiken

Priorisiert nach Dringlichkeit (Hoch = blockiert Vertrauen/Stabilität, schnell
lösbar; strukturell = mittelfristig):

1. **(Hoch)** **Komponenten-Marker-Problem** — `check-testid.ts` läuft lax
   (`components/ui/` übersprungen), ist regex-basiert und **für die AI
   unsichtbar** (keine Standards-Doku). Bedroht E2E-/VRT-Stabilität an der
   Wurzel (AUFG-02-01, AUFG-02-02).
2. **(Hoch)** **Agent-Namen-Drift** — Root-`AGENTS.md` + `orchestrator.md`
   routen auf `narrare-architecture/implementation/testing/...`, die realen
   Subagents heißen `Narrare*Specialist`. Jeder AI-Workflow riskiert einen
   Aufruffehler (AUFG-04-01).
3. **(Hoch)** **Phantom-Gate + stale `just`-Kommandos** —
   `check_governance_health.py` wird als „CI-blocking" dokumentiert,
   existiert nicht; `just check-types`/`check-constraints`/`db-seed`/`format`
   in Doku genannt, existieren nicht. Ironischerweise genau der
   „documented ≠ implemented"-Anti-Pattern, den dieselben Gates woanders
   abwehren (AUFG-04-02, AUFG-04-03, AUFG-04-04).
4. **(Hoch)** **Keine Writing/Generation-Prose-Eval-Suite** für das Kern-
   Feature (extend/suggest/variant/session). Prompt-/Gateway-Änderungen haben
   keinen automatisierten Qualitätsregressionsschutz für das Haupt-Feature
   (AUFG-02-03).
5. **(Mittel)** **Feature-Prompts EN-only + `AnalysisPanel.tsx`-Placeholder**
   — i18n-Versprechen für Prompts nicht vollständig; verwaistes Dashboard-
   Element suggeriert Unvollständigkeit (AUFG-03-01, AUFG-03-02).
6. **(Mittel)** **Frontend-Controller-Hotspots ungetestet + 15 % components-
   Coverage-Schwelle** — `useKnowledgeGraphController`/`useGenerationPanelController`/
   `useKBAssistedCreationController` (degree 52–92) ohne Unit-Tests; hohe
   Blast-Radius-Lücken (AUFG-02-04).
7. **(Mittel)** **mem0 RULE-02b-Graubereich + 2 Dateien exakt am RULE-04 Hard-
   Limit** — `integration_contracts.py` und `llm/intents.py` (je 400 Zeilen)
   drohen beim nächsten Zuwachs Build-Fehler; Extraktions-Prompts in
   `core/memory/` statt `core/prompts/` (AUFG-01-02, AUFG-01-03, AUFG-01-05).
8. **(Mittel)** **Docker-Only-Distribution + private GHCR-Image für nicht-
   technische Nutzer** — keine Guided-Installer-/One-Liner; Q-011 (Distributions-
   Strategie) 🟡 Open; „local-first für Romanautoren" bleibt CLI-affin
   (review-05 §2).
9. **(Niedrig–Mittel)** **Supply-Chain- und Operations-Härte hinter dem
   Standard** — Cosign-Image-Signing nur „Future Enhancement"; SBOM best-effort
   (`continue-on-error`); kein Container-Image-/Dependency-Review-Scan in CI;
   Key-Rotation nur manuell ohne Skript; 2 unkommentierte pip-audit-Suppressions
   (AUFG-04-10, AUFG-05-15…18).

### Bewertungs-Übersicht

| Bereich | Bewertung | Wichtigster Handlungsbedarf |
|---|---|---|
| Architektur & Code-Qualität | ⭐⭐⭐⭐⭐ `⭐⭐⭐⭐` | mem0 RULE-02b-Graubereich klären + präventive Aufteilung von `integration_contracts.py`/`intents.py` (am Hard-Limit) vor dem nächsten Zuwachs (AUFG-01-02/03/05). |
| Testing & CI/CD | ⭐⭐⭐⭐⭐ `⭐⭐⭐⭐` | Komponenten-Marker AI-sichtbar machen (ui-principles.md) + `--strict`-Ratchet; Writing-Prose-Eval-Suite für das Kern-Feature (AUFG-02-01/02/03). |
| AI-Features & Prompting | ⭐⭐⭐⭐⭐ `⭐⭐⭐⭐` | Feature-Prompts de/fr übersetzen; `AnalysisPanel.tsx`-Placeholder verdrahten/entfernen (AUFG-03-01/02). |
| Developer Experience | ⭐⭐⭐⭐⭐ `⭐⭐⭐⭐` | Agent-Namen synchronisieren; stale `just`-Kommandos + Phantom-Gate bereinigen; `CONTRIBUTING.md` anlegen (AUFG-04-01/02/03/05). |
| Release & Packaging | ⭐⭐⭐⭐⭐ `⭐⭐⭐⭐` | SBOM-Härtung (best-effort → blockierend); Container-Image-Scan + Cosign-Signing implementieren (AUFG-05-15/16/17). |
| Security & Privacy | ⭐⭐⭐⭐⭐ `⭐⭐⭐⭐` | Container-Scan + `dependency-review-action` in CI; Key-Rotation automatisieren; 2 Vuln-Suppressions kommentieren (AUFG-02-06, AUFG-04-10, AUFG-05-16/18). |
| Observability & Operations | ⭐⭐⭐⭐⭐ `⭐⭐⭐⭐` | `/metrics`-Exposed-Behauptung verifizieren (Route-Registrierung); Optional: Default-OTel-Endpoint-Dok für Self-Hoster (AUFG-05-19). |
| **Gesamt** | **⭐⭐⭐⭐⭐ `⭐⭐⭐⭐`** | Kein Bereich kritisch (≤⭐⭐), keiner vorbildlich frei (⭐⭐⭐⭐⭐⭐) — ein diszipliniertes, reifes Projekt mit aufräumbaren „documented ≠ implemented"-Drifts in der DX-/Release-Schicht. |

**Gesamtbewertung:** ⭐⭐⭐⭐⭐ `⭐⭐⭐⭐`
**Vorherige Bewertung:** _keine (Erst-Audit)_ | **Trend:** _➡️ Erst-Audit (Baseline)_
**Fazit:** Narrare ist ein architektonisch herausragend diszipliniertes, reifes
Projekt: 23 maschinell erzwungene RULE-XX, ~9.500 Tests mit ratcheted per-Modul-
Coverage, eine TipTap/AI-Integration als echtes Herzstück (⭐⭐⭐⭐⭐), 30+
spezialisierte Agents, ein automatisierter Release-Prozess mit SBOM, starker
Security-Baseline (Argon2id/CSRF/Rate-Limiting/verschlüsselte API-Keys) und
local-first-Privacy — deutlich über dem Durchschnitt AI-gestützter Schreibtools.
Die Abwertung auf ⭐⭐⭐⭐ (statt ⭐⭐⭐⭐⭐) ist **konsistent über alle sieben
Bereiche**: in jedem gibt es mehrere aufräumbare „documented ≠ implemented"-
Drifts (Agent-Namen, Phantom-Gate, stale `just`-Befehle, EN-only-Prompts,
unverbundener `AnalysisPanel`-Placeholder, `/metrics`-Exposed-Behauptung) und
Supply-Chain-/Operations-Härte-Lücken (Cosign fehlt, SBOM best-effort, kein
Container-/Dependency-Scan, Key-Rotation manuell) — einzeln S–M-Aufwand, aber
sie häufen sich genau in der DX-/Release-Schicht, wo neue Mitwirkende/Nutzer
zuerst hinschauen, und widersprechen dem selbst deklarierten
Qualitätsanspruch. Kein einziger Bereich ist kritisch (≤⭐⭐), kein Release-
Blocker existiert — alle 16 Quality Gates sind grün —, aber die konsequente
Schließung der ~9 Hoch-Priorität-AUFG (Marker-Doku, Agent-Namen, Phantom-Gate,
Writing-Eval) würde das Projekt von „gut mit sichtbaren Reibungsverlusten" auf
„vorbildlich" heben. Für ein Erst-Audit ist das eine starke Baseline.

---

## 6. Roadmap-Empfehlung

> Priorisierte Liste aller Aufgaben aus den Reviews 01–05 nach Dringlichkeit.
> Denke in Sprints oder Meilensteinen.

Aggregiert über **alle** AUFG aus 01–04 (5+7+7+10 = 29) + die neuen AUFG-05-15…19
(5) = **34 Aufgaben**. Gruppierung nach Impact × Aufwand.

### Sofort (nächste 1–2 Wochen)

_Hoch-Priorität, Aufwand S,Quick-Wins — beheben unmittelbar sichtbare „documented
≠ implemented"-Reibung und AI-Workflow-Brüche:_

- **AUFG-04-01** — Agent-Namen synchronisieren (AGENTS.md/orchestrator.md ↔
  `Narrare*Specialist`) — Hoch, M
- **AUFG-04-02** — Stale `just`-Kommandos in orchestrator.md korrigieren
  (`check-types`→`typecheck` etc.) — Hoch, S
- **AUFG-04-03** — Phantom-Referenz `check_governance_health.py` entfernen
  oder Script anlegen — Hoch, S
- **AUFG-04-05** — `CONTRIBUTING.md` anlegen + README-Link — Hoch, S
- **AUFG-02-01** — Komponenten-Marker-Pflicht in `ui-principles.md` dokumentieren
  (AI-Sichtbarkeit) — Hoch, S
- **AUFG-01-01** — CONSTRAINTS.md RULE-16 Locale-Pfad-Korrektur (Doc-Drift) —
  Niedrig, S (aber trivial und hoch-sichtbar)

### Kurzfristig (nächste 4–6 Wochen)

_Hoch-Impact, Aufwand S–M — schließen strukturelle Test-/Quality-Lücken und
bereinigen die DX-Schicht vollständig:_

- **AUFG-02-02** — `check-testid` auf `--strict` + Ratchet-Baseline umstellen —
  Hoch, M
- **AUFG-02-03** — Writing/Generation-Prose-Eval-Suite erstellen (Kern-Feature-
  Schutz) — Hoch, L
- **AUFG-03-02** — Verwaisten `AnalysisPanel.tsx`-Placeholder verdrahten/
  entfernen — Mittel, S
- **AUFG-02-04** — Frontend-Controller-Hooks testen + components-Coverage-
  Schwelle anheben — Mittel, M
- **AUFG-02-05** — Pyright-Cache-Key + `--dist loadfile` in CI korrigieren —
  Mittel, S
- **AUFG-01-04** — RULE-13-Signatur-Reconciliation (run/stream) — Niedrig, S/M
- **AUFG-04-04** — Stale Justfile-Command-Catalog in deployment-guide.md
  korrigieren — Mittel, S
- **AUFG-04-06** — `dev-setup-min` für Nicht-NLP-Entwickler — Mittel, S
- **AUFG-05-15** — SBOM-Generierung härten (`continue-on-error` entfernen +
  Verifikations-Gate) — Mittel, S
- **AUFG-05-16** — Container-Image-Vulnerability-Scan in CI (Trivy/Grype auf
  gebautes Image) — Mittel, S

### Mittelfristig (nächste 3–6 Monate)

_Strukturelle Verbesserungen + Mehrwert-Features — konsolidieren die
Architektur und schließen i18n-/Eval-Lücken:_

- **AUFG-01-02** — mem0-Extraktionsprompts RULE-02b-Klärung (migrieren oder
  Ausnahme registrieren) — Mittel, M
- **AUFG-01-03** — Präventive Aufteilung `integration_contracts.py` (am Hard-
  Limit) — Mittel, M
- **AUFG-01-05** — Präventive Aufteilung `llm/intents.py` (am Hard-Limit) —
  Niedrig, S
- **AUFG-03-01** — Feature-Prompts auf de/fr übersetzen (i18n-Vollständigkeit) —
  Mittel, L
- **AUFG-03-04** — Emotionale Intensitätskurve über Kapitel visualisieren —
  Mittel, M
- **AUFG-02-06** — `dependency-review-action` + Frontend-Perf-Budget
  revalidieren — Niedrig, S
- **AUFG-04-07/08/09/10** — DX-Cleanups (enforced-Regeln vereinheitlichen,
  ESLint/Prettier-Extensions entfernen, `jsonschema` verschieben, pip-audit-
  Suppressions kommentieren) — Niedrig, je S
- **AUFG-05-17** — Cosign-Keyless-Image-Signing implementieren (Supply-Chain) —
  Mittel, M
- **AUFG-05-18** — `NARRARE_ENCRYPTION_KEY`-Rotations-Skript automatisieren —
  Mittel, M
- **AUFG-05-19** — Prometheus-`/metrics`-Exposed-Behauptung verifizieren/Route
  registrieren (documented ≠ implemented) — Mittel, S

### Langfristig / Optional

_Nice-to-have, größere Umbauten, Roadmap-Abhängigkeiten:_

- **AUFG-03-03** — Ghost-Text-Auto-Retry bei Connection-Loss — Niedrig, S
- **AUFG-03-05** — Meta-Lite-Variante: Selektor verifizieren oder entfernen —
  Niedrig, S
- **AUFG-03-06** — Cross-Agent-Kontext-Teilung für aufeinanderfolgende
  Werkzeug-Aufrufe — Niedrig, L
- **AUFG-03-07** — Skill-Duplikation zwischen `.agents/skills/`,
  `.opencode/skills/`, Superpowers auflösen — Niedrig, S
- **Q-001 / ADAPTER-001** — MCP-Auth-Strategie klären → MCP-Server bauen
  (blockiert) — Strategic
- **Q-002 / ADAPTER-002** — A2A-Streaming-Anforderung klären → A2A-Server
  bauen (blockiert) — Strategic
- **Q-011** — Distributions-Strategie für nicht-technische Nutzer (Guided-
  Installer / `narrare`-CLI) — Strategic
- Optional: öffentliche GHCR-Image-Option (statt private-by-default) zur
  Senkung der Self-Host-Friction — Strategic

---

## 7. Weitere Anmerkungen

> Alles, was in den bisherigen Reviews keinen Platz gefunden hat.

**Lob:**

- Das **Release-Bundle-README** in `release-please.yml` (L128–249) ist
  herausragend instruiert: erklärt Digest-Pinning vs. Tag, SBOM-Scan-Kommandos
  (Grype/Trivy), Cosign-Verifikations-Pfad (inkl. korrektem
  `--certificate-identity-regexp`), und ist ehrlich über Trust-Levels
  („High/Medium" in der Provenance-Tabelle). Das ist Supply-Chain-Kommunikation
  auf Niveau kommerzieller Produkte.
- Die **OTel-Health-Severity-Policy** (`get_observability_status()` mit
  `healthy`/`degraded`/`critical` + thread-safe State-Tracking + one-shot-
  Warning, AUFG-05-14) ist eine elegante Lösung für das „OTel optional, aber
  trotzdem diagnosable"-Problem local-first-Apps — und die Integration in
  `/health` macht den Degraded-Zustand für Self-Hoster sichtbar.
- Der **`lifespan.py`-Startup-Migration-Log-Flow** (`db_schema_version` →
  `db_migrations_applied`/`db_schema_up_to_date` → `narrare_api_ready`) ist
  vorbildlich für Operations: ein Self-Hoster sieht an den Log-Events exakt,
  welche Migration von welcher auf welche Revision lief.

**Kritik:**

- **„Private-by-default"-GHCR-Image** für ein als Open Source (MIT) deklariertes,
  local-first-positioniertes Tool ist inkonsistent: Self-Hoster müssen
  `docker login ghcr.io` durchführen, was die Adoptions-Hürde erhöht und für
  nicht-technische Zielgruppe (Q-011) kontraproduktiv ist. Eine
  `make-public-on-release`-Option oder ein öffentliches `:latest`-Tag würde
  die Vision besser bedienen.
- **Zwei parallele AUFG-05-Nummernräume.** Das archivierte Security-Audit
  (`docs/archive/architecture/governance/security-audit-cors-rate-limiting.md`)
  nutzt AUFG-05-07/12/13/14, dieses Review beginnt wegen Kollision bei 15. Das
  ist funktionierend, aber es zeigt eine **Lücke im AUFG-Nummerierungs-Schema**:
  es gibt keine zentrale AUFG-Registry, die Kollisionen verhindert. Ein
  `docs/_shared/AUFG-REGISTRY.md` (oder ein CI-Checker analog zu
  `check_exception_baseline.py`) würde das nachhaltig lösen. (Diskrepanz,
  nicht als AUFG angelegt, da Meta-Prozess.)

**Ideen:**

- **Guided-Self-Host-Installer:** Ein `./install.sh` (oder `narrare`-CLI mit
  `init/up/update/backup`), das interaktiv `.env` befüllt (Key-Generierung,
  AI-Provider-Auswahl, Docker-Vorhandenheits-Check), würde Q-011 adressieren,
  ohne das Docker-First-Prinzip aufzugeben. Aufwand M, Impact Hoch für die
  Vision-Zielgruppe.
- **Default-Local-OTel-Sink:** Ein Optional-Bundle-Service im Release-Compose
  (z. B. Jaeger-all-in-one oder ein lokales OTel-Collector-File-Exporter),
  der per `OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317` vernetzt
  ist, würde Out-of-the-Box-Traces ohne Cloud-Abhängigkeit liefern —
  kompatibel mit local-first.

**Konventions-Diskrepanz (dokumentiert, nicht als Task):** Das Review-Template
schlägt `AUFG-05-01, …` vor, aber ein vorangegangenes (archiviertes) Audit hat
05-07/12/13/14 bereits vergeben. Die neuen Aufgaben beginnen daher bei
**AUFG-05-15**. Für künftige Review-05-Durchläufe sollte entweder das Template
auf „fortlaufend ab letzter vergebener AUFG-05-NN" geändert oder eine
zentrale AUFG-Registry eingeführt werden.

---

## Aufgaben

<!-- TODO (Projekt-AI): Nummerierung: AUFG-05-15, AUFG-05-16, … (AUFG-05-01…14
     sind durch das archivierte Security-Audit belegt — siehe §7 Diskrepanz) -->
<!-- Hier nur neue Aufgaben, die noch nicht in 01–04 erfasst wurden.
     Vorhandene AUFG-02-06 (dependency-review-action) und AUFG-04-10
     (pip-audit-Suppressions kommentieren) berühren Security, werden aber
     nicht dupliziert. -->

### [AUFG-05-15] SBOM-Generierung im Release härten (best-effort → verifiziert)
**Re-Check 2026-07-10:** **DEFERRED 2026-07-10** — Release-Strategie
undentschieden (Q-011). Der `publish`-Job in `release-please.yml` (inkl.
Docker-Build, SBOM, GHCR-Push) ist spekulativ — keine GHCR-Credentials
konfiguriert, nie getriggert, Artefakt-Typ offen. SBOM-Härtung ist relevant
erst, wenn entschieden ist, was ein Release-Artefakt ist. Wiedervorlage: mit
Q-011-Entscheidung (Release-/Distributions-Strategie).
**Priorität:** Mittel
**Bereich:** Release / Security
**Kontext:** Die CycloneDX-SBOM-Generierung im `publish`-Job von
`.github/workflows/release-please.yml` (L83–108) läuft mit
`continue-on-error: true` und mit „best-effort"-Meldungen („⚠ No SBOM
generated"). Ein stilles Ausfallen (Syft-Install-Fehler, `docker pull`-Fehlschlag,
Docker-SBOM-Plugin nicht verfügbar) führt zu einem Release **ohne** SBOM, ohne
dass der Release blockiert oder nachträglich alarmiert wird. Das widerspricht
dem „documented = implemented"-Anspruch (architectural-discipline §7) und der
SBOM-Promise im Release-Bundle-README. Supply-Chain-Schwäche: ein Konsument,
der `sbom.cyclonedx.json` erwartet (und laut README scannen will), hat
möglicherweise ein leeres/fehlendes Asset.
**Akzeptanzkriterien:**
- [ ] SBOM-Generierung ist **blockierend** (entferne `continue-on-error: true`,
      ODER fallback auf `uv export`-basierte Python-Only-SBOM, die deterministisch
      funktioniert)
- [ ] Post-Step verifiziert, dass `sbom.cyclonedx.json` existiert und nicht-leer
      ist (fail-if-missing)
- [ ] Bei Fehlschlag: klarer, actionabler Fehler im GitHub-Release-Summary
- [ ] Alternative: separates `sbom-verification`-Job, der den Release blockiert,
      falls das SBOM-Asset fehlt
**Geschätzter Aufwand:** S

### [AUFG-05-16] Container-Image-Vulnerability-Scan in CI (Trivy/Grype)
**Re-Check 2026-07-10:** **DEFERRED 2026-07-10** — Release-Strategie
undentschieden (Q-011). Es wird derzeit kein Docker-Image gebaut (weder in CI
noch im Release — der `publish`-Job ist nie gelaufen). Image-Scanning ist
relevant erst, wenn entschieden ist, dass ein Docker-Image ein
Release-Artefakt ist. Wiedervorlage: mit Q-011-Entscheidung
(Release-/Distributions-Strategie).
**Priorität:** Mittel
**Bereich:** Release / Security
**Kontext:** Die CI prüft Dependencies via `pip-audit` (Source-Manifest) und
`gitleaks` (Secrets), aber das **gebaute Docker-Image** wird **nicht** auf
Schwachstellen gescannt (weder in PR-CI noch im Release-Workflow). Das
Release-Bundle-README instruiert Nutzer, die SBOM manuell mit Grype/Trivy zu
scannen — das Projekt selbst tut das aber nicht proaktiv. Trivy/Grype-Image-
Scan würde OS-Package- (Debian-bookworm-slim), Python- und Node.js-Vulns im
finalen Image gleichzeitig decken undSupply-Chain-Audit-Lücken schließen.
Review-02 hat `dependency-review-action` (AUFG-02-06) bereits notiert, aber
das ist Source-Ebene — dieser Task ist Image-Ebene (komplementär).
**Akzeptanzkriterien:**
- [ ] `aquasecurity/trivy-action` (oder Grype) scannt das gebaute Image im
      `publish`-Job (oder in einem separaten `image-scan`-Job nach Build)
- [ ] Critical-/High-Vulns blockieren den Release (oder: Ratchet-Baseline
      analog `coverage_baselines.json` mit `--exit-code` + dokumentierten
      Ausnahmen)
- [ ] Scan-Ergebnis als Release-Asset oder Job-Summary hinterlegt
- [ ] Dokumentierte Ausnahmen für nicht-fixbare Vulns (mit Begründung +
      Wiedervorlage)
**Geschätzter Aufwand:** S

### [AUFG-05-17] Cosign-Keyless-Image-Signing implementieren (Supply-Chain)
**Re-Check 2026-07-10:** **DEFERRED 2026-07-10** — Release-Strategie
undentschieden (Q-011). Cosign-Signing setzt ein veröffentlichtes
Docker-Image voraus — der `publish`-Job, der es bauen/pushen würde, ist
spekulativ (keine GHCR-Credentials, nie getriggert). Signing ist relevant
erst, wenn entschieden ist, dass ein Docker-Image ein Release-Artefakt ist.
Wiedervorlage: mit Q-011-Entscheidung (Release-/Distributions-Strategie).
**Priorität:** Niedrig
**Bereich:** Release / Security
**Kontext:** Das Release-Bundle-README (release-please.yml L235–248) skizziert
Cosign-Keyless-Signing via GitHub-OIDC explizit als „Optional: Future
Enhancement" und gibt sogar die korrekte `cosign verify`-Kommando-Vorlage. Das
** eigentliche Signieren ist aber nicht implementiert** — das Docker-Image ist
nur durch GitHub's automatische Release-Artefakt-Signatur (nicht das Image
selbst) und Digest-Pinning abgesichert. Für ein OSS-Projekt mit Supply-Chain-
Awareness (SBOM, signed Releases) ist das eine erkennbare Lücke: Konsumenten
können die Image-Provenanz nicht kryptographisch verifizieren.
**Akzeptanzkriterien:**
- [ ] `sigstore/cosign-installer` + `cosign sign --keyless` im `publish`-Job
      nach Docker-Push (via `id-token: write`-Permission)
- [ ] Signatur-Identity-Regexp dokumentiert (passt zur Vorlage im README)
- [ ] `cosign verify`-Kommando im Release-Bundle-README aktualisiert (entferne
      „Future Enhancement"-Caveat)
- [ ] Optional: Rekor-Transparency-Log-Verifizierung im Release-Summary
**Geschätzter Aufwand:** M

### [AUFG-05-18] NARRARE_ENCRYPTION_KEY-Rotation automatisieren
**Priorität:** Mittel
**Bereich:** Security / Operations
**Kontext:** `docs/development/deployment-guide.md` L655 dokumentiert die
Rotation-Prozedur für `NARRARE_ENCRYPTION_KEY` („generate new key, decrypt all
keys with old key, re-encrypt with new key, update env var") rein manuell. Es
gibt **kein Skript** dafür, und die Warnung „If this key is lost, all user API
keys are unrecoverable" macht klar, dass ein Fehler bei manueller Rotation
 katastrophal ist (Verlust aller user API Keys). Ein `scripts/rotate_encryption_key.py`
würde die Prozedur deterministisch machen, Transaktions-Sicherheit (alle Keys
in einer Transaktion re-encrypten oder gar nicht) bieten und die
Operator-Fehleranfälligkeit reduzieren. Backup-Hinweis gibt es bereits
(„Store securely and back up"), aber kein Backup-Tooling.
**Akzeptanzkriterien:**
- [ ] `scripts/rotate_encryption_key.py` CLI: nimmt `--old-key` und `--new-key`
      (via Env oder Prompt, nie CLI-Arg im Klartext), re-encrypted alle Einträge
      in `user_providers` transaktional, dry-run-Modus
- [ ] Dokumentation im deployment-guide.md (Rotation-Abschnitt): Skript-Aufruf,
      Pre-Flight-Backup-Hinweis, Rollback bei Fehler
- [ ] Unit- + Integration-Test für den Rotations-Skript
- [ ] Optional: Backup-Dump-Skript (`scripts/export_encrypted_keys.py`) für
      Offline-Backup der `user_providers`-Tabelle
**Geschätzter Aufwand:** M

### [AUFG-05-19] Prometheus-/metrics-Exposed-Behauptung verifizieren (Route-Registrierung)
**Priorität:** Niedrig
**Bereich:** Observability / Operations
**Kontext:** `packages/core/narrare_core/llm/metrics.py` L7 doccumentiert
„Prometheus metrics are exposed at /metrics by the API" und definiert 8
Counter/Histograms (`narrare_llm_*`). Die eigentliche **Route-Registrierung**
von `/metrics` (via `prometheus_client.make_asgi_app()` o. ä.) und der
`metrics_router` sind in `_app/lifespan.py`/`telemetry.py`/`main.py` nicht
eindeutig als `/metrics`-Mount verifiziert (der `metrics/router.py` exponiert
nur `/health` und `/ready`). Das ist ein „documented ≠ implemented"-Kandidat:
entweder `/metrics` ist tatsächlich gemountet (dann Code-Kommentar/Verdrahtung
klären) oder die Docstring-Behauptung ist inaccurate (dann Metrics werden nur
intern erfasst, aber nicht via HTTP scrapable). Für Self-Hoster, die
Prometheus-Grafana-Dashboards für LLM-Kosten/-Tokens aufbauen wollen, ist die
Frage „ist `/metrics` erreichbar?" operations-entscheidend.
**Akzeptanzkriterien:**
- [ ] Verifikation: ist `/metrics` als Route registriert? (Grep nach
      `make_asgi_app`, `metrics`-Mount in `main.py`/`lifespan.py`)
- [ ] Falls ja: klarer Code-Kommentar + Deployment-Guide-Eintrag („scrape
      `http://<host>:8000/metrics`")
- [ ] Falls nein: entweder `/metrics`-Mount nachziehen (inkl. Auth-Decision:
      öffentlich vs. Token-gated) ODER Docstring-Behauptung korrigieren
- [ ] Optional: Sample-`prometheus.yml`-Scrape-Config in deployment-guide.md
**Geschätzter Aufwand:** S

---

## Angenommene Risiken (Accepted Risks)

> Beobachtungen aus diesem Review, die bewusst als akzeptierte Risiken
> eingestuft wurden — keine Aufgabe, sondern dokumentierte Entscheidung
> mit Begründung und Wiedervorlage-Termin.

### AR-05-01: Keine automatisierte Rollback-Variante
**Bereich:** Release / Operations
**Akzeptiert am:** 2026-07-10
**Begründung:** Der manuelle Rollback-Prozess ist vollständig dokumentiert
(deployment-guide.md §Rollback: Image-Tag-Replace + Alembic-Migrations-
Caveat). Kein akuter Blocker — Automatisierung ist eine Ops-Maturity-
Erweiterung, kein Defekt. Keine aktuelle Verletzung.
**Wiedervorlage:** Bei Einführung von Blue-Green-Deployments oder
automatischem Health-Check-basiertem Rollback.

### AR-05-02: Kein `github/codeql-action` in CI
**Bereich:** Security / CI
**Akzeptiert am:** 2026-07-10
**Begründung:** CodeQL erfordert GitHub Advanced Security (GHAS), das auf
diesem Repo nicht verfügbar ist. Gleiche Voraussetzung wie AUFG-02-06(a)
(dependency-review-action, deferred/accepted_risk). bandit (SAST) +
pip-audit (Dependency-Audit) decken Python-Level ab.
**Wiedervorlage:** Bei Verfügbarkeit von GHAS auf diesem Repo.

### AR-05-03: Private-by-default GHCR-Image
**Bereich:** Release / Distribution
**Akzeptiert am:** 2026-07-10
**Begründung:** Strategische Produktentscheidung, verknüpft mit Q-011
(Distributions-Strategie für nicht-technische Nutzer). Ein öffentliches
Image ist eine Produktentscheidung, kein Code-Defekt.
**Wiedervorlage:** Mit Q-011-Entscheidung (Distributions-Strategie).

### AR-05-04: Keine zentrale AUFG-Nummerierungs-Registry
**Bereich:** Meta-Prozess / Governance
**Akzeptiert am:** 2026-07-10
**Begründung:** IDs sind per-Review scope; Kollisionen wurden manuell
behandelt (archiviertes Security-Audit nutzt AUFG-05-07/12/13/14, dieses
Review beginnt bei 15). Eine zentrale Registry würde zukünftige Kollisionen
verhindern, ist aber Meta-Prozess-Overhead, kein Code-Defekt. Review-Autor
hat bewusst auf eine AUFG verzichtet.
**Wiedervorlage:** Bei häufigeren Review-Kollisionen oder Einführung
eines automatisierten AUFG-Tracking-Systems.
