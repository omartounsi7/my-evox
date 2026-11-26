# Design decisions for my-evox

my-evox is a re-implementation of **EvoX** (Liu et al., *EvoX: Meta-Evolution for Automated Discovery*,
arXiv 2602.23413v2) that extends it. It takes the authors' implementation in the skydiscover repository as
its blueprint, and much of its machinery from **my-evolve**, an earlier AlphaEvolve re-implementation whose
design decisions are cited as ME-D19 (decision D19 of `my-evolve/docs/design-decisions.md`). How EvoX is
implemented in skydiscover, and that code's weak spots, are described in
[evox-in-code.md](evox-in-code.md), cited as §8.1 (a section) or §13.5 (item 5 of its list of weak spots).

The overview says what my-evox is for and how it differs from EvoX. Sections 1 to 12 state the decisions,
each with its reason when it is not obvious. Appendices A and B give the two prompts, and Appendix C the
whole run as pseudocode, in the paper's notation.

## Terms

| Term | Meaning |
|---|---|
| problem | a task to solve: an initial program, an evaluator and a problem description |
| solution | a program that solves the problem, written by an LLM (the initial program is the first) |
| child | the solution an LLM writes in an iteration |
| iteration | one call to the solution model and the child it writes, checked, evaluated and stored; a selection that yields a failed child is retried, each attempt being an iteration (D35) |
| status | how a child's evaluation ended: `ok`, `rejected`, `failed`, `timeout`, `invalid` or `error` (D33) |
| record | a child whose score beats the run's best score at the time it was evaluated |
| strategy | Python code, written by an LLM, that makes the solution loop's choices: the parent, the inspirations, the change size, and a direction (the paper's "search strategy") |
| inspirations | the solutions shown in the prompt besides the parent |
| change size | the variation operator asked of the solution model: free, refine or diverge (the paper's π) |
| direction | a short text written with a strategy, telling the solution model what to pursue while the strategy is active |
| active strategy | a strategy currently choosing iterations; up to $K$ are active at once |
| deployment | the iterations during which one strategy is active |
| archive | every strategy deployed so far, active or retired, with its score and champion (the paper's H) |
| champion | the best of a strategy's own children |
| population statistics | numbers describing the solutions and the recent iterations (the paper's φ) |
| solution model, strategy model | the LLMs that write solutions and strategies |

---

## Overview

### EvoX in brief
LLM-driven evolutionary search (AlphaEvolve and its descendants) repeats one iteration: choose a parent
solution and a few inspirations, ask an LLM for a child, evaluate it, keep it. How the parent and the
inspirations are chosen, and what kind of change is asked for, is the **search strategy**, usually fixed by
hand. EvoX evolves the search strategy itself, in two nested loops:

- the **solution loop** runs iterations under the current strategy;
- the **strategy loop** watches the best score; when the strategy stagnates, an LLM writes a new one, given
  earlier strategies, their scores, and statistics of the population of solutions. The new strategy
  replaces the old one, and the solutions carry over.

In skydiscover a strategy is a Python class that stores the solutions and samples from them; it chooses
the parent, the inspirations, and one of three variation operators (free-form, structural variation, local
refinement). The paper reports EvoX beating OpenEvolve, ShinkaEvolve and GEPA on most of nearly 200
problems.

### What my-evox is for
To be a better EvoX, measured on problems from the paper with the paper's models and budget, and to be
understood and owned by its author: it is built from scratch in small steps (D1, D46).

### How my-evox differs from EvoX
- **Prompt evolution.** Besides choosing the parent, the inspirations and the change size, a strategy
  gives the solution model a **direction**, written by the strategy model from the solutions so far
  (D13). An ablation without directions measures what this adds (D4).
- **Several strategies at once.** Up to $K$ strategies share one pool of solutions, scheduled by
  round-robin or a bandit, run by parallel workers (D19 to D22, D9). With $K = 1$, my-evox runs EvoX's
  scheme.
- **Fair scoring and stagnation per strategy.** A strategy is scored by the records its own children set,
  and by how close they came when they set none (D24); it is replaced when its own recent children stop
  setting records, or when it gets too few iterations to do so (D25).
- **Strategies cannot harm solutions.** The framework owns every solution; a strategy only observes them
  and selects among them (D11, D40).
- **Every piece of LLM-written code runs in Docker** (D10).
- **Failed strategies are repaired** with their error shown (D34), and every summary the strategy model
  reads is written by the framework, not by another LLM (D30, D31).
- **Solutions in any language** (D2), **complete resume** (D42), and **cost measured for both levels**
  (D6).

### One run, end to end
1. The problem file is read; the operator texts are written once by the strategy model (D14).
2. The initial program is evaluated and stored; the initial strategy, random selection without a
   direction, becomes active (D17).
3. Iterations run (D8): the scheduler picks an active strategy, which selects a parent, inspirations and a
   change size; the solution model writes a child; the child is checked, evaluated in a container, stored,
   and shown to every active strategy. A child that fails is retried with its error shown, up to 3
   attempts (D35).
4. When a strategy stagnates (D25), it is retired and scored, and the strategy model writes a replacement
   in the background (D22, D31), which is checked (D32) and deployed.
5. After the last iteration, the run folder holds every solution, strategy and LLM call (D41), and a
   report can be drawn (D43).

---

## 1. Scope

### D1. Built from scratch
my-evox is a new repository, built step by step. Code from my-evolve, skydiscover or any other repository
at hand is brought in when a step needs it: copied and adapted, never imported. Copied files keep their
license notices (skydiscover and openevolve are Apache-2.0).
*Why:* small steps on a code base the author understands worked for my-evolve; copying leaves the sources
untouched and lets my-evox change what it takes.

### D2. Languages of solutions
Any language, so that ALE-Bench-Lite's C++ problems can be run. Strategies are always Python. Whatever
depended on Python in my-evolve becomes language-neutral or is done per language: the evolve-block markers
(`#` or `//` comments), the checks before evaluation (D33), and the fingerprint of a solution's code (D40).

### D3. Problems and evaluators
- **Problems**, in order: circle packing in the unit square (26 circles) and MinMaxMinDist (14 points in 3
  dimensions); then ALE-Bench-Lite's 10 problems, starting from ALE-Agent's C++ solutions, as in the paper.
- **Everything about a problem comes from skydiscover's benchmarks**, unchanged: the initial program, the
  problem description (its `prompt.system_message`), and the evaluator, so that scores are the paper's.
- **Evaluators run as containers** (skydiscover's container protocol: a `Dockerfile` and an `evaluate.sh`
  that receives the program's path and prints JSON), never in the main process (D10). For circle packing
  this is the `evaluator/` folder's version; the top-level `evaluator.py` runs programs on the host.
- To check when the plan reaches them: that skydiscover's two circle-packing evaluators score every program
  alike; how the `ale_bench` package, which ALE-Bench-Lite's evaluator calls and which is installed
  separately, runs on this machine (it is believed to judge programs in its own containers).

---

## 2. Experiments

### D4. Comparability with the paper
- Each problem: **3 runs of 100 iterations**; the mean and the best final score are reported, as in the
  paper, and compared with the paper's own numbers (skydiscover's EvoX is not re-run):
  - circle packing (higher is better): mean 2.6324, best 2.6359 with GPT-5; 2.6328 and 2.6359 with
    Gemini-3-Pro (Table 2);
  - MinMaxMinDist, $d = 3$ (lower is better): 4.21 and 4.18 with GPT-5; 4.17 and 4.16 with Gemini-3-Pro
    (Table 2);
  - ALE-Bench-Lite: average private performance 1958.2 with GPT-5 (Figure 3a).
- Not exceeding the paper's best scores on the two math problems is acceptable: they already reach the best
  known results.
- **Ablation studies**, each on the same problems with the same runs as far as the budget allows, each
  changing one thing:
  1. **no direction**: strategies write no direction and only choose among the change sizes, so that a
     strategy's role is the paper's; my-evox's other differences from skydiscover remain. It shows how
     much of any difference comes from directions;
  2. **a static direction**: one direction, written by the strategy model at the start of the run from the
     problem alone, shown in every solution prompt and never updated; strategies write none. Compared with
     the full method, it tells whether gains come from evolving directions or merely from having one;
  3. **skydiscover's strategy score**: $J_s$ with its second case clipped to 0 (D24), to see what crediting
     near misses changes;
  4. **several strategies**, once $K > 1$ exists (D19): $K = 2$ against $K = 1$, then round-robin against
     the bandit (D20).

  The full method, the first and the second come first; the others after $K > 1$ is built.
- The cost of every run is measured and reported (D6).
- Target-score and patience stops (section 13) are off in these runs.

### D5. Models
- **Two roles**: the **solution model** writes children (Appendix A); the **strategy model** writes
  strategies, their repairs, and the operator texts (Appendix B, D14). There is no third, cheaper "guide"
  model, as skydiscover has.
- **Both are GPT-5** in the experiments, as in the paper's GPT-5 column. If GPT-5 is retired before the
  experiments are done, both become Gemini-3-Pro; this differs from the paper's Gemini column, in which
  GPT-5 still wrote the strategies, and is reported as such.
- Settings, as in skydiscover's benchmark configurations: `max_tokens` 32,000, a 600 s timeout, and the
  provider's default reasoning effort (the paper states none).
- Each role is configured as in my-evolve (ME-D31 to ME-D33): a list of models with weights, an endpoint and
  an API-key variable per model, so one model or an ensemble work alike.
- During development both roles use a cheap model or a fake server, never the experiment model.

### D6. Budget and cost
- **One iteration is one call to the solution model**, producing one child whatever its status. A retry
  after a failed child (D35) is an iteration too, as in skydiscover. A run of 100 iterations makes 100
  solution calls, as skydiscover's does, so budgets compare.
- The strategy model's calls (strategies, repairs, operator texts) are outside the budget, as in
  skydiscover.
- The tokens and cost of every call are recorded with its role, and reported for each level apart (D41).

---

## 3. Architecture

### D7. One machinery for both levels
Solutions and strategies are evolved in much the same way, so both levels share one machinery: building a
prompt and calling an LLM (with the client's retries of failed calls, and repair turns where a level uses
them); parsing the reply; checking the result; running LLM-written code in Docker (D10); storing records
with their ids and fingerprints (D40) in append-only files (D41). Each level supplies its own prompt, parser,
checks and driver: the solution level runs iterations; the strategy level runs when a slot needs a
strategy, and scores strategies later, from their children. A level is never forced to carry a piece only
the other needs. Anything finer is an engineering choice made while building.

### D8. The solution loop
my-evolve's loop (ME-D36, ME-D70), with its database replaced by strategies and its evaluator by
skydiscover's containers. The main thread alone touches the store and the files; worker threads do the slow
calls. One selection, with its attempts:
1. **main**: the scheduler (D20) picks an active strategy; its worker answers `select(view)` (D11); the
   prompt is built (Appendix A);
2. **worker thread**: the solution model is called, and its reply parsed as a full rewrite or as diffs
   (D37);
3. **main**: the checks before evaluation (D33);
4. **worker thread**: the child is evaluated in its problem's container (D3), and the result mapped to a
   status: `invalid` when `validity` is 0; `timeout` on a timeout; `failed` when the evaluator reports an
   error of the program; `error` when the container itself breaks; `ok` otherwise, with `combined_score`
   as its score and the other metrics and artifacts kept as its results;
5. **main**: the child is stored, tagged with the strategy that chose its parent and its change size (D41);
   every active strategy's worker receives `observe(child)`; scores (D24) and stagnation tests (D25) are
   updated; a retired strategy's replacement starts being written in the background (D22);
6. if the child failed and attempts remain (D35), steps 2 to 5 run again with the same selection, the
   failed attempts added to the prompt; each attempt is an iteration.

### D9. Iterations in parallel
Worker threads, as in my-evolve (ME-D36): at most `--workers` iterations at once (default 1). Every child is
tagged with the strategy that chose its parent and credited to it, even if it finishes after that strategy
was retired. With several active strategies (D19), workers run iterations of different strategies at the
same time, all adding to one pool of solutions.

### D10. Running LLM-written code
Every piece of LLM-written code runs in Docker, never in the main process.
- **Strategies**: each active strategy lives in a long-lived worker container (an image with Python's
  standard library only, no network), which holds the strategy object; the framework sends it `observe`
  messages and asks it to `select`, each call within a time limit; a worker that hangs or crashes is
  killed. my-evolve's sandbox and worker protocol (ME-D40, ME-D41, ME-D77) are the starting point. A new
  strategy's checks (D32) run in the same kind of container.
- **Solutions**: through their problem's evaluator container (D3).
*Why:* skydiscover runs generated strategies in its own process, without a time limit (§13.9).

---

## 4. Search strategies

### D11. What a strategy is
The framework owns every solution (D40). A strategy is a Python class, `EvolvedSearchStrategy`, with two
methods:
- `observe(child)`: called after every child is evaluated and stored, other strategies' children included,
  and, when the strategy is deployed, over the whole history in order. It updates the strategy's own state
  only: it stores nothing and cannot change the child.
- `select(view)`: called before each of the strategy's iterations, with a read-only view of the population
  (D15). It returns `Selection(parent_id, change, inspiration_ids)`.

The direction is not part of the class: it comes with the strategy, in its own part of the strategy
model's reply (D31).
*Why:* in skydiscover a strategy stores the solutions itself, so it can lose or alter them, and a 777-line
checker guards against that (§10.1); here the question cannot arise.

### D12. What a strategy decides
- At each of its iterations: the **parent** (a working solution), the **inspirations** (from none up to a
  maximum set in the problem file, default 4, all working solutions), and the **change size**: `"free"`,
  `"refine"` or `"diverge"` (D13).
- For its whole deployment: its **direction** (D13).

Everything else in the solution prompt is fixed by the framework (Appendix A). The framework refuses a
failed solution as parent, whatever the strategy returns.

### D13. Guidance for the solution model: direction and change size
The solution prompt has a **fixed part**, never written or changed by a strategy (the problem description,
the rules, the reply format), and an **evolvable part**, set by the strategy: the parent, the inspirations,
the direction and the change size.
- **The direction** says what the search should pursue while the strategy is active. The strategy model
  writes it when it writes the strategy: it first analyses the run (what has worked, what has not, what
  could), then writes the direction, then the code that serves it (Appendix B). The direction is constant
  for the deployment and must be general enough that children made from different parents still differ.
  It has a hard size cap, set in the problem file; a strategy whose direction is over it fails its checks.
  No LLM is called while a strategy runs.
- **The change size** is one of three presets, chosen by the strategy's code at each iteration and
  recorded by name with the child: `free` (no instruction beyond improving the score), `refine` (keep the
  approach, polish it) or `diverge` (a fundamentally different approach). Their texts: D14.
- **Precedence**, stated in the solution prompt: the problem and its rules come first, the direction second,
  the change size third. The direction says what to pursue, the change size how far to move from the
  parent, so the two do not contradict each other.

*Why:* in EvoX a strategy can only pick among three fixed instruction texts. A direction lets each strategy
pass on what it learned from the population, in words; the paper's own case studies read as a sequence of
such directions. AlphaEvolve also evolves parts of its prompts.

### D14. Operator texts
The `refine` and `diverge` texts are skydiscover's `REFINE_TEMPLATE` and `DIVERGE_TEMPLATE`, verbatim, each
with a list of problem-specific examples (approaches to try, knobs to tune). The examples are written once
per run by the strategy model, with skydiscover's generation prompt: the problem description, the
evaluator's source, and the packages listed in the benchmark's `requirements.txt`. The texts are saved in
the run folder and reused when a run continues. A setting replaces them with skydiscover's generic
templates, without examples. The `free` change adds the line "Any change that improves the score."
*Why:* the ablation (D4) then asks for changes exactly as skydiscover does; with directions, the operator
texts mainly convey the size of a change. skydiscover's refinement template contradicts itself (§13.21);
it is kept verbatim for that reason.

### D15. What a strategy can read
`select` receives a read-only view, kept up to date inside the strategy's worker from the `observe`
messages:
- **every stored solution**, failed ones included, as a frozen record: id, code, description, status, score,
  metrics, parent, inspirations, the strategy that chose its parent, its change size, its iteration; and
  facts computed by the framework: its gain over its parent, its gain $g_i$ over the run's best score at
  the time (D23), its rank among working solutions, its number of children;
- **the run**: the current iteration, the budget left, the best score, the number of active strategies;
- **the strategy itself**: its number of iterations, whether it is in warm-up, its records.

*Why:* computed facts make strategies shorter and less error-prone.

### D16. A strategy's state
Rebuilt by replay: before a new strategy's first `select`, its worker receives `observe(child)` for every
stored solution, in order. The same replay rebuilds every active strategy when a run continues (D42).
Nothing of a strategy's state is saved.

### D17. Built-in strategies
Two strategies are written by hand, as `EvolvedSearchStrategy` classes run like any other:
- **random**: the parent drawn uniformly among the working solutions, up to 4 inspirations drawn the same
  way, always the `free` change, no direction. It is the paper's initial strategy.
- **weighted**: my-evolve's parent rule (ME-D19), adapted to a flat population.

The problem file chooses the initial strategy (default: random). The random strategy also stands in for a
strategy whose call fails (D36). The initial strategy never has a direction, as in the paper.

### D18. Population structure
Flat: the framework keeps a pool of solutions with no islands or grids. Any structure (score tiers,
niches, a Pareto front) is built by a strategy in its own code, since structure is part of what EvoX
evolves. my-evolve's output features (ME-D17) may later be added to the view as read-only facts.

---

## 5. Several active strategies

### D19. The portfolio
Up to $K$ strategies are active at once and share one pool of solutions; each is judged and replaced on its
own. $K$ is set in the problem file; $K = 1$ (the default) is EvoX's scheme and the reference for
comparisons. $K = 1$ is built first; the design allows $K > 1$ from the start (children tagged with their
strategy; windows, scores and stagnation kept per strategy), and $K > 1$ is added afterwards.
Which strategy an iteration belongs to (scheduling, D20) is separate from how many iterations run at once
(execution, D9).

### D20. Scheduling
- **Warm-up**: a new strategy first gets $n_{\min}$ iterations of its own (default $W$, D25). Strategies in
  warm-up are served first, taking turns.
- **After warm-up**, two schedulers are implemented; which one the experiments use, or a combination, is
  decided later:
  - **round-robin**: strategies take turns;
  - **bandit**: more iterations go to strategies whose recent children did well; older results count less
    (a sliding window or a discount), since improvements get harder as a run goes on. The bandit's
    algorithm is chosen when it is built.
- **The bandit's reward** for child $i$ is its rank among the working solutions when it is evaluated:
  $r_i \in [0, 1]$, the fraction of working solutions it beats; $r_i = 0$ for a failed child.
  *Why:* a strategy cannot inflate it by choosing weak parents (they give low-ranked children), and it
  does not depend on the scale of scores.

### D21. Sequential start
At the start only the initial strategy exists: $K$ copies of it would be identical, and $K - 1$ strategies
written at the first iteration would be written blind and alike. So:
1. the initial strategy runs alone for its warm-up, building a population and data for the strategy model;
2. the other $K - 1$ slots are then filled one strategy at a time, each written seeing the active ones and
   asked to complement their directions (Appendix B), never several in one batch;
3. the initial strategy stays one of the $K$ and is judged like the others.

The other strategies are written in the background while the initial strategy runs (D22). With $K = 1$,
nothing changes.

### D22. Writing strategies in the background
The run never pauses while a strategy can work. Strategies are written by a thread of their own, beside the
workers.
- **A strategy stagnates while others are active** ($K > 1$): it is retired at once and its slot stays
  empty while its replacement is written; the others keep running. The replacement joins when its checks
  pass, starting with its warm-up.
- **The last strategy left stagnates** ($K = 1$): the run waits for its replacement, as in EvoX.
- A retired strategy is not kept running: its iterations would be budget taken from better uses, and its
  record stops when it is judged. The one exception: with $K = 1$, when every attempt to write a
  replacement fails, the stagnated strategy keeps running until the next attempt (D34).
- The strategy prompt is a snapshot of the population when it is built; records made meanwhile are seen by
  the next one. Only wall time changes; the budget does not.

---

## 6. Judging strategies

### D23. Records and near misses
For each child $i$, with score $s_i$, and $b_i$ the run's best score just before the child was evaluated:

$$
g_i = s_i - b_i .
$$

$g_i > 0$: the child set a record, and $g_i$ is how much it raised the best score. $g_i \le 0$: the child
landed $|g_i|$ below the best of its moment. Both the score and the stagnation test rest on $g_i$. When
shown to the strategy model, each $g_i$ is given in score units and as a percentage of the best score.

### D24. The strategy score
Strategy $s$, with children $C_s$ and $n_s$ iterations of its own, scores

$$
J_s = \frac{w(b_{\text{start}})}{\sqrt{n_s}} \times
\begin{cases}
\displaystyle\sum_{i \in C_s,\; g_i > 0} g_i & \text{if } s \text{ set at least one record,} \\[2ex]
\displaystyle\max_{i \in C_s} g_i & \text{otherwise (a negative number: its closest approach),}
\end{cases}
$$

with $w(b) = 1 + \ln(1 + \max(0, b))$ (skydiscover's weight, favouring gains made from a higher score) and
$b_{\text{start}}$ the run's best score when $s$ was deployed.
- **Records are credited once**: the run's progress is the sum of all positive $g_i$, each belonging to the
  strategy whose child set it.
- **Near misses count**: a strategy without records ranks by how close it came, instead of tying at 0.
- **The frontier moves**: each child is compared with the best of its own moment, so a strategy earns
  nothing for beating a best that another strategy has since passed.
- **Unequal shares are fair**: dividing by $\sqrt{n_s}$ compares strategies given different numbers of
  iterations.
- **$J_s$ stays absolute** on every problem: it only ranks strategies within a run, where every $g_i$ has
  the same units.
- With $K = 1$, $J_s$ is skydiscover's score without its clipping at 0; clipping the second case to 0 gives
  skydiscover's score back, if an experiment needs it.

### D25. Stagnation and starvation
Strategy $s$ is retired when either holds:

$$
\underbrace{\max_{\text{last } W \text{ children of } s} g_i \le \tau}_{\text{stagnated}}
\qquad \text{or} \qquad
\underbrace{\text{no record by } s \text{ in the run's last } K \cdot W \text{ iterations}}_{\text{starved}}
$$

- **$W$**: default 10% of the run's iterations, as in the paper. **$\tau$**: relative to the run's best
  score $b$, default 1% of $|b|$, with a small absolute floor for scores near 0, so that the test means the
  same on every scale.
- **Minimum trial**: no strategy is judged before it has $W$ children of its own; its warm-up (D20) gives it
  these first. EvoX's strategies, too, run at least $W$ iterations.
- **Starvation**: a strategy that did well, then lost the bandit's favour, would get almost no iterations,
  keep its last $W$ children unchanged, and hold its slot forever; the second condition retires it.
  $K \cdot W$ iterations are about $W$ turns of each strategy. With $K = 1$ the second condition never fires
  before the first.

*Why:* skydiscover's test compares consecutive iterations, so many small gains still count as stagnation
(§13.5); a window over a strategy's own children is what the paper describes, and works when strategies
share the pool.

---

## 7. The archive of strategies

### D26. Archive entries
- **One entry per deployed strategy**: its code, analysis and direction; its score $J_s$; its champion; the
  population statistics at the start and end of its deployment (D30); a short history of its score.
- **Its champion** is the best of its own children, even when below the run's best score. The entry stores
  the champion's id, its score, and whether it set a new best for the run.
- **A strategy enters the archive when it is deployed**, marked active; its score and champion are updated
  as its children arrive. It is marked retired, with the reason (stagnated, starved or struck out, D25,
  D36), when it leaves its slot.
- **Strategies that fail their checks are not entries**: they are saved (D41) but never chosen as parent or
  inspiration; one is shown only to the strategy model repairing it (D34).

### D27. The parent strategy
When a strategy is to be written, the strategy to revise (its parent) is drawn from the archive with
probability decreasing with its rank by $J_s$, rank 0 being the best:

$$
p_j \propto e^{-\,\text{rank}_j / T}, \qquad T = 1 \text{ by default.}
$$

Active strategies are drawn like the others.
*Why:* the paper speaks of "score-biased selection" without a formula, and skydiscover always takes the
best. Ranks ignore the score's scale and work with negative scores; with fewer than about 10 strategies per
run, $T = 1$ gives the best most draws and the next ones some.

### D28. Inspiration strategies
Up to 2 other strategies are shown besides the parent:
- the strategy that just ended (stagnated, starved or struck out), if it is not the parent: its failure is
  the freshest evidence;
- the rest drawn with D27's weights among the other entries, without replacement.

When no strategy just ended (a slot filled during the sequential start, or a retry after failed
attempts), both are drawn; fewer are shown when the archive is small. When $K > 1$, the active strategies
are also shown, in a block of their own (Appendix B).

### D29. One candidate per replacement
The strategy model writes one strategy per replacement, with up to 3 attempts (D34).
*Why:* several candidates would multiply its cost, and the checks can only show that a strategy works, not
that it will do well; the portfolio already tries several strategies at once.

---

## 8. Writing a strategy

### D30. Population statistics
What the strategy model is told about the population, all of it written by the framework:
- population size;
- score summary: best, 75th, 50th and 25th percentiles, worst; the share of solutions in four score tiers,
  with each tier's bounds; the number of distinct scores (to 4 decimals);
- children per distinct parent, on average;
- the 20 best scores;
- over the run's last $K \cdot W$ iterations, all strategies included: the execution trace (for each
  iteration, the strategy, the child's score, the parent's change size and score, each inspiration's
  score), the score trajectory, the parents' scores, the iterations without improvement (measured with
  $\tau$), the most reused parent and inspiration (their share and score), the outcomes per change size
  (children, mean rank, records), and the failures by status.

These are skydiscover's statistics, cut to the recent iterations as it intends (its code uses the last 100,
§13.1), plus the last two lines. Statistics about one strategy (the strategy to revise, the other past
strategies, archive entries) use only that strategy's own children. Each archive entry also stores a short
vector of normalized statistics (the gap between best and median score, the iterations since the last
record, how concentrated parent choices are, the share of the budget used), for analysis; choosing
strategies by similar population states, as the paper suggests, may use it later.

### D31. The strategy prompt
Its text is Appendix B; the wording may be improved, the structure is decided.
- **System message**, fixed for a run: the role; how the search works (iterations, the $K$ strategies
  sharing the pool, warm-up and replacement rules, exactly what the solution model sees, and that it never
  sees the strategy's code); how strategies are scored ($J_s$ in words); what to write; the constraints;
  the reply format.
- **User message**, new for each strategy, in this order: the problem description, verbatim (the same as
  in the solution prompt); the run so far (iteration, best score, records, counts by status); the
  population statistics (D30); the 5 best solutions, by score and description, without code; the other
  active strategies when $K > 1$, with the instruction to complement them; the strategy to revise (D27);
  the other past strategies (D28); the task.
- **Past strategies** are shown with their direction, score, records and near misses, outcomes per change
  size, champion (score and description), how they ended, a summary of their deployment written by the
  framework, and their code. **The strategy to revise also shows its champion's code**, in full, so the
  strategy model sees concretely what the last direction produced.
- **The reply** has three parts: an analysis of the run, the direction, and the class's code, written in
  full (no diffs). The analysis is kept with the strategy, to explain later why it was written.
- **No other solution code** appears: descriptions say which approaches exist, and ALE-Bench-Lite programs
  of up to 45 KB (about 12,000 tokens each) would make the prompt too long.

*Why:* skydiscover shows summaries written by a cheaper LLM instead of the numbers and code (§9.4); text
written by the framework costs nothing, invents nothing, and can be checked.

### D32. Checks before deployment
In a container like the strategy's worker, in this order, stopping at the first failure:
1. the reply has an analysis, a direction within its cap, and code within its length limit (default about
   20,000 characters);
2. the code compiles and defines `EvolvedSearchStrategy` with `observe` and `select`;
3. a trial on a copy of the real population: the whole history replayed through `observe`, then `select`
   called several times, each call within the time limit, each answer valid (a working parent, working
   inspirations within the maximum, a known change size).

There is no static check of the code: the container has no network and no access to the host. A strategy
that picks the same parent in every trial call is logged, not rejected: no child arrives between the calls,
so a strategy whose choice depends on new children may rightly repeat itself.

### D33. Checks before a child is evaluated
my-evolve's checks (ME-D13), made language-neutral (how each is done for a language is settled when it is
built): the reply contains code that compiles or parses; the code keeps the evolve blocks, and the code
outside them is the initial program's (ME-D12); it defines the entry functions the problem file lists; and
the child is not a duplicate of an earlier solution, by fingerprint (D40). A child that fails a check is
stored as `rejected` and not evaluated. Statuses are my-evolve's (ME-D7), mapped from skydiscover's evaluator results as in D8.

### D34. Repairing a strategy
A strategy that fails its checks is sent back in the same conversation: "Your strategy failed: {error}.
Reply again in the same format." Up to 3 attempts in all. When all three fail:
- with $K > 1$, the slot stays empty and a new strategy is written later (for example after $W$ more
  iterations), without blocking the run;
- with $K = 1$, the stagnated strategy keeps running until the next attempt (D22); a strategy retired after
  strikes (D36) is replaced meanwhile by the random built-in.

*Why:* skydiscover retries with the same prompt, without the error (§13.3).

### D35. Retries for solutions
skydiscover's retries: a selection gets up to 3 attempts. When a child is `rejected`, `failed`, `timeout`
or `invalid`, the solution model is called again with the same parent, inspirations, direction and change
size, the prompt now showing each failed attempt's code and error (Appendix A); the first child that
works, or the third attempt, ends the selection. Each attempt is an iteration of the budget (D6). A child
with status `error` (the infrastructure's fault, not the program's) is not retried.
Unlike skydiscover, every failed attempt is stored with its status, credited to the strategy, and seen by
every active strategy's `observe`: failed children are never parents and never shown as inspirations, but
strategies can read them through their view (D15).
*Why:* many failures (a compile error, a wrong signature, an exception) are easy to fix once the error is
shown, which matters most for ALE-Bench-Lite's C++ programs; and the budget counts LLM calls exactly as
skydiscover's does. Storing the failures keeps them visible to strategies, which skydiscover's drop
(§13.8).

### D36. A strategy that fails while deployed
A call of `observe` or `select` that raises, runs over its time limit, crashes the worker, or returns an
invalid selection gives the strategy a **strike**; that iteration uses the random built-in strategy instead,
and a crashed worker is restarted and rebuilt by replay. After 3 strikes during its deployment, the
strategy is retired like a stagnated one and its slot is refilled (D22); with $K = 1$ the run waits for the
replacement. Only the strategy's own errors count: an LLM call or an evaluation that fails is never a
strike.

---

## 9. Writing a solution

### D37. Edit format
SEARCH/REPLACE diffs for every problem of the experiments, as in the paper's runs (skydiscover's benchmark
configurations set `diff_based_generation: true`); full rewrites remain available as a setting of the
problem file. Edits stay inside the evolve blocks (every starting program has them).
*Why:* comparability with the paper (D4); and ALE-Bench-Lite's C++ programs average about 28 KB and reach
45 KB, so rewriting them in full would cost up to about 12,000 output tokens per child.

### D38. The solution prompt
my-evolve's prompt (ME-D25), adapted; its text is Appendix A.
- **System message**, fixed for a run (providers can cache it): the role; the problem description, which is
  skydiscover's `prompt.system_message` for the benchmark, verbatim, since the paper's runs used it; how to
  use the guidance, with its precedence (D13); the rules; the reply format (D37).
- **User message**, new for each iteration: the direction; the inspirations the strategy chose; the parent;
  the change to make; the request. The direction comes first, as context; the parent and the change come
  last, just before the request, where models attend most.
- **Results** shown for the parent and each inspiration: its score, its description, and the metrics and
  artifacts that skydiscover's evaluators return, each cut to a size limit. The parent's line also gives
  the run's best score.
- **Failed attempts**: on a retry (D35), a block before the change to make shows each failed attempt of
  this selection, its error and its code, cut to a size limit.
- **No other block**: skydiscover always adds the 3 best of the last 100 solutions; here the strategy
  decides everything the prompt shows.
- **Every reply includes a description** of the program, for a reader who has never seen another version
  (ME-D15): inspirations, champions and the strategy prompt depend on it.
- **Size**: a budget for the whole prompt (default 60,000 characters, ME-D30); over it, inspirations are
  shown by score and description only, the last ones first.

---

## 10. Models' failures

### D39. LLM failures
As in my-evolve (ME-D34), for both models: before the first iteration, each model gets a test request, and
any failure stops the run, since a run without strategy evolution is not an EvoX run. During the run, a
failed call of the strategy model counts as a failed repair attempt (D34); 3 failures in a row of a model
with no alternative in its role stop the run. A failed solution call ends its iteration.

---

## 11. Records and outputs

### D40. Identifiers and memory
- Every solution and every strategy has a **UUID**, its identity, and a **fingerprint**, a SHA-256 of its
  code after a language-neutral normalization, used to detect duplicates. Logs and prompts may show the
  first 8 hexadecimal characters.
- **Every record stays in memory** for the whole run: solutions in the store, strategies in the archive.
  The files of D41 are written as records appear and read only when a run continues. A 100-iteration run
  holds about 100 solutions of 10 to 60 KB each: a few megabytes.
- Prompts and replies are not kept in memory: they are written to `llm_calls.jsonl`.

### D41. The run folder
my-evolve's run folder (ME-D47 to ME-D51), extended. Every file is written as soon as its content exists;
JSONL files are append-only.
- `programs.jsonl`: one line per solution, as in my-evolve, plus the strategy that chose its parent and its
  change size.
- `strategies.jsonl`: one line per generated strategy, failed ones included: id, code, analysis,
  direction, status (rejected, active, or retired with its reason), the error of its checks if any, its
  parent and inspiration strategies, the LLM call that wrote it, its deployment (first and last
  iteration), its score $J_s$ and per-child signals, its champion, and its population statistics, as
  numbers and ids only. A strategy's line is appended again when its status or scores change; when read
  back, its last line wins.
- `strategies/strategy_NNNN.py`: a readable copy of each strategy's code.
- `llm_calls.jsonl`: every LLM call, with its role (solution or strategy), tokens and cost.
- `history.csv`: one row per completed iteration, as in my-evolve, plus the strategy and the change size.
- The operator texts, written once (D14).
- `best_program` and the `best/` snapshots, with the solutions' file extension.
- `run.json`, a copy of the problem file, `log.txt`, as in my-evolve.

### D42. Continuing a run
Complete, as in my-evolve (ME-D49): the store and the archive are rebuilt from `programs.jsonl` and
`strategies.jsonl`; every active strategy is rebuilt by replay (D16); the operator texts are reused; the
scheduler and the stagnation tests are restored, so that a continued run behaves as if it had not stopped.
*Why:* skydiscover restarts its strategy level from scratch (§11.2).

### D43. The report
my-evolve's report (ME-D51), plus, from `strategies.jsonl` and `history.csv`:
- the progress plot with each strategy's deployment marked, with its gain and score (as the paper's
  Figure 2);
- a table of strategies: direction, use of each change size, records, iterations, how it ended (as the
  paper's Tables A7 to A9).

### D44. Randomness
As in my-evolve (ME-D39): one generator per run, seeded by `--seed` or by a seed drawn at random, saved in
`run.json`, reseeded on resume so that draws continue. It makes the framework's draws (the scheduler, the
parent and inspiration strategies). Each strategy gets a generator of its own, seeded from the run's seed
and the strategy's number, handed to its worker. A run repeats exactly only with one worker and
deterministic LLMs.

---

## 12. Configuration and project

### D45. The problem file and the command line
As in my-evolve (ME-D43 to ME-D46): a YAML problem file holds everything about a problem and its runs,
every value is checked when it is loaded, an unknown key is an error, and API keys are named by environment
variable, never written in the file. The command line is my-evolve's, plus flags for the strategy level.
The strategy level's settings, with their defaults:

| Setting | Default | Decision |
|---|---|---|
| $K$, active strategies | 1 | D19 |
| $W$, stagnation window | 10% of the iterations | D25 |
| $\tau$, stagnation threshold | 1% of $\lvert b \rvert$, with a small absolute floor | D25 |
| $n_{\min}$, warm-up iterations | $W$ | D20 |
| scheduler after warm-up | round-robin | D20 |
| $T$, rank temperature | 1 | D27 |
| initial strategy | random | D17 |
| maximum inspirations | 4 | D12 |
| direction cap, in characters | to be set | D13 |
| strategy code length limit, in characters | about 20,000 | D32 |
| time limit per `observe` or `select` call | to be set | D10 |
| strikes before retirement | 3 | D36 |
| repair attempts for a strategy | 3 | D34 |
| attempts per selection, for solutions | 3 | D35 |
| operator texts | generated examples (or generic) | D14 |
| edit format | per problem | D37 |
| solution prompt budget, in characters | 60,000 | D38 |

### D46. The project
As in my-evolve (ME-D55 to ME-D59): the package is `src/my_evox/`; Python 3.11 or later; Linux and Windows;
ruff (lint and format), mypy in strict mode, `unittest`, a fake OpenAI-compatible server for tests, Docker
tests skipped when Docker is missing; plain-English docstrings and comments throughout; small steps, each
runnable and tested, one commit each, each step's design explained before it is written.

---

## 13. Smaller features

| Feature | Decision |
|---|---|
| Target-score stop and patience (ME-D37) | yes; off in the experiments (D4) |
| Logging, Ctrl+C handling (ME-D52 to ME-D54) | as in my-evolve |
| Generic operator texts, as a setting | yes (D14) |
| Multiobjective mode (Pareto front) | no |
| LLM-as-judge scores | no |
| Agentic generation (tool calls) | no |
| Human feedback, live monitor | no |
| "Consider simplifying" hints in prompts | no |
| Command printing a problem's operator texts | not planned |

---

## Appendix A. The solution prompt

The two messages sent to the solution model (D38). Words in braces are filled in for each problem or
iteration; comments after `<-` are not part of the prompt. The wording will be polished when the prompt is
built; the structure and the order are decided.

### System message (fixed for a run, never written by a strategy)

````text
You are an expert software engineer improving a program that solves the problem below.
Each request shows you the program to improve (the parent), some other solutions with
their results, and guidance from the search: a direction and the size of the change to
make. Write a new version of the parent that scores higher.

# Problem
{the problem description: skydiscover's prompt.system_message for this benchmark, verbatim}

# How to use the guidance
- The direction says what the search is currently pursuing. Follow it unless it
  conflicts with the problem or the rules below, which always come first.
- The change size says how far to move from the parent: a free change, a small
  refinement of the same approach, or a different approach.

# Rules
- Change only the code between the EVOLVE-BLOCK-START and EVOLVE-BLOCK-END markers, and
  keep the markers; the code outside them is kept as it is.
- {language-specific rules: the packages Python programs may import, or the compiler and
  time limit for C++}
- Higher scores are better.
- In the description, say what the program does, for a reader who has never seen any
  other version of it. Never compare it with another program.

# Reply format
{one of the two formats below, set per problem (D37)}
````

Reply format for a full rewrite (a setting, D37):

````text
Your reply must contain these two parts. You may write anything else around them.
<DESCRIPTION>
The program's approach and main ideas, in a few sentences.
</DESCRIPTION>
```{language}
the complete program
```
````

Reply format for diffs (every problem of the experiments, D37):

````text
Your reply must contain these two parts. You may write anything else around them.
<DESCRIPTION>
The new program's approach and main ideas, in a few sentences.
</DESCRIPTION>
One or more changes, each in this form:
<<<<<<< SEARCH
code copied exactly from the parent, inside the evolve blocks
=======
the code that replaces it
>>>>>>> REPLACE
````

### User message (new for each iteration)

````text
# Direction of the search
{the strategy's direction}                       <- set by the strategy, fixed for its deployment

# Other solutions                                <- chosen by the strategy
## Solution 1: score {score}
Description: {description}
Results: {the evaluator's metrics and artifacts}
```{language}
{code}
```

## Solution 2: score {score}
...

# Program to improve (the parent): score {score}; best score so far in this run: {best score}
Description: {description}
Results: {the evaluator's metrics and artifacts}
```{language}
{code}
```

# Failed attempts                                <- only on a retry (D35)
## Attempt 1: {status}
Error: {error}
```{language}
{code}
```
Avoid these errors.

# Change to make                                 <- the change size chosen by the strategy
{the change size's text (D14); for free: "Any change that improves the score."}

Write the new program.
````

Notes:
- Other solutions are working solutions only, in the order the strategy returned them.
- An empty field (no description, no results) is left out with its label.
- Results are cut to a size limit. Over the prompt's budget, other solutions are shown by score and
  description only, the last ones first.
- The failed-attempts block appears only on a retry; each attempt's code and error are cut to a size limit
  (skydiscover cuts code to 1,500 characters and tracebacks to 800).
- In the ablation without prompt evolution (D4), the direction block is left out, and the system message no
  longer mentions a direction.

---

## Appendix B. The strategy prompt

The messages sent to the strategy model (D31). Words in braces are filled in for each run or strategy;
comments after `<-` are not part of the prompt. The structure is decided; the wording may be improved.

### System message (fixed for a run)

````text
You design search strategies for an evolutionary system that improves solutions to a
problem. A strategy decides, at each iteration of the search, which solution the
solution LLM improves (the parent), which other solutions it sees, and how big a change
it makes. It also gives the solution LLM one direction: what the search should pursue
while the strategy is active.

# How the search works
- Each iteration, one strategy picks a parent, other solutions and a change size; the
  solution LLM writes one child from them; the child is evaluated and stored.
- Up to {K} strategies are active at once and share one pool of solutions.
- A new strategy first gets {n_min} iterations. After that it is replaced when none of
  its last {W} children set a record above {tau}, or when it sets no record during
  {K*W} iterations of the run.
- The solution LLM sees, in this order: your direction, the solutions you chose with
  their scores and descriptions, the parent, and the change size. It never sees your code.

# How strategies are scored
{J_s in words: the sum of the records your children set, measured against the best
score at the moment each child was made; if you set none, how close your best child
came; divided by the square root of your number of iterations}

# What you write
1. A short analysis of the run: what has worked, what has not, what could work.
2. One direction for the solution LLM: what to pursue, in at most {cap} characters.
   General enough that children made from different parents still differ; concrete
   enough to act on. It must not contradict the problem's rules.
3. The class EvolvedSearchStrategy, which serves your direction:
   - observe(child): called after every child (yours and other strategies'), in order;
     update your own state here.
   - select(view) -> Selection(parent_id, change, inspiration_ids), where change is
     "free", "refine" or "diverge", with at most {max inspirations} inspirations.
   {the read-only view's fields (D15)}

# Constraints
- No LLM calls, no file or network access, imports from the standard library only;
  at most {length limit} characters of code.
- select() must return within {time limit}; never choose a failed solution as parent.
- Avoid always picking the same parent; keep it simple: the population is small.

# Reply format
<ANALYSIS>
...
</ANALYSIS>
<DIRECTION>
...
</DIRECTION>
```python
the complete class
```
````

### User message (new for each strategy)

````text
# Problem
{the problem description, verbatim}
Higher scores are better.

# The run so far
Iteration {t} of {T}. Best score {b}.
Records: {for each: iteration, score, gain, strategy}
Solutions: {n} ({counts by status})

# Population statistics (last {K*W} iterations of the run)     <- D30
{score distribution and tiers; distinct scores; parent and inspiration reuse;
 outcomes per change size: children, mean rank, records; failures by status}

# Best solutions                                               <- which approaches exist
{the 5 best working solutions: score and description, no code}

# Active strategies                                            <- only when K > 1
{for each: direction, score so far, share of iterations}
Write a direction that complements theirs instead of repeating them.

# Strategy to revise                                           <- the parent strategy (D27)
Direction: {direction}
Score: {J}; iterations: {n}; ended: {stagnated, starved, struck out, or still active}
Records and near misses: {g, raw and as % of the best}
Outcomes per change size: {children, mean rank, records}
Champion: score {score}; {description}
```{language}
{the champion's code}
```
```python
{the strategy's code}
```

# Other past strategies                                        <- D28
## Strategy {id}
Direction: {direction}; score {J}
Champion: score {score}; {description}
Deployment: {summary written by the framework}
```python
{code}
```

# Task
Analyse the run, then write a new direction and the class that serves it.
````

### Repair message (after a failed check, in the same conversation)

````text
Your strategy failed: {error}. Reply again in the same format.
````

Notes:
- The initial strategy has no direction; where it is shown, its Direction line says "none".
- A failed reply is followed by the repair message, up to 3 attempts in all (D34).
- In the ablation without prompt evolution (D4), the prompt asks for no direction: the reply has an
  analysis and the class only, and the system message no longer mentions a direction.

---

## Appendix C. Pseudocode

my-evox's run, in the notation of the paper's Algorithm 1. It is written sequentially, one iteration at a
time; with several workers (D9), up to `--workers` iterations are in flight at once, and lines 13 to 26 run
for each child in the order the children finish.

Notation, besides the paper's ($\mathcal{D}$, $E$, $\mathcal{G}_\text{sol}$, $\mathcal{G}_\text{str}$, $\phi$,
$\mathcal{H}$, $\pi$, $\mathcal{I}$, $W$, $\tau$, $T$):

| Symbol | Meaning |
|---|---|
| $\mathcal{A}$ | the active strategies, at most $K$ (D19) |
| $d_S$ | strategy $S$'s direction; $\varnothing$ for the initial strategy and in the ablation (D13) |
| $C_S(\mathcal{D})$ | $S$'s `select` on a read-only view of $\mathcal{D}$ (D11, D15) |
| $\sigma$ | the scheduler: warm-up first, then round-robin or a bandit (D20) |
| $O$ | the operator texts, one per change size $\pi \in \{\text{free}, \text{refine}, \text{diverge}\}$ (D14) |
| $b$ | the run's best score so far |
| $g'$ | the child's gain over $b$ at the time it is evaluated (D23) |
| $C_S$, $n_S$ | strategy $S$'s children and its number of iterations |
| $J_S$ | strategy $S$'s score (D24) |
| $\text{CHECK}$ | the checks before a child is evaluated (D33) |
| $\text{VALID}$ | the checks before a strategy is deployed (D32) |

```text
Algorithm 2  my-evox: two-level evolution with several active strategies

Require: budget T; window W; threshold τ (relative to |b|); slots K; warm-up n_min; rank temperature T_r
Require: evaluator E; solution model 𝒢_sol; strategy model 𝒢_str; descriptor φ(·); scheduler σ
Require: checks CHECK(·) and VALID(·); initial program x₀; initial strategy S₀ (random, d_S₀ = ∅)

 1: O ← 𝒢_str(operator examples | problem)                       ▷ once per run, saved (D14)
 2: (s₀, a₀) ← E(x₀);  𝒟 ← {(x₀, s₀, a₀)};  b ← s₀;  t ← 0
 3: ℋ ← ∅;  𝒜 ← ∅;  DEPLOY(S₀, ∅)
 4: while t < T do
      Phase I: one selection under a scheduled strategy, with up to 3 attempts (D8, D35)
 5:   S ← σ(𝒜)                                                    ▷ strategies in warm-up first (D20)
 6:   (x_par, π, ℐ) ← C_S(𝒟)                                       ▷ on error or timeout: a strike for S,
                                                                    ▷   and S₀'s random rule instead (D36)
 7:   F ← ∅                                                         ▷ this selection's failed attempts
      repeat                                                        ▷ each pass is one iteration
 8:     x' ~ 𝒢_sol(· | x_par, π, ℐ, d_S, O[π], F)                   ▷ prompt of Appendix A
 9:     if CHECK(x') then (s', a') ← E(x') else (s', a') ← (⊥, rejected);  t ← t + 1
10:     𝒟 ← 𝒟 ∪ {(x', s', a', S, π)}                               ▷ stored whatever its status (D35)
11:     g' ← s' − b if s' ≠ ⊥ else −∞;  b ← max(b, s')
12:     C_S ← C_S ∪ {(x', g')};  n_S ← n_S + 1;  if x' failed then F ← F ∪ {(x', error)}
      (lines 13 to 26 run here, after each attempt)
      until x' works, or |F| = 3, or its status is error, or t = T
      Phase II: progress monitoring, per strategy (D23 to D25)
13:   for all S'' ∈ 𝒜 do S''.observe(x')                           ▷ every active strategy sees every child
14:   update J_S and S's champion in ℋ;  reward σ with rank(s') ∈ [0, 1]
15:   for all S'' ∈ 𝒜 do
16:     stagnated ← n_S'' ≥ W and max{g : last W children of S''} ≤ τ
17:     starved   ← n_S'' ≥ W and no g > 0 among the children of S'' made in the last K·W iterations
18:     if stagnated or starved or strikes(S'') ≥ 3 then
19:       𝒜 ← 𝒜 ∖ {S''};  mark S'' retired in ℋ, with its reason and J_S''
20:     end if
21:   end for
      Phase III: strategy evolution, when a slot is free (D21, D22)
22:   if |𝒜| < K and no strategy is being written
          and S₀ has finished its warm-up of n_min iterations then
23:     if 𝒜 = ∅ then WRITE-STRATEGY()                             ▷ K = 1: the run waits, as in EvoX
24:     else start WRITE-STRATEGY() in the background             ▷ the other strategies keep running
25:     end if
26:   end if
27: end while
28: return argmax_{(x, s, a) ∈ 𝒟} s

procedure WRITE-STRATEGY()                                          ▷ D27, D28, D31, D32, D34
29:   S_par ~ p_j ∝ exp(−rank_j / T_r) over ℋ, ranked by J            ▷ the strategy to revise
30:   ℐ_ℋ ← {the strategy that just ended, if ≠ S_par} ∪ draws by the same weights, |ℐ_ℋ| ≤ 2
31:   for attempt = 1 to 3 do
32:     (analysis, d', S') ~ 𝒢_str(· | S_par, ℐ_ℋ, 𝒜, φ(𝒟), previous attempts and errors)
                                                                    ▷ prompt of Appendix B
33:     if VALID(S', d') then DEPLOY(S', d'); return               ▷ trial on a copy of 𝒟 (D32)
34:     else add the error to the conversation                     ▷ repair (D34)
35:   end for
36:   if K > 1 then retry later, for example after W more iterations
37:   else put back the strategy that just stagnated (or S₀'s rule, if it was struck out) until the next attempt
38: end procedure

procedure DEPLOY(S, d)                                              ▷ D16, D26
39:   d_S ← d;  C_S ← ∅;  n_S ← 0;  strikes(S) ← 0
40:   start S's worker container;  for all x ∈ 𝒟, in order, do S.observe(x)    ▷ replay
41:   ℋ ← ℋ ∪ {(S, d_S, φ(𝒟), J_S, champion)}, marked active;  𝒜 ← 𝒜 ∪ {S}
42: end procedure
```

How it differs from the paper's Algorithm 1:
- **Phase I is one selection (one iteration, or up to 3 when children fail), not a window of $W$.** Progress is monitored after every child, for each
  active strategy, on its own children (lines 15 to 21); a strategy is judged on progress once it has $W$
  of them.
- **Up to $K$ strategies are active at once** (lines 5, 22), sharing $\mathcal{D}$; with $K = 1$ the loop is
  EvoX's, one strategy at a time.
- **$\mathcal{G}_\text{sol}$ also receives the strategy's direction** $d_S$ (line 7), the operator text
  $O[\pi]$ being fixed per run.
- **Records, not windows, are scored**: $g'$ compares each child with the best score of its moment, and
  $J_S$ (D24) sums a strategy's records, or takes its closest approach, instead of the paper's
  $J_t = \Delta \log(1 + s_\text{start}) / \sqrt{W}$.
- **$\mathcal{H}$ gains an entry when a strategy is deployed** (line 41), updated as its children arrive,
  instead of one entry per window.
- **$\mathcal{G}_\text{str}$ revises one strategy drawn from $\mathcal{H}$** by rank (line 29), sees up to
  two others and the active ones, and gets the error back when its strategy fails VALID (lines 31 to 35).
- **A deployed strategy can still fail**: a failing `select` costs it a strike and the iteration falls back
  to the random rule (line 6); three strikes retire it (line 18).
