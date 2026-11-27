# Circle packing

Pack 26 non-overlapping circles in the unit square, maximizing the sum of their radii (AlphaEvolve's
problem B.12). The score is the sum of the radii divided by 2.635, AlphaEvolve's result, as the paper's
evaluator gives it; the sum itself is the metric `sum_radii`, which the paper's tables report.

Everything here comes from skydiscover's `benchmarks/math/circle_packing/` at commit `0d932b6`
(Apache-2.0, see `LICENSE`), so that scores are the paper's (D3):

| File | From skydiscover |
|---|---|
| `initial_program.py` | `initial_program.py`, unchanged |
| `evaluator/evaluator.py` | the top-level `evaluator.py`, unchanged: the evaluator skydiscover's reproduce scripts give the paper's runs |
| `evaluator/wrapper.py` | `skydiscover/optimize/evaluation/wrapper.py`, unchanged: it turns the dictionary `evaluate()` returns into the container protocol's JSON |
| `problem.yaml` | its `description` is `config.yaml`'s `prompt.system_message`, verbatim; its time limit is `config.yaml`'s `evaluator.timeout`; the rest is my-evox's |

my-evox's own files:

| File | Contents |
|---|---|
| `evaluator/evaluate.sh` | runs `evaluate()` through `wrapper.py`, as skydiscover does for its other evaluators of this kind |
| `evaluator/Dockerfile` | the image: Python 3.12 with the packages of skydiscover's `math` extra, which the paper's runs had on their host |
| `evaluator/requirements.txt` | those packages, at the versions skydiscover's first release locked for Python 3.12 (torch, installed apart from its CPU index, is in the `Dockerfile`) |

skydiscover also has a container version of this evaluator (its `evaluator/` folder), which came after
the paper's runs. On deterministic programs the two agree on the sum of the radii and on validity, but
that one scores the sum itself, and reports an error, rather than validity 0, for a program that raises
or returns the wrong shape. `tests/parity/` holds programs scored by both, and checks that my-evox's
container gives the same results as the evaluator kept here.

The image is about 3 GB and takes several minutes to build the first time; my-evox builds it when a run
or a test first needs it.
