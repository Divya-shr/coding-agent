"""
Read-only results dashboard for the self-correcting coding agent.

Reads every eval/results/*.json file (produced by eval/harness.py) and
displays success rate, iterations, tokens, and per-task breakdown.
Purely presentational — does not execute any agent code, so it's safe
to deploy publicly (e.g. on Streamlit Community Cloud).

Run locally with: streamlit run dashboard/app.py
"""
import json
import os

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Coding Agent — Eval Results", page_icon="🤖", layout="wide")

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "eval", "results")


@st.cache_data
def load_runs():
    runs = {}
    if not os.path.isdir(RESULTS_DIR):
        return runs
    for filename in sorted(os.listdir(RESULTS_DIR)):
        if filename.endswith(".json"):
            with open(os.path.join(RESULTS_DIR, filename)) as f:
                runs[filename.replace(".json", "")] = json.load(f)
    return runs


st.title("🤖 Self-Correcting Coding Agent")
st.caption("Live results from the eval harness — a Planner → Coder → Reviewer → Sandbox pipeline benchmarked against real bug-fix tasks.")

runs = load_runs()

if not runs:
    st.warning(
        "No eval results found yet. Run `python eval/harness.py --run-name my_run` "
        "locally, commit the resulting JSON in `eval/results/`, and redeploy."
    )
    st.stop()

run_names = list(runs.keys())
selected_run = st.selectbox("Eval run", run_names, index=len(run_names) - 1)
data = runs[selected_run]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Success rate", f"{data['success_rate'] * 100:.0f}%")
col2.metric("Tasks", data["total_tasks"])
col3.metric("Avg. iterations", f"{data['avg_iterations']:.1f}")
col4.metric("Avg. time / task", f"{data.get('avg_wall_clock_seconds', 0):.1f}s")

st.divider()
st.subheader("Per-task breakdown")

rows = []
for r in data["results"]:
    rows.append({
        "Task": r["task"],
        "Result": "✅ Pass" if r["success"] else "❌ Fail",
        "Iterations": r["iterations_used"],
        "Time (s)": r.get("wall_clock_seconds", "—"),
        "Tokens (in/out)": f"{r.get('tokens', {}).get('input', '—')} / {r.get('tokens', {}).get('output', '—')}",
    })

df = pd.DataFrame(rows)
st.dataframe(df, use_container_width=True, hide_index=True)

st.divider()
st.subheader("Iterations per task")
chart_df = pd.DataFrame({
    "Task": [r["task"] for r in data["results"]],
    "Iterations used": [r["iterations_used"] for r in data["results"]],
})
st.bar_chart(chart_df.set_index("Task"))

with st.expander("About this project"):
    st.markdown(
        """
An autonomous coding agent that plans a fix, rewrites the affected file,
runs the real test suite in an isolated Docker sandbox, and self-corrects
based on real error output — not just the model's own judgment.

**Architecture:** Planner → Coder → Reviewer → Sandbox, with each role a
separately-scoped LLM call so the Reviewer genuinely catches bad changes
rather than rubber-stamping its own output.

**Full source & architecture notes:** see the GitHub repository linked below.
        """
    )
    st.markdown("[View source on GitHub](https://github.com/Divya-shr/coding-agent)")
