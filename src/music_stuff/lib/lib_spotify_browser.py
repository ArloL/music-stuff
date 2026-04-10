import json
import time
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import (
    Page,
    PlaywrightContextManager,
    sync_playwright,
)

BROWSER_STATE_PATH = Path("secrets/spotify-browser-state.json")
VIDEO_DIR = Path("tmp")


def ensure_logged_in(
    page: Page,
    browser_state_path: Path = BROWSER_STATE_PATH,
    headless: bool = False,
) -> bool:
    """Check login state on the given page. If headed and not logged in, prompts user to log in.
    Returns True if logged in, False if not logged in and headless (cannot prompt)."""
    page.goto("https://open.spotify.com/")
    page.locator("#Desktop_LeftSidebar_Id").wait_for()
    user_widget = page.locator('[data-testid="user-widget-link"]')
    login_button = page.get_by_test_id("login-button")
    if not user_widget.is_visible() and login_button.is_visible():
        if headless:
            return False
        print("Please log in to Spotify in the browser window.")
        user_widget.wait_for(timeout=120_000)
        print("Logged in.")

    browser_state_path.parent.mkdir(parents=True, exist_ok=True)
    page.context.storage_state(path=str(browser_state_path))
    return True


@contextmanager
def _create_page(
    p: PlaywrightContextManager,
    headless: bool,
    storage: str | None,
    slow_mo: float = 500,
):
    with p.chromium.launch(headless=headless, slow_mo=slow_mo) as browser:
        kwargs = {}
        if storage:
            kwargs = {"storage_state": storage}
        if headless:
            VIDEO_DIR.mkdir(parents=True, exist_ok=True)
            kwargs["record_video_dir"] = str(VIDEO_DIR)
        with browser.new_context(**kwargs) as context:
            with context.new_page() as page:
                error = None
                try:
                    yield page
                except Exception as e:
                    error = e
                    raise
                finally:
                    if page.video is not None:
                        video_path = page.video.path()
                        if error:
                            print(f"Recording saved to: {video_path}")
                        elif Path(video_path).exists():
                            Path(video_path).unlink()


@contextmanager
def _create_logged_in_page(
    headless: bool = False, browser_state_path: Path = BROWSER_STATE_PATH
):
    """Launch a browser, ensure login, and yield a ready-to-use page.

    Headed mode: one browser window, page reused for login check and work.
    Headless mode: opens a headed window if login is needed, then relaunches headless.
    """
    storage = str(browser_state_path) if browser_state_path.exists() else None
    with sync_playwright() as p:
        if not headless:
            with _create_page(p, headless=headless, storage=storage) as page:
                ensure_logged_in(page, browser_state_path, headless=False)
                yield page
                return

        if storage is None:
            with _create_page(p, headless=False, storage=storage) as page:
                ensure_logged_in(page, browser_state_path, headless=False)
            with _create_page(p, headless=headless, storage=storage) as page:
                yield page
                return

        with _create_page(p, headless=headless, storage=storage) as page:
            logged_in = ensure_logged_in(page, browser_state_path, headless=headless)
            if logged_in:
                yield page
                return

            if not logged_in:
                with _create_page(p, headless=False, storage=storage) as page:
                    ensure_logged_in(page, browser_state_path, headless=False)
                with _create_page(p, headless=True, storage=storage) as page:
                    yield page
                    return


