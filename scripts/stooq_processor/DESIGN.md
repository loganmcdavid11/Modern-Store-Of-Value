# Stooq Processor Design

## Purpose
`scripts/stooq_processor` provides a local, notebook-friendly way to work with the Stooq U.S. daily archive in `data/d_us_txt.zip` without unpacking the full archive to disk first.

The package is designed around three goals:

1. Fast exact ticker lookup.
2. A yfinance-like user experience for pulling multiple symbols at once.
3. Monthly output by default, because the project analysis workflow is monthly-first.

## High-Level Architecture
The package currently exposes two public symbols:

- `TickerInfo`
- `StooqProcessor`

`StooqProcessor` owns three core pieces of state:

1. An open `ZipFile` handle for `data/d_us_txt.zip`.
2. An in-memory ticker catalog keyed by normalized ticker symbol.
3. A lazy cache of parsed daily `pandas.DataFrame` objects.

This gives a hybrid model:

- metadata is loaded eagerly at initialization
- price data is loaded lazily on first use

That split was chosen because the archive is roughly 500 MB compressed and about 1.75 GB uncompressed, which is larger than we want to fully preload for ordinary notebook work.

## Why the Catalog Is Eager
The catalog is built up front so users can:

- quickly check whether a ticker exists
- search by substring
- inspect exchange and instrument type metadata
- fail fast when a requested symbol is missing

The catalog is small relative to the raw data and gives the biggest usability win for the least memory cost.

Each catalog entry stores:

- `symbol`: canonical ticker without `.US`
- `symbol_us`: Stooq ticker format such as `IBIT.US`
- `exchange`: `nasdaq`, `nyse`, or `nysemkt`
- `instrument_type`: `stock` or `etf`
- `zip_member`: exact archive member path
- `bucket`: optional shard folder like `1`, `2`, or `3`

## Path-Based Metadata Inference
The current archive structure is regular enough that we can infer metadata from the member path instead of maintaining a separate mapping file.

Examples:

```text
data/daily/us/nasdaq etfs/ibit.us.txt
data/daily/us/nyse etfs/1/dba.us.txt
data/daily/us/nasdaq stocks/1/aapl.us.txt
data/daily/us/nysemkt stocks/xyz.us.txt
```

Design decisions:

- exchange comes from the leading folder token: `nasdaq`, `nyse`, `nysemkt`
- instrument type comes from the trailing folder token: `stocks` or `etfs`
- the optional intermediate folder becomes `bucket`

This avoids hand-curated metadata and stays aligned with the archive itself.

## Why Daily Data Is Cached, Not Raw Text
The implementation caches parsed daily DataFrames instead of raw decompressed text.

That choice was made because:

- the user-facing API consumes DataFrames, not raw CSV lines
- repeated requests for the same ticker should skip both decompression and CSV parsing
- monthly resampling starts from the daily table anyway

So the cache stores the most useful representation for downstream analysis.

## Data Normalization Decisions
Each raw Stooq file is parsed with these rules:

- only rows with `<PER> == "D"` are kept
- `<DATE>` and `<TIME>` are merged into a `DatetimeIndex` named `Date`
- Stooq column names are renamed to:
  - `Open`
  - `High`
  - `Low`
  - `Close`
  - `Volume`
  - `OpenInt`
- numeric columns are converted with `pandas.to_numeric`
- rows are sorted ascending by `Date`

These choices keep the output clean and close to the shape users expect from yfinance-style workflows.

## Monthly Aggregation Policy
Monthly output is the default interval because that is what this project wants most of the time.

The processor aggregates from daily rows to month-end OHLCV bars:

- `Open`: first daily open in the month
- `High`: maximum daily high in the month
- `Low`: minimum daily low in the month
- `Close`: last daily close in the month
- `Volume`: sum of daily volume in the month
- `OpenInt`: last daily open interest in the month

The date range filter is applied to daily rows before monthly aggregation. That means if a user requests a partial month, the resulting monthly bar reflects only the in-range daily rows.

This was chosen deliberately to avoid leaking out-of-range observations into the returned data.

## API Design Decisions
### `download(...)` returns a dict
The API returns `dict[str, DataFrame]` instead of a list.

That makes it:

- easy to look up a specific symbol after download
- stable even when duplicate requested tickers are deduplicated
- closer to how grouped project analysis code tends to use ticker data

### Ticker normalization is case-insensitive
Users can pass:

- `aapl`
- `AAPL`
- `AAPL.US`

All of these normalize to `AAPL`.

### Missing symbols raise immediately
The processor raises a `KeyError` before loading any data if one or more tickers do not exist in the catalog.

This fail-fast behavior was chosen over silent omission because local data processing is easier to debug when missing symbols are explicit.

### Context manager support
`StooqProcessor` implements `__enter__` and `__exit__` so notebooks and scripts can safely manage the archive handle with:

```python
with StooqProcessor() as processor:
    ...
```

## Search Behavior
`search_tickers()` currently supports case-insensitive substring matching over `symbol`, with optional filters for:

- `exchange`
- `instrument_type`

It returns a metadata DataFrame rather than raw dataclass instances because:

- it is easy to display in notebooks
- it is easy to filter, sort, and inspect interactively
- it matches the project’s pandas-centric workflow

## Tradeoffs and Known Limits
Current limitations are intentional for v1:

- only `data/daily/us/` archive members are supported
- no macro series such as CPI or FRED-style identifiers
- no non-U.S. archive support
- no adjusted close or corporate action handling
- no grouped download helper yet
- only `1d` and `1mo` intervals are supported

These limits keep the package small, explicit, and aligned with the current project needs.

## Testing Strategy
The tests use two layers:

1. Synthetic zip fixture tests
   - verify path parsing
   - verify metadata inference
   - verify daily parsing and monthly aggregation
   - verify error handling and dedup behavior

2. Real archive smoke tests
   - verify that the implementation works against `data/d_us_txt.zip` when present
   - confirm expected symbols and monthly downloads

This combination gives fast, deterministic unit coverage while still checking real-world compatibility.

## Future Extension Points
If the package grows, the likely next steps are:

- grouped ticker download helpers for category dicts
- optional metadata caching to a serialized sidecar file
- broader archive support outside `data/daily/us/`
- optional combined wide DataFrame output
- richer search fields and exchange summaries
