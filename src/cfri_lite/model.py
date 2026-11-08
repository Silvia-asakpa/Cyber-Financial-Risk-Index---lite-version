"""Data model for cfri-lite: utility profiles, attack scenarios and security controls."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Scenario:
    """One cyber-attack scenario and the financial loss it causes if it succeeds.

    annual_probability: chance of at least one successful incident in the horizon (0-1).
    loss_low / loss_mode / loss_high: triangular distribution of the total financial
        loss (USD) of one incident: response, manual operation, lost or delayed revenue,
        regulatory costs, fraud loss and legal costs combined.
    """

    id: str
    name: str
    annual_probability: float
    loss_low: float
    loss_mode: float
    loss_high: float
    category: str = ""
    description: str = ""

    def validate(self) -> None:
        if not 0.0 <= self.annual_probability <= 1.0:
            raise ValueError(f"{self.id}: annual_probability must be between 0 and 1")
        if not 0.0 <= self.loss_low <= self.loss_mode <= self.loss_high:
            raise ValueError(f"{self.id}: losses must satisfy 0 <= low <= mode <= high")
        if self.loss_high == self.loss_low:
            raise ValueError(f"{self.id}: loss_high must be greater than loss_low")


@dataclass
class Control:
    """A security control and its modeled effect.

    annual_cost: annualized cost in USD (license, staff time, amortized capital).
    probability_reduction: {scenario_id: fraction} - cuts the chance the scenario succeeds.
    severity_reduction: {scenario_id: fraction} - cuts the loss when it does succeed.
    Effects of several controls on the same scenario combine multiplicatively.
    """

    id: str
    name: str
    annual_cost: float
    probability_reduction: dict[str, float] = field(default_factory=dict)
    severity_reduction: dict[str, float] = field(default_factory=dict)
    description: str = ""

    def validate(self, scenario_ids: set[str]) -> None:
        if self.annual_cost < 0:
            raise ValueError(f"{self.id}: annual_cost must be >= 0")
        for label, effects in (("probability_reduction", self.probability_reduction),
                               ("severity_reduction", self.severity_reduction)):
            for sid, value in effects.items():
                if sid not in scenario_ids:
                    raise ValueError(f"{self.id}: {label} refers to unknown scenario {sid!r}")
                if not 0.0 <= value <= 1.0:
                    raise ValueError(f"{self.id}: {label}[{sid}] must be between 0 and 1")


@dataclass
class UtilityProfile:
    """A (synthetic) public water utility.

    loss_capacity = reserves + undrawn_liquidity: the money the utility could use to absorb
    a loss without emergency rate increases or new borrowing. It is the denominator of the index.
    """

    name: str
    reserves: float
    undrawn_liquidity: float
    scenarios: list[Scenario]
    controls: list[Control] = field(default_factory=list)
    population_served: int = 0
    annual_operating_budget: float = 0.0
    horizon_years: int = 1
    synthetic: bool = True
    notes: str = ""

    @property
    def loss_capacity(self) -> float:
        return self.reserves + self.undrawn_liquidity

    @property
    def scenario_ids(self) -> list[str]:
        return [s.id for s in self.scenarios]

    def validate(self) -> None:
        if self.loss_capacity <= 0:
            raise ValueError("reserves + undrawn_liquidity must be positive")
        ids = [s.id for s in self.scenarios]
        if len(ids) != len(set(ids)):
            raise ValueError("scenario ids must be unique")
        for s in self.scenarios:
            s.validate()
        cids = [c.id for c in self.controls]
        if len(cids) != len(set(cids)):
            raise ValueError("control ids must be unique")
        for c in self.controls:
            c.validate(set(ids))

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "UtilityProfile":
        data = dict(data)
        data["scenarios"] = [Scenario(**s) for s in data.get("scenarios", [])]
        data["controls"] = [Control(**c) for c in data.get("controls", [])]
        profile = cls(**data)
        profile.validate()
        return profile


def load_profile(path: str | Path) -> UtilityProfile:
    with open(path, encoding="utf-8") as fh:
        return UtilityProfile.from_dict(json.load(fh))


def save_profile(profile: UtilityProfile, path: str | Path) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(profile.to_dict(), fh, indent=2)
        fh.write("\n")
