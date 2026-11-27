# Date finder (CNN + OCR)

Finds and reads the printed date on a package photo (ticket PP-03).

1. RapidOCR finds every line of text on the photo.
2. A small Keras CNN scores each line: how likely is it the date?
3. RapidOCR reads the 3 best-scoring lines. The first one that looks like a date wins.
4. If none of them does, RapidOCR reads the whole photo instead.

| File | What it does |
|---|---|
| `prepare_data.py` | Cuts every text line out of 400 training photos and labels it date or not date. Saves `data/crops.npz`. |
| `train_cnn.py` | Trains the CNN and saves `date_cnn.keras`. |
| `read_date.py` | `find_date(photo_path)`, plus the numbers on 120 test photos. |

## Data

The scripts use the Products-Real part of the ExpDate dataset.

1. Download `Products-Real.zip` (661 MB) from the [ExpDate Google Drive folder](https://drive.google.com/drive/folders/1YuxWzVj6bT6gs6XlewEGetYrdgwZt7EH).
2. Unzip it into `models/cnn/data/`, so that `models/cnn/data/Products-Real/train/` and `models/cnn/data/Products-Real/evaluation/` exist.

The photos and `crops.npz` stay out of Git (`data/` is in `.gitignore`). The trained model, `date_cnn.keras` (6 MB), is in Git, so the app can read dates without the dataset or any training. Running `train_cnn.py` again rewrites it; commit the new file only if the training changed.

## Run

From the project folder, after installing `backend/requirements.txt`:

```bash
backend/.venv/bin/python models/cnn/prepare_data.py   # about 1 minute
backend/.venv/bin/python models/cnn/train_cnn.py      # under 1 minute
backend/.venv/bin/python models/cnn/read_date.py      # under 2 minutes, prints the test numbers
backend/.venv/bin/python models/cnn/read_date.py path/to/photo.jpg   # reads one photo
```

Times are from a MacBook with an M4 chip. On the same computer, training gives the same numbers every run.

Photos must be JPG or PNG. To read an iPhone HEIC photo, convert it first, for example: `sips -s format jpeg IMG_1234.HEIC --out IMG_1234.jpg`.

## Results

Test photos: the first 120 of the ExpDate evaluation set. The CNN never trained on them. They were measured once with the first 10-epoch model (full scanner 0.81). The two settings in "What was tried" were then chosen on other photos. An early trial that shaped the design used 120 random evaluation photos, and 21 of them are in this test set.

| What | Result |
|---|---|
| The top-scoring box holds the expiry date | 0.80 |
| Boxes scoring 0.5 or more (precision / recall) | 0.76 / 0.70 |
| Box reading: the best 3 boxes plus the date pattern | 0.82, 0.21 s per photo |
| Whole-photo reading plus the date pattern | 0.51, 0.58 s per photo |
| Full scanner: box reading, then whole photo | 0.84 |

- A box counts as the date when the centre of the real date box is inside it.
- A read counts as right when the real date's digits appear in the text read.
- Whole-photo reading often stops at a different number first, such as `69.2%`, `5.3g` or a phone number.

Validation (training photos 340-399): accuracy 0.98, precision 0.72, recall 0.65.

What was tried:
- **Epochs.** 10 epochs gave a validation loss of 0.12. It kept falling until epoch 14 (0.07) and rose after about epoch 17, so the CNN trains for 14.
- **Date pattern.** Two stricter patterns were checked on 300 training photos the CNN never used (photos 400-699). Full scanner: simple pattern 0.870, strict pattern 0.847, strict pattern plus a rule for dates like `2021 12 04` 0.877. Neither gained a full point, so the simple pattern stayed.

Known limits:
- The text finder never boxes the date on about 1 photo in 17 (7 of the 120 test photos).
- The CNN finds dates, not which kind. A production date can win over the expiry date. Telling them apart is PP-04 (the BERT label step).
- Dates with month names, like `29 NOV 2021`, don't match the date pattern.
- The date must be the right way up in the photo. Sideways or upside-down text is usually missed or misread, because the rotation step is off on purpose, and a misread can still look like a date.

## Credit

- ExpDate dataset (CC BY 4.0), created at the Korea Institute of Science and Technology (KIST). Seker, A. C., & Ahn, S. C. (2022). A generalized framework for recognition of expiration dates on product packages using fully convolutional networks. *Expert Systems with Applications*, 203, 117310. https://doi.org/10.1016/j.eswa.2022.117310
- [RapidOCR](https://github.com/RapidAI/RapidOCR) (Apache-2.0), which runs PaddleOCR's PP-OCRv6 models.
