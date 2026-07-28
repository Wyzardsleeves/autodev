# AutoDev — design

An autonomous coding agent that takes a ticket, fixes a repository, and proves it
with tests. One command:

```bash
uv run autodev run --ticket tickets/T-001.json --repo ./target-app
```

## Three layers

```
┌─────────────────────────────────────────┐
│ CLI                index.py             │  parse argv, load ticket, exit code
└──────────────────┬──────────────────────┘
                   │ ticket dict + repo path
┌──────────────────▼──────────────────────┐
│ Agent platform     agent.py (LangGraph) │  control flow: what happens next
│                    reporting.py          │
│                    memory.py             │
└──────────────────┬──────────────────────┘
                   │ tool calls
┌──────────────────▼──────────────────────┐
│ Boundary           tools.py              │  capabilities
│                    safety.py             │  what is permitted
│                    isolation.py          │  where it may happen
└──────────────────┬──────────────────────┘
                   │
              .worktrees/T-001/target-app
```

The split that matters: **the model requests, the platform decides.** Every
filesystem call goes through `safety.safe_path`, and the only executable the
agent can trigger is `pytest`.

## Control flow

```
START → classify ─── refused ──────────────────────► report → learn → END
             │
             └── recall → understand → plan → act → verify
                                        ▲              │
                                        │          tests pass?
                            budget left ┴──── no ──────┤
                                                   yes │
                                                       ▼
                                                    report
```

LangGraph nodes are **stages of reasoning**. Reading, grepping and writing are
**tools**, not nodes — otherwise every file read becomes a graph edge and the
control flow drowns in plumbing.

| Node | LLM? | What it does |
|---|---|---|
| `classify` | no | `safety.ticket_refusals()`. Unsafe or malformed → straight to report. |
| `recall` | no | Keyword-scores past lessons, injects the top 5 into the plan prompt. |
| `understand` | no | `list_files`, greps seeded from the ticket title, and a **baseline test run**. Deterministic context-gathering is cheaper and more reliable than asking the model to go look. |
| `plan` | yes | Numbered plan. On a retry it also receives the previous attempt and the test output, with an explicit instruction to diagnose rather than repeat. |
| `act` | yes | `create_react_agent` loop over the six tools, `recursion_limit=40`. |
| `verify` | no | Runs pytest. The **exit code** is the signal. |
| `report` | no | `verdict()` — see below. Writes JSON + Markdown. |
| `learn` | yes | One-sentence reusable lesson, stored only if the run resolved. |

## What counts as success

A passing suite is *not* evidence of a fix — it also describes a run that did
nothing to a repo that was already green. `agent.verdict()` distinguishes:

| Status | Condition |
|---|---|
| `resolved` | Tests pass, and either the baseline was red, or the diff contains both a regression test and a source change. |
| `unproven` | Tests pass, baseline was already green, no test+fix pair. The ticket probably doesn't reproduce. |
| `no_change` | Tests pass, empty diff. |
| `failed` | Tests still red at the budget ceiling. |
| `refused` | Never started. |

This was not theoretical. The first live T-001 run left a scratch probe file,
found nothing wrong, and the plain test gate called it **resolved** — then
`learn` wrote a fabricated lesson into memory. The verdict rules and the
"no scratch files" prompt rule both come from that run.

## Safety

Five boundaries, all enforced in code rather than by prompt:

1. **Ticket validation** (`safety.ticket_refusals`) — the ticket is untrusted
   input. Eight patterns cover arbitrary execution, destructive deletion,
   credential access, exfiltration, safeguard-disabling and prompt injection.
   The whole ticket is scanned as one blob, so splitting a request across
   `title` and `description` doesn't slip through.
2. **Path sandboxing** (`safety.safe_path`) — absolute paths rejected; the path
   is `resolve()`d *before* the containment check, so a symlink out of the
   sandbox is caught like a literal `../../..`; `.git`, `.venv` and `.env` are
   protected even inside the sandbox.
3. **Restricted tools** — six named capabilities. Deliberately **no
   `run_shell_command`**: a dedicated `run_tests` is the whole difference
   between the platform deciding what may execute and the model deciding.
   A refused call returns `DENIED: …` as a normal tool result, so the model can
   read it and pick another approach instead of crashing the run.
