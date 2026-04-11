# Report Updates — Modern Store of Value
> This file contains the updated and new section text to copy into the Google Doc.
> Sections are labeled by their location in the report.

---

## SECTION 1 — Data Sources: "Stock Market Data" (replace existing paragraph)

Stock market data was gathered using a custom data processor built on Stooq's historical pricing archive. The `StooqProcessor` reads directly from a local compressed archive (`data/d_us_txt.zip`, ~500 MB compressed / ~1.75 GB uncompressed) without unpacking it to disk, enabling fast, reproducible, offline data access with no API rate limits or external service dependencies. Monthly price data was collected for 23 securities covering a five-year period from January 1st, 2021, to March 31st, 2026. Monthly intervals were selected to reduce noise while capturing meaningful price movements and trends.

---

## SECTION 3 — "Stooq Data Processor" (replace "blarg")

### Stooq Data Processor

Stock and ETF price data for this project is sourced from Stooq's U.S. daily archive—a compressed dataset containing OHLCV records for thousands of NASDAQ, NYSE, and NYSEMKT-listed instruments. To access this archive programmatically, we built a custom Python package (`scripts/stooq_processor`) that wraps the ZIP file with a yfinance-style API.

**Why a custom processor instead of yfinance?**

Our initial pipeline fetched data from Yahoo Finance via the `yfinance` Python library (see Section 7, Archive). While convenient, that approach introduced several reliability risks: API rate limiting, dependency on an external service's uptime, and lack of reproducibility across machines or over time. As the scope of the analysis expanded to 23 tickers and a five-year window, the brittle nature of live API calls became a growing concern. Moving to a locally cached archive solved all of these problems simultaneously.

**Architecture**

`StooqProcessor` owns three pieces of state:

1. An open `ZipFile` handle pointing to `data/d_us_txt.zip`
2. An in-memory **ticker catalog** keyed by normalized symbol (e.g., `"IBIT"`)
3. A **lazy price cache** of parsed daily DataFrames, populated on first use

The catalog is built eagerly at initialization time. Because each member path in the archive encodes exchange and instrument type in its folder structure (e.g., `data/daily/us/nasdaq etfs/ibit.us.txt`), the processor can infer all metadata without a separate mapping file. This eager-catalog / lazy-data split keeps startup fast while avoiding the memory cost of pre-loading the full 1.75 GB uncompressed dataset.

**Monthly aggregation**

The default interval is monthly (`interval="1mo"`). When a caller requests monthly data, the processor:
1. Loads and parses the relevant daily rows from the ZIP
2. Applies the date-range filter at the daily level
3. Resamples to month-end bars using the following OHLCV aggregation policy:
   - `Open`: first daily open of the month
   - `High`: maximum daily high of the month
   - `Low`: minimum daily low of the month
   - `Close`: last daily close of the month
   - `Volume`: sum of all daily volumes in the month

This ensures partial months at either end of a date range only reflect the in-range trading days, not any out-of-window observations.

**Usage in ratio_calculations.py**

The analysis pipeline in `notebooks/ratio_calculations.py` interacts with the processor through a context manager, which guarantees the ZIP handle is closed cleanly after use:

```python
with StooqProcessor(repo_root / "data" / "d_us_txt.zip") as processor:
    valid_tickers = [t for t in flat_tickers if processor.has_ticker(t)]
    raw_data = processor.download(
        valid_tickers,
        start="2021-01-01",
        end="2026-03-31",
    )
```

`download()` returns a `dict[str, DataFrame]`—one entry per ticker—which is then annotated with category metadata and concatenated into a single unified `combined_data` DataFrame for downstream analysis.

For full architecture rationale and API reference, see `scripts/stooq_processor/DESIGN.md` and `scripts/stooq_processor/QUICKSTART.md`.

---

## SECTION 3 — "Stock Data" (full replacement)

### Stock Data

Stock and ETF data was retrieved from Stooq's local archive via the `StooqProcessor` package described above. The dataset comprises 23 securities spanning January 1st, 2021 to March 31st, 2026, collected at monthly intervals. Monthly granularity was chosen to reduce week-to-week noise while preserving enough resolution to track regime changes and crisis events over the five-year window.

The ticker universe was organized into six categories:

