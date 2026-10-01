# ADR-090 — Multi-Vector Rerank Tier: post-retrieval MaxSim reranking via sentence-transformers v6 `MultiVectorEncoder`

> **Status:** ✅ Implemented — dependency pin landed with this ADR (Task 13 of
> the pydantic-ai 2.52 upgrade plan, feature F5); the rerank tier implemented
> by Tasks 14–16 and measured by the Task-16 pilot; flipped 2026-10-01 at
> Phase-6 gate closure. Wiring is dormant by design until a production search
> consumer lands (see CURRENT_STATE).
> **Date:** 2026-10-01
> **Deciders:** Architecture Agent; binding user decision 2026-09-30 — the
> rerank default encoder is a **specific pinned checkpoint** (candidate
> `lightonai/LateOn`, verified below), **never the library default** (drifts
> between releases, breaks eval comparability).
> **Supersedes:** none
> **Amendment (2026-10-01, Task-18 docs pass):** Decision 6's extra-missing
> degradation wording corrected to the implemented behavior — the stage is
> **skipped entirely**, not "`NullReranker` wired" (see the amendment note
> under Decision 6).
> **Related:** ADR-033 (mem0 OSS memory — cascade gates this ADR must not
> disturb), ADR-006 (technology choices & explicit exclusions; local-first
> posture detailed in `docs/_shared/TECH_STACK.md`), ADR-071 (`CoreSettings`),
> ADR-089 (sibling plan feature — settings/degradation patterns reused),
> RULE-03/04/06/07/08/11/18b/20

---

## Context

### The gap

Narrare's semantic retrieval is single-vector end to end: content is embedded
to one vector per entity (pgvector, `vector(1536)`, migration 0022), searched
by cosine top-K, then ranked by the hybrid score
(`core/embeddings/scoring.py`: similarity 0.50 / usage 0.30 / recency 0.20).
A bi-encoder compresses each document into a single vector **before seeing the
query** — token-level alignment information is irretrievably lost at write
time. The observable symptom: lexically adjacent queries (paraphrases,
term overlaps the author actually wrote) rank below semantically "close but
answer-wrong" candidates, and no hybrid-weight tuning recovers the difference.

**Root cause (2× Why):**
1. *Symptom:* retrieval precision on query-term-adjacent candidates is capped.
2. *Why?* Scoring happens between two pre-compressed single vectors; the
   query never interacts with document tokens.
3. *Why is that the actual cause?* The write path is single-vector by design
   (pgvector store, dimension-pinned). Late-interaction (multi-vector)
   scoring removes that cap **without touching the index** — it can be added
   purely as a post-retrieval stage over the fetched candidate texts.

### Dependency state at decision time

The `embeddings` optional extra (`packages/core/pyproject.toml`) carried an
open floor `sentence-transformers>=3.0`. The lock had silently drifted to
5.6.0 under that floor — concrete evidence of the drift risk the pin closes.
Today ST is consumed only indirectly: mem0's `"huggingface"` embedder
(`core/memory/embedding_cascade.py` Tier 3, `all-MiniLM-L6-v2`) imports
`SentenceTransformer` when that tier is constructed.

---

## Verified upstream API (sentence-transformers 6.1.0, installed 2026-10-01)

Installed via `uv sync --all-packages --extra embeddings` →
`sentence-transformers==6.1.0`, `transformers==5.12.1`, `torch==2.13.0`
(lock updated from 5.6.0). All signatures below are verbatim from the
installed package (`.venv/lib/python3.14/site-packages/sentence_transformers/`)
— **this section is the contract Task 14 implements against.**

**Public import** (verified executable):

```python
from sentence_transformers import MultiVectorEncoder
# → <class 'sentence_transformers.multi_vector_encoder.model.MultiVectorEncoder'>
```

**Class semantics** (docstring, verbatim excerpts): *"Loads or creates a
multi-vector / late-interaction (ColBERT-style) embedding model. … produces a
*sequence* of vectors per input, one per token. Scoring between queries and
documents is done with the MaxSim late-interaction operator: for each query
token, take the max similarity to any document token, then sum across query
tokens."* Asymmetric `encode_query` / `encode_document` split; default
`similarity_fn_name="maxsim"` (alternatives: `"meanmaxsim"`). The class
docstring's own first example is `MultiVectorEncoder("lightonai/LateOn")`.

**Constructor** (`multi_vector_encoder/model.py:157`) — verbatim:

