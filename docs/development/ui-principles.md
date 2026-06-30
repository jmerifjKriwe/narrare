# Narrare UI/UX Principles

> This document defines the visual and interaction design rules for Narrare's frontend.
> All frontend work MUST follow these principles.
>
> **Last updated:** 2026-05-26
> **Source:** Design-first rebuild — all values extracted from production code
> **Applies to:** `packages/web/` (Next.js App Router + TypeScript + Tailwind CSS v4)

---

## 1. Design Philosophy

1. **Minimal, distraction-free writing environment.** The editor dominates the viewport. Everything else supports it.
2. **Content-first.** Navigation, suggestions, and analysis all serve the writing surface. Nothing competes with it.
3. **Dark and light mode as first-class citizens.** Both themes are complete and tested. Dark mode uses inverted primary tokens (white buttons on dark backgrounds).
4. **German as reference language, i18n required for all visible text.** Zero hardcoded user-facing strings in components. Mock content (character names, descriptions) is exempt — it's data, not UI.
5. **Errors are actionable or silent.** Non-critical errors appear in non-blocking notifications that auto-dismiss. Never show a modal for a non-critical error.
6. **Settings persist without save buttons.** Preference changes save immediately.

---

## 2. Layout Paradigm

### Sidebar-based navigation (NOT header bar)

The app uses a persistent sidebar on the left with the main content area filling the remaining space. There is no header bar, no top navigation, and no body-level scrolling.

### Shell Structure

```
┌──────────────────────────────────────────────────┐
│ Sidebar (w-72 = 288px) │ Main Content (flex-1)   │
│                         │                         │
│ ┌─────────────────────┐ │                         │
│ │ Logo + App Name     │ │                         │
│ ├─────────────────────┤ │                         │
│ │ Nav Buttons         │ │   [View content here]   │
│ │  · Editor           │ │                         │
│ │  · Welt & Chars     │ │                         │
│ │  · Analysis         │ │                         │
│ │  · Settings         │ │                         │
│ ├─────────────────────┤ │                         │
│ │ Chapter List        │ │                         │
│ │  (editor view only) │ │                         │
│ │                     │ │                         │
│ ├─────────────────────┤ │                         │
│ │ [+ New Chapter]     │ │                         │
│ └─────────────────────┘ │                         │
└──────────────────────────────────────────────────┘
```

**Implementation** (`app/(studio)/layout.tsx`):
```tsx
<div className="size-full flex">
  <Sidebar />
  <main className="flex-1 min-h-0 min-w-0">{children}</main>
</div>
```

- **Full-height app:** Root is `size-full flex` (100vw x 100vh, no scrolling on shell)
- **No header bar:** All navigation is in the sidebar
- **No page-level scrolling:** Each view manages its own scroll internally via `overflow-y-auto`

### Sidebar

Source: `components/studio/Sidebar.tsx`

The sidebar is persistent across all views with four sections:

**1. Logo area** (`p-6 border-b border-border`):
- Logo icon: `w-10 h-10 rounded-lg bg-primary` with `BookOpen` icon (`w-5 h-5 text-primary-foreground`)
- App name: `text-lg font-medium` — "Narrare" via `t("sidebar.appName")`
- Tagline: `text-xs text-muted-foreground` — via `t("sidebar.subtitle")`

**2. Nav buttons** (`p-3 border-b border-border space-y-0.5`):
- 4 buttons, each: `w-full flex items-center gap-3 px-4 py-2.5 rounded-md transition-all text-sm`
- **Active:** `bg-primary text-primary-foreground shadow-sm`
- **Inactive:** `hover:bg-accent`
- Icon size: `w-4 h-4`

| Label (de)        | Icon       | Route           |
|-------------------|------------|-----------------|
| Editor            | `FileText` | `/`             |
| Welt & Charaktere | `Package`  | `/worldbuilding` |
| Analyse           | `BarChart3`| `/analysis`     |
| Einstellungen     | `Settings` | `/settings`     |

**3. Chapter list** (editor view only, shown when `pathname === "/"`):
- Header: `px-3 py-2 border-b border-border` with label `text-xs text-muted-foreground px-4 py-1 uppercase`
- Scrollable list: `flex-1 overflow-y-auto p-3`, items in `space-y-1`
- Chapter button: `w-full text-left px-4 py-3 rounded-md transition-all`
  - **Active:** `bg-card shadow-sm border border-border`
  - **Inactive:** `hover:bg-accent border border-transparent`
  - Title: `truncate text-sm`
  - Word count: `text-xs text-muted-foreground mt-1`
- Footer: `p-4 border-t border-border` with "New Chapter" button

**4. New Chapter button:**
- `w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity shadow-sm`
- Icon: `Plus` (`w-4 h-4`), label: `text-sm`

### View Routing

All routes live under `app/(studio)/`. Pages are thin wrappers that import a single view component.

| URL             | Page file                           | View Component              | Description                    |
|-----------------|-------------------------------------|-----------------------------|--------------------------------|
| `/`             | `app/(studio)/page.tsx`             | `EditorView`                | Default, TipTap editor         |
| `/worldbuilding`| `app/(studio)/worldbuilding/page.tsx`| `WorldBuilding`             | 3-column entity management     |
| `/analysis`     | `app/(studio)/analysis/page.tsx`    | `AnalysisPanel`             | Stats + AI analysis cards      |
| `/settings`     | `app/(studio)/settings/page.tsx`    | `SettingsView`              | 2-column settings with tabs    |

---

## 3. Design Tokens

Source: `packages/web/styles/theme.css`

### CSS Architecture

**Import order** (from `styles/index.css`):
```
1. tailwind.css    — Tailwind v4 base
2. theme.css       — All design tokens + base typography
3. editor.css      — TipTap/ProseMirror styles
```

**Tailwind v4 integration:**
- `@custom-variant dark (&:is(.dark *));` — dark mode is class-based
- `@theme inline { ... }` registers all CSS variables as Tailwind utilities
- Dark mode activated by adding `.dark` class to `<html>` element

### Color Palette — Light Mode

