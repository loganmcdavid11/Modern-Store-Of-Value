# Stooq In-Memory Parser Package

## Summary
Build a local package in `scripts/stooq_processor` centered on a `StooqProcessor` class that reads `data/d_us_txt.zip`, indexes all U.S. ticker files for fast lookup, and exposes a yfinance-like `download(...)` API that returns `dict[str, pandas.DataFrame]` keyed by ticker.

Defaults for v1:
- Keep a full ticker catalog in memory at initialization.
- Use lazy per-ticker data caching instead of preloading the entire archive.
- Return monthly data by default.
- Aggregate monthly bars as month-end OHLCV.

## Public API and Implementation
### Public API
Implement and export these symbols:
- `TickerInfo` dataclass
  - `symbol: str` — canonical ticker without `.US`
  - `symbol_us: str` — archive ticker value like `IBIT.US`
  - `exchange: Literal["nasdaq", "nyse", "nysemkt"]`
  - `instrument_type: Literal["stock", "etf"]`
  - `zip_member: str` — full member path inside the zip
  - `bucket: str | None` — shard folder like `"1"` / `"2"` / `"3"` when present
- `StooqProcessor`
  - `__init__(zip_path: str | Path = "data/d_us_txt.zip")`
  - `list_tickers() -> list[str]`
  - `has_ticker(ticker: str) -> bool`
  - `get_ticker_info(ticker: str) -> TickerInfo`
  - `search_tickers(query: str, *, exchange: str | None = None, instrument_type: str | None = None) -> pd.DataFrame`
  - `download(tickers: str | Sequence[str], *, start: str | pd.Timestamp | None = None, end: str | pd.Timestamp | None = None, interval: Literal["1mo", "1d"] = "1mo") -> dict[str, pd.DataFrame]`
  - `close() -> None`
  - `__enter__` / `__exit__` for context-manager use

### Package layout
- `scripts/stooq_processor/parser.py`
  - holds `TickerInfo`, `StooqProcessor`, and internal helpers
- `scripts/stooq_processor/__init__.py`
  - re-export `StooqProcessor` and `TickerInfo`
- `tests/test_stooq_processor.py`
  - unit and smoke tests

### Initialization behavior
On processor creation:
- Open the zip once and keep the `ZipFile` handle on the instance until `close()`.
- Scan only `.txt` members under `data/daily/us/`.
- Build an in-memory catalog `dict[str, TickerInfo]` keyed by uppercase ticker without `.US`.
- Infer metadata from the member path:
  - exchange from folder name: `nasdaq`, `nyse`, `nysemkt`
  - instrument type from folder suffix: `stocks` -> `stock`, `etfs` -> `etf`
  - optional bucket from the extra path segment used in some folders
- Normalize lookups case-insensitively by uppercasing requested symbols.

### Data loading and caching
Use lazy data caching:
- Keep only the ticker catalog in memory at init.
- On first `download()` for a ticker, read and decompress that member from the zip, parse it into a daily DataFrame, and cache the parsed daily DataFrame in memory.
- Reuse the cached daily DataFrame on subsequent calls.

Do not preload the full 1.75 GB uncompressed archive in v1.

### Daily parsing rules
For each ticker file:
- Read the CSV header from Stooq format.
- Keep only rows where `<PER> == "D"`.
- Combine `<DATE>` and `<TIME>` into a pandas `DatetimeIndex` named `Date`.
- Rename columns to clean names:
  - `Open`, `High`, `Low`, `Close`, `Volume`, `OpenInt`
- Convert numeric columns to numeric dtype.
- Sort ascending by `Date`.
- Drop raw Stooq columns that are only needed during parsing.

### Download behavior
`download(...)` should:
- Accept either a single ticker string or a sequence of ticker strings.
- Normalize, validate, and deduplicate tickers while preserving first-seen order.
- Raise `KeyError` listing any missing tickers before loading any data.
- Apply `start` / `end` filtering on daily rows before interval conversion.
- Return a dict keyed by canonical uppercase ticker.

Interval rules:
- `interval="1d"` returns the cached or parsed daily DataFrame slice.
- `interval="1mo"` returns month-end aggregated bars using:
  - `Open`: first daily open in month
  - `High`: max daily high in month
  - `Low`: min daily low in month
  - `Close`: last daily close in month
  - `Volume`: sum of daily volume in month
  - `OpenInt`: last daily open interest in month
- Label monthly rows at calendar month-end.
- Drop empty monthly rows created by resampling.

Search rules:
- `search_tickers()` performs case-insensitive substring matching on `symbol`.
- Optional filters narrow by `exchange` and `instrument_type`.
- Return a metadata DataFrame sorted by `symbol`.

Do not add grouped-category download helpers in v1; notebooks can flatten category dicts before calling `download()`.

## Test Plan
### Unit tests with a synthetic zip fixture
Create a tiny temporary zip containing a few sample members across exchanges and types. Cover:
- catalog construction from member paths
- exact lookup via `has_ticker()` and `get_ticker_info()`
- metadata inference for exchange, type, and bucket
- case-insensitive lookup
- missing ticker validation
- `download(..., interval="1d")` parsing and date slicing
- `download(..., interval="1mo")` month-end OHLCV aggregation
- deduped multi-ticker request returning a dict in request order
- `search_tickers()` substring and filter behavior

### Optional smoke test against the real archive
If `data/d_us_txt.zip` exists locally:
- load the real processor
- confirm known symbols like `IBIT`, `ETHA`, `DBA`, `AAPL`
- assert expected metadata for at least one ETF and one stock
- assert monthly output is non-empty and indexed by datetime

## Assumptions and Defaults
- v1 supports only the U.S. daily archive structure under `data/daily/us/`.
- No non-price macro series support in this parser.
- No adjusted-close logic; Stooq files do not provide Yahoo-style adjusted fields.
- `download()` returns `dict[str, DataFrame]`, not a list and not one combined frame.
- Monthly output is the default because that matches the notebook workflow.
- Lazy data caching is chosen over full-archive preload because the uncompressed archive is about 1.75 GB.
