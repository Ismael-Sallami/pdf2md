# pdf-to-md

![Python](https://img.shields.io/badge/Python-3.12-3776AB)
![PyMuPDF](https://img.shields.io/badge/PyMuPDF-1.24-1a7f37)
[![tests](https://img.shields.io/github/actions/workflow/status/Ismael-Sallami/pdf-to-md/ci.yml?branch=main&logo=github&label=tests)](https://github.com/Ismael-Sallami/pdf-to-md/actions/workflows/ci.yml)
![license](https://img.shields.io/badge/license-MIT-4c1)

A command-line converter that turns a PDF into Markdown: headings taken from the font size,
tables, embedded images, attachments and metadata, with optional OCR for scans.

> There is a browser version for PDF, Word and Excel, with nothing to install:
> [elblogdeismael.github.io/pdf2md](https://elblogdeismael.github.io/pdf2md/)

## Context

A tool of my own, not coursework. University notes arrive as PDF and are read, searched and
edited far better as Markdown, and the converters within reach either flatten everything to
plain text or charge for the ones that do not.

## The problem

A PDF does not know what a heading is. It knows glyphs, positions and font sizes: the
structure a reader sees is something the eye reconstructs. Converting to Markdown means
guessing that structure back, and no single library gives you all of it.

Tables live in the ruling lines, images in the object stream, metadata in a dictionary, and
a scanned page has none of the three because it is a photograph of a page.

## The solution

**One engine per job**, because each one is the best at exactly one thing:

| Engine | What it is asked for | Why that one |
| --- | --- | --- |
| PyMuPDF | Text with its font size, embedded images, page renders | The only one that reports the size of each span |
| pdfplumber | Tables, from the ruling lines | Its table detection is the good one |
| pypdf | Metadata and embedded attachments | Reads the document dictionary without decoding pages |
| Tesseract | Text on pages that have none | Last resort, and only there |

**Heading levels come from the size, relative to the document.** The largest text in the
whole PDF is measured first, and everything is compared against it: 95 % or more is `#`,
80 % is `##`, 68 % is `###`. Fixed thresholds would break the moment a document sets its
body text at 14 pt.

**OCR is the last step, and only on pages without a text layer.** It is orders of magnitude
slower than reading a text layer, and worse: it hands back a guess where the page had the
exact string. The requested languages are checked against the installed models first, so a
missing model warns once instead of failing the run.

## Layout

```
src/pdf_to_md.py          the converter, one file
docs/usage.md             every option, and what OCR needs
tests/test_convert.py     end-to-end test over the fixture
tests/make_fixture.py     builds that fixture
tests/fixtures/sample.pdf a PDF with a heading, a paragraph, an image and a ruled table
requirements.txt          the dependencies
```

## Requirements

- Python 3.12
- `pymupdf` 1.24+, `pdfplumber` 0.11+, `pypdf` 4.0+
- For OCR only: `pytesseract` 0.3.13+, `Pillow` 10+, and Tesseract installed on the system

## Build and run

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python3 src/pdf_to_md.py document.pdf                 # writes ./document/
python3 src/pdf_to_md.py document.pdf --output out    # somewhere else
python3 src/pdf_to_md.py scanned.pdf --ocr            # scans, Spanish and English
```

OCR needs Tesseract and its language models:

```bash
sudo apt install tesseract-ocr tesseract-ocr-spa
```

Running the tests:

```bash
pip install pytest ruff
pytest -q
ruff check .
```

The full list of options is in [`docs/usage.md`](docs/usage.md).

## Results

Converting `tests/fixtures/sample.pdf`, which is what the CI does on every push:

```markdown
---
title: "Sample Document"
author: "Ismael Sallami Moreno"
pages: 1
source: sample.pdf
---

# Sample Document

## First Section

A paragraph of body text at the usual size.

| Language | Extension |
| --- | --- |
| Python | .py |
| Markdown | .md |

![Imagen página 1](images/page_01_img_001.png)
```

The 28 pt title became `#` and the 24 pt one `##` without either being tagged as a heading
anywhere in the PDF; the ruled table came back as GFM; and the embedded image was written to
`images/` and linked.

## What I learned

- The size of the largest text in the document is a better yardstick than any absolute
  threshold. It is one line of code and it is what makes the heading detection survive a
  document that sets its body at 14 pt.
- Reaching for OCR first is the expensive mistake. Most PDFs that look like scans carry a
  text layer underneath, and it is exact where OCR is a guess.
- **Limitations:**
  - **The text of a table comes out twice.** pdfplumber returns the table and PyMuPDF
    returns those same cells as part of the text flow, and the two are not cross-checked, so
    the cells also land in the paragraph above. Visible in the sample output.
  - Headings rest entirely on the font size. A document that marks its sections with bold
    rather than a larger size comes out flat.
  - There is no page-range option: it converts the whole document.
  - OCR is not covered by the tests. It needs Tesseract and its language models, and a test
    that installs them checks Tesseract rather than this converter.
  - The messages the command prints, and the comments in the code, are in Spanish.

## Author and licence

Ismael Sallami Moreno. Released under the MIT licence (see `LICENSE`).
