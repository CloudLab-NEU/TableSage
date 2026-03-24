import pandas as pd
from difflib import SequenceMatcher
import numpy as np
from db.db_manager import DatabaseManager
from core_progress.bm25_searcher import BM25Searcher

def string_similarity(a: str, b: str) -> float:

    return SequenceMatcher(None, a, b).ratio()

def cosine_similarity(a, b):

    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def match_byString_fromDB(question_skeleton: str, top_n: int = 100):
    """
    Use MongoDB text index for Question skeleton string matching
    
    Args:
        question_skeleton: User input Question skeleton
        top_n: Benchmark return count, default 100
        
    Returns:
        list: List of similarity matched IDs
    """
    if not isinstance(question_skeleton, str) or not question_skeleton.strip():
        return []

    try:
        db_manager = DatabaseManager()
        
        # We use the existing question text search, assuming question_skeleton 
        # is a standardized version of the question.
        text_search_results = db_manager.search_similar_questions_by_text(question_skeleton)

        results_with_similarity = []
        for record in text_search_results:
            record_question = record.get('question', '')
            if record_question:
                similarity = string_similarity(record_question, question_skeleton)
                results_with_similarity.append({
                    'id': record['table_id'],
                    'similarity_byString': similarity
                })
        
        results_with_similarity.sort(key=lambda x: x['similarity_byString'], reverse=True)
        
        if len(results_with_similarity) >= top_n:
            if results_with_similarity[top_n - 1]['similarity_byString'] == 1.0:
                final_results = []
                for result in results_with_similarity:
                    if result['similarity_byString'] == 1.0:
                        final_results.append(result)
                    else:
                        break
                top_ids = [result['id'] for result in final_results]
            else:
                top_ids = [result['id'] for result in results_with_similarity[:top_n]]
        else:
            top_ids = [result['id'] for result in results_with_similarity]
        
        return top_ids
        
    except Exception as e:
        print(f"Database Question skeleton string matching failed: {str(e)}")
        return []
    
def match_byString_enhanced(question_skeleton: str, top_n: int = 100):
    """
    Enhanced Question skeleton string matching: first use text index matching, then get complete data
    
    Args:
        question_skeleton: User input Question skeleton
        top_n: Benchmark return count, default 100
        
    Returns:
        list: List of records with complete fields, sorted by Question skeleton string similarity
    """
    if not isinstance(question_skeleton, str) or not question_skeleton.strip():
        return []

    try:
        top_ids = match_byString_fromDB(question_skeleton, top_n)
        
        if not top_ids:
            return []
        
        db_manager = DatabaseManager()
        complete_records = db_manager.fetch_records_by_ids(top_ids)
        
        if not complete_records:
            return []
        
        return complete_records
        
    except Exception as e:
        print(f"Enhanced Question skeleton string matching failed: {str(e)}")
        return []

def match_bySkeleton(string_results, skeleton_embedding):
    """
    Perform question skeleton embedding similarity matching on string matching results
    
    Args:
        string_results: String matching results
        skeleton_embedding: Question skeleton embedding vector
        
    Returns:
        list: Results sorted by skeleton similarity
    """
    if not string_results:
        return []
    
    if skeleton_embedding is None or len(skeleton_embedding) == 0:
        return string_results
    
    try:
        df = pd.DataFrame(string_results)
        required_fields = ["table_id","sk_embedding"]
        missing_fields = [field for field in required_fields if field not in df.columns]
        if missing_fields:
            return string_results
        
        df = df.dropna(subset=required_fields)
        
        if df.empty:
            return string_results

        my_embedding = np.array(skeleton_embedding)

        df["similarity_bySkeleton"] = df["sk_embedding"].apply(
            lambda x: cosine_similarity(np.array(x), my_embedding) if x else 0
        )

        results_sorted = df.sort_values("similarity_bySkeleton", ascending=False)
          
        return results_sorted.to_dict('records')
        
    except Exception as e:
        print(f"Skeleton matching failed: {str(e)}")
        return string_results

