# Sector Rotation (RRG) data engine
# Downloads real market data via yfinance and computes JdK-style
# RS-Ratio / RS-Momentum for the 11 SPDR sector ETFs vs SPY, plus
# "money flow" metrics (excess return vs benchmark, volume surge).
#
# build_payload()  -> dict ready to serialize (used by serve_rrg.py too)
# main()           -> fetch, compute, write rrg_data.json + rrg_live.html
#
# Why the tails are smooth (unlike a naive 1-bar diff):
#   * RS line is lightly smoothed (EMA) before normalizing.
#   * RS-Momentum is the normalized RATE-OF-CHANGE of RS-Ratio over a
#     multi-bar lookback (not a 1-bar difference), then smoothed again.
#   This mirrors the de Kempenaer / StockCharts construction.

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

SECTORS = {
    "XLY": "Consumer Discretionary",
    "XLC": "Communication Services",
    "XLK": "Information Technology",
    "XLF": "Financials",
    "XLV": "Health Care",
    "XLI": "Industrials",
    "XLP": "Consumer Staples",
    "XLE": "Energy",
    "XLU": "Utilities",
    "XLB": "Materials",
    "XLRE": "Real Estate",
}
BENCH = "SPY"

# Visual scale: z-scores are multiplied by SCALE so the band spans the
# familiar ~95-105 RRG range instead of a cramped ~98-102.
SCALE = 1.6

HERE = Path(__file__).resolve().parent


def _zscore(s: pd.Series, w: int) -> pd.Series:
    mean = s.rolling(w).mean()
    std = s.rolling(w).std()
    return (s - mean) / std.replace(0, np.nan)


def rrg_series(prices: pd.DataFrame, *, z_win: int, mom_lb: int,
               smooth: int, keep: int):
    """JdK-style RS-Ratio / RS-Momentum, smoothed for clean tails.

    z_win  : window for the cross-time z-score normalization
    mom_lb : lookback (bars) for the rate-of-change that defines momentum
    smooth : EMA span applied to both axes to kill 1-bar noise
    keep   : number of trailing points (tail) to emit
    """
    out = {}
    dates = []
    for t in SECTORS:
        rs = 100.0 * prices[t] / prices[BENCH]
        rs = rs.ewm(span=smooth, adjust=False).mean()

        # RS-Ratio: normalized, centered at 100
        ratio = 100.0 + SCALE * _zscore(rs, z_win)
        ratio = ratio.ewm(span=smooth, adjust=False).mean()

        # RS-Momentum: normalized rate-of-change of RS-Ratio over mom_lb bars
        roc = ratio / ratio.shift(mom_lb) * 100.0 - 100.0
        mom = 100.0 + SCALE * _zscore(roc, z_win)
        mom = mom.ewm(span=smooth, adjust=False).mean()

        df = pd.DataFrame({"ratio": ratio, "mom": mom}).dropna().tail(keep)
        out[t] = {
            "ratio": [round(float(v), 2) for v in df["ratio"]],
            "mom": [round(float(v), 2) for v in df["mom"]],
        }
        dates = [d.strftime("%Y-%m-%d") for d in df.index]
    return out, dates


def _ret(px: pd.Series, n: int) -> float:
    if len(px) <= n:
        return float("nan")
    return px.iloc[-1] / px.iloc[-1 - n] - 1.0


def _pct(px: pd.Series, n: int) -> float:
    r = _ret(px, n)
    return round(r * 100, 2) if r == r else float("nan")


def fetch_prices():
    tickers = list(SECTORS) + [BENCH]
    raw = yf.download(tickers, period="3y", interval="1d",
                      auto_adjust=True, progress=False)
    close = raw["Close"][tickers].ffill().dropna()
    vol = raw["Volume"][tickers].ffill().dropna()
    return close, vol


def build_payload(close=None, vol=None) -> dict:
    if close is None or vol is None:
        close, vol = fetch_prices()

    weekly = close.resample("W-FRI").last().dropna()

    # Weekly: 12-week z window, 5-week momentum lookback, light smoothing.
    w_series, w_dates = rrg_series(weekly, z_win=12, mom_lb=5,
                                   smooth=3, keep=26)
    # Daily: 21-day z window, 10-day momentum lookback.
    d_series, d_dates = rrg_series(close, z_win=21, mom_lb=10,
                                   smooth=5, keep=40)

    ytd_start = close[close.index.year < close.index[-1].year]
    spy = close[BENCH]
    # benchmark excess return helpers (sector minus SPY over the window)
    ex = lambda px, n: round((_ret(px, n) - _ret(spy, n)) * 100, 2) \
        if _ret(px, n) == _ret(px, n) else float("nan")

    stats = {}
    for t in list(SECTORS) + [BENCH]:
        px = close[t]
        dv = (close[t] * vol[t])
        ytd = round((px.iloc[-1] / ytd_start[t].iloc[-1] - 1) * 100, 2) \
            if len(ytd_start) else float("nan")
        surge = float(dv.tail(5).mean() / dv.tail(60).mean()) \
            if dv.tail(60).mean() else float("nan")
        stats[t] = {
            "name": SECTORS.get(t, "S&P 500 Benchmark"),
            "price": round(float(px.iloc[-1]), 2),
            "d1": _pct(px, 1),
            "w1": _pct(px, 5),
            "m1": _pct(px, 21),
            "m3": _pct(px, 63),
            "ytd": ytd,
            # money-flow signals: excess return vs SPY (where money is going)
            "ex1w": 0.0 if t == BENCH else ex(px, 5),
            "ex1m": 0.0 if t == BENCH else ex(px, 21),
            "ex3m": 0.0 if t == BENCH else ex(px, 63),
            "surge": round(surge, 2) if surge == surge else None,
            "vol": int(vol[t].tail(20).mean()),
        }

    payload = {
        "asof": close.index[-1].strftime("%Y-%m-%d"),
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "benchmark": BENCH,
        "weekly": {"dates": w_dates, "series": w_series, "window": 12},
        "daily": {"dates": d_dates, "series": d_series, "window": 21},
        "stats": stats,
    }

    # Optional research-driven "Remarks & advice" note (today + next week).
    # Produced separately and refreshed periodically; the live signals in the
    # dashboard are always computed from data regardless of this file.
    note = HERE / "commentary.json"
    if note.exists():
        try:
            payload["commentary"] = json.loads(note.read_text(encoding="utf-8"))
        except Exception:
            pass

    return payload


def write_outputs(payload: dict):
    out = HERE / "rrg_data.json"
    out.write_text(json.dumps(payload), encoding="utf-8")

    template = HERE / "rrg_template.html"
    if template.exists():
        html = (template.read_text(encoding="utf-8")
                .replace("__DATA__", json.dumps(payload))
                .replace("__LIVE__", "false"))
        (HERE / "rrg_live.html").write_text(html, encoding="utf-8")
    return out


def main():
    payload = build_payload()
    out = write_outputs(payload)
    print(f"wrote {out} | as of {payload['asof']} | "
          f"weekly pts {len(payload['weekly']['dates'])} | "
          f"daily pts {len(payload['daily']['dates'])}")


if __name__ == "__main__":
    sys.exit(main())
