# Polymarket FAA attribution forecast — make.fun entry

Forecasts the Yes price of every market of Polymarket's FAA outage
attribution family at every minute of the 4 hours after each checkpoint,
as five quantiles (5%, 25%, 50%, 75%, 95%) per minute.

Entry for the make.fun competition `polymarket-faa-attribution-01`
($250 USDC escrowed, 100 places). Python 3.13, standard library only,
offline, deterministic.

## Method

Per market, from the market's own price history:

1. **Empirical change distribution.** For each horizon H in
   {10, 30, 60, 120, 240} minutes, take the distribution of H-minute
   price changes whose start lies in the last 720 minutes before the
   checkpoint, and read off its 5/25/50/75/95% quantiles.
2. **sqrt(h) interpolation.** The change quantiles for horizon h are
   interpolated linearly in sqrt(h) between grid horizons (random-walk
   scaling outside the grid). The median carries the market's recent
   drift.
3. **Shrink to a house-style normal.** The empirical quantiles are
   shrunk 85% of the way toward a normal spread centred on the
   checkpoint price with sigma 0.0008 per sqrt-minute. One-minute
   volatility is mostly bid/ask bounce and would overstate 4-hour
   travel about threefold if used raw; the shrink keeps the tails
   honest while the 15% empirical weight still covers real jumps.

Constants were swept offline on the practice instance
(`HISTORY_MINUTES` 720, `BASE_SIGMA` 0.0008, `SHRINK` 0.85).

## Practice score (local, vs collected Polymarket actuals)

| | pinball loss |
|---|---|
| This entry | **0.309061** |
| House baseline | 0.363589 |

Beats the house baseline on every practice case (p00–p05). The local
scorer reproduces the official baseline figure exactly (0.363589).

## Run

```sh
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Reads every `*.in` case in the input dir, writes one `<id>.out` per
case. About 0.1 s per case; two runs are byte-identical.

## Files

- `main.py` — the forecaster (the entrypoint)
- `LICENSE` — MIT
