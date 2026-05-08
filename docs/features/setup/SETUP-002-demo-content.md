---
id: SETUP-002
title: "Demo Projects"
status: planned
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

---

## The Three Demo Projects

### Im stillen Wald ✅ Content exists
- **Genre:** Literarische Fiktion
- **Language:** German (`de`)
- **Chapters:** 2
- **Characters:** 3 (Anna Müller, Johann Bauer, Der Waldgeist)
- **Locations:** 2 (Der stille Wald, Das Försterhaus)
- **Story:** Eine Lehrerin aus der Stadt besucht einen alten Förster am
  Waldrand. Sie sucht Erklärungen für die Geschichten, die ihre Schüler
  erzählen — über einen Waldgeist, über verschwundene Kinder, über Dinge,
  die jenseits der Logik liegen. Was sie findet, ist mehr als sie erwartet hat.
- **Tone:** Ruhig, literarisch, philosophisch. Langsames Tempo, viel Stille.
- **Good for testing:** German prompts, KB-Sessions auf Deutsch,
  Stimmungsanalyse, Voice-Analyse für literarischen Stil

**Existing KB entries (confirmed):**

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
- **Der stille Wald** — (referenced, entry to be created)

**Chapter 1:** "Das Flüstern im Wald" (~680 Wörter)
Anna besucht zum ersten Mal das Försterhaus. Gespräch über Beweise, Realität,
den Waldgeist. Endet mit Anna, die ein Lied aus dem Wald zu hören glaubt.
POV: third-limited (Anna). Status: draft.

---

### Echoes of the Thornwall 📋 Content to be created
- **Genre:** High Fantasy
- **Language:** English (`en`)
- **Chapters:** 4 (target: ~3,130 words total)
- **Characters:** 5 (Lyra, Aldric, Mara, Thornwall Guardian, Elder Soren)
- **Locations:** 2 (The Thornwall, Village of Ashford)
- **Story:** A young mage discovers that the magical barrier protecting her
  village is slowly failing — and that someone inside the village may be
  responsible.
- **Good for testing:** KB character sessions, writing extension, consistency check

---

### Dead Signal 📋 Content to be created
- **Genre:** Science Fiction / Thriller
- **Language:** English (`en`)
- **Chapters:** 3 (target: ~3,450 words total)
- **Characters:** 3 (Commander Voss, Dr. Chen, ARIA)
- **Story:** A deep-space crew receives a signal from a ship that disappeared
  forty years ago — and the signal contains their own voices.
- **Good for testing:** Plot analysis, timeline, beta reader, voice analysis

---

## File Structure

```
scripts/demo_data/
  german/
    project.md                ← novel metadata (title, genre, language, tone)
    chapters/
      ch-de-001-fluestern.md  ← "Das Flüstern im Wald" (exists ✅)
      ch-de-002-[title].md    ← chapter 2 (to be written)
    kb/
      char-anna.md            ← Anna Müller (to be created from notes)
      char-johann.md          ← Johann Bauer (to be created from notes)
      char-waldgeist.md       ← Der Waldgeist (exists as draft ✅)
      loc-foersterhaus.md     ← Das Försterhaus (exists ✅)
      loc-wald.md             ← Der stille Wald (to be created)

  fantasy/
    project.md
    chapters/
      ch-en-001.md ... ch-en-004.md
    kb/
      char-lyra.md ... (5 characters)
      loc-thornwall.md ... (2 locations)

  scifi/
    project.md
    chapters/
      ch-en-001.md ... ch-en-003.md
    kb/
      char-voss.md ... (3 characters)
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
status: draft
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
status: draft
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
status: draft
---
```

## Loading Implementation

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

## What Still Needs to Be Created

Before Phase 3 can complete:

| Item | Status |
|------|--------|
| `german/chapters/ch-de-002-*.md` | 📋 To be written (~1,000 words) |
| `german/kb/char-anna.md` | 📋 To be structured from existing notes |
| `german/kb/char-johann.md` | 📋 To be structured from existing notes |
| `german/kb/loc-wald.md` | 📋 To be written |
| All fantasy/ content | 📋 To be written |
| All scifi/ content | 📋 To be written |

The German demo has the strongest existing foundation and should be finalized first.

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
- `project-init+1` — German demo content confirmed: chapter 1 + Waldgeist + Försterhaus exist
