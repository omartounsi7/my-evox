"""Strategies as code: loaded, checked, and run in the run's process.

A strategy is the code of a class named EvolvedSearchStrategy (D11): written by the strategy
model, or, for the built-in random strategy, by hand in exactly the same form. Its code is run
with exec, in a namespace that already holds the names the interface uses (Selection,
SearchStrategy, Solution, SolutionInView, MAX_INSPIRATIONS, CHANGE_SIZES, and the random module,
whose Random type the constructor receives); the code may import anything else it needs. The
class is then built with the strategy's own random generator (D44) and wrapped in a
LoadedStrategy, which checks every answer. Before it is deployed, a strategy replays every stored
solution through observe (D16) and is asked to select once: a strategy that fails anywhere is
rejected.

LLM-written code runs here, in the run's process, with your files and network and without a
time limit, until strategies move into their own process (step 3.1) and into Docker (3.2).
"""

import random
from typing import Any

from my_evox.records import Solution
from my_evox.store import SolutionInView, Store
from my_evox.strategies import CHANGE_SIZES, MAX_INSPIRATIONS, SearchStrategy, Selection

# The name of the class the strategy model must write
CLASS_NAME = "EvolvedSearchStrategy"
# The longest part of a strategy's answer quoted in an error message
MAX_QUOTED_ANSWER = 200


class StrategyError(Exception):
    """Raised when a strategy the strategy model wrote breaks a rule; the message says how."""


class LoadedStrategy(SearchStrategy):
    """A strategy loaded from its code, with every call checked.

    An exception inside the strategy, or an invalid answer from select, becomes a StrategyError.
    """

    def __init__(self, instance: Any) -> None:
        # The object built from the strategy model's class
        self.instance: Any = instance

    def observe(self, child: Solution) -> None:
        """Pass the child to the strategy. Raises StrategyError if the strategy raises."""
        try:
            self.instance.observe(child)
        except Exception as error:
            raise StrategyError(f"observe raised {describe(error)}") from error

    def select(self, view: tuple[SolutionInView, ...]) -> Selection:
        """Ask the strategy for a selection and check it. Raises StrategyError if it is invalid."""
        try:
            answer = self.instance.select(view)
        except Exception as error:
            raise StrategyError(f"select raised {describe(error)}") from error
        return checked_selection(answer, view)


def load_strategy(code: str, rng: random.Random) -> LoadedStrategy:
    """Run the strategy model's code and return its strategy, built with rng.

    Raises StrategyError if the code does not run, defines no usable EvolvedSearchStrategy, or
    its constructor raises.
    """
    namespace = strategy_namespace()
    try:
        exec(compile(code, "<strategy>", "exec"), namespace)
    except Exception as error:
        raise StrategyError(f"the code does not run: {describe(error)}") from error
    strategy_class = namespace.get(CLASS_NAME)
    if not isinstance(strategy_class, type):
        raise StrategyError(f"the code defines no class named {CLASS_NAME}")
    for method in ("observe", "select"):
        if not callable(getattr(strategy_class, method, None)):
            raise StrategyError(f"{CLASS_NAME} has no method {method}")
    try:
        instance = strategy_class(rng)
    except Exception as error:
        raise StrategyError(f"{CLASS_NAME}(rng) raised {describe(error)}") from error
    return LoadedStrategy(instance)


def strategy_namespace() -> dict[str, Any]:
    """Return the names a strategy's code finds already defined: those of its interface."""
    return {
        # Classes defined by exec need a module name.
        "__name__": "evolved_strategy",
        "Selection": Selection,
        "SearchStrategy": SearchStrategy,
        "Solution": Solution,
        "SolutionInView": SolutionInView,
        "MAX_INSPIRATIONS": MAX_INSPIRATIONS,
        "CHANGE_SIZES": CHANGE_SIZES,
        # The random strategy's code, shown to the strategy model as an example, writes
        # rng: random.Random without the import at the top of its file; a strategy that copies
        # the annotation must find the module defined.
        "random": random,
    }


def replay_and_check(strategy: LoadedStrategy, store: Store) -> None:
    """Prepare a new strategy for deployment, checking it on the way.

    Every stored solution is replayed through observe, in order, so that the strategy's state
    is what it would be had it watched the whole run (D16); then select is asked once and its
    answer checked (D32). Raises StrategyError at the first failure.
    """
    for solution in store.all():
        strategy.observe(solution)
    strategy.select(store.view())


def checked_selection(answer: object, view: tuple[SolutionInView, ...]) -> Selection:
    """Return the answer as a Selection if it is valid, else raise StrategyError saying why.

    Valid (D32): a working parent; at most MAX_INSPIRATIONS inspirations, all working; a known
    change size. The inspirations may come as a list; they are returned as a tuple.
    """
    if not isinstance(answer, Selection):
        raise StrategyError(f"select returned {quoted(answer)}, not a Selection")
    working_ids = {solution.id for solution in view}
    if not is_working_id(answer.parent_id, working_ids):
        raise StrategyError(f"the parent {quoted(answer.parent_id)} is not a working solution")
    if answer.change not in CHANGE_SIZES:
        raise StrategyError(f"the change {quoted(answer.change)} is not one of {CHANGE_SIZES}")
    if not isinstance(answer.inspiration_ids, list | tuple):
        raise StrategyError(f"the inspirations {quoted(answer.inspiration_ids)} are not a list")
    if len(answer.inspiration_ids) > MAX_INSPIRATIONS:
        raise StrategyError(f"more than {MAX_INSPIRATIONS} inspirations")
    for inspiration_id in answer.inspiration_ids:
        if not is_working_id(inspiration_id, working_ids):
            message = f"the inspiration {quoted(inspiration_id)} is not a working solution"
            raise StrategyError(message)
    return Selection(answer.parent_id, answer.change, tuple(answer.inspiration_ids))


def is_working_id(value: object, working_ids: set[str]) -> bool:
    """True when value is the id of a working solution."""
    return isinstance(value, str) and value in working_ids


def describe(error: BaseException) -> str:
    """Return an exception as its type and message, such as "KeyError: 'score'"."""
    return f"{type(error).__name__}: {error}"


def quoted(value: object) -> str:
    """Return a value as it would be written in Python, cut to a length for error messages."""
    text = repr(value)
    if len(text) <= MAX_QUOTED_ANSWER:
        return text
    return text[: MAX_QUOTED_ANSWER - 3] + "..."
