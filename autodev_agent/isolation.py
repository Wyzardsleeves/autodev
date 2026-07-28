"""Git worktree isolation. The agent never gets your checkout as its cwd.

    target-app/                 <- yours, untouched
    .worktrees/T-001/           <- disposable copy at HEAD, branch autodev/T-001
        target-app/             <- what the agent is handed

Kept on success so the diff is reviewable, deleted on failure.
"""

import subprocess
from pathlib import Path


class IsolationError(Exception):
    """The worktree could not be created or removed."""


def git(*args: str, cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise IsolationError(f"git {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout


class Worktree:
    """Context manager around one `git worktree`.

    Only files committed to HEAD come across -- that is what makes the copy
    reproducible, and it means uncommitted work in your checkout is invisible
    to the agent. Commit before running.
    """

    def __init__(self, repo: Path, ticket_id: str):
        self.repo = Path(repo).resolve()
        self.ticket_id = ticket_id
        self.toplevel = Path(git("rev-parse", "--show-toplevel", cwd=self.repo).strip())
        # Worktrees are per-repo, so a repo arg pointing at a subdirectory
        # (./target-app inside this repo) has to be re-found inside the copy.
        self.subpath = self.repo.relative_to(self.toplevel)
        self.root = self.toplevel / ".worktrees" / ticket_id
        self.branch = f"autodev/{ticket_id}"
        self.keep = False

    @property
    def path(self) -> Path:
        """Where the agent works: the target repo inside the worktree."""
        return self.root / self.subpath

    def create(self) -> "Worktree":
        if self.root.exists():
            self.remove()
        # -B so a re-run of the same ticket resets the branch instead of failing.
        git("worktree", "add", "-B", self.branch, str(self.root), "HEAD", cwd=self.toplevel)
        return self

    def remove(self) -> None:
        git("worktree", "remove", "--force", str(self.root), cwd=self.toplevel)
        # The branch outlives the worktree, so it needs its own cleanup. A failed
        # delete is not worth aborting over -- the worktree is already gone.
        subprocess.run(
            ["git", "branch", "-D", self.branch],
            cwd=self.toplevel,
            capture_output=True,
            check=False,
        )

    def stage_all(self) -> None:
        """Stage everything under the target subpath, so new files show in the diff."""
        git("add", "-A", "--", str(self.subpath), cwd=self.root)

    def diff(self) -> str:
        self.stage_all()
        return git("diff", "--cached", "HEAD", "--", str(self.subpath), cwd=self.root)

    def commit(self, message: str) -> str:
        """Commit the staged work onto the run's branch, so the diff outlives the
        worktree. Without this the branch stays at HEAD and the work exists only
        as uncommitted files."""
        self.stage_all()
        if not self.files_changed():
            return ""
        git("-c", "user.name=autodev", "-c", "user.email=autodev@local",
            "commit", "-qm", message, cwd=self.root)
        return git("rev-parse", "HEAD", cwd=self.root).strip()

    def files_changed(self) -> list[str]:
        self.stage_all()
        names = git("diff", "--cached", "HEAD", "--name-only", "--", str(self.subpath), cwd=self.root)
        return [line for line in names.splitlines() if line]

    def __enter__(self) -> "Worktree":
        return self.create()

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.keep and exc_type is None:
            return
        self.remove()
