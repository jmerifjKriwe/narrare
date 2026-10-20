# The Feature Scaffolder — `just new-feature`

Starting a feature means creating a set of declaration files that several gates
check independently. Doing that by hand is a tour of failures: the feature
document's frontmatter, the test directories, the contract, the report stub, and —
when an intent is involved — eight declaration surfaces and three locale prompts.
The scaffolder writes all of those at once and then proves the result passes the
gates. A scaffold either arrives green or does not arrive at all.

## The recipe

```text
just new-feature <id> <layer...>
```

`<id>` is a feature id shaped like `FIND-099` (an uppercase prefix, a hyphen, a
number). `<layer...>` is one or more layer names; order does not matter and a
repeated name is used once. `--root PATH` exists for tests and mirror trees and
defaults to the current directory; normal use does not need it.

Every generated path is derived from the id through a slug: lowercased, every run
of non-alphanumeric characters becomes `_`, leading and trailing `_` are removed.
`FIND-099` therefore becomes `find_099`.

### Layers

The layer names choose which test skeletons and which core artifacts are written.
They do not wire anything into the application.

| Layer | What it adds |
|---|---|
| `core` | `tests/unit/core/test_<slug>.py`, plus `packages/core/narrare_core/<slug>/__init__.py` and `contracts.py` with an `@runtime_checkable` Protocol named `<Id>Protocol` |
| `api` | `tests/unit/api/test_<slug>.py` |
| `web` | `tests/unit/web/test_<slug>.py` |

