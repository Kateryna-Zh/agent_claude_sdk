"""Manual KB ingestion script.

Usage:
    python scripts/ingest_kb.py
    python scripts/ingest_kb.py --rebuild
"""

import argparse
import shutil
from pathlib import Path

from app.config import settings
from app.rag.ingest import ingest_kb


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest KB into Chroma.")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Delete existing vector store before ingesting.",
    )
    return parser.parse_args()


def _maybe_rebuild(rebuild: bool) -> None:
    if not rebuild:
        return
    persist_dir = Path(settings.chroma_persist_dir)
    if persist_dir.exists():
        shutil.rmtree(persist_dir)


def main() -> None:
    args = _parse_args()
    _maybe_rebuild(args.rebuild)
    ingest_kb()


if __name__ == "__main__":
    main()
