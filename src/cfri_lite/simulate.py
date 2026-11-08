"""Monte Carlo simulation of annual cyber-attack losses.

The simulation uses common random numbers: the same uniform draws are reused when
controls are switched on or off, so differences between control sets reflect the
controls rather than sampling noise.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np

from .model import Control, UtilityProfile


@dataclass
class Draws:
    occurrence: np.ndarray  # shape (n, S), uniform(0,1)
    severity: np.ndarray    # shape (n, S), uniform(0,1)

    @property
    def n(self) -> int:
        return self.occurrence.shape[0]


def make_draws(profile: UtilityProfile, n: int = 20_000, seed: int | None = 42) -> Draws:
    if n < 1_000:
        raise ValueError("use at least 1,000 simulations")
    rng = np.random.default_rng(seed)
    shape = (n, len(profile.scenarios))
    return Draws(rng.random(shape), rng.random(shape))


def triangular_ppf(u: np.ndarray, low: np.ndarray, mode: np.ndarray, high: np.ndarray) -> np.ndarray:
    """Inverse CDF of the triangular distribution (vectorized over columns)."""
    span = high - low
    cut = (mode - low) / span
    left = low + np.sqrt(u * span * (mode - low))
    right = high - np.sqrt((1.0 - u) * span * (high - mode))
    return np.where(u < cut, left, right)


def control_multipliers(profile: UtilityProfile, controls: Iterable[Control]) -> tuple[np.ndarray, np.ndarray]:
    """Return per-scenario multipliers (probability, severity) for a set of controls."""
    ids = profile.scenario_ids
    p_mult = np.ones(len(ids))
    s_mult = np.ones(len(ids))
    for c in controls:
        for k, sid in enumerate(ids):
            p_mult[k] *= 1.0 - c.probability_reduction.get(sid, 0.0)
            s_mult[k] *= 1.0 - c.severity_reduction.get(sid, 0.0)
    return p_mult, s_mult


def simulate_losses(profile: UtilityProfile, draws: Draws,
                    controls: Iterable[Control] = ()) -> np.ndarray:
    """Return a (n, S) matrix of simulated annual losses per scenario."""
    sc = profile.scenarios
    p = np.array([s.annual_probability for s in sc])
    low = np.array([s.loss_low for s in sc])
    mode = np.array([s.loss_mode for s in sc])
    high = np.array([s.loss_high for s in sc])
    p_mult, s_mult = control_multipliers(profile, controls)
    occurs = draws.occurrence < p * p_mult
    severity = triangular_ppf(draws.severity, low, mode, high) * s_mult
    return np.where(occurs, severity, 0.0)
