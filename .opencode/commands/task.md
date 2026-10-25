---
description: Implement one numbered task from a plan, in a child session. No commit until the review is green
agent: implementer
---

One task, nothing else. Plan file and task number: $ARGUMENTS

Base commit: !`git rev-parse --short HEAD`

Follow the task's brief: the files it names, the gates it names. Do not commit — the
review comes first. Read the gate output; a gate you did not run is not green. Report
the exact file list you touched; it is the commit's pre-flight expectation.
