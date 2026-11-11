# Design-Token-Spezifikation & Übersicht — „Literary Modernism“
**Plattform:** Narrare — Literarisches Autoren- & Story-Architecture-Atelier  
**Design System ID:** `{{DATA:DESIGN_SYSTEM:DESIGN_SYSTEM_1}}`  
**Version:** 2.4 (Production Specification)

---

## 1. Farbpalette & Farb-Tokens (Color Palette)

Das Designsystem *Literary Modernism* basiert auf warmen, haptischen Papiertönen („Naturpapier / Büttenpapier“), tiefem Buchdrucker-Terracotta und präzisen funktionalen Kontrastfarben für Semantik, Kausalität und Status.

### 1.1 Oberflächen & Hintergründe (Surfaces & Canvas)

| Token Name | Hex-Code | CSS Variable | Verwendung & Semantik |
| :--- | :--- | :--- | :--- |
| `surface-canvas` | `#fff8f2` | `var(--surface)` | Globaler App-Hintergrund, Naturpapier-Fond (Warm White / Cream) |
| `surface-container-lowest` | `#ffffff` | `var(--surface-lowest)` | Höchste Kontrastebene: Modale, Tooltips, reine Texturflächen |
| `surface-container-low` | `#faf2ea` | `var(--surface-low)` | Subtile Card-Hintergründe, Zettelkasten-Karten, Manuskript-Körper |
| `surface-container` | `#f4ebd9` | `var(--surface-container)` | Standard-Container, Sidebars, Paneele und Tab-Hintergründe |
| `surface-container-high` | `#ebdcc9` | `var(--surface-high)` | Eingabefelder, inaktive Badges, hervorgehobene Sektionen |
| `surface-container-highest` | `#dec7ae` | `var(--surface-highest)` | Hover-Zustände auf Containern, Trennlinien, Card-Borders |
| `surface-dim` | `#e0d9d1` | `var(--surface-dim)` | Gedimmte Hintergrundbereiche, Sekundärflächen |
| `surface-dark-base` | `#181513` | `var(--surface-dark)` | Dark Mode Workspace, Tiefe Schacht-Karten, Kontrastpaneele |
| `surface-dark-card` | `#231f1c` | `var(--surface-dark-card)` | Dark Mode Cards, Graph-Knoten, Terminal-Overlays |

---

### 1.2 Primär- & Akzentfarben (Brand & Action)

| Token Name | Hex-Code | CSS Variable | Verwendung & Semantik |
| :--- | :--- | :--- | :--- |
| `primary` | `#743b1f` | `var(--primary)` | Buchbinder-Terracotta / Rostbraun; primäre Buttons, Brand-Akzente |
| `primary-hover` | `#5d2f18` | `var(--primary-hover)` | Hover-Zustand für Primäraktionen |
| `primary-active` | `#482412` | `var(--primary-active)` | Aktiver Klickzustand, gedrückter Button |
| `primary-container` | `#faebd7` | `var(--primary-container)` | Weicher Akzent-Hintergrund für aktive Menüpunkte & Badges |
| `on-primary` | `#ffffff` | `var(--on-primary)` | Text/Icons auf Primärflächen |
| `on-primary-container` | `#3e1d0b` | `var(--on-primary-container)` | Text auf weichen Akzentflächen |
| `secondary` | `#935433` | `var(--secondary)` | Wärmeres Terrakotta / Lederbraun; sekundäre Schaltflächen |
| `secondary-container` | `#f5e5db` | `var(--secondary-container)` | Sekundäre Chips, Entitäten-Tags (Figuren) |

---

### 1.3 Semantische Statusfarben (Narrative & Functional Semantics)

