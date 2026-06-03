# Q-011 — Wie wird Narrare für nicht-technische Nutzer zugänglich?

> **Status:** 🟡 Open
> **Blocks:** Zielgruppen-Positionierung, Setup-UX-Vereinfachung, Post-MVP-Distribution
> **Raised:** 2026-06-03 (Technical Audit Review 05 — Deployment Usability)

---

## Question

Wie wird Narrare für nicht-technische Nutzer zugänglich? Docker-only Self-Host, vereinfachter Installer, Desktop-App (Tauri/Electron), oder gehostetes Angebot?

---

## Context

Narrare positioniert sich als „local-first, fully customizable" AI-Schreibtool. Die Projektvision (`docs/reference/project-vision.md`) definiert die Zielgruppe:

- **Primary:** Serious hobby or independent author — jemand der einen Roman schreibt, nicht zwingend technisch
- **Secondary:** Professional author who wants a private AI writing partner
- **Not:** Der casual User der „schreib mir eine Geschichte über Drachen" will

Die Vision sagt explizit: „Narrare runs locally. Your manuscript, your KB, your prompts — all on your machine." Das local-first-Prinzip ist zentral für die Identität.

Das technische Audit (Review 05) bewertet die Nutzerfreundlichkeit der Bereitstellung mit ⭐⭐ („Für nicht-technische Nutzer schwierig"): Nutzer müssen Docker, `.env`-Konfiguration, Secrets-Management, AI API Keys und `docker-compose` verstehen. Für die Zielgruppe „serious hobby author" ist das eine signifikante Barriere.

Derzeit ist Docker-only Self-Hosting die einzige Bereitstellungsmethode. MCP und A2A sind als „planned" markiert (Q-001, Q-002) aber nicht implementiert. Es gibt keinen vereinfachten Installer, keine Desktop-App, kein gehostetes Angebot.

### Die Diskrepanz

| Aspekt | Anspruch | Realität |
|--------|----------|----------|
| Zielgruppe | Kreative Schreiber, nicht zwingend technisch | Docker + .env + API Keys erforderlich |
| Positionierung | „Local-first, fully customizable" | Local-first = Docker Self-Host |
| Setup-Aufwand | Ziel: 5-Minute Setup | Realität: DevOps-Kenntnisse nötig |
| Vision: „available when you need it" | Sofort einsatzbereit | Setup Wizard hilft, aber nur nach Docker-Deployment |

Diese Diskrepanz ist kein Bug — sie ist eine offene strategische Entscheidung, die dokumentiert werden muss.

---

## Options Considered

### Option A — Docker-only, positioniere als „Tech-Savvy Self-Host"

Narrare bleibt Docker-only. Die Zielgruppe wird explizit als „technisch versierte Selbsthoster" positioniert. Das Setup wird dokumentationsseitig optimiert (bessere Docker-Guides, Video-Tutorials), aber architekturell nicht vereinfacht.

**Pros:**
- Kein architektonischer Änderungsaufwand — Status quo
- Keine neuen Dependencies oder Plattformen
- Behält volle local-first-Integrität (kein Cloud-Dependency-Risiko)
- Tech-savvy Community ist oft die earliest adopter-Gruppe
- Docker-Kenntnisse sind unter Entwicklern und technisch versierten Nutzern weit verbreitet
- Positionierung ist ehrlich und transparent

**Cons:**
- Schließt den Großteil der primären Zielgruppe aus (kreative Schreiber ≠ DevOps)
- Widerspricht der Vision „serious hobby author" — die meisten sind keine Docker-Nutzer
- Begrenzt das Wachstumspotenzial auf eine Nische
- „Bessere Dokumentation" löst nicht das grundsätzliche UX-Problem
- Review 05 bleibt bei ⭐⭐ — keine Verbesserung der Bereitstellungsnutzerfreundlichkeit

**Architectural Impact:**
- Keine Änderung an Architektur, Modules, Dependencies
- Docs-Aufwand: Docker-Setup-Guide, Video-Tutorials, Troubleshooting
- Risiko: Wachstum deckelt sich bei technisch versierter Nische

---

### Option B — Desktop-App via Tauri (oder Electron)

Narrare wird als native Desktop-App verpackt. Tauri (Rust-basiert) ist preferred wegen geringer Bundle-Größe, Performance und Sicherheit. Electron als Fallback falls Tauri-Integration mit dem bestehenden Python-Backend problematisch ist.

**Variante B1 — Tauri + Embedded Backend:**
- Tauri-Shell bundled ein Python-Runtime (oder kompiliert via PyOxidizer/Nuitka)
- PostgreSQL → SQLite (lokal, embedded)
- Redis → In-Memory-Cache (für lokale Nutzung ausreichend)
- API-Server läuft als Hintergrundprozess in der App

**Variante B2 — Tauri + External Backend:**
- Tauri-Shell startet Docker-Container automatisch (versteckt für den Nutzer)
- Nutzer merkt nicht, dass Docker läuft — „One-Click Installer"
- Nutzt bestehende Docker-Infrastruktur, aber mit Desktop-UX

**Variante B3 — Electron + Node.js Sidecar:**
- Electron-Shell mit Python-Backend als Sidecar-Prozess
- Größerer Bundle, aber bewährtes Pattern (VS Code, Slack)

**Pros:**
- Erreicht die primäre Zielgruppe: Download → Install → Schreiben
- Behält local-first-Prinzip bei (Daten auf dem eigenen Rechner)
- Tauri: ~10 MB Bundle (vs. ~200 MB Electron), Rust-Sicherheit, native Performance
- Keine Cloud-Abhängigkeit — passt zur Vision
- Nativer OS-Integration: Datei-Dialoge, System-Tray, Auto-Update
- Potenzial für Offline-Funktionalität (mit local LLM)

**Cons:**
- Signifikanter architektonischer Aufwand: Tauri/Electron-Shell, Backend-Bundling, DB-Migration (SQLite)
- PostgreSQL → SQLite erfordert Anpassungen: Migration-Tooling, Feature-Parität (pgvector!)
- pgvector-Funktionalität müsste ersetzt werden (sqlite-vss, oder Embeddings extern)
- Multi-Platform-Testing: Windows, macOS, Linux — dreifache QA-Last
- Auto-Update-Infrastruktur muss aufgebaut werden
- Python-Backend bundlen ist komplex (PyOxidizer ist relativ neu, Nuitka hat Einschränkungen)
- Variante B2 (Docker-versteckt) löst das pgvector/Redis-Problem nicht für Nutzer ohne Docker

**Architectural Impact:**
- Neue Plattform-Abstraktion: `packages/desktop/` für Tauri/Electron-Shell
- Core und Backend bleiben unverändert — Desktop-App ist ein weiterer Client (RULE-12)
- Neue Dependency: Tauri (Rust toolchain) oder Electron
- DB-Abstraktionsschicht prüfen: SQLAlchemy bereits da, aber pgvector-spezifische Queries anpassen
- CI/CD-Erweiterung: Desktop-Builds für 3 Plattformen

---

### Option C — Gehostetes Angebot (Cloud/SaaS)

Narrare wird als gehosteter Service angeboten. Nutzer erstellen einen Account und schreiben sofort — ohne Installation.

**Variante C1 — Vollständige Cloud-Instanz:**
- Jeder Nutzer bekommt eine eigene Instanz (Container-basiert)
- Vollständige Narrare-Features, keine Einschränkungen
- Daten liegen auf Servern des Anbieters

**Variante C2 — Managed Hosting (begrenzte Features):**
- Gemeinsame Infrastruktur, tenant-isoliert
- Eingeschränkte Features: kein eigenes Model-Routing, keine Custom-Prompts
- Niedrigere Kosten, aber weniger „fully customizable"

**Pros:**
- Maximale Accessibility: Browser → Account → Schreiben
- Kein Installationsaufwand — entfernt die größte Barriere komplett
- Monetarisierung direkt möglich (Subscription-Modell)
- Zentrale Wartung: Updates, Security-Patches, Backups
- Analytics und Usage-Tracking möglich (mit User-Einwilligung)

**Cons:**
- **Widerspricht der Vision:** „Narrare runs locally. Your manuscript, your KB, your prompts — all on your machine."
- Datenschutz-Bedenken: Manuskripte auf fremden Servern — kritisch für Autoren
- Neue Infrastruktur: Multi-Tenancy, Billing, User-Management, GDPR-Compliance
- Kosten: Server-Infrastruktur, LLM-API-Kosten (wer zahlt?), Support
- Vendor-Lock-in-Risiko für Nutzer
- Vollständig andere Architektur-Annahmen nötig (Multi-Tenancy, Rate-Limiting, Billing)

**Architectural Impact:**
- Multi-Tenancy in bestehender Architektur: Datenisolierung, Row-Level-Security
- Billing-System: Stripe-Integration, Subscription-Management
- Neue Client-Rolle: Gehosteter Web-Client (bestehender Next.js-Client mit Auth-Erweiterung)
- RULE-12 bleibt gültig — Service Layer ist weiterhin die API
- Server-Kosten: PostgreSQL + Redis + TaskIQ-Worker pro Tenant oder shared

---

### Option D — One-Click-Deploy (Fly.io, Railway, Coolify, etc.)

Narrare bleibt Docker-basiert, aber bekommt One-Click-Deploy-Templates für Plattformen wie Fly.io, Railway, oder selbst-gehostetes Coolify. Nutzer klickt einen Button → Narrare wird in der Cloud deployed.

**Variante D1 — Fly.io / Railway Template:**
- `fly.toml` / `railway.json` mit vorkonfigurierten Services
- Nutzer braucht nur einen Account bei der Plattform + AI API Key
- „Deploy to Fly" Button im README

**Variante D2 — Coolify / Dokku Self-Hosted:**
- Template für selbst-gehostete PaaS-Lösungen
- Ein-Klick-Deployment auf eigenem Server
- Behält local-first-Semantik (eigener Server statt lokaler Rechner)

**Pros:**
- Geringerer Aufwand als Desktop-App oder SaaS — Templates statt neue Plattform
- Docker-Infrastruktur bleibt unverändert
- Nutzer bekommt eine echte Instanz (volle Kontrolle, volle Features)
- Fly.io/Railway haben Free-Tiers — niedrige Einstiegshürde
- „Deploy to Your Cloud" positioniert als flexibel, nicht als Vendor
- Coolify-Variante: Nutzer hostet selbst, aber ohne Docker-Kenntnisse

**Cons:**
- Nutzer braucht trotzdem einen Account bei einem Cloud-Provider — nicht „echt lokal"
- Kostet Geld ab einem gewissen Nutzungsgrad (Cloud-Provider-Kosten)
- Keine echte Desktop-Integration (läuft im Browser, Server woanders)
- Fly.io/Railway-Template-Wartung bei API-Änderungen der Plattform
- Löst nicht das Problem für Nutzer die bewusst lokal arbeiten wollen
- Variante D2: Coolify-Setup ist für nicht-technische Nutzer ebenfalls eine Hürde

**Architectural Impact:**
- Keine Änderung an Core oder Backend
- Neue Config-Templates: `deploy/fly.toml`, `deploy/railway.json`
- CI/CD-Erweiterung: Automated Template-Validation
- Doku: Deploy-Guides pro Plattform

---

## Impact Summary

| Aspekt | A: Docker-only | B: Desktop-App | C: Cloud/SaaS | D: One-Click-Deploy |
|--------|---------------|---------------|--------------|-------------------|
| **Zielgruppe** | Tech-Nische | Breite Autorenschaft | Breite Autorenschaft | Mittel (Cloud-affine) |
| **Local-first** | ✅ Vollständig | ✅ Vollständig | ❌ Widerspricht Vision | 🟡 Hybrid |
| **Aufwand** | Minimal (Doku) | Hoch (neue Plattform) | Sehr hoch (SaaS) | Niedrig (Templates) |
| **Barrier** | Docker-Kenntnisse | Download + Install | Account-Erstellung | Cloud-Account |
| **Architektur-Änderung** | Keine | Mittel (DB, Bundling) | Hoch (Multi-Tenancy) | Minimal |
| **Monetarisierung** | Indirekt | Einmal-/Abo-Lizenz | Subscription | Indirekt |
| **Vision-Kompatibilität** | 🟡 Zielgruppe eng | ✅ Passt | ❌ Bricht local-first | 🟡 Kompromiss |
| **Review 05 Score** | Bleibt ⭐⭐ | Potenziell ⭐⭐⭐⭐ | Potenziell ⭐⭐⭐⭐⭐ | Potenziell ⭐⭐⭐ |

---

## Recommendation

Keine Entscheidung empfohlen — diese Frage dient der Dokumentation der strategischen Optionen.

**Plausibler inkrementeller Pfad** (falls entschieden wird, die Zugänglichkeit zu verbessern):

1. **Kurzfristig (Post-MVP):** Option D — One-Click-Deploy-Templates für Fly.io/Railway. Geringer Aufwand, sofortige Verbesserung.
2. **Mittelfristig (Post-MVP Phase 4+):** Option B2 — Tauri-Shell mit verstecktem Docker-Backend. „One-Click Installer" für Desktop.
3. **Langfristig (bei Wachstum):** Option C — Cloud-Angebot als ergänzendes Angebot, nicht als Ersatz.

Dieser Pfad setzt voraus dass die Docker-only-Phase (Option A) die earliest adopter-Gruppe zufrieden stellt, während Zugangsbarrieren iterativ gesenkt werden.

---

## Decision Required By

- **Post-MVP Phase 4** (Platform & Integrations) — bevor MCP/A2A die Nutzerbasis erweitern
- **Spätestens:** Wenn aktives Nutzer-Onboarding beginnt (nicht-dev Nutzer)
- **Idealerweise:** Vor Feature-Complete, um die Architekturentscheidung nicht nachträglich einbauen zu müssen

---

## Related

- `docs/reference/project-vision.md` — Zielgruppen-Definition und Local-first-Prinzip
- `docs/mvp/mvp-plan.md` — Aktuelle Phasen-Planung
- `docs/_shared/TECH_STACK.md` — Technologie-Entscheidungen die Distribution beeinflussen
- `docs/development/deployment-guide.md` — Aktuelle Deployment-Dokumentation
- Q-001 (MCP Auth Strategy), Q-002 (A2A Streaming) — Geplante Client-Erweiterungen

---

> **Status:** 🟡 Open — wartet auf strategische Entscheidungsfindung durch den Projekt-Owner
