# CR-AUFG-07-18 — Standardized Diff View across AI Outputs — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce one reusable, accessible AI-diff vocabulary (`AIDiffViewModel` + `AIDiffView`) and adopt it across Rewrite, Co-Author, and KB Enhance, with an honest (null-returning) Beta-Reader adapter — no fabricated diffs, no backend change.

**Architecture:** Frontend-only shared primitive under `packages/web/lib/ai-diff/` (contracts + pure algorithm + domain adapters) and `packages/web/components/shared/ai-diff/` (accessible rendering). Each existing review surface keeps its own lifecycle/keyboard wiring (CR-AUFG-07-13) and only swaps its local comparison rendering for the shared view model. The diff primitive never starts AI work.

**Tech Stack:** Next.js, React, TypeScript (strict), next-intl, `diff-match-patch` (already a dependency), Vitest + @testing-library/react, Biome, `scripts/validate-i18n.ts`, `just check-ai-ux`, `scripts/check_frontend_file_size.py`.

**Spec source:** `docs/features/ai-ux/CR-AUFG-07-18-diff-view-standardization.md` (status: `planned`).
**Umbrella:** `docs/architecture/governance/cr-07-phase-c-spec.md` (§5 ordering: this AUFG is #1 in Phase C).

> **No commits.** Per the orchestrator's instruction this plan contains no `git commit` steps. Verification gates run at the end of every task and again in Task 18.

---

## Root cause + architecture fit

**Symptom (spec §Problem):** Rewrite, Co-Author, KB Enhance, and Beta Reader each render "AI changed A→B" with a feature-local pattern.

**Warum 1:** Each feature built its own review UI around its own payload shape (rewrite alternatives, co-author change list, KB before/after cards, beta-reader feedback items).

**Warum 2:** CR-07 standardized the AI-operation *lifecycle/action* vocabulary (ADR-043, `studio.aiActions.*`, `lib/ai-action-shortcuts.ts`) but never the *representation contract* for "AI changed this from A to B."

**Root cause:** Narrare has no reusable frontend diff vocabulary that adapts domain payloads into a shared author-control view without forcing backend schemas into one shape.

**Code evidence (read during planning):**
- `packages/web/components/studio/editor/InlineDiff.tsx` (74 lines) — the only "shared" text-diff renderer; **color-only**, no `<ins>`/`<del>`, no screen-reader labels → violates spec AC "additions/deletions are not conveyed by color alone."
- `packages/web/components/studio/editor/ChangeReview.tsx` (152 lines) — Co-Author card; renders original/revised as two hard-coded colored lines; uses `studio.changeReview.*`; has **hard-coded English** `aria-label={isAccepted ? "Reject change" : "Accept change"}` (RULE-16 regression risk).
- `packages/web/components/studio/editor/RewriteSuggestionModal.tsx` (179 lines) — uses `InlineDiff`.
- `packages/web/components/studio/kb/_components/EnhanceReviewCard.tsx` (124 lines) — KB field before/after grid using `studio.kb.original/suggested`.
- `packages/web/components/studio/analysis/BetaReaderPanel.tsx` (144 lines) — feedback-only; `BetaFeedbackItem` (`packages/web/lib/api/analysis.ts`) has `suggestion: string|null` (prose advice) and `text_excerpt: string|null` (a passage) but **no grounded A→B revision pair**.
- `packages/web/lib/ai-action-shortcuts.ts` — `isApplyShortcut` (Ctrl/Cmd+Enter) already standardized across review surfaces (CR-AUFG-07-13). Must be preserved.
- i18n: `packages/i18n/messages/{de,en,fr}/studio.json` — `studio.aiActions.{original,suggested,accept,…}` canonical; `studio.changeReview.*` Co-Author-local.
- Inventory: `scripts/checks/ai_operation_inventory.yaml` — 17 operations; `writing.rewrite`, `writing.co_author`, `kb.enhance`, `analysis.beta_reader` are the four touched operations that must reference the shared primitive.

**Chosen alternative (spec §Alternatives #3):** Frontend shared view model + domain adapters. Contract-first; no backend churn unless a domain later needs grounded location metadata (RULE-17 coordinated change). Rejected alternatives: (1) backend-normalized universal schema — forces unlike domains into one shape; (2) keep feature-local UIs — preserves the root cause.

**RULE-20 (no half implementation) applied to Beta Reader:** The current schema has no grounded original→suggested text pair, so the Beta-Reader adapter **returns `null`** for every live item and no Beta-Reader UI changes. Feedback stays feedback. The adapter + its null-asserting test are the *complete, honest* deliverable; fabricating diffs from `suggestion`+`text_excerpt` is explicitly out-of-scope.

---

## File structure

### New — shared primitive (Greenfield; `packages/web/lib/ai-diff/` does not exist yet)

| File | Responsibility | Approx. lines (limit) |
|------|----------------|-----------------------|
| `packages/web/lib/ai-diff/contracts.ts` | `AIDiffState`, `AIDiffSegmentKind`, `AIDiffSegment`, `AIDiffMode`, `AIDiffViewModel`. Pure types, no runtime. | ~70 (ts 400) |
| `packages/web/lib/ai-diff/segmentize.ts` | Pure `segmentize(original, suggested): AIDiffSegment[]` using `diff-match-patch`. Single source of the diff algorithm (DRY). No React. | ~45 (ts 400) |
| `packages/web/lib/ai-diff/adapters/rewrite.ts` | `rewriteAdapter(original, suggestion, label, provisional): AIDiffViewModel` (text mode; primitives only — no component import). | ~30 (ts 400) |
| `packages/web/lib/ai-diff/adapters/coauthor.ts` | `coAuthorChangeAdapter(change: ChangeDetail): AIDiffViewModel` (text mode). | ~30 (ts 400) |
| `packages/web/lib/ai-diff/adapters/kb-enhance.ts` | `kbEnhanceFieldAdapter(enhancement, fieldLabel): AIDiffViewModel` (**field** mode — no inline prose diff). | ~30 (ts 400) |
| `packages/web/lib/ai-diff/adapters/beta-reader.ts` | `isBetaReaderGrounded(item): boolean` (false today) + `betaReaderGroundedAdapter(item): AIDiffViewModel \| null` (null today). | ~45 (ts 400) |
| `packages/web/lib/ai-diff/index.ts` | Barrel re-export of public types + adapters + `segmentize`. | ~20 (ts 400) |

### New — shared accessible component (Greenfield; `packages/web/components/shared/ai-diff/` does not exist yet)

| File | Responsibility | Approx. lines (limit) |
|------|----------------|-----------------------|
| `packages/web/components/shared/ai-diff/AIDiffSegmentList.tsx` | Renders segments with semantic `<ins>`/`<del>` + visible `+`/`−` markers + per-segment `aria-label` (NOT color alone). | ~80 (tsx 200) |
| `packages/web/components/shared/ai-diff/AIDiffBadge.tsx` | State badge (Suggested/Accepted/Rejected/Unchanged) using `aiActions.suggested` + `aiDiff.*`; text label (not color alone). | ~55 (tsx 200) |
| `packages/web/components/shared/ai-diff/AIDiffView.tsx` | Composes badge + segment list; supports `text` and `field` modes; provisional indicator; `role="group"` + sr-summary. | ~110 (tsx 200) |

### Tests (new)

| File |
|------|
| `packages/web/lib/ai-diff/__tests__/contracts.test.ts` |
| `packages/web/lib/ai-diff/__tests__/segmentize.test.ts` |
| `packages/web/lib/ai-diff/__tests__/adapters/rewrite.test.ts` |
| `packages/web/lib/ai-diff/__tests__/adapters/coauthor.test.ts` |
| `packages/web/lib/ai-diff/__tests__/adapters/kb-enhance.test.ts` |
| `packages/web/lib/ai-diff/__tests__/adapters/beta-reader.test.ts` |
| `packages/web/components/shared/ai-diff/__tests__/AIDiffSegmentList.test.tsx` |
| `packages/web/components/shared/ai-diff/__tests__/AIDiffBadge.test.tsx` |
| `packages/web/components/shared/ai-diff/__tests__/AIDiffView.test.tsx` |

### Modified — adoption (existing flows preserved; keyboard untouched)

| File | Change |
|------|--------|
| `packages/web/components/studio/editor/InlineDiff.tsx` | Delegate to `segmentize` + `<AIDiffSegmentList>`; add a11y. Public API (`InlineDiff`, and `computeDiffElements` only if still consumed) preserved or removed per Task 12 grep. |
| `packages/web/components/studio/editor/RewriteSuggestionModal.tsx` | Replace `<InlineDiff>` with `<AIDiffView viewModel={rewriteAdapter(...)} state="suggested" />`. Keep `isApplyShortcut`/Escape wiring. |
| `packages/web/components/studio/editor/ChangeReview.tsx` | Replace manual before/after with `<AIDiffView viewModel={coAuthorChangeAdapter(change)} state={...} />`; fix hard-coded aria-labels → `aiDiff.acceptChange/rejectChange`. |
| `packages/web/components/studio/kb/_components/EnhanceReviewCard.tsx` | Replace before/after grid with `<AIDiffView viewModel={kbEnhanceFieldAdapter(...)} state={...} />` (field mode). |
| `packages/i18n/messages/{de,en,fr}/studio.json` | Add `studio.aiDiff.*` (9 keys × 3 locales); remove now-unused `studio.changeReview.*` after ChangeReview migration (Task 14 verify). |
| `scripts/checks/ai_operation_inventory.yaml` | Add optional `shared_diff_view` field to the 4 touched operations. |

### Unchanged (verified, not modified)
- `packages/web/lib/ai-action-shortcuts.ts` — keyboard contract preserved.
- Backend / Core — no change in this increment (spec §"Architecture fit").

---

## Conventions for every task

- **Working directory for pnpm commands:** `packages/web` (run `pnpm …` from there).
- **Working directory for `uv` / `just` / `npx tsx scripts/validate-i18n.ts`:** repo root.
- **TDD order in every code task:** (1) write failing test → (2) run it, confirm it fails for the right reason → (3) implement minimal code → (4) run it, confirm pass. No skipping.
- **No commit steps** in this plan.

---

## Task 1: Add `studio.aiDiff.*` i18n keys (DE/EN/FR)

**Files:**
- Modify: `packages/i18n/messages/en/studio.json` (insert after the `aiActions` block, which ends at line 1772)
- Modify: `packages/i18n/messages/de/studio.json` (same location)
- Modify: `packages/i18n/messages/fr/studio.json` (same location)

- [ ] **Step 1: Add the `aiDiff` block to EN**

Insert immediately after the closing `}` of `"aiActions": { … }` (before `"tour": {`):

```json
  "aiDiff": {
    "added": "Added",
    "removed": "Removed",
    "unchanged": "Unchanged",
    "accepted": "Accepted",
    "rejected": "Rejected",
    "srSummary": "{added} addition(s) and {removed} removal(s)",
    "acceptChange": "Accept change",
    "rejectChange": "Reject change",
    "provisional": "Provisional"
  },
```

- [ ] **Step 2: Add the `aiDiff` block to DE**

```json
  "aiDiff": {
    "added": "Hinzugefügt",
    "removed": "Entfernt",
    "unchanged": "Unverändert",
    "accepted": "Akzeptiert",
    "rejected": "Abgelehnt",
    "srSummary": "{added} Ergänzung(en) und {removed} Streichung(en)",
    "acceptChange": "Änderung übernehmen",
    "rejectChange": "Änderung verwerfen",
    "provisional": "Vorläufig"
  },
```

- [ ] **Step 3: Add the `aiDiff` block to FR**

```json
  "aiDiff": {
    "added": "Ajouté",
    "removed": "Supprimé",
    "unchanged": "Inchangé",
    "accepted": "Accepté",
    "rejected": "Rejeté",
    "srSummary": "{added} ajout(s) et {removed} suppression(s)",
    "acceptChange": "Accepter la modification",
    "rejectChange": "Rejeter la modification",
    "provisional": "Provisoire"
  },
```

- [ ] **Step 4: Validate i18n parity + JSON syntax**

Run (from repo root):
```bash
npx tsx scripts/validate-i18n.ts
```
Expected: exit code `0`; no `[ERROR]` lines mentioning `aiDiff`. If a key-completeness error appears, the locale block was mis-placed — fix the JSON and re-run.

---

## Task 2: Contracts (`packages/web/lib/ai-diff/contracts.ts`)

**Files:**
- Create: `packages/web/lib/ai-diff/contracts.ts`
- Test: `packages/web/lib/ai-diff/__tests__/contracts.test.ts`

- [ ] **Step 1: Write the failing test**

`packages/web/lib/ai-diff/__tests__/contracts.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import type { AIDiffMode, AIDiffSegment, AIDiffSegmentKind, AIDiffState, AIDiffViewModel } from "../contracts";

describe("ai-diff contracts", () => {
  it("exposes the documented AIDiffState values", () => {
    const states: AIDiffState[] = ["suggested", "accepted", "rejected", "unchanged"];
    expect(states).toHaveLength(4);
  });

  it("exposes the documented AIDiffSegmentKind values", () => {
    const kinds: AIDiffSegmentKind[] = ["added", "removed", "unchanged"];
    expect(kinds).toHaveLength(3);
  });

  it("a field-mode view model has no segments (structural invariant)", () => {
    const vm: AIDiffViewModel = {
      id: "kb-role",
      mode: "field" satisfies AIDiffMode,
      segments: [],
      originalFull: "Mentor",
      suggestedFull: "Wise mentor",
      label: "Role",
      provisional: false,
    };
    expect(vm.mode).toBe("field");
    expect(vm.segments).toHaveLength(0);
  });

  it("a segment is a readonly kind+text pair", () => {
    const seg: AIDiffSegment = { kind: "added", text: "x" };
    expect(seg.kind).toBe("added");
    expect(seg.text).toBe("x");
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run (from `packages/web`):
```bash
pnpm test src/__tests__/../lib/ai-diff/__tests__/contracts.test.ts
```
(If the path alias differs, use: `pnpm test lib/ai-diff/__tests__/contracts.test.ts`.)
Expected: FAIL — `Cannot find module '../contracts'` (file does not exist yet).

- [ ] **Step 3: Write the contracts**

`packages/web/lib/ai-diff/contracts.ts`:
```ts
/**
 * CR-AUFG-07-18 — Shared, domain-agnostic AI diff vocabulary.
 *
 * Frontend-only contract (RULE-03): defined BEFORE any component or adapter.
 * The diff primitive is a pure VIEW — it never starts AI work and owns no
 * lifecycle. Lifecycle/cancel/error stay with the source AI operation
 * (ADR-043 useAIOperation).
 */

/** Author-control / acceptance state of an AI diff. */
export type AIDiffState =
  | "suggested" // AI proposal pending an author decision
  | "accepted" // author accepted
  | "rejected" // author rejected
  | "unchanged"; // original and suggested are equal

/** Kind of a single text-level diff segment. */
export type AIDiffSegmentKind = "added" | "removed" | "unchanged";

/** Rendering mode for the view model. */
export type AIDiffMode = "text" | "field";

/** One atomic piece of an inline text diff. Immutable. */
export interface AIDiffSegment {
  readonly kind: AIDiffSegmentKind;
  readonly text: string;
}

/**
 * Shared view model for "AI changed A → B".
 *
 * - `text` mode: inline character/word diff via `segments` (Rewrite, Co-Author).
 * - `field` mode: whole-value before/after, NO inline diff (KB Enhance) —
 *   structured fields must not be假装 as prose diffs (CR-AUFG-07-18 AC #3).
 *   Invariant: `mode === "field"` ⇒ `segments` is empty.
 */
export interface AIDiffViewModel {
  /** Stable id (change id, field key, suggestion index, …). */
  readonly id: string;
  readonly mode: AIDiffMode;
  /** `text` mode: segmented diff; `field` mode: empty array. */
  readonly segments: readonly AIDiffSegment[];
  /** Whole original value. */
  readonly originalFull: string;
  /** Whole suggested value. */
  readonly suggestedFull: string;
  /** Optional domain label (change_type, field label). `null` when N/A. */
  readonly label: string | null;
  /** True while the source operation is still streaming (provisional output). */
  readonly provisional: boolean;
}
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pnpm test lib/ai-diff/__tests__/contracts.test.ts
```
Expected: PASS — 4 tests.

- [ ] **Step 5: Type-check**

```bash
pnpm type-check
```
Expected: exit code `0`.

---

## Task 3: Pure diff algorithm (`segmentize.ts`)

**Files:**
- Create: `packages/web/lib/ai-diff/segmentize.ts`
- Test: `packages/web/lib/ai-diff/__tests__/segmentize.test.ts`

- [ ] **Step 1: Write the failing test**

`packages/web/lib/ai-diff/__tests__/segmentize.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { segmentize } from "../segmentize";

describe("segmentize", () => {
  it("returns a single unchanged segment when strings are equal", () => {
    const segs = segmentize("hello", "hello");
    expect(segs).toEqual([{ kind: "unchanged", text: "hello" }]);
  });

  it("produces added + removed segments for a real change", () => {
    const segs = segmentize("the cat", "the dog");
    const kinds = segs.map((s) => s.kind);
    expect(kinds).toContain("removed");
    expect(kinds).toContain("added");
    expect(kinds).toContain("unchanged"); // "the " prefix
  });

  it("is pure: same input ⇒ same output and no mutation", () => {
    const a = segmentize("a b", "a c");
    const b = segmentize("a b", "a c");
    expect(a).toEqual(b);
  });

  it("concatenated removed+added text reproduces the change", () => {
    const segs = segmentize("old", "new");
    const removed = segs.filter((s) => s.kind === "removed").map((s) => s.text).join("");
    const added = segs.filter((s) => s.kind === "added").map((s) => s.text).join("");
    expect(removed).toBe("old");
    expect(added).toBe("new");
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pnpm test lib/ai-diff/__tests__/segmentize.test.ts
```
Expected: FAIL — `Cannot find module '../segmentize'`.

- [ ] **Step 3: Write `segmentize.ts`**

`packages/web/lib/ai-diff/segmentize.ts`:
```ts
import DiffMatchPatch from "diff-match-patch";
import type { AIDiffSegment, AIDiffSegmentKind } from "./contracts";

// Singleton — reused across calls (mirrors the prior InlineDiff instance).
const dmp = new DiffMatchPatch();

/**
 * Pure diff: returns ordered {@link AIDiffSegment}s mapping `original` → `suggested`.
 *
 * No React, no side effects. This is the single source of the diff algorithm
 * (DRY): `InlineDiff` and the shared adapters all depend on it.
 */
export function segmentize(original: string, suggested: string): AIDiffSegment[] {
  const diffs = dmp.diff_main(original, suggested);
  dmp.diff_cleanupSemantic(diffs);

  const segments: AIDiffSegment[] = [];
  for (const [operation, text] of diffs) {
    const kind: AIDiffSegmentKind =
      operation === DiffMatchPatch.DIFF_INSERT
        ? "added"
        : operation === DiffMatchPatch.DIFF_DELETE
          ? "removed"
          : "unchanged";
    segments.push({ kind, text });
  }
  return segments;
}
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pnpm test lib/ai-diff/__tests__/segmentize.test.ts
```
Expected: PASS — 4 tests.

---

## Task 4: `AIDiffSegmentList` (accessible segment renderer)

**Files:**
- Create: `packages/web/components/shared/ai-diff/AIDiffSegmentList.tsx`
- Test: `packages/web/components/shared/ai-diff/__tests__/AIDiffSegmentList.test.tsx`

- [ ] **Step 1: Write the failing test**

`packages/web/components/shared/ai-diff/__tests__/AIDiffSegmentList.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AIDiffSegmentList } from "../AIDiffSegmentList";
import { NextIntlClientProvider } from "next-intl";

const messages = { studio: { aiDiff: { added: "Added", removed: "Removed" } } };

function wrap(ui: React.ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages as never}>
      {ui}
    </NextIntlClientProvider>
  );
}

describe("AIDiffSegmentList", () => {
  it("renders additions in a semantic <ins> element", () => {
    const { container } = render(
      wrap(<AIDiffSegmentList segments={[{ kind: "added", text: "new" }]} />),
    );
    expect(container.querySelector("ins")).not.toBeNull();
    expect(container.querySelector("ins")?.textContent).toContain("new");
  });

  it("renders removals in a semantic <del> element", () => {
    const { container } = render(
      wrap(<AIDiffSegmentList segments={[{ kind: "removed", text: "old" }]} />),
    );
    expect(container.querySelector("del")).not.toBeNull();
  });

  it("does NOT rely on color alone: visible + / − markers are present", () => {
    const { container } = render(
      wrap(
        <AIDiffSegmentList
          segments={[
            { kind: "removed", text: "old" },
            { kind: "added", text: "new" },
          ]}
        />,
      ),
    );
    const markers = container.querySelectorAll("[aria-hidden='true']");
    expect(markers.length).toBeGreaterThanOrEqual(2);
  });

  it("labels each change segment for screen readers via aria-label", () => {
    render(
      wrap(
        <AIDiffSegmentList
          segments={[
            { kind: "added", text: "x" },
            { kind: "removed", text: "y" },
          ]}
        />,
      ),
    );
    expect(screen.getByLabelText("Added")).toBeTruthy();
    expect(screen.getByLabelText("Removed")).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pnpm test components/shared/ai-diff/__tests__/AIDiffSegmentList.test.tsx
```
Expected: FAIL — `Cannot find module '../AIDiffSegmentList'`.

- [ ] **Step 3: Write the component**

`packages/web/components/shared/ai-diff/AIDiffSegmentList.tsx`:
```tsx
"use client";

import { useTranslations } from "next-intl";
import type { AIDiffSegment } from "@/lib/ai-diff/contracts";

interface AIDiffSegmentListProps {
  readonly segments: readonly AIDiffSegment[];
}

/**
 * Renders diff segments accessibly (CR-AUFG-07-18 AC #6):
 * - additions → semantic `<ins>` + green tint + visible `+` marker + sr label
 * - removals  → semantic `<del>` + red tint + strikethrough + visible `−` marker + sr label
 * - unchanged → plain `<span>`
 *
 * Change type is therefore conveyed by element semantics, text marker, AND
 * color — never by color alone.
 */
export function AIDiffSegmentList({ segments }: AIDiffSegmentListProps) {
  const t = useTranslations("studio");
  return (
    <>
      {segments.map((seg, i) => {
        if (seg.kind === "added") {
          return (
            <ins
              key={`ins-${i}`}
              aria-label={t("aiDiff.added")}
              className="bg-green-200/60 dark:bg-green-900/40 rounded-sm px-0.5 no-underline"
            >
              <span aria-hidden="true" className="font-mono mr-0.5">+</span>
              {seg.text}
            </ins>
          );
        }
        if (seg.kind === "removed") {
          return (
            <del
              key={`del-${i}`}
              aria-label={t("aiDiff.removed")}
              className="bg-red-200/60 dark:bg-red-900/40 line-through rounded-sm px-0.5"
            >
              <span aria-hidden="true" className="font-mono mr-0.5">−</span>
              {seg.text}
            </del>
          );
        }
        return <span key={`eq-${i}`}>{seg.text}</span>;
      })}
    </>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pnpm test components/shared/ai-diff/__tests__/AIDiffSegmentList.test.tsx
```
Expected: PASS — 4 tests.

---

## Task 5: `AIDiffBadge` (state badge)

**Files:**
- Create: `packages/web/components/shared/ai-diff/AIDiffBadge.tsx`
- Test: `packages/web/components/shared/ai-diff/__tests__/AIDiffBadge.test.tsx`

- [ ] **Step 1: Write the failing test**

`packages/web/components/shared/ai-diff/__tests__/AIDiffBadge.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { NextIntlClientProvider } from "next-intl";
import { AIDiffBadge } from "../AIDiffBadge";

const messages = {
  studio: {
    aiActions: { suggested: "Suggested" },
    aiDiff: { accepted: "Accepted", rejected: "Rejected", unchanged: "Unchanged" },
  },
};

function wrap(ui: React.ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages as never}>
      {ui}
    </NextIntlClientProvider>
  );
}

describe("AIDiffBadge", () => {
  it("shows the canonical Suggested label for the suggested state", () => {
    render(wrap(<AIDiffBadge state="suggested" />));
    expect(screen.getByText("Suggested")).toBeTruthy();
  });

  it("shows dedicated diff labels for accepted/rejected/unchanged", () => {
    const { rerender } = render(wrap(<AIDiffBadge state="accepted" />));
    expect(screen.getByText("Accepted")).toBeTruthy();
    rerender(wrap(<AIDiffBadge state="rejected" />));
    expect(screen.getByText("Rejected")).toBeTruthy();
    rerender(wrap(<AIDiffBadge state="unchanged" />));
    expect(screen.getByText("Unchanged")).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pnpm test components/shared/ai-diff/__tests__/AIDiffBadge.test.tsx
```
Expected: FAIL — module not found.

- [ ] **Step 3: Write the component**

`packages/web/components/shared/ai-diff/AIDiffBadge.tsx`:
```tsx
"use client";

import { useTranslations } from "next-intl";
import type { AIDiffState } from "@/lib/ai-diff/contracts";

interface AIDiffBadgeProps {
  readonly state: AIDiffState;
}

const STATE_STYLES: Record<AIDiffState, string> = {
  suggested: "bg-primary/10 text-primary border-primary/30",
  accepted: "bg-green-500/10 text-green-700 dark:text-green-400 border-green-500/40",
  rejected: "bg-red-500/10 text-red-700 dark:text-red-400 border-red-500/40",
  unchanged: "bg-muted text-muted-foreground border-border",
};

/**
 * Accessible state badge. The label is always visible text (never color alone),
 * using canonical `studio.aiActions.suggested` plus dedicated `studio.aiDiff.*`
 * state keys (CR-AUFG-07-18 AC #1).
 */
export function AIDiffBadge({ state }: AIDiffBadgeProps) {
  const t = useTranslations("studio");
  const label =
    state === "suggested"
      ? t("aiActions.suggested")
      : state === "accepted"
        ? t("aiDiff.accepted")
        : state === "rejected"
          ? t("aiDiff.rejected")
          : t("aiDiff.unchanged");
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${STATE_STYLES[state]}`}
    >
      {label}
    </span>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pnpm test components/shared/ai-diff/__tests__/AIDiffBadge.test.tsx
```
Expected: PASS — 2 tests.

---

## Task 6: `AIDiffView` (composing primitive)

**Files:**
- Create: `packages/web/components/shared/ai-diff/AIDiffView.tsx`
- Test: `packages/web/components/shared/ai-diff/__tests__/AIDiffView.test.tsx`

- [ ] **Step 1: Write the failing test**

`packages/web/components/shared/ai-diff/__tests__/AIDiffView.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { NextIntlClientProvider } from "next-intl";
import { AIDiffView } from "../AIDiffView";
import { segmentize } from "@/lib/ai-diff/segmentize";
import type { AIDiffViewModel } from "@/lib/ai-diff/contracts";

const messages = {
  studio: {
    aiActions: { original: "Original", suggested: "Suggested" },
    aiDiff: {
      accepted: "Accepted",
      unchanged: "Unchanged",
      provisional: "Provisional",
      srSummary: "{added} addition(s) and {removed} removal(s)",
    },
    kb: { empty: "empty" },
  },
};

function wrap(ui: React.ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages as never}>
      {ui}
    </NextIntlClientProvider>
  );
}

const textVm: AIDiffViewModel = {
  id: "rw-1",
  mode: "text",
  segments: segmentize("cat", "dog"),
  originalFull: "cat",
  suggestedFull: "dog",
  label: "Sentence",
  provisional: false,
};

describe("AIDiffView", () => {
  it("renders the badge and label in text mode", () => {
    render(wrap(<AIDiffView viewModel={textVm} state="suggested" />));
    expect(screen.getByText("Sentence")).toBeTruthy();
    expect(screen.getByText("Suggested")).toBeTruthy();
  });

  it("announces a screen-reader summary on the group", () => {
    render(wrap(<AIDiffView viewModel={textVm} state="suggested" />));
    const group = screen.getByRole("group");
    expect(group.getAttribute("aria-label")).toContain("addition");
    expect(group.getAttribute("aria-label")).toContain("removal");
  });

  it("renders before/after columns in field mode (no inline diff)", () => {
    const fieldVm: AIDiffViewModel = {
      id: "kb-role",
      mode: "field",
      segments: [],
      originalFull: "Mentor",
      suggestedFull: "Wise mentor",
      label: "Role",
      provisional: false,
    };
    render(wrap(<AIDiffView viewModel={fieldVm} state="accepted" />));
    expect(screen.getByText("Original")).toBeTruthy();
    expect(screen.getByText("Suggested")).toBeTruthy();
    expect(screen.getByText("Mentor")).toBeTruthy();
    expect(screen.getByText("Wise mentor")).toBeTruthy();
  });

  it("shows a provisional indicator when viewModel.provisional is true", () => {
    const provVm: AIDiffViewModel = { ...textVm, provisional: true };
    render(wrap(<AIDiffView viewModel={provVm} state="suggested" />));
    expect(screen.getByText("Provisional")).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pnpm test components/shared/ai-diff/__tests__/AIDiffView.test.tsx
```
Expected: FAIL — module not found.

- [ ] **Step 3: Write the component**

`packages/web/components/shared/ai-diff/AIDiffView.tsx`:
```tsx
"use client";

import { useTranslations } from "next-intl";
import type { AIDiffState, AIDiffViewModel } from "@/lib/ai-diff/contracts";
import { AIDiffBadge } from "./AIDiffBadge";
import { AIDiffSegmentList } from "./AIDiffSegmentList";

interface AIDiffViewProps {
  readonly viewModel: AIDiffViewModel;
  /** Author-control state. Caller-owned — the view never starts AI work. */
  readonly state: AIDiffState;
}

/**
 * Shared, accessible AI-diff surface (CR-AUFG-07-18).
 *
 * - `text` mode: inline diff via {@link AIDiffSegmentList} (Rewrite, Co-Author).
 * - `field` mode: whole-value before/after columns (KB Enhance) — no prose diff.
 *
 * The group carries an sr-only summary of additions/removals so screen readers
 * announce change volume, not just per-segment labels.
 */
export function AIDiffView({ viewModel: vm, state }: AIDiffViewProps) {
  const t = useTranslations("studio");
  const added = vm.segments.filter((s) => s.kind === "added").length;
  const removed = vm.segments.filter((s) => s.kind === "removed").length;

  return (
    <div
      role="group"
      aria-label={t("aiDiff.srSummary", { added, removed })}
      className="space-y-2"
    >
      <div className="flex flex-wrap items-center gap-2">
        {vm.label !== null && (
          <span className="text-xs font-medium text-muted-foreground">{vm.label}</span>
        )}
        <AIDiffBadge state={state} />
        {vm.provisional && (
          <span className="text-xs italic text-muted-foreground">{t("aiDiff.provisional")}</span>
        )}
      </div>

      {vm.mode === "text" ? (
        <div className="text-sm leading-relaxed">
          <AIDiffSegmentList segments={vm.segments} />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          <div>
            <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">
              {t("aiActions.original")}
            </div>
            <div className="text-sm text-muted-foreground whitespace-pre-wrap line-through opacity-70">
              {vm.originalFull || <span className="italic not-italic">{t("kb.empty")}</span>}
            </div>
          </div>
          <div>
            <div className="text-xs font-medium text-green-600 dark:text-green-400 uppercase tracking-wider mb-1">
              {t("aiActions.suggested")}
            </div>
            <div className="text-sm whitespace-pre-wrap">{vm.suggestedFull}</div>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pnpm test components/shared/ai-diff/__tests__/AIDiffView.test.tsx
```
Expected: PASS — 4 tests.

---

## Task 7: Rewrite adapter

**Files:**
- Create: `packages/web/lib/ai-diff/adapters/rewrite.ts`
- Test: `packages/web/lib/ai-diff/__tests__/adapters/rewrite.test.ts`

- [ ] **Step 1: Write the failing test**

`packages/web/lib/ai-diff/__tests__/adapters/rewrite.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { rewriteAdapter } from "../../adapters/rewrite";

describe("rewriteAdapter", () => {
  it("builds a text-mode view model with segmented diff", () => {
    const vm = rewriteAdapter("the cat", "the dog", "Sentence", false);
    expect(vm.mode).toBe("text");
    expect(vm.originalFull).toBe("the cat");
    expect(vm.suggestedFull).toBe("the dog");
    expect(vm.label).toBe("Sentence");
    expect(vm.provisional).toBe(false);
    expect(vm.segments.some((s) => s.kind === "added")).toBe(true);
    expect(vm.segments.some((s) => s.kind === "removed")).toBe(true);
  });

  it("accepts a null label", () => {
    const vm = rewriteAdapter("a", "b", null, true);
    expect(vm.label).toBeNull();
    expect(vm.provisional).toBe(true);
  });

  it("produces a stable id derived from the suggestion", () => {
    const vm = rewriteAdapter("a", "suggestion text", null, false);
    expect(vm.id).toContain("rewrite-");
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pnpm test lib/ai-diff/__tests__/adapters/rewrite.test.ts
```
Expected: FAIL — module not found.

- [ ] **Step 3: Write the adapter**

`packages/web/lib/ai-diff/adapters/rewrite.ts`:
```ts
import type { AIDiffViewModel } from "../contracts";
import { segmentize } from "../segmentize";

/**
 * Build a text-mode {@link AIDiffViewModel} for a single Rewrite alternative.
 *
 * Takes primitives only (no component import) so `lib/ai-diff` never depends on
 * `components/` (RULE-07 direction: components → lib, never lib → components).
 */
export function rewriteAdapter(
  original: string,
  suggestion: string,
  label: string | null,
  provisional: boolean,
): AIDiffViewModel {
  return {
    id: `rewrite-${suggestion.slice(0, 32)}`,
    mode: "text",
    segments: segmentize(original, suggestion),
    originalFull: original,
    suggestedFull: suggestion,
    label,
    provisional,
  };
}
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pnpm test lib/ai-diff/__tests__/adapters/rewrite.test.ts
```
Expected: PASS — 3 tests.

---

## Task 8: Co-Author adapter

**Files:**
- Create: `packages/web/lib/ai-diff/adapters/coauthor.ts`
- Test: `packages/web/lib/ai-diff/__tests__/adapters/coauthor.test.ts`

- [ ] **Step 1: Write the failing test**

`packages/web/lib/ai-diff/__tests__/adapters/coauthor.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { coAuthorChangeAdapter } from "../../adapters/coauthor";
import type { ChangeDetail } from "@/lib/api/coauthor";

const change: ChangeDetail = {
  id: "ch-1",
  change_type: "word_choice",
  original_text: "quick",
  revised_text: "swift",
  index: 0,
};

describe("coAuthorChangeAdapter", () => {
  it("maps a ChangeDetail to a text-mode view model", () => {
    const vm = coAuthorChangeAdapter(change);
    expect(vm.id).toBe("ch-1");
    expect(vm.mode).toBe("text");
    expect(vm.originalFull).toBe("quick");
    expect(vm.suggestedFull).toBe("swift");
    expect(vm.label).toBe("word_choice");
    expect(vm.provisional).toBe(false);
  });

  it("segments the original→revised text", () => {
    const vm = coAuthorChangeAdapter(change);
    expect(vm.segments.some((s) => s.kind === "removed")).toBe(true);
    expect(vm.segments.some((s) => s.kind === "added")).toBe(true);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pnpm test lib/ai-diff/__tests__/adapters/coauthor.test.ts
```
Expected: FAIL — module not found.

- [ ] **Step 3: Write the adapter**

`packages/web/lib/ai-diff/adapters/coauthor.ts`:
```ts
import type { ChangeDetail } from "@/lib/api/coauthor";
import type { AIDiffViewModel } from "../contracts";
import { segmentize } from "../segmentize";

/** Map a Co-Author {@link ChangeDetail} to a text-mode {@link AIDiffViewModel}. */
export function coAuthorChangeAdapter(change: ChangeDetail): AIDiffViewModel {
  return {
    id: change.id,
    mode: "text",
    segments: segmentize(change.original_text, change.revised_text),
    originalFull: change.original_text,
    suggestedFull: change.revised_text,
    label: change.change_type,
    provisional: false,
  };
}
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pnpm test lib/ai-diff/__tests__/adapters/coauthor.test.ts
```
Expected: PASS — 2 tests.

---

## Task 9: KB Enhance adapter (field mode)

**Files:**
- Create: `packages/web/lib/ai-diff/adapters/kb-enhance.ts`
- Test: `packages/web/lib/ai-diff/__tests__/adapters/kb-enhance.test.ts`

- [ ] **Step 1: Write the failing test**

`packages/web/lib/ai-diff/__tests__/adapters/kb-enhance.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { kbEnhanceFieldAdapter } from "../../adapters/kb-enhance";
import type { KBEnhancementResult } from "@/lib/api/kb-sessions";

const enhancement: KBEnhancementResult = {
  field_key: "role",
  original: "Mentor",
  suggested: "Wise mentor and guide",
  reasoning: "Adds depth",
};

describe("kbEnhanceFieldAdapter", () => {
  it("builds a FIELD-mode view model (no inline prose diff)", () => {
    const vm = kbEnhanceFieldAdapter(enhancement, "Role");
    expect(vm.mode).toBe("field");
    expect(vm.id).toBe("role");
    expect(vm.originalFull).toBe("Mentor");
    expect(vm.suggestedFull).toBe("Wise mentor and guide");
    expect(vm.label).toBe("Role");
  });

  it("NEVER produces inline segments (structured fields are not prose diffs)", () => {
    const vm = kbEnhanceFieldAdapter(enhancement, "Role");
    expect(vm.segments).toEqual([]);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pnpm test lib/ai-diff/__tests__/adapters/kb-enhance.test.ts
```
Expected: FAIL — module not found.

- [ ] **Step 3: Write the adapter**

`packages/web/lib/ai-diff/adapters/kb-enhance.ts`:
```ts
import type { KBEnhancementResult } from "@/lib/api/kb-sessions";
import type { AIDiffViewModel } from "../contracts";

/**
 * Map a KB enhancement to a FIELD-mode {@link AIDiffViewModel}.
 *
 * Structured fields are compared as whole values (before/after), NEVER as an
 * inline prose diff — per CR-AUFG-07-18 AC #3. Invariant: `segments` is empty.
 */
export function kbEnhanceFieldAdapter(
  enhancement: KBEnhancementResult,
  fieldLabel: string,
): AIDiffViewModel {
  return {
    id: enhancement.field_key,
    mode: "field",
    segments: [],
    originalFull: enhancement.original,
    suggestedFull: enhancement.suggested,
    label: fieldLabel,
    provisional: false,
  };
}
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pnpm test lib/ai-diff/__tests__/adapters/kb-enhance.test.ts
```
Expected: PASS — 2 tests.

---

## Task 10: Beta Reader adapter (honest null — RULE-20)

**Files:**
- Create: `packages/web/lib/ai-diff/adapters/beta-reader.ts`
- Test: `packages/web/lib/ai-diff/__tests__/adapters/beta-reader.test.ts`

- [ ] **Step 1: Write the failing test**

`packages/web/lib/ai-diff/__tests__/adapters/beta-reader.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { betaReaderGroundedAdapter, isBetaReaderGrounded } from "../../adapters/beta-reader";
import type { BetaFeedbackItem } from "@/lib/api/analysis";

const item: BetaFeedbackItem = {
  category: "pacing",
  severity: "moderate",
  location: "para 3",
  title: "Slow middle",
  description: "The middle drags.",
  suggestion: "Consider tightening the description.",
  text_excerpt: "The long winding road stretched...",
};

describe("betaReaderGroundedAdapter", () => {
  it("returns null for current-schema feedback (no grounded A→B pair)", () => {
    expect(betaReaderGroundedAdapter(item)).toBeNull();
  });

  it("isBetaReaderGrounded is false for current schema", () => {
    expect(isBetaReaderGrounded(item)).toBe(false);
  });

  it("returns null even when suggestion + text_excerpt are both present", () => {
    // suggestion is prose advice, NOT a verbatim replacement — must NOT be
    // treated as a grounded revision (CR-AUFG-07-18 out-of-scope: fabrication).
    expect(betaReaderGroundedAdapter(item)).toBeNull();
  });

  it("returns null for a minimal feedback item too", () => {
    const minimal: BetaFeedbackItem = {
      category: "prose",
      severity: "minor",
      location: null,
      title: "Wordy",
      description: "Verbose sentence.",
      suggestion: null,
      text_excerpt: null,
    };
    expect(betaReaderGroundedAdapter(minimal)).toBeNull();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pnpm test lib/ai-diff/__tests__/adapters/beta-reader.test.ts
```
Expected: FAIL — module not found.

- [ ] **Step 3: Write the adapter**

`packages/web/lib/ai-diff/adapters/beta-reader.ts`:
```ts
import type { BetaFeedbackItem } from "@/lib/api/analysis";
import type { AIDiffViewModel } from "../contracts";

/**
 * A feedback item is "grounded" ONLY when it carries a verbatim original
 * passage AND a concrete replacement text (a real A→B revision).
 *
 * The current `BetaFeedbackItem` schema has `text_excerpt` (a passage) and
 * `suggestion` (prose advice) — but `suggestion` is NOT a verbatim
 * replacement, so the pair does not form a grounded revision. Therefore
 * `isBetaReaderGrounded` returns `false` for every live item and
 * {@link betaReaderGroundedAdapter} returns `null`: feedback stays feedback,
 * and no diff is fabricated.
 *
 * RULE-20 (no half implementation): returning `null` here is the COMPLETE,
 * honest behaviour for the current data. When the backend later adds explicit
 * original/revised text spans (a coordinated RULE-17 change), update this
 * predicate and the adapter together.
 */
export function isBetaReaderGrounded(_item: BetaFeedbackItem): boolean {
  // No dedicated original/revised text-pair field exists in the schema today.
  return false;
}

/**
 * Convert a beta-reader feedback item to a diff view model, or `null` when the
 * item is not a grounded revision. Callers MUST render `null` as feedback, not
 * as a diff.
 */
export function betaReaderGroundedAdapter(
  item: BetaFeedbackItem,
): AIDiffViewModel | null {
  if (!isBetaReaderGrounded(item)) return null;
  // Forward-compatible branch — unreachable for the live schema. When grounded
  // fields are added, build a text-mode view model here from those fields.
  return null;
}
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pnpm test lib/ai-diff/__tests__/adapters/beta-reader.test.ts
```
Expected: PASS — 4 tests.

---

## Task 11: Barrel `index.ts`

**Files:**
- Create: `packages/web/lib/ai-diff/index.ts`
- Test: extend `packages/web/lib/ai-diff/__tests__/contracts.test.ts` with a barrel import check

- [ ] **Step 1: Add a barrel-import test**

Append to `packages/web/lib/ai-diff/__tests__/contracts.test.ts`:
```ts
import {
  segmentize,
  rewriteAdapter,
  coAuthorChangeAdapter,
  kbEnhanceFieldAdapter,
  betaReaderGroundedAdapter,
  isBetaReaderGrounded,
} from "../index";
import type { AIDiffViewModel, AIDiffState, AIDiffSegment, AIDiffMode } from "../index";

describe("ai-diff barrel", () => {
  it("re-exports every public symbol", () => {
    expect(typeof segmentize).toBe("function");
    expect(typeof rewriteAdapter).toBe("function");
    expect(typeof coAuthorChangeAdapter).toBe("function");
    expect(typeof kbEnhanceFieldAdapter).toBe("function");
    expect(typeof betaReaderGroundedAdapter).toBe("function");
    expect(typeof isBetaReaderGrounded).toBe("function");
    // type-only imports compile when the barrel exports them:
    const _types: AIDiffViewModel | AIDiffState | AIDiffSegment | AIDiffMode = "suggested";
    expect(_types).toBe("suggested");
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pnpm test lib/ai-diff/__tests__/contracts.test.ts
```
Expected: FAIL — `Cannot find module '../index'`.

- [ ] **Step 3: Write the barrel**

`packages/web/lib/ai-diff/index.ts`:
```ts
/** CR-AUFG-07-18 — shared AI diff vocabulary. Public surface. */

export type {
  AIDiffMode,
  AIDiffSegment,
  AIDiffSegmentKind,
  AIDiffState,
  AIDiffViewModel,
} from "./contracts";

export { segmentize } from "./segmentize";

export { rewriteAdapter } from "./adapters/rewrite";
export { coAuthorChangeAdapter } from "./adapters/coauthor";
export { kbEnhanceFieldAdapter } from "./adapters/kb-enhance";
export { betaReaderGroundedAdapter, isBetaReaderGrounded } from "./adapters/beta-reader";
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pnpm test lib/ai-diff/__tests__/contracts.test.ts
```
Expected: PASS (original 4 + barrel 1 = 5 tests).

- [ ] **Step 5: Type-check the new lib**

```bash
pnpm type-check
```
Expected: exit code `0`.

---

## Task 12: Refactor `InlineDiff.tsx` (DRY + a11y)

**Files:**
- Modify: `packages/web/components/studio/editor/InlineDiff.tsx`
- Verify (grep): no external consumer of `computeDiffElements`
- Test: `packages/web/components/studio/editor/__tests__/InlineDiff.test.tsx` (new — there is none today)

- [ ] **Step 1: Check consumers of the exported `computeDiffElements`**

Run (from repo root):
```bash
rg -n "computeDiffElements" --type ts --type tsx packages
```
Expected output: only `packages/web/components/studio/editor/InlineDiff.tsx` (self-reference). If ANY other file imports it, STOP and keep `computeDiffElements` as a re-export in Step 3 instead of removing it.

- [ ] **Step 2: Write the failing test**

`packages/web/components/studio/editor/__tests__/InlineDiff.test.tsx`:
```tsx
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { NextIntlClientProvider } from "next-intl";
import { InlineDiff } from "../InlineDiff";

const messages = { studio: { aiDiff: { added: "Added", removed: "Removed" } } };

function wrap(ui: React.ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages as never}>
      {ui}
    </NextIntlClientProvider>
  );
}

describe("InlineDiff (refactored)", () => {
  it("renders additions in <ins> and removals in <del> (a11y via shared renderer)", () => {
    const { container } = render(wrap(<InlineDiff original="cat" alternative="dog" />));
    expect(container.querySelector("ins")).not.toBeNull();
    expect(container.querySelector("del")).not.toBeNull();
  });

  it("has visible +/- markers (not color alone)", () => {
    const { container } = render(wrap(<InlineDiff original="cat" alternative="dog" />));
    expect(container.querySelectorAll("[aria-hidden='true']").length).toBeGreaterThanOrEqual(2);
  });
});
```

- [ ] **Step 3: Refactor `InlineDiff.tsx`**

If Step 1 found NO external consumer, replace the entire file with:
```tsx
"use client";

import { AIDiffSegmentList } from "@/components/shared/ai-diff/AIDiffSegmentList";
import { segmentize } from "@/lib/ai-diff/segmentize";

interface InlineDiffProps {
  readonly original: string;
  readonly alternative: string;
}

/**
 * Inline text-only diff facade. Delegates to the shared {@link segmentize}
 * algorithm and accessible {@link AIDiffSegmentList} renderer (CR-AUFG-07-18).
 *
 * Kept as a low-level inline-text primitive (distinct responsibility from the
 * full {@link AIDiffView} review surface which adds badges/state).
 */
export function InlineDiff({ original, alternative }: InlineDiffProps) {
  const segments = segmentize(original, alternative);
  return <AIDiffSegmentList segments={segments} />;
}
```

If Step 1 found an external consumer of `computeDiffElements`, additionally append this back-compat shim (keep the ReactNode export):
```tsx
import type { ReactNode } from "react";
/** @deprecated use segmentize() + AIDiffSegmentList via InlineDiff. Kept for back-compat. */
export function computeDiffElements(original: string, alternative: string): ReactNode[] {
  // Render InlineDiff to a static element array is not feasible without a host;
  // callers should migrate to <InlineDiff/> or <AIDiffView/>. This shim returns
  // the segments wrapped minimally so legacy call sites still compile.
  return segmentize(original, alternative).map((s, i) => {
    if (s.kind === "added") return <span key={`a-${i}`}>{s.text}</span>;
    if (s.kind === "removed") return <span key={`r-${i}`}>{s.text}</span>;
    return <span key={`u-${i}`}>{s.text}</span>;
  });
}
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pnpm test components/studio/editor/__tests__/InlineDiff.test.tsx
```
Expected: PASS — 2 tests.

- [ ] **Step 5: Ensure no regression in the existing rewrite test**

```bash
pnpm test components/studio/editor/__tests__/RewriteSuggestionModal.test.tsx
```
Expected: PASS (RewriteSuggestionModal still uses `<InlineDiff>` until Task 13).

---

## Task 13: Adopt `AIDiffView` in `RewriteSuggestionModal`

**Files:**
- Modify: `packages/web/components/studio/editor/RewriteSuggestionModal.tsx`
- Test: `packages/web/components/studio/editor/__tests__/RewriteSuggestionModal.test.tsx` (extend; keyboard preserved)

- [ ] **Step 1: Add/extend a test asserting shared-primitive usage + keyboard preservation**

Append to `packages/web/components/studio/editor/__tests__/RewriteSuggestionModal.test.tsx` (inside the existing `describe` or a new one; reuse the file's existing render helpers):
```tsx
import { fireEvent } from "@testing-library/react";
import { rewriteAdapter } from "@/lib/ai-diff/adapters/rewrite";

it("renders each alternative through the shared AIDiffView (semantic <ins>/<del>)", () => {
  // Use the file's existing render setup; this is an additive assertion.
  const { container } = renderModalWithSuggestion({
    original: "the cat",
    suggestions: ["the dog"],
    labels: ["Sentence"],
  });
  expect(container.querySelector("ins")).not.toBeNull();
  expect(container.querySelector("del")).not.toBeNull();
});

it("still triggers onAccept on Ctrl+Enter (CR-AUFG-07-13 preserved)", () => {
  const onAccept = vi.fn();
  const { container } = renderModalWithSuggestion({
    original: "a",
    suggestions: ["b"],
    labels: [],
    onAccept,
  });
  fireEvent.keyDown(container.ownerDocument.body, {
    key: "Enter",
    ctrlKey: true,
  });
  expect(onAccept).toHaveBeenCalled();
});
```
> If the existing test file lacks a `renderModalWithSuggestion` helper, inline the props the existing tests already use (see the file's current `render(...)` calls) — do not invent new setup. The assertion is: after adoption, `<ins>`/`<del>` appear AND Ctrl+Enter still calls `onAccept`.

- [ ] **Step 2: Run the test to verify it fails (ins/del absent until adoption)**

```bash
pnpm test components/studio/editor/__tests__/RewriteSuggestionModal.test.tsx
```
Expected: the `<ins>/<del>` assertion FAILS (current InlineDiff uses `<span>`). The keyboard test PASSES already.

- [ ] **Step 3: Adopt `AIDiffView` in the component**

In `packages/web/components/studio/editor/RewriteSuggestionModal.tsx`:

Replace the import:
```tsx
import { InlineDiff } from "./InlineDiff";
```
with:
```tsx
import { AIDiffView } from "@/components/shared/ai-diff/AIDiffView";
import { rewriteAdapter } from "@/lib/ai-diff/adapters/rewrite";
```

Replace the diff render block:
```tsx
                  <div className="flex-1">
                    <InlineDiff original={aiSuggestion.original} alternative={suggestion} />
                  </div>
```
with:
```tsx
                  <div className="flex-1">
                    <AIDiffView
                      viewModel={rewriteAdapter(
                        aiSuggestion.original,
                        suggestion,
                        aiSuggestion.labels[index] ?? null,
                        isRewriteStreaming,
                      )}
                      state="suggested"
                    />
                  </div>
```

Leave the `useEffect` keyboard block (`isApplyShortcut(e)` → `onApply`, Escape handling) **unchanged**.

- [ ] **Step 4: Run the full test file**

```bash
pnpm test components/studio/editor/__tests__/RewriteSuggestionModal.test.tsx
```
Expected: PASS — including the new `<ins>/<del>` assertion AND the Ctrl+Enter keyboard test.

- [ ] **Step 5: Lint + type-check**

```bash
pnpm lint:check
pnpm type-check
```
Expected: both exit code `0`.

---

## Task 14: Adopt `AIDiffView` in `ChangeReview` + fix hard-coded aria-labels

**Files:**
- Modify: `packages/web/components/studio/editor/ChangeReview.tsx`
- Test: `packages/web/components/studio/editor/__tests__/ChangeReview.test.tsx` (new — there is none today; the existing coverage is via `CoAuthorReviewPhase` tests)
- Verify + modify i18n: remove `studio.changeReview.*` after confirming no remaining consumer

- [ ] **Step 1: Verify consumers of `changeReview.*` keys**

Run (from repo root):
```bash
rg -n 'changeReview\.' packages/web --type ts --type tsx
rg -n '"changeReview"' packages/i18n/messages
```
Expected: usages only inside `ChangeReview.tsx`; definitions only in the three `studio.json` files. If any other consumer exists, STOP and keep the keys.

- [ ] **Step 2: Write the failing test**

`packages/web/components/studio/editor/__tests__/ChangeReview.test.tsx`:
```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { NextIntlClientProvider } from "next-intl";
import { ChangeReview } from "../ChangeReview";
import type { ChangeDetail } from "@/lib/api/coauthor";

const messages = {
  studio: {
    aiActions: { suggested: "Suggested", accept: "Accept", reject: "Reject" },
    aiDiff: {
      accepted: "Accepted",
      rejectChange: "Reject change",
      acceptChange: "Accept change",
      added: "Added",
      removed: "Removed",
      srSummary: "{added} addition(s) and {removed} removal(s)",
    },
  },
};

const change: ChangeDetail = {
  id: "ch-1",
  change_type: "word_choice",
  original_text: "quick",
  revised_text: "swift",
  index: 0,
};

function wrap(ui: React.ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages as never}>
      {ui}
    </NextIntlClientProvider>
  );
}

describe("ChangeReview (adopted)", () => {
  it("renders the shared AIDiffView with ins/del", () => {
    const { container } = render(wrap(<ChangeReview change={change} isAccepted={false} />));
    expect(container.querySelector("ins")).not.toBeNull();
    expect(container.querySelector("del")).not.toBeNull();
  });

  it("uses i18n aria-labels (no hard-coded English)", () => {
    render(wrap(<ChangeReview change={change} isAccepted={false} onToggle={vi.fn()} />));
    const toggle = screen.getByRole("button", { name: "Accept change" });
    expect(toggle).toBeTruthy();
  });

  it("reflects accepted state in the badge", () => {
    render(wrap(<ChangeReview change={change} isAccepted={true} onToggle={vi.fn()} />));
    expect(screen.getByText("Accepted")).toBeTruthy();
  });

  it("invokes onToggle with the change id", () => {
    const onToggle = vi.fn();
    render(wrap(<ChangeReview change={change} isAccepted={false} onToggle={onToggle} />));
    fireEvent.click(screen.getByRole("button", { name: "Accept change" }));
    expect(onToggle).toHaveBeenCalledWith("ch-1");
  });
});
```

- [ ] **Step 3: Run the test to verify it fails**

```bash
pnpm test components/studio/editor/__tests__/ChangeReview.test.tsx
```
Expected: FAIL — `<ins>`/`<del>` absent and aria-label is hard-coded English.

- [ ] **Step 4: Rewrite `ChangeReview.tsx`**

Replace the entire file with:
```tsx
"use client";

import { Check, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { AIDiffView } from "@/components/shared/ai-diff/AIDiffView";
import { coAuthorChangeAdapter } from "@/lib/ai-diff/adapters/coauthor";
import type { AIDiffState } from "@/lib/ai-diff/contracts";
import type { ChangeDetail } from "@/lib/api/coauthor";

export interface ChangeReviewProps {
  readonly change: ChangeDetail;
  readonly isAccepted: boolean;
  readonly onToggle?: (changeId: string) => void;
  readonly readOnly?: boolean;
}

export function ChangeReview({
  change,
  isAccepted,
  onToggle,
  readOnly = false,
}: ChangeReviewProps) {
  const t = useTranslations("studio");
  const viewModel = coAuthorChangeAdapter(change);
  const state: AIDiffState = isAccepted ? "accepted" : "suggested";

  return (
    <div
      className={`rounded-lg border transition-all ${
        isAccepted ? "border-green-500/50 bg-green-500/5" : "border-border hover:border-primary/30"
      }`}
    >
      <div className="flex items-center justify-between px-3 py-2 border-b border-border/50">
        <span className="text-xs text-muted-foreground">#{change.index + 1}</span>
        {!readOnly && onToggle && (
          <button
            type="button"
            onClick={() => onToggle(change.id)}
            aria-label={isAccepted ? t("aiDiff.rejectChange") : t("aiDiff.acceptChange")}
            className={`flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-md transition-all ${
              isAccepted
                ? "bg-green-500/10 text-green-600 dark:text-green-400 hover:bg-green-500/20"
                : "bg-muted text-muted-foreground hover:bg-accent"
            }`}
          >
            {isAccepted ? (
              <>
                <Check className="w-3 h-3" />
                <span>{t("aiActions.accept")}</span>
              </>
            ) : (
              <>
                <X className="w-3 h-3" />
                <span>{t("aiActions.reject")}</span>
              </>
            )}
          </button>
        )}
      </div>

      <div className="px-3 py-2.5">
        <AIDiffView viewModel={viewModel} state={state} />
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Run the new test**

```bash
pnpm test components/studio/editor/__tests__/ChangeReview.test.tsx
```
Expected: PASS — 4 tests.

- [ ] **Step 6: Run the existing Co-Author review tests (no regression)**

```bash
pnpm test components/studio/editor/__tests__/CoAuthorReviewPhase.keyboard.test.tsx
pnpm test components/studio/editor/__tests__/CoAuthorPanel.keyboard.test.tsx
```
Expected: PASS — keyboard wiring unchanged.

- [ ] **Step 7: Remove the now-unused `studio.changeReview.*` keys (DE/EN/FR)**

Delete the `changeReview` block from each of:
- `packages/i18n/messages/en/studio.json`
- `packages/i18n/messages/de/studio.json`
- `packages/i18n/messages/fr/studio.json`

Each block looks like:
```json
  "changeReview": {
    "accepted": "…",
    "rejected": "…",
    "original": "…",
    "revised": "…"
  },
```

- [ ] **Step 8: Validate i18n parity after removal**

```bash
npx tsx scripts/validate-i18n.ts
```
Expected: exit code `0`, no `[ERROR]`.

---

## Task 15: Adopt `AIDiffView` (field mode) in `EnhanceReviewCard`

**Files:**
- Modify: `packages/web/components/studio/kb/_components/EnhanceReviewCard.tsx`
- Test: `packages/web/components/studio/kb/__tests__/KBEnhanceReview.test.tsx` (extend; existing)

- [ ] **Step 1: Add an additive assertion to the existing KBEnhanceReview test**

In `packages/web/components/studio/kb/__tests__/KBEnhanceReview.test.tsx`, add (using the file's existing render helpers / message setup):
```tsx
it("renders the before/after comparison via the shared AIDiffView (field mode)", () => {
  const { container } = renderReviewWithEnhancement({
    field_key: "role",
    original: "Mentor",
    suggested: "Wise mentor",
    reasoning: "Adds depth",
  });
  // Field mode renders whole-value columns (Original/Suggested labels),
  // and never inline <ins>/<del> segments.
  expect(container.querySelector("ins")).toBeNull();
  expect(container.querySelector("del")).toBeNull();
});
```
> Adapt `renderReviewWithEnhancement` to the file's existing setup. The key assertion: field mode produces NO `<ins>`/`<del>` (no fabricated prose diff over structured fields).

- [ ] **Step 2: Run the test to verify it fails (current card uses a grid, no AIDiffView)**

```bash
pnpm test components/studio/kb/__tests__/KBEnhanceReview.test.tsx
```
Expected: the new assertion may pass vacuously today (no `<ins>`/`<del>` currently either). To make it meaningful, also assert the shared labels are used:
```tsx
  expect(screen.getByText("Original")).toBeTruthy();   // aiActions.original via AIDiffView
  expect(screen.getByText("Suggested")).toBeTruthy();  // aiActions.suggested via AIDiffView
```
Re-run; expected FAIL until adoption (current card uses `kb.original`/`kb.suggested` which may or may not render those exact strings — verify against the current i18n). The test encodes the intended post-adoption behaviour.

- [ ] **Step 3: Rewrite the comparison block in `EnhanceReviewCard.tsx`**

Replace the import block:
```tsx
import type { KBEnhancementResult } from "@/lib/api/kb-sessions";
```
with:
```tsx
import { AIDiffView } from "@/components/shared/ai-diff/AIDiffView";
import { kbEnhanceFieldAdapter } from "@/lib/ai-diff/adapters/kb-enhance";
import type { AIDiffState } from "@/lib/ai-diff/contracts";
import type { KBEnhancementResult } from "@/lib/api/kb-sessions";
```

Replace the before/after comparison `<div className="grid …"> … </div>` block (the whole two-column grid) with:
```tsx
      {/* Before/After comparison via shared field-mode AIDiffView */}
      <div className="px-4 py-3">
        <AIDiffView
          viewModel={kbEnhanceFieldAdapter(enhancement, fieldLabel)}
          state={isSelected ? ("accepted" satisfies AIDiffState) : "suggested"}
        />
      </div>
```

Leave the field header (checkbox + `kb.willApply`/`kb.skipped`), reasoning block, and accept/reject buttons **unchanged** (those are KB-specific affordances).

- [ ] **Step 4: Run the KB test suite**

```bash
pnpm test components/studio/kb/__tests__/KBEnhanceReview.test.tsx
```
Expected: PASS — including the new shared-primitive assertions.

- [ ] **Step 5: Lint + type-check + i18n**

```bash
pnpm lint:check
pnpm type-check
npx tsx scripts/validate-i18n.ts
```
Expected: all exit code `0`.

---

## Task 16: Beta Reader — honest adapter wiring (no UI change)

**Files:**
- Create test: `packages/web/components/studio/analysis/__tests__/beta-reader-diff-honesty.test.tsx`
- Verify (grep): no fabricated diff rendering introduced

> This task deliberately does NOT modify `BetaReaderPanel.tsx`. The adapter from Task 10 returns `null` for every live feedback item, so the panel keeps rendering feedback (CR-AUFG-07-18 AC #4 + out-of-scope "Fabricating Beta Reader text spans"). The deliverable is a regression test proving the honesty contract.

- [ ] **Step 1: Write the honesty regression test**

`packages/web/components/studio/analysis/__tests__/beta-reader-diff-honesty.test.tsx`:
```tsx
import { describe, expect, it } from "vitest";
import { betaReaderGroundedAdapter } from "@/lib/ai-diff/adapters/beta-reader";
import type { BetaFeedbackItem, BetaReaderResponse } from "@/lib/api/analysis";

const feedback: BetaFeedbackItem[] = [
  {
    category: "pacing",
    severity: "moderate",
    location: "para 2",
    title: "Slow",
    description: "Drags.",
    suggestion: "Tighten the prose.",
    text_excerpt: "The long winding road stretched on and on.",
  },
  {
    category: "prose",
    severity: "minor",
    location: null,
    title: "Wordy",
    description: "Verbose.",
    suggestion: null,
    text_excerpt: null,
  },
];

describe("Beta Reader diff honesty (CR-AUFG-07-18)", () => {
  it("produces NO diff view model for any current-schema feedback item", () => {
    for (const item of feedback) {
      expect(betaReaderGroundedAdapter(item)).toBeNull();
    }
  });

  it("a full BetaReaderResponse yields zero grounded diffs", () => {
    const response: BetaReaderResponse = {
      novel_id: "n",
      chapter_ids: ["c1"],
      total_word_count: 1000,
      strengths: [],
      feedback,
      questions: [],
      overall: {
        summary: "ok",
        reader_engagement: 5,
        emotional_impact: 5,
        pacing_score: 5,
        prose_quality: 5,
        plot_progression: 5,
        character_development: 5,
      },
      analyzed_at: "2026-06-22T00:00:00Z",
      cache_key: "k",
    };
    const groundedCount = response.feedback
      .map(betaReaderGroundedAdapter)
      .filter((vm) => vm !== null).length;
    expect(groundedCount).toBe(0);
  });
});
```

- [ ] **Step 2: Run the test**

```bash
pnpm test components/studio/analysis/__tests__/beta-reader-diff-honesty.test.tsx
```
Expected: PASS — 2 tests (proving no diff is fabricated for current data).

- [ ] **Step 3: Confirm BetaReaderPanel is unchanged**

Run (from repo root):
```bash
git status --short packages/web/components/studio/analysis/BetaReaderPanel.tsx
```
Expected: no output (file not modified by this task). If it appears modified, revert — this task must not touch the panel.

---

## Task 17: AI Operation Inventory — reference the shared primitive

**Files:**
- Modify: `scripts/checks/ai_operation_inventory.yaml`

- [ ] **Step 1: Add an optional `shared_diff_view` field to the 4 touched operations**

In `scripts/checks/ai_operation_inventory.yaml`, add the following line to each of these four operations (`writing.rewrite`, `writing.co_author`, `kb.enhance`, `analysis.beta_reader`), placed immediately after their `partial_output:` line:

For `writing.rewrite` (after `partial_output: "Streaming alternatives preserved until accept/reject"`):
```yaml
    shared_diff_view: "packages/web/components/shared/ai-diff/AIDiffView via lib/ai-diff/adapters/rewrite.ts (CR-AUFG-07-18)"
```

For `writing.co_author` (after `partial_output: "Per-changelist acceptance map preserves partial output"`):
```yaml
    shared_diff_view: "packages/web/components/shared/ai-diff/AIDiffView via lib/ai-diff/adapters/coauthor.ts (CR-AUFG-07-18)"
```

For `kb.enhance` (after `partial_output: "Before/after comparison preserved per field"`):
```yaml
    shared_diff_view: "packages/web/components/shared/ai-diff/AIDiffView (field mode) via lib/ai-diff/adapters/kb-enhance.ts (CR-AUFG-07-18)"
```

For `analysis.beta_reader` (after `partial_output: "Feedback preserved on connection loss"`):
```yaml
    shared_diff_view: "packages/web/lib/ai-diff/adapters/beta-reader.ts returns null today (no grounded A→B pair); feedback stays feedback (CR-AUFG-07-18 RULE-20)"
```

- [ ] **Step 2: Confirm the inventory gate still passes (optional field, checker validates required fields only)**

```bash
just check-ai-ux
```
Expected: `Violations: 0`. (Check 10 validates the 16 required fields; an additional optional `shared_diff_view` field does not violate the schema.)

- [ ] **Step 3: Sanity-check the YAML parses**

```bash
uv run python -c "import yaml; yaml.safe_load(open('scripts/checks/ai_operation_inventory.yaml')); print('ok')"
```
Expected: prints `ok`.

---

## Task 18: Full gate run (validation)

> Run every gate from the repo root unless noted. All must be green before declaring the plan complete.

- [ ] **Step 1: Frontend unit/component tests (full suite)**

From `packages/web`:
```bash
pnpm test
```
Expected: exit code `0`, all tests pass (shared primitive + adapters + adopted surfaces + existing flows).

- [ ] **Step 2: Type-check**

From `packages/web`:
```bash
pnpm type-check
```
Expected: exit code `0`.

- [ ] **Step 3: Biome lint (non-mutating)**

From `packages/web`:
```bash
pnpm lint:check
```
Expected: exit code `0`.

- [ ] **Step 4: i18n parity (DE/EN/FR) + no fallback strings**

From repo root:
```bash
npx tsx scripts/validate-i18n.ts
```
Expected: exit code `0`, no `[ERROR]`. (Note: `pnpm check:i18n` is not a defined script in `packages/web/package.json`; `scripts/validate-i18n.ts` is the authoritative frontend i18n validator, invoked by `scripts/run_checks.py`.)

- [ ] **Step 5: AI-UX compliance gate**

From repo root:
```bash
just check-ai-ux
```
Expected: `Violations: 0`, `Stale excludes: 0`, inventory complete.

- [ ] **Step 6: Frontend file-size gate (RULE-04)**

From repo root:
```bash
just check-frontend-size
```
Expected: `0 current` violations, no new debt. (Limits: tsx 200, ts 400, hook 150; every new file in this plan is well under.)

- [ ] **Step 7: AI-UX checker unit tests (pytest)**

From repo root:
```bash
uv run pytest tests/unit/scripts -q
```
Expected: all pass (the inventory/checker tests must remain green after the optional-field addition).

- [ ] **Step 8: Verify no fabricated Beta-Reader diff and no keyboard regression**

From `packages/web`:
```bash
pnpm test components/studio/analysis/__tests__/beta-reader-diff-honesty.test.tsx
pnpm test components/studio/editor/__tests__/CoAuthorReviewPhase.keyboard.test.tsx
pnpm test components/studio/editor/__tests__/RewriteSuggestionModal.test.tsx
```
Expected: all PASS (Beta Reader honesty + CR-AUFG-07-13 keyboard preserved on Rewrite & Co-Author).

---

## Self-review

### 1. Spec coverage (each spec requirement → task)

| Spec requirement (CR-AUFG-07-18) | Task(s) |
|----------------------------------|---------|
| Consistent labels Original/Suggested/Accepted/Rejected/Unchanged via `aiActions.*` + diff keys | Task 1 (i18n), Task 5 (`AIDiffBadge`) |
| Rewrite & Co-Author use shared diff primitive for text diffs | Task 13 (Rewrite), Task 14 (Co-Author) |
| KB Enhance uses same state model for field-level before/after, NOT prose diff | Task 9 (field-mode adapter), Task 15 (adoption) |
| Beta Reader shows diff ONLY when grounded original+suggested; else feedback | Task 10 (null adapter), Task 16 (honesty test) |
| CR-AUFG-07-13 keyboard actions continue to trigger same handlers | Task 13 (Ctrl+Enter preserved), Task 14 (Co-Author keyboard tests), Task 18 step 8 |
| Accessibility: additions/deletions not color-alone; sr labels describe change type | Task 4 (`<ins>`/`<del>` + markers + aria-label), Task 6 (group sr-summary) |
| Component tests for shared diff rendering, keyboard equivalence, sr labels | Tasks 4, 5, 6, 13, 14, 18 |
| Adapter tests for Rewrite, Co-Author, KB Enhance, grounded Beta Reader | Tasks 7, 8, 9, 10, 16 |
| AI Operation Inventory entries reference shared diff primitive | Task 17 |
| File-size gate green | Task 18 step 6 |
| Frontend-only first increment; no backend/core change | Confirmed — no backend/core files touched |
| No new diffing dependency | Confirmed — reuses existing `diff-match-patch` |
| No fabricated Beta Reader spans | Task 10/16 — adapter returns `null`; `BetaReaderPanel` untouched |
| i18n DE/EN/FR under `studio` namespace; reuse `aiActions.original/suggested` | Task 1 (9 new keys × 3 locales; Original/Suggested reused from `aiActions`) |

No spec gap identified.

### 2. Placeholder scan

Searched the plan for: `TBD`, `TODO`, `implement later`, `fill in`, `add appropriate`, `handle edge cases`, `similar to Task`, `…` in code blocks.
- The only ellipses present are inside `<input/>`-style JSX attribute continuations that are explicitly narrative (`{...textVm}`), not placeholders — all are complete, valid spread expressions.
- Task 13 Step 1 and Task 15 Step 1 reference "the file's existing render helpers" — this is deliberate (the existing test files already define their setup; the plan reuses rather than reinvents). Both steps tell the engineer exactly what to assert and that they may inline existing props. This is guidance, not a placeholder.
- Every code step contains complete, compilable code. No `// TODO` in any code block.

### 3. Type consistency

- `AIDiffState` values: `suggested | accepted | rejected | unchanged` — used identically in `contracts.ts`, `AIDiffBadge.tsx`, `AIDiffView.tsx`, and adoption (`state="suggested"`, `state={isAccepted ? "accepted" : "suggested"}`, `isSelected ? "accepted" : "suggested"`). ✓
- `AIDiffSegment.kind`: `added | removed | unchanged` — identical in `contracts.ts`, `segmentize.ts`, `AIDiffSegmentList.tsx`. ✓
- `AIDiffViewModel` fields (`id`, `mode`, `segments`, `originalFull`, `suggestedFull`, `label`, `provisional`) — constructed identically by all four adapters and consumed identically by `AIDiffView`. ✓
- Adapter names: `rewriteAdapter`, `coAuthorChangeAdapter`, `kbEnhanceFieldAdapter`, `betaReaderGroundedAdapter`, `isBetaReaderGrounded` — spelled identically in their files, tests, barrel, and adoption sites. ✓
- Domain source types (`ChangeDetail`, `KBEnhancementResult`, `BetaFeedbackItem`) — imported from their real `@/lib/api/*` locations; field names (`original_text`/`revised_text`, `original`/`suggested`, `suggestion`/`text_excerpt`) match the read source. ✓
- i18n keys: `aiDiff.{added,removed,unchanged,accepted,rejected,srSummary,acceptChange,rejectChange,provisional}` added in Task 1 and referenced identically in Tasks 4, 5, 6, 14. `aiActions.{original,suggested,accept,reject}` reused (already canonical). ✓

No type/name drift detected.

---

## Notes / unresolved questions for the Coordinator

1. **`pnpm check:i18n` does not exist** as a script in `packages/web/package.json`. The authoritative frontend i18n validator is `scripts/validate-i18n.ts` (invoked by `scripts/run_checks.py` as "i18n Validation"). Task 1 and Task 18 use `npx tsx scripts/validate-i18n.ts`. If the orchestrator wants a `check:i18n` script added, that is a separate (tiny) task outside this plan's scope.
2. **`InlineDiff.tsx` disposition:** Kept as a thin accessible facade (delegating to `segmentize` + `AIDiffSegmentList`) rather than deleted, because it has a distinct responsibility (inline text-only rendering) from the full `AIDiffView` review surface. Task 12 Step 1 verifies whether `computeDiffElements` has external consumers before removing it.
3. **Beta Reader has no UI change in this increment** — by design (RULE-20 + spec out-of-scope). When the backend adds grounded original/revised text spans (coordinated RULE-17 change), update `isBetaReaderGrounded` + `betaReaderGroundedAdapter` together and add the `AIDiffView` to the relevant feedback card. That is a future AUFG, not this one.
4. **Optional inventory field:** Adding `shared_diff_view` to four operations is safe — `check_10_operation_inventory.py` validates the 16 *required* fields only and does not reject additional optional fields. If Platform later wants this field required/checked, that is a separate governance change to §4 + Check 10.
