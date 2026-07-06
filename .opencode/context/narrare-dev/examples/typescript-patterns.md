<!-- Context: narrare-dev/examples/typescript-patterns | Priority: P2 | Source: docs/development/coding-standards.md | Updated: 2026-06-12 -->

# TypeScript Patterns

TypeScript/React patterns for Narrare frontend (`packages/web/`). Tailwind CSS v4 only.

> **⛔ NEVER create `middleware.ts`.** Use `proxy.ts` exclusively (RULE-15). Creating `middleware.ts` is a CI build failure.

## Types

```typescript
// interface for object shapes, type for unions/intersections
interface Chapter { id: string; title: string; position: number; wordCount: number }
type WritingMode = "new_chapter" | "extend" | "rewrite" | "interactive"
type LoadingState = "idle" | "loading" | "success" | "error"

// Never use any — use unknown and narrow
// Never use non-null assertion (!) — handle null explicitly
// Always type function return values
const getChapter = async (id: string): Promise<Chapter> => { ... }
```

## React Components

- **Named exports** for components (not default — except Next.js page files)
- **`"use client"` directive** on all client components
- **Props inline**, defined above the component
- **Hooks → derived state → handlers → render** (internal order)
- Styling: Tailwind CSS v4 utilities + CSS variable tokens (`bg-[var(--color-accent)]`)
- Use `cn()` from `@/lib/utils` to merge Tailwind classes

```typescript
interface ChapterItemProps { chapter: Chapter; isActive: boolean; onSelect: (id: string) => void }

export function ChapterItem({ chapter, isActive, onSelect }: ChapterItemProps) {
  const t = useTranslations("editor")
  return (
    <button className={cn("px-3 py-2 rounded-[var(--radius-md)]", isActive && "bg-[var(--color-accent-light)]")}>
      {chapter.title}
    </button>
  )
}
```

## API Client

- Typed functions using central `fetchApi<T>()` wrapper with auto token refresh
- Components **never** call `fetch` directly — always use typed API functions
- SSE streaming: `connectSSE` from `@/lib/api/streaming`

```typescript
export const chaptersApi = {
  updateContent: async (novelId: string, chapterId: string, content: string) => {
    const { data } = await fetchApi<Chapter>(`/novels/${novelId}/chapters/${chapterId}/content`,
      { method: "PUT", body: JSON.stringify({ content }) })
    return data
  },
}
```

## i18n — Non-Negotiable

Every user-facing string uses `useTranslations()`. **Zero** hardcoded English in components.

```typescript
const t = useTranslations("editor")
<button>{t("saveChapter")}</button>   // ✅
<button>Save Chapter</button>          // ❌
```

- 3 locales: **en** (reference), **de**, **fr**
- Namespace files: `packages/i18n/messages/{locale}/{namespace}.json`
- Namespaces: `common`, `auth`, `wizard`, `dashboard`, `editor`, `errors`, `settings`
- `validate-i18n.ts` catches missing keys in CI

## Component Structure (5-step order)

```typescript
"use client";                                    // 1. Directive
import { useState } from "react";                // 2. Imports (external → internal)
import { useTranslations } from "next-intl";
interface MyProps { content: string }             // 3. Types (co-located)
const MOCK = [...];                              // 4. Constants
export function MyComponent({ content }: MyProps) { // 5. Component (named export)
  const t = useTranslations("studio");           // hooks → derived → handlers → render
}
```

## Git Commits

Conventional Commits: `feat(writing): add chapter reorder`. Types: `feat`, `fix`, `docs`, `chore`, `test`, `refactor`, `perf`, `ci`. Scope: domain module or `core`, `deps`, `infra`.

**Reference**: `docs/development/coding-standards.md`
**Related**: narrare-dev/examples/python-patterns · narrare-dev/concepts/design-philosophy · narrare-dev/lookup/design-tokens
