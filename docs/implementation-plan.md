# Implementation plan for my-evox

The order in which my-evox is built from [design-decisions.md](design-decisions.md) (D1 to D46, Appendices A
to C). The design says what the finished system does; this plan says in which order to get there. It
changes nothing in the design.

The plan follows one rule, the one that worked for my-evolve:

> **Build simple components, then improve them gradually.**

Phase 0 builds every component of my-evox in the simplest form that works, both levels included, and wires
them so that a run goes end to end: solutions evolve under a strategy, the strategy stagnates, the
strategy model writes a new one, and the run goes on under it. Every later step improves one thing, and the
loop still runs after it. The components reach their designed form one small step at a time; $K = 1$ comes
first, then $K > 1$ (D19), then ALE-Bench-Lite, then the experiments.

Read against: design-decisions.md at `1beea65`; skydiscover at `0d932b6`; my-evolve at `04879a1`.

## The loop

This is the loop my-evox writes from Phase 0 on, both levels in a few lines:

```python
strategy = scheduler.pick(active)                         # D20; with K = 1, the only active strategy
selection = strategy.select(store.view())                 # D11: parent, inspirations, change size
prompt = solution_prompt.build(selection, strategy.direction, failed_attempts)
reply = solution_llm.complete(prompt)
child = evaluator.evaluate(apply_reply(selection.parent, reply))
store.add(child, strategy, selection.change)              # D40, D41
for s in active: s.observe(child)                         # D11
if judge.update(child).retired: writer.replace(strategy)  # D24, D25; then D27 to D34
```

These lines keep their shape to the end. What changes is what happens inside each call, plus four
additions around them: checks and retries between the reply and the store (Phase 2), strategies moved into
Docker workers (Phase 3), worker threads running several iterations at once (Phase 5), and several active
strategies with a real scheduler (Phase 6).

## How each step is carried out

- **One idea per step.** A step changes one thing, and its diff can be read in one sitting: as a rule of
  thumb, under about 300 changed lines, tests included. A step that grows past that is split in two.
- **The loop always runs.** A step ends with ruff (lint and format), mypy in strict mode and every test
  passing (D46), including the end-to-end test `tests/test_loop.py` (from step 0.8, completed in step 0.10: a
  whole run on a toy problem, with fake solution and strategy models). A step that changes what a real run does also ends with a short
  real run (a few iterations, a cheap model, D5).
- **Simplifications are written down.** Each step's **Not yet** says what it deliberately leaves out, and
  names the step that adds it. So the code is always simpler than the design in known ways, never by
  accident.
- **Settings arrive with their feature.** The problem file accepts only the keys the code already uses; an
  unknown key is an error from step 0.3 on (D45).
- **The design stays the target.** A decision that changes during the build is changed in
  design-decisions.md in the same commit.
- **Explained as it is built** (D46). A step's text here is its design; a detail it leaves open is settled
  when the step starts. Once a step is done, a short walk-through of its diff says what changed, where, and
  why.
- **One commit per step**, named after it ("Step 1.2: evaluators in containers"), with plain-English
  docstrings and comments (D46).
- **The other repositories are sources, not dependencies** (D1). A step's **From** names the code it copies
  and adapts; a copied file keeps its licence notice. Nothing is imported from my-evolve or skydiscover.
- **No experiment model while building** (D5). Tests use fake models; real runs use `claude-haiku-5-5`
  through Anthropic's OpenAI-compatible endpoint (Milestone 0 showed a 3B local model cannot write
  strategies). GPT-5 is spent only in Phase 8.
- **Platforms** (D46). The code avoids anything specific to one system; Docker is needed from Phase 1 (Docker
  Desktop on Windows). Whether `ale_bench` runs on Windows is checked at step 7.1.

## Overview

| Step | Builds | Decisions |
|---|---|---|
| **Phase 0** | **Both loops, end to end** | |
| 0.1 | Project skeleton | D46 |
| 0.2 | A toy problem, and circle packing from skydiscover | D3 |
| 0.3 | Records: `Result`, `Solution`, `Problem` | D40, D45 |
| 0.4 | Evaluator, basic: the problem's evaluator as a subprocess | D3 |
| 0.5 | The store and the random strategy, in the run's process | D11, D17, D40 |
| 0.6 | Solution prompt, basic | D38 |
| 0.7 | LLM, basic: one model, the reply's first code block | D5, D37 |
| 0.8 | The solution loop and the command line | D8, D45 |
| 0.9 | The judge, basic: records, score, stagnation | D23 to D25 |
| 0.10 | Writing and deploying a strategy, basic | D13, D16, D26, D31, D32 |
| M0 | The first real run | |
| **Phase 1** | **Solutions evaluated as designed, and what Milestone 0 asked for** | |
| 1.1 | Statuses | D8, D33 |
| 1.2 | Evaluators in containers; status `timeout` | D3, D10 |
| 1.3 | Containers never outlive a run | D10 |
| 1.4 | Circle packing, scored exactly as in the paper's runs | D3, D4 |
| 1.5 | MinMaxMinDist | D3 |
| 1.6 | Results in the prompt | D38 |
| 1.7 | Every LLM call saved, with its role (was 2.1) | D6, D40, D41 |
| 1.8 | The generic operator texts | D13, D14 |
| 1.9 | The random strategy written as strategy code | D17, D31 |
| M1 | The first run in containers | |
| **Phase 2** | **The solution prompt and the LLMs** | |
| 2.2 | my-evolve's reply parser, and descriptions | D38 |
| 2.3 | Diffs | D37 |
| 2.4 | Evolve blocks enforced; status `rejected` | D2, D33 |
| 2.5 | Compiling and entry functions | D33 |
| 2.6 | Duplicates | D33, D40 |
| 2.7 | Retries for solutions | D6, D35 |
| 2.8 | The operator texts' examples | D13, D14 |
| 2.9 | The solution prompt of Appendix A | D13, D38 |
| 2.10 | Model settings, API keys, test requests | D5, D39, D45 |
| M2 | The first run with designed solution prompts | |
| **Phase 3** | **Strategies as designed** | |
| 3.1 | The strategy worker and its messages | D10, D11 |
| 3.2 | Strategies in Docker | D10 |
| 3.3 | The view, as designed | D15 |
| 3.4 | Strikes, and the random fallback | D17, D36 |
| 3.5 | The weighted built-in, and the initial strategy as a setting | D17 |
| 3.6 | Checks before deployment, as designed | D32 |
| 3.7 | Repairing a strategy | D34, D39 |
| M3 | The first run with sandboxed strategies | |
| **Phase 4** | **Judging, the archive and the strategy prompt** | |
| 4.1 | The strategy score, as designed | D23, D24 |
| 4.2 | Stagnation, as designed | D25 |
| 4.3 | Archive entries and champions | D26, D41 |
| 4.4 | The parent strategy and the inspiration strategies | D27, D28 |
| 4.5 | Population statistics | D30 |
| 4.6 | The strategy prompt of Appendix B | D31 |
| M4 | The first run of the whole method, $K = 1$ | |
| **Phase 5** | **The run** | |
| 5.1 | Logging and the summary | D6, section 13 |
| 5.2 | The complete run folder | D41, D45 |
| 5.3 | Several iterations at once | D9 |
| 5.4 | Errors inside an iteration | D39 |
| 5.5 | Ctrl+C and SIGTERM | section 13 |
| 5.6 | Continuing a run | D16, D42, D44 |
| 5.7 | Refusing to continue a changed problem | D45 |
| 5.8 | Target score and patience | section 13 |
| 5.9 | The report | D43 |
| 5.10 | The ablations' settings | D4, D24 |
| M5 | The whole design, $K = 1$ | |
| **Phase 6** | **Several active strategies** | |
| 6.1 | $K$ slots and round-robin with warm-up | D19, D20 |
| 6.2 | Starvation | D25 |
| 6.3 | Writing strategies in the background | D22 |
| 6.4 | The sequential start | D21 |
| 6.5 | The active strategies in the strategy prompt | D28, D31 |
| 6.6 | The bandit | D20 |
| M6 | The first run with $K = 2$ | |
| **Phase 7** | **ALE-Bench-Lite** | |
| 7.1 | `ale_bench` on this machine | D3 |
| 7.2 | C++ solutions | D2, D33, D40 |
| 7.3 | One ALE problem end to end, and its private evaluation | D3, D4 |
| 7.4 | The other nine problems | D3 |
| M7 | The first ALE-Bench-Lite run | |
| **Phase 8** | **The experiments** | |
| 8.1 | Cost pilot | D4, D6 |
| 8.2 | The math problems | D4 |
| 8.3 | ALE-Bench-Lite | D4 |
| 8.4 | The ablations | D4 |

