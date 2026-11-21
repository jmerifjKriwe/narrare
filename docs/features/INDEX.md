# Features — the live inventory

One page for every feature Narrare will have, and the one question that matters about
each: **does it exist today, and if not, what is missing?**

- The **order** in which the gaps close is [`roadmap.md`](../../roadmap.md).
- The **v1 detail** behind a name (user stories, acceptance criteria, old code paths)
  is in [`docs/archive/v1/features/`](../archive/v1/features/INDEX.md).
- The **decision** that put a feature on the later pile is
  [`feature-triage.md`](../superpowers/feature-triage.md), taken per area on
  2026-10-31.

This page replaces the v1 registry as the working inventory. It describes the
product, not the code: no service names, no router paths. State is checked against
the tree — a row is `live` only when a surface, its backend and an end-to-end test
exist.

## States

| State | Meaning |
|---|---|
| `live` | Surface, backend and E2E are in the tree |
| `building` | An open branch or PR carries the surface |
| `backend` | The API serves it; no surface offers it |
| `designed` | A Stitch draft exists; no backend, no build decision yet |
| `idea` | Named and registered; no draft |
| `later` | Decided against for now, with the condition that reopens it |

## Phases

| Phase | What it is |
|---|---|
| `0` | The rebuild's last tasks and the record itself |
| `1` | The rebuild's missing surfaces — the backend is already there |
| `2` | The contracts that unlock whole feature families |
| `3` | The feature waves |
| `4` | Release hardening |
| `later` | Not planned; the condition is in the last table |

`designed` does not mean approved, and a draft never decides scope: every area gets
its verdict before a wave opens. Where "Stitch alone designs" applies, a feature with
no draft cannot be built before one exists — the list of those drafts is in the
roadmap's design-debt section.

---

## Library and entry

| Feature | What it is | State | Phase |
|---|---|---|---|
| Shelf as home | Every novel as a card: cover, progress, last edited; search and filter | `live` | `0` |
| Welcome and setup | Four steps: starting point, dramatic structure, AI rules, provisioning | `live` | `0` |
| Demo novels | A populated example novel to explore instead of a blank page | `live` | `0` |
| New-book dialog | Title, genre, cover, series link, in one dialog | `live` | `0` |
| Onboarding tour (ONBOARD-001) | A guided tour of the AI surfaces for a first-time writer | `designed` | `3` |
| Start from a manuscript (SETUP-003) | Import an existing book instead of starting blank | `designed` | `3` |

## Writing

| Feature | What it is | State | Phase |
|---|---|---|---|
| Editor with autosave | Scene-centric prose editor; nothing is lost, nothing is asked | `live` | `0` |
| Chapter and scene tree | Reorder, split and navigate the manuscript | `live` | `0` |
| AI continuation (WRITE-003) | A draft continues at the caret, streamed into the text | `live` | `0` |
| Instruction on continuation | A short directive on the next continuation (tension, dialogue, detail) | `live` | `0` |
| Zen focus | The draft alone, chrome and dock gone | `live` | `0` |
| Book settings | Genre, target length, series link, per-book AI rules | `live` | `0` |
| Daily goal and progress | A word target per day and its honest progress | `live` | `0` |
| Rewrite selection (WRITE-004) | Rewrite a passage in a named tone, accept or discard | `idea` | `2` |
| Draft variants (WRITE-008) | Two to five drafts of one passage, compared side by side | `later` | `later` |
| Inline suggestions (WRITE-007) | Ghost text that completes the sentence as you type | `idea` | `3` |
| New chapter from outline (WRITE-002) | A first draft from a premise or outline | `idea` | `3` |
| Co-author mode (WRITE-006) | A session that proposes changes as diffs, accepted per hunk | `idea` | `3` |
| Writer's unblock (WRITE-009) | Three to five directions when the scene will not move | `idea` | `3` |
| Voice check (WRITE-010) | Dialogue checked against a character's voice profile | `idea` | `3` |
| Chapter summary (WRITE-012) | A summary per chapter, for context and review | `idea` | `3` |
| Context inspector (WRITE-014) | What the model sees right now: context, sources, budget | `idea` | `3` |
| Title suggestions (ASSIST-002) | A list of titles for a novel, chapter or scene | `idea` | `2` |
| Name generator (GEN-001) | Culturally aware, deduplicated names for people and places | `idea` | `2` |
| Volumes (WRITE-011) | Several volumes in one project, shared canon | `designed` | `3` |
| Writing workflows (WRITE-013) | Multi-step runs driven from the palette | `later` | `later` |

