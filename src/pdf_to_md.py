#!/usr/bin/env python3
"""
pdf_to_md.py — Convierte un PDF a Markdown con máxima fidelidad.

Estructura de salida:
  <nombre_pdf>/
  ├── output.md          ← contenido principal en Markdown
  ├── images/            ← imágenes extraídas del PDF
  │   ├── page_01_img_001.png
  │   └── ...
  └── attachments/       ← archivos adjuntos embebidos (si los hay)
      └── ...

Uso:
  python pdf_to_md.py documento.pdf
  python pdf_to_md.py documento.pdf --output carpeta_destino
  python pdf_to_md.py documento.pdf --ocr          # activa OCR para PDFs escaneados
  python pdf_to_md.py documento.pdf --dpi 200      # resolución para páginas visuales
"""

import argparse
import re
import shutil
import sys
from pathlib import Path

# ── Dependencias ──────────────────────────────────────────────────────────────
MISSING = []
try:
    import fitz  # PyMuPDF
except ImportError:
    MISSING.append("pymupdf")

try:
    import pdfplumber
except ImportError:
    MISSING.append("pdfplumber")

try:
    from pypdf import PdfReader
except ImportError:
    MISSING.append("pypdf")

if MISSING:
    print("❌ Faltan dependencias. Instálalas con:")
    print(f"   pip install {' '.join(MISSING)}")
    sys.exit(1)

# OCR opcional
try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False


# ── Utilidades ─────────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    """Convierte texto en un nombre de fichero seguro."""
    text = re.sub(r"[^\w\s\-]", "", text.lower())
    text = re.sub(r"[\s_]+", "_", text).strip("_")
    return text or "document"


def detect_heading_level(text: str, font_size: float, max_size: float) -> int | None:
    """Heurística: estima nivel de encabezado basándose en el tamaño de fuente."""
    if font_size >= max_size * 0.95:
        return 1
    if font_size >= max_size * 0.80:
        return 2
    if font_size >= max_size * 0.68:
        return 3
    return None


def table_to_md(table: list[list]) -> str:
    """Convierte tabla de pdfplumber a Markdown GFM."""
    if not table:
        return ""

    # Normaliza celdas (None → cadena vacía)
    rows = [[str(cell or "").replace("\n", " ").strip() for cell in row] for row in table]
    col_count = max(len(r) for r in rows)

    # Rellena filas cortas
    rows = [r + [""] * (col_count - len(r)) for r in rows]

    header = rows[0]
    body = rows[1:]

    lines = []
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join(["---"] * col_count) + " |")
    for row in body:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def extract_images_from_page(page_fitz, page_num: int, images_dir: Path, doc) -> list[str]:
    """Extrae imágenes embebidas de una página y devuelve rutas relativas para el MD."""
    refs = []
    image_list = page_fitz.get_images(full=True)

    for img_index, img in enumerate(image_list):
        xref = img[0]
        try:
            base_image = doc.extract_image(xref)
        except Exception:
            continue

        img_bytes = base_image.get("image")
        ext = base_image.get("ext", "png")
        width = base_image.get("width", 0)
        height = base_image.get("height", 0)

        # Descartar imágenes diminutas (iconos, masks, decoraciones)
        if width < 30 or height < 30:
            continue
        if not img_bytes or len(img_bytes) < 500:
            continue

        fname = f"page_{page_num:02d}_img_{img_index + 1:03d}.{ext}"
        fpath = images_dir / fname
        with open(fpath, "wb") as f:
            f.write(img_bytes)

        refs.append(f"images/{fname}")

    return refs


def render_page_as_image(page_fitz, page_num: int, images_dir: Path, dpi: int) -> str:
    """Renderiza la página completa como imagen (para páginas sin texto o vectoriales)."""
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page_fitz.get_pixmap(matrix=mat, alpha=False)
    fname = f"page_{page_num:02d}_render.png"
    fpath = images_dir / fname
    pix.save(str(fpath))
    return f"images/{fname}"


_ocr_lang_warned = set()


