# PantryPilot

**An AI-powered pantry assistant for smarter food inventory management.**

PantryPilot helps people keep track of the food they have at home. Take a photo of a food package, and the app finds the printed date and tells you what kind of date it is. You check what it read, and the item goes into your pantry list, sorted by the date that comes first. An assistant answers questions about date labels and about the items in your pantry.

PantryPilot is the team project for CSYE 7380, Theory and Practical Applications of AI Generative Modeling (Northeastern University, Fall 2026).

Some parts of PantryPilot were built with help from AI coding tools (vibe coding).

> **Status (Nov 27, 2026):** The phone page and the scanner work on real photos. The Pantry and Assistant tabs use sample data until the pantry API and the assistant API are connected. The GAN and VAE experiments are in progress.

## Features

### Scan a package

- Take a photo with the phone's camera, or choose one from the phone.
- The app finds the printed date, reads it, and names its label type: Use by / Expires, Best before, Sell by, or Made on.
- When a package prints a production date and an expiry date, the expiry date is filled in. If no label word says which is which, the app uses the later date and asks you to check it.
- When the app isn't sure, it says "Please check this". You can correct the details, type them in yourself, or retake the photo. Nothing is saved until you have checked it.

### Your pantry

- Every item shows its label type, its date, and how many days are left.
- The list is sorted by date, soonest first. Items without a date go last.
- Add, edit and delete items, including items with no date.

### Ask about dates

- Ask what a label means, like "What does best before mean?", or ask about an item, like "When does my yogurt expire?".
- The answers explain the words on the label. They never promise that food is safe to eat.

### Made for phones

- One web page with three tabs, served by the laptop. Any phone on the same Wi-Fi can open it.
- It works in iPhone Safari and Android Chrome, in light and dark mode. On iPhone it can be added to the Home Screen and opens full screen.

## How the scan works

| Step | What happens | Built with |
|---|---|---|
| 1 | Find every line of text on the photo. | RapidOCR (PP-OCRv6 models) |
| 2 | Score each line: how likely is it the date? | A small CNN trained on the ExpDate dataset |
| 3 | Read the 3 best-scoring lines and keep the ones that look like a date. | RapidOCR |
| 4 | Name the label type of each date line from the line and the 3 lines nearest to it. A date with an expiry label is chosen over a production date; with no label word, the latest date is used. | BERT (`bert_tiny_en_uncased`), fine-tuned |
| 5 | Turn the date into YYYY-MM-DD, and send anything unsure to "Please check this". | Simple rules in `backend/dates.py` |

If no line looks like a date, the app reads the whole photo instead and asks the user to check what it found.

## Results

The scanner's models, data and results are in [models/cnn/README.md](models/cnn/README.md) (finding and reading the date) and [models/bert/README.md](models/bert/README.md) (the label type). The whole scan was measured with `backend/measure_scans.py` on 402 package photos that no model learned from:

- 61% of scans (245) came back without "Please check this". All 245 dates are printed on the package. 241 match the dataset's labels. The other 4 are mistakes in the labels: the photos print the date the app read.
- The right printed date was filled in for 69% of photos (278). 59 of the photos print a date that can be read two ways, so the date is left empty for the user to type in.
- When the date was right, the label type was right 96% of the time.
- A scan takes about 0.2 seconds on a MacBook with an M4 chip, plus the time to send the photo.
- 19 photos print two or more different dates that can each be read as one day, usually a production date and an expiry date. The app filled in the latest one, the expiry date, on 14 of them. It never showed an earlier date as sure: on the 3 photos where it filled one in, it asked the user to check it. On the last 2, the user types the date in.

A date counts as right when it is one of the dates printed on the package.

These numbers are from after a fix on Nov 27. A phone test with a real package showed that the app could fill in the production date instead of the expiry date. Looking into it also showed that dates with month names, like `10 AUG 2022`, were skipped. Before the fix, the same photos gave 61% shown as sure and 64% with the right date (257).

## Real-world cases

PantryPilot follows one rule: missing or uncertain information is never shown as a confirmed fact.

| What the package shows | What the app does |
|---|---|
| A clearly printed expiry date | Reads it and fills it in. |
| A best-before or sell-by date | Fills it in and keeps the label type. |
| A manufacturing date only | Fills it in as "Made on", not as an expiry date. |
| A production date and an expiry date | Fills in the expiry date. If no label word says which is which, it uses the later date and asks the user to check it. |
| A date that can be read two ways, like 03/04/27, or two dates on one line | Leaves the date empty and asks the user to type it in. |
| Month and year only, like 05/2027 | Uses the last day of that month and asks the user to check it. |
| No printed date | The item can be saved without a date. |
| A blurry or unreadable label | Asks the user to retake the photo or type the details in. |
| A date printed sideways | Usually missed. Hold the phone so the date is upright. |

