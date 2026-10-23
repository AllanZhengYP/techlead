# Create a work item

Run only when the human explicitly asks for a new work item under one named
parent.

1. Resolve the project and parent.
2. Reject a missing, ambiguous, or resolved parent.
3. Identify the requested title and work type: `design`, `exploration`,
   `implementation`, or `verification`.
4. Add narrow Markdown links to the relevant parent context, signed
   presumptions, and source material. Do not copy the entire parent.
5. Invoke `techlead-state create-work-item`.

The new item always starts as unsigned `in-design`, with no active revision and
no pending-review flag. Creation never inherits the parent's sign-off.