## How each component grows

| Component | In Phase 0 | Then, step by step |
|---|---|---|
| Evaluator | the problem's evaluator run as a subprocess on the host, JSON back; a score or an error | statuses (1.1) → containers, time limit (1.2) → cleanup (1.3) → the paper's exact scores (1.4, 1.5) → results shown (1.6) → C++ and `ale_bench` (7.1 to 7.3) |
| Solution prompt | one system message; the inspirations and the parent with their scores and code; the direction, if any | results (1.6) → the generic operator texts (1.8) → descriptions (2.2) → diffs (2.3) → the evolve-block rule (2.4) → failed attempts (2.7) → the operator texts' examples (2.8) → Appendix A's text and budget (2.9) |
| Solution LLM and reply | one model; the reply's first code block | calls saved (1.7) → my-evolve's parser (2.2) → diffs (2.3) → checks (2.4 to 2.6) → retries (2.7) → settings, keys, test requests (2.10) |
| Store and view | every solution in memory; a view listing working solutions with id, score and code | fingerprints (2.6) → the designed view (3.3) → replay from the run folder (5.6) |
| Strategies | `EvolvedSearchStrategy` loaded with `exec` in the run's process; the random built-in | the random built-in as strategy code (1.9) → a worker process (3.1) → Docker (3.2) → the view (3.3) → strikes (3.4) → the weighted built-in (3.5) |
| Judge | records, a sum-of-records score, stagnation over the last $W$ children with an absolute $\tau$ | the designed score (4.1) → relative $\tau$, minimum trial, no replacement near the end (4.2) → starvation (6.2) |
| Strategy writer | a short prompt (problem, best scores and the best solution's results, the current strategy's code); direction and code parsed; compile and interface checks; one attempt | checks as designed (3.6) → repair (3.7) → archive and champions (4.3) → parent and inspiration strategies, the initial one left out (4.4) → statistics (4.5) → Appendix B (4.6) → in the background (6.3) → active strategies shown (6.5) |
| Scheduler | the one active strategy | $K$ slots, warm-up and round-robin (6.1) → sequential start (6.4) → the bandit (6.6) |
| Loop and run folder | one iteration after another; console lines; `programs.jsonl`, `strategies.jsonl`, `best_program` | `llm_calls.jsonl`, `run.json` (1.7) → logging (5.1) → the full run folder (5.2) → threads (5.3) → errors (5.4) → Ctrl+C (5.5) → continuing (5.6, 5.7) → target and patience (5.8) → the report (5.9) |

The evaluator and the strategies both run LLM-written code on the host until they move into Docker (steps 1.2
and 3.2). Until then, runs are short, watched, and made with a cheap model; from Milestone 3 on, every piece
of LLM-written code runs in a container (D10).

---

## Phase 0: both loops, end to end

The goal: `scripts/run.py` evolves circle packing with a cheap model, the random strategy stagnates, the
strategy model writes a new strategy with a direction, and the run goes on under it. Each component is as
simple as it can be while doing its job.

### Step 0.1. Project skeleton
- **Builds.** `pyproject.toml`: the package `my_evox` in `src/`, Python 3.11 or later, dependencies `openai`
  and `pyyaml`; development extras ruff, mypy, `types-PyYAML`; my-evolve's ruff and mypy settings (mypy
  strict). An empty `src/my_evox/__init__.py`; a `tests/` folder with one test that imports the package; a
  README with the set-up and the check commands, for Linux and Windows; `runs/` in `.gitignore`.
- **From.** my-evolve's `pyproject.toml` and README.
- **Check.** `pip install -e ".[dev]"` works; ruff, mypy and `unittest` pass.

### Step 0.2. A toy problem, and circle packing from skydiscover
- **Builds.** `problems/circle_packing/`: skydiscover's `benchmarks/math/circle_packing/` at `0d932b6`, the
  initial program, the `evaluator/` folder (its `evaluator.py`, `Dockerfile`, `evaluate.sh`,
  `requirements.txt`) and skydiscover's licence; a `problem.yaml` with `name`, `description` (the benchmark's
  `prompt.system_message`, verbatim, D3) and an `llm` section naming one cheap model. For the tests,
  `tests/toy/`: an initial program whose `solve()` returns a number, and an evaluator in the same protocol
  (`evaluator.py PROGRAM_PATH` prints one JSON object with `combined_score`), scoring that number divided by
  10, in milliseconds.
- **Not yet.** Running the evaluator in its container (1.2); checking skydiscover's two circle-packing
  evaluators against each other (1.4).
- **Check.** Run by hand, the circle-packing evaluator scores the initial program and prints its JSON.

### Step 0.3. Records: `Result`, `Solution`, `Problem`
- **Builds.** `records.py`: `Result` with `score` (none when the evaluation failed), `error`, `metrics`;
  `Solution` with `id` (a UUID, D40), `code`, `result`, `parent_id`, `iteration`, `strategy_id`, `change`;
  `to_dict()` and `from_dict()`. `problem.py`: `Problem` (`name`, `description`, the initial program and
  evaluator paths, `llm.model`, `llm.api_base`) and `Problem.load(path)`: YAML read as plain data, required
  keys checked, unknown keys refused with their location (D45).
- **Not yet.** Every other attribute of the design: each arrives with the step that uses it.
- **From.** my-evolve's `program.py` and `problem.py`, cut down.
- **Check.** Round trips through `to_dict`; a missing or unknown key is a clear error.

### Step 0.4. The evaluator, basic
- **Builds.** `evaluator.py`: `Evaluator(problem)`; `evaluate(code)` writes the code to a temporary file, runs
  the problem's `evaluator.py` on it as a subprocess, reads the JSON it prints, and returns a `Result`: the
  `combined_score` as the score, the other numbers as metrics; a crash, invalid JSON or `validity` 0 as an
  error.
