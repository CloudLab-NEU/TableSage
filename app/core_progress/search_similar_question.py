import pandas as pd
from difflib import SequenceMatcher
import numpy as np
from db.db_manager import DatabaseManager

def string_similarity(a: str, b: str) -> float:

    return SequenceMatcher(None, a, b).ratio()

def cosine_similarity(a, b):

    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def match_byString_fromDB(sql_skeleton: str, top_n: int = 100):
    """
    Use MongoDB text index for SQL skeleton string matching
    
    Args:
        sql_skeleton: User input SQL skeleton
        top_n: Benchmark return count, default 100
        
    Returns:
        list: List of similarity matched IDs
    """
    if not isinstance(sql_skeleton, str) or not sql_skeleton.strip():
        return []

    try:
        db_manager = DatabaseManager()
        
        text_search_results = db_manager.search_similar_sql_skeleton_by_text(sql_skeleton)

        results_with_similarity = []
        for record in text_search_results:
            record_sql_skeleton = record['sql_skeleton'], 
            if record_sql_skeleton:
                similarity = string_similarity(record_sql_skeleton, sql_skeleton)
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
        print(f"Database SQL skeleton string matching failed: {str(e)}")
        return []
    
def match_byString_enhanced(sql_skeleton: str, top_n: int = 100):
    """
    Enhanced SQL skeleton string matching: first use text index matching, then get complete data
    
    Args:
        sql_skeleton: User input SQL skeleton
        top_n: Benchmark return count, default 100
        
    Returns:
        list: List of records with complete fields, sorted by SQL skeleton string similarity
    """
    if not isinstance(sql_skeleton, str) or not sql_skeleton.strip():
        return []

    try:
        top_ids = match_byString_fromDB(sql_skeleton, top_n)
        
        if not top_ids:
            return []
        
        db_manager = DatabaseManager()
        complete_records = db_manager.fetch_records_by_ids(top_ids)
        
        if not complete_records:
            return []
        
        return complete_records
        
    except Exception as e:
        print(f"Enhanced SQL skeleton string matching failed: {str(e)}")
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
       
        df = df.dropna(subset=required_fields)
        
        if df.empty:
            return string_results

        df["similarity_byTableStructure"] = df["table_structure"].apply(
            lambda x: string_similarity(str(x), str(table_structure)) if x else 0
        )
        
        df["total_similarity"] = df["similarity_byTableStructure"] + df["similarity_bySkeleton"]
        
        top_results = df.sort_values("total_similarity", ascending=False).head(top_n)
        
        return top_results["table_id"].tolist(),top_results["total_similarity"].tolist()

    except Exception as e:
        print(f"Table structure matching failed: {str(e)}")
        return string_results
    
def find_topn_question(sql_skeleton, skeleton_embedding, table_structure, top_n, first_top_n=100):
    """
    Find top_n most similar questions from database
    
    Args:
        sql_skeleton: User SQL skeleton
        skeleton_embedding: Question skeleton embedding
        table_structure: User table structure
        top_n: Return top N results
        first_top_n: Initial filtering count
        
    Returns:
        list: List of table_ids for top_n most similar questions
    """
    try:
        string_results = match_byString_enhanced(sql_skeleton, first_top_n)
        
        if not string_results:
            return []

        skeleton_results = match_bySkeleton(string_results, skeleton_embedding)

        if not skeleton_results:
            return []

        top_n_ids, top_n_similar_list = match_byTableStructure(
            skeleton_results,
            table_structure,
            top_n
        )

        return top_n_ids, top_n_similar_list

    except Exception as e:
        print(f"Search process failed: {str(e)}")
        return []
    
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