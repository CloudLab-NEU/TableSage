"""
Practice Question Tool – Consolidated Re-learning & Strategic Attempt

This tool consolidates 'answer_by_id' and 'apply_strategy_by_id' into a single 
Agent-driven interface. The Agent decides which strategy to use for which ID.
"""
import re
import logging
import datetime
from typing import Any, Dict, Optional

from openai_api.openai_client import OpenAIClient
from db.db_manager import DatabaseManager
from utils.utils import TableUtils

# Reuse helper logic from existing tools for consistency
from agent.tools.answer_by_id_tool import (
    _build_direct_prompt, 
    _build_guided_prompt, 
    _build_error_reflection_prompt
)
from agent.tools.strategy_by_id_tool import (
    _get_strategy_content,
    _build_strategy_prompt,
    _generate_student_reflection,
    _generate_error_summary,
    AVAILABLE_STRATEGIES
)

logger = logging.getLogger(__name__)

# ── OpenAI function-calling schema ────────────────────────────────────────────
PRACTICE_QUESTION_SCHEMA = {
    "type": "function",
    "function": {
        "name": "practice_question",
        "description": (
            "Attempt to answer a similar question from the knowledge base to build logic confidence. "
            "You can choose a direct attempt or use a specific reasoning strategy (CoT, Sorting, etc.)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "table_id": {
                    "type": "string",
                    "description": "The table_id of the candidate question from search_knowledge."
                },
                "strategy": {
                    "type": "string",
                    "enum": ["direct", "cot", "column_sorting", "schema_linking"],
                    "description": "The logic strategy to apply. Use 'direct' for your first attempt.",
                    "default": "direct"
                },
                "use_learning": {
                    "type": "boolean",
                    "description": "If true, use existing reflection/learning records to guide a 'direct' attempt.",
                    "default": True
                },
                "is_final_attempt": {
                    "type": "boolean",
                    "description": "Set to true if this is your last attempt for this ID. If wrong, a failure record (Flag 2) is saved.",
                    "default": False
                }
            },
            "required": ["table_id"]
        }
    }
}

def practice_question_tool(
    table_id: str,
    strategy: str = "direct",
    use_learning: bool = True,
    is_final_attempt: bool = False
) -> Dict[str, Any]:
    """
    Execute a strategic practice attempt.
    """
    try:
        db = DatabaseManager()
        openai_client = OpenAIClient()
        table_utils = TableUtils()

        knowledge = db.get_knowledge_by_id(table_id)
        if not knowledge:
            return {"table_id": table_id, "error": f"Knowledge entry not found."}

        question = knowledge.get("question", "")
        true_answer = knowledge.get("answer")
        formatted_table = table_utils.table2format(
            table_utils.truncate_table(knowledge["table"])
        )

        # Check existing learning record status
        learning_record = db.get_learning_record(table_id)
        existing_flag = learning_record.get("flag") if learning_record else None
        rethink_summary = learning_record.get("rethink_summary", "") if learning_record else ""

        # ── Step 1: Build Prompt based on Strategy ─────────────────────────────
        if strategy == "direct":
            if use_learning and rethink_summary and existing_flag in (1, 2):
                if existing_flag == 1:
                    prompt = _build_guided_prompt(question, formatted_table, rethink_summary)
                else: 
                    prompt = _build_error_reflection_prompt(question, formatted_table, rethink_summary)
            else:
                prompt = _build_direct_prompt(question, formatted_table)
        else:
            strategy_content = _get_strategy_content(knowledge, strategy)
            prompt = _build_strategy_prompt(question, formatted_table, strategy, strategy_content)

        # ── Step 2: Get LLM Response ──────────────────────────────────────────
        messages = [{"role": "user", "content": prompt}]
        model_answer = openai_client.get_llm_response(messages)
        is_correct = table_utils.is_answer_correct(model_answer, true_answer)
        
        match = re.search(r"<Answer>([\s\S]*?)</Answer>", model_answer)
        extracted = match.group(1).strip() if match else ""

        # ── Step 3: Persistence Logic (Learning Records) ──────────────────────
        record_saved = "none"
        reflection = ""

        if is_correct:
            if strategy == "direct" and existing_flag is None:
                # First time success -> Flag 0
                db.add_or_update_learning_record(table_id, 0, first_answer_time=datetime.datetime.now())
                record_saved = "flag0"
            elif strategy != "direct":
                # Strategy success -> Flag 1 + Reflection
                reflection = _generate_student_reflection(openai_client, knowledge, strategy, model_answer)
                db.add_or_update_learning_record(table_id, 1, rethink_summary=reflection, first_answer_time=datetime.datetime.now())
                # Update Teaching Record
                db.upsert_teaching_record({"table_id": table_id, "strategy_type": strategy, "created_at": datetime.datetime.now()})
                record_saved = "flag1"
        elif is_final_attempt:
            # Final failure -> Flag 2 + Error Summary
            err_summary = _generate_error_summary(openai_client, knowledge, AVAILABLE_STRATEGIES, str(true_answer), model_answer)
            db.update_learning_record_with_rethink(table_id, 2, err_summary)
            db.delete_teaching_record(table_id)
            record_saved = "flag2"
            reflection = err_summary

        return {
            "table_id": table_id,
            "strategy_used": strategy,
            "is_correct": is_correct,
            "extracted_answer": extracted,
            "true_answer": str(true_answer),
            "record_saved": record_saved,
            "new_reflection": reflection[:200] + "..." if reflection else ""
        }

    except Exception as e:
        logger.error(f"Practice Question Tool Error: {e}")
        return {"error": str(e)}