- **Not yet.** Containers and a time limit (1.2): until then, the solution model's code runs on the host with
  your files and network, and a program that never ends stops the run; Phase 0's runs are short and watched.
  Statuses (1.1).
- **From.** skydiscover's container protocol (`evaluation/wrapper.py`, `container_evaluator.py`'s
  `_parse_output`).
- **Check.** The toy problem's working, failing and crashing programs; circle packing's initial program
  scores as in step 0.2.

### Step 0.5. The store and the random strategy, in the run's process
- **Builds.** `store.py`: `Store` keeps every solution in memory, by id, in the order added (D40);
  `best()`; `view()`, a read-only list of the working solutions with id, score and code. `strategies.py`:
  `Selection(parent_id, change, inspiration_ids)`; the abstract `EvolvedSearchStrategy` with `observe(child)`
  and `select(view)` (D11); `RandomStrategy`, the paper's initial strategy (D17): a parent and up to 4
  inspirations drawn uniformly among the working solutions, `change` always `"free"`. One `random.Random`
  per run, from `--seed` or a seed drawn at random (D44); the random strategy gets its own, derived from it.
- **Not yet.** Strategies in their own process (3.1) and in Docker (3.2); the designed view (3.3); the
  weighted built-in (3.5).
- **Check.** Failed solutions never drawn; the parent never among its inspirations; the same seed, the same
  draws.

