"""Records what skydiscover's own evaluators give each parity program (steps 1.4 and 1.5).

Run once, against the skydiscover checkout, inside the problem's evaluator image, which holds the
packages the paper's runs had. From the repository root, in PowerShell:

    docker run --rm --network none `
        -v "${PWD}/../skydiscover:/skydiscover:ro" -v "${PWD}/tests/parity:/parity" `
        --entrypoint python IMAGE /parity/record.py /skydiscover PROBLEM

where IMAGE is the problem's image (my-evox-evaluator:<tag>, built by the tests) and PROBLEM is
circle_packing or min_max_min_dist_3. It writes tests/parity/PROBLEM.json: for each program of
tests/parity/PROBLEM/, and for each of skydiscover's evaluators of the problem, the JSON object
that evaluator prints, as skydiscover's containers do. test_parity.py then checks that my-evox's
container gives the same results.
"""

import json
import subprocess
import sys
from pathlib import Path

# The parity folder, where this script lives
PARITY = Path(__file__).parent
# How each of skydiscover's evaluators of a problem is run on a program, from the checkout's root:
# a script in the container protocol, or an old evaluate() through skydiscover's wrapper.py
WRAPPER_FOLDER = "skydiscover/optimize/evaluation"
EVALUATORS = {
    "circle_packing": {
        "evaluator.py": ("evaluate", "benchmarks/math/circle_packing"),
        "evaluator/evaluator.py": ("script", "benchmarks/math/circle_packing/evaluator"),
    },
    "min_max_min_dist_3": {
        "evaluator/evaluator.py": ("script", "benchmarks/math/minimizing_max_min_dist/3/evaluator"),
    },
}
# Seconds one evaluation may take
TIME_LIMIT = 600


def command(kind: str, folder: Path, skydiscover: Path, program: Path) -> list[str]:
    """Return the command that runs one of skydiscover's evaluators on a program."""
    if kind == "script":
        return [sys.executable, str(folder / "evaluator.py"), str(program)]
    # An evaluate() function, bridged to the container protocol by skydiscover's own wrapper
    bridge = (
        f"import sys; sys.path[:0] = [{str(folder)!r}, {str(skydiscover / WRAPPER_FOLDER)!r}]; "
        "from wrapper import run; from evaluator import evaluate; run(evaluate)"
    )
    return [sys.executable, "-c", bridge, str(program)]


def evaluate(kind: str, folder: Path, skydiscover: Path, program: Path) -> object:
    """Return the JSON object the evaluator printed last, or a note of what went wrong."""
    completed = subprocess.run(
        command(kind, folder, skydiscover, program),
        cwd=folder,
        capture_output=True,
        text=True,
        timeout=TIME_LIMIT,
        check=False,
    )
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    try:
        return json.loads(lines[-1])
    except (IndexError, json.JSONDecodeError):
        return {"no_json": True, "exit_code": completed.returncode, "stderr": completed.stderr}


def record(skydiscover: Path, problem: str) -> dict[str, dict[str, object]]:
    """Return what each of the problem's evaluators gives each of its parity programs."""
    recorded: dict[str, dict[str, object]] = {}
    for program in sorted((PARITY / problem).glob("*.py")):
        recorded[program.name] = {}
        for name, (kind, folder) in EVALUATORS[problem].items():
            output = evaluate(kind, skydiscover / folder, skydiscover, program)
            recorded[program.name][name] = output
            print(f"{program.name} | {name}: {json.dumps(output)[:160]}")
    return recorded


def main() -> None:
    """Record the problem named on the command line, and save it next to this script."""
    skydiscover, problem = Path(sys.argv[1]), sys.argv[2]
    recorded = record(skydiscover, problem)
    target = PARITY / f"{problem}.json"
    target.write_text(json.dumps(recorded, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Saved {target}")


if __name__ == "__main__":
    main()
