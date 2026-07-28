"""Lessons carried between runs. A JSON file, because that is enough.

Stored beside the real repo (not in the worktree, which gets deleted), so run 2
of a ticket type starts with what run 1 learned:

    run 1: no memory        -> 4 iterations
    run 2: memory retrieved -> 2 iterations
"""

import json
from pathlib import Path

# Keyword overlap, not embeddings. ponytail: naive scoring, swap in embeddings
# if the store ever outgrows a few hundred lessons.
MAX_RECALLED = 5
STOPWORDS = frozenset(
    "the a an is are was were be to of in on for and or not with that this it".split()
)


def store_path(repo: Path) -> Path:
    return Path(repo).resolve().parent / ".autodev" / "memory.json"


def load(repo: Path) -> list[dict]:
    path = store_path(repo)
    if not path.is_file():
        return []
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        # A corrupt store should not take down a run; it just means no memory.
        return []


def _keywords(text: str) -> set[str]:
    words = {word.strip(".,:;()[[]\"'").lower() for word in str(text).split()}
    return {word for word in words if len(word) > 2 and word not in STOPWORDS}


def recall(repo: Path, ticket: dict) -> list[str]:
    """Lessons worth putting in the prompt, most relevant first."""
    ticket_words = _keywords(f"{ticket.get('title', '')} {ticket.get('description', '')}")
    scored = []
    for entry in load(repo):
        # Same ticket type is a weak signal, shared vocabulary a stronger one.
        overlap = len(ticket_words & _keywords(entry.get("lesson", "")))
        score = overlap + (1 if entry.get("ticket_type") == ticket.get("type") else 0)
        if score:
            scored.append((score, entry["lesson"]))
    scored.sort(key=lambda pair: -pair[0])
    return [lesson for _, lesson in scored[:MAX_RECALLED]]


def remember(repo: Path, lesson: str, ticket: dict, evidence: str) -> None:
    """Append one lesson. Only ever called after a run the tests approved."""
    if not lesson.strip():
        return
    entries = load(repo)
    if any(entry.get("lesson") == lesson for entry in entries):
        return
    entries.append(
        {
            "lesson": lesson,
            "ticket_id": ticket.get("id"),
            "ticket_type": ticket.get("type"),
            "evidence": evidence,
        }
    )
    path = store_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2))
