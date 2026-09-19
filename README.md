## Self-Correcting Coding Agent



An autonomous coding agent that takes a task ("fix this bug," "make this failing test pass"), plans it, rewrites the affected file, runs the real test suite in an isolated Docker sandbox, and — if it fails — reads the actual error and retries. Exposed as an MCP server so external AI clients (like Claude Desktop) can call it as a tool directly.



## Results



Benchmarked against a 4-task suite covering distinct bug types (off-by-one error, wrong comparison operator, missing return statement, incorrect operator):



| Metric | Result |

|---|---|

| Success rate | \*\*100% (4/4)\*\* |

| Avg. iterations to fix | \*\*1.0\*\* |

| Architecture | Planner → Coder → Reviewer → Sandbox |



Full run logs: \[`eval/results/v2\_fullfile.json`](eval/results/v2\_fullfile.json)



> Note: this is a small, controlled benchmark meant to prove the architecture works end-to-end, not a claim of real-world SWE-bench-level performance. Next step is testing against a larger, messier benchmark.



## Architecture



```

&#x20;                ┌─────────────┐

&#x20;  task  ──────▶ │   Planner   │  breaks task into steps

&#x20;                └──────┬──────┘

&#x20;                       ▼

&#x20;                ┌─────────────┐

&#x20;                │    Coder    │  rewrites the full corrected file

&#x20;                └──────┬──────┘  (not a diff — see "Design decisions")

&#x20;                       ▼

&#x20;                ┌─────────────┐

&#x20;                │  Reviewer   │  approves or rejects the change

&#x20;                └──────┬──────┘  before it's ever written to disk

&#x20;                       ▼

&#x20;                ┌──────────────┐

&#x20;                │   Sandbox    │  Docker, no network, memory-capped

&#x20;                │ (real tests) │  runs the actual test suite

&#x20;                └──────┬───────┘

&#x20;                       │ pass ──▶ done

&#x20;                       │ fail ──▶ real error fed back to Coder, retry

&#x20;                       ▼

&#x20;                 (up to N iterations)

```



All of the above is also exposed as MCP tools (`run\_task`, `run\_tests`), so any MCP-compatible client — Claude Desktop, Claude Code, etc. — can drive the agent directly instead of a human running a script.



## Design decisions worth knowing



\*\*Full-file rewrite instead of diff-based patching.\*\* The first version had the Coder emit a unified diff, applied via `git apply`. In practice, the model's diff output was inconsistent enough (missing `+++` headers, malformed context lines, Windows CRLF mismatches) that diff application became the most fragile part of the system. Switching the Coder to return the complete corrected file — with a diff computed afterward via `difflib`, purely for logging and review — eliminated an entire class of failures and is the main reason the eval success rate went from inconsistent to 100%.



\*\*Three separated LLM roles, not one prompt.\*\* A single prompt tends to rubber-stamp its own output. Splitting Planner / Coder / Reviewer into distinct calls with narrow responsibilities makes the Reviewer step actually catch bad changes, and makes failures debuggable — you can tell exactly which stage broke.



\*\*Network-isolated sandbox with a pre-baked image.\*\* The sandbox runs with `network\_disabled=True` and a memory cap, since it's executing LLM-generated code. Rather than allowing runtime `pip install` (which would require network access, defeating the isolation), a custom Docker image (`sandbox.Dockerfile`) has test dependencies pre-installed.



## Tech stack



 \*\*Python\*\* — core agent logic

\*\*Google Gemini API\*\* (`google-genai`) — Planner / Coder / Reviewer, behind a swappable `LLMClient` abstraction (originally built against Claude's API)

\*\*Docker\*\* — isolated, network-disabled sandbox execution

 \*\*MCP (Model Context Protocol)\*\* — exposes the agent as tools for external AI clients

\*\*pytest\*\* — target test framework for the benchmark tasks



## Project structure



```

coding-agent/

├── src/

│   ├── agent/

│   │   ├── loop.py          # orchestration: planner → coder → sandbox → reviewer

│   │   ├── planner.py       # breaks a task into steps

│   │   ├── coder.py         # generates the full corrected file

│   │   ├── reviewer.py      # approves/rejects a change before it's written

│   │   ├── llm\_client.py    # Gemini API wrapper with retry/backoff

│   │   └── prompts.py       # system prompts per role

│   ├── sandbox/

│   │   └── docker\_runner.py # isolated, network-disabled test execution

│   └── mcp\_server/

│       └── server.py        # exposes run\_task / run\_tests as MCP tools

├── eval/

│   ├── harness.py           # runs the agent across eval/tasks/\*.json, scores results

│   ├── tasks/                # benchmark task definitions

│   └── results/              # eval run logs (success rate, iterations, tokens)

├── setup\_eval\_tasks.py       # (re)creates all benchmark task repos from scratch

├── sandbox.Dockerfile        # pre-baked sandbox image with test deps installed

└── requirements.txt

```



## Setup



```bash

python -m venv venv

source venv/bin/activate       # Windows: venv\\Scripts\\Activate.ps1

pip install -r requirements.txt

cp .env.example .env            # add your GEMINI\_API\_KEY



docker build -t coding-agent-sandbox:latest -f sandbox.Dockerfile .



python setup\_eval\_tasks.py

python eval/harness.py --run-name my\_run

```



### Connect it to Claude Desktop (MCP)



Add to your Claude Desktop config (Settings → Developer → Edit config):

```json

{

&#x20; "mcpServers": {

&#x20;   "coding-agent": {

&#x20;     "command": "/absolute/path/to/coding-agent/venv/Scripts/python.exe",

&#x20;     "args": \["/absolute/path/to/coding-agent/src/mcp\_server/server.py"]

&#x20;   }

&#x20; }

}

```

Restart Claude Desktop, then ask it to use the `coding-agent` tool with a `task\_description`, `repo\_path`, `test\_command`, and `relevant\_files`.



## What's not finished



\- Benchmark is currently small (4 tasks) and synthetic — real-world bugs are messier and often span multiple files

\- Single-file-edit heuristic (`pick\_target\_file`) doesn't yet support multi-file changes

\- No cost-per-run tracking beyond raw token counts

\- MCP server currently supports two tools (`run\_task`, `run\_tests`); more (e.g. `get\_diff`, `list\_tasks`) would make it more useful as a general-purpose tool for other agents



## License



MIT

