---
name: create-work-item
description: Explicitly create one unsigned child in a Tech Lead Protocol 2.0 work log. Use only when the human asks to add a work item under a named parent.
disable-model-invocation: true
---

# Create a work item

Read `${CLAUDE_PLUGIN_ROOT}/core/behaviors/create-work-item.md` and the packaged
protocol. Resolve the canonical project, confirm one explicit parent, and reject
a resolved parent.

Prepare a concise free-form body with narrow Markdown links to the relevant
parent context and presumptions. Invoke the packaged `techlead-state
create-work-item` command with the requested title and work type. The child must
remain `in-design`, with no active revision and no inherited sign-off. Validate
the project and return the new `WORK.md` as the agent context entry point.
