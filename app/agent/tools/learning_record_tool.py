"""
Learning Record Tool (optimized: batch DB queries)

Flag Semantics:
  flag=0: Correct with NO guidance → SKIP
  flag=1: Correct AFTER guidance, has rethink_summary → SKIP, use as few-shot
  flag=2: ALL strategies tried and STILL failed → SKIP + NO RETRY, use as error context
  flag=None: Never attempted → ATTEMPT via answer_by_id
"""
from typing import Any, Dict, List

from db.db_manager import DatabaseManager

LEARNING_RECORD_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_learning_records",
        "description": (
            "Retrieve learning records for similar question IDs from RAG retrieval. "
            "Returns categorized action lists: "
            "'mastered_ids' (flag=0, Correct WITHOUT guidance—SKIP, no reflection summary), "
            "'strategy_ids' (flag=1, Correct AFTER guidance—SKIP, USE for few-shot), "
            "'attempt_ids' (flag=None, fresh attempt needed via answer_by_id), "
            "'reflection_ids' (flag=2, previously attempted but guidance was wrong—DO NOT retry, "
            "pass to generate_final_answer as Reflection Record instead). "
            "Also returns pre-built success_strategy_context (from flag=1) and reflection_context (from flag=2) "
            "strings ready to use in generate_final_answer."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "table_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of table_ids from RAG retrieval."
                }
            },
            "required": ["table_ids"]
        }
    }
}


def get_learning_records_tool(table_ids: List[str]) -> Dict[str, Any]:
    """
    Retrieve and classify learning records using a single batch DB query.

    Returns:
        - mastered_ids:             flag=0 — Correct without guidance, skip answering
        - strategy_ids:             flag=1 — Correct with guidance, skip + use for few-shot
        - attempt_ids:              flag=None — must call answer_by_id
        - reflection_ids:           flag=2 — previously wrong guidance, DO NOT retry
        - success_strategy_context: positive context string from flag=1 rethink_summaries
        - reflection_context:       negative context string from flag=2 error_summaries
        - auto_confidence:          confidence from mastered_ids + strategy_ids
    """
    try:
        db = DatabaseManager()

        # ── Single batch query instead of N individual queries ──────────────
        learning_map = db.batch_get_learning_records(table_ids)  # {table_id: record}
        # Also batch-fetch knowledge records we'll need for question text
        from db.db_manager import DatabaseManager as _DB
        knowledge_cursor = db.knowledge_db.find(
            {"table_id": {"$in": table_ids}},
            {"table_id": 1, "question": 1, "_id": 0}
        )
        knowledge_map = {doc["table_id"]: doc.get("question", "") for doc in knowledge_cursor}

        records = {}
        mastered_ids: List[str] = []
        strategy_ids: List[str] = []
        attempt_ids: List[str] = []
        reflection_ids: List[str] = []

        for table_id in table_ids:
            learning = learning_map.get(table_id)
            question_text = knowledge_map.get(table_id, "")

            entry: Dict[str, Any] = {
                "table_id": table_id,
                "question": question_text,
            }

            if learning:
                flag = learning.get("flag")
                entry["flag"] = flag

                if flag == 0:
                    entry["action"] = "SKIP"
                    mastered_ids.append(table_id)

                elif flag == 1:
                    entry["action"] = "SKIP → pass to few_shot_ids"
                    strategy_ids.append(table_id)

                elif flag == 2:
                    entry["action"] = "SKIP + NO RETRY → pass to reflection_ids"
                    reflection_ids.append(table_id)

                else:
                    entry["action"] = "ATTEMPT"
                    attempt_ids.append(table_id)
            else:
                entry["flag"] = None
                entry["action"] = "ATTEMPT"
                attempt_ids.append(table_id)

            records[table_id] = entry

        total = len(table_ids)
        auto_confidence = (len(mastered_ids) + len(strategy_ids)) / total if total > 0 else 0.0

        return {
            "records": records,
            "mastered_ids": mastered_ids,
            "strategy_ids": strategy_ids,
            "attempt_ids": attempt_ids,
            "reflection_ids": reflection_ids,
            "auto_confidence": round(auto_confidence, 3),
            "auto_confidence_explanation": (
                f"{len(mastered_ids)} mastered (flag=0), {len(strategy_ids)} strategies (flag=1), "
                f"{len(reflection_ids)} reflections (flag=2), {len(attempt_ids)} to attempt. "
                f"auto_confidence={auto_confidence:.1%}. "
                + ("You may call generate_final_answer directly."
                   if auto_confidence >= 0.8 else
                   f"Practice {len(attempt_ids)} question(s) first.")
            ),
        }

    except Exception as e:
        import traceback
        return {
            "records": {},
            "mastered_ids": [],
            "strategy_ids": [],
            "attempt_ids": table_ids,
            "reflection_ids": [],
            "success_strategy_context": "",
            "reflection_context": "",
            "auto_confidence": 0.0,
            "error": str(e),
            "error_details": traceback.format_exc(),
        }
