---
description: Hand review findings back to the implementer session that made the change
---

Resume the implementer's child session with the `subagent` tool, passing it as
`sessionID` together with the `implementer` agent: $ARGUMENTS

The first word is the session id (`ses_…`). Everything after it is the finding, or the
path to a review report to work through verbatim.

No new brief and no restatement of the plan: the child still has its task, its base
commit and its context. It fixes what the findings name, reruns the gates it ran
before and commits. Re-review only the delta afterwards, with the sha that the first
review covered.