| Token Name | Hex-Code | CSS Variable | Semantische Bedeutung in Narrare |
| :--- | :--- | :--- | :--- |
| `success-kausal` | `#2e6930` | `var(--success)` | Kausalität 100% synchron, widerspruchsfreie Lore, validierter Beleg |
| `success-container` | `#e8f5e9` | `var(--success-container)` | Kausalitäts-Badge Hintergrund, verifizierte Statuskarten |
| `warning-divergenz` | `#b76e00` | `var(--warning)` | What-If Abweichung, ungeprüfter Entwurf, Zeitlinien-Drift |
| `warning-container` | `#fff8e1` | `var(--warning-container)` | Warnungsbanner, offene Lektorats-Anmerkungen |
| `danger-paradox` | `#ba1a1a` | `var(--danger)` | Kausalitätsbruch / Paradoxon, Signalverlust, Manuskript-Konflikt |
| `danger-container` | `#ffdad6` | `var(--danger-container)` | Fehler-Meldungen, Konflikt-Overlay im Lore-Graphen |
| `info-lore` | `#1f5974` | `var(--info)` | Wissenschaftliche Fakten, Primärquellen-Zitate, ARIA-Telemetrie |
| `info-container` | `#e1f3fa` | `var(--info-container)` | Quellen-Badges, Transponder-Tags, USGS-Belege |

---

### 1.4 Typografische Textfarben (Typography & On-Surface)

| Token Name | Hex-Code | CSS Variable | Kontrast-Verwendung |
| :--- | :--- | :--- | :--- |
| `text-primary` | `#231a14` | `var(--text-primary)` | Haupttext, Überschriften, Fließtext-Manuskript (Druckerschwärze) |
| `text-secondary` | `#5c4d42` | `var(--text-secondary)` | Metadaten, Zähler, Szenenbeschreibungen, Kapitel-Subheader |
| `text-muted` | `#8c7b6f` | `var(--text-muted)` | Deaktivierte Elemente, Tastaturkürzel-Hinweise, Ghost-Text |
| `text-subtle` | `#b5a598` | `var(--text-subtle)` | Typewriter-Out-of-Focus Absätze, Platzhalter |
| `border-subtle` | `#e6dbcd` | `var(--border-subtle)` | Feine Haarlinien, Tabellenränder, Card-Outlines |
| `border-focus` | `#743b1f` | `var(--border-focus)` | Aktiver Eingabefeld-Rahmen, Tastatur-Fokusring |

---

## 2. Typografie-Tokens (Typography Scale)

Die Typografie von Narrare kombiniert die geometrische Präzision einer modernen Atelier-Benutzeroberfläche (**Plus Jakarta Sans**) mit der literarischen Eleganz traditioneller Buchdruck-Schriften (**Newsreader / EB Garamond / Georgia**) und der technischen Exaktheit eines Normseiten-Schreibmaschinen-Fonts (**Courier Prime / Space Mono**).

### 2.1 Schriftfamilien (Font Families)

```css
--font-sans: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
--font-serif: 'Newsreader', 'EB Garamond', Georgia, serif;
--font-mono: 'Courier Prime', 'Space Mono', Menlo, Consolas, monospace;
```

### 2.2 Hierarchie & Schriftgrade (Type Scale)

| Token Name | Schriftfamilie | Größe (`px` / `rem`) | Zeilenhöhe | Schnitt (Weight) | Einsatzbereich |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `type-display-hero` | Serif | `36px` / `2.25rem` | `1.2` | Bold (700) | Romantitel, Splash-Screens, Buchcover |
| `type-title-large` | Sans | `24px` / `1.5rem` | `1.3` | Bold (700) | Studio-Modulüberschriften, Dashboard-Kopf |
| `type-title-medium` | Sans | `18px` / `1.125rem` | `1.4` | SemiBold (600) | Sektions-Header, Kausalitäts-Anker |
| `type-title-small` | Sans | `15px` / `0.9375rem` | `1.4` | SemiBold (600) | Card-Titel, Dossier-Figurenname |
| `type-manuscript-body` | Serif | `18px` / `1.125rem` | `1.75` | Regular (400) | Fließtext im Schreib-Workspace & Zen-Fokus |
| `type-body-regular` | Sans | `14px` / `0.875rem` | `1.5` | Regular (400) | Standard-UI, Formulartexte, Notizen |
| `type-body-dense` | Sans | `13px` / `0.8125rem` | `1.4` | Regular (400) | Dichte Datenlisten, Einreichungs-Pipeline |
| `type-caption-meta` | Sans | `11px` / `0.6875rem` | `1.3` | Medium (500) / Upper | Badges, Status-Tags, Wortzähler-Zusätze |
| `type-code-normseite` | Mono | `12px` / `0.75rem` | `1.6` | Regular (400) | VG-Wort Normseite (60 Anschläge/30 Zeilen) |

