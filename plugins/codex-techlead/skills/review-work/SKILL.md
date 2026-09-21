---
name: review-work
description: Explicitly bar-raise or review a named Tech Lead Protocol 2.0 work item. Use only when the human invokes $review-work to review a design, assess a supplied work outcome, or synthesize child findings.
---

# Review work

Resolve this skill's installed plugin root, then read
`core/behaviors/review-work.md` and `core/protocol/PROTOCOL.md` from that root.

Use the root's `bin/techlead-state` helper to resolve and validate the project.
Register or reuse a dedicated `techlead-review` session; never relabel another
session role. Inspect the named `WORK.md`, active revision, parent and child
verdicts, source design or outcome, and only the linked context used for the
decision.

Challenge assumptions and credible alternatives adversarially but keep the
human in control. Ask one material decision at a time and include a
recommendation. Run the packaged `validate-links` command with every document
opened or relied on, then check each reported external URL when network access
is available. Do not implement work or claim independent verification.

Before invoking `apply-review`, explain the proposed transition, revision, and
children. Obtain explicit approval for child creation. Use a new revision only
when the semantic baseline changes, then rerun `validate` and report the exact
state change and remaining review obligations.
