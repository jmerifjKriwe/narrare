# Narrare

[![CI](https://github.com/jmerifjKriwe/narrare/actions/workflows/ci.yml/badge.svg)](https://github.com/jmerifjKriwe/narrare/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.14+](https://img.shields.io/badge/Python-3.14%2B-blue.svg)](https://www.python.org/downloads/)
[![Code style: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

> Local-first, AI-assisted creative writing.

Narrare is a writing environment for novels that runs entirely on your machine.
Write in a focused editor, ask your own reference material questions and get
streamed answers with sources, and continue a chapter with any OpenAI-compatible
model — cloud or local.

<!-- TODO(screenshot): replace with a real app capture once the UI rework lands. -->

## Why Narrare

Narrare exists so that a writer's body of work stays theirs: the manuscripts,
the reference material behind them and the tools that touch them. It treats
novels as a body of work, not a single file — several novels, chapters under
each, and novels that belong together in a series.

There is no account and no cloud: it is your install, your Postgres, your
machine, and the model is your choice — a hosted endpoint or one you run
yourself. Nothing leaves the machine but what you send to the model.

## Features

- **Novels, not files** — writing works the way books do: several novels,
  chapters under each, a focused editor, and continuations generated from your
  own text.
- **A knowledge base that is yours** — upload plain-text reference material and
  it is chunked, embedded and searched in your own Postgres.
- **Answers with receipts** — chat over the knowledge base, streamed, every
  answer citing its sources.
- **A first run that ends with your first novel** — enter a title and start
  writing; there is no account to create.
- **Local-first** — your data lives in your own Postgres (`pgvector` included)
  on your machine; nothing leaves it but what you send to your model.
- **Bring your own model** — any OpenAI-compatible endpoint: OpenAI, OpenRouter,
  DeepSeek, Groq, or fully local through Ollama, llama.cpp or vLLM. The same
  three settings drive text and embeddings, and a model switch re-embeds the
  corpus in one click.
- **English, Deutsch, français** — the UI speaks all three; a missing
  translation is a build error, not a quiet fallback.

## Status

Pre-1.0 and moving: the writing surface keeps growing, more import formats and
series support are on the way, and every capability is proven by an end-to-end
test that drives the real browser, API and database.

## Quick start

[Python 3.14+](https://www.python.org/downloads/) with [uv](https://docs.astral.sh/uv/),
[Node.js 22+](https://nodejs.org/) with [pnpm](https://pnpm.io/),
[Docker](https://docs.docker.com/get-docker/) with Compose and
[just](https://just.systems/):

```bash
just dev-setup     # python env, web deps, git hooks, Postgres, schema
just dev           # API on :8000, web on :3100
```

Open <http://localhost:3100>. A fresh database lands on `/setup`, and the
default provider needs no key.

The daily workflow — branches, commits, PRs, gates — lives in
[CONTRIBUTING.md](CONTRIBUTING.md).

## Where to look next

- [CONTRIBUTING.md](CONTRIBUTING.md) — getting started, branch model, PR process
- [AGENTS.md](AGENTS.md) — the rules of the codebase and the agent layer
- [v2 architecture spec](docs/superpowers/specs/2026-10-21-narrare-v2-architecture-design.md)
  — the authority for structure and boundaries
- [docs/user/INDEX.md](docs/user/INDEX.md) — the app's surfaces, generated from
  the capability facts
