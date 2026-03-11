import subprocess
from dataclasses import dataclass
from pathlib import Path

from lib_clonefile import clonefile

SOURCE_DB = Path.home() / "Library/Application Support/beaTunes/Database/beaTunes-F17A2D52DA187A20.h2.db"
DB_PATH = Path(__file__).parent / "tmp/beaTunes-F17A2D52DA187A20.h2.db"
H2_JAR = Path("/Applications/beaTunes5.app/Contents/Java/h2-1.4.195.jar")


def hex_id_to_beatunes_id(hex_id: str) -> int:
    """Convert an Apple Music hex persistent ID to a beaTunes ID."""
    value = int(hex_id, 16)
    if value >= (1 << 63):
        value -= (1 << 64)
    return value ^ (-(1 << 63))


def beatunes_id_to_hex_id(beatunes_id: int) -> str:
    """Convert a beaTunes ID to an Apple Music hex persistent ID."""
    value = beatunes_id ^ (-(1 << 63))
    if value < 0:
        value += (1 << 64)
    return format(value, "016X")


@dataclass
class BeaTunesSong:
    hex_id: str
    exactbpm: float | None
    tonalkey: int | None
    artist: str
    name: str


def _clone_db() -> None:
    """Clone the live beaTunes H2 database to DB_PATH."""
    if not SOURCE_DB.exists():
        raise FileNotFoundError(f"beaTunes database not found: {SOURCE_DB}")
    for suffix in (".lock.db", ".trace.db"):
        Path(str(DB_PATH).replace(".h2.db", suffix)).unlink(missing_ok=True)
    clonefile(SOURCE_DB, DB_PATH)


def _run_sql(sql: str) -> list[dict]:
    """Run SQL against the cloned H2 database via the H2 Shell tool."""
    # JDBC URL omits the .h2.db extension (H2 convention)
    jdbc_path = str(DB_PATH).replace(".h2.db", "")
    result = subprocess.run(
        [
            "java", "-cp", str(H2_JAR), "org.h2.tools.Shell",
            "-url", f"jdbc:h2:{jdbc_path};ACCESS_MODE_DATA=r",
            "-user", "sa", "-password", "", "-sql", sql,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return _parse_h2_output(result.stdout)


def _parse_h2_output(output: str) -> list[dict]:
    """Parse pipe-delimited H2 Shell output into a list of dicts."""
    lines = [line for line in output.strip().splitlines() if line.strip()]
    if not lines:
        return []

    headers = [h.strip() for h in lines[0].split("|")]
    rows = []
    for line in lines[1:]:
        if line.startswith("("):
            break
        values = [v.strip() for v in line.split("|")]
        rows.append(dict(zip(headers, values)))
    return rows


def lookup_songs(hex_ids: list[str]) -> dict[str, BeaTunesSong]:
    """Batch lookup songs by Apple Music hex IDs."""
    if not hex_ids:
        return {}

    _clone_db()

    id_to_hex = {}
    for hex_id in hex_ids:
        bt_id = hex_id_to_beatunes_id(hex_id)
        id_to_hex[bt_id] = hex_id

    in_clause = ", ".join(str(bt_id) for bt_id in id_to_hex)
    sql = (
        f"SELECT ID, EXACTBPM, TONALKEY, ARTIST, NAME "
        f"FROM SONGS WHERE ID IN ({in_clause})"
    )
    rows = _run_sql(sql)

    result = {}
    for row in rows:
        bt_id = int(row["ID"])
        hex_id = id_to_hex[bt_id]
        exactbpm_raw = row.get("EXACTBPM", "").strip()
        tonalkey_raw = row.get("TONALKEY", "").strip()
        result[hex_id] = BeaTunesSong(
            hex_id=hex_id,
            exactbpm=float(exactbpm_raw) if exactbpm_raw and exactbpm_raw != "null" else None,
            tonalkey=int(tonalkey_raw) if tonalkey_raw and tonalkey_raw != "null" else None,
            artist=row.get("ARTIST", "").strip(),
            name=row.get("NAME", "").strip(),
        )
    return result


def lookup_song(hex_id: str) -> BeaTunesSong | None:
    """Look up a single song by Apple Music hex ID."""
    result = lookup_songs([hex_id])
    return result.get(hex_id)
