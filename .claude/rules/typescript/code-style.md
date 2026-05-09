---
paths:
  - "packages/web/**/*.ts"
  - "packages/web/**/*.tsx"
---

# TypeScript/React Code Style

## Component Structure
```typescript
// 1. Imports (external → internal → types)
import { useState } from "react"
import { useStreamingText } from "@/hooks/useStreamingText"
import type { Draft } from "@/types/writing"

// 2. Types (co-located)
interface DraftPanelProps {
  draft: Draft
  onAccept: (draft: Draft) => void
}

// 3. Component (named export)
export function DraftPanel({ draft, onAccept }: DraftPanelProps) {
  // hooks first
  // derived state
  // handlers
  // render
}
```

## File size limits
- Page component: 100 lines
- Feature component: 200 lines
- Hook: 150 lines
- Store: 150 lines

## State management
- Server state: TanStack Query
- UI state: Zustand
- Local state: useState
- Forms: React Hook Form

Full documentation: docs/development/coding-standards.md
