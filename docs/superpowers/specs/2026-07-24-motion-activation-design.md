# Design: Motion-Aktivierung

**Status:** Approved
**Date:** 2026-07-24
**Scope:** packages/web/ — Frontend-Animationen mit motion (Framer Motion)

## Context

Narrare's Tech-Stack definiert `motion` (Framer Motion) als Standard für
Frontend-Animationen (TECH_STACK.md, GLOSSARY.md). Die Bibliothek ist
installiert (`^12.42.2`) aber komplett ungenutzt — 0 Imports im gesamten
Codebase. Stattdessen gibt es ad-hoc CSS-Transitions (~100 Stellen),
tw-animate-css (2 Komponenten), und 40+ Komponenten ohne jegliche
Animation.

## Architektonische Entscheidung

### Zentrale Variants-Datei (statt dezentral)

**Entscheidung:** `lib/motion-variants.ts` als einzige Quelle für
Animation-Variants.

**Begründung:**
- Variants sind reine Daten, nicht Komponentenlogik — gehören in ein
  shared Modul (RULE-06: Eine Verantwortlichkeit pro Datei)
- Zentrale Definition erzwingt Konsistenz über alle ~40 Komponenten
- Discoverability — neue Entwickler finden alle Animation-Patterns an
  einem Ort
- Wartbarkeit — Dauer/Easing ändern = eine Datei, nicht 40

### tw-animate-css Migration

**Entscheidung:** tw-animate-css wird aus `confirm-dialog.tsx` migriert
und anschließend entfernt.

**Begründung:**
- Ein einziges Animations-System (motion) statt zweier Paradigmen
- motion kann dasselbe leisten (`initial`/`animate`/`exit` statt
  `data-[state]` CSS-Klassen)
- Reduziert Komplexität für neue Entwickler und Code Reviews

### dnd-kit bleibt

**Entscheidung:** `@dnd-kit` wird nicht durch motion's Draggable ersetzt.

**Begründung:**
- dnd-kit ist spezialisiert auf Listen-Reordering mit Barrierefreiheit
  (Keyboard, Screen-Reader)
- motion's Draggable ist für freies Drag (Position, Snap, Flick)
- Fundamental verschiedene Use Cases — kein Overhead, sondern
  richtige Werkzeuge

## Animation-Typen

### 1. Overlay Fade
```ts
// Hintergrund-Overlay bei Modals/Panels
export const overlayVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1 },
  exit: { opacity: 0 },
};
```

### 2. Dialog Enter/Exit
```ts
// Modal-Dialoge: Fade + Scale
export const dialogVariants = {
  hidden: { opacity: 0, scale: 0.95 },
  visible: { opacity: 1, scale: 1 },
  exit: { opacity: 0, scale: 0.95 },
};
```

### 3. Panel Slide
```ts
// Rechte Seitenleiste: Slide-in von rechts (Desktop) / unten (Mobile)
export const panelSlideVariants = {
  hidden: { x: '100%' },
  visible: { x: 0 },
  exit: { x: '100%' },
};
```

### 4. List Item Stagger
```ts
// Listen-Einträge: Fade + Translate mit Stagger
export const listContainerVariants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.05 } },
};
export const listItemVariants = {
  hidden: { opacity: 0, y: 8 },
  visible: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
};
```

### 5. Banner Slide
```ts
// Benachrichtigungen: Slide-down von oben
export const bannerSlideVariants = {
  hidden: { opacity: 0, y: -20 },
  visible: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -20 },
};
```

### 6. Reduced Motion
```ts
// Alle Variants respektieren prefers-reduced-motion
// via motion's useReducedMotion() Hook
```

## Reduced Motion

`useReducedMotion()` aus motion wird in einer zentralen Hook-Wrapper
genutzt. Wenn aktiv, werden alle Animationen auf einfache Opacity-Wechsel
reduziert (kein Scale, kein Translate, kein Stagger).

