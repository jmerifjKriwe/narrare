# KB Benchmark — Verified API Surface Map

> **Task 1 artifact** (plan `docs/superpowers/plans/2026-08-27-kb-benchmark-package3-runner.md`).
> Verified 2026-08-27 against router source (method-pinned decorator reads under
> `apps/api/narrare/`), Pydantic schemas quoted **verbatim** (field names/types/constraints),
> and mount verification in `apps/api/narrare/_app/main.py` (`_register_routers`).
> This map is the SSOT for all later runner tasks (client, provisioning, drivers).
> The 26-capability inventory (`benchmark/inventory/*.md`) remains the SSOT for
> benchmarkability verdicts and per-capability notes; §8 cross-references it.

## 1. Global conventions

| Aspect | Convention | Source |
|---|---|---|
| Base prefix | All domain routers mount under `/api/v1` (single `prefix = "/api/v1"` in `_app/main.py`). Monitoring endpoints are root-level (no prefix). | `_app/main.py` |
| Auth header | `Authorization: Bearer <access_token>` (FastAPI `HTTPBearer`, `auto_error=False`) | `_app/dependencies_auth.py` |
| Auth failures | 401 `{"detail": "Not authenticated"}` / `{"detail": "Invalid or expired token"}` with `WWW-Authenticate: Bearer` header | `_app/dependencies_auth.py` |
| Domain errors | `{"detail": <str>, "code": <str>}` — `NarrareError` handler maps subclass → status: `NotFoundError` 404, `ForbiddenError` 403, `ConflictError` 409, `AuthenticationError` 401, `ValidationError` 422, default 400 | `_app/main.py` `_narrare_error_handler` |
| Export errors | Same shape; `code` = exception class name; 404/410/503/400 mapping | `_app/main.py` `_export_error_handler` |
| Unhandled | 500 `{"detail": "Internal server error"}` | `_app/main.py` `_unhandled_exception_handler` |
| Validation errors | FastAPI default 422 `{"detail": [{"loc": [...], "msg": ..., "type": ...}, ...]}` (no custom handler) | FastAPI built-in |
| Rate limits | 429 on excess via `pyrate_limiter` (per-user keyed on user id; IP for unauthenticated endpoints). Defaults: AI write 3/min, **AI analysis 5/min** (`NARRARE_RATE_LIMIT_ANALYSIS`), light 10/min, setup models 10/min. **Disabled entirely in test/E2E mode** (`rate_limiter_dep.py`). Runner relevance: incremental ingest pacing — extraction is analysis-limited (5/min default). | `_app/rate_limits.py`, `_app/rate_limiter_dep.py` |
| CORS | `http://localhost:3000` (non-production). CSRF Origin/Referer validation active outside test mode — `OriginValidationMiddleware.dispatch` (read line-by-line, Task-16 rehearsal): safe methods (GET/HEAD/OPTIONS) pass; state-changing requests need an exact-match trusted `Origin` (else `Referer` origin), and with **neither** header a syntactically valid Bearer token — otherwise 403 `{"detail": "Origin not allowed", "code": "CSRF_ORIGIN_MISMATCH"}`. Default trusted list `["http://localhost:3000"]` (env `NARRARE_CSRF_TRUSTED_ORIGINS`, JSON list; `_app/settings_model.py`). Runner: client sends `Origin: <api.origin>` (default `http://localhost:3000`) on every request — see OPEN-3 (resolved). | `_app/main.py`, `middleware.py`, `_app/settings_model.py` |
| Timestamps | ISO-8601 datetimes in responses (`created_at`, `updated_at`). | schemas |

## 2. Auth flow

Token type: **JWT, HS256**, signed with server `secret_key`. Access token claims: `sub` (user UUID str), `iat`, `exp`, `type: "access"`. Refresh token: same claims with `type: "refresh"`. Lifetimes (settings defaults): **access 60 min** (`access_token_expire_minutes`), **refresh 30 days** (`refresh_token_expire_days`); response `expires_in` = access minutes × 60 (seconds).

