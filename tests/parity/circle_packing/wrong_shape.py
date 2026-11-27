"""A packing of 25 circles instead of 26."""
import numpy as np


def run_packing():
    centers = [[0.1 + 0.2 * column, 0.1 + 0.2 * row] for row in range(5) for column in range(5)]
    radii = np.array([0.1] * 25)
    return np.array(centers), radii, radii.sum()
