"""Points with a coordinate that is not a number."""
import numpy as np


def min_max_dist_dim3_14():
    np.random.seed(1)
    points = np.random.randn(14, 3)
    points[3, 1] = float("nan")
    return points