```python
def __init__(
    self,
    model_name_or_path: str | None = None,
    *,
    modules: list[nn.Module] | None = None,
    device: str | None = None,
    prompts: dict[str, str] | None = None,
    default_prompt_name: str | None = None,
    cache_folder: str | None = None,
    trust_remote_code: bool = False,
    revision: str | None = None,
    local_files_only: bool = False,
    token: bool | str | None = None,
    model_kwargs: dict[str, Any] | None = None,
    processor_kwargs: dict[str, Any] | None = None,
    config_kwargs: dict[str, Any] | None = None,
    model_card_data: MultiVectorEncoderModelCardData | None = None,
    backend: Literal["torch", "onnx", "openvino"] = "torch",
    similarity_fn_name: str | SimilarityFunction | None = None,
) -> None
```

**Encoding methods** — `encode_query` and `encode_document` share this
signature (mutatis mutandis; both verified) — verbatim:

```python
def encode_query(  # likewise encode_document
    self,
    inputs: Sequence[SingleInput] | SingleInput,
    prompt_name: str | None = None,
    prompt: str | None = None,
    batch_size: int = 32,
    show_progress_bar: bool | None = None,
    output_value: Literal["token_embeddings"] | None = "token_embeddings",
    convert_to_numpy: bool = False,
    device: str | torch.device | list[str | torch.device] | None = None,
    normalize_embeddings: bool = False,
    pool: dict[Literal["input", "output", "processes"], Any] | None = None,
    chunk_size: int | None = None,
    token_pooling: BaseTokenPooling | None = None,
    **kwargs: Any,
) -> list[Tensor] | list[np.ndarray] | Tensor | np.ndarray
    | list[dict[str, Tensor]] | dict[str, Tensor]
```

Default call shape for reranking: `enc.encode_query([q])` /
`enc.encode_document(texts)` → `list[Tensor]`, each entry
`(num_tokens_i, embedding_dim)`.

**Scoring** — verbatim:

```python
def similarity(
    self,
    embeddings1: Tensor | np.ndarray | list[Tensor] | list[np.ndarray],
    embeddings2: Tensor | np.ndarray | list[Tensor] | list[np.ndarray],
    **kwargs: Any,          # forwarded to maxsim: device, chunk_elements, length_normalize
) -> Tensor                  # [num_embeddings_1, num_embeddings_2], documents' device

def similarity_pairwise(
    self,
    embeddings1: Tensor | np.ndarray | list[Tensor] | list[np.ndarray],
    embeddings2: Tensor | np.ndarray | list[Tensor] | list[np.ndarray],
    **kwargs: Any,
) -> Tensor                  # [num_embeddings] pairwise scores
```

**Binding call sequence for Task 14** (the rerank hot path):

```python
enc = MultiVectorEncoder(settings_model_name)     # positional model_name_or_path
q = enc.encode_query([query])                     # 1 × (q_tokens, dim)
d = enc.encode_document([c.text for c in candidates])
scores = enc.similarity(q, d)                     # Tensor [1, len(candidates)] — MaxSim
```

### Checkpoint verification — `lightonai/LateOn` (shallow, hub-API level)

No weights were downloaded in this task. Verification is metadata +
installed-source based (HF Hub API + ST 6.1.0 loader source); **the ~600 MB
model download happens on first rerank use at runtime** (`model.safetensors`
596.1 MB fp32 + three small `*_Dense` heads; an int8 ONNX variant exists at
154.7 MB but v1 pins the torch backend).

| Fact | Evidence |
|---|---|
| Exists, active, permissively licensed | Hub `lightonai/LateOn`: Apache-2.0, `sentence-similarity`, 7,938 downloads/30d, last modified 2026-08-17, sha `62911e1` |
| Size fits the "small local reranker" slot | 149,015,808 safetensors params (~149M) |
| ST-native loadable format | `modules.json` + `config_sentence_transformers.json` present (ST export, v5.1.1 via PyLate) |
| ST 6.1 loads PyLate v3 checkpoints **natively, without the `pylate` package** | `_CLASS_REF_ALIASES = {"pylate.models.Dense.Dense": "sentence_transformers.base.modules.dense.Dense"}` (`multi_vector_encoder/model.py:35-40`); `is_pylate_v3` promotion on `model_type == "ColBERT"` (`:1131-1133`); `_LegacyStash` recovers `query_prefix`/`document_prefix`, `query_length`, `document_length`, `query_expansion`, `skiplist_words` (`:45-63`) |
| LateOn's config carries exactly those legacy keys | fetched `config_sentence_transformers.json`: `model_type: "ColBERT"`, prefixes `"[Q] "`/`"[D] "`, `query_length: 32`, `document_length: 300`, `do_query_expansion: false`, punctuation `skiplist_words` |
| API-fit exemplar | `MultiVectorEncoder` docstring example loads this exact checkpoint |