| Token                        | Hex         | Tailwind Class                | Usage                           |
|------------------------------|-------------|-------------------------------|---------------------------------|
| `--background`              | `#f8f8f7`   | `bg-background`               | Main background (warm off-white)|
| `--foreground`              | `#1a1a1a`   | `text-foreground`             | Primary text                    |
| `--card`                     | `#ffffff`   | `bg-card`                     | Card/surface backgrounds        |
| `--card-foreground`         | `#1a1a1a`   | `text-card-foreground`        | Text on cards                   |
| `--popover`                 | `#ffffff`   | `bg-popover`                  | Popover/dropdown backgrounds    |
| `--popover-foreground`      | `#1a1a1a`   | `text-popover-foreground`     | Text on popovers                |
| `--primary`                 | `#2c2c2c`   | `bg-primary`                  | Primary buttons, active states  |
| `--primary-foreground`      | `#ffffff`   | `text-primary-foreground`     | Text on primary elements        |
| `--secondary`               | `#f4f4f3`   | `bg-secondary`                | Secondary backgrounds           |
| `--secondary-foreground`    | `#2c2c2c`   | `text-secondary-foreground`   | Text on secondary               |
| `--muted`                   | `#f0f0ef`   | `bg-muted`                    | Muted backgrounds, badges       |
| `--muted-foreground`        | `#737373`   | `text-muted-foreground`       | Secondary/hint text             |
| `--accent`                  | `#f4f4f3`   | `bg-accent`                   | Hover states, subtle highlights |
| `--accent-foreground`       | `#2c2c2c`   | `text-accent-foreground`      | Text on accent                  |
| `--destructive`             | `#dc2626`   | `bg-destructive`              | Destructive/danger actions      |
| `--destructive-foreground`  | `#ffffff`   | `text-destructive-foreground` | Text on destructive             |
| `--border`                  | `#e5e5e4`   | `border-border`               | Borders, dividers               |
| `--input`                   | `transparent`| —                            | Input border color              |
| `--input-background`        | `#fafafa`   | `bg-input-background`         | Input field backgrounds         |
| `--switch-background`       | `#d4d4d3`   | `bg-switch-background`        | Toggle switch track (off state) |
| `--ring`                    | `#525252`   | `ring-ring`                   | Focus ring color                |
| `--sidebar`                 | `#fafafa`   | `bg-sidebar`                  | Sidebar background              |
| `--sidebar-foreground`      | `#1a1a1a`   | `text-sidebar-foreground`     | Sidebar text                    |
| `--sidebar-primary`         | `#2c2c2c`   | `bg-sidebar-primary`          | Sidebar active elements         |
| `--sidebar-primary-foreground`| `#ffffff` | `text-sidebar-primary-foreground` | Text on sidebar active     |
| `--sidebar-accent`          | `#f4f4f3`   | `bg-sidebar-accent`           | Sidebar hover states            |
| `--sidebar-accent-foreground`| `#1a1a1a`  | `text-sidebar-accent-foreground` | Text on sidebar accent     |
| `--sidebar-border`          | `#e5e5e4`   | `border-sidebar-border`       | Sidebar borders                 |
| `--sidebar-ring`            | `#525252`   | `ring-sidebar-ring`           | Sidebar focus ring              |

### Color Palette — Dark Mode

Activated by `.dark` class on `<html>`. Primary tokens invert: white buttons on dark backgrounds.

| Token                        | Hex         | Notes                          |
|------------------------------|-------------|--------------------------------|
| `--background`              | `#0a0a0a`   | Near-black                     |
| `--foreground`              | `#fafafa`   | Off-white                      |
| `--card`                     | `#171717`   | Dark surface                   |
| `--card-foreground`         | `#fafafa`   |                                |
| `--popover`                 | `#171717`   |                                |
| `--popover-foreground`      | `#fafafa`   |                                |
| `--primary`                 | `#fafafa`   | Inverted: white buttons        |
| `--primary-foreground`      | `#0a0a0a`   | Dark text on white             |
| `--secondary`               | `#262626`   |                                |
| `--secondary-foreground`    | `#fafafa`   |                                |
| `--muted`                   | `#262626`   |                                |
| `--muted-foreground`        | `#a3a3a3`   |                                |
| `--accent`                  | `#262626`   |                                |
| `--accent-foreground`       | `#fafafa`   |                                |
| `--destructive`             | `#ef4444`   | Brighter red than light mode   |
| `--destructive-foreground`  | `#fafafa`   |                                |
| `--border`                  | `#262626`   |                                |
| `--input-background`        | `#171717`   |                                |
| `--ring`                    | `#737373`   |                                |
| `--sidebar`                 | `#0a0a0a`   | Same as background             |
| `--sidebar-primary`         | `#fafafa`   | Inverted                       |
| `--sidebar-primary-foreground`| `#0a0a0a` |                                |

### Semantic Color Usage

| Purpose              | Token(s) to use                                   |
|----------------------|--------------------------------------------------|
| Main actions / CTAs  | `bg-primary text-primary-foreground shadow-sm`    |
| Elevated surfaces    | `bg-card border border-border rounded-lg`         |
| Muted backgrounds    | `bg-muted`                                        |
| Hover states         | `hover:bg-accent`                                 |
| All borders          | `border-border` (applied globally via `@layer base`) |
| Delete / errors      | `text-destructive`, `bg-destructive`              |
| Input fields         | `bg-input-background border border-border rounded-md` |
| Secondary hint text  | `text-muted-foreground`                           |
| Focus rings          | `ring-ring`                                       |

### Radii

| Token         | Value                 | Tailwind       |
|---------------|-----------------------|----------------|
| `--radius`    | `0.5rem` (8px)        | Base radius    |
| `--radius-sm` | `calc(0.5rem - 4px)` = 4px  | `rounded-sm`  |
| `--radius-md` | `calc(0.5rem - 2px)` = 6px  | `rounded-md`  |
| `--radius-lg` | `0.5rem` = 8px        | `rounded-lg`   |
| `--radius-xl` | `calc(0.5rem + 4px)` = 12px | `rounded-xl` |

### Typography

| Element  | Size          | Weight | Line-height |
|----------|---------------|--------|-------------|
| Base     | `16px` (`var(--font-size)`) | —    | —           |
| h1       | `text-2xl`    | 500    | 1.5         |
| h2       | `text-xl`     | 500    | 1.5         |
| h3       | `text-lg`     | 500    | 1.5         |
| h4       | `text-base`   | 500    | 1.5         |
| label    | `text-base`   | 500    | 1.5         |
| button   | `text-base`   | 500    | 1.5         |
| input    | `text-base`   | 400    | 1.5         |

