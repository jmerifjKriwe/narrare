# Narrare – AI Content Review Framework

Ergänzt das technische Review-System (`_audit/review-prompts/technical-review-prompts`) um inhaltliche Qualitätssicherung.

## Abgrenzung

| Technisches Review (`_audit/review-prompts/technical-review-prompts`) | Inhaltliches Review (`_audit/review-prompts/content-review-prompts`) |
|---|---|
| Funktioniert die Cascade-Resolution? | Sind die Prompt-Inhalte effektiv? |
| Existieren alle API-Endpoints? | Nutzen die Endpoints die Features konsistent? |
| Coverage ≥ 70%? | Widersprechen sich Features inhaltlich? |
| Läuft mem0-Client? | Wird mem0 dort genutzt, wo es sinnvoll ist? |

## Verzeichnisstruktur

```
_audit/review-prompts/content-review-prompts/   ← Diese Templates (Quelltext, nicht anfassen)
_audit/results/content-review/           ← Ausgefüllte Reviews (von der Projekt-AI befüllt)
  ├── README.md                 ← Aktueller Stand + Befund-Index
  ├── audit-prompts/
  │   ├── kb-prompts.md
  │   ├── writing-prompts.md
  │   └── analysis-prompts.md
  ├── adoption/
  │   ├── mem0-adoption.md
  │   ├── context-budget-adoption.md
  │   └── kg-adoption.md
  ├── coherence/
  │   ├── kb-writing-coherence.md
  │   └── persona-consistency.md
  └── findings/
      ├── FIND-001-*.md
      ├── FIND-002-*.md
      └── ...
```

## Review-Zyklen

| Typ | Rhythmus | Auslöser |
|---|---|---|
| **Sprint-Review** | Wöchentlich | Neue Prompts, geänderte Features |
| **Major Review** | Quartalsweise | Vollständiger Audit aller Bereiche |
| **Ad-hoc Review** | Bei Bedarf | Neue Features, grundlegende Prompt-Änderungen |

## Verwendung mit Claude Code

```bash
# Kontext zuerst (falls noch nicht aus technischem Review vorhanden)
claude "Führe _audit/review-prompts/content-review-prompts/cr-00-kontext.md aus"

# Einzelne Reviews
claude "Führe _audit/review-prompts/content-review-prompts/cr-01-prompt-quality.md aus"

# Vollständiger Content-Review-Lauf
claude "Führe alle Prompts in _audit/review-prompts/content-review-prompts/ der Reihe nach aus (cr-00 → cr-08)"
```

## Reihenfolge

| Datei | Thema | Führt Review durch? |
|---|---|---|
| `cr-00-kontext.md` | Projekt- und Prompt-Kontext | Ja - zuerst |
| `cr-01-prompt-quality.md` | Default-Prompts und Prompt-Standards | Ja |
| `cr-02-system-prompt.md` | Capability-basierte Prompt-Architektur und KI-Persona | Ja |
| `cr-03-feature-adoption.md` | mem0, ContextBudget, KG, Prompt-Anreicherung | Ja |
| `cr-04-cross-feature.md` | Cross-Feature-Kohärenz | Ja |
| `cr-05-initial-findings.md` | Bekannte Befunde vertiefen | Ja |
| `cr-07-ux.md` | UI/UX und AI-Interaktionsqualität | Ja |
| `cr-08-hardcoded-values.md` | Hardcodierte Werte und Konfigurierbarkeit | Ja |
| `cr-06-summary.md` | Gesamtbewertung und Roadmap | Ja - zuletzt |

## Quellen-Aktualität

- Lies vor jedem Review `docs/_shared/CONSTRAINTS.md`, `docs/development/prompt-standards.md`, `docs/development/prompt-content-standards.md` und `docs/development/ui-principles.md`.
- Prüfe relevante ADRs aus `docs/architecture/decisions/`; neuere akzeptierte ADRs schlagen Annahmen in diesen Templates.
- Insbesondere ADR-026 gilt für Prompt-Injektion: garantierte Inhalte über Capabilities, anpassbare Inhalte über PromptComposer/Cascade, dynamische Daten über PromptContext/Variablen.
- Nutze im Narrare-Projekt zuerst die Code-Review-Graph MCP Tools. `Glob`/`Grep`/`Read` sind nur gezielte Fallbacks, wenn der Graph die Information nicht liefert.

## Checkliste für neue Features (in AGENTS.md integrieren)

Vor jedem Merge einer neuen AI-Funktion prüfen:

- [ ] Nutzt die Funktion mem0, wo Cross-Session-Kontext sinnvoll ist?
- [ ] Nutzt die Funktion ContextBudget für Kontext-Management?
- [ ] Wird KB-Context in einheitlichem Format injiziert?
- [ ] Ist der System-Prompt zentralisiert (nicht inline im Code)?
- [ ] Sind garantierte Regeln/Persona über Capabilities abgesichert (ADR-026)?
- [ ] Ist der Prompt konsistent mit bestehenden Prompts (Stil, Persona, Struktur)?
- [ ] Sind Prompt-Locale-Anforderungen korrekt erfüllt: Meta/Universal Rules mehrsprachig, Feature-Templates gemäß aktueller ADR/Prompt-Standards?
- [ ] Gibt es keine inhaltlichen Widersprüche zu anderen Features?
- [ ] Kann der Nutzer diesen Prompt in der WebUI anpassen?

## Befund-Konventionen

```
FIND-[NNN]-[kurzer-titel].md
Priorität: 🔴 Hoch / 🟡 Mittel / 🟢 Niedrig
Status: Offen / In Bearbeitung / Gelöst
```

### Strukturmarker für CR-08-Konfigurations-/Effekt-Befunde

Materielle P0/P1-Befunde, bei denen ein konfigurierter oder dokumentierter Wert
nicht nachweisbar am Runtime-Effekt ankommt, werden zusätzlich maschinenlesbar
markiert (empfohlene Konvention für Ad-hoc-Audits; Review-Datei als SSOT):

```markdown
- [P1] [category: configuration-effect] FIND-099 / CR-AUFG-08-99: Kurzbeschreibung
```

Der Marker ist eine empfohlene Konvention, nicht maschinengesteuert. Es gibt keine
Configuration Adoption Matrix und keinen Checker mehr — beide wurden mit `f8abb42c`
bewusst entfernt (ADR-047/051/061/062 ⛔ Superseded). Befunde werden als Prosa/Aufgabe
direkt in der Review-Datei geführt. RULE-18b wird über Per-Value-Regressionstests +
ADR-045 (Runtime Adoption Enforcement) + Ad-hoc-Audits durchgesetzt.
