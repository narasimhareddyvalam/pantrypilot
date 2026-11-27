# PantryPilot

**An AI-powered pantry assistant for smarter food inventory management.**

PantryPilot is a smart food inventory management application designed to help users organize their groceries, understand food date labels, track upcoming expiration and best-before dates, and reduce avoidable food waste.

By combining computer vision, natural language processing, and generative AI, PantryPilot aims to simplify the process of managing everyday food products.

Some parts of PantryPilot were built with help from AI coding tools (vibe coding).

> **Project Status:** Planning & Early Development  
> PantryPilot is currently under development. The features and capabilities described below are planned and may evolve as the project progresses.

## Overview

Keeping track of groceries can be difficult, especially when products have different date-label formats, unclear packaging information, or no printed expiration date at all.

PantryPilot aims to address these challenges by providing a centralized inventory system supported by AI-powered product scanning and date-label interpretation.

Instead of manually tracking every product, users will be able to photograph food packaging, review extracted information, and maintain an organized inventory of their food products.

## Key Features

The following capabilities are planned for PantryPilot.

### Intelligent Product Scanning

- Upload or capture images of food packaging.
- Detect and extract visible product information.
- Recognize printed dates and associated labels.
- Allow users to review and correct extracted information before saving.

### Smart Date Recognition

- Identify common labels such as **Expiration**, **Use By**, **Best Before**, and **Sell By**.
- Distinguish manufacturing dates from expiration-related dates.
- Interpret explicitly stated shelf-life information where available.
- Handle ambiguous or unreadable dates without inventing missing information.

### Pantry Inventory Management

- Add, view, edit, and remove food products.
- Maintain product information and relevant dates.
- Organize inventory by category.
- Track products with upcoming date-label deadlines.
- Support products that do not have a known expiration date.

### Date Tracking and Notifications

- Highlight products approaching their recorded dates.
- Organize products by date and priority.
- Provide reminders for upcoming dates, subject to implementation scope.
- Help users identify products that may need attention.

### AI-Powered Food Assistance

Potential future enhancements include:

- Recipe recommendations based on available ingredients.
- Ingredient prioritization based on recorded dates.
- Food storage guidance.
- Natural-language assistance for understanding product information.

These enhancements are exploratory and are not part of the confirmed initial feature set.

## How PantryPilot Works

The proposed user workflow consists of five steps:

1. **Scan:** Capture or upload an image of a food product.
2. **Analyze:** Extract product details and identify available date information.
3. **Verify:** Review and correct AI-generated results when necessary.
4. **Organize:** Save the product to the pantry inventory.
5. **Track:** Monitor upcoming dates and manage inventory from a centralized dashboard.

## Handling Real-World Edge Cases

Food products do not always contain a clearly identifiable expiration date.

PantryPilot is designed around the principle that **missing or uncertain information should never be presented as a confirmed fact**.

The application will aim to handle scenarios including:

| Scenario | Intended Behavior |
|---|---|
| Clearly printed expiration date | Extract and record the date |
| Best-before or sell-by label | Preserve the original date-label type |
| Manufacturing date only | Record the manufacturing date without assuming expiration |
| Explicit shelf-life instructions | Calculate a derived date when sufficient information is available |
| No printed date | Allow the product to be stored without a known expiration date |
| Blurry or unreadable label | Request another image or manual entry |
| Ambiguous date format | Request user confirmation |
| Multiple printed dates | Distinguish and record the relevant date types |

**Food safety note:** Printed date labels and estimated freshness windows do not independently establish whether a product is safe to consume. PantryPilot is intended as an inventory and informational tool, not a food-safety certification system.

## AI and Machine Learning

PantryPilot is being designed to explore how multiple AI techniques can work together within a practical application.

Potential areas of exploration include:

| Area | Proposed Application |
|---|---|
| Computer Vision | Analyze packaging images and locate relevant information |
| Optical Character Recognition | Extract printed text and dates |
| Natural Language Processing | Interpret date labels and surrounding context |
| Classification Models | Categorize extracted information and identify date types |
| Generative AI | Provide contextual explanations and optional food assistance |

Specific models, datasets, frameworks, and evaluation methods will be documented after the technical design is finalized.

## Technology Stack

Most of the stack is chosen. The rest is decided as each part is built.

| Component | Status |
|---|---|
| Frontend | Phone web page (HTML, CSS, plain JavaScript) served by Flask |
| Backend | Python 3.12 + Flask |
| Database | SQLite |
| Computer Vision / OCR | RapidOCR (PP-OCRv6 models) finds and reads the text; a small Keras CNN picks the date line |
| Machine Learning Framework | TensorFlow Keras for the scanner (CNN, BERT); the GAN and VAE owners choose theirs |
| Generative AI Integration | To be decided |
| Deployment | Runs on the demo laptop; phones open it over Wi-Fi |

Technology choices will prioritize maintainability, practical performance, and suitability for the project's scope.

## Development Roadmap

PantryPilot is currently in the planning stage.

- [x] Define the initial project concept
- [x] Create the GitHub repository
- [x] Establish repository code ownership
- [ ] Finalize the minimum viable product (MVP)
- [ ] Select AI models and supporting technologies
- [ ] Design the application architecture
- [ ] Implement product scanning and date extraction
- [ ] Implement inventory management
- [ ] Integrate and evaluate AI components
- [ ] Test real-world scenarios and edge cases
- [ ] Prepare the application for demonstration

A detailed development roadmap will be maintained separately as the project progresses.

## Run

```bash
cd backend
python3.12 -m venv .venv            # or: uv venv -p 3.12 --seed .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/python app.py
```

The app prints two addresses. Open the first one on this computer, or the second one on a phone connected to the same Wi-Fi. Until the pantry and assistant APIs are ready, the Pantry and Assistant tabs use sample data. To see the review screen for an unclear photo, open the address with `/?sample=ambiguous` at the end.

Windows commands and more details are in [run_guide.txt](run_guide.txt).

## API so far

| Method | Path | What it does |
|---|---|---|
| GET | `/` | the phone page with the Scan, Pantry and Assistant tabs |
| POST | `/scans` | read the date label from a photo (form field `image`) |
| GET, POST | `/pantry/items` | list or add pantry items (coming, Yuhao) |
| PATCH, DELETE | `/pantry/items/<id>` | change or remove one item (coming, Yuhao) |
| POST | `/assistant` | ask a question about label dates (coming, Sreeja) |

Every error comes back as `{"error": "<one polite sentence>", "code": "<code>"}`.

## Contributing

PantryPilot is currently developed by a small project team.

Development follows a feature-branch and pull-request workflow. Changes to the protected `main` branch are subject to repository review requirements.

Detailed contribution guidelines will be added as the development workflow is finalized.

## Project Background

PantryPilot is being developed as a team project exploring practical applications of artificial intelligence and generative modeling.

The project emphasizes combining AI techniques with useful software functionality, handling real-world uncertainty, and evaluating the reliability of model-generated results.

## Credits

- ExpDate dataset (CC BY 4.0), created at the Korea Institute of Science and Technology (KIST). Seker, A. C., & Ahn, S. C. (2022). A generalized framework for recognition of expiration dates on product packages using fully convolutional networks. *Expert Systems with Applications*, 203, 117310. https://doi.org/10.1016/j.eswa.2022.117310
- [RapidOCR](https://github.com/RapidAI/RapidOCR) (Apache-2.0), which runs PaddleOCR's PP-OCRv6 models.

## License

No open-source license has been selected at this stage.

The repository is publicly accessible, but its contents are not automatically licensed for unrestricted reuse, modification, or redistribution.
