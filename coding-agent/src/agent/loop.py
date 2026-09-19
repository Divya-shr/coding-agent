"""
Core agent loop: planner -> coder -> sandbox -> reviewer, with self-correction.

Week 1 scope: get single-step coder -> sandbox -> retry-on-failure working
end to end on ONE hand-picked task before adding planner/reviewer (Week 2).

Usage (once wired up):
    result = run_agent(
        task_description="Fix the failing test in test_math.py",
        repo_path="./sample_repo",
        test_command="pytest -q",
    )
"""
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

from .coder import generate_diff
from .llm_client import LLMClient
from .planner import plan_task
from .reviewer import review_diff
from ..sandbox.docker_runner import DockerRunner, apply_diff

load_dotenv()

MAX_ITERATIONS = int(os.environ.get("MAX_ITERATIONS", 5))


@dataclass
class AgentResult:
    success: bool
    iterations_used: int
    final_output: str
    diffs_tried: list[str] = field(default_factory=list)
    tokens: dict = field(default_factory=dict)


def read_repo_files(repo_path: str, filenames: list[str]) -> dict[str, str]:
    contents = {}
    for name in filenames:
        path = os.path.join(repo_path, name)
        if os.path.exists(path):
            with open(path) as f:
                contents[name] = f.read()
    return contents


def run_agent(
    task_description: str,
    repo_path: str,
    test_command: str,
    relevant_files: list[str],
    use_planner: bool = False,
    use_reviewer: bool = False,
) -> AgentResult:
    """
    Week 1: call with use_planner=False, use_reviewer=False for the simplest
    coder -> sandbox -> retry loop. Turn the flags on as you build Week 2.
    """
    llm = LLMClient()
    sandbox = DockerRunner()

    diffs_tried = []
    previous_error = None

    steps = [task_description]
    if use_planner:
        repo_summary = "\n".join(relevant_files)
        steps = plan_task(llm, task_description, repo_summary)

    for iteration in range(1, MAX_ITERATIONS + 1):
        step = steps[0] if steps else task_description  # Week 1: single-step; extend for multi-step

        file_contents = read_repo_files(repo_path, relevant_files)
        diff = generate_diff(llm, step, file_contents, previous_error)
        diffs_tried.append(diff)

        if use_reviewer:
            review = review_diff(llm, task_description, diff)
            if not review.approved:
                previous_error = f"Reviewer rejected this diff: {review.reason}"
                continue  # skip applying, let coder try again next iteration

        applied, apply_error = apply_diff(repo_path, diff)
        if not applied:
            previous_error = f"Diff failed to apply: {apply_error}"
            continue

        run_result = sandbox.run(repo_path, test_command)

        if run_result.exit_code == 0:
            return AgentResult(
                success=True,
                iterations_used=iteration,
                final_output=run_result.stdout,
                diffs_tried=diffs_tried,
                tokens=llm.total_tokens(),
            )

        previous_error = run_result.stdout

    return AgentResult(
        success=False,
        iterations_used=MAX_ITERATIONS,
        final_output=previous_error or "unknown failure",
        diffs_tried=diffs_tried,
        tokens=llm.total_tokens(),
    )
