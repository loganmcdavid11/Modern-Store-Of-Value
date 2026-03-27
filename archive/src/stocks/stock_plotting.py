import pandas as pd
import plotly.express as px

def plot_close_prices(filepath='all_stocks.csv'):
    df = pd.read_csv(filepath, parse_dates=['Date'])

    fig = px.line(
        df,
        x='Date',
        y='Close',
        color='Ticker',
        title='Stock Closing Prices Over Time',
        labels={'Close': 'Closing Price (USD)'},
    )

    fig.show()