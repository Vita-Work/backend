import asyncio
from pathlib import Path
from zipfile import ZipFile

from src.modules.extraction.parsers import extract_local_cv_text, validate_file_signature


def _write_docx(path: Path) -> None:
    document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Senior Backend Engineer</w:t></w:r></w:p>
    <w:p><w:r><w:t>Python, FastAPI, PostgreSQL</w:t></w:r></w:p>
  </w:body>
</w:document>
"""
    with ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document_xml)


def test_extract_local_cv_text_from_txt(tmp_path: Path) -> None:
    file_path = tmp_path / "resume.txt"
    file_path.write_text("Senior Engineer\n\nPython  FastAPI\n", encoding="utf-8")

    extracted = asyncio.run(extract_local_cv_text(path=file_path, extension=".txt"))

    assert extracted == "Senior Engineer\nPython FastAPI"


def test_extract_local_cv_text_from_docx(tmp_path: Path) -> None:
    file_path = tmp_path / "resume.docx"
    _write_docx(file_path)

    extracted = asyncio.run(extract_local_cv_text(path=file_path, extension=".docx"))

    assert extracted == "Senior Backend Engineer\nPython, FastAPI, PostgreSQL"


def test_validate_file_signature_accepts_pdf(tmp_path: Path) -> None:
    file_path = tmp_path / "resume.pdf"
    file_path.write_bytes(b"%PDF-1.7\nhello")

    validate_file_signature(path=file_path, extension=".pdf")
