# KB Benchmark Package 2 — Test Corpus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Author the German benchmark test corpus (12-chapter novel ~36k words) with machine-readable ground truth (YAML reference) and two error-variant overlay registries (light, complex), plus the riding inventory follow-ups deferred from package 1.

**Architecture:** Pure data/docs package — no production code, no runner code. Clean corpus is the single source; variants are overlay registries (exact snippet find/replace pairs anchored in clean chapters), never stored chapter copies. Every factual statement in prose is planned in the story bible's per-chapter information plan and anchored in the YAML reference with source chapters. Mechanical gates (YAML parse, rg -F anchor uniqueness, ID uniqueness, word-count corridor) run in-task via one-liners; durable tooling belongs to the runner slice.

**Tech Stack:** Markdown (German prose), YAML (reference + registries), rg + `uv run python -c` one-liners for gates, standard repo hooks.

**Spec:** `docs/superpowers/specs/2026-08-20-kb-benchmark-instrument-design.md` §4 (corpus), §8.3. **PO decisions:** F1=C (rich: 12 × ~3,000 words), F2=A (YAML), F3=A (PO checkpoint after story bible).

## Global Constraints

- Prose language: **German** (corpus data — the spec §4 exception). All meta-docs (README, story bible narrative, YAML keys, registry descriptions, commit messages): **English**; names/values/anchors/replacements inside them stay German verbatim.
- NO production code changes; no runner code. Created/modified files under `benchmark/` and `docs/_shared/CURRENT_STATE.md` only.
- Per-task cap: ≤ 3 files. Prose LOC naturally stays under ~250/task (one paragraph per line).
- Chapter word corridor: **2,400–3,600 words** per chapter (target ~3,000; gate `wc -w`).
- One paragraph per line in chapter Markdown; only `#` chapter title + `##` scene headings + `***` scene breaks as structure.
- Variants = overlay registries ONLY (`variants/<name>/errors.yaml` + `manifest.yaml`): each error carries an exact `anchor` string (unique in its clean chapter) + `replacement`; no variant chapter files exist.
- Gates per reference/registry file (in-task, verbatim commands in the tasks): YAML parses; `rg -F` anchor exactly 1 match in the named clean chapter; `rg -F` replacement 0 matches in clean (error not pre-present); IDs unique across entities/relations/events/errors.
- Ground truth describes the CLEAN corpus only. Error registries reference ground-truth fact IDs they violate.
- Information discipline: every factual statement a chapter plants (names, dates, places, relations, object ownership) must trace to the story bible's information plan for that chapter; the reference task for the batch anchors exactly those.
- Benchmark program remains manually-only: nothing here enters CI/pre-commit.

---

### Task 1: Story Bible (PO GATE after this task)

**Files:**
- Create: `benchmark/corpus/story-bible.md`

**Interfaces:**
- Consumes: spec §4; PO decisions F1=C, F3=A.
- Produces: the authoring backbone for all chapter and reference tasks — premise, cast (8–12 core + secondary/distractor figures), places/objects, master timeline (in-story calendar), per-chapter outline + per-chapter information plan (fact → chapter mapping). Later tasks may not invent facts absent from the bible; new facts require a bible amendment first.

- [ ] **Step 1: Author the bible** (English narrative about German material; names/values German)

Sections (binding):
1. **Premise & tone** — contemporary German family/relationship novel, ~2015–2026, mid-size cast across two cities (prototype arc: Anna Meyer, born 1991-04-17, architect, Hamburg→Munich 2021, married to Peter, brother Thomas, colleague Maria — formalize the spec §3/§4 prototypes). No crime/SF elements — maximum density of ages, moves, marriages, professions, inheritances.
2. **Cast** — 8–12 core figures with full sheets (name, birth date, profession incl. changes, residences incl. intervals, relationships) + ≥6 secondary figures incl. distractor designs: one name-near pair (e.g. Anna Meyer / Anna Meier — unrelated), one alias figure (Alexander "Alex"/"Sascha"), one figure who shares a workplace with another to invite confusion. Every figure gets a stable `p_<slug>` id.
3. **Places & objects** — places with `pl_<slug>` ids (move-relevant: 2 cities + ≥4 sub-locations); objects with `o_<slug>` ids incl. ≥3 with ownership changes (gift, sale, loss, inheritance) across the arc.
4. **Master timeline** — table of all dated events (in-story dates) in chronological order; every reference `valid_from/valid_to` and event date later must be consistent with this.
5. **Chapter outlines 1–12** — 2–4 sentences each (what happens, who appears).
6. **Information plan** — per chapter, the bulleted list of facts that chapter plants (fact id draft `F…`, statement, figure/place/object ids, source anchors for temporal facts). This is THE source the reference tasks anchor from; chapters 1–12 each get 8–15 planned facts. Distribute deliberately: age statements across ≥4 chapters (progression), residence intervals across ≥5, profession change mid-arc, relation reveals staggered (some facts restated later, some only implied-then-confirmed).
7. **Temporal design notes** — where the clean corpus states things that LOOK like contradictions but are not (age progression, retrospective mentions, "damals" references) — the material later complex-error variants will mimic.

