# B — I-Copy-001 Formality Register — Closure & Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close program item B of the Post-Export Follow-ups program — verify I-Copy-001 (User-Selectable UI Formality, du/Sie) against its spec DoD, close the one genuine test gap (loader-level behavior tests), and land the docs closure that marks the feature and the program complete.

**Architecture:** Plan-time investigation (2026-08-18, evidence below) established that I-Copy-001's **implementation already shipped on `main`** in commits `17ad629d` (2026-08-09: loader seam `request.ts` + `mergeOverlay.ts` + `FormalitySwitcher` + switcher tests + governance assertions) and `da5c73d2` (2026-08-09: the full editorial overlay — 159 DE formal variants + FR parity) — **before** the program design doc (2026-08-14) was written and listed B as pending. This plan therefore does NOT re-implement anything: it is a **verification-and-closure slice**. Task 1 adds the only missing test layer (the loader seam itself, including the DoD letter "`en` message catalog byte-identical in both registers (asserted)" as a *direct, executed* assertion); Task 2 lands the docs closure (spec status, feature INDEX, CURRENT_STATE program-complete entry). **Zero production files are touched.**

**Tech Stack:** TypeScript, vitest 4 (happy-dom), vi.mock (`next/headers`, `next-intl/server`), next-intl 4.13 (untouched), Markdown docs.

**Binding inputs:**
- Feature spec (Q-015 resolution): `docs/features/i18n/I-Copy-001-formality-register.md` — Overlay-Merge architecture, cookie-only v1, RULE-02 boundary, DoD §Acceptance criteria.
- Program design: `docs/superpowers/specs/2026-08-14-post-export-followups-design.md` §8 (B = implement the existing spec 1:1) + §12 (B gate: "Per existing I-Copy-001 spec DoD").

---

## Plan-Time Empirical Findings (2026-08-18, all verified on this machine)

The coordinator's dispatch assumed B was unimplemented (stale session-checkpoint memory). The repository says otherwise. Every claim below was verified against `main` @ `3e1f2f3f`:

| Spec DoD item | State on `main` | Evidence |
|---|---|---|
| `NEXT_FORMALITY` read in `request.ts`, default `"informal"` | ✅ implemented / ❌ **no direct test** | `packages/web/lib/i18n/request.ts:29-48` |
| Deep-merge overlay when `locale !== "en" && formality === "formal"` | ✅ implemented / ❌ **no direct test** | `request.ts:70-78` |
| `mergeOverlay.ts` helper + unit tests (flat / nested / leaf-only) | ✅ done | `__tests__/i18n-mergeOverlay.test.ts`, 9 tests, pass |
| `overlays/formality/de.json` + `fr.json`, ~150–300/lang | ✅ done | **159 DE + 159 FR** leaf overrides, per-namespace parity exact (studio 103, wizard 13, settings 11, editor 10, analysis 9, adaptive 3, dashboard 3, settings-ai 3, dialogueCoach 2, auth 1, settings-appearance 1) — inside the spec's 150–300 band |
| Toggle mirrors the locale-switcher; persists | ✅ done — auth-screen placement | `FormalitySwitcher.tsx` beside `LanguageSwitcher` in `app/(auth)/layout.tsx` (the spec's parenthetical "or the existing language/locale area" option); `formality-switcher.test.tsx`, 5 tests, pass |
| Governance: orphan-override + de/fr parity + no-en | ✅ done | `__tests__/i18n-namespace-registry.test.ts:200-236`, 4 assertions, pass |
| `en` byte-identical in both registers **(asserted)** | ⚠️ only indirect (no-en test + loader skip) | no test *executes* en+formal and compares against the base — **closed by Task 1** |
| Zero `core/prompts/` changes; zero call-site migration | ✅ | commit scopes of `17ad629d`/`da5c73d2` contain no component/prompt edits |
| Frontend tests green; `just check` green | ✅ baseline re-verified | 19/19 formality tests pass (2026-08-18 scoped run) |

Additional verified facts that shape this plan:

1. **DE overlay is functionally real:** all 159 DE values differ from the base (du→Sie forms). **FR overlay is a documented forward-correct no-op:** all 159 FR values are byte-equal to the FR base (which already uses vouvoiement) — intentional per `da5c73d2`'s commit message; parity is required by the governance test.
2. **Loader testability was probed end-to-end** (throwaway probe, deleted, tree clean): vitest CAN drive `request.ts` directly — (a) mock `next/headers` with an in-memory cookie store; (b) mock `next-intl/server`'s `getRequestConfig` as an **identity passthrough** (under happy-dom the package's browser export condition resolves to its client shim, which throws `getRequestConfig is not supported in Client Components` — the real server registration is next-intl plumbing, not loader logic); (c) the loader's dynamic JSON imports from `packages/i18n/` resolve natively. The exact Task 1 test file below was **executed green (7/7) + biome clean + `tsc --noEmit` clean** before being removed — implementers paste it verbatim.
3. **`validate-i18n` scope is consciously correct:** the script (pre-commit hook `.pre-commit-config.yaml:295` + CI `ci.yml:687`) is scoped to `packages/i18n/messages/`; overlays live in `packages/i18n/overlays/` ("formality is a register, not a locale" — `17ad629d`). Overlay integrity is owned by the vitest governance test. **No gate change needed.**
4. **Docs are stale:** spec `status: planned`, feature INDEX row `📋`, CURRENT_STATE has no B entry. Also discovered: **C4's own CURRENT_STATE entry is missing** (top entry is C3, 2026-08-17) — *flagged to the coordinator, explicitly OUT of B's scope*; Task 2 does not fabricate it.
5. `packages/web/biome.json` lineWidth = 100. `request.ts` is 81 lines (limit 400, category `default`). File-size checker: `scripts/check_frontend_file_size.py` via `just check`.

