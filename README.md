# my-evox

A re-implementation of EvoX: LLM-driven evolution of programs in which the search strategy (how parents,
inspirations and the size of a change are chosen) is itself written and rewritten by an LLM, as the run
goes.

The design is in [docs/design-decisions.md](docs/design-decisions.md), how the authors' code implements
EvoX in [docs/evox-in-code.md](docs/evox-in-code.md), and the order in which my-evox is built in
[docs/implementation-plan.md](docs/implementation-plan.md).

## Layout

| Path | Contents |
|---|---|
| `src/my_evox/` | The package |
| `problems/` | The problems, one folder each, taken from skydiscover's benchmarks |
| `scripts/` | Files you launch directly: `run.py` |
| `tests/` | Automatic checks, and the toy problem they run (`tests/toy/`) |
| `docs/` | The design and the plan |
| `pyproject.toml` | Project description and tool settings |

## Setup

Run once, from the repository root. Python 3.11 or later is needed.

Linux and macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

## Running a problem

For now, every program runs as a plain process on this machine, with your files and your network, and
without a time limit: containers arrive in step 1.2 of the plan. Keep runs short, and watch them.

A run needs the problem file's model reachable: for now it writes both the solutions and, whenever
the active strategy stagnates, its replacement. Circle packing's problem file names `claude-haiku-5-5`,
reached through Anthropic's OpenAI-compatible endpoint. The key is named by its environment variable,
never written in the file:

```yaml
llm:
  model: claude-haiku-5-5
  api_base: https://api.anthropic.com/v1/
  api_key: ${ANTHROPIC_API_KEY}   # the variable holding the key
  max_tokens: 16000               # the longest reply, in tokens; the server's default if absent
```

so the variable must be set before a run (in PowerShell: `$env:ANTHROPIC_API_KEY = "sk-ant-..."`).

A local [Ollama](https://ollama.com) server works too: name its model and `http://localhost:11434/v1`,
without `api_key`. Ollama silently cuts prompts longer than its context length, 4096 tokens unless set
otherwise, and a circle-packing prompt with four other solutions takes 6,000 tokens or more: start it with
`OLLAMA_CONTEXT_LENGTH=16384` or more. Small local models are not enough: in Milestone 0,
`qwen2.5-coder:3b` never wrote a strategy that passed its checks.

```bash
.venv/bin/python scripts/run.py problems/circle_packing/initial_program.py problems/circle_packing/evaluator --config problems/circle_packing/problem.yaml --iterations 30 --output runs/circle_packing_1
```

| Flag | Meaning | Default |
|---|---|---|
| `--config` | The problem file: the problem's description and its model | required |
| `--iterations` | How many iterations in all | required |
| `--output` | The run folder; it must not already hold a run | `runs/<problem>_<date>_<time>` |
| `--seed` | The seed of the run's random draws | drawn, and printed |

The console shows one line per iteration, and each change of strategy. The run folder holds:

| File | Contents |
|---|---|
| `programs.jsonl` | Every solution, one line of JSON each, written as it is stored |
| `strategies.jsonl` | Every strategy, rejected ones included, with its direction, analysis, code, status and score; written again when its status or score changes, so that its last line is its current state |
| `best_program.py` | The best solution so far |

## Everyday commands

These are written for Linux and macOS. On Windows, replace `.venv/bin/python` with
`.venv\Scripts\python.exe`.

```bash
# Run the tests
.venv/bin/python -m unittest discover tests

# Check the types
.venv/bin/python -m mypy

# Check for common mistakes and style problems
.venv/bin/python -m ruff check

# Check the formatting, or reformat the code automatically
.venv/bin/python -m ruff format --check
.venv/bin/python -m ruff format
```
