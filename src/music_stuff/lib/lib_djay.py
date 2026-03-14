import re
import sqlite3
import struct
from dataclasses import dataclass, field
from pathlib import Path

from music_stuff.lib.lib_clonefile import clonefile


@dataclass
class TsafEntity:
    type_name: str
    fields: dict[str, int | float | str | bytes] = field(default_factory=dict)
    compact: bool = False


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


_APPLE_ID_RE = re.compile(rb"\x08com\.apple\.(?:iTunes|Music):(-?\d+)\x00")


def _extract_persistent_ids(data: bytes) -> list[str]:
    """Extract Apple Music persistent IDs as hex strings from a TSAF blob."""
    result = []
    for m in _APPLE_ID_RE.finditer(data):
        value = int(m.group(1))
        if value < 0:
            value += 1 << 64
        result.append(format(value, "016X"))
    return result


def hex_id_to_djay_id(hex_id: str) -> int:
    """Convert an Apple Music hex persistent ID to a djay ID."""
    value = int(hex_id, 16)
    return value


def parse_tsaf(blob: bytes) -> list[TsafEntity]:
    """Parse a TSAF blob and return a list of entities."""
    if len(blob) < 20 or blob[:4] != b"TSAF":
        return []

    schema_registry: dict[str, list[str]] = {}
    entities: list[TsafEntity] = []

    entity_starts = [i for i, b in enumerate(blob) if b == 0x2B]
    for idx, start in enumerate(entity_starts):
        end = entity_starts[idx + 1] if idx + 1 < len(entity_starts) else len(blob)
        entity_slice = blob[start:end]

        if len(entity_slice) < 2:
            continue

        if entity_slice[1] == 0x08:
            entity = _parse_verbose_entity(entity_slice, schema_registry)
        elif entity_slice[1] == 0x05:
            entity = _parse_compact_entity(entity_slice, schema_registry)
        else:
            continue

        if entity:
            entities.append(entity)

    return entities


def _parse_verbose_entity(
    data: bytes, schema_registry: dict[str, list[str]]
) -> TsafEntity | None:
    if len(data) < 4 or data[0] != 0x2B or data[1] != 0x08:
        return None

    end_of_name = data.find(b"\x00", 2)
    if end_of_name < 0:
        return None

    type_name = data[2:end_of_name].decode("utf-8", errors="replace")
    entity = TsafEntity(type_name=type_name)

    all_markers = []
    search_start = end_of_name + 1
    while True:
        pos = data.find(b"\x08", search_start)
        if pos < 0:
            break
        end_marker = data.find(b"\x00", pos + 1)
        if end_marker < 0:
            break
        all_markers.append((pos, end_marker))
        search_start = end_marker + 1

    i = 0
    skipped = []
    while i < len(all_markers):
        marker_pos, marker_end = all_markers[i]

        prev_marker_is_value = False
        if marker_pos >= 5 and data[marker_pos - 5] in (0x0B, 0x13):
            prev_marker_is_value = True
        elif (
            marker_pos >= 6
            and data[marker_pos - 5] == 0x00
            and data[marker_pos - 6] in (0x0B, 0x13)
        ):
            prev_marker_is_value = True
        elif marker_pos >= 9 and data[marker_pos - 9] == 0x30:
            prev_marker_is_value = True
        elif (
            marker_pos >= 10
            and data[marker_pos - 10] == 0x00
            and data[marker_pos - 9] == 0x30
        ):
            prev_marker_is_value = True
        elif marker_pos >= 2 and data[marker_pos - 2] == 0x0F:
            prev_marker_is_value = True

        if i > 0 and not prev_marker_is_value:
            prev_marker_end = all_markers[i - 1][1]
            if marker_pos == prev_marker_end + 1 and not skipped[i - 1]:
                skipped.append(True)
                i += 1
                continue

        if i == 0 and not prev_marker_is_value:
            if marker_pos > 0 and data[marker_pos - 1] not in (
                0x0B,
                0x13,
                0x30,
                0x0F,
                0x00,
            ):
                skipped.append(True)
                i += 1
                continue

        skipped.append(False)

        field_name = data[marker_pos + 1 : marker_end].decode("utf-8", errors="replace")

        value = _find_verbose_value(data, marker_pos, marker_end)
        if value is not None:
            entity.fields[field_name] = value

        if type_name not in schema_registry:
            schema_registry[type_name] = []
        if field_name not in schema_registry[type_name]:
            schema_registry[type_name].append(field_name)

        i += 1

    return entity


def _find_verbose_value(
    data: bytes, marker_pos: int, marker_end: int
) -> int | float | str | bytes | None:
    if marker_pos < 2:
        return None

    if marker_pos >= 5 and data[marker_pos - 5] in (0x0B, 0x13):
        tag = data[marker_pos - 5]
        value_start = marker_pos - 4
        if tag == 0x0B:
            return struct.unpack_from("<I", data, value_start)[0]
        elif tag == 0x13:
            return struct.unpack_from("<f", data, value_start)[0]

    if (
        marker_pos >= 6
        and data[marker_pos - 5] == 0x00
        and data[marker_pos - 6] in (0x0B, 0x13)
    ):
        tag = data[marker_pos - 6]
        value_start = marker_pos - 4
        if tag == 0x0B:
            return struct.unpack_from("<I", data, value_start)[0]
        elif tag == 0x13:
            return struct.unpack_from("<f", data, value_start)[0]

    if marker_pos >= 9 and data[marker_pos - 9] == 0x30:
        return struct.unpack_from("<d", data, marker_pos - 8)[0]

    if (
        marker_pos >= 10
        and data[marker_pos - 10] == 0x00
        and data[marker_pos - 9] == 0x30
    ):
        return struct.unpack_from("<d", data, marker_pos - 8)[0]

    if marker_pos >= 2 and data[marker_pos - 2] == 0x0F:
        return data[marker_pos - 1]

    if marker_pos >= 1 and marker_end + 1 < len(data):
        next_marker = data.find(b"\x08", marker_end + 1)
        if next_marker > marker_end + 1:
            str_value = data[marker_end + 1 : next_marker]
            if b"\x00" not in str_value:
                return str_value.decode("utf-8", errors="replace")

    if (
        marker_pos >= 1
        and data[marker_pos - 1] != 0x00
        and data[marker_pos - 1] not in (0x08, 0x0B, 0x0F, 0x13, 0x30)
    ):
        return data[marker_pos - 1]

    return None


