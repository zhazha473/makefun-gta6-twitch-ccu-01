# GTA VI Twitch CCU Forecaster

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/zhazha473/makefun-gta6-twitch-ccu-01/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/zhazha473/makefun-gta6-twitch-ccu-01/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

Entry for the make.fun bounty
[gta6-twitch-ccu-forecast-01](https://make.fun/bounty/gta6-twitch-ccu-forecast-01):
forecast, hour by hour, how many people watch Grand Theft Auto VI live on
Twitch over its release day (19 November 2026, UTC), as five quantiles per
hour, from everything recorded up to the end of the day's first hour.

## How it works

`main.py` (Python 3.13, standard library only) reads the case file and fits,
at run time, one small regression per forecast hour on the case's own
comparables — past big game launches with full release-day hourly curves:

- Each comparable contributes the log-ratio of each hour's viewers to its
  hour-1 print, `log(v_h / v_1)`, regressed on its own hour-1 size,
  `log(v_1)`. Bigger launches have flatter curves, and the regression learns
  that slope from the comparables instead of hard-coding it.
- The median forecast is the regression prediction at this case's hour-1
  print; the outer quantiles come from the regression's in-sample residuals,
  so the spread is the honest spread of past launches around the same fit.
- Predictions are clamped to the range of log-ratios the comparables
  actually showed at that hour, so an hour-1 print far outside their range
  cannot extrapolate the curve to absurdity.
- Comparables are kept only when they are usable rolling-midnight analogues:
  a complete 24-hour release day, hour 1 at least 5% of the day's peak, and
  not flagged early-access-contaminated or weak-tier. With fewer than three
  usable comparables the entry falls back to the house persistence baseline.

## Practice score (local scorer, answers reconstructed from the public
SullyGnome source the kit cites)

- House baseline: pinball loss **0.387**
- This entry: pinball loss **0.180**, typical miss 30%, 90% coverage 0.85

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=<kit>/input MAKEFUN_OUTPUT_DIR=out python3 main.py
```