**Verdict: API fit confirmed.** The pinned default encoder for
`embedding_rerank_model` is `lightonai/LateOn`.

### Dependency coherence (mem0 ↔ ST ↔ transformers)

Verified against mem0ai 2.2.1's actual published metadata — **weaker coupling
than the plan assumed, which is good news**:

- mem0ai 2.2.1 **core** dependencies (lock, verbatim list): httpx, openai,
  posthog, protobuf, pydantic, pytz, qdrant-client, sqlalchemy — **no
  transformers, no sentence-transformers**. The plan's "mem0 requires
  `transformers>=5.3.0`" holds only for mem0's **`extras` extra**
  (`transformers>=5.3.0; extra == "extras"`, alongside
  `sentence-transformers>=5.2.0`), which Narrare does not install
  (`mem0ai==2.2.1`, no extras).
- The only active transformers constraint is ST 6.1.0's
  `transformers>=5.0.0,<6` → lock resolves **transformers 5.12.1** (unchanged
  by the pin; satisfies mem0's extras floor too, should anyone ever install
  it). One coherent transformers-v5 line for both consumers.
- `uv pip check` on the fully synced workspace with the embeddings extra:
  **"All installed packages are compatible"** (206 packages, incl.
  mem0ai 2.2.1 + sentence-transformers 6.1.0 + torch 2.13.0).
- Tier-3 cascade unaffected: mem0's huggingface embedder
  (`mem0/embeddings/huggingface.py:6,27`) does
  `from sentence_transformers import SentenceTransformer` — class verified
  present in 6.1.0 — and the module is imported lazily by mem0's provider
  factory, so environments **without** the extra keep importing mem0
  unchanged (Phase 5 ran green without ST installed). The cascade pins its
  own model name (`all-MiniLM-L6-v2`, `embedding_cascade.py:81`) — untouched.
- Regression evidence: `tests/unit/core/memory/test_embedding_cascade.py` +
  `test_create_memory_client.py` → **36 passed** on the ST-6.1 environment.

---

## Decision Drivers

- **Retrieval precision ceiling** (root cause above) — the only stage where
  token-level query↔document interaction can be added without index change.
- **Local-first posture** (ADR-006 / TECH_STACK): an always-on retrieval path
  must not depend on a hosted API.
- **RULE-08**: every external integration confined to its adapter module.
- **RULE-03 / RULE-11 / RULE-18b**: contract first; degradation is loud, not
  silent; every settings knob demonstrably reaches its consumer.
- **Zero-default impact** (ADR-088/089 precedent): the shipped search path is
  the reviewed behavior; a pilot may not change it for anyone who did not opt
  in — and rollback must be a flag, not a migration.
- **Reproducible evals**: the encoder checkpoint is data for the benchmark
  program (ADR-083); a drifting default breaks comparability across runs.

---

## Options Considered

### Option 0 — ST v6 `MultiVectorEncoder` local reranker behind the `embeddings` extra (chosen)

Post-retrieval MaxSim reranking of pgvector top-K using a pinned
late-interaction checkpoint.

**Pros:** token-level interaction without index/schema change (pure
post-processing); one coherent dependency floor with mem0 (transformers v5);
CPU-viable at ~149M params for K ≤ ~50 candidates; opt-in extra — zero
footprint when absent; checkpoint pinned → reproducible evals.

**Cons:** first-use runtime download (~600 MB) + load latency on the first
rerank call; rerank adds one local inference stage to search latency; the
pinned checkpoint is English-primary (see Review Triggers).

### Option (a) — Cross-encoder reranker (rejected)

**Rejected:** highest precision, but ~10–50× rerank latency on CPU (full
transformer forward **per query×document pair**, no indexable
pre-computation) and heavier model management for a pilot; late-interaction
keeps pre-computable document token embeddings and one backbone pass per
batch.

### Option (b) — Hosted rerank API (Cohere/Jina) (rejected)

**Rejected:** violates the local-first posture (ADR-006 /
`TECH_STACK.md`) for an always-on retrieval path — network dependency,
per-call cost, and prose text egress to a third party on every search.

### Option (c) — Do nothing / tune hybrid weights only (rejected)

**Rejected:** the defect is architectural (single-vector compression), not a
weighting miscalibration; hybrid-weight tuning cannot recover token-level
alignment. This is the baseline the pilot (Task 16) measures against.

---

## Decision

**We choose Option 0** in seven binding decisions:

### 1. Rerank is a post-retrieval stage only — no index change

