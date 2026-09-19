"""
Runs code/tests inside an isolated Docker container and captures the result.

This is what makes the agent "self-correcting": instead of trusting its own
code, it actually executes it and feeds the real stdout/stderr back in.
Never run agent-generated code directly on your host machine.
"""
import os
from dataclasses import dataclass

import docker

SANDBOX_TIMEOUT = int(os.environ.get("SANDBOX_TIMEOUT_SECONDS", 60))
DEFAULT_IMAGE = "coding-agent-sandbox:latest"  # swap per-task if the repo needs something else


@dataclass
class RunResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool


class DockerRunner:
    def __init__(self, image: str = DEFAULT_IMAGE):
        self.client = docker.from_env()
        self.image = image

    def run(self, repo_path: str, command: str) -> RunResult:
        """
        Mount `repo_path` read-write into a fresh container and run `command`
        inside it (e.g. "pytest -q", "python main.py").
        """
        try:
            container = self.client.containers.run(
                self.image,
                command=["sh", "-c", command],
                volumes={os.path.abspath(repo_path): {"bind": "/workspace", "mode": "rw"}},
                working_dir="/workspace",
                network_disabled=True,   # no network access from inside the sandbox
                mem_limit="512m",
                detach=True,
            )
            try:
                result = container.wait(timeout=SANDBOX_TIMEOUT)
                exit_code = result.get("StatusCode", 1)
                logs = container.logs(stdout=True, stderr=True).decode(errors="replace")
                timed_out = False
            except Exception:
                container.kill()
                exit_code = -1
                logs = "TIMEOUT: sandbox exceeded time limit"
                timed_out = True
            finally:
                container.remove(force=True)

            return RunResult(exit_code=exit_code, stdout=logs, stderr="", timed_out=timed_out)

        except docker.errors.APIError as e:
            return RunResult(exit_code=-1, stdout="", stderr=str(e), timed_out=False)


def _normalize_diff_headers(diff_text: str) -> str:
    """
    Models frequently produce '--- file.py' / '+++ file.py' instead of the
    'a/file.py' / 'b/file.py' prefixes git expects. Normalize so git apply
    doesn't reject an otherwise-correct diff over a cosmetic header issue.
    """
    lines = diff_text.splitlines()
    fixed = []
    for line in lines:
        if line.startswith("--- ") and not line.startswith("--- a/"):
            path = line[4:].strip()
            line = f"--- a/{path}"
        elif line.startswith("+++ ") and not line.startswith("+++ b/"):
            path = line[4:].strip()
            line = f"+++ b/{path}"
        fixed.append(line)
    return "\n".join(fixed) + "\n"


def apply_diff(repo_path: str, diff_text: str) -> tuple[bool, str]:
    """
    Apply a unified diff to a repo on disk using `git apply`.
    Returns (success, error_message).
    """
    import subprocess
    import tempfile

    # Strip accidental markdown fences some models add despite instructions not to.
    diff_text = diff_text.strip()
    if diff_text.startswith("```"):
        diff_text = "\n".join(diff_text.splitlines()[1:])
    if diff_text.endswith("```"):
        diff_text = "\n".join(diff_text.splitlines()[:-1])

    diff_text = _normalize_diff_headers(diff_text)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".diff", delete=False) as f:
        f.write(diff_text)
        diff_path = f.name

    # --unidiff-zero tolerates diffs with imprecise context/line numbers,
    # which smaller/faster models are more prone to producing.
    result = subprocess.run(
        ["git", "apply", "--whitespace=fix", "--unidiff-zero", diff_path],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        # Retry without --unidiff-zero in case that flag itself was the issue.
        result2 = subprocess.run(
            ["git", "apply", "--whitespace=fix", diff_path],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        if result2.returncode == 0:
            os.unlink(diff_path)
            return True, ""

        # Windows often converts LF -> CRLF on checkout, which breaks git apply's
        # strict context-line matching even when the actual change is correct.
        # This pass ignores whitespace/line-ending differences entirely.
        result3 = subprocess.run(
            ["git", "apply", "--whitespace=fix", "--ignore-whitespace", diff_path],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        os.unlink(diff_path)
        if result3.returncode != 0:
            return False, result3.stderr or result2.stderr or result.stderr
        return True, ""

    os.unlink(diff_path)
    return True, ""