| Category | Tickers |
|---|---|
| Crypto ETFs | BITW, IBIT, ETHA |
| Individual Stocks | NVDA, AAPL, MSFT, AMD, AMZN, TSLA, WMT, LOW, HD, JNJ |
| Sector ETFs | XLU |
| Broad Market ETFs | SPY, VTI |
| Commodity ETFs (Metals) | GLD, SLV, PPLT, PALL |
| Commodity ETFs (Agriculture) | WEAT, SOYB, DBA |

The raw data for each ticker is returned as a DataFrame indexed by `Date` with columns `Open`, `High`, `Low`, `Close`, `Volume`, and `OpenInt`. The pipeline then attaches `Ticker` and `Category` columns to each frame and concatenates all 23 into a unified `combined_data` DataFrame. The final calculated outputs are exported to `data/risk_adjusted_metrics.csv`, which contains the annualized return, Sharpe ratio, and Sortino ratio for each security.

*Note: DIA (Dow Jones ETF) and QQQ (Nasdaq-100 ETF) were present in the earlier yfinance-based pipeline but were excluded from the current Stooq analysis in favor of a tighter, more analytically distinct asset universe. The current 23-ticker selection prioritizes category diversity over broad index redundancy.*

---

## SECTION 4 — "Data Processing Pipeline" → "Extraction and Consolidation" (full replacement)

### Extraction and Consolidation

The data processing pipeline is implemented as a Marimo reactive notebook (`notebooks/ratio_calculations.py`). Each cell in the notebook is a discrete, labeled stage, making the full workflow reproducible and easy to inspect step-by-step.

**Stage 1 — Environment Setup:** Imports pandas, numpy, and Plotly, then adds the repo root to `sys.path` so the local `StooqProcessor` package can be imported by relative path.

**Stage 2 — Pipeline Configuration:** Defines the 2021-2026 analysis window and the 23-ticker asset universe, organized as a dictionary keyed by category name.

**Stage 3 — Data Ingestion:** Opens the Stooq archive via `StooqProcessor`, validates that each requested ticker exists in the catalog, and downloads monthly OHLCV data for the full date range. Any tickers absent from the archive are logged and skipped rather than raising a hard failure.

**Stage 4 — Data Formatting:** Iterates over the downloaded `dict[str, DataFrame]`, attaches `Ticker` and `Category` columns to each frame, and concatenates all frames into a single `combined_data` DataFrame with a proper `datetime` Date column.

**Stage 5 — Risk-Free Rate Ingestion:** Reads the locally cached FRED TB3MS yield file (`data/TB3MS.csv`), converts the annualized whole-number yield to a monthly decimal (dividing by 100 and then by 12), and creates a `YearMonth` period key for a later date-agnostic merge.

**Stage 6 — Calculation Engine:** Merges the risk-free rate into the combined price data by `YearMonth`, calculates monthly returns via percentage change on the Close column, and computes Sharpe and Sortino ratios per ticker. Results are exported to `data/risk_adjusted_metrics.csv`.

**Stage 7 — Visualization:** Generates side-by-side horizontal bar chart leaderboards using Plotly, independently sorted by Sharpe and Sortino ratios, with the top performer in each metric highlighted in gold.

---

## SECTION 4 — "Feature Engineering" (replace existing text)

### Feature Engineering

Raw monthly close prices were transformed into the metrics used for risk analysis through a sequence of calculated fields.

**Returns Calculation:** Month-over-month returns were computed using percentage change (`pct_change()`) applied to the Close column, grouped by ticker. Percentage change was selected over logarithmic returns because the downstream Sharpe and Sortino formulas use arithmetic mean excess return, which is more naturally interpreted in percentage terms.

**Excess Return:** Each month's return was adjusted by the contemporaneous risk-free rate (TB3MS monthly equivalent) to produce an excess return series: `Excess_Return = Monthly_Return − Monthly_RF_Rate`. Using a time-varying risk-free rate, rather than a fixed constant, ensures the analysis correctly reflects the rising rate environment of 2022–2023.

**Downside Return:** The Sortino calculation requires isolating only the negative excess return months: `Downside_Return = min(Excess_Return, 0)`. Months where the asset outperformed the risk-free rate contribute zero to the downside deviation, not a negative number.

**Annualized Return:** The mean monthly return across the full 2021-2026 window was multiplied by 12 to express cumulative average performance in annualized terms.

