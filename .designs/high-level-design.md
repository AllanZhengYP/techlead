# Tech Lead Agent — High-Level Design

> **Status:** Draft  
> **Date:** 13 August 2026  
> **Depends on:** [Vision](./vision.md)

## 1. Design decisions

The project ships as two installable, versioned plugins:

1. a Codex plugin;
2. a Claude Code plugin.

They implement one shared workflow and repository-state contract but use the native extension and agent-invocation mechanisms of each host. A plugin is the distribution package; Codex or Claude Code remains the runtime.

The PoC does not ship a service, daemon, database, scheduler, or custom agent loop. It also does not require an MCP server. The harnesses already provide the local model loop, repository tools, shell and Git access, isolated agent contexts, permission handling, session interaction, and human steering needed to test the vision.

## 2. What we ship

The product is the plugin pair, not a new coding harness. A release contains:

- one installable Codex plugin;
- one installable Claude Code plugin;
- a versioned, provider-neutral `.techlead/` state protocol shared by both;
- deterministic validation code and conformance fixtures embedded in each plugin;
- documentation and a small example project demonstrating the full PoC workflow.

The two plugins should normally share a release version. Each initialized project records its state-protocol version so a plugin can reject an incompatible project or perform an explicit migration rather than reinterpret old records silently.

The source repository produces two self-contained plugin artifacts from a shared semantic core:

```text
techlead-agent/
├── core/
│   ├── roles/                 # provider-neutral role contracts
│   ├── protocol/              # work graph and state semantics
│   ├── templates/             # .techlead project templates
│   └── schemas/               # mechanically checkable record shapes
├── plugins/
│   ├── codex-techlead/
│   │   ├── .codex-plugin/plugin.json
│   │   ├── skills/
│   │   └── hooks/             # optional mechanical hooks
│   └── claude-techlead/
│       ├── .claude-plugin/plugin.json
│       ├── skills/
│       ├── agents/
│       └── hooks/             # optional mechanical hooks
└── tools/
    └── techlead-state         # local deterministic helper
```

The release process copies or generates shared material into each plugin artifact. Installed plugins must be self-contained; they must not depend on paths back into this source tree.

The normal delivery path is the native marketplace or plugin-install mechanism of each host. Local-directory installation remains supported for development. Installing the plugin does not install a daemon, start a process, or rewrite the user's global agent configuration.

### User-facing capabilities

Each plugin provides the same conceptual entry points, even if their host-specific invocation names differ:

- **Initialize or adopt a project:** create or validate `.techlead/` state from the user's goal and existing repository.
- **Lead or resume a project:** load the charter, overview, and frontier; select and advance the next graph action.
- **Inspect status:** explain established knowledge, active work, blockers, risks, and the next recommended action.
- **Reconcile a pivot:** traverse affected graph nodes, update validity, and create replacement or cleanup work.
- **Validate state:** mechanically check record shape, IDs, graph links, backlinks, and references.

The first four are agent skills requiring judgment. State validation is deterministic local code. The helper may edit files only when invoked for a specific state transition authorized by the active tech lead; it does not independently schedule work or decide project meaning.

### Target-repository state

The plugins store project memory in the target repository, not in plugin installation data:

```text
.techlead/
├── CHARTER.md
├── OVERVIEW.md
├── FRONTIER.md
├── RISKS.md
├── DECISIONS.md
└── work-items/<id>/...
```

This state is portable between providers and survives replacement of any agent session. Existing `AGENTS.md`, `CLAUDE.md`, repository rules, and nested guidance remain owned by the target repository and are loaded by the corresponding harness.

## 3. Logical roles

The design defines four roles independently of their provider representation:

| Role | Responsibility | Typical harness context |
| --- | --- | --- |
| Global tech lead | Own the project view, work graph, risk decisions, delegation, resolution, and pivots. | Main interactive session. |
| Worker | Execute one assignment contract and report changes, evidence, and discoveries. | Native subagent or child agent thread. |
| Verifier | Evaluate specified acceptance criteria with the required independence. | Fresh native subagent when agent review is required. |
| Sub-tech-lead | Discuss and analyze fundamental divergence in full project context. | Fresh native subagent, returning a graph-change proposal. |

The roles define semantic authority. The harness owns execution mechanics. A worker does not become accepted merely because its native agent thread returns successfully; the global tech lead still applies the repository-state protocol.

## 4. Harness capability boundary

The plugins should use host capabilities instead of reproducing them:

| Concern | Plugin responsibility | Harness responsibility |
| --- | --- | --- |
| Agent behavior | Supply role instructions, assignment contract, and selected context. | Run the model/tool loop. |
| Delegation | Decide which role and contract are needed. | Spawn, display, steer, wait for, and stop child agents. |
| Context isolation | Select the frontier neighborhood and historical links. | Give the child a separate context window. |
| Repository operations | State allowed scope, artifacts, and verification requirements. | Provide file, search, shell, Git, and other tools. |
| Workspace isolation | Request isolation appropriate to the assignment. | Provide native worktree/isolation when available; otherwise execute Git operations under normal permissions. |
| Permissions | Express project authority boundaries and protected actions. | Enforce sandbox, tool approvals, credentials, and user consent. |
| Human checkpoints | Identify semantic uncertainty or explicit sign-off requirements. | Pause, ask, display the question, and resume. |
| Worker interaction | Decide whether a question is tactical input or contract-changing divergence. | Mediate through the parent, or expose attach/steer controls when the host supports them. |
| Session continuity | Record contract revision and opaque session reference. | Preserve and resume an unchanged session when supported. |
| Durable memory | Maintain `.techlead/` records and evidence links. | Preserve ordinary repository files and Git history. |

This boundary keeps provider adapters thin. The project does not parse model transcripts, simulate a message loop, maintain its own approval UI, or infer completion from process exit alone.

## 5. Harness-driven execution flow

The PoC topology is deliberately small: one interactive tech-lead session and at most one active worker, verifier, or sub-tech-lead context at a time. The tech lead is the sole graph coordinator. This exercises native delegation without introducing parallel scheduling or a distributed coordination protocol.

### Start or resume the tech lead

1. The user invokes the tech-lead skill in the target repository.
2. The harness loads its normal repository guidance.
3. The skill loads `CHARTER.md`, `OVERVIEW.md`, and `FRONTIER.md`, validates references, and follows only the work-item or risk links needed for the next decision.
4. The main session acts as the global tech lead and updates authoritative state as work advances.

### Delegate a worker

1. The tech lead selects one `READY` work item.
2. It creates an immutable assignment-contract revision and a context projection.
3. It asks the harness to start a fresh native worker context, optionally isolated in a worktree.
4. The worker uses native repository tools, test execution, progress reporting, permission prompts, and human interaction.
5. The harness returns the worker's result to the parent; the durable attempt record links the result to its session, commits, artifacts, and evidence.

The context projection contains the assignment, relevant charter constraints, global risk references, required resolved facts with provenance links, and the relevant frontier neighborhood. It does not contain all historical resolutions or unrelated active work.

The portable interaction path is through the main tech-lead session: it relays a tactical question to the current worker or records a human answer in the assignment result. If the host exposes an attachable or steerable child session, the user may speak to the worker directly. That richer UI is an optimization, not part of the state protocol. In either path, tactical discussion may change execution details, while a change to the governing design, assumptions, scope, or acceptance criteria triggers the divergence flow.

### Verify and resolve

The global tech lead maps each acceptance criterion to worker evidence, a deterministic check, a fresh verifier, or human sign-off. Deterministic checks run through native shell and repository tools. Independent review uses a fresh native agent context. Human sign-off uses the harness's ordinary interaction channel.

Only the tech lead writes `RESOLUTION.md`, updates the evidence-backed overview, and releases dependency edges after all required verification passes.

### Steer, diverge, or pivot

- Tactical steering stays in the current worker thread when the assignment contract is unchanged.
- Fundamental divergence stops affected work and starts a fresh sub-tech-lead context with the full relevant project view.
- A changed contract starts a fresh worker context; unchanged contracts may resume their existing sessions.
- A pivot triggers graph impact traversal and workspace reconciliation through normal tech-lead and worker assignments rather than a special external runtime.

## 6. Provider adapters

### Codex plugin