### Step 0.6. The solution prompt, basic
- **Builds.** `solution_prompt.py`: `Prompt` (`system`, `user`); the system message once: a one-line role,
  the problem's description, and "reply with the complete program in a fenced code block". `build(selection,
  direction)`: the direction, if any; each inspiration's score and code; the parent's score and code;
  "Write the new program."
- **Not yet.** Appendix A's text and budget (2.9); operator texts (2.8); results (1.6); descriptions (2.2).
- **Check.** The exact text for a fixed selection, with and without a direction.

### Step 0.7. The LLM, basic
- **Builds.** `llm.py`: `LLMError`; an abstract `LLM` with `complete(prompt)`, which returns the reply's
  text; `OpenAICompatibleLLM(model, api_base)` with the synchronous `openai` client (a 600 s timeout, the
  package's own retries, an empty reply as an `LLMError`). `replies.py`: `extract_code(reply)`, the first
  fenced code block, or the whole reply if there is none. `tests/fakes.py`: `FakeLLM`, which returns replies
  written in advance.
- **Not yet.** Settings, keys and roles (2.10); token counts (1.7); my-evolve's parser (2.2); diffs (2.3).
- **From.** my-evolve's `llm.py`, cut down.
- **Check.** `extract_code` on replies with one block, several, and none; by hand, one question to the cheap
  model.

### Step 0.8. The solution loop and the command line
- **Builds.** `loop.py`: `run(...)` evaluates the initial program and stops if it has no score; stores it;
  then runs the loop's lines once per iteration, with the random strategy as the only active one, printing
  one line each (iteration, the child's score or error, the best score). An `LLMError` skips the iteration.
  The run folder given by `--output` gets `programs.jsonl`, one line per solution, appended as it is stored
  (D41), and `best_program` with the solutions' extension, rewritten when the best changes.
  `scripts/run.py INITIAL_PROGRAM EVALUATION_FOLDER --config PROBLEM_FILE --iterations N --output FOLDER
  --seed S`.
- **Not yet.** Strategy evolution (0.9, 0.10); threads (5.3); Ctrl+C beyond Python's own (5.5); continuing
  a run (5.6).
- **From.** my-evolve's `loop.py` and `scripts/run.py`, cut down.
- **Check.** `tests/test_loop.py`: the toy problem, with a `FakeLLM` replying a better program, a program
  that raises, and a reply without code; the solutions stored, the best one, `programs.jsonl`. This
  end-to-end test stays, and grows with every phase.

### Step 0.9. The judge, basic
- **Builds.** `judge.py`: for each child, $g_i = s_i - b_i$ (D23), with failed children at $-\infty$; for
  the active strategy, its children, its records, a basic score (the sum of its records, or its best
  $g_i$), and a stagnation test: its last $W$ children set no record above $\tau$ (D25). `W` and `tau` in
  the problem file, $\tau$ absolute for now. The console line shows the strategy and its score.
- **Not yet.** The designed score, with its weight and $\sqrt{n}$ (4.1); a relative $\tau$ and the minimum
  trial (4.2); starvation (6.2).
- **Check.** $g_i$ against hand-computed records; stagnation fires after $W$ children without a record, not
  before.

### Step 0.10. Writing and deploying a strategy, basic
- **Builds.** `strategy_writer.py`: when the active strategy stagnates, the strategy model (the same cheap
  model for now) gets a short prompt: the problem's description, the best scores so far, the current
  strategy's code, the interface of `EvolvedSearchStrategy`, and the request for an `<ANALYSIS>`, a
  `<DIRECTION>` and the class (Appendix B's reply format). The reply is parsed; the code is loaded with
  `exec` in the run's process and checked: it compiles, defines `EvolvedSearchStrategy`, and its `select`
  returns a valid selection once. A strategy that passes is deployed: its `observe` replays every stored
  solution in order (D16), the direction goes into the solution prompt, and it becomes the active strategy;
  one that fails is dropped and the old strategy keeps running. `strategies.jsonl` gets one line per
  generated strategy (D41): id, code, analysis, direction, status (rejected, active, retired), score. The
  run waits while the strategy is written (D22, $K = 1$). `tests/fakes.py` gains a fake strategy model.
- **Not yet.** The strategy in its own process (3.1) and in Docker (3.2); the checks as designed (3.6);
  repair (3.7); the archive, champions, parent and inspiration strategies (4.3, 4.4); statistics (4.5);
  Appendix B's text (4.6). The change size a strategy chooses is recorded, but adds no text to the solution
  prompt until the operator texts exist (1.8).
- **Check.** The end-to-end test grows: the random strategy stagnates; the fake strategy model writes a
  greedy strategy with a direction; the direction appears in the next solution prompts; a broken strategy
  is dropped and the old one keeps running.

### Milestone 0. The first real run
30 iterations of circle packing with the cheap model, $W = 5$. Look at the replies, the scores, the strategy
the strategy model writes and its direction, and the time an iteration takes. This run is the baseline for
what follows.

**What it showed.** With `qwen2.5-coder:3b`, 6 of 10 children failed and neither of its two strategies
passed its checks; Ollama also cut prompts silently to its 4096-token context. With `claude-haiku-5-5`, all 30
children worked and the strategy level ran as designed: the random strategy raised the best from 0.96 to
2.35 in 12 iterations, then three generated strategies raised it to 2.37. It led to these changes:
- in the design: no strategy written when it could not get its trial (D25); the initial strategy kept out
  of the parent draw, J being unfair to strategies deployed later (D24, D27); directions that never say how
  far to move, analyses that claim only what the numbers support and say how the direction differs from
  the revised one (D13, D31); Haiku as the milestones' model (D5); two more facts in the view (D15);
- in the plan: LLM calls saved, the generic operator texts, and the random strategy written as strategy
  code, all in Phase 1 (steps 1.7 to 1.9), since every milestone needs them.

---

## Phase 1: solutions evaluated as designed

By the end of this phase every child is evaluated in its problem's container (D3, D10), has a status (D33),
and gets exactly the paper's score for both math problems. Steps 1.7 to 1.9 come from Milestone 0: every
later milestone needs the calls' cost and replies, change sizes that reach the prompt, and an example
strategy the strategy model can copy safely.

### Step 1.1. Statuses
- **Builds.** `Status` with `ok`, `failed`, `invalid`, `timeout` and `error` (`rejected` comes in 2.4);
  `Result.status`, with a score for `ok` only. The mapping of D8: `invalid` when `validity` is 0; `failed`
  when the evaluator reports an error of the program; `error` when the evaluator itself breaks; `ok`
  otherwise. The status is saved and shown on the console line; $g_i$ is $-\infty$ for anything but `ok`.
- **Check.** A test per status, with small toy evaluators; only `ok` solutions are ever drawn.

### Step 1.2. Evaluators in containers
- **Builds.** `containers.py`: the problem's image built from its `evaluator/` folder on first use, tagged
  with a hash of the folder; one long-lived container per run, started from it; each child copied in and
  evaluated by `evaluate.sh`, as skydiscover does. A time limit per evaluation (the problem file's
  `evaluation.timeout`): over it, the evaluation is stopped and the child gets `timeout`. Docker missing, or
  an image that does not build, is an `error` and a clear message. Docker becomes the default;
  `--unsafe-local-evaluation` keeps step 0.4's subprocess, for the tests, with a warning.
- **From.** skydiscover's `ContainerizedEvaluator`; my-evolve's Docker checks and tests.
- **Check** (skipped without Docker). Circle packing scores as before; a program that never ends gets
  `timeout`, and the container is usable afterwards; a missing Docker gives a clear message.

### Step 1.3. Containers never outlive a run
- **Builds.** Every container is labelled with the run's id; the run removes its containers when it stops,
  and those of an earlier session at start-up.
- **From.** my-evolve's `remove_leftovers` (ME-D42).
- **Check** (skipped without Docker). No container left after a run, a timeout or an exception.

### Step 1.4. Circle packing, scored exactly as in the paper's runs
- **Builds.** The open check of D3: a parity test scoring a fixed set of programs (the initial program, a few
  children of Milestone 0, an invalid packing) with skydiscover's two circle-packing evaluators, recorded
  once by a script run against the skydiscover checkout, and with my-evox's container. If skydiscover's two
  evaluators disagree, the difference is written into D3 and the problem keeps the one the paper's scripts
  use.
- **Check.** The parity test.

### Step 1.5. MinMaxMinDist
- **Builds.** `problems/min_max_min_dist_3/`: skydiscover's `benchmarks/math/minimizing_max_min_dist/3/`,
  its description and its container evaluator, with a parity test like 1.4's.
- **Check.** Its parity test; the initial program's score.

### Step 1.6. Results in the prompt
- **Builds.** The parent's and each inspiration's metrics and artifacts in the solution prompt, each cut to
  `prompt.max_result_chars` (2,000, D38); the parent's line gives the run's best score.
- **Check.** Results reach the prompt, cut; an empty field is left out with its label.

### Step 1.7. Every LLM call saved, with its role
Moved here from Phase 2 (it was step 2.1): Milestone 0 had no record of what a call cost or how long it
took, and its replies could be read only through a script outside the repository.
- **Builds.** `complete` returns an `LLMReply` (`text`, `model`, `input_tokens`, `output_tokens`,
  `duration`). `llm_calls.jsonl` (D41): the role (solution or strategy), the iteration or the strategy, the
  model, the user message, the reply, the tokens, the duration, the cost (prices per model in the problem
  file, D6), and the error of a failed call. A first `run.json`: the run's id, its seed, the system messages.
- **Check.** One line per call of either role, failed calls included; tokens summed per role.

### Step 1.8. The generic operator texts
In Milestone 0 strategies chose `refine` and `diverge`, but the solution prompt did not change with them.
- **Builds.** The change size reaches the solution prompt, in Appendix A's "Change to make" block:
  skydiscover's generic templates for `refine` and `diverge`, without examples (D14's `generic` texts), and
  "Any change that improves the score." for `free`. The strategy prompt shows the three texts and says that
  the direction never says how far to move from the parent (D13).
- **Not yet.** The examples written by the strategy model (2.8); the rest of Appendix A (2.9).
- **From.** skydiscover's `template.py`.
- **Check.** The right text for each change; the strategy prompt shows all three.

### Step 1.9. The random strategy written as strategy code
In Milestone 0 both rejected strategies failed on lines copied from the random strategy's code, which the
prompt showed as a framework class (`RandomStrategy`, without its imports).
- **Builds.** The random built-in (D17) becomes source code written exactly as the strategy model must
  write its own: a class named `EvolvedSearchStrategy`, its imports included, kept in the package as a
  text file. It is loaded and checked like a generated strategy, is the stand-in for a failing strategy
  (D36), and is the initial strategy's code shown in the strategy prompt. The framework's `RandomStrategy`
  class is removed. Its generator is still derived from the run's seed (D44).
- **Check.** Step 0.5's checks of the random strategy, run on the loaded code; the code the strategy prompt
  shows passes `load_strategy` and the replay check as it stands.

### Milestone 1. The first run in containers
Milestone 0's run again, now in containers, on both math problems. Look at the counts by status and at the
time an iteration takes, split between the LLM and the evaluation; at each call's cost (step 1.7); and at
how often strategies choose each change size, now that it reaches the prompt (1.8).

**What it showed.** With `claude-haiku-5-5`, 30 iterations of each problem: all 60 children `ok`, no failed
call, all 7 generated strategies deployed, $0.25 in all (about $0.005 a solution call on circle packing,
$0.003 on MinMaxMinDist, $0.002 a strategy call; replies cost more than prompts). An iteration took about
55 s on circle packing and 39 s on MinMaxMinDist, half in the LLM and half in the evaluation, whose share
grew as programs optimised longer (up to 106 s; the two runs shared the machine). Circle packing reached
0.99801 (a sum of 2.6298); MinMaxMinDist reached 1.000016, the best known value, at iteration 2, so it
cannot tell strategies apart and serves as a quick check. Generated strategies chose `free` 22 times,
`refine` 11 and `diverge` 13; one `diverge` child made the largest gain after the first iteration, no
`refine` child set a real record. It led to these changes:
- the strategy prompt shows the best solution's results (D31): with scores alone, the strategy model read
  circle packing's 0.998 as a sum of radii far below 2.635;
- both problem files set $\tau$ to $10^{-6}$: with $\tau = 0$, rounding noise (gains of $10^{-16}$ to
  $10^{-9}$ between equal solutions) counted as records four times and kept one strategy five more
  iterations. Step 4.2's relative $\tau$ with its floor replaces this.

---

## Phase 2: the solution prompt and the LLMs

By the end of this phase replies are parsed as designed (diffs, descriptions), children are checked
before they cost an evaluation and retried when they fail, and the solution prompt is Appendix A's. Step
2.1, saving every LLM call, moved to Phase 1 after Milestone 0 (step 1.7); the other steps keep their
numbers.

### Step 2.2. my-evolve's reply parser, and descriptions
- **Builds.** my-evolve's `parse_reply` (ME-D68): thinking sections removed, the code block chosen as it
  does; the `<DESCRIPTION>` asked for in the reply format and kept with the solution; descriptions shown for
  the parent and each inspiration (D38).
- **From.** my-evolve's `reply_parser.py` and its tests, with the Python-only choices made per language.
- **Check.** my-evolve's parser tests; a reply without a description keeps its code.

### Step 2.3. Diffs
- **Builds.** `diffs.py`: SEARCH/REPLACE blocks extracted from the reply and applied to the parent (D37); a
  block whose SEARCH text is not found makes the child unusable, with that reason. `edit_format` in the
  problem file (`diff` for the experiments' problems, or `rewrite`), and the matching reply format.
- **From.** skydiscover's `extract_diffs` and `apply_diff` (`optimize/utils/code_utils.py`).
- **Check.** Blocks applied in order; a SEARCH text not found; several blocks; a reply with no block.

### Step 2.4. Evolve blocks enforced; status `rejected`
- **Builds.** `checks.py`: the evolve blocks split by their markers, with the comment syntax of the
  solutions' language (`#` for Python for now, D2); the child's code outside the blocks replaced by the
  initial program's, and broken markers rejected (D33, ME-D12). The new status `rejected`: stored with its
  reason, never evaluated. The rule in the system message.