## Design Rulings (locked for this slice)

- **Ruling 1 — Toggle placement stays on the auth screens (no Settings move in v1).** The spec's user-perspective section offers "Settings → Appearance (or the existing language/locale area)"; the shipped control lives in the language/locale area on auth screens, exactly mirroring the cookie-based `LanguageSwitcher`. Moving it into studio Settings would put a cookie-only control into the API-backed settings panel (persistence mismatch — the spec's own reason for cookie-only v1) and would violate the zero-call-site-changes premise. Task 2 aligns the spec *text* with the shipped placement instead.
- **Ruling 2 — Characterization tests, not red-green TDD.** Task 1 tests **existing shipped behavior**; the tests are expected to PASS on first run. Failing-first applies to new production code — this slice has none. (Honest deviation from the default TDD step order, documented here.)
- **Ruling 3 — The loader's defensive catch (missing overlay file → base) is not unit-tested.** Exercising it requires mocking a dynamic JSON import for a locale that routing cannot produce; the two real paths (overlay present / not requested) are covered, and overlay *existence* is governed by the registry test. Defensive-only branch, accepted uncovered.
- **Ruling 4 — FR no-op stays.** The FR overlay's byte-equal values are load-bearing (governance parity requirement; forward-correct for a future tutoiement base — separate follow-up, explicitly out of scope). Do not "clean it up".

## Global Constraints

