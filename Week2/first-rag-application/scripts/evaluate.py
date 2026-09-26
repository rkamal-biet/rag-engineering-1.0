"""
Evaluate retrieval and answers on 22 test questions (20 answerable + 2 out of scope).

    python -m scripts.evaluate                 # retrieval + answer checks (22 LLM calls)
    python -m scripts.evaluate --retrieval-only

Retrieval : Success@1/3/5 and MRR (is the expected file in the top-k, and how high?)
Answers   : expected fact present, correct abstention, valid [S#] citations
Output    : evaluation/evaluation_sheet.csv (answer_grounded / answer_complete / notes left for a human)
"""

import argparse
import csv
from pathlib import Path
from statistics import mean, median
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.tracing import flush
from app.rag.indexing import ingest_directory
from app.rag.pipeline import answer_question
from app.rag.prompting import ABSTAIN_MESSAGE
from app.rag.retrieval import similarity_search

HANDBOOK, REFUND = "novacart_employee_handbook.pdf", "refund_policy.md"
PLUS, IT_FAQ = "novacart_plus_terms.docx", "it_security_faq.txt"

# (question, expected source file, fact the answer must contain) — None = must abstain
TEST_SET = [
    ("How many days of paid annual leave does a confirmed employee get?", HANDBOOK, "24"),
    ("What is the maximum annual leave I can carry forward?", HANDBOOK, "8"),
    ("When do I need a medical certificate for sick leave?", HANDBOOK, "3"),
    ("How many weeks of parental leave does a primary caregiver get?", HANDBOOK, "26"),
    ("How many days a week must employees work from the office?", HANDBOOK, "3"),
    ("How much can I claim for home-office equipment?", HANDBOOK, "25,000"),
    ("What is the deadline to submit a business expense claim?", HANDBOOK, "30"),
    ("What is the notice period after confirmation?", HANDBOOK, "60"),
    ("What is the return window for electronics?", REFUND, "10"),
    ("How long do I have to return shoes or clothes?", REFUND, "30"),
    ("How quickly are UPI refunds processed?", REFUND, "48"),
    ("Name some items that cannot be returned.", REFUND, "innerwear"),
    ("How much is the return pickup fee for non-members?", REFUND, "49"),
    ("How much does NovaCart Plus cost per year?", PLUS, "999"),
    ("Can I get a full refund if I cancel Plus within 14 days?", PLUS, "14"),
    ("How many family members can share a Plus membership?", PLUS, "3"),
    ("When is the renewal reminder sent?", PLUS, "7"),
    ("How often do I have to change my password?", IT_FAQ, "90"),
    ("Are SMS codes allowed for multi-factor authentication?", IT_FAQ, "not"),
    ("Within how many hours must a lost laptop be reported?", IT_FAQ, "24"),
    ("What is NovaCart's share price today?", None, None),
    ("Who won the IPL in 2025?", None, None),
]


def first_relevant_rank(hits: List[Dict[str, Any]], expected_source: str) -> Optional[int]:
    return next((h["rank"] for h in hits if h["payload"]["source"] == expected_source), None)


def success_at_k(rank: Optional[int], k: int) -> int:
    return int(rank is not None and rank <= k)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the RAG pipeline")
    parser.add_argument("--retrieval-only", action="store_true", help="skip the 22 LLM calls")
    args = parser.parse_args()

    ingest_directory(settings.data_dir)          # make sure the index exists (unchanged files are skipped)

    rows = []
    for question, expected_source, expected_fact in TEST_SET:
        row: Dict[str, Any] = {"question": question, "expected_source": expected_source or "(out of scope)"}

        if expected_source:
            hits = similarity_search(question, top_k=5)
            row["retrieved_rank"] = first_relevant_rank(hits, expected_source)
            row["top_score"] = round(hits[0]["score"], 3) if hits else None

        if not args.retrieval_only:
            result = answer_question(question)
            answer = result["answer"]
            abstained = ABSTAIN_MESSAGE.lower().rstrip(".") in answer.lower()
            row.update({
                "fact_present": (expected_fact.lower() in answer.lower()) if expected_fact else None,
                "abstained_correctly": abstained if expected_source is None else not abstained,
                "citations_valid": not result["invalid_citations"],
                "answer": answer,
                "total_ms": result["metrics"]["total_ms"],
                "answer_grounded": "", "answer_complete": "", "notes": "",     # filled in by a human
            })
        rows.append(row)

    ranks = [r["retrieved_rank"] for r in rows if r["expected_source"] != "(out of scope)"]
    print("RETRIEVAL")
    for k in (1, 3, 5):
        print(f"  Success@{k}: {mean(success_at_k(r, k) for r in ranks):.2f}")
    print(f"  MRR      : {mean(1 / r if r else 0 for r in ranks):.2f}")

    if not args.retrieval_only:
        answerable = [r for r in rows if r["expected_source"] != "(out of scope)"]
        print("ANSWERS")
        print(f"  Fact present       : {mean(r['fact_present'] for r in answerable):.2f}")
        print(f"  Abstention correct : {mean(r['abstained_correctly'] for r in rows):.2f}")
        print(f"  Citations valid    : {mean(r['citations_valid'] for r in rows):.2f}")
        print(f"  Median latency (ms): {median(r['total_ms'] for r in rows):.0f}")

    out = Path("evaluation/evaluation_sheet.csv")
    out.parent.mkdir(exist_ok=True)
    fieldnames = list(dict.fromkeys(key for r in rows for key in r))
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nSaved {out} ({len(rows)} rows)")
    flush()


if __name__ == "__main__":
    main()
