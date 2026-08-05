---
# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary: the serious hobby or independent author — someone writing a novel (or
has tried to), with a story they care about, who is not a professional author
with an editor and an agent, but who takes their writing seriously and has
given up on AI writing tools because they felt generic.

Secondary: the professional author who wants a private AI writing partner —
someone who already knows how to write but wants the cognitive overhead
reduced: consistency checking, not generation; feedback at 2am, not at the
next editorial meeting.

Not for: the casual user who wants AI to write a story for them. That use
case is explicitly out of scope.

## Product Purpose

Narrare is an AI-assisted writing environment that helps authors write better
stories — without replacing the author. It exists to sustain the act of
writing a novel across months or years by reducing cognitive overhead
(tracking characters, locations, timelines, contradictions), beating the
blank page, and providing a writing partner who has read everything and
remembers it all.

Success means the author keeps full authorship and control while writing
better, more consistent prose with less friction.

## Positioning

Narrare is a writing environment, not a writing tool. Its meaningfully
different mechanism: persistent, structured knowledge of the author's
specific story world (the Knowledge Base), automatically assembled into
context for every AI operation. Without the KB, Narrare is just another LLM
wrapper; with it, no other writing tool has persistent knowledge of your
story that is automatically read before every interaction with your text.

Core claims a neighboring product could not truthfully copy:

- The AI is a collaborator, not an author — it generates only when asked.
- The manuscript, KB, and prompts live on the user's machine; AI calls go
  to the provider of the user's choice; nothing lives on Narrare's servers.
- Customizable at every level: prompts, models, templates, personas.

## Operating Context

Phase 1 interface is a browser-based WebUI (Next.js) — this is the primary
interface; all features are built here first. Phases 2–4 (MCP adapter, A2A
adapter, CLI) are planned as transport adapters over the same service layer,
not new services.

The author works inside a full-featured writing editor: left sidebar with
chapter list, main editor surface (TipTap/ProseMirror), right context panel,
toolbar with AI action slots, keyboard-accessible command palette (Cmd+K),
focus mode, live word count, autosave.

Established workflows: 5-step setup wizard (project name, language, novel
metadata, starter content, AI provider + API key validation); demo content
loadable in 3 languages; knowledge base entity management (template-driven
editor, @mention autocomplete, tag input, relationships); storyboard planning
with drag-and-drop and structure adapters; feedback recording with a learned
preference profile; AI chapter generation with streaming.

The writing pipeline supports four modes: full draft, scene by scene,
interview, interactive. AI actions are explicit and undoable; the editor
keeps working (with degraded capabilities) when the AI provider, memory
layer, or KB is unavailable.

## Capabilities and Constraints

Confirmed functionality (MVP Phases 0–5 complete; Phase 6 "Writing
Intelligence" in progress):

- Writing editor: TipTap v3 with custom extensions (NarrareDocument,
  SceneBreak, DialogueMark, Autosave), chapter-scoped documents, autosave,
  word count/reading time, focus mode.
- AI writing pipeline: 4 modes, SSE streaming, WebSocket sessions,
  6-step WritingGraph (plan → write → review → finalize → summary),
  5 structure adapters, context assembly with 5-tier ranking + token budgets.
- LLM gateway with 7 providers + model registry; embedding cascade
  (4-tier: OpenAI → local → disabled).
- Knowledge base: 8 entity types, template-driven entries, cross-references,
  relationships, status workflow (draft/reviewed/canon/deprecated).
- Planning: storyboard with drag-and-drop, outlines, sync status, AI remap.
- Learning: feedback recording, preference profile, mem0 memory layer.
- Settings: AI providers, model routing, token limits, project AI settings,
  9 bundled tones (contemplative, dark, adventurous, romantic + 5 more) with
  custom tone CRUD.
- Auth: JWT access token in memory, refresh token in httpOnly cookie.
- i18n: en/de/fr via next-intl; zero hardcoded English in components.
- Light and dark mode; design tokens as CSS variables (Tailwind).
- Demo content: "Echoes of the Thornwall" (EN, Fantasy), "Dead Signal" (EN,
  SciFi), "Im stillen Wald" (DE, Fantasy).

Constraints:

- The story is the author's; the AI never auto-completes sentences or
  suggests what happens next unasked.
- Local first: data is not stored on Narrare servers.
- Graceful degradation is required: editor works without AI provider, mem0,
  or KB content.
- Explicitly undecided: brand voice / visual identity — no binding
  commitments exist yet; voice development is future work.

## Brand Commitments

Name: Narrare — Latin, "to tell, to narrate"; root of "narrative",
"narrator", "narration." Confirmed and binding.

No other binding brand commitments (voice, tone, assets, personality,
visual identity) are established yet. The owner signaled that developing a
fitting voice/identity is desirable future work — it is not a current
constraint and must not be assumed.

## Evidence on Hand

- docs/reference/project-vision.md — vision, user segments, design
  principles, interface strategy.
- docs/mvp/mvp-plan.md — roadmap, feature inventory, architecture
  decisions, tech stack.
- Demo content with real manuscript material in 3 languages (see
  apps/api/scripts/demo_data/).
- Dev credentials flow documented for local evaluation
  (dev@narrare.dev).

Absences that must not be fabricated: no testimonials, no customer case
studies, no pricing, no benchmark claims, no deployment/service claims.

## Product Principles

1. The writer's flow is sacred. Assistance is available on demand and never
   pushed; an element that interrupts writing unnecessarily is wrong.
2. Local first. The manuscript, KB, and prompts are on the user's machine;
   AI calls go to the user's chosen provider.
3. Customizable at every level. Prompts, models, templates, personas are
   all customizable; defaults should be excellent, overrides easy.
4. Transparent AI. The author always knows when AI is involved; every AI
   action is explicit and undoable.
5. Graceful degradation. The editor still works when the AI provider, memory
   layer, or KB is unavailable.

## Accessibility & Inclusion

WCAG 2.1 AA is a required standard for the web UI. No additional
product-specific user needs were established at init time.
---
