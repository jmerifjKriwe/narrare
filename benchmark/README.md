# KB Benchmark Runner — Runbook

Manually-only tooling (ADR-083). This directory is **never** built or run by CI:
no CI job, pre-commit gate, coverage baseline, or adoption check touches
`benchmark/`. Tests run by hand (`uv run pytest benchmark/tests/ -q`); a guard
test in the repo test tree asserts that the root pytest config never collects
this tree.

## 1. Purpose

The runner is a deterministic Python program that measures how well Narrare's
Knowledge-Base capabilities actually work end to end. One run spins up its own
throwaway Narrare stack (docker compose), provisions a benchmark user and LLM
config through the normal setup path, ingests the German benchmark corpus
(the `clean` corpus or an error variant), drives the capability surface via the
production REST/SSE API exactly as the UI would, scores the results against the
reference and error registries, writes a standardized artifact tree — and tears
the stack down residue-free. Design rationale and scope:
`docs/architecture/decisions/ADR-083-kb-infrastructure-benchmark-program.md`;
measurement and runner design: the instrument spec §5–§6
(`docs/superpowers/specs/2026-08-20-kb-benchmark-instrument-design.md`).

Two properties matter when operating it. First, it is **production-surface
only**: the runner speaks HTTP to the API and imports no Narrare code, so it
survives internal refactors. Second, it is **honest about what it could not
measure**: capabilities that are structurally impossible for the corpus
(e.g. series-scoped checks) are reported as `SKIPPED(structural)` rows in the
artifacts, never silently omitted or fabricated.

## 2. Prerequisites

