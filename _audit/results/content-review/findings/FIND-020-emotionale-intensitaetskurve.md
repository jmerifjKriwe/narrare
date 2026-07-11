# FIND-020: Emotionale Intensitätskurve (Sentiment-Arc) nicht visualisiert
Priorität: 🟡 Mittel
Status: Offen (Enhancement)
Review: cr-07
CR-AUFG: CR-AUFG-07-28

## Befund

Das Backend hat bereits Sentiment-Analyse (`useSentiment.ts`,
`analysis.sentiment`-Namespace). Es gibt jedoch **keine Visualisierung** als
Kapitel-Intensitätskurve — ein Feature, das für Schriftsteller enorm wert
wäre (Pacing-Editing, emotionale Strukturierung, "Show don't tell"-Checks).

Entsprechend `ui-principles.md` §14 ("Future chart types: sentiment arc over
chapter progression (time series)") ist dies bereits als geplantes
ANAL-Feature dokumentiert, aber nicht implementiert.

Dies ist ein **Enhancement** (Alleinstellungsmerkmal), kein Defekt.

## Evidenz

- `packages/web/lib/hooks/useSentiment.ts` — Sentiment-Hook (SSE) existiert.
- `packages/web/.../editorRightPanelState.ts` — `EditorRightPanelId` enthält
  bereits `"sentiment"` (Slot existiert, Panel fehlt).
- `docs/development/ui-principles.md` §14 — "Future chart types: sentiment arc
  over chapter progression (time series)" als geplant dokumentiert.
- Recharts bereits im Stack (für ScoreRadar genutzt).

## Auswirkung

Narrare verschenkt ein Alleinstellungsmerkmal: Pacing- und Emotions-Editing
visualisiert wäre ein Narrare-spezifisches Feature, das kein konkurrierendes
AI-Writing-Tool bietet. Schriftsteller müssen Pacing mental verfolgen statt
visuell.

## Empfehlung

- Recharts `<LineChart>` (bereits im Stack).
- X-Achse: Kapitel-Position (Token-Offset oder Absatz-Index).
- Y-Achse: Sentiment-Intensity (-1.0 bis +1.0 oder normalisiert 0-10).
- Interaktiv: Hover zeigt Text-Snippet an der Position.
- Integration in Editor-Right-Panel (`EditorRightPanelId = "sentiment"` —
  Slot existiert bereits).
- Mehrere Kapitel vergleichbar (Overlay oder getrennte Linien).

**Owner:** Frontend + Backend.

## Verifikation

- [ ] Sentiment-Panel öffnet via Toolbar/Sidebar
- [ ] LineChart rendert mit Theme-Tokens
- [ ] Hover-Tooltip mit Text-Snippet
- [ ] URL-deep-linkbar (`?panel=sentiment`)
