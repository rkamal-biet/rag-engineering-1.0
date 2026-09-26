"""POST /rag/query — question in, grounded answer + sources + metrics out."""

from fastapi import APIRouter, HTTPException

from app.core.logging import get_logger
from app.models.api import RAGQueryRequest, RAGQueryResponse
from app.rag.pipeline import answer_question

router = APIRouter(prefix="/rag", tags=["rag"])
log = get_logger(__name__)


@router.post("/query", response_model=RAGQueryResponse)
def rag_query(request: RAGQueryRequest):
    try:
        return answer_question(request.question, top_k=request.top_k, source_filter=request.source_filter)
    except Exception as exc:
        log.exception("Query failed")
        raise HTTPException(status_code=500, detail=str(exc))
