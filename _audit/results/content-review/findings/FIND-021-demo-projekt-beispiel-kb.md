# FIND-021: Kein Demo-Projekt mit Beispiel-KB für Onboarding-Aha-Moment
Priorität: 🟡 Mittel
Status: Offen (Enhancement)
Review: cr-07
CR-AUFG: CR-AUFG-07-29

## Befund

Der Wizard (`WizardShell.tsx`) und Quick-Start (`useQuickStart.ts`) erstellen
ein **leeres Projekt** (`starter: "blank"`). Die `FeatureTour` ist global
verdrahtet und erklärt konzeptionell das Zusammenspiel (Tour-Step 7: "KB →
Context → AI", Step 8: "Storyboard → Chapter → AI"). **Aber:** Der Nutzer kann
das Erklärte nicht sofort ausprobieren, da das Projekt leer ist — es gibt keine
Beispiel-KB, keine Beispiel-Characters, kein Beispiel-Kapitel.

Der "wahre" Aha-Moment (KI generiert Text MIT KB-Kontext) erfordert, dass der
Nutzer erst manuell KB-Einträge anlegt. Für Neueinsteiger ist der Weg vom
Onboarding zum ersten sinnvollen KB-gestützten AI-Erlebnis zu lang.

Dies ist ein **Enhancement** (Onboarding-Verbesserung), kein Defekt.

## Evidenz

- `packages/web/.../useQuickStart.ts:37` — `starter: "blank"` (leeres Projekt).
- `packages/web/.../useQuickStart.ts:48` — `requestFeatureTour()` nach Quick-Start.
- `packages/web/.../StudioWorkspaceShell.tsx:68` — `<FeatureTour>` global gerendert.
- `packages/web/.../feature-tour-steps.ts:43-52` — Step 7-8 erklären KB→AI,
  Step 9 "before/after demo moment" definiert aber nicht aktiv.
- Kein Sample-Novel oder Beispiel-KB im Code gefunden.

## Auswirkung

Neueinsteiger verstehen das KB→AI-Konzept (Tour erklärt es), können es aber
nicht sofort erleben. Der "Aha-Moment" (KI mit KB-Kontext generiert deutlich
besseren Text) erfordert vorheriges manuelles KB-Anlegen. Abbruch-Rate bei
Onboarding möglicherweise höher als nötig.

## Empfehlung

1. **Demo-Starter (neue Option):** Quick-Start erhält einen `starter: "demo"`
   Modus, der ein Projekt mit vorausgefüllter Beispiel-KB erstellt:
   - 2 Beispiel-Characters (Protagonist + Antagonist mit Description/Backstory)
   - 1 Beispiel-Location
   - 1 Beispiel-Kapitel (~500 Wörter) mit @-Mentions der Characters
   - Beispiel-Outline
2. **Leere-State-Guides:** Wenn KB leer ist, zeige Hinweis mit CTA zum
   Assisted-Creation-Flow.
3. **Tour-Step 9:** Sollte den Nutzer aktiv dazu bringen, eine AI-Operation
   auszulösen.

**Vorhandene Infrastruktur:** FeatureTour global, KB-Assisted-Creation-Flow,
Backend `setupApi.complete` akzeptiert `starter`-Feld (Erweiterung um `"demo"`).

**Owner:** Backend + Frontend.

## Verifikation

- [ ] Quick-Start mit `starter: "demo"` erstellt Projekt mit ≥2 KB-Entities
- [ ] Continue/Extend mit Demo-KB liefert明显 bessere Ergebnisse als ohne
- [ ] Leere-KB-State hat erklärende Hinweise mit CTA
- [ ] "Aha-Moment" innerhalb von 2 Minuten nach Onboarding erlebbar
