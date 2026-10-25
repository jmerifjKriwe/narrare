---
description: Review one task's uncommitted change in a child session
agent: reviewer
---

Review one task's change in the working tree. Base commit or task: $ARGUMENTS

Base commit: !`git rev-parse --short HEAD` — if $ARGUMENTS names an earlier
base, that one wins; say which you used. Nothing is committed before this
review: if `git log` shows a commit on top of the base, that is a finding.

The change is `git diff <base>` for tracked files plus every untracked file from
`git status --porcelain`, read in full.

Read the task brief and the implementer's report the dispatch names. The brief is
the requirement; the report is a claim. Follow the rubric in your agent file,
including the Declined-to-judge list.

Run the gates the task names, `just check`, and the capability E2E when one
exists. Read their output. A gate you did not run is not green.

Report in your agent's output format.
