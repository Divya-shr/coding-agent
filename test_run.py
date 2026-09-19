from src.agent.loop import run_agent

result = run_agent(
    task_description="reverse_string in string_utils.py is missing a return statement, causing test_reverse_string to fail. Fix it.",
    repo_path="eval/tasks/repos/missing_return",
    test_command="pytest -q",
    relevant_files=["string_utils.py", "test_string_utils.py"],
    use_planner=False,
    use_reviewer=False,
)

print("Success:", result.success)
print("Iterations used:", result.iterations_used)
print("\n--- Final output ---")
print(result.final_output)
print("\n--- Last diff tried ---")
print(result.diffs_tried[-1] if result.diffs_tried else "(none)")