import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from lib_clonefile import clonefile

SOURCE_DB = Path.home() / "Music/djay/djay Media Library.djayMediaLibrary/MediaLibrary.db"
DB_PATH = Path(__file__).parent / "tmp/djay-MediaLibrary.db"

DJAY_KEY_INDEX_TO_OPEN_KEY = {
    0: "1d",  1: "1m",
    2: "8d",  3: "8m",
    4: "3d",  5: "3m",
    6: "10d", 7: "10m",
    8: "5d",  9: "5m",
    10: "12d", 11: "12m",
    12: "7d", 13: "7m",
    14: "2d", 15: "2m",
    16: "9d", 17: "9m",
    18: "4d", 19: "4m",
    20: "11d", 21: "11m",
    22: "6d", 23: "6m",
}


def _clone_db() -> None:
    """Clone the live djay MediaLibrary.db (and WAL/SHM files) to DB_PATH."""
    if not SOURCE_DB.exists():
        raise FileNotFoundError(f"djay database not found: {SOURCE_DB}")
    clonefile(SOURCE_DB, DB_PATH)
    for suffix in ("-wal", "-shm"):
        src = Path(str(SOURCE_DB) + suffix)
        if src.exists():
            clonefile(src, Path(str(DB_PATH) + suffix))


_APPLE_ID_RE = re.compile(rb'\x08com\.apple\.(?:iTunes|Music):(-?\d+)\x00')


def _extract_persistent_ids(data: bytes) -> list[str]:
    """Extract Apple Music persistent IDs as hex strings from a TSAF blob."""
    result = []
    for m in _APPLE_ID_RE.finditer(data):
        value = int(m.group(1))
        if value < 0:
            value += (1 << 64)
        result.append(format(value, "016X"))
    return result


@dataclass
class DjaySongData:
    bpm: float | str
    manual_bpm: float | str
    open_key: str


def load_djay_index() -> dict[str, DjaySongData]:
    """
    Clone the live djay MediaLibrary.db then query it, returning a dict mapping
    persistent_id -> DjaySongData for songs in the library.
    """
    _clone_db()
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = con.execute("""
        SELECT
            bpm_idx.bpm,
            bpm_idx.manualBPM,
            bpm_idx.keySignatureIndex,
            loc.data AS location_blob
        FROM secondaryIndex_mediaItemAnalyzedDataIndex AS bpm_idx
        JOIN database2 AS analyzed
            ON analyzed.rowid = bpm_idx.rowid
            AND analyzed.collection = 'mediaItemAnalyzedData'
        JOIN database2 AS loc
            ON loc.key = analyzed.key
            AND loc.collection = 'localMediaItemLocations'
        WHERE bpm_idx.bpm IS NOT NULL
    """).fetchall()
    con.close()

    djay_index: dict[str, DjaySongData] = {}
    for row in rows:
        for pid in _extract_persistent_ids(bytes(row["location_blob"])):
            if pid in djay_index:
                continue
            key_index = row["keySignatureIndex"]
            djay_index[pid] = DjaySongData(
                bpm=round(row["bpm"], 2) if row["bpm"] else "",
                manual_bpm=round(row["manualBPM"], 2) if row["manualBPM"] else "",
                open_key=("Key " + DJAY_KEY_INDEX_TO_OPEN_KEY[key_index]) if key_index in DJAY_KEY_INDEX_TO_OPEN_KEY else "",
            )
    return djay_index
