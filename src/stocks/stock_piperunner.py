"""
Pipeline runner for stock data processing and analysis.
This script orchestrates the execution of various stages in the stock data pipeline.
"""

from stock_pull import pull_all_stocks
from stock_plotting import plot_close_prices

def main():
    pull_all_stocks()
    plot_close_prices()

if __name__ == "__main__":
    main()
