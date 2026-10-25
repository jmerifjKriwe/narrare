---
description: Review the uncommitted change on a different model, in a child session
agent: reviewer
---

Review the change in the working tree. Base commit, or a narrower instruction: $ARGUMENTS

Nothing is committed before this review, so the tree is the change: `git diff <base>`
for the tracked part and every untracked file from `git status --porcelain`, read in
full. You cannot stage, so do not expect an untracked file to appear in a diff.

Run the gates the change touches and read their output; the implementer's report is a
claim, not evidence. Report findings by severity with `file:line` and how to reproduce,
and do not re-litigate a decision the task names as settled.
