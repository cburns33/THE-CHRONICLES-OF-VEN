#!/usr/bin/env python3
"""
CLI query tool for testing retrieval.

Usage:
  python scripts/query.py "find all passages mentioning the Ash Crown"
  python scripts/query.py "where is Elric first introduced" --top-k 5
  python scripts/query.py "Silver Oath" --entity
  python scripts/query.py --stats
"""

import argparse
import sys
import io
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Force UTF-8 output on Windows so Unicode characters in the manuscript print cleanly
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from src.retrieval.query_engine import semantic_search, entity_search
from src.retrieval.formatters import format_for_terminal
from src.indexing.vector_store import collection_stats
from src.indexing.sqlite_store import get_all_chapters


def main():
    parser = argparse.ArgumentParser(description="Query the novel index")
    parser.add_argument("query", nargs="?", help="Search query")
    parser.add_argument("--top-k", type=int, default=None, help="Number of results")
    parser.add_argument("--chapter", type=str, default=None, help="Filter by chapter slug")
    parser.add_argument("--character", type=str, default=None, help="Filter by character name")
    parser.add_argument("--entity", action="store_true", help="Entity/chapter lookup instead of semantic search")
    parser.add_argument("--stats", action="store_true", help="Show index statistics")
    parser.add_argument("--chapters", action="store_true", help="List all indexed chapters")
    args = parser.parse_args()

    if args.stats:
        stats = collection_stats()
        print(f"Total chunks in index: {stats['total_chunks']}")
        chapters = get_all_chapters()
        print(f"Total chapters:        {len(chapters)}")
        return

    if args.chapters:
        chapters = get_all_chapters()
        for ch in chapters:
            print(f"  [{ch['chapter_idx']:02d}] {ch['title']:<40} {ch['chunk_count']} chunks  (slug: {ch['slug']})")
        return

    if not args.query:
        parser.print_help()
        return

    if args.entity:
        results = entity_search(args.query)
        if not results:
            print("No entity matches found.")
        else:
            print(f"\nChapters where '{args.query}' appears:")
            for r in results:
                print(f"  [{r['chapter_idx']:02d}] {r['chapter_title']}  ({r['entity_type']})")
        return

    results = semantic_search(
        args.query,
        top_k=args.top_k,
        filter_chapter=args.chapter,
        filter_character=args.character,
    )
    print(format_for_terminal(results, query=args.query))


if __name__ == "__main__":
    main()
