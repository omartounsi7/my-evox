"""The run: the initial program, then one iteration after another (D8), and the strategy loop.

Each iteration, the active strategy selects a parent, inspirations and a change size; the
solution model writes a child from the prompt, which carries the strategy's direction; the child
is evaluated, stored, written to the run folder, shown to the strategy, and judged.

When the active strategy stagnates, the strategy model writes a new one; the run waits
meanwhile, since only one strategy is active (K = 1, D22). A new strategy that passes its
checks is deployed and the old one retired. One that fails is rejected, and the old strategy
keeps running for another trial of W children. A deployed strategy that fails while it runs is
stood in for by the random strategy for that call (D36; strikes arrive in step 3.4).
"""

import inspect
from dataclasses import dataclass, replace
from pathlib import Path

from my_evox import console, solution_prompt, strategy_prompt
from my_evox.evaluator import Evaluator
from my_evox.generated_strategy import StrategyError, load_strategy, replay_and_check
from my_evox.judge import Judge
from my_evox.llm import LLM, LLMError
from my_evox.problem import Problem
from my_evox.prompt import Prompt
from my_evox.records import Solution, StrategyRecord, new_id
from my_evox.replies import extract_code
from my_evox.run_folder import RunFolder
from my_evox.store import Store
from my_evox.strategies import RandomStrategy, SearchStrategy, Selection, strategy_rng
from my_evox.strategy_writer import StrategyReply, write_strategy


class RunError(Exception):
    """Raised when a run cannot start or go on; the message says why."""


@dataclass
class ActiveStrategy:
    """The strategy choosing the iterations, and its record."""

    strategy: SearchStrategy
    record: StrategyRecord


