import marimo

__generated_with = "0.22.0"
app = marimo.App()


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Stooq Database Summary Report
    A structural and statistical survey of every instrument in `data/d_us_txt.zip`.

    The catalog (exchange, instrument type, sub-bucket) is built instantly from ZIP member paths — no price data is loaded. Price-level statistics (date ranges, row counts, data completeness) are estimated from a random sample of tickers to keep runtime manageable.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("### 1. Environment Setup")
    return


@app.cell
def _():
    import sys
    import random
    from pathlib import Path
    import marimo as mo
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    if '__file__' in globals():
        current_dir = Path(__file__).resolve().parent
    else:
        current_dir = Path.cwd().resolve()

    repo_root = current_dir.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from scripts.stooq_processor import StooqProcessor

    return Path, StooqProcessor, go, make_subplots, mo, random, repo_root, sys


@app.cell(hide_code=True)
def _(mo):
    mo.md("### 2. Build Catalog")
    return


@app.cell
def _(StooqProcessor, repo_root):
    import pandas as pd

    processor = StooqProcessor(repo_root / "data" / "d_us_txt.zip")

    # Full catalog as a DataFrame — search_tickers('') returns all rows
    catalog = processor.search_tickers("")

    total_tickers = len(catalog)
    print(f"Total tickers in archive: {total_tickers:,}")
    print(catalog.head())
    return catalog, pd, processor, total_tickers


@app.cell(hide_code=True)
def _(mo):
    mo.md("### 3. Catalog Breakdown")
    return


@app.cell
def _(catalog, pd, total_tickers):
    by_exchange = catalog.groupby("exchange").size().rename("count").reset_index()
    by_type     = catalog.groupby("instrument_type").size().rename("count").reset_index()
    by_bucket   = (
        catalog.groupby(["exchange", "instrument_type", "bucket"])
        .size()
        .rename("count")
        .reset_index()
        .sort_values("count", ascending=False)
    )
    crosstab = pd.crosstab(catalog["exchange"], catalog["instrument_type"])

    print(f"\n{'='*40}")
    print(f"  TOTAL TICKERS: {total_tickers:,}")
    print(f"{'='*40}\n")
    print("By Exchange:")
    print(by_exchange.to_string(index=False))
    print("\nBy Instrument Type:")
    print(by_type.to_string(index=False))
    print("\nExchange × Type Crosstab:")
    print(crosstab)
    print("\nTop Buckets (sub-categories within exchange):")
    print(by_bucket.head(20).to_string(index=False))

    return by_bucket, by_exchange, by_type, crosstab


@app.cell(hide_code=True)
def _(mo):
    mo.md("### 4. Catalog Visualizations")
    return


@app.cell
def _(by_bucket, by_exchange, by_type, go, make_subplots, total_tickers):
    EXCHANGE_COLORS = {
        "nasdaq":  "#636EFA",
        "nyse":    "#00CC96",
        "nysemkt": "#FFA15A",
    }
    TYPE_COLORS = {
        "stock": "#AB63FA",
        "etf":   "#FFD700",
    }

    fig_cat = make_subplots(
        rows=1, cols=2,
        subplot_titles=("Tickers by Exchange", "Tickers by Instrument Type"),
        specs=[[{"type": "pie"}, {"type": "pie"}]],
    )

    fig_cat.add_trace(go.Pie(
        labels=by_exchange["exchange"],
        values=by_exchange["count"],
        marker_colors=[EXCHANGE_COLORS.get(e, "#888") for e in by_exchange["exchange"]],
        textinfo="label+percent+value",
        hole=0.35,
    ), row=1, col=1)

    fig_cat.add_trace(go.Pie(
        labels=by_type["instrument_type"],
        values=by_type["count"],
        marker_colors=[TYPE_COLORS.get(t, "#888") for t in by_type["instrument_type"]],
        textinfo="label+percent+value",
        hole=0.35,
    ), row=1, col=2)

    fig_cat.update_layout(
        title=f"Stooq Archive Composition — {total_tickers:,} Total Tickers",
        template="plotly_white",
        height=420,
        showlegend=False,
    )
    fig_cat


