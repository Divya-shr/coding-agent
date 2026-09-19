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


def apply_diff(repo_path: str, diff_text: str) -> tuple[bool, str]:
    """
    Apply a unified diff to a repo on disk using `git apply`.
    Returns (success, error_message).
    """
    import subprocess
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".diff", delete=False) as f:
        f.write(diff_text)
        diff_path = f.name

    result = subprocess.run(
        ["git", "apply", "--whitespace=fix", diff_path],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    os.unlink(diff_path)

    if result.returncode != 0:
        return False, result.stderr
    return True, ""
