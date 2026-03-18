"""prompt_toolkit TUI for the interactive playlist builder."""
from __future__ import annotations

import datetime
import time
from pathlib import Path

import miniaudio

from prompt_toolkit import Application
from prompt_toolkit.application import get_app
from prompt_toolkit.data_structures import Point
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import HSplit, VSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension as D
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame

from music_stuff.lib.lib_apple_music import AppleMusicSong
from music_stuff.lib.lib_transitions import calculate_transition_score, get_transition_type
from music_stuff.playlist_builder import (
    AppState,
    build_initial_state,
    recompute,
    save_csv,
    select_candidate,
    undo,
    _song_dict,
)

_STYLE = Style.from_dict(
    {
        "header": "bold",
        "cursor": "reverse bold",
        "cursor-inactive": "underline ansibrightblack",
        "group-label": "bold ansiyellow",
        "dim": "ansibrightblack",
        "status": "bg:ansiblue ansiwhite",
        "frame.border": "ansibrightblack",
    }
)

_ARTIST_WIDTH = 20
_NAME_WIDTH = 22
_KEY_WIDTH = 3
_BPM_WIDTH = 4

_FOCUS_PLAYLIST = "playlist"
_FOCUS_CANDIDATES = "candidates"

# Overhead rows: header(1) + status(1) + frame borders(2) + VSplit border(0) + padding
_CHROME_ROWS = 5

_PREVIEW_START = 60.0   # seconds into the track to begin playback
_PREVIEW_SKIP  = 15.0   # seconds to jump per left/right keypress


def _bpm_delta(seed_bpm: float, cand_bpm: float) -> str:
    d = cand_bpm - seed_bpm
    if d == 0:
        return "±0"
    return f"+{int(d)}" if d > 0 else str(int(d))


def _truncate(s: str, width: int) -> str:
    if len(s) <= width:
        return s.ljust(width)
    return s[: width - 1] + "…"


def _visible_height() -> int:
    try:
        return max(get_app().output.get_size().rows - _CHROME_ROWS, 5)
    except Exception:
        return 30