| # | Method & path | Auth | Request | Response | Notes |
|---|---|---|---|---|---|
| 2.1 | `POST /api/v1/auth/register` | none | `RegisterRequest` → 201 `TokenResponse`; sets `narrare_refresh` httpOnly cookie. Rate 3/min. Repeat registration = 400/409 (duplicate email path in `AuthService.register`). | see schemas | Runner: create benchmark user once per stack |
| 2.2 | `POST /api/v1/auth/login` | none | `LoginRequest` → 200 `TokenResponse` + refresh cookie. Rate 5/min. | | |
| 2.3 | `POST /api/v1/auth/refresh` | none (cookie or body) | httpOnly cookie `narrare_refresh` **or** JSON body `{"refresh_token": "<str>"}` → 200 `TokenResponse` (rotates refresh cookie). 401 `{"detail": "No refresh token provided"}` if neither present. | | Client keeps `refresh_token` from login/register response body — cookie not needed |
| 2.4 | `POST /api/v1/auth/logout` | none | — | 204 no content; clears refresh cookie | |
| 2.5 | `GET /api/v1/auth/me` | Bearer | — | `UserResponse` | `has_providers: bool` — useful to detect already-provisioned LLM config (idempotent provisioning check) |

Schemas (verbatim, `auth/schemas.py`):

```python
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    display_name: str = Field(default="", max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class UserResponse(BaseModel):  # from_attributes
    id: uuid.UUID
    email: str
    display_name: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    has_providers: bool = False
```

## 3. Setup wizard (steps 1–5)

Steps 1–4 are independent `POST /setup/validate/step-N` validations; step 5 is the single authenticated `POST /setup/complete` that persists everything (novel + settings + provider). The wizard does **not** require prior authentication until `complete`.

| # | Method & path | Auth | Request | Response |
|---|---|---|---|---|
| 3.1 | `POST /api/v1/setup/validate/step-1` | none | `Step1LocationRequest` | `Step1LocationResponse {valid, project_name, writing_language, autosave_interval}` |
| 3.2 | `POST /api/v1/setup/validate/step-2` | none | `Step2NovelRequest` | `Step2NovelResponse {valid, title}` |
| 3.3 | `POST /api/v1/setup/validate/step-3` | none | `Step3StarterRequest` | `Step3StarterResponse {valid, starter, demo_info?}` |
| 3.4 | `POST /api/v1/setup/validate/step-4` | none | `Step4ProviderRequest` | `Step4ProviderResponse {valid, provider, model, validation_message}` — **performs a real provider API validation call** |
| 3.5 | `GET /api/v1/setup/providers/{provider}/models` | none | query params `api_key: str = ""`, `ollama_url: str = OLLAMA_DEFAULT_URL` | `AvailableModelsResponse` (rate 10/min, IP-keyed; falls back to bundled list with `provenance.source = "bundled-fallback"`) |
| 3.6 | `POST /api/v1/setup/complete` | **Bearer** | `CompleteSetupRequest {state: WizardState}` | `CompleteSetupResponse {novel_id, redirect_to, message}` |

Schemas (verbatim, `setup/base_schemas.py` + `setup/provider_schemas.py`):

```python
class AIProvider(StrEnum):  # provider ids
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"
    GROQ = "groq"
    OLLAMA = "ollama"
    OPENROUTER = "openrouter"
    ZAI = "zai"


class Step1LocationRequest(BaseModel):
    project_name: str = Field(min_length=1, max_length=100)  # no /\:*?"<>|, no lead/trail space
    writing_language: str = Field(default="en", min_length=2, max_length=10)
    autosave_interval: int = Field(default=30, ge=0, le=3600)


class Step2NovelRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    author: str = Field(default="", max_length=200)
    genre: str = Field(default="", max_length=100)
    logline: str = Field(default="", max_length=500)
    story_structure: StoryStructure = (
        THREE_ACT  # three_act|five_act|heros_journey|save_the_cat|seven_point
    )
    tone: StoryTone = DRAMATIC  # balanced|dramatic|humorous|suspenseful|contemplative|romantic|dark|adventurous|quiet


class Step3StarterRequest(BaseModel):
    starter: StarterContent = BLANK  # blank|demo_fantasy|demo_scifi|demo_german|import
    import_path: str | None = Field(default=None, max_length=500)


class Step4ProviderRequest(BaseModel):  # ← LLM provider provisioning shape
    provider: AIProvider
    api_key: str = Field(default="", max_length=200)
    model: str = Field(min_length=1, max_length=200)
    ollama_url: str = Field(default=OLLAMA_DEFAULT_URL, max_length=200)
    zai_endpoint: str = Field(default="general", max_length=50)  # "general" | "coding"


class WizardState(BaseModel):  # full state sent to /setup/complete
    project_name: str
    writing_language: str
    autosave_interval: int
    title: str
    author: str
    genre: str
    logline: str
    story_structure: StoryStructure
    tone: StoryTone
    starter: StarterContent
    import_path: str | None
    provider: AIProvider = ANTHROPIC
    api_key: str = ""
    model: str = ""
    ollama_url: str = OLLAMA_DEFAULT_URL
    zai_endpoint: str = "general"
    skip_provider: bool = False  # True when providers already configured


class CompleteSetupRequest(BaseModel):
    state: WizardState


class CompleteSetupResponse(BaseModel):
    novel_id: str
    redirect_to: str  # "/dashboard" or "/novel/{id}"
    message: str
```

