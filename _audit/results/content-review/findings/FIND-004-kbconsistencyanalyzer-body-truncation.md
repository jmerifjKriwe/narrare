# FIND-004: KBConsistencyAnalyzer Body-Truncation hardcoded
Priorität: 🟡 Mittel
Status: Offen
Review: cr-03
CR-AUFG: CR-AUFG-03-04

## Befund

`KBConsistencyAnalyzer` trunciert `entity.body[:5000]` hardcoded. Bei
Einträgen >5000 Zeichen schneidet der Consistency-Check mitten im Content ab
— das Modell sieht unvollständige Daten und kann Feld-Widersprüche, die im
abgeschnittenen Teil liegen, übersehen.

## Evidenz

- `apps/api/narrare/kb/consistency_analyzer.py:199` — `entity.body[:5000]`
  hardcoded.
- `ConsistencyOrchestrator` bekommt `max_chapter_tokens` als Param, aber keine
  Tier-Allokation — KB-Body hat kein Budget-System.

## Auswirkung

KB-Entries mit >5000 Zeichen Body werden für den Consistency-Check verstümmelt.
Feld-Widersprüche, Konflikte oder Inkonsistenzen im abgeschnittenen Teil werden
nicht geprüft. Bei detaillierten KB-Einträgen (umfangreiche Charakter-Backstory)
ist dies ein realer Qualitätsverlust.

## Empfehlung

Token-bewusste Truncation oder Budget-basierte Kürzung einführen. Zumindest
dokumentieren/parametrisieren, dass 5000 Zeichen ein bewusstes Limit sind
(analog `NARRARE_CONSISTENCY_MAX_CHAPTER_TOKENS` / `NARRARE_CONSISTENCY_MAX_KB_ENTRIES`
die bereits als Env-Vars existieren).

**Owner:** Backend.

## Verifikation

- [ ] Body-Truncation ist parametrisierbar (Env-Var oder Method-Param)
- [ ] Token-bewusste Kürzung statt starrer 5000-Zeichen-Grenze
- [ ] Dokumentiert, ob 5000 Zeichen bewusst oder Tech-Debt
