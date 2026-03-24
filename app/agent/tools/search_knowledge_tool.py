"""
Search Knowledge Tool – Agent-Driven Rich Meta-Search

This tool allows the Agent to autonomously search the knowledge base.
It differs from a standard RAG step in two ways:
1. Intent Generation: The Agent provides its own search_query/intent.
2. Rich Metadata: The result contains Question, Category, Similarity, and History Status.
"""
import logging
from typing import Any, Dict, List, Optional
import json

from db.db_manager import DatabaseManager
from utils.utils import TableUtils
from core_progress.search_similar_question import find_topn_question

logger = logging.getLogger(__name__)

# ── OpenAI function-calling schema ────────────────────────────────────────────
SEARCH_KNOWLEDGE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_knowledge",
        "description": (
            "Search the knowledge base for similar questions or logic patterns using the ORIGINAL user question. "
            "Use this when you lack context, are unsure about the correct logic, or your confidence score is below 0.8. "
            "Returns a ranked list of candidates with question text, categories, and your practice history status. "
            "NOTE: The search is automatically based on the user's original question — you do NOT need to reformulate it."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "category_filter": {
                    "type": "string",
                    "description": "Optional category to narrow search (e.g., 'Aggregation', 'Filtering', 'Ranking').",
                },
                "top_n": {
                    "type": "integer",
                    "description": "How many candidates to return. Default 5. Max 10.",
                    "default": 5,
                },
                "exclude_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of table_ids to exclude from the fresh search results. Auto-injected by Agent.",
                }
            },
            "required": [],
        },
    },
}

def search_knowledge_tool(
    user_question: str,
    user_table: Optional[Dict[str, Any]] = None,
    top_n: int = 5,
    category_filter: Optional[str] = None,
    exclude_ids: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Execute knowledge search using the original user question for accurate RAG retrieval.
    Both user_question and user_table are auto-injected by the TableSageAgent loop.
    """
    try:
        top_n = min(max(1, top_n), 10)
        db_manager = DatabaseManager()

        if not user_table:
            return {"error": "user_table is required for search_knowledge but was not provided."}
        if not user_question:
            return {"error": "user_question is required for search_knowledge but was not provided."}

        # Step 1: Use the ORIGINAL user question to build skeleton + embedding for RAG
        features = TableUtils.match_similar_data_processor(user_question, user_table)
        
        # Step 2: Perform tiered retrieval (Similarity + Table Structure)
        similar_ids, scores = find_topn_question(
            features.get("question_skeleton", ""),
            features.get("question_skeleton_embedding", []),
            features.get("table_structure", ""),
            top_n,
            exclude_ids=exclude_ids
        )

        if not similar_ids:
            return {"results": [], "message": "No sufficiently similar patterns found in knowledge base."}

        # Step 3: Fetch rich metadata (Question, Categories)
        # We use db_manager directly to get more fields than standard fetch
        cursor = db_manager.knowledge_db.find(
            {"table_id": {"$in": list(similar_ids)}},
            {"table_id": 1, "question": 1, "categories": 1, "_id": 0}
        )
        raw_details = {r["table_id"]: r for r in cursor}

        # Step 4: Cross-reference with Learning Records
        history = db_manager.batch_get_learning_records(list(similar_ids))

        # Step 5: Merge and Format
        enriched_results = []
        id_to_score = {tid: s for tid, s in zip(similar_ids, scores)}

        for tid in similar_ids:
            detail = raw_details.get(tid, {})
            record = history.get(tid, {})
            
            # 🚀 TRUE RAG FIX 🚀
            # We completely soft-deprecate the strict category_filter.
            # LLMs often guess arbitrary categories (e.g. "Filtering" vs "Aggregation"). 
            # Dropping an item because the category string doesn't match destroys cross-domain RAG.
            res_category = detail.get("categories", "General")

            # Determine status label
            flag = record.get("flag")
            status = "New"
            if flag == 0: status = "Mastered (Direct Success)"
            elif flag == 1: status = "Strategic Success (CoT/Sorting/etc.)"
            elif flag == 2: status = "Lesson Learned (Prior Failure with Reflection)"

            enriched_results.append({
                "table_id": tid,
                "question": detail.get("question", "N/A"),
                "category": res_category,
                "similarity": round(id_to_score.get(tid, 0.0), 3),
                "history_status": status,
                "rethink_summary": record.get("rethink_summary", "")[:200] # Expanded snippet
            })

        return {
            "question_searched": user_question[:80],
            "skeleton_used": features.get("question_skeleton", ""),
            "results": enriched_results,
            "total_found": len(enriched_results),
            "instruction": (
                "Scan the results. Note that 'Lesson Learned' or 'Strategic Success' entries provide EXPLICIT "
                "guidance on how to solve this pattern. Use these reflections to INCREASE your confidence score "
                "via the 'think' tool before generating the final answer."
            )
        }

    except Exception as e:
        logger.error(f"Search Knowledge Tool Error: {e}")
        import traceback
        return {"error": str(e), "details": traceback.format_exc()}
