# ADR-021 — Deterministic Analysis Strategy

> **Status:** ✅ Accepted
> **Date:** 2026-05-27
> **Deciders:** Architecture Specialist
> **Affects:** `core/nlp/`, `core/analysis/`, analysis features ANAL-001 through ANAL-011, consistency features CONS-001/CONS-002, analytics features STATS-001/STATS-002

---

## Context

Narrare plans 11 analysis features (ANAL-001 through ANAL-011), 2 consistency features (CONS-001, CONS-002), and 2 analytics features (STATS-001, STATS-002). The original feature specs assumed LLMs as the sole analysis engine.

**Problem:** LLMs are non-deterministic. If a writer runs sentiment analysis on the same chapter twice (or with a minor edit), they may get dramatically different VAD scores, leading to wrong editing decisions. The user explicitly flagged this:

> "I ask an LLM twice and once it goes right, once it goes wrong, and I get two completely different analyses from which I draw wrong conclusions."

**Root Cause (2x Why):**

1. **Why different results?** → LLMs sample from probability distributions, so identical inputs can produce different outputs.
2. **Why is this a problem?** → The original specs conflated MEASUREMENT (needs determinism) with UNDERSTANDING (qualitative is OK). Using one tool for both is an architectural category error.

**Key insight:** The analysis suite must separate measurement (deterministic, comparable across edits) from understanding (qualitative, LLM-appropriate). These are fundamentally different operations that require fundamentally different tools.

---

## Decision Drivers

- **Reproducibility:** Writers must be able to trust that the same text produces the same metric. Non-deterministic measurement is worse than no measurement — it leads to wrong editing decisions.
- **Comparability:** Analysis results must be comparable across edits. "Did chapter 3's sentiment improve after my revision?" requires deterministic measurement.
- **Cost:** LLM calls for every analysis feature (stats, readability, sentiment) would be expensive and slow. Deterministic computation is free and instant.
- **TECH_STACK philosophy:** "We choose boring technology where possible." spaCy is boring, well-maintained, and stable — exactly what the philosophy calls for.
- **Python 3.14 compatibility:** The project requires Python 3.14+. Any new dependency must support (or be likely to support) this version.
- **RULE-08 compliance:** All external integrations must be abstracted behind a Protocol. spaCy is no exception.

---

## Options Considered

### Option A — Local BERT/Transformer Models (distilBERT, mDeBERTa)

Deterministic sentiment and NER via forward pass through fixed model weights.

- **Models:** `distilbert-base-multilingual-cased-sentiments` (Apache-2.0), `mDeBERTa-v3-base-xnli` (MIT)
- **Dependency:** ~1.5GB (PyTorch) or ~200MB (ONNX Runtime)
- **Literary domain:** Trained on reviews/tweets, NOT literary prose

**Pros:**
- Deterministic output (fixed weights, no sampling)
- Better context-awareness than word-level lexica
- Transformer architectures handle subword tokens well

**Cons:**
- **Python 3.14 compatibility: UNCERTAIN.** PyTorch typically lags 3–6 months behind new Python releases. This is a showstopper for a hard dependency.
- Literary domain mismatch: these models are trained on social media text and product reviews, not literary prose
- ~1.5GB dependency (PyTorch) is heavy for analysis-only functionality
- ONNX Runtime reduces size but adds a second complex dependency

**Verdict: REJECTED** — Python 3.14 risk is a showstopper for a hard dependency. Literary domain mismatch.

### Option B — spaCy + Multilingual Lexica (CHOSEN for measurement)

Deterministic NLP pipeline with fixed models and lexicon-based scoring.

- **Dependency:** ~175MB (spaCy + 3 language models for DE/EN/FR)
- **Python 3.14:** MORE LIKELY — spaCy uses Thinc (numpy-backed), not PyTorch
- **Existing project data:** `german_pronouns.py` (1333 lines of German pronoun data in `_scratch/`)

**Pros:**
- Deterministic: pipeline with fixed models + lexicon lookup produces identical output for identical input
- Well-maintained, stable library ("boring technology" per TECH_STACK philosophy)
- spaCy's POS, NER, and sentence splitting work well on any text domain
- Thinc/numpy backend has better Python version compatibility than PyTorch
- Existing project data (`german_pronouns.py`) can seed language-specific rules
- Lower resource footprint than transformer models

