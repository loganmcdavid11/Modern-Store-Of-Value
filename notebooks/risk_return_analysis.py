import marimo

__generated_with = "0.22.0"
app = marimo.App()


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 1. Environment Setup & Imports
    **Purpose:** Initialize libraries and configure the system path so `StooqProcessor` can be imported.
    """)
    return


@app.cell
def _():
    import pandas as pd
    import numpy as np
    from pathlib import Path
    import sys
    import marimo as mo
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.subplots import make_subplots

    if '__file__' in globals():
        current_dir = Path(__file__).resolve().parent
    else:
        current_dir = Path.cwd().resolve()

    repo_root = current_dir.parent

    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from scripts.stooq_processor import StooqProcessor

    return StooqProcessor, go, make_subplots, mo, np, pd, repo_root


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 2. Pipeline Configuration
    **Purpose:** Define the analysis window and 23-ticker asset universe.
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
        "Commodity ETFs (Agriculture)": ["WEAT", "SOYB", "DBA"],
    }

    # Category color palette (consistent across all charts)
    CATEGORY_COLORS = {
        "Crypto ETFs":                  "#AB63FA",
        "Individual Stocks":            "#636EFA",
        "Sector ETFs":                  "#FFA15A",
        "Broad Market ETFs":            "#19D3F3",
        "Commodity ETFs (Metals)":      "#FFD700",
        "Commodity ETFs (Agriculture)": "#00CC96",
    }
    return CATEGORY_COLORS, end_date, start_date, stooq_tickers


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 3. Data Ingestion
    **Purpose:** Pull monthly OHLCV data for all tickers from the local Stooq archive.
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
        raw_data = processor.download(valid_tickers, start=start_date, end=end_date)
    return category_map, raw_data


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 4. Data Formatting & Combination
    **Purpose:** Attach `Ticker` and `Category` metadata and build the unified `combined_data` DataFrame.
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
    print(combined_data.shape)
    return (combined_data,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 5. Risk-Free Rate Ingestion (TB3MS)
    **Purpose:** Load FRED TB3MS data and convert to a monthly decimal rate for excess-return calculations.
    """)
    return


@app.cell
def _(pd, repo_root):
    tbill_data = pd.read_csv(repo_root / "data" / "TB3MS.csv")
    tbill_data = tbill_data.rename(columns={'DATE': 'Date', 'TB3MS': 'Yield'})
    tbill_data['Yield'] = pd.to_numeric(tbill_data['Yield'], errors='coerce').ffill()
    tbill_data['Monthly_RF_Rate'] = (tbill_data['Yield'] / 100) / 12
    tbill_data['Date'] = pd.to_datetime(tbill_data['Date'])
    tbill_data['YearMonth'] = tbill_data['Date'].dt.to_period('M')
    clean_tbill = tbill_data[['YearMonth', 'Monthly_RF_Rate']]
    print(clean_tbill.tail())
    return (clean_tbill,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 6. Calculation Engine: Sharpe, Sortino & Risk-Return Metrics
    **Purpose:** Calculate all risk-adjusted metrics, including Sharpe, Sortino, annualized return, mean monthly return (reward), and standard deviation of monthly returns (risk).

    **Risk-Return framing:** The "reward" metric is the mean monthly return over the full analysis window. The "risk" metric is the standard deviation of monthly returns—a measure of price volatility. Assets in the lower-risk, higher-reward quadrant are the strongest candidates as modern stores of value.
    """)
    return


@app.cell
def _(clean_tbill, combined_data, np, pd, repo_root):
    monthly_data = combined_data.copy()
    monthly_data['Date'] = pd.to_datetime(monthly_data['Date'])
    monthly_data['YearMonth'] = monthly_data['Date'].dt.to_period('M')
    monthly_data = monthly_data.sort_values(['Ticker', 'Date'])
    monthly_data['Monthly_Return'] = monthly_data.groupby('Ticker')['Close'].pct_change()
    monthly_data = pd.merge(monthly_data, clean_tbill, on='YearMonth', how='left')
    monthly_data['Excess_Return'] = monthly_data['Monthly_Return'] - monthly_data['Monthly_RF_Rate']
    monthly_data['Downside_Return'] = np.minimum(monthly_data['Excess_Return'], 0)

    clean_monthly = monthly_data.dropna(subset=['Monthly_Return']).copy()

    def calculate_metrics(group):
        avg_monthly = group['Monthly_Return'].mean()
        avg_excess = group['Excess_Return'].mean()
        std_excess = group['Excess_Return'].std()
        std_downside = group['Downside_Return'].std()
        std_monthly = group['Monthly_Return'].std()   # raw volatility for risk-return plot
        MONTHS = 12
        sharpe = (avg_excess / std_excess) * np.sqrt(MONTHS) if std_excess > 0 else np.nan
        sortino = (avg_excess / std_downside) * np.sqrt(MONTHS) if std_downside > 0 else np.nan

        # Cumulative return: terminal price / initial price
        first_close = group['Close'].iloc[0]
        last_close = group['Close'].iloc[-1]
        cumulative_return = (last_close / first_close) if first_close > 0 else np.nan

        return pd.Series({
            'Annualized_Return_%': (avg_monthly * 12) * 100,
            'Mean_Monthly_Return': avg_monthly,
            'Std_Monthly_Return': std_monthly,
            'Sharpe_Ratio': sharpe,
            'Sortino_Ratio': sortino,
            'Cumulative_Return': cumulative_return,
        })

    results_df = clean_monthly.groupby(['Ticker', 'Category']).apply(calculate_metrics).reset_index()
    results_df = results_df.sort_values('Sortino_Ratio', ascending=False).round(4)

    results_df.to_csv(repo_root / 'data' / 'risk_adjusted_metrics.csv', index=False)
    print(results_df[['Ticker', 'Category', 'Annualized_Return_%', 'Sharpe_Ratio', 'Sortino_Ratio', 'Cumulative_Return']])
    return clean_monthly, results_df


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 7. Visualization: Sharpe & Sortino Leaderboards
    **Purpose:** Side-by-side horizontal bar charts comparing risk-adjusted performance, with the top performer in each metric highlighted in gold.
    """)
    return