Runner provisioning path (Task 4): register/login → (optional step-4 validation) → `POST /setup/complete` with `starter=blank`, provider fields from benchmark config. `complete` creates a novel — the runner's own novel creation (§4.1) must account for that (either reuse the setup novel or delete it). `skip_provider=True` only when `GET /auth/me` reports `has_providers=True`.

## 4. Novel / chapter lifecycle + extraction (CAP-IN-01)

### 4.1 Novels (`novels/router.py`)

| # | Method & path | Auth | Request → Response |
|---|---|---|---|
| 4.1.1 | `GET /api/v1/novels` | Bearer | → `list[NovelSummaryResponse]` |
| 4.1.2 | `POST /api/v1/novels` | Bearer | `CreateNovelRequest` → 201 `NovelResponse` |
| 4.1.3 | `GET /api/v1/novels/{novel_id}` | Bearer | → `NovelResponse` |
| 4.1.4 | `PATCH /api/v1/novels/{novel_id}` | Bearer | `UpdateNovelRequest` → `NovelResponse` |
| 4.1.5 | `DELETE /api/v1/novels/{novel_id}` | Bearer | → 204 |

```python
class CreateNovelRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    author: str = Field(default="", max_length=200)
    genre: str = Field(default="", max_length=100)
    writing_language: str = Field(default="en", max_length=100)
    tone: str = Field(default="", max_length=100)
    story_structure: str = Field(default="three_act", max_length=100)
    logline: str = Field(default="", max_length=500)
    synopsis: str = Field(default="")


class NovelResponse(BaseModel):  # from_attributes
    id: uuid.UUID
    series_id: uuid.UUID | None = None
    title: str
    author: str
    genre: str
    writing_language: str
    tone: str
    story_structure: str
    logline: str
    synopsis: str
    is_demo: bool
    created_at: datetime
    updated_at: datetime


class NovelSummaryResponse(BaseModel):
    id: uuid.UUID
    series_id: uuid.UUID | None = None
    series_position: int | None = None
    title: str
    author: str
    genre: str
    writing_language: str
    is_demo: bool
    updated_at: datetime
```

### 4.2 Chapters (`chapters/router.py`, prefix `/novels/{novel_id}/chapters`)

| # | Method & path | Auth | Request → Response |
|---|---|---|---|
| 4.2.1 | `GET /api/v1/novels/{novel_id}/chapters` | Bearer | query `volume_id?` → `list[ChapterSummaryResponse]` |
| 4.2.2 | `POST /api/v1/novels/{novel_id}/chapters` | Bearer | `CreateChapterRequest` → 201 `ChapterResponse` |
| 4.2.3 | `GET /api/v1/novels/{novel_id}/chapters/{chapter_id}` | Bearer | → `ChapterResponse` |
| 4.2.4 | `PUT /api/v1/novels/{novel_id}/chapters/{chapter_id}/content` | Bearer | `UpdateChapterContentRequest` → `ChapterResponse` (autosave endpoint) |
| 4.2.5 | `PATCH /api/v1/novels/{novel_id}/chapters/{chapter_id}` | Bearer | `UpdateChapterMetaRequest` → `ChapterResponse` |
| 4.2.6 | `POST /api/v1/novels/{novel_id}/chapters/reorder` | Bearer | `ReorderChaptersRequest` → `list[ChapterSummaryResponse]` |
| 4.2.7 | `DELETE /api/v1/novels/{novel_id}/chapters/{chapter_id}` | Bearer | → 204 |