- **From.** my-evolve's `split_evolve_blocks` and `with_fixed_code` (ME-D74).
- **Check.** Each way of breaking the markers; code outside the blocks put back; a rejected child in the
  end-to-end test.

### Step 2.5. Compiling and entry functions
- **Builds.** The rest of D33's checks, for Python: the code parses; every function named by the problem
  file's `entry_functions` is defined at the top level. Each check is chosen by the solutions' language, so
  C++ can add its own (7.2).
- **Check.** Each rejection with its reason, in order; the initial program passes its own checks.

### Step 2.6. Duplicates
- **Builds.** `fingerprint(code, language)`: the SHA-256 of the code after a normalization chosen per
  language (for Python, its syntax tree, as my-evolve; D40). A child whose fingerprint is known is rejected,
  "same program as" the solution that has it.
- **From.** my-evolve's `fingerprint` (ME-D13, ME-D74).
- **Check.** Comments and spacing leave a Python fingerprint unchanged; a child identical to its parent costs
  no evaluation.

### Step 2.7. Retries for solutions
- **Builds.** D35: a selection gets up to `attempts_per_selection` (3) attempts; a `rejected`, `failed`,
  `timeout` or `invalid` child is followed by another call with the same selection and a "Failed attempts"
  block (Appendix A: each attempt's status, error and code, cut to a size limit); an `error` child is not
  retried. Each attempt is an iteration (D6), stored, observed and judged like any child.
- **Check.** Retries stop at the first working child or at the third attempt; the failed-attempts block's
  text; the budget counts every attempt; no retry after `error`.

### Step 2.8. The operator texts' examples
- **Builds.** `operators.py`: at the start of a run, one call of the strategy model with skydiscover's
  generation prompt (the problem description, the evaluator's source, the packages of the benchmark's
  `requirements.txt`); the two example lists put into skydiscover's `DIVERGE_TEMPLATE` and
  `REFINE_TEMPLATE`, verbatim (D14); saved in the run folder. `operator_texts: generated | generic` in the
  problem file, `generic` keeping step 1.8's texts. The random strategy still uses `free`.
- **From.** skydiscover's `variation_operator_generator.py` (the prompt, the parsing) and `template.py`.
- **Check.** With a fake strategy model, the two texts built from its reply; the generic texts; the right text
  for each change.

### Step 2.9. The solution prompt of Appendix A
- **Builds.** Both messages exactly as in Appendix A: the guidance section with its precedence (D13), the
  rules, the reply format of the problem's edit format, the direction block, the inspirations, the parent,
  the failed attempts, the change to make. `prompt.max_chars` (60,000, D38): over it, inspirations shown by
  score and description only, the last ones first. A direction without a strategy (the initial strategy)
  leaves its block out.
- **Check.** The exact text of both messages, for each edit format; the budget rule.

### Step 2.10. Model settings, API keys, test requests
- **Builds.** The `llm` section with two roles, `solution` and `strategy` (D5), each a list of models with a
  `name`, a `weight`, an `api_base`, `api_key: ${VARIABLE}` (a key written in the file is refused), and the
  settings `max_tokens` (32,000), `timeout` (600 s), `reasoning_effort`; reasoning models handled as in
  my-evolve. Before the first iteration, a test request to every model; any failure stops the run (D39).
  Failures counted per model during the run; 3 in a row of a model with no alternative stop the run.
- **Already there.** For Milestone 0 on a Claude model (through Anthropic's OpenAI-compatible
  endpoint), Phase 0 gave the one model of the `llm` section `api_key: ${VARIABLE}` and `max_tokens`
  (no default: the server's applies when it is absent). This step builds the rest around them.
- **From.** my-evolve's `llm.py` settings, keys and ensemble (ME-D31 to ME-D34), and its fake
  OpenAI-compatible server.
- **Check.** Each setting sent, or not; the key read from its variable; a test request that fails stops the
  run; 3 failures in a row stop it.

### Milestone 2. The first run with designed solution prompts
Both math problems, 30 iterations, the cheap model in both roles. Look in `llm_calls.jsonl`: are diffs
applied, descriptions kept, retries useful; how long are the prompts; what does a run cost per iteration.

---

## Phase 3: strategies as designed

By the end of this phase every strategy runs in its own Docker worker, sees the designed view, cannot stop
the run when it misbehaves, and is checked and repaired before it is deployed.

### Step 3.1. The strategy worker and its messages
- **Builds.** `strategy_protocol.py`: one JSON message per line. `strategy_worker.py`, run as `python -m
  my_evox.strategy_worker`: it receives `load` (the strategy's code and its generator's seed) and answers
  `loaded` or `load_failed`; `observe` (a child's record) and `select` (answered by a selection, or by
  `raised` with the traceback). The run talks to it through `StrategyHandle`, which stands where the
  in-process strategy stood; each call has a time limit, over which the worker is killed. For now the worker
  is a local subprocess.
- **Not yet.** Docker (3.2); the designed view (3.3); strikes (3.4).
- **From.** my-evolve's `sandbox_protocol.py` and `sandbox_worker.py` (ME-D77).
- **Check.** Tests drive the worker through its pipes: load, observe, select, an exception, a time limit; the
  end-to-end test passes unchanged.

### Step 3.2. Strategies in Docker
- **Builds.** The strategy image (Python's standard library only) and the worker run in a container with no
  network, a read-only file system except `/tmp`, and my-evolve's limits (D10); labelled and removed like the
  evaluator's (1.3). The checks of 0.10 run in the same kind of container. `--unsafe-local-strategies`
  keeps 3.1's subprocess, for the tests.
- **From.** my-evolve's `DockerSandbox` (ME-D40, ME-D41).
- **Check** (skipped without Docker). No network; no host files; a strategy importing numpy fails to load;
  the end-to-end test in Docker.

### Step 3.3. The view, as designed
- **Builds.** D15: every stored solution, failed ones included, as a frozen record (id, code, description,
  status, score, metrics, parent, inspirations, the strategy that chose its parent, its change, its
  iteration) with the computed facts (gain over the parent, $g_i$, rank among working solutions, number of
  children); the run's facts (iteration, budget left, best score, iterations since the last record, active
  strategies); the strategy's own facts (iterations, warm-up, records, and how many more of its children
  without a record would retire it). In Milestone 0 every strategy rebuilt the last two itself, and badly. The worker keeps its copy up to date from the `observe` messages, so
  a `select` sends only what changed. The framework refuses a failed parent whatever the strategy returns.
- **Check.** The computed facts on a made-up population; the worker's copy equal to the run's after many
  observes; a failed parent refused.

### Step 3.4. Strikes, and the random fallback
- **Builds.** D36: a call that raises, runs over its time limit, crashes the worker, or returns an invalid
  selection is a strike; that iteration uses the random strategy instead; a crashed worker is restarted and
  rebuilt by replay; 3 strikes retire the strategy, and, with $K = 1$, the run waits for its replacement.
- **Check.** One test per kind of strike; the third retires the strategy; an LLM or evaluation failure is
  never a strike.

### Step 3.5. The weighted built-in, and the initial strategy as a setting
- **Builds.** `WeightedStrategy`: my-evolve's parent rule (ME-D19), adapted to a flat population, written as
  an `EvolvedSearchStrategy`, as the random one is since step 1.9. `initial_strategy: random | weighted` in
  the problem file (D17).
- **From.** my-evolve's `WeightedSelector`.
- **Check.** Draw frequencies on a made-up population; the setting chooses the initial strategy.

### Step 3.6. Checks before deployment, as designed
- **Builds.** D32, in a strategy container, stopping at the first failure: the reply's three parts, the
  direction within `direction_cap`, the code within `strategy_max_chars` (about 20,000); the class and its
  two methods; a trial on a copy of the population (the history replayed, then `select` called several
  times, each answer valid and in time). A strategy that always picks the same parent in the trial is logged,
  not rejected. A rejected strategy is saved with its error (D41).
- **Check.** One test per failure, with fake strategy-model replies; a strategy too slow in the trial.

### Step 3.7. Repairing a strategy
- **Builds.** D34: a strategy that fails its checks is sent back in the same conversation with Appendix B's
  repair message, up to 3 attempts; when all fail, with $K = 1$, the stagnated strategy keeps running (a
  struck-out one is replaced by the random strategy) until a new attempt after $W$ more iterations. A failed
  call of the strategy model counts as a failed attempt (D39).
- **Check.** A strategy fixed at the second attempt; three failures and the fallback; the conversation's
  messages.

### Milestone 3. The first run with sandboxed strategies
Milestone 2's runs with strategies in Docker. Look at what the strategy model writes, how often its
strategies fail their checks and why, and whether repair fixes them.

---

## Phase 4: judging, the archive and the strategy prompt

By the end of this phase strategies are scored and replaced as designed, the archive keeps them with their
champions, and the strategy model gets Appendix B's prompt. This completes the method with $K = 1$.

### Step 4.1. The strategy score, as designed
- **Builds.** D24: $J_s$ with the weight $w(b_{\text{start}})$ and the division by $\sqrt{n_s}$; the sum of
  records, or the closest approach. `score_clipping: false` in the problem file; `true` clips the second
  case to 0, giving skydiscover's score (ablation 3, D4).
- **Check.** $J_s$ against hand-computed values; with $K = 1$, equal to skydiscover's formula on the same
  children when clipped (§8.2).

### Step 4.2. Stagnation, as designed
- **Builds.** D25: $\tau$ relative to the best score, `tau_relative` (1%) with `tau_floor`; $W$ by default 10%
  of the iterations; the minimum trial of $W$ children of its own; no strategy written when fewer than
  $n_{\min}$ iterations remain, the stagnated one running to the end (Phase 0 skips only the last
  iteration).
- **Not yet.** Starvation (6.2): with $K = 1$ it never fires before stagnation.
- **Check.** The relative threshold on scores near 1, large, negative and near 0; no judgement before $W$
  children; no strategy written in the last $n_{\min}$ iterations.

### Step 4.3. Archive entries and champions
- **Builds.** `archive.py`: D26's entries: code, analysis, direction, $J_s$, its champion (id, score, whether
  it set a new best), the population statistics at the start and end of the deployment as numbers (with
  D30's vector), a short history of its score; entered when deployed, marked retired with its reason.
  `strategies.jsonl` gets every field of D41 (a line appended when a strategy's status or score changes; the
  last line wins when read back); `strategies/strategy_NNNN.py`, a readable copy.
- **Check.** A champion below the run's best; the reasons; the last line wins.

### Step 4.4. The parent strategy and the inspiration strategies
- **Builds.** D27: the strategy to revise drawn with $p_j \propto e^{-\text{rank}_j / T}$ (`rank_temperature`,
  1); D28: the strategy that just ended, if it is not the parent, and draws by the same weights, up to 2.
  The initial strategy is never drawn once a generated strategy exists (D27).
- **Check.** Draw frequencies; the strategy that just ended always shown; fewer when the archive is small;
  the initial strategy drawn only for the first replacement.

### Step 4.5. Population statistics
- **Builds.** `statistics.py`: D30's statistics over the run's last $K \cdot W$ iterations, formatted as text
  by the framework: skydiscover's set (size, score summary and tiers, distinct scores, children per parent,
  the 20 best, the execution trace naming each child's strategy, the trajectory, iterations without
  improvement, most reused parent and inspiration) plus outcomes per change size and failures by status;
  the per-strategy versions; the summary of a strategy's deployment.
