# Q-020 — When can the temporary @swc/helpers standalone-tracing workaround be removed?

> **Status:** 🟡 Open
> **Blocks:** Removal of the `outputFileTracingIncludes` block in `packages/web/next.config.ts`
> **Raised:** 2026-08-20 (post-merge of npm deps batch, PR #181 / merge 0d9c175c)

---

## Context

`next@16.3.1` combined with `@swc/helpers >= 0.5.17` produces an exports-condition
divergence between server runtime and build-time tracing:

- `@swc/helpers >= 0.5.17` lists the `module-sync` condition (resolving to `esm/*.js`)
  first in its `exports` map.
- Node 24 supports native `require(esm)` and therefore activates `module-sync` at
  server runtime — the standalone server loads `@swc/helpers/esm/*.js`.
- Next's output-file tracing (next@16.3.1) resolves with classic `require` conditions,
  so only the `cjs/*.cjs` variants are traced into `.next/standalone`.
- Result: standalone server crashes on boot with
  `MODULE_NOT_FOUND: @swc/helpers/esm/_interop_require_default.js`.

Surfaced post-merge on the main CI run 32371751047: `test-e2e` is main-push-only,
so PR CI never booted the standalone build and the gap was invisible before merge.

## Mitigation (live)

`outputFileTracingIncludes` glob in `packages/web/next.config.ts` — introduced in
commit 5e014943 and marked **"DELETE this block"** in-code:

```ts
outputFileTracingIncludes: {
  "/**": ["../../node_modules/.pnpm/@swc+helpers@*/node_modules/@swc/helpers/esm/**"],
},
```

## Removal Condition (core)

First **stable** Next release (> 16.3.1) with condition-aware output-file tracing.

### Removal verification (all four steps required)

1. Delete the `outputFileTracingIncludes` block from `packages/web/next.config.ts`.
2. `E2E_FRONTEND_MODE=build just e2e` is green (standalone boot exercised).
3. Without the include:
   `find packages/web/.next/standalone -path '*@swc/helpers/esm/_interop_require_default.js' | wc -l`
   reports **≥ 1**.
4. Commit the removal referencing this document; move this file to `resolved/`.

## Cross-References

- PR #181 / merge 0d9c175c — npm deps batch that raised `@swc/helpers` to ≥ 0.5.17.
- Commit 5e014943 — workaround introduction (this doc's anchor commit).
- New CI job `frontend-standalone` — PR-gated standalone smoke test landing in the
  same batch; prevents recurrence of the main-only blind spot.
- Upstream facts at time of writing: no stable `next > 16.3.1` exists yet;
  `@swc/core` declares a peer floor `@swc/helpers >= 0.5.17`, which forbids
  downgrading below 0.5.17 (where `module-sync` begins) as an alternative.

## Resolution

*Not yet resolved. Re-evaluate on each Next version bump: check whether the new
stable release ships condition-aware tracing, then run the removal verification
above.*
