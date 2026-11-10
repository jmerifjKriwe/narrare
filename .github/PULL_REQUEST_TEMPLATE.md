<!--
  Keep this short and honest. Fill in what applies, delete what does not, and
  write "N/A" with a reason rather than leaving a claim unchecked.
-->

## What and why

<!-- The behaviour that changes, and for whom — the user, or the release, CI or docs
     where no user can see it. The issue it closes and the spec section may follow as
     references, not as the name of the work. -->

## Verification

<!-- The gate you actually ran: command and result. A checkbox without a read result is not verification. -->

| Ran | Command | Result |
| --- | --- | --- |
| fast gate | `just check` | |
| tests | `just test` or `just test-file <path>` | |
| capability E2E | `app/capabilities/<name>/e2e/` | |
| full gate | `just verify` | |

## Commit standard

- [ ] Conventional commit; `feat`, `fix`, `perf` and `docs` carry a real `User-visible:` line
- [ ] Development-only work uses a hidden type (`chore`, `refactor`, `test`, `ci`, `build`, `style`); `chore(docs)` for development documents, `docs` for user documentation
- [ ] No `--no-verify` and no force push

## Boundaries

- [ ] No capability imports another; shared domain lives in `app/kernel/`
- [ ] User-visible text exists in the catalogs (`i18n/*.json` and each capability's `web/i18n/*.json`)
- [ ] No new rule, registry, check script, hook, required field or mandatory document — or it was approved (`docs/_shared/CONSTRAINTS.md`)

## UX review

<!-- Only for UI or AI-touching changes; delete this whole section otherwise. -->

**Before / after:** <!-- screenshot, recording, or one line describing the change -->

- [ ] Text arrives incrementally; the frame renders each chunk as it lands
- [ ] The sources of an answer are visible with or before the answer
- [ ] A running generation can be cancelled
- [ ] Generated text is applied only on user confirmation
- [ ] Visible state change under 200 ms after the action starts
- [ ] Idle → working → streaming → done is distinguishable
- [ ] All user-visible strings go through the merged catalogs
- [ ] Errors say what happened and what to do next
- [ ] AI activity is announced to assistive tech (aria-live or equivalent)
- [ ] Focus lands sensibly after output arrives

Items marked N/A: <!-- … -->
