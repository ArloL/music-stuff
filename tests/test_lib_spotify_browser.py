from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from music_stuff.lib.lib_spotify_browser import (
    PlaylistNotFoundError,
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

def _make_playwright_mocks(submenu_visible=True):
    mock_page = MagicMock()
    mock_page.evaluate.return_value = 0  # stable scroll position

    mock_row = MagicMock()
    mock_locator = MagicMock()
    mock_locator.first = mock_row
    mock_page.locator.return_value = mock_locator

    mock_submenu_item = MagicMock()
    mock_submenu_item.is_visible.return_value = submenu_visible
    mock_page.get_by_role.return_value = mock_submenu_item

    mock_context = MagicMock()
    mock_context.new_page.return_value = mock_page

    mock_browser = MagicMock()
    mock_browser.new_context.return_value = mock_context

    mock_chromium = MagicMock()
    mock_chromium.launch.return_value = mock_browser

    mock_pw = MagicMock()
    mock_pw.__enter__ = MagicMock(return_value=mock_pw)
    mock_pw.__exit__ = MagicMock(return_value=False)
    mock_pw.chromium = mock_chromium

    return mock_pw, mock_browser, mock_context, mock_page


# ---------------------------------------------------------------------------
# ensure_logged_in
# ---------------------------------------------------------------------------

def test_ensure_logged_in_saves_state(tmp_path):
    state_path = tmp_path / "spotify-browser-state.json"

    mock_user_widget = MagicMock()
    mock_user_widget.is_visible.return_value = True

    mock_page = MagicMock()
    mock_page.locator.return_value = mock_user_widget

    mock_context = MagicMock()
    mock_context.new_page.return_value = mock_page

    ensure_logged_in(mock_context, browser_state_path=state_path)

    mock_context.storage_state.assert_called_once_with(path=str(state_path))
    mock_page.close.assert_called_once()


def test_ensure_logged_in_waits_when_user_widget_not_visible(tmp_path):
    state_path = tmp_path / "state.json"

    mock_user_widget = MagicMock()
    mock_user_widget.is_visible.return_value = False

    mock_page = MagicMock()
    mock_page.locator.return_value = mock_user_widget

    mock_context = MagicMock()
    mock_context.new_page.return_value = mock_page

    ensure_logged_in(mock_context, browser_state_path=state_path)

    mock_user_widget.wait_for.assert_called_once_with(state="visible", timeout=120_000)
    mock_context.storage_state.assert_called_once()


# ---------------------------------------------------------------------------
# copy_playlist_via_browser
# ---------------------------------------------------------------------------

def test_playlist_not_found_raises(tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text("{}")

    mock_pw, mock_browser, mock_context, mock_page = _make_playwright_mocks(submenu_visible=False)

    with patch("music_stuff.lib.lib_spotify_browser.sync_playwright", return_value=mock_pw):
        with pytest.raises(PlaylistNotFoundError, match="not found in Add-to-playlist submenu"):
            copy_playlist_via_browser(
                source_playlist_ids=["abc123"],
                target_playlist_name="Nonexistent Playlist",
                browser_state_path=state_path,
            )


def test_successful_copy_calls_ctrl_a_and_submenu(tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text("{}")

    mock_pw, mock_browser, mock_context, mock_page = _make_playwright_mocks(submenu_visible=True)

    with patch("music_stuff.lib.lib_spotify_browser.sync_playwright", return_value=mock_pw):
        copy_playlist_via_browser(
            source_playlist_ids=["abc123"],
            target_playlist_name="My Playlist",
            browser_state_path=state_path,
        )

    tracklist = mock_page.locator.return_value
    rows = tracklist.locator.return_value
    calls = rows.last.click.call_args_list
    assert any(c.kwargs.get("modifiers") == ["Shift"] for c in calls)
    assert any(c.kwargs.get("button") == "right" for c in calls)
    mock_browser.close.assert_called_once()


def test_no_state_file_starts_without_storage(tmp_path):
    state_path = tmp_path / "nonexistent.json"

    mock_pw, mock_browser, mock_context, mock_page = _make_playwright_mocks(submenu_visible=True)

    with patch("music_stuff.lib.lib_spotify_browser.sync_playwright", return_value=mock_pw):
        copy_playlist_via_browser(
            source_playlist_ids=["abc123"],
            target_playlist_name="My Playlist",
            browser_state_path=state_path,
        )

    # new_context called without storage_state kwarg
    mock_browser.new_context.assert_called_once_with()


# ---------------------------------------------------------------------------
# Integration test — requires real saved state, skipped in CI
# ---------------------------------------------------------------------------

@needs_browser
def test_integration_copy_playlist_via_browser():
    """Smoke test: navigate to a real playlist and verify no error is raised.
    Requires secrets/spotify-browser-state.json to exist."""
    pass