def run_tui(
    initial_state: AppState | None,
    original_played_ids: set[str],
    *,
    pool: list[AppleMusicSong],
    exclude_ids: set[str],
    bpm_range: float,
    genres: set[str] | None,
    min_rating: int,
) -> None:
    state_ref: list[AppState | None] = [initial_state]
    original_played_ids_ref: list[set[str]] = [original_played_ids]
    focus_ref: list[str] = [_FOCUS_CANDIDATES]
    bpm_range_ref: list[float] = [bpm_range]

    # Each pane tracks its own scroll top (index into the pane's line list).
    cand_scroll_ref: list[int] = [0]
    pl_scroll_ref: list[int] = [0]

    # Playlist cursor (row index within history list).
    playlist_cursor_ref: list[int] = [max(len(initial_state.history) - 1, 0) if initial_state else 0]

    status_override: list[str | None] = [None]

    # Seed selection mode: pool sorted by BPM ascending, with its own cursor.
    seed_pool: list[AppleMusicSong] = sorted(pool, key=lambda s: s.bpm)
    seed_cursor_ref: list[int] = [0]

    # ------------------------------------------------------------------ preview

    preview_device:  list[miniaudio.PlaybackDevice | None] = [None]
    preview_song_id: list[str | None]                      = [None]
    preview_offset:  list[float]                           = [_PREVIEW_START]
    preview_wall:    list[float]                           = [0.0]

    def _preview_current_offset() -> float:
        if preview_device[0] is None:
            return preview_offset[0]
        return preview_offset[0] + (time.monotonic() - preview_wall[0])

    def _stop_preview() -> None:
        if preview_device[0] is not None:
            preview_device[0].stop()
            preview_device[0] = None

    def _start_preview(song, offset: float) -> None:
        _stop_preview()
        if not song.location:
            return
        offset = max(0.0, offset)
        try:
            info = miniaudio.get_file_info(song.location)
            stream = miniaudio.stream_file(
                song.location,
                output_format=miniaudio.SampleFormat.SIGNED16,
                nchannels=info.nchannels,
                sample_rate=info.sample_rate,
                seek_frame=int(offset * info.sample_rate),
            )
            device = miniaudio.PlaybackDevice(
                output_format=miniaudio.SampleFormat.SIGNED16,
                nchannels=info.nchannels,
                sample_rate=info.sample_rate,
            )
            device.start(stream)
            preview_device[0] = device
            preview_song_id[0] = song.id
            preview_offset[0] = offset
            preview_wall[0] = time.monotonic()
        except miniaudio.MiniaudioError as e:
            status_override[0] = f"Preview error: {e}"

    def _focused_song():
        state = state_ref[0]
        if state is None:
            # Seed selection mode
            if seed_pool:
                return seed_pool[seed_cursor_ref[0]]
            return None
        if focus_ref[0] == _FOCUS_CANDIDATES:
            if state.flat:
                return state.flat[state.cursor]
        else:
            idx = playlist_cursor_ref[0]
            if idx < len(state.history):
                return state.history[idx]
        return None

    def _preview_status() -> str:
        if preview_device[0] is None:
            return ""
        t = int(_preview_current_offset())
        return f"  ▶ {t // 60}:{t % 60:02d}"

    # ------------------------------------------------------------------ line builders

    def _playlist_all_lines() -> list[tuple[str, str]]:
        """All playlist rows as (style, text_no_newline)."""
        state = state_ref[0]
        if state is None:
            return [("class:dim", "  Select a seed song →")]
        lines = []
        for i, song in enumerate(state.history):
            num = f"{i + 1:>3}"
            artist = _truncate(song.artist, 18)
            name = _truncate(song.name, 18)
            bpm = f"{song.bpm:.0f}"
            key = song.key.ljust(3)
            text = f"{num}  {artist}  {name}  {bpm}  {key}"
            if i == playlist_cursor_ref[0]:
                style = "class:cursor" if focus_ref[0] == _FOCUS_PLAYLIST else "class:cursor-inactive"
            else:
                style = ""
            lines.append((style, text))
        return lines or [("", "(empty)")]

    def _candidates_all_lines() -> list[tuple[str, str]]:
        """All candidate rows as (style, text_no_newline)."""
        state = state_ref[0]
        if state is None:
            # Seed selection mode: flat BPM-sorted list, no sections
            if not seed_pool:
                return [("", "(no songs)")]
            lines: list[tuple[str, str]] = []
            for i, song in enumerate(seed_pool):
                artist = _truncate(song.artist, _ARTIST_WIDTH)
                name = _truncate(song.name, _NAME_WIDTH)
                key = song.key.ljust(_KEY_WIDTH)
                bpm = f"{song.bpm:.0f}".rjust(_BPM_WIDTH)
                if i == seed_cursor_ref[0]:
                    style = "class:cursor"
                    prefix = "▶ "
                else:
                    style = ""
                    prefix = "  "
                lines.append((style, f"{prefix}{artist}  {name}  {key} {bpm}"))
            return lines
        if not state.flat:
            return [("", "(no candidates)")]
        lines = []
        flat_idx = 0
        first_group = True
        for group_label, songs in state.grouped:
            if not first_group:
                lines.append(("", ""))
            first_group = False
            lines.append(("class:group-label", group_label))
            if not songs:
                lines.append(("class:dim", "  (none)"))
                continue
            for song in songs:
                artist = _truncate(song.artist, _ARTIST_WIDTH)
                name = _truncate(song.name, _NAME_WIDTH)
                key = song.key.ljust(_KEY_WIDTH)
                bpm = f"{song.bpm:.0f}".rjust(_BPM_WIDTH)
                delta = _bpm_delta(state.seed.bpm, song.bpm).rjust(3)
                score = round(
                    calculate_transition_score(_song_dict(state.seed), _song_dict(song))
                )
                if flat_idx == state.cursor:
                    style = "class:cursor" if focus_ref[0] == _FOCUS_CANDIDATES else "class:cursor-inactive"
                    prefix = "▶ "
                else:
                    style = ""
                    prefix = "  "
                lines.append((style, f"{prefix}{artist}  {name}  {key} {bpm}  {delta}  {score:>3}"))
                flat_idx += 1
        return lines

    def _candidates_cursor_abs() -> int:
        """Absolute line index of the selected candidate within _candidates_all_lines()."""
        state = state_ref[0]
        if state is None:
            return seed_cursor_ref[0]
        if not state.flat:
            return 0
        flat_idx = 0
        line = 0
        first_group = True
        for _, songs in state.grouped:
            if not first_group:
                line += 1  # blank separator
            first_group = False
            line += 1  # group label
            if not songs:
                line += 1  # "(none)"
                continue
            for _ in songs:
                if flat_idx == state.cursor:
                    return line
                line += 1
                flat_idx += 1
        return 0

    def _render_slice(
        all_lines: list[tuple[str, str]],
        scroll_ref: list[int],
        cursor_abs: int,
    ) -> list[tuple[str, str]]:
        """Return the visible slice of all_lines, updating scroll_ref to keep cursor_abs in view."""
        vh = _visible_height()
        top = scroll_ref[0]
        if cursor_abs < top:
            top = cursor_abs
        elif cursor_abs >= top + vh:
            top = cursor_abs - vh + 1
        top = max(0, min(top, max(len(all_lines) - vh, 0)))
        scroll_ref[0] = top
        return all_lines[top: top + vh]

    # ------------------------------------------------------------------ text functions

    def _fmt_playlist():
        all_lines = _playlist_all_lines()
        cursor_abs = playlist_cursor_ref[0]
        visible = _render_slice(all_lines, pl_scroll_ref, cursor_abs)
        return [(s, t + "\n") for s, t in visible] or [("", "\n")]

    def _fmt_candidates():
        all_lines = _candidates_all_lines()
        cursor_abs = _candidates_cursor_abs()
        visible = _render_slice(all_lines, cand_scroll_ref, cursor_abs)
        return [(s, t + "\n") for s, t in visible] or [("", "\n")]

    def _fmt_header() -> str:
        state = state_ref[0]
        if state is None:
            return f" Select seed song{_preview_status()}"
        seed = state.seed
        ttype = ""
        if len(state.history) >= 2:
            prev = state.history[-2]
            ttype = get_transition_type(_song_dict(prev), _song_dict(seed))
        extra = f"  [{ttype}]" if ttype else ""
        return f" Now: {seed.artist} – {seed.name}  [{seed.bpm:.0f} BPM  {seed.key}]{extra}{_preview_status()}"

    def _fmt_status() -> str:
        if status_override[0]:
            return f"  {status_override[0]}"
        bpm_r = bpm_range_ref[0]
        if state_ref[0] is None:
            return f"  ↑/↓ navigate  Enter select seed  p preview  ←/→ seek  q quit         {len(seed_pool)} songs  "
        n = len(state_ref[0].flat)
        if focus_ref[0] == _FOCUS_PLAYLIST:
            return f"  ↑/↓ navigate  p preview  ←/→ seek  Tab switch  u undo  s save  q quit         ±{bpm_r:.0f} BPM  "
        return f"  ↑/↓ navigate  Enter select  p preview  ←/→ seek  Tab switch  u undo  s save  +/- BPM range  q quit         {n} candidates  ±{bpm_r:.0f} BPM  "

    # ------------------------------------------------------------------ widgets

    header_win = Window(
        content=FormattedTextControl(text=_fmt_header),
        height=1,
        style="class:header",
    )

    # get_cursor_position always returns a position within the rendered slice
    playlist_ctrl = FormattedTextControl(
        text=_fmt_playlist,
        get_cursor_position=lambda: Point(
            x=0,
            y=max(0, min(playlist_cursor_ref[0] - pl_scroll_ref[0], _visible_height() - 1)),
        ),
    )
    playlist_win = Window(content=playlist_ctrl, wrap_lines=False)
    left_frame = Frame(body=playlist_win, title="Playlist", width=D(preferred=36))

    candidates_ctrl = FormattedTextControl(
        text=_fmt_candidates,
        get_cursor_position=lambda: Point(
            x=0,
            y=max(0, min(_candidates_cursor_abs() - cand_scroll_ref[0], _visible_height() - 1)),
        ),
    )
    candidates_win = Window(content=candidates_ctrl, wrap_lines=False)
    right_frame = Frame(body=candidates_win, title="Candidates")

    status_win = Window(
        content=FormattedTextControl(text=_fmt_status),
        height=1,
        style="class:status",
    )

    layout = Layout(
        HSplit([header_win, VSplit([left_frame, right_frame]), status_win]),
        focused_element=candidates_win,
    )

    # ------------------------------------------------------------------ keys

    kb = KeyBindings()

    @kb.add("tab")
    def _switch_focus(_event):
        if state_ref[0] is None:
            return  # no tab in seed selection mode
        if focus_ref[0] == _FOCUS_CANDIDATES:
            focus_ref[0] = _FOCUS_PLAYLIST
            playlist_cursor_ref[0] = max(len(state_ref[0].history) - 1, 0)
        else:
            focus_ref[0] = _FOCUS_CANDIDATES
        status_override[0] = None
        _maybe_switch_preview()
        app.invalidate()

    def _maybe_switch_preview() -> None:
        """If a preview is active, restart it for the newly focused song."""
        if preview_device[0] is not None:
            song = _focused_song()
            if song and song.id != preview_song_id[0]:
                _start_preview(song, _PREVIEW_START)

    @kb.add("up")
    @kb.add("k")
    def _up(_event):
        status_override[0] = None
        state = state_ref[0]
        if state is None:
            n = len(seed_pool)
            if n:
                seed_cursor_ref[0] = (seed_cursor_ref[0] - 1) % n
        elif focus_ref[0] == _FOCUS_PLAYLIST:
            playlist_cursor_ref[0] = max(playlist_cursor_ref[0] - 1, 0)
        else:
            n = len(state.flat)
            if n:
                state.cursor = (state.cursor - 1) % n
        _maybe_switch_preview()
        app.invalidate()

    @kb.add("down")
    @kb.add("j")
    def _down(_event):
        status_override[0] = None
        state = state_ref[0]
        if state is None:
            n = len(seed_pool)
            if n:
                seed_cursor_ref[0] = (seed_cursor_ref[0] + 1) % n
        elif focus_ref[0] == _FOCUS_PLAYLIST:
            playlist_cursor_ref[0] = min(
                playlist_cursor_ref[0] + 1, len(state.flat) - 1
            )
        else:
            n = len(state.flat)
            if n:
                state.cursor = (state.cursor + 1) % n
        _maybe_switch_preview()
        app.invalidate()

    @kb.add("enter")
    def _select(_event):
        state = state_ref[0]
        if state is None:
            # Seed selection mode: select seed and enter normal mode
            if not seed_pool:
                return
            seed = seed_pool[seed_cursor_ref[0]]
            new_state = build_initial_state(
                seed=seed,
                pool=pool,
                exclude_ids=exclude_ids,
                bpm_range=bpm_range_ref[0],
                genres=genres,
                min_rating=min_rating,
            )
            state_ref[0] = new_state
            original_played_ids_ref[0] = exclude_ids | {seed.id}
            playlist_cursor_ref[0] = 0
            cand_scroll_ref[0] = 0
            status_override[0] = None
            app.invalidate()
            return
        if focus_ref[0] != _FOCUS_CANDIDATES:
            return
        if not state.flat:
            return
        song = state.flat[state.cursor]
        state_ref[0] = select_candidate(state, song)
        playlist_cursor_ref[0] = len(state_ref[0].history) - 1
        status_override[0] = None
        _maybe_switch_preview()
        app.invalidate()

    @kb.add("u")
    def _undo(_event):
        state = state_ref[0]
        if state is None:
            return
        if len(state.history) <= 1:
            # Back to seed selection mode
            state_ref[0] = None
            original_played_ids_ref[0] = exclude_ids
            cand_scroll_ref[0] = 0
            pl_scroll_ref[0] = 0
            status_override[0] = None
            app.invalidate()
            return
        state_ref[0] = undo(state, original_played_ids_ref[0])
        playlist_cursor_ref[0] = max(len(state_ref[0].history) - 1, 0)
        status_override[0] = None
        app.invalidate()

    @kb.add("s")
    def _save(_event):
        state = state_ref[0]
        if state is None:
            return
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = Path(f"playlist_{ts}.csv")
        save_csv(state, path)
        status_override[0] = f"Saved → {path}  (any key to dismiss)"
        app.invalidate()

    @kb.add("p")
    def _toggle_preview(_event):
        song = _focused_song()
        if song is None:
            return
        if preview_song_id[0] == song.id and preview_device[0] is not None:
            _stop_preview()
        else:
            _start_preview(song, _PREVIEW_START)
        app.invalidate()

    @kb.add("left")
    def _seek_back(_event):
        if preview_device[0] is not None:
            song = _focused_song()
            if song:
                _start_preview(song, _preview_current_offset() - _PREVIEW_SKIP)
        app.invalidate()

    @kb.add("right")
    def _seek_forward(_event):
        if preview_device[0] is not None:
            song = _focused_song()
            if song:
                _start_preview(song, _preview_current_offset() + _PREVIEW_SKIP)
        app.invalidate()

    @kb.add("+")
    @kb.add("=")
    def _bpm_range_up(_event):
        bpm_range_ref[0] += 1
        state = state_ref[0]
        if state is not None:
            state.bpm_range = bpm_range_ref[0]
            recompute(state)
        status_override[0] = None
        app.invalidate()

    @kb.add("-")
    def _bpm_range_down(_event):
        if bpm_range_ref[0] > 1:
            bpm_range_ref[0] -= 1
            state = state_ref[0]
            if state is not None:
                state.bpm_range = bpm_range_ref[0]
                recompute(state)
        status_override[0] = None
        app.invalidate()

    @kb.add("q")
    @kb.add("c-c")
    def _quit(_event):
        _stop_preview()
        app.exit()

    app = Application(
        layout=layout,
        key_bindings=kb,
        style=_STYLE,
        full_screen=True,
        mouse_support=False,
    )
    app.run()
