---
id: WRITE-001
title: "Writing Editor"
status: planned
area: writing
mvp: true

ui_tooltip: "Your writing surface — distraction-free, always saving, ready for AI assistance."
ui_help_short: |
  The editor is where you write. It automatically saves your work, tracks your
  word count, and has dedicated slots for every AI feature — available when
  you want them, invisible when you don't.
ui_help_long: |
  ## The Writing Editor

  Narrare's editor is built around one principle: your writing comes first.

  **Autosave**
  Your work is saved automatically. The interval is configurable in Settings
  (default: every 30 seconds). A small indicator shows save status — green
  means saved, spinning means saving.

  **Chapter navigation**
  The left sidebar lists all chapters in order. Click to switch chapters.
  Drag to reorder. The sidebar can be collapsed for a fully distraction-free view.

  **Word count**
  Live word count and estimated reading time are shown at the bottom of the
  editor. Hover for a chapter-vs-novel breakdown.

  **Formatting**
  The toolbar provides basic formatting: headings, bold, italic, scene breaks.
  Narrare uses a document model that understands narrative structure — not just
  rich text.

  **AI features (coming soon)**
  The toolbar has slots for AI actions. The right panel has space for AI-generated
  content. The command palette (Cmd+K) will give keyboard access to everything.
  None of these interrupt your writing — they activate only when you call them.

  **Keyboard shortcuts**
  - `Cmd/Ctrl + S` — force save
  - `Cmd/Ctrl + K` — command palette
  - `Cmd/Ctrl + \` — toggle sidebars
  - `Cmd/Ctrl + Shift + F` — focus mode (hide everything but text)
ui_available_in: [editor]

service: chapters/service.py
contract: chapters/contracts.py#ChapterServiceProtocol
router: chapters/router.py
prompt: ~
requires: [INFRA-001, SET-001, SET-002]
---

# WRITE-001 — Writing Editor

## What it does

A ProseMirror-based writing editor (via TipTap) with chapter-scoped documents,
autosave, live word count, and a layout designed for extension: left sidebar
for navigation, main surface for writing, right panel and toolbar slots for
AI features that will be added in subsequent milestones.

## Why it exists

The editor is the primary interface. Every AI feature in Narrare surfaces through
or alongside the editor. Getting the editor foundation wrong means refactoring
the entire frontend when AI features are added. Getting it right means every
future feature is a plugin, not a rewrite.

## Architecture: Built for Extension

The editor has four extension points, all designed at MVP even though most are
empty until AI features are built:

```
┌─────────────────────────────────────────────────┐
│  Toolbar  [Format] [Scene Break]  [AI slots...]  │  ← AI actions plug in here
├──────────┬──────────────────────┬────────────────┤
│          │                      │                │
│ Chapter  │   Editor Surface     │  Context       │
│ Sidebar  │   (ProseMirror)      │  Panel         │  ← AI content surfaces here
│          │                      │                │
│  [list]  │   Your text here.    │  [empty MVP]   │
│          │                      │                │
├──────────┴──────────────────────┴────────────────┤
│  Word count: 1,204 · Reading time: ~5 min  [●]   │  ← status bar
└─────────────────────────────────────────────────┘
```

**Toolbar slots:** Each AI action (Generate, Extend, Rewrite, etc.) registers
a TipTap extension that adds a button to the toolbar. MVP toolbar has only
formatting buttons. AI buttons appear when those features are built.

**Context panel sections:** Each AI feature can register a section in the right
panel (suggestions panel, voice check panel, KB references panel). MVP panel
is empty — its layout shell is in place.

**Command palette:** `Cmd+K` opens a palette. MVP has formatting commands only.
AI features register commands that appear here automatically when built.

**Inline decorations:** TipTap's decoration API allows highlights and annotations
in the text. Used by voice check, consistency check, sensitivity review.
No inline decorations at MVP.

## How it works (Technical)

### Frontend

**Editor library:** TipTap v3 with ProseMirror.
Chosen over plain ProseMirror for React integration; over Slate/Lexical for
mature extension API and active maintenance.

**Custom TipTap extensions at MVP:**
- `NarrareDocument` — chapter-scoped document node
- `SceneBreak` — custom node (`---` rendered as visual divider)
- `DialogueMark` — marks dialogue spans (future: character attribution)
- `Autosave` — extension that triggers save on content change + debounce

**Document schema:**
```typescript
// Nodes: doc → paragraph | heading | scene_break | blockquote | code_block
// Marks: bold | italic | underline | dialogue
// Every node type is extensible — new node types are new TipTap extensions
```

**Autosave implementation:**
1. TipTap `onUpdate` fires on every keystroke
2. Debounce (configurable interval from project settings, default 30s)
3. Serializes editor content to Markdown via `@tiptap/pm` serializer
4. `PUT /api/v1/chapters/{id}/content` — optimistic update, confirmed by response
5. Save indicator: `idle` | `saving` | `saved` | `error`
6. Error state: shows "Save failed — retry?" with manual save button

**Focus mode:** `Cmd+\` toggles both sidebars. `Cmd+Shift+F` hides toolbar
and status bar too. All layout toggling via CSS class on `<EditorLayout>` —
no state juggling.

**Chapter switching:**
1. User clicks chapter in sidebar
2. Current chapter content serialized to Markdown and saved (force save)
3. New chapter content fetched from API
4. Editor content replaced — `editor.commands.setContent(newContent)`
5. Cursor position reset to start of document

### Backend

**Content storage:**
Chapter content stored as Markdown in the `chapters.content` column (TEXT).
Not JSON, not HTML. Markdown is the canonical format.
Rationale: human-readable, portable, diff-friendly, works for future CLI/MCP.

**Word count:**
Computed server-side on save, stored in `chapters.word_count`.
Also computed client-side (live) during editing from editor content.
Server is authoritative; client is for live feedback only.

**Chapter reordering:**
Chapters have a `position` integer. Reorder via `PUT /api/v1/chapters/reorder`
with `[{id, position}, ...]`. Single transaction, no gaps in positions.

**Content versioning (MVP decision: no):**
Full content versioning is not in MVP. The API saves the current content.
There is no undo history that persists across sessions (TipTap history works
within a session). This is acceptable for MVP — version history is a
post-MVP feature.

## Layout Components

```
EditorLayout.tsx          ← orchestrates layout, keyboard shortcuts
├── ChapterSidebar.tsx    ← chapter list, drag-to-reorder (dnd-kit)
│   ├── ChapterItem.tsx   ← single chapter with word count + status
│   └── AddChapterButton.tsx
├── EditorSurface.tsx     ← TipTap editor, content serialization
│   └── extensions/
│       ├── NarrareDocument.ts
│       ├── SceneBreak.ts
│       ├── DialogueMark.ts
│       └── Autosave.ts
├── EditorToolbar.tsx     ← formatting buttons + AI slot registry
├── ContextPanel.tsx      ← right panel shell + section registry
├── CommandPalette.tsx    ← Cmd+K shell + command registry
└── StatusBar.tsx         ← word count, save status, reading time
```

**Slot registries (built at MVP, used by future AI features):**
```typescript
// EditorToolbar registers AI actions via:
registerToolbarAction({
  id: 'write-new-chapter',
  icon: PenLine,
  label: t('toolbar.writeChapter'),
  shortcut: 'Mod-Shift-W',
  handler: () => openWriteChapterPanel(),
  feature: 'WRITE-002',  // only shown if feature is enabled
})

// ContextPanel registers sections via:
registerContextSection({
  id: 'inline-suggestions',
  title: t('panel.suggestions'),
  component: InlineSuggestionsPanel,
  feature: 'WRITE-007',
})
```

## Constraints & Edge Cases

- Maximum chapter content: 100,000 characters (soft warning at 80,000)
- Autosave does not run if content has not changed since last save
- If save fails 3 times: editor enters "offline" mode, user is warned,
  local copy preserved in `localStorage` as emergency backup (exception
  to no-localStorage rule — this is a safety net, not primary storage)
- Chapter sidebar shows chapters in position order, not creation order
- Empty chapters (0 words) show a "Start writing..." placeholder
- No real-time collaboration at MVP (single user per project)
- The editor does not support images at MVP

## Related Features

- [WRITE-002](WRITE-002-new-chapter.md) — first AI feature to plug into toolbar
- [WRITE-007](WRITE-007-inline-suggestions.md) — first feature to use context panel
- [SET-002](../settings/SET-002-project-settings.md) — autosave interval source

## Status & History

- `project-init` — Specified for MVP, detailed for Phase 4 implementation
