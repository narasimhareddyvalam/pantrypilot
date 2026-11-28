"""The one error type that every part of PantryPilot raises.

When something goes wrong because of the user's input or a service the app
uses, the code raises PantryError with a short, polite sentence. app.py turns it into JSON
like {"error": "...", "code": "..."} so the phone page can show the sentence.
"""


class PantryError(Exception):
    """An error with a message that is safe to show to the user."""

    def __init__(self, message, status=400, code="invalid_input"):
        super().__init__(message)
        # The sentence the user will read.
        self.message = message
        # The HTTP status code, like 400 for bad input or 404 for not found.
        self.status = status
        # A short word the page can check, like "invalid_input" or "try_again".
        self.code = code
