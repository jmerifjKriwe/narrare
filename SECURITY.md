# Security Policy

Narrare is a local-first application: one user, one database, on your own machine.
It has no accounts, no hosted service and no telemetry.

## Supported versions

Pre-1.0 and moving. Only the latest release on `main` receives security fixes.
There are no maintenance branches and no backports — the fix is the update.

## Reporting a vulnerability

Report privately through GitHub's advisory form:
<https://github.com/jmerifjKriwe/narrare/security/advisories/new>

The form is the only channel; there is no security mailbox. Please do not open a
public issue for anything exploitable.

**What to expect:** best effort, no SLA. One maintainer, alongside other work. You
get an acknowledgement once the report has been read, and an honest answer about
whether and when a fix lands. A real issue found in good faith is credited in the
advisory unless you prefer otherwise.

## Scope

In scope is Narrare's own code: the API, the web app, database access, file and asset
handling, and the behaviour of its dependencies as Narrare uses them.

Out of scope:

- **An instance you exposed.** The local build has no authentication: every request
  is the single local user, so anything that can reach the API port acts as you.
  Keep it on localhost, or put your own auth in front of it.
- **Your model provider.** Prompts and text go to the endpoint you configured. What
  that provider does with them is between you and them.
- **Your machine, your Postgres, your keys in `.env`.**

## No bounty

There is no payment for reports. The credit in the advisory is what there is.
