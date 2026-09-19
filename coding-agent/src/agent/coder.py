from .llm_client import LLMClient
from .prompts import CODER_SYSTEM


def generate_diff(
    llm: LLMClient,
    step_description: str,
    file_contents: dict[str, str],
    previous_error: str | None = None,
) -> str:
    """
    Produce a unified diff for the given step.

    file_contents: {filepath: content} for the files relevant to this step.
    previous_error: stderr/test output from the last failed attempt, if any —
    this is what makes the loop "self-correcting" rather than one-shot.
    """
    files_block = "\n\n".join(
        f"--- {path} ---\n{content}" for path, content in file_contents.items()
    )

    user_prompt = f"Step: {step_description}\n\nFiles:\n{files_block}"

    if previous_error:
        user_prompt += f"\n\nThe previous attempt failed with this output:\n{previous_error}\n\nFix the specific issue described above."

    response = llm.call(system=CODER_SYSTEM, user=user_prompt, max_tokens=4096)
    return response.text.strip()