def copy_playlist_via_browser(
    source_playlist_ids: list[str],
    target_playlist_name: str,
    browser_state_path: Path = BROWSER_STATE_PATH,
    recommendations: int = 0,
    headless: bool = False,
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

    with _create_logged_in_page(headless, browser_state_path) as page:
        for source_playlist_id in source_playlist_ids:
            print(f"Processing playlist: {source_playlist_id}")
            page.goto(f"https://open.spotify.com/playlist/{source_playlist_id}")

            page.locator(container_selector).wait_for()

            remaining = recommendations if recommendations > 0 else 1
            iteration_label = "recommendation set" if recommendations > 0 else "batch"
            while remaining > 0:
                print(f"  Adding {iteration_label} {remaining}...")
                container = page.locator(container_selector).last
                _element_scroll_into_view(page, container, "start")

                firstRow = container.locator(
                    '[data-testid="tracklist-row"]'
                ).first.element_handle()
                firstRow.click(position=_bottom_right(firstRow))
                _element_scroll_into_view(page, container, "end")

                lastRow = container.locator(
                    '[data-testid="tracklist-row"]'
                ).last.element_handle()

                lastRow.click(modifiers=["Shift"], position=_bottom_right(lastRow))
                lastRow.click(button="right", position=_bottom_right(lastRow))

                page.get_by_role("menuitem", name="Add to playlist").hover()

                submenu_item = page.get_by_role(
                    "menuitem", name=target_playlist_name, exact=True
                )
                if not submenu_item.is_visible():
                    raise ValueError(
                        f"Playlist '{target_playlist_name}' not found in Add-to-playlist submenu."
                    )
                submenu_item.click()

                wait_for_adding_success(page)

                remaining -= 1

                if remaining > 0:
                    container.locator("button", has_text="Refresh").click()
                    lastRow.wait_for_element_state("hidden")


def copy_track_radios_via_browser(
    track_ids: list[str],
    target_playlist_name: str,
    browser_state_path: Path = BROWSER_STATE_PATH,
    headless: bool = False,
) -> None:
    """For each track ID, navigate to its song radio and copy all tracks to target playlist."""
    with _create_logged_in_page(headless, browser_state_path) as page:
        for track_id in track_ids:
            print(f"Processing track: {track_id}")
            page.goto(f"https://open.spotify.com/track/{track_id}")
            page.locator(
                '[data-testid="action-bar-row"] [data-testid="more-button"]'
            ).click()
            page.get_by_role("menuitem", name="Go to song radio").click()
            page.locator('[data-testid="playlist-tracklist"]').wait_for()

            container = page.locator('[data-testid="playlist-tracklist"]').last
            _element_scroll_into_view(page, container, "start")

            firstRow = container.locator('[data-testid="tracklist-row"]').first
            firstRow.click(position=_bottom_right(firstRow))
            _element_scroll_into_view(page, container, "end")

            lastRow = container.locator('[data-testid="tracklist-row"]').last
            lastRow.click(modifiers=["Shift"], position=_bottom_right(lastRow))
            lastRow.click(button="right", position=_bottom_right(lastRow))

            page.get_by_role("menuitem", name="Add to playlist").hover()

            submenu_item = page.get_by_role(
                "menuitem", name=target_playlist_name, exact=True
            )
            if not submenu_item.is_visible():
                raise ValueError(
                    f"Playlist '{target_playlist_name}' not found in Add-to-playlist submenu."
                )
            submenu_item.click()
            print(f"  Adding tracks to '{target_playlist_name}'...")

            wait_for_adding_success(page)


def _bottom_right(locator) -> dict:
    """Click position at the bottom-right edge of a locator, avoiding links."""
    box = locator.bounding_box()
    return {"x": box["width"] - 5, "y": box["height"] - 5}


def _element_scroll_into_view(page, element, block: str = "start") -> None:
    """Scroll to the bottom of the element, waiting for virtualised content to load."""
    previous_position = -1
    while True:
        options = json.dumps({"block": block, "inline": "nearest"})
        element.evaluate(f"(element) => element.scrollIntoView({options})")
        page.wait_for_timeout(500)
        current_position = element.evaluate("(element) => element.scrollTop")
        if current_position == previous_position:
            break
        previous_position = current_position


def wait_for_adding_success(page):
    added_alert = page.get_by_role("alert")
    already_added_modal = page.locator('[aria-label="Already added"]')

    either = _wait_for_either(added_alert, already_added_modal)

    if either == already_added_modal:
        dont_add = already_added_modal.locator("button", has_text="Don't add")
        add_new = already_added_modal.locator("button", has_text="Add new ones")
        if dont_add.is_visible():
            dont_add.click()
        elif add_new.is_visible():
            add_new.click()
        added_alert.wait_for()


def _wait_for_either(a, b, timeout=10, interval=0.05):
    end = time.time() + timeout

    while time.time() < end:
        if a.is_visible():
            return a
        if b.is_visible():
            return b
        time.sleep(interval)

    raise TimeoutError("Neither element appeared")
