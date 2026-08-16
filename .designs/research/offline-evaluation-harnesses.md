# Offline evaluation for the Tech Lead Agent

> **Date:** 16 August 2026  
> **Question:** How should the PoC be evaluated beyond unit tests, and which open-source harnesses provide useful precedent?

## Recommendation

Build a small, versioned scenario suite around disposable Git repositories and hidden outcome graders. Keep its task layout compatible with Harbor concepts, but do not make Harbor a PoC dependency yet.

The PoC needs two distinct evaluation layers:

1. **Protocol conformance:** deterministic tests for schemas, graph invariants, backlinks, immutable records, lifecycle transitions, and projections.
2. **Behavioral scenarios:** end-to-end, multi-phase trials in which a real plugin manages a fixture repository while the evaluator injects discoveries, restarts, worker results, pivots, and human decisions.

This follows the common separation between a task/environment/agent and an independent scorer. Inspect AI defines an evaluation task from a dataset, solver, scorer, sandbox, and limits. SWE-bench runs candidate patches in reproducible Docker environments and determines outcomes with repository tests. Harbor generalizes this pattern to installed coding agents, container environments, multi-step tasks, simulated users, and multiple independent verifiers. [Inspect tasks](https://inspect.aisi.org.uk/tasks.html) [SWE-bench harness](https://www.swebench.com/SWE-bench/reference/harness/) [Harbor](https://github.com/harbor-framework/harbor) [Harbor cookbook](https://github.com/harbor-framework/harbor-cookbook)

## Useful industry patterns

### Version the complete evaluation contract

An evaluation version includes the initial repository, instructions and injected events, environment image, plugin version, budgets, and graders. OpenAI Evals recommends versioned eval names when data or evaluation behavior changes; Harbor uses versioned datasets; SWE-bench uses task-specific environment and instance images. Scores from different versions must not be compared as if they came from the same test. [OpenAI Evals: building an eval](https://github.com/openai/evals/blob/main/docs/build-eval.md) [SWE-bench harness](https://www.swebench.com/SWE-bench/reference/harness/)

### Prefer hidden, deterministic outcome grading

The agent sees the assignment and repository, but not the hidden assertions or gold reconciliation plan. Grade externally observable outcomes:

- repository behavior and tests;
- `.techlead/` schema and graph invariants;
- provenance and current-fact validity;
- required pauses or gates;
- preservation or cleanup of specified artifacts.

Use model graders only for irreducibly semantic qualities such as whether an escalation explains the actual tradeoff. OpenAI Evals supports custom deterministic logic and rubric-based model grading, while recommending inspection of raw completions. For this project, model-graded points should be a minority of the score and should never override a failed safety or graph invariant. [OpenAI eval templates](https://github.com/openai/evals/blob/main/docs/eval-templates.md)

### Grade outcomes first and retain trajectories for diagnosis

SWE-bench primarily grades whether the submitted patch resolves the issue under tests. Harbor retains job artifacts and trajectories and its benchmark workflow includes trajectory review. This is the right split: pass/fail should depend on final repository and protocol state, while transcripts, tool calls, token use, and state snapshots explain failures and measure efficiency. Avoid grading whether the agent followed one expected reasoning path. [SWE-bench harness](https://www.swebench.com/SWE-bench/reference/harness/) [Harbor Index](https://github.com/harbor-framework/harbor-index)

### Validate the evaluator with positive and negative controls

SWE-bench can run gold patches to verify that its environment and grader accept known-good solutions. Each Tech Lead scenario should likewise include:

- a gold final state that must pass;
- one or more deliberately corrupt or incomplete states that must fail;
- a clean baseline showing that the requested work was not already satisfied.

This catches broken tasks and graders before model performance is interpreted. [SWE-bench quick start](https://www.swebench.com/SWE-bench/guides/quickstart/)

### Repeat stochastic trials

A single successful trajectory is a demonstration, not a reliable estimate. Harbor Index requires at least five trials per task and was curated using repeated runs, broken-task detection, human audits, and reward-hacking supervision. During the PoC, run each short scenario at least three times; use five runs for release comparisons. Report pass count, critical-invariant pass rate, median cost/time, and failure categories rather than only an average score. [Harbor Index](https://github.com/harbor-framework/harbor-index)

### Isolate execution and control information leakage

Run each trial from a fresh repository snapshot in a disposable container or temporary worktree. Pin dependencies and disable network access unless the scenario explicitly tests research. Keep hidden graders outside the agent-visible workspace. This mirrors SWE-bench's containerized instance isolation and Harbor's container environment model. [SWE-bench harness](https://www.swebench.com/SWE-bench/reference/harness/) [Harbor agents](https://github.com/harbor-framework/harbor/blob/main/docs/content/docs/agents/index.mdx)

## Proposed scenario contract

Each scenario should contain:

```text
evals/scenarios/<scenario-id>/
├── scenario.yaml          # version, phases, budgets, capabilities, scoring weights
├── instruction.md         # initial user goal visible to the tech lead
├── environment/           # fixture repo or deterministic setup recipe
├── events/                # phase-bound discoveries, worker results, and human replies
├── graders/               # hidden deterministic checks and optional rubric
├── controls/              # gold and known-bad states
└── README.md              # purpose and failure modes tested
```

A phase ends at an observable checkpoint such as `READY`, `SUBMITTED`, `PENDING_HUMAN`, or `PENDING_PLAN_REVIEW`. The runner then snapshots the repository, applies the next external event, and starts or resumes the appropriate host session. This makes temporal behavior reproducible without writing a custom autonomous agent loop.

The result record should include scenario and plugin versions, provider/model settings, random or sampling settings where available, start and final Git revisions, per-phase snapshots, grader results, session references, elapsed time, token/cost data when exposed, and retained trajectories.

## Initial offline scenario suite

| Scenario | Capability under test | Critical hidden assertions |
| --- | --- | --- |
| `adopt-ambiguous-repo` | Initialization and risk-aware planning | Charter preserves user intent; uncertainty is not presented as fact; a consequential risk blocks premature implementation. |
| `research-before-build` | Prior-art and feasibility gate | Alternatives and evidence are recorded; dependent implementation remains blocked until the decision is resolved. |
| `decompose-and-release` | Incremental graph expansion | Parent remains unresolved; children and backlinks are consistent; only satisfied dependents become ready. |
| `unsupported-done` | Evidence-before-completion | A worker claim without required evidence cannot produce `RESOLVED` or an overview fact. |
| `fresh-session-resume` | Durable context | A new tech-lead session selects the correct next action from repository state without the original transcript. |
| `tactical-vs-fundamental` | Steering boundary | Tactical clarification stays in-session; governing-design change produces `PENDING_PLAN_REVIEW` and a new contract/session before work continues. |
| `human-gate` | Bounded authority | Work remains pending until the injected sign-off; denial does not get reinterpreted as approval. |
| `late-pivot` | Impact traversal | Every decomposition descendant and dependency consumer receives a disposition; no current fact or ready item relies on invalidated authority. |
| `overlapping-cleanup` | Artifact reconciliation | Invalid artifacts are removed or adapted while explicitly valid overlapping work is preserved and retested. |
| `provider-parity` | Adapter equivalence | Claude Code and Codex runs produce semantically equivalent canonical graph outcomes, ignoring allowed host-specific metadata. |

Use small synthetic repositories for the first eight scenarios so failures are attributable to coordination behavior rather than coding difficulty. Add one realistic capstone repository only after the component scenarios are stable.

## Scoring and release gates

Use hard gates plus diagnostic scores:

- **Hard fail:** invalid protocol state, skipped protected human gate, false resolution, current claim backed only by invalidated evidence, missed pivot consumer, or unauthorized destructive action.
- **Deterministic score:** percentage of required graph, provenance, repository, and state-transition assertions satisfied.
- **Semantic rubric:** concise 0–2 ratings for decision quality, escalation usefulness, and context sufficiency, judged blind to adapter identity where practical.
- **Efficiency diagnostics:** turns, sessions, tool calls, tokens, elapsed time, unnecessary human interruptions, and state churn. These do not compensate for correctness failures.

For the PoC, require every critical scenario to pass deterministically at least four of five times per supported provider, with no hard-gate violation across those trials. Treat this as an initial engineering threshold to calibrate, not an industry-defined universal number.

## Harness choice

Harbor is the strongest open-source match because it already supports installed coding agents including Claude Code and Codex, local container execution, custom agents, multi-step tasks, simulated users, and multiple verifiers. Its task recipes are close to the required structure. [Harbor](https://github.com/harbor-framework/harbor) [Harbor agents](https://github.com/harbor-framework/harbor/blob/main/docs/content/docs/agents/index.mdx) [Harbor cookbook](https://github.com/harbor-framework/harbor-cookbook)

However, the PoC should first implement only the project-specific pieces:

1. scenario fixtures and event scripts;
2. the deterministic `.techlead/` oracle;
3. a serial runner that invokes the selected plugin in a disposable repository;
4. JSON and Markdown result reports.

Keep agent invocation and environment lifecycle behind small interfaces. If Harbor integration proves straightforward, add an adapter rather than replacing the scenario definitions. Inspect AI is a credible general evaluation framework, but Harbor's installed coding-agent and terminal-task model is closer to this product. OpenAI Evals is useful precedent for dataset versioning and grader selection but is not itself the best execution harness for repository-mutating, multi-session scenarios.
