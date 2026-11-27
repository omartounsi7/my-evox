"""An invalid packing: one circle crosses the square's edge."""
import numpy as np


def run_packing():
    centers = [[0.1 + 0.2 * column, 0.1 + 0.2 * row] for row in range(5) for column in range(5)]
    centers.append([0.99, 0.5])
    radii = np.array([0.1] * 25 + [0.05])
    return np.array(centers), radii, radii.sum()
