# Brand-Assets (Logo-Familie), Design-Dokument

Datum: 2026-10-30. Status: vom Nutzer freigegeben (Chat, 2026-10-30).

## Was gebaut wird

Narrare hat kein Brand-Asset (kein Favicon, kein Logo, kein `public/`).
Gebaut wird die vollständige Familie auf der bereits existierenden Identität
aus `web/globals.css` (warmes Papier Hue 85, Sepia primary Hue 45). Kein
Rebrand: die Tokens sind und bleiben die eine Designfläche.

## Design-Entscheidungen (vom Nutzer gewählt)

1. Motiv: Variante D „Kachel-Monogramm". Abgerundete Kachel in `--primary`,
   Serifen-N in Papierton. Die Kachel trägt ihren eigenen Grund und liest
   sich auf hellem und dunklem Theme sowie in 16 px (in der Mockup-Sitzung
   verifiziert).
2. Serif: EB Garamond, Gewicht 600. Gewählt aus vier Kandidaten (EB Garamond,
   Fraunces, Newsreader, Cormorant Garamond), live verglichen als Subsets.
3. Glyphen-Härtung: Das N und „Narrare" werden aus dem Font in SVG-Pfade
   überführt. Keine `<text>`-Elemente, keine Font-Datei im Repo. Die Marke
   rendert damit überall identisch: README, GitHub, SVG, PNG.

## Festgelegte Farben

Berechnet aus den Tokens (`oklch` → sRGB, dreistellige Rundung):

- Kachel: `#743B1F` (aus `--primary`, hell)
- Glyph auf Kachel: `#FCFAF6` (aus `--background`, hell)
- Tinte (Wortmark): `#24211C` (aus `--foreground`, hell)
- `#D39562` (`--primary`, dunkel) wird in keinem Asset dieses Tasks benutzt;
  die Kachel deckt beide Themes ab.

Es gibt eine kanonische Palette. Alternative Varianten (dunkle Kachel,
`currentColor`) wurden verworfen: kein zweiter Konsument, mehr Dateien.

## Erwartetes Datei-Set

Erzeugt: `assets/logo/icon.svg`, `assets/logo/wordmark.svg`,
`assets/logo/lockup.svg`, `web/public/favicon.svg`,
`web/public/favicon-32.png`, `web/public/favicon-16.png`,
`web/public/apple-touch-icon-180.png`, `assets/logo/social-og.png` (1280×640),
`assets/logo/avatar.png` (1024×1024).
Geändert: `web/index.html` (Favicon-Links), `README.md` (Header-Embed).

Das überschreitet den ≤3-Produktionsdateien-Budget. Deck-Regelung (Koordinator,
2026-10-30, Chat): „Asset-Familie, einmalig" — die 9 erzeugten Dateien stehen
als erwartetes Set im Plan; Abweichungen sind Abbruch-Kriterium.

## Verworfene Ansätze

- SVG-`<text>` mit `font-family`: rendert ohne installierte Font anders,
  unbrauchbar für README und GitHub.
- EB Garamond als Webfont in der App: kein Konsument der Assets braucht es;
  als separates Follow-up Issue (siehe unten), nicht in diesem Task.

## Follow-up (separater Issue, nicht in diesem Task)

„Brand-Typo am Prose-Surface": `web/globals.css` `.ProseMirror` nutzt
Georgia-Serif. EB Garamond dort statt Georgia verbindet die Brand-Typo mit
der Textfläche. Selbstgehostetes Subset in `web/public` (~50 KB, OFL,
local-first kompatibel). Layout-Metrics ändern sich leicht; Gatter:
`just test-frontend` plus Editor-E2E.

## Hände-behaltene Quests

- GitHub-Upload macht der Nutzer selbst: `social-og.png` in Repo-Settings
  („Social preview"), `avatar.png` in Profil/Repo-Settings. Wir liefern nur
  die Assets.
- Favicon-PNGs in Hirn-Größen 32/16/180; apple-touch ohne Eckenrundung
  (das OS rundet).
