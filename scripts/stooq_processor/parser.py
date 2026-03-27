from __future__ import annotations

from dataclasses import asdict, dataclass
from io import TextIOWrapper
from pathlib import Path
from typing import Literal, Mapping, Sequence
from zipfile import ZipFile

import pandas as pd

Exchange = Literal["nasdaq", "nyse", "nysemkt"]
InstrumentType = Literal["stock", "etf"]
TickerGroups = Mapping[str, Sequence[str]]

STOOQ_ROOT = "data/daily/us/"
STOOQ_MEMBER_SUFFIX = ".us.txt"
DAILY_INTERVAL = "1d"
MONTHLY_INTERVAL = "1mo"
DAILY_COLUMNS = ["Open", "High", "Low", "Close", "Volume", "OpenInt"]

_COLUMN_RENAME = {
    "<OPEN>": "Open",
    "<HIGH>": "High",
    "<LOW>": "Low",
    "<CLOSE>": "Close",
    "<VOL>": "Volume",
    "<OPENINT>": "OpenInt",
}
_MONTHLY_AGGREGATIONS = {
    "Open": "first",
    "High": "max",
    "Low": "min",
    "Close": "last",
    "Volume": "sum",
    "OpenInt": "last",
}
_INSTRUMENT_TYPE_MAP = {"stocks": "stock", "etfs": "etf"}


@dataclass(frozen=True, slots=True)
class TickerInfo:
    symbol: str
    symbol_us: str
    exchange: Exchange
    instrument_type: InstrumentType
    zip_member: str
    bucket: str | None