**Publishing:** there is **no dedicated publish endpoint**. Publication state is the `status` meta field (`draft|reviewed|final`, pattern-validated) set via 4.2.5. Extraction (4.3) reads chapter text directly — it does not require `status=final`. Incremental ingest = create (4.2.2, optionally with `content`) or create + set content (4.2.4), then extract → endorse.

```python
class CreateChapterRequest(BaseModel):
    title: str = Field(default="", max_length=500)
    content: str = Field(default="")
    position: int | None = None  # None → appended at end
    volume_id: uuid.UUID | None = None


class UpdateChapterContentRequest(BaseModel):
    content: str
    word_count: int | None = None  # server recomputes if None


class UpdateChapterMetaRequest(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    status: str | None = Field(default=None, pattern="^(draft|reviewed|final)$")
    pov_character_id: str | None = Field(default=None, max_length=100)
    timeline_position: str | None = Field(default=None, max_length=200)
    volume_id: uuid.UUID | None = None


class ChapterResponse(BaseModel):  # from_attributes
    id: uuid.UUID
    novel_id: uuid.UUID
    volume_id: uuid.UUID | None
    title: str
    content: str
    summary: str
    position: int
    word_count: int
    status: str
    pov_character_id: str
    timeline_position: str
    created_at: datetime
    updated_at: datetime


class ChapterSummaryResponse(BaseModel):
    id: uuid.UUID
    novel_id: uuid.UUID
    volume_id: uuid.UUID | None
    title: str
    position: int
    word_count: int
    status: str
    updated_at: datetime
```

### 4.3 Extraction + endorsement (CAP-IN-01, `kb/router_extraction.py`)

| # | Method & path | Auth | Request → Response |
|---|---|---|---|
| 4.3.1 | `POST /api/v1/novels/{novel_id}/kb/extract/{chapter_id}` | Bearer | **no body** → 200 JSON `{"results": [ExtractionItem...], "analysis_notes": str}`. Rate **AI analysis 5/min**. Errors: 400 (ValueError → e.g. chapter/novel not found), 500. Plain JSON — **not SSE**. |
| 4.3.2 | `POST /api/v1/novels/{novel_id}/kb/extract/apply` | Bearer | `ApplyExtractionRequest` → `ApplyExtractionResponse`. 400 on invalid items, 500 on failure. |

**Endorse/reject semantics:** there is no explicit reject endpoint — rejection = omission. The client sends only the endorsed items to `/apply`; everything not sent is discarded. v1 strategy (plan Task 6): endorse ALL candidates → send every result item back as an `ApplyExtractionItem`.

```python
# packages/core/narrare_core/agents/extraction_types.py — 4.3.1 result items
class ExtractionItem(BaseModel):
    item_type: Literal["new_entity", "update_entity", "relationship", "conflict"]
    entity_type: str | None = None
    name: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_text: str
    proposed_content: dict[str, Any] | None = None
    target_entity_id: str | None = None
    conflict_description: str | None = None
    relationship_type: str | None = None
    related_entity_name: str | None = None


# apps/api/narrare/kb/schemas_extraction.py — 4.3.2 apply
class ApplyExtractionItem(BaseModel):
    item_type: Literal["new_entity", "update_entity", "relationship", "conflict"]
    name: str
    entity_type: str | None = None
    proposed_content: dict[str, Any] | None = None
    target_entity_id: str | None = None
    relationship_type: str | None = None
    related_entity_name: str | None = None
    source_text: str = ""


class ApplyExtractionRequest(BaseModel):
    items: list[ApplyExtractionItem]


class ApplyExtractionEntryResult(BaseModel):
    id: str
    name: str
    entity_type: str


class ApplyExtractionResponse(BaseModel):
    created_entries: list[ApplyExtractionEntryResult] = []
    updated_entries: list[ApplyExtractionEntryResult] = []
```

## 5. Health / readiness / version (stack-manager wait loop)

| # | Method & path | Auth | Response | Notes |
|---|---|---|---|---|
| 5.1 | `GET /health` | none | `{"status": "healthy"|"degraded"|"critical", "observability": {...}}` | Liveness. 200 for healthy+degraded. **Recommended primary wait-loop probe.** |
| 5.2 | `GET /ready` | none | 200 `{"status": "ready"}` / 503 `{"status": "unhealthy", "error": str}` | Readiness incl. `SELECT 1` on the DB — **use after /health to confirm migrations+DB up.** |
| 5.3 | `GET /metrics` | none | Prometheus text | not needed by runner |

