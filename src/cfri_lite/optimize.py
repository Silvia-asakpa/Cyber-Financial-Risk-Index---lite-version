"""Rank security controls and choose the best set within a budget."""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations

from .index import cfri_score, expected_shortfall
from .model import Control, UtilityProfile
from .simulate import Draws, simulate_losses

EXHAUSTIVE_LIMIT = 14  # 2**14 = 16,384 control sets


@dataclass
class ControlValue:
    id: str
    name: str
    annual_cost: float
    expected_loss_reduction: float
    es95_reduction: float
    roi: float  # (expected loss reduction - annual cost) / annual cost

    def as_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class Portfolio:
    budget: float
    objective: str
    method: str
    selected: list[str]
    total_cost: float
    expected_loss: float
    es95: float
    score: float
    baseline_expected_loss: float
    baseline_es95: float
    baseline_score: float
    standalone: list[ControlValue] = field(default_factory=list)

    def as_dict(self) -> dict:
        d = self.__dict__.copy()
        d["standalone"] = [c.as_dict() for c in self.standalone]
        return d


def _evaluate(profile: UtilityProfile, draws: Draws, controls: list[Control]) -> tuple[float, float]:
    total = simulate_losses(profile, draws, controls).sum(axis=1)
    return float(total.mean()), expected_shortfall(total)


def standalone_values(profile: UtilityProfile, draws: Draws) -> list[ControlValue]:
    """Value of each control on its own, compared with no controls."""
    base_el, base_es = _evaluate(profile, draws, [])
    out = []
    for c in profile.controls:
        el, es = _evaluate(profile, draws, [c])
        red = base_el - el
        roi = (red - c.annual_cost) / c.annual_cost if c.annual_cost > 0 else float("inf")
        out.append(ControlValue(c.id, c.name, c.annual_cost, red, base_es - es, roi))
    return sorted(out, key=lambda v: v.es95_reduction / max(v.annual_cost, 1.0), reverse=True)


def optimize(profile: UtilityProfile, draws: Draws, budget: float,
             objective: str = "es95") -> Portfolio:
    """Choose the control set within `budget` that minimizes the objective.

    objective: "es95" (worst-case tail loss, which drives the index) or
    "total_cost" (expected loss + control cost, i.e. best financial return).
    Uses an exhaustive search for up to 14 controls and a greedy search beyond that.
    """
    if objective not in ("es95", "total_cost"):
        raise ValueError("objective must be 'es95' or 'total_cost'")
    controls = profile.controls
    base_el, base_es = _evaluate(profile, draws, [])

    def cost_of(sel):
        return sum(c.annual_cost for c in sel)

    def value(sel):
        el, es = _evaluate(profile, draws, list(sel))
        key = es if objective == "es95" else el + cost_of(sel)
        return key, el, es

    best_sel: tuple = ()
    best = (base_es if objective == "es95" else base_el, base_el, base_es)

    if len(controls) <= EXHAUSTIVE_LIMIT:
        method = "exhaustive"
        for k in range(1, len(controls) + 1):
            for sel in combinations(controls, k):
                if cost_of(sel) > budget:
                    continue
                v = value(sel)
                if v[0] < best[0] - 1e-9 or (abs(v[0] - best[0]) <= 1e-9 and cost_of(sel) < cost_of(best_sel)):
                    best, best_sel = v, sel
    else:
        method = "greedy"
        chosen: list[Control] = []
        while True:
            remaining = [c for c in controls if c not in chosen and cost_of(chosen) + c.annual_cost <= budget]
            if not remaining:
                break
            scored = []
            for c in remaining:
                v = value(chosen + [c])
                gain = (best[0] - v[0]) / max(c.annual_cost, 1.0)
                scored.append((gain, c, v))
            gain, c, v = max(scored, key=lambda t: t[0])
            if gain <= 0:
                break
            chosen.append(c)
            best = v
        best_sel = tuple(chosen)

    _, el, es = best
    return Portfolio(
        budget=budget,
        objective=objective,
        method=method,
        selected=[c.id for c in best_sel],
        total_cost=cost_of(best_sel),
        expected_loss=el,
        es95=es,
        score=cfri_score(es, profile.loss_capacity),
        baseline_expected_loss=base_el,
        baseline_es95=base_es,
        baseline_score=cfri_score(base_es, profile.loss_capacity),
        standalone=standalone_values(profile, draws),
    )
