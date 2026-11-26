"""Stand-ins the tests use in place of the real building blocks: the toy problem, solutions,
and a model that replies with texts written in advance."""

from pathlib import Path

from my_evox.llm import LLM
from my_evox.problem import Problem
from my_evox.prompt import Prompt
from my_evox.records import Result, Solution, new_id

# The toy problem's folder: solve() returns a number, scored as that number divided by 10
TOY = Path(__file__).parent / "toy"


def toy_problem() -> Problem:
    """Return the toy problem, as its problem file describes it."""
    return Problem.load(TOY / "problem.yaml", TOY / "initial_program.py", TOY / "evaluator")


def toy_program(answer: str) -> str:
    """Return a toy program whose solve() returns the Python expression answer."""
    return f"def solve():\n    return {answer}\n"


def solution_with_score(score: float | None, iteration: int = 1) -> Solution:
    """Return a child solution with this score; None makes it a failed one."""
    result = Result(score=score) if score is not None else Result(score=None, error="it broke")
    return Solution(
        id=new_id(),
        code=toy_program(str(score)),
        result=result,
        parent_id=None,
        iteration=iteration,
        strategy_id=None,
        change="free",
    )


class FakeLLM(LLM):
    """An LLM that returns replies written in advance, in order, and remembers the prompts.

    A reply that is an exception is raised instead of returned, as a failing model would.
    """

    def __init__(self, replies: list[str | Exception], name: str = "fake-model") -> None:
        super().__init__(name)
        # The replies still to give, first one first
        self.replies: list[str | Exception] = list(replies)
        # Every prompt received, in order
        self.prompts: list[Prompt] = []

    def complete(self, prompt: Prompt) -> str:
        """Return the next reply written in advance, or raise it if it is an exception."""
        self.prompts.append(prompt)
        if not self.replies:
            raise AssertionError("FakeLLM: no reply left to give")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


# A strategy the fake strategy model writes: always the best solution, asking for a refinement.
# Its inspirations come as a list, as a model may well write them.
GREEDY_STRATEGY = """\
class EvolvedSearchStrategy:
    \"\"\"Always improves the best solution, showing no other.\"\"\"

    def __init__(self, rng):
        self.rng = rng

    def observe(self, child):
        pass

    def select(self, view):
        best = max(view, key=lambda solution: solution.score)
        return Selection(best.id, "refine", [])
"""


def strategy_reply(code: str, direction: str = "Return larger numbers.") -> str:
    """Return a reply of the strategy model in Appendix B's format, holding code and direction."""
    return (
        "<ANALYSIS>\nThe best solution returns the largest number so far.\n</ANALYSIS>\n"
        f"<DIRECTION>\n{direction}\n</DIRECTION>\n"
        f"```python\n{code}```\n"
    )