- [ ] **Step 2: Self-verify** — timeline table has no internal ordering conflicts; every cast id appears in ≥1 chapter information plan; fact ids unique within the bible draft.

- [ ] **Step 3: Commit**

```bash
git add benchmark/corpus/story-bible.md
git commit -m "docs(corpus): add story bible — authoring backbone for the benchmark test novel"
```

- [x] **Step 4: PO GATE (hard stop)** — Coordinator presents bible digest (premise, cast, arc, timeline skeleton) to the PO and WAITS for approval/adjustment. No prose task starts before PO sign-off. PO adjustments are applied as a bible amendment commit before Task 3.
  - Executed 2026-08-21: bible digest presented in session (premise/cast/arc/timeline skeleton + the two ack points); PO approved ("ja") — mid-arc profession-change reading and future-promise watch design acked with the digest.

---

### Task 2: Corpus README + corpus manifest

**Files:**
- Create: `benchmark/corpus/README.md`
- Create: `benchmark/corpus/corpus.yaml`

**Interfaces:**
- Consumes: spec §4; this plan's overlay-variant ruling.
- Produces: binding format specs for all later tasks — reference YAML schemas, error taxonomy, overlay mechanics, gate catalogue; `corpus.yaml` is the machine-readable index (runner slice consumes it).

- [ ] **Step 1: Write `README.md`** with sections: Purpose (spec §4 pointer); Layout (clean/, reference/, variants/); Language rules (German prose / English meta); Variant overlay mechanism (registries, no stored chapters, materialization deferred to runner); Error taxonomy — light classes `attribute_value`, `date_mismatch`, `place_mismatch`, `relation_mismatch`; complex classes `implicit_temporal`, `near_duplicate_name`, `alias_confusion`, `negation`, `belief_uncertainty`, `rumor`, `retcon`, `foreshadowing_incomplete` (each with a one-line German example); Reference schemas verbatim:

```yaml
# reference/entities.yaml
persons:
  - id: p_anna                      # stable, unique
    name: Anna Meyer
    aliases: []                     # aliases used in prose, if any
    facts:
      - id: F001                    # unique across ALL reference files
        predicate: birth_date       # free predicate vocabulary, snake_case
        value: "1991-04-17"
        source_chapters: [3]        # chapters where the fact is stated
      - id: F002
        predicate: residence
        value: Hamburg
        valid_from: {year: 2015}
        valid_to: {year: 2021}
        source_chapters: [2, 6]
places: []                          # pl_* ids, same facts shape (location facts)
objects: []                         # o_* ids, ownership facts with validity intervals
```

```yaml
# reference/relations.yaml
- id: R001
  subject: p_anna                   # entity id
  predicate: sibling_of             # snake_case; direction subject -> object
  object: p_thomas
  source_chapters: [1]
```

```yaml
# reference/events.yaml
- id: E001
  name: Annas Umzug nach München
  date: {year: 2021, month: 3}      # precision as the prose states it
  participants: [p_anna]
  location: pl_munich
  source_chapters: [6]
```

```yaml
# variants/<name>/errors.yaml
variant: light                      # light | complex
base: clean
errors:
  - id: L01                         # L* for light, X* for complex
    class: attribute_value          # from the taxonomy above
    description: "Anna's age understated as 29 in ch-07 (truth: 33)."
    chapter: ch-07                  # clean chapter file stem
    anchor: "Anna, 31 Jahre alt,"   # EXACT substring, unique in that clean chapter
    replacement: "Anna, 29 Jahre alt,"
    ground_truth_ref: F001          # fact/relation/event id this error violates
```