Pipeline: **existing pgvector dense top-K (+ hybrid scoring, unchanged) →
local rerank → top-N.** NO pgvector schema change, NO index change, NO change
to embedding write paths (`MultiVectorEncoder` only scores query×document at
rerank time; nothing is persisted). Corollaries: no Alembic migration
(RULE-14 N/A by construction), no dimension changes, no re-embedding of
existing content, and **rollback = disable the flag**.

### 2. Dependency policy: pin `sentence-transformers>=6.1,<7`

The `embeddings` extra pins `sentence-transformers>=6.1,<7` (was open
`>=3.0` — the lock had drifted to 5.6.0). Major-version ceiling because v6
moved multi-vector support to the dedicated `MultiVectorEncoder` class; a
future v7 is a re-pin decision (Review Trigger), never a silent drift.
Coherence verified above: one transformers-v5 line serves ST 6.1 and (its
extras-extra floor aside) mem0 2.2.1; `uv pip check` clean.

### 3. Contract-first confinement (RULE-03 + RULE-08): `core/embeddings/rerank.py`

All rerank logic lives in one new Core module,
`packages/core/narrare_core/embeddings/rerank.py`, exporting:

- `RerankCandidate` — frozen dataclass: `source_id: UUID`, `source_type: str`,
  `text: str`, `base_score: float` (carries the pre-rerank hybrid score for
  observability/tie-breaking; the rerank score is the new sort key).
- `Reranker` — `Protocol`: `async def rerank(self, query: str, candidates:
  Sequence[RerankCandidate], *, top_n: int) -> list[RerankCandidate]`
  (stable sort by rerank score descending, truncated to `top_n`).
- `MultiVectorReranker` — the implementation. `sentence_transformers` is
  imported **only here, lazily inside the class** (never at Core module
  import time), mirroring `core/memory/availability.py` for mem0.
- `is_rerank_available() -> bool` — import probe, `is_mem0_available` pattern.
- `NullReranker` — passthrough (returns `list(candidates)[:top_n]`, input
  order) as the always-available contract implementation; production wiring
  skips the stage entirely instead of wiring it when the extra is absent
  (see the Decision 6 amendment).

This ADR + the verified API section above are the Task-14 contract; if the
installed surface disagrees with the ADR, the ADR wins and gets amended.

### 4. Candidate text supply: caller-injected async fetcher — Core stays pure

Search rows carry no text — verified: `SearchResult` is `(source_id,
source_type, score, content_hash)` (`core/embeddings/store.py:26-43`) and
`ScoredCandidate` adds only usage/recency metadata (`scoring.py:52-70`).
Fetching text would need DB access, which Core must never have (RULE-07).
**Binding:** callers (Backend layer) fetch candidate texts via their own
repositories through an injected async fetcher and build `RerankCandidate`s;
the Core `Reranker` contract receives fully materialized candidates and stays
pure/sync-free of I/O.

### 5. Opt-in, pinned default (RULE-18b; binding user decision 2026-09-30)

Two new `CoreSettings` fields (ADR-071 pattern, `validation_alias` +
`populate_by_name`):

- `embedding_rerank_enabled: bool = Field(default=False,
  validation_alias="NARRARE_EMBEDDING_RERANK")`
- `embedding_rerank_model: str = Field(default="lightonai/LateOn",
  validation_alias="NARRARE_EMBEDDING_RERANK_MODEL")`

Default `False` → behavior byte-identical to today. The model default is the
**specific pinned checkpoint** — never the ST library default, which is not
stable across releases and would break eval comparability (ADR-083).

### 6. Graceful degradation (RULE-11) — never break search

> **Amendment (2026-10-01, Task-18 docs pass):** the first bullet below is
> corrected to the implemented Task-15 behavior: with the extra missing, the
> rerank stage is **skipped entirely** (byte-identical path) rather than a
> `NullReranker` being wired. Skip is strictly better: it avoids the 4×
> overfetch (`min(limit*4, 100)`) and the pointless candidate-text fetch
> roundtrip that a wired passthrough reranker would still incur.
> `NullReranker` remains part of the Core contract (passthrough for any
> consumer that requires a `Reranker` instance); production wiring resolves
> to "no components" instead.

- Extra absent + flag on → one structured warning (`embedding_rerank_unavailable`,
  `reason="extra_missing"`) at wiring time, **no rerank components wired —
  the stage is skipped and search returns the byte-identical pre-rerank
  path** (amended 2026-10-01; originally worded as "`NullReranker` wired").
- Checkpoint load/scoring failure at first rerank use → one structured
  warning (`embedding_rerank_degraded` with the exception class), that
  request returns the pre-rerank top-N. The base pgvector + hybrid path
  never gains a new failure mode.
