"""Evolve a program with my-evox: the command line.

Usage:
    python scripts/run.py INITIAL_PROGRAM EVALUATION_FOLDER --config PROBLEM_FILE
        --iterations N [--output FOLDER] [--seed S] [--unsafe-local-evaluation]

The evaluation folder holds the problem's evaluator, in skydiscover's container protocol (a
Dockerfile and an evaluate.sh). Every child is evaluated in a container built from it, so Docker
must be installed and running. The run folder defaults to runs/<problem name>_<date>_<time>; it
must not already hold a run.

Example, from the repository root:
    python scripts/run.py problems/circle_packing/initial_program.py
        problems/circle_packing/evaluator --config problems/circle_packing/problem.yaml
        --iterations 30 --output runs/circle_packing_1
"""

import argparse
import io
import random
import sys
import uuid
from datetime import datetime
from pathlib import Path

from my_evox.containers import ContainerError, ContainerRunner
from my_evox.evaluator import Evaluator, LocalRunner, Runner
from my_evox.llm import MissingKeyError, OpenAICompatibleLLM
from my_evox.loop import RunError, run
from my_evox.problem import Problem, ProblemError
from my_evox.records import format_score
from my_evox.store import Store

# Shown when programs are evaluated without the container
UNSAFE_WARNING = (
    "WARNING: --unsafe-local-evaluation: the programs the LLM writes run as plain processes, "
    "with your files, your network and your environment variables (API keys included). "
    "Use it for tests and trusted code only."
)


def positive_integer(text: str) -> int:
    """Read a whole number of at least 1, for argparse."""
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not a whole number") from None
    if value < 1:
        raise argparse.ArgumentTypeError(f"must be 1 or more, got {value}")
    return value


def parse_arguments(arguments: list[str]) -> argparse.Namespace:
    """Read the command line; a wrong value stops the script with a usage message."""
    parser = argparse.ArgumentParser(description="Evolve a program, and its search strategy.")
    parser.add_argument("initial_program", type=Path, help="the program evolution starts from")
    parser.add_argument("evaluation_folder", type=Path, help="the folder holding evaluator.py")
    parser.add_argument("--config", type=Path, required=True, help="the problem file (YAML)")
    parser.add_argument(
        "--iterations", type=positive_integer, required=True, help="how many iterations in all"
    )
    parser.add_argument(
        "--output", type=Path, help="the run folder (default: runs/<problem>_<date>_<time>)"
    )
    parser.add_argument("--seed", type=int, help="fixes the random draws (default: drawn)")
    parser.add_argument(
        "--unsafe-local-evaluation",
        action="store_true",
        help="run the evaluator's evaluator.py as a plain process, without Docker (tests only)",
    )
    return parser.parse_args(arguments)


def default_output(problem_name: str) -> Path:
    """Return the default run folder: runs/, the problem's name, the date and the time."""
    return Path("runs") / f"{problem_name}_{datetime.now():%Y-%m-%d_%H-%M-%S}"


def draw_seed() -> int:
    """Return a seed drawn from the system's randomness, for a run given none (D44)."""
    return random.SystemRandom().randrange(2**32)


def make_runner(problem: Problem, unsafe_local: bool, run_id: str) -> Runner:
    """Return what runs the problem's evaluator: its container, labelled with the run's id,
    unless the unsafe local one is asked for. Raises ContainerError if Docker fails."""
    if unsafe_local:
        print(UNSAFE_WARNING, file=sys.stderr)
        return LocalRunner(problem)
    print("Starting the evaluator's container...")
    return ContainerRunner.start(problem, run_id)


def run_problem(problem: Problem, parsed: argparse.Namespace, output: Path, seed: int) -> Store:
    """Run the problem with its runner, whose containers are removed however the run ends."""
    # One model writes both solutions and strategies, for now (separate roles: step 2.10).
    model = OpenAICompatibleLLM(problem.llm)
    # Identifies the run, and labels its containers
    run_id = uuid.uuid4().hex
    with make_runner(problem, parsed.unsafe_local_evaluation, run_id) as runner:
        evaluator = Evaluator(runner)
        return run(problem, model, model, evaluator, parsed.iterations, output, seed, run_id)


def main(arguments: list[str]) -> int:
    """Run my-evox from the command line; return the exit code."""
    # Text beyond plain English must reach a Windows console too, even when redirected.
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")
    parsed = parse_arguments(arguments)
    try:
        problem = Problem.load(parsed.config, parsed.initial_program, parsed.evaluation_folder)
        output = parsed.output or default_output(problem.name)
        seed = parsed.seed if parsed.seed is not None else draw_seed()
        print(f"Run folder: {output}\nSeed: {seed}")
        store = run_problem(problem, parsed, output, seed)
    except (ProblemError, RunError, MissingKeyError, ContainerError, OSError) as error:
        # A mistake in the user's files, a missing API key, Docker failing, or a run folder that
        # cannot be written: one clear message, no traceback.
        print(f"Error: {error}", file=sys.stderr)
        return 1
    best = store.best()
    print(f"Done. Best score: {format_score(best.score if best else None)}. Folder: {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
