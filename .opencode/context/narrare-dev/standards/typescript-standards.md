<!-- Context: narrare-dev/standards/typescript-standards | Priority: high | Source: docs/development/coding-standards.md (TypeScript section) | Updated: 2026-06-12 -->

# TypeScript/React Standards — Quick Reference

Concise code patterns. Full reference: `docs/development/coding-standards.md`.

---

## THE CARDINAL RULE (RULE-15)

> **NEVER create `middleware.ts` in this project.**
> Next.js 16+ uses `proxy.ts` exclusively. Creating `middleware.ts` causes a hard build failure enforced by CI.
> Route protection, auth checks, redirects: edit `packages/web/proxy.ts` only.

---

## Types

```typescript
// Prefer interface for object shapes, type for unions/intersections
interface Chapter {
  id: string
  title: string
  position: number
  wordCount: number
  updatedAt: string
}

type WritingMode = "new_chapter" | "extend" | "rewrite" | "interactive"
type LoadingState = "idle" | "loading" | "success" | "error"

// Never use any — use unknown and narrow
// Never use non-null assertion (!) — handle null explicitly
// Always type function return values
const getChapter = async (id: string): Promise<Chapter> => { ... }
```

---

## React Components

```typescript
// Named exports (not default — easier to search)
// Exception: Next.js page files require default export

// Styling: Tailwind CSS v4 utility classes ONLY.
// Design tokens via CSS variables: bg-[var(--color-accent)]
// cn() from @/lib/utils merges Tailwind classes safely

interface ChapterItemProps {
  chapter: Chapter
  isActive: boolean
  onSelect: (id: string) => void
}

export function ChapterItem({ chapter, isActive, onSelect }: ChapterItemProps) {
  const t = useTranslations("editor")

  const formattedWordCount = chapter.wordCount.toLocaleString()
  const handleClick = () => onSelect(chapter.id)

  return (
    <button
      onClick={handleClick}
      className={cn(
        "flex-1 flex flex-col items-start py-2 px-3 border-none bg-transparent",
        "cursor-pointer rounded-[var(--radius-md)] text-left min-w-0",
        "hover:bg-[var(--color-bg-secondary)]",
        isActive && "bg-[var(--color-accent-light)] text-[var(--color-accent)]"
      )}
    >
      <span className="text-sm font-medium text-[var(--color-text-primary)]">
        {chapter.title}
      </span>
      <span className="text-xs text-[var(--color-text-tertiary)]">
        {formattedWordCount} {t("words")}
      </span>
    </button>
  )
}
```

---

## Tailwind v4 + CSS Variable Tokens

```typescript
// All colors via CSS variables defined in styles/globals.css
// NEVER hardcode colors: text-red-500 → WRONG
// ALWAYS use tokens: text-[var(--color-error)] → RIGHT

// Token categories:
// --color-accent, --color-error, --color-warning, --color-success
// --color-text-primary, --color-text-secondary, --color-text-tertiary
// --color-bg-primary, --color-bg-secondary, --color-bg-card
// --radius-sm, --radius-md, --radius-lg
```

---

## API Client

```typescript
// Typed API functions using native fetch — never raw fetch in components
// Central fetchApi<T>() wrapper with auto token refresh
// All in packages/web/lib/api/client.ts

export const chaptersApi = {
  updateContent: async (novelId: string, chapterId: string, content: string) => {
    const { data } = await fetchApi<Chapter>(
      `/novels/${novelId}/chapters/${chapterId}/content`,
      { method: "PUT", body: JSON.stringify({ content }) },
    )
    return data
  },
}

// For SSE streaming (AI responses):
import { connectSSE } from "@/lib/api/streaming"
```

---

## i18n (Non-Negotiable)

```typescript
// EVERY user-facing string uses useTranslations()
// ZERO hardcoded English in components

// WRONG:
<button>Save Chapter</button>

// CORRECT:
const t = useTranslations("editor")
<button>{t("saveChapter")}</button>

// Adding a new translation key:
// 1. Add to packages/i18n/messages/en/<namespace>.json
// 2. Add to packages/i18n/messages/de/<namespace>.json
// 3. Add to packages/i18n/messages/fr/<namespace>.json
// 4. Register namespace in lib/i18n/request.ts (RULE-16)

// Namespaces: common, auth, wizard, dashboard, editor, errors, settings
```

---

## State Management

| Data Type | Tool | Location |
|-----------|------|----------|
| Server data (chapters, novels, user) | TanStack Query v5 | Components via `useQuery` |
| UI state (sidebar, focus mode) | Zustand | `lib/stores/` |

**Never** store server data in Zustand. **Never** use Zustand for API calls.

---

**Reference**: `docs/development/coding-standards.md` lines 453-576
**Related**: narrare-dev/examples/typescript-patterns · narrare-dev/standards/python-standards · narrare-dev/lookup/design-tokens
