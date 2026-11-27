"""A valid packing (a 5 by 5 grid and one small circle) that prints while it runs."""
import numpy as np


def run_packing():
    print("placing 26 circles")
    centers = [[0.1 + 0.2 * column, 0.1 + 0.2 * row] for row in range(5) for column in range(5)]
    centers.append([0.2, 0.2])
    radii = [0.1] * 25 + [0.04]
    centers, radii = np.array(centers), np.array(radii)
    print("done:", radii.sum())
    return centers, radii, radii.sum()
