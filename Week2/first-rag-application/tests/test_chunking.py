import pytest

from app.models.document import Document
from app.rag.chunking import chunk_document, normalize_text


def make_doc(num_words: int) -> Document:
    return Document(document_id="doc-test", text=" ".join(f"w{i}" for i in range(num_words)),
                    source="test.txt", metadata={"page": None})


def test_normalize_collapses_spaces_and_blank_lines():
    assert normalize_text("a   b\r\n\r\n\r\n\r\nc") == "a b\n\nc"


def test_chunks_overlap_by_the_requested_number_of_words():
    chunks = chunk_document(make_doc(250), chunk_size=100, overlap=20)
    assert [(c.metadata["word_start"], c.metadata["word_end"]) for c in chunks] == [(0, 100), (80, 180), (160, 250)]


def test_chunk_ids_are_stable_across_runs():
    first = [c.chunk_id for c in chunk_document(make_doc(250), 100, 20)]
    second = [c.chunk_id for c in chunk_document(make_doc(250), 100, 20)]
    assert first == second and len(set(first)) == len(first)


def test_overlap_must_be_smaller_than_chunk_size():
    with pytest.raises(ValueError):
        chunk_document(make_doc(50), chunk_size=10, overlap=10)
