# How EvoX is implemented in skydiscover

This file explains how the EvoX method (Liu et al., *EvoX: Meta-Evolution for Automated Discovery*,
arXiv 2602.23413v2) is implemented in the skydiscover repository, the blueprint for my-evox. It describes
the code at commit `0d932b6` ("fix(topk): optimize zero context requests (#103)"). Paths are relative to
the root of the skydiscover repository; `file.py:123` means line 123 of that file at that commit.

Sections 1 and 2 give the overview and the file map. Sections 3 to 11 follow the code in the order a run
executes it. Section 12 lists where the code departs from the paper, and section 13 the weak spots that
matter for a re-implementation; [design-decisions.md](design-decisions.md) cites both.

## Contents

1. [EvoX in brief](#1-evox-in-brief)
2. [Where EvoX lives in the code](#2-where-evox-lives-in-the-code)
3. [From the command line to two controllers](#3-from-the-command-line-to-two-controllers)
4. [The main loop](#4-the-main-loop)
5. [One solution iteration](#5-one-solution-iteration)
6. [A search strategy is a database class](#6-a-search-strategy-is-a-database-class)
7. [Variation operators](#7-variation-operators)
8. [Detecting stagnation and scoring strategies](#8-detecting-stagnation-and-scoring-strategies)
9. [Writing a new strategy](#9-writing-a-new-strategy)
10. [Validating and deploying a strategy](#10-validating-and-deploying-a-strategy)
11. [Outputs, checkpoints and LLM calls](#11-outputs-checkpoints-and-llm-calls)
12. [Paper versus code](#12-paper-versus-code)
13. [Quirks and weak spots](#13-quirks-and-weak-spots)

---

## 1. EvoX in brief

EvoX runs two evolutionary loops in one process:

- The **solution loop** (inner loop) is an ordinary LLM-driven evolutionary loop, as in AlphaEvolve: choose
  a parent solution and a few other solutions to show, ask an LLM for a child, evaluate it, store it.
- The **strategy loop** (outer loop, "meta-evolution") evolves the **search strategy** that makes the
  solution loop's choices: which parent, which other solutions to show, and which **variation operator** to
  ask for (a free-form change, a structural variation, or a local refinement). When the best solution
  score stops improving, an LLM writes a new strategy, given earlier strategies, how much each improved the
  best score, and statistics of the solution population. The new strategy replaces the old one; the
  solutions carry over.

In skydiscover a strategy is **Python source code**: a class named `EvolvedProgramDatabase`, with an `add()`
and a `sample()` method, that stores the solutions and chooses among them. Replacing the strategy means
loading the new class and moving every solution into an instance of it ("hot-swapping the database").

The paper's symbols, and what implements them:

| Paper | Meaning | Code |
|---|---|---|
| D_t | solution database | `CoEvolutionController.database`: an instance of the active strategy's `EvolvedProgramDatabase` |
| S_t | search strategy | the source of an `EvolvedProgramDatabase` class; the active one is in `_active_search_algorithm_code` |
| C_S(D_t) → (x_par, π, I) | generation context | `database.sample()` returns `({label: parent}, {"": [context programs]})` |
| π | variation operator | the parent's dict key ("label"): `""` (free-form), `DIVERGE_LABEL` (structural variation) or `REFINE_LABEL` (local refinement) |
| I | inspiration set | the "context programs" (`other_context_programs`) |
| G_sol | solution generator | the solution controller's LLM pool, `llm.models` of the user's config |
| E | evaluator | the user's `evaluator.py` |
| H | strategy database | `search_controller.database`: a `SearchStrategyDatabase` |
| J | strategy score | `LogWindowScorer.compute_metrics()["combined_score"]` |
| φ(D_t) | population descriptor | `ProgramDatabase.get_statistics()`, turned into text by `formatters.py`, then summarized by an LLM |
| W | window length | `switch_interval`, by default 10% of the iterations |
| τ | stagnation threshold | `DEFAULT_IMPROVEMENT_THRESHOLD = 0.01` |
| G_str | strategy generator | `search_controller`: a second `DiscoveryController`, with `EvoxContextBuilder` and its own LLMs |
| VALID | validity test | `search_strategy_evaluator.evaluate()`, then loading and migration at deployment, then a run-time fallback |

The two loops, as the code runs them:

```text
CoEvolutionController.run_discovery
|
|  solution loop, one pass per iteration (up to 3 LLM attempts)
|    database.sample()              -> ({operator: parent}, {"": context programs})
|    DefaultContextBuilder          -> prompt; the operator text sits under "# Current Solution"
|    main LLM -> child -> user's evaluator -> database.add(child)
|    scorer.record_step(best score)
|
|  best score up by no more than 0.01 for switch_interval passes in a row?
|    no  -> next pass
|    yes -> strategy loop (_evolve_search):
|             score the active strategy (J) and add it to H (SearchStrategyDatabase)
|             H.sample()            -> the best strategy + up to 2 others
|             EvoxContextBuilder    -> meta prompt (guide-LLM summaries of the population and of the others)
|             meta LLM              -> new strategy code -> search_strategy_evaluator (tests)
|             load the class, move every solution into it, swap the database
v
best solution
```

---

## 2. Where EvoX lives in the code

### 2.1 EvoX's own files

| File | Lines | Role |
|---|---:|---|
| `skydiscover/optimize/search/evox/controller.py` | 686 | `CoEvolutionController`: the main loop, stagnation, strategy scoring, switching, fallback |
| `skydiscover/optimize/search/evox/database/initial_search_strategy.py` | 89 | S_0, the initial strategy: random parent and context programs |
| `skydiscover/optimize/search/evox/database/search_strategy_db.py` | 60 | `SearchStrategyDatabase`: the strategy archive H |
| `skydiscover/optimize/search/evox/database/search_strategy_evaluator.py` | 777 | the validity test of generated strategies |
| `skydiscover/optimize/search/evox/utils/search_scorer.py` | 83 | `LogWindowScorer`: the strategy score J |
| `skydiscover/optimize/search/evox/utils/variation_operator_generator.py` | 641 | writes the problem-specific operator texts with an LLM |
| `skydiscover/optimize/search/evox/utils/template.py` | 99 | the operator templates |
| `skydiscover/optimize/search/evox/utils/coevolve_logging.py` | 280 | the files written under `search/` |
| `skydiscover/optimize/search/evox/config/search.yaml` | 40 | the strategy loop's config |
| `skydiscover/optimize/search/evox/config/evox_search_sys_prompt.txt` | 171 | the strategy generator's system message |
| `skydiscover/optimize/context_builder/evox/builder.py` | 310 | `EvoxContextBuilder`: the strategy generator's prompt |
| `skydiscover/optimize/context_builder/evox/formatters.py` | 626 | text formatting of statistics and strategies |
| `skydiscover/optimize/context_builder/evox/templates/*.txt` | 148 | six templates of the strategy prompt and of the summary calls |
| `skydiscover/optimize/configs/evox.yaml` | 65 | the template config users copy |

### 2.2 Shared code EvoX depends on

None of these is EvoX-specific, but EvoX's behaviour depends on them.

| File | What EvoX uses |
|---|---|
| `skydiscover/optimize/search/base_database.py` | `Program` (every solution and every strategy is one) and `ProgramDatabase`, the base class of every strategy; `get_statistics()` computes φ |
| `skydiscover/optimize/search/default_discovery_controller.py` | `DiscoveryController`: one iteration (sample, prompt, LLM, parse, evaluate, store); used twice, once per level |
| `skydiscover/optimize/context_builder/default/builder.py` and `default/templates/` | the solution prompt; it prints the operator text |
| `skydiscover/optimize/search/registry.py`, `route.py` | loading the initial strategy from its file; registering `evox` and `evox_meta` |
| `skydiscover/optimize/search/utils/discovery_utils.py` | `load_database_from_file()`, `SerializableResult` |
| `skydiscover/optimize/config.py` | `EvoxDatabaseConfig`; `SearchConfig.switch_interval` and `share_llm`; system messages read from files |
| `skydiscover/optimize/runner.py` | evaluating and adding the initial program; checkpoints |
| `skydiscover/optimize/evaluation/evaluator.py` | runs `evaluate(path)` in a thread with a timeout; also used to validate strategies |
| `skydiscover/optimize/llm/llm_pool.py` | weighted model pools; the availability probe |

### 2.3 Tests

`tests/search/test_evox.py` (the `switch_interval` config field, a path computation),
`test_evox_multiobjective.py` (the initial strategy's Pareto mode), `test_meta_llm_availability.py` (the
startup probe) and `test_seeded_reproducibility.py` (seeded sampling of the initial strategy and of H). No
test runs the co-evolution loop.

Everything else in skydiscover (AdaEvolve, GEPA, OpenEvolve-native, beam search, top-k, the `synthesize`
package, the benchmarks) is unrelated to EvoX, apart from the benchmark problems themselves.

---

## 3. From the command line to two controllers

`skydiscover optimize initial_program.py evaluator.py --search evox` (or `search: type: evox` in the
config) sets things up in five steps.

1. **Config.** `search.database` becomes an `EvoxDatabaseConfig` (`config.py:411`). Its `__post_init__`
   (`config.py:434`) fills three paths left unset: `database_file_path` (S_0, `initial_search_strategy.py`),
   `evaluation_file` (`search_strategy_evaluator.py`, used as the strategy loop's evaluator) and
   `config_path` (`evox/config/search.yaml`). It also holds `auto_generate_variation_operators` (default
   true) and the multiobjective fields. `SearchConfig` (`config.py:584`) has two EvoX fields:
   `switch_interval` (default None: 10% of the iterations) and `share_llm` (default false).
2. **Database.** `Runner.__init__` calls `create_database("evox", config)` (`registry.py:58`). For `evox`
   with a `database_file_path`, it imports that file with `load_database_from_file()`
   (`discovery_utils.py:76`, which caches the module by a hash of the path), takes its
   `EvolvedProgramDatabase` and `EvolvedProgram` classes, creates the database, and remembers the program
   class in `db._program_class`.
3. **Controllers.** `route.py:68` registers `CoEvolutionController` for `evox`, and `SearchStrategyDatabase`
   for `evox_meta`. `CoEvolutionController.__init__` (`controller.py:50`) first builds the solution
   controller (its superclass, `DiscoveryController`), then a second, independent `DiscoveryController` for
   strategies (`_init_search_evolution_controller`, `controller.py:56`), through `setup_search()`
   (`registry.py:119`), which loads `search.yaml` as a complete `Config`. It also creates the scorer, the
   tracking state (`_init_search_tracking`, `controller.py:79`) and the `<output_dir>/search` folder.
4. **Initial program.** `Runner._add_initial_program()` (`runner.py:268`) evaluates the initial solution,
   wraps it in the strategy's `EvolvedProgram` class (`get_program()`, `registry.py:83`) with
   `iteration_found = 0`, adds it, and sets `initial_program_id` and `initial_program_score`.
5. **Run.** `Runner.run()` calls `run_discovery(1, max_iterations, checkpoint_callback)` (`runner.py:199`).

The two controllers:

| | Solution controller (`self`) | Strategy controller (`self.search_controller`) |
|---|---|---|
| Config | the user's | `evox/config/search.yaml` |
| Database | the active `EvolvedProgramDatabase` (S_0 at first) | `SearchStrategyDatabase` (`search.type: evox_meta`) |
| Its "programs" | solutions | strategies: source code of a database class |
| Evaluator | the user's `evaluator.py` | `search_strategy_evaluator.py`: tests; the score is always 0.0 |
| Prompt builder | `DefaultContextBuilder` | `EvoxContextBuilder`, user template `search_evolution_user_message` |
| System message | the user's `prompt.system_message` | `evox_search_sys_prompt.txt`, read by `Config.from_yaml()` (`config.py:708`) |
| Main LLM | `llm.models` (e.g. `gpt-5`) | `gpt-5`, from `search.yaml` |
| Guide LLM | unused | `gpt-5-mini`, from `search.yaml`: operator texts and prompt summaries |
| Edit format | the user's (`evox.yaml`: SEARCH/REPLACE diffs) | full rewrite |
| Context programs | `search.num_context_programs`, default 4 | 2 |
| Checkpoints | by the `Runner`, every `checkpoint_interval` | none; files under `search/` only |

With `search.share_llm: true`, `setup_search()` copies the user's models into the strategy controller's
`models`, `evaluator_models` and `guide_models` (`registry.py:148`), so one endpoint serves the whole run.
Without it, the strategy level uses `search.yaml`'s OpenAI models, whatever `--model` says.

---

## 4. The main loop

`CoEvolutionController.run_discovery()` (`controller.py:153`), written as pseudo-code that follows the code:

```text
total = start + max_iterations                    # start = 1: the initial program is iteration 0
W = switch_interval or max(1, int(0.10 * max_iterations))
start_db_stats = database.get_statistics(improvement_threshold=0.01)
probe the guide and meta LLM pools (max_tokens=1); remember which answered        # :107
scorer.reset_window(best score)                   # the first window starts now
write the DIVERGE and REFINE operator texts once (section 7); assign them to the database

i = start
while i < total:
    result = _run_iteration(i, retry_times=3)     # section 5: up to 3 LLM attempts
    if result.error:
        if a fallback database exists and result.prompt is None:
            restore the fallback database (section 10.3); continue      # same i again
        # otherwise the failed child is dropped: it is never added
    else:
        database.add(child)                       # through _process_iteration_result: logging, checkpoints
    repeat result.attempts_used times: scorer.record_step(best score)
    done = i                                      # the iteration this pass started at
    i += result.attempts_used                     # every LLM attempt costs one iteration
    if i < total and _should_evolve_search():     # stagnation test, section 8.1
        _evolve_search(done)                      # sections 8 to 10; an exception is only logged
    # an exception from database.add(): restore the fallback if one exists and retry i; else i += 1

if a strategy is pending: score it and add it to H                              # section 8.3
return database.get_best_program()
```

What follows from it:

- **Sequential.** The loop never runs iterations in parallel: it does not use the base class's parallel
  loop, so `max_parallel_iterations` has no effect under EvoX.
- **Budget.** `i` advances by the number of LLM attempts used. An iteration whose child fails evaluation
  three times costs three iterations, and its child is thrown away. "100 iterations" means at most 100
  solution-generation attempts, not 100 stored children.
- **Blocking.** Writing and validating a new strategy (several LLM calls, section 11.3) happens between two
  solution iterations; the solution loop waits.
- **Failures of the strategy loop do not stop the run.** `_evolve_search()` is wrapped in a `try`; a failure
  is logged and counted in `_meta_evolution_failures`, and the current strategy stays.

---

## 5. One solution iteration

`DiscoveryController._run_iteration()` (`default_discovery_controller.py:444`) is skydiscover's generic
iteration; EvoX does not change it. Strategy code runs at step 1 and, through `add()`, at step 5.

1. **Sample.** `raw_parent, raw_context = database.sample(num_context_programs=n)` (`:454`), with n =
   `search.num_context_programs` (default 4), in the main thread, without a time limit. A dict-wrapped
   parent must hold exactly one entry; its key is the operator text. The iteration records
   `parent_info = (operator text, parent id)`, `context_info = [(label, id), ...]` and the context
   programs' ids.
2. **Prompt.** For each of at most 3 attempts, `_build_prompt()` (`:756`) gathers the parent's metrics, the
   context programs, `database.get_statistics()` (its `previous_programs` are the last 100 solutions) and
   the attempts that failed so far, and `DefaultContextBuilder.build_prompt()` fills `diff_user_message` or
   `full_rewrite_user_message`. The operator text is printed right under the "# Current Solution" heading
   (`default/builder.py:198`); the task section of both templates says that an "## IMPORTANT: ..." header
   below "# Current Solution" must be followed, and both operator templates start with
   "## IMPORTANT: YOU MUST FOLLOW THE FOLLOWING IN YOUR GENERATION". The shape of the user message:

   ```text
   # Current Solution Information
   - Main Metrics: <the parent's metrics>
   - Focus areas: <score trend versus the most recent program; "solution is long" hint>
   # Program Generation History
   ## Previous Attempts
   <the 3 best-scoring of the last 100 programs: their change summaries, metrics, outcome; no code>
   ## Other Context Solutions                        <- the strategy's context programs, with code
   ### Program 1 (combined_score: 0.8123) ...
   # Current Solution
   <operator text, when the label is not "">       <- "## IMPORTANT: YOU MUST FOLLOW ..."
   ## Program Information
   combined_score: 0.8412 ... <the parent's code, then the evaluator's feedback (artifacts)>
   # Task
   <SEARCH/REPLACE or full-rewrite instructions; "If an instruction header of "## IMPORTANT: ..." ...">
   ```

   The "Previous Attempts" block is chosen by the prompt builder, not by the strategy.
3. **Generate and parse.** One call to the main LLM; the reply is parsed as SEARCH/REPLACE diffs applied to
   the parent, or as a full rewrite (`_parse_llm_response()`, `:786`); a child longer than
   `max_solution_length` is refused.
4. **Evaluate.** The user's evaluator runs. A child **fails** when `validity` is 0 or -1, when it timed out
   without a `validity`, or when `combined_score == 0` with an error (`:632`). A failed attempt (parse,
   length or evaluation) is added to the next attempt's prompt; after the third, the iteration returns an
   error, with `attempts_used = 3`.
5. **Store.** The child (`_create_child_program()`, `:845`) carries `parent_id`, `other_context_ids`,
   `parent_info`, `context_info`, `metrics`, `iteration_found`, `metadata` (`changes`, `parent_metrics`) and
   `artifacts`. `_process_iteration_result()` (`:914`) converts it to the active strategy's program class,
   calls `database.add(child, iteration=i)`, logs the prompt, and calls the checkpoint callback every
   `checkpoint_interval` iterations.

The `Program` fields a strategy can read (`base_database.py:26`):

| Field | Content |
|---|---|
| `id`, `solution`, `language` | identity and code |
| `metrics` | the evaluator's dict; `combined_score` is the main score |
| `iteration_found` | the iteration that produced it (0 for the initial program) |
| `parent_id`, `other_context_ids` | lineage: the parent and the context programs it was made from |
| `parent_info` | `(operator text, parent id)`: which operator produced it |
| `context_info` | `[(label, id), ...]` |
| `metadata` | `changes` (summary of the diff), `parent_metrics` |
| `artifacts` | the evaluator's feedback |
| `timestamp`, `prompts`, `generation` | bookkeeping (`generation` stays 0) |

---

## 6. A search strategy is a database class

### 6.1 The contract

The strategy generator's system message (`evox/config/evox_search_sys_prompt.txt`) defines it; the
validator (section 10.1) enforces part of it.

- The file defines `EvolvedProgram(Program)`, a dataclass, and `EvolvedProgramDatabase(ProgramDatabase)`.
- `add(self, program, iteration=None, **kwargs) -> str` stores the program in `self.programs` and may update
  the strategy's own state. It must keep every program (the validator looks each one up after adding it)
  and must not change any metric. S_0's `add()` calls `_update_best_program()`; the controller wraps every
  deployed strategy's `add()` so that this call always happens (section 10.2).
- `sample(self, num_context_programs=4, **kwargs)` returns `(parent_dict, context_dict)`: `parent_dict` maps
  one operator label to exactly one program; `context_dict` maps `""` to a list of at most
  `num_context_programs` programs. The parent's label is `""` by default, `self.DIVERGE_LABEL` or
  `self.REFINE_LABEL` "when progress is stagnating"; with one of these two, the context may be empty, for a
  targeted change. Context labels must always be `""`.
- Rules from the system message: initialize every variable in `__init__`; check that a metric is a number
  before computing with it (error strings occur); keep progress state in `add()`, not `sample()`;
  programs are not hashable, so use ids; avoid deterministic choices that always pick the same program;
  "only count improvements as meaningful if they exceed 1% relative or 0.01 absolute".
- Available to the strategy: `self.programs`, `self.get(id)`, `self.rng` (a `random.Random`), the two
  labels, and everything `ProgramDatabase` offers: `get_best_program()`, `get_top_programs()`,
  `get_pareto_front()`, `get_statistics()`, and so on.

The same system message gives the strategy's score formula (section 8.2), says that a strategy failing to
improve during its window may be replaced, and lists design ideas: diversify parents and context, read
the population (spread, convergence, reuse), use the labels when stuck, and do not overuse one program.

### 6.2 The initial strategy

`initial_search_strategy.py`, S_0:

- `add()` (`:29`) stores the program, records the initial program, updates the best.
- `sample()` (`:47`) draws the parent uniformly among all programs, and the context programs by drawing
  `num_context_programs + 1` programs at random and removing the parent; both labels are `""`.
- With `pareto_objectives` set (multiobjective mode), the parent comes from the Pareto front, and the context
  prefers other front members.

This is the paper's starting point, "a simple random search strategy": parent and inspirations drawn
uniformly at random, always with free-form changes.

### 6.3 What evolved strategies look like

The paper's appendix (Tables A7 to A9) names the strategies EvoX evolved on three problems: greedy sampling
from the top candidates; stratified and multi-objective sampling (parents from different score tiers and
per-objective rankings); UCB-based parent choice penalizing overused parents; tiered sampling across score
bands; quantile-biased refinement; each with an operator bias. A sketch of such a strategy, written for
this document (it is not taken from the paper or the repository), that would pass the validator:

```python
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from skydiscover.optimize.config import DatabaseConfig
from skydiscover.optimize.search.base_database import Program, ProgramDatabase


@dataclass
class EvolvedProgram(Program):
    pass


class EvolvedProgramDatabase(ProgramDatabase):
    def __init__(self, name: str, config: DatabaseConfig):
        super().__init__(name, config)
        self.children: Dict[str, int] = {}  # parent id -> children so far
        self.best_history: List[float] = []  # best score after each add

    def add(self, program: EvolvedProgram, iteration: Optional[int] = None, **kwargs) -> str:
        self.programs[program.id] = program
        if program.parent_id:
            self.children[program.parent_id] = self.children.get(program.parent_id, 0) + 1
        self._update_best_program(program)
        self.best_history.append(self._score(self.get_best_program()))
        return program.id

    def _score(self, p: Optional[Program]) -> float:
        s = p.metrics.get("combined_score") if p else None
        return float(s) if isinstance(s, (int, float)) else 0.0

    def sample(
        self, num_context_programs: Optional[int] = 4, **kwargs
    ) -> Tuple[Dict[str, EvolvedProgram], Dict[str, List[EvolvedProgram]]]:
        candidates = list(self.programs.values())
        total = sum(self.children.values()) + 1

        def ucb(p: Program) -> float:  # high score, rarely chosen
            n = self.children.get(p.id, 0)
            return self._score(p) + 0.1 * math.sqrt(math.log(total + 1) / (n + 1))

        parent = self.rng.choice(sorted(candidates, key=ucb, reverse=True)[:3])
        h = self.best_history
        stuck = len(h) > 8 and h[-1] - h[-8] < 0.01
        label = self.DIVERGE_LABEL if stuck and self.rng.random() < 0.5 else ""
        others = [p for p in candidates if p.id != parent.id]
        context = self.rng.sample(others, min(num_context_programs or 0, len(others)))
        return {label: parent}, {"": context}
```

Because every solution is replayed through `add()` when a strategy is deployed (section 10.2), `children`
and `best_history` describe the whole run, not only the strategy's own iterations.

---

## 7. Variation operators

### 7.1 The three operators

| Operator | Label | What the solution prompt gets |
|---|---|---|
| free-form variation | `""` | nothing: the template's generic "suggest improvements" applies |
| structural variation | `DIVERGE_LABEL` | `DIVERGE_TEMPLATE` (`template.py:3`): use a fundamentally different approach, solver or library, possibly rewriting from scratch; prefer libraries the parent does not use; stay valid; then a problem-specific list of approaches |
| local refinement | `REFINE_LABEL` | `REFINE_TEMPLATE` (`template.py:31`): keep the approach; refine, tune, polish, spend more compute; then a problem-specific list of refinements |

The labels are the operator texts themselves: a strategy returns `{self.DIVERGE_LABEL: parent}`, and the
whole text (a few kilobytes) travels as the dict key into the prompt and into the child's `parent_info`.

### 7.2 Writing the operator texts, once per run

`_generate_variation_operators()` (`controller.py:350`) runs once, before the first iteration:

- With `auto_generate_variation_operators: false`, the generic `DEFAULT_DIVERGE_TEMPLATE` and
  `DEFAULT_REFINE_TEMPLATE` (`template.py:62`, `:82`) are used, without examples (skydiscover's prompt
  optimization benchmark does this).
- If the guide LLM did not answer the startup probe, or the call fails, both labels stay `""` (section 13.4).
- Otherwise `generate_variation_operators()` (`variation_operator_generator.py:479`) makes **one guide-LLM
  call**. Its system message (`COMBINED_SYSTEM_PROMPT`, `:202`) asks for two sections: "EXPLORATION"
  (`EXPLORE_SYSTEM_PROMPT`, `:27`: analyse the problem type, objective, constraints, decomposition; list 3
  to 6 categories of different approaches, libraries first, alternatives separated by "↔") and
  "EXPLOITATION" (`EXPLOIT_SYSTEM_PROMPT`, `:129`: knobs to tune within the current approach, budget, seeds,
  tolerances, polish), consistent with each other. The user message (`_build_operator_prompt()`, `:423`)
  holds the problem description (the solution system message), the installed packages, and the evaluator's
  source. The packages come from `requirements.txt` in the evaluator's folder or its `evaluator/`
  subfolder, else the repository's `requirements.txt`, else `pyproject.toml`'s dependencies, else
  `uv pip list` (`get_available_packages()`, `:261`). The initial program is not sent (the module's command
  line can send it, with `--provide-initial`).
- The reply is split into its two sections, the "EXAMPLES OF ..." lists are extracted
  (`_parse_combined_response()`, `:355`) and inserted into `DIVERGE_TEMPLATE` and `REFINE_TEMPLATE` at
  `{GENERATED_EXAMPLES}`.

The texts are assigned to the database (`_assign_labels_to_db()`, `:407`), and to every later strategy's
database before migration. They never change during a run. `search/iteration_1/labels.yaml` keeps a copy
(written only if the first strategy generation succeeds).

### 7.3 How strategies see the operators' effect

A child's `parent_info[0]` is the operator text it was made with, so a strategy learns which operator
produced which child by comparing it with `self.DIVERGE_LABEL` and `self.REFINE_LABEL`. The execution trace
of the statistics (section 9.3) prints the same text for every iteration that used an operator.

---

## 8. Detecting stagnation and scoring strategies

### 8.1 The stagnation test

`_should_evolve_search()` (`controller.py:252`) runs after every pass of the loop:

```text
current = best score
if last is None:                       stagnant = 0
elif current - last > 0.01:            stagnant = 0          # DEFAULT_IMPROVEMENT_THRESHOLD
else:                                  stagnant += 1
last = current
if stagnant >= switch_interval:        stagnant = 0; return True
```

- A strategy runs for at least about W iterations, and for as long as some iteration raises the best score
  by more than 0.01 at least once every W iterations; the paper's tables show windows of 10 to 26
  iterations for W = 10.
- The test compares consecutive iterations, not the start and end of a window: improvements of 0.01 or less
  never reset the counter, however many there are (section 13.5).
- The counter counts passes of the loop, while the budget counts LLM attempts (section 4).
- The threshold is absolute. skydiscover's benchmarks divide their score by the best known result (circle
  packing: the sum of radii over 2.635), so 0.01 means 1% of the target.
- If the meta LLM did not answer the startup probe, the test always returns false: no strategy is ever
  replaced.

### 8.2 The scoring window and J

`LogWindowScorer` (`search_scorer.py:12`) keeps a window: a start score, a start iteration, and the best
score after every attempt.

- `reset_window(best, start_iteration)` (`:23`) is called at the start of the run, before each strategy
  generation, and again when a new strategy is deployed, with that iteration.
- `record_step(best)` (`:35`) is called once per LLM attempt (section 4).
- `compute_metrics()` (`:48`) computes

  ```text
  J = (max(start, recorded bests) - start) * (1 + ln(1 + max(0, start))) / sqrt(horizon)
  ```

  with `horizon = switch_interval`, however long the strategy actually ran. It returns `combined_score` (J),
  `window_start_iteration`, `search_window_start_score`, `search_window_end_score` and `search_horizon`.

The weight `1 + ln(1 + start)` favours gains made from a higher starting score, where gains are harder. For
example, with W = 10, a strategy that took the best score from 0.60 to 0.66 scores
0.06 × (1 + ln 1.6) / √10 = 0.06 × 1.470 / 3.162 ≈ 0.0279.

### 8.3 When a strategy gets its score

- **The initial strategy**, at the first stagnation: `_initialize_first_search_program()`
  (`controller.py:307`) scores the window opened at the start of the run, wraps S_0's code in a strategy
  `Program` with these metrics, the statistics at the start of the run and now (`metadata.start_db_stats`,
  `end_db_stats`), adds it to H as its first entry, and goes on to generate S_1.
- **A deployed strategy** stays *pending* (`_pending_search_result`) until the next stagnation or the end
  of the run. Then `_finalize_pending_search()` (`:288`) calls `_assign_search_score()` (`:640`), which
  computes J over the strategy's window, adds the metrics and `end_db_stats`, and adds the strategy to H
  (`search_controller.postprocess_result()`); the saved metadata is updated.
- A strategy that failed validation, or was rolled back at run time, never gets a score and never enters
  H. When generating a new strategy fails, the current strategy keeps running, but it is not pending any
  more, so the rest of its run is never scored.

So H holds one entry per strategy that was deployed and replaced (or ran until the end), scored over its
whole deployment.

---

## 9. Writing a new strategy

### 9.1 The flow

`_evolve_search()` (`controller.py:274`): if H is empty, score S_0 and add it (section 8.3); otherwise
score the pending strategy, if any, and add it. Then reset the window and call
`_generate_and_validate_search_algorithm()` (`:412`):

1. Gather the statistics (`_build_search_stats()`, `:466`): the coming window (start iteration, total
   iterations, `switch_interval`, threshold), the problem description (the solution system message), the
   evaluator's path, and `database.get_statistics(improvement_threshold=0.01)` (φ).
2. Put them in `search_controller._prompt_context`, then run one iteration of the strategy controller:
   `search_controller.run_discovery(start_iteration=k, max_iterations=1, post_process_result=False)`, which
   samples H, builds the prompt (section 9.4), calls the meta LLM, parses a full rewrite, and evaluates it
   with the validator (section 10.1), with up to 3 attempts (section 9.5).
3. On failure: log it (section 11.1), count it, keep the current strategy.
4. On success: save the code, then deploy it (section 10.2). If deployment fails, it counts as a validation
   failure. Otherwise the new strategy becomes pending, and its window starts at this iteration.

### 9.2 The strategy archive H

`SearchStrategyDatabase` (`search_strategy_db.py:16`) stores strategies as `Program` objects whose
`solution` is the code and whose `metrics.combined_score` is J. Its `sample()` (`:37`) returns:

- **parent**: the strategy with the highest J, always (deterministic);
- **context**: `min(2, |H|)` strategies drawn uniformly from all of H, minus the parent: 0 to 2 strategies.
  At the first generation H holds only S_0, so there are none.

### 9.3 The population descriptor φ

`ProgramDatabase.get_statistics(num_recent_iterations=100, k=20, improvement_threshold)`
(`base_database.py:458`) returns:

| Key | Content |
|---|---|
| `population_size` | number of solutions |
| `solution_score_summary` | best, 75th, 50th and 25th percentiles, worst; the share of programs in four score tiers (top, upper-mid, lower-mid, bottom) and each tier's bounds; the number of distinct scores (to 4 decimals) |
| `avg_solutions_per_parent` | children per distinct parent, on average |
| `top_solution_scores` | the 20 best scores |
| `recent_solution_stats` | over the last 100 iterations: the **execution trace** (for each iteration: the child's id and score; the parent's label, id and score; each context program's label, id and score), the score trajectory, the parents' scores, the iterations since a program first came within the threshold of the current best ("iterations without improvement"), the most reused parent and context program (share and score) |
| `previous_programs` | the last 100 solutions themselves (`Program` objects) |

Failed children are not in the database (section 4), so φ never counts failures.

### 9.4 The strategy prompt

`EvoxContextBuilder.build_prompt()` (`context_builder/evox/builder.py:136`) builds it.

**System message**: the whole of `evox_search_sys_prompt.txt` (section 6.1): role, the score formula, the
class contract, the operator labels and when to use them, design ideas, constraints.

**User message**: `search_evolution_user_message.txt`, whose five slots are filled as follows.

| Slot | Content | Built by |
|---|---|---|
| `{problem_template}` | a guide-LLM summary of the problem description and the evaluator's source: "**Task:** ... **Scoring:** combined_score = ... **Goal:** ...", under 100 words; cached for the run; the raw texts if the call fails | `_generate_problem_context_summary_async()` (`:102`), template `problem_context_summary_system_message.txt` |
| `{search_window_context}` | where the new strategy starts, that it runs at least `switch_interval` iterations, more if improving, and is replaced if it fails to improve by more than 0.01; "exactly one program is generated per iteration" | `format_search_window_context()` (`formatters.py:421`) |
| `{population_state}` | a guide-LLM summary of the formatted statistics: a one-line state, 3 or 4 key numbers, 2 or 3 patterns, "every statement must cite a number"; the raw statistics are not shown | `format_population_state()` (`formatters.py:227`), then `_generate_stats_insight_async()` (`:91`), template `stats_insight_system_message.txt` |
| `{current_program}` | the parent strategy: "Focus areas", its J, the iterations it ran, the best score at its start and end, its code | `format_current_program()` (`formatters.py:326`), `identify_search_improvement_areas()` (`:373`) |
| `{other_context_programs}` | the other strategies: their J, iterations and score change, and a guide-LLM summary *instead of their code* | `format_search_algorithms()` (`formatters.py:571`), `_generate_batch_summaries_async()` (`:128`) |

The summaries of the other strategies come from one guide-LLM call
(`templates/batch_summary_prompt.txt`, split at its `===SYSTEM===`, `===PER_PROGRAM===` and
`===INSTRUCTIONS===` markers). For each strategy it sends the whole strategy system message again, the
strategy's code, and the change of the population statistics from the start to the end of its window,
including the execution trace (`format_db_stats_diff()`, `formatters.py:106`); it asks for what each
strategy did, what helped, and one key insight per strategy, under 60 words, with `[PROGRAM n]` markers
that `parse_batch_summaries()` (`:603`) uses to split the reply.

The three guide calls (population summary, problem summary, strategy summaries) run concurrently; one that
fails gives an empty string.

The shape of the result (numbers invented):

~~~text
[system] evox_search_sys_prompt.txt
[user]
# DOWNSTREAM PROBLEM CONTEXT
<**Task:** ... **Scoring:** combined_score = ... **Goal:** Maximize `combined_score`>
---------------------------
# Search Algorithm Information
## Your Algorithm's Search Window
- Your newly designed search algorithm will start at iteration 23 out of 100. It will run for at least
  10 iterations (potentially more if improving), but will be cut to just 10 iterations if it fails to
  improve the solution score by more than 0.0100.
- If your algorithm fails to improve the solution score by more than 0.0100 during this window, it will
  be replaced.
- Goal: Design a better search strategy ... - NOTE: Exactly one program is generated per iteration. ...
## Solution Population Statistics
<guide-LLM summary of the statistics>
# What You Are Writing
## Current Search Program
### Metrics
Focus areas:
- Search algorithm score declined: 0.6412 → 0.0279. Consider revising.         <- section 13.2
- Consider simplifying - solution length exceeds 500 characters
Search Algorithm Score = 0.0279
This search algorithm ran from iteration 12 to 12 (0 iterations)                <- section 13.1
This search algorithm changed the downstream solution combined_score by: 0.6000 -> 0.6600 (+0.0600)
### Solution
```python
<the parent strategy's code>
```
## Other Reference Programs
Diverse search programs that may inspire new ideas:
### Program 1
#### Metrics
Search Algorithm Score = 0.0000 ...
#### Summary
<guide-LLM summary>
---------------------------
# Task
Rewrite the program to improve search algorithm score based on the population state. ...
Keep things SIMPLE. ... maintains the same inputs and outputs ...
```python
# Your rewritten search algorithm here
```
~~~

### 9.5 Calling the meta LLM

The strategy controller's `_run_iteration()` is the generic one (section 5): one meta-LLM call; the reply's
first fenced code block is the new strategy (`parse_full_rewrite()`); the validator evaluates it; a result
with `validity: 0` is a failed attempt, and up to 3 attempts are made. `EvoxContextBuilder` ignores the
failed attempts the controller passes it, so every retry sends the same prompt, without the error, and
repeats the guide calls (section 13.3). The three attempts are the paper's "retries generation up to a
fixed budget".

---

## 10. Validating and deploying a strategy

### 10.1 The validity test

`search_strategy_evaluator.evaluate(path)` (`:55`) is the strategy controller's "evaluator". It returns
`{"validity": 1, "combined_score": 0.0}` or `{"validity": 0, "error": message, "combined_score": None}`,
stopping at the first failed check:

1. **Load**: the file imports, and defines `EvolvedProgramDatabase` and `EvolvedProgram`.
2. **Structure**: the class names, `EvolvedProgramDatabase` subclasses `ProgramDatabase`, `EvolvedProgram`
   subclasses `Program`, `sample()`'s second parameter is `num_context_programs`, and its return
   annotation, if any, is a 2-tuple.
3. **Construction**: `EvolvedProgramDatabase("test_db", DatabaseConfig())` works (the labels are set to `""`
   first if the class lacks them).
4. **add**: one program added, its id returned, found by `get()`, its metrics unchanged in the stored and
   in the original object.
5. **add and sample**: 10 more programs (scores 0.0 to 0.9), each found with unchanged metrics; then 10
   calls of `sample(num_context_programs=4)`: a 2-tuple of dicts, exactly one parent, a `Program` in the
   database, context values are lists of `Program`s in the database, at most `min(4, size)` context
   programs, all metrics unchanged.
6. **Error strings**: a program whose metrics include an `"error"` string; 5 more `sample()` calls.
7. **Immutability**: a program with five metrics, unchanged after `add()`.
8. **Migration**: a new database filled with 5 base-class `Program`s (not `EvolvedProgram`s), then 3
   `sample()` calls; this catches strategies that filter with `isinstance(p, EvolvedProgram)`.
9. **Context count**: `sample(num_context_programs=3)` returns at most 3 context programs.

The test runs in a thread (`Evaluator._run_stage()`, `evaluation/evaluator.py:207`), in the main process,
with `search.yaml`'s timeout of 3,600 seconds.

### 10.2 Deploying: the hot swap

`_switch_to_new_search_algorithm()` (`controller.py:482`):

1. Write the code to a temporary file and import it with `load_database_from_file()`; set
   `DIVERGE_LABEL`/`REFINE_LABEL` on the class if it lacks them.
2. Create the database with the run's `search.type` and `EvoxDatabaseConfig`; remember its program class.
3. Assign the operator texts (`_assign_labels_to_db()`).
4. **Migrate** (`_migrate_to_db()`, `:564`): every solution, in order of `iteration_found`, is converted to
   the new program class (`prog_class(**program.to_dict())`) and passed to the new `add()`, so the new
   strategy rebuilds its state from the whole history. Logged prompts are copied too.
5. Wrap `add()` so that `_update_best_program()` always runs after it (`_wrap_add_method()`, `:629`), and
   compute the best program.
6. Keep the old database and code as the **fallback**; make the new database the controller's (and the LLM
   judge's, if any). The `Runner` picks it up at the next checkpoint (`_sync_database()`, `runner.py:432`).

Any exception during these steps means a failed deployment: the old strategy stays.

### 10.3 Falling back at run time

When a solution iteration returns an error without a prompt (an exception in `sample()` or before the
prompt was built, but also an LLM call failure, section 13.7), or `database.add()` raises, and a fallback
exists, `_restore_fallback_database()` (`:535`):

1. adds every solution the failing strategy stored, and the fallback does not have, to the fallback
   database;
2. makes the fallback the active database again, with its code;
3. drops the pending strategy (it is never scored or added to H), counts a strategy evolution, and clears
   the fallback;
4. repeats the same iteration (the loop does not advance `i`).

The fallback stays armed from deployment until it is used, possibly for the strategy's whole life.

---

## 11. Outputs, checkpoints and LLM calls

### 11.1 Files

```text
<output_dir>/
  logs/, best/, checkpoints/checkpoint_<i>/        Runner: the solution database and best program
  search/
    iteration_1/  code.py  metadata.json  labels.yaml      (labels.yaml only in iteration_1)
    iteration_2/  code.py  metadata.json
    iteration_k/  failed_attempts.json  failed_attempt_<n>.py  failed_attempt_<n>_prompt.json
                  failed_attempt_<n>_llm_response.txt  code.py or active_code.py  metadata.json
```

- `metadata.json` (`save_search_algorithm()`, `coevolve_logging.py:70`) is written when a strategy is
  generated (`pending_score: true`) and completed when it is scored (`update_saved_search_algorithm_score()`,
  `:139`): J, the window metrics, `is_new_best`, the statistics at the start and end of its window.
- A failed generation or validation (`handle_generation_failure()`, `:175`) writes the failed attempt (code,
  prompt and reply when available, error, stage) and the code of the strategy that stays (`active_code.py`
  when `code.py` holds the failed candidate), and marks the metadata `is_fallback`.
- S_0 gets no folder; the prompts of successful generations are not saved.

### 11.2 Checkpoints and resuming

The `Runner` saves the solution database every `checkpoint_interval` iterations and at the end. Nothing of
the strategy level is checkpointed: the active strategy's code, H, the operator texts, the window and the
stagnation counter. A resumed run rebuilds the database from S_0's file, loads the solutions, and starts
the strategy level from scratch: S_0, an empty H, new operator texts (section 13.13).

### 11.3 LLM calls

| When | Model (default) | Calls |
|---|---|---|
| start | guide and meta pools | 2 probes, `max_tokens=1` |
| start | guide (`gpt-5-mini`) | 1: the operator texts |
| every solution attempt | main (the user's) | 1 |
| every strategy-generation attempt (up to 3 per switch) | guide | 1 population summary; 1 problem summary (the first time only, then cached); 1 summary of the other strategies (when there are any) |
| | meta (`gpt-5`) | 1: the strategy |

With 100 iterations and W = 10 there are at most 9 switches (the first after iteration 11, then every 10
iterations at the soonest). The paper reports that on the Heilbronn triangle problem, EvoX needed less than
1 dollar of generation cost to pass a score of 0.031 (Figure 4b).

### 11.4 Multiobjective mode

With `pareto_objectives` set in `search.database`, the base class keeps a cached Pareto front,
`get_best_program()` returns the front's member with the best proxy score (`fitness_key`, else
`combined_score`, else the mean of the objectives), S_0 samples parents from the front, and the stagnation
test and J use that proxy (`_get_best_score()`, `controller.py:588`). Without it, everything uses
`combined_score`.

---

## 12. Paper versus code

| Aspect | Paper | Code |
|---|---|---|
| When to change strategy | after each window of W steps, if the window's gain Δ = s_end − s_start < τ (Algorithm 1) | when the best score has not risen by more than 0.01 from one iteration to the next for W passes in a row (section 8.1) |
| Window length | fixed, W | at least W; longer while the strategy keeps improving |
| Strategy score J | Δ · log(1 + s_start) / √W | Δ · (1 + ln(1 + max(0, s_start))) / √W, where Δ covers the whole deployment and W = `switch_interval` whatever its length |
| Entries of H | (S_t, φ_t, J_t) after every window | one per deployed strategy, added when it is replaced or at the end; φ kept as the statistics at its start and end |
| Parent strategy | "score-biased selection" | always the highest J |
| Inspiration strategies | strategies with strong progress, and strategies that did well "under similar population descriptors" | up to 2 drawn uniformly from H |
| φ for the generator | the population descriptor | statistics formatted as text and summarized by a guide LLM; only the summary is shown |
| Validity | VALID(S'); retry up to a budget; fall back to the previous strategy | synthetic tests, up to 3 attempts (the error not shown), keep the current strategy; plus a check when deploying and a fallback at run time |
| Operators | instantiated at the start of each problem by a lightweight model, from the problem description | one guide-LLM call (problem description, evaluator source, installed packages) fills two templates; free-form adds no text |
| Initial strategy | random parent and inspirations | the same, with 4 context programs |
| Generator prompt | Appendix C: a system message ("You are an expert software developer tasked with ...") and a user message with five slots | the system message is `evox_search_sys_prompt.txt` (the paper's "System Model" box); the user message has the same five slots. `context_builder/evox/templates/system_message.txt` is unused |
| Budget | T evaluation steps | T LLM attempts; failed children are not stored |

---

## 13. Quirks and weak spots

Observations made while reading the code, numbered for reference from the design decisions. None was
confirmed by running skydiscover.

1. **Window length lost.** The scorer stores the window length under `search_horizon`
   (`search_scorer.py:82`), but the prompt code reads `search_window_horizon` from a strategy's metrics
   (`context_builder/evox/builder.py:175`, `formatters.py:345`, `:516`, `:546`), and finds 0. So the
   prompt says every strategy "ran from iteration k to k (0 iterations)", and the statistics are never cut
   to a strategy's window: the population summary and the summaries of past strategies use the last 100
   iterations, including those run by earlier strategies.
2. **Meaningless focus areas.** `identify_search_improvement_areas()` compares the parent strategy's J with
   the score of the most recent *solution* (the `previous_programs` of the solution statistics,
   `default_discovery_controller.py:774`), so it usually reports "Search algorithm score declined". The
   "consider simplifying" hint fires for any strategy over 500 characters, that is, always.
3. **Blind retries.** A strategy that fails validation is retried with the same prompt: the error is not
   shown (`EvoxContextBuilder` ignores `context["errors"]`), and the guide summaries are recomputed.
4. **Missing operators when the guide model fails.** If the guide LLM does not answer, both labels stay
   `""`, although the log says default operators are used: structural variation and refinement then add
   nothing to the prompt and cannot be told apart from free-form changes.
5. **Small gains count as stagnation.** The stagnation test compares consecutive iterations, so a strategy
   that raises the best score by 0.005 at every iteration is replaced after W iterations, while the
   paper's window test would keep it (cumulative gain 0.05). The counter counts loop passes while the budget
   counts attempts.
6. **J ignores how long a strategy ran.** It divides by √`switch_interval`, not by the deployment's length:
   a strategy that kept improving for 40 iterations collects all its gain over the same denominator as one
   that ran 10.
7. **Fallback triggered by LLM errors.** Any iteration that errors before a prompt exists triggers the
   fallback, including a failed call to the solution LLM ("LLM generation failed",
   `default_discovery_controller.py:557`), so a network error can roll back a working strategy. The fallback
   stays armed for the new strategy's whole life. When `add()` raises, the child already generated and
   evaluated is lost, and the repeated iteration is not counted in the budget.
8. **Failures are invisible.** Failed children are never stored, so neither strategies nor φ can see what
   failed (failure rates per operator, per parent), although the strategy system message says that "failure
   programs can also provide useful insights".
9. **Unsandboxed strategy code.** Generated strategies run in the main process: `sample()` and `add()` are
   called without a time limit (an infinite loop hangs the run; a slow `sample()` slows every iteration),
   imports are not restricted, and the validation thread cannot be killed when it times out. Validation
   fills its test database with 13 synthetic programs at most, so speed on a real population and degenerate
   behaviour (always the same parent) are not tested.
10. **Validation and deployment configs differ.** The tests build the strategy with `DatabaseConfig()`; the
    run builds it with `EvoxDatabaseConfig`. A strategy that reads, for example, `self.config.pareto_objectives`
    fails validation although it would work.
11. **Dead SOTA line.** The formatters print a "gap_to_SOTA" line when the statistics hold `SOTA_score`;
    nothing sets it.
12. **Bulky records.** The operator texts are copied into every child's `parent_info` and printed in full in
    every line of the execution trace that used one, which inflates the strategy-summary prompts; every H
    entry keeps two complete statistics snapshots, each with the last 100 solutions' code.
13. **No resume of the strategy level** (section 11.2).
14. **Two thresholds.** The statistics saved with a scored strategy use `get_statistics()`'s default
    threshold of 0.10 (`controller.py:298`); the prompts use 0.01.
15. **Inconsistent summary instructions.** The strategy-summary call's system section asks for "TECHNIQUE"
    and "KEY TAKEAWAYS" in under 70 words; its user section asks for "SIGNALS OBSERVED", "WHAT SEEMED TO
    HELP" and "POTENTIAL KEY INSIGHT" in under 60.
16. **Documentation drift.** `search/evox/README.md` names `coevolve_controller.py` (the file is
    `controller.py`); the controller's warning says labels "fall back to generic defaults" (they become
    empty, item 4).
17. **No parallel iterations** (section 4).
18. **Strategy models ignore `--model`.** Without `share_llm: true`, the strategy level calls OpenAI's
    `gpt-5` and `gpt-5-mini` whatever model the solution level uses.
19. **Absolute threshold.** τ = 0.01 suits scores normalized to about 1, as skydiscover's benchmarks are; on
    another scale it means something else.
20. **Strategies cannot forget.** The validator requires `add()` to keep every program, so a strategy
    always manages the whole history; any smaller "active population" lives inside its own state.
21. **A self-contradicting refinement operator.** `REFINE_TEMPLATE` asks to "keep the same fundamental
    approach", but its "Tools Available" part, shared with `DIVERGE_TEMPLATE`, says "Feel free to break from
    the existing code entirely".