@app.cell
def _(CATEGORY_COLORS, go, make_subplots, results_df):
    sharpe_df = results_df.dropna(subset=['Sharpe_Ratio']).sort_values('Sharpe_Ratio', ascending=True)
    sortino_df = results_df.dropna(subset=['Sortino_Ratio']).sort_values('Sortino_Ratio', ascending=True)

    max_sharpe_ticker = sharpe_df['Ticker'].iloc[-1] if not sharpe_df.empty else None
    max_sortino_ticker = sortino_df['Ticker'].iloc[-1] if not sortino_df.empty else None

    def bar_color(row, winner):
        return '#FFD700' if row['Ticker'] == winner else CATEGORY_COLORS.get(row['Category'], '#636EFA')

    sharpe_colors = [bar_color(row, max_sharpe_ticker) for _, row in sharpe_df.iterrows()]
    sortino_colors = [bar_color(row, max_sortino_ticker) for _, row in sortino_df.iterrows()]

    fig_leaderboard = make_subplots(
        rows=1, cols=2,
        subplot_titles=("Sharpe Ratio (Total Volatility)", "Sortino Ratio (Downside Protection)"),
        horizontal_spacing=0.15,
    )

    fig_leaderboard.add_trace(
        go.Bar(
            x=sharpe_df['Sharpe_Ratio'],
            y=sharpe_df['Ticker'],
            orientation='h',
            marker_color=sharpe_colors,
            text=sharpe_df['Sharpe_Ratio'].round(2),
            textposition='outside',
            hovertemplate="<b>%{y}</b><br>Sharpe: %{x:.2f}<extra></extra>",
        ),
        row=1, col=1,
    )

    fig_leaderboard.add_trace(
        go.Bar(
            x=sortino_df['Sortino_Ratio'],
            y=sortino_df['Ticker'],
            orientation='h',
            marker_color=sortino_colors,
            text=sortino_df['Sortino_Ratio'].round(2),
            textposition='outside',
            hovertemplate="<b>%{y}</b><br>Sortino: %{x:.2f}<extra></extra>",
        ),
        row=1, col=2,
    )

    dynamic_height = max(500, len(results_df) * 28)
    fig_leaderboard.update_layout(
        title="Risk-Adjusted Performance Leaderboard (2021–2026)",
        height=dynamic_height,
        showlegend=False,
        template="plotly_white",
        margin=dict(l=20, r=20, t=60, b=20),
    )
    fig_leaderboard.update_xaxes(rangemode="tozero", row=1, col=1)
    fig_leaderboard.update_xaxes(rangemode="tozero", row=1, col=2)

    fig_leaderboard
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 8. Visualization: Risk-Return Scatter Plot
    **Purpose:** Map every asset onto a two-dimensional risk-return space to identify optimal stores of value.

    **Axes:**
    - **X-axis (Risk):** Standard deviation of monthly returns — higher values mean greater price volatility.
    - **Y-axis (Reward):** Mean monthly return over the full 2021–2026 window.

    **Quadrant interpretation:**
    - **Upper-left (Low Risk, High Reward):** Ideal store-of-value candidates.
    - **Upper-right (High Risk, High Reward):** Strong growth assets but unsuitable as safe havens.
    - **Lower-left (Low Risk, Low Reward):** Defensive but underperforming relative to inflation.
    - **Lower-right (High Risk, Low Reward):** Worst outcome — high volatility with poor returns.

    Quadrant lines are drawn at the **median** risk and reward values across the asset universe.
    """)
    return


@app.cell
def _(CATEGORY_COLORS, go, results_df):
    def _():
        scatter_df = results_df.dropna(subset=['Mean_Monthly_Return', 'Std_Monthly_Return']).copy()

        # Quadrant thresholds: median across the universe
        med_risk = scatter_df['Std_Monthly_Return'].median()
        med_reward = scatter_df['Mean_Monthly_Return'].median()

        fig_scatter = go.Figure()

        # One trace per category for the legend (markers only — labels added separately)
        for category, group in scatter_df.groupby('Category'):
            color = CATEGORY_COLORS.get(category, '#636EFA')
            fig_scatter.add_trace(go.Scatter(
                x=group['Std_Monthly_Return'],
                y=group['Mean_Monthly_Return'],
                mode='markers',
                name=category,
                text=group['Ticker'],
                marker=dict(size=8, color=color, line=dict(width=1, color='white')),
                hovertemplate=(
                    "<b>%{text}</b><br>"
                    "Risk (σ): %{x:.3f}<br>"
                    "Reward (μ): %{y:.3f}<br>"
                    "<extra>" + category + "</extra>"
                ),
            ))

        # Quadrant dividers — padding as a fraction of the data span so
        # negative values are handled correctly and the chart has breathing room.
        PADDING = 0.35
        x_span = scatter_df['Std_Monthly_Return'].max() - scatter_df['Std_Monthly_Return'].min()
        y_span = scatter_df['Mean_Monthly_Return'].max() - scatter_df['Mean_Monthly_Return'].min()
        x_range = [scatter_df['Std_Monthly_Return'].min() - x_span * PADDING,
                   scatter_df['Std_Monthly_Return'].max() + x_span * PADDING]
        y_range = [scatter_df['Mean_Monthly_Return'].min() - y_span * PADDING,
                   scatter_df['Mean_Monthly_Return'].max() + y_span * PADDING]

        fig_scatter.add_shape(type="line",
            x0=med_risk, x1=med_risk, y0=y_range[0], y1=y_range[1],
            line=dict(color="gray", width=1, dash="dash"))
        fig_scatter.add_shape(type="line",
            x0=x_range[0], x1=x_range[1], y0=med_reward, y1=med_reward,
            line=dict(color="gray", width=1, dash="dash"))

        # Ticker labels: each pushed radially away from the plot center to
        # spread labels out and minimize overlap.
        import math
        # Normalize axes so the push direction is in display-space, not data-space
        x_span = (x_range[1] - x_range[0]) or 1
        y_span = (y_range[1] - y_range[0]) or 1
        OFFSET_PX = 38   # pixel distance from the dot to the label anchor

        for _, row in scatter_df.iterrows():
            dx_norm = (row['Std_Monthly_Return'] - med_risk) / x_span
            dy_norm = (row['Mean_Monthly_Return'] - med_reward) / y_span
            magnitude = math.sqrt(dx_norm ** 2 + dy_norm ** 2) or 1
            ax = (dx_norm / magnitude) * OFFSET_PX
            # Plotly's ay is screen-space with y inverted (positive = down)
            ay = -(dy_norm / magnitude) * OFFSET_PX

            fig_scatter.add_annotation(
                x=row['Std_Monthly_Return'],
                y=row['Mean_Monthly_Return'],
                text=f"<b>{row['Ticker']}</b>",
                showarrow=True,
                arrowhead=0,
                arrowwidth=1,
                arrowcolor='#AAAAAA',
                ax=ax,
                ay=ay,
                font=dict(size=10),
                bgcolor='rgba(255,255,255,0.7)',
                borderpad=2,
            )

        # Quadrant labels
        quadrant_labels = [
            dict(x=x_range[0] * 1.05, y=y_range[1] * 0.93, text="◀ Low Risk, High Reward (Ideal)                                "),
            dict(x=med_risk * 1.02,    y=y_range[1] * 0.93, text="                            High Risk, High Reward ▶"),
            dict(x=x_range[0] * 1.05, y=y_range[0] * 0.85, text="◀ Low Risk, Low Reward                                "),
            dict(x=med_risk * 1.02,    y=y_range[0] * 0.85, text="                            High Risk, Low Reward ▶"),
        ]
        for ql in quadrant_labels:
            fig_scatter.add_annotation(
                x=ql['x'], y=ql['y'], text=ql['text'],
                showarrow=False, font=dict(size=10, color="gray"),
                xanchor="left",
            )

        fig_scatter.update_layout(
            title="Risk-Return Tradeoff Across Asset Universe (2021–2026)",
            xaxis_title="Risk — Std Dev of Monthly Returns",
            yaxis_title="Reward — Mean Monthly Return",
            template="plotly_white",
            # height=600,
            # width=1000,
            legend=dict(title="Category", orientation="v", x=1.01, y=1),
            margin=dict(l=60, r=200, t=60, b=60),
        )
        fig_scatter.update_xaxes(range=x_range)
        fig_scatter.update_yaxes(range=y_range)
        return fig_scatter


    _()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 9. Visualization: Normalized Price History (Base = 100)
    **Purpose:** Compare cumulative price appreciation across all assets on a common scale, regardless of absolute price level.

    Each asset is indexed to 100 at January 2021. A value of 277 at end-of-period means the asset appreciated 2.77× over the window.
    """)
    return


