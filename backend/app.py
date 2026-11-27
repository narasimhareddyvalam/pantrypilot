"""PantryPilot - the backend that serves the phone page and the API.

Page
  GET  /                              the phone page with the Scan, Pantry and Assistant tabs

API (JSON)
  POST /scans                         read the date label from a photo (Narasimha)
  GET/POST /pantry/items              list or add pantry items (Yuhao, coming)
  PATCH/DELETE /pantry/items/<id>     change or remove one item (Yuhao, coming)
  POST /assistant                     ask the assistant a question (Sreeja, coming)

Every error comes back as {"error": "<one polite sentence>", "code": "<code>"}.
Settings come from the .env file (see .env.example).
"""

import os
import socket
import sys

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template
from werkzeug.exceptions import HTTPException
from werkzeug.serving import is_running_from_reloader

from errors import PantryError

load_dotenv()

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

# 0.0.0.0 means "listen on every network", so a phone on the same Wi-Fi can open the app.
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "5001"))
# Debug mode shows code details when something breaks, so it stays off unless .env turns it on.
DEBUG = os.getenv("DEBUG", "false").strip().lower() == "true"
# Phone photos are a few MB, so anything bigger than this is refused.
MAX_UPLOAD_MB = 10

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

# Flask's own errors, each turned into a code and a sentence the user can read.
HTTP_ERRORS = {
    404: ("not_found", "We couldn't find that page."),
    405: ("invalid_input", "That action isn't allowed here."),
    413: ("too_large", f"That photo is too big. Please use a photo under {MAX_UPLOAD_MB} MB."),
    500: ("server_error", "Something went wrong on our side. Please try again."),
}


@app.errorhandler(PantryError)
def handle_pantry_error(error):
    # Here I send our own errors back as JSON, with the status code the error carries.
    return jsonify({"error": error.message, "code": error.code}), error.status


@app.errorhandler(HTTPException)
def handle_http_error(error):
    # Here I catch Flask's own errors (wrong address, wrong method, file too big,
    # or a crash) and give them the same JSON shape as our own errors.
    if error.code in HTTP_ERRORS:
        code, message = HTTP_ERRORS[error.code]
    else:
        code = "invalid_input"
        message = "That request didn't work. Please try again."
    return jsonify({"error": message, "code": code}), error.code


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

@app.get("/")
def home():
    # The whole app is one page. app.js switches between the three tabs.
    return render_template("index.html")


# ---------------------------------------------------------------------------
# Parts of the API
# ---------------------------------------------------------------------------

# Each part of the API lives in its own file as a Flask blueprint.
# Blueprints: Yuhao and Sreeja register theirs here.


# ---------------------------------------------------------------------------
# Start the app
# ---------------------------------------------------------------------------

def find_lan_address():
    """Find this laptop's address on the Wi-Fi, so I can tell the phone where to go."""
    # Connecting a UDP socket sends nothing. It only makes the computer pick the
    # network it would use to reach the internet, and then I read our address on it.
    connection = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        connection.connect(("8.8.8.8", 80))
        address = connection.getsockname()[0]
    except OSError:
        # There is no network at all, so only this laptop can open the app.
        address = "127.0.0.1"
    finally:
        connection.close()
    return address


def port_is_free(port):
    """Check that no other program is using this port, so the app can start on it."""
    test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Flask's server sets this option too, so a port our own app just let go of still counts as free.
    test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        test_socket.bind(("0.0.0.0", port))
        return True
    except OSError:
        return False
    finally:
        test_socket.close()


if __name__ == "__main__":
    # With DEBUG on, Flask starts this file a second time so it can reload code
    # changes. That second start already owns the port, so I only check the port
    # and print the addresses the first time.
    if not is_running_from_reloader():
        # If another program already uses the port, I say so plainly and stop,
        # instead of printing addresses that would not work.
        if not port_is_free(PORT):
            print(f"Port {PORT} is already used by another program on this computer.")
            print("Stop that program, or set a different PORT in the .env file (for example PORT=5002), then start again.")
            sys.exit(1)

        print(f"On this laptop: http://localhost:{PORT}")
        print(f"On your phone (same Wi-Fi): http://{find_lan_address()}:{PORT}")

    app.run(host=HOST, port=PORT, debug=DEBUG)
