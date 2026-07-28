"""Run output: the live `[STAGE]` log, plus a JSON and Markdown report."""

import json
from pathlib import Path


def stage(name: str, message: str = "") -> None:
    """One line of the trace the operator watches while a run happens."""
    print(f"[{name.upper()}] {message}".rstrip(), flush=True)


def build(state: dict) -> dict:
    """The machine-readable result. Mirrors the state, minus the bulky diff."""
    return {
        "ticket_id": state["ticket"].get("id"),
        "ticket_type": state["ticket"].get("type"),
        "status": state["status"],
        "summary": state["summary"],
        "refusal_reasons": state.get("refusal_reasons", []),
        "files_changed": state.get("files_changed", []),
        "tests_passed": state.get("tests_passed", False),
        "iterations": state.get("iteration", 0),
        "max_iterations": state.get("max_iterations", 0),
        "plan": state.get("plan", ""),
        "actions": state.get("actions", []),
        "observations": state.get("observations", []),
        "branch": state.get("branch", ""),
    }


def as_markdown(report: dict, diff: str = "") -> str:
    lines = [
        f"# {report['ticket_id']} -- {report['status'].upper()}",
        "",
        report["summary"],
        "",
        f"- tests passed: {report['tests_passed']}",
        f"- iterations: {report['iterations']}/{report['max_iterations']}",
        f"- branch: {report['branch'] or 'n/a'}",
        "",
    ]
    if report["refusal_reasons"]:
        lines += ["## Refused because", *(f"- {r}" for r in report["refusal_reasons"]), ""]
    if report["files_changed"]:
        lines += ["## Files changed", *(f"- {f}" for f in report["files_changed"]), ""]
    if report["plan"]:
        lines += ["## Plan", report["plan"], ""]
    if diff:
        lines += ["## Diff", "```diff", diff, "```", ""]
    return "\n".join(lines)


def write(repo: Path, report: dict, diff: str = "") -> Path:
    """Save both formats next to the real repo, keyed by ticket id."""
    out = Path(repo).resolve().parent / ".autodev" / "runs"
    out.mkdir(parents=True, exist_ok=True)
    ticket_id = report["ticket_id"] or "unknown"
    (out / f"{ticket_id}.json").write_text(json.dumps(report, indent=2))
    markdown = out / f"{ticket_id}.md"
    markdown.write_text(as_markdown(report, diff))
    return markdown


def summarize(report: dict) -> None:
    """Final console block."""
    stage("result", report["status"].upper())
    print(f"        {report['summary']}")
    for path in report["files_changed"]:
        print(f"        changed: {path}")
