"""
Exposes the coding agent as MCP tools so any MCP client (Claude Desktop,
Claude Code, etc.) can drive it directly.

Week 2 target. Start with `run_task` — the others are conveniences that
make the agent inspectable/debuggable from the client side.

Run with: python -m src.mcp_server.server
"""
from mcp.server.fastmcp import FastMCP

from ..agent.loop import run_agent
from ..sandbox.docker_runner import DockerRunner

mcp = FastMCP("coding-agent")


@mcp.tool()
def run_task(task_description: str, repo_path: str, test_command: str, relevant_files: list[str]) -> dict:
    """
    Run the coding agent on a task against a local repo. Returns success,
    number of iterations used, and the final test output.
    """
    result = run_agent(
        task_description=task_description,
        repo_path=repo_path,
        test_command=test_command,
        relevant_files=relevant_files,
        use_planner=True,
        use_reviewer=True,
    )
    return {
        "success": result.success,
        "iterations_used": result.iterations_used,
        "final_output": result.final_output,
        "tokens": result.tokens,
    }


@mcp.tool()
def run_tests(repo_path: str, test_command: str) -> dict:
    """Run a test command in the sandbox and return the raw result — useful for debugging."""
    sandbox = DockerRunner()
    result = sandbox.run(repo_path, test_command)
    return {"exit_code": result.exit_code, "output": result.stdout}


if __name__ == "__main__":
    mcp.run()
