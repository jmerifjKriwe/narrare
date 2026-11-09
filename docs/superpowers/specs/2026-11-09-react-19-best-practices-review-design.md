# Spec: React 19 Best-Practices Review

**Date:** 2026-11-09
**Status:** Draft
**Author:** Coordinator
**Implements:** Audit follow-up item E18

---

## 1. Problem

The web app runs React 19.3.1 but was written incrementally across multiple waves
(frontend-foundation, frontend-surfaces, frontend-depth, knowledge-depth, merit-closeout).
Some components predate React 19 patterns and carry manual memoization, effect-based
data fetching, and prop-drilling that newer React 19 primitives (`use()`, `useActionState`,
`useFormStatus`, `useOptimistic`) or the React Compiler could simplify. The
`vercel-react-best-practices` skill exists but has not been applied systematically.

## 2. Goals

- Review `NovelPage.tsx` (1378 lines) and `ChatPanel.tsx` (193 lines) for React 19
  anti-patterns and improvement opportunities.
- Produce a prioritized list of findings with effort/impact ratings.
- Apply only low-risk, high-value fixes in this pass; defer larger refactors.
- No behavioral changes — all existing tests must pass unchanged.
- No new dependency, no new gate, no new standing rule (CONSTRAINTS §8).

## 3. Non-Goals

- Enabling the React Compiler (requires build pipeline changes, separate task).
- Rewriting component architecture (e.g., splitting NovelPage into smaller components).
- Changing routing or state management strategy.
- Adding new features or UI changes.

## 4. Scope

**In scope:**
- `app/capabilities/writing/web/NovelPage.tsx`
- `app/capabilities/chat/web/ChatPanel.tsx`
- Shared shell components they depend on (only if a finding requires it).

**Out of scope:**
- Other capability pages (knowledge, settings, etc.) — separate pass.
- E2E tests (no changes).
- CSS/layout.

## 5. Review Checklist (React 19 Best Practices)

### 5.1 Memoization
- [ ] `useMemo`/`useCallback` with empty deps `[]` — verify no stale closures.
- [ ] `useMemo`/`useCallback` with missing deps — exhaustive-deps violations.
- [ ] Remove manual memoization that the React Compiler would handle (if compiler
      is later enabled) — document, don't remove now.

### 5.2 Effects
- [ ] `useEffect` that fetches data — candidate for `use()` or TanStack Query.
- [ ] `useEffect` with cleanup that could be a return function.
- [ ] Effects that run on every render (missing deps array).
- [ ] Effects that set state based on props (derive instead).

### 5.3 State
- [ ] State updates during render (should use `useMemo` or derive).
- [ ] `useState` initialized with a function call (should be lazy initializer).
- [ ] Multiple related `useState` that could be `useReducer`.
- [ ] `useRef` used as state (should be `useState` if it triggers re-render).

### 5.4 Rendering
- [ ] Missing `key` props in lists.
- [ ] Inline object/array creation in JSX props (new reference every render).
- [ ] Conditional rendering with `&&` (potential 0-render bug).
- [ ] `React.memo` on components that receive new props every render (useless).

### 5.5 React 19 Specifics
- [ ] `forwardRef` usage — React 19 allows `ref` as a regular prop.
- [ ] Context providers — React 19 allows `<Context>` directly instead of `<Context.Provider>`.
- [ ] `use()` hook for promises/context in render.
- [ ] `useActionState` / `useFormStatus` for form handling.

### 5.6 Performance
- [ ] Unnecessary re-renders (parent state change re-rendering children).
- [ ] Large inline computations in render.
- [ ] Missing `Suspense` boundaries for lazy components.

## 6. Deliverables

1. A findings report (`docs/superpowers/reports/2026-11-09-react-19-review.md`)
   with per-finding: location, severity, description, recommended fix, effort.
2. Low-risk fixes applied (e.g., stale closure fixes, missing keys, `forwardRef` → `ref` prop).
3. Medium/high-risk findings documented as follow-up issues.
4. All existing tests pass unchanged.

## 7. Constraints

- No behavioral changes — tests must pass unmodified.
- No new dependency, no new gate, no new standing rule (CONSTRAINTS §8).
- Changes limited to the two named files (+ shared components only if a finding
  requires it).
- English in code/tests/docs.
EOF