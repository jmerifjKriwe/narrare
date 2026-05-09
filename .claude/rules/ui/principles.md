---
paths:
  - "packages/web/**/*.tsx"
---

# UX Principles (Non-Negotiable)

1. The writing surface is sacred — editor is center
2. AI responses stream always — no blank loading areas
3. Errors are actionable or silent — no modals for non-critical
4. Settings persist without save buttons — immediate save
5. Language follows user setting — all strings from i18n

## Required patterns
```typescript
// Streaming
const { text, isStreaming } = useSSE<WriteResponse>({
  url: "/api/writing/new-chapter",
  body: request,
})

// i18n (every user-facing string)
const { t } = useTranslations("editor")
<button>{t("saveChapter")}</button>

// Design tokens (no inline styles)
<div className="bg-primary"> // ✅
<div style={{ backgroundColor: "#faf9f7" }}> // ❌
```

Full documentation: docs/development/ui-principles.md