- **Docker** with **Docker Compose v2.24+** (both stack modes inject the
  selected host port through a generated compose override file using the
  `ports: !override` tag — replaces the file's fixed port mapping instead of
  merging with it; a Compose v2.24+ feature). Check yours:
  `docker compose version`. **Stack mode** (`stack.mode`):
  - `hybrid` (DEFAULT): only the `postgres` service runs in docker (from
    `docker-compose.dev.yml`, prefixed compose project); the API is a
    **local uvicorn subprocess from the working tree**
    (`uv run uvicorn` from `apps/api`, DATABASE_URL pointed at the
    stack's own postgres) — the benchmark measures current code, with
    no image build. Uvicorn stdout/stderr go to
    `<tmpdir>/<project_name>-uvicorn/uvicorn.log` for failure diagnosis.
  - `containers` (non-default): the full app stack from
    `docker-compose.release.yml`. **Image acquisition** (containers mode
    only): no release image exists on GHCR yet — with
    `stack.build_image: auto` the runner builds the API image locally
    from the repo `Dockerfile` on first use (takes minutes, one-time per
    code state); `never` leaves acquisition to compose (pull of
    `ghcr.io/jmerifjkriwe/narrare:latest`) — usable once release images
    exist.
- **Python environment via uv** (repo toolchain). All commands below use
  `uv run` from the repo root.
- **Local config** — the runner refuses to start without it:

  ```sh
  cp benchmark/config.template.yaml benchmark/config.local.yaml
  ```

  `benchmark/config.local.yaml` is gitignored and guarded by the secrets gate.
  Fill in:

  | Field | What to put there |
  |---|---|
  | `llm.provider` | One of `anthropic`, `openai`, `google`, `groq`, `ollama`, `openrouter`, `zai` |
  | `llm.api_key` | Your provider API key (empty string is valid only for `ollama`) |
  | `llm.model` | A model id valid for the provider (1–200 chars) |
  | `auth.password` | Benchmark user password, 8–72 chars (any email works; the user is created per stack) |
  | `stack.project_name` | Only if you run parallel stacks; every container/volume/network carries this prefix |

  The remaining fields (`api.*`, `stack.port_range_*`, `run.*`) have working
  defaults. Note: the CLI flags (`--variant`, `--mode`, `--capabilities`,
  `--keep-stack`) control a run; the config's `run:` block is validated but
  not read by the CLI today. `api.base_url` must stay `null` in hybrid mode
  (the runner spawns the API itself and derives the URL from the selected
  port). `api.origin` (OPTIONAL, default `http://localhost:3000`) is the
  `Origin` header sent on every request — see the CSRF bullet in §6.

**Where your API key travels:** `llm.api_key` is sent in the request body of
exactly two calls — the pre-flight provider validation
(`POST /api/v1/setup/validate/step-4`) and the setup completion
(`POST /api/v1/setup/complete`), both via the normal user setup path
(`benchmark/provision.py`). It is never logged, never appears in error
messages, and never enters any artifact: the manifest carries only provider,
model, and a SHA-256 fingerprint over the redacted config.

## 3. Commands

> **Run all commands from the repository root** (`~/projects/narrare`), not from inside `benchmark/` — Python module resolution requires the repo root on the path.

Full run (all 26 registered capabilities, artifact tree under
`benchmark/runs/`, stack torn down afterwards):

```sh
uv run python -m benchmark run --variant light --mode incremental
```

Capability-subset smoke run (fast; only extraction + entity detail —
useful as the first-ever rehearsal):

```sh
uv run python -m benchmark run --variant clean --mode incremental \
  --capabilities CAP-IN-01,CAP-OUT-03
```

Flags (verified against `benchmark/__main__.py`; no others exist):

| Flag | Values | Notes |
|---|---|---|
| `--variant` | `clean`, `light`, `complex` | required; `light`/`complex` apply registry errors chapter-scoped |
| `--mode` | `incremental` (default), `import` | import = same build path without inter-chapter waits (no bulk-import endpoint exists) |
| `--capabilities` | comma-separated CAP ids | default: all 26 registry entries in order; unknown/duplicate ids fail **before** the stack starts |
| `--keep-stack` | flag | skip teardown (debugging; leaves containers/volumes behind) |
| `--out` | directory | default `benchmark/runs` (gitignored) |
| `--config` | path | default `benchmark/config.local.yaml` |

Stack debug subcommands (operate the compose stack without a run; `up` leaves
the stack up by design, `down` tears down and verifies residue-free, `status`
is read-only):

```sh
uv run python -m benchmark stack up
uv run python -m benchmark stack status
uv run python -m benchmark stack down
```

Manual tests (manual scope — never CI):

```sh
uv run pytest benchmark/tests/ -q
```

Exit codes: `0` success, `1` run failure (one-line message on stderr; the
failure artifacts carry the details), `2` argparse usage error.

## 4. Artifacts

Each complete run writes five files into `benchmark/runs/<run-id>/`, where
`<run-id>` is `YYYY-MM-DD-<variant>-<mode>-<n>` (counter per day/variant/mode):

| File | Contents |
|---|---|
| `results.json` | Per-capability × per-class scores with itemized lists (found/missing/spurious, matched/FP/FN) — every item traceable to a reference id (`F`/`R`/`E`/`PF`/`OF`) or registry error id |
| `answers.jsonl` | One JSON line per driven capability: the parsed raw output as recorded |
| `events.jsonl` | The run's sanitized raw HTTP-exchange sink, verbatim |
| `manifest.json` | Run id, timestamps, git commit, corpus version, config fingerprint (provider/model/hash — never the key), stack facts (compose file SHA-256, image digests, API version), capability counters |
| `overview.md` | The human-readable summary: per-direction tables, error-class matrix, FP-baseline note per capability, skipped table with reasons |

A failed run writes `failure.json` + `events.jsonl` into
`benchmark/runs/<day>-<variant>-failed-<n>/` (stage reached, error type and
message, event count) — written **before** teardown, so a partial run always
leaves evidence.

**FP-baseline note semantics.** `overview.md` states per capability whether
the clean-run FP baseline was applied:

- `Clean-run FP baseline: APPLIED` — findings whose fingerprint also occurs in
  the clean run's same-capability report were subtracted before claiming TP/FP.
- `Clean-run FP baseline: ABSENT — detection scored WITHOUT baseline
  subtraction` — every unmatched variant finding counts as FP, including
  findings that would also appear on the clean corpus.

**Current behavior is ABSENT.** The CLI has **no `--baseline` flag**
(verified against `__main__.py`): each run is self-contained, and the clean
run is a separate full run whose check reports are baseline *material*, not
detection evidence. Passing a clean-run baseline into a variant run is a known
gap deferred to the next iteration — until then, read FP counts from variant
runs as uncorrected (upper bounds).

## 5. Rehearsal checklist (PO-step)

No rehearsal has run yet: this environment has no `benchmark/config.local.yaml`
with a real LLM key, and Docker availability was unverified at writing time.
Per the plan's fallback clause the rehearsal is therefore a **PO step** — do
not mark it done until it has executed against a real stack. Exact procedure:

1. **Docker present:** `docker info` — must succeed without permission errors.
2. **Compose version:** `docker compose version` — must be **≥ 2.24**
   (the `ports: !override` mechanism requires it).
3. **Config filled:** `cp benchmark/config.template.yaml benchmark/config.local.yaml`
   and fill `llm.provider` / `llm.api_key` / `llm.model` + `auth.password`
   (see §2).
4. **Smoke run:**

   ```sh
   uv run python -m benchmark run --variant clean --mode incremental \
     --capabilities CAP-IN-01,CAP-OUT-03
   ```

   Expected, in order: compose starts the `postgres` service with project
   prefix `narrare-benchmark` and the runner waits for it to accept
   connections; the API comes up as a local uvicorn subprocess (working
   tree) and applies pending migrations; health wait passes (`GET /health`
   then `GET /ready`); provisioning registers the user and validates the
   provider config (a **real** provider API call happens at step-4
   validation); per-chapter ingest (novel "KB Benchmark [clean/incremental]",
   extraction + endorse-all per chapter); the two capabilities are driven
   and scored; artifacts appear under `benchmark/runs/<run-id>/`; teardown
   kills uvicorn, runs compose down, and verifies residue-free.
5. **Teardown residue check:**

   ```sh
   docker ps -a --filter name=narrare-benchmark
   docker volume ls --filter name=narrare-benchmark
   docker network ls --filter name=narrare-benchmark
   ```

   All three must return empty (this is exactly what the runner verifies
   internally; `stack down` does the same on demand).
6. **Report back:** the run id, a short excerpt of `overview.md`, the manifest's
   `stack` block (confirms image-digest parsing against the real compose
   engine), and any failures — including whether the server-side requests
   succeeded **with** the configured `Origin` header (the OPEN-3 fix, §6).
   Record results (redacted) here in the README and correct anything this
   document promises that the real stack contradicts.

Expected minimum runtime: roughly 2.5 minutes for the full corpus in
incremental mode (12 s pacing wait × 11 chapter boundaries, plus extraction
time; the two-capability smoke above is considerably faster).

## 6. Troubleshooting

- **Port collisions** — the runner picks the first bindable port in
  `[stack.port_range_low, stack.port_range_high]` (default 18080–18180) and
  binds it on `127.0.0.1` via the generated override file
  (`<tmp>/<project_name>-override/benchmark-compose-override.yml`). If the
  range is exhausted you get `no free port in [low, high]`; widen the range or
  set `api.base_url` to an explicit URL (the port scan is skipped then).
  Collisions with other services on the chosen port cannot happen — it is
  bound-checked — but a port occupied *between* scan and compose-up will fail
  `compose up`; simply re-run.
- **Health-wait timeout** — the runner polls `GET /health` and `GET /ready`
  for up to 180 s; at the deadline it raises `StackError` with the last 200
  compose log lines attached. For interactive debugging use
  `uv run python -m benchmark stack status`, or read logs directly:
  `docker compose -p narrare-benchmark -f docker-compose.release.yml logs`.
  A stack left behind by a `--keep-stack` run or `stack up` must be removed
  with `stack down` before starting a new run.
- **Provisioning 422 / step-4 validation failure** — step-4 validation makes a
  **real call to your LLM provider**; a failure there means the key/model pair
  was rejected by the provider, not by Narrare. Check: provider is one of the
  seven enum values (§2), model id is valid for that provider
  (`llm.model`), key has quota; `ollama` needs a reachable `ollama_url` and
  accepts an empty key. Server-side schema details:
  `benchmark/docs/api-surface.md` §3 (mirrors `Step4ProviderRequest`).
- **CSRF / Origin (OPEN-3 — resolved)** — outside test mode the API runs
  `OriginValidationMiddleware`: state-changing requests need either a
  trusted `Origin`/`Referer` header or a valid Bearer token. Register/login
  carry neither, so the first rehearsal hit 403 `CSRF_ORIGIN_MISMATCH`
  (exactly the OPEN-3 checkpoint outcome in api-surface.md §8). Fix: the
  client sends `Origin: <api.origin>` on **every** request; the default
  `http://localhost:3000` equals the API's default trusted origin. If your
  server overrides its trusted list — env var `NARRARE_CSRF_TRUSTED_ORIGINS`
  (JSON list, e.g. `'["https://narrare.example.com"]'`) — set `api.origin`
  in `config.local.yaml` to one of its entries (a bare origin:
  `scheme://host[:port]`, no path or trailing slash).
- **Config errors before anything starts** — a missing or invalid
  `config.local.yaml` fails with a precise `ConfigError` and exit 1 before the
  stack is created; unknown/duplicate `--capabilities` ids fail the same way,
  with no stack and no artifacts.

## 7. Known v1 boundaries

- **CAP-CHK-02/03 always skip (`SKIPPED(structural)`)** — they require a
  *series*, and v1 runs are single-novel: no series is provisioned, so
  `targets` never carries a `series_id`. CAP-CHK-05's structural target is the
  first ingested *chapter*, which the run populates, so CHK-05 **is** driven
  (grouping deviation flagged for coordinator ruling in the Task 15 report).
- **FP baseline: ABSENT** — no `--baseline` flag exists (§4). The baseline
  mechanism subtracts by **exact normalized fingerprint**, which is fragile
  under paraphrase: a reworded finding produces a different fingerprint and is
  not recognized as pre-existing. Baseline passing + fingerprint robustness are
  next-iteration work.
- **Detection threshold untuned** — the topic-overlap threshold
  (`TOPIC_OVERLAP_THRESHOLD = 0.5` in `benchmark/scoring/detection.py`) accepts
  a report item as matching when it shares ≥ 50% of the error's ground-truth
  topic tokens. The value is a reasoned default, not tuned against real runs.
- **API version via OpenAPI** — there is no `/version` endpoint (OPEN-1); the
  manifest records `GET /openapi.json` → `info.version`.
