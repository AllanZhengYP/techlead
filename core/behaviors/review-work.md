# Review work

Run only when the human explicitly asks Tech Lead to review a named work item.
Do not implement the work and do not claim independent implementation
verification.

1. Resolve the canonical project and named item with `techlead-state`.
2. Register or reuse a dedicated `techlead-review` session. Never relabel a
   design, exploration, implementation, or verification session.
3. Read `WORK.md`, its active revision, parent context, child verdicts, the
   named design or outcome, and only the additional links used for the review.
4. Run deterministic validation and `techlead-state validate-links` over every
   document in the bounded review context. Check each reported external URL
   when network permission is available. A broken or unavailable required link
   blocks transition.
5. Select the state-specific bar:
   - `in-design`: challenge explicit and implicit assumptions, credible
     alternatives, requirements, decomposition, start conditions,
     coordination, verifiable outputs, and resolution conditions.
   - `in-working` leaf: assess the supplied external outcome against the signed
     resolution conditions without independently re-verifying it.
   - `in-working` parent: handle an early material exception immediately, or
     wait for every current child for an ordinary completion review.
   - `resolved`: stop; resolution is terminal.
6. Present recommendations and ask the human to decide materiality,
   invalidation, and any proposed child creation.
7. Apply the authorized decision through `techlead-state apply-review`. Create
   a revision only when the semantic baseline changes. Create proposed children
   only after explicit approval and in the same mutation as the parent change.

An incomplete review leaves the item in its current state and records current
findings. Reaffirmation clears a due review without creating a revision.
Resolution is allowed only when every current child is resolved.
