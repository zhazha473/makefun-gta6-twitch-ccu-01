"""Forecast GTA VI's launch-day Twitch viewers hour by hour (program/v1).

Model: scale-aware launch-curve regression on the case's own comparables.

Every comparable is a past big launch with a full release-day hourly curve.
For each comparable we take the log-ratio of each hour's viewers to its
hour-1 print, log(v_h / v_1), and regress that ratio on the launch's own
hour-1 size, log(v_1), separately for each hour h = 2..24.  Bigger launches
have flatter curves (their hour 1 already holds most of the world), so the
slope is near zero in the small hours and about -0.4 to -0.5 in the evening,
which the regression learns from the comparables at run time instead of
hard-coding it.  The median forecast is the regression prediction at this
case's hour-1 print; the outer quantiles come from the in-sample residuals
at each hour, so the spread is the honest spread of past launches around the
same regression.  Predictions are clamped to the range of log-ratios the
comparables actually showed at that hour, so an hour-1 print far outside the
comparables' range cannot extrapolate the curve to absurdity.

Comparables are kept only when they are usable as a rolling-midnight launch
analogue: a complete 24-hour release day, every hour positive, hour 1 at
least 5% of the day's peak (a simultaneous global launch whose whole surge
sits outside hour 1 has a near-zero hour 1 and a meaningless ratio curve),
and not flagged early-access-contaminated or weak-tier in its unlock note.
With fewer than three usable comparables the entry falls back to the house
persistence baseline (every hour at the hour-1 print, spread widening like
a random walk).

Standard library only, no network, deterministic: comparables are processed
in name order and every sum is over a fixed order, so two runs on the same
case write byte-identical output.
"""

import json
import math
import os
from datetime import datetime
from pathlib import Path

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0, 0.674, 1.645]
BASELINE_SIGMA = 0.15
MIN_HOUR1_FRACTION = 0.05
MIN_COMPARABLES = 3
RIDGE = 1.0


def parse_time(text):
    """An ISO 8601 UTC timestamp from the case files."""
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def percentile(sorted_values, p):
    """Linear-interpolation percentile of an already sorted list."""
    n = len(sorted_values)
    if n == 1:
        return sorted_values[0]
    k = p * (n - 1)
    lo = int(math.floor(k))
    hi = int(math.ceil(k))
    if lo == hi:
        return sorted_values[lo]
    return sorted_values[lo] * (hi - k) + sorted_values[hi] * (k - lo)


def release_day_hours(comparable):
    """Hour 1..24 viewers of a comparable's release day, or None if incomplete."""
    day_start = parse_time(comparable["day_start"])
    hours = {}
    for point in comparable.get("hourly") or []:
        try:
            when = parse_time(point["from"])
            viewers = point["viewers"]
        except (KeyError, TypeError, ValueError):
            continue
        offset = (when - day_start).total_seconds() / 3600.0
        if offset == int(offset) and 0 <= offset < 24:
            hours.setdefault(int(offset) + 1, viewers)
    if len(hours) != 24:
        return None
    if any(not isinstance(v, (int, float)) or v <= 0 for v in hours.values()):
        return None
    return hours


def usable_curve(comparable):
    """A comparable's log-ratio curve, or None when it is not a usable analogue."""
    unlock = (comparable.get("unlock") or "").lower()
    if "early-access-contaminated" in unlock or "tier: weak" in unlock:
        return None
    hours = release_day_hours(comparable)
    if hours is None:
        return None
    first = hours[1]
    if first / max(hours.values()) < MIN_HOUR1_FRACTION:
        return None
    return (math.log(first), [math.log(hours[h] / first) for h in range(2, 25)])


def round2(x):
    """Round to 2 decimals, half up (the house baseline's rounding)."""
    scaled = x * 100.0
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100.0
    return int(value) if value == int(value) else value


def baseline_quantiles(p1, h):
    """House persistence baseline: every hour at the hour-1 print."""
    return [round2(p1 * math.exp(z * BASELINE_SIGMA * math.sqrt(h - 1))) for z in Z]


def regression_forecast(p1, curves, forecast_rows):
    """Per-hour median + residual quantiles from the scale regression.

    forecast_rows are the case's own hours to forecast (2..24 in this
    competition); the regression is fit per hour, so each row is predicted
    from the comparables' log-ratio at that same hour.
    """
    log_p1 = math.log(p1)
    xs = [c[0] for c in curves]
    mean_x = sum(xs) / len(xs)
    hours = []
    for row in forecast_rows:
        h = row["hour"]
        j = h - 2
        ys = [c[1][j] for c in curves]
        mean_y = sum(ys) / len(ys)
        sxx = sum((x - mean_x) ** 2 for x in xs) + RIDGE
        sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
        slope = sxy / sxx
        intercept = mean_y - slope * mean_x
        median = intercept + slope * log_p1
        residuals = sorted(y - (intercept + slope * x) for x, y in zip(xs, ys))
        low, high = min(ys), max(ys)
        row = []
        for tau in LEVELS:
            if tau == 0.5:
                value = median
            else:
                value = median + percentile(residuals, tau)
            value = min(high, max(low, value))
            row.append(p1 * math.exp(value))
        row = [max(1.0, min(1e9, q)) for q in row]
        for k in range(1, 5):
            row[k] = max(row[k], row[k - 1])
        hours.append({"hour": h, "q": [round2(q) for q in row]})
    return {"hours": hours}


def forecast_case(case):
    first = next((k for k in case.get("known", []) if k.get("hour") == 1), None)
    if first is None:
        raise ValueError("case has no hour-1 print")
    p1 = max(1.0, float(first["viewers"]))
    curves = []
    for comparable in sorted(case.get("comparables") or [], key=lambda c: c.get("name", "")):
        curve = usable_curve(comparable)
        if curve is not None:
            curves.append(curve)
    if len(curves) < MIN_COMPARABLES:
        return {"hours": [{"hour": row["hour"], "q": baseline_quantiles(p1, row["hour"])}
                          for row in case["forecast"]]}
    return regression_forecast(p1, curves, case["forecast"])


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case)
        (OUTPUT_DIR / (path.stem + ".out")).write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
