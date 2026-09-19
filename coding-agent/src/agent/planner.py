from .llm_client import LLMClient
from .prompts import PLANNER_SYSTEM


def plan_task(llm: LLMClient, task_description: str, repo_summary: str) -> list[str]:
    """
    Break a task into ordered steps.

    repo_summary should be a short description of relevant files/structure —
    not the whole repo. Keep it small; this is Week 2 scope, so a naive
    "list of file names + task" is fine to start.
    """
    user_prompt = f"""Task: {task_description}

Repository context:
{repo_summary}

Break this into concrete steps."""

    response = llm.call(system=PLANNER_SYSTEM, user=user_prompt)

    # Parse numbered list into a clean list of strings.
    steps = []
    for line in response.text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        # strip leading "1. " / "1) " / "- " style prefixes
        for sep in [". ", ") "]:
            if sep in line[:4]:
                line = line.split(sep, 1)[1]
                break
        steps.append(line.lstrip("- ").strip())

    return steps
