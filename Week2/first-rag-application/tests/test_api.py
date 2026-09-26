"""End-to-end API tests: startup ingestion -> upload -> list -> query."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:          # "with" runs the lifespan -> data/ is ingested at startup
        yield c


def test_health_after_startup_ingestion(client):
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["points"] > 0 and body["documents"] >= 4


def test_list_documents_are_completed(client):
    docs = client.get("/documents").json()
    assert {d["ingestion_status"] for d in docs} == {"completed"}


def test_query_returns_answer_with_valid_citations(client):
    r = client.post("/rag/query", json={"question": "How many days of annual leave do employees get?", "top_k": 3})
    body = r.json()
    assert r.status_code == 200
    assert body["sources"][0]["source"] == "novacart_employee_handbook.pdf"
    assert body["sources"][0]["cited"] and body["invalid_citations"] == []


def test_source_filter_limits_search_to_one_file(client):
    r = client.post("/rag/query", json={"question": "refund", "source_filter": "it_security_faq.txt"})
    assert {s["source"] for s in r.json()["sources"]} == {"it_security_faq.txt"}


def test_upload_then_fetch_document(client):
    content = b"NovaCart support is available 24x7 through in-app chat."
    r = client.post("/documents/upload", files={"file": ("support_faq.txt", content, "text/plain")})
    assert r.status_code == 200 and r.json()["status"] == "completed"

    detail = client.get(f"/documents/{r.json()['document_id']}").json()
    assert detail["chunks_in_registry"] == detail["points_in_qdrant"] == 1


def test_upload_rejects_unsupported_file_type(client):
    r = client.post("/documents/upload", files={"file": ("virus.exe", b"x")})
    assert r.status_code == 400


def test_unknown_document_returns_404(client):
    assert client.get("/documents/doc-does-not-exist").status_code == 404


def test_empty_question_is_rejected(client):
    assert client.post("/rag/query", json={"question": ""}).status_code == 422
