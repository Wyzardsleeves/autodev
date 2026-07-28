"""The agent's capabilities. Every one of them is checked before it acts.

Deliberately no `run_shell_command`. A dedicated `run_tests` is the whole
difference between "the platform decides what may run" and "the model does".
Each method is usable directly by the graph's deterministic nodes and, via
`as_langchain_tools()`, by the model during the act step -- one implementation,
one safety check, two callers.
"""

import subprocess
from pathlib import Path

from langchain_core.tools import tool

from .safety import TEST_TIMEOUT_SECONDS, SafetyError, safe_path

# Tool output goes straight into the next prompt, so it gets a ceiling.
MAX_OUTPUT_CHARS = 20_000
MAX_WRITE_CHARS = 200_000


def _clip(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}\n...[truncated {len(text) - limit} chars]"


class Toolbox:
    """Tools bound to one sandbox directory. Nothing reaches outside it."""

    def __init__(self, sandbox: Path, interpreter: Path | None = None, worktree=None):
        self.sandbox = Path(sandbox).resolve()
        # The worktree has no .venv of its own (it is gitignored, so it never gets
        # copied), so tests run under the target repo's existing interpreter with
        # cwd set to the sandbox -- imports resolve from cwd, not from the venv.
        self.interpreter = Path(interpreter) if interpreter else Path("python3")
        self.worktree = worktree

    # -- read side ---------------------------------------------------------

    def list_files(self) -> str:
        """Tracked files in the sandbox. Tracked-only keeps venvs and caches out."""
        result = self._git("ls-files")
        return _clip(result or "(no tracked files)")

    def read_file(self, path: str) -> str:
        target = safe_path(self.sandbox, path)
        if not target.is_file():
            raise SafetyError(f"not a file: {path}")
        return _clip(target.read_text())

    def search_code(self, query: str) -> str:
        """grep the sandbox for `query`, with file:line prefixes."""
        if not query.strip():
            raise SafetyError("empty search query")
        # Fixed-string search: the model supplies this, and a stray regex
        # metacharacter should not turn into a silent zero-match.
        result = self._git("grep", "-n", "--fixed-strings", "-e", query)
        return _clip(result or f"no matches for {query!r}")

    def get_diff(self) -> str:
        """Everything the agent has changed so far, as a unified diff."""
        if self.worktree is None:
            return "(no worktree; diff unavailable)"
        return _clip(self.worktree.diff() or "(no changes yet)")

    # -- write side --------------------------------------------------------

    def write_file(self, path: str, content: str) -> str:
        target = safe_path(self.sandbox, path, for_write=True)
        if len(content) > MAX_WRITE_CHARS:
            raise SafetyError(f"refusing to write {len(content)} chars to {path}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        return f"wrote {len(content)} chars to {path}"

    # -- verification ------------------------------------------------------

    def run_tests(self) -> tuple[bool, str]:
        """Run the sandbox's suite. Returns (passed, output).

        This is the test gate: the return value comes from pytest's exit code,
        never from the model's opinion about whether the fix worked.
        """
        try:
            result = subprocess.run(
                [str(self.interpreter), "-m", "pytest", "-q"],
                cwd=self.sandbox,
                capture_output=True,
                text=True,
                timeout=TEST_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return False, f"pytest timed out after {TEST_TIMEOUT_SECONDS}s"
        except OSError as err:
            return False, f"could not run pytest: {err}"
        return result.returncode == 0, _clip(result.stdout + result.stderr)

    # -- plumbing ----------------------------------------------------------

    def _git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(self.sandbox), *args],
            capture_output=True,
            text=True,
            check=False,
        )
        # git grep exits 1 on "no matches", which is not an error worth raising.
        return result.stdout.strip()

    def as_langchain_tools(self) -> list:
        """The same methods, wrapped for the model.

        A refused call comes back as a normal tool result rather than an
        exception, so the model can read "denied" and choose something else.
        """

        def guard(func):
            def wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except (SafetyError, OSError) as err:
                    return f"DENIED: {err}"

            return wrapper

        @tool
        def list_files() -> str:
            """List every tracked file in the repository you are working on."""
            return guard(self.list_files)()

        @tool
        def read_file(path: str) -> str:
            """Read one file. `path` must be relative to the repository root."""
            return guard(self.read_file)(path)

        @tool
        def search_code(query: str) -> str:
            """Search the repository for a literal string. Returns file:line matches."""
            return guard(self.search_code)(query)

        @tool
        def write_file(path: str, content: str) -> str:
            """Overwrite a file with `content`. Always read the file first."""
            return guard(self.write_file)(path, content)

        @tool
        def get_diff() -> str:
            """Show the unified diff of every change you have made so far."""
            return guard(self.get_diff)()

        @tool
        def run_tests() -> str:
            """Run the repository's test suite and return the output."""
            passed, output = self.run_tests()
            return f"{'PASSED' if passed else 'FAILED'}\n{output}"

        return [list_files, read_file, search_code, write_file, get_diff, run_tests]
