"""Checks for the app shell: the page loads, errors come back as JSON,
and the app can find the laptop's address for the phone."""

import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request

from werkzeug.exceptions import InternalServerError

from app import app, find_lan_address, handle_http_error, port_is_free

# The test client lets me call the app without starting a real server.
client = app.test_client()

# The backend folder, where app.py lives.
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_free_port():
    """Ask the computer for a port nobody is using, then let it go again."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("0.0.0.0", 0))
    port = probe.getsockname()[1]
    probe.close()
    return port


def test_home_page_has_the_three_tabs():
    response = client.get("/")
    assert response.status_code == 200

    # The page must have the right title and all three tab names.
    page = response.get_data(as_text=True)
    assert "<title>PantryPilot</title>" in page
    for tab_name in ["Scan", "Pantry", "Assistant"]:
        assert tab_name in page


def test_unknown_address_gives_json_not_found():
    response = client.get("/no-such-page")
    assert response.status_code == 404

    # Every error must use the same JSON shape so the page can show it.
    assert response.get_json() == {"error": "We couldn't find that page.", "code": "not_found"}


def test_port_is_free_spots_a_busy_port():
    # Here I keep a port open myself, the way another program would.
    busy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    busy.bind(("0.0.0.0", 0))
    busy.listen()
    port = busy.getsockname()[1]
    try:
        assert port_is_free(port) is False
    finally:
        busy.close()


def test_port_is_free_on_an_unused_port():
    assert port_is_free(find_free_port()) is True


def test_app_starts_with_debug_on():
    # Debug mode starts the app a second time to watch for code changes.
    # That second start must not mistake the first one for "another program".
    port = find_free_port()
    settings = dict(os.environ)
    settings["DEBUG"] = "true"
    settings["PORT"] = str(port)
    # The normal setting, so a phone could reach it.
    settings["HOST"] = "0.0.0.0"
    # start_new_session lets me stop both copies of the app together at the end.
    server = subprocess.Popen(
        [sys.executable, "app.py"],
        cwd=BACKEND_DIR,
        env=settings,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    answered = False
    try:
        # Here I wait up to 10 seconds for the page to answer.
        for attempt in range(40):
            time.sleep(0.25)
            if server.poll() is not None:
                break
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1)
                answered = True
                break
            except OSError:
                pass
    finally:
        if server.poll() is None:
            os.killpg(os.getpgid(server.pid), signal.SIGTERM)
        output = server.communicate(timeout=10)[0]
    assert answered, output


def test_server_error_is_json():
    # A crash inside the app must still reach the page as one polite JSON sentence.
    with app.test_request_context():
        response, status = handle_http_error(InternalServerError())
    assert status == 500
    assert response.get_json() == {"error": "Something went wrong on our side. Please try again.", "code": "server_error"}


def test_find_lan_address_looks_like_an_ip():
    # An IPv4 address is 4 numbers with dots between them, like 192.168.1.20.
    parts = find_lan_address().split(".")
    assert len(parts) == 4
    for part in parts:
        assert part.isdigit()
