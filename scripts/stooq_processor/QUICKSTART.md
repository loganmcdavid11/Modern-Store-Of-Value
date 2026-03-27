# Stooq Processor Quick Start

## What It Does
`StooqProcessor` reads `data/d_us_txt.zip`, indexes the U.S. ticker archive, and lets you download ticker data as pandas DataFrames.

By default, downloads return monthly data.

## Basic Example
```python
from scripts.stooq_processor import StooqProcessor

with StooqProcessor() as processor:
    data = processor.download(
        ["IBIT", "ETHA", "AAPL", "DBA"],
        start="2024-01-01",
        end="2024-12-31",
    )

ibit = data["IBIT"]
print(ibit.head())
```

`data` is a dictionary where each key is the normalized ticker and each value is a `pandas.DataFrame`.

## Daily vs Monthly
Monthly is the default:

```python
with StooqProcessor() as processor:
    monthly = processor.download(["AAPL", "MSFT"])
```

If you want daily data:

```python
with StooqProcessor() as processor:
    daily = processor.download(
        ["AAPL", "MSFT"],
        start="2024-01-01",
        end="2024-03-31",
        interval="1d",
    )
```

Supported intervals:

- `"1mo"` for month-end OHLCV bars
- `"1d"` for daily rows

## Inspecting Tickers
List all available symbols:

```python
with StooqProcessor() as processor:
    tickers = processor.list_tickers()
    print(tickers[:20])
```

Check whether a ticker exists:

```python
with StooqProcessor() as processor:
    print(processor.has_ticker("IBIT"))
    print(processor.has_ticker("BTC-USD"))
```

Get metadata for a symbol:

```python
with StooqProcessor() as processor:
    info = processor.get_ticker_info("IBIT")
    print(info)
```

Search by partial symbol:

```python
with StooqProcessor() as processor:
    matches = processor.search_tickers("bit", instrument_type="etf")
    print(matches.head(10))
```

## Expected Output Shape
Each returned DataFrame is indexed by `Date`.

Columns:

- `Open`
- `High`
- `Low`
- `Close`
- `Volume`
- `OpenInt`

## Example With Your Project Tickers
```python
stooq_tickers = [
    "BITW",
    "IBIT",
    "ETHA",
    "NVDA",
    "AAPL",
    "MSFT",
    "AMD",
    "AMZN",
    "TSLA",
    "WMT",
    "LOW",
    "HD",
    "JNJ",
    "XLU",
    "SPY",
    "VTI",
    "GLD",
    "SLV",
    "PPLT",
    "PALL",
    "WEAT",
    "SOYB",
    "DBA",
]

with StooqProcessor() as processor:
    monthly_data = processor.download(
        stooq_tickers,
        start="2021-01-01",
        end="2026-03-31",
    )
```

Then pull the frames you need:

```python
crypto = monthly_data["IBIT"]
gold = monthly_data["GLD"]
market = monthly_data["SPY"]
```

## Common Errors
### Missing ticker
If you request a symbol that is not in the archive, `download()` raises `KeyError`.

```python
with StooqProcessor() as processor:
    processor.download(["AAPL", "BTC-USD"])
```

Use `has_ticker()` or `search_tickers()` first when you are unsure.

### Bad interval
Only `"1d"` and `"1mo"` are supported.

## Running Tests
From the repo root:

```bash
python -m unittest discover -s tests -v
```

## Where To Read More
For design rationale and implementation details, see [DESIGN.md](./DESIGN.md).