## Knowledge

| Feature | What it is | State | Phase |
|---|---|---|---|
| Entities and relations (KB-001) | The world as typed entries with typed links | `live` | `0` |
| Extraction review (KB-007) | Facts proposed from a chapter, accepted or discarded | `live` | `0` |
| Consistency check (CONS-001) | A novel-wide job that names contradictions as findings | `live` | `0` |
| Merge duplicates (KB-009) | Two entries folded into one, relations kept | `live` | `0` |
| Lore graph (KB-008) | The world as a navigable graph in the browser | `live` | `0` |
| Dossiers | Character and place pages with their relations and sources | `live` | `0` |
| Sources archive | Uploaded documents, chunked and searchable | `live` | `0` |
| Create an entity by hand | The graph's door; needs the create endpoint (Phase 1) | `designed` | `1` |
| Psychological profile | Want, need and lie per character, as dossier fields | `designed` | `2` |
| Linguistic profile | How a character speaks, as dossier fields | `designed` | `2` |
| Worldbuilding atlas (KB-006) | Geography and cultures as their own surface | `designed` | `3` |
| Assisted creation (KB-002) | An interview that turns answers into entries | `idea` | `3` |
| Improve an entry (KB-003) | Fill the gaps in an existing entry | `idea` | `3` |
| Proactive suggestions (KB-005) | Entries offered while writing, not only on extraction | `idea` | `3` |
| Journey back to the manuscript | Which scene mentions this entry, and a door to it | `idea` | `3` |
| Original-document view | Read the page a source passage came from | `designed` | `2` |
| Re-embed door | The one action the mismatch face still owes | `backend` | `1` |

## Planning

| Feature | What it is | State | Phase |
|---|---|---|---|
| Chronology (PLAN-004) | Events on a timeline, linked to chapters | `building` | `0` |
| Storyboard (PLAN-005) | Chapters in stages, five structures, remap, scene drill-in | `building` | `0` |
| Causality strip | Each scene's conflict and resolution as a chain | `building` | `0` |
| Scene planning (PLAN-001) | Goal, conflict, resolution and beats per scene, before writing | `live` | `0` |
| Structure view (PLAN-003) | Acts and their share of the book, read from the storyboard | `building` | `0` |
| Narrative gap analysis (PLAN-002) | Missing transitions, dropped threads, unused entities | `idea` | `3` |
| Character arc (PLAN-006) | A character's development in phases, against the plan | `idea` | `3` |
| AI scene drafts | A scene breakdown proposed from chapter and canon | `idea` | `3` |

## Chat and dialogue

| Feature | What it is | State | Phase |
|---|---|---|---|
| Sourced answer (CHAT-001) | One question, answered from the manuscript, with its passages | `backend` | `1` |
| Entity interview (KB-002) | A guided conversation that proposes an entity, reviewed before saving | `designed` | `1` |
| Conversation with history | A running exchange that survives a reload, with stop and regenerate | `designed` | `1` |
| Chat in the workspace | The dock next to the prose, with the passages it used, and insert or replace | `designed` | `1` |
| Entity sparring | Talk to a character, in their voice, about the scene | `designed` | `3` |
| Dialogue coach (ASSIST-004) | A session that sharpens subtext and flow in dialogue | `idea` | `3` |

## Analysis and feedback

| Feature | What it is | State | Phase |
|---|---|---|---|
| Beta reader (ANAL-001) | A reader's report on the whole book, on demand | `designed` | `3` |
| Subtext and scene analysis | What a scene says under the surface | `designed` | `3` |
| Dialogue voice lab | A character simulator to test how they sound | `designed` | `3` |
| Writing analytics | Productivity and rhythm over time | `designed` | `3` |
| Sentiment and emotional curve (ANAL-002) | The emotional arc made visible | `idea` | `3` |
| Readability (ANAL-003) | Complexity measured, with suggestions | `idea` | `3` |
| POV analysis (ANAL-004) | Head-hopping and knowledge leakage | `idea` | `3` |
| Coreference (ANAL-005) | Ambiguous pronouns, found | `idea` | `3` |
| Author voice (ANAL-007) | A profile of how this author writes | `idea` | `3` |
| Character voice (ANAL-008) | A profile per character | `idea` | `3` |
| Voice drift (ANAL-009) | Where a voice changes across chapters | `idea` | `3` |
| Analysis hub and dock | One home for every report | `designed` | `3` |
| Sensitivity review (ANAL-006) | Stereotypes and tropes flagged | `later` | `later` |
| Literary suite (ANAL-010) | Several analyses as one report | `later` | `later` |

