# FIND-016: Writing de/fr Legacy-Templates — ADR-026 Phase 5 Deviation
Priorität: 🟡 Mittel
Status: Offen
Review: cr-02
CR-AUFG: CR-AUFG-02-09
Querverweise: cr-00 §6 (bekanntes Problem), cr-04 §5.5 (i18n-Inkonsistenz)

## Befund

6 Writing-Modi existieren in de/fr (`chat`, `co_author`, `inline_suggest`,
`interview`, `new_chapter`, `rewrite_selection`), obwohl ADR-026 Phase 5
EN-only für Feature-Prompts vorschreibt. Diese Templates sind weder vollständig
(4 EN-Modi fehlen in de/fr: `extend_chapter`, `interactive_session`,
`scene_by_scene`, `story_suggest`) noch mit dem EN-only-Standard konsistent.

Die de/fr-Templates haben eigene Rollenbeschreibungen ("Du bist ein versierter
Assistent für kreatives Schreiben"), die vom EN-Standard abweichen könnten.
Sie sind nicht Teil der normalen Review-Zyklen — Content-Drift zwischen EN und
de/fr ist möglich.

## Evidenz

- `packages/core/narrare_core/prompts/_bundled/writing/de/` — 6 Modi.
- `packages/core/narrare_core/prompts/_bundled/writing/fr/` — 6 Modi.
- ADR-026 Phase 5: "adding DE/FR copies of bundled feature system prompts is
  architectural drift: it multiplies templates without improving output-language
  control."
- Fehlende de/fr-Modi: `extend_chapter`, `interactive_session`, `scene_by_scene`,
  `story_suggest`.
- `prompt-standards.md` §5 — EN-only-Standard für Feature-Prompts.

## Auswirkung

- Content-Drift-Risiko: de/fr-Templates können vom EN-Standard abweichen, ohne
  dass Reviews es merken.
- Inkonsistenz: 6 von 10 Modi lokalisiert — halbfertige Lokalisierung.
- Wartungslast: Änderungen am EN-Standard müssen in de/fr nachgezogen werden.

## Empfehlung

ADR-026 Phase 5 ist explizit: Output-Sprache wird über `{{writing_language}}`
gesteuert (EN-Instructions + DE-Output funktioniert zuverlässig).

**Option 1 (Empfohlen):** Entfernen — de/fr-Templates löschen. Die de/fr
Meta/Universal-Capabilities bleiben mehrsprachig (persona/safety sind
locale-sensitiv per Phase 5 Tabelle).

**Option 2:** Behalten + vervollständigen — alle 10 EN-Modi nach de/fr
übersetzen. Hoher Wartungsaufwand, widerspricht Phase 5 Intention.

**Option 3:** Als offizielle lokalisierte Prompt-Familie deklarieren — erfordert
ADR-Änderung.

**Owner:** Core + Architecture (ADR-Entscheidung).

## Verifikation

- [ ] Architektur-Entscheidung dokumentiert (Entfernen vs. Behalten)
- [ ] Falls Entfernen: `writing/de/` und `writing/fr/` gelöscht; Output-Sprache
      über `{{writing_language}}` verifiziert
- [ ] Falls Behalten: als lokalisierte Prompt-Familie in ADR deklariert,
      Versions-Parität mit EN hergestellt
- [ ] `prompt-inventory.yaml` aktualisiert