No custom fonts loaded — use system font stack. Font weights: `--font-weight-medium: 500`, `--font-weight-normal: 400`.

### Theme vs shadcn Default

Our theme is intentionally warmer and softer than the default shadcn theme:

| Property       | shadcn Default | Our Theme (Light)             |
|----------------|---------------|-------------------------------|
| `--background` | `#ffffff`     | `#f8f8f7` (warm off-white)    |
| `--primary`    | `#030213`     | `#2c2c2c` (softer black)      |
| `--radius`     | `0.625rem`    | `0.5rem` (slightly smaller)   |
| `--border`     | `rgba(0,0,0,0.1)` | `#e5e5e4` (opaque warm gray) |
| `--muted`      | `#ececf0`     | `#f0f0ef` (warm variant)      |

Always use `theme.css` values, never the shadcn defaults.

### Live Design Token Reference (`/dev/design-tokens`)

A development-only route at `/dev/design-tokens` (inside the `(studio)` layout) provides a live reference for all CSS custom properties, theme values, and Tailwind utility mappings. Accessible only when `NODE_ENV=development`.

**Sections:**
1. **Color Palette** — all `--color-*` tokens with visual swatches, hex/oklch values, Tailwind class labels
2. **Radii & Typography** — `--radius-{sm,md,lg,xl}` preview boxes, h1-h4 type scale, editor token cards
3. **Theme Comparison** — default (neutral) vs `data-theme="narrare"` side-by-side in isolated context panels
4. **Tailwind Mapping** — 37-row mapping table (utility → CSS variable → current value → description)

This reference is always current because it reads CSS variable values at runtime via `getComputedStyle()`. See ADR-059.

---

## 4. Component Conventions

### Component Organization

```
components/studio/
├── Sidebar.tsx         ← App navigation (persistent)
├── EditorView.tsx      ← Editor layout (header + status bar)
├── TipTapEditor.tsx    ← TipTap wrapper with bubble menu + AI modal
├── WorldBuilding.tsx   ← Entity management (3-column)
├── AnalysisPanel.tsx   ← Stats + analysis cards
└── SettingsView.tsx    ← Settings (2-column with tab switching)

components/editor/
├── CommandPalette.tsx
├── commands.ts
├── MetadataSidebar.tsx  ← Right sidebar (live stats, chapter metadata)
└── extensions/
```

### Naming Rules

- **PascalCase** for components
- **One component per file**, file name matches component name
- Client components use `"use client"` directive
- Props interfaces defined inline, above the component (e.g., `interface TipTapEditorProps { ... }`)
- Event handlers: `on[Action]` (e.g., `onContentChange`, `onChapterSelect`)
- State variables: camelCase, descriptive (e.g., `activeCategory`, `selectedEntity`)

### Styling Rules

- **Tailwind CSS v4 only** — no CSS modules, no styled-jsx, no inline styles (except fixed positioning for bubble menu)
- Use semantic tokens: `bg-primary`, `text-muted-foreground`, `border-border`
- Active states: `bg-primary text-primary-foreground shadow-sm`
- Hover states: `hover:bg-accent`
- Cards: `bg-card border border-border rounded-lg`
- Input fields: `bg-input-background border border-border rounded-md`
- No hardcoded color values in components — everything goes through CSS variables
- All `@apply` usage confined to `@layer base` in `theme.css`

### shadcn/ui Usage

- Use shadcn/ui primitives where available (Button, Dialog, etc.)
- Currently using custom components matching the design prototype
- When adding new interactive elements, prefer shadcn/ui

### Component Structure

```typescript
// 1. "use client" directive
"use client";

// 2. Imports (external → internal)
import { useState } from "react";
import { useTranslations } from "next-intl";
import { SomeIcon } from "lucide-react";

// 3. Types (co-located)
interface MyComponentProps {
  content: string;
  onChange: (content: string) => void;
}

// 4. Constants / mock data
const MOCK_DATA = [...];

// 5. Component (named export)
export function MyComponent({ content, onChange }: MyComponentProps) {
  const t = useTranslations("studio");
  // hooks → derived state → handlers → render
}
```

### Page Components

Page components are thin wrappers that import and render a single view component:

```typescript
"use client";
import { EditorView } from "@/components/studio/EditorView";
export default function EditorPage() {
  return <EditorView />;
}
```

---

## 5. i18n Rules

### Mandatory Rules

- **ALL visible text** must use `useTranslations("studio")` from `next-intl`
- **Zero** hardcoded user-facing strings in components
- Mock content (character names, descriptions, chapter text) is exempt — it's data, not UI
- 3 locales: **de** (reference), **en**, **fr**
- Files: `packages/i18n/messages/{locale}/studio.json`
- Namespace: `studio` for all studio UI

### Key Structure

Keys follow a `studio.{view}.{element}` pattern in the JSON files. Since the namespace is `"studio"`, the hook accesses keys relative to `studio`:

```typescript
const t = useTranslations("studio");
// t("sidebar.editor") → studio.sidebar.editor
// t("editor.save") → studio.editor.save
// t("worldbuilding.characters.label") → studio.worldbuilding.characters.label
```

### Key Sections in `studio.json`

| Section                    | Keys example                            |
|---------------------------|-----------------------------------------|
| `sidebar.*`               | `sidebar.appName`, `sidebar.editor`     |
| `editor.*`                | `editor.save`, `editor.words`           |
| `bubble.*`                | `bubble.bold`, `bubble.aiRewrite`       |
| `aiModal.*`               | `aiModal.title`, `aiModal.accept`       |
| `worldbuilding.*`         | `worldbuilding.categories`              |
| `worldbuilding.{type}.*`  | `worldbuilding.characters.label`        |
| `worldbuilding.aiDialog.*`| `worldbuilding.aiDialog.title`          |
| `analysis.*`              | `analysis.title`, `analysis.score`       |
| `settings.*`              | `settings.general`, `settings.ai.title` |

---

## 6. View-Specific Rules

### Editor (`/`)

Source: `EditorView.tsx` + `TipTapEditor.tsx`