class Run:
    """The state of one run: its solutions, its strategies, and what it talks to."""

    def __init__(
        self,
        problem: Problem,
        solution_llm: LLM,
        strategy_llm: LLM,
        evaluator: Evaluator,
        folder: RunFolder,
        iterations: int,
        seed: int,
    ) -> None:
        self.problem: Problem = problem
        # The models that write solutions and strategies
        self.solution_llm: LLM = solution_llm
        self.strategy_llm: LLM = strategy_llm
        self.evaluator: Evaluator = evaluator
        self.folder: RunFolder = folder
        # How many iterations the run makes in all
        self.iterations: int = iterations
        # The run's seed, from which every strategy's random generator is derived (D44)
        self.seed: int = seed
        # Every solution of the run
        self.store: Store = Store()
        # The random strategy: the initial strategy (D17), and the stand-in for a strategy that
        # fails while it runs (D36)
        self.random_strategy: RandomStrategy = RandomStrategy(strategy_rng(seed, 0))
        self.active: ActiveStrategy = initial_strategy(self.random_strategy)
        # How many strategies the strategy model has written, rejected ones included
        self.strategies_written: int = 0
        # Judges the active strategy from its children
        self.judge: Judge = Judge(problem.strategies.window, problem.strategies.threshold)

    def start(self) -> None:
        """Evaluate and keep the initial program. Raises RunError if it gets no score."""
        code = self.problem.initial_program.read_text(encoding="utf-8")
        result = self.evaluator.evaluate(code)
        if not result.works:
            raise RunError(f"the initial program gets no score: {result.error}")
        initial = Solution(new_id(), code, result, None, 0, None, None)
        self.keep(initial)
        self.folder.save_strategy(self.active.record)

    def iterate(self, iteration: int) -> None:
        """Run one iteration: select, ask the solution model, evaluate, keep, observe, judge.

        A failed call to the solution model skips the iteration.
        """
        selection = self.select()
        try:
            reply = self.solution_llm.complete(self.prompt_for(selection))
        except LLMError as error:
            print(console.skipped_line(iteration, self.iterations, str(error)))
            return
        child = self.make_child(reply, selection, iteration)
        # The child is judged against the best score of its moment, before it joins the store.
        best_before = self.store.best_score()
        self.keep(child)
        self.show_child(child)
        self.judge.record(child, best_before)
        self.print_iteration(iteration, child)
        # After the last iteration, a new strategy would never run: none is written.
        if self.judge.stagnated() and iteration < self.iterations:
            self.replace_strategy(iteration)

    def finish(self) -> None:
        """Write the active strategy's final score to strategies.jsonl."""
        final = replace(self.active.record, score=self.judge.strategy_score())
        self.folder.save_strategy(final)

    def select(self) -> Selection:
        """Return the active strategy's selection; the random strategy's if the active one fails."""
        view = self.store.view()
        try:
            return self.active.strategy.select(view)
        except StrategyError as error:
            consequence = "the random strategy chooses this iteration"
            print(console.strategy_failed_line(self.active.record.number, str(error), consequence))
            return self.random_strategy.select(view)

    def prompt_for(self, selection: Selection) -> Prompt:
        """Return the solution prompt for a selection: its parent, inspirations and direction."""
        parent = self.store.get(selection.parent_id)
        inspirations = [self.store.get(solution_id) for solution_id in selection.inspiration_ids]
        direction = self.active.record.direction
        return solution_prompt.build(self.problem.description, parent, inspirations, direction)

    def make_child(self, reply: str, selection: Selection, iteration: int) -> Solution:
        """Return the child written in the reply, evaluated, and tagged with its origins."""
        code = extract_code(reply)
        result = self.evaluator.evaluate(code)
        return Solution(
            id=new_id(),
            code=code,
            result=result,
            parent_id=selection.parent_id,
            iteration=iteration,
            strategy_id=self.active.record.id,
            change=selection.change,
        )

    def keep(self, solution: Solution) -> None:
        """Store a solution and write it to the run folder, with best_program if it is the best."""
        self.store.add(solution)
        self.folder.save_solution(solution)
        if self.store.best() is solution:
            self.folder.save_best(solution)

    def show_child(self, child: Solution) -> None:
        """Pass the child to the active strategy; if the strategy fails, the run goes on."""
        try:
            self.active.strategy.observe(child)
        except StrategyError as error:
            consequence = "this child goes unobserved"
            print(console.strategy_failed_line(self.active.record.number, str(error), consequence))

    def print_iteration(self, iteration: int, child: Solution) -> None:
        """Print the iteration's line: the child, the best score, the strategy and its score."""
        line = console.iteration_line(
            iteration,
            self.iterations,
            child,
            self.store.best_score(),
            self.active.record.number,
            self.judge.strategy_score(),
        )
        print(line)

    def replace_strategy(self, iteration: int) -> None:
        """Replace the stagnated strategy, or give it another trial if no new strategy passes."""
        number, score = self.active.record.number, self.judge.strategy_score()
        print(console.stagnated_line(number, score, self.problem.strategies.window))
        candidate = self.write_candidate(iteration)
        if candidate is None:
            self.judge.new_trial()
            return
        self.retire_active()
        self.deploy(candidate)

    def write_candidate(self, iteration: int) -> ActiveStrategy | None:
        """Ask the strategy model for a new strategy and check it (D32).

        Returns it ready to deploy, its state rebuilt by replay (D16), or None if it was
        rejected.
        """
        self.strategies_written += 1
        number = self.strategies_written
        try:
            reply = write_strategy(self.strategy_llm, self.strategy_prompt(iteration))
        except (LLMError, StrategyError) as error:
            self.reject(number, None, str(error))
            return None
        try:
            strategy = load_strategy(reply.code, strategy_rng(self.seed, number))
            replay_and_check(strategy, self.store)
        except StrategyError as error:
            self.reject(number, reply, str(error))
            return None
        record = StrategyRecord(
            new_id(), number, "active", reply.code, reply.direction, reply.analysis
        )
        return ActiveStrategy(strategy, record)

    def strategy_prompt(self, iteration: int) -> Prompt:
        """Return the prompt asking the strategy model to replace the active strategy."""
        return strategy_prompt.build(
            self.problem.description,
            self.problem.strategies.window,
            self.store,
            iteration,
            self.iterations,
            self.active.record,
            self.judge.strategy_score(),
        )

    def reject(self, number: int, reply: StrategyReply | None, error: str) -> None:
        """Record a strategy that failed its checks, with whatever its reply held."""
        record = StrategyRecord(
            id=new_id(),
            number=number,
            status="rejected",
            code=reply.code if reply else None,
            direction=reply.direction if reply else None,
            analysis=reply.analysis if reply else None,
            error=error,
        )
        self.folder.save_strategy(record)
        print(console.rejected_line(number, error, self.active.record.number))

    def retire_active(self) -> None:
        """Record the active strategy as retired, with its final score."""
        retired = replace(self.active.record, status="retired", score=self.judge.strategy_score())
        self.folder.save_strategy(retired)

    def deploy(self, candidate: ActiveStrategy) -> None:
        """Make a checked strategy the active one; its direction reaches the next prompts."""
        self.active = candidate
        self.judge.new_strategy()
        self.folder.save_strategy(candidate.record)
        print(console.deployed_line(candidate.record.number, candidate.record.direction))


def initial_strategy(random_strategy: RandomStrategy) -> ActiveStrategy:
    """Return the random strategy as the run's first active strategy, number 0 (D17).

    Its record holds its source code, which the strategy model sees when it replaces it.
    """
    code = inspect.getsource(RandomStrategy)
    record = StrategyRecord(new_id(), 0, "active", code, direction=None, analysis=None)
    return ActiveStrategy(random_strategy, record)


def run(
    problem: Problem,
    solution_llm: LLM,
    strategy_llm: LLM,
    evaluator: Evaluator,
    iterations: int,
    output: Path,
    seed: int,
) -> Store:
    """Run the whole evolution and return its store of solutions.

    Raises RunError if the initial program gets no score, and FileExistsError if output already
    holds a run.
    """
    folder = RunFolder(output, problem.initial_program.suffix)
    the_run = Run(problem, solution_llm, strategy_llm, evaluator, folder, iterations, seed)
    the_run.start()
    for iteration in range(1, iterations + 1):
        the_run.iterate(iteration)
    the_run.finish()
    return the_run.store
