import marimo

__generated_with = "0.22.0"
app = marimo.App()


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 1. Environment Setup & Imports
    **Purpose:** Initialize the necessary data manipulation libraries and establish the file path to the project root.

    **Implementation:** Imports `pandas` and `numpy` for vectorized math, and configures the system path so the custom `StooqProcessor` can be imported reliably regardless of where the notebook is executed.
    """)
    return


@app.cell
def _():
    import pandas as pd
    import numpy as np
    from pathlib import Path
    import sys
    import marimo as mo

    # Detect environment to reliably find the project root
    if '__file__' in globals():
        current_dir = Path(__file__).resolve().parent
    else:
        current_dir = Path.cwd().resolve()

    repo_root = current_dir.parent 

    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from scripts.stooq_processor import StooqProcessor

    return StooqProcessor, mo, np, pd, repo_root


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 2. Pipeline Configuration
    **Purpose:** Define the time horizon and the specific universe of assets we are analyzing.
    **Implementation:** Sets the 2021-2026 window. Critically, it includes `3MUSY.B` (the 3-month Treasury yield) to act as our dynamic macroeconomic baseline, and `VTI` as our market correlation baseline.
    """)
    return


@app.cell
def _():
    start_date = "2021-01-01"
    end_date = "2026-03-31"

    stooq_tickers = {
        "Crypto ETFs": ["BITW", "IBIT", "ETHA"], 
        "Individual Stocks": ["NVDA", "AAPL", "MSFT", "AMD", "AMZN", "TSLA", "WMT", "LOW", "HD", "JNJ"],
        "Sector ETFs": ["XLU"],
        "Broad Market ETFs": ["SPY", "VTI"],
        "Commodity ETFs (Metals)": ["GLD", "SLV", "PPLT", "PALL"],
        "Commodity ETFs (Agriculture)": ["WEAT", "SOYB", "DBA"]
    }
    return end_date, start_date, stooq_tickers


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 3. Data Ingestion
    **Purpose:** Extract the historical data from the local Stooq database.
    **Implementation:** Flattens the dictionary to create a category map, checks for valid tickers in the ZIP file, and downloads the daily data into a dictionary of DataFrames.
    """)
    return


@app.cell
def _(StooqProcessor, end_date, repo_root, start_date, stooq_tickers):
    category_map = {
        ticker: category
        for category, tickers in stooq_tickers.items()
        for ticker in tickers
    }

    flat_tickers = list(category_map.keys())

    with StooqProcessor(repo_root / "data" / "d_us_txt.zip") as processor:
        valid_tickers = [t for t in flat_tickers if processor.has_ticker(t)]

        missing = sorted(set(flat_tickers) - set(valid_tickers))
        if missing:
            print("Skipping missing tickers:", missing)

        raw_data = processor.download(
            valid_tickers,
            start=start_date,
            end=end_date,
        )
    return category_map, raw_data


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 4. Data Formatting & Combination
    **Purpose:** Merge the disparate ticker DataFrames into a single, unified matrix.

    **Implementation:** Loops through the downloaded dictionary, attaches the `Ticker` and `Category` metadata to each row, and concatenates them into `combined_data`. Finally, it converts the Date column to a proper datetime format.
    """)
    return


