import difflib
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

from .coder import generate_fixed_file
from .llm_client import LLMClient
from .planner import plan_task
from .reviewer import review_diff
from ..sandbox.docker_runner import DockerRunner

load_dotenv()

MAX_ITERATIONS = int(os.environ.get("MAX_ITERATIONS", 5))


@dataclass
class AgentResult:
    success: bool
    iterations_used: int
    final_output: str
    diffs_tried: list = field(default_factory=list)
    tokens: dict = field(default_factory=dict)


def read_repo_files(repo_path, filenames):
    contents = {}
    for name in filenames:
        path = os.path.join(repo_path, name)
        if os.path.exists(path):
            with open(path) as f:
                contents[name] = f.read()
    return contents


def pick_target_file(relevant_files):
    for f in relevant_files:
        if not os.path.basename(f).startswith("test_"):
            return f
    return relevant_files[0]


def compute_diff(old_content, new_content, filename):
    diff_lines = difflib.unified_diff(
        old_content.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
    )
    return "".join(diff_lines)


def run_agent(task_description, repo_path, test_command, relevant_files, use_planner=False, use_reviewer=False):
    llm = LLMClient()
    sandbox = DockerRunner()

    diffs_tried = []
    previous_error = None
    target_file = pick_target_file(relevant_files)

    steps = [task_description]
    if use_planner:
        repo_summary = "\n".join(relevant_files)
        steps = plan_task(llm, task_description, repo_summary)

    for iteration in range(1, MAX_ITERATIONS + 1):
        step = steps[0] if steps else task_description

        file_contents = read_repo_files(repo_path, [target_file])
        old_content = file_contents.get(target_file, "")

        new_content = generate_fixed_file(llm, step, target_file, old_content, previous_error)
        diff_for_log = compute_diff(old_content, new_content, target_file)
        diffs_tried.append(diff_for_log)

        if use_reviewer:
            review = review_diff(llm, task_description, diff_for_log)
            if not review.approved:
                previous_error = f"Reviewer rejected this change: {review.reason}"
                continue

        target_path = os.path.join(repo_path, target_file)
        with open(target_path, "w", newline="\n") as f:
            f.write(new_content)

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