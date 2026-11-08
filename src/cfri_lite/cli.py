"""Command-line interface.

Examples:
    cfri-lite synth --out data/synthetic
    cfri-lite run data/synthetic/mid_size.json --budget 400000 --out examples
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .index import summarize
from .model import load_profile
from .optimize import optimize
from .report import money, write_report
from .simulate import make_draws, simulate_losses
from .synthetic import write_all


def _run(args: argparse.Namespace) -> None:
    profile = load_profile(args.profile)
    draws = make_draws(profile, n=args.simulations, seed=args.seed)
    matrix = simulate_losses(profile, draws)
    summary = summarize(profile, matrix)
    portfolio = None
    if profile.controls and args.budget is not None:
        portfolio = optimize(profile, draws, args.budget, objective=args.objective)
    stem = args.stem or Path(args.profile).stem
    path = write_report(profile, matrix, summary, portfolio, args.out, stem)
    print(f"{profile.name}: score {summary.score:.1f} ({summary.tier}), "
          f"ES95 {money(summary.es95)} vs capacity {money(summary.loss_capacity)}")
    if portfolio:
        print(f"  best set within {money(args.budget)}: {', '.join(portfolio.selected) or 'none'} "
              f"-> score {portfolio.score:.1f}")
    print(f"  report: {path}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="cfri-lite",
                                     description="Cyber-financial loss calculator for public water utilities.")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="simulate a utility profile and write a report")
    run.add_argument("profile", help="path to a utility profile JSON file")
    run.add_argument("--budget", type=float, default=None,
                     help="annual security budget (USD) for choosing controls")
    run.add_argument("--objective", choices=["es95", "total_cost"], default="es95")
    run.add_argument("--simulations", type=int, default=20_000)
    run.add_argument("--seed", type=int, default=42)
    run.add_argument("--out", default="reports")
    run.add_argument("--stem", default=None, help="file name prefix for outputs")
    run.set_defaults(func=_run)

    synth = sub.add_parser("synth", help="write the synthetic utility profiles")
    synth.add_argument("--out", default="data/synthetic")
    synth.set_defaults(func=lambda a: [print(f"wrote {p}") for p in write_all(a.out)])

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