def resolve_ocr_lang(lang: str) -> str:
    """Filtra los idiomas pedidos dejando solo los instalados en Tesseract.

    Devuelve la cadena de idiomas disponible (formato 'spa+eng') o "" si ninguno
    está instalado. Avisa una sola vez por idioma faltante.
    """
    requested = [code for code in lang.split("+") if code]
    try:
        available = set(pytesseract.get_languages(config=""))
    except Exception:
        # No se pudo consultar (Tesseract roto/ausente): probamos tal cual
        return lang

    usable = [code for code in requested if code in available]
    for missing in (code for code in requested if code not in available):
        if missing not in _ocr_lang_warned:
            _ocr_lang_warned.add(missing)
            print(
                f"⚠️  Idioma OCR '{missing}' no instalado en Tesseract. "
                f"Instálalo con: sudo apt install tesseract-ocr-{missing}",
                file=sys.stderr,
            )
    return "+".join(usable)


def ocr_page_image(image_path: Path, lang: str = "spa+eng") -> str:
    """Aplica OCR a una imagen de página y devuelve texto."""
    if not OCR_AVAILABLE:
        return ""
    use_lang = resolve_ocr_lang(lang)
    if not use_lang:
        return ""
    try:
        img = Image.open(image_path)
        return pytesseract.image_to_string(img, lang=use_lang)
    except Exception as e:
        print(f"⚠️  Error de OCR en {image_path.name}: {e}", file=sys.stderr)
        return ""


def extract_metadata(pdf_path: Path) -> dict:
    """Lee metadatos del PDF con pypdf."""
    try:
        reader = PdfReader(str(pdf_path))
        meta = reader.metadata or {}
        return {
            "title": meta.get("/Title", ""),
            "author": meta.get("/Author", ""),
            "subject": meta.get("/Subject", ""),
            "creator": meta.get("/Creator", ""),
            "pages": len(reader.pages),
        }
    except Exception:
        return {}


def extract_attachments(pdf_path: Path, attachments_dir: Path) -> list[str]:
    """Extrae archivos adjuntos embebidos en el PDF."""
    saved = []
    try:
        reader = PdfReader(str(pdf_path))
        for name, content_list in (reader.attachments or {}).items():
            safe_name = Path(name).name
            for content in content_list:
                dest = attachments_dir / safe_name
                dest.write_bytes(content)
                saved.append(safe_name)
    except Exception:
        pass
    return saved


# ── Núcleo de conversión ───────────────────────────────────────────────────────