> **Implementierung (2026-07-25):** Umgesetzt über einen globalen
> `<MotionConfig reducedMotion="user">`-Provider
> (`packages/web/components/shared/MotionProvider.tsx`, gewired in
> `app/layout.tsx`) statt eines pro-Komponenten Hooks. Eine erste
> Implementation gate nur `panel-shell.tsx` via `useReducedMotion()` und
> verfehlte ~22 weitere animierte Komponenten; der zentrale Provider behebt
> das (eine Quelle, automatisch für jeden `motion.*`-Nachkommen).
> Regression-Test: `components/shared/__tests__/MotionProvider.test.tsx`.
> Die pro-Komponente Hook-Datei `lib/hooks/use-reduced-motion.ts` existiert
> weiterhin, wird aber aktuell nicht mehr importiert.

## Phasen

### Phase 1 — Foundation
- `lib/motion-variants.ts` erstellen
- `hooks/useReducedMotion.ts` erstellen
- tw-animate-css Migration in `confirm-dialog.tsx`

### Phase 2 — Modals (12 Komponenten)
Komponenten mit `AnimatePresence` + `motion.div` für Overlay-Fade +
Dialog-Scale:
1. `RewriteSuggestionModal`
2. `CommandPalette`
3. `CoAuthorPanel`
4. `PromptPreviewDialog`
5. `PromptResetConfirmDialog`
6. `PromptLiveTestDialog`
7. `ToneFormDialog`
8. `ExtractionPanel`
9. `AddRelationshipDialog`
10. `StructureChangeDialog`
11. `NameGeneratorModal` (existierende CSS-Animation migrieren)
12. `ConfirmDialog` (tw-animate-css → motion)

### Phase 3 — Panels (PanelShell + Kinder)
- `PanelShell`: Slide-in from right (Desktop) / bottom (Mobile)
- `GenerationPanel`: Phase-Crossfade (`AnimatePresence mode="wait"`)
- `SessionPanel`: Banner-Animationen
- `ChatPanel`: Message-Stagger
- 9 Analysis-Panels: Shared Phase-Wrapper
- `UnblockPanel`: Slide-in

### Phase 4 — Listen-Stagger (6 Komponenten)
- `NovelCardGrid`
- ChatMessage-Listen (ChatPanel, SessionPanel)
- `KBEntryList`
- `RewriteSuggestionList`
- `UnblockResults`
- `VolumeCard`

### Phase 5 — Banner/Notification (6 Stellen)
- `SessionReconnectBanner`
- `ConnectionLostBanner`
- `StatusMessage`
- Inline-Banner in GenerationPanel
- Inline-Banner in SessionPanel

### Phase 6 — State-Crossfade (7 Stellen)
- Skeleton→Content (NovelCardGrid, EditorLoadingState)
- FeatureTour Step-Transitions
- Phase-Transitions in Analysis-Panels (shared mit Phase 3)

## Kompatibilität

- **tw-animate-css wird entfernt** nach Phase 1 (ConfirmDialog-Migration)
- **dnd-kit bleibt** für Drag-and-Drop
- **Sonner bleibt** für Toast-Animationen
- **Tailwind CSS transitions** bleiben für einfache Hover-Effekte
  (`transition-colors` etc.) — motion ergänzt, ersetzt nicht Hover-Basics

## Abweichungen / Accepted Exceptions

Die folgenden zwei bewusst akzeptierten Abweichungen vom "single animation
system (motion)"-Ziel wurden nach der Implementierung dokumentiert. Sie
verletzen nicht den Sinn der Regel, sondern adressieren technische
Randbedingungen, die motion nicht abdecken kann.

### 1. ConfirmDialog — CSS-Keyframes statt motion

`packages/web/components/ui/confirm-dialog.tsx` nutzt weiterhin CSS-`@keyframes`
(definiert in `packages/web/styles/tailwind.css`: `overlay-show`,
`overlay-hide`, `dialog-show`, `dialog-hide`), gesteuert über Radix'
`data-[state=open]` / `data-[state=closed]`-Attribute — **nicht**
`motion` / `AnimatePresence`.