@app.cell
def _(category_map, pd, raw_data):
    for ticker, frame in raw_data.items():
        raw_data[ticker] = frame.assign(
            Ticker=ticker,
            Category=category_map[ticker],
        )

    combined_data = pd.concat(raw_data.values()).reset_index()
    combined_data['Date'] = pd.to_datetime(combined_data['Date'])
    return (combined_data,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 5. Resampling & Dynamic Baseline Generation
    **Purpose:** Convert daily noise into standardized monthly periods and calculate the specific macroeconomic hurdles for each month.

    **Implementation:** 1. Resamples all equities to the last closing price of the month.
    2. Calculates the month-over-month percentage return using `pct_change()`.
    3. Isolates the Treasury yield (`3MUSY.B`), converts the whole number into a monthly decimal, and maps that exact risk-free rate to every asset's row for that specific month.
    """)
    return


@app.cell
def _(combined_data):
    # 1. Resample to Monthly
    monthly_data = (
        combined_data.set_index('Date')
        .groupby(['Ticker', 'Category'])
        .resample('MS')['Close']
        .last()
        .reset_index()
    )

    # 2. Vectorized Monthly Returns
    monthly_data = monthly_data.sort_values(['Ticker', 'Date'])
    monthly_data['Monthly_Return'] = monthly_data.groupby('Ticker')['Close'].pct_change()

    # 3. Dynamic Risk-Free Rate Processing
    tbill_data = monthly_data[monthly_data['Ticker'] == '3MUSY.B'].copy()

    # Convert Stooq's yield (e.g., 5.0) to a monthly decimal (0.00416)
    tbill_data['Monthly_RF_Rate'] = (tbill_data['Close'] / 100) / 12
    rf_mapping = tbill_data.set_index('Date')['Monthly_RF_Rate']

    # Map the rate across the dataset and remove the T-Bill from the equity pool
    monthly_data['Monthly_RF_Rate'] = monthly_data['Date'].map(rf_mapping)
    monthly_data = monthly_data[monthly_data['Category'] != 'Treasury Yields']
    return (monthly_data,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 6. The Calculation Engine (Matrix Math)
    **Purpose:** Calculate the advanced risk-adjusted metrics across the entire dataset simultaneously.
    **Implementation:** Calculates excess returns and isolates downside volatility. It extracts VTI's returns, joins them to the master matrix, and uses a `groupby.apply()` function to compute the Annualized Return, Sharpe, Sortino, and Correlation ratios. The final output is sorted by Sortino Ratio to highlight the best safe-haven assets.
    """)
    return


@app.cell
def _(np, pd, repo_root):
    # 1. Calculate Excess and Downside Returns
    monthly_data['Excess_Return'] = monthly_data['Monthly_Return'] - monthly_data['Monthly_RF_Rate']
    monthly_data['Downside_Return'] = np.minimum(monthly_data['Excess_Return'], 0)

    # 2. Extract VTI Baseline for Correlation
    vti_returns = monthly_data[monthly_data['Ticker'] == 'VTI'].set_index('Date')['Monthly_Return'].rename('VTI_Return')
    monthly_data = monthly_data.join(vti_returns, on='Date')

    # Drop the first NaN month caused by pct_change
    clean_monthly_data = monthly_data.dropna(subset=['Monthly_Return']).copy()

    # 3. Vectorized Aggregation Function
    def calculate_metrics(group):
        avg_monthly_return = group['Monthly_Return'].mean()
        avg_excess_return = group['Excess_Return'].mean()

        std_excess = group['Excess_Return'].std()
        std_downside = group['Downside_Return'].std()

        # Prevent zero-division errors
        sharpe = (avg_excess_return / std_excess) * np.sqrt(12) if std_excess > 0 else np.nan
        sortino = (avg_excess_return / std_downside) * np.sqrt(12) if std_downside > 0 else np.nan

        vti_corr = group['Monthly_Return'].corr(group['VTI_Return'])

        return pd.Series({
            'Annualized_Return_%': (avg_monthly_return * 12) * 100,
            'Sharpe_Ratio': sharpe,
            'Sortino_Ratio': sortino,
            'VTI_Correlation': vti_corr
        })

    # 4. Apply Math and Sort
    results_df = clean_monthly_data.groupby(['Ticker', 'Category']).apply(calculate_metrics).reset_index()
    results_df = results_df.sort_values(by='Sortino_Ratio', ascending=False).round(3)

    # 5. Export
    print(results_df)
    results_df.to_csv(repo_root / 'data' / 'risk_adjusted_metrics.csv', index=False)
    return (monthly_data,)


if __name__ == "__main__":
    app.run()