The Codex artifact packages the tech-lead workflows as skills, plus templates, deterministic scripts, and optional lifecycle hooks. Current Codex plugin packaging supports a `.codex-plugin/plugin.json` manifest with skills, hooks, MCP configuration, and assets. Codex itself supplies native built-in workers and subagent orchestration. Applicable skill or `AGENTS.md` instructions can request delegation, and the host manages agent threads, steering, waiting, sandbox inheritance, and approvals. [Codex plugin packaging](https://developers.openai.com/plugins/build/plugins) [Codex subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents)

Current Codex custom-agent definitions live in user or project `.codex/agents/*.toml`, while the plugin format does not currently list agents as a packaged component. The PoC therefore uses native built-in agents with explicit role and assignment prompts. Optional custom Codex profiles may be offered later as an installer-generated optimization, but the semantic workflow must not depend on them. This conclusion is an inference from the current plugin and custom-agent documentation. [Codex customization](https://learn.chatgpt.com/docs/customization/overview)

### Claude Code plugin

The Claude artifact packages the same skills and can also package worker, verifier, and sub-tech-lead definitions under `agents/`. Claude Code plugins natively bundle skills, agents, hooks, MCP servers, and executables; plugin agents run in isolated contexts and can request worktree isolation. The parent Claude session remains the global tech lead and invokes those agents with generated assignment contracts. [Claude Code plugin guide](https://code.claude.com/docs/en/plugins) [Claude Code plugin reference](https://code.claude.com/docs/en/plugins-reference)

Claude's `CLAUDE.md` continues to provide repository guidance. A `CLAUDE.md` placed inside a plugin is not automatically project context, so all shipped role behavior belongs in skills and agent definitions. Native subagents provide context isolation and return summarized results to the parent. [Claude Code extension model](https://code.claude.com/docs/en/features-overview)

Claude also offers independently attachable sessions and experimental agent teams, but the PoC does not require them. Its portable execution model is the ordinary parent-and-subagent path; direct attachment can be enabled later as a host-specific user experience. [Claude Code agent modes](https://code.claude.com/docs/en/agents)

## 7. Hooks and MCP policy

Hooks are optional and mechanical. Suitable PoC uses include validating graph links after `.techlead/` edits or reminding the tech lead to flush state before a session ends. Hooks must not decide whether evidence is sufficient, resolve a work item, classify pivot impact, or silently modify project meaning.

An MCP server is intentionally absent from the PoC. Local files and built-in harness tools are sufficient. MCP becomes justified only if the workflow later needs a stable cross-harness tool API, remote project storage, or external-system integration that cannot be expressed safely through repository files and local scripts.

## 8. Compatibility contract

Provider parity means equivalent outcomes, not identical files or prompts. Both plugins must preserve:

- the `.techlead/` memory format;
- work-item states and graph-edge semantics;
- immutable assignment revisions;
- context-projection rules;
- verification authority;
- divergence, invalidation, and pivot behavior;
- role result shapes.

Provider-specific behavior is allowed only for invocation, agent configuration, tool and permission surfaces, worktree mechanics, and user-interface affordances.

## 9. PoC delivery sequence

1. Define the provider-neutral state schema, role contracts, and expected result envelopes.
2. Implement the deterministic state validator and fixtures for graph expansion, resolution, and pivot reconciliation.
3. Ship the Claude Code plugin first and run the complete vision scenario manually through its native harness. Claude Code is the development-first adapter because its plugin format can package the worker, verifier, and sub-tech-lead agents directly and exposes the broader plugin feature surface needed to exercise the design with less adapter scaffolding.
4. Implement the Codex adapter against the same fixtures and compare semantic outcomes. The provider-neutral protocol and fixtures, rather than the first adapter, remain the reference semantics.
5. Add hooks only for repetitive mechanical gaps observed in those runs.

## 10. PoC implementation decisions

- **Provider order:** Implement the Claude Code plugin first, followed by Codex. The first adapter is a development vehicle, not the semantic reference.
- **Status entry point:** Do not add a separate user-visible `status` skill initially. `lead/resume` answers status questions without changing project state. A dedicated entry point is reconsidered only if trials show a discoverability or safety problem.
- **State representation:** Use Markdown records with YAML frontmatter. Frontmatter holds mechanically validated identity, lifecycle, graph relationships, immutable references, and provenance pointers; Markdown holds objectives, explanations, findings, and rationale. `WORK.md` is the sole mutable canonical record for a graph node. Contract revisions, attempts, verifications, resolutions, and invalidations become immutable once referenced. Role results use the same Markdown-plus-frontmatter envelope rather than a separate JSON protocol.
- **Identifiers and references:** Use stable opaque IDs such as `WI-001`, `AC-001`, `EV-001`, `RISK-001`, and `DEC-001`. Graph edges use IDs rather than filesystem paths. Artifact and evidence references may contain repository-relative paths and Git revisions. Timestamps are informational and never determine correctness.
- **Validation boundary:** Deterministic validation checks schemas, allowed states, immutable references, graph links and backlinks, ID uniqueness, and referential integrity. It does not decide semantic questions such as whether evidence is sufficient or a work item should be resolved.
- **Workspace isolation:** The plugin requests host-native worktree or workspace isolation and records what the host supplied. The PoC helper does not create, switch, merge, or remove worktrees itself.
- **Hooks:** Begin with no hooks. Add a mechanical post-edit validator or session-end state reminder only when the manual end-to-end run demonstrates a recurring failure that the hook would prevent.

The remaining schema work is specification rather than an architectural choice: define the exact frontmatter fields, constraints, and role result envelopes before implementing the validator.

> **Design rule:** Use plugins to install the workflow, repository files to preserve the project, native agents to execute work, and the selected harness to manage sessions, tools, isolation, permissions, and human interaction.
