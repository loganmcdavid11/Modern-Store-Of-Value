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
    ### 5. Ingest & Format Macroeconomic Baseline (T-Bills)
    **Purpose:** Load the offline risk-free rate data and prepare it for a date-agnostic merge.
    **Implementation:** Reads the CSV, converts the date into a unified `YearMonth` period, and transforms the annualized whole-number yield into a monthly decimal.
    """)
    return


@app.cell
def _(pd, repo_root):
    # Load the CSV
    tbill_path = repo_root / "data" / "tb3ms.csv"
    tbill_data = pd.read_csv(tbill_path)

    # Standardize column names
    tbill_data = tbill_data.rename(columns={'DATE': 'Date', 'TB3MS': 'Yield'})

    # Force numeric (FRED sometimes puts '.' for missing data)
    tbill_data['Yield'] = pd.to_numeric(tbill_data['Yield'], errors='coerce')
    
    # Forward-fill any missing months
    tbill_data['Yield'] = tbill_data['Yield'].ffill()

    # Convert yield to monthly decimal (e.g., 5.0 -> 0.00416)
    tbill_data['Monthly_RF_Rate'] = (tbill_data['Yield'] / 100) / 12

    # Create the unified YearMonth matching key
    tbill_data['Date'] = pd.to_datetime(tbill_data['Date'])
    tbill_data['YearMonth'] = tbill_data['Date'].dt.to_period('M')

    # Isolate just the columns we need for the merge
    clean_tbill = tbill_data[['YearMonth', 'Monthly_RF_Rate']]

    return clean_tbill,


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 6. The Calculation Engine (Matrix Math)
    **Purpose:** Calculate the advanced risk-adjusted metrics across the entire dataset simultaneously.
    **Implementation:** Sorts the pre-aggregated monthly data, merges the dynamic risk-free rate using the `YearMonth` key, calculates excess and downside returns, and applies the final matrix math to generate the metrics.
    """)
    return


@app.cell
def _(combined_data, clean_tbill, np, pd, repo_root):
    # 1. Prepare Stooq Data
    monthly_data = combined_data.copy()
    monthly_data['Date'] = pd.to_datetime(monthly_data['Date'])
    
    # Create the unified YearMonth matching key
    monthly_data['YearMonth'] = monthly_data['Date'].dt.to_period('M')

    # Sort chronologically for accurate pct_change
    monthly_data = monthly_data.sort_values(['Ticker', 'Date'])
    
    # Calculate month-over-month returns
    monthly_data['Monthly_Return'] = monthly_data.groupby('Ticker')['Close'].pct_change()

    # 2. Merge the Risk-Free Rate
    monthly_data = pd.merge(monthly_data, clean_tbill, on='YearMonth', how='left')

    # 3. Calculate Excess and Downside Returns
    monthly_data['Excess_Return'] = monthly_data['Monthly_Return'] - monthly_data['Monthly_RF_Rate']
    monthly_data['Downside_Return'] = np.minimum(monthly_data['Excess_Return'], 0)

    # 4. Extract VTI Baseline for Correlation
    vti_returns = monthly_data[monthly_data['Ticker'] == 'VTI'].set_index('YearMonth')['Monthly_Return'].rename('VTI_Return')
    monthly_data = monthly_data.join(vti_returns, on='YearMonth')

    # Drop the first NaN month caused by pct_change
    clean_monthly_data = monthly_data.dropna(subset=['Monthly_Return']).copy()

    # 5. Vectorized Aggregation Function
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

    # 6. Apply Math and Sort
    results_df = clean_monthly_data.groupby(['Ticker', 'Category']).apply(calculate_metrics).reset_index()
    results_df = results_df.sort_values(by='Sortino_Ratio', ascending=False).round(3)

    # 7. Export
    print(results_df)
    results_df.to_csv(repo_root / 'data' / 'risk_adjusted_metrics.csv', index=False)

    return clean_monthly_data, results_df


if __name__ == "__main__":
    app.run()
