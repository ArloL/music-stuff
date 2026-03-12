from unittest.mock import MagicMock, patch

import pytest

from music_stuff.lib.lib_spotify import all_items, user_playlist_by_name


# --- all_items ---

def test_all_items_single_page():
    sp = MagicMock()
    results = {"items": [{"name": "A"}, {"name": "B"}], "next": None}
    items = all_items(sp, results)
    assert items == [{"name": "A"}, {"name": "B"}]
    sp.next.assert_not_called()


def test_all_items_multiple_pages():
    sp = MagicMock()
    page1 = {"items": [{"name": "A"}], "next": "url1"}
    page2 = {"items": [{"name": "B"}], "next": "url2"}
    page3 = {"items": [{"name": "C"}], "next": None}
    sp.next.side_effect = [page2, page3]

    items = all_items(sp, page1)
    assert items == [{"name": "A"}, {"name": "B"}, {"name": "C"}]
    assert sp.next.call_count == 2


def test_all_items_empty():
    sp = MagicMock()
    results = {"items": [], "next": None}
    assert all_items(sp, results) == []


# --- user_playlist_by_name ---

def test_user_playlist_by_name_found():
    sp = MagicMock()
    sp.current_user_playlists.return_value = {
        "items": [
            {"name": "Chill", "id": "1"},
            {"name": "Party", "id": "2"},
        ],
        "next": None,
    }
    result = user_playlist_by_name(sp, "Party")
    assert result == {"name": "Party", "id": "2"}


def test_user_playlist_by_name_not_found():
    sp = MagicMock()
    sp.current_user_playlists.return_value = {
        "items": [{"name": "Chill", "id": "1"}],
        "next": None,
    }
    with pytest.raises(ValueError, match="No playlist with name Nope"):
        user_playlist_by_name(sp, "Nope")


def test_user_playlist_by_name_paginated():
    sp = MagicMock()
    sp.current_user_playlists.return_value = {
        "items": [{"name": "Chill", "id": "1"}],
        "next": "url",
    }
    sp.next.return_value = {
        "items": [{"name": "Deep", "id": "2"}],
        "next": None,
    }
    result = user_playlist_by_name(sp, "Deep")
    assert result == {"name": "Deep", "id": "2"}
