"""Build the Excel version of cfri-lite from a utility profile JSON.

Usage:
    python scripts/build_excel.py data/synthetic/mid_size.json excel/cfri_lite_calculator.xlsx

The workbook is self-contained: users edit the yellow cells on the Inputs and Controls
sheets and press F9 to re-run the simulation. Results update on the Results sheet.
"""
from __future__ import annotations

import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter as col
from openpyxl.worksheet.datavalidation import DataValidation

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from cfri_lite.index import TIERS  # noqa: E402
from cfri_lite.model import load_profile  # noqa: E402

ROWS = 5000  # simulated years in the workbook (the Python model defaults to 20,000)
INPUT = PatternFill("solid", fgColor="FFF2CC")
HEAD = PatternFill("solid", fgColor="D9E2F3")
BOLD = Font(bold=True)
THIN = Border(*(Side(style="thin", color="BFBFBF"),) * 4)
USD = '"$"#,##0'


def head(ws, row, values, widths=None):
    for j, v in enumerate(values, start=1):
        c = ws.cell(row=row, column=j, value=v)
        c.font, c.fill, c.border = BOLD, HEAD, THIN
        c.alignment = Alignment(wrap_text=True, vertical="center")
    if widths:
        for j, w in enumerate(widths, start=1):
            ws.column_dimensions[col(j)].width = w


