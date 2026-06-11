# pdf-to-md

Conversor de **PDF → Markdown** por línea de comandos, con máxima fidelidad: preserva
estructura, encabezados (detectados por tamaño de fuente), tablas, imágenes embebidas y
metadatos. Soporta **OCR** opcional para PDFs escaneados.

> Versión web (client-side, sin instalar nada) para PDF/Word/Excel:
> [elblogdeismael.github.io/pdf2md](https://elblogdeismael.github.io/pdf2md/)

## Cómo funciona

Enfoque híbrido multi-motor:

- **PyMuPDF (fitz)** — texto con tamaño de fuente (encabezados), imágenes embebidas, render de página.
- **pdfplumber** — detección y extracción de tablas a Markdown GFM.
- **pypdf** — metadatos (título, autor…) y adjuntos embebidos.
- **pytesseract** (opcional) — OCR de páginas sin texto extraíble.

Salida: una carpeta con `output.md` + `images/` (+ `attachments/` si hay adjuntos).

## Instalación

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# OCR (opcional):
sudo apt install tesseract-ocr tesseract-ocr-spa
```

## Uso

```bash
# Básico
python pdf_to_md.py documento.pdf

# Carpeta de salida personalizada
python pdf_to_md.py documento.pdf --output mi_carpeta

# Mayor resolución para páginas visuales
python pdf_to_md.py documento.pdf --dpi 200

# OCR (solo se aplica a páginas sin texto; sube a 300 DPI automáticamente)
python pdf_to_md.py documento_es.pdf --ocr               # español (default)
python pdf_to_md.py documento_en.pdf --ocr --lang eng    # inglés
python pdf_to_md.py documento.pdf   --ocr --lang spa+eng --dpi 300
```

`--lang` elige el modelo de reconocimiento (no traduce). Los idiomas no instalados se
ignoran con un aviso. Ver idiomas: `tesseract --list-langs`.

## Licencia

MIT.
