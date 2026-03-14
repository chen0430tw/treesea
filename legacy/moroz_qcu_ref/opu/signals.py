# signals.py
def quality_from_candidates(n: int, best_score: float) -> float:
    if n <= 0:
        return 0.0
    return min(1.0, 0.5 + best_score / (n + 1))
