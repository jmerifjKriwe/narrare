<!-- Context: narrare-dev/concepts/design-philosophy | Priority: P1 | Source: docs/development/ui-principles.md | Updated: 2026-05-30 -->

# Design Philosophy

Narrare's frontend design principles, layout paradigm, and component conventions. All frontend work must follow these rules.

## 6 Design Principles

1. **Minimal, distraction-free writing environment.** The editor dominates the viewport. Everything else supports it.
2. **Content-first.** Navigation, suggestions, and analysis serve the writing surface. Nothing competes.
3. **Dark and light mode as first-class citizens.** Both complete and tested. Dark uses inverted primary tokens (white buttons on dark).
4. **i18n required for all visible text.** German as reference language. Zero hardcoded strings. Mock content exempt (data, not UI).
5. **Errors are actionable or silent.** Non-critical errors in non-blocking notifications that auto-dismiss. Never modals for non-critical errors.
6. **Settings persist without save buttons.** Preference changes save immediately.

## Layout Paradigm — Sidebar Navigation

The app uses a **persistent sidebar** (w-72 = 288px) on the left with main content filling the rest. **No header bar. No top navigation. No body-level scrolling.**

Shell: `<div className="size-full flex"><Sidebar /><main className="flex-1 min-h-0 min-w-0">{children}</main></div>`

### Sidebar Sections

1. **Logo area** — Icon (BookOpen) + "Narrare" + tagline, `p-6 border-b`
2. **Nav buttons** — 4 buttons: Editor (`/`), Welt & Charaktere (`/worldbuilding`), Analyse (`/analysis`), Einstellungen (`/settings`). Active: `bg-primary text-primary-foreground shadow-sm`
3. **Chapter list** — Editor view only, scrollable, active/inactive states
4. **New Chapter button** — `bg-primary text-primary-foreground`, Plus icon

### View Routing

| Route | Component | Description |
|-------|-----------|-------------|
| `/` | `EditorView` | TipTap editor (default) |
| `/worldbuilding` | `WorldBuilding` | 3-column entity management |
| `/analysis` | `AnalysisPanel` | Stats + AI analysis cards |
| `/settings` | `SettingsView` | 2-column settings with tabs |

All routes under `app/(studio)/`. Pages are thin wrappers importing a single view component.

## Component Conventions

- **Organization**: `components/studio/` (views), `components/editor/` (editor-specific), `components/ui/` (primitives)
- **Naming**: PascalCase, one component per file, file name matches component name
- **Client components**: `"use client"` directive required
- **Props**: defined inline above the component
- **Styling**: Tailwind CSS v4 only, semantic tokens (`bg-primary`, `border-border`), no hardcoded colors, `cn()` for merging
- **shadcn/ui**: prefer for new interactive elements

## Component Structure (5-step order)

1. `"use client"` directive
2. Imports (external → internal)
3. Types (co-located interface)
4. Constants / mock data
5. Component (named export): hooks → derived state → handlers → render

## Entity Types (WorldBuilding)

7 types: `characters` (User), `locations` (MapPin), `artifacts` (Package), `regions` (Map), `religions` (Church), `magic` (Wand2), `concepts` (Lightbulb). Each has i18n keys: `label`, `singular`, `article`, `subtitleLabel`, `subtitlePlaceholder`.

## SSR/Hydration Rules

- `immediatelyRender: false` on all TipTap `useEditor()` calls
- Date/time: init as `null`, set in `useEffect`
- No `new Date()` or `Math.random()` in initial state

**Reference**: `docs/development/ui-principles.md` (820 lines)
**Related**: narrare-dev/lookup/design-tokens · narrare-dev/examples/typescript-patterns
