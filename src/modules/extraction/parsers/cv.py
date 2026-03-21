from __future__ import annotations

import asyncio
import zipfile
from pathlib import Path
from xml.etree import ElementTree

DOCX_XML_NAMESPACE = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def _normalize_text(text: str) -> str:
    normalized_lines = [" ".join(line.split()) for line in text.splitlines()]
    non_empty_lines = [line for line in normalized_lines if line]
    return "\n".join(non_empty_lines).strip()


def _extract_text_like_file(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        text = raw.decode("utf-8-sig", errors="replace")
    elif raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = raw.decode("utf-16", errors="replace")
    else:
        text = raw.decode("utf-8", errors="replace")
    return _normalize_text(text)


def _extract_docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        document_xml = archive.read("word/document.xml")

    root = ElementTree.fromstring(document_xml)
    paragraphs: list[str] = []

    for paragraph in root.findall(".//w:p", DOCX_XML_NAMESPACE):
        text_parts = [
            node.text for node in paragraph.findall(".//w:t", DOCX_XML_NAMESPACE) if node.text
        ]
        if text_parts:
            paragraphs.append("".join(text_parts))

    return _normalize_text("\n".join(paragraphs))


async def extract_local_cv_text(*, path: Path, extension: str) -> str | None:
    """Extract normalized text for formats best handled locally."""
    normalized_extension = extension.lower()
    if normalized_extension in {".txt", ".md"}:
        return await asyncio.to_thread(_extract_text_like_file, path)
    if normalized_extension == ".docx":
        return await asyncio.to_thread(_extract_docx_text, path)
    return None


def validate_file_signature(*, path: Path, extension: str) -> None:
    """Perform a lightweight signature check for binary formats."""
    normalized_extension = extension.lower()
    with path.open("rb") as file_obj:
        header = file_obj.read(8)

    if normalized_extension == ".pdf" and not header.startswith(b"%PDF-"):
        raise ValueError("Uploaded file does not look like a valid PDF.")

    if normalized_extension == ".docx" and not header.startswith(b"PK"):
        raise ValueError("Uploaded file does not look like a valid DOCX document.")