Selecting `core` writes the Protocol stub because RULE-03 requires the contract
before the implementation: an empty, valid boundary is the first correct artifact
for that layer, and it keeps the service and router from depending on each other
later. The Protocol carries no methods until the feature's contract is designed —
see [What is deliberately never generated](#what-is-deliberately-never-generated).

### What a run writes

| Artifact | Path |
|---|---|
| Feature document | `docs/features/<ID>.md` |
| Test skeleton, one per layer | `tests/unit/<layer>/test_<slug>.py` |
| Core package initialiser, `core` only | `packages/core/narrare_core/<slug>/__init__.py` |
| Protocol stub, `core` only | `packages/core/narrare_core/<slug>/contracts.py` |
| Implementation-report stub | `docs/superpowers/plans/reports/<UTC date>-<slug>.md` |

The feature document starts at `status: planned` with `area: unassigned`, an
`## Open questions` section and empty prose sections for the author. Its
frontmatter `paths:` list contains the document itself and any planned path that
already existed when the document was rendered; the author extends it as the
implementation files appear. The report stub follows the report contract: scope,
verification, concerns.

Each test skeleton holds one assertion — that the feature document exists — and is
marked `pytest.mark.mutation_inert`. That assertion is the registry anchor and
stays; behaviour tests are added as the feature lands. No skeleton carries a
left-over marker: the generated prose is English and complete, and the open
design questions live in a named section instead of a note in the code.

## Intent surfaces: `--with-intent`

```text
just new-feature FIND-099 core --with-intent NAME --category CATEGORY --mode MODE
```

Without `--with-intent`, the run writes no intent surface and no prompt. With it,
the run writes the eight declaration surfaces of the intent plus one prompt per
locale:

| Surface | File |
|---|---|
| Intent enum member and summary docstring | `packages/core/narrare_core/llm/intents/_enums.py` |
| `INTENT_CATEGORY_MAP` entry | `packages/core/narrare_core/llm/intent_categories.py` |
| `INTENT_PROFILES` entry | `packages/core/narrare_core/llm/intent_profiles.py` |
| `ROUTE_CONFIGS` entry | `packages/core/narrare_core/prompts/route_table.py` |
| `INTENT_TO_CATEGORY` and `INTENT_TO_MODE` entries | `packages/core/narrare_core/prompts/route_table_intents.py` |
| Manifest block | `scripts/architecture/prompt-surface-manifest.yaml` |
| `prompt_path_compliance` entry | `scripts/architecture/adoption-registry.yaml` |
| Prompt files, `en` / `de` / `fr` | `packages/core/narrare_core/prompts/_bundled/<prompt category>/<locale>/<mode>/system.md` |

### Why `--category` and `--mode` are mandatory

Neither flag can be derived, and guessing either produces an intent that is green
in every gate and wrong in the product. The parity gate checks that the surfaces
agree with each other, not that they name the right thing: an invented category
would put the intent in a family nobody asked for, and an invented mode would
write prompts into a route no caller uses. Both remain internally consistent, so
nothing fails until the intent is routed and misbehaves.

The two flags name different facts. `--category` is the model category, which must
be one of the `IntentCategory` values. The prompt-route category is not taken from
it: it is cloned from the first routed sibling in that category, because a model
category and a prompt family are separate (for example, a routed sibling in the
`kb` model category writes `kb` prompts, while other categories route into
`writing`, `analysis` or `planning`). `--mode` is the prompt-mode name and the
directory under each locale.

Missing `--category` or `--mode` exits `2` and names both flags before anything is
read or written. Passing either without `--with-intent` exits `2` for the same
reason. An unknown category exits `2` and lists the categories that exist.

### Clone the sibling, derive only what must be new

For a valid category the scaffolder finds the first routed sibling, copies its
route shape for the enum, category map, profile, route configs and manifest block,
and clones the sibling's own `system.md` as the prompt skeleton:

- **Copied:** frontmatter keys in their order, every section heading in its order,
  and every variable placeholder where the sibling used it — including its XML
  wrapper.
- **Derived:** frontmatter values (`prompt_type`, `prompt_language`,
  `prompt_version`), a localized scope sentence per locale, four intent-agnostic
  `Do NOT` items, and — when the sibling's output section holds a JSON example — a
  minimal `{intent, result, notes}` example for the new intent.

The structure is cloned because it is already encoded in every compliant prompt;
re-deriving it here would be a second source that drifts the moment
`check_prompt_structure.py` changes. A frontmatter key the scaffolder cannot
derive exits `2` and names the key rather than copying the sibling's value or
dropping it.

If any surface already declares the intent, the run exits `1` and writes nothing;
the message lists every surface where the declaration was found. Intent surfaces
that already exist are edited in place, so only newly created prompt files
participate in the duplicate-path check.

## What is deliberately never generated

No service, router, repository, database model, migration, endpoint or frontend
component is ever written. The layer names do not change that: `api` and `web`
produce a test directory, nothing more.

This is RULE-20, and it is the point of the tool. A generated service stub is a
half-implementation that looks like progress and silently asserts behaviour no one
has designed: imports resolve, the app boots, and a route answers while the
feature does not exist. A declaration, by contrast, is complete at birth — the
feature document describes what is planned, the test skeleton names the artifact,
and the Protocol states the boundary first, as RULE-03 requires. Everything that
needs a design decision is authored after that decision, not scaffolded before it.

The same restraint applies to the intent prompt (see below) and to the feature
index: the scaffolder does not edit `docs/features/INDEX.md`. Add the row when the
feature document is written.

## Exit codes and atomicity

| Code | Meaning | Tree state |
|---:|---|---|
| `0` | Every planned file was written and the post-condition passed. | Changed as reported. |
| `1` | The feature id or the intent already exists in a target path or declaration surface. | Untouched. |
| `2` | Invalid input, an unreadable or uncloneable surface, a failed write, or a failed post-condition. | Restored to its pre-run state. |

Exit `2` covers more than gate failures because every refusal on the way to a
write shares the same outcome: nothing new survives. Invalid ids, unsupported
layers, a missing flag, an unknown category, a category with no routed sibling, a
missing sibling template and an underivable frontmatter key are all planning
refusals — they happen before the first write. A failed write and a failed
post-condition happen after it.

Atomicity is by snapshot. Before each write the run records the file's previous
text, or records that it did not exist. If a write or the post-condition fails,
every touched file is restored: edited surfaces get their original bytes back and
files the run created are removed. The run reports how many files it restored. If
a restore itself fails, that is reported separately and the exit code stays `2`;
the failure path never masks the original reason.

## The post-condition

A successful write is not a successful scaffold. Before returning, the run proves
the tree passes the gates that would reject it.

1. **Intent parity gate — always, for every root.** The scaffolder runs the parity
   oracle (`check_intent_parity`) over the tree it just wrote and exits `2` with
   each disagreement if the eight declaration surfaces do not agree. Because the
   oracle takes a root, it works on a mirror tree as well as on this repository.
2. **Four scoped checks — repository root only.** When the root is this
   repository, the run also executes `check_prompt_structure.py`,
   `check_prompt_surface_contract.py`, `check_locale_sync.py` and
   `check_feature_path_accuracy.py`, each with this interpreter and the root as
   working directory. A non-zero exit prints the script name, its exit code and
   the last eight lines of its output, then exits `2`.

The scoped checks are skipped when the root is not the running repository. They
resolve their own paths from the invoked script and only describe this project, so
running them against a mirror would produce a verdict about the wrong tree.
Mirrors still get the parity gate, which is the checks' shared subject.

The result is the promise in one sentence: a scaffold either arrives gate-green or
arrives with a named failure, and a failure leaves the tree exactly as it was.

## Dependencies and what they protect

**The intent parity gate (P2).** This is a direct dependency: the post-condition
imports `collect_facts` and `find_disagreements` from `check_intent_parity`. Without
it there is no post-condition for intent scaffolds, and a generated intent could
land with, say, an enum member that no manifest block and no route config describe
— internally plausible, unroutable in practice, and only caught later at runtime
or at the next commit. The gate itself moves no authority: the manifest and the
adoption registry remain the sources, and the gate only compares.

**The provider catalog (P1).** The scaffolder does not import the catalog and
writes no provider string. The program expected provider-aware feature templates
built from `catalog_generated.PROVIDER_IDS`; no such template exists, so a
provider-touching feature receives the same declaration surfaces as any other
feature and the provider work stays with the author. The catalog remains a
dependency of the surrounding gate: `just check-architecture` includes
`generate_provider_catalog.py --check`, so a stale catalog turns the first full
architecture run after a scaffold red for a reason the scaffolder neither sees nor
can fix. Keep the catalog current before starting a feature.

## The scaffolded prompt is a skeleton, not a finished prompt

A `--with-intent` prompt is structurally complete and green on arrival, and that is
deliberately all it is. The frontmatter, headings and placeholders are cloned and
the scope sentence is real, but a section whose sibling text was its own
instruction arrives without instruction — as a bare heading or as its placeholder
list — and the JSON example is a placeholder. The four `Do NOT` items are generic
on purpose: the sibling's prohibitions describe the sibling's job.

The gates check structure, not meaning. An author who routes real work through an
untouched scaffold gets a prompt that passes every check and gives the model no
useful instruction. Fill the prose — analysis instructions, quality rules and the
output contract — before the intent is used.

## After the scaffold

1. Design the contract first: add the feature's method signatures to
   `contracts.py`, then implement the service and router against it.
2. Replace each scaffold assertion with behaviour tests as the feature lands; keep
   the document-existence test as the registry anchor.
3. Fill the feature document's prose sections and extend its `paths:` list with the
   implementation files.
4. With `--with-intent`, finish the prompt prose and confirm the JSON example
   matches the intent's output contract.
5. Add the row to `docs/features/INDEX.md` when the document is written.
