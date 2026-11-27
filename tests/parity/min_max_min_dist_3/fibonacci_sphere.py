"""14 points spread over a sphere by the golden angle."""
import numpy as np


def min_max_dist_dim3_14():
    index = np.arange(14) + 0.5
    height = 1 - 2 * index / 14
    radius = np.sqrt(1 - height**2)
    angle = np.pi * (1 + 5**0.5) * index
    return np.stack([radius * np.cos(angle), radius * np.sin(angle), height], axis=1)
