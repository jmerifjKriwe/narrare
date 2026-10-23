<!--
  Keep this short and honest. Fill in what applies, delete what does not, and
  write "N/A" with a reason rather than leaving a claim unchecked.
-->

## What and why

<!-- The behaviour that changes for the user, and the issue or spec section it serves. -->

## Verification

<!-- The gate you actually ran: command and result. A checkbox without a read result is not verification. -->

| Ran | Command | Result |
| --- | --- | --- |
| fast gate | `just check` | |
| tests | `just test` or `just test-file <path>` | |
| capability E2E | `app/capabilities/<name>/e2e/` | |
| full gate | `just verify` | |

## Commit standard

- [ ] Conventional commit; a `feat` or `fix` carries a real `User-visible:` line
- [ ] No `--no-verify` and no force push

## Boundaries

- [ ] No capability imports another; shared domain lives in `app/kernel/`
- [ ] User-visible text exists in `i18n/en.json`, `de.json` and `fr.json`
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
- [ ] All user-visible strings go through the i18n catalog (en, de, fr)
- [ ] Errors say what happened and what to do next
- [ ] AI activity is announced to assistive tech (aria-live or equivalent)
- [ ] Focus lands sensibly after output arrives

Items marked N/A: <!-- … -->