- **From.** skydiscover's `get_statistics` (`search/base_database.py`) and `format_population_state`
  (`context_builder/evox/formatters.py`), without their dead or broken parts (§13.1, §13.11).
- **Check.** Each number on a made-up population; the window of $K \cdot W$ iterations.

### Step 4.6. The strategy prompt of Appendix B
- **Builds.** Both messages exactly as in Appendix B: how the search works, $J_s$ in words, what to write,
  the change-size texts, the constraints (the view's fields, the limits), the reply format, the analysis
  claiming only what the numbers support and ending with how the direction differs; the problem; the run
  so far; the
  statistics; the 5 best solutions by score and description; the strategy to revise, with its champion's
  code; the other past strategies; the task. With $K = 1$ the active-strategies block is left out.
- **Check.** The exact text for a made-up run.

### Milestone 4. The first run of the whole method, K = 1
Both math problems, 50 iterations, the cheap model. Look at the strategies' directions, their scores, the
champions, and whether directions show in the children.

---

## Phase 5: the run

By the end of this phase runs use several workers, survive a crash or Ctrl+C and can be continued, stop on a
target score or when they stall, leave a report, and offer the ablations as settings.

### Step 5.1. Logging and the summary
- **Builds.** my-evolve's logging (ME-D52, ME-D78): the console shows one line per iteration, `--verbose`
  adds details, `log.txt` gets everything. The end-of-run summary: iterations, why the run stopped, the best
  score, counts by status, strategies deployed and how they ended, tokens and cost per role and per model
  (D6).
- **From.** my-evolve's `logs.py`.
- **Check.** `log.txt` gets the details the console leaves out; no API key in any output.

### Step 5.2. The complete run folder
- **Builds.** D41's run folder: `history.csv` with the strategy and the change size; the `best/` snapshots;
  `best_program` with its header; the problem file's copy; `run.json` with one record per session; the
  default `--output`.
- **From.** my-evolve's `storage.py`.
- **Check.** my-evolve's storage tests, adapted; every file of D41 after a run.

### Step 5.3. Several iterations at once
- **Builds.** D9: `--workers` threads, my-evolve's split between the main thread and the workers (D8): the
  main thread schedules, selects, builds prompts, runs the checks, stores and judges; workers call the LLM
  and evaluate. A child is credited to the strategy that chose its parent even if it finishes after that
  strategy was retired; with $K = 1$, no new selection starts while the run waits for a strategy.
- **From.** my-evolve's `WorkerPool` (ME-D70).
- **Check.** Several iterations in flight; one worker and one seed repeat the same draws; a child finishing
  after a switch credited to its strategy.

### Step 5.4. Errors inside an iteration
- **Builds.** my-evolve's rule (ME-D38): an exception that is not the program's fault gives the child
  `error`; 3 in a row stop the run; a failed solution call ends its iteration (D39).
- **Check.** As in my-evolve.

### Step 5.5. Ctrl+C and SIGTERM
- **Builds.** my-evolve's (ME-D53, ME-D54): the first Ctrl+C lets the iterations in flight finish; a second,
  or SIGTERM, stops at once; every container, evaluator and strategy worker, is removed.
- **From.** my-evolve's loop and its tests.
- **Check.** No container left after either.

### Step 5.6. Continuing a run
- **Builds.** D42: the same command and `--output` continue the run: the store from `programs.jsonl`, the
  archive from `strategies.jsonl`, every active strategy rebuilt by replay (D16), the operator texts
  reused, the judge's state rebuilt from the stored children; completed iterations from `history.csv`; the
  generators reseeded so that draws continue (D44).
- **Check.** An interrupted run finished by the same command, with the same active strategy and the same
  stagnation state; a larger `--iterations` extends it.

### Step 5.7. Refusing to continue a changed problem
- **Builds.** my-evolve's fingerprints in `run.json` (the initial program, the evaluator folder, the problem
  file without its `llm` section, the images); a change stops the run, saying which (ME-D50).