def _parse_compact_entity(
    data: bytes, schema_registry: dict[str, list[str]]
) -> TsafEntity | None:
    if len(data) < 2 or data[0] != 0x2B or data[1] != 0x05:
        return None

    markers = []
    pos = 1
    while pos < len(data):
        if data[pos] == 0x05 and pos + 1 < len(data):
            markers.append((pos, data[pos + 1]))
            pos += 2
        else:
            pos += 1

    if not markers:
        return None

    field_ids = [m[1] for m in markers if m[1] >= 0x10]
    cross_refs = [m[1] for m in markers if m[1] < 0x10]

    if not field_ids:
        return TsafEntity(type_name="", compact=True)

    type_name = ""
    field_names: list[str] = []

    schema_items = list(schema_registry.items())
    for type_n, fields in reversed(schema_items):
        if len(fields) > 0:
            potential_names = fields
            if len(potential_names) == len(set(potential_names)):
                type_name = type_n
                field_names = potential_names
                break

    entity = TsafEntity(type_name=type_name, compact=True)

    for i, field_id in enumerate(field_ids):
        if i + 1 < len(markers):
            region_start = markers[i][0] + 2
            region_end = markers[i + 1][0]
        else:
            region_start = markers[i][0] + 2
            region_end = len(data)

        region = data[region_start:region_end]
        if not region:
            continue

        type_tag = region[0]
        value = None

        if type_tag == 0x0B and len(region) >= 5:
            value = struct.unpack_from("<I", region, len(region) - 4)[0]
        elif type_tag == 0x13 and len(region) >= 5:
            value = struct.unpack_from("<f", region, len(region) - 4)[0]
        elif type_tag == 0x30 and len(region) >= 9:
            value = struct.unpack_from("<d", region, len(region) - 8)[0]
        elif type_tag == 0x0F and len(region) >= 2:
            value = region[-1]
        elif len(region) == 1:
            value = region[0]

        if value is not None:
            if i < len(field_names):
                entity.fields[field_names[i]] = value
            else:
                entity.fields[f"field_{field_id - 0x10}"] = value

    return entity


def _extract_automix_data(
    blob: bytes,
) -> tuple[float | None, float | None]:
    """
    Parse a mediaItemUserData TSAF blob and return
    (cue_start_time, cue_end_time).

    These are the precise track positions (seconds from the start) where
    the automix transition begins and ends.
    """
    parsed = parse_tsaf(blob)
    cs: float | None = None
    ct: float | None = None

    for entity in parsed:
        if entity.type_name == "ADCCuePoint":
            time_val = entity.fields.get("time")
            if isinstance(time_val, float):
                if not entity.compact:
                    ct = time_val
                elif cs is None:
                    cs = time_val

    return cs, ct


@dataclass
class DjaySongData:
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
        SELECT
            bpm_idx.bpm,
            bpm_idx.manualBPM,
            bpm_idx.keySignatureIndex,
            analyzed.data AS analyzed_blob,
            loc.data AS location_blob,
            ud.data AS ud_blob
        FROM secondaryIndex_mediaItemAnalyzedDataIndex AS bpm_idx
        JOIN database2 AS analyzed
            ON analyzed.rowid = bpm_idx.rowid
            AND analyzed.collection = 'mediaItemAnalyzedData'
        JOIN database2 AS loc
            ON loc.key = analyzed.key
            AND loc.collection = 'localMediaItemLocations'
        LEFT JOIN database2 AS ud
            ON ud.key = analyzed.key
            AND ud.collection = 'mediaItemUserData'
        WHERE bpm_idx.bpm IS NOT NULL
    """).fetchall()
    con.close()

    djay_index: dict[str, DjaySongData] = {}
    for row in rows:
        for pid in _extract_persistent_ids(bytes(row["location_blob"])):
            if pid in djay_index:
                continue
            key_index = row["keySignatureIndex"]
            analyzed_blob = bytes(row["analyzed_blob"]) if row["analyzed_blob"] else b""
            ud_blob = bytes(row["ud_blob"]) if row["ud_blob"] else b""
            cs, ct = _extract_automix_data(ud_blob)
            djay_index[pid] = DjaySongData(
                bpm=round(row["bpm"], 2) if row["bpm"] else "",
                manual_bpm=round(row["manualBPM"], 2) if row["manualBPM"] else "",
                key=DJAY_KEY_INDEX_TO_OPEN_KEY.get(key_index, ""),
                is_straight_grid=b"isStraightGrid" in analyzed_blob,
                cue_start_time=cs,
                cue_end_time=ct,
            )
    return djay_index
