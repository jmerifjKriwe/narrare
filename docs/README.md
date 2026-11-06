# Narrare documentation

Where everything lives, and what each place is for.

## Using the application

- [User guide](user/INDEX.md) — the screens, the writing flow, settings.
- [Feature notes](features/INDEX.md) — one page per capability and cross-cutting topic.

## Installing and running it

[The README](../README.md#getting-started) is the installation path: prerequisites,
`just dev-setup`, and the first run. [TESTING.md](../TESTING.md) covers the test
layers, the gates and how to run each of them.

## Architecture

- [Constraints](_shared/CONSTRAINTS.md) — the five standing rules, the shape of a
  capability, and the governance budget.
- [Architecture spec](superpowers/specs/2026-10-21-narrare-v2-architecture-design.md)
  — why the boundaries sit where they do.
- [Decisions](architecture/decisions/INDEX.md) — the choices that are expensive
  to reverse.
- [The GitHub surface](architecture/github.md) — workflows, the ruleset, the
  repository settings, and which signal is advisory.

## Security

- [Security policy](../SECURITY.md) — how to report a vulnerability privately,
  what is in scope, and what is not.
- [Dependency updates](architecture/github.md#dependabot) — how Dependabot,
  the nightly audit and the monthly tool-pin check fit together.

## The design record

`superpowers/` holds the dated plans, specs and reports of finished work
packages — read one only when a comment points at it. Its
[follow-ups page](superpowers/follow-ups.md) indexes the open findings.