```yaml
# variants/<name>/manifest.yaml
variant: light
base: clean
registry: errors.yaml
chapters_touched: [ch-05, ch-07]    # derived; must match registry contents
```

Plus the gate catalogue (parse / anchor-uniqueness / replacement-absence / id-uniqueness / word corridor) with the exact one-liners from the tasks.

- [ ] **Step 2: Write `corpus.yaml`** — corpus index: `name: benchmark-corpus`, `version: 1`, `language: de`, `chapters: [ch-01 … ch-12]` (list), `variants: [{name: light, registry: variants/light/errors.yaml}, {name: complex, …}]`, `reference: {entities: reference/entities.yaml, relations: reference/relations.yaml, events: reference/events.yaml}`.

- [ ] **Step 3: Commit**

```bash
git add benchmark/corpus/README.md benchmark/corpus/corpus.yaml
git commit -m "docs(corpus): add corpus format spec and manifest"
```

---

### Task 3: Chapters 1–3

**Files:**
- Create: `benchmark/corpus/clean/chapters/ch-01.md`, `ch-02.md`, `ch-03.md`

**Interfaces:**
- Consumes: story bible (Task 1, incl. PO amendments) — chapters realize outlines 1–3 and plant exactly the information-plan facts for chapters 1–3.
- Produces: German prose chapters; the anchor surface for the batch reference task (Task 4).

- [ ] **Step 1: Author the three chapters** — German, ~3,000 words each, one paragraph per line, `# <Titel>` + `***` scene breaks. Plant every information-plan fact for the chapter naturally in prose (no fact-dump paragraphs; weave into scene). Do NOT plant facts reserved for later chapters; incidental color that reads as factual (streets, weather, brands) must stay non-contradictory with the bible (invent freely where the bible is silent, but avoid new names/dates/places).
- [ ] **Step 2: Gates** — `wc -w` per file in 2,400–3,600; spot-list each planted fact with its containing sentence fragment (goes into the task report for the reference task).
- [ ] **Step 3: Commit**

```bash
git add benchmark/corpus/clean/chapters/ch-01.md benchmark/corpus/clean/chapters/ch-02.md benchmark/corpus/clean/chapters/ch-03.md
git commit -m "docs(corpus): add test novel chapters 1-3 (German)"
```

### Task 4: Reference for chapters 1–3

**Files:**
- Create: `benchmark/corpus/reference/entities.yaml`, `relations.yaml`, `events.yaml`

**Interfaces:**
- Consumes: chapters 1–3 (committed), bible information plan, schemas from README (Task 2).
- Produces: the initial reference files containing ALL facts/relations/events planted in chapters 1–3, with ids stable for the rest of the slice.

- [ ] **Step 1: Author the three YAMLs** per the README schemas, exactly covering the information plan of chapters 1–3; `source_chapters` values verified against the prose.
- [ ] **Step 2: Gates** — parse: `uv run python -c "import yaml; [yaml.safe_load(open(p)) for p in ['benchmark/corpus/reference/entities.yaml','benchmark/corpus/reference/relations.yaml','benchmark/corpus/reference/events.yaml']]"`; id uniqueness across the three files; every `source_chapters` entry in 1–3.
- [ ] **Step 3: Commit**

```bash
git add benchmark/corpus/reference/entities.yaml benchmark/corpus/reference/relations.yaml benchmark/corpus/reference/events.yaml
git commit -m "docs(corpus): add ground-truth reference for chapters 1-3"
```

### Task 5: Chapters 4–6
Same shape as Task 3 (`ch-04.md`, `ch-05.md`, `ch-06.md`; commit message `…chapters 4-6…`). Interface: bible plans for 4–6; may restate earlier facts only where the bible plans restatements (record the same fact id with extended `source_chapters` — done by the next reference task).

### Task 6: Reference for chapters 4–6
Same shape as Task 4, but files are Modified (append; extend `source_chapters` of restated facts instead of duplicating ids). Gates additionally: no id introduced twice across the file's history (`rg "id: " <file> | sort | uniq -d` empty).

### Task 7: Chapters 7–9
Same shape as Task 3 (`ch-07.md` … `ch-09.md`).

