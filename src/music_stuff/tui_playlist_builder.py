"""prompt_toolkit TUI for the interactive playlist builder."""

from __future__ import annotations

import datetime
import threading
import time

import miniaudio
from prompt_toolkit import Application
from prompt_toolkit.application import get_app
from prompt_toolkit.data_structures import Point
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import (
    ConditionalKeyBindings,
    KeyBindings,
    merge_key_bindings,
)
from prompt_toolkit.layout.containers import (
    ConditionalContainer,
    HSplit,
    VSplit,
    Window,
)
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension as D
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame, TextArea

from music_stuff.lib.lib_apple_music import AppleMusicSong
from music_stuff.lib.lib_transitions import (
    calculate_transition_score,
    get_transition_type,
)
from music_stuff.playlist_builder import (
    AppState,
    _song_dict,
    build_initial_state,
    hide_candidate,
    playlist_duration,
    recompute,
    save_apple_music,
    select_candidate,
    undo,
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

_PREVIEW_START = 60.0  # seconds into the track to begin playback
_PREVIEW_SKIP = 15.0  # seconds to jump per left/right keypress


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


def _fmt_duration(seconds: float) -> str:
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}h{m:02d}m"
    return f"{m}m{sec:02d}s"


def run_tui(
    initial_state: AppState | None,
    original_played_ids: set[str],
    *,
    pool: list[AppleMusicSong],
    exclude_ids: set[str],
    bpm_range: float,
    genres: set[str] | None,
    min_rating: int,
    djay_index: dict | None = None,
    hidden_ids: set[str] | None = None,
) -> None:
    state_ref: list[AppState | None] = [initial_state]
    original_played_ids_ref: list[set[str]] = [original_played_ids]
    focus_ref: list[str] = [_FOCUS_CANDIDATES]
    bpm_range_ref: list[float] = [bpm_range]

    # Each pane tracks its own scroll top (index into the pane's line list).
    cand_scroll_ref: list[int] = [0]
    pl_scroll_ref: list[int] = [0]

    # Playlist cursor (row index within history list).
    playlist_cursor_ref: list[int] = [
        max(len(initial_state.history) - 1, 0) if initial_state else 0
    ]

    status_override: list[str | None] = [None]

    # Inline playlist-name prompt: a single-line TextArea (created below in the
    # widgets section) shown only while saving. input_mode_ref gates the main
    # key bindings off so editing keys reach the TextArea.
    input_mode_ref: list[bool] = [False]

    # Seed selection mode: pool sorted by BPM ascending, with its own cursor.
    seed_pool: list[AppleMusicSong] = sorted(pool, key=lambda s: s.bpm)
    seed_cursor_ref: list[int] = [0]

    # Session-only hidden songs (h key). Shared by reference with every AppState
    # so a hide survives selecting, undoing, and reseeding. Also filters the
    # seed-selection list below.
    hidden_ids_ref: list[set[str]] = [hidden_ids if hidden_ids is not None else set()]

    def _visible_seed_pool() -> list[AppleMusicSong]:
        """Seed-selection list with hidden songs removed."""
        return [s for s in seed_pool if s.id not in hidden_ids_ref[0]]

    # Confirm-hide prompt state: while active the main key bindings are gated
    # off and a y/n prompt is shown in the status bar.
    confirm_mode_ref: list[bool] = [False]
    confirm_target_ref: list[AppleMusicSong | None] = [None]

    # ------------------------------------------------------------------ preview

    preview_device: list[miniaudio.PlaybackDevice | None] = [None]
    preview_song_id: list[str | None] = [None]
    preview_offset: list[float] = [_PREVIEW_START]
    preview_wall: list[float] = [0.0]
    _ticker_stop: list[bool] = [False]
    _preview_timer: list[threading.Timer | None] = [None]
    # Whether the user has previewing turned on (p key). Track selection only
    # follows the cursor while this is True. Kept separate from preview_device
    # so a momentarily-stopped device (mid-restart) doesn't disable following.
    preview_enabled: list[bool] = [False]
    # Serialises device start/stop so overlapping restarts (a debounce timer
    # firing while a seek keypress also restarts) can never leave two audio
    # devices playing at once. Navigation does not touch this lock, so row
    # rendering stays snappy.
    _preview_lock = threading.RLock()

    def _cancel_preview_timer() -> None:
        if _preview_timer[0] is not None:
            _preview_timer[0].cancel()
            _preview_timer[0] = None

    def _preview_start_for(song: AppleMusicSong) -> float:
        djay = (djay_index or {}).get(song.id)
        if djay and djay.cue_start_time is not None:
            return djay.cue_start_time + 60.0
        return _PREVIEW_START

    def _start_ticker() -> None:
        _ticker_stop[0] = False

        def _tick() -> None:
            while not _ticker_stop[0]:
                time.sleep(1.0)
                if not _ticker_stop[0]:
                    app.invalidate()

        threading.Thread(target=_tick, daemon=True).start()

    def _stop_ticker() -> None:
        _ticker_stop[0] = True

    # Channel mode: "stereo" | "left" | "right"
    _CHANNEL_MODES = ["stereo", "left", "right"]
    channel_mode_ref: list[str] = ["right"]

    def _apply_channel_routing(stream, mode: str):
        """Wrap a pre-primed stereo SIGNED16 miniaudio stream, mixing to mono and routing to the selected channel.

        Mirrors miniaudio's generator protocol: yield b"" to prime, then receive
        framecount via send() and yield the (possibly modified) chunk.
        """
        import array as _array

        required_frames = yield b""  # initialization yield — mirrors stream_file
        while True:
            try:
                chunk = stream.send(required_frames)
            except StopIteration:
                return
            if mode != "stereo" and chunk:
                samples = _array.array("h", chunk)
                # interleaved stereo: even indices = left, odd = right
                # Mix to mono and route to selected channel only
                for i in range(0, len(samples), 2):
                    left = samples[i]
                    right = samples[i + 1]
                    mono = (left + right) // 2
                    if mode == "left":
                        samples[i] = mono
                        samples[i + 1] = 0
                    else:  # right
                        samples[i] = 0
                        samples[i + 1] = mono
                chunk = samples.tobytes()
            required_frames = yield chunk

    def _preview_current_offset() -> float:
        if preview_device[0] is None:
            return preview_offset[0]
        return preview_offset[0] + (time.monotonic() - preview_wall[0])

    def _stop_playback() -> None:
        """Stop the audio device and ticker, but leave any pending debounce
        timer alone — a firing timer must not cancel a newer scheduled one."""
        with _preview_lock:
            _stop_ticker()
            if preview_device[0] is not None:
                preview_device[0].stop()
                preview_device[0] = None

    def _stop_preview() -> None:
        _cancel_preview_timer()
        _stop_playback()

    def _start_preview(song, offset: float) -> None:
        # Held across the whole start so a concurrent restart waits its turn
        # and stops this device before starting its own — never two at once.
        with _preview_lock:
            _stop_playback()
            if not song.location:
                return
            offset = max(0.0, offset)
            try:
                info = miniaudio.get_file_info(song.location)
                stream = miniaudio.stream_file(
                    song.location,
                    output_format=miniaudio.SampleFormat.SIGNED16,
                    nchannels=2,
                    sample_rate=info.sample_rate,
                    seek_frame=int(offset * info.sample_rate),
                )
                stream = _apply_channel_routing(stream, channel_mode_ref[0])
                next(stream)  # prime: consume the b"" initialization yield
                device = miniaudio.PlaybackDevice(
                    output_format=miniaudio.SampleFormat.SIGNED16,
                    nchannels=2,
                    sample_rate=info.sample_rate,
                )
                device.start(stream)
                preview_device[0] = device
                preview_song_id[0] = song.id
                preview_offset[0] = offset
                preview_wall[0] = time.monotonic()
                _start_ticker()
            except miniaudio.MiniaudioError as e:
                status_override[0] = f"Preview error: {e}"

    def _focused_song():
        state = state_ref[0]
        if state is None:
            # Seed selection mode
            visible = _visible_seed_pool()
            if visible:
                idx = min(seed_cursor_ref[0], len(visible) - 1)
                return visible[idx]
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
        mode = channel_mode_ref[0]
        ch = {"stereo": "stereo", "left": "L", "right": "R"}[mode]
        return f"  ▶ {t // 60}:{t % 60:02d} [{ch}]"

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
                style = (
                    "class:cursor"
                    if focus_ref[0] == _FOCUS_PLAYLIST
                    else "class:cursor-inactive"
                )
            else:
                style = ""
            lines.append((style, text))
        return lines or [("", "(empty)")]

    def _candidates_all_lines() -> list[tuple[str, str]]:
        """All candidate rows as (style, text_no_newline)."""
        state = state_ref[0]
        if state is None:
            # Seed selection mode: flat BPM-sorted list, no sections
            visible = _visible_seed_pool()
            if not visible:
                return [("", "(no songs)")]
            lines: list[tuple[str, str]] = []
            for i, song in enumerate(visible):
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
                    style = (
                        "class:cursor"
                        if focus_ref[0] == _FOCUS_CANDIDATES
                        else "class:cursor-inactive"
                    )
                    prefix = "▶ "
                else:
                    style = ""
                    prefix = "  "
                lines.append(
                    (
                        style,
                        f"{prefix}{artist}  {name}  {key} {bpm}  {delta}  {score:>3}",
                    )
                )
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
        return all_lines[top : top + vh]

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
        dur = playlist_duration(state.history, djay_index or {})
        dur_str = f"  {_fmt_duration(dur)}" if dur > 0 else ""
        return f" Now: {seed.artist} – {seed.name}  [{seed.bpm:.0f} BPM  {seed.key}]{extra}{dur_str}{_preview_status()}"

    def _fmt_status() -> str:
        if confirm_mode_ref[0]:
            target = confirm_target_ref[0]
            if target is not None:
                return f"  Hide {target.artist} – {target.name}?  y/n"
        if input_mode_ref[0]:
            return "  Enter save · Esc cancel"
        if status_override[0]:
            return f"  {status_override[0]}"
        bpm_r = bpm_range_ref[0]
        if state_ref[0] is None:
            return f"  ↑/↓ navigate  Enter select seed  p preview  c channel  ←/→ seek  h hide  q quit         {len(_visible_seed_pool())} songs  "
        n = len(state_ref[0].flat)
        if focus_ref[0] == _FOCUS_PLAYLIST:
            return f"  ↑/↓ navigate  p preview  c channel  ←/→ seek  Tab switch  u undo  s save→Music  q quit         ±{bpm_r:.0f} BPM  "
        return f"  ↑/↓ navigate  Enter select  p preview  c channel  ←/→ seek  Tab switch  u undo  h hide  s save→Music  +/- BPM  q quit         {n} candidates  ±{bpm_r:.0f} BPM  "

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
            y=max(
                0, min(playlist_cursor_ref[0] - pl_scroll_ref[0], _visible_height() - 1)
            ),
        ),
    )
    playlist_win = Window(content=playlist_ctrl, wrap_lines=False)
    left_frame = Frame(body=playlist_win, title="Playlist", width=D(preferred=36))

    candidates_ctrl = FormattedTextControl(
        text=_fmt_candidates,
        get_cursor_position=lambda: Point(
            x=0,
            y=max(
                0,
                min(
                    _candidates_cursor_abs() - cand_scroll_ref[0], _visible_height() - 1
                ),
            ),
        ),
    )
    candidates_win = Window(content=candidates_ctrl, wrap_lines=False)
    right_frame = Frame(body=candidates_win, title="Candidates")

    status_win = Window(
        content=FormattedTextControl(text=_fmt_status),
        height=1,
        style="class:status",
    )

    def _do_save(name: str) -> None:
        state = state_ref[0]
        if state is None:
            return
        try:
            result = save_apple_music(state, name)
        except Exception as e:
            status_override[0] = f"Apple Music error: {e}  (any key to dismiss)"
            app.invalidate()
            return
        count = result.get("trackCount", len(state.history))
        status_override[0] = (
            f"Saved {count} tracks → “{name}” in Apple Music  (any key to dismiss)"
        )
        app.invalidate()

    def _accept_name(_buffer) -> bool:
        name = name_input.text.strip()
        _exit_input_mode()
        if not name:
            status_override[0] = "Save cancelled (empty name)"
            app.invalidate()
        else:
            _do_save(name)
        return False  # clear the buffer for next time

    name_input = TextArea(
        multiline=False,
        prompt="Playlist name: ",
        accept_handler=_accept_name,
        style="class:status",
    )
    name_input_container = ConditionalContainer(
        content=name_input,
        filter=Condition(lambda: input_mode_ref[0]),
    )

    def _exit_input_mode() -> None:
        input_mode_ref[0] = False
        app.layout.focus(candidates_win)

    layout = Layout(
        HSplit(
            [
                header_win,
                VSplit([left_frame, right_frame]),
                name_input_container,
                status_win,
            ]
        ),
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
        """If previewing is enabled, debounce-restart it for the newly focused song."""
        if not preview_enabled[0]:
            return
        song = _focused_song()
        if song is None:
            return
        _cancel_preview_timer()  # always drop any stale pending timer
        if song.id == preview_song_id[0] and preview_device[0] is not None:
            return  # focused song is already playing

        def _fire() -> None:
            # Runs on the timer's own thread so the slow audio-file load never
            # blocks UI rendering. Skip if a newer timer has superseded this one.
            if _preview_timer[0] is not timer:
                return
            _preview_timer[0] = None
            _start_preview(song, _preview_start_for(song))
            app.invalidate()

        timer = threading.Timer(0.15, _fire)
        timer.daemon = True
        _preview_timer[0] = timer
        timer.start()

    @kb.add("up")
    @kb.add("k")
    def _up(_event):
        status_override[0] = None
        state = state_ref[0]
        if state is None:
            n = len(_visible_seed_pool())
            if n:
                seed_cursor_ref[0] = (min(seed_cursor_ref[0], n - 1) - 1) % n
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
            n = len(_visible_seed_pool())
            if n:
                seed_cursor_ref[0] = (min(seed_cursor_ref[0], n - 1) + 1) % n
        elif focus_ref[0] == _FOCUS_PLAYLIST:
            playlist_cursor_ref[0] = min(
                playlist_cursor_ref[0] + 1, len(state.history) - 1
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
            visible = _visible_seed_pool()
            if not visible:
                return
            seed = visible[min(seed_cursor_ref[0], len(visible) - 1)]
            new_state = build_initial_state(
                seed=seed,
                pool=pool,
                exclude_ids=exclude_ids,
                bpm_range=bpm_range_ref[0],
                genres=genres,
                min_rating=min_rating,
                hidden_ids=hidden_ids_ref[0],
            )
            state_ref[0] = new_state
            original_played_ids_ref[0] = exclude_ids | {seed.id}
            playlist_cursor_ref[0] = 0
            cand_scroll_ref[0] = 0
            status_override[0] = None
            _maybe_switch_preview()
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
            _maybe_switch_preview()
            app.invalidate()
            return
        state_ref[0] = undo(state, original_played_ids_ref[0])
        playlist_cursor_ref[0] = max(len(state_ref[0].history) - 1, 0)
        status_override[0] = None
        _maybe_switch_preview()
        app.invalidate()

    @kb.add("h")
    def _hide(_event):
        # Only meaningful for a focused candidate or a seed-selection row; a
        # song already in the playlist can't be "not shown again".
        if state_ref[0] is not None and focus_ref[0] != _FOCUS_CANDIDATES:
            return
        song = _focused_song()
        if song is None:
            return
        confirm_target_ref[0] = song
        confirm_mode_ref[0] = True
        status_override[0] = None
        app.invalidate()

    @kb.add("s")
    def _save(_event):
        if state_ref[0] is None:
            return
        # Open the inline name prompt, pre-filled with a timestamped default and
        # the cursor at the end so the user can edit or just hit Enter.
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        name_input.text = f"DJ Set {ts}"
        name_input.buffer.cursor_position = len(name_input.text)
        input_mode_ref[0] = True
        status_override[0] = None
        app.layout.focus(name_input)
        app.invalidate()

    @kb.add("p")
    def _toggle_preview(_event):
        song = _focused_song()
        if song is None:
            return
        if preview_song_id[0] == song.id and preview_device[0] is not None:
            preview_enabled[0] = False
            _stop_preview()
        else:
            preview_enabled[0] = True
            _start_preview(song, _preview_start_for(song))
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

    @kb.add("c")
    def _cycle_channel(_event):
        cur = channel_mode_ref[0]
        channel_mode_ref[0] = _CHANNEL_MODES[
            (_CHANNEL_MODES.index(cur) + 1) % len(_CHANNEL_MODES)
        ]
        # Restart preview on the new channel if active
        if preview_device[0] is not None:
            song = _focused_song()
            if song:
                _start_preview(song, _preview_current_offset())
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
        _maybe_switch_preview()
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
        _maybe_switch_preview()
        app.invalidate()

    @kb.add("q")
    @kb.add("c-c")
    def _quit(_event):
        _stop_preview()
        app.exit()

    # ------------------------------------------------------------------ name prompt
    # While the name prompt is open the main bindings above are suppressed, so
    # text editing keys reach the focused TextArea. Enter is handled by the
    # TextArea's accept handler; these only add cancel.

    input_kb = KeyBindings()

    @input_kb.add("escape")
    @input_kb.add("c-c")
    def _input_cancel(_event):
        _exit_input_mode()
        status_override[0] = None
        app.invalidate()

    # ------------------------------------------------------------------ confirm hide
    # While the confirm prompt is open the main bindings are suppressed; only
    # y (hide) and n/Esc (cancel) are live.

    confirm_kb = KeyBindings()

    def _exit_confirm_mode() -> None:
        confirm_mode_ref[0] = False
        confirm_target_ref[0] = None

    @confirm_kb.add("y")
    def _confirm_hide(_event):
        song = confirm_target_ref[0]
        _exit_confirm_mode()
        if song is not None:
            state = state_ref[0]
            if state is not None:
                # state.hidden_ids is the same object as hidden_ids_ref[0], so
                # the song drops out of the recomputed candidates. Keep the
                # cursor in place (recompute would reset it to 0) so the
                # selection stays near where it was; _render_slice re-derives
                # the scroll to keep the cursor visible.
                hide_candidate(state, song)
            else:
                # Seed-selection mode: the visible list shrank by one.
                hidden_ids_ref[0].add(song.id)
                visible = _visible_seed_pool()
                seed_cursor_ref[0] = min(seed_cursor_ref[0], max(len(visible) - 1, 0))
            status_override[0] = f"Hidden {song.artist} – {song.name}"
            # The focused song changed (the hidden one is gone), so move the
            # preview to whatever now sits under the cursor.
            _maybe_switch_preview()
        app.invalidate()

    @confirm_kb.add("n")
    @confirm_kb.add("escape")
    @confirm_kb.add("c-c")
    def _cancel_hide(_event):
        _exit_confirm_mode()
        status_override[0] = None
        app.invalidate()

    in_input_mode = Condition(lambda: input_mode_ref[0])
    in_confirm_mode = Condition(lambda: confirm_mode_ref[0])
    app_kb = merge_key_bindings(
        [
            ConditionalKeyBindings(kb, ~in_input_mode & ~in_confirm_mode),
            ConditionalKeyBindings(input_kb, in_input_mode),
            ConditionalKeyBindings(confirm_kb, in_confirm_mode),
        ]
    )

    app = Application(
        layout=layout,
        key_bindings=app_kb,
        style=_STYLE,
        full_screen=True,
        mouse_support=False,
    )
    app.run()
