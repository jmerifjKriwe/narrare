---
description: Implement one numbered task from a plan, in a child session
agent: implementer
---

One task, nothing else. Plan file and task number: $ARGUMENTS

Base commit: !`git rev-parse --short HEAD`

Follow the task's brief: the files it names, the gates it names, the commit it asks
for. Read the gate output; a gate you did not run is not green.
