import io
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

def get_inflation():
    # FRED blocks urllib's default agent — use requests with a browser header
    response = requests.get(
        'https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCSL',
        headers={'User-Agent': 'Mozilla/5.0'},
        timeout=15
    )
    response.raise_for_status()
    cpi = pd.read_csv(io.StringIO(response.text))
    cpi.columns = ['DATE', 'CPIAUCSL']
    cpi['DATE'] = pd.to_datetime(cpi['DATE'])
    cpi = cpi.set_index('DATE')
    cpi['YoY_Inflation'] = cpi['CPIAUCSL'].pct_change(periods=12) * 100
    cpi = cpi.dropna()
    return cpi.loc['2021-01-01':'2026-03-11']

def plot_close_prices(filepath='all_stocks.csv'):
    df = pd.read_csv(filepath, parse_dates=['Date'])
    yoy_inflation = get_inflation()

    # Build base line chart for stocks
    fig = px.line(
        df,
        x='Date',
        y='Close',
        color='Company',
        title='Stock Closing Prices Over Time',
        labels={'Close': 'Closing Price (USD)'},
    )

    # Add YoY inflation as a shaded area on a secondary y-axis
    inflation_trace = go.Scatter(
        x=yoy_inflation.index,
        y=yoy_inflation['YoY_Inflation'],
        name='US Inflation Rate (YoY %)',
        fill='tozeroy',
        mode='lines',
        line=dict(color='rgba(64, 64, 64, 0.9)', width=4, dash='dot'),
        fillcolor='rgba(128, 128, 128, 0.25)',
        yaxis='y2'
    )
    fig.add_trace(inflation_trace)

    # Push inflation trace to the back
    fig.data = (fig.data[-1],) + fig.data[:-1]

    fig.update_layout(
        height=800,
        width=1400,
        template='plotly_white',
        yaxis2=dict(
            title='YoY Inflation Rate (%)',
            overlaying='y',
            side='right',
            showgrid=False,
        ),
        legend=dict(
            title='<b>Assets</b>',
            itemsizing='constant'
        )
    )

    fig.show()
