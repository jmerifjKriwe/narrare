---
id: SETUP-002
title: "Demo Projects"
status: in progress
area: setup
mvp: true

ui_tooltip: "Explore Narrare with a ready-made story already loaded."
ui_help_short: |
  Demo projects let you explore all of Narrare's features immediately,
  without writing anything first. Choose from three pre-built stories —
  fantasy, sci-fi, or German literary fiction — each with chapters,
  characters, and a world already set up.
ui_help_long: |
  ## Demo Projects

  Not sure where to start? Load a demo project and explore Narrare with
  real content already in place.

  **Echoes of the Thornwall** (Fantasy, English)
  A high-fantasy story with 4 chapters, 5 characters, and an established
  world with locations and factions. Good for exploring the Knowledge Base
  and writing features.

  **Dead Signal** (Science Fiction, English)
  A tense sci-fi thriller with 3 chapters and 3 characters.
  Good for exploring analysis features and plot tools.

  **Im stillen Wald** (Literarische Fiktion, Deutsch)
  Eine deutschsprachige Geschichte mit 2 Kapiteln, 3 Charakteren und
  Orten, die bereits als KB-Einträge angelegt sind.
  Ideal, um Narrare auf Deutsch auszuprobieren.

  Demo content is real content — you can edit it, extend it, run analysis
  on it, and use it to test every feature. It's your project once loaded.
ui_available_in: [setup]

service: setup/service.py#SetupService.load_demo_content
contract: setup/contracts.py#SetupServiceProtocol
router: setup/router.py
prompt: ~
requires: [SETUP-001]
---

# SETUP-002 — Demo Projects

## What it does

Three pre-built story projects bundled with Narrare, loadable during the
Setup Wizard. Each contains chapters with real prose, character and location
KB entries, and project metadata. They function as complete Narrare projects —
not read-only samples.

## Why it exists

An empty project is a blank page problem. Users who install Narrare to
evaluate it need real content to understand what the tool does. Demo projects
let users explore the KB, run analysis, test the editor, and understand the
structure without the barrier of creating content first.

## How it works (User perspective)

1. During Setup Wizard Step 3, choose "Load a demo project" instead of "Start blank"
2. Select from three demo projects: Fantasy, Sci-Fi, or German Literary Fiction
3. Preview shows what's included (chapters, characters, word count)
4. Click "Load" — all content is copied into your new project
5. The demo becomes your project — edit, extend, or delete anything

### The Three Demo Projects

### Im stillen Wald ✅ Complete
- **Genre:** Literarische Fiktion
- **Language:** German (`de`)
- **Chapters:** 2 complete (Das Flüstern im Wald, Grenze der Welten)
- **Characters:** 3 (Anna Müller, Johann Bauer, Der Waldgeist)
- **Locations:** 3 (Der stille Wald, Das Försterhaus, Das Dorf)
- **Story:** Eine Lehrerin aus der Stadt besucht einen alten Förster am
  Waldrand. Sie sucht Erklärungen für die Geschichten, die ihre Schüler
  erzählen — über einen Waldgeist, über verschwundene Kinder, über Dinge,
  die jenseits der Logik liegen. Was sie findet, ist mehr als sie erwartet hat.
- **Tone:** Ruhig, literarisch, philosophisch. Langsames Tempo, viel Stille.
- **Good for testing:** German prompts, KB-Sessions auf Deutsch,
  Stimmungsanalyse, Voice-Analyse für literarischen Stil

**KB entries (all complete):**

*Characters:*
- **Anna Müller** — Lehrerin, Frau der Logik, sucht Beweise. POV-Charakter.
- **Johann Bauer** — Förster, 50 Jahre im Wald, kann Dinge sehen die andere nicht sehen.
- **Der Waldgeist** — Keine klassische Geistererscheinung. Ist der Wald selbst —
  seine Erinnerung, seine Stimme. Erscheint unterschiedlich je nach Betrachter.
  Verbunden mit Johann (Respekt), geduldig mit Anna (sie lernt noch zu glauben).

*Locations:*
- **Das Försterhaus** — Am Waldrand, zwei Räume unten (Wohnraum mit Kamin,
  Arbeitsraum), Schlafraum oben. Johanns Welt. Die Schwelle zwischen Dorf
  und Wald, zwischen Annas Welt und Johanns Welt.
