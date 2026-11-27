# Label-type classifier (BERT)

Decides what kind of date a package shows (ticket PP-04): `expiration`, `best_before`, `sell_by`, `manufacturing`, or `other` when no label word goes with the date.

BERT reads the date line plus the 3 lines nearest to it, joined with `" | "`. For example, `2022.08.31 | Best before: | NET WT 500g | KEEP REFRIGERATED` gives `best_before`. In the ExpDate photos, the label word is on the date line itself only about half the time. With the 3 nearest lines, it is there about 8 times in 10 (9 in 10 on PP-03's 120 test photos).

| File | What it does |
|---|---|
| `make_train_lines.py` | Makes 5,000 practice lines (1,000 per label type) from keyword lists, real date formats, other package text and OCR-style typos. |
| `collect_real_lines.py` | Reads real lines from ExpDate photos with the PP-03 OCR code: for every labelled date, the line that holds it (found with the dataset's date box, not the CNN) and its 3 nearest lines. 706 lines come from the evaluation photos, and 417 test lines from training photos `img_00701.jpg` to `img_01102.jpg`. |
| `real_lines.csv`, `test_lines.csv` | Those real lines with their labels (made with AI help, see below). |
| `train_bert.py` | Trains `bert_tiny_en_uncased`, tests it next to keyword rules, and saves `label_model/`. |
| `label_type.py` | `find_label_type(text)` returns the label type and how sure BERT is. The scan endpoint will use it (next PR). |
| `label_model/` | The trained model (18 MB). It is in Git, so the app runs without any training. |

## Run

From the project folder, after installing `backend/requirements.txt`:

```bash
backend/.venv/bin/python models/bert/make_train_lines.py     # a few seconds
backend/.venv/bin/python models/bert/collect_real_lines.py   # optional, about 3 minutes (see below)
backend/.venv/bin/python models/bert/train_bert.py           # under 1 minute, downloads BERT (17 MB) the first time
backend/.venv/bin/python models/bert/label_type.py "2022.08.31 | Best before: | NET WT 500g"
```

- `collect_real_lines.py` only re-reads the real lines for labelling, and needs the ExpDate photos (see `models/cnn/README.md`). `train_bert.py` uses the labelled copies that are in Git.
- `data/` stays out of Git. `label_model/` is in Git, and `train_bert.py` rewrites it, at least `metadata.json`. Commit it only if the training changed.
- On the same computer, training gives the same numbers every run.
- Training needs macOS or Linux, because KerasHub's training path uses `tensorflow-text`, which has no Windows version. `label_type.py` works on Windows too.

## How the real lines were labelled

Every line got one label, decided from its text alone, which is all BERT sees:

1. A label word on the date line decides.
2. Otherwise, the nearest line that is only a label word decides.
3. A nearby label word that has its own date belongs to that other date.
4. With no label word, the label is `other`.

Label words in any language count. `USE BY` counts as expiration, as in the team's scan examples.

The labels were made with an AI assistant: two separate passes, each following the same written rules, agreed on every line (706 and 417). That is weaker evidence than two people agreeing, and no person has checked them line by line.

In one test photo (`img_01020.jpg`, test lines 334 and 335), a single OCR line holds two dates. Each row takes the label word next to its own date, so the text alone can't tell the two rows apart.

## Results

Test lines: 417 lines from training photos `img_00701.jpg` to `img_01102.jpg`. Nothing learned from them, and no setting was chosen with them. They were scored twice: for the first version (0.94 on all lines), and for this one, after a code review changed the practice lines.

| Lines | BERT | Keyword rules |
|---|---|---|
| All | **0.95** | 0.92 |
| With an English label word (78) | **0.94** | 0.74 |
| With no label word (327) | 0.97 | **1.00** |
| With a label word in another language (12) | **0.50** | 0.08 |
| Expiration (25) | **0.96** | 0.88 |
| Best before (55) | **0.84** | 0.56 |
| Manufacturing (10) | **0.90** | 0.60 |

- The test lines start from the right date line. In the app, the CNN picks the line, and PP-03's full scanner reads the expiry date right on 0.84 of its test photos. So the app's label-type accuracy is lower, and it hasn't been measured yet.
- The keyword rules use the same English words as the practice lines and the same 4 labelling rules. They miss typos and joined words like `Bestbefore` or `Best Befre`. They also find dates with PP-03's number pattern, so a label word with a month-name date (`MFG DEC2020`) counts as a label line. That is their one miss on lines with no label word.
- BERT reads typos, but sometimes gives a label type to a line that has no label word.
- Training: 5,000 practice lines plus 558 real lines (evaluation photos `test_00001` to `test_00532`), each real line used 3 times. Validation: 148 real lines (`test_00533` to `test_00665`), accuracy 0.90.

What was tried:
- **Practice lines alone.** The first runs trained only on practice lines and were measured on the evaluation-photo lines, which were the test set then. After 3 epochs at learning rate 1e-4, BERT gave a label type to 11% of the lines with no label word. After 11 epochs at 3e-4 (the best setting on the practice lines), it was 43%. The made-up "other" lines look too clean next to real OCR text. So the labelled evaluation lines became training data, and a new test set was labelled from photos nothing had used.
- **Settings.** Trial runs, checked on the validation lines only: learning rate 1e-4 or 3e-4, real lines used once or 3 times, 12 epochs. The lowest validation loss was 1e-4 with the real lines 3 times, at epoch 2.
- **Junk lines.** Practice lines with random OCR junk made no difference on validation (0.355 vs 0.357), so they were left out.
- **After the code review.** The practice lines gained maker lines ("MANUFACTURED FOR ACME FOODS" now counts as other text) and examples where the nearest of two label words decides. The lines go in a fixed order, practice first and then the real lines, which had a lower validation loss than a shuffled order (0.34 against 0.42).

Known limits:
- BERT's word list is English. Letters with accents (à, é), Korean and most Chinese characters become "unknown". The 12 other-language test lines are Italian, French, Spanish, Dutch and Turkish, and only 23 real training lines have other-language words, so BERT got 6 of the 12 right.
- The dataset has no real sell-by lines (they are a US shop label), so `sell_by` is learned from practice lines only.
- When two label words sit on their own lines near a bare date, BERT doesn't always pick the nearest. It is less sure then, and the app asks the user to check when BERT is under 0.7 sure.
- The label type is only as good as the text. If the OCR misses the label word, or it is more than 3 lines away, BERT says `other`.
- `label_type.py` takes about 0.01 s per line on a MacBook with an M4 chip.

## Credit

- BERT: Devlin et al. (2019). The `bert_tiny_en_uncased` weights (Turc et al., 2019) come through [KerasHub](https://github.com/keras-team/keras-hub) (Apache-2.0).
- ExpDate dataset (CC BY 4.0): see `models/cnn/README.md`.