**Layout:** Full-height flex column (`flex-1 flex flex-col h-full bg-background`).

```
┌──────────────────────────────────────────────────────────────┐
│ Header bar (border-b, bg-card)                                │
│ [Chapter title input]  [Clock] [PanelToggle] [Save]          │
├──────────────────────────────────────────────────────────────┤
│ Toolbar: formatting + AI tools                                │
├─────────────────────────────────────┬────────────────────────┤
│ Editor area (flex-1, overflow-y)    │ MetadataSidebar (w-64) │
│ max-w-4xl mx-auto                   │ (conditional)          │
│                                     │                        │
│ [TipTap content]                    │ Statistics             │
│                                     │ Session                │
│                                     │ Chapter Info           │
│                                     │ Novel Progress         │
└─────────────────────────────────────┴────────────────────────┘
```

**TipTap configuration:**
- Extensions: `StarterKit` (heading levels: `[1, 2, 3]`) + `Placeholder`
- `immediatelyRender: false` (prevents SSR hydration mismatch)
- Editor props class: `max-w-none focus:outline-none min-h-[70vh] px-8 py-6`
- `onUpdate` callback returns `editor.getHTML()`

**Bubble menu** (appears when text is selected, no active AI suggestion):
- Fixed position: `left: 50%; top: 20%; transform: translateX(-50%)`
- Container: `bg-card border border-border rounded-lg shadow-lg overflow-hidden`
- Buttons in row: `divide-x divide-border`, each `px-3 py-2 hover:bg-accent transition-colors`
- Bold (`<strong>B</strong>`), Italic (`<em>I</em>`), AI Rewrite (`Sparkles` icon + label)

**AI Suggestion Modal:**
- Overlay: `fixed inset-0 bg-black/50`
- Modal: `bg-card border border-border rounded-xl shadow-2xl max-w-2xl w-full max-h-[80vh]`
- Suggestion cards: `p-4 rounded-lg border-2 transition-all`
  - Selected: `border-primary bg-accent` with `Check` icon
  - Unselected: `border-border hover:border-primary/50`
- Rejection input (conditional): `bg-muted/30`, textarea `bg-input-background border border-border rounded-lg`

**Header details:**
- Title input: `bg-transparent border-none outline-none flex-1 mr-4 text-lg font-medium`
- Last saved time: `flex items-center gap-2 text-sm text-muted-foreground` with `Clock` icon (`w-4 h-4`)
- Time display uses **client-only rendering**: initialized as `null`, set in `useEffect` to avoid hydration mismatch
- Save button: `flex items-center gap-2 px-5 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity shadow-sm`

**Metadata sidebar** (`components/editor/MetadataSidebar.tsx`):

Collapsible right panel (`w-64`, toggled via `contextPanelOpen` in editorStore) with four sections:
- **Statistics**: live word count, character count, reading time (250 wpm), paragraph count
- **Session**: word delta since chapter open (green/red/muted), session start word count
- **Chapter Info**: status badge (draft/reviewed/final), POV character, timeline position, chapter position
- **Novel Progress**: total words across chapters, progress bar toward 80,000-word goal

```typescript
// Live stats computed in EditorView, passed as props
const text = content.replace(/<[^>]*>/g, "");
const wordCount = text.trim().split(/\s+/).filter(w => w.length > 0).length;
const charCount = text.length;
const readingTime = Math.ceil(wordCount / 250);  // 250 words/minute
```

### WorldBuilding (`/worldbuilding`)

Source: `WorldBuilding.tsx`

**Layout:** Full-height, 3-column flex row (`flex-1 flex h-full`).

```
┌──────────┬────────────┬─────────────────────────────┐
│ Category │  Entity    │  Detail Panel               │
│ sidebar  │  List      │                             │
│ w-56     │  w-64      │  flex-1                     │
│ (224px)  │  (256px)   │                             │
└──────────┴────────────┴─────────────────────────────┘
```

**Column 1 — Category sidebar** (`w-56 border-r border-border bg-card flex flex-col`):
- Header: `p-4 border-b border-border` with `text-sm font-medium text-muted-foreground uppercase tracking-wider`
- Category buttons: `w-full flex items-center justify-between gap-3 px-3 py-2 rounded-md transition-all text-sm`
  - Active: `bg-primary text-primary-foreground shadow-sm`
  - Inactive: `hover:bg-accent text-foreground`
  - Badge: active uses `bg-primary-foreground/20`, inactive uses `bg-muted text-muted-foreground`

**Column 2 — Entity list** (`w-64 border-r border-border bg-muted/30 flex flex-col`):
- Action buttons: `p-3 border-b border-border space-y-2`
  - "Neu erstellen": `bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity text-sm shadow-sm`
  - "Mit KI erstellen": `border border-border bg-card rounded-md hover:bg-accent transition-colors text-sm`
- Entity buttons: `w-full text-left px-3 py-2.5 rounded-md transition-all`
  - Selected: `bg-card shadow-sm border border-border` with `ChevronRight` icon
  - Unselected: `hover:bg-card/50`
- Empty state: `text-center py-12 text-muted-foreground text-sm` with type icon (`w-8 h-8 mx-auto mb-2 opacity-20`)

**Column 3 — Detail panel** (`flex-1 overflow-y-auto bg-background`):
- Content: `max-w-3xl mx-auto p-8`
- Entity icon: `w-14 h-14 rounded-xl bg-muted`
- Inline-editable name: `text-2xl font-medium bg-transparent border-none outline-none`
- Delete button: `p-2 text-destructive hover:bg-destructive/10 rounded-md` with `aria-label`
- Input fields: `bg-input-background border border-border rounded-md text-sm`

**7 entity types:**

| Type          | Icon      | i18n key prefix                    |
|---------------|-----------|-------------------------------------|
| `characters`  | `User`    | `worldbuilding.characters.*`        |
| `locations`   | `MapPin`  | `worldbuilding.locations.*`         |
| `artifacts`   | `Package` | `worldbuilding.artifacts.*`         |
| `regions`     | `Map`     | `worldbuilding.regions.*`           |
| `religions`   | `Church`  | `worldbuilding.religions.*`         |
| `magic`       | `Wand2`   | `worldbuilding.magic.*`             |
| `concepts`    | `Lightbulb`| `worldbuilding.concepts.*`         |