### Task 8: Reference for chapters 7–9
Same shape as Task 6.

### Task 9: Chapters 10–12
Same shape as Task 3 (`ch-10.md` … `ch-12.md`); arc closes per bible outline 12.

### Task 10: Reference for chapters 10–12
Same shape as Task 6.

---

### Task 11: Reference global validation & consistency pass

**Files:**
- Modify: `benchmark/corpus/reference/entities.yaml`, `relations.yaml`, `events.yaml` (fixes only), and `benchmark/corpus/story-bible.md` ONLY if a bible correction is required (any such change = a documented deviation, reported).

**Interfaces:**
- Consumes: complete reference (Tasks 4/6/8/10), complete prose (Tasks 3/5/7/9), master timeline.
- Produces: a validated, internally consistent reference — the scoring substrate for the whole program.

- [ ] **Step 1: Cross-checks** — (a) every reference item traces to prose (spot-verify 10 random facts by finding them in the named chapters); (b) every information-plan fact of the bible appears in the reference (completeness diff against the bible); (c) intervals/events consistent with the master timeline (no `valid_to` before `valid_from`, no event dated inside a contradicting interval); (d) relation endpoints exist as entity ids; (e) total counts: report entities/facts/relations/events.
- [ ] **Step 2: Fix findings** in the YAMLs (or flag bible defects as deviations).
- [ ] **Step 3: Re-run all gates** (parse + uniqueness + the README catalogue).
- [ ] **Step 4: Commit**

```bash
git add benchmark/corpus/reference/
git commit -m "docs(corpus): validate and reconcile ground-truth reference"
```

---

### Task 12: Light variant registry

**Files:**
- Create: `benchmark/corpus/variants/light/errors.yaml`, `manifest.yaml`

**Interfaces:**
- Consumes: clean chapters + reference (all committed); taxonomy from README.
- Produces: `errors.yaml` with 8–10 light errors: ≥2 `attribute_value` (age/height), ≥2 `date_mismatch`, ≥2 `place_mismatch`, ≥1 `relation_mismatch`, remainder free within light classes; `manifest.yaml` matching.

- [ ] **Step 1: Author the registry** — each error's `anchor` copied byte-exact from the clean chapter (short, ≤ ~80 chars, unique in that chapter); `replacement` minimal-edit; `ground_truth_ref` must exist in the reference.
- [ ] **Step 2: Gates per error** — `rg -F -c "<anchor>" benchmark/corpus/clean/chapters/<chapter>.md` = exactly 1; `rg -F "<replacement>" benchmark/corpus/clean/chapters/` = 0 matches; YAML parses; ids unique (`L01…`).
- [ ] **Step 3: Commit**

```bash
git add benchmark/corpus/variants/light/
git commit -m "docs(corpus): add light-error variant overlay registry"
```

### Task 13: Complex variant registry

**Files:**
- Create: `benchmark/corpus/variants/complex/errors.yaml`, `manifest.yaml`

**Interfaces:** like Task 12; taxonomy classes `implicit_temporal`, `near_duplicate_name`, `alias_confusion`, `negation`, `belief_uncertainty`, `rumor`, `retcon`, `foreshadowing_incomplete`.

- [ ] **Step 1: Author 8–12 complex errors** — at least one per class above; `replacement` may be a longer insertion (anchor a full paragraph, replace with modified/extended paragraph). `ground_truth_ref` = the fact/relation/event the passage misrepresents or falsely implies (for insertion-type errors, the implied-but-wrong target; document the implication in `description`).
- [ ] **Step 2–3: Gates + commit** — same as Task 12 (ids `X01…`; commit message `…complex-error variant overlay registry`).

---

### Task 14: Inventory riders A — in-direction additions + citation rewords (1/2)

**Files:**
- Modify: `benchmark/inventory/01-in.md` (reword evidence-path citation at line ~6; add entries for the R7/R8 analysis-domain coverage gaps)
- Modify: `benchmark/inventory/02-out.md` (reword evidence-path citation at line ~8)

