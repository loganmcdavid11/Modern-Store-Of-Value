from pathlib import Path
from typing import List

DEFAULT_DATA_DIR = Path("data/data/daily/us")
DEFAULT_OUTPUT_DIR = Path("output")
DEFAULT_START_DATE = "2021-01-01"
DEFAULT_END_DATE = "2026-03-27"

EXCHANGES = [
    "nasdaq etfs", "nasdaq stocks",
    "nyse etfs", "nyse stocks", 
    "nysemkt etfs", "nysemkt stocks"
]