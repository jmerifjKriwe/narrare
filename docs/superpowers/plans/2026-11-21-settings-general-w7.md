# Settings Allgemein W7 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The settings capability's general surface — language, appearance, profile, the honest offline note — on the complete existing backend, plus the W6/W5 follow-up opener and the BookSettings retirement.

**Architecture:** Same shape as W5/W6 scaled down: a Stitch split round produces the W7 authority (Allgemein-only) and parks the W8 authority (AI-Regeln); one SDD task per surface concern; **one PR** (the owner's PR-für-PR rule); the settings e2e directory grows the kernel expectation.

**Tech Stack:** React + TanStack Router/Query, Tailwind on the shell tokens, i18n catalogs (de/en/fr), Vitest, Playwright E2E; backend untouched.

**Spec:** `~/.opencode/plan/2026-11-21-settings-general-w7-design.md` (moves to `docs/superpowers/specs/` at execution start) — the plan argues from it; executors read both.

## Global Constraints

- No new backend; the settings API is the boundary.
- The four conversation rulings are binding: immediate locale/theme (existing seams reused), one dirty form for name/goal, clean BookSettings retirement (no corpses), the user-block menu wires (Abmelden honestly disabled), the causality disclaimer line lands.
- Standing rules (CONSTRAINTS.md); **PR für PR** (one PR green + threads resolved before anything else); seats: implementer `glm-5.3-flash`, reviewer `glm-5.3` (rev. 7).
- Stitch alone designs; the harmonized Allgemein draft is owner-approved before Task 3.
- i18n: three catalogs, sorted parity, du-tone (fr tu).
- Route `/settings` (global; the gear door; `nav: false` stands).
- Absent-vs-carried-null is the wire contract everywhere (absent keeps, null clears/hands back).
- The phantom-dir trap: after any branch switch, remove leftover capability `e2e/__pycache__` dirs the target branch doesn't track.

## Review Focus

1. **Absent vs carried null on the settings PUT** — `{locale: null}` follows the browser, `{}` never crosses (client bug); pins on the wire. — Task 3.
2. **Language switch under a dirty profile form** — the i18n re-render must not eat the form's draft. — Task 3.
3. **The BookSettings retirement leaves no corpse** — no dead door, no stale E2E leg, the user-block label still reads the email fallback everywhere. — Task 4.
4. **Abmelden honestly disabled** (no backend) — no dead promise in the wired menu. — Task 3.
5. **One theme mechanism** — the settings page's toggle and the rail's toggle are the same seam (tri-state, no divergent copy). — Task 3.

---

### Task 1: Stitch split round (gate — coordinator + Stitch + owner, no porting)

The split brief from the design: `settings-ai-rules` becomes the **Allgemein-only authority** (Sprache & Aussehen as immediate controls, Autorenname/Tagesziel as one form with Verwerfen/Änderungen speichern, the offline note, the wired user-block menu's door) and the **AI-Regeln screen** (W8's authority: Provider/Modelle/Aufgaben tabs, parked). The Projekt-Regeln fields retire from both settings authorities — the pointer goes to writing's BookSettings. Archive as `shell/settings-allgemein-2.html` and `shell/settings-ai-rules-2.html`. Owner approves before Task 3.

### Task 2: Wave opener — #928, #929, #926, the disclaimer line (PR)

Each its own commit closing its issue (`Closes #928`/`#929`/`#926`): the route-leave guard over a dirty scene draft (the same confirm machinery, `app/capabilities/knowledge/…` — read the issue), the generated `structures.ts` consumed (the switcher imports it; the hand copy dies; `Closes #929`), the knowledge dialog viewport containment CSS (`Closes #926`), and the causality strip's honest bottom line (one key ×3 locales, the "kommt mit dem weiteren Aufbau" family — no banned vocabulary).

### Task 3: The Allgemein surface (PR)

**Files:** Create `app/capabilities/settings/web/` (routes.tsx, SettingsPage.tsx, profileForm.tsx, i18n/{de,en,fr}.json), `web/lib/query.ts` additions (`useSettings`, `useUpdateSettings`, `useTheme` if absent — read the existing seam first), `web/components/IconRail.tsx` + `TopBar.tsx` (the gear door + the wired user-block menu), generated tables via `just generate`.

**Interfaces:** the settings PUT body carries only dirtied fields (the novel-update rule); the profile form's save emits `{author_name?, daily_goal_words?}` with carried-null clears; the locale/theme controls reuse `useLanguageChoice`/`toggleTheme` verbatim — no second mechanism.

The page: Sprache & Aussehen (immediate, the draft's geometry), the profile form (dirty, Verwerfen/Änderungen speichern, refusal/busy faces, focus contracts), the offline note (the backend's truth — the local fake driver), honest outage/empty states. The user-block menu: Autorenname/Tagesziel/Einstellungen door in (section addressing), Abmelden disabled with its note. The rail's Planung-pattern gear door goes live.

### Task 4: BookSettings retirement (PR)

Writing's `BookSettings.tsx` profile section (locale, author_name, daily_goal_words) retires; its door routes to `/settings`; the writing E2E legs that edited the profile update to walk the settings surface (or drop, disclosed per leg); no dead door remains. The Projekt-Regeln fields stay untouched.

### Task 5: Settings E2E suite + kernel expectation (PR)

`app/capabilities/settings/e2e/` — browser legs: the round-trip (profile form save, carried-null clears), the immediate controls (locale switch re-renders, theme toggles), the wired menu doors, the gear door, the retired BookSettings route, de-DE, per-suite DB. The kernel expectation grows to include `"settings"` in the SAME commit as the directory.

### Task 6: Gap ledger + index (PR)

`docs/design/stitch/gaps/2026-11-21-settings.md` (the split's retirements: AI tabs → W8 pointer, Projekt-Regeln → BookSettings pointer, whatever the harmonized draft sheds); the W7 index issue (`follow-up-index`) + `docs/superpowers/follow-ups.md` row; any surviving finding becomes its child issue before merge.

### Task 7: Wave gate (PR)

`just verify` green; whole-branch review; the PR ready for the owner. One PR for the wave (PR-für-PR).
