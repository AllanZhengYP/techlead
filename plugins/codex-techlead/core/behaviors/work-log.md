# Work log

Run only when the human explicitly asks to initialize, inspect, attach, manage
sessions, validate, or recommend work from the Tech Lead log.

Deterministic actions delegate to `techlead-state`: `init`, `attach`,
`register-session`, `pause-session`, `close-session`, `status`, `next`, and
`validate`. Re-register an existing provider session to move it to another
attached workspace. These actions do not transition work-item state.

For `next`, begin with the deterministic projection, then read the signed start
conditions, current findings, coordination notes, and live sessions. Return one
or more `(action, work item)` pairs with a short reason, the `WORK.md` context
entry point, and explicit reasoning for any proposed parallel group. Do not
invent dependency edges. Do not recommend affected execution while a mandatory
review is pending.

Workspace attachment and session identity are distinct. Registration may
attach or repair the supplied workspace, and one session may cover several work
items. Git branch and revision are optional hints. Local symlinks, mappings,
locks, and snapshots must remain untracked.
