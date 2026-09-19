# Self-Correcting Coding Agent

An autonomous coding agent that takes a task ("fix this bug", "add this feature",
"make this test pass"), plans, writes code, runs it in a sandbox, reads errors,
and self-corrects — with multi-agent review, MCP tool exposure, and a real
eval harness to prove it works.

## Why this project

Most "AI chatbot" portfolio projects prove you can call an API. This one proves
you understand **agentic loops, tool orchestration, multi-agent handoffs, and
how to measure whether an agent actually works** — the parts companies are
currently hiring for.

## Architecture

```
                 ┌─────────────┐
   task  ──────▶ │   Planner   │  breaks task into steps
                 └──────┬──────┘
                        ▼
                 ┌─────────────┐      ┌──────────────┐
                 │    Coder    │─────▶│   Sandbox    │  Docker: run code/tests
                 └──────┬──────┘◀─────│  (isolated)  │
                        │  error/output └──────────────┘
                        ▼
                 ┌─────────────┐
                 │  Reviewer   │  approves diff or sends back to Coder
                 └──────┬──────┘
                        ▼
                 patch applied / task marked done or failed

   All of the above exposed as MCP tools ─▶ any MCP client can drive it
   Every run logged ─▶ eval harness scores success rate, iterations, cost
```

## Repo structure

```
coding-agent/
├── src/
│   ├── agent/
│   │   ├── loop.py          # orchestration: planner → coder → sandbox → reviewer
│   │   ├── planner.py       # breaks a task into steps
│   │   ├── coder.py         # writes/edits code, produces diffs
│   │   ├── reviewer.py      # critiques a diff before it's applied
│   │   ├── llm_client.py    # thin wrapper around Claude API calls
│   │   └── prompts.py       # system prompts for each role
│   ├── sandbox/
│   │   └── docker_runner.py # runs code/tests in an isolated container, captures output
│   └── mcp_server/
│       └── server.py        # exposes agent tools (run_task, run_tests, read_file...) via MCP
├── eval/
│   ├── harness.py           # runs the agent against eval/tasks/*.json, scores results
│   ├── tasks/                # your benchmark: 15-30 real bug-fix/feature tasks
│   └── results/              # JSON logs of each eval run, for tracking regressions
├── logs/                     # per-run traces (tool calls, tokens, latency)
├── requirements.txt
└── .env.example
```

## Week-by-week plan

### Week 1 — Core agentic loop
- [ ] `docker_runner.py`: spin up a container, mount a repo, run a command, capture stdout/stderr/exit code
- [ ] `llm_client.py`: wrapper around the Claude API (retries, token counting)
- [ ] `coder.py`: given a task + repo state, produce a code diff
- [ ] `loop.py`: single-agent loop — write code → run tests → if failing, feed error back → retry (cap at N iterations)
- [ ] Test end-to-end on ONE hand-picked task: a repo with one failing test, agent should fix it

### Week 2 — Multi-agent + MCP
- [ ] `planner.py`: breaks a task into ordered steps before coding starts
- [ ] `reviewer.py`: reads the diff, flags issues (doesn't touch code, just approves/rejects with reasons)
- [ ] Wire planner → coder → sandbox → reviewer → (approve or loop back to coder)
- [ ] `mcp_server/server.py`: expose `run_task`, `run_tests`, `get_diff` as MCP tools
- [ ] Test the MCP server from Claude Desktop or another MCP client

### Week 3 — Eval harness
- [ ] Curate 15-30 tasks in `eval/tasks/` (small repos + task description + known-good check, e.g. a test suite)
- [ ] `harness.py`: runs the agent against every task, records: success/fail, # iterations, tokens used, wall-clock time
- [ ] Run a baseline, save results to `eval/results/baseline.json`
- [ ] Make ONE deliberate improvement (better prompt, review step, retry strategy) and re-run — compare numbers

### Week 4 — Polish + write-up
- [ ] Add per-run tracing/logging (which tools were called, in what order, cost)
- [ ] Simple dashboard or CLI report over `eval/results/`
- [ ] Record a demo video (task in → agent working → diff out → tests passing)
- [ ] Write a short post: what failed first, what you changed, before/after eval numbers

## Getting started

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your GEMINI_API_KEY
```

See `src/agent/loop.py` for the entry point once Week 1 pieces are filled in.