def match_byTableStructure(string_results, table_structure, top_n):
    """
    Perform table structure similarity matching on string matching results
    
    Args:
        string_results: String matching results
        table_structure: Table structure
        
    Returns:
        list: Results sorted by table structure similarity
    """
    if not string_results or not table_structure:
        return string_results
    
    try:
        df = pd.DataFrame(string_results)
        
        required_fields = ["table_id", "table_structure"]
        missing_fields = [field for field in required_fields if field not in df.columns]
        if missing_fields:
            return string_results

        df["similarity_byTableStructure"] = df["table_structure"].apply(
            lambda x: string_similarity(str(x), str(table_structure)) if x else 0
        )
        
        # Weights: 0.9 for Semantic Embedding, 0.1 for Table Structure
        w_skeleton = 0.9
        w_table = 0.1
        df["total_similarity"] = (df["similarity_byTableStructure"] * w_table) + (df["similarity_bySkeleton"] * w_skeleton)
        
        top_results = df.sort_values("total_similarity", ascending=False).head(top_n)
        
        return top_results["table_id"].tolist(),top_results["total_similarity"].tolist()

    except Exception as e:
        print(f"Table structure matching failed: {str(e)}")
        return string_results
    
def find_topn_question(question_skeleton, skeleton_embedding, table_structure, top_n, first_top_n=200, exclude_ids=None):
    """
    Find top_n most similar questions from database, excluding specific IDs.
    """
    if exclude_ids is None:
        exclude_ids = []

    try:
        # Step 1: BM25 Coarse Filtering (Keyword-based)
        # Using first_top_n (default 200) to ensure high recall
        bm25_results = BM25Searcher().search(question_skeleton, top_n=first_top_n)
        
        if not bm25_results:
            # Fallback to MongoDB text search if BM25 index is empty or search fails
            string_results = match_byString_enhanced(question_skeleton, first_top_n)
        else:
            # BM25 results are already structured with table_id and other fields
            bm25_ids = [r['table_id'] for r in bm25_results]
            db_manager = DatabaseManager()
            string_results = db_manager.fetch_records_by_ids(bm25_ids)
            
        if not string_results:
            # 🚀 TRUE RAG FIX 🚀
            # 如果关键字搜索一无所获，绝不能直接退出
            # 我们直接回退到最本源的“全局纯向量搜索”模式，兜底寻找长尾的语义相似逻辑！
            db_manager = DatabaseManager()
            cursor = db_manager.knowledge_db.find(
                {"sk_embedding": {"$exists": True}}, 
                {"_id": 0, "table_id": 1, "sk_embedding": 1, "table_structure": 1}
            )
            string_results = [r for r in cursor]
            
            if not string_results:
                return [], []

        # Filter out excluded IDs immediately
        string_results = [r for r in string_results if r.get("table_id") not in exclude_ids]
        
        if not string_results:
            return [], []

        # Step 2: Semantic refinement (Vector similarity)
        skeleton_results = match_bySkeleton(string_results, skeleton_embedding)

        if not skeleton_results:
            return [], []

        # Step 3: Table structure refinement
        result = match_byTableStructure(
            skeleton_results,
            table_structure,
            top_n
        )

        # match_byTableStructure may return a plain list on error path
        if not result or not isinstance(result, tuple):
            return [], []

        top_n_ids, top_n_similar_list = result
        return top_n_ids, top_n_similar_list

    except Exception as e:
        print(f"Search process failed: {str(e)}")
        return [], []
    
def match_byString_fromDB_forGraph(question: str, top_n: int = 50):
    """
    Use MongoDB text index for question string matching for graph visualization
    
    Args:
        question: User input question
        top_n: Return top N most similar IDs
        
    Returns:
        list: List of top_n IDs with highest similarity
    """
    if not isinstance(question, str) or not question.strip():
        return []

    try:
        db_manager = DatabaseManager()
        
        text_search_results = db_manager.search_similar_questions_by_text(question)
        
        results_with_similarity = []
        for record in text_search_results:
            record_question = record.get('question', '')
            if record_question:
                similarity = string_similarity(record_question, question)
                results_with_similarity.append({
                    'table_id': record.get('table_id'),
                    'similarity_byString': similarity
                })
        
        results_with_similarity.sort(key=lambda x: x['similarity_byString'], reverse=True)
        top_ids = [result['table_id'] for result in results_with_similarity[:top_n]]

        return top_ids,results_with_similarity[:top_n]

    except Exception as e:
        print(f"Database question string matching failed: {str(e)}")
        return []