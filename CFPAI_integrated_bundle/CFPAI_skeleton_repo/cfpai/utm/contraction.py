from __future__ import annotations

import numpy as np

def contract_population(means: np.ndarray, scales: np.ndarray, elite_vecs: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    new_means = elite_vecs.mean(axis=0)
    elite_std = elite_vecs.std(axis=0)
    new_scales = np.maximum(0.03 * (upper - lower), 0.85 * elite_std + 0.15 * scales)
    return new_means, new_scales
