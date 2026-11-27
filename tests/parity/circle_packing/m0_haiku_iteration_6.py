# EVOLVE-BLOCK-START
"""Constructor-based circle packing for n=26 circles"""

import itertools
import math
import numpy as np


def construct_packing():
    """
    Construct an arrangement of 26 circles in a unit square.

    Row-based layouts are generated explicitly and ranked by their feasible
    radius sum. The top few seeds are refined by a seeded simulated-annealing
    search over center positions. For each candidate center set, radii are
    computed as the exact LP optimum (when SciPy is available), so the
    annealing objective is the true maximal radius sum for those centers.

    Returns:
        Tuple of (centers, radii, sum_of_radii)
    """
    n = 26
    candidates = []

    for k, rng in ((4, range(5, 9)), (5, range(3, 8)), (6, range(3, 8))):
        for counts in itertools.product(rng, repeat=k):
            if sum(counts) != n:
                continue
            centers = np.zeros((n, 2))
            idx = 0
            for i, c in enumerate(counts):
                y = (i + 0.5) / k
                for j in range(c):
                    x = (j + 0.5) / c
                    centers[idx] = [x, y]
                    idx += 1
            radii = compute_max_radii(centers)
            candidates.append((float(np.sum(radii)), centers.copy()))

    candidates.sort(key=lambda t: -t[0])

    best_c = None
    best_s = -1.0
    for rank, (_, start) in enumerate(candidates[:3]):
        c = anneal(start, iters=2000, seed=rank)
        s = float(np.sum(compute_max_radii(c)))
        if s > best_s:
            best_s = s
            best_c = c

    centers = best_c
    radii = compute_max_radii(centers, sweeps=300)
    return centers, radii, float(np.sum(radii))


def anneal(centers, iters=2000, seed=0):
    """
    Seeded simulated annealing on center positions with decaying step size
    and decaying temperature. Scoring uses the feasible radius sum, so every
    accepted state corresponds to a valid packing. The best state seen is
    returned.
    """
    rng = np.random.default_rng(seed)
    n = centers.shape[0]

    cur_c = centers.copy()
    cur_s = float(np.sum(compute_max_radii(cur_c)))
    best_c = cur_c.copy()
    best_s = cur_s

    step0, step1 = 0.05, 0.001
    T0, T1 = 0.01, 0.0001

    for t in range(iters):
        frac = t / max(1, iters - 1)
        step = step0 * (step1 / step0) ** frac
        T = T0 * (T1 / T0) ** frac

        c = cur_c.copy()
        u = rng.random()
        if u < 0.6:
            k = int(rng.integers(n))
            c[k] += rng.normal(0.0, step, 2)
        elif u < 0.9:
            # Move a small group of nearby circles together
            k = int(rng.integers(n))
            d = np.sqrt(np.sum((c - c[k]) ** 2, axis=1))
            near = np.where(d < 0.25)[0]
            c[near] += rng.normal(0.0, step * 0.5, 2)
        else:
            c += rng.normal(0.0, step * 0.2, c.shape)
        c = np.clip(c, 0.001, 0.999)

        s = float(np.sum(compute_max_radii(c)))
        delta = s - cur_s
        if delta > 1e-12 or (T > 0 and rng.random() < math.exp(min(0.0, delta) / T)):
            cur_c = c
            cur_s = s
            if cur_s > best_s + 1e-12:
                best_s = cur_s
                best_c = cur_c.copy()

    return best_c


def _pairwise_and_bounds(centers):
    n = centers.shape[0]
    diff = centers[:, None, :] - centers[None, :, :]
    D = np.sqrt(np.sum(diff ** 2, axis=-1))
    np.fill_diagonal(D, np.inf)
    bnd = np.minimum(np.minimum(centers[:, 0], centers[:, 1]),
                     np.minimum(1 - centers[:, 0], 1 - centers[:, 1]))
    bnd = np.maximum(bnd, 0.0)
    return D, bnd


def _lp_radii(centers):
    """Exact maximal radii for fixed centers via LP (requires SciPy)."""
    from scipy.optimize import linprog
    n = centers.shape[0]
    D, bnd = _pairwise_and_bounds(centers)
    rows = []
    b = []
    for i in range(n):
        for j in range(i + 1, n):
            row = np.zeros(n)
            row[i] = 1.0
            row[j] = 1.0
            rows.append(row)
            b.append(D[i, j])
    A = np.array(rows)
    bvec = np.array(b)
    bounds = [(0.0, float(bnd[i])) for i in range(n)]
    res = linprog(-np.ones(n), A_ub=A, b_ub=bvec, bounds=bounds,
                  method="highs")
    if not res.success:
        return None
    r = np.maximum(res.x - 1e-12, 0.0)
    return r


def compute_max_radii(centers, sweeps=30):
    """
    Compute feasible radii for given centers.

    Preferred: exact LP maximum of the radius sum for fixed centers.
    Fallback: Gauss-Seidel refinement r_i = min(border distance,
    min_j (d_ij - r_j)), which is always feasible.

    Args:
        centers: np.array of shape (n, 2)

    Returns:
        np.array of shape (n) with radii
    """
    try:
        r = _lp_radii(centers)
        if r is not None:
            return r
    except Exception:
        pass

    n = centers.shape[0]
    D, bnd = _pairwise_and_bounds(centers)
    r = bnd.copy()
    for _ in range(sweeps):
        old = r.copy()
        for i in range(n):
            vals = D[i] - r
            m = min(bnd[i], float(np.min(vals)))
            r[i] = max(m, 0.0)
        if np.max(np.abs(r - old)) < 1e-13:
            break
    return r


# EVOLVE-BLOCK-END


# This part remains fixed (not evolved)
def run_packing():
    """Run the circle packing constructor for n=26"""
    centers, radii, sum_radii = construct_packing()
    return centers, radii, sum_radii


def visualize(centers, radii):
    """
    Visualize the circle packing

    Args:
        centers: np.array of shape (n, 2) with (x, y) coordinates
        radii: np.array of shape (n) with radius of each circle
    """
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal")
    ax.grid(True)

    for i, (center, radius) in enumerate(zip(centers, radii)):
        circle = Circle(center, radius, alpha=0.5)
        ax.add_patch(circle)
        ax.text(center[0], center[1], str(i), ha="center", va="center")

    plt.title(f"Circle Packing (n={len(centers)}, sum={sum(radii):.6f})")
    plt.show()


if __name__ == "__main__":
    centers, radii, sum_radii = run_packing()
    print(f"Sum of radii: {sum_radii}")
    # AlphaEvolve improved this to 2.635

    # Uncomment to visualize:
    # visualize(centers, radii)