*Note: Rolling volatility windows (e.g., 12-week rolling standard deviation) are used in the broader exploratory analysis but are not part of the core risk-adjusted metrics pipeline, which operates on the full-period aggregation.*

---

## SECTION 4 — "Sharpe Ratio Calculation" (replace/complete existing text)

### Sharpe Ratio Calculation

The Sharpe ratio measures excess return per unit of total volatility. It penalizes both upside and downside variance equally, making it an appropriate metric for evaluating whether an asset delivers sufficient return to justify its overall price variation.

**Formula:**

$$\text{Sharpe} = \frac{\bar{r}_{excess}}{\sigma_{excess}} \times \sqrt{12}$$

Where:
- $\bar{r}_{excess}$ = mean monthly excess return (monthly asset return minus monthly TB3MS equivalent)
- $\sigma_{excess}$ = standard deviation of monthly excess returns across the full analysis window
- $\sqrt{12}$ = annualization factor for monthly data

**Risk-Free Rate:** The 3-Month U.S. Treasury Bill secondary market rate (FRED series TB3MS, stored locally in `data/TB3MS.csv`) serves as the risk-free benchmark. The annualized whole-number yield is converted to a monthly decimal: `Monthly_RF_Rate = (Yield / 100) / 12`. A time-varying rate is used rather than a fixed constant to accurately reflect the significantly different rate environments across the 2021–2026 period (near-zero rates in 2021–2022 vs. 5%+ in 2023–2024).

**Interpretation:** A Sharpe ratio above 1.0 is generally considered good, above 2.0 excellent. Negative ratios indicate that the asset failed to beat the risk-free rate on average. Ratios are not directly comparable across assets with fundamentally different volatility profiles without also considering the Sortino ratio for a fuller picture.

A ticker with zero standard deviation of excess returns returns `NaN` rather than infinity and is excluded from the leaderboard visualization.

---

## SECTION 4 — "Sortino Ratio Calculation" (new content)

### Sortino Ratio Calculation

The Sortino ratio is a refinement of the Sharpe ratio that penalizes only downside volatility rather than total volatility. This makes it a more appropriate measure for evaluating safe haven characteristics, since upward price swings are desirable for investors and should not reduce a store-of-value score.

**Formula:**

$$\text{Sortino} = \frac{\bar{r}_{excess}}{\sigma_{downside}} \times \sqrt{12}$$

Where:
- $\bar{r}_{excess}$ = mean monthly excess return (same numerator as Sharpe)
- $\sigma_{downside}$ = standard deviation of the downside excess return series, where $r_{downside,t} = \min(r_{excess,t},\ 0)$
- $\sqrt{12}$ = annualization factor for monthly data

Months where the asset outperformed the risk-free rate contribute `0` to the downside series, not a negative value. Only months in which the asset fell short of the risk-free rate contribute to the downside deviation. This means an asset with high upward volatility (e.g., NVDA) is not penalized compared to a smooth-but-stagnant asset (e.g., GLD), as long as its losses are contained.

**Why Sortino matters for this analysis:** Traditional stores of value are judged primarily on their ability to preserve capital during downturns. An asset that doubles during bull markets but loses 50% during stress events is not a safe haven. The Sortino ratio directly encodes this asymmetry: it rewards strong average returns while specifically quantifying the cost of downside risk, making it the more discriminating metric for identifying true stores of value in our asset universe.

---

## SECTION 4 — "Technology Stack and Implementation" (updated Python Libraries list)

Replace the existing bulleted library list with the following. Remove the yfinance, Requests, and python-dotenv entries from the "active" list and move them to the new "Archive (Legacy)" subsection below.

**Active Libraries:**

- **Pandas:** Data manipulation, cleaning, and transformation operations. Pandas' DataFrame structure provided efficient handling of time-series data across 23 securities. Used for monthly return calculation (`pct_change()`), period-based merging of the risk-free rate, and vectorized aggregation of Sharpe and Sortino metrics.

- **NumPy:** Numerical computations including statistical calculations (`np.sqrt`, `np.minimum`), zero-division guards, and matrix operations for correlation analysis.

- **StooqProcessor (custom):** Local archive reader for `data/d_us_txt.zip`. Provides a yfinance-compatible API without network dependency. See `scripts/stooq_processor/parser.py` and `DESIGN.md`.

