# Sector Rotation Tracker (RRG)

A live **Relative Rotation Graph (RRG)** dashboard for the 11 S&P 500 sector ETFs vs the S&P 500 (SPY) — in the style of the classic Julius de Kempenaer / StockCharts / Interactive Brokers sector-rotation chart, plus a plain-English **"money map"** and per-sector buy/watch/avoid signals.

It answers one question at a glance: **where is the money moving?**

## What it shows

- **Money map** — a diverging bar chart of each sector's relative performance vs SPY (1-week / 1-month / 3-month), with a plain-English rotation headline. Green = money arriving (outperforming), red = money leaving.
- **Relative Rotation Graph** — the 11 SPDR sector ETFs plotted on RS-Ratio (relative strength) × RS-Momentum, with the four quadrants (Leading / Weakening / Lagging / Improving) and smooth historical "tails". Weekly/daily toggle, adjustable tail length, date scrubber, and play-through animation.
- **Live signals** — each sector tagged **Buy / Accumulate / Watch / Trim / Avoid**, derived from its quadrant, momentum direction, and money flow. Recomputed on every data refresh.
- **Remarks & advice** — an optional research-driven note on today's read and the week ahead (catalysts, good buys, risks). Populated from `commentary.json`.

## The math (and why the tails are smooth)

For each sector the relative-strength line is `RS = 100 × sector / SPY`. From it:

- **RS-Ratio** = `100 + z-score(RS)` over a rolling window, lightly EMA-smoothed.
- **RS-Momentum** = `100 + z-score(rate-of-change of RS-Ratio)` over a multi-bar lookback, EMA-smoothed.

The key detail: momentum is the **smoothed rate-of-change over several bars**, not a 1-bar difference. A 1-bar diff is mostly noise and produces jagged tails; the multi-bar, smoothed construction reproduces the clean curved tails of a proper RRG.

A sector is **Leading** (RS-Ratio ≥ 100, RS-Momentum ≥ 100), **Weakening** (≥100, <100), **Lagging** (<100, <100), or **Improving** (<100, ≥100). The classic clockwise rotation runs Improving → Leading → Weakening → Lagging.

## Quick start

```bash
pip install -r requirements.txt
```

**Live (auto-updating in the browser):**

```bash
python serve_rrg.py            # serves http://localhost:8787 and opens it
```

The page polls the server every 60s and hot-updates; the server re-pulls market data from Yahoo Finance at most once every 90s (intraday-aware). On Windows you can just double-click `live.cmd`.

**Static snapshot (no server):**

```bash
python generate_rrg.py         # writes rrg_data.json + rrg_live.html
```

Then open `rrg_live.html` in any browser.

## Files

| File | Purpose |
|---|---|
| `generate_rrg.py` | Data engine — downloads prices, computes RS-Ratio/RS-Momentum + flow metrics, writes the static snapshot |
| `serve_rrg.py` | Local live server with auto-refresh + browser hot-reload |
| `rrg_template.html` | The dashboard (UI + all client-side logic) |
| `live.cmd` | Windows one-click launcher for the live server |
| `commentary.json` | Optional research-driven "remarks & advice" note (today + next week) |

## Data

Sector ETFs: XLY, XLC, XLK, XLF, XLV, XLI, XLP, XLE, XLU, XLB, XLRE. Benchmark: SPY. Source: [Yahoo Finance](https://finance.yahoo.com) via [`yfinance`](https://github.com/ranaroussi/yfinance) (split/dividend-adjusted).

## Disclaimer

This is a data-driven, educational analytics tool, **not personalized financial advice**. Relative-strength signals are lagging and can reverse quickly — a single macro event (e.g. an FOMC decision) can invalidate a technical setup overnight. Do your own research; nothing here is a recommendation to buy or sell any security.

## License

MIT — see [LICENSE](LICENSE).
