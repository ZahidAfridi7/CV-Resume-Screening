from app.core.text_normalizer import normalize_text

def test_empty():
    assert normalize_text(None) == ""
    assert normalize_text("") == ""

def test_whitespace():
    assert normalize_text("  a   b  ") == "a b"

def test_truncate():
    assert len(normalize_text("x" * 20000, max_chars=8000)) == 8000