- **Plotly:** Interactive visualization enabling detailed examination of time-series patterns, crisis-period behavior, and cross-asset comparisons. Used for the Sharpe/Sortino leaderboard charts and the risk-return scatter plot.

- **Marimo:** Reactive notebook runtime used to structure `notebooks/ratio_calculations.py` as a series of labeled, independently executable pipeline stages.

- **SciPy:** Advanced statistical tests including correlation significance tests and distribution fitting for volatility analysis.

- **Statsmodels:** Time-series modeling and regression analysis.

**Archive (Legacy):**

The following libraries were used in an earlier pipeline iteration (`archive/src/stocks/`) and have since been replaced:

- **yfinance:** Direct interface to Yahoo Finance API. Used in `stock_pull.py` to retrieve weekly price data for 16 tickers. Replaced by `StooqProcessor` + local Stooq archive to eliminate API rate limiting and external service dependency.

- **Requests / python-dotenv:** HTTP requests and secure API key management for Alpha Vantage. Used in `archive/src/crypto/CryptoDataDownload.py` for cryptocurrency data retrieval. Replaced because crypto ETFs (IBIT, ETHA, BITW) are available directly in the Stooq archive.

---

## SECTION 7 — Appendix: Data Sources (replace existing list)

**Active Data Sources:**

- **Stooq U.S. Daily Archive** (`data/d_us_txt.zip`) — Primary source for all stock and ETF OHLCV data. Accessed via the custom `StooqProcessor` package. Contains NASDAQ, NYSE, and NYSEMKT-listed instruments.

- **FRED — Federal Reserve Economic Data**
  - `data/TB3MS.csv`: 3-Month U.S. Treasury Bill Secondary Market Rate (risk-free rate for Sharpe/Sortino calculations)
  - `data/CPIAUCSL.csv`: Consumer Price Index for All Urban Consumers (inflation benchmark)

---

## SECTION 7 — Appendix: Archive (new subsection)

### Archive

The `/archive` directory preserves the complete prior data pipeline for reference and reproducibility. This version of the codebase was active from project inception through early 2026, before the migration to the Stooq-based architecture.

| File | Description |
|---|---|
| `archive/src/stocks/stock_pull.py` | Downloads weekly OHLCV data for 16 tickers via `yfinance.download()` at `interval='1wk'`. Produces `all_stocks.csv`. |
| `archive/src/stocks/stock_piperunner.py` | Two-stage pipeline orchestrator: calls `pull_all_stocks()` then `plot_close_prices()`. |
| `archive/src/stocks/stock_plotting.py` | Plotly visualizations with inflation overlay using the `all_stocks.csv` output. |
| `archive/src/stocks/stock_list.txt` | Historical ticker list used by the yfinance pipeline. |
| `archive/src/crypto/CryptoDataDownload.py` | Alpha Vantage API-based cryptocurrency price downloader (requires `AV_API_KEY` environment variable). |
| `archive/src/crypto/WilshireDataDownload.py` | Fetches Wilshire 5000 total market index data. |
| `archive/CryptoEDA.ipynb` | Early exploratory data analysis notebook for Bitcoin and Ethereum price behavior. |
| `archive/commodities.ipynb` | Early commodities EDA notebook covering raw material price trends. |

**Why these were replaced:**

- **yfinance → Stooq:** The Yahoo Finance API has unpredictable rate limits and has historically changed its response format without notice. The local Stooq archive guarantees reproducibility: the same ZIP file produces the same data regardless of when the analysis is run.

- **Alpha Vantage → Stooq:** After the launch of SEC-approved spot Bitcoin and Ethereum ETFs (IBIT, ETHA), the relevant exposure to cryptocurrency for a regulated analysis context shifted from raw BTC/ETH API prices to the ETF price series—which are available directly in the Stooq archive. This eliminated the need for a separate API key and request pipeline.

- **Weekly → Monthly intervals:** Monthly data reduces day-to-day noise and aligns the return series with the TB3MS risk-free rate, which is also reported at a monthly frequency, simplifying the Sharpe/Sortino merge logic.

- **16 → 23 tickers:** DIA and QQQ were dropped (redundant with SPY/VTI for broad market exposure). BITW, IBIT, ETHA, PPLT, PALL, WEAT, SOYB, and DBA were added to provide meaningful coverage of crypto ETFs, platinum-group metals, and agricultural commodities—the core alternative asset classes the research investigates.
