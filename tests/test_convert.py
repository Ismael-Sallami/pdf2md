"""End-to-end test: convert tests/fixtures/sample.pdf and read the result.

The fixture carries one of each thing the converter claims to handle, so every
assertion here maps to a sentence in the README. Rebuild it with
`python3 tests/make_fixture.py` if the fixture ever changes.

@author Ismael Sallami Moreno
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import pdf_to_md  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "sample.pdf"


@pytest.fixture(scope="module")
def markdown(tmp_path_factory):
    """Convert the fixture once and hand the Markdown to every test."""
    out = tmp_path_factory.mktemp("converted")
    pdf_to_md.convert(FIXTURE, out, use_ocr=False, dpi=150)
    return (out / "output.md").read_text(encoding="utf-8"), out


def test_metadata_becomes_frontmatter(markdown):
    text, _ = markdown
    assert text.startswith("---")
    assert 'title: "Sample Document"' in text
    assert 'author: "Ismael Sallami Moreno"' in text
    assert "pages: 1" in text


def test_font_size_becomes_heading_level(markdown):
    text, _ = markdown
    # 28 pt is the largest text in the document, so it is h1; 24 pt clears the
    # 80 % threshold and is h2. The 11 pt paragraph stays a paragraph.
    assert "# Sample Document" in text
    assert "## First Section" in text
    assert "# A paragraph" not in text


def test_embedded_image_is_extracted_and_linked(markdown):
    text, out = markdown
    images = sorted((out / "images").iterdir())
    assert len(images) == 1
    assert images[0].name == "page_01_img_001.png"
    assert "](images/page_01_img_001.png)" in text


def test_ruled_table_becomes_gfm(markdown):
    text, _ = markdown
    assert "| Language | Extension |" in text
    assert "| --- | --- |" in text
    assert "| Markdown | .md |" in text


def test_no_attachments_leaves_no_empty_folder(markdown):
    _, out = markdown
    assert not (out / "attachments").exists()
