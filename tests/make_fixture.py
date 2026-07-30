#!/usr/bin/env python3
"""Build the PDF the test suite converts.

The fixture is committed so the CI is deterministic: a generated-on-the-fly PDF
would drift with the PyMuPDF version and take the assertions with it. Run this
only to rebuild it.

    python3 tests/make_fixture.py

@author Ismael Sallami Moreno
"""
import zlib
from pathlib import Path

import fitz

FIXTURE = Path(__file__).parent / "fixtures" / "sample.pdf"

# A 64x64 gradient as a raw PNG. Written by hand rather than pulled from a
# library so the fixture has no dependency beyond PyMuPDF. The size is not
# arbitrary: the converter drops anything under 30x30 pixels or 500 bytes,
# taking it for an icon or a decoration.
def _png_bytes() -> bytes:
    width = height = 64
    rows = b""
    for y in range(height):
        rows += b"\x00"  # filter byte: none
        for x in range(width):
            rows += bytes((x * 4 % 256, y * 4 % 256, (x * y) % 256))

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (
            len(payload).to_bytes(4, "big")
            + tag
            + payload
            + zlib.crc32(tag + payload).to_bytes(4, "big")
        )

    header = width.to_bytes(4, "big") + height.to_bytes(4, "big") + bytes((8, 2, 0, 0, 0))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


TABLE = [["Language", "Extension"], ["Python", ".py"], ["Markdown", ".md"]]


def _draw_table(page, x: float, y: float) -> None:
    """Draw a ruled table.

    pdfplumber finds tables by their lines, so the borders are the table as far
    as the converter is concerned. Text alone would come out as a paragraph.
    """
    col_width, row_height = 120, 24
    cols, rows = len(TABLE[0]), len(TABLE)

    for i in range(rows + 1):
        page.draw_line((x, y + i * row_height), (x + cols * col_width, y + i * row_height))
    for j in range(cols + 1):
        page.draw_line((x + j * col_width, y), (x + j * col_width, y + rows * row_height))

    for i, row in enumerate(TABLE):
        for j, cell in enumerate(row):
            page.insert_text(
                (x + j * col_width + 6, y + i * row_height + 16), cell, fontsize=11
            )


def main() -> None:
    doc = fitz.open()
    page = doc.new_page()

    # Heading levels come out of the font size, so the sizes are what matters
    # here. The largest text in the document becomes h1; h2 needs at least 80 %
    # of it, which is why the section is at 24 and not at 18.
    page.insert_text((72, 100), "Sample Document", fontsize=28)
    page.insert_text((72, 150), "First Section", fontsize=24)
    page.insert_text((72, 190), "A paragraph of body text at the usual size.", fontsize=11)

    page.insert_image(fitz.Rect(72, 220, 172, 320), stream=_png_bytes())

    _draw_table(page, x=72, y=360)

    doc.set_metadata({"title": "Sample Document", "author": "Ismael Sallami Moreno"})
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(FIXTURE))
    doc.close()
    print(f"written: {FIXTURE}")


if __name__ == "__main__":
    main()
