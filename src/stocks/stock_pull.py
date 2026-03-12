'''
Author: Matt Hazelwood
File Name: stock_pull.py
Goal: Pull stock data from Yahoo Finance and display it in a readable format.
'''

import yfinance as yf
import pandas as pd

tickers = ['NVDA', 'AAPL', 'MSFT', 'AMD', 'AMZN', 'SPY', 'XLU', 'VTI', 'TSLA', 'DIA', 'QQQ', 'LOW', 'HD', 'WMT', 'JNJ', 'BITW']

def pull_stock_data(ticker, start_date, end_date):
    # Download the stock data using yfinance
    stock_data = yf.download(ticker, start=start_date, end=end_date, interval='1wk')

    # Flatten MultiIndex columns (yfinance returns e.g. ('Close', 'NVDA') — keep only the metric name)
    if isinstance(stock_data.columns, pd.MultiIndex):
        stock_data.columns = stock_data.columns.droplevel(1)

    # Reset the index to make 'Date' a column
    stock_data.reset_index(inplace=True)

    stock_data['Ticker'] = ticker  # Add a column for the ticker symbol

    return stock_data

def pull_all_stocks(start_date='2016-02-19', end_date='2026-02-13', output='all_stocks.csv'):
    all_data = pd.concat(
        [pull_stock_data(ticker, start_date, end_date) for ticker in tickers],
        ignore_index=True
    )
    all_data.to_csv(output, index=False)
    print(f"Saved {len(all_data)} rows to {output}")