@app.cell
def _(by_bucket, go):
    # Top-30 sub-buckets horizontal bar
    top_buckets = by_bucket.head(30).copy()
    top_buckets["label"] = (
        top_buckets["exchange"].str.upper()
        + " / "
        + top_buckets["instrument_type"]
        + " / "
        + top_buckets["bucket"].fillna("(none)")
    )
    top_buckets = top_buckets.sort_values("count", ascending=True)

    fig_buckets = go.Figure(go.Bar(
        x=top_buckets["count"],
        y=top_buckets["label"],
        orientation="h",
        marker_color="#636EFA",
        text=top_buckets["count"].apply(lambda v: f"{v:,}"),
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Tickers: %{x:,}<extra></extra>",
    ))
    fig_buckets.update_layout(
        title="Top 30 Sub-Buckets by Ticker Count",
        xaxis_title="Number of Tickers",
        template="plotly_white",
        height=700,
        margin=dict(l=300, r=80, t=60, b=40),
    )
    fig_buckets


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 5. Price Data Sample — Date Ranges & Row Counts
    Reading every ticker's price file would take many minutes. Instead, we draw a **random sample of 300 tickers** (stratified by exchange × instrument type) and read their daily data to estimate date-range coverage and data density across the archive.
    """)
    return


@app.cell
def _(catalog, pd, processor, random):
    random.seed(42)
    SAMPLE_N = 300

    # Stratified sample: proportional within each exchange × type group
    sample_rows = (
        catalog.groupby(["exchange", "instrument_type"], group_keys=False)
        .apply(lambda g: g.sample(min(len(g), max(1, round(SAMPLE_N * len(g) / len(catalog)))), random_state=42))
    )
    sample_tickers = sample_rows["symbol"].tolist()[:SAMPLE_N]

    sample_stats = []
    for _sym in sample_tickers:
        try:
            _info = sample_rows[sample_rows["symbol"] == _sym].iloc[0]
            _df = processor.download([_sym], interval="1d")[_sym]
            if _df.empty:
                continue
            sample_stats.append({
                "symbol":          _sym,
                "exchange":        _info["exchange"],
                "instrument_type": _info["instrument_type"],
                "bucket":          _info["bucket"],
                "first_date":      _df.index.min(),
                "last_date":       _df.index.max(),
                "row_count":       len(_df),
                "years_covered":   (_df.index.max() - _df.index.min()).days / 365.25,
                "null_close_pct":  _df["Close"].isna().mean() * 100,
            })
        except Exception:
            pass

    sample_df = pd.DataFrame(sample_stats)
    print(f"Successfully sampled {len(sample_df)} tickers")
    print(sample_df[["symbol", "exchange", "instrument_type", "first_date", "last_date", "row_count", "years_covered"]].describe())
    return sample_df, sample_tickers, SAMPLE_N


@app.cell(hide_code=True)
def _(mo):
    mo.md("### 6. Sample Visualizations — Coverage & Density")
    return


@app.cell
def _(go, make_subplots, sample_df):
    fig_cov = make_subplots(
        rows=1, cols=2,
        subplot_titles=("Distribution of Years Covered", "Distribution of Daily Row Count"),
    )

    fig_cov.add_trace(go.Histogram(
        x=sample_df["years_covered"],
        nbinsx=30,
        marker_color="#636EFA",
        opacity=0.8,
        name="Years covered",
        hovertemplate="Years: %{x:.1f}<br>Count: %{y}<extra></extra>",
    ), row=1, col=1)

    fig_cov.add_trace(go.Histogram(
        x=sample_df["row_count"],
        nbinsx=30,
        marker_color="#00CC96",
        opacity=0.8,
        name="Row count",
        hovertemplate="Rows: %{x:,}<br>Count: %{y}<extra></extra>",
    ), row=1, col=2)

    fig_cov.update_layout(
        title="Sampled Tickers — Historical Coverage",
        template="plotly_white",
        height=400,
        showlegend=False,
    )
    fig_cov


@app.cell
def _(EXCHANGE_COLORS, go, sample_df):
    # Box plot: years covered by exchange
    fig_box = go.Figure()
    for _exch in sample_df["exchange"].unique():
        _grp = sample_df[sample_df["exchange"] == _exch]
        fig_box.add_trace(go.Box(
            y=_grp["years_covered"],
            name=_exch.upper(),
            marker_color=EXCHANGE_COLORS.get(_exch, "#888"),
            boxmean=True,
        ))

    fig_box.update_layout(
        title="Years of History by Exchange (sampled)",
        yaxis_title="Years Covered",
        template="plotly_white",
        height=400,
    )
    fig_box


@app.cell
def _(go, sample_df):
    # Scatter: first date vs last date, sized by row count
    _size = (sample_df["row_count"] / sample_df["row_count"].max() * 14 + 4).round(1)

    TYPE_COLORS_SAMPLE = {"stock": "#AB63FA", "etf": "#FFD700"}
    fig_dates = go.Figure()
    for _itype in sample_df["instrument_type"].unique():
        _g = sample_df[sample_df["instrument_type"] == _itype]
        _sz = (_g["row_count"] / sample_df["row_count"].max() * 14 + 4).round(1)
        fig_dates.add_trace(go.Scatter(
            x=_g["first_date"],
            y=_g["last_date"],
            mode="markers",
            name=_itype,
            marker=dict(size=_sz, color=TYPE_COLORS_SAMPLE.get(_itype, "#888"), opacity=0.6),
            text=_g["symbol"],
            hovertemplate="<b>%{text}</b><br>Start: %{x|%Y-%m-%d}<br>End: %{y|%Y-%m-%d}<extra></extra>",
        ))

    fig_dates.update_layout(
        title="First vs Last Trading Date (sampled) — point size = row count",
        xaxis_title="First Available Date",
        yaxis_title="Last Available Date",
        template="plotly_white",
        height=500,
        legend=dict(title="Type"),
    )
    fig_dates


@app.cell(hide_code=True)
def _(mo):
    mo.md("### 7. Summary Statistics Table")
    return


@app.cell
def _(SAMPLE_N, mo, sample_df, total_tickers):
    _stats = sample_df[["years_covered", "row_count", "null_close_pct"]]

    mo.md(f"""
    ## Stooq Archive — Summary Report

    | Metric | Value |
    |---|---|
    | **Total tickers in archive** | {total_tickers:,} |
    | **Sample size** | {len(sample_df)} / {SAMPLE_N} requested |
    | **Median years of history** | {_stats['years_covered'].median():.1f} yrs |
    | **Mean years of history** | {_stats['years_covered'].mean():.1f} yrs |
    | **Max years of history** | {_stats['years_covered'].max():.1f} yrs |
    | **Min years of history** | {_stats['years_covered'].min():.1f} yrs |
    | **Median daily row count** | {_stats['row_count'].median():,.0f} rows |
    | **Mean daily row count** | {_stats['row_count'].mean():,.0f} rows |
    | **Median null Close %** | {_stats['null_close_pct'].median():.2f}% |
    | **Earliest first date (sample)** | {sample_df['first_date'].min().date()} |
    | **Latest last date (sample)** | {sample_df['last_date'].max().date()} |
    """)


if __name__ == "__main__":
    app.run()