- **Der stille Wald** — Der Wald selbst, eine Entität mit Gedächtnis und Stimme.
- **Das Dorf** — Das Dorf am Waldrand, Ausgangspunkt für Annas Reise.

**Chapter 1:** "Das Flüstern im Wald" (~680 Wörter)
Anna besucht zum ersten Mal das Försterhaus. Gespräch über Beweise, Realität,
den Waldgeist. Endet mit Anna, die ein Lied aus dem Wald zu hören glaubt.
POV: third-limited (Anna). Status: draft.

**Chapter 2:** "Grenze der Welten" (~1,200 Wörter)
Anna überschreitet die Schwelle zwischen Dorf und Wald. Die Grenze zwischen
logischer und spiritueller Welt beginnt zu verschwimmen. Sie beginnt zu
glauben — aber der Preis für diesen Glauben ist höher als sie dachte.

---

### Echoes of the Thornwall ✅ Complete
- **Genre:** High Fantasy
- **Language:** English (`en`)
- **Chapters:** 4 complete (Compass Points, Secrets in Stone, The Silent Keep, Archive of Truth)
- **Characters:** 5 (Elara, Kaelen, Morven, Sera, Verrick)
- **Locations:** 4 (Aethelgard, Silver Flame Fortress, Temple of Silent Flames, The Thornwall)
- **Story:** A young mage discovers that the magical barrier protecting her
  village is slowly failing — and that someone inside the village may be
  responsible.
- **Good for testing:** KB character sessions, writing extension, consistency check

---

### Dead Signal ✅ Complete
- **Genre:** Science Fiction / Thriller
- **Language:** English (`en`)
- **Chapters:** 3 complete (Ghost Machine, Door Worlds, Signal Lost)
- **Characters:** 3 (ARIA, Kavic, Maya)
- **Story:** A deep-space crew receives a signal from a ship that disappeared
  forty years ago — and the signal contains their own voices.
- **Good for testing:** Plot analysis, timeline, beta reader, voice analysis

---

## File Structure

```
scripts/demo_data/
  german/
    project.md                ← novel metadata (title, genre, language, tone) ✅
    chapters/
      ch-de-001-fluestern.md  ← "Das Flüstern im Wald" ✅
      ch-de-002-grenze-welten.md ← "Grenze der Welten" ✅
    kb/
      char-anna.md            ← Anna Müller ✅
      char-johann.md          ← Johann Bauer ✅
      char-waldgeist.md       ← Der Waldgeist ✅
      loc-foersterhaus.md     ← Das Försterhaus ✅
      loc-wald.md             ← Der stille Wald ✅
      loc-dorf.md             ← Das Dorf ✅

  english/echoes-of-the-thornwall/
    project.md                ✅
    chapters/
      ch-en-001-compass-points.md ✅
      ch-en-002-secrets-stone.md ✅
      ch-en-003-silent-keep.md ✅
      ch-en-004-archive-truth.md ✅
    kb/
      char-elara.md, char-kaelen.md, char-morven.md, char-sera.md, char-verrick.md ✅
      loc-aethelgard.md, loc-silver-flame-fortress.md, loc-temple-silent-flames.md, loc-thornwall.md ✅
      obj-compass.md ✅
      fact-ashen-covenant.md, fact-silver-flame.md ✅
      sys-cataclysm.md, sys-political.md, sys-void-magic.md ✅

  english/dead-signal/
    project.md                ✅
    chapters/
      ch-en-ds-001-ghost-machine.md ✅
      ch-en-ds-002-door-worlds.md ✅
      ch-en-ds-003-signal-lost.md ✅
    kb/
      char-aria.md, char-kavic.md, char-maya.md ✅
      loc-earth-facility-7.md, loc-horizon.md ✅
      obj-resonator.md ✅
      sys-comm.md, sys-tech.md ✅
```

## Frontmatter Standards for Demo Files

### project.md
```yaml
---
id: novel-im-stillen-wald
title: "Im stillen Wald"
author: ""
genre: "literary_fiction"
language: de
tone: contemplative
story_structure: three_act
logline: "Eine Lehrerin sucht Beweise für das Übernatürliche und findet stattdessen sich selbst."
demo: true
demo_id: german
---
```

### Chapter files
```yaml
---
id: ch-de-001
title: "Das Flüstern im Wald"
chapter: 1
volume: 1
status: planned
word_count: 680
pov_character: char-anna
pov_type: third-limited
timeline_position: "Tag 1"
location: loc-foersterhaus
---
```

