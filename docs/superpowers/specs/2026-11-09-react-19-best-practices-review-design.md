# Spec: React 19 Best-Practices Review

**Date:** 2026-11-09
**Status:** Proposed
**Author:** Coordinator

---

## 1. Problem

The web app runs React 19.3.1 but was written incrementally across several
waves. Some components predate React 19 patterns and carry manual memoization,
effect-based data fetching and prop drilling that newer primitives
(`useActionState`, `useFormStatus`, `useOptimistic`, `use()`) or a compiler could
simplify. The `vercel-react-best-practices` skill exists but has never been
applied systematically to the two largest surfaces.

This spec defines a **review pass**, not a refactor: findings are recorded with
severity and effort, only mechanical fixes are applied, everything else becomes
a follow-up issue.

## 2. Goals

- Review `NovelPage.tsx` (1378 lines) and `ChatPanel.tsx` (193 lines) against the
  checklist in §5, and record a verdict for **every** item — including "no
  finding", so an unchecked category is visible.
- Apply only fixes that are mechanically safe (§4) — no observable change.
- Write a findings report with a per-finding severity, location, description,
  recommended fix and effort.
- File one GitHub issue per surviving medium/high finding, with the repo's
  labels, under the review index.

## 3. Non-Goals

- Enabling the React Compiler (separate build-pipeline change).
- Splitting `NovelPage` into components, changing routing or the state strategy.
- Converting data fetching to `use()` or a different query pattern in this pass.
- Any new feature, UI change, dependency, gate or standing rule (CONSTRAINTS §8).
- Changes to tests. A fix that needs a test changed is not low-risk (§4).

## 4. Scope and Risk Rubric

**In scope:** `app/capabilities/writing/web/NovelPage.tsx`,
`app/capabilities/chat/web/ChatPanel.tsx`, and a shared shell component only if a
specific finding requires it.

**Out of scope:** other capability pages, E2E tests, CSS and layout.

**Low-risk** (may be applied in this pass) means all four hold:

1. Mechanical: typing, an import, a `forwardRef` → `ref` prop, `<Context.Provider>`
   → `<Context>`, a missing `key`, a dependency-array typo whose fix cannot change
   the rendered order or the number of requests.
2. No observable change: the same DOM in the same order, the same text, the same
   network calls in the same order.
3. No test modification needed; the suite passes untouched.
4. The commit subject can be `refactor(...)` honestly. If the change needs a
   `feat`/`fix` with a `User-visible:` line, it is not low-risk.

Everything else — an effect rewrite, a fetch change, a state-shape change, a
split — is **documented**, not applied.

## 5. Review Checklist

Every item gets a verdict in the report: `finding` (with an id), `clean`, or
`n/a` with the reason.

### 5.1 Memoization
- `useMemo`/`useCallback` with `[]` — stale closures.
- Missing dependencies — exhaustive-deps violations.
- Manual memoization a compiler would subsume — **document only**, never removed
  in this pass.

### 5.2 Effects
- `useEffect` that fetches data — **document only** in this pass; the conversion
  is an architecture change (§3), not a mechanical fix.
- Cleanup that should be a returned function.
- Effects with no dependency array.
- Effects that set state from props — derive instead; document only.

### 5.3 State
- State updates during render.
- Eager initialisation that should be a lazy initializer.
- Related `useState` calls that suggest `useReducer` — document only.
- `useRef` used where a render is intended.

### 5.4 Rendering
- Missing `key` props.
- New object/array literals in JSX props — document only unless the fix is
  hoisting a constant.
- Conditional rendering with `&&` where `0` would render.
- `React.memo` that is useless because props are new every render.

### 5.5 React 19 Specifics
- `forwardRef` where `ref` is a normal prop now.
- `<Context.Provider>` where `<Context>` suffices.
- `use()` for promises/context — document only.
- `useActionState` / `useFormStatus` for forms — document only.

### 5.6 Composition
- Prop drilling a value that context or `use()` would carry — document only.
- Unnecessary re-renders from a parent state change.
- Large inline computations in render.
- Missing `Suspense` boundaries for lazy components.

## 6. Deliverables

1. `docs/superpowers/reports/2026-11-09-react-19-review.md` with:
   - a verdict per checklist item,
   - per finding: id, file:line, severity (`blocker`/`major`/`minor`), risk
     class (`low`/`medium`/`high`), description, recommended fix, effort,
   - a summary table of counts by severity and risk,
   - the applied fixes (commit subjects) and the issue numbers created,
   - an explicit "not verified" section for anything the reviewer could not
     exercise.
2. Low-risk fixes, each its own commit.
3. One issue per surviving finding:
   `--label follow-up --label "severity: minor|major" --label "area: <where>"`
   plus `--label "kind: <nature>"` where one applies
   (`a11y`, `race`, `test-gap`, …). `area` names where the finding lives —
   `writing` for `NovelPage`, `chat` for `ChatPanel`, `web` only for shared
   shell code. The issues hang under index **#308** ("Reviews and audits outside
   a wave") and the report lists every number.
4. All existing tests pass unmodified.

## 7. Constraints

- No behavioral change; tests unmodified (§4).
- No new dependency, gate or standing rule (CONSTRAINTS §8).
- English in code, tests and docs.
- The report states what was found, what was fixed, what was deferred and why —
  an honest audit, not a victory list.

## 8. Verification

- `just check` — lint and types.
- `just test-frontend` — the web unit suite.
- `just test-e2e writing` and `just test-e2e chat` — the two affected
  capabilities, which is what rule 2 asks for.
- `git diff --name-only | rg '(test|spec)\.'` prints nothing: no test file was
  touched.
- Every issue referenced in the report exists with the labels above.
