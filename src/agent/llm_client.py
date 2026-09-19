"""
Thin wrapper around the Gemini API (google-genai SDK).

Keeping this separate from planner/coder/reviewer means you can swap models,
add retries, or add caching in exactly one place. Also makes it trivial to
log every call for the eval harness (tokens, latency, cost).

Every other file in the agent (coder.py, planner.py, reviewer.py, loop.py)
calls llm.call(system=..., user=...) and reads response.text — none of them
know or care that the model underneath is Gemini instead of Claude.
"""
import os
import time
from dataclasses import dataclass

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

MODEL = os.environ.get("AGENT_MODEL", "gemini-2.5-flash")


@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    latency_seconds: float


class LLMClient:
    def __init__(self):
        # Picks up GEMINI_API_KEY from env. If you set GOOGLE_API_KEY instead,
        # the client also reads that automatically — either name works.
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        self.client = genai.Client(api_key=api_key)
        self.call_log: list[dict] = []  # every call recorded here for eval/cost tracking

    def call(self, system: str, user: str, max_tokens: int = 4096) -> LLMResponse:
        start = time.time()
        response = self.client.models.generate_content(
            model=MODEL,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=max_tokens,
            ),
        )
        latency = time.time() - start

        text = response.text or ""

        # Gemini reports token counts via usage_metadata.
        usage = response.usage_metadata
        input_tokens = usage.prompt_token_count if usage else 0
        output_tokens = usage.candidates_token_count if usage else 0

        result = LLMResponse(
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_seconds=latency,
        )

        # Log every call — this is what your eval harness and cost tracking read from later.
        self.call_log.append({
            "role_context": system[:60],
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "latency_seconds": round(latency, 2),
        })

        return result

    def total_tokens(self) -> dict:
        return {
            "input": sum(c["input_tokens"] for c in self.call_log),
            "output": sum(c["output_tokens"] for c in self.call_log),
            "calls": len(self.call_log),
        }
