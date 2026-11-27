"""Checks for POST /scans: good photos get a scan result, and bad requests
get a polite JSON error the phone page can show."""

import datetime
import io
import json
import os

from PIL import Image

from app import app
from scan import FIXTURES_DIR, LABEL_TYPES, SAMPLE_FILES

client = app.test_client()

# The scan results the endpoint must return, written out by hand.
READABLE = {"rawText": "BEST BEFORE 2027-01-05", "labelType": "best_before", "date": "2027-01-05", "requiresReview": False}
AMBIGUOUS = {"rawText": "USE BY 03/04/27", "labelType": "expiration", "date": None, "requiresReview": True}
UNREADABLE = {"rawText": "", "labelType": None, "date": None, "requiresReview": True}


def make_photo(image_format="JPEG"):
    """Make a small white picture in memory, like a tiny phone photo."""
    picture = Image.new("RGB", (40, 20), "white")
    data = io.BytesIO()
    picture.save(data, image_format)
    data.seek(0)
    return data


def send(photo=None, file_name="label.jpg", sample=None):
    """Post a photo to /scans the same way the phone page does."""
    url = "/scans"
    if sample is not None:
        url = f"/scans?sample={sample}"
    form = {}
    if photo is not None:
        form["image"] = (photo, file_name)
    return client.post(url, data=form, content_type="multipart/form-data")


def test_readable_sample_is_the_default():
    response = send(make_photo())
    assert response.status_code == 200
    assert response.get_json() == READABLE


def test_ambiguous_sample():
    response = send(make_photo(), sample="ambiguous")
    assert response.status_code == 200
    assert response.get_json() == AMBIGUOUS


def test_unreadable_sample():
    response = send(make_photo(), sample="unreadable")
    assert response.status_code == 200
    assert response.get_json() == UNREADABLE


def test_png_photo_is_accepted():
    response = send(make_photo("PNG"), "label.png")
    assert response.status_code == 200


def test_missing_photo_is_refused():
    response = send()
    assert response.status_code == 400
    assert response.get_json() == {"error": "Please add a photo of the package.", "code": "invalid_input"}


def test_non_image_file_is_refused():
    response = send(io.BytesIO(b"hello"), "notes.txt")
    assert response.status_code == 400
    assert response.get_json() == {
        "error": "That file isn't a photo we can read. Please use a JPG or PNG photo.",
        "code": "invalid_input",
    }


def test_unknown_sample_is_refused():
    response = send(make_photo(), sample="blurry")
    assert response.status_code == 400
    assert response.get_json() == {"error": "Sample must be readable, ambiguous or unreadable.", "code": "invalid_input"}


def test_too_large_upload_is_refused(monkeypatch):
    # Here I lower the size limit for this one test, so I don't need a real 10 MB file.
    monkeypatch.setitem(app.config, "MAX_CONTENT_LENGTH", 1000)
    response = send(io.BytesIO(b"x" * 5000), "big.jpg")
    assert response.status_code == 413
    assert response.get_json() == {"error": "That photo is too big. Please use a photo under 10 MB.", "code": "too_large"}


def test_huge_picture_is_refused(monkeypatch):
    # Here I pretend the pixel limit is tiny, so my small test photo counts as huge.
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100)
    response = send(make_photo())
    assert response.status_code == 413
    assert response.get_json() == {"error": "That photo is too big to read. Please use a smaller photo.", "code": "too_large"}


def test_giant_picture_is_refused_before_it_is_decoded():
    # An 8000 x 8000 picture is 64 megapixels. Its PNG file is tiny, but decoding it
    # could use a lot of memory, so the server must refuse it before decoding.
    picture = Image.new("1", (8000, 8000))
    data = io.BytesIO()
    picture.save(data, "PNG")
    data.seek(0)
    response = send(data, "giant.png")
    assert response.status_code == 413
    assert response.get_json() == {"error": "That photo is too big to read. Please use a smaller photo.", "code": "too_large"}


def test_other_picture_formats_are_refused():
    # The page always sends JPEG and the message promises JPG or PNG,
    # so other formats, like TIFF, are refused instead of being opened.
    picture = Image.new("RGB", (40, 20), "white")
    data = io.BytesIO()
    picture.save(data, "TIFF")
    data.seek(0)
    response = send(data, "label.tiff")
    assert response.status_code == 400
    assert response.get_json() == {
        "error": "That file isn't a photo we can read. Please use a JPG or PNG photo.",
        "code": "invalid_input",
    }


def test_get_on_scans_is_refused():
    response = client.get("/scans")
    assert response.status_code == 405
    assert response.get_json()["code"] == "invalid_input"


def test_every_sample_has_the_agreed_fields():
    # Yuhao, Sreeja and the phone page all depend on this exact shape.
    for file_name in SAMPLE_FILES.values():
        with open(os.path.join(FIXTURES_DIR, file_name)) as sample_file:
            sample = json.load(sample_file)
        assert set(sample.keys()) == {"rawText", "labelType", "date", "requiresReview"}
        assert isinstance(sample["rawText"], str)
        assert sample["labelType"] is None or sample["labelType"] in LABEL_TYPES
        if sample["date"] is not None:
            datetime.date.fromisoformat(sample["date"])
        assert isinstance(sample["requiresReview"], bool)
