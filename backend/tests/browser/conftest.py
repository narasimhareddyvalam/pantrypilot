"""Shared setup for the browser checks.

These checks open the real page in Google Chrome (through Playwright) at
phone size, and click through it the way a person would. They need the dev
packages: pip install -r requirements-dev.txt
"""

import threading

import pytest
from PIL import Image
from werkzeug.serving import make_server

from app import app


@pytest.fixture(scope="session")
def server_url():
    # Here I start the real app on a free port (port 0 means "pick any free one")
    # in a background thread, so the browser has something to talk to.
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.fixture(scope="session")
def browser():
    # I import Playwright here, so the normal tests still run on a computer without it.
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        try:
            chrome = playwright.chromium.launch(channel="chrome")
        except Exception:
            try:
                chrome = playwright.chromium.launch()
            except Exception:
                pytest.skip("No browser found for the browser checks. Please install Google Chrome.")
        yield chrome
        chrome.close()


@pytest.fixture
def open_page(browser, server_url):
    # Each check gets a fresh phone-sized browser, so saved data never leaks between checks.
    # The time zone is US Pacific, so a date bug that shifts days would show up here.
    contexts = []

    def open_at(path="/", init_script=None, mobile=True, height=844, set_up=None):
        # mobile=False opens a laptop-sized browser instead of a phone.
        # height lets a check use a shorter phone screen, like Safari with its toolbars.
        if mobile:
            context = browser.new_context(
                viewport={"width": 390, "height": height},
                is_mobile=True,
                has_touch=True,
                timezone_id="America/Los_Angeles",
                locale="en-US",
            )
        else:
            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                timezone_id="America/Los_Angeles",
                locale="en-US",
            )
        contexts.append(context)
        # A check that waits more than 5 seconds for something has already failed.
        context.set_default_timeout(5000)
        # Some checks change the browser before the page loads, for example to block storage.
        if init_script is not None:
            context.add_init_script(init_script)
        # set_up gets the browser before the page opens, for example to fake the clock.
        if set_up is not None:
            set_up(context)
        page = context.new_page()
        page.goto(server_url + path)
        return page

    yield open_at
    for context in contexts:
        context.close()


@pytest.fixture
def photo_path(tmp_path):
    # A big photo, like a phone camera makes, so I can check the page shrinks it.
    path = tmp_path / "package.jpg"
    Image.new("RGB", (3000, 2000), "white").save(path, "JPEG")
    return str(path)
