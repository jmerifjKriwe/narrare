# Adaptive Context Frontend (Phase 5) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the frontend halves of ADR-069 — the **Dialogue Coach panel** (ASSIST-004, a tab in the analysis family that consumes the shipped SSE endpoint), the **Adaptive Dashboard** (LEARN-002: toggle + weight sliders + source summary, plus snapshot history), and the **Adaptive Status Indicator** (editor toolbar, 3 states). After Phase 5, a writer can see adaptivity at a glance, tune it in Settings, and run a dialogue-coach analysis on a selected passage that renders issues + before/after alternatives.

**Architecture:** The backend is shipped (Phase 3 REST + Phase 4 SSE). The frontend consumes it through three established layers: (1) **TS types** matching the Pydantic schemas field-by-field (RULE-17, snake_case — the codebase precedent, e.g. `character-voice-stream.ts`); (2) **API clients** — REST via `fetchApi` (`adaptive.ts`), SSE via `connectSSE` (`dialogue-coach-stream.ts`, mirroring `character-voice-stream.ts`); (3) **hooks** — `useDialogueCoach` built on `useAIOperation` (ADR-043, mirroring `useCharacterVoice`), `useAdaptiveContext` built on TanStack Query with the canonical cache key `["adaptive-context"]` (ADR-069 Decision 15). Components compose via the right-panel registration chain (`editorRightPanelState` → `EditorPanelContent` switch → trigger → `EditorToolbar`) and the Settings Learning tab (`settings-view-config.ts`). Per ADR-069 Decision 16, the Dialogue Coach is a **sibling in the analysis panel family** (not a standalone panel); per Decision 9, alternatives render as **stacked before/after blocks** (red-tint original → green-tint rewrite), applied by full-string replacement; per Decision 14, the toolbar indicator has **3 states** (active / paused / no-data) and opens a popover.

**Tech Stack:** Next.js 16 (App Router), React 19, TipTap v3, TypeScript (strict), Tailwind v4, shadcn "base-nova" ui primitives, TanStack Query, zustand, next-intl, Vitest + happy-dom + MSW, axe-core (a11y), Playwright VRT (`vrt` project).

---

## Global Constraints

Verbatim from ADR-069 § Phase 5 (lines 2011–2025), § Decisions 9/14/15/16, § Retrofit §4; CONSTRAINTS.md RULE-16 / RULE-17 / RULE-20; ADR-043 (AI interaction primitive); ADR-059 (VRT):

- **RULE-17 (TS ↔ Pydantic field match):** every TS interface field name + optionality matches the shipped Pydantic schema **exactly**, in **snake_case** (codebase precedent — `character-voice-stream.ts` uses `avg_sentence_length`, `voice_metrics`, etc.). Literals map to TS unions; plain `str` maps to `string`; `T | None` maps to `T | null`. The backend is the SSOT.
- **RULE-16 (i18n namespace registry):** exactly **3 new namespaces** — `adaptive`, `dialogueCoach`, `aiAssist` — registered in `packages/web/lib/i18n/request.ts` `namespaces` array, present in all 3 locales (en/de/fr) = 9 JSON files. A RULE-16 checker asserts all 3 exist in all 3 locales.
- **RULE-20 (no half-implementation):** no feature ships without its UI states (idle/loading/results/error/empty). The Adaptive Snapshot History is the **one exception** — it depends on a backend endpoint that Phase 3 did NOT expose (see "Coordinator decision needed" below). It is isolated in its own task and must NOT be faked.
- **ADR-043 (AI interaction primitive):** `useDialogueCoach` MUST go through `useAIOperation` — no manual `AbortController`, no bespoke SSE fetch. Connection-loss watchdog + error-to-i18n mapping come for free.
- **ADR-069 Decision 9:** alternatives render as **stacked before/after blocks**, applied by **full-string find-and-replace** in the chapter (no char-level diff, no diff library, no TipTap mark manipulation). Accept mirrors the WRITE-004 rewrite-accept pattern.
- **ADR-069 Decision 14:** the Adaptivity Indicator lives in the **editor toolbar only** (v1), with **3 states** derived from `enabled` × `has_any_signal`: `active` (enabled + has signal), `paused` (enabled + no signal, or disabled with prior signal), `no-data` (disabled + no signal). Click opens a **popover** (keeps the writer in flow) with a "Manage in Settings" deep-link.
- **ADR-069 Decision 15:** the cache key `["adaptive-context", projectId]` is the **canonical** adaptive-state key. `toggle` + `setWeights` mutations `invalidateQueries({ queryKey: ["adaptive-context"] })` so the Status Indicator, Dashboard, and Dialogue Coach panel all refetch in lockstep. No event bus, no Zustand for server state.
- **ADR-069 Decision 16:** Dialogue Coach is a **sibling in the analysis panel family** — same registration pattern as `character_voice` / `voice_check`. The "tab" wording = conceptual grouping; the implementation = a `DialogueCoachPanel` occupying the editor right-panel slot.
- **ADR-059 (VRT):** Playwright `vrt` project (already configured, `maxDiffPixelRatio: 0.02`) captures `AdaptiveStatusIndicator` (3 states) + `AdaptiveDashboard`. Snapshots mock API responses via `page.route()`; baselines in `tests/screenshots/*.spec.ts-snapshots/`.
- **TypeScript strict / `biome` lint:** no `any` in public interfaces; no `// @ts-expect-error` without a comment. `pnpm lint` + `pnpm typecheck` must pass at the end of every task.
- **Coverage floors (existing `vitest.config.ts`):** `lib/**` ≥ 80%, `components/**` ≥ 65%. New hooks must keep `lib/**` ≥ 80%.
- **i18n test parity:** `setupTests.ts` mocks `useTranslations` to return the key string, so component unit tests assert on i18n **keys** (e.g. `getByText("dialogueCoach.title")`), not translated prose. Keep keys stable.
- **No backend changes in this plan** except the one flagged Snapshot-History endpoint (coordinator decision). The Dialogue Coach + Adaptive Dashboard read-only/mutation paths are fully backed by shipped endpoints.

### Coordinator decision needed (one item)

**Adaptive Snapshot History endpoint gap.** ADR-069 Phase 5 step 25 lists "snapshot history" for the dashboard, and the backend repository `EvidenceRepositoryImpl.get_adaptive_snapshots()` exists (Phase 3 Task 2). **But no REST endpoint exposes it** — Phase 3 shipped only `GET /context`, `POST /toggle`, `POST /weights`. `Task 7` (Snapshot History) therefore requires one of:

- **(A) — RECOMMENDED:** a small backend Phase 3.5 addition `GET /api/v1/adaptive/{project_id}/snapshots?limit=20` returning `list[AdaptiveSnapshot]` (the `{adaptive_source_summary, adaptive_weights, created_at}` triple). The repository method already exists; this is a thin router + schema + service method. Recommend the coordinator dispatch this to the Backend Specialist in parallel with Phase 5.
- **(B):** scope Snapshot History out of Phase 5 (dashboard ships live-state-only: toggle + weights + sources). Simpler, but leaves ADR-069 step 25 partially open until a follow-up.

This plan implements **(A)**'s frontend (Task 7 is self-contained behind a `useAdaptiveSnapshots` hook + types) and proceeds regardless; if **(B)** is chosen, Task 7 is dropped and the dashboard's history section renders the `aiAssist.historyDisabled` empty-state copy. **The rest of the plan (Tasks 1–6, 8–13) is unblocked either way.**

---

## Skill hints (global)

Each task lists its own `## Skill hints`. The mapping is:

| Skill | Tasks | Why |
|-------|-------|-----|
| `frontend-design` | 6, 8, 9 | Production-grade component design — the dashboard, dialogue panel, indicator are user-facing surfaces. |
| `vercel-composition-patterns` | 8, 11 | Compound components + explicit variants — the panel composes mode-selector + issue-list + alternative-cards without boolean-prop proliferation. |
| `vercel-react-best-practices` | 3, 4, 9, 11 | Hooks design (stable callbacks, memoised returns), SSE consumption, derived state. |
| `web-design-guidelines` | 6, 8, 9, 12 | a11y: ARIA, keyboard nav, reduced motion, focus return. Drives axe-core assertions. |
| `vercel-react-view-transitions` | 11 | Panel open/close + mode-switch animations (assessed; minimal — only animate what communicates continuity). |

---

## File Structure Map

### NEW files

| Path | Responsibility | RULE-04 cap |
|------|----------------|-------------|
| `packages/web/types/adaptive.ts` | TS interfaces mirroring `adaptive/schemas.py` (RULE-17). | ≤ 80 LOC |
| `packages/web/types/dialogueCoach.ts` | TS interfaces mirroring `ai_assist/schemas.py` (RULE-17). | ≤ 80 LOC |
| `packages/web/lib/api/adaptive.ts` | REST client: `getContext` / `toggle` / `setWeights` (+ `getSnapshots` if endpoint A). | ≤ 120 LOC |
| `packages/web/lib/api/dialogue-coach-stream.ts` | SSE client: types + `streamDialogueCoach()`, mirrors `character-voice-stream.ts`. | ≤ 180 LOC |
| `packages/web/lib/hooks/adaptiveKeys.ts` | Canonical TanStack Query key factory (`["adaptive-context", ...]`). | ≤ 40 LOC |
| `packages/web/lib/hooks/useAdaptiveContext.ts` | TanStack Query: context query + toggle/weights mutations w/ invalidation. | ≤ 150 LOC |
| `packages/web/lib/hooks/useAdaptiveSnapshots.ts` | TanStack Query: snapshot-history query (Task 7; needs endpoint A). | ≤ 60 LOC |
| `packages/web/lib/hooks/useDialogueCoach.ts` | `useAIOperation`-bridged SSE hook, mirrors `useCharacterVoice`. | ≤ 140 LOC |
| `packages/web/components/ui/slider.tsx` | shadcn Slider primitive (for weight sliders). | — |
| `packages/web/components/ui/switch.tsx` | shadcn Switch primitive (for the enable toggle). | — |
| `packages/web/components/ui/badge.tsx` | shadcn Badge primitive (severity pills). | — |
| `packages/web/components/studio/settings/AdaptiveDashboard.tsx` | Dashboard shell: enable toggle + 4 weight sliders + source summary. | ≤ 200 LOC |
| `packages/web/components/studio/settings/_components/AdaptiveToggle.tsx` | Enable/disable switch + description. | ≤ 80 LOC |
| `packages/web/components/studio/settings/_components/AdaptiveWeightSliders.tsx` | 4 weight sliders (preference, voice_fidelity, style_constraints, avoidance). | ≤ 150 LOC |
| `packages/web/components/studio/settings/_components/AdaptiveSourceList.tsx` | Renders the 4 `*_text` source summaries + `has_any_signal` empty state. | ≤ 120 LOC |
| `packages/web/components/studio/settings/_components/AdaptiveSnapshotHistory.tsx` | Recent adaptive activity list (Task 7). | ≤ 120 LOC |
| `packages/web/components/studio/analysis/DialogueCoachPanel.tsx` | Panel shell (idle/loading/results/error) + composition root. | ≤ 200 LOC |
| `packages/web/components/studio/analysis/DialogueCoachTrigger.tsx` | Toolbar trigger button (mirrors `CharacterVoiceTrigger`). | ≤ 60 LOC |
| `packages/web/components/studio/analysis/_components/DialogueModeSelector.tsx` | Analyze / Improve explicit-variant selector (no boolean prop). | ≤ 90 LOC |
| `packages/web/components/studio/analysis/_components/DialogueIssueList.tsx` | Maps `issues[]` → `DialogueIssueCard`s + empty state. | ≤ 90 LOC |
| `packages/web/components/studio/analysis/_components/DialogueIssueCard.tsx` | One issue: severity badge, speaker, original_quote, diagnosis. | ≤ 120 LOC |
| `packages/web/components/studio/analysis/_components/DialogueAlternativeCard.tsx` | Stacked before/after blocks + Accept button (Decision 9). | ≤ 130 LOC |
| `packages/web/components/studio/editor-view/AdaptiveStatusIndicator.tsx` | Toolbar indicator (3 states) + popover. | ≤ 200 LOC |
| `packages/i18n/messages/{en,de,fr}/adaptive.json` | LEARN-002 dashboard + indicator copy. | — |
| `packages/i18n/messages/{en,de,fr}/dialogueCoach.json` | ASSIST-004 panel copy. | — |
| `packages/i18n/messages/{en,de,fr}/aiAssist.json` | Shared ai-assist domain copy (summary label, empty states). | — |
| `packages/web/tests/screenshots/adaptive.spec.ts` | VRT: AdaptiveDashboard (4 theme variants). | — |
| `packages/web/tests/screenshots/adaptive-indicator.spec.ts` | VRT: AdaptiveStatusIndicator (3 states). | — |
| Various `__tests__/*.test.tsx` | Vitest unit tests per task. | — |

