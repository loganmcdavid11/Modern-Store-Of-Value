import pandas as pd
from pathlib import Path
from typing import List, Optional
from .config import DEFAULT_DATA_DIR, DEFAULT_OUTPUT_DIR, DEFAULT_START_DATE, DEFAULT_END_DATE, EXCHANGES

class StooqProcessor:
    def __init__(
        self,
        data_dir: Path = DEFAULT_DATA_DIR,
        output_dir: Path = DEFAULT_OUTPUT_DIR,
        start_date: str = DEFAULT_START_DATE,
        end_date: str = DEFAULT_END_DATE
    ):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.start_date = pd.to_datetime(start_date)
        self.end_date = pd.to_datetime(end_date)
    
    def find_ticker_file(self, ticker: str) -> Optional[Path]:
        """Locate ticker file across exchanges."""
        ticker_file = ticker.lower() + '.us.txt'
        for exch in EXCHANGES:
            exch_path = self.data_dir / exch
            if exch_path.exists():
                potential = exch_path / ticker_file
                if potential.exists():
                    return potential
        return None
    
    def load_ticker(self, ticker: str) -> pd.DataFrame:
        """Load, filter, and standardize one ticker."""
        file_path = self.find_ticker_file(ticker)
        if not file_path:
            raise FileNotFoundError(f"Ticker {ticker} not found")
        
        df = pd.read_csv(
            file_path,
            names=['Ticker', 'PER', 'Date', 'Time', 'Open', 'High', 'Low', 'Close', 'Volume', 'OpenInt']
        )
        df['Date'] = pd.to_datetime(df['Date'], format='%Y%m%d')
        df = df[(df['Date'] >= self.start_date) & (df['Date'] <= self.end_date)]
        df = df[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']].copy()
        df['Ticker'] = ticker.upper()
        df = df.sort_values('Date').reset_index(drop=True)
        return df
    
    def process_tickers(self, tickers: List[str], output_file: str = "stooq_data.csv") -> pd.DataFrame:
        """Process multiple tickers and save combined CSV."""
        data_list = []
        for ticker in tickers:
            try:
                df = self.load_ticker(ticker)
                data_list.append(df)
                print(f"✓ {ticker}: {len(df)} rows")
            except FileNotFoundError as e:
                print(f"✗ {e}")
        
        if data_list:
            combined = pd.concat(data_list, ignore_index=True)
            combined = combined.sort_values(['Ticker', 'Date']).reset_index(drop=True)
            output_path = self.output_dir / output_file
            combined.to_csv(output_path, index=False)
            print(f"Saved {len(combined)} rows to {output_path}")
            return combined
        else:
            print("No data processed")
            return pd.DataFrame()