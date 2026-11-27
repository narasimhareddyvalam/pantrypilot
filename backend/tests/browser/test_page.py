"""Browser checks for the page shell: the tabs, the safety note and the sample-data badges."""

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect  # noqa: E402


def test_page_works_when_the_internet_hangs(browser, server_url):
    # On a Wi-Fi with no internet, requests to other websites can hang forever.
    # The page must still load and work, because it only needs this app.
    context = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    context.set_default_timeout(5000)

    def hang_outside_requests(route):
        if route.request.url.startswith(server_url):
            route.continue_()
        # Anything else gets no answer at all.

    context.route("**/*", hang_outside_requests)
    page = context.new_page()
    page.goto(server_url + "/", wait_until="commit")
    expect(page.locator("#tab-scan")).to_have_attribute("aria-current", "page")
    context.close()


def test_scan_tab_is_shown_first(open_page):
    page = open_page()
    assert page.locator("#view-scan").is_visible()
    assert page.locator("#view-pantry").is_hidden()
    assert page.locator("#view-assistant").is_hidden()
    assert page.locator("#tab-scan").get_attribute("aria-current") == "page"


def test_tabs_switch_views(open_page):
    page = open_page()

    page.click("#tab-pantry")
    assert page.locator("#view-pantry").is_visible()
    assert page.locator("#view-scan").is_hidden()
    assert page.locator("#view-assistant").is_hidden()
    assert page.locator("#tab-pantry").get_attribute("aria-current") == "page"
    assert page.locator("#tab-scan").get_attribute("aria-current") is None

    page.click("#tab-assistant")
    assert page.locator("#view-assistant").is_visible()
    assert page.locator("#view-pantry").is_hidden()
    assert page.locator("#tab-assistant").get_attribute("aria-current") == "page"


def test_safety_note_is_on_the_page(open_page):
    page = open_page()
    note = page.locator("#safety-note")
    assert note.is_visible()
    assert note.text_content().strip() == "Printed dates don't prove food is safe to eat."


def test_sample_badges_show_while_switches_are_on(open_page):
    page = open_page()

    page.click("#tab-pantry")
    assert page.locator("#sample-badge-pantry").is_visible()
    assert page.locator("#sample-badge-pantry").text_content().strip() == "Sample data"

    page.click("#tab-assistant")
    assert page.locator("#sample-badge-assistant").is_visible()
    assert page.locator("#sample-badge-assistant").text_content().strip() == "Sample data"