@app.cell
def _(CATEGORY_COLORS, clean_monthly, go):
    # Pivot to wide form: Date × Ticker
    price_wide = clean_monthly.pivot_table(index='Date', columns='Ticker', values='Close')

    # Normalize: divide each column by its first valid observation × 100
    price_normalized = price_wide.div(price_wide.bfill().iloc[0]) * 100

    # Build one trace per ticker, colored by category
    ticker_to_cat = clean_monthly[['Ticker', 'Category']].drop_duplicates().set_index('Ticker')['Category'].to_dict()

    fig_price = go.Figure()
    for ticker_sym in price_normalized.columns:
        cat = ticker_to_cat.get(ticker_sym, "")
        color = CATEGORY_COLORS.get(cat, '#636EFA')
        is_xlu = ticker_sym == 'XLU'
        fig_price.add_trace(go.Scatter(
            x=price_normalized.index,
            y=price_normalized[ticker_sym],
            mode='lines',
            name=ticker_sym,
            line=dict(
                color=color,
                width=3 if is_xlu else 1,
                dash='solid' if is_xlu else 'solid',
            ),
            opacity=1.0 if is_xlu else 0.5,
            hovertemplate=f"<b>{ticker_sym}</b><br>Date: %{{x|%Y-%m}}<br>Index: %{{y:.1f}}<extra></extra>",
        ))

    # Reference line at 100
    fig_price.add_hline(y=100, line_dash="dot", line_color="black", opacity=0.4,
                        annotation_text="Base (Jan 2021 = 100)", annotation_position="top left")

    fig_price.update_layout(
        title="Normalized Price History — All Assets (Jan 2021 = 100)",
        xaxis_title="Date",
        yaxis_title="Price Index (Jan 2021 = 100)",
        template="plotly_white",
        height=550,
        legend=dict(title="Ticker", orientation="v", x=1.01, y=1),
        margin=dict(l=60, r=150, t=60, b=60),
    )

    fig_price
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 10. XLU Spotlight
    **Purpose:** Surface the key metrics for the utilities sector ETF (XLU), which the research identifies as a notable inflation-adjacent store of value due to its stable appreciation and below-average volatility.
    """)
    return


@app.cell
def _(mo, results_df):
    xlu = results_df[results_df['Ticker'] == 'XLU']
    if xlu.empty:
        mo.md("XLU not found in results.")
    else:
        xlu = xlu.iloc[0]
        cum = xlu['Cumulative_Return']
        ann = xlu['Annualized_Return_%']
        sharpe = xlu['Sharpe_Ratio']
        sortino = xlu['Sortino_Ratio']
        risk = xlu['Std_Monthly_Return']
        mo.md(f"""
        | Metric | XLU Value |
        |---|---|
        | Cumulative Return (2021–2026) | **{cum:.2f}×** |
        | Annualized Return | **{ann:.2f}%** |
        | Sharpe Ratio | **{sharpe:.3f}** |
        | Sortino Ratio | **{sortino:.3f}** |
        | Monthly Return Std Dev (Risk) | **{risk:.4f}** |

        XLU's cumulative return of **{cum:.2f}×** places it among the steadier appreciators in the universe.
        Its below-median volatility combined with a positive Sortino ratio positions it in the **low-risk, positive-reward** quadrant — the defining characteristic of a store-of-value candidate.
        """)
    return


if __name__ == "__main__":
    app.run()
