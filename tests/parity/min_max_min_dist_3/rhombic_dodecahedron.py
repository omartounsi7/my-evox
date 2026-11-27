"""The 14 vertices of a rhombic dodecahedron: a cube's 8 corners and an octahedron's 6."""
import itertools

import numpy as np


def min_max_dist_dim3_14():
    corners = [list(signs) for signs in itertools.product((-1.0, 1.0), repeat=3)]
    tips = [[2.0, 0, 0], [-2.0, 0, 0], [0, 2.0, 0], [0, -2.0, 0], [0, 0, 2.0], [0, 0, -2.0]]
    return np.array(corners + tips)
