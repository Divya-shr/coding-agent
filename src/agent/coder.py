from .llm_client import LLMClient
from .prompts import CODER_SYSTEM


def generate_fixed_file(
    llm: LLMClient,
    step_description: str,
    target_file: str,
    target_file_content: str,
    previous_error: str | None = None,
) -> str:
    """
    Ask the model for the COMPLETE corrected content of target_file.
    """
    user_prompt = f"Step: {step_description}\n\nFile: {target_file}\n\nCurrent content:\n{target_file_content}"

    if previous_error:
        user_prompt += f"\n\nThe previous attempt failed with this output:\n{previous_error}\n\nFix the specific issue described above."

    response = llm.call(system=CODER_SYSTEM, user=user_prompt, max_tokens=4096)
    text = response.text.strip()

    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

    return text + "\n"