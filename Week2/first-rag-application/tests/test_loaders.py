import pytest

from app.core.config import settings
from app.loaders.dispatcher import load_directory, load_document


def test_pdf_is_loaded_one_document_per_page():
    pages = load_document(settings.data_dir / "novacart_employee_handbook.pdf")
    assert [p.metadata["page"] for p in pages] == [1, 2, 3, 4]
    assert len({p.document_id for p in pages}) == 1          # all pages share the file's id


@pytest.mark.parametrize("filename, source_type", [
    ("refund_policy.md", "md"), ("it_security_faq.txt", "txt"), ("novacart_plus_terms.docx", "docx"),
])
def test_text_formats_load_with_metadata(filename, source_type):
    docs = load_document(settings.data_dir / filename)
    assert len(docs) == 1 and docs[0].metadata["source_type"] == source_type and docs[0].text.strip()


def test_load_directory_skips_subfolders():
    sources = {d.source for d in load_directory(settings.data_dir)}
    assert "refund_policy_2025.md" not in sources               # data/archive/ is not indexed


def test_unsupported_extension_is_rejected():
    with pytest.raises(ValueError):
        load_document("malware.exe")
