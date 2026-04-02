import marimo

__generated_with = "0.22.0"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Imports & Downloads
    """)
    return


@app.cell
def _():
    # Data manipulation tools
    import pandas as pd
    import datetime

    # Visualization tools
    import matplotlib.pyplot as plt
    import plotly.express as px
    import plotly.graph_objects as go

    # OS tools
    from pathlib import Path
    import sys

    # Custom Stooq data importer
    repo_root = Path.cwd().parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from scripts.stooq_processor import StooqProcessor

    return StooqProcessor, pd, repo_root


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Downloads
    """)
    return


@app.cell
def _():
    stooq_tickers = {
        "Crypto ETFs": [
            "BITW",  # Bitwise 10 Crypto Index
            "IBIT",  # iShares Bitcoin Trust (Replaces BTC-USD)
            "ETHA"   # iShares Ethereum Trust (Replaces ETH-USD)
        ], 

        "Individual Stocks": [
            "NVDA", "AAPL", "MSFT", "AMD", "AMZN", "TSLA", "WMT", "LOW", "HD", "JNJ"
        ],

        "Sector ETFs": [
            "XLU"    # Utilities Select Sector SPDR Fund
        ],

        "Broad Market ETFs": [
            "SPY",   # S&P 500
            "VTI",   # Total US Market (replaces Wilshire 5000)
        ],

        "Commodity ETFs (Metals)": [
            "GLD",   # Gold (Baseline)
            "SLV",   # Silver
            "PPLT",  # Platinum
            "PALL"   # Palladium
        ],

        "Commodity ETFs (Agriculture)": [
            "WEAT",  # Wheat
            "SOYB",  # Soybeans
            "DBA"    # Broad Agriculture
        ]
    }

    start_date = "2021-01-01"
    end_date = "2026-03-31"
    return end_date, start_date, stooq_tickers


@app.cell
def _(StooqProcessor, end_date, pd, repo_root, start_date, stooq_tickers):
    with StooqProcessor(repo_root / "data" / "d_us_txt.zip") as processor:
        category_map = processor.build_category_map(stooq_tickers)
        data = processor.download(
            stooq_tickers,
            start=start_date,
            end=end_date,
        )

    for ticker, frame in data.items():
        data[ticker] = frame.assign(Ticker=ticker, Category=category_map[ticker])

    combined_data = pd.concat(data.values()).reset_index()

    # combined_data.head()
    data["AAPL"].tail()
    return


if __name__ == "__main__":
    app.run()
