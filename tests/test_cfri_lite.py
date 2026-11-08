import json
import math

import numpy as np
import pytest

from cfri_lite import (Control, Scenario, UtilityProfile, cfri_score, expected_shortfall,
                       make_draws, optimize, ratio_for_score, simulate_losses, summarize, tier,
                       value_at_risk)
from cfri_lite.cli import main
from cfri_lite.simulate import triangular_ppf
from cfri_lite.synthetic import SIZE_CLASSES, make_profile


# ---------- index ----------

def test_score_anchor_points():
    assert cfri_score(0, 10) == 0
    assert cfri_score(10, 10) == pytest.approx(80.0)          # loss == capacity -> 80
    assert cfri_score(1e12, 10) == pytest.approx(100.0)
    assert ratio_for_score(80.0) == pytest.approx(1.0)


def test_score_reproduces_illustrative_case():
    # Illustrative case: worst-case loss $4.0M -> score 30.1 and $15.3M -> 74.5 for the
    # same utility. Both points fit the curve with one loss capacity of about $18M.
    capacity = 4.0e6 / ratio_for_score(30.1)
    assert capacity == pytest.approx(18.0e6, rel=0.01)
    assert cfri_score(15.3e6, capacity) == pytest.approx(74.5, abs=0.2)


def test_tiers():
    assert tier(0) == "Tier 1 - Low"
    assert tier(39.9) == "Tier 2 - Guarded"
    assert tier(80) == "Tier 5 - Severe"


def test_tail_measures():
    losses = np.arange(1, 101, dtype=float)
    assert value_at_risk(losses) == pytest.approx(95.05)
    assert expected_shortfall(losses) == pytest.approx(np.mean([96, 97, 98, 99, 100]))


# ---------- simulation ----------

def test_triangular_ppf_mean():
    u = np.random.default_rng(0).random(400_000)
    x = triangular_ppf(u, 1.0, 2.0, 6.0)
    assert x.min() >= 1.0 and x.max() <= 6.0
    assert x.mean() == pytest.approx((1 + 2 + 6) / 3, rel=0.01)


def _toy_profile():
    return UtilityProfile(
        name="toy", reserves=1_000_000, undrawn_liquidity=0,
        scenarios=[Scenario("S1", "a", 0.2, 100, 200, 400), Scenario("S2", "b", 0.1, 1000, 1500, 3000)],
        controls=[Control("C1", "cut S1", 10, {"S1": 0.5}), Control("C2", "shrink S2", 20, {}, {"S2": 0.5})],
    )


def test_simulation_matches_analytic_expected_loss():
    p = _toy_profile()
    m = simulate_losses(p, make_draws(p, n=200_000, seed=1))
    analytic = 0.2 * (100 + 200 + 400) / 3 + 0.1 * (1000 + 1500 + 3000) / 3
    assert m.sum(axis=1).mean() == pytest.approx(analytic, rel=0.02)


def test_controls_reduce_loss_and_seed_is_deterministic():
    p = _toy_profile()
    d = make_draws(p, n=20_000, seed=7)
    base = simulate_losses(p, d).sum()
    with_c = simulate_losses(p, d, p.controls).sum()
    assert with_c < base
    again = simulate_losses(p, make_draws(p, n=20_000, seed=7)).sum()
    assert again == base


def test_validation_rejects_bad_inputs():
    with pytest.raises(ValueError):
        Scenario("S1", "bad", 1.5, 1, 2, 3).validate()
    with pytest.raises(ValueError):
        Scenario("S1", "bad", 0.1, 5, 2, 3).validate()
    p = _toy_profile()
    p.controls.append(Control("C9", "unknown", 1, {"S9": 0.5}))
    with pytest.raises(ValueError):
        p.validate()


# ---------- optimizer ----------

def test_optimizer_respects_budget_and_improves():
    p = make_profile("mid_size")
    d = make_draws(p, n=5_000, seed=3)
    port = optimize(p, d, budget=400_000)
    assert port.total_cost <= 400_000
    assert port.es95 <= port.baseline_es95
    assert port.score <= port.baseline_score
    assert len(port.standalone) == len(p.controls)


def test_zero_budget_selects_nothing():
    p = make_profile("small_rural")
    port = optimize(p, make_draws(p, n=2_000, seed=1), budget=0)
    assert port.selected == []
    assert port.es95 == pytest.approx(port.baseline_es95)


# ---------- synthetic data and CLI ----------

@pytest.mark.parametrize("key", sorted(SIZE_CLASSES))
def test_synthetic_profiles_are_valid_and_marked(key):
    p = make_profile(key)
    p.validate()
    assert p.synthetic and "SYNTHETIC" in p.notes
    s = summarize(p, simulate_losses(p, make_draws(p, n=5_000, seed=0)))
    assert 0 <= s.score <= 100
    assert math.isclose(sum(s.scenario_tail_share.values()), 1.0, rel_tol=1e-9)


def test_reserve_scaling_ranks_small_system_highest():
    scores = {}
    for key in SIZE_CLASSES:
        p = make_profile(key)
        scores[key] = summarize(p, simulate_losses(p, make_draws(p, n=10_000, seed=0))).score
    assert scores["small_rural"] > scores["mid_size"] > scores["large_metro"]


def test_cli_end_to_end(tmp_path):
    main(["synth", "--out", str(tmp_path / "data")])
    main(["run", str(tmp_path / "data" / "mid_size.json"), "--budget", "400000",
          "--simulations", "5000", "--out", str(tmp_path / "out")])
    report = (tmp_path / "out" / "mid_size_report.md").read_text(encoding="utf-8")
    assert "Synthetic data" in report and "CFRI-lite score" in report
    results = json.loads((tmp_path / "out" / "mid_size_results.json").read_text(encoding="utf-8"))
    assert results["synthetic"] is True
