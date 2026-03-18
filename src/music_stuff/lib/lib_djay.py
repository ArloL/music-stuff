import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from music_stuff.lib.lib_clonefile import clonefile
from music_stuff.lib.lib_tsaf_parser import (
    CompactEntity,
    TSAFParseError,
    VerboseEntity,
    parse_media_item_user_data,
    parse_tsaf as _tsaf_parse,
)


SOURCE_DB = (
    Path.home() / "Music/djay/djay Media Library.djayMediaLibrary/MediaLibrary.db"
)
DB_PATH = Path(__file__).parent.parent.parent.parent / "tmp/djay-MediaLibrary.db"

DJAY_KEY_INDEX_TO_OPEN_KEY = {
    0: "1d",
    1: "1m",
    2: "8d",
    3: "8m",
    4: "3d",
    5: "3m",
    6: "10d",
    7: "10m",
    8: "5d",
    9: "5m",
    10: "12d",
    11: "12m",
    12: "7d",
    13: "7m",
    14: "2d",
    15: "2m",
    16: "9d",
    17: "9m",
    18: "4d",
    19: "4m",
    20: "11d",
    21: "11m",
    22: "6d",
    23: "6m",
}


def _clone_db() -> None:
    """Clone the live djay MediaLibrary.db (and WAL/SHM files) to DB_PATH."""
    if not SOURCE_DB.exists():
        raise FileNotFoundError(f"djay database not found: {SOURCE_DB}")
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    clonefile(SOURCE_DB, DB_PATH)
    for suffix in ("-wal", "-shm"):
        src = Path(str(SOURCE_DB) + suffix)
        if src.exists():
            clonefile(src, Path(str(DB_PATH) + suffix))


def _parse_apple_music_hex_id(data: bytes) -> str | None:
    """Parse a dlmil TSAF blob and return the Apple Music persistent ID as a 16-char hex string.

    Returns None if the data is not a valid TSAF document or contains no Apple Music ID.
    Handles both positive and negative (two's-complement) ID values.
    """
    try:
        doc = _tsaf_parse(data)
    except TSAFParseError:
        return None
    for entity in doc.entities:
        if not isinstance(entity, (VerboseEntity, CompactEntity)):
            continue
        for f in entity.fields:
            if not isinstance(f.value, list):
                continue
            for item in f.value:
                if not isinstance(item, str):
                    continue
                for prefix in ("com.apple.iTunes:", "com.apple.Music:"):
                    if item.startswith(prefix):
                        raw = item[len(prefix):]
                        try:
                            value = int(raw)
                            if value < 0:
                                value += 1 << 64
                            return format(value, "016X")
                        except ValueError:
                            pass
    return None


def _has_straight_grid(data: bytes) -> bool:
    """Return True if the TSAF blob contains an entity with an isStraightGrid field."""
    if not data:
        return False
    try:
        doc = _tsaf_parse(data)
        for entity in doc.entities:
            if isinstance(entity, (VerboseEntity, CompactEntity)):
                for f in entity.fields:
                    if f.name == "isStraightGrid":
                        return True
    except TSAFParseError:
        pass
    return False


def hex_id_to_djay_id(hex_id: str) -> int:
    """Convert an Apple Music hex persistent ID to a djay ID."""
    value = int(hex_id, 16)
    return value


@dataclass
class DjaySongData:
    id: str
    bpm: float | str
    manual_bpm: float | str
    key: str
    is_straight_grid: bool | str
    cue_start_time: float | None  # seconds from track start where transition begins
    cue_end_time: float | None  # seconds from track start where transition ends


def load_djay_index() -> dict[str, DjaySongData]:
    """
    Clone the live djay MediaLibrary.db then query it, returning a dict mapping
    persistent_id -> DjaySongData for songs in the library.
    """
    _clone_db()
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = con.execute("""
        select
            dlmil.key as id,
            simiadi.bpm as bpm,
            simiadi.keySignatureIndex as keyIndex,
            simiudi.manualBPM as manualBpm,
            dmiad.data AS dmiad_data,
            dlmil.data AS dlmil_data,
            dmiud.data AS dmiud_data
        from database2 dlmil
        left join database2 as dmiad
            on dmiad.key = dlmil.key
            and dmiad.collection = 'mediaItemAnalyzedData'
        left join database2 AS dmiud
            on dmiud.key = dlmil.key
            and dmiud.collection = 'mediaItemUserData'
        left join secondaryIndex_mediaItemAnalyzedDataIndex simiadi
            on  simiadi.rowid = dmiad.rowid
        left join secondaryIndex_mediaItemUserDataIndex AS simiudi
            on simiudi.rowid = dmiud.rowid
        where dlmil.collection = 'localMediaItemLocations'
        and instr(dlmil.data, 'com.apple.iTunes') > 0
    """).fetchall()
    con.close()

    djay_index: dict[str, DjaySongData] = {}
    for row in rows:
        dlmil_data = bytes(row["dlmil_data"]) if row["dlmil_data"] else b""
        pid = _parse_apple_music_hex_id(dlmil_data)
        if pid is None or pid in djay_index:
            continue
        key = DJAY_KEY_INDEX_TO_OPEN_KEY.get(row["keyIndex"], "")
        dmiad_data = bytes(row["dmiad_data"]) if row["dmiad_data"] else b""
        dmiud_data = bytes(row["dmiud_data"]) if row["dmiud_data"] else b""
        cs: float | None = None
        ct: float | None = None
        if dmiud_data:
            try:
                ud = parse_media_item_user_data(dmiud_data)
                cs = ud.automix_start_point
                ct = ud.automix_end_point
            except TSAFParseError:
                pass
        djay_index[pid] = DjaySongData(
            id=row["id"],
            bpm=round(row["bpm"], 2) if row["bpm"] else "",
            manual_bpm=round(row["manualBpm"], 2) if row["manualBpm"] else "",
            key=key,
            is_straight_grid=_has_straight_grid(dmiad_data),
            cue_start_time=cs,
            cue_end_time=ct,
        )
    return djay_index
