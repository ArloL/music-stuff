import subprocess
from dataclasses import dataclass
from pathlib import Path

from lib_clonefile import clonefile

SOURCE_DB_DIR = Path.home() / "Library/Application Support/beaTunes/Database"
H2_JAR_DIR = Path("/Applications/beaTunes5.app/Contents/Java")


def _find_h2_jar() -> Path:
    """Find the H2 jar file in the beaTunes application bundle."""
    matches = sorted(H2_JAR_DIR.glob("h2-*.jar"))
    if not matches:
        raise FileNotFoundError(
            f"No H2 jar found matching h2-*.jar in {H2_JAR_DIR}"
        )
    return matches[-1]


def _find_source_db() -> Path:
    """Find the beaTunes H2 database file in the standard location."""
    matches = sorted(SOURCE_DB_DIR.glob("beaTunes-*.h2.db"))
    if not matches:
        raise FileNotFoundError(
            f"No beaTunes database found matching beaTunes-*.h2.db in {SOURCE_DB_DIR}"
        )
    return matches[-1]


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


def tonalkey_to_str(key: int | None) -> str:
    """Convert a beaTunes tonalkey integer to Open Key notation (e.g. 'Key 6d')."""
    if not key:
        return ""
    n = (key + 1) // 2
    mode = "d" if key % 2 != 0 else "m"
    return f"Key {n}{mode}"


@dataclass
class BeaTunesSong:
    hex_id: str
    exactbpm: float | None
    tonalkey: int | None
    artist: str
    name: str


def _clone_db() -> Path:
    """Clone the live beaTunes H2 database and return the clone path."""
    source_db = _find_source_db()
    db_path = Path(__file__).parent / "tmp" / source_db.name
    for suffix in (".lock.db", ".trace.db"):
        Path(str(db_path).replace(".h2.db", suffix)).unlink(missing_ok=True)
    clonefile(source_db, db_path)
    return db_path


def _run_sql(sql: str, db_path: Path) -> list[dict]:
    """Run SQL against the cloned H2 database via the H2 Shell tool."""
    # JDBC URL omits the .h2.db extension (H2 convention)
    jdbc_path = str(db_path).replace(".h2.db", "")
    result = subprocess.run(
        [
            "java", "-cp", str(_find_h2_jar()), "org.h2.tools.Shell",
            "-url", f"jdbc:h2:{jdbc_path};ACCESS_MODE_DATA=r",
            "-user", "sa", "-password", "",
        ],
        input=f"list\n{sql};\n",
        capture_output=True,
        text=True,
        check=True,
    )
    return _parse_h2_list_output(result.stdout)


def _parse_h2_list_output(output: str) -> list[dict]:
    """Parse H2 Shell list-mode output into a list of dicts.

    List mode emits one KEY: VALUE pair per line, with blank lines
    between rows and a "(N rows, ...)" trailer.
    """
    # Strip the interactive preamble (everything up to and including "sql> Result list mode is now on")
    marker = "Result list mode is now on"
    idx = output.find(marker)
    if idx != -1:
        output = output[idx + len(marker):]

    rows = []
    current: dict[str, str] = {}
    for line in output.splitlines():
        line = line.removeprefix("sql> ").rstrip()
        if line.startswith("(") or not line:
            if current:
                rows.append(current)
                current = {}
            continue
        if ": " in line:
            key, _, value = line.partition(": ")
            current[key.strip().upper()] = value.strip()
    if current:
        rows.append(current)
    return rows


def lookup_songs(hex_ids: list[str]) -> dict[str, BeaTunesSong]:
    """Batch lookup songs by Apple Music hex IDs."""
    if not hex_ids:
        return {}

    db_path = _clone_db()

    id_to_hex = {}
    for hex_id in hex_ids:
        bt_id = hex_id_to_beatunes_id(hex_id)
        id_to_hex[bt_id] = hex_id

    in_clause = ", ".join(str(bt_id) for bt_id in id_to_hex)
    sql = (
        f"SELECT ID, EXACTBPM, TONALKEY, ARTIST, NAME "
        f"FROM SONGS WHERE ID IN ({in_clause})"
    )
    rows = _run_sql(sql, db_path)

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
