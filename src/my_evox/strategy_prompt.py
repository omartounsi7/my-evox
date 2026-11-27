"""The strategy prompt, in its basic form: what the strategy model is asked after a stagnation.

The system message, the same for the whole run, says what a strategy is, the texts of the three
change sizes (D13: the direction never says how far to move), the interface of the class
EvolvedSearchStrategy, the constraints and the reply format (Appendix B's, shortened).
The user message gives the problem's description; the best scores so far, with the best
solution's results (the evaluator's metrics and artifacts, which say what a score means); and
the current strategy: its direction, its score and its code. Appendix B's full prompt, with the
archive of past strategies and the population statistics, arrives in steps 4.3 to 4.6.
"""

from my_evox.operators import DIVERGE_TEXT, FREE_TEXT, REFINE_TEXT
from my_evox.prompt import Prompt
from my_evox.records import StrategyRecord, format_score
from my_evox.solution_prompt import results_text
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
- The solution LLM sees your direction, the inspirations with their scores, results and code,
  the parent, then the text of the change size you chose. It never sees your code.
- A strategy is replaced when none of its last {window} children sets a new best score.

# The change sizes
The text the solution LLM sees for each change size:
## free
{free_text}
## refine
{refine_text}
## diverge
{diverge_text}

# What you write
1. A short analysis of the run: what has worked, what has not, what could work.
2. One direction for the solution LLM, in a few sentences: what to pursue. General enough that
   children of different parents still differ; concrete enough to act on. It must not
   contradict the problem. It never says how far to move from the parent (keep the
   structure, rewrite it): the change size says that.
3. The class EvolvedSearchStrategy, which serves your direction, with three methods:
   - __init__(self, rng): rng is a random.Random of your own; make every random draw with it.
   - observe(self, child): called after every child is stored, in order; update your own
     state here. child has the fields id, code, score (None unless it works), parent_id,
     iteration and change; child.result.status.value is "ok", "failed", "invalid",
     "timeout" or "error".
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
    max_result_chars: int,
) -> Prompt:
    """Return the prompt asking for a strategy to replace current, whose score is current_score.

    Each of the best solution's results is cut to max_result_chars.
    """
    sections = [
        f"# Problem\n{problem_description.strip()}\nHigher scores are better.",
        run_section(store, iteration, iterations, max_result_chars),
        current_strategy_section(current, current_score),
        "# Task\nAnalyse the run, then write a new direction and the class that serves it.",
    ]
    return Prompt(system=system_message(window), user="\n\n".join(sections))


def system_message(window: int) -> str:
    """Return the system message, the same for every strategy of a run."""
    return SYSTEM_MESSAGE.format(
        window=window,
        max_inspirations=MAX_INSPIRATIONS,
        free_text=FREE_TEXT,
        refine_text=REFINE_TEXT.strip(),
        diverge_text=DIVERGE_TEXT.strip(),
    )


def run_section(store: Store, iteration: int, iterations: int, max_result_chars: int) -> str:
    """Return the section on the run so far: where it is, the counts by status, the best scores,
    and the best solution's results (left out when it has none)."""
    counts = ", ".join(
        f"{count} {status.value}" for status, count in store.counts_by_status().items()
    )
    scores = sorted((entry.score for entry in store.view()), reverse=True)
    best_scores = ", ".join(format_score(score) for score in scores[:SHOWN_SCORES])
    section = (
        f"# The run so far\n"
        f"Iteration {iteration} of {iterations}. Best score: {format_score(store.best_score())}.\n"
        f"Solutions: {len(store.all())} ({counts}). The best scores: {best_scores}."
    )
    best = store.best()
    results = results_text(best.result, max_result_chars) if best is not None else ""
    if not results:
        return section
    # Without the results, the model reads a normalised score as the raw quantity (Milestone 1)
    return f"{section}\nThe best solution's results: {results}"


def current_strategy_section(current: StrategyRecord, score: float | None) -> str:
    """Return the section on the current strategy: its direction, its score and its code."""
    return (
        f"# Current strategy\n"
        f"Direction: {current.direction or 'none'}\n"
        f"Score: {format_score(score)} (the sum of the gains its children made over the best "
        f"score; when none beat it, how close the nearest came)\n"
        f"```python\n{(current.code or '').rstrip()}\n```"
    )
