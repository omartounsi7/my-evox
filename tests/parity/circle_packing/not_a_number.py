"""A packing with a radius that is not a number."""
import numpy as np


def run_packing():
    centers = [[0.1 + 0.2 * column, 0.1 + 0.2 * row] for row in range(5) for column in range(5)]
    centers.append([0.2, 0.2])
    radii = np.array([0.1] * 25 + [float("nan")])
    return np.array(centers), radii, radii.sum()
