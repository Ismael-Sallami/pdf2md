# Usage

Everything the command line takes, and what OCR needs on top.

## Options

| Option | Default | What it does |
| --- | --- | --- |
| `pdf` | — | The file to convert. The only required argument |
| `--output`, `-o` | `<pdf name>/` next to the PDF | Where the output folder goes |
| `--dpi` | 150 | Resolution used to render pages that have no text layer |
| `--ocr` | off | Read the rendered pages with Tesseract. Raises the render to 300 DPI |
| `--lang` | `spa+eng` | Which Tesseract models to use. It picks the recognition model, it does not translate |

## Examples

```bash
python3 src/pdf_to_md.py document.pdf
python3 src/pdf_to_md.py document.pdf --output my_folder
python3 src/pdf_to_md.py document.pdf --dpi 200          # sharper page renders

python3 src/pdf_to_md.py scanned.pdf --ocr               # Spanish and English
python3 src/pdf_to_md.py scanned.pdf --ocr --lang eng    # English only
python3 src/pdf_to_md.py scanned.pdf --ocr --lang spa+eng --dpi 300
```

## OCR

OCR only runs on pages with no extractable text, which is what a scan is. Pages that
already carry a text layer are read from it, because that is both faster and exact.

Tesseract has to be installed on the system; the Python package alone is not enough:

```bash
sudo apt install tesseract-ocr          # base, English included
sudo apt install tesseract-ocr-spa      # Spanish
tesseract --list-langs                  # what you have
```

Languages you ask for but have not installed are dropped with a warning, once per
language, and the conversion carries on with the rest. If none of them are installed the
page is left without OCR text rather than failing.

## Output

```
<output>/
├── output.md        the Markdown, with a YAML header carrying the PDF metadata
├── images/          images pulled out of the PDF, and full-page renders
└── attachments/     files embedded in the PDF, only if there are any
```

Empty folders are removed, so a PDF with no images leaves no `images/` behind.