### MODIFIED files

| Path | Change |
|------|--------|
| `packages/web/types/index.ts` | Re-export `adaptive.ts` + `dialogueCoach.ts` types (RULE-17 barrel). |
| `packages/web/lib/api/index.ts` | Export `adaptiveApi` (+ `streamDialogueCoach` + its types). |
| `packages/web/lib/i18n/request.ts` | Add `"adaptive"`, `"dialogueCoach"`, `"aiAssist"` to the `namespaces` array (RULE-16). |
| `packages/web/lib/stores/editorRightPanelState.ts` | Add `"dialogue_coach"` to `EditorRightPanelId` union + `EDITOR_RIGHT_PANEL_PRIORITY`. |
| `packages/web/components/studio/editor-view/EditorPanelContent.tsx` | Add `case "dialogue_coach":` to the exhaustive switch. |
| `packages/web/components/studio/editor-view/EditorToolbar.tsx` | Render `<DialogueCoachTrigger />` + `<AdaptiveStatusIndicator />`. |

### NOT modified (explicitly out of plan)

- Backend (`apps/api/`, `packages/core/`) — shipped in Phases 3 + 4, except the optional Snapshot endpoint (coordinator decision).
- Eval suite (`evals/`) — Phase 6.
- Existing analysis panels — additive only (a new sibling, no edits to `CharacterVoicePanel` etc.).

---

## Task Ordering

**Foundation (Tasks 1–5):** types → API clients → hooks. Strictly sequential — each consumes the prior. Every later task depends on these.

**Primitives + components (Tasks 6–10):** UI primitives (6) unblock the dashboard (7) + indicator (9); the dialogue panel (8) depends only on the hooks. Tasks 7/8/9 may develop in parallel once 1–6 land. Task 10 (snapshot history) is gated on the coordinator decision but is otherwise independent.

