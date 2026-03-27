import pandas as pd
from pathlib import Path
from datetime import datetime

# Configuration
tickers = ['AAPL', 'MSFT', 'AGNG']  # Edit your ticker list here
data_dir = Path('data/data/daily/us')  # Adjust if needed
start_date = '2021-01-01'
end_date = '2026-03-27'
output_file = 'output/selected_stock_data.csv'

# Known exchange folders (from your ls)
exchanges = [
    'nasdaq etfs', 'nasdaq stocks',
    'nyse etfs', 'nyse stocks',
    'nysemkt etfs', 'nysemkt stocks'
]

data_list = []

for ticker in tickers:
    ticker_file = (ticker.lower() + '.us.txt')
    file_path = None
    
    # Search across exchanges
    for exch in exchanges:
        exch_path = data_dir / exch
        if exch_path.exists():
            potential = exch_path / ticker_file
            if potential.exists():
                file_path = potential
                break
    
    if file_path:
        print(f"Loading {ticker} from {file_path}")
        # Read CSV with exact columns
        df = pd.read_csv(
            file_path,
            names=['Ticker', 'PER', 'Date', 'Time', 'Open', 'High', 'Low', 'Close', 'Volume', 'OpenInt'],
            skiprows=0  # No header
        )
        # Convert Date YYYYMMDD to datetime
        df['Date'] = pd.to_datetime(df['Date'], format='%Y%m%d')
        # Filter dates
        df = df[(df['Date'] >= start_date) & (df['Date'] <= end_date)]
        # Select & rename standard columns (drop PER, Time, OpenInt)
        df = df[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']].copy()
        df['Ticker'] = ticker
        data_list.append(df)
    else:
        print(f"Ticker {ticker} not found in any exchange")

# Combine, sort, save
if data_list:
    combined = pd.concat(data_list, ignore_index=True)
    combined = combined.sort_values(['Ticker', 'Date']).reset_index(drop=True)
    combined.to_csv(output_file, index=False)
    print(f"Saved {len(combined)} rows to {output_file}")
    print(combined.head())
else:
    print("No data found for any ticker")   