# Narrare Plan Template

## [Titel]

## Context
[Warum wird diese Änderung gemacht? Das Problem oder der Anlass, und das gewünschte Ergebnis.]

## Agent-Workflow

| Phase | Agent | Output |
|-------|-------|--------|
| Architektur | `narrare-architecture` | Contract, ADR |
| Implementation | `narrare-implementation` | Code |
| Testing | `narrare-testing` | Tests |

_Passe diese Tabelle an deinen spezifischen Workflow an — nicht jede Aufgabe benötigt alle Phasen._

## Schritte

### 1. Architektur (→ narrare-architecture)
- [ ] Contract definieren
- [ ] ADR erstellen
- [ ] Module boundaries festlegen

### 2. Implementation (→ narrare-implementation)
- [ ] Service implementieren
- [ ] Router anpassen
- [ ] Constraints einhalten

### 3. Testing (→ narrare-testing)
- [ ] Unit tests schreiben
- [ ] Coverage prüfen
- [ ] Integration tests

## Verification
[Wie wird das Ergebnis getestet? Welche Kommandos laufen, um zu verifizieren?]

## Referenzen
- `docs/_shared/CONSTRAINTS.md` — Architektur-Regeln
- `docs/development/coding-standards.md` — Coding Standards
- `docs/development/testing-standards.md` — Testing Standards