def convert_page(
    page_plumber,
    page_fitz,
    page_num: int,
    images_dir: Path,
    doc_fitz,
    use_ocr: bool,
    dpi: int,
    max_font_size: float,
    lang: str = "spa+eng",
) -> str:
    """Convierte una sola página a Markdown."""
    md_parts = []

    # ── 1. Tablas (pdfplumber) ────────────────────────────────────────────────
    tables = page_plumber.extract_tables() or []
    # Guardamos los bboxes para no repetir ese texto después
    table_bboxes = []
    table_blocks = []

    for table in tables:
        md_table = table_to_md(table)
        if md_table:
            table_blocks.append(md_table)
            # Aproximamos la bbox de la tabla a partir de palabras de la página
            # (pdfplumber no expone bbox directamente en extract_tables)
            # La dejamos como marcador para luego insertarla en orden
            table_bboxes.append(md_table)

    # ── 2. Texto enriquecido (PyMuPDF: bloques con font size) ─────────────────
    blocks = page_fitz.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]

    text_lines = []

    for block in blocks:
        if block["type"] == 1:
            # Bloque de imagen embebida → se tratará en el paso 3
            continue

        for line in block.get("lines", []):
            line_text_parts = []
            max_size_in_line = 0.0
            is_bold = False
            is_italic = False

            for span in line.get("spans", []):
                txt = span["text"].strip()
                if not txt:
                    continue
                size = span["size"]
                flags = span["flags"]
                # flags bit 4 = bold, bit 1 = italic (PyMuPDF convention)
                bold = bool(flags & (1 << 4))
                italic = bool(flags & (1 << 1))
                is_bold = is_bold or bold
                is_italic = is_italic or italic
                max_size_in_line = max(max_size_in_line, size)
                line_text_parts.append(txt)

            if not line_text_parts:
                continue

            raw_text = " ".join(line_text_parts)

            # Detectar encabezados por tamaño
            heading = detect_heading_level(raw_text, max_size_in_line, max_font_size)
            if heading:
                text_lines.append(f"\n{'#' * heading} {raw_text}\n")
            elif is_bold and len(raw_text) < 120:
                text_lines.append(f"**{raw_text}**")
            elif is_italic and len(raw_text) < 120:
                text_lines.append(f"*{raw_text}*")
            else:
                text_lines.append(raw_text)

    # Agrupamos líneas contiguas en párrafos (heurística: si una línea termina
    # con punto/signo o es muy corta respecto a la siguiente, es párrafo nuevo)
    paragraphs = []
    current = []

    for line in text_lines:
        if line.startswith("\n#"):
            # Flush acumulado antes del encabezado
            if current:
                paragraphs.append(" ".join(current))
                current = []
            paragraphs.append(line)
        elif line in ("", "\n"):
            if current:
                paragraphs.append(" ".join(current))
                current = []
        else:
            current.append(line)

    if current:
        paragraphs.append(" ".join(current))

    # Insertar tablas después de todo el texto de la página
    # (inserción precisa requeriría bbox matching; aquí las añadimos al final del bloque)
    page_text = "\n\n".join(p.strip() for p in paragraphs if p.strip())

    if page_text:
        md_parts.append(page_text)

    for t in table_blocks:
        md_parts.append("\n" + t + "\n")

    # ── 3. ¿La página tiene texto extraíble real? ────────────────────────────
    plain_text = page_plumber.extract_text() or ""
    has_text = bool(plain_text.strip())

    # ── 4. Página escaneada / sin texto + OCR ────────────────────────────────
    # Un PDF escaneado guarda cada página como una imagen embebida, así que el
    # disparador del OCR es "no hay texto extraíble", NO "no hay imágenes".
    if not has_text and use_ocr and OCR_AVAILABLE:
        # Renderizar la página completa. Para OCR usamos un DPI mínimo de 300
        # (subir resolución mejora mucho el reconocimiento de texto pequeño).
        ocr_dpi = max(dpi, 300)
        render_ref = render_page_as_image(page_fitz, page_num, images_dir, ocr_dpi)
        ocr_text = ocr_page_image(images_dir / Path(render_ref).name, lang)
        if ocr_text.strip():
            md_parts.append(ocr_text.strip())
        else:
            # OCR no devolvió nada → dejamos la imagen de la página como fallback
            md_parts.append(f"![Página {page_num} (escaneada)]({render_ref})")
        return "\n\n".join(md_parts)

    # ── 5. Imágenes embebidas (páginas con texto, o sin --ocr) ───────────────
    img_refs = extract_images_from_page(page_fitz, page_num, images_dir, doc_fitz)
    for ref in img_refs:
        md_parts.append(f"![Imagen página {page_num}]({ref})")

    # ── 6. Página sin texto y sin OCR → renderizar la página como imagen ─────
    if not has_text and not img_refs:
        render_ref = render_page_as_image(page_fitz, page_num, images_dir, dpi)
        md_parts.append(f"![Página {page_num} (escaneada)]({render_ref})")

    return "\n\n".join(md_parts)


# ── Main ───────────────────────────────────────────────────────────────────────

