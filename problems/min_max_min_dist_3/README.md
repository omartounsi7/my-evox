# MinMaxMinDist

Place 14 points in 3 dimensions so that the ratio of their smallest to their largest pairwise distance
is as large as possible (AlphaEvolve's problem B.8). The evaluator's `min_max_ratio` is that ratio
squared, and the score is `min_max_ratio` over 1/4.165849767, AlphaEvolve's result, so that a score
above 1 beats it. The paper's tables give the inverse, 1/`min_max_ratio`, where lower is better: its
4.16 is a score of 1.0014.

Everything here comes from skydiscover's `benchmarks/math/minimizing_max_min_dist/3/` at commit
`0d932b6` (Apache-2.0, see `LICENSE`), so that scores are the paper's (D3):

| File | From skydiscover |
|---|---|
| `initial_program.py` | `initial_program.py`, unchanged |
| `evaluator/evaluator.py` | `evaluator/evaluator.py`, unchanged: its `evaluate()` is that of skydiscover's first release, the evaluator its reproduce scripts gave the paper's runs, with only the order of its imports changed and a bridge to the container protocol added |
| `evaluator/wrapper.py` | `evaluator/wrapper.py`, unchanged: that bridge, skydiscover's own |
| `evaluator/evaluate.sh` | `evaluator/evaluate.sh`, unchanged |
| `problem.yaml` | its `description` is `config.yaml`'s `prompt.system_message`, verbatim; its time limit is `config.yaml`'s `evaluator.timeout`; the rest is my-evox's |

my-evox's own files:

| File | Contents |
|---|---|
| `evaluator/Dockerfile` | the image: Python 3.12 with the packages of skydiscover's `math` extra, which the paper's runs had on their host (skydiscover's container installs numpy and scipy only) |
| `evaluator/requirements.txt` | those packages, at the versions skydiscover's first release locked for Python 3.12 (torch, installed apart from its CPU index, is in the `Dockerfile`) |

`tests/parity/` holds programs scored by skydiscover's evaluator, run from its checkout, and checks that
my-evox's container gives the same results. The image is the same as circle packing's but for the
evaluator's files, so Docker builds the second one from the first one's layers.
