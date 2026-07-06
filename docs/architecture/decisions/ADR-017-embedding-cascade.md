# ADR-017: Embedding Cascade for mem0

## Status

⛔ Superseded by ADR-033

## Kontext

mem0 benötigt Embeddings für semantische Suche. Nutzer können einen einzelnen LLM-Provider konfiguriert haben (z.ai, Anthropic, OpenAI, Ollama). z.ai und Anthropic bieten keine Embedding-APIs an. Das Memory-System muss für alle Nutzer funktionieren.

## Entscheidung

4-tier Embedding Cascade:

1. **OpenAI** `text-embedding-3-small` — wenn Nutzer OpenAI-Key hat
2. **Provider-native** — Future Hook (nicht implementiert)
3. **Local** `all-MiniLM-L6-v2` via sentence-transformers — keine API nötig
4. **Disabled** — NullMemoryClient fallback

Nutzer können `embedding_provider` in Settings explizit setzen (`"auto"` | `"openai"` | `"local"` | `"disabled"`).

## Konsequenzen

- **Positiv**: Jeder Nutzer hat funktionales Memory, unabhängig vom Provider
- **Positiv**: Beste verfügbare Embedding-Qualität wird automatisch gewählt
- **Negativ**: sentence-transformers als optionale Abhängigkeit (~80MB Model)
- **Negativ**: Embedding-Qualität variiert je nach Tier (akzeptabel für Preference-Matching)
