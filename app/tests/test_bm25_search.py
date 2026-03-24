import sys
import os
import logging

# Add current directory to path
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from core_progress.bm25_searcher import BM25Searcher

def test_bm25():
    logging.basicConfig(level=logging.INFO)
    print("Initializing BM25Searcher...")
    searcher = BM25Searcher()
    
    if not searcher.bm25:
        print("Error: BM25 index not initialized.")
        return
    
    queries = [
        "Calculate mean fare",
        "How many passengers survived?",
        "What is the average age?"
    ]
    
    for query in queries:
        print(f"\nSearching for: '{query}'")
        results = searcher.search(query, top_n=3)
        if not results:
            print("  No results found.")
        for res in results:
            print(f"  - {res['table_id']}: {res['bm25_score']:.4f} | {res['question']}")

if __name__ == "__main__":
    test_bm25()
