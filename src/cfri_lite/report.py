"""Write a plain-language risk report (Markdown + JSON + chart) for a utility profile."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .index import TIERS, RiskSummary
from .model import UtilityProfile
from .optimize import Portfolio


def money(x: float) -> str:
    x = float(x)
    if abs(x) >= 1e6:
        return f"${x / 1e6:,.2f}M"
    if abs(x) >= 1e3:
        return f"${x / 1e3:,.0f}K"
    return f"${x:,.0f}"


def _chart(total_losses: np.ndarray, summary: RiskSummary, path: Path, title: str) -> bool:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False
    nonzero = total_losses[total_losses > 0]
    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=120)
    ax.hist(nonzero / 1e6, bins=60, color="#4C78A8", alpha=0.85)
    for value, label, style in ((summary.expected_loss, "Expected loss", ":"),
                                (summary.var95, "95% VaR", "--"),
                                (summary.es95, "95% expected shortfall", "-"),
                                (summary.loss_capacity, "Loss capacity", "-.")):
        ax.axvline(value / 1e6, color="#222222", linestyle=style, linewidth=1.2)
        ax.text(value / 1e6, ax.get_ylim()[1] * 0.92, " " + label, rotation=90,
                va="top", ha="left", fontsize=8)
    share = 100 * (1 - nonzero.size / total_losses.size)
    ax.set_title(f"{title}\nSimulated annual losses in years with at least one incident "
                 f"({share:.0f}% of years have none)", fontsize=10)
    ax.set_xlabel("Annual loss (USD millions)")
    ax.set_ylabel("Simulated years")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return True


def write_report(profile: UtilityProfile, loss_matrix: np.ndarray, summary: RiskSummary,
                 portfolio: Portfolio | None, out_dir: str | Path, stem: str) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    total = loss_matrix.sum(axis=1)
    chart_name = f"{stem}_loss_distribution.png"
    has_chart = _chart(total, summary, out / chart_name, profile.name)
    names = {s.id: s.name for s in profile.scenarios}
    cnames = {c.id: c.name for c in profile.controls}

    lines = [f"# CFRI-lite Risk Report: {profile.name}", ""]
    if profile.synthetic:
        lines += ["> **Synthetic data.** This report uses illustrative assumptions, not data from any "
                  "real utility. It demonstrates the method only.", ""]
    lines += [
        "## Headline",
        "",
        f"- **CFRI-lite score: {summary.score:.1f} / 100 ({summary.tier})**",
        f"- Worst-case loss (average of the worst 5% of years, ES95): **{money(summary.es95)}**",
        f"- Loss capacity (reserves {money(profile.reserves)} + undrawn liquidity "
        f"{money(profile.undrawn_liquidity)}): **{money(summary.loss_capacity)}**",
        f"- The worst-case loss equals **{summary.loss_to_capacity:.0%}** of loss capacity "
        f"(a ratio of 100% scores 80, the start of the highest tier).",
        f"- Expected annual loss: {money(summary.expected_loss)}; 95% value-at-risk: {money(summary.var95)}",
        f"- Simulations: {summary.simulations:,}",
        "",
    ]
    if has_chart:
        lines += [f"![Loss distribution]({chart_name})", ""]
    lines += ["## Which scenarios drive the worst case", "",
              "| Scenario | Annual probability | Expected annual loss | Share of worst-case loss |",
              "|---|---:|---:|---:|"]
    probs = {s.id: s.annual_probability for s in profile.scenarios}
    for sid in sorted(summary.scenario_tail_share, key=summary.scenario_tail_share.get, reverse=True):
        lines.append(f"| {sid} {names[sid]} | {probs[sid]:.1%} | "
                     f"{money(summary.scenario_expected_loss[sid])} | "
                     f"{summary.scenario_tail_share[sid]:.0%} |")
    lines.append("")

    if portfolio is not None:
        lines += ["## Security investments ranked", "",
                  "Each control evaluated on its own against no controls. Ranked by worst-case "
                  "loss reduction per dollar.", "",
                  "| Control | Annual cost | Expected loss reduction | Worst-case (ES95) reduction | ROI on expected loss |",
                  "|---|---:|---:|---:|---:|"]
        for v in portfolio.standalone:
            lines.append(f"| {v.id} {v.name} | {money(v.annual_cost)} | {money(v.expected_loss_reduction)} | "
                         f"{money(v.es95_reduction)} | {v.roi:+.0%} |")
        objective = ("lowest worst-case loss (ES95)" if portfolio.objective == "es95"
                     else "lowest expected loss plus control cost")
        selected = ", ".join(f"{c} {cnames[c]}" for c in portfolio.selected) or "none"
        lines += ["", f"## Best control set within a {money(portfolio.budget)} annual budget", "",
                  f"Objective: {objective}. Search: {portfolio.method}.", "",
                  f"- Selected: {selected}",
                  f"- Annual cost: {money(portfolio.total_cost)}",
                  f"- Score: **{portfolio.baseline_score:.1f} -> {portfolio.score:.1f}** "
                  f"(worst-case loss {money(portfolio.baseline_es95)} -> {money(portfolio.es95)})",
                  f"- Expected annual loss: {money(portfolio.baseline_expected_loss)} -> "
                  f"{money(portfolio.expected_loss)}",
                  ""]

    lines += ["## How to read the score", "",
              "| Score | Tier |", "|---|---|"]
    bounds = [t[0] for t in TIERS] + [100.0]
    for (lo, label), hi in zip(TIERS, bounds[1:]):
        lines.append(f"| {lo:.0f} - {hi:.0f} | {label} |")
    lines += ["", "Method: see `docs/methodology.md`. This is a planning model, not a forecast.", ""]

    md_path = out / f"{stem}_report.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    payload = {"summary": summary.as_dict(),
               "portfolio": portfolio.as_dict() if portfolio else None,
               "synthetic": profile.synthetic}
    (out / f"{stem}_results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return md_path
