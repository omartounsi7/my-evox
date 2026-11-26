"""The strategy prompt, in its basic form: what the strategy model is asked after a stagnation.

The system message, the same for the whole run, says what a strategy is, the interface of the
class EvolvedSearchStrategy, the constraints and the reply format (Appendix B's, shortened).
The user message gives the problem's description, the best scores so far, and the current
strategy: its direction, its score and its code. Appendix B's full prompt, with the archive of
past strategies and the population statistics, arrives in steps 4.3 to 4.6.
"""

from my_evox.prompt import Prompt
from my_evox.records import StrategyRecord, format_score
from my_evox.store import Store
from my_evox.strategies import MAX_INSPIRATIONS

# How many of the best scores the user message lists
SHOWN_SCORES = 5

SYSTEM_MESSAGE = """\
You design search strategies for an evolutionary system that improves solutions to a problem.
A strategy decides, at each iteration of the search, which solution the solution LLM improves
(the parent), which other solutions it sees (the inspirations), and how big a change it asks
for. It also gives the solution LLM one direction: what the search should pursue while the
strategy is active.

# How the search works
- Each iteration, the strategy picks a parent, inspirations and a change size; the solution
  LLM writes one child from them; the child is evaluated and stored.
- The solution LLM sees your direction, the inspirations with their scores and code, then the
  parent. It never sees your code.
- A strategy is replaced when none of its last {window} children sets a new best score.

# What you write
1. A short analysis of the run: what has worked, what has not, what could work.
2. One direction for the solution LLM, in a few sentences: what to pursue. General enough that
   children of different parents still differ; concrete enough to act on. It must not
   contradict the problem.
3. The class EvolvedSearchStrategy, which serves your direction, with three methods:
   - __init__(self, rng): rng is a random.Random of your own; make every random draw with it.
   - observe(self, child): called after every child is stored, in order; update your own
     state here. child has the fields id, code, score (None if it failed), parent_id,
     iteration and change.
   - select(self, view): view is a tuple of the working solutions, each with the fields id,
     score and code. Return Selection(parent_id, change, inspiration_ids), where change is
     "free", "refine" or "diverge", and inspiration_ids lists at most {max_inspirations} ids
     of other working solutions.
   Selection, SearchStrategy, Solution, SolutionInView, MAX_INSPIRATIONS, CHANGE_SIZES and the
   random module are already defined, as in the current strategy's code; import anything else
   you use.

# Constraints
- Imports from Python's standard library only; no files, no network, no LLM calls.
- Never choose a failed solution; avoid always picking the same parent.
- Keep it simple: the population is small.

# Reply format
<ANALYSIS>
...
</ANALYSIS>
<DIRECTION>
...
</DIRECTION>
```python
the complete class
```"""


def build(
    problem_description: str,
    window: int,
    store: Store,
    iteration: int,
    iterations: int,
    current: StrategyRecord,
    current_score: float | None,
) -> Prompt:
    """Return the prompt asking for a strategy to replace current, whose score is current_score."""
    system = SYSTEM_MESSAGE.format(window=window, max_inspirations=MAX_INSPIRATIONS)
    sections = [
        f"# Problem\n{problem_description.strip()}\nHigher scores are better.",
        run_section(store, iteration, iterations),
        current_strategy_section(current, current_score),
        "# Task\nAnalyse the run, then write a new direction and the class that serves it.",
    ]
    return Prompt(system=system, user="\n\n".join(sections))


def run_section(store: Store, iteration: int, iterations: int) -> str:
    """Return the section on the run so far: where it is, and the best scores."""
    solutions = store.all()
    failed = sum(1 for solution in solutions if solution.score is None)
    scores = sorted((entry.score for entry in store.view()), reverse=True)
    best_scores = ", ".join(format_score(score) for score in scores[:SHOWN_SCORES])
    return (
        f"# The run so far\n"
        f"Iteration {iteration} of {iterations}. Best score: {format_score(store.best_score())}.\n"
        f"Solutions: {len(solutions)} ({failed} failed). The best scores: {best_scores}."
    )


def current_strategy_section(current: StrategyRecord, score: float | None) -> str:
    """Return the section on the current strategy: its direction, its score and its code."""
    return (
        f"# Current strategy\n"
        f"Direction: {current.direction or 'none'}\n"
        f"Score: {format_score(score)} (the sum of the gains its children made over the best "
        f"score; when none beat it, how close the nearest came)\n"
        f"```python\n{(current.code or '').rstrip()}\n```"
    )