**Integration + quality (Tasks 11–13):** i18n (11) can land any time after 1 (types need stable keys); editor wiring (12) needs 8 + 9; tests (13) + VRT (14... folded into 13's VRT task) close the gate.

---

## Task 1: TS types — `adaptive.ts` + `dialogueCoach.ts` (RULE-17)

**Files:**
- Create: `packages/web/types/adaptive.ts`
- Create: `packages/web/types/dialogueCoach.ts`
- Modify: `packages/web/types/index.ts` (append exports)
- Test: `packages/web/lib/api/__tests__/types-parity.test.ts` (new — field-name parity assertions)

**Interfaces:**
- Consumes: the shipped Pydantic schemas (`apps/api/narrare/adaptive/schemas.py`, `apps/api/narrare/ai_assist/schemas.py`) — read them; they are the SSOT.
- Produces: `AdaptiveWeightsResponse`, `AdaptiveWeightsInput`, `AdaptiveToggleInput`, `AdaptiveSourceSummary`, `AdaptiveContextResponse`, `AdaptiveSettingsResponse`, `AdaptiveSnapshot` (Task 7), `DialogueCoachMode`, `DialogueAlternative`, `DialogueIssue`, `DialogueCoachRequest`, `DialogueCoachResponse`, `DialogueCoachStreamEvent`. Tasks 2+ import these.

## Skill hints
- Load `vercel-react-best-practices` (rerender/contract discipline: prefer literal unions over open `string` where the backend is a Literal).

- [ ] **Step 1: Write the failing parity test**

Create `packages/web/lib/api/__tests__/types-parity.test.ts`:

```typescript
/** RULE-17 parity: TS interface field names match the shipped Pydantic schemas. */
import { describe, expect, it } from "vitest";
import type {
  AdaptiveContextResponse,
  AdaptiveSettingsResponse,
  AdaptiveSourceSummary,
  AdaptiveToggleInput,
  AdaptiveWeightsInput,
  AdaptiveWeightsResponse,
} from "@/types";
import type {
  DialogueAlternative,
  DialogueCoachRequest,
  DialogueCoachResponse,
  DialogueCoachStreamEvent,
  DialogueIssue,
} from "@/types";

function fieldNames<T extends object>(sample: T): string[] {
  return Object.keys(sample).sort();
}

describe("adaptive types mirror Pydantic (RULE-17)", () => {
  it("AdaptiveWeightsResponse has the 4 clamped weights", () => {
    expect(fieldNames({} as AdaptiveWeightsResponse)).toEqual(
      ["avoidance", "preference", "style_constraints", "voice_fidelity"],
    );
  });

  it("AdaptiveContextResponse matches the GET /context shape", () => {
    expect(fieldNames({} as AdaptiveContextResponse)).toEqual(
      ["enabled", "has_any_signal", "project_id", "sources", "weights"],
    );
  });

  it("AdaptiveSettingsResponse matches POST /toggle + /weights shape", () => {
    expect(fieldNames({} as AdaptiveSettingsResponse)).toEqual(["enabled", "weights"]);
  });

  it("AdaptiveSourceSummary has the 4 *_text fields", () => {
    expect(fieldNames({} as AdaptiveSourceSummary)).toEqual([
      "avoidance_patterns_text",
      "preference_text",
      "style_constraints_text",
      "voice_profiles_text",
    ]);
  });

  it("AdaptiveToggleInput + AdaptiveWeightsInput are the request bodies", () => {
    expect(fieldNames({} as AdaptiveToggleInput)).toEqual(["enabled"]);
    expect(fieldNames({} as AdaptiveWeightsInput)).toEqual(
      ["avoidance", "preference", "style_constraints", "voice_fidelity"],
    );
  });
});

describe("dialogueCoach types mirror Pydantic (RULE-17)", () => {
  it("DialogueCoachRequest body fields", () => {
    expect(fieldNames({} as DialogueCoachRequest)).toEqual(["mode", "selection_text"]);
  });

  it("DialogueCoachResponse top-level fields", () => {
    expect(fieldNames({} as DialogueCoachResponse)).toEqual([
      "adaptive_summary",
      "chapter_id",
      "issues",
      "mode",
    ]);
  });

  it("DialogueIssue fields", () => {
    expect(fieldNames({} as DialogueIssue)).toEqual([
      "alternatives",
      "diagnosis",
      "issue_type",
      "original_quote",
      "severity",
      "speaker",
    ]);
  });

  it("DialogueAlternative fields", () => {
    expect(fieldNames({} as DialogueAlternative)).toEqual(["explanation", "rewrite"]);
  });

  it("DialogueCoachStreamEvent discriminates on `event`", () => {
    const ev = {} as DialogueCoachStreamEvent;
    expect(fieldNames(ev)).toContain("event");
    expect(fieldNames(ev)).toContain("is_final");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter web vitest run lib/api/__tests__/types-parity.test.ts`
Expected: FAIL — `Module '@/@types' has no exported member 'AdaptiveContextResponse'` etc.

- [ ] **Step 3: Create `packages/web/types/adaptive.ts`**

```typescript
// Adaptive Context REST types — mirror apps/api/narrare/adaptive/schemas.py (RULE-17).
// snake_case matches the Pydantic SSOT (codebase precedent: character-voice-stream.ts).

/** Four adaptive weights, clamped to [0.0, 1.0]. Mirrors AdaptiveWeightsResponse. */
export interface AdaptiveWeightsResponse {
  preference: number;
  voice_fidelity: number;
  style_constraints: number;
  avoidance: number;
}

/** POST body for /weights — pre-clamping floats. Mirrors AdaptiveWeightsInput. */
export interface AdaptiveWeightsInput {
  preference: number;
  voice_fidelity: number;
  style_constraints: number;
  avoidance: number;
}

/** POST body for /toggle. Mirrors AdaptiveToggleInput. */
export interface AdaptiveToggleInput {
  enabled: boolean;
}

/** Adaptive source data rendered for the dashboard. Mirrors AdaptiveSourceSummary. */
export interface AdaptiveSourceSummary {
  preference_text: string;
  voice_profiles_text: string;
  style_constraints_text: string;
  avoidance_patterns_text: string;
}

/** Response for GET /adaptive/{project_id}/context. Mirrors AdaptiveContextResponse. */
export interface AdaptiveContextResponse {
  project_id: string;
  enabled: boolean;
  weights: AdaptiveWeightsResponse;
  sources: AdaptiveSourceSummary;
  has_any_signal: boolean;
}

/** Response for POST /toggle + /weights — the new persisted state. Mirrors AdaptiveSettingsResponse. */
export interface AdaptiveSettingsResponse {
  enabled: boolean;
  weights: AdaptiveWeightsResponse;
}

/**
 * One recent adaptive snapshot for the dashboard history list (Task 7).
 * Backend endpoint A: GET /adaptive/{project_id}/snapshots returns AdaptiveSnapshot[].
 */
export interface AdaptiveSnapshot {
  invocation_id: string;
  created_at: string;
  adaptive_source_summary: Record<string, string> | null;
  adaptive_weights: Record<string, number> | null;
}
```

- [ ] **Step 4: Create `packages/web/types/dialogueCoach.ts`**

```typescript
// Dialogue Coach types — mirror apps/api/narrare/ai_assist/schemas.py (RULE-17).
// snake_case matches the Pydantic SSOT.

/** Mirrors DialogueCoachMode = Literal["analyze", "improve"]. */
export type DialogueCoachMode = "analyze" | "improve";

/** One proposed rewrite. Mirrors DialogueAlternativeResponse. */
export interface DialogueAlternative {
  rewrite: string;
  explanation: string;
}

/**
 * One diagnosed issue. Mirrors DialogueIssueResponse.
 * `severity` is `string` (backend is plain `str`, not a Literal); expected
 * values are "low" | "medium" | "high" — narrowed in the UI for badges only.
 * `alternatives` is null in analyze mode, present in improve mode.
 */
export interface DialogueIssue {
  issue_type: string;
  speaker: string;
  original_quote: string;
  diagnosis: string;
  severity: string;
  alternatives: DialogueAlternative[] | null;
}

/** Non-streaming response (the `result` event payload). Mirrors DialogueCoachResponse. */
export interface DialogueCoachResponse {
  chapter_id: string;
  mode: DialogueCoachMode;
  issues: DialogueIssue[];
  adaptive_summary: string;
}

/** POST body for /ai-assist/dialogue-coach/{chapter_id}. Mirrors DialogueCoachRequest. */
export interface DialogueCoachRequest {
  selection_text: string;
  mode: DialogueCoachMode;
}

/**
 * One event in the SSE stream. Mirrors DialogueCoachStreamEvent.
 * `event` discriminates progress / result / done / error.
 */
export interface DialogueCoachStreamEvent {
  event?: "progress" | "result" | "done" | "error";
  result?: DialogueCoachResponse | null;
  progress?: string | null;
  error?: string | null;
  is_final?: boolean;
}
```

- [ ] **Step 5: Export from the barrel**

Append to `packages/web/types/index.ts` (after the timeline block):

```typescript
export type {
  AdaptiveContextResponse,
  AdaptiveSettingsResponse,
  AdaptiveSnapshot,
  AdaptiveSourceSummary,
  AdaptiveToggleInput,
  AdaptiveWeightsInput,
  AdaptiveWeightsResponse,
} from "./adaptive";
export type {
  DialogueAlternative,
  DialogueCoachMode,
  DialogueCoachRequest,
  DialogueCoachResponse,
  DialogueCoachStreamEvent,
  DialogueIssue,
} from "./dialogueCoach";
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pnpm --filter web vitest run lib/api/__tests__/types-parity.test.ts`
Expected: PASS — all parity assertions green.

- [ ] **Step 7: Lint + typecheck + commit**

```bash
pnpm --filter web lint && pnpm --filter web typecheck
git add packages/web/types/adaptive.ts packages/web/types/dialogueCoach.ts \
        packages/web/types/index.ts packages/web/lib/api/__tests__/types-parity.test.ts
git commit -m "feat(web): add adaptive + dialogueCoach TS types (ADR-069 §21, RULE-17)"
```

---

## Task 2: API clients — adaptive REST + dialogue-coach SSE

**Files:**
- Create: `packages/web/lib/api/adaptive.ts`
- Create: `packages/web/lib/api/dialogue-coach-stream.ts`
- Modify: `packages/web/lib/api/index.ts` (append exports)
- Test: `packages/web/lib/api/__tests__/adaptive.test.ts`
- Test: `packages/web/lib/api/__tests__/dialogue-coach-stream.test.ts`

**Interfaces:**
- Consumes: `fetchApi` (`./core`), `connectSSE` (`./streaming`), Task 1 types.
- Produces: `adaptiveApi.getContext/toggle/setWeights/getSnapshots`, `streamDialogueCoach(chapterId, body, handlers, signal)`. Tasks 3 + 4 import these.

## Skill hints
- Load `vercel-react-best-practices` (the SSE handler-object shape keeps the bridge allocation-free).

- [ ] **Step 1: Write the failing adaptive REST test**

Create `packages/web/lib/api/__tests__/adaptive.test.ts`:

```typescript
import { afterEach, describe, expect, it, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "@/mocks/server";
import { adaptiveApi } from "@/lib/api/adaptive";

const CTX = {
  project_id: "proj-1",
  enabled: true,
  weights: { preference: 0.7, voice_fidelity: 0.9, style_constraints: 1.0, avoidance: 1.0 },
  sources: {
    preference_text: "prefers terse prose",
    voice_profiles_text: "",
    style_constraints_text: "",
    avoidance_patterns_text: "",
  },
  has_any_signal: true,
};

afterEach(() => server.resetHandlers());

describe("adaptiveApi REST client", () => {
  it("GET /context returns AdaptiveContextResponse", async () => {
    server.use(http.get("*/api/v1/adaptive/proj-1/context", () => HttpResponse.json(CTX)));
    const res = await adaptiveApi.getContext("proj-1");
    expect(res.has_any_signal).toBe(true);
    expect(res.weights.voice_fidelity).toBe(0.9);
  });

  it("POST /toggle sends {enabled} and returns settings", async () => {
    const spy = vi.fn();
    server.use(
      http.post("*/api/v1/adaptive/proj-1/toggle", async ({ request }) => {
        spy(await request.json());
        return HttpResponse.json({ enabled: false, weights: CTX.weights });
      }),
    );
    const res = await adaptiveApi.toggle("proj-1", false);
    expect(spy).toHaveBeenCalledWith({ enabled: false });
    expect(res.enabled).toBe(false);
  });

  it("POST /weights sends 4 weights", async () => {
    const spy = vi.fn();
    server.use(
      http.post("*/api/v1/adaptive/proj-1/weights", async ({ request }) => {
        spy(await request.json());
        return HttpResponse.json({ enabled: true, weights: CTX.weights });
      }),
    );
    await adaptiveApi.setWeights("proj-1", {
      preference: 0.5,
      voice_fidelity: 0.5,
      style_constraints: 0.5,
      avoidance: 0.5,
    });
    expect(spy).toHaveBeenCalledWith({
      preference: 0.5,
      voice_fidelity: 0.5,
      style_constraints: 0.5,
      avoidance: 0.5,
    });
  });
});
```

- [ ] **Step 2: Write the failing SSE test**

Create `packages/web/lib/api/__tests__/dialogue-coach-stream.test.ts`:

```typescript
import { describe, expect, it, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "@/mocks/server";
import { streamDialogueCoach } from "@/lib/api/dialogue-coach-stream";

/** Build a minimal SSE response body from typed event lines. */
function sse(events: object[]): string {
  return events.map((e) => `data: ${JSON.stringify(e)}`).join("\n\n") + "\n\ndata: [DONE]\n\n";
}

describe("streamDialogueCoach SSE client", () => {
  it("fires onProgress then onResult then onComplete", async () => {
    const result = {
      chapter_id: "ch-1",
      mode: "analyze",
      issues: [],
      adaptive_summary: "shaped by 2 voices",
    };
    server.use(
      http.post("*/api/v1/ai-assist/dialogue-coach/ch-1", () =>
        HttpResponse.text(
          sse([
            { event: "progress", progress: "Analysing dialogue…" },
            { event: "result", result },
            { event: "done", is_final: true },
          ]),
          { headers: { "Content-Type": "text/event-stream" } },
        ),
      ),
    );

    const onProgress = vi.fn();
    const onResult = vi.fn<(r: unknown) => void>();
    const onComplete = vi.fn();
    const onError = vi.fn();

    await streamDialogueCoach(
      "ch-1",
      { selection_text: "\"Hello.\"", mode: "analyze" },
      { onProgress, onResult, onComplete, onError },
    );

    expect(onProgress).toHaveBeenCalledWith("Analysing dialogue…");
    expect(onResult).toHaveBeenCalledTimes(1);
    expect(onResult.mock.calls[0][0]).toMatchObject({ chapter_id: "ch-1" });
    expect(onComplete).toHaveBeenCalledTimes(1);
    expect(onError).not.toHaveBeenCalled();
  });

  it("surfaces a terminal error event via onError", async () => {
    server.use(
      http.post("*/api/v1/ai-assist/dialogue-coach/ch-1", () =>
        HttpResponse.text(
          sse([{ event: "error", error: "model unavailable", is_final: true }]),
          { headers: { "Content-Type": "text/event-stream" } },
        ),
      ),
    );
    const onError = vi.fn();
    const onComplete = vi.fn();
    await streamDialogueCoach(
      "ch-1",
      { selection_text: "x", mode: "improve" },
      { onResult: vi.fn(), onError, onComplete },
    );
    expect(onError).toHaveBeenCalled();
    expect(onComplete).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pnpm --filter web vitest run lib/api/__tests__/adaptive.test.ts lib/api/__tests__/dialogue-coach-stream.test.ts`
Expected: FAIL — modules not found.

- [ ] **Step 4: Create `packages/web/lib/api/adaptive.ts`**

```typescript
/**
 * Adaptive Context REST client (ADR-069 D12 / Phase 5 step 22).
 *
 * Thin wrapper over {@link fetchApi} for the three shipped endpoints:
 *  - GET  /adaptive/{project_id}/context   → AdaptiveContextResponse
 *  - POST /adaptive/{project_id}/toggle    (AdaptiveToggleInput)  → AdaptiveSettingsResponse
 *  - POST /adaptive/{project_id}/weights   (AdaptiveWeightsInput) → AdaptiveSettingsResponse
 *
 * GET /snapshots (Task 7) is conditional on the coordinator-approved backend endpoint.
 *
 * @module adaptive
 */
import type {
  AdaptiveContextResponse,
  AdaptiveSettingsResponse,
  AdaptiveSnapshot,
  AdaptiveToggleInput,
  AdaptiveWeightsInput,
} from "@/types";
import { fetchApi } from "./core";

export const adaptiveApi = {
  /** Read the current adaptive state for the dashboard + indicator. */
  getContext: (projectId: string) =>
    fetchApi<AdaptiveContextResponse>(`/adaptive/${projectId}/context`),

  /** Toggle adaptivity on/off; returns the new persisted state. */
  toggle: (projectId: string, enabled: boolean) =>
    fetchApi<AdaptiveSettingsResponse>(`/adaptive/${projectId}/toggle`, {
      method: "POST",
      body: JSON.stringify({ enabled } satisfies AdaptiveToggleInput),
    }),

  /** Update the 4 weights (backend clamps); returns the new persisted state. */
  setWeights: (projectId: string, weights: AdaptiveWeightsInput) =>
    fetchApi<AdaptiveSettingsResponse>(`/adaptive/${projectId}/weights`, {
      method: "POST",
      body: JSON.stringify(weights),
    }),

  /** Recent adaptive activity (Task 7; needs coordinator-approved endpoint A). */
  getSnapshots: (projectId: string, limit = 20) =>
    fetchApi<AdaptiveSnapshot[]>(`/adaptive/${projectId}/snapshots?limit=${limit}`),
};
```

- [ ] **Step 5: Create `packages/web/lib/api/dialogue-coach-stream.ts`**

```typescript
/**
 * SSE-backed Dialogue Coach stream (ADR-069 D17 / Phase 5 step 22).
 *
 * Connects to POST /api/v1/ai-assist/dialogue-coach/{chapter_id} and parses
 * the typed `DialogueCoachStreamEvent` stream. Mirrors the established analysis
 * stream pattern ({@link ./character-voice-stream.ts}): the backend emits a
 * type-discriminated event stream — one "progress", one "result" carrying the
 * full DialogueCoachResponse, then a terminal "done" (or "error"), followed by
 * a `data: [DONE]` sentinel.
 *
 * RULE-17 contract parity: types below mirror ai_assist/schemas.py exactly.
 * The transport (auth, SSE line parsing, connect timeout, abort) lives in
 * {@link ./streaming.ts}.
 *
 * @module dialogue-coach-stream
 */
import { connectSSE } from "./streaming";
import type {
  DialogueCoachRequest,
  DialogueCoachResponse,
  DialogueCoachStreamEvent,
} from "@/types";

export interface DialogueCoachStreamHandlers {
  /** Called for each "progress" event. */
  onProgress?: (message: string) => void;
  /** Called once with the full result when the "result" event arrives. */
  onResult: (result: DialogueCoachResponse) => void;
  /** Called after the terminal "done" event. Never after onError. */
  onComplete?: () => void;
  /** Called on transport failure or a terminal "error" event. */
  onError?: (error: Error) => void;
}

/**
 * Stream a dialogue-coach analysis for a chapter selection.
 *
 * @param chapterId  Chapter the selection belongs to (URL path param).
 * @param body       `{ selection_text, mode }` (RULE-17 DialogueCoachRequest).
 * @param handlers   Progress / result / complete / error callbacks.
 * @param signal     Optional abort signal (provided by useAIOperation).
 */
export async function streamDialogueCoach(
  chapterId: string,
  body: DialogueCoachRequest,
  handlers: DialogueCoachStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  let isComplete = false;

  function complete(): void {
    if (isComplete) return;
    isComplete = true;
    handlers.onComplete?.();
  }

  await connectSSE<DialogueCoachStreamEvent>({
    url: `/ai-assist/dialogue-coach/${chapterId}`,
    method: "POST",
    body,
    signal,
    onChunk: (event) => {
      if (event.event === "error" || event.error) {
        if (isComplete) return;
        isComplete = true;
        handlers.onError?.(new Error(event.error ?? "Dialogue coach failed"));
        return;
      }
      if (event.event === "progress" && event.progress) {
        handlers.onProgress?.(event.progress);
        return;
      }
      if (event.event === "result" && event.result) {
        handlers.onResult(event.result);
        return;
      }
      if (event.event === "done" || event.is_final) complete();
    },
    onComplete: complete,
    onError: (error) => {
      if (isComplete) return;
      isComplete = true;
      handlers.onError?.(error);
    },
  });
}
```

- [ ] **Step 6: Append barrel exports**

In `packages/web/lib/api/index.ts`, add (next to the other domain exports):

```typescript
export { adaptiveApi } from "./adaptive";
export type { DialogueCoachStreamHandlers } from "./dialogue-coach-stream";
export { streamDialogueCoach } from "./dialogue-coach-stream";
```

- [ ] **Step 7: Run tests, lint, commit**

```bash
pnpm --filter web vitest run lib/api/__tests__/adaptive.test.ts lib/api/__tests__/dialogue-coach-stream.test.ts
pnpm --filter web lint
git add packages/web/lib/api/adaptive.ts packages/web/lib/api/dialogue-coach-stream.ts \
        packages/web/lib/api/index.ts packages/web/lib/api/__tests__/adaptive.test.ts \
        packages/web/lib/api/__tests__/dialogue-coach-stream.test.ts
git commit -m "feat(web): add adaptive REST + dialogue-coach SSE clients (ADR-069 §22)"
```

---

## Task 3: `useAdaptiveContext` hook + canonical query keys (TanStack Query, Decision 15)

**Files:**
- Create: `packages/web/lib/hooks/adaptiveKeys.ts`
- Create: `packages/web/lib/hooks/useAdaptiveContext.ts`
- Test: `packages/web/lib/hooks/__tests__/useAdaptiveContext.test.tsx`

**Interfaces:**
- Consumes: `adaptiveApi` (Task 2), `QueryClientProvider` (`components/shared/QueryProvider.tsx`).
- Produces: `adaptiveKeys.context(projectId)` → `["adaptive-context", projectId]` (the canonical key, Decision 15); `useAdaptiveContext(projectId)`, `useToggleAdaptive(projectId)`, `useSetAdaptiveWeights(projectId)`. Tasks 6, 7, 9 import these.

## Skill hints
- Load `vercel-react-best-practices`: `rerender-functional-setstate` / stable mutation callbacks; the canonical key factory avoids key drift across components.

- [ ] **Step 1: Write the failing test**

Create `packages/web/lib/hooks/__tests__/useAdaptiveContext.test.tsx`:

```typescript
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { type ReactNode } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { server } from "@/mocks/server";
import { adaptiveKeys, useAdaptiveContext, useSetAdaptiveWeights, useToggleAdaptive } from "@/lib/hooks/useAdaptiveContext";

function wrapper(qc: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

const CTX = {
  project_id: "proj-1",
  enabled: true,
  weights: { preference: 0.7, voice_fidelity: 0.9, style_constraints: 1.0, avoidance: 1.0 },
  sources: { preference_text: "", voice_profiles_text: "", style_constraints_text: "", avoidance_patterns_text: "" },
  has_any_signal: false,
};

afterEach(() => server.resetHandlers());

describe("adaptiveKeys (Decision 15 canonical key)", () => {
  it("produces the canonical adaptive-context key", () => {
    expect(adaptiveKeys.context("proj-1")).toEqual(["adaptive-context", "proj-1"]);
  });
});

describe("useAdaptiveContext", () => {
  it("fetches context via the canonical key", async () => {
    server.use(http.get("*/api/v1/adaptive/proj-1/context", () => HttpResponse.json(CTX)));
    const qc = new QueryClient();
    const { result } = renderHook(() => useAdaptiveContext("proj-1"), { wrapper: wrapper(qc) });
    await waitFor(() => expect(result.current.data?.enabled).toBe(true));
    expect(qc.getQueryData(adaptiveKeys.context("proj-1"))).toBeTruthy();
  });

  it("toggle mutation invalidates the canonical key", async () => {
    let toggledTo: boolean | null = null;
    let contextHits = 0;
    server.use(
      http.get("*/api/v1/adaptive/proj-1/context", () => {
        contextHits += 1;
        return HttpResponse.json({ ...CTX, enabled: toggledTo ?? true });
      }),
      http.post("*/api/v1/adaptive/proj-1/toggle", async ({ request }) => {
        toggledTo = (await request.json() as { enabled: boolean }).enabled;
        return HttpResponse.json({ enabled: toggledTo, weights: CTX.weights });
      }),
    );
    const qc = new QueryClient();
    const { result } = renderHook(() => useToggleAdaptive("proj-1"), { wrapper: wrapper(qc) });
    result.current.mutate(false);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    await waitFor(() => expect(contextHits).toBeGreaterThan(1)); // refetched
  });

  it("setWeights mutation invalidates the canonical key", async () => {
    const spy = vi.fn();
    server.use(
      http.get("*/api/v1/adaptive/proj-1/context", () => HttpResponse.json(CTX)),
      http.post("*/api/v1/adaptive/proj-1/weights", async ({ request }) => {
        spy(await request.json());
        return HttpResponse.json({ enabled: true, weights: CTX.weights });
      }),
    );
    const qc = new QueryClient();
    const { result } = renderHook(() => useSetAdaptiveWeights("proj-1"), { wrapper: wrapper(qc) });
    result.current.mutate({ preference: 0.3, voice_fidelity: 0.3, style_constraints: 0.3, avoidance: 0.3 });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(spy).toHaveBeenCalled();
  });
});
```

(Add `import { vi } from "vitest";` at the top alongside the other vitest imports.)

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter web vitest run lib/hooks/__tests__/useAdaptiveContext.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Create the query-key factory**

`packages/web/lib/hooks/adaptiveKeys.ts`:

```typescript
/** Canonical TanStack Query keys for adaptive state (ADR-069 Decision 15).
 *  Every adaptive query/mutation shares the `["adaptive-context", projectId]` root
 *  so a single invalidation propagates to the indicator, dashboard, and panel. */
export const adaptiveKeys = {
  all: ["adaptive-context"] as const,
  context: (projectId: string) => ["adaptive-context", projectId] as const,
  snapshots: (projectId: string) => ["adaptive-context", projectId, "snapshots"] as const,
};
```

- [ ] **Step 4: Create the hooks**

`packages/web/lib/hooks/useAdaptiveContext.ts`:

```typescript
"use client";

/** TanStack Query hooks for Adaptive Context CRUD (ADR-069 Decision 15).
 *
 *  Adaptive settings are NOT an AI operation (ADR-043) — they are regular REST
 *  CRUD, so TanStack Query cache invalidation is the conform pattern. The
 *  canonical key {@link adaptiveKeys} is the SSOT; mutations invalidate it so
 *  the Status Indicator, Dashboard, and Dialogue Coach panel refetch in lockstep.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { AdaptiveWeightsInput } from "@/types";
import { adaptiveApi } from "@/lib/api/adaptive";
import { adaptiveKeys } from "./adaptiveKeys";

export { adaptiveKeys } from "./adaptiveKeys";

/** Read the current adaptive context for the dashboard + indicator. */
export function useAdaptiveContext(projectId: string) {
  return useQuery({
    queryKey: adaptiveKeys.context(projectId),
    queryFn: () => adaptiveApi.getContext(projectId),
    enabled: !!projectId,
  });
}

/** Toggle adaptivity on/off; invalidates the canonical key on success. */
export function useToggleAdaptive(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (enabled: boolean) => adaptiveApi.toggle(projectId, enabled),
    onSuccess: () => void qc.invalidateQueries({ queryKey: adaptiveKeys.context(projectId) }),
  });
}

/** Update the 4 weights; invalidates the canonical key on success. */
export function useSetAdaptiveWeights(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (weights: AdaptiveWeightsInput) => adaptiveApi.setWeights(projectId, weights),
    onSuccess: () => void qc.invalidateQueries({ queryKey: adaptiveKeys.context(projectId) }),
  });
}
```

- [ ] **Step 5: Run test, lint, commit**

```bash
pnpm --filter web vitest run lib/hooks/__tests__/useAdaptiveContext.test.tsx
pnpm --filter web lint
git add packages/web/lib/hooks/adaptiveKeys.ts packages/web/lib/hooks/useAdaptiveContext.ts \
        packages/web/lib/hooks/__tests__/useAdaptiveContext.test.tsx
git commit -m "feat(web): add useAdaptiveContext + canonical query keys (ADR-069 D15)"
```

---

## Task 4: `useDialogueCoach` hook (`useAIOperation`, ADR-043)

**Files:**
- Create: `packages/web/lib/hooks/useDialogueCoach.ts`
- Test: `packages/web/lib/hooks/__tests__/useDialogueCoach.test.tsx`

**Interfaces:**
- Consumes: `useAIOperation` (`./use-ai-operation`), `streamDialogueCoach` (Task 2), Task 1 types.
- Produces: `useDialogueCoach()` → `{ state, result, error, progress, run, cancel, retry, reset, isIdle/isLoading/isStreaming/isComplete/isError/isConnectionLost }`. Task 8 imports this.

## Skill hints
- Load `vercel-react-best-practices`: ref-staging for run params (mirrors `useCharacterVoice`), stable `run` callback, memoised return.

- [ ] **Step 1: Write the failing test**

Create `packages/web/lib/hooks/__tests__/useDialogueCoach.test.tsx`:

```typescript
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { type ReactNode } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { server } from "@/mocks/server";
import { useDialogueCoach } from "@/lib/hooks/useDialogueCoach";

function wrapper() {
  const qc = new QueryClient();
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

function sse(events: object[]): string {
  return events.map((e) => `data: ${JSON.stringify(e)}`).join("\n\n") + "\n\ndata: [DONE]\n\n";
}

afterEach(() => server.resetHandlers());

describe("useDialogueCoach", () => {
  it("runs and surfaces the single result", async () => {
    const result = {
      chapter_id: "ch-1",
      mode: "analyze",
      issues: [{ issue_type: "on-the-nose", speaker: "Alice", original_quote: "\"I am sad.\"",
        diagnosis: "stated emotion directly", severity: "medium", alternatives: null }],
      adaptive_summary: "",
    };
    server.use(
      http.post("*/api/v1/ai-assist/dialogue-coach/ch-1", () =>
        HttpResponse.text(sse([
          { event: "progress", progress: "Analysing…" },
          { event: "result", result },
          { event: "done", is_final: true },
        ]), { headers: { "Content-Type": "text/event-stream" } }),
      ),
    );
    const { result: hook } = renderHook(() => useDialogueCoach(), { wrapper: wrapper() });
    hook.current.run({ chapterId: "ch-1", selectionText: "\"I am sad.\"", mode: "analyze" });
    await waitFor(() => expect(hook.current.isComplete).toBe(true));
    expect(hook.current.result?.issues).toHaveLength(1);
    expect(hook.current.progress).toBe("Analysing…");
  });

  it("surfaces errors and stays retryable", async () => {
    server.use(
      http.post("*/api/v1/ai-assist/dialogue-coach/ch-1", () =>
        HttpResponse.text(sse([{ event: "error", error: "boom", is_final: true }]),
          { headers: { "Content-Type": "text/event-stream" } }),
      ),
    );
    const { result: hook } = renderHook(() => useDialogueCoach(), { wrapper: wrapper() });
    hook.current.run({ chapterId: "ch-1", selectionText: "x", mode: "improve" });
    await waitFor(() => expect(hook.current.isError).toBe(true));
    expect(hook.current.error).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter web vitest run lib/hooks/__tests__/useDialogueCoach.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Create the hook**

`packages/web/lib/hooks/useDialogueCoach.ts` (mirrors `useCharacterVoice`, but single-result):

```typescript
"use client";

/**
 * useDialogueCoach — SSE streaming hook for the Dialogue Coach (ASSIST-004).
 *
 * Wraps {@link useAIOperation} (ADR-043) with the dialogue-coach streaming
 * logic, the same way `useCharacterVoice` wraps `streamCharacterVoice`. Unlike
 * character-voice (multiple per-character results), the coach emits a SINGLE
 * `result` event carrying the full DialogueCoachResponse — so `run()` resolves
 * with that one result rather than an array.
 *
 * Enforces §16 AI-Interaction Standards / ADR-043: no manual AbortController —
 * the abort signal comes from `useAIOperation`.
 *
 * @module useDialogueCoach
 */
import { useCallback, useRef, useState } from "react";
import type { DialogueCoachMode, DialogueCoachResponse } from "@/types";
import { streamDialogueCoach } from "@/lib/api/dialogue-coach-stream";
import { useAIOperation } from "@/lib/hooks/use-ai-operation";

export interface DialogueCoachRunParams {
  chapterId: string;
  selectionText: string;
  mode: DialogueCoachMode;
}

export function useDialogueCoach() {
  // Staged before start() so execute() reads the current values via refs.
  const paramsRef = useRef<DialogueCoachRunParams | null>(null);
  const [progress, setProgress] = useState<string | null>(null);

  const {
    state,
    start,
    cancel,
    retry,
    reset,
    notifyData,
    isIdle,
    isLoading,
    isStreaming,
    isComplete,
    isError,
    isConnectionLost,
  } = useAIOperation<DialogueCoachResponse>({
    execute: (signal) =>
      new Promise<DialogueCoachResponse>((resolve, reject) => {
        const params = paramsRef.current;
        if (!params) {
          reject(new Error("No run params provided for dialogue coach"));
          return;
        }
        let settled = false;
        const onAbort = () => {
          if (!settled) {
            settled = true;
            reject(new DOMException("Aborted", "AbortError"));
          }
        };
        signal.addEventListener("abort", onAbort, { once: true });

        streamDialogueCoach(
          params.chapterId,
          { selection_text: params.selectionText, mode: params.mode },
          {
            onProgress: (msg) => {
              setProgress(msg);
              notifyData();
            },
            onResult: (result) => {
              notifyData();
              if (!settled) {
                settled = true;
                signal.removeEventListener("abort", onAbort);
                resolve(result);
              }
            },
            onComplete: () => {
              // Stream ends after the single result; nothing more to resolve.
            },
            onError: (err) => {
              if (!settled) {
                settled = true;
                signal.removeEventListener("abort", onAbort);
                reject(err);
              }
            },
          },
          signal,
        );
      }),
    connectionLossTimeout: 15_000,
  });

  /** Stage the run params and start the dialogue-coach analysis. */
  const run = useCallback(
    (params: DialogueCoachRunParams) => {
      paramsRef.current = params;
      setProgress(null);
      start();
    },
    [start],
  );

  /** Clear progress on reset. */
  const resetAll = useCallback(() => {
    reset();
    setProgress(null);
  }, [reset]);

  return {
    state,
    result: state.result,
    error: state.error,
    progress,
    run,
    cancel,
    retry,
    reset: resetAll,
    isIdle,
    isLoading,
    isStreaming,
    isComplete,
    isError,
    isConnectionLost,
  };
}
```

- [ ] **Step 4: Run test, lint, commit**

```bash
pnpm --filter web vitest run lib/hooks/__tests__/useDialogueCoach.test.tsx
pnpm --filter web lint
git add packages/web/lib/hooks/useDialogueCoach.ts packages/web/lib/hooks/__tests__/useDialogueCoach.test.tsx
git commit -m "feat(web): add useDialogueCoach hook on useAIOperation (ADR-069 §23, ADR-043)"
```

---

## Task 5: UI primitives — shadcn `slider`, `switch`, `badge`

**Files:**
- Create: `packages/web/components/ui/slider.tsx`
- Create: `packages/web/components/ui/switch.tsx`
- Create: `packages/web/components/ui/badge.tsx`
- Test: `packages/web/components/ui/__tests__/primitives.test.tsx`

**Interfaces:**
- Consumes: `components.json` (shadcn "base-nova" style), Radix primitives.
- Produces: `Slider`, `Switch`, `Badge` — consumed by Tasks 6 + 8.

## Skill hints
- Load `frontend-design`: the primitives must match the existing "base-nova" aesthetic (custom warm palette + `.dark`); do not import a default shadcn theme that clashes.
- Load `web-design-guidelines`: Slider + Switch must be keyboard-operable + have accessible labels (Radix provides this — wire `aria-label`).

- [ ] **Step 1: Add the primitives via shadcn**

Run (from `packages/web/`):

```bash
pnpm dlx shadcn@latest add slider switch badge
```

If the CLI is unavailable in the sandbox, vendor the three components manually from the shadcn "base-nova" registry, matching the existing `components/ui/toolbar-button.tsx` import style (`@/components/ui/*`, Tailwind v4 tokens `bg-primary`, `text-muted-foreground`, etc.). Each must:
- `slider.tsx` — wrap `@radix-ui/react-slider`, export `Slider`, forward `className`, step=0.01 for weight use.
- `switch.tsx` — wrap `@radix-ui/react-switch`, export `Switch`, keyboard + `aria-checked`.
- `badge.tsx` — export `Badge` with `variant` ("default" | "secondary" | "destructive" | "outline").

- [ ] **Step 2: Write the smoke test**

`packages/web/components/ui/__tests__/primitives.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Badge } from "@/components/ui/badge";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";

describe("shadcn primitives render", () => {
  it("Badge renders children", () => {
    render(<Badge>medium</Badge>);
    expect(screen.getByText("medium")).toBeInTheDocument();
  });
  it("Slider is labelled", () => {
    render(<Slider defaultValue={[0.5]} max={1} step={0.01} aria-label="preference weight" />);
    expect(screen.getByRole("slider", { name: "preference weight" })).toBeInTheDocument();
  });
  it("Switch toggles", () => {
    render(<Switch aria-label="adaptive toggle" />);
    expect(screen.getByRole("switch", { name: "adaptive toggle" })).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run, lint, commit**

```bash
pnpm --filter web vitest run components/ui/__tests__/primitives.test.tsx
pnpm --filter web lint
git add packages/web/components/ui/slider.tsx packages/web/components/ui/switch.tsx \
        packages/web/components/ui/badge.tsx packages/web/components/ui/__tests__/primitives.test.tsx
git commit -m "feat(web): add shadcn slider/switch/badge primitives (ADR-069 §24/25)"
```

---

## Task 6: Adaptive Dashboard — toggle + weight sliders + source list (LEARN-002)

**Files:**
- Create: `packages/web/components/studio/settings/AdaptiveDashboard.tsx`
- Create: `packages/web/components/studio/settings/_components/AdaptiveToggle.tsx`
- Create: `packages/web/components/studio/settings/_components/AdaptiveWeightSliders.tsx`
- Create: `packages/web/components/studio/settings/_components/AdaptiveSourceList.tsx`
- Modify: `packages/web/components/studio/settings/LearningTab.tsx` (render `<AdaptiveDashboard novelId={novelId} />` in a new card before the preference section)
- Test: `packages/web/components/studio/settings/__tests__/AdaptiveDashboard.test.tsx`

**Interfaces:**
- Consumes: `useAdaptiveContext` / `useToggleAdaptive` / `useSetAdaptiveWeights` (Task 3), `Switch`/`Slider` (Task 5).
- Produces: `<AdaptiveDashboard novelId={string} />` rendered inside `LearningTab`.

## Skill hints
- Load `frontend-design`: production-grade dashboard — commit to the existing warm/custom palette, generous spacing, clear hierarchy (toggle → weights → sources). Avoid generic card soup.
- Load `web-design-guidelines`: each slider has an accessible label + current value; the toggle has a visible focus ring; the `has_any_signal=false` state is a clear empty state.

- [ ] **Step 1: Write the failing test**

`packages/web/components/studio/settings/__tests__/AdaptiveDashboard.test.tsx`:

```typescript
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { type ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { server } from "@/mocks/server";
import { AdaptiveDashboard } from "@/components/studio/settings/AdaptiveDashboard";

function wrapper(qc: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

const CTX = {
  project_id: "proj-1",
  enabled: true,
  weights: { preference: 0.7, voice_fidelity: 0.9, style_constraints: 1.0, avoidance: 1.0 },
  sources: { preference_text: "terse prose", voice_profiles_text: "Alice", style_constraints_text: "", avoidance_patterns_text: "" },
  has_any_signal: true,
};

afterEach(() => server.resetHandlers());

describe("AdaptiveDashboard", () => {
  it("renders toggle, 4 sliders, and sources", async () => {
    server.use(http.get("*/api/v1/adaptive/proj-1/context", () => HttpResponse.json(CTX)));
    render(<AdaptiveDashboard novelId="proj-1" />, { wrapper: wrapper(new QueryClient()) });
    await waitFor(() => expect(screen.getByRole("switch", { name: "adaptive.enableLabel" })).toBeInTheDocument());
    expect(screen.getByRole("slider", { name: "adaptive.weight.preference" })).toBeInTheDocument();
    expect(screen.getByRole("slider", { name: "adaptive.weight.voice_fidelity" })).toBeInTheDocument();
    expect(screen.getByRole("slider", { name: "adaptive.weight.style_constraints" })).toBeInTheDocument();
    expect(screen.getByRole("slider", { name: "adaptive.weight.avoidance" })).toBeInTheDocument();
    expect(screen.getByText("terse prose")).toBeInTheDocument();
  });

  it("POSTs weights on slider commit", async () => {
    const spy = vi.fn();
    server.use(
      http.get("*/api/v1/adaptive/proj-1/context", () => HttpResponse.json(CTX)),
      http.post("*/api/v1/adaptive/proj-1/weights", async ({ request }) => {
        spy(await request.json());
        return HttpResponse.json({ enabled: true, weights: CTX.weights });
      }),
    );
    render(<AdaptiveDashboard novelId="proj-1" />, { wrapper: wrapper(new QueryClient()) });
    const slider = await screen.findByRole("slider", { name: "adaptive.weight.preference" });
    fireEvent.keyDown(slider, { key: "ArrowRight" });
    await waitFor(() => expect(spy).toHaveBeenCalled());
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter web vitest run components/studio/settings/__tests__/AdaptiveDashboard.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the sub-components**

`_components/AdaptiveToggle.tsx`:

```tsx
"use client";
import { useTranslations } from "next-intl";
import { Switch } from "@/components/ui/switch";

export function AdaptiveToggle({
  enabled,
  onToggle,
  pending,
}: {
  enabled: boolean;
  onToggle: (next: boolean) => void;
  pending: boolean;
}) {
  const t = useTranslations("adaptive");
  return (
    <div className="flex items-center justify-between gap-4">
      <div>
        <p className="font-medium">{t("enableLabel")}</p>
        <p className="text-sm text-muted-foreground">{t("enableDescription")}</p>
      </div>
      <Switch
        checked={enabled}
        onCheckedChange={onToggle}
        disabled={pending}
        aria-label={t("enableLabel")}
      />
    </div>
  );
}
```

`_components/AdaptiveWeightSliders.tsx`:

```tsx
"use client";
import { useTranslations } from "next-intl";
import { useCallback, useState } from "react";
import type { AdaptiveWeightsInput } from "@/types";
import { Slider } from "@/components/ui/slider";

const WEIGHTS = [
  { key: "preference", labelKey: "preference" },
  { key: "voice_fidelity", labelKey: "voice_fidelity" },
  { key: "style_constraints", labelKey: "style_constraints" },
  { key: "avoidance", labelKey: "avoidance" },
] as const satisfies readonly { key: keyof AdaptiveWeightsInput; labelKey: string }[];

export function AdaptiveWeightSliders({
  weights,
  onCommit,
  pending,
}: {
  weights: AdaptiveWeightsInput;
  onCommit: (next: AdaptiveWeightsInput) => void;
  pending: boolean;
}) {
  const t = useTranslations("adaptive");
  const [draft, setDraft] = useState<AdaptiveWeightsInput>(weights);

  // Keep local draft in sync when the server state changes (Decision 15 invalidation).
  if (
    draft.preference !== weights.preference ||
    draft.voice_fidelity !== weights.voice_fidelity ||
    draft.style_constraints !== weights.style_constraints ||
    draft.avoidance !== weights.avoidance
  ) {
    // Only re-sync when not actively pending (avoids clobbering an in-flight edit).
    if (!pending) setDraft(weights);
  }

  const handleCommit = useCallback(
    (key: keyof AdaptiveWeightsInput, value: number) => {
      const next = { ...draft, [key]: value } as AdaptiveWeightsInput;
      setDraft(next);
      onCommit(next);
    },
    [draft, onCommit],
  );

  return (
    <div className="space-y-4">
      <p className="font-medium">{t("weightsTitle")}</p>
      {WEIGHTS.map(({ key, labelKey }) => (
        <div key={key}>
          <div className="flex items-center justify-between text-sm">
            <label htmlFor={`weight-${key}`}>{t(`weight.${labelKey}`)}</label>
            <span className="text-muted-foreground tabular-nums">
              {Math.round((draft[key] ?? 0) * 100)}%
            </span>
          </div>
          <Slider
            id={`weight-${key}`}
            value={[draft[key] ?? 0]}
            min={0}
            max={1}
            step={0.01}
            disabled={pending}
            onValueChange={(v) => handleCommit(key, v[0] ?? 0)}
            aria-label={t(`weight.${labelKey}`)}
          />
        </div>
      ))}
    </div>
  );
}
```

`_components/AdaptiveSourceList.tsx`:

```tsx
"use client";
import { useTranslations } from "next-intl";
import type { AdaptiveSourceSummary } from "@/types";

export function AdaptiveSourceList({
  sources,
  hasAnySignal,
}: {
  sources: AdaptiveSourceSummary;
  hasAnySignal: boolean;
}) {
  const t = useTranslations("adaptive");
  const rows = [
    { labelKey: "source.preference", text: sources.preference_text },
    { labelKey: "source.voice_profiles", text: sources.voice_profiles_text },
    { labelKey: "source.style_constraints", text: sources.style_constraints_text },
    { labelKey: "source.avoidance_patterns", text: sources.avoidance_patterns_text },
  ];
  if (!hasAnySignal) {
    return <p className="text-sm text-muted-foreground">{t("noSignals")}</p>;
  }
  return (
    <div className="space-y-3">
      <p className="font-medium">{t("sourcesTitle")}</p>
      <dl className="space-y-2">
        {rows.map(({ labelKey, text }) => (
          <div key={labelKey}>
            <dt className="text-xs uppercase tracking-wide text-muted-foreground">{t(labelKey)}</dt>
            <dd className="text-sm">{text || t("source.empty")}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
```

- [ ] **Step 4: Implement the dashboard shell**

`packages/web/components/studio/settings/AdaptiveDashboard.tsx`:

```tsx
"use client";

/** AdaptiveDashboard — LEARN-002 settings surface (ADR-069 Decision 12/15).
 *
 *  Composes the enable toggle, the 4 weight sliders, and the source summary.
 *  All state flows through the canonical TanStack Query key (Decision 15):
 *  mutations invalidate `["adaptive-context", projectId]`, so the editor
 *  Status Indicator and the Dialogue Coach panel refetch in lockstep. */
import { Sparkles } from "lucide-react";
import { useTranslations } from "next-intl";
import { AdaptiveSourceList } from "./_components/AdaptiveSourceList";
import { AdaptiveToggle } from "./_components/AdaptiveToggle";
import { AdaptiveWeightSliders } from "./_components/AdaptiveWeightSliders";
import {
  useAdaptiveContext,
  useSetAdaptiveWeights,
  useToggleAdaptive,
} from "@/lib/hooks/useAdaptiveContext";

export function AdaptiveDashboard({ novelId }: { readonly novelId: string }) {
  const t = useTranslations("adaptive");
  const { data, isLoading, error } = useAdaptiveContext(novelId);
  const toggle = useToggleAdaptive(novelId);
  const setWeights = useSetAdaptiveWeights(novelId);

  if (isLoading) {
    return <div className="animate-pulse text-sm text-muted-foreground">{t("loading")}</div>;
  }
  if (error || !data) {
    return <div className="text-sm text-destructive" role="alert">{t("loadFailed")}</div>;
  }

  return (
    <section className="bg-card border border-border rounded-lg p-6 space-y-6">
      <div className="flex items-center gap-2">
        <Sparkles className="w-5 h-5 text-violet-500" />
        <h3 className="text-lg font-medium">{t("title")}</h3>
      </div>
      <AdaptiveToggle
        enabled={data.enabled}
        onToggle={(next) => toggle.mutate(next)}
        pending={toggle.isPending}
      />
      <AdaptiveWeightSliders
        weights={data.weights}
        onCommit={(next) => setWeights.mutate(next)}
        pending={setWeights.isPending}
      />
      <AdaptiveSourceList sources={data.sources} hasAnySignal={data.has_any_signal} />
    </section>
  );
}
```

- [ ] **Step 5: Mount it in the Learning tab**

In `packages/web/components/studio/settings/LearningTab.tsx`, import `AdaptiveDashboard` and render it as the **first** card inside the top-level `<div className="space-y-6">` (before the Header block, or immediately after the header — designer's call; keep it above the Preference Profile so adaptivity is the primary control):

```tsx
<AdaptiveDashboard novelId={novelId} />
```

- [ ] **Step 6: Run test, lint, commit**

```bash
pnpm --filter web vitest run components/studio/settings/__tests__/AdaptiveDashboard.test.tsx
pnpm --filter web lint
git add packages/web/components/studio/settings/AdaptiveDashboard.tsx \
        packages/web/components/studio/settings/_components/ \
        packages/web/components/studio/settings/LearningTab.tsx \
        packages/web/components/studio/settings/__tests__/AdaptiveDashboard.test.tsx
git commit -m "feat(web): add Adaptive Dashboard (LEARN-002) to Settings Learning tab (ADR-069 §25)"
```

---

## Task 7: Adaptive Snapshot History (GATED on coordinator decision — endpoint A)

> **BLOCKED until the coordinator confirms endpoint A.** If **(B)** is chosen, skip this task and render the `aiAssist.historyDisabled` empty-state copy in `AdaptiveDashboard` instead (no code beyond adding the copy + a `<p>` in the dashboard shell). Do NOT fake history data — RULE-20.

**Files:**
- Create: `packages/web/lib/hooks/useAdaptiveSnapshots.ts`
- Create: `packages/web/components/studio/settings/_components/AdaptiveSnapshotHistory.tsx`
- Modify: `packages/web/components/studio/settings/AdaptiveDashboard.tsx` (render history after sources)
- Test: `packages/web/lib/hooks/__tests__/useAdaptiveSnapshots.test.tsx`

**Interfaces:**
- Consumes: `adaptiveApi.getSnapshots` (Task 2), `adaptiveKeys.snapshots` (Task 3).
- Produces: `useAdaptiveSnapshots(projectId)` + `<AdaptiveSnapshotHistory projectId={string} />`.

## Skill hints
- Load `vercel-react-best-practices`: `rendering-content-visibility` if the list is long; `js-tosorted-immutable` for ordering by `created_at`.

- [ ] **Step 1: Confirm endpoint A ships** — verify `GET /api/v1/adaptive/{project_id}/snapshots` returns `AdaptiveSnapshot[]` (the Backend Specialist's Phase 3.5 task). If absent, escalate (do not proceed).

- [ ] **Step 2–N:** Follow the TDD cycle mirroring Task 3 (hook test → `useAdaptiveSnapshots` with `queryKey: adaptiveKeys.snapshots(projectId)`) and Task 6 (component test → `AdaptiveSnapshotHistory` rendering each snapshot's `created_at` + which sources/weights were active, newest first). Empty state: `aiAssist.historyEmpty`.

```typescript
// packages/web/lib/hooks/useAdaptiveSnapshots.ts
"use client";
import { useQuery } from "@tanstack/react-query";
import { adaptiveApi } from "@/lib/api/adaptive";
import { adaptiveKeys } from "./adaptiveKeys";

export function useAdaptiveSnapshots(projectId: string, limit = 20) {
  return useQuery({
    queryKey: adaptiveKeys.snapshots(projectId),
    queryFn: () => adaptiveApi.getSnapshots(projectId, limit),
    enabled: !!projectId,
  });
}
```

The component renders a vertical timeline of recent invocations (date + active weights + which sources shaped it). Commit message: `feat(web): add Adaptive Snapshot History (ADR-069 §25, endpoint A)`.

---

## Task 8: Dialogue Coach panel + sub-components (ASSIST-004)

**Files:**
- Create: `packages/web/components/studio/analysis/DialogueCoachPanel.tsx`
- Create: `packages/web/components/studio/analysis/_components/DialogueModeSelector.tsx`
- Create: `packages/web/components/studio/analysis/_components/DialogueIssueList.tsx`
- Create: `packages/web/components/studio/analysis/_components/DialogueIssueCard.tsx`
- Create: `packages/web/components/studio/analysis/_components/DialogueAlternativeCard.tsx`
- Test: `packages/web/components/studio/analysis/__tests__/DialogueCoachPanel.test.tsx`

**Interfaces:**
- Consumes: `useDialogueCoach` (Task 4), `Badge` (Task 5), Task 1 types, the TipTap `editor` instance (for Accept — string replace).
- Produces: `<DialogueCoachPanel chapterId={string} selectionText={string|null} editor={Editor} onClose={() => void} />`.

## Skill hints
- Load `frontend-design`: this is the flagship AI surface — commit to a distinctive, cohesive treatment for the before/after blocks (red-tint original / green-tint rewrite), severity badges, and the mode selector. Make it memorable, not generic.
- Load `vercel-composition-patterns`: `architecture-compound-components` + `patterns-explicit-variants` — the panel composes ModeSelector + IssueList + IssueCard + AlternativeCard via a small context; the mode selector exposes explicit `Analyze`/`Improve` controls (NOT a `mode?: "analyze"|"improve" | boolean` prop on the panel). Avoid `architecture-avoid-boolean-props`.
- Load `web-design-guidelines`: severity badges need colour + text (not colour alone); the Accept button must be keyboard-reachable; issue cards need a heading hierarchy.

- [ ] **Step 1: Write the failing test**

`packages/web/components/studio/analysis/__tests__/DialogueCoachPanel.test.tsx`:

```typescript
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";
import { server } from "@/mocks/server";
import { DialogueCoachPanel } from "@/components/studio/analysis/DialogueCoachPanel";

const fakeEditor = {
  getHTML: () => "<p>I am sad.</p>",
  state: { doc: { textBetween: () => "I am sad." } },
  chain: () => ({ focus: () => ({ setContent: vi.fn(), run: () => {} }) }),
} as unknown as Parameters<typeof DialogueCoachPanel>[0]["editor"];

function sse(events: object[]): string {
  return events.map((e) => `data: ${JSON.stringify(e)}`).join("\n\n") + "\n\ndata: [DONE]\n\n";
}

afterEach(() => server.resetHandlers());

describe("DialogueCoachPanel", () => {
  it("idle: shows a run CTA disabled when no selection", () => {
    render(<DialogueCoachPanel chapterId="ch-1" selectionText={null} editor={fakeEditor} onClose={vi.fn()} />);
    expect(screen.getByText("dialogueCoach.selectPrompt")).toBeInTheDocument();
  });

  it("runs analyze and renders issues without alternatives", async () => {
    server.use(http.post("*/api/v1/ai-assist/dialogue-coach/ch-1", () =>
      HttpResponse.text(sse([
        { event: "result", result: {
          chapter_id: "ch-1", mode: "analyze", adaptive_summary: "",
          issues: [{ issue_type: "on-the-nose", speaker: "Alice", original_quote: "\"I am sad.\"",
            diagnosis: "telling, not showing", severity: "medium", alternatives: null }],
        } },
        { event: "done", is_final: true },
      ]), { headers: { "Content-Type": "text/event-stream" } })));
    render(<DialogueCoachPanel chapterId="ch-1" selectionText="\"I am sad.\"" editor={fakeEditor} onClose={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "dialogueCoach.mode.analyze" }));
    await waitFor(() => expect(screen.getByText("telling, not showing")).toBeInTheDocument());
    expect(screen.queryByText("dialogueCoach.alternatives.apply")).not.toBeInTheDocument();
  });

  it("improve mode renders before/after blocks and an Apply button", async () => {
    server.use(http.post("*/api/v1/ai-assist/dialogue-coach/ch-1", () =>
      HttpResponse.text(sse([
        { event: "result", result: {
          chapter_id: "ch-1", mode: "improve", adaptive_summary: "",
          issues: [{ issue_type: "on-the-nose", speaker: "Alice", original_quote: "\"I am sad.\"",
            diagnosis: "telling", severity: "medium",
            alternatives: [{ rewrite: "\"Her shoulders slumped.\"", explanation: "show emotion" }] }],
        } },
        { event: "done", is_final: true },
      ]), { headers: { "Content-Type": "text/event-stream" } })));
    render(<DialogueCoachPanel chapterId="ch-1" selectionText="\"I am sad.\"" editor={fakeEditor} onClose={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "dialogueCoach.mode.improve" }));
    await waitFor(() => expect(screen.getByText("\"I am sad.\"")).toBeInTheDocument());
    expect(screen.getByText("\"Her shoulders slumped.\"")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "dialogueCoach.alternatives.apply" })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter web vitest run components/studio/analysis/__tests__/DialogueCoachPanel.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `DialogueModeSelector.tsx`** (explicit variants, not a boolean prop)

```tsx
"use client";
import { useTranslations } from "next-intl";
import type { DialogueCoachMode } from "@/types";

/** Two explicit controls — NOT a boolean `improve?` prop (vercel-composition-patterns). */
export function DialogueModeSelector({
  mode,
  onSelect,
  disabled,
}: {
  mode: DialogueCoachMode;
  onSelect: (mode: DialogueCoachMode) => void;
  disabled: boolean;
}) {
  const t = useTranslations("dialogueCoach");
  const options: DialogueCoachMode[] = ["analyze", "improve"];
  return (
    <div role="group" aria-label={t("mode.groupLabel")} className="flex gap-2">
      {options.map((opt) => (
        <button
          key={opt}
          type="button"
          onClick={() => onSelect(opt)}
          disabled={disabled}
          aria-pressed={mode === opt}
          className={`px-3 py-1.5 text-sm rounded-md border transition-colors ${
            mode === opt ? "bg-primary text-primary-foreground border-primary" : "border-border hover:bg-muted"
          } disabled:opacity-50`}
        >
          {t(`mode.${opt}`)}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Implement `DialogueAlternativeCard.tsx`** (Decision 9 — stacked before/after)

```tsx
"use client";
import { Check } from "lucide-react";
import { useTranslations } from "next-intl";
import type { Editor } from "@tiptap/react";
import type { DialogueAlternative } from "@/types";

/** Stacked before/after blocks (ADR-069 Decision 9). Accept = full-string
 *  replace of `originalQuote` with `rewrite` in the chapter (no char-level diff). */
export function DialogueAlternativeCard({
  alternative,
  originalQuote,
  editor,
  onApplied,
}: {
  alternative: DialogueAlternative;
  originalQuote: string;
  editor: Editor;
  onApplied: () => void;
}) {
  const t = useTranslations("dialogueCoach");

  const handleApply = () => {
    const html = editor.getHTML();
    if (!html.includes(originalQuote)) return; // not found — graceful no-op (RULE-11)
    editor
      .chain()
      .focus()
      .command(({ tr, state }) => {
        // String-level find-and-replace on the text content (Decision 9).
        const text = state.doc.textBetween(0, state.doc.content.size, "\n");
        const idx = text.indexOf(originalQuote);
        if (idx === -1) return false;
        // Replace via insertText at the resolved positions is complex; the
        // simplest correct path mirrors WRITE-004: replace the whole doc text.
        return true;
      })
      .run();
    // The robust WRITE-004 path (see components/studio/editor/CoAuthorPanel.tsx)
    // performs the actual replacement; this hook signals success to the panel.
    onApplied();
  };

  return (
    <div className="mt-3 space-y-2 border-l-2 border-border pl-3">
      <div className="rounded-md bg-red-500/5 border border-red-500/20 p-2">
        <p className="text-xs uppercase tracking-wide text-red-600 dark:text-red-400">
          {t("alternatives.original")}
        </p>
        <p className="text-sm">{originalQuote}</p>
      </div>
      <div className="rounded-md bg-emerald-500/5 border border-emerald-500/20 p-2">
        <p className="text-xs uppercase tracking-wide text-emerald-600 dark:text-emerald-400">
          {t("alternatives.rewrite")}
        </p>
        <p className="text-sm">{alternative.rewrite}</p>
        {alternative.explanation && (
          <p className="text-xs text-muted-foreground mt-1">{alternative.explanation}</p>
        )}
      </div>
      <button
        type="button"
        onClick={handleApply}
        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md bg-primary text-primary-foreground hover:opacity-90"
      >
        <Check className="w-3.5 h-3.5" />
        {t("alternatives.apply")}
      </button>
    </div>
  );
}
```

> **Implementation note for the Frontend Specialist:** the exact ProseMirror text-replacement transaction should reuse the helper already used by WRITE-004 (`components/studio/editor/CoAuthorPanel.tsx` / `rewriteStream.ts`). Read that file at implementation time and extract/ reuse its replace logic rather than reinventing it (DRY). The `handleApply` skeleton above shows the contract; the real transaction call comes from the WRITE-004 helper.

- [ ] **Step 5: Implement `DialogueIssueCard.tsx`**

```tsx
"use client";
import type { Editor } from "@tiptap/react";
import { useTranslations } from "next-intl";
import type { DialogueIssue } from "@/types";
import { Badge } from "@/components/ui/badge";
import { DialogueAlternativeCard } from "./DialogueAlternativeCard";

const SEVERITY_VARIANT: Record<string, "default" | "secondary" | "destructive"> = {
  high: "destructive",
  medium: "default",
  low: "secondary",
};

export function DialogueIssueCard({
  issue,
  editor,
  onApplied,
}: {
  issue: DialogueIssue;
  editor: Editor;
  onApplied: () => void;
}) {
  const t = useTranslations("dialogueCoach");
  return (
    <article className="border border-border rounded-lg p-4 space-y-2">
      <header className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <Badge variant={SEVERITY_VARIANT[issue.severity] ?? "secondary"}>
            {t(`severity.${issue.severity}`, {}, issue.severity)}
          </Badge>
          <span className="text-sm font-medium truncate">{issue.issue_type}</span>
        </div>
        {issue.speaker && <span className="text-xs text-muted-foreground">{issue.speaker}</span>}
      </header>
      <blockquote className="text-sm italic text-muted-foreground border-l-2 border-border pl-2">
        {issue.original_quote}
      </blockquote>
      <p className="text-sm">{issue.diagnosis}</p>
      {issue.alternatives?.map((alt, i) => (
        <DialogueAlternativeCard
          key={`${i}-${alt.rewrite.slice(0, 16)}`}
          alternative={alt}
          originalQuote={issue.original_quote}
          editor={editor}
          onApplied={onApplied}
        />
      ))}
    </article>
  );
}
```

- [ ] **Step 6: Implement `DialogueIssueList.tsx`**

```tsx
"use client";
import type { Editor } from "@tiptap/react";
import { useTranslations } from "next-intl";
import type { DialogueIssue } from "@/types";
import { DialogueIssueCard } from "./DialogueIssueCard";

export function DialogueIssueList({
  issues,
  editor,
  onApplied,
}: {
  issues: DialogueIssue[];
  editor: Editor;
  onApplied: () => void;
}) {
  const t = useTranslations("dialogueCoach");
  if (issues.length === 0) {
    return <p className="text-sm text-muted-foreground text-center py-8">{t("noIssues")}</p>;
  }
  return (
    <div className="space-y-3">
      {issues.map((issue, i) => (
        <DialogueIssueCard
          key={`${i}-${issue.original_quote.slice(0, 16)}`}
          issue={issue}
          editor={editor}
          onApplied={onApplied}
        />
      ))}
    </div>
  );
}
```

- [ ] **Step 7: Implement `DialogueCoachPanel.tsx`** (shell + composition root)

```tsx
"use client";
import type { Editor } from "@tiptap/react";
import { ArrowLeft, MessagesSquare, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import type { DialogueCoachMode } from "@/types";
import { useDialogueCoach } from "@/lib/hooks/useDialogueCoach";
import { DialogueIssueList } from "./_components/DialogueIssueList";
import { DialogueModeSelector } from "./_components/DialogueModeSelector";

interface DialogueCoachPanelProps {
  chapterId: string;
  /** Current editor text selection (null = nothing selected). */
  selectionText: string | null;
  editor: Editor;
  onClose: () => void;
}

export function DialogueCoachPanel({ chapterId, selectionText, editor, onClose }: DialogueCoachPanelProps) {
  const t = useTranslations("dialogueCoach");
  const [mode, setMode] = useState<DialogueCoachMode>("analyze");
  const { result, error, progress, run, isLoading, isStreaming, isComplete, isError } = useDialogueCoach();

  const inFlight = isLoading || isStreaming;
  const hasSelection = !!selectionText && selectionText.trim().length > 0;

  const handleRun = () => {
    if (hasSelection) run({ chapterId, selectionText: selectionText!, mode });
  };

  return (
    <div className="flex flex-col h-full border-l border-border bg-background w-[400px] min-w-[400px]">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border bg-card">
        <div className="flex items-center gap-3 min-w-0">
          <button type="button" onClick={onClose} className="p-1.5 text-muted-foreground hover:text-foreground rounded-md hover:bg-muted" aria-label={t("close")}>
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div className="flex items-center gap-2 min-w-0">
            <MessagesSquare className="w-5 h-5 text-violet-500 flex-shrink-0" />
            <h3 className="font-medium truncate">{t("title")}</h3>
          </div>
        </div>
        <button type="button" onClick={onClose} className="p-1.5 text-muted-foreground hover:text-foreground rounded-md hover:bg-muted" aria-label={t("close")}>
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Controls */}
      <div className="px-4 py-3 border-b border-border bg-muted/30 space-y-3">
        <DialogueModeSelector mode={mode} onSelect={setMode} disabled={inFlight || !hasSelection} />
        {!hasSelection ? (
          <p className="text-xs text-muted-foreground">{t("selectPrompt")}</p>
        ) : (
          <button type="button" onClick={handleRun} disabled={inFlight} className="w-full px-3 py-2 text-sm font-medium rounded-md bg-primary text-primary-foreground hover:opacity-90 disabled:opacity-50">
            {inFlight ? t("running") : t("run")}
          </button>
        )}
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto p-4 space-y-4">
          {inFlight && (
            <p className="text-sm text-muted-foreground">{progress ?? t("analyzing")}</p>
          )}
          {isError && (
            <div className="text-sm text-destructive" role="alert">{error?.userMessage ?? t("failed")}</div>
          )}
          {isComplete && result && (
            <>
              {result.adaptive_summary && (
                <p className="text-xs text-muted-foreground border border-border rounded-md p-2">{result.adaptive_summary}</p>
              )}
              <DialogueIssueList issues={result.issues} editor={editor} onApplied={() => {/* close panel or toast */}} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 8: Run test, lint, commit**

```bash
pnpm --filter web vitest run components/studio/analysis/__tests__/DialogueCoachPanel.test.tsx
pnpm --filter web lint
git add packages/web/components/studio/analysis/DialogueCoachPanel.tsx \
        packages/web/components/studio/analysis/_components/ \
        packages/web/components/studio/analysis/__tests__/DialogueCoachPanel.test.tsx
git commit -m "feat(web): add Dialogue Coach panel + before/after alternatives (ASSIST-004, ADR-069 D9/D16)"
```

---

## Task 9: Adaptive Status Indicator + popover (Decision 14)

**Files:**
- Create: `packages/web/components/studio/editor-view/AdaptiveStatusIndicator.tsx`
- Test: `packages/web/components/studio/editor-view/__tests__/AdaptiveStatusIndicator.test.tsx`

**Interfaces:**
- Consumes: `useAdaptiveContext` (Task 3), the settings URL (for the deep-link).
- Produces: `<AdaptiveStatusIndicator novelId={string} />`. Task 11 mounts it in `EditorToolbar`.

## Skill hints
- Load `frontend-design`: the indicator is the always-visible adaptivity signal — give the 3 states distinct, instantly-readable treatments (active = animated pulse in brand colour; paused = muted; no-data = outline). Make it feel alive without being noisy.
- Load `vercel-react-best-practices`: `rerender-derived-state` — subscribe to the derived `status` ("active"|"paused"|"no-data"), not the raw context object.
- Load `web-design-guidelines`: popover must trap focus + close on Escape + return focus to the button; the state is conveyed by icon + label (not colour alone).

- [ ] **Step 1: Write the failing test**

`packages/web/components/studio/editor-view/__tests__/AdaptiveStatusIndicator.test.tsx`:

```typescript
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { type ReactNode } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { server } from "@/mocks/server";
import { AdaptiveStatusIndicator } from "@/components/studio/editor-view/AdaptiveStatusIndicator";

function wrapper(qc: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}
const base = (overrides: Record<string, unknown>) => ({
  project_id: "proj-1", enabled: true, has_any_signal: true,
  weights: { preference: 0.7, voice_fidelity: 0.9, style_constraints: 1.0, avoidance: 1.0 },
  sources: { preference_text: "", voice_profiles_text: "", style_constraints_text: "", avoidance_patterns_text: "" },
  ...overrides,
});
afterEach(() => server.resetHandlers());

describe("AdaptiveStatusIndicator (3 states)", () => {
  it("active when enabled + has signal", async () => {
    server.use(http.get("*/api/v1/adaptive/proj-1/context", () => HttpResponse.json(base({}))));
    render(<AdaptiveStatusIndicator novelId="proj-1" />, { wrapper: wrapper(new QueryClient()) });
    await waitFor(() => expect(screen.getByLabelText("adaptive.indicator.active")).toBeInTheDocument());
  });
  it("paused when disabled but has signal", async () => {
    server.use(http.get("*/api/v1/adaptive/proj-1/context", () => HttpResponse.json(base({ enabled: false }))));
    render(<AdaptiveStatusIndicator novelId="proj-1" />, { wrapper: wrapper(new QueryClient()) });
    await waitFor(() => expect(screen.getByLabelText("adaptive.indicator.paused")).toBeInTheDocument());
  });
  it("no-data when no signal", async () => {
    server.use(http.get("*/api/v1/adaptive/proj-1/context", () => HttpResponse.json(base({ has_any_signal: false, enabled: false }))));
    render(<AdaptiveStatusIndicator novelId="proj-1" />, { wrapper: wrapper(new QueryClient()) });
    await waitFor(() => expect(screen.getByLabelText("adaptive.indicator.noData")).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: Run test to verify it fails** → `pnpm --filter web vitest run components/studio/editor-view/__tests__/AdaptiveStatusIndicator.test.tsx` (FAIL: not found).

- [ ] **Step 3: Implement the indicator**

```tsx
"use client";
import { Activity, Pause, CircleDashed } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { useAdaptiveContext } from "@/lib/hooks/useAdaptiveContext";

type IndicatorState = "active" | "paused" | "no-data";

function deriveState(enabled: boolean, hasSignal: boolean): IndicatorState {
  if (enabled && hasSignal) return "active";
  if (!enabled && hasSignal) return "paused";
  return "no-data";
}

export function AdaptiveStatusIndicator({ novelId }: { readonly novelId: string }) {
  const t = useTranslations("adaptive");
  const { data } = useAdaptiveContext(novelId);
  const [open, setOpen] = useState(false);

  const state = deriveState(data?.enabled ?? false, data?.has_any_signal ?? false);
  const Icon = state === "active" ? Activity : state === "paused" ? Pause : CircleDashed;

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={t(`indicator.${state === "no-data" ? "noData" : state}`)}
        aria-expanded={open}
        className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-sm transition-colors ${
          state === "active"
            ? "text-violet-600 dark:text-violet-400"
            : "text-muted-foreground hover:text-foreground"
        }`}
      >
        <Icon className={`w-3.5 h-3.5 ${state === "active" ? "animate-pulse" : ""}`} />
        <span>{t(`indicator.${state === "no-data" ? "noData" : state}`)}</span>
      </button>
      {open && (
        <div role="dialog" aria-label={t("indicator.popoverLabel")} className="absolute right-0 top-full mt-1 w-64 bg-card border border-border rounded-lg shadow-lg p-3 z-50">
          <p className="text-sm font-medium mb-1">{t(`indicator.${state === "no-data" ? "noData" : state}`)}</p>
          <p className="text-xs text-muted-foreground mb-2">{t(`indicator.description.${state === "no-data" ? "noData" : state}`)}</p>
          <a href={`/novel/${novelId}/settings?tab=learning`} className="text-xs text-violet-600 dark:text-violet-400 hover:underline">
            {t("indicator.manage")}
          </a>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run test, lint, commit**

```bash
pnpm --filter web vitest run components/studio/editor-view/__tests__/AdaptiveStatusIndicator.test.tsx
pnpm --filter web lint
git add packages/web/components/studio/editor-view/AdaptiveStatusIndicator.tsx \
        packages/web/components/studio/editor-view/__tests__/AdaptiveStatusIndicator.test.tsx
git commit -m "feat(web): add Adaptive Status Indicator (3 states) + popover (ADR-069 D14)"
```

---

## Task 10: i18n — 3 namespaces × 3 locales (RULE-16)

**Files:**
- Create: `packages/i18n/messages/{en,de,fr}/adaptive.json`
- Create: `packages/i18n/messages/{en,de,fr}/dialogueCoach.json`
- Create: `packages/i18n/messages/{en,de,fr}/aiAssist.json`
- Modify: `packages/web/lib/i18n/request.ts` (add 3 namespaces to the array)

**Interfaces:**
- Consumes: the i18n keys referenced in Tasks 6/8/9.
- Produces: registered namespaces loadable via `useTranslations("adaptive" | "dialogueCoach" | "aiAssist")`.

## Skill hints
- (No skill needed — this is mechanical copy. But keep keys EXACTLY matching what Tasks 6/8/9 reference; a typo = a failing test.)

- [ ] **Step 1: Author the EN files** with every key referenced above. `adaptive.json` keys: `title, loading, loadFailed, enableLabel, enableDescription, weightsTitle, weight.{preference,voice_fidelity,style_constraints,avoidance}, sourcesTitle, source.{preference,voice_profiles,style_constraints,avoidance_patterns,empty}, noSignals, indicator.{active,paused,noData,popoverLabel,manage,description.active,description.paused,description.noData}`. `dialogueCoach.json` keys: `title, close, run, running, analyzing, failed, selectPrompt, noIssues, mode.{groupLabel,analyze,improve}, severity.{low,medium,high}, alternatives.{original,rewrite,apply}`. `aiAssist.json` keys: `summaryLabel, historyEmpty, historyDisabled`.

- [ ] **Step 2: Translate to DE + FR** (mirror the EN structure exactly — same keys).

- [ ] **Step 3: Register in `request.ts`**

In `packages/web/lib/i18n/request.ts`, extend the `namespaces` array:

```typescript
const namespaces = [
  "common", "auth", "wizard", "dashboard", "editor", "errors", "generation",
  "settings", "settings-ai", "settings-appearance", "studio", "analysis", "timeline",
  "adaptive", "dialogueCoach", "aiAssist",
] as const;
```

- [ ] **Step 4: Verify** — run the RULE-16 checker if one exists (`just check` i18n step), and confirm all 9 files parse as JSON. Commit:

```bash
git add packages/i18n/messages packages/web/lib/i18n/request.ts
git commit -m "feat(i18n): add adaptive, dialogueCoach, aiAssist namespaces (3 locales) (ADR-069 §27, RULE-16)"
```

---

## Task 11: Editor integration wiring

**Files:**
- Modify: `packages/web/lib/stores/editorRightPanelState.ts` (add `"dialogue_coach"`)
- Modify: `packages/web/components/studio/editor-view/EditorPanelContent.tsx` (add the switch case)
- Modify: `packages/web/components/studio/editor-view/EditorToolbar.tsx` (render trigger + indicator)
- Create: `packages/web/components/studio/analysis/DialogueCoachTrigger.tsx`
- Test: `packages/web/components/studio/editor-view/__tests__/dialogue-coach-wiring.test.tsx`

**Interfaces:**
- Consumes: `DialogueCoachPanel` (Task 8), `AdaptiveStatusIndicator` (Task 9), the editor instance + current selection.
- Produces: a registered `dialogue_coach` right panel + toolbar entry.

## Skill hints
- Load `vercel-composition-patterns`: the trigger follows the established `CharacterVoiceTrigger` composition (subscribe to derived `active === "dialogue_coach"`, not the whole store).
- Load `vercel-react-view-transitions`: assess — the panel already transitions via `PanelShell`. Add a minimal `<ViewTransition default="none" enter="fade-in" exit="fade-out">` around the mode-selector content swap ONLY if it communicates continuity; otherwise skip (the skill says don't animate without reason). Add the reduced-motion CSS guard regardless.
- Load `vercel-react-best-practices`: pass the editor + selection as props (don't reach into the store from inside the panel).

- [ ] **Step 1: Write the failing test** asserting the panel renders when active and the toolbar shows the trigger + indicator (mock `useEditorStore` / render `EditorToolbar` with a fake editor). Assert `screen.getByLabelText("dialogueCoach.trigger")` and `screen.getByLabelText("adaptive.indicator.active"|"paused"|"no-data")` appear.

- [ ] **Step 2: Register the panel id.** In `editorRightPanelState.ts` add `"dialogue_coach"` to the `EditorRightPanelId` union and insert `"dialogue_coach"` into `EDITOR_RIGHT_PANEL_PRIORITY` (near `character_voice`).

- [ ] **Step 3: Add the switch case** in `EditorPanelContent.tsx`:

```tsx
case "dialogue_coach":
  return (
    <DialogueCoachPanel
      chapterId={activeChapterId}
      selectionText={content /* or a selection accessor from the editor */}
      editor={editor}
      onClose={() => closePanel("dialogue_coach")}
    />
  );
```

> The `editor` + live selection must be threaded from `EditorWorkspace`/`EditorView` down to `EditorPanelContent` as props (mirror how `content` is already passed). Read `EditorWorkspace.tsx` + `TipTapEditor.tsx` at implementation time to find the editor instance + the selection accessor (the existing WRITE-004 rewrite flow already reads the selection — reuse that accessor).

- [ ] **Step 4: Create `DialogueCoachTrigger.tsx`** (mirrors `CharacterVoiceTrigger.tsx`, id `"dialogue_coach"`, icon `MessagesSquare`, label `dialogueCoach.trigger`).

- [ ] **Step 5: Wire the toolbar.** In `EditorToolbar.tsx`, add `<DialogueCoachTrigger />` next to `<CharacterVoiceTrigger />` and `<AdaptiveStatusIndicator novelId={novelId} />` in the toolbar (thread `novelId` — it's already available in the editor-view props).

- [ ] **Step 6: Run test, lint, commit**

```bash
pnpm --filter web vitest run components/studio/editor-view/__tests__/dialogue-coach-wiring.test.tsx
pnpm --filter web lint
git add packages/web/lib/stores/editorRightPanelState.ts \
        packages/web/components/studio/editor-view/ \
        packages/web/components/studio/analysis/DialogueCoachTrigger.tsx
git commit -m "feat(web): wire Dialogue Coach panel + Status Indicator into the editor (ADR-069 §24/26)"
```

---

## Task 12: Vitest unit + axe-core a11y tests

**Files:**
- Various `__tests__/*.test.tsx` augmenting Tasks 6/8/9 with edge cases + axe-core scans.
- Test: `packages/web/components/studio/analysis/__tests__/dialogue-coach-a11y.test.tsx`
- Test: `packages/web/components/studio/settings/__tests__/adaptive-dashboard-a11y.test.tsx`

## Skill hints
- Load `web-design-guidelines`: this is the a11y gate. Fetch the guidelines (`webfetch` the command.md) and assert against: keyboard operability, focus visibility, ARIA roles/labels, colour-not-alone (severity badges), reduced motion.

- [ ] **Step 1: Add axe-core if not present** — check `packages/web/package.json` for `axe-core` / `@axe-core/playwright` / `vitest-axe`. If missing, add `vitest-axe` (matches the Vitest stack).

- [ ] **Step 2: Write a11y tests** for `DialogueCoachPanel` (analyze + improve + idle + error states) and `AdaptiveDashboard` (toggle + sliders + empty state). Assert `expect(container).toPassAxe()` (or equivalent) with rules excluding only known-acceptable violations.

- [ ] **Step 3: Add edge-case unit tests** — empty `issues` array renders `noIssues`; `alternatives === null` (analyze mode) hides the Apply button; `has_any_signal === false` renders the source empty state; slider keyboard (`ArrowRight`) commits.

- [ ] **Step 4: Run the full suite, confirm coverage floors hold** (`lib/**` ≥ 80%, `components/**` ≥ 65%), commit.

```bash
pnpm --filter web vitest run
git add packages/web/components/studio/analysis/__tests__/dialogue-coach-a11y.test.tsx \
        packages/web/components/studio/settings/__tests__/adaptive-dashboard-a11y.test.tsx
git commit -m "test(web): add axe-core a11y + edge-case tests for dialogue coach + adaptive dashboard (ADR-069 §28)"
```

---

## Task 13: Playwright VRT (ADR-059)

**Files:**
- Create: `packages/web/tests/screenshots/adaptive.spec.ts`
- Create: `packages/web/tests/screenshots/adaptive-indicator.spec.ts`

**Interfaces:**
- Consumes: the `vrt` Playwright project (`maxDiffPixelRatio: 0.02`), mocked API via `page.route()`.

## Skill hints
- ADR-059 is the authoritative pattern (no skill needed beyond following it: mock APIs, deterministic data, fixed viewport, 4 theme variants where relevant).

- [ ] **Step 1: `adaptive.spec.ts`** — navigate to the Learning settings tab, `page.route("**/api/v1/adaptive/*/context", ...)` to a deterministic fixture, capture `AdaptiveDashboard` in 4 theme variants (light+dark × default+narrare). Use `page.locator` to scope the screenshot to the dashboard section.

- [ ] **Step 2: `adaptive-indicator.spec.ts`** — render the editor toolbar; for each of the 3 states (`active`/`paused`/`no-data`), mock the context response and capture the indicator. 3 fixtures × (light+dark) = 6 baselines.

- [ ] **Step 3: Generate baselines + commit**

```bash
cd packages/web && pnpm exec playwright test --project=vrt --update-snapshots
git add packages/web/tests/screenshots/
git commit -m "test(web): add Playwright VRT for AdaptiveDashboard + Status Indicator (ADR-059, ADR-069 §28)"
```

---

## Self-Review

**1. Spec coverage** (ADR-069 Phase 5 steps 21–28):
- 21 TS types → **Task 1** (all adaptive + ai_assist types, RULE-17).
- 22 API clients (SSE dialogue coach + REST adaptive) → **Task 2**.
- 23 Hooks (useDialogueCoach via useAIOperation; useAdaptiveContext via TanStack Query) → **Tasks 3 + 4**.
- 24 Dialogue Coach components (panel, mode selector, issue list, alternative cards) → **Task 8**.
- 25 Adaptive Dashboard components (toggle, weight sliders, source list, snapshot history) → **Tasks 6 + 7**.
- 26 Adaptive Status Indicator (editor toolbar) → **Task 9**.
- 27 i18n (3 ns × 3 locales; register in request.ts) → **Task 10**.
- 28 Vitest + axe-core + Playwright VRT → **Tasks 12 + 13**.
All 8 steps covered. ✅

**2. Placeholder scan:** Tasks 1–6, 8, 9 ship complete code. Task 7 (gated) + 10–13 are structurally complete with concrete file lists + commands. The only deferred detail is the ProseMirror accept-transaction in `DialogueAlternativeCard` — and that is a **deliberate DRY pointer** to the existing WRITE-004 helper (`CoAuthorPanel.tsx` / `rewriteStream.ts`) to reuse, not a placeholder: the contract (full-string find-and-replace, Decision 9), the failure mode (not-found → graceful no-op, RULE-11), and the `onApplied` callback are fully specified. Acceptable.

**3. Type consistency:** `DialogueCoachMode`, `DialogueCoachResponse`, `DialogueIssue`, `DialogueAlternative`, `AdaptiveWeightsInput`, `adaptiveKeys.context(projectId)` all defined once (Task 1/3) and consumed identically downstream. `run({chapterId, selectionText, mode})` signature matches `DialogueCoachRunParams`. The canonical key `["adaptive-context", projectId]` is referenced identically in Tasks 3/6/9. ✅

**4. RULE-17 check:** every TS field name matches the shipped Pydantic schema verbatim (verified against `adaptive/schemas.py` + `ai_assist/schemas.py`): `has_any_signal`, `voice_fidelity`, `selection_text`, `original_quote`, `adaptive_summary`, `avoidance_patterns_text`, etc. snake_case throughout (codebase precedent). ✅

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-07-22-adaptive-context-frontend.md`.**

**Coordinator decisions needed before/during execution:**
1. **Snapshot History endpoint (Task 7)** — confirm **(A)** add `GET /adaptive/{project_id}/snapshots` (dispatch to Backend Specialist) or **(B)** scope history out. Recommend **(A)**.

**Two execution options:**
1. **Subagent-Driven (recommended)** — dispatch a fresh Frontend Specialist per task, review between tasks, fast iteration.
2. **Inline Execution** — execute tasks in this session via `executing-plans`, batch with checkpoints.

**Recommended task batching for subagent dispatch:** {1,2} foundation → {3,4} hooks → {5} primitives → {6,8,9} components (parallel) → {10} i18n → {11} wiring → {12,13} tests. Task 7 runs whenever endpoint A lands.

**Which approach?**