Each type has keys: `label`, `singular`, `article`, `subtitleLabel`, `subtitlePlaceholder`.

**AI Create Dialog:**
- Overlay: `fixed inset-0 bg-black/60 backdrop-blur-sm`
- Modal: `bg-card border border-border rounded-xl shadow-2xl max-w-xl w-full`
- Structure: header (icon + title + close) → textarea input → footer (cancel + create)

### Analysis (`/analysis`)

Source: `AnalysisPanel.tsx`

**Layout:** Single-column, scrollable (`flex-1 overflow-y-auto p-8`), `max-w-4xl mx-auto`.

**Stats cards** — `grid grid-cols-3 gap-4 mb-8`:
- Each card: `bg-card border border-border rounded-lg p-6`
- Value: `text-3xl font-medium mb-1`
- Label: `text-sm text-muted-foreground`

**Analysis cards** — `space-y-4 mb-8`:
- Each card: `bg-card border border-border rounded-lg overflow-hidden`
- Header button: `w-full p-6 flex items-start gap-4 hover:bg-accent transition-colors text-left`
  - Icon container: `w-12 h-12 rounded-lg bg-muted` with icon `w-6 h-6`
  - Text: title (`font-medium`) + description (`text-sm text-muted-foreground`)
  - Analyze button: `px-4 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 shadow-sm` with `Sparkles` icon

**Results panel** (expanded, `border-t border-border p-6 bg-muted/20`):
- Loading: `Sparkles` icon with `animate-pulse`
- Score bar: `h-2 bg-muted rounded-full` with `bg-primary` fill, width set via inline style `{ width: ${score}% }`
- Detail rows: `grid grid-cols-3 gap-4 mb-6`
- Suggestions: bullet list with `w-1.5 h-1.5 rounded-full bg-muted-foreground` dots

**4 analysis types:**

| ID             | Icon         | Title key                        |
|----------------|--------------|----------------------------------|
| `readability`  | `BookOpen`   | `analysis.readability.title`     |
| `pacing`       | `TrendingUp` | `analysis.pacing.title`          |
| `characters`   | `Users`      | `analysis.characterAnalysis.title` |
| `timeline`     | `Clock`      | `analysis.timeline.title`        |

### Settings (`/settings`)

Source: `SettingsView.tsx`

**Layout:** Full-height, 2-column flex row (`flex-1 flex h-full`).

```
┌──────────┬─────────────────────────────────────┐
│ Settings │  Content area                       │
│ nav      │  flex-1 overflow-y-auto bg-background│
│ w-56     │  p-8, max-w-3xl                     │
└──────────┴─────────────────────────────────────┘
```

**Column 1 — Settings nav** (`w-56 border-r border-border bg-card flex flex-col`):
- Header: `p-4 border-b border-border` with `text-sm font-medium text-muted-foreground uppercase tracking-wider`
- Nav buttons: `w-full flex items-center gap-3 px-3 py-2 rounded-md transition-all text-sm`
  - Active: `bg-primary text-primary-foreground shadow-sm`
  - Inactive: `hover:bg-accent text-foreground`
  - Icon: `w-4 h-4`
- **Internal tab switching** (no sub-routes) — uses `useState<SettingsCategory>`

**5 settings categories:**

| ID          | Icon        | Label key              |
|-------------|-------------|------------------------|
| `general`   | `Settings2` | `settings.general`     |
| `writing`   | `Target`    | `settings.writingGoals`|
| `ai`        | `Sparkles`  | `settings.aiSetup`     |
| `shortcuts` | `Keyboard`  | `settings.shortcuts`   |
| `about`     | `Info`      | `settings.about`       |

**Settings cards** all follow: `bg-card border border-border rounded-lg p-6`
- Icon container: `w-12 h-12 rounded-lg bg-muted flex items-center justify-center` with icon `w-6 h-6`
- Title: `font-medium`
- Description: `text-sm text-muted-foreground`

**Dark mode toggle:**
- Custom switch: `w-14 h-8 rounded-full transition-colors relative`
- Active (dark): `bg-primary`, thumb `translate-x-7`
- Inactive (light): `bg-switch-background`, thumb `translate-x-1`
- Thumb: `absolute top-1 w-6 h-6 bg-white rounded-full shadow-sm transition-transform`

**Shortcuts card:**
- Rows: `flex items-center justify-between py-3`
- Separator: `h-px bg-border`
- Shortcut keys: `<kbd>` styled `px-3 py-1.5 bg-muted rounded text-sm border border-border font-mono`

---

## 7. State Management (Current)

**Local state only** — `useState` for all view state. No external stores connected yet.

- **Mock data** defined as constants in components (e.g., `MOCK_CHAPTERS`, `MOCK_ENTITIES`)
- **No API calls** — all interactions are simulated (mock delay with `setTimeout`)
- **No Zustand stores** connected
- **No TanStack Query** connected

**Future reconnection plan:**
- Server state (chapters, entities, settings) → TanStack Query
- UI state (active views, toggles) → Zustand
- Ephemeral state (form inputs, selections) → `useState`

---

## 8. SSR/Hydration Rules

Critical for Next.js App Router:

1. **`immediatelyRender: false`** on all TipTap `useEditor()` calls — prevents SSR hydration mismatch
2. **Date/time values:** initialize as `null`, set in `useEffect` — avoids server/client time mismatch
3. **No `new Date()` or `Math.random()`** in initial state
4. **No `typeof window` checks** in render path
5. **Use `suppressHydrationWarning`** only as last resort
6. **Page components** that use client hooks must have `"use client"` directive

---

## 9. Editor CSS Reference

Source: `packages/web/styles/editor.css`