4. **Test gate** — `verdict()` reads pytest's exit code. There is no path by
   which the model's opinion sets `status`.
5. **Budget** — `MAX_ITERATIONS = 5`, `recursion_limit` on both graphs, and a
   300s pytest timeout.

Ticket text reaching a prompt is wrapped by `safety.as_untrusted_data()` in a
`<ticket-data>` fence, with the system prompt stating that instructions inside
it are data. That's defence in depth, not the defence — the real protection is
that a compromised model still can't reach outside the worktree.

## Isolation

```
target-app/                     ← your checkout, never touched
   │ git worktree add -B autodev/T-001
   ▼
.worktrees/T-001/target-app/    ← what the agent is handed
   │
   ├── resolved → commit onto autodev/T-001, worktree kept for review
   └── otherwise → worktree and branch deleted
```

Only committed state crosses over, which is what makes a run reproducible — and
means uncommitted work in your checkout is invisible to the agent. On success the
staged work is **committed** onto the branch, so `git diff HEAD autodev/T-001`
shows the change after the worktree is gone.

The worktree has no `.venv` (gitignored, never committed), so tests run under the
target repo's own interpreter with `cwd` set to the worktree — imports resolve
from `cwd`.

## Memory

`.autodev/memory.json`, a flat list of `{lesson, ticket_id, ticket_type,
evidence}`. Recall scores keyword overlap against the ticket, plus one point for
a matching type. Only runs the tests approved may write.

Observed: T-002 stored *"the update schema uses `Field(default=…)` … causing
omitted fields to be overwritten"*; T-004 recalled it before planning.

`ponytail:` naive keyword scoring — swap in embeddings if the store outgrows a
few hundred lessons.

## Results

| Ticket | Status | Iterations | Why |
|---|---|---|---|
| T-001 | `unproven` | 1 | Added a regression test, which passed — the reported bug doesn't reproduce. |
| T-002 | `resolved` | 1 | Added `TodoUpdate` with optional fields, made `update_todo` skip unset ones, added tests. |
| T-004 | `resolved` | 1 | Added `?q=` title search with `ilike`, combined with the `completed` filter. |
| T-005 | `refused` | 0 | Arbitrary command execution + safeguard-disabling + prompt injection. No worktree, no model call. |

37 platform tests (`uv run pytest autodev_agent`), no model key required.

## Scaling this to production

**Execution.** A git worktree shares the host. Real isolation is a container or
microVM per run with no network except the model endpoint — otherwise
`run_tests` executes whatever the agent just wrote to `conftest.py`. This is the
single largest gap between this and production.

**Concurrency.** Runs are independent, so it's a queue: ticket → worker → branch
→ PR. Worktrees already give per-ticket filesystem separation; a worker pool and
a per-repo lock on branch creation is most of what's missing.

**Durability.** `graph.compile()` takes a `checkpointer`. With Postgres behind
it, a crashed run resumes at its last node instead of restarting, and a
human-in-the-loop `interrupt_before=["act"]` becomes a config change.

**Cost.** `understand` is deliberately LLM-free for this reason. Next levers:
cache the repo map across tickets, and route `plan` to a cheap model with
escalation on the second retry.

**Observability.** `[STAGE]` lines are fine for one operator watching one run.
At scale each node emits a span with token counts and tool calls; the questions
you actually need answered are which tickets burn the whole budget, and which
tools get denied most (that last one is a prompt bug, not an attack).

**Trust.** The agent proposes; it never merges. Every run ends as a branch plus a
report. `unproven` and `refused` are first-class outcomes — an agent that always
claims success is worse than one that admits it found nothing.

## Deliberate omissions

- Only `pytest` — no lint or type-check gate. Add when the target repo has one.
- No parallel tool calls in `act`; the model calls them one at a time.
- `write_file` overwrites whole files. A patch-based tool would use fewer tokens
  on large files but adds a fuzzy-match failure mode; not worth it at this size.
- No retry/backoff around the model API — one transient 429 kills a run.
