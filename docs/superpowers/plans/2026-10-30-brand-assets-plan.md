# Narrare Brand-Assets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Marke-Asset-Familie für Narrare bauen: Kachel-N-Icon, EB-Garamond-Wortmark (gehärtete Pfade), horizontale Lockup, Favicons (SVG+PNG), GitHub-Social-Preview und Repo-Avatar; Favicon-Links in `web/index.html`, Lockup-Embed in `README.md`.

**Architecture:** Alle SVGs teilen eine Glyphenquelle: EB Garamond 600, Subset „Narrare", via `fontTools` nach Pfade extrahiert. Raster-Ableitungen offline via `cairosvg`. Eine kanonische Festpalette, berechnet aus den Token in `web/globals.css`; keine Token-Änderung, keine Webfont-Einführung.

**Tech Stack:** Python 3.14 (`.venv`), fontTools + brotli, cairosvg, Pillow; git + gh CLI; `just check` / `just verify` als Gates.

**Spec:** `~/.opencode/plan/2026-10-30-brand-assets-design.md` (dieses Build
verschiebt sie gemeinsam mit diesem Plan nach `docs/superpowers/specs/`
beziehungsweise `docs/superpowers/plans/` und committet beide; Move, nie Copy).

## Global Constraints

Es wird auf Branch `openchamber/brand-assets` gearbeitet (Ausgang von `main`);
`main` hat Branch-Schutz — kein direkter Push.
**Nichts wird committet, bevor der Review grün ist.** Der Commit kommt erst
nach Task 7. Kein `--no-verify`.

**Festpalette (verbatim, aus Tokens berechnet):**
- Kachel `#743B1F` (← `oklch(0.42 0.09 45)`)
- Glyph auf Kachel `#FCFAF6` (← `oklch(0.985 0.005 85)`)
- Tinte/Wordmark `#24211C` (← `oklch(0.25 0.01 85)`)
- `#D39562` benutzt kein Asset dieses Plans.

**Skript-Grenzen:** keine `<text>`-, `<font>`- oder `font-family`-Strings in
einem committeten SVG; nur Pfade aus Task 1. Kanonische Festpalette, keine
Theme-Varianten. Prose-Surface/Token bleiben unverändert.

