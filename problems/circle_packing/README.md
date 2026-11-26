# Circle packing

Pack 26 non-overlapping circles in the unit square, maximizing the sum of their radii (AlphaEvolve's
problem B.12). The score is the sum of the radii; AlphaEvolve reached 2.635.

Everything here comes from skydiscover's `benchmarks/math/circle_packing/` at commit `0d932b6`
(Apache-2.0, see `LICENSE`), so that scores are the paper's (D3):

| File | From skydiscover |
|---|---|
| `initial_program.py` | `initial_program.py`, unchanged |
| `evaluator/` | `evaluator/`, the container version of the evaluator: its `Dockerfile`, `evaluate.sh` and `requirements.txt` unchanged, its `evaluator.py` changed as below |
| `problem.yaml` | its `description` is `config.yaml`'s `prompt.system_message`, verbatim; the rest is my-evox's |

`evaluator/evaluator.py` has two changes, marked "my-evox" in the file, so that it also runs on Windows,
where my-evox's first steps run evaluators outside containers: the time limit uses `SIGALRM` only where
it exists, and the log goes to the system's temporary folder rather than `/tmp`. Scoring is unchanged.

Run by hand, from the repository root, the evaluator scores a program and prints one line of JSON:

```bash
.venv/bin/python problems/circle_packing/evaluator/evaluator.py problems/circle_packing/initial_program.py
```
