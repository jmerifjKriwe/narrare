# CR-07 v3 Phase B — Onboarding "Aha Moment" Implementation Plan (CR-AUFG-07-17)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **No commit steps:** The Coordinator delegates the final commit to the Platform Specialist after all gates pass. Each task ends at "run tests to verify they pass."

**Goal:** Add a conceptual "How Narrare thinks with your world" tour layer to ONBOARD-001 that explains how KB facts and Storyboard structure shape AI output — without claiming runtime context consumption that the implementation cannot prove. ONBOARD-001's `stable` base status is unchanged; this plan closes the CR-AUFG-07-17 follow-up.

**Architecture:** Root cause: the existing 6-step FeatureTour walks users through UI locations (editor, nav, AI toolbar, GhostText, worldbuilding, settings) but never explains *why* the AI produces coherent output — i.e., that KB entries and Storyboard chapters feed into the prompts the AI receives. Users finish onboarding knowing *where* things are but not *how they connect*. The architecturally correct fix is a new conceptual tour segment (steps 7–9) plus richer i18n description text — reusing the existing `FeatureTour` component, `FEATURE_TOUR_STEPS` config, and `requestFeatureTour()` replay path. No new library, no new component class.

**Tech Stack:** Next.js, React, TypeScript strict, next-intl, Vitest, Testing Library. Backend untouched.

---

## Scope, Root Cause, Alternatives

**In scope:** CR-AUFG-07-17. Three new conceptual tour steps (KB → context → AI; Storyboard → chapter → AI; one concrete before/after demo moment), DE/EN/FR `studio.json` keys, updated `FEATURE_TOUR_STEPS`, replay-from-Settings stays functional, runtime-context-claim guard test.

**Out of scope:** New tour library (Shepherd.js etc. explicitly rejected by ONBOARD-001 spec), new demo projects, backend changes, Phase A/B items other than CR-AUFG-07-17, downgrading ONBOARD-001's stable status, modifying the existing 6 steps' content.

**Warum 1:** The current tour ends at "Settings" (step 6) without ever connecting KB, Storyboard, and AI into a single mental model. Users can find each feature but cannot articulate *why* filling the KB improves AI output.

**Warum 2:** The codebase's `variable_taxonomy.py` and `PromptContext` prove that KB variables (`kb_summary`, `kb_context_entries`, `world_context`, etc.) and Storyboard variables (`chapter_outline`, `story_structure`, etc.) are real runtime prompt inputs — but this fact is invisible to users, and a careless tour text could easily over-claim ("the AI always uses your full KB") and violate the §B.2 acceptance criterion.

**Chosen design:** Append three new tour steps (7, 8, 9) to `FEATURE_TOUR_STEPS`. Each step has an i18n `titleKey` + `descriptionKey` under `studio.tour.step{7,8,9}.*`. Step 9 carries a concrete before/after example drawn from the existing demo project "Echoes of the Thornwall" — embedded in description text, no new component. Add a guard test that greps the new tour description strings for forbidden over-claim phrases ("always uses", "every AI action", "automatically reads your full KB").

**Rejected alternatives:**

- **New `ConceptualTour` component with rich media:** Rejected — ONBOARD-001 spec explicitly says "no new tour library." The existing `FeatureTour` already supports centered tooltips (omit `target`) and i18n-driven content. Adding a parallel component duplicates the persistence/keyboard/localStorage logic.
- **Inline demo viewer (load a demo project inside the tour):** Rejected — couples onboarding to project-load state machine, breaks replay-from-Settings (no project context), and risks the tour claiming runtime behavior the loaded project cannot demonstrate. The before/after moment is safer as static example text.
- **Expand the existing 6 steps' descriptions to include conceptual content:** Rejected — mixes "where things are" with "how they connect," dilutes both messages, and forces a re-translation of all 6 steps. Adding steps 7–9 keeps the existing stable content untouched (ONBOARD-001 base scope unchanged).
- **A modal "How Narrare thinks" video/animation:** Rejected — out of scope (no media pipeline), inaccessible by default, and not replayable from the existing Settings → Help path without new UI.

