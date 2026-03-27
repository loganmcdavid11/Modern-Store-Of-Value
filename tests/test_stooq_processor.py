from __future__ import annotations

import unittest
import zipfile
from pathlib import Path

import pandas as pd

from scripts.stooq_processor import StooqProcessor

HEADER = "<TICKER>,<PER>,<DATE>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<VOL>,<OPENINT>\n"


def _member_text(rows: list[str]) -> str:
    return HEADER + "\n".join(rows) + "\n"


class StooqProcessorSyntheticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.zip_path = Path("tests") / "_synthetic_stooq.zip"
        cls.zip_path.unlink(missing_ok=True)

        members = {
            "data/daily/us/nasdaq stocks/1/aapl.us.txt": _member_text(
                [
                    "AAPL.US,D,20240129,000000,10,12,9,11,100,1",
                    "AAPL.US,D,20240131,000000,11,13,10,12,150,2",
                    "AAPL.US,D,20240203,000000,12,14,11,13,200,3",
                    "AAPL.US,D,20240228,000000,13,15,12,14,250,4",
                    "AAPL.US,W,20240228,000000,13,15,12,14,999,9",
                ]
            ),
            "data/daily/us/nyse etfs/2/dba.us.txt": _member_text(
                [
                    "DBA.US,D,20240110,000000,20,21,19,20.5,300,10",
                    "DBA.US,D,20240131,000000,20.5,22,20,21,400,11",
                ]
            ),
            "data/daily/us/nysemkt stocks/xyz.us.txt": _member_text(
                [
                    "XYZ.US,D,20240105,000000,5,6,4.5,5.5,50,1",
                    "XYZ.US,D,20240131,000000,5.5,6.5,5,6,75,2",
                ]
            ),
        }

        with zipfile.ZipFile(cls.zip_path, "w") as archive:
            for member, text in members.items():
                archive.writestr(member, text)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.zip_path.unlink(missing_ok=True)

    def setUp(self) -> None:
        self.processor = StooqProcessor(self.zip_path)

    def tearDown(self) -> None:
        self.processor.close()

    def test_catalog_construction_and_listing(self) -> None:
        self.assertEqual(self.processor.list_tickers(), ["AAPL", "DBA", "XYZ"])
        self.assertTrue(self.processor.has_ticker("aapl"))
        self.assertTrue(self.processor.has_ticker("DBA.US"))
        self.assertFalse(self.processor.has_ticker("missing"))

    def test_get_ticker_info_infers_metadata_from_member_path(self) -> None:
        aapl = self.processor.get_ticker_info("aapl")
        self.assertEqual(aapl.exchange, "nasdaq")
        self.assertEqual(aapl.instrument_type, "stock")
        self.assertEqual(aapl.bucket, "1")
        self.assertEqual(
            aapl.zip_member, "data/daily/us/nasdaq stocks/1/aapl.us.txt"
        )

        xyz = self.processor.get_ticker_info("XYZ")
        self.assertEqual(xyz.exchange, "nysemkt")
        self.assertEqual(xyz.instrument_type, "stock")
        self.assertIsNone(xyz.bucket)

    def test_search_tickers_filters_by_query_and_metadata(self) -> None:
        query_result = self.processor.search_tickers("a")
        self.assertEqual(query_result["symbol"].tolist(), ["AAPL", "DBA"])

        filtered = self.processor.search_tickers(
            "", exchange="nyse", instrument_type="etf"
        )
        self.assertEqual(filtered["symbol"].tolist(), ["DBA"])

    def test_download_daily_parses_and_filters_rows(self) -> None:
        result = self.processor.download(
            "aapl", start="2024-01-30", end="2024-02-15", interval="1d"
        )
        frame = result["AAPL"]

        self.assertEqual(list(result.keys()), ["AAPL"])
        self.assertEqual(frame.columns.tolist(), ["Open", "High", "Low", "Close", "Volume", "OpenInt"])
        self.assertEqual(frame.index.tolist(), [pd.Timestamp("2024-01-31"), pd.Timestamp("2024-02-03")])
        self.assertEqual(frame.loc[pd.Timestamp("2024-01-31"), "Close"], 12)
        self.assertEqual(frame.loc[pd.Timestamp("2024-02-03"), "Volume"], 200)

    def test_download_monthly_aggregates_to_month_end_ohlcv(self) -> None:
        frame = self.processor.download("AAPL", interval="1mo")["AAPL"]

        self.assertEqual(frame.index.tolist(), [pd.Timestamp("2024-01-31"), pd.Timestamp("2024-02-29")])
        self.assertEqual(frame.loc[pd.Timestamp("2024-01-31"), "Open"], 10)
        self.assertEqual(frame.loc[pd.Timestamp("2024-01-31"), "High"], 13)
        self.assertEqual(frame.loc[pd.Timestamp("2024-01-31"), "Low"], 9)
        self.assertEqual(frame.loc[pd.Timestamp("2024-01-31"), "Close"], 12)
        self.assertEqual(frame.loc[pd.Timestamp("2024-01-31"), "Volume"], 250)
        self.assertEqual(frame.loc[pd.Timestamp("2024-01-31"), "OpenInt"], 2)
        self.assertEqual(frame.loc[pd.Timestamp("2024-02-29"), "Open"], 12)
        self.assertEqual(frame.loc[pd.Timestamp("2024-02-29"), "Close"], 14)
        self.assertEqual(frame.loc[pd.Timestamp("2024-02-29"), "Volume"], 450)
        self.assertEqual(frame.loc[pd.Timestamp("2024-02-29"), "OpenInt"], 4)

    def test_download_deduplicates_tickers_while_preserving_first_seen_order(self) -> None:
        result = self.processor.download(["dba", "AAPL", "DBA"], interval="1d")
        self.assertEqual(list(result.keys()), ["DBA", "AAPL"])

    def test_download_raises_for_missing_tickers_before_loading(self) -> None:
        with self.assertRaises(KeyError) as exc:
            self.processor.download(["AAPL", "MISSING"], interval="1d")

        self.assertIn("MISSING", str(exc.exception))


@unittest.skipUnless(
    Path("data/d_us_txt.zip").exists(), "Real Stooq archive not available"
)
class StooqProcessorRealArchiveSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.processor = StooqProcessor("data/d_us_txt.zip")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.processor.close()

    def test_real_archive_contains_expected_symbols_and_metadata(self) -> None:
        self.assertTrue(self.processor.has_ticker("IBIT"))
        self.assertTrue(self.processor.has_ticker("ETHA"))
        self.assertTrue(self.processor.has_ticker("DBA"))
        self.assertTrue(self.processor.has_ticker("AAPL"))

        ibit = self.processor.get_ticker_info("IBIT")
        aapl = self.processor.get_ticker_info("AAPL")

        self.assertEqual(ibit.exchange, "nasdaq")
        self.assertEqual(ibit.instrument_type, "etf")
        self.assertEqual(aapl.exchange, "nasdaq")
        self.assertEqual(aapl.instrument_type, "stock")

    def test_real_archive_monthly_download_returns_datetime_indexed_frames(self) -> None:
        result = self.processor.download(
            ["IBIT", "AAPL"], start="2024-01-01", end="2024-03-31"
        )

        self.assertEqual(list(result.keys()), ["IBIT", "AAPL"])
        for frame in result.values():
            self.assertFalse(frame.empty)
            self.assertIsInstance(frame.index, pd.DatetimeIndex)
            self.assertEqual(frame.index.name, "Date")


if __name__ == "__main__":
    unittest.main()
