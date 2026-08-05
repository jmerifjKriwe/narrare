---
name: Narrare
description: AI-assisted creative writing environment — the writer's study.
colors:
  ink: "#030213"
  paper: "#ffffff"
  paper-ink: "oklch(0.145 0 0)"
  ash: "#717182"
  mist: "#ececf0"
  fog: "#e9ebef"
  indigo: "oklch(0.546 0.215 262.881)"
  editor-red: "#d4183d"
  hairline: "rgba(0, 0, 0, 0.1)"
  ring: "oklch(0.708 0 0)"
  sidebar: "oklch(0.985 0 0)"
typography:
  body:
    fontFamily: "ui-sans-serif, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.5
  editor:
    fontFamily: "ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 400
    lineHeight: 1.8
  label:
    fontFamily: "ui-sans-serif, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 500
    lineHeight: 1.5
rounded:
  sm: "calc(0.625rem - 4px)"
  md: "calc(0.625rem - 2px)"
  lg: "0.625rem"
  xl: "calc(0.625rem + 4px)"
spacing:
  xs: "0.25rem"
  sm: "0.5rem"
  md: "0.75rem"
  lg: "1rem"
  xl: "1.5rem"
  sidebar: "288px"
  panel: "320px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "oklch(1 0 0)"
    rounded: "{rounded.md}"
    height: "2.25rem"
    padding: "0 1rem"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ash}"
    rounded: "{rounded.md}"
    height: "2rem"
    padding: "0.25rem"
  button-toolbar-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.paper-ink}"
    rounded: "{rounded.md}"
    height: "1.75rem"
    padding: "0.25rem 0.5rem"
  badge-default:
    backgroundColor: "{colors.ink}"
    textColor: "oklch(1 0 0)"
    rounded: "{rounded.md}"
    padding: "0.125rem 0.625rem"
  badge-outline:
    backgroundColor: "transparent"
    textColor: "{colors.paper-ink}"
    rounded: "{rounded.md}"
    padding: "0.125rem 0.625rem"
---

# Design System: Narrare

## Overview

**Creative North Star: "The Writer's Study"**

Narrare ist eine Schreibumgebung, kein Tool. Der North Star ist ein ruhiger
Arbeitsraum bei Lampenlicht: der *Manuscript Desk*, an dem der Writer sitzt,
umgeben von seinem Material. Die Oberfläche verhält sich wie ein gut
eingerichteter Schreibtisch — alles Wichtige ist griffbereit, nichts drängt
sich auf, und der Text selbst ist das, was Licht bekommt.

Die Ästhetik ist **editorial und handwerklich**: Tinte auf Papier statt
leuchtender Panels, präzise 8–10px-Radien statt verspielter Formen, eine
einzige Indigo-Akzentfarbe statt eines Farbfeuerwerks. Die UI ist flach und
ruhig; Tiefe entsteht nur dort, wo Interaktion sie rechtfertigt. Dichte wird
zurückgenommen, wo Konzentration zählt — der Editor läuft auf 65ch Breite
mit großzügiger Zeilenhöhe (1.8), die Panels treten als gedämpfte
Sidebar-Ebenen zurück.

Technisch ist das System Token-basiert (CSS-Variablen) mit zwei Themes
(`narrare` — das Premium-Theme mit Indigo-Akzent, und `neutral` — die
Stone-Gray-Alternative), jeweils in Light und Dark. Light ist Tinte auf
Papier; Dark invertiert die Hierarchie, ohne die Ruhe zu verlieren. Motion
ist dezent: 0.15–0.2s, ein einziges Easing, Fade/Scale/Slide-Vokabular.

**Key Characteristics:**
- Ruhig, präzise, hilfreich — die UI tritt hinter den Text zurück
- Tinte-auf-Papier-Kontrast statt bunter Panels
- Flach by default; Tiefe nur als Reaktion auf Interaktion
- AI-Unterstützung ist on demand — nichts blinkt, nichts drängt sich auf
- Ein Indigo-Akzent pro Aufmerksamkeitspunkt, sonst Monochrom
- Zwei Themes (narrare / neutral) in Light und Dark, System-Sans-Typografie