**Cons:**
- Lexicon-based sentiment is word-level — misses context, irony, subtext, metaphor
- spaCy coref quality for DE/FR is lower than EN — needs language-specific pronoun rules
- ~175MB new dependency (spaCy + 3 language models)
- NRC EmoLex is CC BY-SA 3.0 (data license, not code)

**Verdict: ACCEPTED as deterministic NLP backbone.**

### Option C — Embedding-based Scoring (pgvector, existing infrastructure)

Score texts by computing cosine similarity between text embeddings and label embeddings (e.g., "joy", "sadness").

- **Dependency:** Zero — uses existing pgvector + embedding infrastructure
- **Deterministic:** Same text → same embedding → same cosine similarity

**Pros:**
- Zero new dependencies — leverages existing infrastructure
- Deterministic (same embedding, same result)
- Multilingual for free (embedding models handle multiple languages)

**Cons:**
- **Critical semantic flaw:** "Text similar to joy text" ≠ "text that expresses joy." Embedding similarity measures topical similarity, not sentiment. A paragraph about a funeral could have high similarity to "sadness" embeddings simply because it discusses sadness-related topics — but the text might be a darkly comedic scene where characters laugh through grief.
- Embedding similarity is a blunt instrument for nuanced literary analysis
- Would conflate topic and tone, producing unreliable metrics

**Verdict: REJECTED as primary strategy. ACCEPTED as supplementary signal for voice drift detection (ANAL-009) where "how different is this chapter's embedding from the story's average" is the actual question.**

### Option D — LLM + Aggressive Caching (original proposal)

Use LLMs for all analysis but cache results keyed by content hash.

**Pros:**
- Best literary understanding (irony, subtext, metaphor, cultural context)
- Simple architecture — one tool for everything
- Content-hash caching ensures "same text, same result" for cached queries

**Cons:**
- **The caching fallacy:** Content-hash caching solves "same query, same result" but does NOT solve "similar query, similar result." A one-word edit = completely fresh non-deterministic LLM call. Writers editing iteratively (the core use case) will get inconsistent results.
- Hides non-determinism behind a cache — the illusion of determinism, not actual determinism
- Expensive at scale: every analysis feature = LLM call per chapter
- Slow: LLM latency (1–5s) vs. deterministic computation (<10ms)

**Verdict: REJECTED for measurement features. ACCEPTED for understanding-grade features (ANAL-010 Literary Suite, ANAL-006 Sensitivity) where qualitative interpretation IS the product.**

---

## Decision

**Tiered Hybrid Architecture** — assign each feature to the simplest tool that produces reliable results:

### Feature-to-Tool Mapping

| Feature | Tool | Determinism | Rationale |
|---------|------|-------------|-----------|
| STATS-001 Writing Stats | Pure Python | Exact | Counting words/sentences/paragraphs needs no NLP |
| STATS-002 Cost Tracking | Pure Python + existing `observability.py` | Exact | Arithmetic on tracked costs |
| ANAL-003 Readability | Pure Python formulas + spaCy for syllables | Exact | Flesch/Kincaid/Fog are deterministic formulas |
| ANAL-002 Sentiment | spaCy + NRC EmoLex + algorithmic arc detection | Deterministic | Lexicon scoring + structural signals |
| ANAL-007/008/009 Voice | spaCy structural metrics + optional embeddings | Deterministic | Sentence length variation, dialogue ratio, vocabulary richness |
| ANAL-005 Coreference | spaCy NER + language-specific pronoun rules | Deterministic | Pattern matching + pronoun resolution rules |
| ANAL-004 POV | spaCy (pronouns/scenes) + LLM (head-hopping) | Hybrid | Pronoun detection is deterministic; head-hopping requires literary understanding |
| ANAL-011 Plot | spaCy (pacing) + LLM (arc/conflicts) | Hybrid | Sentence-based pacing is deterministic; narrative arc requires interpretation |
| CONS-001 Consistency | KB=rule-based, Prosa=LLM | Hybrid | KB facts can be checked deterministically; prose consistency requires understanding |
| ANAL-006 Sensitivity | LLM + cache | Non-deterministic | Cultural sensitivity is inherently interpretive |
| ANAL-010 Literary Suite | LLM + cache | Non-deterministic | Literary analysis (metaphor, theme, symbolism) is qualitative by nature |
| CONS-002 Custom Rules | LLM + cache | Non-deterministic | User-defined rules may require flexible interpretation |

