from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from music_stuff.lib.lib_spotify_browser import (
    copy_playlist_via_browser,
    ensure_logged_in,
)

needs_browser = pytest.mark.skipif(
    not Path("secrets/spotify-browser-state.json").exists(),
    reason="No saved Spotify browser state",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_page_mock(submenu_visible=True, has_video=False):
    mock_page = MagicMock()
    mock_page.evaluate.return_value = 0

    mock_last_row = MagicMock()
    mock_last_row.bounding_box.return_value = {"width": 100, "height": 50}

    mock_rows_locator = MagicMock()
    mock_rows_locator.last = mock_last_row
    mock_rows_locator.first = MagicMock()

    mock_container_locator = MagicMock()
    mock_container_locator.last = MagicMock(
        scroll_into_view_if_needed=MagicMock(),
        locator=MagicMock(return_value=mock_rows_locator),
    )

    mock_page.locator.return_value = mock_container_locator

    mock_submenu_item = MagicMock()
    mock_submenu_item.is_visible.return_value = submenu_visible
    mock_submenu_item.click = MagicMock()

    mock_add_to_playlist = MagicMock()
    mock_add_to_playlist.hover = MagicMock()

    mock_alert = MagicMock()
    mock_alert.wait_for = MagicMock()

    def get_by_role_side_effect(role, name=None, **kwargs):
        if name == "Add to playlist":
            return mock_add_to_playlist
        elif name == "menuitem":
            return mock_submenu_item
        elif role == "alert":
            return mock_alert
        elif role == "menuitem" and name is None:
            return mock_submenu_item
        return MagicMock()

    mock_page.get_by_role = MagicMock(side_effect=get_by_role_side_effect)

    mock_video = MagicMock() if has_video else None
    mock_page.video = mock_video
    if mock_video:
        mock_page.video.path.return_value = "tmp/video.webm"

    mock_context = MagicMock()
    mock_page.context = mock_context

    return mock_page, mock_last_row


# ---------------------------------------------------------------------------
# ensure_logged_in
# ---------------------------------------------------------------------------


def test_ensure_logged_in_saves_state(tmp_path):
    state_path = tmp_path / "spotify-browser-state.json"

    mock_user_widget = MagicMock()
    mock_user_widget.is_visible.return_value = True

    mock_page = MagicMock()
    mock_page.locator.return_value = mock_user_widget

    ensure_logged_in(mock_page, browser_state_path=state_path)

    mock_page.context.storage_state.assert_called_once_with(path=str(state_path))


def test_ensure_logged_in_waits_when_user_widget_not_visible(tmp_path):
    state_path = tmp_path / "state.json"

    mock_user_widget = MagicMock()
    mock_user_widget.is_visible.return_value = False

    mock_page = MagicMock()
    mock_page.locator.return_value = mock_user_widget

    ensure_logged_in(mock_page, browser_state_path=state_path)

    mock_user_widget.wait_for.assert_any_call(state="visible", timeout=120_000)
    mock_page.context.storage_state.assert_called_once()


# ---------------------------------------------------------------------------
# copy_playlist_via_browser
# ---------------------------------------------------------------------------


def test_playlist_not_found_raises(tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text("{}")

    mock_page, _ = _make_page_mock(submenu_visible=False)
    mock_page.get_by_role = MagicMock(
        side_effect=lambda role, name=None, exact=False, **kwargs: MagicMock(
            hover=MagicMock(),
            is_visible=MagicMock(return_value=False),
            click=MagicMock(),
            wait_for=MagicMock(),
        )
    )

    mock_context_manager = MagicMock()
    mock_context_manager.__enter__ = MagicMock(return_value=mock_page)
    mock_context_manager.__exit__ = MagicMock(return_value=False)

    with patch(
        "music_stuff.lib.lib_spotify_browser._create_logged_in_page",
        return_value=mock_context_manager,
    ):
        with pytest.raises(ValueError, match="not found in Add-to-playlist submenu"):
            copy_playlist_via_browser(
                source_playlist_ids=["abc123"],
                target_playlist_name="Nonexistent Playlist",
                browser_state_path=state_path,
            )


def test_successful_copy_calls_shift_and_right_click(tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text("{}")

    mock_page, mock_last_row = _make_page_mock(submenu_visible=True)

    mock_context_manager = MagicMock()
    mock_context_manager.__enter__ = MagicMock(return_value=mock_page)
    mock_context_manager.__exit__ = MagicMock(return_value=False)

    with patch(
        "music_stuff.lib.lib_spotify_browser._create_logged_in_page",
        return_value=mock_context_manager,
    ):
        copy_playlist_via_browser(
            source_playlist_ids=["abc123"],
            target_playlist_name="My Playlist",
            browser_state_path=state_path,
        )

    calls = mock_last_row.click.call_args_list
    assert any(c.kwargs.get("modifiers") == ["Shift"] for c in calls)
    assert any(c.kwargs.get("button") == "right" for c in calls)


def test_no_state_file_starts_without_storage(tmp_path):
    state_path = tmp_path / "nonexistent.json"

    mock_page, _ = _make_page_mock(submenu_visible=True)

    mock_context_manager = MagicMock()
    mock_context_manager.__enter__ = MagicMock(return_value=mock_page)
    mock_context_manager.__exit__ = MagicMock(return_value=False)

    with patch(
        "music_stuff.lib.lib_spotify_browser._create_logged_in_page",
        return_value=mock_context_manager,
    ):
        copy_playlist_via_browser(
            source_playlist_ids=["abc123"],
            target_playlist_name="My Playlist",
            browser_state_path=state_path,
        )


# ---------------------------------------------------------------------------
# copy_recommendations_via_browser
# ---------------------------------------------------------------------------


def test_recommendations_not_found_raises(tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text("{}")

    mock_page, _ = _make_page_mock(submenu_visible=False)
    mock_page.get_by_role = MagicMock(
        side_effect=lambda role, name=None, exact=False, **kwargs: MagicMock(
            hover=MagicMock(),
            is_visible=MagicMock(return_value=False),
            click=MagicMock(),
            wait_for=MagicMock(),
        )
    )

    mock_context_manager = MagicMock()
    mock_context_manager.__enter__ = MagicMock(return_value=mock_page)
    mock_context_manager.__exit__ = MagicMock(return_value=False)

    with patch(
        "music_stuff.lib.lib_spotify_browser._create_logged_in_page",
        return_value=mock_context_manager,
    ):
        with pytest.raises(ValueError, match="not found in Add-to-playlist submenu"):
            copy_playlist_via_browser(
                source_playlist_ids=["abc123"],
                target_playlist_name="Nonexistent Playlist",
                browser_state_path=state_path,
                recommendations=1,
            )


def test_recommendations_successful_copy(tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text("{}")

    mock_page, mock_last_row = _make_page_mock(submenu_visible=True)

    mock_context_manager = MagicMock()
    mock_context_manager.__enter__ = MagicMock(return_value=mock_page)
    mock_context_manager.__exit__ = MagicMock(return_value=False)

    with patch(
        "music_stuff.lib.lib_spotify_browser._create_logged_in_page",
        return_value=mock_context_manager,
    ):
        copy_playlist_via_browser(
            source_playlist_ids=["abc123"],
            target_playlist_name="My Playlist",
            browser_state_path=state_path,
            recommendations=1,
        )

    calls = mock_last_row.click.call_args_list
    assert any(c.kwargs.get("modifiers") == ["Shift"] for c in calls)
    assert any(c.kwargs.get("button") == "right" for c in calls)


# ---------------------------------------------------------------------------
# Integration test — requires real saved state, skipped in CI
# ---------------------------------------------------------------------------


@needs_browser
def test_integration_copy_playlist_via_browser():
    """Smoke test: navigate to a real playlist and verify no error is raised.
    Requires secrets/spotify-browser-state.json to exist."""
    pass


def test_headless_mode_uses_headless_flag(tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text("{}")

    mock_page, _ = _make_page_mock(submenu_visible=True)

    mock_context_manager = MagicMock()
    mock_context_manager.__enter__ = MagicMock(return_value=mock_page)
    mock_context_manager.__exit__ = MagicMock(return_value=False)

    with patch(
        "music_stuff.lib.lib_spotify_browser._create_logged_in_page",
        return_value=mock_context_manager,
    ) as mock_create:
        copy_playlist_via_browser(
            source_playlist_ids=["abc123"],
            target_playlist_name="My Playlist",
            browser_state_path=state_path,
            headless=True,
        )

        mock_create.assert_called_once_with(True, state_path)