## Editing and revision

| Feature | What it is | State | Phase |
|---|---|---|---|
| Revision history | The time machine: old versions of a scene, side by side | `designed` | `3` |
| Editorial comments | Comments anchored to a passage, with a resolution state | `designed` | `3` |

## Import and export

| Feature | What it is | State | Phase |
|---|---|---|---|
| Import a Narrare archive | Move a project between instances, conflicts reported | `backend` | `3` |
| Export a manuscript | Markdown into a server-side path today | `backend` | `3` |
| Import DOCX, Scrivener, ePub | Bring an existing manuscript in, structure intact | `designed` | `3` |
| Export PDF, ePub, DOCX (IO-001) | A finished file, downloaded from the browser | `designed` | `3` |
| Typesetting studio | Trim size, fonts, front matter, preview | `designed` | `3` |
| Corpus pass (IO-002) | Extract the canon from an imported manuscript in one run | `designed` | `3` |
| Audio dictation | Speak a scene, get prose and lore | `designed` | `later` |

## Production and publishing

| Feature | What it is | State | Phase |
|---|---|---|---|
| Procedural covers | A cover drawn from title and genre, no image needed | `live` | `0` |
| Cover, blurb and marketing | The selling surface of a finished book | `designed` | `3` |
| Exposé and pitch | The book pitched to agents and publishers | `designed` | `3` |
| Agency submissions | Track who has what, and when | `designed` | `3` |
| Series (SERIES-001…004) | Volumes as one work: shared canon, voice, drift check | `designed` | `3` |

## Settings, prompts and shell

| Feature | What it is | State | Phase |
|---|---|---|---|
| Settings screen (SET-001) | The hub the gear opens: providers, models, tasks, theme | `backend` | `1` |
| Provider profiles and presets | Several endpoints, keys in the OS keychain or encrypted | `backend` | `1` |
| Per-task model (SET-003) | Each task pointed at its own model | `backend` | `1` |
| Theme and language | Light, dark or system; three languages, du or Sie | `live` | `0` |
| Prompt overrides (PROMPT-001/002) | Every prompt editable, with a diff against the shipped one | `backend` | `1` |
| Prompt variables and preview (PROMPT-003) | See what a prompt renders before it runs | `designed` | `1` |
| Command palette (⌘K) | Every action by name, from anywhere | `designed` | `1` |
| Help centre | The manual inside the app, per surface | `designed` | `1` |
| Shortcut remapping (SET-004) | Bind keys to actions, with conflict resolution | `later` | `later` |

## Analytics and cost

| Feature | What it is | State | Phase |
|---|---|---|---|
| Writing activity (STATS-001) | Words per day, streaks, against the goal | `backend` | `1` |
| AI cost and usage (STATS-002) | What the model calls cost, per task and model | `idea` | `2` |

## Mobile and sync

| Feature | What it is | State | Phase |
|---|---|---|---|
| Pocket quick capture | Capture a line or a scene note from the phone | `designed` | `3` |
| External sync (IO-003) | Two-way sync with a folder | `later` | `later` |

---

## Decided not now

A `later` row is a decision, not a backlog item: it returns only when the named
condition is true.

| Feature | Verdict | Reopens when |
|---|---|---|
| Draft variants (WRITE-008) | later | A diff/accept contract exists and one continuation proves too narrow |
| Writing workflows (WRITE-013) | later | The palette exists and three runs repeat the same sequence |
| Sensitivity review (ANAL-006) | later | The analysis family has shipped and the question of sensitive content is asked by a user |
| Literary suite (ANAL-010), plot suite (ANAL-011) | later | At least three single analyses are live |
| Learning loop (LEARN-001/002) | later | Accept/reject is recorded across features and someone asks for adaptivity |
| Shortcut remapping (SET-004) | later | One dispatcher serves every listener site |
| External sync (IO-003) | later | Import and export are stable and a second device is in use |
| LLM wiki (WIKI-001) | later | Context assembly provably costs too many tokens |
| Editor graph (KB-010) | later | The lore graph has a neighbourhood lens on the canvas |
| MCP and A2A adapters | not planned | An external agent drives Narrare as a product requirement |
| Audio dictation | undecided | A verdict on scope: the draft exists, but v1 never registered it |
