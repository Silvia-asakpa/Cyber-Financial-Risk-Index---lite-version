"""Synthetic water-utility profiles.

All numbers here are ILLUSTRATIVE ASSUMPTIONS chosen to be plausible in order of magnitude.
They are not measurements of any real utility and must not be read as empirical estimates.
Replace them with a utility's own figures before using the results for any decision.
"""
from __future__ import annotations

from pathlib import Path

from .model import Control, Scenario, UtilityProfile, save_profile

# Base scenarios for a mid-size utility: (id, name, category, probability, low, mode, high, description)
_BASE_SCENARIOS = [
    ("S1", "Chemical-dosing tampering", "operational",
     0.02, 500_000, 2_000_000, 12_000_000,
     "Attacker changes treatment chemical setpoints; boil-water notice, response, liability."),
    ("S2", "Control-system disruption (forced manual operation)", "operational",
     0.05, 300_000, 1_500_000, 8_000_000,
     "SCADA/PLC outage forces manual operation, overtime, contractors and lost output."),
    ("S3", "Ransomware on IT and billing systems", "it",
     0.10, 500_000, 2_500_000, 10_000_000,
     "Billing and customer systems offline; delayed revenue, recovery and forensic costs."),
    ("S4", "Sensor and meter data spoofing", "operational",
     0.04, 200_000, 800_000, 4_000_000,
     "Falsified telemetry or meter data causes misbilling, rework and regulatory reporting errors."),
    ("S5", "Vendor-payment diversion (business email compromise)", "financial",
     0.12, 100_000, 600_000, 5_000_000,
     "Fraudulent change of a vendor's bank details diverts large invoice payments."),
    ("S6", "Customer data breach", "it",
     0.06, 200_000, 1_000_000, 6_000_000,
     "Exposure of customer payment and personal data; notification, monitoring, legal costs."),
]

# Controls for a mid-size utility: (id, name, annual cost, prob. reduction, severity reduction, description)
_BASE_CONTROLS = [
    ("C1", "Multi-factor authentication on remote access", 60_000,
     {"S1": 0.40, "S2": 0.50, "S3": 0.30}, {},
     "MFA for all vendor and staff remote access to OT and IT."),
    ("C2", "OT/IT network segmentation", 250_000,
     {"S1": 0.50, "S2": 0.40, "S4": 0.30}, {"S3": 0.20},
     "Separate control networks from business networks; restrict traffic between them."),
    ("C3", "Offline backups with tested restores", 120_000,
     {}, {"S2": 0.20, "S3": 0.50},
     "Immutable/offline backups for billing, finance and SCADA configurations."),
    ("C4", "Vendor bank-detail call-back verification", 15_000,
     {"S5": 0.70}, {},
     "Independent phone verification before any change to vendor payment details."),
    ("C5", "PLC setpoint limits and safety interlocks", 80_000,
     {"S1": 0.20}, {"S1": 0.60},
     "Hard limits on chemical dosing setpoints that software commands cannot override."),
    ("C6", "24/7 security monitoring and response", 300_000,
     {"S3": 0.25, "S4": 0.30, "S6": 0.30}, {"S1": 0.20, "S2": 0.20, "S3": 0.20},
     "Managed detection and response covering IT and OT."),
    ("C7", "Phishing-resistant staff training", 25_000,
     {"S3": 0.20, "S5": 0.30, "S6": 0.20}, {},
     "Recurring training and simulated phishing for finance and operations staff."),
    ("C8", "Cyber insurance (net of deductible)", 180_000,
     {}, {"S1": 0.35, "S2": 0.35, "S3": 0.35, "S4": 0.35, "S5": 0.35, "S6": 0.35},
     "Transfers part of the loss to an insurer; does not prevent attacks."),
]

# Size classes: loss scale, probability scale, control-cost scale and balance-sheet figures.
SIZE_CLASSES = {
    "small_rural": dict(
        name="Synthetic Small Rural Water System",
        population_served=8_000, annual_operating_budget=3_500_000,
        reserves=900_000, undrawn_liquidity=250_000,
        loss_scale=0.08, prob_scale=1.25, cost_scale=0.10,
        notes="Small system with limited IT staff; higher probabilities, smaller absolute losses."),
    "mid_size": dict(
        name="Synthetic Mid-Size Municipal Utility",
        population_served=250_000, annual_operating_budget=60_000_000,
        reserves=15_000_000, undrawn_liquidity=5_000_000,
        loss_scale=1.0, prob_scale=1.0, cost_scale=1.0,
        notes="Reference case used to set the base assumptions."),
    "large_metro": dict(
        name="Synthetic Large Metropolitan Utility",
        population_served=1_500_000, annual_operating_budget=450_000_000,
        reserves=150_000_000, undrawn_liquidity=100_000_000,
        loss_scale=5.0, prob_scale=1.10, cost_scale=4.0,
        notes="Large system; more exposure and a more attractive target, but deeper reserves."),
}


def make_profile(size_class: str) -> UtilityProfile:
    if size_class not in SIZE_CLASSES:
        raise ValueError(f"size_class must be one of {sorted(SIZE_CLASSES)}")
    cfg = SIZE_CLASSES[size_class]
    scenarios = [
        Scenario(id=sid, name=name, category=cat,
                 annual_probability=round(min(p * cfg["prob_scale"], 0.95), 4),
                 loss_low=round(lo * cfg["loss_scale"], -3),
                 loss_mode=round(mo * cfg["loss_scale"], -3),
                 loss_high=round(hi * cfg["loss_scale"], -3),
                 description=desc)
        for sid, name, cat, p, lo, mo, hi, desc in _BASE_SCENARIOS
    ]
    controls = [
        Control(id=cid, name=name, annual_cost=round(cost * cfg["cost_scale"], -2),
                probability_reduction=dict(pr), severity_reduction=dict(sr), description=desc)
        for cid, name, cost, pr, sr, desc in _BASE_CONTROLS
    ]
    profile = UtilityProfile(
        name=cfg["name"], reserves=cfg["reserves"], undrawn_liquidity=cfg["undrawn_liquidity"],
        scenarios=scenarios, controls=controls,
        population_served=cfg["population_served"],
        annual_operating_budget=cfg["annual_operating_budget"],
        synthetic=True,
        notes="SYNTHETIC - illustrative assumptions only, not data from any real utility. " + cfg["notes"],
    )
    profile.validate()
    return profile


def write_all(out_dir: str | Path) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for key in SIZE_CLASSES:
        path = out / f"{key}.json"
        save_profile(make_profile(key), path)
        paths.append(path)
    return paths
