---
description: Sicheres Refactoring — Impact-Analyse + Test-First
---

Sicheres Refactoring. Ziel: $ARGUMENTS

1. **Impact-Analyse via graphify**: `graphify explain "<symbol>"` und
   `graphify path "<von>" "<nach>"` — welche Aufrufer sind betroffen? Volle Reichweite
   verstehen, bevor das erste Symbol bewegt wird.
2. **Sicherheitsnetz**: bestehende Tests prüfen; Lücken VOR dem Refactor schließen.
3. **Kleine Schritte**: nach jedem Schritt `just test-unit` + `just typecheck`.
4. **Keine Verhaltensänderung** — reines Refactoring. Verhaltensänderung = separater Schritt.
5. **RULE-XX einhalten**, besonders RULE-04 (modularisieren statt komprimieren) und
   RULE-06 (eine Verantwortlichkeit pro Datei).

Skills bei Bedarf: `verification-before-completion`, bei Frontend-Component-Architektur
`vercel-composition-patterns`.