- The `MultiVectorReranker` holds the encoder as a **lazy process-wide
  singleton keyed by model name** (first rerank call pays the ~600 MB
  download + load; subsequent calls reuse it).

### 7. Pilot measurement & scope

Effect is measured by the rewrite-selection-derived retrieval comparison
(Task 16) — no pgvector change means rollback = disable the flag. v1 wiring
scope is the semantic search/read path chosen by Tasks 14–15; widening is a
Review Trigger decision backed by pilot data.

---

## Rationale

The precision ceiling is architectural (query never meets document tokens),
so the fix must add an interaction stage. Adding it *after* retrieval —
scoring the already-fetched top-K texts — buys token-level alignment for
zero index/schema/write-path risk, making the feature cheap to roll back and
safe to ship dark. Late-interaction (MaxSim) is the deliberate middle point
on the cost/precision curve: it pre-computes document token embeddings once
per request batch (unlike cross-encoders' per-pair forwards) while still
scoring token-level matches (unlike bi-encoder dot products). sentence-
transformers v6 ships this as a maintained class with native PyLate-checkpoint
support, so Narrare owns only the policy — which candidates, which checkpoint,
when to degrade — not the scoring machinery. Pinning both the library range
(`>=6.1,<7`) and the checkpoint (`lightonai/LateOn`) converts two drift risks
into two explicit, reviewable decisions.

## Consequences

**Positive:** semantic precision lever on retrieval with zero default impact,
zero migration, flag-only rollback; one coherent transformers-v5 floor with
mem0; reproducible evals (pinned checkpoint); dependency floor hardened
against silent drift (`>=3.0` → `>=6.1,<7`).

**Negative / Trade-offs:** first rerank use downloads ~600 MB (offline
first-use fails → degraded path, loud warning); rerank adds one local
inference stage to search latency (pilot measures); torch enters the runtime
**only** when the extra is installed (accepted per plan; it is not a core
dependency); LateOn is English-primary — German/French rerank quality is
unverified (Review Trigger).

**Constraints touched:** RULE-03 (contract in this ADR before Task 14),
RULE-04/06 (one new module, one responsibility), RULE-07 (Core purity —
text fetcher at the caller seam), RULE-08 (ST confined to
`core/embeddings/rerank.py`, mirroring mem0↔`core/memory/`), RULE-11 (loud
degradation), RULE-18b (both settings need effect tests), RULE-20 (pilot
ships complete: flag, contract, wiring, degradation, tests, docs).

---

## Implementation Notes (binding for Tasks 14–16)

- **Task 14 (Core):** `rerank.py` per Decision 3; the two `CoreSettings`
  fields per Decision 5; torch inference runs **off the event loop**
  (`asyncio.to_thread`) — the Protocol is async, `encode_*`/`similarity` are
  blocking; singleton per model name with first-use load inside the
  degradation boundary (Decision 6). Scoring uses `similarity()` (not
  `similarity_pairwise`) — one query against K documents.
- **Task 15 (Backend wiring):** inject the async text fetcher at the search
  service seam; wire `NullReranker` when `is_rerank_available()` is False or
  the flag is off; structured events per Decision 6.
- **Task 16 (pilot measurement):** rewrite-selection-derived retrieval
  comparison; report includes rerank-on/off deltas.
- **Test contract:** pure-contract tests with a fake `Reranker`;
  `NullReranker` passthrough; `is_rerank_available()` both ways; RULE-18b
  effect evidence (flag flips wiring; model name reaches the constructor —
  asserted via monkeypatched `MultiVectorEncoder`); degradation warning
  emitted exactly once on load failure; flag-off byte-identical search
  behavior. Real-checkpoint integration is **not** a unit-test concern
  (download) — covered by the pilot, not CI.

---

## Review Triggers

- [ ] **ST v7 release** (blocked by `<7`): re-pin, re-verify
      `MultiVectorEncoder` + PyLate promotion path, re-run coherence checks;
      amend this ADR.
- [ ] **Multilingual rerank quality:** LateOn is English-primary; if the
      Task-16 pilot shows weak German/French rerank deltas, evaluate a
      multilingual late-interaction checkpoint (same contract, different
      pinned default — settings knob already exists).
- [ ] **Latency budget:** if rerank measurably degrades search UX on
      CPU-only boxes, evaluate the int8 ONNX variant (154.7 MB,
      `backend="onnx"`) or lower K before widening scope.
- [ ] **Scope widening** beyond the Task-15 path requires pilot data.
