"""cfri-lite: a cyber-financial loss calculator for public water utilities.

Open-source companion to the Cyber-Financial Risk Index (CFRI) research of
Silvia Tsovwen Asakpa. Implements only the financial loss-simulation and scoring
layer, using synthetic data. See README.md and docs/methodology.md.
"""
from .index import cfri_score, expected_shortfall, ratio_for_score, summarize, tier, value_at_risk
from .model import Control, Scenario, UtilityProfile, load_profile, save_profile
from .optimize import optimize, standalone_values
from .simulate import make_draws, simulate_losses

__version__ = "0.1.0"

__all__ = [
    "Control", "Scenario", "UtilityProfile", "load_profile", "save_profile",
    "make_draws", "simulate_losses", "summarize", "cfri_score", "ratio_for_score",
    "tier", "value_at_risk", "expected_shortfall", "optimize", "standalone_values",
]
