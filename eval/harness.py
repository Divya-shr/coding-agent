"""
Eval harness: run the agent against every task in eval/tasks/*.json,
score results, and save to eval/results/<run_name>.json.

This is what turns "I built a coding agent" into "I built a coding agent
that solves 68% of tasks in 2.3 iterations on average, here's what improved
it to 84%" — the numbers recruiters and interviewers actually respond to.

Usage:
    python eval/harness.py --run-name baseline
"""
import argparse
import json
import os
import time
from pathlib import Path

import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.agent.loop import run_agent

TASKS_DIR = Path(__file__).parent / "tasks"
RESULTS_DIR = Path(__file__).parent / "results"


def load_tasks() -> list[dict]:
    """
    Each task file: eval/tasks/<name>.json
    {
      "task_description": "...",
      "repo_path": "./eval/tasks/repos/<name>",
      "test_command": "pytest -q",
      "relevant_files": ["math_utils.py", "test_math_utils.py"]
    }
    """
    tasks = []
    for path in TASKS_DIR.glob("*.json"):
        with open(path) as f:
            task = json.load(f)
            task["name"] = path.stem
            tasks.append(task)
    return tasks


def run_eval(run_name: str, use_planner: bool = True, use_reviewer: bool = True):
    tasks = load_tasks()
    if not tasks:
        print(f"No tasks found in {TASKS_DIR}. Add task JSON files first (see docstring).")
        return

    results = []
    for i, task in enumerate(tasks):
        print(f"Running: {task['name']}...")
        start = time.time()

        try:
            result = run_agent(
                task_description=task["task_description"],
                repo_path=task["repo_path"],
                test_command=task["test_command"],
                relevant_files=task["relevant_files"],
                use_planner=use_planner,
                use_reviewer=use_reviewer,
            )
            elapsed = time.time() - start
            results.append({
                "task": task["name"],
                "success": result.success,
                "iterations_used": result.iterations_used,
                "wall_clock_seconds": round(elapsed, 1),
                "tokens": result.tokens,
            })
            print(f"  -> {'PASS' if result.success else 'FAIL'} in {result.iterations_used} iteration(s)")
        except Exception as e:
            # Don't let one task's crash (e.g. quota exhausted mid-run) kill the whole batch —
            # record it as a failure and keep going so you still get partial results.
            elapsed = time.time() - start
            results.append({
                "task": task["name"],
                "success": False,
                "iterations_used": 0,
                "wall_clock_seconds": round(elapsed, 1),
                "tokens": {},
                "error": str(e)[:200],
            })
            print(f"  -> ERROR: {str(e)[:150]}")

        # Small pause between tasks to avoid tripping per-minute rate limits.
        if i < len(tasks) - 1:
            time.sleep(3)

    # Summary stats — the numbers to quote in your write-up.
    success_count = sum(1 for r in results if r["success"])
    summary = {
        "run_name": run_name,
        "total_tasks": len(results),
        "success_rate": round(success_count / len(results), 2),
        "avg_iterations": round(sum(r["iterations_used"] for r in results) / len(results), 2),
        "avg_wall_clock_seconds": round(sum(r["wall_clock_seconds"] for r in results) / len(results), 1),
        "results": results,
    }

    os.makedirs(RESULTS_DIR, exist_ok=True)
    out_path = RESULTS_DIR / f"{run_name}.json"
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\nSuccess rate: {summary['success_rate']*100:.0f}% ({success_count}/{len(results)})")
    print(f"Avg iterations: {summary['avg_iterations']}")
    print(f"Saved to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-name", required=True, help="Label for this eval run, e.g. 'baseline'")
    parser.add_argument("--no-planner", action="store_true")
    parser.add_argument("--no-reviewer", action="store_true")
    args = parser.parse_args()

    run_eval(
        run_name=args.run_name,
        use_planner=not args.no_planner,
        use_reviewer=not args.no_reviewer,
    )
