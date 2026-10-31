# Narrare

[![CI](https://github.com/jmerifjKriwe/narrare/actions/workflows/ci.yml/badge.svg)](https://github.com/jmerifjKriwe/narrare/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.14+](https://img.shields.io/badge/Python-3.14%2B-blue.svg)](https://www.python.org/downloads/)
[![Code style: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![codecov](https://codecov.io/gh/jmerifjKriwe/narrare/branch/main/graph/badge.svg)](https://codecov.io/gh/jmerifjKriwe/narrare)

<img src="assets/logo/lockup.svg" alt="" width="180" />

> Local-first, AI-assisted creative writing. Bring your own model — cloud or local.

Narrare is a writing environment for novels that runs on your machine. A shelf of
books, a chapter in a quiet editor, your own notes as a knowledge base, and a model
you choose that continues a scene, answers questions about your story and points at
the contradictions you left behind.

## What you do with it

- **Write the book.** Several novels on one shelf, chapters in a rail beside the
  editor, autosave after every pause, and a focus mode (`F9`) that puts everything
  but the page away.
- **Ask for a continuation, not a rewrite.** "Continue writing" streams a suggestion
  where the cursor stands. It stays ghost text until you press Tab — a stream that
  dies never drops half a sentence into your manuscript. Esc discards it.
- **Make your notes searchable.** Upload plain-text reference material — a story
  bible, a timeline, the research you keep re-reading. It is chunked, embedded and
  searched in your own Postgres, and a model switch re-embeds it from the page where
  you uploaded it.
- **Ask your own material, and see where the answer came from.** Chat streams an
  answer and lists the sources it used underneath. In the workspace the same panel
  opens beside the chapter you are writing in.
- **Let it find the cast and the contradictions.** Extraction proposes entities from
  a chapter as a review queue — accept or discard each — and the entries it creates
  can be edited and merged. The whole-book check reports contradictions to
  acknowledge or dismiss.
- **English, Deutsch, français** — the interface speaks all three, and a missing
  translation is a build error rather than a quiet fallback.

## Why local

The manuscripts, the chapters, the notes and the embeddings live in your own Postgres
with `pgvector`, on your disk. There is no account and no cloud: one local user, one
database, one machine. The model is yours to pick — any OpenAI-compatible endpoint,
from OpenAI, OpenRouter, DeepSeek or Groq to Ollama, llama.cpp or vLLM on localhost,
where the key is nothing at all. Nothing leaves the machine but what you send to a
model.

## Getting started

Narrare runs from source today. There is no installer and no image yet; until there
is, a first run needs the toolchain below and two commands.

You need [Python 3.14+](https://www.python.org/downloads/) with
[uv](https://docs.astral.sh/uv/), [Node.js 22+](https://nodejs.org/) with
[pnpm](https://pnpm.io/), [Docker](https://docs.docker.com/get-docker/) with Compose
and [just](https://just.systems/):

```bash
just dev-setup     # python env, web deps, git hooks, Postgres, schema
just dev           # API on :8000, web on :3100
```

Open <http://localhost:3100>. A fresh database lands on the setup page: enter a title
and the book opens in the workspace — the first chapter is one click away. There is
nothing to configure first: the default provider is a deterministic stand-in, so a
first run needs no key and no `.env`. To write with a real model, copy `.env.example`
to `.env` and point it at an endpoint; provider settings inside the app are planned.

The daily workflow — branches, commits, pull requests, the full gate — lives in
[CONTRIBUTING.md](CONTRIBUTING.md).

## Status

Pre-1.0 and moving. The foundation is in place, and three gaps are named here rather
than discovered later: the model is configured in `.env` because there is no settings
page yet, a manuscript cannot be exported or imported yet, and series do not exist.
Next on the list are relations between entities, provider settings in the app, and
export with import.

What *is* built is proven the expensive way: every capability carries an end-to-end
test that drives a real browser against the real API and a real Postgres, and the only
fake in the system is the model at its boundary.

## Where to look next

- [CONTRIBUTING.md](CONTRIBUTING.md) — getting started, branch model, PR process
- [SECURITY.md](SECURITY.md) — the supported version and how to report a vulnerability
- [AGENTS.md](AGENTS.md) — the rules of the codebase and the agent layer
- [v2 architecture spec](docs/superpowers/specs/2026-10-21-narrare-v2-architecture-design.md)
  — the authority for structure and boundaries
- [docs/user/INDEX.md](docs/user/INDEX.md) — the app's surfaces, generated from the
  capability facts
