# Narrare — Project Vision

> **This document answers: What is Narrare? Why does it exist? For whom?**
> It is the foundation that every agent and developer reads first.
> It is not a feature list. It is a statement of intent.
>
> Location: `docs/agents/_shared/PROJECT_VISION.md`
> Maintained by: Architecture Agent (structure) + project owner (vision)

---

## The One-Sentence Version

Narrare is an AI-assisted writing environment that helps authors write better
stories — without replacing the author.

---

## The Problem We're Solving

Writing a novel is an act of sustained creative will across months or years.
The challenge is not a lack of ideas — most writers have more ideas than they
can use. The challenges are:

**Cognitive overhead.**
Keeping track of 30 characters, their relationships, their histories, their
contradictions. Remembering that the tavern was on the east side of the city
in chapter 2 but somehow on the west side in chapter 14. Knowing whether the
protagonist's voice in the new chapter sounds like the same person from
chapter 1.

**The blank page.**
Getting unstuck. Finding the next sentence when the last sentence stopped
making sense. Knowing whether a scene is working or just feels like it is.

**The loneliness.**
Most writers write alone. A writing partner who has read everything you've
written, remembers it all, and can give honest feedback at 2am does not exist.

Current AI tools solve none of these well. They either:
- Generate content for you (replacing, not assisting)
- Require you to paste context manually every session (no memory)
- Offer generic feedback that ignores your specific story (no context)
- Break your flow with clunky interfaces (bad UX)

---

## What Narrare Is

Narrare is a **writing environment**, not a writing tool.

The distinction matters. A tool does something for you. An environment is a
space you inhabit — it knows your world, your history, your style. It is
available when you need it and invisible when you don't.

Concretely, Narrare provides:

### A Knowledge Base that remembers your world
Every character, location, faction, object, and concept in your story lives in
the Knowledge Base. The KB is not a static database — it is a living document
that the AI helps you build through conversation, and that the AI reads before
every interaction with your text.

### A writing context that spans your entire manuscript
Before generating or analyzing anything, Narrare assembles a context bundle:
relevant KB entries, recent chapter summaries, your style profile, your
established narrative voice. The AI never works blind.

### An editor that assists without interrupting
Inline suggestions, voice checks, plot consistency analysis — all available
on demand, never pushed at you. The editor surface is for writing.
AI assistance is one keystroke away, not in your face.

### A feedback layer that knows your story
Beta reader simulation, POV analysis, readability scoring, sensitivity review —
all in the context of your specific manuscript, not generic writing advice.

### A planning layer that holds your structure
Scene planning, plot gap analysis, timeline tracking, act structure visualization.
The plan and the manuscript stay in sync.

---

## What Narrare Is Not

**Not an AI that writes your book.**
Narrare generates when you ask it to generate. It does not auto-complete your
sentences. It does not suggest what happens next unless you explicitly ask.
The story is yours. The AI is a collaborator, not an author.

**Not a cloud service that owns your data.**
Narrare runs locally. Your manuscript, your KB, your prompts — all on your machine.
AI calls go to the provider of your choice, but your data does not live on our servers.

**Not a one-size-fits-all tool.**
Prompts are customizable at every level: per-project, per-user, per-feature.
Model selection is configurable per task type. The writing persona is yours to define.

---

## Who Narrare Is For

### Primary: The serious hobby or independent author
Someone who is writing a novel (or has tried to). Who has a story they care about.
Who is not a professional author with an editor and an agent, but who takes their
writing seriously. Who has given up on AI writing tools because they felt generic.

### Secondary: The professional author who wants a private AI writing partner
Someone who already knows how to write, but wants the cognitive overhead reduced.
Who wants consistency checking, not generation. Who wants feedback at 2am, not
at the next editorial meeting.

### Not: The casual user who wants AI to write a story for them
Narrare is not the right tool for "write me a story about dragons."
The prompts, the KB, the context system — all of this is overkill for that use case.
And that use case is well-served by existing tools.

---

## The Knowledge Base — Core to Everything

The Knowledge Base (KB) is not a feature. It is the foundation of Narrare's value.

Without the KB, Narrare is just another LLM wrapper. With the KB, Narrare has
something no other writing tool has: **persistent, structured knowledge of your
specific story world** that is automatically assembled into context for every
AI operation.

Every character the AI writes for you — it has read the character's KB entry.
Every consistency check — it compares against the KB.
Every plot suggestion — it knows the existing storylines from the KB.

The KB has three layers:

**1. Structured entities** (explicitly managed by the author)
Characters, locations, factions, objects, systems, languages, timelines.
Each entity has a type-specific template, a status (draft/reviewed/canon/deprecated),
and optional relationships to other entities.

**2. The Knowledge Graph** (automatically maintained)
Facts extracted from chapters and KB entries. Nodes are entities, edges are
relationships. Used for consistency checking — if chapter 15 contradicts a
fact established in chapter 3, the Knowledge Graph knows.

**3. Memory** (accumulated across sessions)
Writing preferences, rejected suggestions, style patterns, feedback themes.
Managed via mem0. Persists across sessions. Makes each session smarter than the last.

---

## The Interface Strategy

### Phase 1 (current): WebUI
A browser-based writing environment. Full-featured. This is the primary interface.
All features are built here first.

### Phase 2 (planned): MCP
Narrare as a set of tools for AI coding assistants and agent frameworks.
Allows external agents to read/write the KB, query the manuscript, run analyses.
Same Service Layer as WebUI — new transport adapter only.

### Phase 3 (planned): A2A
Narrare as an agent that other agents can collaborate with.
A research agent finds information; a Narrare agent integrates it into the KB.

### Phase 4 (possible): CLI
A command-line interface for writers who prefer terminal workflows.
Same Service Layer. Different transport.

The architecture is designed so that Phases 2–4 add adapters, not new services.

---

## Design Principles

**1. The writer's flow is sacred.**
If a UI element interrupts writing unnecessarily, it is wrong.
Every notification, suggestion, and analysis should be available on demand —
not pushed.

**2. Local first.**
The manuscript is on your machine. The KB is on your machine.
AI calls go to your chosen provider. Nothing is on our servers.

**3. Customizable at every level.**
Prompts, models, templates, personas — all customizable.
The defaults should be excellent. The overrides should be easy.

**4. Transparent AI.**
The author always knows when AI is involved.
There is no "AI writes in the background without telling you."
Every AI action is explicit and undoable.

**5. Graceful degradation.**
If the AI provider is down, the editor still works.
If mem0 is unavailable, the session still runs (without memory).
If the KB is empty, writing still works (without context).

---

## The Name

*Narrare* — Latin, "to tell, to narrate."

The root of "narrative," "narrator," "narration."
A writing tool should be named for what writers do.

---

> Last updated: project initialization
> Author: project owner
> This document changes only when the vision changes — not on every feature addition
