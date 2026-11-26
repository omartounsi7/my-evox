"""The strategy writer, basic: asks the strategy model for a new strategy and reads its reply.

The reply has three parts, in Appendix B's format: an analysis between <ANALYSIS> tags, a
direction between <DIRECTION> tags, then the class EvolvedSearchStrategy in a fenced code
block. Checks beyond these parts (the direction's cap, the code's length) arrive in step 3.6,
and repairing a failed strategy in step 3.7.
"""

from dataclasses import dataclass

from my_evox.generated_strategy import StrategyError
from my_evox.llm import LLM
from my_evox.prompt import Prompt
from my_evox.replies import extract_tagged, find_code_block, text_after


@dataclass(frozen=True)
class StrategyReply:
    """The three parts of the strategy model's reply."""

    # Its analysis of the run: what has worked, what has not, what could
    analysis: str
    # What the solution model should pursue while the strategy is active (D13)
    direction: str
    # The code of the class EvolvedSearchStrategy
    code: str


def write_strategy(llm: LLM, prompt: Prompt) -> StrategyReply:
    """Ask the strategy model for a strategy and return the three parts of its reply.

    Raises LLMError if the model gives no reply, StrategyError if a part is missing.
    """
    return parse_strategy_reply(llm.complete(prompt))


def parse_strategy_reply(reply: str) -> StrategyReply:
    """Return the analysis, the direction and the code of a reply. Raises StrategyError if one
    is missing or empty."""
    analysis = extract_tagged(reply, "ANALYSIS")
    if not analysis:
        raise StrategyError("the reply has no <ANALYSIS> section, or an empty one")
    direction = extract_tagged(reply, "DIRECTION")
    if not direction:
        raise StrategyError("the reply has no <DIRECTION> section, or an empty one")
    # The code is looked for after the direction, so that code quoted in the analysis is not
    # taken for the strategy.
    code = find_code_block(text_after(reply, "</DIRECTION>"))
    if code is None:
        raise StrategyError("the reply has no code block after its <DIRECTION> section")
    return StrategyReply(analysis, direction, code)
