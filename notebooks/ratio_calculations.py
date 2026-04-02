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
    import time

    # Visualization tools
    import matplotlib.pyplot as plt
    import plotly.express as px
    import plotly.graph_objects as go

    # OS tools
    from pathlib import Path
    import sys

    # Anchor to this file's location
    repo_root = Path(__file__).resolve().parent.parent 

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
    # -----------------------------
    # Flatten tickers + category map
    # -----------------------------
    category_map = {
        ticker: category
        for category, tickers in stooq_tickers.items()
        for ticker in tickers
    }

    flat_tickers = list(category_map.keys())


    # -----------------------------
    # Download data
    # -----------------------------
    with StooqProcessor(repo_root / "data" / "d_us_txt.zip") as processor:

        # Stores valid tickers
        valid_tickers = [
            t for t in flat_tickers
            if processor.has_ticker(t)
        ]

        # Prints tickers that were not valid
        missing = sorted(set(flat_tickers) - set(valid_tickers))
        if missing:
            print("Skipping missing tickers:", missing)

        data = processor.download(
            valid_tickers,
            start=start_date,
            end=end_date,
        )


    # -----------------------------
    # Attach metadata
    # -----------------------------
    for ticker, frame in data.items():
        data[ticker] = frame.assign(
            Ticker=ticker,
            Category=category_map[ticker],
        )


    # -----------------------------
    # Combine dataset
    # -----------------------------
    combined_data = pd.concat(data.values()).reset_index()

    # data['AAPL'].tail()
    # data["BITW"]
    # combined_data[combined_data['Ticker'] == 'BITW']
    print(combined_data)
    # combined_data
    return combined_data, ticker


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Prepare Monthly Data & Calculate Monthly Returns
    """)
    return


@app.cell
def _(combined_data, display, pd, ticker):
    # Prepare monthly data & calculate static returns
    combined_data['Date'] = pd.to_datetime(combined_data['Date'])

    # Resample monthly frequency, taking last closing price of each month
    monthly_data = (
        combined_data.set_index('Date')
        .groupby(['Ticker', 'Category'])
        .resample('MS')['Close']
        .last()
        .reset_index()
    )

    # Calculate total returns and inflation-adjusted returns for each asset
    results = []
    for _ticker in monthly_data['Ticker'].unique():
        ticker_df = monthly_data[monthly_data['Ticker'] == ticker].sort_values('Date')

        # No data in ticker condition
        if ticker_df.empty:
            continue

        # Start and end price for total return calculation
        start_price = ticker_df.iloc[0]['Close']
        end_price = ticker_df.iloc[-1]['Close']

        # Calculate total return and adjust for inflation
        asset_return_pct = ((end_price - start_price) / start_price) * 100

        # Append results
        results.append({
            'Category': ticker_df.iloc[0]['Category'],
            'Ticker': ticker,
            'Total_Return_%': asset_return_pct
        })

    # Format and display the table
    returns_df = pd.DataFrame(results).sort_values(by='Inflation_Adjusted_Return_%', ascending=False)
    formatted_df = returns_df.copy()
    formatted_df['Total_Return_%'] = formatted_df['Total_Return_%'].round(2).astype(str) + '%'

    display(formatted_df)
    formatted_df.to_csv('../data/monthly_returns.csv', index=False)
    return


if __name__ == "__main__":
    app.run()
