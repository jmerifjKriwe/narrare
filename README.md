# Narrare

[![CI](https://github.com/jmerifjKriwe/narrare/actions/workflows/ci.yml/badge.svg)](https://github.com/jmerifjKriwe/narrare/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.14+](https://img.shields.io/badge/Python-3.14%2B-blue.svg)](https://www.python.org/downloads/)
[![Code style: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

> Local-first, AI-assisted creative writing.

Four capabilities, one folder each under `app/capabilities/`: writing (novel, chapter,
editor, continuation), knowledge (upload, chunk, embed, search), chat (question over
the knowledge base, streamed answer with sources) and setup (first run). Shared domain
lives in `app/kernel/`; the web app is `web/`.

## Requirements

- [Python 3.14+](https://www.python.org/downloads/) and [uv](https://docs.astral.sh/uv/)
- [Node.js 22+](https://nodejs.org/) and [pnpm](https://pnpm.io/)
- [Docker](https://docs.docker.com/get-docker/) with Compose (Postgres + pgvector)
- [just](https://just.systems/)

## Quick start

```bash
just dev-setup     # python env, web deps, git hooks, Postgres, schema
just dev           # API on :8000, web on :3100
```

Open <http://localhost:3100>. A fresh database lands on `/setup`.

## Commands

`just --list` shows all 22. The ones used daily:

```bash
just check              # fast gate: ruff + pyright
just test               # every integration test
just test-file <path>   # one file or one node
just test-e2e           # capability E2E: browser, API, Postgres
just test-frontend      # web unit tests
just verify             # check + all suites + web build
just build              # production build of the web app
just dev-services       # Postgres on :5432 (dev) and :5433 (tests)
just db-init            # create the schema directly from the models
just db-reset           # drop and rebuild the dev database
just db-shell           # psql on the dev database
just generate           # write the OpenAPI document (no consumer yet)
just new-capability x   # scaffold the test fixtures for a new capability
```

## Structure

```
app/
├── api/            ← FastAPI app, mounts the capability routers
├── capabilities/   ← one folder per capability: router, service, repository, tests, e2e
└── kernel/         ← contracts, db, auth, llm and embedding boundaries, retrieval, testing
web/                ← Next.js app
i18n/               ← en, de, fr; typing makes a missing key a build error
docs/               ← the design record
```

The authority for structure and boundaries is
[`docs/superpowers/specs/2026-10-21-narrare-v2-architecture-design.md`](docs/superpowers/specs/2026-10-21-narrare-v2-architecture-design.md).

## Testing

A capability is done only with a green E2E that drives the real browser, the real API
and the real Postgres. The only fake is the provider at its boundary, and it is a
catalog entry chosen by configuration (`NARRE_LLM_PROVIDER`, `NARRE_EMBEDDING_PROVIDER`),
not a test branch.

`fake` is the default and needs no key. Setting `NARRE_LLM_PROVIDER=openai-compatible`
switches generations to a real model through one fetch strategy for the chat
completions SSE shape — OpenAI, OpenRouter, DeepSeek, Groq and local servers (Ollama,
llama.cpp, vLLM) all speak it, so `NARRE_LLM_BASE_URL`, `NARRE_LLM_MODEL` and
`NARRE_LLM_API_KEY` are all that change. `NARRE_EMBEDDING_PROVIDER=openai-compatible`
does the same for retrieval through the `/embeddings` JSON shape; the vendor must return
vectors of the schema width (the strategy asks for it and refuses another answer).
Startup logs which providers serve and refuses to start on a half-configured one.

The integration suites share `narrare_v2_test`; each E2E capability owns a database and
a module-scoped stack, so `just test-e2e` runs suites one after another on the same
ports.

## License

MIT