- **Package sizing:** ≤3 production files / ≤250 new LOC per delegated task. **This slice touches ZERO production files** (Task 1: 1 new test file; Task 2: 3 docs files — tests/docs do not count toward the cap). The implementer's `git diff --stat` must show NO file outside the task's list — any deviation is a violation, not an optimization.
- **RULE-02 boundary (verbatim from the spec):** "this setting is **UI-copy-only**. It MUST NOT reach `core/prompts/` or any AI-generated content." Enforced here by scope: no `core/`, no `apps/api/` file is touched at all.
- **`en` untouched:** no `overlays/formality/en.json` (governance-asserted), en catalog byte-identical in both registers (directly asserted by Task 1's test).
- **Zero call-site changes:** no component, hook, or `useTranslations` call site is edited. The diff proves it.
- **No changes to existing production code:** `request.ts`, `mergeOverlay.ts`, `FormalitySwitcher.tsx`, overlay JSONs, and all other production files stay **byte-identical**. If any test fails against them, STOP and report — do not "fix" production code inside this slice.
- **English** everywhere (code, comments, tests, docs, commit messages).
- **biome lineWidth 100** (`packages/web/biome.json`) — Task 1's file is pre-validated against `biome check`; keep it byte-identical.
- **Commits:** implementer edits + runs gates + reports; **Platform specialist commits with the verbatim message in each task's commit step**. No `--no-verify`/`-n` (absolute), no push. On any hook failure: STOP and report verbatim. The pre-commit hooks that will fire: architecture-constraints, validate-i18n (scoped to `packages/i18n/messages` — stays green; overlays are consciously outside), file-size, Ruff, secrets, TypeScript Check.
- **Locating edit targets:** by semantic name/text (the plan quotes current text verbatim) — never by line number.
- **Test commands:** frontend scoped: `cd packages/web && npx vitest run <path>`; frontend lint/format: `npx biome check <path>`; frontend types: `pnpm type-check`; frontend suite: `just test-frontend`; all-checks: `just check`; python safety gates: `just typecheck`, `just lint-check`, `just test-unit`.

---

### Task 1: Loader-Level Formality Behavior Tests

**Files:**
- Create: `packages/web/__tests__/i18n-request-formality.test.ts` (the ONLY file — zero production files)

**Interfaces:**
- Consumes (existing, byte-identical): `default export` of `packages/web/lib/i18n/request.ts` (the `getRequestConfig`-wrapped loader — under the identity mock it is callable as `(args: { requestLocale: Promise<string> }) => Promise<{ locale: string; messages: Record<string, unknown> }>`); `packages/i18n/messages/{en,de,fr}/*.json`; `packages/i18n/overlays/formality/{de,fr}.json`.
- Produces (for Task 2): the loader-test references used in the docs closure — file `__tests__/i18n-request-formality.test.ts`, "7 tests incl. the executed `en`-byte-identical assertion". Task 2's spec/history/INDEX text quotes these facts; do not rename the file.

- [ ] **Step 1: Create the test file (verbatim — plan-time validated green)**

Create `packages/web/__tests__/i18n-request-formality.test.ts` with EXACTLY this content (it was executed 2026-08-18: 7/7 vitest PASS, `biome check` clean, `tsc --noEmit` clean — any edit reintroduces unvalidated risk):

```ts
/**
 * Loader-level behavior tests for the formality overlay seam in
 * `lib/i18n/request.ts` (Feature Spec I-Copy-001 — program item B closure).
 *
 * The neighbouring files already pin the other three seams:
 *   - `i18n-mergeOverlay.test.ts`       — the deep-merge helper itself
 *   - `i18n-namespace-registry.test.ts` — overlay governance (orphan/parity/no-en)
 *   - `formality-switcher.test.tsx`     — the UI control (cookie write + refresh)
 * This file pins the LOADER: NEXT_FORMALITY cookie → conditional deep-merge →
 * the message object next-intl receives.
 *
 * Test mechanics (empirically probed 2026-08-18): `next/headers` is mocked
 * with an in-memory cookie store; `next-intl/server`'s `getRequestConfig` is
 * mocked as an IDENTITY PASSTHROUGH — under happy-dom the package's browser
 * export condition resolves to its client shim, whose `getRequestConfig`
 * throws ("not supported in Client Components"). The real server-side
 * registration is next-intl plumbing, not loader logic, so passing the config
 * function through exercises 100 % of the loader's own code. The loader's
 * dynamic JSON imports from `packages/i18n/` resolve natively in vitest.
 *
 * RULE-02 boundary (by construction): the loader seam is UI-copy-only —
 * `formality` never leaves the message-merge layer.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

const cookieStore = new Map<string, string>();

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    get: (name: string) =>
      cookieStore.has(name) ? { value: cookieStore.get(name) as string } : undefined,
  })),
}));

vi.mock("next-intl/server", () => ({
  getRequestConfig: <T>(fn: T) => fn,
}));

import loadRequestConfigDefault from "@/lib/i18n/request";

type ResolvedConfig = { locale: string; messages: Record<string, unknown> };
type RequestConfigFn = (args: { requestLocale: Promise<string> }) => Promise<ResolvedConfig>;

const loadRequestConfig = loadRequestConfigDefault as unknown as RequestConfigFn;

function loadMessages(requestLocale: string): Promise<ResolvedConfig> {
  return loadRequestConfig({ requestLocale: Promise.resolve(requestLocale) });
}

/** Narrow one namespace out of the merged messages object. */
function ns(messages: Record<string, unknown>, namespace: string): Record<string, unknown> {
  return messages[namespace] as Record<string, unknown>;
}

describe("request.ts formality overlay seam (I-Copy-001)", () => {
  beforeEach(() => {
    cookieStore.clear();
  });

  it("de + NEXT_FORMALITY=formal serves the formal overlay value", async () => {
    cookieStore.set("NEXT_LOCALE", "de");
    cookieStore.set("NEXT_FORMALITY", "formal");
    const { locale, messages } = await loadMessages("de");
    expect(locale).toBe("de");
    // Overlay leaf (auth.displayNamePlaceholder: du→Sie form).
    expect(ns(messages, "auth").displayNamePlaceholder).toBe("Wie sollen wir Sie nennen?");
    // A second, nested overlay leaf (wizard.step1.title).
    const wizardStep1 = ns(messages, "wizard").step1 as Record<string, unknown>;
    expect(wizardStep1.title).toBe("Ihr Projekt");
  });

  it("tone-neutral keys fall through to the base in the formal register", async () => {
    cookieStore.set("NEXT_LOCALE", "de");
    cookieStore.set("NEXT_FORMALITY", "formal");
    const { messages } = await loadMessages("de");
    // `common.save` is tone-neutral and deliberately NOT in the overlay.
    expect(ns(messages, "common").save).toBe("Speichern");
  });

  it("de + no NEXT_FORMALITY cookie defaults to the informal base", async () => {
    cookieStore.set("NEXT_LOCALE", "de");
    const { messages } = await loadMessages("de");
    expect(ns(messages, "auth").displayNamePlaceholder).toBe("Wie sollen wir dich nennen?");
  });

  it("de + NEXT_FORMALITY=informal keeps the informal base (explicit)", async () => {
    cookieStore.set("NEXT_LOCALE", "de");
    cookieStore.set("NEXT_FORMALITY", "informal");
    const { messages } = await loadMessages("de");
    expect(ns(messages, "auth").displayNamePlaceholder).toBe("Wie sollen wir dich nennen?");
  });

  it("de + an undocumented NEXT_FORMALITY value falls back to informal", async () => {
    cookieStore.set("NEXT_LOCALE", "de");
    cookieStore.set("NEXT_FORMALITY", "FORMAL"); // case-sensitive: not honoured
    const { messages } = await loadMessages("de");
    expect(ns(messages, "auth").displayNamePlaceholder).toBe("Wie sollen wir dich nennen?");
  });

  it("en + NEXT_FORMALITY=formal is byte-identical to the en base (no overlay ever)", async () => {
    cookieStore.set("NEXT_LOCALE", "en");
    cookieStore.set("NEXT_FORMALITY", "formal");
    const { locale, messages } = await loadMessages("en");
    expect(locale).toBe("en");
    const baseAuth = (await import("../../i18n/messages/en/auth.json")).default;
    expect(messages.auth).toEqual(baseAuth);
  });

  it("fr + NEXT_FORMALITY=formal merges cleanly; FR overlay equals the base (documented no-op)", async () => {
    cookieStore.set("NEXT_LOCALE", "fr");
    cookieStore.set("NEXT_FORMALITY", "formal");
    const { messages } = await loadMessages("fr");
    // The FR base catalog already uses vouvoiement; the parity-required
    // overlay's values are byte-equal to the base (forward-correct for a
    // future tutoiement base). The merge must be a clean no-op, never a crash.
    expect(ns(messages, "auth").displayNamePlaceholder).toBe("Comment devons-nous vous appeler ?");
  });
});
```

- [ ] **Step 2: Run the tests (characterization — expected PASS, see Ruling 2)**

Run: `cd packages/web && npx vitest run __tests__/i18n-request-formality.test.ts`
Expected: `Test Files  1 passed (1)`, `Tests  7 passed (7)`.
If any test FAILS against the shipped code: **STOP and report** — a failure means `main`'s loader diverges from the spec DoD; do not modify production code (Global Constraint).

- [ ] **Step 3: Lint/format + type gates on the new file**

Run: `cd packages/web && npx biome check __tests__/i18n-request-formality.test.ts && pnpm type-check`
Expected: biome `Checked 1 file … No fixes applied` with NO error line; `tsc --noEmit` exits 0 (no output).

- [ ] **Step 4: Full frontend suite (no cross-test interference)**

Run: `just test-frontend`
Expected: full vitest suite green (baseline 2026-08-18: the three existing formality files alone are 19/19).

- [ ] **Step 5: Commit (via Platform, verbatim)**

Stage exactly one file:
```bash
git add packages/web/__tests__/i18n-request-formality.test.ts
```
Pre-flight: `git status --porcelain` must show ONLY that file staged, nothing else.

Commit message:
```
test(i18n): loader-level formality behavior tests (B closure)

Pins the one untested seam of I-Copy-001 (program item B): the loader in
lib/i18n/request.ts — NEXT_FORMALITY cookie read -> conditional deep-merge
-> the message object next-intl receives. The helper
(i18n-mergeOverlay.test.ts), the governance rules
(i18n-namespace-registry.test.ts) and the UI control
(formality-switcher.test.tsx) were already covered; these 7 tests execute
the loader itself, including the spec's "en byte-identical in both
registers" DoD as a direct assertion (en + formal === base import).

Mechanics (probed 2026-08-18): in-memory cookie store mock for
next/headers; identity passthrough mock for next-intl/server (under
happy-dom its browser export condition resolves to the client shim which
throws; the server registration is next-intl plumbing, not loader logic).
No production change — characterization tests for shipped behavior
(17ad629d, 2026-08-09).
```

---

### Task 2: Docs Closure — Spec Status, Feature INDEX, CURRENT_STATE (Program Complete)

**Files:**
- Modify: `docs/features/i18n/I-Copy-001-formality-register.md`
- Modify: `docs/features/INDEX.md`
- Modify: `docs/_shared/CURRENT_STATE.md`

**Interfaces:**
- Consumes: Task 1's landed commit (the DoD ticks and history entry reference `__tests__/i18n-request-formality.test.ts` and its 7 tests as facts — Task 1 must be committed first).
- Produces: closed documentation state — spec `status: implemented`, INDEX row `✅`, CURRENT_STATE B-closure entry marking the Post-Export Follow-ups program (C0→C5→C1→C2→C3→C4→B) complete.

- [ ] **Step 1: Update the feature spec — frontmatter status**

In `docs/features/i18n/I-Copy-001-formality-register.md` frontmatter, replace:

```
status: planned
```

with:

```
status: implemented
```

(Exactly one occurrence — the frontmatter line; verify with `grep -n "^status:" docs/features/i18n/I-Copy-001-formality-register.md` before and after.)

- [ ] **Step 2: Align the user-perspective section with the shipped placement**

In the same file, §"How it works (User perspective)", replace:

```
1. Open **Settings → Appearance** (or the existing language/locale area).
2. Pick **Anrede** (Address): *Vertraut (du)* [default] or *Neutral (Sie)*.
```

with:

```
1. Open the language/locale area on the auth screens (bottom-right corner, beside the
   language switcher — this spec's "existing language/locale area" option; the studio
   Settings language control is API-backed, while formality is cookie-only in v1).
2. Pick **Anrede** (Address): *Du* [default] or *Sie* (FR: *tu* / *vous*). The control is
   hidden for `en`.
```

(Items 3–4 of that numbered list stay unchanged.)

- [ ] **Step 3: Tick the DoD checkboxes**

In the same file, §"Acceptance criteria / Definition of Done", replace the whole unchecked block:

```
- [ ] `NEXT_FORMALITY` cookie read in `request.ts`; default `"informal"`.
- [ ] Deep-merge of `overlays/formality/{locale}.json` over base when `locale !== "en" && formality === "formal"`.
- [ ] `mergeOverlay.ts` helper with unit tests covering flat, nested, and leaf-only-override cases.
- [ ] `overlays/formality/de.json` + `overlays/formality/fr.json` populated with the formal variants (~150–300/lang).
- [ ] Settings toggle mirrors the locale-switcher; choice persists across reloads.
- [ ] Extended AST test: orphan-override check + de/fr key parity + no `overlays/formality/en.json`.
- [ ] `en` message catalog byte-identical in both registers (asserted).
- [ ] Zero changes to `core/prompts/` (RULE-02 boundary verified); zero call-site migration.
- [ ] Frontend tests green; `just check` green.
```

with:

```
- [x] `NEXT_FORMALITY` cookie read in `request.ts`; default `"informal"`.
- [x] Deep-merge of `overlays/formality/{locale}.json` over base when `locale !== "en" && formality === "formal"`.
- [x] `mergeOverlay.ts` helper with unit tests covering flat, nested, and leaf-only-override cases.
- [x] `overlays/formality/de.json` + `overlays/formality/fr.json` populated with the formal variants (~150–300/lang).
- [x] Settings toggle mirrors the locale-switcher; choice persists across reloads.
- [x] Extended AST test: orphan-override check + de/fr key parity + no `overlays/formality/en.json`.
- [x] `en` message catalog byte-identical in both registers (asserted).
- [x] Zero changes to `core/prompts/` (RULE-02 boundary verified); zero call-site migration.
- [x] Frontend tests green; `just check` green.
```

(All nine are true on `main` after Task 1: the two previously untested letters are directly asserted by `__tests__/i18n-request-formality.test.ts`; the final gate is re-executed in Step 7.)

- [ ] **Step 4: Append the Status & History entry**

In the same file, §"Status & History", append after the existing `2026-08-08` entry:

```markdown
- `2026-08-18` — **B closure — implemented & verified** (program item B of the Post-Export
  Follow-ups). Spec `2026-08-08`, shipped `2026-08-09` in commits `17ad629d`
  (loader + `mergeOverlay` + `FormalitySwitcher` + governance tests) and `da5c73d2`
  (159 DE formal variants + FR parity overlay) — before the program design doc existed;
  the B slice therefore verifies the DoD and closes the one test gap: loader-level
  behavior tests (`__tests__/i18n-request-formality.test.ts`, 7 tests incl. the executed
  `en`-byte-identical assertion). Toggle shipped in the language/locale area on the auth
  screens (this spec's parenthetical option; the Settings language control is API-backed
  while formality is cookie-only v1). FR overlay values are byte-equal to the FR base
  (already vouvoiement) — documented forward-correct no-op for a future tutoiement base.
  Status → `implemented`.
```

- [ ] **Step 5: Update the features INDEX**

In `docs/features/INDEX.md`, §"Internationalization & UI Copy", replace the row:

```
| [I-Copy-001](i18n/I-Copy-001-formality-register.md) | User-Selectable UI Formality (du / Sie) | 📋 | ❌ |
```

with:

```
| [I-Copy-001](i18n/I-Copy-001-formality-register.md) | User-Selectable UI Formality (du / Sie) | ✅ | ❌ |
```

Then, in the I-Copy-001 note below the table, replace the tail:

```
(~150–300 formal DE/FR variants to author/review). Status → `planned`.
```

with:

```
(~150–300 formal DE/FR variants to author/review). Spec 2026-08-08, shipped 2026-08-09 (`17ad629d` +
`da5c73d2`): 159/159 DE/FR tone-sensitive variants (FR = forward-correct no-op — base
already vouvoiement); switcher beside the auth-screen language switcher; loader behavior
tests 2026-08-18 (B closure). Status → `implemented`.
```

- [ ] **Step 6: Add the CURRENT_STATE entry**

In `docs/_shared/CURRENT_STATE.md`, §"Last Updated", add this new dated entry as the NEW TOP entry (above the current `Date: 2026-08-17 (**C3 — DOCX Export — implemented**; …)` entry):

```markdown
Date: 2026-08-18 (**B — I-Copy-001 Formality Register — closure; Post-Export Follow-ups program COMPLETE** (C0→C5→C1→C2→C3→C4→B); plan [2026-08-18-b-i-copy-001-formality-register.md](superpowers/plans/2026-08-18-b-i-copy-001-formality-register.md)). I-Copy-001 (Q-015 resolution): user-selectable UI formality (du/Sie, tu/vous) for de/fr; `en` byte-identical. Resolved one layer before next-intl in the message loader (`packages/web/lib/i18n/request.ts`): the `NEXT_FORMALITY` cookie (default informal) conditionally deep-merges the sparse `packages/i18n/overlays/formality/{de,fr}.json` over the base catalog (159 tone-sensitive leaf overrides per language — studio 103, wizard 13, settings 11, editor 10, analysis 9, …; tone-neutral labels fall through). Zero call-site migration; `next-intl` untouched; RULE-02 boundary (UI-copy-only — cannot reach `core/prompts/`); cookie-only persistence v1 (no backend/migration); `FormalitySwitcher` beside the auth-screen `LanguageSwitcher` (hidden for en). **Honest history:** spec 2026-08-08; implementation shipped 2026-08-09 in `17ad629d` + `da5c73d2` — BEFORE the 2026-08-14 program design doc listed B as pending; the B slice = empirical DoD audit + the one missing test layer (loader behavior tests, `__tests__/i18n-request-formality.test.ts` — 7 tests incl. the `en`-byte-identical DoD as a direct assertion) + docs closure. FR overlay = documented forward-correct no-op (FR base already vouvoiement; values byte-equal, parity-required). Governance: orphan-override + de/fr parity + no-en assertions in `i18n-namespace-registry.test.ts`; `validate-i18n` consciously scoped to `messages/` (formality is a register, not a locale). **Open hygiene (flagged separately, out of B scope):** C4's own CURRENT_STATE entry is still pending.
```

- [ ] **Step 7: Sweep for stale live claims + run the slice-final gates**

Sweep (verify no stale "planned" live claim remains — historical records stay verbatim):

```bash
rg -n "I-Copy-001" docs/ --glob '!docs/superpowers/plans/*'
```
Expected: remaining matches are historical-resolution records (Q-015 resolved file, questions INDEX, the CURRENT_STATE 2026-08-15 program-scope entry) or the updated live text (spec, feature INDEX, new CURRENT_STATE entry). No live "not yet implemented / planned" claim about I-Copy-001 outside historical entries.

Run, in order:
```bash
just check
just typecheck
just lint-check
just test-unit
cd packages/web && pnpm type-check && pnpm lint:check && cd ../..
just test-frontend
```
Expected: PASS on every gate. Rationale for the set (design §12 B gate = "Per existing I-Copy-001 spec DoD", whose final item is "Frontend tests green; `just check` green"): `just check` runs the full checks suite (architecture, validate-i18n, file size, secrets, docs drift); `just typecheck`/`lint-check`/`test-unit` are cheap python-side neutrality proof (zero python files changed); frontend trio is the feature's home turf. `just test-integration`/E2E are not in §12's B gate and touch no changed surface (zero backend files) — omitted deliberately, not skipped silently.

- [ ] **Step 8: Commit (via Platform, verbatim)**

Stage exactly three files:
```bash
git add docs/features/i18n/I-Copy-001-formality-register.md \
        docs/features/INDEX.md \
        docs/_shared/CURRENT_STATE.md
```
Pre-flight: `git status --porcelain` must show ONLY those three files staged.

Commit message:
```
docs(i18n): B closure — I-Copy-001 implemented, followups program complete

Documents program item B (I-Copy-001, Q-015 resolution) as shipped and
closes the Post-Export Follow-ups program (C0->C5->C1->C2->C3->C4->B).

- I-Copy-001 spec: status planned -> implemented; user-perspective section
  aligned with the shipped placement (language/locale area on the auth
  screens — the spec's own parenthetical option; the Settings language
  control is API-backed while formality is cookie-only v1); DoD ticked
  (the loader tests from the prior commit close the two test-enforced
  letters); dated Status & History entry (spec 2026-08-08, implemented 2026-08-09 in
  17ad629d + da5c73d2 — before the program design doc existed; B slice
  = DoD verification + loader tests + this closure; FR overlay is the
  documented forward-correct no-op).
- features INDEX: I-Copy-001 row -> done; note extended with shipped
  facts (159/159 DE/FR variants).
- CURRENT_STATE: dated B-closure entry; program complete. Notes C4's own
  CURRENT_STATE entry is still pending (flagged separately, not absorbed).

Refs: docs/features/i18n/I-Copy-001-formality-register.md,
docs/superpowers/specs/2026-08-14-post-export-followups-design.md (§8, §12)
```

---

## Self-Review (performed at plan time — findings recorded honestly)

**1. Spec coverage (I-Copy-001 DoD → tasks):**

| DoD item | Covered by |
|---|---|
| `NEXT_FORMALITY` read; default informal | Shipped (`17ad629d`); directly asserted — Task 1 tests 3–5 (default / explicit informal / garbage value) |
| Deep-merge when formal && ≠ en | Shipped; directly asserted — Task 1 tests 1, 2, 7 (de merge, neutral fall-through, fr merge) |
| `mergeOverlay` helper + unit tests | Shipped; existing `i18n-mergeOverlay.test.ts` (9 tests) — re-verified green 2026-08-18 |
| Overlays populated ~150–300/lang | Shipped; 159/159 verified at plan time — recorded in docs (Task 2) |
| Toggle mirrors locale-switcher; persists | Shipped; `formality-switcher.test.tsx` (5 tests) green; placement ruling 1 + spec-text alignment (Task 2 Step 2) |
| Governance test (orphan/parity/no-en) | Shipped; `i18n-namespace-registry.test.ts` (4 assertions) green |
| `en` byte-identical **asserted** | Task 1 test 6 (direct execution: en + formal ≡ base JSON import) — the DoD letter this slice adds |
| Zero `core/prompts/` / call-site changes | Enforced by scope: zero production files touched (Global Constraint + diff pre-flight) |
| Frontend tests green; `just check` green | Task 1 Steps 2–4; Task 2 Step 7 |

Design §8's "implemented 1:1" is satisfied by the shipped state; the plan adds only what §12's gate demands (DoD verification) plus docs. No gaps.

**2. Placeholder scan:** every code/doc step carries verbatim content (the full validated test file; exact replacement strings for all six doc edits; both commit messages complete). No TBD/TODO/"similar to Task N".

**3. Type consistency:** `RequestConfigFn` cast target matches `request.ts`'s actual return shape `{ locale, messages }` (verified by executing it); `ns()` returns `Record<string, unknown>` so both leaf accesses type-check (tsc-validated); file/test names quoted in Task 2 (`__tests__/i18n-request-formality.test.ts`, "7 tests") match Task 1 exactly; commit hashes `17ad629d`/`da5c73d2` verified against `git log`.

**4. Empirical basis (probes run 2026-08-18 on this machine):** (a) the identity-mock requirement was discovered by a failing probe (`getRequestConfig is not supported in Client Components` — next-intl 4.13.1 browser export condition under happy-dom); (b) the FULL Task 1 test file was executed green (7/7 vitest, biome clean, `tsc --noEmit` clean) and then deleted — tree confirmed clean (`git status --porcelain` empty); (c) a plan-draft typo ("devrons" vs "devons" in the FR assertion) was caught by that executed run and corrected — the embedded code is the corrected, re-validated version; (d) overlay counts and DE-differs/FR-equals facts computed directly from the JSON files; (e) the 19-test baseline of the three existing formality files re-run green.

**5. Discrepancies found during investigation (reported to the coordinator):**
1. **The dispatch premise is stale:** I-Copy-001 was already implemented on `main` (spec Aug 8, shipped Aug 9, commits `17ad629d` + `da5c73d2`) before the program design doc (Aug 14) listed B as pending; the session-checkpoint memory ("B … needs writing-plans → Frontend execution") predates reconciliation with the repo state. Plan scope adjusted accordingly (verify + close, not implement).
2. **C4's CURRENT_STATE entry is missing** (top entry is C3, 2026-08-17, while C4's six commits are in history). Out of B's scope — flagged; Task 2's entry notes it as open hygiene rather than fabricating a C4 record.
3. **`da5c73d2`'s commit-message claim "FR overlay is currently a functional no-op" is accurate** (verified: 159/159 FR values byte-equal to base) — documented as intentional (Ruling 4), not a defect.