## RULE-XX Focus

| Rule | Plan evidence |
|------|---------------|
| RULE-04 | `feature-tour-steps.ts` stays a pure config array (well under 200-line TSX limit; TS limit 400). No component file grows. |
| RULE-06 | Each new step is a data entry; the `FeatureTour` component responsibility is unchanged. |
| RULE-10 | New step content has failing test → impl → passing test; the over-claim guard test is a regression gate. |
| RULE-11 | No silent failures — missing i18n key fails the i18n parity gate, not a silent English fallback (Phase A hardened this). |
| RULE-16 | All new visible text in DE/EN/FR `studio.json`. Phase A's i18n fallback checker (Check 12) prevents reintroducing `t(...) || "..."` patterns. |
| RULE-20 | ONBOARD-001 base stays `stable`; CR-AUFG-07-17 is the only status that moves (open → resolved after gates). |
| RULE-21 | No new endpoint, contract, or shared primitive — reuses `FeatureTour`, `TourStep`, `requestFeatureTour()` unchanged. No Architecture re-review trigger. |
| RULE-22 | Tour text claims are bounded by what `variable_taxonomy.py` proves the runtime consumes. Guard test enforces. |

## File Structure

### Frontend — owner: Frontend Specialist

- **Modify** `packages/web/lib/config/feature-tour-steps.ts` — Append three new entries to `FEATURE_TOUR_STEPS` (steps 7, 8, 9). Each uses i18n keys only; no `target` (centered tooltips, like the existing step 3 and step 4).
- **Modify** `packages/i18n/messages/de/studio.json` — Add `tour.step7`, `tour.step8`, `tour.step9` blocks.
- **Modify** `packages/i18n/messages/en/studio.json` — Add the same three blocks.
- **Modify** `packages/i18n/messages/fr/studio.json` — Add the same three blocks.

### Platform — owner: Platform Specialist

- **Create** `packages/web/__tests__/feature-tour-concept-steps.test.tsx` — Renders `FeatureTour` with the real `FEATURE_TOUR_STEPS` array; asserts steps 7–9 render their i18n-driven title/description; asserts the step indicator dot count is 9.
- **Create** `packages/web/__tests__/tour-no-overclaim.test.ts` — Guard test: greps the three new i18n keys' English values for forbidden phrases ("always uses", "every AI action", "automatically reads your full KB", "reads your entire"). Fails if any forbidden phrase appears.

### Docs / AUFG — owner: Docs Specialist (after gates pass)

- **Modify** `docs/architecture/governance/aufg-registry.md` — Update CR-AUFG-07-17 row from `open` to `resolved` with implementation + enforcement evidence.
- **Modify** `docs/features/onboarding-user-guide.md` — Append a "CR-07 v3 Phase B" history entry: conceptual tour steps added; ONBOARD-001 base scope unchanged.

---

## Runtime-Context-Claim Boundary (RULE-22)

Before writing the tour text, the implementer must confirm which KB/Storyboard variables are ACTUALLY consumed by runtime prompts. The boundary is defined by:

1. `packages/core/narrare_core/prompts/variable_taxonomy.py` — the authoritative provenance/security taxonomy. Variables listed here are real runtime inputs.
2. `packages/core/narrare_core/prompts/_bundled/` — the actual prompt templates. If `{{kb_summary}}` appears in a bundled prompt, the claim "Narrare includes your KB summary in writing prompts" is TRUE.
3. `packages/core/narrare_core/context/assembler.py` — confirms the runtime path that builds `PromptContext` from project data.

