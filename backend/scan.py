"""POST /scans - read the date label from a photo of a food package.

Right now this returns the shared scan examples in shared/fixtures, so the
phone page can be built and tested. In PP-03 and PP-04 the real steps go here:
the CNN finds the date on the photo, OCR reads it, and BERT decides the label
type. The response keeps the same shape.
"""

import json
import os

from flask import Blueprint, jsonify, request
from PIL import Image, UnidentifiedImageError

from errors import PantryError

# The shared examples live in shared/fixtures, one folder up from backend/.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FIXTURES_DIR = os.path.join(BASE_DIR, "..", "shared", "fixtures")

# The example names the page can ask for, and the file each one comes from.
SAMPLE_FILES = {
    "readable": "scan_readable.json",
    "ambiguous": "scan_ambiguous.json",
    "unreadable": "scan_unreadable.json",
}

# The label types the team agreed on in the design.
LABEL_TYPES = ["expiration", "best_before", "sell_by", "manufacturing", "other"]

# Phone photos are about 12 to 50 megapixels. A bigger picture could use too much
# memory to open, so anything over this many pixels is refused.
MAX_PIXELS = 50_000_000

# The page always sends JPEG, and the error message promises JPG or PNG.
PHOTO_FORMATS = ["JPEG", "PNG"]

scan_blueprint = Blueprint("scan", __name__)


def read_photo(file):
    """Open the uploaded file as a picture, or raise a polite error."""
    # Step 1: here I check that a photo was really sent.
    if file is None or file.filename == "":
        raise PantryError("Please add a photo of the package.")

    # Step 2: here I open the file as a picture. A phone can send any kind of
    # file, so if Pillow can't open it as a JPEG or PNG, it is not a photo we can use.
    try:
        picture = Image.open(file.stream, formats=PHOTO_FORMATS)

        # Step 3: opening only reads the picture's size, not the picture itself.
        # So I check the size first, before decoding the whole picture into memory.
        width, height = picture.size
        if width * height > MAX_PIXELS:
            raise PantryError("That photo is too big to read. Please use a smaller photo.", 413, "too_large")
        picture.load()
    except Image.DecompressionBombError:
        # A picture with a huge number of pixels could use up all the memory.
        raise PantryError("That photo is too big to read. Please use a smaller photo.", 413, "too_large")
    except (UnidentifiedImageError, OSError):
        raise PantryError("That file isn't a photo we can read. Please use a JPG or PNG photo.")
    return picture


def load_sample(name):
    """Read one of the shared scan examples from shared/fixtures."""
    if name not in SAMPLE_FILES:
        raise PantryError("Sample must be readable, ambiguous or unreadable.")
    path = os.path.join(FIXTURES_DIR, SAMPLE_FILES[name])
    with open(path) as sample_file:
        return json.load(sample_file)


@scan_blueprint.post("/scans")
def scan_photo():
    # Step 1: here I check the photo first, so a bad photo is refused even now.
    # In PP-03 this picture goes to the CNN.
    read_photo(request.files.get("image"))

    # Step 2: PP-03 and PP-04 put the real work here: the CNN finds the date,
    # OCR reads it, and BERT decides the label type. Until then I return one of
    # the shared examples, so the phone page can be built and tested.
    # ?sample=ambiguous or ?sample=unreadable picks the other examples.
    sample_name = request.args.get("sample", "readable")
    return jsonify(load_sample(sample_name))
