from __future__ import annotations

class TerminationPolicy:
    def should_stop(
        self,
        collapse_score: float,
        stability: float,
        current_step: int,
        target_collapse_score: float,
        target_stability: float,
        max_steps: int,
    ) -> bool:
        if collapse_score >= target_collapse_score and stability >= target_stability:
            return True
        if current_step >= max_steps:
            return True
        return False