---

## 3. Abstands- & Raum-Tokens (Spacing & Layout Grid)

Das Layout basiert auf einem rigorosen **4px/8px-Basis-Grid** mit wohlüberlegtem dramaturgischem Weißraum (*Whitespace Rhythm*), der ein konzentriertes Arbeiten ohne visuelles Rauschen ermöglicht.

| Token | Wert | CSS Variable | Typische Anwendung |
| :--- | :--- | :--- | :--- |
| `space-1` | `4px` | `var(--space-1)` | Minimaler innerer Abstand bei Chips, Icon-Text-Gaps |
| `space-2` | `8px` | `var(--space-2)` | Dichte Buttons, Listen-Abstände, Badge-Padding |
| `space-3` | `12px` | `var(--space-3)` | Input-Padding, kompakte Menü-Einträge |
| `space-4` | `16px` | `var(--space-4)` | Standard Card-Innenabstand, Header-Padding |
| `space-5` | `20px` | `var(--space-5)` | Mittleres Paneel-Padding, Spaltenabstand im 3-Akt-Board |
| `space-6` | `24px` | `var(--space-6)` | Großes Sektions-Padding, Dialogfenster |
| `space-8` | `32px` | `var(--space-8)` | Modultrenner, Haupt-Workspace-Gutter |
| `space-12` | `48px` | `var(--space-12)` | Hero-Abstände, zen-fokussierte Ränder |
| `space-16` | `64px` | `var(--space-16)` | Zen-Modus vertikaler Textur-Offset |

---

## 4. Radien- & Ecken-Tokens (Border Radius)

Die Eckenradien spiegeln klassisches Buchbinder-Handwerk wider: feine, organische Rundungen (`ROUND_FOUR`), keine aggressiven Pills, sondern formale Klarheit.

| Token | Wert | CSS Variable | Komponenten-Zuordnung |
| :--- | :--- | :--- | :--- |
| `radius-none` | `0px` | `var(--radius-none)` | Normseiten-Vorschau, Buchblock-Kanten |
| `radius-sm` | `4px` | `var(--radius-sm)` | Badges, Status-Dots, Tastatur-Shortcuts (KBD) |
| `radius-md` | `8px` | `var(--radius-md)` | Buttons, Eingabefelder, Dropdowns, Zettelkasten-Karten |
| `radius-lg` | `12px` | `var(--radius-lg)` | Inhalts-Karten, Modal-Fenster, Graph-Container |
| `radius-xl` | `16px` | `var(--radius-xl)` | Große Studio-Panels, 3D-Buchmockup-Rahmen |
| `radius-full` | `9999px` | `var(--radius-full)` | Profil-Avatare, Audio-Record-Puls, Floating Action Pill |

---

## 5. Schatten & Tiefenwirkung (Elevation & Shadows)

Weiche, warme Umgebungsverschattungen mit bernsteinfarbenem Einschlag statt kalter grauer Schatten verleihen dem digitalen Atelier Tiefe und Haptik.

```css
/* Schatten-Tokens */
--elevation-0: none;
--elevation-1: 0 1px 2px rgba(35, 26, 20, 0.04), 0 1px 1px rgba(35, 26, 20, 0.02);
--elevation-2: 0 4px 6px -1px rgba(35, 26, 20, 0.06), 0 2px 4px -2px rgba(35, 26, 20, 0.04);
--elevation-3: 0 10px 15px -3px rgba(35, 26, 20, 0.08), 0 4px 6px -4px rgba(35, 26, 20, 0.04);
--elevation-4: 0 20px 25px -5px rgba(35, 26, 20, 0.10), 0 8px 10px -6px rgba(35, 26, 20, 0.04);
--elevation-book-3d: 0 25px 50px -12px rgba(35, 26, 20, 0.25), 8px 15px 30px rgba(116, 59, 31, 0.15);
```

