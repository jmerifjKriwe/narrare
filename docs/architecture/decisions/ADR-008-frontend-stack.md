# ADR-008 — Frontend Architecture & Technology Stack

> **Status:** ✅ Accepted
> **Date:** 2026-05-12
> **Deciders:** Architecture Agent + Orchestrator
> **Supersedes:** —

---

## Context

Phase 4 required building a complete frontend for Narrare — a creative writing tool with
a rich text editor, real-time AI interactions, and multi-language support. The frontend
needed to handle:

1. A TipTap v3 rich text editor with custom extensions (scene breaks, inline AI)
2. SSE streaming for AI-generated content (writing, analysis, suggestions)
3. Internationalization in 3 languages (en, de, fr) with enforcement
4. Responsive layout with collapsible panels and focus mode
5. Authentication with token refresh and session management
6. A design system that is warm, literary, and not "dashboard-like"

The initial scaffold used Next.js 15 + axios + styled-jsx + Zustand for all state.
After auditing the frontend stack, significant optimizations were identified and applied.

---

## Decision Drivers

- **SSE streaming is a core requirement** — "AI responses stream. Always."
- **One styling system** — mixing styled-jsx and Tailwind creates cognitive overhead
- **Server state vs. UI state** — these are fundamentally different and should not be conflated
- **Minimal dependencies** — every dep is a maintenance burden, security surface, and cognitive load
- **i18n must be enforced** — hardcoded strings are bugs that automation should catch
- **Accessibility** — the writing surface is sacred; errors and loading must be handled gracefully

---

## Options Considered

### For HTTP Client

**Option A: axios** — Keep the existing axios setup
**Option B: native fetch** — Remove axios, use fetch for all HTTP + SSE

### For Styling

**Option A: styled-jsx** — Keep Next.js built-in CSS-in-JS
**Option B: Tailwind CSS v4** — Utility-only, CSS variable-based design tokens
**Option C: CSS Modules** — Scoped CSS with .module.css files

### For State Management

**Option A: Zustand for everything** — Server data + UI state in Zustand
**Option B: TanStack Query + Zustand** — Server state in TanStack, UI state in Zustand

### For Component Primitives

**Option A: Build everything from scratch** — Custom Button, Dialog, Toast, etc.
**Option B: shadcn/ui** — Copy-paste Radix-based primitives, customized with Tailwind
**Option C: Full component library** — MUI, Chakra, or Ant Design

---

## Decision

**We choose:**

- **HTTP:** Option B — native fetch. axios cannot handle SSE streaming, adding a dependency
  that fundamentally cannot serve our core use case.
- **Styling:** Option B — Tailwind CSS v4. One system, utility-first, CSS variables for tokens.
  styled-jsx was creating two styling worlds that developers had to choose between every file.
- **State:** Option B — TanStack Query + Zustand. Server data (novels, chapters, user, settings)
  belongs in TanStack Query with its caching, invalidation, and background refresh. Only true
  UI state (sidebar toggles, focus mode, save status) goes in Zustand.
- **Components:** Option B — shadcn/ui. Not a runtime dependency — we own the code. Radix UI
  provides accessible primitives. We customize with our design tokens. Growing the component
  library organically as features are added.

**Additionally:**
- **motion** for animations (formerly Framer Motion)
- **jose** for Edge-compatible JWT validation in middleware
- **Biome** for linting and formatting (replaces ESLint)
- **validate-i18n.ts** (custom AST checker via ts-morph) for hardcoded string detection

---

## Rationale

**fetch over axios:** The SSE requirement is non-negotiable. Running two HTTP clients
(axios for CRUD, fetch for streaming) creates confusion. fetch handles both, and Next.js 15
has built-in fetch optimizations (deduplication, caching).

**Tailwind over styled-jsx:** Tailwind v4's CSS-native configuration eliminated the need
for `tailwind.config.js`. Combined with CSS variables in `globals.css`, we get a complete
design token system without any runtime JS. styled-jsx's scoped styles created fragmented
ownership — the same component's layout, spacing, and colors lived in different systems.

**TanStack Query for server state:** The initial approach synced TanStack Query data into
Zustand via `useEffect` — a React anti-pattern that creates two sources of truth. TanStack
Query IS the state for server data. Zustand is ONLY for UI toggles.

**shadcn/ui over full library:** A full component library (MUI, Chakra) imposes its design
system on us. For a writing tool with a warm, literary aesthetic, we need full control.
shadcn gives us accessible primitives without a runtime dependency.

---

## Consequences

**Positive:**
- One HTTP client (fetch), one styling system (Tailwind), clear state boundaries
- SSE streaming ready for all AI features
- i18n enforcement prevents hardcoded string bugs
- shadcn/ui gives accessible components without vendor lock-in
- ~600 lines of code removed by Tailwind migration (styled-jsx blocks eliminated)
- 101 frontend tests covering core utilities and stores

**Negative / Tradeoffs:**
- Tailwind utility classes in JSX can be verbose — mitigated by `cn()` and component extraction
- shadcn/ui components are copied, not imported — updating them requires manual effort
- jose middleware validates JWT expiration but not signature (signature checked server-side)

**Constraints introduced:**
- Server data NEVER goes in Zustand stores (enforced by code review)
- All styling via Tailwind utilities + CSS variables (no styled-jsx, no inline styles)
- All user-facing strings via `useTranslations()` (enforced by validate-i18n.ts in pre-commit)

---

## Implementation Notes

- API client: `packages/web/lib/api/client.ts` (fetchApi wrapper) + `streaming.ts` (SSE)
- Design tokens: `packages/web/styles/globals.css` — all colors, spacing, typography as CSS variables
- State boundary: Zustand stores in `lib/stores/` — only `activeChapterId`, `saveStatus`, UI toggles
- shadcn config: `packages/web/components.json` — outputs to `@/components/shadcn/`
- i18n lint: `scripts/validate-i18n.ts` — AST-based hardcoded string detection via ts-morph
- Code lint: `packages/web/biome.json` — Biome for linting and formatting (replaces ESLint)
- Error handling: Route-level `error.tsx` files + client `<ErrorBoundary>` component

---

## Review Trigger

- [ ] When Tailwind v5 is released — evaluate migration
- [ ] When Next.js adds built-in SSE support — evaluate simplifying streaming.ts
- [ ] When shadcn/ui has breaking changes — assess migration effort
- [ ] After 20+ components — evaluate if Storybook would add value
