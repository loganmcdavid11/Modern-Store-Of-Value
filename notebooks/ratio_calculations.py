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

    # Custom Stooq data importer: Anchor to this file's location
    # __file__ is notebooks/taylor_marimo.py
    repo_root = Path(__file__).resolve().parent.parent 

    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from scripts.stooq_processor import StooqProcessor

    return StooqProcessor, go, pd, px, repo_root


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
    # data["AAPL"].tail()
    return


@app.cell
def _(cpi_data, end_date, go, monthly_data, px, start_date):
    """
    Function: calc_cumulative_return
    Purpose: Calculate cumulative returns over time for each asset, starting from the first month in the dataset.
    """
    def calc_cumulative_return(group):
        group = group.sort_values('Date')
        start_price = group['Close'].iloc[0]
        group['Cumulative_Return_%'] = ((group['Close'] - start_price) / start_price) * 100
        return group

    # Cumulate returns for each asset
    cumulative_data = monthly_data.groupby('Ticker', group_keys=False).apply(calc_cumulative_return)

    # Plot
    fig = px.line(
        cumulative_data,
        x='Date',
        y='Cumulative_Return_%',
        color='Ticker',
        hover_data=['Category'],
        title=f'Asset Cumulative Returns vs. US Inflation ({start_date} to {end_date})',
        labels={'Cumulative_Return_%': 'Cumulative Return (%)', 'Date': 'Date'}
    )

    fig.update_traces(visible='legendonly')

    inflation_trace = go.Scatter(
        x=cpi_data.index,
        y=cpi_data['Cumulative_Inflation_%'],
        name='Cumulative US Inflation (Baseline)',
        fill='tozeroy',  
        mode='lines',
        line=dict(color='rgba(64, 64, 64, 0.9)', width=4, dash='dot'), 
        fillcolor='rgba(128, 128, 128, 0.25)', 
        hoverinfo='x+y+name'
    )
    fig.add_trace(inflation_trace)

    fig.data = (fig.data[-1],) + fig.data[:-1]

    fig.update_layout(
        height=800,
        width=1400,
        template="plotly_white",
        hovermode="closest",
        legend=dict(
            title="<b>Assets</b><br>(Double-click to isolate)",
            itemsizing="constant"
        )
    )

    fig.show()
    fig.write_html("../plots/inflation_adjusted_returns.html")
    return


if __name__ == "__main__":
    app.run()