### Architectural Principle

The tiering follows a clear principle:

- **Exact** → Pure computation. No external dependencies. Word counts, arithmetic.
- **Deterministic** → spaCy + lexica. Same input always produces same output. Suitable for measurement that writers compare across edits.
- **Hybrid** → Deterministic for the measurable parts, LLM for the interpretive parts. UI clearly labels which is which.
- **Non-deterministic** → LLM. For features where interpretation IS the product. Cache reduces cost but users understand these are AI opinions, not measurements.

---

## Rationale

1. **Root cause addressed:** The original specs conflated measurement with understanding. This tiered approach puts each feature on the right tool for its actual job. Writers get deterministic metrics they can trust AND qualitative insights from the LLM — but they always know which is which.

2. **spaCy is boring technology (TECH_STACK philosophy):** Well-maintained, stable, MIT-licensed, ~50MB core. It does exactly what we need (POS, NER, sentence splitting, tokenization) without the PyTorch compatibility risk of Option A.

3. **The caching fallacy is real:** Option D's content-hash caching creates an illusion of determinism. A writer who edits one sentence in a 3000-word chapter gets a completely fresh, non-deterministic LLM call. The metrics they relied on for editing decisions are now different — not because the text changed meaningfully, but because the LLM sampled differently. This is unacceptable for measurement tools.

4. **No new LLM costs for measurement:** 8 of 15 features use deterministic or pure computation. No LLM tokens consumed for word counts, readability scores, sentiment lexicon lookups, or structural voice metrics.

5. **Graceful degradation path exists:** If spaCy doesn't support Python 3.14 at implementation time, we follow the ADR-017 cascade pattern — degrade to regex-based analysis for the affected features. This is not ideal but is a documented, temporary fallback.

---

## Consequences

### Positive

- **Deterministic measurement** that writers can trust and compare across edits — the core problem is solved
- **spaCy is "boring technology"** per TECH_STACK philosophy — well-maintained, stable, no version churn
- **Clear UI separation:** "Computed metrics" (deterministic) vs. "AI insights" (qualitative) — users always know which is which
- **Python 3.14 risk is low** — spaCy uses Thinc/numpy, not PyTorch; historically faster to support new Python versions
- **No new LLM costs** for 8 of 15 analysis features — pure computation and spaCy are free
- **Solution scales to all planned features** — the tiering principle applies to any future analysis feature
- **Existing project data reused** — `german_pronouns.py` (1333 lines) seeds the German pronoun resolver

### Negative / Tradeoffs

