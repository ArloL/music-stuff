from pathlib import Path

from playwright.sync_api import BrowserContext, sync_playwright

BROWSER_STATE_PATH = Path("secrets/spotify-browser-state.json")


class PlaylistNotFoundError(Exception):
    pass


def ensure_logged_in(context: BrowserContext, browser_state_path: Path = BROWSER_STATE_PATH) -> None:
    """Check login state in the given context. If not logged in, prompt the user.

    Saves storage state to file when done.
    """
    page = context.new_page()
    page.goto("https://open.spotify.com/")

    user_widget = page.locator('[data-testid="user-widget-link"]')
    if not user_widget.is_visible():
        print("Please log in to Spotify in the browser window.")
        user_widget.wait_for(state="visible", timeout=120_000)
        print("Logged in.")

    browser_state_path.parent.mkdir(parents=True, exist_ok=True)
    context.storage_state(path=str(browser_state_path))
    page.close()


def copy_playlist_via_browser(
    source_playlist_ids: list[str],
    target_playlist_name: str,
    browser_state_path: Path = BROWSER_STATE_PATH,
) -> None:
    """Copy all tracks from one or more source playlists to a target playlist via the Spotify Web UI.

    Opens a single headed browser session. Checks login state first and prompts
    if the session has expired. For each source playlist, navigates to it, scrolls
    to load all tracks in the virtualised list, Shift+clicks the range, right-clicks
    and uses the "Add to playlist" context menu.

    Raises PlaylistNotFoundError if the target playlist isn't found in the submenu.
    """
    storage = str(browser_state_path) if browser_state_path.exists() else None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=500)
        kwargs = {"storage_state": storage} if storage else {}
        context = browser.new_context(**kwargs)

        ensure_logged_in(context, browser_state_path)

        page = context.new_page()

        for source_playlist_id in source_playlist_ids:
            url = f"https://open.spotify.com/playlist/{source_playlist_id}"
            page.goto(url)

            # Wait for tracklist to render
            page.wait_for_selector('[data-testid="playlist-tracklist"]', timeout=15_000)
            tracklist = page.locator('[data-testid="playlist-tracklist"]')

            # Click first row, scroll to render all virtualised rows, then Shift+click last.
            # Use bottom-right edge to avoid links (title, artist, album).
            first_row = tracklist.locator('[data-testid="tracklist-row"]').first
            first_row.click(position=_bottom_right(first_row))
            _scroll_to_bottom(page)
            last_row = tracklist.locator('[data-testid="tracklist-row"]').last
            last_row.click(modifiers=["Shift"], position=_bottom_right(last_row))

            # Right-click the last row (already selected) to open context menu
            last_row.click(button="right", position=_bottom_right(last_row))

            # Hover "Add to playlist" to reveal submenu
            page.get_by_role("menuitem", name="Add to playlist").hover()

            # Click the target playlist by name in submenu
            submenu_item = page.get_by_role("menuitem", name=target_playlist_name, exact=True)
            if not submenu_item.is_visible():
                browser.close()
                raise PlaylistNotFoundError(
                    f"Playlist '{target_playlist_name}' not found in Add-to-playlist submenu."
                )
            submenu_item.click()

            # Dismiss "Already added" dialog if it appears
            try:
                already_added = page.locator('[aria-label="Already added"]')
                already_added.wait_for(state="visible", timeout=2000)
                dont_add = already_added.locator("button", has_text="Don't add")
                add_new = already_added.locator("button", has_text="Add new ones")
                if dont_add.is_visible():
                    dont_add.click()
                elif add_new.is_visible():
                    add_new.click()
            except Exception:
                pass

            # Pause to confirm action completed before next playlist
            page.wait_for_timeout(5000)

        browser.close()


def _bottom_right(locator) -> dict:
    """Return a click position at the bottom-right edge of a locator, avoiding links."""
    box = locator.bounding_box()
    return {"x": box["width"] - 5, "y": box["height"] - 5}


def _scroll_to_bottom(page) -> None:
    """Scroll to the bottom of the page, waiting for virtualised content to load."""
    previous_position = -1
    while True:
        page.keyboard.press("End")
        page.wait_for_timeout(500)
        current_position = page.evaluate("() => window.scrollY")
        if current_position == previous_position:
            break
        previous_position = current_position