**Version:** no `/version` endpoint exists (see OPEN-1). The OpenAPI document `GET /openapi.json` carries `info.version` (`"0.1.0"`, from `FastAPI(version=...)`) — manifest's api-version payload source. `/docs` + `/redoc` exist in non-production only.

## 6. SSE conventions

All SSE-capable endpoints use `StreamingResponse(media_type="text/event-stream")` with headers `Cache-Control: no-cache`, `X-Accel-Buffering: no`. Frames are **data-only** — no `event:` field lines; the event discriminator lives **inside the JSON payload**. Every stream terminates with the literal sentinel frame `data: [DONE]\n\n`. Errors after headers are sent are **in-band** (SSE cannot change mid-stream status); pre-stream failures (auth 401, rate 429, validation 422) arrive as normal HTTP error statuses.

**Flavor A — raw item stream** (timeline extraction, `POST /api/v1/planning/timeline/{novel_id}/extract`):

```
data: {"id":"...","expression":"...","event_name":"...","timestamp_raw":"...", \
       "chapter_reference":"...","character_names":[...],"location_name":"...", \
       "confidence":0.9,"context":"..."}     ← ExtractedEventResponse, one per expression
data: {"error": "<message>", "code": "NOT_FOUND"|"CONFIG_ERROR"|"INTERNAL"}   ← in-band error
data: [DONE]
```

Request body: `ExtractionRequest {chapter_ids: list[uuid.UUID] = []}` (empty = all chapters). Rate AI analysis. Confirm: `POST /api/v1/planning/timeline/{novel_id}/extract/confirm` with `ConfirmExtractionRequest` (fields mirror `ExtractedEventResponse` minus `id`) → 201 `TimelineEventCRUDResponse` (fields incl. `source`, `confidence`, `is_confirmed`, `temporal_order`, `character_refs`, `location_ref`).

**Flavor B — type-discriminated event envelope** (analysis family: character-voice, voice-check, voice-drift, author-voice-drift; template `CoreferenceStreamEvent`):

```
data: {"event":"progress","progress":"...","is_final":false, ...}
data: {"event":"result","result":{...per-item payload...},"is_final":false, ...}
data: {"event":"done","is_final":true, ...}
data: {"event":"error","error":"...","is_final":true, ...}   ← in-band terminal error
data: [DONE]
```

Example — `POST /api/v1/analysis/character-voice/{novel_id}` (CAP-IN-09), request `CharacterVoiceRequest {chapter_ids: list[str] | None = None}` (None/empty = all chapters); `result` carries `CharacterVoiceResult {character_name: str = "", voice_analysis: VoiceAnalysis | None, distinctiveness_notes: str | None, kb_entry_id: str | None}`; `kb_entry_id` is `null` when no matching character KB entry exists (result still streamed). Payloads may be enriched with `x_trace_id`/`x_span_id` keys (`_app/observability.enrich_sse_data`) — parsers must tolerate extra top-level keys.

Parser contract for `benchmark/sse.py` (Task 3): read `data:` lines; `[DONE]` sentinel ends accumulation; JSON-decode the rest; branch on presence of `event` (flavor B) vs. item shape (flavor A); `{"error", "code"}` = in-band error; treat `event=error` or `is_final=true`+error accordingly.

## 7. Capability endpoint index (all 26, decorator-verified 2026-08-27)

Auth: Bearer for all except setup models discovery (§3.5) and monitoring. RL = rate-limited (AI analysis 5/min unless noted). Paths verified against router decorators; per-capability output artifacts/notes: see `benchmark/inventory/0{1,2,3}-*.md`.