def build(profile_path: str, out_path: str) -> None:
    p = load_profile(profile_path)
    S, C = len(p.scenarios), len(p.controls)
    wb = Workbook()

    # ---------------- About ----------------
    ab = wb.active
    ab.title = "About"
    about = [
        ("cfri-lite calculator (Excel edition)", True),
        ("A cyber-financial loss calculator for public water utilities.", False),
        ("", False),
        ("How to use", True),
        ("1. Enter reserves, undrawn liquidity and scenario assumptions in the yellow cells on 'Inputs'.", False),
        ("2. Mark controls Yes/No on 'Controls' to see their effect.", False),
        ("3. Press F9 to re-run the simulation. Read the score on 'Results'.", False),
        (f"The workbook simulates {ROWS:,} years; results move slightly on each recalculation.", False),
        ("", False),
        ("Important", True),
        ("The pre-filled values are SYNTHETIC illustrative assumptions, not data from any real utility.", False),
        ("This is a planning model, not a forecast. See docs/methodology.md in the repository.", False),
        ("Score = 100 x (1 - 5^(-ES95 / loss capacity)). A worst-case loss equal to capacity scores 80.", False),
        (f"Profile loaded: {p.name}", False),
    ]
    for i, (text, bold) in enumerate(about, start=1):
        ab.cell(row=i, column=1, value=text).font = Font(bold=bold, size=14 if i == 1 else 11)
    ab.column_dimensions["A"].width = 110

    # ---------------- Inputs ----------------
    ws = wb.create_sheet("Inputs")
    ws["A1"], ws["A1"].font = "Utility", BOLD
    ws["B1"] = p.name
    rows = [("Reserves (USD)", p.reserves), ("Undrawn liquidity (USD)", p.undrawn_liquidity)]
    for i, (label, val) in enumerate(rows, start=2):
        ws.cell(row=i, column=1, value=label)
        c = ws.cell(row=i, column=2, value=val)
        c.fill, c.number_format = INPUT, USD
    ws["A4"] = "Loss capacity (USD)"
    ws["B4"] = "=B2+B3"
    ws["B4"].number_format, ws["A4"].font = USD, BOLD

    top = 6
    head(ws, top, ["ID", "Scenario", "Annual probability", "Loss low", "Loss most likely",
                   "Loss high", "Probability after controls", "Severity multiplier after controls"],
         [8, 52, 14, 14, 14, 14, 16, 18])
    for k, s in enumerate(p.scenarios):
        r = top + 1 + k
        ws.cell(row=r, column=1, value=s.id)
        ws.cell(row=r, column=2, value=s.name)
        for j, (val, fmt) in enumerate([(s.annual_probability, "0.0%"), (s.loss_low, USD),
                                        (s.loss_mode, USD), (s.loss_high, USD)], start=3):
            c = ws.cell(row=r, column=j, value=val)
            c.fill, c.number_format = INPUT, fmt
        # effects of controls: Controls sheet rows 2..C+1; prob cols E.., severity cols after
        pcol, scol = col(5 + k), col(5 + S + k)
        p_terms = "".join(f'*(1-IF(Controls!$D${2 + i}="Yes",Controls!{pcol}${2 + i},0))' for i in range(C))
        s_terms = "*".join(f'(1-IF(Controls!$D${2 + i}="Yes",Controls!{scol}${2 + i},0))' for i in range(C)) or "1"
        ws.cell(row=r, column=7, value=f"=C{r}{p_terms}").number_format = "0.00%"
        ws.cell(row=r, column=8, value=f"={s_terms}").number_format = "0.000"
    ws.freeze_panes = "A7"

    # ---------------- Controls ----------------
    cs = wb.create_sheet("Controls")
    head(cs, 1, ["ID", "Control", "Annual cost", "Include? (Yes/No)"]
         + [f"Prob. reduction {s.id}" for s in p.scenarios]
         + [f"Severity reduction {s.id}" for s in p.scenarios],
         [6, 46, 13, 11] + [11] * (2 * S))
    dv = DataValidation(type="list", formula1='"Yes,No"', allow_blank=False)
    cs.add_data_validation(dv)
    for i, c in enumerate(p.controls, start=2):
        cs.cell(row=i, column=1, value=c.id)
        cs.cell(row=i, column=2, value=c.name)
        x = cs.cell(row=i, column=3, value=c.annual_cost)
        x.fill, x.number_format = INPUT, USD
        y = cs.cell(row=i, column=4, value="No")
        y.fill = INPUT
        dv.add(y)
        for k, s in enumerate(p.scenarios):
            for off, eff in ((5, c.probability_reduction), (5 + S, c.severity_reduction)):
                z = cs.cell(row=i, column=off + k, value=eff.get(s.id, 0.0))
                z.fill, z.number_format = INPUT, "0%"
    tot = C + 3
    cs.cell(row=tot, column=2, value="Annual cost of selected controls").font = BOLD
    cs.cell(row=tot, column=3, value=f'=SUMIF(D2:D{C + 1},"Yes",C2:C{C + 1})').number_format = USD

    # ---------------- Simulation ----------------
    # Columns: A year | B.. loss per scenario | total | severity draws (one uniform per scenario)
    sm = wb.create_sheet("Simulation")
    tcol = 2 + S                 # total loss column
    ucol0 = tcol + 1             # first severity-draw column
    head(sm, 1, ["Year"] + [f"Loss {s.id}" for s in p.scenarios] + ["Total loss"]
         + [f"Severity draw {s.id}" for s in p.scenarios],
         [8] + [13] * S + [15] + [12] * S)
    for r in range(2, ROWS + 2):
        sm.cell(row=r, column=1, value=r - 1)
        for k in range(S):
            ir = top + 1 + k
            a, m, b = f"Inputs!$D${ir}", f"Inputs!$E${ir}", f"Inputs!$F${ir}"
            ucell = f"{col(ucol0 + k)}{r}"
            sm.cell(row=r, column=ucol0 + k, value="=RAND()").number_format = "0.000"
            # triangular inverse CDF on the stored draw, scaled by the severity multiplier
            tri = (f"IF({ucell}<({m}-{a})/({b}-{a}),{a}+SQRT({ucell}*({b}-{a})*({m}-{a})),"
                   f"{b}-SQRT((1-{ucell})*({b}-{a})*({b}-{m})))")
            f = f"=IF(RAND()<Inputs!$G${ir},({tri})*Inputs!$H${ir},0)"
            sm.cell(row=r, column=2 + k, value=f).number_format = USD
        sm.cell(row=r, column=tcol, value=f"=SUM(B{r}:{col(1 + S)}{r})").number_format = USD
    sm.freeze_panes = "B2"

    # ---------------- Results ----------------
    rs = wb.create_sheet("Results", 1)
    total = f"Simulation!${col(2 + S)}$2:${col(2 + S)}${ROWS + 1}"
    rs.column_dimensions["A"].width = 52
    rs.column_dimensions["B"].width = 20
    lines = [
        ("CFRI-lite results (press F9 to re-run)", None, None),
        ("Expected annual loss", f"=AVERAGE({total})", USD),
        ("95% value-at-risk (VaR95)", f"=PERCENTILE({total},0.95)", USD),
        ("Worst-case loss: 95% expected shortfall (ES95)", f'=AVERAGEIF({total},">="&B3)', USD),
        ("Loss capacity (reserves + undrawn liquidity)", "=Inputs!B4", USD),
        ("Worst-case loss as share of capacity", "=B4/B5", "0%"),
        ("CFRI-lite score (0-100)", "=100*(1-5^(-B6))", "0.0"),
        ("Tier", None, None),
        ("Annual cost of selected controls", f"=Controls!C{tot}", USD),
    ]
    for i, (label, formula, fmt) in enumerate(lines, start=1):
        a = rs.cell(row=i, column=1, value=label)
        a.font = Font(bold=True, size=14 if i == 1 else 11)
        if formula:
            b = rs.cell(row=i, column=2, value=formula)
            b.number_format = fmt
            b.border = THIN
    tier_formula = "=" + "".join(f'IF(B7>={t},"{name}",' for t, name in reversed(TIERS[1:])) \
        + f'"{TIERS[0][1]}"' + ")" * (len(TIERS) - 1)
    rs["B8"] = tier_formula
    rs["B7"].font = rs["B8"].font = Font(bold=True, size=12)
    rs["A11"], rs["A11"].font = "Tier scale", BOLD
    bounds = [t[0] for t in TIERS] + [100]
    for i, ((lo, name), hi) in enumerate(zip(TIERS, bounds[1:]), start=12):
        rs.cell(row=i, column=1, value=name)
        rs.cell(row=i, column=2, value=f"{lo:.0f} - {hi:.0f}")
    rs["A18"] = "Synthetic illustrative inputs. Planning model, not a forecast."
    rs["A18"].font = Font(italic=True, color="808080")

    wb.calculation.fullCalcOnLoad = True
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: python scripts/build_excel.py PROFILE.json OUT.xlsx")
    build(sys.argv[1], sys.argv[2])
