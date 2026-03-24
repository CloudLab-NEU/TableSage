import logging
import jieba
from rank_bm25 import BM25Okapi
from typing import List, Dict, Any, Optional
from db.db_manager import DatabaseManager

# Set jieba logger to WARNING to suppress initialization messages
logging.getLogger("jieba").setLevel(logging.WARNING)
jieba.setLogLevel(logging.WARNING)

logger = logging.getLogger(__name__)

class BM25Searcher:
    """
    BM25 Searcher for keyword-based coarse filtering of questions.
    Uses jieba for Chinese tokenization and rank_bm25 for indexing.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BM25Searcher, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        self.db_manager = DatabaseManager()
        self.corpus_ids = []
        self.corpus_questions = []
        self.tokenized_corpus = []
        self.bm25 = None
        
        self.initialize_index()
        self._initialized = True

    def tokenize(self, text: str) -> List[str]:
        """Tokenize text using jieba."""
        if not text:
            return []
        return list(jieba.cut(text))

    def initialize_index(self):
        """Fetch all questions from DB and build the BM25 index."""
        logger.info("Initializing BM25 index...")
        try:
            # Fetch all questions and their table_ids
            # We only need 'table_id' and 'question'
            cursor = self.db_manager.knowledge_db.find(
                {}, 
                {"table_id": 1, "question": 1, "_id": 0}
            )
            
            self.corpus_ids = []
            self.corpus_questions = []
            self.tokenized_corpus = []
            
            for record in cursor:
                table_id = record.get("table_id")
                question = record.get("question", "")
                if table_id and question:
                    self.corpus_ids.append(table_id)
                    self.corpus_questions.append(question)
                    self.tokenized_corpus.append(self.tokenize(question))
            
            if self.tokenized_corpus:
                self.bm25 = BM25Okapi(self.tokenized_corpus)
                logger.info(f"BM25 index initialized with {len(self.corpus_ids)} records.")
            else:
                logger.warning("BM25 index initialization: empty corpus found.")
                # Ensure bm25 is not None to avoid crashes, even if empty
                self.bm25 = None
                
        except Exception as e:
            logger.error(f"Failed to initialize BM25 index: {e}")
            self.bm25 = None

    def search(self, query: str, top_n: int = 100) -> List[Dict[str, Any]]:
        """
        Search for Top-N similar questions.
        
        Returns a list of dicts with 'table_id', 'question', and 'bm25_score'.
        """
        if not self.bm25 or not query:
            return []
        
        tokenized_query = self.tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)
        
        # Zip with IDs and questions, then sort
        results = []
        for i in range(len(self.corpus_ids)):
            if scores[i] > 0: # Only return results with non-zero scores
                results.append({
                    "table_id": self.corpus_ids[i],
                    "question": self.corpus_questions[i],
                    "bm25_score": float(scores[i])
                })
        
        # Sort by score descending and take top N
        results.sort(key=lambda x: x["bm25_score"], reverse=True)
        return results[:top_n]

if __name__ == "__main__":
    # Quick test
    logging.basicConfig(level=logging.INFO)
    searcher = BM25Searcher()
    if searcher.bm25:
        test_query = "Calculate mean fare"
        results = searcher.search(test_query, top_n=5)
        print(f"Results for '{test_query}':")
        for res in results:
            print(f"- {res['table_id']}: {res['bm25_score']:.4f} | {res['question']}")
    else:
        print("BM25 searcher not initialized.")