**Grund:** Radix `AlertDialog` rendert über einen Portal und kontrolliert den
eigenen Exit-Lifecycle via `data-[state]`. Das komponiert nicht sauber mit
motions `AnimatePresence`-Exit (motion erwartet, das Mounting selbst zu
steuern). Für diese Komponenten-Klasse (Radix-Portal-gesteuerte Dialoge) sind
daten-gesteuerte CSS-Keyframes der idiomatic Ansatz und qualifizieren die
"single animation system"-Zielsetzung, ohne ihren Sinn zu verletzen.

### 2. Test-Environment — `motion/react`-Mock in `setupTests.ts`

`PhaseCrossfade` nutzt `<AnimatePresence mode="wait">`. happy-dom kann motions
rAF/WAAPI-Animation-Loop nicht treiben, sodass `mode="wait"` bei schnellen
Phasenwechseln (idle → loading → results) den Mount der Folgephase blockiert
— das würde jede Analysis-Panel-Component-Test timeouten lassen (51 betroffene
Tests).

**Lösung:** Ein globaler, scoped Mock in `packages/web/setupTests.ts` ersetzt
`AnimatePresence` → `Fragment` und `motion.*` → zwischengespeicherte
plain-DOM-Elemente (motion-only Props wie `variants`/`initial`/`animate`/
`exit` werden gestrippt; Komponenten-Funktionen werden gecacht, damit React
sie nicht bei jedem Render als neuen Typ ansieht). `MotionConfig` bzw.
`MotionConfigContext` bleiben **real** (via `importActual`), sodass die globale
Reduced-Motion-Wiring weiterhin echt getestet wird (siehe
`MotionProvider.test.tsx`). Real-Browser-Crossfade-Verhalten ist davon nicht
betroffen. Component-Tests verifizieren Verhalten, nicht Animation-Timing —
dieser Mock ist der Branchenstandard dafür.

## Risiken

| Risiko | Gegenmaßnahme |
|--------|---------------|
| Performance bei vielen `motion.div` | Nur nötige Komponenten animieren, `layout` sparsam einsetzen |
| Bundle-Größe | motion ist modular — nur `AnimatePresence` + `motion` importieren |
| Inkonsistente Dauer/Easing | Zentrale Variants erzwingen Einheitlichkeit |
| Breaking Changes | Jede Phase ist unabhängig deploybar |

## Definition of Done

- [ ] `lib/motion-variants.ts` existiert mit allen 6 Variant-Typen
- [ ] `hooks/useReducedMotion.ts` existiert
- [ ] tw-animate-css ist aus `confirm-dialog.tsx` migriert
  > **Akzeptierte Ausnahme** — siehe "Abweichungen / Accepted Exceptions" §1:
  > statt motion werden CSS-`@keyframes` in `styles/tailwind.css` genutzt
  > (Radix-Portal + `data-[state]`-Exit-Lifecycle komponiert nicht mit
  > `AnimatePresence`). `tw-animate-css` ist dennoch entfernt.
- [ ] tw-animate-css ist aus `package.json` und `tailwind.css` entfernt
- [ ] Alle 12 Modals haben AnimatePresence + motion.div
  > `ConfirmDialog` (Modal #12) ist die dokumentierte Ausnahme (CSS-Keyframes
  > statt motion) — siehe "Abweichungen / Accepted Exceptions" §1.
- [ ] PanelShell hat Slide-Animation
- [ ] Alle Listen haben Stagger-Animation
- [ ] Alle Banner haben Slide-Animation
- [ ] Skeleton→Content-Crossfades funktionieren
- [ ] `prefers-reduced-motion` wird respektiert
- [ ] Alle Animationen nutzen zentrale Variants
- [ ] Keine `tw-animate-css` Imports mehr im Codebase