All rules target `.ProseMirror` (TipTap's contenteditable wrapper):

| Element                        | Styles                                                              |
|--------------------------------|---------------------------------------------------------------------|
| `.ProseMirror`                 | `outline: none`                                                     |
| Placeholder (`p.is-editor-empty:first-child::before`) | `content: attr(data-placeholder); float: left; color: var(--muted-foreground); pointer-events: none; height: 0` |
| `h1`                           | `font-size: 2em; margin-top: 1em; margin-bottom: 0.5em; font-weight: 600; line-height: 1.3` |
| `h2`                           | `font-size: 1.5em; margin-top: 1.2em; margin-bottom: 0.5em; font-weight: 600; line-height: 1.3` |
| `h3`                           | `font-size: 1.25em; margin-top: 1em; margin-bottom: 0.5em; font-weight: 600; line-height: 1.4` |
| `p`                            | `margin-top: 0.75em; margin-bottom: 0.75em; line-height: 1.8`     |
| `ul, ol`                       | `padding-left: 1.5em; margin-top: 0.75em; margin-bottom: 0.75em`  |
| `li`                           | `margin-top: 0.25em; margin-bottom: 0.25em; line-height: 1.7`     |
| `blockquote`                   | `padding-left: 1em; border-left: 3px solid var(--primary); margin-top: 1em; margin-bottom: 1em; font-style: italic; color: var(--muted-foreground)` |
| `code`                         | `background-color: var(--muted); padding: 0.2em 0.4em; border-radius: 0.25rem; font-size: 0.9em` |
| `pre`                          | `background-color: var(--muted); padding: 1em; border-radius: 0.5rem; overflow-x: auto; margin-top: 1em; margin-bottom: 1em` |
| `::selection`                  | `background-color: var(--primary); color: var(--primary-foreground); opacity: 0.3` |

---

## 10. Archive Reference

Old UI components are preserved for reference. **They must NOT be imported.**

| Archive directory               | Contents                |
|---------------------------------|-------------------------|
| `packages/web/_archive_app/`    | Old Next.js pages       |
| `packages/web/_archive_components/` | Old React components |
| `packages/web/_archive_styles/` | Old CSS/style files     |
| `packages/web/_archive_tests/`  | Old test files          |

These exist only for reference when reconnecting features. All new code is written fresh.

---

## 11. Accessibility

- All buttons have `type="button"` (prevent unintended form submission)
- Interactive elements have `aria-label` where icon-only (e.g., delete button: `aria-label={t("worldbuilding.deleteButton")}`)
- Semantic HTML: `nav`, `main`, `button` (not `div` with `onClick`)
- `<label>` elements with `htmlFor` on all form inputs
- Keyboard navigation: Tab order follows visual layout
- Focus states: use Tailwind `focus:ring-1 focus:ring-ring`
- Toggle switches have `aria-label`

---

## 12. Lucide Icon Reference

All icons from `lucide-react`:

| Icon            | Used In                                    |
|-----------------|--------------------------------------------|
| `BookOpen`      | Sidebar logo, About card, Readability      |
| `FileText`      | Editor nav button                          |
| `Package`       | WorldBuilding nav button, artifact type    |
| `BarChart3`     | Analysis nav button                        |
| `Settings`      | Settings nav button                        |
| `Plus`          | New chapter, new entity buttons            |
| `Save`          | Save button in editor header               |
| `Clock`         | Last saved time, Timeline analysis         |
| `Sparkles`      | AI indicator, AI buttons, AI modals        |
| `User`          | Characters entity type                     |
| `MapPin`        | Locations entity type                      |
| `Map`           | Regions entity type                        |
| `Church`        | Religions entity type                      |
| `Wand2`         | Magic entity type                          |
| `Lightbulb`     | Concepts entity type                       |
| `ChevronRight`  | Selected entity indicator                  |
| `Trash2`        | Delete entity button                       |
| `X`             | Close/reject buttons in modals             |
| `Check`         | Accept/selected suggestion                 |
| `RotateCcw`     | New suggestions button                     |
| `Moon` / `Sun`  | Dark mode toggle indicator                 |
| `Target`        | Writing goals                              |
| `TrendingUp`    | Pacing analysis                            |
| `Users`         | Character analysis                         |
| `Settings2`     | General settings category                  |
| `Keyboard`      | Shortcuts settings category                |
| `Info`          | About settings category                    |
| `Cpu`           | AI provider settings                       |
| `MessageSquare` | System prompts settings                    |
| `PanelRight`   | Metadata sidebar toggle button        |

---

## 14. Analysis Visualization Patterns

Source: `components/studio/analysis/BetaReaderPanel.tsx`, `ScoreRadar.tsx`, `FeedbackCard.tsx`

### Analysis Panel Pattern

Analysis results display in a **collapsible panel within the editor view**. The panel slides in from the right (or bottom on mobile) and can be toggled via the sidebar Analysis button or a panel toggle in the editor toolbar.

```
┌──────────────────────────────────────────────────────┐
│ Editor area (flex-1)          │ Analysis Panel (w-96) │
│                               │                       │
│ [Chapter content]             │ [Tabs: Overview | …] │
│                               │ ┌───────────────────┐ │
│                               │ │ Score Radar Chart │ │
│                               │ └───────────────────┘ │
│                               │ ┌───────────────────┐ │
│                               │ │ Feedback Cards    │ │
│                               │ │  · Strengths      │ │
│                               │ │  · Issues         │ │
│                               │ │  · Suggestions    │ │
│                               │ └───────────────────┘ │
└──────────────────────────────────────────────────────┘
```

**Panel structure:**
- Container: `flex flex-col h-full bg-card border-l border-border`
- Tab bar: `flex border-b border-border` with tab buttons using `flex-1 py-3 text-sm font-medium text-center`
- Active tab: `border-b-2 border-primary text-primary`
- Inactive tab: `text-muted-foreground hover:text-foreground`
- Content area: `flex-1 overflow-y-auto p-4 space-y-4`

### Chart Component Pattern (Recharts)

All analysis visualizations use a reusable **`AnalysisChart`** pattern built on Recharts. Charts are responsive, themed via CSS variables, and support both light and dark modes.

**ScoreRadar (multi-dimensional scores):**
- Uses `<RadarChart>` from Recharts
- Displays up to 6 dimensions on a hexagonal grid
- Dimensions: Plot, Characters, Pacing, Prose, Engagement, Originality
- Scores normalized to 0–10 scale
- Colors via theme tokens: `--primary` for fill, `--primary-foreground` for stroke
- Responsive via `<ResponsiveContainer width="100%" height={250>`

**Styling rules for charts:**
- Chart backgrounds: transparent (inherit from panel)
- Grid lines: `var(--border)` color, dashed
- Axis labels: `text-sm text-muted-foreground`
- Data fills: `var(--primary)` with 20% opacity
- Data strokes: `var(--primary)` with full opacity
- Tooltips: `bg-card border border-border rounded-lg shadow-lg` with `text-sm`
- Legend: below chart, `text-xs text-muted-foreground`

**Future chart types (ANAL-002 through ANAL-011):**
- **Line charts**: sentiment arc over chapter progression (time series)
- **Bar charts**: readability score comparison across chapters
- **Area charts**: cumulative theme density
- All will follow the same `AnalysisChart` pattern and theming rules

### Feedback Card Pattern

Individual feedback items display in **FeedbackCard** components with severity badges, collapsible excerpts, and category badges.

**Card structure:**
```tsx
<div className="bg-card border border-border rounded-lg overflow-hidden">
  {/* Header row */}
  <div className="flex items-center gap-2 p-3">
    <SeverityBadge />       {/* Color-coded severity indicator */}
    <CategoryBadge />       {/* Category label (Plot, Characters, etc.) */}
    <span className="text-sm font-medium flex-1">{title}</span>
    <ChevronIcon />         {/* Collapse toggle */}
  </div>
  {/* Collapsible detail */}
  <div className="px-3 pb-3 text-sm text-muted-foreground">
    {detail}
    {excerpt && <blockquote>…</blockquote>}
  </div>
</div>
```

**Severity badges:**
| Severity | Background              | Text                    | Border                |
|----------|-------------------------|-------------------------|-----------------------|
| Critical | `bg-destructive/10`     | `text-destructive`      | `border-destructive/20` |
| Moderate | `bg-primary/10`         | `text-primary`          | `border-primary/20`   |
| Minor    | `bg-muted`              | `text-muted-foreground` | `border-border`       |

**Category badges:**
- `bg-secondary text-secondary-foreground text-xs rounded-full px-2 py-0.5`
- Categories: Plot, Characters, Pacing, Prose, Engagement

**Collapsible excerpts:**
- Quoted text from the chapter that the feedback refers to
- Styled: `border-l-2 border-muted-foreground/30 pl-3 italic text-muted-foreground text-sm mt-2`
- Excerpt text is truncated to 200 characters with "…" ellipsis

### Extensibility

ANAL-001 establishes the foundational patterns for the entire analysis suite (ANAL-002 through ANAL-011). Future analysis features will:

1. **Reuse the analysis panel** — each analysis type adds a new tab
2. **Reuse FeedbackCard** — all analysis types produce categorized, severity-rated feedback
3. **Add chart types** to the AnalysisChart wrapper — new `<XChart>` components as needed
4. **Share the same API module** — `apps/api/narrare/analysis/` handles all analysis endpoints
5. **Follow the same i18n pattern** — `studio.json` under `analysis.*` namespace

---

## 15. File Size Limits

| File type              | Hard limit |
|------------------------|-----------|
| Page component (`page.tsx`) | 100 lines  |
| Feature component      | 200 lines  |
| Hook (`use*.ts`)       | 150 lines  |
| Store (`*Store.ts`)    | 150 lines  |

Large components are a sign of mixed responsibilities. Split them per RULE-06.

---

## 16. AI-Interaction Standards

> **Scope**: Every feature that invokes an LLM, displays AI-generated content, or
> provides an AI-powered user action. Non-negotiable. These rules enforce RULE-20
> (no half-implementations) at the UX layer.
>
> **Reference language**: German (de). All user-facing strings must use canonical
> i18n keys from `studio.aiActions.*` (see §16.8).
>
> **Last updated**: 2026-06-19
> **Source**: CR-07 UX Audit — systemic inconsistency in AI interaction patterns; AUFG-03-10 vocabulary extension (acceptAll/rejectAll/applySelected); CR-07 UX Closure v2 — 11 platform gates implemented (see §16.9)

### 16.1 Streaming Rule

RULE: Every AI-powered feature MUST use SSE streaming via `connectSSE()` if the backend provides an SSE endpoint. REST-only consumption is a RULE-20 violation.

Rationale: Streaming is the core UX pattern for AI interaction. Users see output accumulate in real time.

Existing infrastructure: `connectSSE()` in `packages/web/lib/api/streaming.ts`, `AbortController` pattern in all SSE consumers.

Violation: Any `fetch()` or `apiClient.post()` call to an endpoint with a corresponding SSE router without using `connectSSE()`.

### 16.2 Cancel Rule

RULE: Every AI operation >2s MUST provide an AbortController-based cancel option visible to the user.

Required implementation pattern:
```typescript
const abortRef = useRef<AbortController | null>(null);
const handleStart = () => {
  const controller = new AbortController();
  abortRef.current = controller;
  connectSSE({ signal: controller.signal, ... });
};
const handleStop = () => {
  abortRef.current?.abort();
  abortRef.current = null;
};
```

Violation: AI operation without a stop/cancel button, or fetch without passing signal.

### 16.3 Loading Rule

RULE: Every AI operation MUST show immediate visual feedback within 200ms.

Required states: Idle → Loading (immediate, <200ms) → Streaming → Complete

Violation: No visual change after clicking AI button for >200ms.

### 16.4 Action-Label Rule

RULE: All AI output action buttons MUST use canonical Action Vocabulary from `studio.aiActions.*`.

Violation: Any button on AI-generated output using a label NOT from `studio.aiActions.*`.

### 16.5 Error-Message Rule

RULE: AI error messages MUST be actionable — tell what happened AND what to do.

Format: `[What happened] [What to do]`

Examples table:
| Error | Bad | Good |
|-------|-----|------|
| Timeout | "Timeout error" | "Die KI braucht zu lange. Versuche es mit weniger Kontext erneut." |
| Context too large | "413 Payload Too Large" | "Der Text ist zu lang für die KI. Kürze die Auswahl auf maximal {max} Zeichen." |
| API key invalid | "401 Unauthorized" | "Dein API-Schlüssel ist ungültig. Überprüfe deine KI-Einstellungen." |
| Rate limit | "429 Too Many Requests" | "Du hast zu viele Anfragen gesendet. Warte einen Moment." |
| Connection lost | "fetch failed" | "Verbindung verloren. Prüfe deine Internetverbindung." |

Violation: Error stating what failed without what to do. Raw HTTP status visible.

### 16.6 Feedback Rule

RULE: Every AI interaction with visible output MUST offer accept/reject flow.

Minimum flow: output → accept + reject → on accept: apply / on reject: discard + optional reason

Violation: AI output applied without user confirmation.

### 16.7 Connection-Lost Rule

RULE: Every long-running AI operation MUST handle connection loss gracefully.

Required: preserve partial output → show banner → offer retry

Violation: Connection loss causes blank state, crash, or loss of partial output.

### 16.8 Canonical AI-Action Vocabulary

All AI action labels under `studio.aiActions` namespace:

| i18n key | DE | EN | FR |
|----------|----|----|----|
| `aiActions.accept` | Übernehmen | Accept | Accepter |
| `aiActions.acceptAll` | Alle übernehmen | Accept All | Tout accepter |
| `aiActions.reject` | Verwerfen | Reject | Rejeter |
| `aiActions.rejectAll` | Alle verwerfen | Reject All | Tout rejeter |
| `aiActions.applySelected` | Auswahl übernehmen | Apply Selected | Appliquer la sélection |
| `aiActions.retry` | Erneut versuchen | Retry | Réessayer |
| `aiActions.stop` | Stoppen | Stop | Arrêter |
| `aiActions.addToDraft` | Zum Entwurf hinzufügen | Add to Draft | Ajouter au brouillon |
| `aiActions.insertAsNew` | Als neu einfügen | Insert as New | Insérer comme nouveau |
| `aiActions.replace` | Ersetzen | Replace | Remplacer |
| `aiActions.rating` | Bewerte diesen Vorschlag | Rate this suggestion | Évaluer cette suggestion |
| `aiActions.rejectReason` | Warum möchtest du das verwerfen? | Why do you want to reject this? | Pourquoi souhaitez-vous rejeter ceci ? |
| `aiActions.rejectReasonPlaceholder` | Dein Feedback hilft der KI... | Your feedback helps the AI... | Votre retour aide l'IA... |
| `aiActions.submitRating` | Absenden | Submit | Soumettre |
| `aiActions.skipRating` | Überspringen | Skip | Ignorer |
| `aiActions.ratingSubmitted` | Danke für dein Feedback! | Thanks for your feedback! | Merci pour votre retour ! |
| `aiActions.generating` | Generiere... | Generating... | Génération... |
| `aiActions.aiThinking` | KI denkt nach... | AI is thinking... | L'IA réfléchit... |
| `aiActions.connectionLost` | Verbindung verloren. Prüfe deine Internetverbindung. | Connection lost. Check your internet connection. | Connexion perdue. Vérifiez votre connexion internet. |
| `aiActions.connectionLostRetry` | Erneut verbinden | Reconnect | Reconnecter |
| `aiActions.newSuggestions` | Neue Vorschläge | New Suggestions | Nouvelles suggestions |
| `aiActions.original` | Original | Original | Original |
| `aiActions.suggested` | Vorschlag | Suggested | Suggestion |

Deprecated keys (DO NOT use):
- `aiModal.accept` → `aiActions.accept`
- `aiModal.reject` → `aiActions.reject`
- `generation.stop` → `aiActions.stop`
- `generation.accept` → `aiActions.accept`
- `generation.reject` → `aiActions.reject`
- `annotation.keep` → `aiActions.accept`
- `annotation.undo` → `aiActions.reject`
- `rewrite.cancel` → `aiActions.stop`
- `rewrite.replace` → `aiActions.replace`
- `sessionPanel.addToDraft` → `aiActions.addToDraft`
- `kb.sessions.accept` → `aiActions.accept`
- `kb.sessions.reject` → `aiActions.reject`
- `learning.rating` → `aiActions.rating`
- `coAuthor.acceptAll` → `aiActions.acceptAll`
- `coAuthor.rejectAll` → `aiActions.rejectAll`
- `coAuthor.applySelected` → `aiActions.applySelected`

### 16.9 Machine-Checkability

§16 compliance is **enforced, not aspirational**. The rules in §16.1–§16.8 are
checked by 11 automated gates in `scripts/checks/check_ai_interaction_compliance.py`,
run via `just check-ai-ux` (also part of `just check`). The governance contract and
the machine-readable inventory live at `docs/architecture/governance/ai-ux-compliance-v2.md`
and `scripts/checks/ai_operation_inventory.yaml` (17 operations, all carrying the §4
required fields). Checks 6–11 were added for the CR-07 UX Closure v2; checks 1–5
predate it.

| # | Check | Enforces |
|---|-------|----------|
| 1 | `useAIOperation` in AI components | §16 lifecycle/loading/error — AI flows use the shared primitive |
| 2 | No raw `AbortController` in React AI components | §16.2 cancel via the hook (structural excludes only for non-React extensions) |
| 3 | `aiActions.*` error keys present in all locales | §16.5 i18n-backed, actionable errors (DE/EN/FR parity) |
| 4 | No hardcoded AI `error.message` in TSX | §16.5 structured error mapping via `mapSSEError` |
| 5 | No deprecated `useConnectionLost` | §16.7 connection-loss handling via the shared primitive |
| 6 | No deprecated §16.8 AI-action aliases | §16.4 canonical vocabulary (exact alias gate, not a whole-namespace ban) |
| 7 | `useAIOperation.execute` propagates the signal | §16.2 cancel reaches transport, not just local UI state |
| 8 | `.ai_interaction_exclude` entries fresh + AUFG-linked | governed exceptions cannot silently rot |
| 9 | CR-AUFG IDs referenced in audit exist in the registry | lifecycle SSOT stays in sync |
| 10 | Operation inventory has required §4 fields | every AI operation is documented (transport, lifecycle, cancel, error, keyboard, …) |
| 11 | Resolved AUFG entries have implementation + enforcement evidence | no `resolved` without on-disk files + a regression gate (finding-lifecycle §5) |

Each check ships with unit tests under `tests/unit/scripts/checks/test_check_{1..11}_*.py`.
Structural exceptions (non-React extensions, callback-SSE transports) are tracked as
governed baseline debt in `.ai_interaction_exclude` with owner, reason, exit criteria, and
an AUFG link; Check 8 rejects stale or unlinked exceptions. Current state: `just check-ai-ux`
reports 0 violations and 3 governed exclusions; Check 11 validates all resolved AUFG entries.
