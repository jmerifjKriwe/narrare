# Benchmark Test Corpus

This directory holds the test material for the KB infrastructure benchmark specified in
`docs/superpowers/specs/2026-08-20-kb-benchmark-instrument-design.md` §4. The corpus provides
the ground truth that benchmark runs are scored against. `story-bible.md` is the authoring
backbone from which all chapter content is derived; `corpus.yaml` is the machine-readable
index over the corpus.

## Layout

- `clean/chapters/` — 12 German chapter files `ch-01.md` … `ch-12.md`
- `reference/` — entities/relations/events YAML ground truth for the CLEAN corpus
- `variants/light/` — error registry, light variant
- `variants/complex/` — error registry, complex variant
- `story-bible.md` — authoring backbone
- `corpus.yaml` — machine index
- `README.md` — this file

## Language Rules

- Chapter prose: German.
- Meta-docs, YAML keys, YAML descriptions, commit messages: English.
- German names/values/anchors/replacements stay verbatim inside meta files.

## Variant Overlay Mechanism

Variants are registries, never stored chapter copies. Each error entry consists of an exact
`anchor` substring (unique within its clean chapter) plus a `replacement`. Applying a variant
to the clean corpus is a mechanical find/replace driven by the registry. Materialization —
building variant chapter files at runtime — is deferred to the benchmark runner slice.

Rationale: no chapter duplication, so clean-corpus fixes cannot silently invalidate variants,
and registries gate mechanically.

## Error Taxonomy

Light variant:

| Class | Definition | Example (DE) |
| ----- | --------- | ------------ |
| `attribute_value` | Factual attribute deviates from ground truth (e.g. wrong age). | `Lena ist 34.` (truth: 32) |
| `date_mismatch` | Event date is off. | `im März 2019` (truth: Februar 2019) |
| `place_mismatch` | Wrong location. | `in Hamburg` (truth: München) |
| `relation_mismatch` | Wrong relation type or wrong relation partner. | `Annas Kollege` (truth: ihr Bruder) |

Complex variant:

| Class | Definition | Example (DE) |
| ----- | --------- | ------------ |
| `implicit_temporal` | Temporal implication without explicit date that contradicts truth. | `noch zur Schulzeit` (truth: nach dem Studium) |
| `near_duplicate_name` | Name-near confusion introduced. | `Katharina` statt `Kathrina` |
| `alias_confusion` | Alias used to obscure identity. | `„Ricky"` (truth: Richard Brandt) |
| `negation` | Negated truth statement. | `Sie hat nie in München gearbeitet.` |
| `belief_uncertainty` | Belief/hedging presented where truth is knowable. | `Er glaubt, dass sie kommt.` (she does) |
| `rumor` | Unattributed hearsay asserting a falsehood. | `Man sagt, er sei pleite.` |
| `retcon` | Later statement contradicting an established fact without acknowledgment. | `nach ihrem Studium` (established: kein Abschluss) |
| `foreshadowing_incomplete` | Announcement without later confirmation. | `Sie würde es ihm später erklären.` (nie passiert) |

## Reference Schemas

Verbatim shapes; all files must parse as YAML; ids unique file-crossing.

```yaml reference/entities.yaml
persons:
  - id: p_anna                      # stable, unique
    name: Anna Meyer
    aliases: []                     # aliases used in prose, if any
    gender: female                  # persons only; male | female (kinship equivalence)
    facts:
      - id: F001                    # unique across ALL reference files
        predicate: birth_date       # snake_case predicate vocabulary
        value: "1991-04-17"
        source_chapters: [3]
      - id: F002
        predicate: residence
        value: Hamburg
        valid_from: {year: 2015}
        valid_to: {year: 2021}
        source_chapters: [2, 6]
places: []                          # pl_* ids, same facts shape
objects: []                         # o_* ids, ownership facts with validity intervals
```

```yaml reference/relations.yaml
- id: R001
  subject: p_anna                   # entity id
  predicate: sibling_of             # snake_case; direction subject -> object
  object: p_thomas
  source_chapters: [1]
```

```yaml reference/events.yaml
- id: E001
  name: Annas Umzug nach München
  date: {year: 2021, month: 3}      # precision as the prose states it
  participants: [p_anna]
  location: pl_munich
  source_chapters: [6]
```

```yaml variants/<name>/errors.yaml
variant: light                      # light | complex
base: clean
errors:
  - id: L01                         # L* light, X* complex
    class: attribute_value
    description: "Anna's age understated as 29 in ch-07 (truth: 33)."
    chapter: ch-07                  # clean chapter file stem
    anchor: "Anna, 31 Jahre alt,"   # EXACT substring, unique in that chapter
    replacement: "Anna, 29 Jahre alt,"
    ground_truth_ref: F001          # reference id this error violates
```

```yaml variants/<name>/manifest.yaml
variant: light
base: clean
registry: errors.yaml
chapters_touched: [ch-05, ch-07]    # derived; must match registry contents
```

## Gate Catalogue

- **G1 parse** — `uv run python -c "import yaml; [yaml.safe_load(open(p)) for p in ['benchmark/corpus/reference/entities.yaml','benchmark/corpus/reference/relations.yaml','benchmark/corpus/reference/events.yaml']]"`
- **G2 anchor uniqueness** — `rg -F -c "<anchor>" benchmark/corpus/clean/chapters/<chapter>.md` → exactly 1
- **G3 replacement absence** — `rg -F "<replacement>" benchmark/corpus/clean/chapters/` → 0 matches
- **G4 id uniqueness** — `rg -o "id: F[0-9]{3}" benchmark/corpus/reference/*.yaml | sort | uniq -d` empty (analogously R/E/L/X prefixes; restatement-style reuse does NOT exist in reference files)
- **G5 word corridor** — `wc -w benchmark/corpus/clean/chapters/ch-NN.md` within 2400-3600

## Ground Truth Scope

- The reference files describe the CLEAN corpus only.
- Variant registries violate that truth via `ground_truth_ref`; the reference stays clean-canonical.
- Ingest-mode material (incremental vs full import) consumes the same files; modes are a runner-slice concern.
- The YAML blocks under Reference Schemas are SHAPE examples: field names and structure are binding; example values (dates, ages, id slugs) are illustrative only — the story bible is the single fact source for reference and registry content.
