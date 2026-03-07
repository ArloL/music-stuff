import subprocess
import json


def _run_jxa(script: str) -> str:
    result = subprocess.run(
        ["osascript", "-l", "JavaScript"],
        input=script,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


def _hex_id_to_int(hex_id: str) -> int | None:
    """Convert a hex persistent ID string to a signed 64-bit int."""
    try:
        value = int(hex_id, 16)
        if value >= (1 << 63):
            value -= (1 << 64)
        return value
    except (ValueError, TypeError):
        return None


def load_music_metadata(folder_name: str | None = None) -> dict[int, dict]:
    """
    Query the running Music app for track metadata.
    If folder_name is given, only returns tracks in that library folder.
    Returns dict mapping persistent_id (signed int) -> {name, artist, comment, bpm}.
    """
    if folder_name is not None:
        script = f"""
            const music = Application("Music");
            const folder = music.playlists.whose({{ name: {{ _equals: {json.dumps(folder_name)} }} }})[0];
            const folderID = folder.persistentID();
            const seen = new Set();
            const result = [];
            for (const pl of music.playlists()) {{
                try {{
                    if (!pl.parent || pl.parent().persistentID() !== folderID) continue;
                    for (const p of pl.tracks.properties()) {{
                        if (seen.has(p.persistentID)) continue;
                        seen.add(p.persistentID);
                        result.push({{
                            id: p.persistentID,
                            name: p.name || "",
                            artist: p.artist || "",
                            comment: p.comment || "",
                            bpm: p.bpm || 0,
                            location: p.location ? p.location.toString() : ""
                        }});
                    }}
                }} catch (e) {{}}
            }}
            JSON.stringify(result);
        """
    else:
        script = """
            const music = Application("Music");
            const result = [];
            for (const p of music.libraryPlaylists[0].tracks.properties()) {
                try {
                    result.push({
                        id: p.persistentID,
                        name: p.name || "",
                        artist: p.artist || "",
                        comment: p.comment || "",
                        bpm: p.bpm || 0,
                        location: p.location ? p.location.toString() : ""
                    });
                } catch (e) {}
            }
            JSON.stringify(result);
        """
    records = json.loads(_run_jxa(script))
    metadata: dict[int, dict] = {}
    for rec in records:
        pid = _hex_id_to_int(rec["id"])
        if pid is not None:
            metadata[pid] = {
                "name": rec["name"],
                "artist": rec["artist"],
                "comment": rec["comment"],
                "bpm": rec["bpm"] or "",
                "location": rec["location"],
            }
    return metadata
