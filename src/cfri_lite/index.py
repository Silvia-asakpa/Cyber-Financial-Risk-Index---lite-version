"""Risk measures and the Cyber-Financial Risk Index (CFRI-lite score)."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .model import UtilityProfile

CONFIDENCE = 0.95

# Five tiers on the 0-100 scale. The highest tier starts at 80, the score reached when the
# worst-case (95% expected shortfall) loss equals the utility's loss capacity.
TIERS = [
    (0.0, "Tier 1 - Low"),
    (20.0, "Tier 2 - Guarded"),
    (40.0, "Tier 3 - Elevated"),
    (60.0, "Tier 4 - High"),
    (80.0, "Tier 5 - Severe"),
]


def value_at_risk(losses: np.ndarray, confidence: float = CONFIDENCE) -> float:
    return float(np.quantile(losses, confidence))


def expected_shortfall(losses: np.ndarray, confidence: float = CONFIDENCE) -> float:
    """Average loss in the worst (1 - confidence) share of simulated years."""
    var = value_at_risk(losses, confidence)
    tail = losses[losses >= var]
    return float(tail.mean())


def cfri_score(es: float, loss_capacity: float) -> float:
    """Map the loss-to-capacity ratio r = ES95 / capacity to a 0-100 score.

    score = 100 * (1 - 5 ** (-r)), so r = 0 -> 0, r = 1 -> 80, r -> infinity -> 100.
    The curve rises fastest for small ratios, so early growth in exposure is visible.
    """
    if loss_capacity <= 0:
        raise ValueError("loss_capacity must be positive")
    r = max(es, 0.0) / loss_capacity
    return 100.0 * (1.0 - 5.0 ** (-r))


def ratio_for_score(score: float) -> float:
    """Inverse of cfri_score: the loss-to-capacity ratio that produces a given score."""
    if not 0.0 <= score < 100.0:
        raise ValueError("score must be in [0, 100)")
    return -math.log(1.0 - score / 100.0) / math.log(5.0)


def tier(score: float) -> str:
    label = TIERS[0][1]
    for threshold, name in TIERS:
        if score >= threshold:
            label = name
    return label


@dataclass
class RiskSummary:
    utility: str
    simulations: int
    loss_capacity: float
    expected_loss: float
    var95: float
    es95: float
    loss_to_capacity: float
    score: float
    tier: str
    scenario_expected_loss: dict[str, float] = field(default_factory=dict)
    scenario_tail_share: dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def summarize(profile: UtilityProfile, loss_matrix: np.ndarray,
              confidence: float = CONFIDENCE) -> RiskSummary:
    total = loss_matrix.sum(axis=1)
    var = value_at_risk(total, confidence)
    es = expected_shortfall(total, confidence)
    tail_rows = total >= var
    tail_by_scenario = loss_matrix[tail_rows].mean(axis=0)
    tail_total = tail_by_scenario.sum()
    ids = profile.scenario_ids
    score = cfri_score(es, profile.loss_capacity)
    return RiskSummary(
        utility=profile.name,
        simulations=int(total.size),
        loss_capacity=profile.loss_capacity,
        expected_loss=float(total.mean()),
        var95=var,
        es95=es,
        loss_to_capacity=es / profile.loss_capacity,
        score=score,
        tier=tier(score),
        scenario_expected_loss={sid: float(v) for sid, v in zip(ids, loss_matrix.mean(axis=0))},
        scenario_tail_share={sid: (float(v / tail_total) if tail_total > 0 else 0.0)
                             for sid, v in zip(ids, tail_by_scenario)},
    )