---

## 6. Komponenten-Bausteine & Spezifikationen

### 6.1 Buttons & Interaktive Elemente
* **Primary Button:** Hintergrund `var(--primary)`, Text `var(--on-primary)`, Radius `var(--radius-md)`, Padding `8px 16px`, Font `var(--font-sans)` SemiBold 14px.
* **Secondary / Ghost Button:** Hintergrund transparent / `var(--surface-container-high)`, Rahmen 1px `var(--border-subtle)`, Text `var(--text-primary)`.
* **Kausalitäts-Action:** Button mit Icon und grünem / rotem Status-Dot zur sofortigen Widerspruchsauflösung.

### 6.2 Status-Badges & Lore-Pills
* **Kausalität synchron:** Hintergrund `#e8f5e9`, Text `#2e6930`, Border `#c8e6c9`, Icon Checkmark.
* **Paradoxon / Kollision:** Hintergrund `#ffdad6`, Text `#ba1a1a`, Border `#ffb4ab`, Icon Warning Triangle.
* **Entitäts-Pill (Person / Ort / Artefakt):** Hintergrund `var(--surface-container)`, Border `var(--surface-highest)`, Text `var(--text-secondary)`, Monogramm-Präfix.

### 6.3 Manuskript- & Editor-Spezifikation
* **Satzspiegel-Breite:** `680px` bis `740px` (optimale Zeilenlänge von 65–75 Zeichen für ermüdungsfreies Lesen).
* **Paragraphen-Abstand:** `1.5em` mit Einzug der Folgezeilen (`text-indent: 1.25em`) im Verlagsmodus, blockweiser Abstand im Notizmodus.
* **Typewriter-Fokus:** Aktiver Absatz `opacity: 1.0; font-weight: 400;`, umgebender Text `opacity: 0.35; transition: opacity 0.25s ease`.

---

## 7. JSON-Export für Developer-Handoff (Tokens as Code)

```json
{
  "name": "Literary Modernism",
  "version": "2.4.0",
  "tokens": {
    "color": {
      "surface": {
        "canvas": "#fff8f2",
        "card": "#faf2ea",
        "container": "#f4ebd9",
        "high": "#ebdcc9",
        "highest": "#dec7ae",
        "dark": "#181513"
      },
      "brand": {
        "primary": "#743b1f",
        "primaryHover": "#5d2f18",
        "secondary": "#935433",
        "accentContainer": "#faebd7"
      },
      "text": {
        "primary": "#231a14",
        "secondary": "#5c4d42",
        "muted": "#8c7b6f",
        "subtle": "#b5a598"
      },
      "semantic": {
        "success": "#2e6930",
        "warning": "#b76e00",
        "danger": "#ba1a1a",
        "info": "#1f5974"
      }
    },
    "typography": {
      "fontFamily": {
        "sans": "Plus Jakarta Sans, sans-serif",
        "serif": "Newsreader, EB Garamond, Georgia, serif",
        "mono": "Courier Prime, monospace"
      },
      "fontSize": {
        "xs": "11px",
        "sm": "13px",
        "base": "14px",
        "md": "15px",
        "lg": "18px",
        "xl": "24px",
        "hero": "36px"
      }
    },
    "radii": {
      "sm": "4px",
      "md": "8px",
      "lg": "12px",
      "xl": "16px",
      "full": "9999px"
    },
    "spacing": {
      "1": "4px",
      "2": "8px",
      "3": "12px",
      "4": "16px",
      "5": "20px",
      "6": "24px",
      "8": "32px",
      "12": "48px"
    }
  }
}
```