- **Check.** A changed evaluator stops the run; a changed `llm` section does not.

### Step 5.8. Target score and patience
- **Builds.** `--target-score` and `--patience` (section 13), off unless given.
- **Check.** As in my-evolve, after a resume too.

### Step 5.9. The report
- **Builds.** `scripts/report.py RUN_FOLDER` (D43): my-evolve's progress plot, with each strategy's
  deployment marked and labelled with its gain and score; a table of strategies (direction, use of each
  change size, records, iterations, how it ended), as Markdown.
- **From.** my-evolve's `report.py`.
- **Check.** The report runs on a run folder written by the end-to-end test.

### Step 5.10. The ablations' settings
- **Builds.** D4's ablations as settings of the problem file: `directions: evolved | static | none`. `none`:
  the strategy prompt asks for no direction, the solution prompt has no direction block and no mention of
  one (Appendices A and B). `static`: one direction written by the strategy model at the start, from the
  problem alone, shown in every solution prompt; strategies write none. `score_clipping` (4.1) is the third.
- **Check.** Each setting's prompts, exactly.

### Milestone 5. The whole design, K = 1
Runs of both math problems with several workers, one interrupted and continued, with their reports; one
short run of each ablation.

---

## Phase 6: several active strategies

By the end of this phase up to $K$ strategies share the pool, scheduled as designed, judged and replaced
each on its own, with their replacements written in the background.

### Step 6.1. K slots, and round-robin with warm-up
- **Builds.** `active_strategies` ($K$) in the problem file; one worker container per active strategy; the
  scheduler of D20: strategies in warm-up ($n_{\min}$ iterations, default $W$) served first, taking turns,
  then round-robin. Every active strategy observes every child; each is judged on its own children.
- **Check.** Turns in order; warm-up first; each strategy's children and score kept apart.

### Step 6.2. Starvation
- **Builds.** D25's second condition: no record by the strategy in the run's last $K \cdot W$ iterations.
- **Check.** A strategy that gets few iterations retired; with $K = 1$, stagnation always fires first.

### Step 6.3. Writing strategies in the background
- **Builds.** D22: a thread of its own writes strategies; a stagnated strategy is retired at once and its
  slot stays empty while the others run; the replacement joins when its checks pass; with $K = 1$ the run
  still waits. When all repair attempts fail, with $K > 1$, the slot stays empty and is retried after $W$
  more iterations (D34).
- **Check.** Iterations continue while a strategy is written (with a fake strategy model that waits); the
  replacement joins at its warm-up; a retry after failed attempts.

### Step 6.4. The sequential start
- **Builds.** D21: the initial strategy runs alone for its warm-up; then the other slots are filled one
  strategy at a time, in the background, never several in one batch; the initial strategy stays one of the
  $K$.
- **Check.** One strategy written at a time; the initial strategy judged like the others.

### Step 6.5. The active strategies in the strategy prompt
- **Builds.** Appendix B's "Active strategies" block (each one's direction, score so far, share of
  iterations) with the instruction to complement them.
- **Check.** The block's exact text; left out when $K = 1$.

### Step 6.6. The bandit
- **Builds.** D20's bandit: rewards $r_i$, each child's rank among the working solutions (0 for a failed
  child); recent rewards weigh more. `scheduler: round_robin | bandit`. The algorithm is chosen when the step
  starts (see P3).
- **Check.** On made-up rewards, more iterations go to the better strategy; old rewards fade; warm-up still
  comes first.

### Milestone 6. The first run with K = 2
Circle packing, 50 iterations, $K = 2$, round-robin then bandit. Look at how the two directions differ and
how the iterations are shared.

---

## Phase 7: ALE-Bench-Lite

By the end of this phase my-evox evolves C++ programs on ALE-Bench-Lite, scored by `ale_bench` as in the
paper.

### Step 7.1. `ale_bench` on this machine
- **Builds.** Install `ale_bench` and `ale_bench_eval` as skydiscover's README says, and find how they run
  here: in which containers they judge programs, whether they need Docker inside a container, and whether
  Windows works or a Linux machine (or WSL 2) is needed. The answers go into D3 and the problem files.
- **Check.** skydiscover's evaluator scores ALE-Agent's solution of one problem on its 50 public cases.

### Step 7.2. C++ solutions
- **Builds.** C++ in every place D2 lists: evolve-block markers in `//` comments; the parse check of D33 by
  compiling, in the evaluator's image; the fingerprint's normalization for C++ (D40); the language-specific
  rules of the solution prompt (the compiler and the time limit, Appendix A).
- **Check.** Each check on C++ programs; a fingerprint unchanged by comments and spacing.

### Step 7.3. One ALE problem end to end, and its private evaluation
- **Builds.** `problems/ale/ahc025/` (or another short-running problem): skydiscover's files, with ALE-Agent's
  solution as the initial program; a short run; `scripts/private_eval.py`, which scores a run's best program
  on the private cases, as skydiscover's `private_eval.py` does, for the paper's "average private
  performance" (D4).
