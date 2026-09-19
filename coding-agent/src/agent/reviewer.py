from dataclasses import dataclass

from .llm_client import LLMClient
from .prompts import REVIEWER_SYSTEM


@dataclass
class ReviewResult:
    approved: bool
    reason: str


def review_diff(llm: LLMClient, task_description: str, diff: str) -> ReviewResult:
    user_prompt = f"Task: {task_description}\n\nProposed diff:\n{diff}"

    response = llm.call(system=REVIEWER_SYSTEM, user=user_prompt, max_tokens=300)
    text = response.text.strip()

    approved = "VERDICT: APPROVE" in text.upper()
    reason_line = next((l for l in text.splitlines() if l.upper().startswith("REASON:")), "")
    reason = reason_line.split(":", 1)[1].strip() if ":" in reason_line else text

    return ReviewResult(approved=approved, reason=reason)
