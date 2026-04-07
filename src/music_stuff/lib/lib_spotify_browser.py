from pathlib import Path

from playwright.sync_api import BrowserContext, sync_playwright

BROWSER_STATE_PATH = Path("secrets/spotify-browser-state.json")


class PlaylistNotFoundError(Exception):
    pass


def ensure_logged_in(
    context: BrowserContext, browser_state_path: Path = BROWSER_STATE_PATH
) -> None:
    """Check login state. Prompts the user to log in if the session has expired."""
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
    recommendations: int = 0,
) -> None:
    """Copy tracks from one or more source playlists to a target playlist via the Spotify Web UI.

    If recommendations is > 0, copies the recommended tracks shown below the playlist
    instead of the playlist tracks themselves.
    """
    container_selector = (
        '[data-testid="recommended-track"]'
        if recommendations > 0
        else '[data-testid="playlist-tracklist"]'
    )
    storage = str(browser_state_path) if browser_state_path.exists() else None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=500)
        kwargs = {"storage_state": storage} if storage else {}
        context = browser.new_context(**kwargs)

        ensure_logged_in(context, browser_state_path)

        page = context.new_page()

        for source_playlist_id in source_playlist_ids:
            page.goto(f"https://open.spotify.com/playlist/{source_playlist_id}")

            page.wait_for_selector(container_selector, timeout=15_000)

            remaining = recommendations if recommendations > 0 else 1
            while remaining > 0:
                container = page.locator(container_selector).last
                container.scroll_into_view_if_needed()

                # Click position is bottom-right to avoid links (album, etc.)
                firstRow = container.locator('[data-testid="tracklist-row"]').first
                firstRow.click(position=_bottom_right(firstRow))
                _scroll_to_bottom(page, container)

                # The list is virtualised, rows.last must be fresh after scrolling
                lastRow = container.locator('[data-testid="tracklist-row"]').last

                lastRow.click(modifiers=["Shift"], position=_bottom_right(lastRow))
                lastRow.click(button="right", position=_bottom_right(lastRow))

                page.get_by_role("menuitem", name="Add to playlist").hover()

                submenu_item = page.get_by_role(
                    "menuitem", name=target_playlist_name, exact=True
                )
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

                page.wait_for_timeout(5000)
                remaining -= 1

                if remaining > 0:
                    container.locator("button", has_text="Refresh").click()
                    page.wait_for_selector(container_selector, timeout=15_000)

        browser.close()


def copy_track_radios_via_browser(
    track_ids: list[str],
    target_playlist_name: str,
    browser_state_path: Path = BROWSER_STATE_PATH,
) -> None:
    """For each track ID, navigate to its song radio and copy all tracks to target playlist."""
    storage = str(browser_state_path) if browser_state_path.exists() else None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=500)
        kwargs = {"storage_state": storage} if storage else {}
        context = browser.new_context(**kwargs)

        ensure_logged_in(context, browser_state_path)
        page = context.new_page()

        for track_id in track_ids:
            page.goto(f"https://open.spotify.com/track/{track_id}")
            page.locator(
                '[data-testid="action-bar-row"] [data-testid="more-button"]'
            ).click()
            page.get_by_role("menuitem", name="Go to song radio").click()
            page.wait_for_selector('[data-testid="playlist-tracklist"]', timeout=15_000)

            container = page.locator('[data-testid="playlist-tracklist"]').last
            container.scroll_into_view_if_needed()

            firstRow = container.locator('[data-testid="tracklist-row"]').first
            firstRow.click(position=_bottom_right(firstRow))
            _scroll_to_bottom(page, container)

            lastRow = container.locator('[data-testid="tracklist-row"]').last
            lastRow.click(modifiers=["Shift"], position=_bottom_right(lastRow))
            lastRow.click(button="right", position=_bottom_right(lastRow))

            page.get_by_role("menuitem", name="Add to playlist").hover()

            submenu_item = page.get_by_role(
                "menuitem", name=target_playlist_name, exact=True
            )
            if not submenu_item.is_visible():
                browser.close()
                raise PlaylistNotFoundError(
                    f"Playlist '{target_playlist_name}' not found in Add-to-playlist submenu."
                )
            submenu_item.click()

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

            page.wait_for_timeout(5000)

        browser.close()


def _bottom_right(locator) -> dict:
    """Click position at the bottom-right edge of a locator, avoiding links."""
    box = locator.bounding_box()
    return {"x": box["width"] - 5, "y": box["height"] - 5}


def _scroll_to_bottom(page, element) -> None:
    """Scroll to the bottom of the element, waiting for virtualised content to load."""
    previous_position = -1
    while True:
        element.evaluate("(element) => element.scrollIntoView(false)")
        page.wait_for_timeout(500)
        current_position = element.evaluate("(element) => element.scrollTop")
        if current_position == previous_position:
            break
        previous_position = current_position