- **~175MB new dependency** — spaCy (~50MB) + 3 language models (~40MB each for DE/EN/FR)
- **Lexicon-based sentiment is less nuanced than LLM** — misses irony, subtext, metaphor. Acceptable for measurement (we're honest about limitations) but some users may expect LLM-quality interpretation from all features
- **spaCy coref quality for DE/FR is lower than EN** — needs language-specific pronoun rules as primary resolver, with spaCy NER as supplementary signal
- **NRC EmoLex is CC BY-SA 3.0** — this is a data license, not a code license. Acceptable for our MIT project (we ship the data, not derivative works of it), but requires attribution
- **Hybrid features (ANAL-004, ANAL-011, CONS-001) need careful UI design** — the deterministic and LLM components must be visually distinct so users know what they can trust as measurement vs. what is interpretive
- **Additional maintenance surface** — spaCy + language models + lexica need version management alongside our existing dependencies

### Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Literary text and lexica don't mix well — lexica trained on general text, not literary prose | Medium | Medium | Combine lexicon scoring with structural signals (sentence position, dialogue context). Label clearly in UI: "Lexicon-based analysis. Does not detect irony, subtext, or metaphor." |
| spaCy coref quality insufficient for DE/FR | Medium | Medium | Language-specific pronoun rules as primary resolver (following `german_pronouns.py` pattern). spaCy NER as supplementary signal. Future: Stanza as optional dependency when PyTorch supports 3.14. |
| spaCy doesn't support Python 3.14 at implementation time | Low | High | Graceful degradation to regex-based analysis (following ADR-017 cascade pattern). This is a temporary fallback, not a permanent state. |
| Users expect LLM-quality interpretation from deterministic features | Medium | Low | Clear UI labeling: "Computed metric" vs. "AI interpretation." For full interpretation, direct users to ANAL-001 Beta Reader. |
| NRC EmoLex license incompatibility | Very Low | Low | CC BY-SA 3.0 applies to the data itself. We include attribution in the lexicon loader. Our MIT license covers the code. No derivative work of the lexicon is created. |

---

## Constraints Affected

| Rule | Impact | How we satisfy it |
|------|--------|-------------------|
| RULE-01 | No impact — spaCy is not an LLM. LLM calls for understanding features still go through `core/agents/` → `core/llm/gateway.py` | ✅ |
| RULE-02 | No impact — spaCy has no prompts. LLM prompts for understanding features still built in `core/prompts/` | ✅ |
| RULE-03 | New `NLPProvider` Protocol in `core/nlp/contracts.py` before implementation begins | Required |
| RULE-04 | New modules appropriately scoped: `nlp/` for NLP infrastructure, `analysis/` for computation. Each file < 200 lines target | Required |
| RULE-05 | `core/nlp/` owns the NLP stack, `core/analysis/` owns computation logic. Clean module boundaries | Required |
| RULE-06 | Each file has one responsibility: `provider_spacy.py` = spaCy adapter, `syllables.py` = syllable counting, `sentiment.py` = sentiment analysis | Required |
| RULE-07 | `core/` never imports from `apps/`. Dependencies flow one way: `analysis/` → `nlp/` | Required |
| RULE-08 | spaCy abstracted behind `NLPProvider` Protocol. No direct spaCy imports outside `core/nlp/` | Required |
| RULE-09 | All public methods fully type-annotated. No `Any` in public interfaces | Required |
| RULE-10 | Unit tests for each analysis module. Integration tests for hybrid features. Coverage thresholds apply | Required |
| RULE-11 | spaCy loading errors and model-not-found errors properly caught and logged with structlog | Required |

---

## Implementation Notes

### File Structure

```
packages/core/narrare_core/
├── nlp/                          ← NEW MODULE
│   ├── __init__.py               ← Public exports: NLPProvider, get_nlp_provider
│   ├── contracts.py              ← NLPProvider Protocol (RULE-03, RULE-08)
│   ├── provider_spacy.py         ← spaCy adapter implementation
│   ├── syllables.py              ← Language-specific syllable counting (EN/DE/FR)
│   ├── dialogue.py               ← Dialogue extraction from prose
│   └── languages/
│       ├── __init__.py
│       ├── pronouns_de.py        ← German pronoun data (from existing _scratch/)
│       ├── pronouns_en.py        ← English pronoun data
│       ├── pronouns_fr.py        ← French pronoun data
│       └── emotions.py           ← NRC EmoLex loader + VAD mapping
├── analysis/                     ← NEW MODULE (deterministic computation)
│   ├── __init__.py               ← Public exports for analysis services
│   ├── contracts.py              ← Protocols for all analysis services
│   ├── readability.py            ← Flesch/Kincaid/Fog formulas
│   ├── sentiment.py              ← Lexicon-based + algorithmic arc detection
│   ├── voice_metrics.py          ← Structural voice analysis
│   └── pacing.py                 ← Pacing from sentence structure
├── embeddings/                   ← EXISTING (supplementary signal for ANAL-009)
├── llm/                          ← EXISTING (unchanged)
└── agents/                       ← EXISTING (new agents for understanding features)
```

### Dependency Direction

```
core/analysis/ ──→ core/nlp/ (NLPProvider Protocol)
                ──→ core/embeddings/ (optional, for ANAL-009 voice drift)

core/agents/ ────→ core/llm/ (gateway, per RULE-01)
                ──→ core/analysis/ (deterministic metrics for hybrid features)

apps/api/ ───────→ core/analysis/ (via service layer)
                ──→ core/agents/ (via service layer, for LLM features)
```

No circular dependencies. `core/nlp/` never imports from `core/analysis/`. `core/analysis/` never imports from `core/agents/`.

### New Dependency

```toml
# packages/core/pyproject.toml
[project.optional-dependencies]
nlp = ["spacy>=3.8"]

# Language models installed via post-install script or justfile command:
# python -m spacy download de_core_news_sm   (~40MB)
# python -m spacy download en_core_web_sm   (~12MB)
# python -m spacy download fr_core_news_sm  (~40MB)
```

- spaCy >=3.8 (~50MB, MIT license)
- 3 language models (~40MB each, CC BY-SA for model data)
- **Total: ~175MB**
- **NO PyTorch dependency** — spaCy uses Thinc/numpy for its neural network backend
- Optional dependency: `pip install narrare-core[nlp]` — graceful degradation if not installed

### NLPProvider Contract (core/nlp/contracts.py)

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class NLPProvider(Protocol):
    """Protocol for NLP pipeline providers."""

    @property
    def supported_languages(self) -> list[str]: ...

    async def tokenize(self, text: str, *, language: str) -> TokenResult: ...
    async def sentence_split(self, text: str, *, language: str) -> list[str]: ...
    async def pos_tag(self, text: str, *, language: str) -> list[POSTag]: ...
    async def extract_entities(self, text: str, *, language: str) -> list[Entity]: ...
    async def count_syllables(self, word: str, *, language: str) -> int: ...
    def is_available(self, *, language: str) -> bool: ...
```

### Graceful Degradation (following ADR-017 pattern)

If spaCy is not installed or doesn't support the runtime Python version:

1. `NLPProvider.is_available()` returns `False`
2. Analysis services detect this and fall back to regex-based tokenization and sentence splitting
3. Syllable counting falls back to language-specific heuristic rules
4. Features that fundamentally require spaCy (NER-based coref) report "unavailable" in the UI
5. This is a **temporary** state — the goal is always full spaCy support

### NRC EmoLex Integration

The NRC Emotion Lexicon (EmoLex) provides word-level emotion associations for ~14,000 words across 10 emotions. Integration approach:

- Loaded from bundled data file in `core/nlp/languages/emotions.py`
- Attribution included in the loader (CC BY-SA 3.0 requirement)
- VAD (Valence-Arousal-Dominance) mapping derived from EmoLex emotion categories
- Combined with structural signals (sentence position, dialogue context) for arc detection

### pyproject.toml Update

Register the new module in the architecture exceptions if needed:

```toml
# No RULE-01 exception needed — spaCy is not an LLM.
# The NLPProvider Protocol satisfies RULE-08 (external integration abstraction).
```

---

## Review Trigger

- [ ] **When PyTorch adds Python 3.14 support** → re-evaluate Stanza/Flair as optional dependencies for better DE/FR coref and NER quality. These could become supplementary providers behind `NLPProvider`.
- [ ] **When fine-tuned literary sentiment models become available** → re-evaluate Option A (BERT/Transformer models) for domain-specific sentiment analysis. The `NLPProvider` Protocol makes this a provider swap, not an architectural change.
- [ ] **If spaCy doesn't support Python 3.14 at implementation time** → activate graceful degradation to regex-based analysis. Set a review trigger for 30 days to re-check spaCy compatibility.
- [ ] **When `core/nlp/provider_spacy.py` exceeds 300 lines** → split into `core/nlp/_providers/` directory with per-language provider modules.
- [ ] **When `core/analysis/` exceeds 5 modules** → evaluate whether sub-domain grouping is needed (e.g., `analysis/readability/`, `analysis/sentiment/`).
- [ ] **When a second NLP provider is needed** (e.g., Stanza for better coref) → evaluate whether to create `core/nlp/_providers/` directory structure following the same pattern as `core/llm/_providers/`.
