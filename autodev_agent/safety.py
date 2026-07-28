"""Hard boundaries. The LLM may *request* anything; nothing here trusts it.

The rule this module exists to enforce: a tool call is checked by the platform,
not by the model. If the model asks to read ~/.ssh/id_rsa, the answer is no --
no matter how convincingly the ticket asked for it.
"""

import re
from pathlib import Path

# Budget. Every plan -> act -> verify lap counts as one iteration.
MAX_ITERATIONS = 5
# Wall-clock ceiling for a test run, so a hung pytest can't hang the agent.
TEST_TIMEOUT_SECONDS = 300

# Never writable, even inside the agent's own worktree: its own escape hatches.
PROTECTED_DIRS = frozenset({".git", ".venv", ".autodev", ".worktrees", "__pycache__"})
PROTECTED_SUFFIXES = (".db", ".pyc", ".env")

# Ticket text is data, not instructions. A match means "refuse the ticket" rather
# than "sanitize and continue" -- a ticket asking for a shell-exec endpoint is a
# bad feature request whether or not it is also a prompt injection.
UNSAFE_TICKET_PATTERNS = (
    (r"arbitrary\s+\w*\s*command", "asks for arbitrary command execution"),
    (r"\b(exec|eval|subprocess|os\.system)\b.{0,40}\b(user|request|input|param)", "asks to execute caller-supplied code"),
    (r"\brm\s+-rf\b|\bdelete\s+(all|every)\b|\bwipe\b|\bdrop\s+(the\s+)?(database|table)\b", "asks for destructive deletion"),
    (r"(disable|bypass|skip|turn\s+off)\b.{0,25}(safety|validation|auth|check|test|sandbox)", "asks to disable a safeguard"),
    (r"ignore\s+(all\s+|your\s+|previous\s+|prior\s+)*(instructions|rules|prompt)", "contains prompt injection"),
    (r"\.ssh|id_rsa|private\s+key|\bcredentials?\b|\bsecrets?\b|api[_\s-]?key", "asks to touch credentials"),
    (r"\b(curl|wget|https?)\b.{0,40}(post|upload|exfil|send)", "asks to send data off the machine"),
    (r"\bsudo\b|\bchmod\s+777\b|/etc/passwd", "asks for privileged host access"),
)


class SafetyError(Exception):
    """A requested action was refused. Surfaced to the model as a tool result."""


def safe_path(sandbox: Path, requested: str, *, for_write: bool = False) -> Path:
    """Resolve `requested` inside `sandbox`, or raise SafetyError.

    Resolution happens before the containment check, so a symlink pointing out
    of the sandbox is caught the same way a literal `../../..` is.
    """
    if not str(requested).strip():
        raise SafetyError("empty path")
    # Joining an absolute path silently discards the sandbox, so it is a hard no.
    if Path(requested).is_absolute():
        raise SafetyError(f"absolute paths are not allowed: {requested}")

    root = Path(sandbox).resolve()
    target = (root / requested).resolve()
    if target != root and root not in target.parents:
        raise SafetyError(f"path escapes the sandbox: {requested}")

    relative = target.relative_to(root)
    if PROTECTED_DIRS.intersection(relative.parts):
        raise SafetyError(f"protected location: {requested}")
    if for_write and target.name.endswith(PROTECTED_SUFFIXES):
        raise SafetyError(f"protected file type: {requested}")
    return target


def ticket_refusals(ticket: dict) -> list[str]:
    """Reasons this ticket should not be worked on. Empty list means proceed."""
    if not isinstance(ticket, dict):
        return ["ticket is not a JSON object"]

    reasons = []
    if not str(ticket.get("id", "")).strip():
        reasons.append("ticket has no id")
    if not str(ticket.get("title", "")).strip():
        reasons.append("ticket has no title")

    # Scanned as one blob: splitting a request across title and description
    # shouldn't get it past the check.
    text = " ".join(str(value) for value in ticket.values()).lower()
    for pattern, reason in UNSAFE_TICKET_PATTERNS:
        if re.search(pattern, text):
            reasons.append(reason)
    return reasons


def as_untrusted_data(ticket: dict) -> str:
    """Render a ticket for a prompt, fenced so its text reads as data.

    Cheap but real: the fence plus the surrounding instruction is what lets the
    model tell "the ticket says X" apart from "you have been told to do X".
    """
    body = "\n".join(f"{key}: {value}" for key, value in ticket.items())
    return f"<ticket-data>\n{body}\n</ticket-data>"