### Named Rule
**The Lektor Rule.** The UI speaks like a quiet editor: informal (du), functional, and only when there is something to say. No AI-slop ("As an AI, I..."), no "Yay!", no hipster slang, no jargon, no hollow praise. The copy is as quiet as the surface.

## Colors

Eine monochrome Tinte-auf-Papier-Palette mit einem einzigen Indigo-Akzent
und einem kräftigen Editor's Red nur für destruktive Aktionen.

### Primary
- **Ink** (#030213): Die Primärfarbe — fast schwarze Tinte. Füllt Primary-Buttons, aktive Zustände, den Wizard-Stepper. Im Dark-Theme invertiert zu fast Weiß (oklch(0.985 0 0)), Text auf Ink wird zu Tinte-Dunkel.
- **Indigo** (oklch(0.546 0.215 262.881)): Der einzige Akzent. Dient als Series-Akzent (Badges, Karten-Highlights) und als Sidebar-Primary im Dark-Theme. Wird sparsam eingesetzt — ein Highlight pro Aufmerksamkeitspunkt.

### Neutral
- **Paper** (#ffffff): Der Hintergrund (Light). Editor- und Content-Fläche.
- **Paper-Ink** (oklch(0.145 0 0)): Primärtext auf Paper.
- **Ash** (#717182): Gedämpfter Text — muted-foreground, Platzhalter, Captions.
- **Mist** (#ececf0): Muted-Flächen, Code-Hintergründe, sekundäre Fills.
- **Fog** (#e9ebef): Accent-Flächen, Hover-Hintergründe.
- **Hairline** (rgba(0, 0, 0, 0.1)): Border/Trenner im Light-Theme.
- **Ring** (oklch(0.708 0 0)): Fokus-Ringe (focus-visible).
- **Sidebar** (oklch(0.985 0 0)): Seitenleisten-Fläche, fast weiß.

### Tertiary
- **Editor's Red** (#d4183d): Ausschließlich für destruktive Aktionen (Löschen, Fehler, Ghost-Text-Fehler). Kräftig, aber selten.

### Named Rules
**The Ink Rule.** Die Primärfarbe ist Tinte, kein Akzent. Alles, das als "wichtig" erscheinen soll, wird mit Ink gefüllt — Indigo markiert höchstens einen einzigen Fokuspunkt pro Bildschirm.

**The Red Rule.** Editor's Red erscheint nur bei destruktiven Aktionen oder echten Fehlern. Warnungen und sekundäre Zustände nutzen Ash, nie Red.

## Typography

**Body Font:** System-Sans-Stack (ui-sans-serif, system-ui, sans-serif — Tailwind-Default)
**Label Font:** Gleiche Familie, Weight 500 (font-weight-medium)
**Mono Font:** System-Mono für Code, Token-Inspektor, Shortcuts (font-mono)

**Character:** Bewusst keine Display-Font. Narrare ist eine Arbeitsumgebung —
Editorialität entsteht nicht durch eine Plakat-Schrift, sondern durch
Weißraum (65ch), großzügige Zeilenhöhe (1.8) und Ruhe. Die System-Sans liest
auf jedem Gerät identisch, ohne Font-Download.

### Hierarchy
- **Headline (h1)** (medium 500, 2xl, line-height 1.5): Seiten- und Sektions-Titel.
- **Title (h2)** (medium 500, xl, line-height 1.5): Panel-Titel, Dialog-Titel.
- **Subtitle (h3)** (medium 500, lg, line-height 1.5): Gruppen-Überschriften.
- **Body** (normal 400, 1rem, line-height 1.5): Standard-UI-Text.
- **Editor-Body** (normal 400, 1.0625rem, line-height 1.8, max-width 65ch): Der Schreibtext — die wichtigste Typografie im System.
- **Label** (medium 500, 1rem, line-height 1.5): Formular-Labels, Buttons.
- **Caption** (normal 400, text-xs, mono): Token-Werte, Shortcut-Hints, Metadaten.

### Named Rules
**The Study Rule.** Die UI-typografie ist leiser als der Text. Editor-Body hat die größte Zeilenhöhe (1.8) und die ruhigste Breite (65ch) — alles drumherum ist kleiner, gedämpfter und enger.

## Layout

Das Layout folgt der Schreibspur: Ein schmaler, zentrierter Textbereich
(65ch max-width), flankiert von einer 288px-Sidebar (Kapitelliste) links und
einem 320px-Panel rechts (Kontext). Panels sind auf Mobile Bottom-Sheets
(max-h 85vh, rounded-t-xl, shadow-2xl) und auf `lg` statische Sidebars
(border-l, keine Schatten). Der Setup-Wizard zentriert eine max-w-2xl-Karte.
Die Basis-Schriftgröße ist 16px (1rem); Abstände folgen einer 4px-Rasterung
(0.25 / 0.5 / 0.75 / 1 / 1.5rem).

## Elevation & Depth

Flach by default. Das System nutzt fast keine dauerhafte Tiefe — Flächen
sind im Ruhezustand flach, getrennt durch Hairline-Borders (rgba(0,0,0,0.1)
bzw. oklch(0.269 0 0) im Dark). Tiefe ist eine Reaktion: Primary-Buttons
tragen shadow-sm (0 1px 2px 0 rgb(0 0 0 / 0.05)), um ihre Klickbarkeit zu
signalisieren; Mobile-Panels heben sich mit shadow-2xl vom Text ab; Dialoge
erscheinen mit Scale-Fade (0.95 → 1, 0.2s).

### Shadow Vocabulary
- **Button-Lift** (`box-shadow: 0 1px 2px 0 rgb(0 0 0 / 0.05)`): Primary-Buttons, aktive Stepper.
- **Panel-Lift** (`box-shadow: 0 25px 50px -12px rgb(0 0 0 / 0.25)`): Mobile Bottom-Sheets.

### Named Rules
**The Flat-By-Default Rule.** Flächen sind flach im Ruhezustand. Schatten erscheinen nur als Reaktion auf Interaktion (Hover, Fokus, temporäre Überlagerung) — nie als dauerhafte Hierarchie-Aussage.

## Shapes

Radius-Strategie: sanft, aber nicht verspielt. Der Basis-Radius ist 0.625rem
(10px); abgeleitet sm = 0.375rem, md = 0.5rem, xl = 0.875rem. Buttons und
Inputs nutzen md (0.5rem), Cards und Wizard-Karten lg (0.625rem), Mobile-Panels
oben xl (0.875rem). Badges sind rounded-md mit 2px-Padding. Einzige
Vollkreise: der Wizard-Stepper (w-10 h-10, border-2) und Status-Dots.
Border-Sprache: 1px Hairline; Borderless wo möglich (Inputs transparent,
Border kommt erst über bg-input-background und Focus-Ring).

## Components

### Buttons
- **Shape:** Rounded-md (0.5rem); Fokus-Ring 1px ring-ring (focus-visible).
- **Primary:** Ink-Fill (light) / Paper-Fill (dark), Primary-Foreground-Text, h-9 (2.25rem), shadow-sm, Hover `hover:opacity-90`, Transition-colors.
- **Ghost (IconButton):** Transparent, Ash-Text, Hover `hover:bg-muted hover:text-foreground`, p-1 (sm) / p-1.5 (md); Loading ersetzt Icon durch Spinner (aria-busy).
- **Toolbar-Button:** Wie Ghost, zusätzlich `active`-State (bg-accent, aria-pressed), Label + Icon (gap-1.5, text-sm), Destructive-Variante (text-destructive, border-destructive).
- **Auth-Submit:** Volle Breite, h-9, bg-primary shadow-sm, `hover:bg-primary/90`, focus:ring-2 ring-offset-1.

### Badges
- **Style:** Rounded-md, text-xs font-semibold, px-2.5 py-0.5, border transparent.
- **Varianten:** default (Ink-Fill), secondary (bg-secondary), destructive (Editor's Red), outline (transparent, border-border, Foreground-Text). Hover opacity-90.
- **State:** Non-interactive (div, keine Button-Semantik).

### Cards / Containers
- **Corner Style:** Rounded-lg (0.625rem).
- **Background:** Card (Paper/oklch(0.145 0 0) dark).
- **Border:** 1px Hairline (border-border).
- **Shadow Strategy:** Shadow-sm bei Wizard-Karten; flach bei Inline-Karten.
- **Internal Padding:** p-10 bei Wizard, p-3/p-4 bei Inline-Karten.

### Inputs / Fields
- **Style:** Transparent Border, bg-input-background (#f3f3f5 light / oklch(0.145) dark), Rounded-md.
- **Focus:** Focus-Ring 1px ring-ring (focus-visible) — nie Border-Shift.
- **Error:** Destructive-Text für Fehlermeldungen (Editor's Red).

### Panels (Signature Component)
- **Shell:** Ein einziges gerendertes Element, das auf Mobile Bottom-Sheet (fixed, inset-x-0 bottom-0, max-h-85vh, rounded-t-xl, shadow-2xl) und auf `lg` statische Sidebar (w-96, border-l, keine Schatten) wird — kein duales Desktop/Mobile-Rendering (RULE-13).
- **Header:** p-4, border-b border-border, bg-card, Titel + Aktionen.
- **Tabs:** Panel-Tabs mit aktivem Ink-Akzent.

### Navigation / Wizard Stepper
- **Stepper:** 10x10 Vollkreis (rounded-full, border-2), aktiv = Ink-Fill, erledigt = Ink-Fill + ✓, zukünftig = Card-Fill + Hairline-Border. Verbindungslinien 2px, aktiv = Ink. Labels text-xs, medium, darunter; inaktive Labels auf Mobile ausgeblendet (opacity-0 sm:opacity-100).

## Do's and Don'ts

### Do:
- **Do** den Text führen: Editor 65ch, line-height 1.8, große Ruhe um den Schreibbereich.
- **Do** Tinte als Primärfarbe nutzen und Indigo auf genau einen Fokuspunkt pro Bildschirm beschränken.
- **Do** Tiefe als Reaktion einsetzen: flach im Ruhezustand, shadow-sm auf Primary-Buttons, shadow-2xl nur für Mobile-Panels.
- **Do** Editor's Red nur für destruktive Aktionen und echte Fehler verwenden.
- **Do** AI-Ergebnisse als annotierten, rückgängig machbaren Text zeigen (ai-generated-pending = 8–15% Primary-Tint), nie als unmarkierten Final-Content.
- **Do** Motion auf das minimale Vokabular beschränken: Fade (Overlay), Scale 0.95→1 (Dialog), Slide (Panel), 0.15–0.2s, ease-out.
- **Do** speak like the Lektor: informal (du), functional, direct — "Weiter geht's" only when the action deserves it, never chatter.

### Don't:
- **Don't** Neon-Startup-Look: keine leuchtenden Verläufe, keine gesättigten Banner-Farben, kein Glow.
- **Don't** überfrachten: keine Doppel-Panels, keine redundanten Toolbars, keine dekorativen Elemente ohne Funktion.
- **Don't** "Blinki-Bunti": keine unaufgeforderten Animationen, keine Blink-Effekte, keine Auto-rotierenden Karussells, kein pulsierendes AI-Branding.
- **Don't** AI-Unterstützung aufdrängen: kein Auto-Complete, das in den Text schreibt, keine Popups ohne Nutzeraktion (The On-Demand Rule).
- **Don't** die UI lauter machen als den Text — Schriftgrößen, Gewichte und Radien der UI bleiben unterhalb der Editor-Typografie.
- **Don't** neue Formsprache einführen (neue Radien, neue Akzentfarben, neue Schatten) außerhalb des definierten Token-Systems.
- **Don't** write AI-slop: no "As an AI, I...", no "Yay!", no hipster slang, no jargon, no hollow praise (The Lektor Rule).
