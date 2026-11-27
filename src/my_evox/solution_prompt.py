"""The solution prompt, in its basic form: what the solution model is asked at each iteration.

The system message is the same for the whole run: a one-line role, the problem's description,
and the reply format. The user message shows the active strategy's direction, if it has one,
then each inspiration with its score, results and code, then the parent with its score, the
run's best score, its results and its code, then the change to make: the text of the change size
the strategy chose (D14). A solution's results are the evaluator's metrics and artifacts, each
cut to a size limit (D38).

The headings are those of Appendix A, whose full text arrives step by step: descriptions (2.2),
diffs (2.3), failed attempts (2.7), operator texts (1.8, 2.8), the rest (2.9).
"""

from dataclasses import dataclass

from my_evox.operators import change_text
from my_evox.prompt import Prompt
from my_evox.records import Result, Solution, format_score

# The first line of the system message
ROLE = "You are an expert software engineer improving a program that solves the problem below."
# The last part of the system message
REPLY_FORMAT = "Reply with the complete program in a fenced code block."
# The language named on the code blocks: solutions are Python until step 7.2
CODE_LANGUAGE = "python"


@dataclass(frozen=True)
class Request:
    """What one solution prompt shows, besides the problem."""

    # The solution to improve
    parent: Solution
    # The other solutions the strategy chose, in the order they are shown
    inspirations: list[Solution]
    # The active strategy's direction; None for a strategy that has none
    direction: str | None
    # The change size the strategy chose: "free", "refine" or "diverge" (D13)
    change: str
    # The run's best score so far
    best_score: float
    # The longest any one result is shown, in characters
    max_result_chars: int


def build(problem_description: str, request: Request) -> Prompt:
    """Return the prompt asking for a child of the request's parent."""
    return Prompt(system=system_message(problem_description), user=user_message(request))


def system_message(problem_description: str) -> str:
    """Return the system message: the role, the problem and the reply format."""
    return f"{ROLE}\n\n# Problem\n{problem_description.strip()}\n\n# Reply format\n{REPLY_FORMAT}"


def user_message(request: Request) -> str:
    """Return the user message: the direction, the other solutions, the parent, the request."""
    sections = []
    if request.direction is not None:
        sections.append(f"# Direction of the search\n{request.direction.strip()}")
    if request.inspirations:
        sections.append(inspirations_section(request.inspirations, request.max_result_chars))
    parent = request.parent
    parent_title = (
        f"# Program to improve (the parent): score {format_score(parent.score)}; "
        f"best score so far in this run: {format_score(request.best_score)}"
    )
    sections.append(solution_section(parent_title, parent, request.max_result_chars))
    sections.append("# Change to make\n" + change_text(request.change).strip())
    sections.append("Write the new program.")
    return "\n\n".join(sections)


def inspirations_section(inspirations: list[Solution], max_result_chars: int) -> str:
    """Return the section showing the other solutions, each with its score, results and code."""
    parts = ["# Other solutions"]
    for number, solution in enumerate(inspirations, start=1):
        title = f"## Solution {number}: score {format_score(solution.score)}"
        parts.append(solution_section(title, solution, max_result_chars))
    return "\n\n".join(parts)


def solution_section(title: str, solution: Solution, max_result_chars: int) -> str:
    """Return a solution's title, its results (left out when there are none), and its code."""
    lines = [title]
    results = results_text(solution.result, max_result_chars)
    if results:
        lines.append(f"Results: {results}")
    lines.append(code_block(solution.code))
    return "\n".join(lines)


def results_text(result: Result, max_result_chars: int) -> str:
    """Return the evaluator's metrics and artifacts on one line, each cut to max_result_chars."""
    metrics = [f"{name} {value:g}" for name, value in result.metrics.items()]
    artifacts = [f"{name}: {text}" for name, text in result.artifacts.items()]
    return "; ".join(cut(field, max_result_chars) for field in metrics + artifacts)


def cut(text: str, max_chars: int) -> str:
    """Return text on one line, cut to max_chars, ending with "..." when it was cut."""
    flat = " ".join(text.split())
    if len(flat) <= max_chars:
        return flat
    return flat[: max_chars - 3] + "..."


def code_block(code: str) -> str:
    """Return code inside a fenced block, named with its language."""
    return f"```{CODE_LANGUAGE}\n{code.rstrip()}\n```"
