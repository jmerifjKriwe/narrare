# FIND-002: Coreference ohne Charakter-Liste
Priorität: 🔴 Hoch
Status: Offen
Review: cr-03
CR-AUFG: CR-AUFG-03-02
Querverweise: cr-04 §2.2, §4.1 (funktionaler Adoptions-Fehler)

## Befund

Der Coreference-Service setzt **alle** KB-Variablen (`kb_characters`,
`kb_locations`, `kb_factions`, `kb_relationships`) auf leere Strings.
Coreference-Resolution (Pronomen → Charakter-Zuordnung) braucht aber
zwingend die Charakter-Liste des Romans, um Pronomen korrekt zuzuordnen.
Das Modell muss raten.

Dies ist ein **funktionaler Adoptions-Fehler** — kein Budget-Problem, sondern
ein fehlendes Runtime-Wiring. Das Template hat die Variable (Registry:
adopted), aber der Runtime-Wert ist leer.

## Evidenz

- `apps/api/narrare/analysis/coreference_service.py:175-179` — setzt alle
  KB-Variablen auf `=""`.
- Kommentar im Code: *"No KB repository is wired for this call path (the
  service constructor intentionally omits it)"*.
- `_bundled/analysis/en/coreference/system.md` — Template erwartet
  `{{kb_characters}}` (Registry: adopted), erhält aber leeren String.
- Verifiziert via Read von `coreference_service.py` + Grep nach
  `kb_characters`.

## Auswirkung

Pronomen-Resolution ohne Charakter-Liste produziert falsche oder ungenaue
Zuordnungen. Das Modell kann "er" oder "sie" nicht verlässlich einem
Charakter zuordnen, wenn es die Charakter-Namen nicht kennt. Die
Analyse-Qualität der Coreference-Funktion ist strukturell eingeschränkt.

Zusätzlich: Kein maschinelles Gate erkennt diese Runtime-Lücke — die
Adoption-Registry prüft nur Template-Variablen-Präsenz (statisch), nicht
ob der Runtime-Wert nicht-leer ist (CR-AUFG-03-08).

## Empfehlung

Wire das `KBRepositoryProtocol` in den Coreference-Service. Lade Charaktere
für den Roman und fülle `kb_characters` mit echten Daten. Evaluiere
zusätzlich, ob `kb_locations` und `kb_relationships` für Coreference-Relevant
sind.

**Owner:** Backend.

## Verifikation

- [ ] `coreference_service.py` hat ein `KBRepositoryProtocol`-Dependency
- [ ] `kb_characters` wird zur Runtime mit echten Charakter-Daten gefüllt
- [ ] Test: Coreference mit bekannten Charakteren liefert bessere Ergebnisse
- [ ] Runtime-Probe zeigt nicht-leere `kb_characters`-Werte
