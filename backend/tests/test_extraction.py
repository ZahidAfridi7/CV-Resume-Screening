from pathlib import Path
import tempfile
import pytest
from docx import Document
from app.services.extraction.service import ExtractionError, ExtractionService


def _make_docx(path, text):
    doc = Document()
    doc.add_paragraph(text)
    doc.save(path)


def test_extract_unsupported_type():
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        path = Path(f.name)
    try:
        with pytest.raises(ExtractionError, match="Unsupported file type"):
            ExtractionService.extract_from_path(path)
    finally:
        path.unlink(missing_ok=True)


def test_extract_file_not_found():
    with pytest.raises(ExtractionError, match="File not found"):
        ExtractionService.extract_from_path("/nonexistent/file.pdf")


def test_extract_docx_simple():
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        path = Path(f.name)
    try:
        _make_docx(path, "Hello World from DOCX")
        text = ExtractionService.extract_from_path(path)
        assert "Hello World from DOCX" in text
    finally:
        path.unlink(missing_ok=True)