| CAP id | Direction | Endpoint(s) under `/api/v1` | SSE | RL | Router file |
|---|---|---|---|---|---|
| CAP-IN-01 | in | `POST /novels/{novel_id}/kb/extract/{chapter_id}` · `POST /novels/{novel_id}/kb/extract/apply` | no | yes | `kb/router_extraction.py` |
| CAP-IN-02 | in | `POST /novels/{novel_id}/kb/sessions` · `POST …/sessions/{session_id}/suggest/{field_key}` · `POST …/sessions/{session_id}/interview` · `POST …/sessions/{session_id}/enhance` · `PATCH …/sessions/{session_id}/fields/{field_key}` · `POST …/sessions/{session_id}/complete` | no | yes | `kb/router_sessions.py`, `kb/router_sessions_complete.py` |
| CAP-IN-03 | in | `POST /novels/{novel_id}/kb/entities/{entry_id}/improve` · `POST …/improve/apply` | no | yes | `kb/router_improve.py` |
| CAP-IN-04 | in | `POST /novels/{novel_id}/kb/worldbuilding/analyze` · `POST …/worldbuilding/apply` | no | yes | `kb/router_worldbuilding.py` |
| CAP-IN-05 | in | `POST /novels/{novel_id}/kb/entries` · `PATCH …/kb/entries/{entry_id}` · `POST /series/{series_id}/kb` · `PATCH /series/{series_id}/kb/{entry_id}` · `POST /novels/{novel_id}/kb/relationships` | no | no | `kb/router.py`, `kb/router_canon.py`, `kb/router_relationships.py` |
| CAP-IN-06 | in | `POST /novels/{novel_id}/kb/{entry_id}/promote` · `POST …/{entry_id}/demote` · `POST /series/{series_id}/novels` (join preview) · `POST /series/{series_id}/novels/{novel_id}/apply` | no | no | `kb/router_scope.py`, `series/router_novels.py` |
| CAP-IN-07 | in | `POST /planning/timeline/{novel_id}/extract` · `POST /planning/timeline/{novel_id}/extract/confirm` | **yes** (flavor A) | yes | `planning/router_timeline_analysis.py` |
| CAP-IN-08 | in | `POST /novels/{novel_id}/wiki/summaries/{entity_id}/refresh` · `POST /novels/{novel_id}/wiki/mark-stale` | no | yes | `wiki/router.py` |
| CAP-IN-09 | in | `POST /analysis/character-voice/{novel_id}` | **yes** (flavor B) | yes | `analysis/router_character_voice.py` |
| CAP-OUT-01 | out | `GET /novels/{novel_id}/kb/entries` · `GET …/kb/entries/autocomplete` | no | no | `kb/router.py`, `kb/router_references.py` |
| CAP-OUT-02 | out | `GET /novels/{novel_id}/kb/entries/search` | no | no | `kb/router.py` |
| CAP-OUT-03 | out | `GET /novels/{novel_id}/kb/entries/{entry_id}` · `GET …/entries/{entry_id}/relationships` · `GET …/kb/relationships/inverse-suggestion` | no | no | `kb/router.py`, `kb/router_relationships.py` |
| CAP-OUT-04 | out | `GET /novels/{novel_id}/kb/graph` · `GET …/kb/graph/shortest-path` | no | no | `kb/router_graph.py` |
| CAP-OUT-05 | out | `GET /series/{series_id}/kb` · `GET /series/{series_id}/kb/{entry_id}` | no | no | `kb/router_canon.py` |
| CAP-OUT-06 | out | `GET /novels/{novel_id}/wiki/summaries` · `GET …/wiki/summaries/{entity_id}` · `GET …/wiki/chapters/{chapter_id}/summary` · `GET …/wiki/index` | no | no | `wiki/router.py` |
| CAP-OUT-07 | out | `GET /planning/timeline/{novel_id}/events` · `GET …/events/{event_id}` · `GET …/character-ages` | no | no | `planning/router_timeline.py`, `planning/router_timeline_analysis.py` |
| CAP-OUT-08 | out | `GET /novels/{novel_id}/kb/suggestions/{chapter_id}` (`max_results ≤ 100`) | no | no | `kb/router_suggestions.py` |
| CAP-OUT-09 | out | `POST /novels/{novel_id}/kb/resolve-references` | no | no | `kb/router_references.py` |
| CAP-OUT-10 | out | `GET /novels/{novel_id}/kb/templates` · `GET …/kb/templates/{entity_type}` | no | no | `templates/router.py` |
| CAP-CHK-01 | check | `POST /novels/{novel_id}/kb/consistency-check` (+ dismiss mgmt: `POST …/kb/consistency/dismiss`, `GET …/kb/consistency/dismissed`, `DELETE …/kb/consistency/dismissed/{fingerprint}`) | no | yes | `kb/router_consistency.py` |
| CAP-CHK-02 | check | `POST /series/{series_id}/consistency/check` · `GET /series/{series_id}/consistency/{novel_id}` | no | yes | `series/router_consistency.py` |
| CAP-CHK-03 | check | `POST /series/{series_id}/voice-drift/check` | no | yes | `series/router_voice_drift.py` |
| CAP-CHK-04 | check | `GET /planning/timeline/{novel_id}/consistency` → `TemporalConsistencyResponse {issues: [{severity, rule_id, event_ids, description, suggestion, source}], deterministic_pass, overall_assessment}` | no | yes | `planning/router_timeline_analysis.py` |
| CAP-CHK-05 | check | `POST /analysis/voice-check/{chapter_id}` | **yes** (flavor B) | yes | `analysis/router_voice_check.py` |
| CAP-CHK-06 | check | `POST /analysis/voice-drift/{novel_id}` | **yes** (flavor B) | yes | `analysis/router_voice_drift.py` |
| CAP-CHK-07 | check | `POST /analysis/author-voice-drift/{novel_id}` | **yes** (flavor B) | yes | `analysis/router_author_voice_drift.py` |

