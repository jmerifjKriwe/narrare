<!-- Context: narrare-dev/lookup/design-tokens | Priority: P2 | Source: docs/development/ui-principles.md | Updated: 2026-06-12 -->

# Design Tokens

CSS variable reference for Narrare's theme system. All values from `packages/web/styles/theme.css`.

## CSS Architecture

Import order (from `styles/index.css`): **tailwind.css → theme.css → editor.css**. Dark mode: class-based via `.dark` on `<html>`. Tailwind v4: `@theme inline { ... }` registers CSS vars as utilities.

## Color Palette — Light Mode

| Token | Hex | Tailwind | Usage |
|-------|-----|----------|-------|
| `--background` | `#f8f8f7` | `bg-background` | Main bg (warm off-white) |
| `--foreground` | `#1a1a1a` | `text-foreground` | Primary text |
| `--card` | `#ffffff` | `bg-card` | Card/surface bg |
| `--card-foreground` | `#1a1a1a` | `text-card-foreground` | Text on cards |
| `--popover` | `#ffffff` | `bg-popover` | Dropdown bg |
| `--primary` | `#2c2c2c` | `bg-primary` | Buttons, active states |
| `--primary-foreground` | `#ffffff` | `text-primary-foreground` | Text on primary |
| `--secondary` | `#f4f4f3` | `bg-secondary` | Secondary bg |
| `--muted` | `#f0f0ef` | `bg-muted` | Muted bg, badges |
| `--muted-foreground` | `#737373` | `text-muted-foreground` | Hint text |
| `--accent` | `#f4f4f3` | `bg-accent` | Hover states |
| `--destructive` | `#dc2626` | `bg-destructive` | Danger actions |
| `--border` | `#e5e5e4` | `border-border` | Borders, dividers |
| `--input-background` | `#fafafa` | `bg-input-background` | Input field bg |
| `--switch-background` | `#d4d4d3` | `bg-switch-background` | Toggle track (off) |
| `--ring` | `#525252` | `ring-ring` | Focus ring |
| `--sidebar` | `#fafafa` | `bg-sidebar` | Sidebar bg |
| `--sidebar-primary` | `#2c2c2c` | `bg-sidebar-primary` | Sidebar active |

## Color Palette — Dark Mode

Primary tokens **invert**: white buttons on dark backgrounds.

| Token | Hex | Note |
|-------|-----|------|
| `--background` | `#0a0a0a` | Near-black |
| `--foreground` | `#fafafa` | Off-white |
| `--card` | `#171717` | Dark surface |
| `--primary` | `#fafafa` | **Inverted**: white buttons |
| `--primary-foreground` | `#0a0a0a` | Dark text on white |
| `--muted-foreground` | `#a3a3a3` | |
| `--destructive` | `#ef4444` | Brighter than light |
| `--border` | `#262626` | |

## Semantic Color Usage

| Purpose | Tokens |
|---------|--------|
| Main CTAs | `bg-primary text-primary-foreground shadow-sm` |
| Elevated surfaces | `bg-card border border-border rounded-lg` |
| Hover states | `hover:bg-accent` |
| Delete/errors | `text-destructive`, `bg-destructive` |
| Input fields | `bg-input-background border border-border rounded-md` |
| Hint text | `text-muted-foreground` |
| Focus rings | `ring-ring` |

## Radii

| Token | Value | Tailwind |
|-------|-------|----------|
| `--radius` | `0.5rem` (8px) | Base |
| `--radius-sm` | 4px | `rounded-sm` |
| `--radius-md` | 6px | `rounded-md` |
| `--radius-lg` | 8px | `rounded-lg` |
| `--radius-xl` | 12px | `rounded-xl` |

## Typography

System font stack (no custom fonts). Weights: `--font-weight-medium: 500`, `--font-weight-normal: 400`. All headings use weight 500, line-height 1.5.

## Theme vs shadcn Default

| Property | shadcn | Our Theme |
|----------|--------|-----------|
| `--background` | `#ffffff` | `#f8f8f7` (warm off-white) |
| `--primary` | `#030213` | `#2c2c2c` (softer black) |
| `--radius` | `0.625rem` | `0.5rem` |
| `--border` | `rgba(0,0,0,0.1)` | `#e5e5e4` (opaque warm gray) |

Always use `theme.css` values, never shadcn defaults.

**Reference**: `docs/development/ui-principles.md`
**Related**: narrare-dev/concepts/design-philosophy · narrare-dev/examples/typescript-patterns
