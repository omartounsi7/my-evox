# EVOLVE-BLOCK-START
"""Constructor-based circle packing for n=26 circles"""

import itertools
import numpy as np


def construct_packing():
    """
    Construct an arrangement of 26 circles in a unit square.

    Row-based layouts are generated and ranked by feasible radius sum. The best
    few seeds (plus jittered copies) are refined by a penalty-method optimizer
    that jointly moves centers and radii (L-BFGS-B with increasing penalty).
    Final radii are always recomputed by a feasible Gauss-Seidel refinement, so
    every returned packing is valid.

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

    # Fallback / baseline: best row layout
    best_c = candidates[0][1].copy()
    best_s = float(np.sum(compute_max_radii(best_c, sweeps=300)))

    try:
        from scipy.optimize import minimize  # noqa: F401
        have_scipy = True
    except Exception:
        have_scipy = False

    if have_scipy:
        rng = np.random.default_rng(1)
        starts = [c for _, c in candidates[:4]]
        for base in list(starts):
            for _ in range(2):
                jitter = base + rng.normal(0.0, 0.02, base.shape)
                starts.append(np.clip(jitter, 0.02, 0.98))
        for _ in range(4):
            starts.append(rng.uniform(0.05, 0.95, (n, 2)))

        for st in starts:
            c = penalty_optimize(st)
            s = float(np.sum(compute_max_radii(c, sweeps=300)))
            if s > best_s:
                best_s = s
                best_c = c
    else:
        best_c = local_search(best_c, iters=1500, seed=0)

    radii = compute_max_radii(best_c, sweeps=300)
    return best_c, radii, float(np.sum(radii))


def _penalty_fun(z, n, mu):
    """Objective -sum(r) + mu * penalty(overlaps and boundary violations)."""
    x = z[:2 * n].reshape(n, 2)
    r = z[2 * n:]

    diff = x[:, None, :] - x[None, :, :]
    D = np.sqrt(np.sum(diff ** 2, axis=-1) + 1e-18)
    np.fill_diagonal(D, 1.0)
    P = r[:, None] + r[None, :] - D
    np.fill_diagonal(P, 0.0)
    P = np.maximum(P, 0.0)
    f_pair = 0.5 * np.sum(P * P)
    gr = 2.0 * P.sum(axis=1)
    coef = -2.0 * P / D
    gx = (coef[:, :, None] * diff).sum(axis=1)

    a = np.maximum(r[:, None] - x, 0.0)
    b = np.maximum(r[:, None] - (1.0 - x), 0.0)
    c = np.maximum(-r, 0.0)
    f_b = np.sum(a * a) + np.sum(b * b) + np.sum(c * c)
    gx = gx + (-2.0 * a + 2.0 * b)
    gr = gr + 2.0 * a.sum(axis=1) + 2.0 * b.sum(axis=1) - 2.0 * c

    f = -np.sum(r) + mu * (f_pair + f_b)
    g_r = -np.ones(n) + mu * gr
    g_x = mu * gx
    grad = np.concatenate([g_x.ravel(), g_r])
    return f, grad


def penalty_optimize(centers):
    """Jointly optimize centers and radii with a quadratic penalty method."""
    from scipy.optimize import minimize

    n = centers.shape[0]
    r0 = compute_max_radii(centers, sweeps=30) * 0.9
    z = np.concatenate([centers.ravel(), r0])
    bounds = [(0.0, 1.0)] * (2 * n) + [(0.0, 0.5)] * n
    for mu in (10.0, 100.0, 1e3, 1e4, 1e5, 1e6):
        res = minimize(_penalty_fun, z, args=(n, mu), jac=True,
                       method="L-BFGS-B", bounds=bounds,
                       options={"maxiter": 400})
        z = res.x
    c = np.clip(z[:2 * n].reshape(n, 2), 0.0, 1.0)
    return c


def local_search(centers, iters=1500, seed=0):
    """
    Seeded stochastic hill climbing on center positions with a decaying
    step size. A move is accepted only if the feasible radius sum improves.
    """
    rng = np.random.default_rng(seed)
    n = centers.shape[0]
    best_c = centers.copy()
    best_s = float(np.sum(compute_max_radii(best_c, sweeps=20)))
    step0, step1 = 0.05, 0.001
    for t in range(iters):
        frac = t / max(1, iters - 1)
        step = step0 * (step1 / step0) ** frac
        c = best_c.copy()
        if rng.random() < 0.7:
            k = int(rng.integers(n))
            c[k] += rng.normal(0.0, step, 2)
        else:
            c += rng.normal(0.0, step * 0.2, c.shape)
        c = np.clip(c, 0.001, 0.999)
        s = float(np.sum(compute_max_radii(c, sweeps=20)))
        if s > best_s + 1e-12:
            best_s = s
            best_c = c
    return best_c


def compute_max_radii(centers, sweeps=30):
    """
    Compute feasible radii for given centers by Gauss-Seidel refinement:
    r_i = min(distance to square border, min_j (d_ij - r_j)).
    Every assignment respects all current neighbors, so the result is feasible.

    Args:
        centers: np.array of shape (n, 2)

    Returns:
        np.array of shape (n) with radii
    """
    n = centers.shape[0]
    diff = centers[:, None, :] - centers[None, :, :]
    D = np.sqrt(np.sum(diff ** 2, axis=-1))
    np.fill_diagonal(D, np.inf)
    bnd = np.minimum(np.minimum(centers[:, 0], centers[:, 1]),
                     np.minimum(1 - centers[:, 0], 1 - centers[:, 1]))
    bnd = np.maximum(bnd, 0.0)
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