**Interfaces:**
- Consumes: `04-findings.md` register rows R7/R8 (the recorded in-direction gaps — analysis/-domain writers outside Task 2's scope); README method + entry format.
- Produces: new `CAP-IN-09…` entries (mechanically verified per package-1 method: method-pinned decorator + mounted-path + client), reworded citations that no longer reference gitignored files (state: verification logs are session-local; re-run per README Method).

- [ ] **Step 1: Survey & add entries** for the R7/R8 gaps (same honesty rules; anything unmounted/unverifiable → findings, not entries; update the file's findings section counts if affected).
- [ ] **Step 2: Reword the gitignored-evidence citations** in both files (the 04-findings "Sources" column convention: no `.superpowers/` paths in committed docs).
- [ ] **Step 3: Gates** — `rg -n "superpowers|task-[0-9]+-report" benchmark/inventory/01-in.md benchmark/inventory/02-out.md` = 0 matches; new entries pass the package-1 verification method (output in report).
- [ ] **Step 4: Commit** `git add benchmark/inventory/01-in.md benchmark/inventory/02-out.md && git commit -m "docs(benchmark): inventory in-direction additions (R7/R8) + citation rewords"`

### Task 15: Inventory riders B — check citation reword, CHK-07 pointer, README counts

**Files:**
- Modify: `benchmark/inventory/03-check.md` (citation reword line ~9; close the CAP-CHK-07 "Task 5 may reclassify" forward pointer with its actual outcome)
- Modify: `benchmark/inventory/README.md` (reword citation line ~21; update status-section counts for the new in-entries from Task 14)

- [ ] **Step 1:** Apply both rewords + close the CHK-07 note (reference where the question landed: findings register / corpus slice).
- [ ] **Step 2: Gates** — `rg -n "superpowers|task-[0-9]+-report" benchmark/inventory/` = 0 matches anywhere now; README counts match `rg -c "^### CAP-"` (in now 8+N).
- [ ] **Step 3: Commit** `git add benchmark/inventory/03-check.md benchmark/inventory/README.md && git commit -m "docs(benchmark): inventory citation rewords + check-direction pointer closure"`

### Task 16: Inventory riders C — synthesis counts + CURRENT_STATE entry

**Files:**
- Modify: `benchmark/inventory/04-findings.md` (counts table, register rows for new entries, close the deferred riders note)
- Modify: `docs/_shared/CURRENT_STATE.md` (prepend the corpus-slice entry; today's date)

- [ ] **Step 1:** Update counts (direction × verdicts × LLM-backed) to include Task-14 additions; add register rows for any new findings; mark the package-1 deferred riders (evidence-citations, CHK-07, R7/R8) as resolved with this slice.
- [ ] **Step 2:** CURRENT_STATE entry: package 2 shipped (corpus structure, counts: chapters/words/entities/facts/relations/events, variant registries with error-class counts, PO checkpoint noted, inventory riders closed), commit range filled truthfully, dense house style.
- [ ] **Step 3: Gates** — counts cross-check (`rg -c "^### CAP-"` × 3 files vs table); `uv run python scripts/check_current_state_facts.py` exit 0.
- [ ] **Step 4: Commit** `git add benchmark/inventory/04-findings.md docs/_shared/CURRENT_STATE.md && git commit -m "docs(benchmark): corpus slice synthesis — inventory counts + CURRENT_STATE"`

---

## Plan Self-Review (executed)

- **Spec coverage:** §4 novel (Tasks 1,3,5,7,9) ✓; ground truth incl. temporal courses + chapter anchors (4,6,8,10,11) ✓; variants light/complex with recorded class+location (12,13) ✓; ingest modes are runner-slice concerns (corpus provides the material both modes consume) ✓; package-1 deferred riders (14–16) ✓; ADR-083 Decision 9 inventory check rides along ✓. F1=C → 12×3,000 with corridor gates ✓; F2=A → YAML schemas fixed in Task 2 ✓; F3=A → PO gate Task 1 Step 4 ✓.
- **Placeholder scan:** no TBD/TODO; prose content itself is the creative deliverable constrained by bible + gates (inherent to this slice, not a placeholder). Chapter-batch tasks 5–10 reference Task 3/4 shape explicitly with deltas — repeated shape is stated once and each task names its files and deltas (following the plan-style rule pragmatically; full repetition would add ~180 lines without new information).
- **Type consistency:** id schemes (`p_/pl_/o_`, `F…`, `R…`, `E…`, `L…`, `X…`), file paths, and schema fields are used identically across Tasks 2, 4, 6, 8, 10, 12, 13; registry `chapter` values match chapter file stems (`ch-01`…).
