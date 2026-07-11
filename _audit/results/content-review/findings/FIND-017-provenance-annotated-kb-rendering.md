# FIND-017: Kein Provenance-annotated KB-Rendering
Priorität: 🟡 Mittel
Status: Offen
Review: cr-04
CR-AUFG: CR-AUFG-04-01
Querverweise: cr-04 §1.1, §4.2.2 (KB-Auto-Extraktion vs manuelle Einträge)

## Befund

Alle 4 Text-Render-Pfade (Format A/B/D/F) haben `preserved_fields=frozenset()`
— kein Provenance-Feld wird in den Prompt-Text gerendert. `KBContextEntry`
trägt `source` (manual/auto_extraction/imported), `confidence` (0.0-1.0),
`review_status` (pending/endorsed/rejected), `freshness` (fresh/stale/pending)
— aber das LLM sieht keine dieser Informationen.

ADR-050 P1-A macht die Omission *explizit* (kein stiller Verlust), aber die
Information kommt nicht beim Konsumenten (LLM) an. Das LLM kann eine manuell
kuratierte Tatsache nicht von einer 0.72-Confidence-Auto-Extraktion
unterscheiden.

## Evidenz

- `packages/core/narrare_core/writing/_helpers.py:format_entities()` —
  `preserved_fields=frozenset()`.
- `packages/core/narrare_core/writing/context_wiki.py:format_entities_with_wiki()`
  — `preserved_fields=frozenset()`.
- `packages/core/narrare_core/prompts/context.py:_format_kb_entries()` —
  `preserved_fields=frozenset()`.
- `packages/core/narrare_core/context/_kb_envelope.py` (L78-145) — Protocol
  macht Omission explizit, bietet aber keine Provenance-Rendering-Option.
- Konkreter Konfliktfall: Auto-Extraktion erstellt Character "The Archer"
  (confidence 0.72), manuell existiert "Aria" (confidence 1.0). Beide werden
  im Prompt identisch gerendert — LLM sieht zwei "verschiedene" Charaktere.

## Auswirkung

- Das LLM behandelt alle KB-Entries als gleichwertig, unabhängig von Quelle
  oder Vertrauenswürdigkeit.
- Bei Konflikten kann das Modell eine fehlerhafte Auto-Extraktion nicht von
  einem kuratierten manuellen Eintrag unterscheiden.
- Fehlerhafte Auto-Extraktionen (die akzeptiert wurden) werden beim Schreiben
  als gleichwertige Fakten injiziert.

## Empfehlung

Erweitere das `KBContextEnvelope`-Protocol um eine Provenance-Rendering-Option.
Bei niedriger Confidence (<0.7), bei `review_status="pending"`, oder bei
`source="auto_extraction"` mit niedriger Confidence soll die Provenance inline
in den Prompt-Text gerendert werden:

```
### Character: Aria Thorne [auto-extracted, confidence: 0.72, pending review]
```

Bei `source="manual"` oder `confidence>=0.9` und `review_status="endorsed"`:
keine Annotation (wie bisher).

**Owner:** Core. **Abstimmung:** Architecture-Specialist (RULE-03
Contract-Erweiterung).

## Verifikation

- [ ] `KBContextEnvelope.render()` hat eine Option für Provenance-Rendering
- [ ] Render-Pfade (_helpers, context_wiki, context.py) implementieren die Option
- [ ] Niedrige Confidence / pending Status → inline Annotation im Prompt-Text
- [ ] Hohe Confidence / endorsed → keine Annotation (wie bisher)
- [ ] Tests verifizieren Provenance-Rendering bei Schwellwerten
