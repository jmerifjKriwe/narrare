# FIND-005: mem0-Preference-Injection-Gate verhindert Preferences im Writing-Prompt
Priorität: 🟡 Mittel
Status: Offen
Review: cr-03
CR-AUFG: CR-AUFG-03-05
Querverweise: cr-04 §4.1, §4.2.1 (Writing-Style-Learning vs Manual-Override)

## Befund

`PromptComposer.build()` injiziert Preferences nur, wenn der `context`
(PromptContext) "leer" ist. Die WritingContextAssembler-vorangestellten
Services füllen den Context aber immer (`kb_characters`, `chapter_content`,
etc.) — somit greift die Preference-Injection im Writing-Pfad möglicherweise
**nie**.

Der Widerspruch entsteht nicht durch Konflikt, sondern durch Abwesenheit:
mem0-Preferences werden still geschluckt, statt mit Manual-Override zu
konkurrieren. Die architektonisch korrekte Präzedenz ("author instructions >
preferences") wird nie erreicht, weil Preferences gar nicht ankommen.

## Evidenz

- `packages/core/narrare_core/prompts/composer.py:93-113` — Gate-Bedingung
  injiziert Preferences nur bei leerem Context.
- WritingContextAssembler füllt Context immer (KB-Tiers, Chapter-Content).
- `universal/en/system.md:15` — "When author instructions contradict user
  preferences, always follow the author instructions." (Präzedenz klar geregelt,
  aberPreferences kommen nie an).

## Auswirkung

mem0-Preferences (Satzlänge, Ton, Wortschatz, Pacing, etc.) erreichen die
Writing-Prompts nicht. Das Preference-Learning (LEARN-001) ist funktional
eingeschränkt: Feedback wird gespeichert, aber die abgeleiteten Preferences
werden im wichtigsten Use-Case (Writing) nicht angewendet. Der Nutzer merkt
keinen Effekt vom Preference-Learning beim Schreiben.

Beispiel: Autor schreibt nie Dialoge → mem0 lernt "präferiert Beschreibungen"
→ aber Writing-Continue injiziert diese Preference nie → Modell generiert Dialoge.

## Empfehlung

Gate-Bedingung anpassen: Preferences sollen auch bei gefülltem
KB/Chapter-Context injiziert werden, da sie orthogonal sind. Preferences und
KB-Context konkurrieren nicht um denselben Slot — sie ergänzen sich.

**Owner:** Core.

## Verifikation

- [ ] Verifiziert: Preference-Injection greift im Writing-Pfad mit gefülltem Context
- [ ] Test: Writing-Continue mit konfiguriertem mem0 erhält `{{user_preferences}}`
- [ ] Gate-Bedingung in `composer.py` angepasst (Preferences orthogonal zu Context)
- [ ] Preference-Werte sind nicht-leer im Writing-Prompt (Runtime-Probe)