Shelf-life text, like "use within 3 days of opening", is not read. The user types the date in.

**Food safety note:** Printed date labels do not prove whether a product is safe to eat. PantryPilot is an inventory and information tool, not a food-safety system.

## Technology stack

| Part | Built with |
|---|---|
| Phone page | HTML, CSS and plain JavaScript, served by Flask |
| Backend | Python 3.12 and Flask |
| Text finding and reading | RapidOCR (PP-OCRv6 models on ONNX Runtime) |
| Date finder | A small CNN in TensorFlow Keras |
| Label types | BERT through KerasHub |
| Pantry storage | SQLite (coming, with the pantry API) |
| Assistant | An LLM (coming, with the assistant API) |
| Synthetic date-label images | A GAN and a VAE (in progress) |
| Running it | On the demo laptop; phones open it over Wi-Fi |

## Run

```bash
cd backend
python3.12 -m venv .venv            # or: uv venv -p 3.12 --seed .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/python app.py
```

The install downloads about 0.5 GB (more on Linux) and needs about 2 GB of disk space, mostly TensorFlow for the scanner. Set up before? After pulling, run the install line again, because the scanner needs TensorFlow, RapidOCR and KerasHub. On start, the app loads the scanner's models (a few seconds), then prints two addresses. Open the first one on this computer, or the second one on a phone connected to the same Wi-Fi. Until the pantry and assistant APIs are ready, the Pantry and Assistant tabs use sample data. To see the review screen for an unclear photo, open the address with `/?sample=ambiguous` at the end.

Windows commands and more details are in [run_guide.txt](run_guide.txt).

## API

| Method | Path | What it does |
|---|---|---|
| GET | `/` | the phone page with the Scan, Pantry and Assistant tabs |
| POST | `/scans` | read the date and its label type from a photo (form field `image`); `?sample=readable`, `ambiguous` or `unreadable` returns a test example instead |
| GET, POST | `/pantry/items` | list or add pantry items (coming, Yuhao) |
| PATCH, DELETE | `/pantry/items/<id>` | change or remove one item (coming, Yuhao) |
| POST | `/assistant` | ask a question about label dates (coming, Sreeja) |

A scan comes back as `{"rawText": "...", "labelType": "...", "date": "YYYY-MM-DD", "requiresReview": true}`. `labelType` and `date` are null when they are not known. Every error comes back as `{"error": "<one polite sentence>", "code": "<code>"}`.

## Project structure

| Folder | What is in it |
|---|---|
| `backend/` | The Flask app: the phone page, the scan endpoint, the date rules, and `measure_scans.py` |
| `models/cnn/` | The date finder: data preparation, CNN training, and the trained CNN |
| `models/bert/` | The label-type classifier: training lines, training, and the trained BERT |
| `shared/fixtures/` | The example scan results the team agreed on |
| `run_guide.txt` | Step-by-step run instructions, including Windows |

## Team

| Person | Parts |
|---|---|
| Narasimha | Phone page, scanner (CNN and OCR), BERT label types, release |
| Yuhao | Pantry API and SQLite storage, GAN |
| Sreeja | Assistant API with the LLM, VAE |

Changes go into the protected `main` branch through pull requests.

## Credits

- ExpDate dataset (CC BY 4.0), created at the Korea Institute of Science and Technology (KIST). Seker, A. C., & Ahn, S. C. (2022). A generalized framework for recognition of expiration dates on product packages using fully convolutional networks. *Expert Systems with Applications*, 203, 117310. https://doi.org/10.1016/j.eswa.2022.117310
- [RapidOCR](https://github.com/RapidAI/RapidOCR) (Apache-2.0), which runs PaddleOCR's PP-OCRv6 models.
- BERT (Devlin et al., 2019): the `bert_tiny_en_uncased` weights (Turc et al., 2019) through [KerasHub](https://github.com/keras-team/keras-hub) (Apache-2.0).
- Fonts: Atkinson Hyperlegible Next and Doto (SIL Open Font License).

## License

No open-source license has been selected at this stage.

The repository is publicly accessible, but its contents are not automatically licensed for unrestricted reuse, modification, or redistribution.
