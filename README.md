# Portfolio Time Machine

**[Try the live app →](https://portfolio-time-machine.streamlit.app/)**

A backtesting tool for Japanese equity portfolios. Pick a starting date, choose your holdings, and see what the position would be worth today — including the drawdowns you would have had to sit through.

Built with Streamlit and Plotly. Price data comes from Yahoo Finance via `yfinance`.

---

## What it does

Most backtesting tools assume a single lump-sum purchase. Real investors rarely behave that way, so the app supports three strategies:

| Mode | Behaviour |
|---|---|
| **Lump sum** | Invest the full amount on the start date and hold. |
| **DCA** | Invest a fixed amount at regular intervals across the period. |
| **Hybrid** | An initial lump sum, followed by regular top-ups. |

The hybrid mode reflects how Japan's NISA scheme is commonly used in practice: a larger initial allocation through the growth investment quota, combined with ongoing monthly contributions through the accumulation quota. Backtesting only the lump-sum case tends to overstate the impact of entry timing for anyone actually investing this way.

## Automatic stock split adjustment

Japanese listings have gone through frequent splits, and unadjusted historical prices produce misleading results — a 1-for-5 split looks like an 80% crash if you don't correct for it.

The app detects splits automatically and adjusts historical prices accordingly. Known cases are also maintained in a registry, since automatic detection alone is not always reliable. Whenever an adjustment is applied, the app says so on screen and indicates whether it came from automatic detection or the registry. Adjustments affect displayed prices only — total portfolio value is unchanged.

## Running it locally

```bash
git clone https://github.com/shishishishi/portfolio-time-machine.git
cd portfolio-time-machine
pip install -r requirements.txt
streamlit run app.py
```

Requires Python 3.12. No API key or configuration is needed.

## Project structure

```
app.py                  Streamlit UI and chart rendering
core/calc.py            Simulation logic for all three modes
core/data.py            Price retrieval, caching, split adjustment
data/master.csv         Ticker master (generated from JPX listing data)
scripts/build_master.py Rebuilds the ticker master
```

## Notes and limitations

- The selectable range starts from 2001, which is roughly where `yfinance` coverage for Japanese equities becomes usable.
- Dividends are not reinvested.
- Transaction costs and taxes are not modelled.
- Delisted companies cannot be retrieved and are flagged rather than silently skipped.

## Disclaimer

This is a simulation tool built for education and personal research. It is not investment advice. Price data is sourced from Yahoo Finance and is provided without any guarantee of accuracy. Past performance tells you nothing certain about future returns.

## Licence

MIT