**Erwartetes Datei-Set (porcelain-Grenze für Task 7; Koordinator-Ruling
„Asset-Familie, einmalig"):**
Create: `assets/logo/icon.svg`, `assets/logo/wordmark.svg`,
`assets/logo/lockup.svg`, `web/public/favicon.svg`,
`web/public/favicon-32.png`, `web/public/favicon-16.png`,
`web/public/apple-touch-icon-180.png`, `assets/logo/social-og.png`,
`assets/logo/avatar.png`.
Modify: `web/index.html`, `README.md`.
Alles andere als dieses Set geht NICHT in den Commit.

**Task-Report-Pfad:** `/tmp/opencode/brand/task-report.md` — implementer
pflegt ihn fortlaufend (Feld-Vokabular: status, files, ledger, verify,
deviations, concerns; eng und zeilen-orientiert pro Feld).

**Verifikations-Fassung:** Befehl für Befehl ausführen, Output lesen; ein
Gate zählt nur mit gelesenem Output. Fehlende Tools werden lokal installiert
(`.venv`), keine Skip-Guards.

## Review Focus

Die Inputs, die der Spec-Text impliziert, aber kein Task-Test fängt, plus der
Test, der sie pinnt (jeweils im eigenen Task):

1. **16 px Favicon im dunklen Tab** — Glyph muss ohne Theme-Hilfe lesbar
   bleiben (Kachel trägt den Grund). Pinnt Task 3, visuelle Screenshot-Prüfung
   auf dunkler Fläche + Pixelprobe (Zentrum = `#743B1F`, Ecke transparent).
2. **README auf GitHub ohne installierte Font** — ein unbeabsichtigtes
   `<text>`/`font-family` hätte Georgia-Fallback zur Folge. Pinnt Task 2:
   `rg -ic 'text|font-family'` über alle drei SVGs muss 0 liefern.
3. **Kerning-Sprünge bei „aa"/„ar"** (nur Advances, kein GPOS) — Pinnt Task 5:
   Screenshot in Arbeitsbreite; korrigierbar nur über den mitgeloggten
   Letter-Offset (±6 Einheiten, in deviations dokumentiert).
4. **GitHub-Social-Image-Beschaffenheit** (2:1, Ränder frei von Tinte):
   1280×640 exakt, Tinte ≥64 px vom Rand. Pinnt Task 4: Pixelprobe + bbox.
5. **Local-first:** Build/CI darf nicht vom Netz abhängen — Font-/Raster-Tools
   nur in Task 1; committet wird keine Font-Datei. Pinnt Task 7: porcelain
   enthält keine `.woff2`/`.ttf`.

---

### Task 1: Werkzeuge + Glyphen-Extraktion

**Files:**
- Create: `/tmp/opencode/brand/glyphs.json` (Produkt), `/tmp/opencode/brand/task-report.md`
- Kein Repo-File.

**Interfaces:**
- Consumes: EB-Garamond-Subset-WOFF2 (siehe Schritt 2).
- Produces: `glyphs.json`: `{"upem": <int>, "glyphs": {"N": {"name": <str>, "d": <str>, "advance": <int>}, "a": …, "r": …, "e": …}}`. Pfade in Font-Einheiten (y-up, noch nicht gespiegelt). Tasks 2–4 konsumieren exakt dieses Schema.

- [ ] **Step 1: Werkzeuge installieren und Versionen loggen**

`.venv/bin/pip install fonttools brotli cairosvg Pillow`, dann
`.venv/bin/python -c "import fontTools, brotli, cairosvg, PIL; print(fontTools.version)"`.
Erwartet: Versionszeile. Schlägt sie fehl: Task-Abbruch, Report.

- [ ] **Step 2: Subset-Font beschaffen (offline-toleranter Neuzug)**

`/tmp/opencode/fs/ebgaramond.woff2` ist bereits vorhanden (Sitzung 2026-10-30).
Falls fehlend, exakt nachstellen:
`curl -s -A "<Browser-UA, Chrome-format>" "https://fonts.googleapis.com/css2?family=EB+Garamond:wght@600&text=Narrare&display=swap"`,
dann die eine `https://fonts.gstatic.com/…`-URL aus dem CSS laden.
Erwartet: Datei existiert, `file` sagt „Web Open Font Format (Version 2)".

- [ ] **Step 3: Glyphen extrahieren (Script-Body, verbindlich)**

```python
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
import json

font = TTFont("/tmp/opencode/fs/ebgaramond.woff2")
upem = font["head"].unitsPerEm
cmap = font.getBestCmap()
glyphset = font.getGlyphSet()
hmtx = font["hmtx"]
glyphs = {}
for ch in ["N", "a", "r", "e"]:
    gname = cmap[ord(ch)]
    pen = SVGPathPen(glyphset)
    glyphset[gname].draw(pen)
    glyphs[ch] = {"name": gname, "d": pen.getCommands(), "advance": hmtx[gname][0]}
assert all(g["d"] for g in glyphs.values()), "leerer Pfad"
assert upem == 1000, f"unerwartete upem: {upem}"
json.dump({"upem": upem, "glyphs": glyphs}, open("/tmp/opencode/brand/glyphs.json", "w"))
print("upem", upem, "| advances:", {k: v["advance"] for k, v in glyphs.items()})
```

- [ ] **Step 4: Output lesen und verifizieren**

N, a, r, e je mit nicht-leerem `d`; `upem == 1000`; Advances loggen (N > a ≥ r mit e-advance > r-advance, plausibel-geprüft). Die vier echten Glyphennamen aus `name` ins Report (z. B. `N: uniN`); Ergebnis unter Überschrift „Task 1" ins Report.

### Task 2: SVG-Familie (icon, wordmark, lockup)

**Files:**
- Create: `assets/logo/icon.svg`, `assets/logo/wordmark.svg`, `assets/logo/lockup.svg`

**Interfaces:**
- Consumes: `glyphs.json` (Task 1).
- Produces: SVG-Familie mit Geometrie-Vertrag: Kachel in 96er viewBox (rect x=4 y=4 w=88 h=88 rx=20, fill `#743B1F`); N mit bbox-höhe 62 Einheiten, Baseline y=71, horizontal zentriert auf 48. Wordmark: N-Kappenhöhe 34, Baseline y=24, Glyphen ab x=0 mit Advance-Offsets, viewBox aus Tinte-bbox mit 2 Einheiten Padding. Lockup: icon bei x=0, wordmark-Gruppe bei x=112, Baseline-Formel „Kachel-Mitte + Kappenhöhe/2" = y=65 (±6 Einheiten Korrektur erlaubt, in deviations dokumentiert).

- [ ] **Step 1: Builder-Script schreiben und ausführen**

Ein Python-Script (im Report als Anhang), das aus `glyphs.json` die drei SVGs schreibt. Transformation pro Glyph: `Transform(s, 0, 0, -s, dx, baseline_y)` mit `s = zielhoehe / bbox_hoehe` (bbox numerisch aus Pfad berechnen). Kerning: advances ohne GPOS-Kerning — Pin mit Begründung: EB-Garamond-Kerning für N-a/a-r/a-r ist visuell nah-null, geprüft in Task 5.

- [ ] **Step 2: Verifikation (nur voll, sonst Abbruch)**

`.venv/bin/python - <<'EOF'` Checkscript mit exakt diesen Asserts:
1. XML-Parsbarkeit jedes SVGs (xml.etree).
2. `rg -ic 'text|font-family' assets/logo/*.svg` → 0 Treffer.
3. Wordmark: genau 6 `<path>`-Kinder, Reihenfolge n-a-r-a-r-e.
4. Icon: genau 1 `rect` + ≥1 Pfad; Farbe `#743B1F`/`#FCFAF6` verbatim.
5. Wordmark: nur `#24211C` als fill.
6. Lockup: deckungsgleiche Kopie der definierten Kachel + Wortmark-Gruppe.
7. Farb-Lokation: `rg -c '#743B1F' icon.svg lockup.svg` → je ≥1.
Output verbatim ins Report.

### Task 3: Favicons + index.html

**Files:**
- Create: `web/public/favicon.svg`, `web/public/favicon-32.png`, `web/public/favicon-16.png`, `web/public/apple-touch-icon-180.png`
- Modify: `web/index.html` (nach `<title>`)

**Interfaces:**
- Consumes: `icon.svg`-Geometrie (Task 2).
- Produces: Favicon-Sets; 4 exakte `<link>`-Zeilen in `web/index.html` (Block: rel=icon svg + 32 + 16 + apple-touch-icon).

- [ ] **Step 1: favicon.svg + apple-touch-Quelle bauen**

`favicon.svg` = Icon-Geometrie unverändert (96er viewBox skaliert in Browsern).
Apple-touch braucht volle Kante: separate 96er Quelle mit `rx=0` (rect 0,0,96,96, Tinte `#FCFAF6`), nur temp.

- [ ] **Step 2: PNGs rasterisieren (cairosvg)**

favicon.svg → 32 und 16 px; apple-temp.svg → 180 px. Output nach
`web/public/`. Kommando + Log ins Report.

- [ ] **Step 3: index.html bekommt exakt diese 4 Zeilen** nach dem `<title>`:

```html
<link rel="icon" href="/favicon.svg" type="image/svg+xml" />
<link rel="icon" href="/favicon-32.png" sizes="32x32" type="image/png" />
<link rel="icon" href="/favicon-16.png" sizes="16x16" type="image/png" />
<link rel="apple-touch-icon" href="/apple-touch-icon-180.png" />
```

- [ ] **Step 4: Verifikation**

Pillow IHDR: 32×32, 16×16, 180×180; Pixelprobe: apple-touch (0,0) =
`#743B1F`; favicon-32/-16: Ecke transparent (Alpha 0), Zentrum =
`#743B1F` (Kachel beginnt bei 4/96, die Ecke ist Außenraum).
`rg -c 'rel="icon"' web/index.html` → 2, `rg -c 'apple-touch-icon' web/index.html` → 1. `just check` → PASS (Output unverkürzt ins Report).

### Task 4: GitHub-Assets + README

**Files:**
- Create: `assets/logo/social-og.png` (1280×640), `assets/logo/avatar.png` (1024×1024)
- Modify: `README.md` (eine Zeile nach dem Badge-Block, vor dem `> Local-first, …`-Zitat)

**Interfaces:**
- Consumes: Kachel + Wortmark-Geometrie (Task 2).
- Produces: PNGs als Fertig-Assets; README-Zeile:
  `<img src="assets/logo/lockup.svg" alt="Narrare" width="180" />`

- [ ] **Step 1: social-og.svg (temp) bauen**

Papier-Grund (1280×640, 100 % `#FCFAF6`), Lockup zentriert: Kachel 260 px,
Wortmark-Kappenhöhe 92, Lücke 65, Baseline = 320+46 (±6, deviation-Log).
Alle Teile ≥64 px vom Rand.

- [ ] **Step 2: avatar.svg (temp) bauen**

1024×1024, komplett `#743B1F` (rx=0, volle Kante), N-bbox-höhe 560,
Glyph-Mitte (512, 512).

- [ ] **Step 3: rasterisieren und README-Zeile setzen**

`cairosvg` beides; README-Zeile exakt wie oben, eine Zeile nach der letzten
Badge-Zeile, eine Leerzeile vor `> Local-first`.

- [ ] **Step 4: Verifikation**

Pillow: 1280×640 und 1024×1024; Pixelprobe Ecke og = `#FCFAF6`, Ecke avatar
= `#743B1F`; `rg -c 'assets/logo/lockup.svg' README.md` → 1.
`just check` → PASS.

### Task 5: Visuelle Prüfung (Vorschau + Screenshots)

**Files:**
- Create: `/tmp/opencode/brand/preview.html` (temp), 3 Screenshots.

**Interfaces:**
- Consumes: alle Assets.

- [ ] **Step 1: Preview-Seite bauen**

Lockup, Favicon-Chips in 24 px und 16 px, Wortmark allein auf Papier,
daneben ein dunkler Streifen mit der Kachel, darunter og/avatar als PNG.

- [ ] **Step 2: Screenshots + Kerning-Checks**

`python3 -m http.server` in `/tmp/opencode/brand`, Browser-Shell (openchamber
browser.open → capture): Lockup 1:1, Favicon-Zeile 1:1, og/avatar je 1:1.
Report: Screenshot-Pfade + Kerning-Einschätzung („ra"-Paar) — bei Bedarf
Baselining-Offset im Code korrigieren, nur ±6, dann Task 2-SVGs erneut
verifizieren.

- [ ] **Step 3: User-Prüfung anstoßen**

Screenshots dem Nutzer im Report zeigen (Bewertung: Korrektur-Pass oder
Freigabe). KEINE Zustimmung ersetzt diesen Schritt.

### Task 6: Follow-up-Issue umsetzen (EB-Garamond-Webfont)

- [ ] **Step 1: Issue-Draft validieren und anlegen**

`gh issue create --label follow-up --title "brand: EB Garamond als Webfont für das Prose-Surface" --body-file /tmp/opencode/brand/issue-body.md`
(Entwurf liegt im Design-Dokument, §Follow-up). Titel-Grammatik beachten,
`User-visible:` gehört nicht in ein Issue, sondern in den finalen Commit.

### Task 7: Branch, Commit, PR (nach Review!)

**Files:** nur die unter Global Constraints gelisteten Create/Modify-Pfade.

- [ ] **Step 1: Branch und Worktree**

`openchamber/brand-assets` von `main` (Voll-Isolation via Worktree-Skill bei
Bedarf: `superpowers:using-git-worktrees`). Porcelain-Pre-Check: Arbeitsbaum
rein, nichts außer dem erwarteten Set (nur committbare Dateien), sonst Abbruch.

- [ ] **Step 2: `just verify`**

Volle Gate-Ausführung, unverkürzt. PASS, Output ins Report. Fehlschlag → Abbruch, kein Fix
über Task-Grenzen ohne Ruling.

- [ ] **Step 3: Guarded Commit (porcelain-Pre-Flight)**

Exakt und nur das oben gelistete Set stagen (kein ADR-Draft, keine Font-Dateien, keine temp-SVGs), dann ein Commit:

```text
feat(brand): logo icon, wordmark and favicon family

Adds the first brand asset set: tile-N icon (#743B1F/#FCFAF6), EB Garamond
wordmark traced to paths, horizontal lockup, favicon SVG + PNG 32/16/180
and GitHub avatar + social preview raster. Palette read verbatim from
web/globals.css; the token surface is unchanged.

User-visible: Browser-Tab zeigt das Narrare-Favicon; README und Repo
tragen das Narrare-Logo.

Provenance: Glyphen N,a,r,e aus EB-Garamond-Subset (600), advances only
(GPOS-Kerning für die Paare visuell nahe-null, verifiziert im Preview).

Deviations: [aus task report, verbatim]

Verify: just verify grün; PNG-Dims 32/16/180/1280x640/1024 bestätigt.
```

(Namens-Hinweis: Alle Namens-Strings im finalen Commit heißen exakt
„Narrare".)

- [ ] **Step 4: Post-Commit-Verification + Push + PR**

`git status --porcelain` → clean; `git log --oneline -1` → eine Zeile, Subject
passt zur Struktur oben. Push nach `narrare` (Remote heißt `narrare`, nicht `origin`),
`gh pr create --base main` mit Titel `feat(brand): logo, favicon and wordmark family` und Report-Link im Body. Report abschließen (alle sechs Felder).

## Self-Review (ausgefüllt)

- Spec-Coverage: Design-Entscheidungen → Tasks 1–4 (Assets+Integration), Task 5
  (visuelle Prüfung), Task 6 (Follow-up Issue), Task 7 (Commit/PR). Kein
  Gap.
- Step-Scan: kein „TBD"; jeder Step entscheidet genau eine Sache; die
  Builder-Scripts sind(!) als Anhang ins Report (nicht ins Plan-Transkript).
- Typ-Konsistenz: `glyphs.json`-Schema einmal definiert; `#743B1F`/`#FCFAF6`
  /`#24211C` verbatim konsistent; 96er viewBox über alle Tasks konstant.
- Review Focus: 1→Task 3 (Pixel+Screenshot), 2→Task 2 (rg), 3→Task 5
  (Kerning), 4→Task 4 (Dims+Rand), 5→Task 7 (porcelain).
- Proportion: Plan ~180 Zeilen mit 5 Script-blöcken statt Code-Transkript —
  angemessen für die Design-Entscheidungsdichte.
