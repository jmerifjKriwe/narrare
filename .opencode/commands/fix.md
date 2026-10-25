---
description: Hand review findings back to the implementer session that made the change
---

Resume the implementer's child session with the `subagent` tool, passing it as
`sessionID` together with the `implementer` agent: $ARGUMENTS

The first word is the session id (`ses_…`). Everything after it is the finding, or the
path to a review report to work through verbatim.

No new brief and no restatement of the plan: the child still has its task, its base
commit and its context. It fixes what the findings name and reruns the gates it ran
before. Still no commit — that waits for a green review. When the review does come
back green, resume the same session once more and tell it to commit exactly the file
list it reported.

Re-review the whole uncommitted change against the same base: a fix round adds no
commit, so there is no delta to isolate.
