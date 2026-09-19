"""
One-shot setup script: creates all eval task repos + task JSON definitions.
Run this once from the coding-agent/ root: python setup_eval_tasks.py

Safe to re-run — it resets each repo to a clean buggy state every time,
so you can run this before every eval session.
"""
import json
import os
import subprocess

BASE = os.path.join("eval", "tasks", "repos")

TASKS = {
    "sample_fix_bug": {
        "files": {
            "math_utils.py": 'def add(a, b):\n    return a - b  # bug: should be addition\n',
            "test_math_utils.py": 'from math_utils import add\n\ndef test_add():\n    assert add(2, 3) == 5\n',
        },
        "task_description": "The function `add` in math_utils.py has a bug that makes test_add fail. Fix it so the test passes.",
        "test_command": "pytest -q",
        "relevant_files": ["math_utils.py", "test_math_utils.py"],
    },
    "off_by_one": {
        "files": {
            "list_utils.py": "def last_n_items(items, n):\n    return items[-n+1:]  # bug: off by one, drops the first of the n items\n",
            "test_list_utils.py": "from list_utils import last_n_items\n\ndef test_last_n_items():\n    assert last_n_items([1, 2, 3, 4, 5], 3) == [3, 4, 5]\n",
        },
        "task_description": "last_n_items in list_utils.py has an off-by-one bug causing test_last_n_items to fail. Fix it.",
        "test_command": "pytest -q",
        "relevant_files": ["list_utils.py", "test_list_utils.py"],
    },
    "wrong_comparison": {
        "files": {
            "validators.py": "def is_adult(age):\n    return age > 18  # bug: should be >= 18\n",
            "test_validators.py": "from validators import is_adult\n\ndef test_is_adult():\n    assert is_adult(18) == True\n    assert is_adult(17) == False\n",
        },
        "task_description": "is_adult in validators.py uses the wrong comparison operator, causing test_is_adult to fail. Fix it.",
        "test_command": "pytest -q",
        "relevant_files": ["validators.py", "test_validators.py"],
    },
    "missing_return": {
        "files": {
            "string_utils.py": "def reverse_string(s):\n    result = s[::-1]\n    # bug: forgot to return the result\n",
            "test_string_utils.py": "from string_utils import reverse_string\n\ndef test_reverse_string():\n    assert reverse_string(\"hello\") == \"olleh\"\n",
        },
        "task_description": "reverse_string in string_utils.py is missing a return statement, causing test_reverse_string to fail. Fix it.",
        "test_command": "pytest -q",
        "relevant_files": ["string_utils.py", "test_string_utils.py"],
    },
}


def run(cmd, cwd):
    subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


for name, spec in TASKS.items():
    repo_dir = os.path.join(BASE, name)
    os.makedirs(repo_dir, exist_ok=True)

    for filename, content in spec["files"].items():
        with open(os.path.join(repo_dir, filename), "w", newline="\n") as f:
            f.write(content)

    # git init + disable autocrlf + commit, so git apply works cleanly on Windows.
    run(["git", "init"], repo_dir)
    run(["git", "config", "core.autocrlf", "false"], repo_dir)
    run(["git", "add", "."], repo_dir)
    run(["git", "commit", "-m", "init"], repo_dir)

    task_json = {
        "task_description": spec["task_description"],
        "repo_path": f"./{repo_dir.replace(os.sep, '/')}",
        "test_command": spec["test_command"],
        "relevant_files": spec["relevant_files"],
    }
    os.makedirs(os.path.join("eval", "tasks"), exist_ok=True)
    with open(os.path.join("eval", "tasks", f"{name}.json"), "w") as f:
        json.dump(task_json, f, indent=2)

    print(f"Set up task: {name}")

print("\nAll tasks ready. Run: python eval/harness.py --run-name baseline")