def convert(pdf_path: Path, output_dir: Path, use_ocr: bool, dpi: int, lang: str = "spa+eng"):
    print(f"📄 Procesando: {pdf_path.name}")

    # Crear estructura de directorios
    output_dir.mkdir(parents=True, exist_ok=True)
    images_dir = output_dir / "images"
    images_dir.mkdir(exist_ok=True)
    attachments_dir = output_dir / "attachments"

    # ── Metadatos ─────────────────────────────────────────────────────────────
    meta = extract_metadata(pdf_path)
    total_pages = meta.get("pages", 0)
    print(f"   Páginas detectadas : {total_pages}")

    # ── Adjuntos ──────────────────────────────────────────────────────────────
    attachments_dir.mkdir(exist_ok=True)
    attachments = extract_attachments(pdf_path, attachments_dir)
    if attachments:
        print(f"   Adjuntos extraídos : {len(attachments)}")
    else:
        # Borrar carpeta vacía
        shutil.rmtree(attachments_dir, ignore_errors=True)

    # ── Tamaño máximo de fuente en todo el documento (para encabezados) ───────
    doc_fitz = fitz.open(str(pdf_path))
    max_font_size = 12.0
    for page in doc_fitz:
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    max_font_size = max(max_font_size, span.get("size", 0))

    # ── Construcción del Markdown ──────────────────────────────────────────────
    md_lines = []

    # Cabecera YAML frontmatter
    md_lines.append("---")
    if meta.get("title"):
        md_lines.append(f'title: "{meta["title"]}"')
    if meta.get("author"):
        md_lines.append(f'author: "{meta["author"]}"')
    if meta.get("subject"):
        md_lines.append(f'subject: "{meta["subject"]}"')
    if meta.get("creator"):
        md_lines.append(f'creator: "{meta["creator"]}"')
    md_lines.append(f"pages: {total_pages}")
    md_lines.append(f"source: {pdf_path.name}")
    md_lines.append("---\n")

    # Si hay adjuntos, listarlos al principio
    if attachments:
        md_lines.append("## Archivos adjuntos\n")
        for att in attachments:
            md_lines.append(f"- [attachments/{att}](attachments/{att})")
        md_lines.append("\n---\n")

    # ── Procesar cada página ──────────────────────────────────────────────────
    with pdfplumber.open(str(pdf_path)) as pdf_plumber:
        for page_num, (page_pl, page_fz) in enumerate(
            zip(pdf_plumber.pages, doc_fitz), start=1
        ):
            print(f"   Página {page_num}/{total_pages}...", end="\r")

            md_lines.append(f"\n<!-- página {page_num} -->\n")
            page_md = convert_page(
                page_pl, page_fz, page_num,
                images_dir, doc_fitz,
                use_ocr, dpi, max_font_size, lang
            )
            md_lines.append(page_md)
            md_lines.append("\n---")  # separador de página

    doc_fitz.close()

    # Limpiar carpeta images si está vacía
    if not any(images_dir.iterdir()):
        shutil.rmtree(images_dir)

    # ── Escribir fichero MD ───────────────────────────────────────────────────
    md_path = output_dir / "output.md"
    full_md = "\n".join(md_lines)

    # Colapsar más de 2 líneas en blanco consecutivas
    full_md = re.sub(r"\n{3,}", "\n\n", full_md)

    md_path.write_text(full_md, encoding="utf-8")

    print("\n✅ Conversión completada:")
    print(f"   📝 Markdown  → {md_path}")
    if images_dir.exists():
        n_imgs = len(list(images_dir.iterdir()))
        print(f"   🖼️  Imágenes  → {images_dir}/ ({n_imgs} archivo/s)")
    if attachments_dir.exists():
        print(f"   📎 Adjuntos  → {attachments_dir}/")


def main():
    parser = argparse.ArgumentParser(
        description="Convierte un PDF a Markdown preservando toda la información."
    )
    parser.add_argument("pdf", help="Ruta al fichero PDF")
    parser.add_argument(
        "--output", "-o",
        help="Directorio de salida (por defecto: <nombre_pdf>/)",
        default=None,
    )
    parser.add_argument(
        "--ocr",
        action="store_true",
        help="Activar OCR en páginas escaneadas (requiere pytesseract + Tesseract)",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=150,
        help="Resolución (DPI) para renderizar páginas sin texto (defecto: 150). "
             "Con --ocr se usa un mínimo de 300 DPI para mejorar el reconocimiento.",
    )
    parser.add_argument(
        "--lang",
        default="spa+eng",
        help="Idioma(s) de Tesseract para OCR, formato 'spa+eng' (defecto: spa+eng). "
             "Los idiomas no instalados se ignoran con aviso.",
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf).expanduser().resolve()
    if not pdf_path.exists():
        print(f"❌ No se encuentra el fichero: {pdf_path}")
        sys.exit(1)
    if pdf_path.suffix.lower() != ".pdf":
        print("⚠️  El fichero no tiene extensión .pdf, continuando igualmente...")

    if args.output:
        output_dir = Path(args.output).expanduser().resolve()
    else:
        output_dir = pdf_path.parent / slugify(pdf_path.stem)

    if args.ocr and not OCR_AVAILABLE:
        print("⚠️  --ocr solicitado pero pytesseract/Pillow no están instalados.")
        print("   Instálalos con: pip install pytesseract pillow")
        print("   Y asegúrate de tener Tesseract en el PATH.")

    convert(pdf_path, output_dir, use_ocr=args.ocr, dpi=args.dpi, lang=args.lang)


if __name__ == "__main__":
    main()
