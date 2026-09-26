"""
Index every supported file in data/ (or another folder) from the command line.

    python -m scripts.ingest              # skip unchanged files
    python -m scripts.ingest --force      # re-embed everything
    python -m scripts.ingest --path my_docs

Useful with VECTOR_STORE=cloud: index once, then every API server start is instant.
(With in-memory Qdrant the vectors vanish when this script exits — the API indexes at startup instead.)
"""

import argparse

from app.core.config import settings
from app.core.tracing import flush
from app.db.qdrant import count_points, get_qdrant_client
from app.rag.indexing import ingest_directory


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest documents into Qdrant + the registry")
    parser.add_argument("--path", default=str(settings.data_dir), help="folder to ingest (default: data/)")
    parser.add_argument("--force", action="store_true", help="re-embed even unchanged files")
    args = parser.parse_args()

    if settings.vector_store == "memory":
        print("NOTE: VECTOR_STORE=memory -> these vectors disappear when the script exits.\n")

    for r in ingest_directory(args.path, force=args.force):
        print(f"{r['filename']:34s} {r['status']:22s} chunks={r['chunks']:<4} {r['seconds']}s")

    print(f"\nPoints in '{settings.collection_name}': {count_points(get_qdrant_client(), settings.collection_name)}")
    flush()


if __name__ == "__main__":
    main()
