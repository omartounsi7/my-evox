"""The operator texts: what each change size asks of the solution model (D13, D14).

A strategy chooses a change size at each iteration; the solution prompt then shows its text, in
Appendix A's "Change to make" block:
    free      "Any change that improves the score." (D14)
    refine    skydiscover's generic refinement template
    diverge   skydiscover's generic structural-variation template

The two templates are skydiscover's DEFAULT_REFINE_TEMPLATE and DEFAULT_DIVERGE_TEMPLATE, from
skydiscover/optimize/search/evox/utils/template.py at commit 0d932b6 (Apache-2.0), verbatim: the
texts skydiscover uses when no examples are generated. The examples, written once per run by the
strategy model, arrive in step 2.8.
"""

# The text of the free change: nothing beyond improving the score (D14)
FREE_TEXT = "Any change that improves the score."

# skydiscover's DEFAULT_REFINE_TEMPLATE, verbatim
REFINE_TEXT = """\
## IMPORTANT: YOU MUST FOLLOW THE FOLLOWING IN YOUR GENERATION, OTHERWISE THE SOLUTION WILL BE REJECTED.

### Goal
Improve the current solution **within the same core structure**.
Do **not** change the fundamental structure of the following solution; instead make it stronger, cleaner, and more reliable.

Allowed: rewriting for clarity, fixing weaknesses, improving completeness, better edge-case handling, and added polish.
DO NOT switch to a fundamentally different approach.

### Constraints
- Keep the output **valid** for the same task and constraints.
- Spend effort on higher-quality execution and fewer mistakes.

### Output
1. REFINEMENT: One short paragraph describing what you improved and how.
2. OUTPUT: The full refined solution.
"""

# skydiscover's DEFAULT_DIVERGE_TEMPLATE, verbatim
DIVERGE_TEXT = """\
## IMPORTANT: YOU MUST FOLLOW THE FOLLOWING IN YOUR GENERATION, OTHERWISE THE SOLUTION WILL BE REJECTED.

### Goal
Produce a **fundamentally different** solution than the current one.
This must be a real **strategy shift**, not minor edits or small tweaks.

Allowed: new structure, new strategy, different generation plan, different style/format, new components.
DO NOT do: superficial rewrites, polishing, or the same idea with only small changes.

### Constraints
- Keep the output **valid** for the same task and constraints.
- Prefer changes that introduce something **not present** in the following current solution.
- If reliable tools or shortcuts exist, use them instead of manual re-creation.

### Output
1. APPROACH: One short paragraph describing what is different and why.
2. OUTPUT: The full generated solution.
"""

# Each change size's text, by the name a strategy gives it
CHANGE_TEXTS = {"free": FREE_TEXT, "refine": REFINE_TEXT, "diverge": DIVERGE_TEXT}


def change_text(change: str) -> str:
    """Return the text of a change size. Raises KeyError for a change that is not one of them."""
    return CHANGE_TEXTS[change]
