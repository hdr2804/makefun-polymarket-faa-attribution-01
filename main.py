#!/usr/bin/env python3
"""Forecast Polymarket prices minute by minute, 4 hours ahead.

Reads every case file in $MAKEFUN_INPUT_DIR (else /input/) and writes one
forecast file per case to $MAKEFUN_OUTPUT_DIR (else /output/).

Method, per market: the empirical distribution of H-minute price changes
taken from the market's own last HISTORY_MINUTES minutes, evaluated on a
grid of horizons H; the change quantiles for horizon h are interpolated in
sqrt(h) between grid horizons (random-walk scaling below the smallest grid
horizon and above the largest). The empirical quantiles are then shrunk
toward a house-style normal spread centred on the checkpoint price with
per-sqrt-minute sigma BASE_SIGMA. The median of the empirical distribution
carries the market's recent drift; the shrink keeps the tails honest when
the recent window saw jumps that will not repeat every hour.

Python 3.13, standard library only, offline, deterministic.
"""

import json
import math
import os
import sys

HISTORY_MINUTES = 720
BASE_SIGMA = 0.0008
SHRINK = 0.85
# Swept offline on the practice instance (NVIDIA cut): the score is flat
# across SHRINK 0.8-0.9 and SIGMA 0.0006-0.001, best 0.309061 here vs the
# house baseline 0.363589; the 15% empirical weight is kept on purpose,
# it is what saves the jumpy early case (p00) where a pure normal fails.
GRID_H = (10, 30, 60, 120, 240)
TAUS = (0.05, 0.25, 0.5, 0.75, 0.95)
Z = (-1.6448536269514722, -0.6744897501960817, 0.0,
     0.6744897501960817, 1.6448536269514722)


def quantile(sorted_vals, tau):
    """Linear-interpolation quantile of a sorted non-empty list."""
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    pos = tau * (n - 1)
    lo = int(pos)
    if lo >= n - 1:
        return sorted_vals[-1]
    frac = pos - lo
    return sorted_vals[lo] * (1.0 - frac) + sorted_vals[lo + 1] * frac


def horizon_quantiles(prices, horizon):
    """Five quantiles of the `horizon`-minute change, from the trailing window.

    Changes p[t+h] - p[t] for t starting inside the last HISTORY_MINUTES
    minutes and ending at or before the checkpoint. Returns None when the
    market is too young to hold enough changes.
    """
    n = len(prices)
    t_hi = n - 1 - horizon
    t_lo = max(0, n - 1 - HISTORY_MINUTES)
    if t_hi < t_lo or t_hi - t_lo + 1 < 8:
        return None
    changes = sorted(prices[t + horizon] - prices[t]
                     for t in range(t_lo, t_hi + 1))
    return [quantile(changes, tau) for tau in TAUS]


def forecast_market(prices, horizon_minutes, taus=TAUS):
    """240 x 5 forecast rows for one market; prices end at the checkpoint."""
    x = prices[-1]
    grid = []
    for h in GRID_H:
        qs = horizon_quantiles(prices, h)
        if qs is not None:
            grid.append((h, qs))
    rows = []
    for h in range(1, horizon_minutes + 1):
        sq = math.sqrt(h)
        emp = []
        if not grid:
            emp = None
        elif len(grid) == 1:
            gh, gq = grid[0]
            scale = math.sqrt(h / gh)
            emp = [q * scale for q in gq]
        else:
            if h <= grid[0][0]:
                gh, gq = grid[0]
                scale = math.sqrt(h / gh)
                emp = [q * scale for q in gq]
            elif h >= grid[-1][0]:
                gh, gq = grid[-1]
                scale = math.sqrt(h / gh)
                emp = [q * scale for q in gq]
            else:
                for (h1, q1), (h2, q2) in zip(grid, grid[1:]):
                    if h1 <= h <= h2:
                        s1 = math.sqrt(h1)
                        s2 = math.sqrt(h2)
                        w = (sq - s1) / (s2 - s1)
                        emp = [a * (1.0 - w) + b * w for a, b in zip(q1, q2)]
                        break
        row = []
        for k, tau in enumerate(taus):
            house = Z[k] * BASE_SIGMA * sq
            if emp is None:
                change = house
            else:
                change = (1.0 - SHRINK) * emp[k] + SHRINK * house
            v = x + change
            if v < 0.0:
                v = 0.0
            elif v > 1.0:
                v = 1.0
            row.append(round(v, 6))
        # Rounding can only tie neighbours; enforce non-decreasing explicitly.
        for k in range(1, len(row)):
            if row[k] < row[k - 1]:
                row[k] = row[k - 1]
        rows.append(row)
    return rows


def forecast_case(case):
    horizon = int(case.get("horizon_minutes", 240))
    taus = tuple(case.get("quantiles", TAUS))
    forecasts = []
    for market in case["markets"]:
        rows = forecast_market(market["prices"], horizon, taus)
        forecasts.append({"id": market["id"], "q": rows})
    return {"forecasts": forecasts}


def main():
    input_dir = os.environ.get("MAKEFUN_INPUT_DIR") or "/input"
    output_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    os.makedirs(output_dir, exist_ok=True)
    names = sorted(fn for fn in os.listdir(input_dir) if fn.endswith(".in"))
    for name in names:
        case_id = name[:-3]
        with open(os.path.join(input_dir, name), "r", encoding="utf-8") as f:
            case = json.load(f)
        out = forecast_case(case)
        out_path = os.path.join(output_dir, case_id + ".out")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(out, f, separators=(",", ":"), sort_keys=True)
            f.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
