# Self-Correcting Coding Agent

An autonomous coding agent that takes a task ("fix this bug," "make this failing test pass"), plans it, rewrites the affected file, runs the real test suite in an isolated Docker sandbox, and — if it fails — reads the actual error and retries. Exposed as an MCP server so external AI clients (like Claude Desktop) can call it as a tool directly.

## Results

Benchmarked against a 4-task suite covering distinct bug types (off-by-one error, wrong comparison operator, missing return statement, incorrect operator):

| Metric | Result |
|---|---|
| Success rate | **100% (4/4)** |
| Avg. iterations to fix | **1.0** |
| Architecture | Planner → Coder → Reviewer → Sandbox |

Full run logs: [`eval/results/v2_fullfile.json`](eval/results/v2_fullfile.json)

> Note: this is a small, controlled benchmark meant to prove the architecture works end-to-end, not a claim of real-world SWE-bench-level performance. Next step is testing against a larger, messier benchmark.

## Architecture

```
                 ┌─────────────┐
   task  ──────▶ │   Planner   │  breaks task into steps
                 └──────┬──────┘
                        ▼
                 ┌─────────────┐
                 │    Coder    │  rewrites the full corrected file
                 └──────┬──────┘  (not a diff — see "Design decisions")
                        ▼
                 ┌─────────────┐
                 │  Reviewer   │  approves or rejects the change
                 └──────┬──────┘  before it's ever written to disk
                        ▼
                 ┌──────────────┐
                 │   Sandbox    │  Docker, no network, memory-capped
                 │ (real tests) │  runs the actual test suite
                 └──────┬───────┘
                        │ pass ──▶ done
                        │ fail ──▶ real error fed back to Coder, retry
                        ▼
                  (up to N iterations)
```

All of the above is also exposed as MCP tools (`run_task`, `run_tests`), so any MCP-compatible client — Claude Desktop, Claude Code, etc. — can drive the agent directly instead of a human running a script.

## Design decisions worth knowing

**Full-file rewrite instead of diff-based patching.** The first version had the Coder emit a unified diff, applied via `git apply`. In practice, the model's diff output was inconsistent enough (missing `+++` headers, malformed context lines, Windows CRLF mismatches) that diff application became the most fragile part of the system. Switching the Coder to return the complete corrected file — with a diff computed afterward via `difflib`, purely for logging and review — eliminated an entire class of failures and is the main reason the eval success rate went from inconsistent to 100%.

**Three separated LLM roles, not one prompt.** A single prompt tends to rubber-stamp its own output. Splitting Planner / Coder / Reviewer into distinct calls with narrow responsibilities makes the Reviewer step actually catch bad changes, and makes failures debuggable — you can tell exactly which stage broke.

**Network-isolated sandbox with a pre-baked image.** The sandbox runs with `network_disabled=True` and a memory cap, since it's executing LLM-generated code. Rather than allowing runtime `pip install` (which would require network access, defeating the isolation), a custom Docker image (`sandbox.Dockerfile`) has test dependencies pre-installed.

## Tech stack

- **Python** — core agent logic
- **Google Gemini API** (`google-genai`) — Planner / Coder / Reviewer, behind a swappable `LLMClient` abstraction (originally built against Claude's API)
- **Docker** — isolated, network-disabled sandbox execution
- **MCP (Model Context Protocol)** — exposes the agent as tools for external AI clients
- **pytest** — target test framework for the benchmark tasks

## Project structure

```
coding-agent/
├── src/
│   ├── agent/
│   │   ├── loop.py          # orchestration: planner → coder → sandbox → reviewer
│   │   ├── planner.py       # breaks a task into steps
│   │   ├── coder.py         # generates the full corrected file
│   │   ├── reviewer.py      # approves/rejects a change before it's written
│   │   ├── llm_client.py    # Gemini API wrapper with retry/backoff
│   │   └── prompts.py       # system prompts per role
│   ├── sandbox/
│   │   └── docker_runner.py # isolated, network-disabled test execution
│   └── mcp_server/
│       └── server.py        # exposes run_task / run_tests as MCP tools
├── eval/
│   ├── harness.py           # runs the agent across eval/tasks/*.json, scores results
│   ├── tasks/                # benchmark task definitions
│   └── results/              # eval run logs (success rate, iterations, tokens)
├── setup_eval_tasks.py       # (re)creates all benchmark task repos from scratch
├── sandbox.Dockerfile        # pre-baked sandbox image with test deps installed
└── requirements.txt
```

## Setup

```bash
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env            # add your GEMINI_API_KEY

docker build -t coding-agent-sandbox:latest -f sandbox.Dockerfile .

python setup_eval_tasks.py
python eval/harness.py --run-name my_run
```

### Connect it to Claude Desktop (MCP)

Add to your Claude Desktop config (Settings → Developer → Edit config):
```json
{
  "mcpServers": {
    "coding-agent": {
      "command": "/absolute/path/to/coding-agent/venv/Scripts/python.exe",
      "args": ["/absolute/path/to/coding-agent/src/mcp_server/server.py"]
    }
  }
}
```
Restart Claude Desktop, then ask it to use the `coding-agent` tool with a `task_description`, `repo_path`, `test_command`, and `relevant_files`.

## What's not finished

- Benchmark is currently small (4 tasks) and synthetic — real-world bugs are messier and often span multiple files
- Single-file-edit heuristic (`pick_target_file`) doesn't yet support multi-file changes
- No cost-per-run tracking beyond raw token counts
- MCP server currently supports two tools (`run_task`, `run_tests`); more (e.g. `get_diff`, `list_tasks`) would make it more useful as a general-purpose tool for other agents

## License

MIT