- **From.** skydiscover's `benchmarks/ale_bench/`.
- **Check.** A run of a few iterations; the private evaluation of its best program.

### Step 7.4. The other nine problems
- **Builds.** The remaining problems of ALE-Bench-Lite's list (ahc008, ahc011, ahc015, ahc016, ahc024, ahc026,
  ahc027, ahc039, ahc046), each with its files and problem file.
- **Check.** Each initial program scores on its public cases.

### Milestone 7. The first ALE-Bench-Lite run
One problem, 30 iterations, the cheap model. Look at compile failures, retries, the evaluation's time, and
the prompt sizes with C++ programs.

---

## Phase 8: the experiments

These spend GPT-5 (D5). Every run is 100 iterations (D4), with target score and patience off.

### Step 8.1. Cost pilot
10 iterations of circle packing and of one ALE problem with GPT-5 in both roles: the cost per iteration for
each role (from `llm_calls.jsonl`) gives the cost of the whole programme before it starts.

### Step 8.2. The math problems
Circle packing and MinMaxMinDist: 3 runs each, the full method with $K = 1$; mean and best final score
against the paper's Table 2 (D4); cost per run.

### Step 8.3. ALE-Bench-Lite
The 10 problems, 3 runs each; each run's best program scored on the private cases; the average private
performance against the paper's 1958.2 (Figure 3a); cost per run.

### Step 8.4. The ablations
On the same problems as far as the budget allows (D4): no direction and the static direction first; then
skydiscover's score; then $K = 2$ against $K = 1$, and round-robin against the bandit.

---

## Points the design leaves open

Each with a proposed answer and the step where it is settled.

**P1. The direction cap** (step 3.6). D13 leaves its value open. Proposed: 1,500 characters, about one
paragraph, so that the direction stays a direction and not a second program description.

**P2. The time limits of a strategy's calls** (step 3.1). D10 leaves them open. Proposed: 5 s per `select`,
1 s per `observe`, and 60 s for a whole replay; the trial of D32 uses the same limits.

**P3. The bandit's algorithm** (step 6.6). D20 leaves it open. Proposed: discounted UCB (each past reward
multiplied by a factor, for example 0.9, at every new iteration of the run), simple and deterministic, so
runs repeat with one worker.

**P4. $\tau$'s absolute floor** (step 4.2). D25 says "small". Proposed: $10^{-6}$, so that it matters only
when the best score is within $10^{-4}$ of 0.

**P5. The trial's size** (step 3.6). D32 says "several" `select` calls. Proposed: 5.

**P6. The solution containers' limits** (step 1.2). D10 puts solutions in their evaluator's container,
built from skydiscover's `Dockerfile`, but does not say with which limits. Proposed: no network and
my-evolve's memory and CPU limits, unless an evaluator needs otherwise (ALE's may, step 7.1).
*Settled at step 1.2:* no network; a read-only file system except a 512 MB `/tmp`; 2 GB of memory
without swap; 256 processes; no capabilities, no new privileges, the `nobody` user; and no CPU limit,
since skydiscover sets none and a program that searches for a fixed time then runs as on the paper's host.
A program over the memory limit is killed (status `failed`), after about 20 s of memory pressure with
Docker Desktop.

**P7. Identical children in flight** (step 5.3). As in my-evolve's plan: with several workers, the duplicate
check sees only stored solutions. Proposed: the main thread also holds the fingerprints of the children
being evaluated.

**P8. A strategy retired during a selection's retries** (steps 2.7, 6.3). With $K > 1$, a strategy may be
retired while one of its selections still has attempts left. Proposed: the remaining attempts go ahead and
are credited to it, as any child in flight is (D9).

---

## Where each decision is built

| Decisions | Steps |
|---|---|
| D1 (built from scratch) | every step's **From** |
| D2 (any language) | 2.4, 2.5, 2.6, 7.2 |
| D3 (problems and evaluators) | 0.2, 0.4, 1.2, 1.4, 1.5, 7.1 to 7.4 |
| D4 (comparability, ablations) | 4.1, 5.10, Phase 8 |
| D5 (models) | 0.7, 2.10, and every milestone |
| D6 (budget and cost) | 1.7, 2.7, 5.1 |
| D7 (one machinery) | 0.10, 3.1, and how both levels share the LLM, parsing, checks and storage |
| D8 (the solution loop) | 0.8, 1.1, 5.3 |
| D9 (iterations in parallel) | 5.3 |
| D10 (LLM-written code in Docker) | 1.2, 1.3, 3.1, 3.2 |
| D11 (what a strategy is) | 0.5, 3.1 |
| D12 (what a strategy decides) | 0.5, 3.3, 3.6 |
| D13 (direction and change size) | 0.6, 0.10, 1.8, 2.8, 2.9, 4.6 |
| D14 (operator texts) | 1.8, 2.8 |
| D15 (the view) | 0.5, 3.3 |
| D16 (a strategy's state, replay) | 0.10, 3.1, 5.6 |
| D17 (built-in strategies) | 0.5, 1.9, 3.4, 3.5 |
| D18 (a flat population) | 0.5 |
| D19 (the portfolio) | 6.1 |
| D20 (scheduling) | 6.1, 6.6 |
| D21 (sequential start) | 6.4 |
| D22 (writing in the background) | 0.10 (the run waits), 4.2, 6.3 |
| D23 (records) | 0.9 |
| D24 (the strategy score) | 0.9, 4.1 |
| D25 (stagnation and starvation) | 0.9, 4.2, 6.2 |
| D26 (archive entries) | 0.10, 4.3 |
| D27, D28 (parent and inspiration strategies) | 4.4 |
| D29 (one candidate per replacement) | 0.10 |
| D30 (population statistics) | 4.3, 4.5 |
| D31 (the strategy prompt) | 0.10, 1.8, 1.9, 4.6, 6.5 |
| D32 (checks before deployment) | 0.10, 3.6 |
| D33 (checks before evaluation, statuses) | 1.1, 2.4, 2.5, 2.6, 7.2 |
| D34 (repairing a strategy) | 3.7, 6.3 |
| D35 (retries for solutions) | 2.7 |
| D36 (strikes) | 3.4 |
| D37 (edit format) | 0.7, 2.3 |
| D38 (the solution prompt) | 0.6, 1.6, 2.2, 2.9 |
| D39 (LLM failures) | 0.8, 2.10, 3.7, 5.4 |
| D40 (identifiers and memory) | 0.3, 0.5, 2.6 |
| D41 (the run folder) | 0.8, 0.10, 1.7, 4.3, 5.2 |
| D42 (continuing a run) | 5.6 |
| D43 (the report) | 5.9 |
| D44 (randomness) | 0.5, 5.6 |
| D45 (problem file and command line) | 0.3, 0.8, then every step that adds a setting; 5.7 |
| D46 (the project) | 0.1, and every step |
| Section 13 (smaller features) | 5.1, 5.5, 5.8 |
| Appendix A | 0.6, 2.9 |
| Appendix B | 0.10, 1.8, 1.9, 4.6, 6.5 |
| Appendix C | the loop of 0.8 and 0.10, completed by 2.7, 6.1 to 6.4 |
