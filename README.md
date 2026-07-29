# AutoDev

An autonomous coding agent. Give it a ticket and a repo; it plans, edits, runs
the tests, retries on failure, and reports what it can actually prove.

Architecture and design decisions: [DESIGN.md](DESIGN.md).

## Setup

[Here's](https://docs.google.com/document/d/1BuZPRsvsxsYnMR3C6s1WK7SkfGMwWdo5GmvSrdmOlkM/edit?usp=sharing) is a temporary Deepseek Key that can be used.

```bash
uv sync
echo 'DEEPSEEK_API_KEY=sk-...' > .env    # DEEPSEEK_KEY also accepted
```

## Run

```bash
uv run autodev run --ticket tickets/T-001.json --repo ./target-app
```

Or `source .venv/bin/activate` once, then plain `autodev run --ticket ...`.

Commit your target repo first — the agent works from a `git worktree` at `HEAD`,
so uncommitted changes are invisible to it.

Exit code is `0` only for `resolved`, so CI can gate on it.

## What a run looks like

```
[ISOLATE]    .worktrees/T-002/target-app on autodev/T-002
[CLASSIFY]   bug, actionable
[RECALL]     1 relevant lesson(s)
[UNDERSTAND] baseline suite passes
[PLAN]       iteration 1/5
[ACT]        editing files>
             read_file(app/schemas/todo_schema.py)
             write_file(tests/test_todos.py, ...)
[VERIFY]     28 passed in 0.66s
[LEARN]      The update schema uses Field(default=...) for optional fields...
[RESULT]     RESOLVED
             changed: target-app/app/schemas/todo_schema.py
```

Reports land in `.autodev/runs/<ticket>.{json,md}`; lessons in
`.autodev/memory.json`. A resolved run leaves a commit on `autodev/<ticket>`:

```bash
git diff HEAD autodev/T-002
```

Anything else deletes its worktree and branch.

## Outcomes

`resolved` · `unproven` (tests green but nothing was proven) · `no_change` ·
`failed` (budget exhausted) · `refused` (unsafe ticket, never started)

## Tests

```bash
uv run pytest autodev_agent     # 37 platform tests, no model key needed
```

The target app has its own suite, which is what the agent is graded against:

```bash
cd target-app && .venv/bin/python -m pytest -q
```

## Layout

```
autodev_agent/
  index.py       CLI (argparse)
  agent.py       AgentState, the LangGraph, verdict rules
  tools.py       list_files read_file search_code write_file get_diff run_tests
  safety.py      path sandbox, ticket validation, budgets
  isolation.py   git worktree per ticket
  memory.py      lessons across runs
  reporting.py   [STAGE] log, JSON + Markdown reports
tickets/         T-001..T-005
target-app/      the FastAPI todo app under repair
```