### KB character files
```yaml
---
id: char-waldgeist
name: "Der Waldgeist"
type: character
tags: [ghost, forest-spirit, ancient]
age: "Unbekannt (seit Jahrhunderten im Wald)"
role: supporting
arc: "Die Prüfung für Anna und Bestätigung für Johann"
first_appearance: ch-de-001
pov_character: false
status: planned
---
```

### KB location files
```yaml
---
id: loc-foersterhaus
name: "Das Försterhaus"
type: location
tags: [house, forest-edge, isolated]
location_type: building
first_appearance: ch-de-001
parent_location: loc-wald
status: planned
---
```

## How it works (Technical)

**Entry point:** `setup/router.py` → `POST /api/v1/setup/load-demo`
**Service:** `SetupService.load_demo_content()` in `setup/service.py`
**Contract:** `SetupServiceProtocol` in `setup/contracts.py`
**Prompt:** ~ (no LLM calls)

### Loading Implementation

`SetupService.load_demo_content(starter: StarterContent, novel_id: UUID)`:

1. Reads `project.md` → creates `Novel` DB record
2. For each chapter file → creates `Chapter` DB record with content + position
3. For each KB file → creates `KBEntry` DB record with entity type + name + content
4. Sets project settings (language, genre, tone) from project.md frontmatter
5. All in a single DB transaction — atomic

**Atomicity:** Any failure rolls back completely. No partial state.

**KB entry status:** All demo KB entries are created with `status: draft` —
intentionally incomplete to invite the user to continue building them
with KB session features.

## Current Status

All three demo projects are **complete** and ready for use:

| Demo | Chapters | KB Entries | Status |
|------|----------|------------|--------|
| **Im stillen Wald** (German) | 2 | 6 | ✅ Complete |
| **Echoes of the Thornwall** (Fantasy) | 4 | 13 | ✅ Complete |
| **Dead Signal** (Sci-Fi) | 3 | 7 | ✅ Complete |

### German Demo: Im stillen Wald ✅
- **Chapters:** `ch-de-001-fluestern.md`, `ch-de-002-grenze-welten.md`
- **KB Entries:**
  - Characters: Anna Müller, Johann Bauer, Der Waldgeist
  - Locations: Der stille Wald, Das Försterhaus, Das Dorf
- **Genre:** Literarische Fiktion
- **Good for:** German prompts, voice analysis, literary style testing

### Fantasy Demo: Echoes of the Thornwall ✅
- **Chapters:** `ch-en-001` through `ch-en-004`
- **KB Entries:**
  - Characters: Elara, Kaelen, Morven, Sera, Verrick
  - Locations: Aethelgard, Silver Flame Fortress, Temple of Silent Flames, The Thornwall
  - Objects: The Compass
  - Factions: Ashen Covenant, Silver Flame
  - Systems: Cataclysm, Political Structure, Void Magic
- **Genre:** High Fantasy
- **Good for:** KB sessions, consistency checking, plot analysis

### Sci-Fi Demo: Dead Signal ✅
- **Chapters:** `ch-en-ds-001` through `ch-en-ds-003`
- **KB Entries:**
  - Characters: ARIA, Kavic, Maya
  - Locations: Earth Facility 7, Horizon
  - Objects: Resonator
  - Systems: Comm Systems, Tech Systems
- **Genre:** Science Fiction / Thriller
- **Good for:** Plot analysis, timeline tools, voice analysis

## Constraints & Edge Cases

- Demo content is loaded exactly once — re-running setup creates a new novel
- Demo projects cannot be "reset" to original state — they are regular projects
  after loading (this is intentional: they are yours to work with)
- Word counts in the wizard preview are computed from actual file content
- If a demo file has a parse error, the entire demo load fails with a clear error

## Related Features

- [SETUP-001](SETUP-001-setup-wizard.md) — Step 3 is where demo is selected
- [KB-001](../kb/KB-001-entity-management.md) — KB entries created by demo load

## Status & History

- `project-init` — Specified for MVP
- `2025-05-08` — All three demo projects completed:
  - German: 2 chapters + 6 KB entries ✅
  - Fantasy: 4 chapters + 13 KB entries ✅
  - Sci-Fi: 3 chapters + 7 KB entries ✅