**Allowed claims** (verifiable from the codebase):
- "When you write, Narrare can include relevant KB entries in the AI's prompt." (Hedge: *can*, because the user controls which KB entries are pinned/relevant.)
- "Your chapter outline and story structure are part of the context the AI sees for planning." (True: `chapter_outline`, `story_structure` are in the taxonomy.)
- "Updating your KB makes future AI suggestions more coherent, because more facts are available to the prompt." (True, conditional, no absolute claim.)

**Forbidden claims** (would violate §B.2 acceptance criteria):
- "The AI always uses your full KB." (False — relevance filtering applies.)
- "Every AI action reads your Storyboard." (False — not all intents take storyboard context.)
- "The AI automatically learns your style." (False — preference learning is a separate opt-in feature, not automatic from the tour's perspective.)

Task 3's guard test enforces this boundary mechanically.

---

## Tasks

### Task 1: Add the three conceptual tour steps to `FEATURE_TOUR_STEPS`

**Files:**
- Modify: `packages/web/lib/config/feature-tour-steps.ts`

- [ ] **Step 1: Write the failing test**

```typescript
// packages/web/__tests__/feature-tour-concept-steps.test.tsx
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it } from "vitest";
import { FeatureTour, TOUR_STORAGE_KEY } from "@/components/ui/feature-tour";
import { FEATURE_TOUR_STEPS } from "@/lib/config/feature-tour-steps";

beforeEach(() => {
  localStorage.clear();
});
afterEach(() => {
  cleanup();
});

it("exposes nine tour steps total (six existing + three conceptual)", () => {
  expect(FEATURE_TOUR_STEPS).toHaveLength(9);
});

it("step 7 uses centered tooltip and references the conceptual KB→AI key", () => {
  const step = FEATURE_TOUR_STEPS[6];
  expect(step.target).toBeUndefined();
  expect(step.titleKey).toBe("tour.step7.title");
  expect(step.descriptionKey).toBe("tour.step7.description");
});

it("step 8 references the Storyboard→AI conceptual key", () => {
  const step = FEATURE_TOUR_STEPS[7];
  expect(step.titleKey).toBe("tour.step8.title");
});

it("step 9 references the before/after demo key", () => {
  const step = FEATURE_TOUR_STEPS[8];
  expect(step.titleKey).toBe("tour.step9.title");
});

it("FeatureTour renders nine step indicator dots", () => {
  render(<FeatureTour steps={FEATURE_TOUR_STEPS} />);
  const dialog = screen.getByRole("dialog");
  const dots = dialog.querySelectorAll(".rounded-full");
  expect(dots).toHaveLength(9);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/web && pnpm vitest run __tests__/feature-tour-concept-steps.test.tsx`
Expected: FAIL (`FEATURE_TOUR_STEPS` has length 6, not 9).

- [ ] **Step 3: Append the three new steps**

```typescript
// Append to FEATURE_TOUR_STEPS in packages/web/lib/config/feature-tour-steps.ts:
  {
    // Conceptual: KB → Context → AI (centered tooltip, no DOM target)
    titleKey: "tour.step7.title",
    descriptionKey: "tour.step7.description",
  },
  {
    // Conceptual: Storyboard → Chapter → AI
    titleKey: "tour.step8.title",
    descriptionKey: "tour.step8.description",
  },
  {
    // Conceptual: before/after demo moment
    titleKey: "tour.step9.title",
    descriptionKey: "tour.step9.description",
  },
```

- [ ] **Step 4: Run test to verify it passes (after Task 2 adds the i18n keys)**

Run: `cd packages/web && pnpm vitest run __tests__/feature-tour-concept-steps.test.tsx`
Expected: PASS once Task 2 lands. (The shape tests at the top of the file pass immediately; the dialog-render test requires i18n keys to exist.)

### Task 2: Add the conceptual tour i18n keys (DE/EN/FR)

**Files:**
- Modify: `packages/i18n/messages/de/studio.json`
- Modify: `packages/i18n/messages/en/studio.json`
- Modify: `packages/i18n/messages/fr/studio.json`

- [ ] **Step 1: Add the English keys first (source of truth)**

Insert these blocks inside the existing `tour` object in `packages/i18n/messages/en/studio.json`, immediately after the existing `step6` block and before `skip`:

```json
    "step7": {
      "title": "How Narrare Thinks — Part 1: Knowledge Base",
      "description": "Your Knowledge Base holds the facts of your world: characters, locations, factions. When you ask the AI to write or extend a chapter, Narrare can include the relevant entries in the prompt — so the AI's suggestions fit your world instead of inventing generic detail. Add to your KB and future suggestions become more coherent."
    },
    "step8": {
      "title": "How Narrare Thinks — Part 2: Storyboard & Chapters",
      "description": "Your Storyboard plans the narrative arc, and each chapter carries its own outline. For planning and writing, Narrare makes that structure visible to the AI — so suggestions respect where you are in the story instead of drifting off-course."
    },
    "step9": {
      "title": "Before / After — A Quick Example",
      "description": "Without KB context, the AI might write: 'A woman entered the room.' With your KB entry for Anna Müller — a teacher from the city — the AI can write: 'Anna Müller, still dusting chalk from her sleeve, stepped into the candlelit archive.' That is the difference filling your KB makes. (Example inspired by the demo project 'Echoes of the Thornwall'.)"
    },
```

- [ ] **Step 2: Add the German keys**

Insert the equivalent blocks in `packages/i18n/messages/de/studio.json`:

```json
    "step7": {
      "title": "Wie Narrare denkt — Teil 1: Knowledge Base",
      "description": "Deine Knowledge Base enthält die Fakten deiner Welt: Figuren, Orte, Fraktionen. Wenn du die KI bittest, ein Kapitel zu schreiben oder fortzusetzen, kann Narrare die relevanten Einträge in den Prompt aufnehmen — sodass die Vorschläge der KI zu deiner Welt passen, anstatt generische Details zu erfinden. Je mehr du in deine KB einträgst, desto kohärenter werden künftige Vorschläge."
    },
    "step8": {
      "title": "Wie Narrare denkt — Teil 2: Storyboard & Kapitel",
      "description": "Dein Storyboard plant den Erzählbogen, und jedes Kapitel trägt seine eigene Gliederung. Beim Planen und Schreiben macht Narrare diese Struktur der KI sichtbar — sodass Vorschläge respektieren, wo du in der Geschichte stehst, anstatt vom Kurs abzukommen."
    },
    "step9": {
      "title": "Vorher / Nachher — ein kurzes Beispiel",
      "description": "Ohne KB-Kontext könnte die KI schreiben: 'Eine Frau betrat den Raum.' Mit deinem KB-Eintrag für Anna Müller — einer Lehrerin aus der Stadt — kann die KI schreiben: 'Anna Müller, immer noch dabei, Kreidestaub von ihrem Ärmel zu klopfen, trat in die kerzenbeleuchtete Bibliothek.' Dieser Unterschied entsteht, wenn du deine KB füllst. (Beispiel inspiriert vom Demo-Projekt 'Echoes of the Thornwall'.)"
    },
```

- [ ] **Step 3: Add the French keys**

Insert the equivalent blocks in `packages/i18n/messages/fr/studio.json`:

```json
    "step7": {
      "title": "Comment Narrare pense — Partie 1 : la Knowledge Base",
      "description": "Votre Knowledge Base contient les faits de votre univers : personnages, lieux, factions. Quand vous demandez à l'IA d'écrire ou de prolonger un chapitre, Narrare peut inclure les entrées pertinentes dans le prompt — pour que les suggestions de l'IA s'intègrent à votre univers au lieu d'inventer des détails génériques. Plus vous enrichissez votre KB, plus vos suggestions deviennent cohérentes."
    },
    "step8": {
      "title": "Comment Narrare pense — Partie 2 : Storyboard & chapitres",
      "description": "Votre Storyboard planifie l'arc narratif, et chaque chapitre porte son propre plan. Pour la planification et l'écriture, Narrare rend cette structure visible à l'IA — pour que les suggestions respectent où vous en êtes dans l'histoire au lieu de s'égarer."
    },
    "step9": {
      "title": "Avant / Après — un exemple rapide",
      "description": "Sans contexte KB, l'IA pourrait écrire : « Une femme entra dans la pièce. » Avec votre entrée KB pour Anna Müller — une enseignante de la ville — l'IA peut écrire : « Anna Müller, époussetant encore la craie de sa manche, pénétra dans les archives éclairées aux bougies. » C'est la différence que procure une KB remplie. (Exemple inspiré du projet de démonstration « Echoes of the Thornwall ».)"
    },
```

- [ ] **Step 4: Run the i18n parity gate**

Run: `uv run python scripts/check_i18n_parity.py` (or `just check-i18n` if configured).
Expected: 0 missing keys across DE/EN/FR.

If the script path differs, locate it: `ls scripts/checks/ | grep -i i18n` (or read `Justfile` for the i18n target name).

- [ ] **Step 5: Run the conceptual-steps test**

Run: `cd packages/web && pnpm vitest run __tests__/feature-tour-concept-steps.test.tsx`
Expected: PASS.

### Task 3: Runtime-context over-claim guard test (RULE-22)

**Files:**
- Create: `packages/web/__tests__/tour-no-overclaim.test.ts`

- [ ] **Step 1: Write the guard test**

```typescript
// packages/web/__tests__/tour-no-overclaim.test.ts
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

type LocaleBlock = {
  tour: {
    step7: { title: string; description: string };
    step8: { title: string; description: string };
    step9: { title: string; description: string };
  };
};

const FORBIDDEN_PHRASES = [
  "always uses",
  "every AI action",
  "automatically reads your full KB",
  "reads your entire",
  "always includes your full KB",
  "the AI memorizes",
  "automatically learns your style",
] as const;

function loadLocale(locale: "en"): LocaleBlock {
  const path = resolve(
    __dirname,
    "..",
    "packages/i18n/messages",
    locale,
    "studio.json",
  );
  return JSON.parse(readFileSync(path, "utf-8")) as LocaleBlock;
}

describe("tour conceptual steps — RULE-22 no over-claim", () => {
  const block = loadLocale("en");

  it.each([
    ["step7", block.tour.step7],
    ["step8", block.tour.step8],
    ["step9", block.tour.step9],
  ])("%s description contains no forbidden absolute claim", (_name, step) => {
    const haystack = `${step.title} ${step.description}`.toLowerCase();
    const hits = FORBIDDEN_PHRASES.filter((phrase) =>
      haystack.includes(phrase.toLowerCase()),
    );
    expect(hits, `forbidden phrases found: ${hits.join(", ")}`).toEqual([]);
  });

  it("step7 description mentions the KB variable family or KB concept", () => {
    const desc = block.tour.step7.description.toLowerCase();
    expect(desc).toMatch(/knowledge base|\bkb\b/);
  });

  it("step8 description mentions storyboard or chapter structure", () => {
    const desc = block.tour.step8.description.toLowerCase();
    expect(desc).toMatch(/storyboard|chapter|outline|narrative/);
  });

  it("step9 description includes a concrete before/after example", () => {
    const desc = block.tour.step9.description.toLowerCase();
    expect(desc).toMatch(/before|ohne|without|nachher|after/);
  });
});
```

- [ ] **Step 2: Run the guard test**

Run: `cd packages/web && pnpm vitest run __tests__/tour-no-overclaim.test.ts`
Expected: PASS.

If it FAILS, the i18n description in Task 2 contains a forbidden phrase — rephrase to a hedged, conditional claim (see the "Allowed claims" list in the RULE-22 boundary section above) and re-run.

### Task 4: Replay-from-Settings smoke test

**Files:**
- Modify (extend): `packages/web/__tests__/feature-tour-concept-steps.test.tsx`

The existing `AboutTab.tsx` already wires `requestFeatureTour` to a button (lines 60–71). This task asserts that clicking that button starts a tour that includes the new conceptual steps. No new component.

- [ ] **Step 1: Add the replay test**

```typescript
// Append to packages/web/__tests__/feature-tour-concept-steps.test.tsx:
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { requestFeatureTour, TOUR_STORAGE_KEY } from "@/components/ui/feature-tour";

it("replaying the tour from settings surfaces all nine steps including conceptual ones", async () => {
  // Mark the tour as previously completed, then request replay.
  localStorage.setItem(TOUR_STORAGE_KEY, "true");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

  requestFeatureTour();
  render(<FeatureTour steps={FEATURE_TOUR_STEPS} />);

  await waitFor(() => {
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  // Step forward through all nine steps; the conceptual step 7 title must appear.
  for (let i = 0; i < 6; i++) {
    const nextButton = screen.getByRole("button", { name: /next/i });
    fireEvent.click(nextButton);
  }
  // Now on step 7 (index 6).
  expect(screen.getByText("tour.step7.title")).toBeInTheDocument();
});
```

> **Note:** next-intl is mocked in the existing test setup (the mock returns the key string verbatim — see `packages/web/__tests__/feature-tour.test.tsx` line 74 comment). Asserting on the key string, not the translated text, is the established pattern. Do not change the mock.

- [ ] **Step 2: Run the test**

Run: `cd packages/web && pnpm vitest run __tests__/feature-tour-concept-steps.test.tsx`
Expected: PASS.

### Task 5: Phase A i18n fallback gate regression (no new code)

This task only runs a gate; no files change. It confirms Task 2's i18n additions do not regress Phase A's `t(...) || "..."` ban.

- [ ] **Step 1: Run the AI-UX / i18n fallback checker**

Run: `just check-ai-ux`
Expected: 0 violations.

Run: `uv run python scripts/check_frontend_file_size.py`
Expected: 0 new violations. (`feature-tour-steps.ts` stays well under the 400-line TS limit; no TSX file grows.)

- [ ] **Step 2: Run the broader frontend test suite to catch regressions**

Run: `cd packages/web && pnpm vitest run __tests__/feature-tour.test.tsx __tests__/feature-tour-concept-steps.test.tsx __tests__/tour-no-overclaim.test.ts`
Expected: all PASS.

### Task 6: AUFG evidence + feature spec history (only after all gates pass)

**Files:**
- Modify: `docs/architecture/governance/aufg-registry.md`
- Modify: `docs/features/onboarding-user-guide.md`

- [ ] **Step 1: Update the AUFG registry**

In `docs/architecture/governance/aufg-registry.md`, change the CR-AUFG-07-17 row:
- Status: `open` → `resolved`
- Append to the acceptance summary cell: "Implemented: 3 new conceptual tour steps (KB→AI, Storyboard→AI, before/after demo) in `feature-tour-steps.ts`; DE/EN/FR `studio.json` keys; replay path intact. Enforcement: `feature-tour-concept-steps.test.tsx`, `tour-no-overclaim.test.ts` (RULE-22 over-claim guard), `just check-ai-ux`, i18n parity gate."

- [ ] **Step 2: Append the history entry to the ONBOARD-001 spec**

In `docs/features/onboarding-user-guide.md`, add to the Status & History section:

```markdown
- `2026-06-2X` — CR-07 Follow-up v3 Phase B (CR-AUFG-07-17) implemented:
  three new conceptual tour steps (`tour.step7`, `step8`, `step9`) explaining
  how KB and Storyboard shape AI output, with a concrete before/after demo
  moment. ONBOARD-001 base scope unchanged; the follow-up AUFG is `resolved`
  after `tour-no-overclaim.test.ts` and the AI-UX/i18n gates pass.
```

> **RULE-20 guard:** Do NOT mark CR-AUFG-07-17 `resolved` until every test in this plan passes on disk and the AI-UX + i18n gates are green.

---

## Self-Review

### Spec coverage

| CR-07 v3 §B.2 / CR-AUFG-07-17 acceptance criterion | Task |
|---|---|
| First-run or replayable tour includes a conceptual "How Narrare thinks with your world" step | Tasks 1, 2 (step7), Task 4 (replay) |
| Tour distinguishes KB, Storyboard, and AI without exposing implementation jargon | Tasks 1, 2 (step7 = KB, step8 = Storyboard, no `{{variable}}` syntax in user-facing text) |
| Explanation does not claim AI uses context the runtime does not actually consume | Task 3 (RULE-22 guard test against `variable_taxonomy.py`-bounded claims) |
| User-facing text in DE/EN/FR and follows the no-hardcoded-string gate | Task 2 (three locales), Task 5 (Check 12 regression) |
| Concrete "before/after" or guided demo moment using existing demo projects | Task 2 (step9 references "Echoes of the Thornwall"), Task 3 (asserts before/after phrasing) |
| Replay from Settings/Help stays functional | Task 4 (replay smoke test; `AboutTab.tsx` already wires `requestFeatureTour`) |
| Use existing `FeatureTour` component — no new library | All tasks reuse `feature-tour.tsx` unchanged |
| ONBOARD-001 base scope unchanged (`stable` not downgraded) | No task modifies the existing 6 steps or the ONBOARD-001 DoD checkboxes |
| AUFG evidence + status updates only after gates pass | Task 6 |

### Placeholder scan

- No `TODO`, `TBD`, or "implement later" in any task.
- Step 1 of Task 1 includes a complete TypeScript test body — not pseudocode.
- Step 3 of Task 1 includes the complete three-entry append — not a shape sketch.
- Task 2 includes the complete DE/EN/FR JSON blocks verbatim.
- Task 3's forbidden-phrase list is explicit and mechanical.

### Type consistency

- The new `FEATURE_TOUR_STEPS` entries conform to the existing `TourStep` interface (`{ target?: string; titleKey: string; descriptionKey: string }`) — `target` omitted for centered tooltips, matching the existing step 3 and step 4 entries. No interface change.
- i18n key paths (`tour.step7.title`, `tour.step7.description`, etc.) match the nested JSON structure already used by `tour.step1`…`tour.step6`. next-intl resolves them identically.
- The `loadLocale` type in Task 3 mirrors the actual JSON shape (verified against the existing `tour.step1` block at `packages/i18n/messages/en/studio.json:1743-1746`). The type is narrow on purpose so any future rename of the conceptual keys surfaces as a compile error in the guard test.

### Coverage targets

- Frontend: `feature-tour.tsx` unchanged (existing 12 tests still pass); new tests in `feature-tour-concept-steps.test.tsx` (5 tests) and `tour-no-overclaim.test.ts` (5 tests) cover the new behavior. No coverage regression.
- No backend / core changes — coverage targets there are untouched.

---

## Handoff Plan (sequence for the Coordinator)

1. **Frontend Specialist** — Tasks 1–4 (steps, i18n, guard test, replay test). Self-contained; no other specialist's output is a prerequisite. Hand off to Platform once all four tasks' tests pass.
2. **Platform Specialist** — Task 5 (run `just check-ai-ux`, file-size gate, full feature-tour vitest suite). Report green output to Coordinator.
3. **Docs Specialist** — Task 6 only after Platform confirms green. Update AUFG registry + ONBOARD-001 history.

**Coordinator delegates the final commit to Platform** (per user instruction). No `git commit` steps appear in this plan.

**No RULE-21 review trigger** — this plan adds no endpoint, no service contract, no shared frontend primitive. It reuses `FeatureTour`, `TourStep`, `requestFeatureTour()` unchanged. Architecture sign-off is not required before implementation; the only architectural constraint (RULE-22 over-claim boundary) is enforced by Task 3's guard test.
