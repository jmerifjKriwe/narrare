# Q-012 — Wie erklären wir dem Nutzer Prompt-Variablen und ermöglichen Reset-to-Default?

| Attribute | Value |
|-----------|-------|
| **ID** | Q-012 |
| **Status** | 🟡 Open |
| **Raised** | 2026-06-08 |
| **Source** | CR-07 UX Audit §6 — Prompt-Anpassbarkeit ⭐⭐☆☆☆ |
| **Blocks** | PROMPT-003 Prompt Customization UX |
| **Depends on** | PROMPT-001, PROMPT-002 |

---

## Frage

Nutzer können in den AI-Einstellungen Prompts anpassen (Custom Instructions
via PROMPT-001/PROMPT-002), aber:

1. **Variablen sind undokumentiert.** Platzhalter wie `{{kb_context}}`,
   `{{chapter_text}}`, `{{character_name}}` werden im UI nicht erklärt.
   Nutzer wissen nicht, welche Daten an dieser Stelle eingefügt werden.

2. **Kein Reset-to-Default.** Einmal geänderte Custom Instructions können
   nicht auf die System-Standards zurückgesetzt werden — außer durch
   manuelles Löschen des Overrides.

3. **Kein Preview.** Der vollständig aufgelöste Prompt (Variable →
   Projektdaten) ist vor dem Absenden nicht einsehbar.

---

## Kontext

Das CR-07 UX Audit hat die AI-Settings-Komponenten (`IntentOverrides.tsx`)
als nicht vollständig auditiert markiert. Die bestehende Infrastruktur
(PROMPT-001: File Overrides, PROMPT-002: DB Templates) erlaubt technisch
bereits die Prompt-Anpassung — aber die UX ist für Endnutzer undokumentiert
und potenziell verwirrend.

Die Lösung hängt von architektonischen Entscheidungen ab:

- **Wie werden Variable-Metadaten gepflegt?** In den Prompt-Dateien
  (YAML-Manifest) oder in einem separaten Registry-Service?
- **Wie tief geht der Preview?** Nur Prompt-Auflösung (statisch) oder
  kompletter KI-Testlauf (dynamisch, Token-Kosten)?
- **Reset-Granularität:** Pro Intent oder global für alle übersteuerten
  Prompts?

---

## Optionen

### Option A: Prompt-Variable-Manifest in `core/prompts/`

Jeder Prompt-Ordner enthält eine `variables.yaml`, die alle verwendeten
Variablen mit Name, Beschreibung, Datenquelle und Beispielwert beschreibt.

**Vorteile:** Single Source of Truth, close to prompt, einfache Wartung.
**Nachteile:** Neuer Dateityp im Prompt-System, muss gepflegt werden.
**Bewertung:** 👍 Empfohlen — minimaler Mehraufwand, maximale Transparenz.

### Option B: Variable Registry Service

Ein Backend-Service `PromptVariableService` aggregiert Variablen-Metadaten
aus der Prompt-Konfiguration und liefert sie über einen API-Endpoint.

**Vorteile:** Vom Prompt-Format entkoppelt, einfach erweiterbar, API-getrieben.
**Nachteile:** Overhead für eine im Kern statische Datenstruktur.
**Bewertung:** 👎 Nicht empfohlen — der Prompt-Ordner ist der natürliche Ort.

### Option C: Nur UI ohne strukturierte Metadaten

Variablen werden direkt im UI-Text (i18n) erklärt, ohne separates Manifest.

**Vorteile:** Schnell zu implementieren.
**Nachteile:** Dokumentation und Implementierung laufen auseinander.
**Bewertung:** 👎 Explizit nicht empfohlen — verursacht CR-07-ähnliche Inkonsistenz.

---

## Resolution

> ⏳ **Noch offen** — wird im Rahmen von PROMPT-003 (Post-MVP) entschieden.
> Vorläufige Tendenz: Option A (Manifest in `core/prompts/`).

---

## Referenzen

- [CR-07 §6 UX Audit](../../_audit/results/content-review/cr-07-ux.md#6-prompt-anpassbarkeit-in-der-webui)
- [PROMPT-003 Prompt Customization UX](../../features/prompt-customization-ux.md)
- [PROMPT-001 File-based Overrides](../../features/prompts/PROMPT-001-file-overrides.md)
- [PROMPT-002 DB Templates](../../features/prompts/PROMPT-002-db-templates.md)
