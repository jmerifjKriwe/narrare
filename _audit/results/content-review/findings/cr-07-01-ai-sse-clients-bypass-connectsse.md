# CR-07-01 — AI SSE clients bypass canonical `connectSSE()`

**Priority:** High

## Finding

Several frontend AI streaming clients implement their own `fetch()` + `ReadableStream` parsing instead of the canonical `connectSSE()` required by `docs/development/ui-principles.md:836-845`.

## Evidence

- `packages/web/lib/api/generation.ts:229-348` — `streamRewrite()` manually fetches `/rewrite` SSE.
- `packages/web/lib/api/generation.ts:374-456` — `streamExtend()` manually fetches `/extend` SSE.
- `packages/web/lib/api/generation.ts:459-527` — `streamGeneration()` manually fetches `/generation/{requestId}/stream` SSE.
- `packages/web/lib/api/coauthor.ts:74-185` — `streamCoAuthor()` manually fetches `/co-author` SSE.
- Canonical helper exists in `packages/web/lib/api/streaming.ts:17-84` and is used by KB/timeline clients, e.g. `packages/web/lib/api/kb-sessions.ts:148-178`.

## User impact

Duplicated streaming code makes AI UX inconsistent: abort behavior, malformed chunk handling, error mapping, and connection-loss handling diverge per feature. It also makes §16 machine checks harder and increases regression risk.

## Expected standard

Every SSE-capable AI endpoint should use `connectSSE()` unless there is a documented architectural exception.