**Series lifecycle prerequisite** (for CAP-CHK-02/03, CAP-IN-06): `POST /api/v1/series` with `SeriesCreateRequest {title: str, subtitle: str | None, description: str | None, genre: str | None, writing_language: str | None, status: SeriesStatus | None, planned_novel_count: int | None}` → 201 `SeriesResponse {id, user_id, title, subtitle, description, genre, writing_language, status, ...}`; novel→series join via `POST /api/v1/series/{series_id}/novels` (preview, `JoinPreview`) + `POST /api/v1/series/{series_id}/novels/{novel_id}/apply` (`JoinResult`).

**Unmounted (→ `SKIPPED(unavailable)` per plan Task 7):** KB merge router (`kb/router_merge.py`, `POST /novels/{novel_id}/kb/merge`) and chapter↔KB consistency router (`consistency/router.py`, `POST /consistency/check`, `POST /consistency/check/stream`, `POST /consistency/chapters/{chapter_id}/check`) are implemented but never included in `_app/main.py` — all routes 404 at runtime (inventory 01-in Finding 1, 03-check Finding 1).

**Import mode note (plan Task 6):** no bulk chapter-import endpoint exists. `StarterContent.IMPORT` + `import_path` refers to a server-local path in the setup wizard — not usable for corpus upload via HTTP. Import mode = incremental without per-chapter waits; the reference-KB import path is manual entry authoring (CAP-IN-05).

## 8. OPEN items

| Id | Item | Blocking question | Impact |
|---|---|---|---|
| OPEN-1 | No dedicated version endpoint (`/version` or `/api/v1/version`) — only `info.version` in `GET /openapi.json`. | None — manifest (Task 14) records `GET /openapi.json` → `info.version`. Flag if a version endpoint is added later. | non-blocking |
| OPEN-2 | Per-endpoint request/response shapes for CAP entries beyond §2–§7 deep dives (e.g. `KBEntryResponse` field list, `GraphResponse`, session/`JoinPreview` bodies) are documented by name here and in inventory; verbatim field lists are read from the respective `schemas*.py` by the driver tasks (8–10) at implementation time. | Driver tasks must read the cited router/schema files before coding parsers. | non-blocking (deliberate deferral, per plan: investigation outputs committed, drivers consume routers) |
| OPEN-3 | **RESOLVED** (Task-16 rehearsal + fix). Middleware read line-by-line (`middleware.py dispatch`): no-`Origin`/no-`Referer` state-changing requests require a syntactically valid Bearer token; register/login carry none and were rejected 403 `CSRF_ORIGIN_MISMATCH` in the rehearsal — exactly the checkpoint outcome anticipated here. | Fixed at the client: `BenchmarkClient` sends `Origin` on every request from config `api.origin` (OPTIONAL, default `http://localhost:3000` = the server's default trusted origin; validation: bare origin `scheme://host[:port]`, no path/trailing slash). Escape hatch for a non-default server trust list: set `api.origin` to an entry of `NARRARE_CSRF_TRUSTED_ORIGINS` (env, JSON list). | resolved |
| OPEN-4 | 429 rate-limit body shape (`RateLimiter` dep raises `HTTPException(429, detail=...)`) — detail string not captured verbatim. | Client (Task 3) should treat **status 429** as the signal, not parse the body. | non-blocking |