class StooqProcessor:
    def __init__(self, zip_path: str | Path = "data/d_us_txt.zip") -> None:
        self.zip_path = Path(zip_path)
        if not self.zip_path.exists():
            raise FileNotFoundError(f"Stooq archive not found: {self.zip_path}")

        self._zip_file: ZipFile | None = ZipFile(self.zip_path)
        self._catalog = self._build_catalog()
        self._metadata_frame = self._build_metadata_frame()
        self._daily_cache: dict[str, pd.DataFrame] = {}

    def __enter__(self) -> StooqProcessor:
        return self

    def __exit__(self, exc_type, exc, exc_tb) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def list_tickers(self) -> list[str]:
        return self._metadata_frame["symbol"].tolist()

    def build_category_map(
        self, tickers: str | Sequence[str] | TickerGroups
    ) -> dict[str, str]:
        if isinstance(tickers, Mapping):
            category_map: dict[str, str] = {}
            for category, symbols in tickers.items():
                for symbol in symbols:
                    normalized = self._normalize_ticker(symbol)
                    category_map.setdefault(normalized, category)
            return category_map

        return {}

    def has_ticker(self, ticker: str) -> bool:
        return self._normalize_ticker(ticker) in self._catalog

    def get_ticker_info(self, ticker: str) -> TickerInfo:
        normalized = self._normalize_ticker(ticker)
        try:
            return self._catalog[normalized]
        except KeyError as exc:
            raise KeyError(f"Unknown ticker: {normalized}") from exc

    def search_tickers(
        self,
        query: str,
        *,
        exchange: str | None = None,
        instrument_type: str | None = None,
    ) -> pd.DataFrame:
        frame = self._metadata_frame

        if query:
            frame = frame.loc[
                frame["symbol"].str.contains(query, case=False, regex=False)
            ]

        if exchange is not None:
            normalized_exchange = exchange.strip().lower()
            valid_exchanges = {"nasdaq", "nyse", "nysemkt"}
            if normalized_exchange not in valid_exchanges:
                raise ValueError(
                    "exchange must be one of: nasdaq, nyse, nysemkt"
                )
            frame = frame.loc[frame["exchange"] == normalized_exchange]

        if instrument_type is not None:
            normalized_instrument_type = instrument_type.strip().lower()
            valid_types = {"stock", "etf"}
            if normalized_instrument_type not in valid_types:
                raise ValueError("instrument_type must be one of: stock, etf")
            frame = frame.loc[
                frame["instrument_type"] == normalized_instrument_type
            ]

        return frame.reset_index(drop=True).copy()

    def download(
        self,
        tickers: str | Sequence[str] | TickerGroups,
        *,
        start: str | pd.Timestamp | None = None,
        end: str | pd.Timestamp | None = None,
        interval: Literal["1mo", "1d"] = MONTHLY_INTERVAL,
    ) -> dict[str, pd.DataFrame]:
        self._ensure_open()

        normalized_tickers = self._normalize_ticker_sequence(tickers)
        missing = [ticker for ticker in normalized_tickers if ticker not in self._catalog]
        if missing:
            joined = ", ".join(missing)
            raise KeyError(f"Unknown ticker(s): {joined}")

        start_ts = self._normalize_timestamp(start, label="start")
        end_ts = self._normalize_timestamp(end, label="end")
        if start_ts is not None and end_ts is not None and start_ts > end_ts:
            raise ValueError("start must be earlier than or equal to end")

        if interval not in {DAILY_INTERVAL, MONTHLY_INTERVAL}:
            raise ValueError("interval must be one of: '1d', '1mo'")

        results: dict[str, pd.DataFrame] = {}
        for ticker in normalized_tickers:
            daily_frame = self._get_daily_frame(ticker)
            effective_end = self._resolve_effective_end(
                daily_frame, requested_end=end_ts
            )
            filtered_frame = self._filter_by_date_range(
                daily_frame, start=start_ts, end=effective_end
            )
            if interval == DAILY_INTERVAL:
                results[ticker] = filtered_frame.copy()
            else:
                results[ticker] = self._to_monthly(
                    filtered_frame,
                    effective_end=effective_end,
                    relabel_final_period=(
                        effective_end is not None
                        and end_ts is not None
                        and effective_end < end_ts
                    )
                    or (end_ts is None and effective_end is not None),
                )

        return results

    def close(self) -> None:
        if self._zip_file is not None:
            self._zip_file.close()
            self._zip_file = None

    def _build_catalog(self) -> dict[str, TickerInfo]:
        if self._zip_file is None:
            raise RuntimeError("The Stooq archive is closed.")

        catalog: dict[str, TickerInfo] = {}
        for member in self._zip_file.namelist():
            if not self._is_supported_member(member):
                continue

            ticker_info = self._ticker_info_from_member(member)
            if ticker_info.symbol in catalog:
                raise ValueError(f"Duplicate ticker symbol in archive: {ticker_info.symbol}")
            catalog[ticker_info.symbol] = ticker_info

        return catalog

    def _build_metadata_frame(self) -> pd.DataFrame:
        rows = [asdict(info) for info in self._catalog.values()]
        if not rows:
            return pd.DataFrame(
                columns=[
                    "symbol",
                    "symbol_us",
                    "exchange",
                    "instrument_type",
                    "zip_member",
                    "bucket",
                ]
            )

        return (
            pd.DataFrame(rows)
            .sort_values("symbol", kind="stable")
            .reset_index(drop=True)
        )

    def _get_daily_frame(self, ticker: str) -> pd.DataFrame:
        cached = self._daily_cache.get(ticker)
        if cached is not None:
            return cached

        ticker_info = self._catalog[ticker]
        parsed_frame = self._read_daily_member(ticker_info)
        self._daily_cache[ticker] = parsed_frame
        return parsed_frame

    def _read_daily_member(self, ticker_info: TickerInfo) -> pd.DataFrame:
        if self._zip_file is None:
            raise RuntimeError("The Stooq archive is closed.")

        with self._zip_file.open(ticker_info.zip_member) as raw_member:
            with TextIOWrapper(raw_member, encoding="utf-8") as text_member:
                raw_frame = pd.read_csv(text_member)

        if raw_frame.empty:
            return self._empty_price_frame()

        daily_frame = raw_frame.loc[raw_frame["<PER>"] == "D"].copy()
        if daily_frame.empty:
            return self._empty_price_frame()

        daily_frame["Date"] = pd.to_datetime(
            daily_frame["<DATE>"].astype(str).str.zfill(8)
            + daily_frame["<TIME>"].astype(str).str.zfill(6),
            format="%Y%m%d%H%M%S",
            errors="coerce",
        )
        daily_frame = daily_frame.loc[daily_frame["Date"].notna()].copy()

        for source_column in _COLUMN_RENAME:
            daily_frame[source_column] = pd.to_numeric(
                daily_frame[source_column], errors="coerce"
            )

        daily_frame = daily_frame.rename(columns=_COLUMN_RENAME)
        daily_frame = daily_frame.set_index("Date")[DAILY_COLUMNS]
        daily_frame = daily_frame.sort_index()
        daily_frame.index.name = "Date"

        return daily_frame

    def _filter_by_date_range(
        self,
        frame: pd.DataFrame,
        *,
        start: pd.Timestamp | None,
        end: pd.Timestamp | None,
    ) -> pd.DataFrame:
        filtered = frame
        if start is not None:
            filtered = filtered.loc[filtered.index >= start]
        if end is not None:
            filtered = filtered.loc[filtered.index <= end]
        return filtered

    def _resolve_effective_end(
        self,
        frame: pd.DataFrame, *, requested_end: pd.Timestamp | None
    ) -> pd.Timestamp | None:
        if frame.empty:
            return requested_end

        latest_available = frame.index.max()
        if requested_end is None:
            return latest_available

        return min(requested_end, latest_available)

    def _to_monthly(
        self,
        frame: pd.DataFrame,
        *,
        effective_end: pd.Timestamp | None,
        relabel_final_period: bool,
    ) -> pd.DataFrame:
        if frame.empty:
            return frame.copy()

        monthly = frame.resample("ME").agg(_MONTHLY_AGGREGATIONS)
        monthly = monthly.dropna(how="all")

        if relabel_final_period and effective_end is not None and not monthly.empty:
            final_label = monthly.index[-1]
            if effective_end.to_period("M") == final_label.to_period("M"):
                new_index = monthly.index.to_list()
                new_index[-1] = effective_end
                monthly.index = pd.DatetimeIndex(new_index)

        monthly.index.name = "Date"
        return monthly.copy()

    def _ensure_open(self) -> None:
        if self._zip_file is None:
            raise RuntimeError("The Stooq archive is closed.")

    @staticmethod
    def _normalize_ticker(ticker: str) -> str:
        if not isinstance(ticker, str) or not ticker.strip():
            raise ValueError("Ticker names must be non-empty strings.")

        normalized = ticker.strip().upper()
        if normalized.endswith(".US"):
            normalized = normalized[:-3]
        return normalized

    def _normalize_ticker_sequence(
        self, tickers: str | Sequence[str] | TickerGroups
    ) -> list[str]:
        if isinstance(tickers, Mapping):
            raw_tickers: list[str] = []
            for symbols in tickers.values():
                raw_tickers.extend(symbols)
        else:
            raw_tickers = [tickers] if isinstance(tickers, str) else list(tickers)

        normalized_tickers: list[str] = []
        seen: set[str] = set()
        for raw_ticker in raw_tickers:
            normalized = self._normalize_ticker(raw_ticker)
            if normalized in seen:
                continue
            seen.add(normalized)
            normalized_tickers.append(normalized)

        return normalized_tickers

    @staticmethod
    def _normalize_timestamp(
        value: str | pd.Timestamp | None, *, label: str
    ) -> pd.Timestamp | None:
        if value is None:
            return None

        try:
            timestamp = pd.Timestamp(value)
        except Exception as exc:
            raise ValueError(f"Invalid {label} value: {value}") from exc

        if timestamp.tzinfo is not None:
            timestamp = timestamp.tz_convert(None)
        return timestamp

    @staticmethod
    def _is_supported_member(member: str) -> bool:
        return member.startswith(STOOQ_ROOT) and member.endswith(STOOQ_MEMBER_SUFFIX)

    @staticmethod
    def _ticker_info_from_member(member: str) -> TickerInfo:
        parts = member.split("/")
        if len(parts) not in {5, 6}:
            raise ValueError(f"Unsupported member layout: {member}")

        exchange_and_type = parts[3]
        bucket = parts[4] if len(parts) == 6 else None
        filename = parts[5] if len(parts) == 6 else parts[4]

        exchange, instrument_folder = exchange_and_type.split(" ", maxsplit=1)
        if exchange not in {"nasdaq", "nyse", "nysemkt"}:
            raise ValueError(f"Unsupported exchange in member path: {member}")
        if instrument_folder not in _INSTRUMENT_TYPE_MAP:
            raise ValueError(f"Unsupported instrument type in member path: {member}")

        symbol_us = filename[: -len(".txt")].upper()
        if not symbol_us.endswith(".US"):
            raise ValueError(f"Unsupported filename in member path: {member}")

        symbol = symbol_us.removesuffix(".US")
        instrument_type = _INSTRUMENT_TYPE_MAP[instrument_folder]

        return TickerInfo(
            symbol=symbol,
            symbol_us=symbol_us,
            exchange=exchange,
            instrument_type=instrument_type,
            zip_member=member,
            bucket=bucket,
        )

    @staticmethod
    def _empty_price_frame() -> pd.DataFrame:
        frame = pd.DataFrame(columns=DAILY_COLUMNS)
        frame.index = pd.DatetimeIndex([], name="Date")
        return frame
