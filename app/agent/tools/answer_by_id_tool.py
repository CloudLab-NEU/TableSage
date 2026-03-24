"""
Answer By ID Tool

Given a table_id from the knowledge base (a similar historical question),
attempt to answer it using the LLM. Returns whether the answer is correct
and the model's response. This tool is used within the Agent's answering loop
AFTER RAG retrieval has already identified relevant similar questions.

The Agent uses this tool to build up a confidence score by answering similar
questions before generating the final answer for the user's actual question.
"""
import re
from typing import Any, Dict, Optional

from openai_api.openai_client import OpenAIClient
from db.db_manager import DatabaseManager
from utils.utils import TableUtils

# ── OpenAI function-calling schema ────────────────────────────────────────────
ANSWER_BY_ID_SCHEMA = {
    "type": "function",
    "function": {
        "name": "answer_by_id",
        "description": (
            "Answer a specific question from the knowledge base (identified by table_id). "
            "The Agent calls this to attempt answering a similar historical question in order to "
            "assess its own confidence. Returns whether the answer was correct, the model's answer, "
            "and the existing learning record flag (if any). "
            "Use this for each similar question retrieved from RAG to build confidence before "
            "answering the user's actual question."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "table_id": {
                    "type": "string",
                    "description": "The table_id of a similar question from the knowledge base."
                },
                "use_existing_learning": {
                    "type": "boolean",
                    "description": (
                        "If true, use the existing learning record (rethink_summary) to guide "
                        "the answer. If false, answer from scratch without prior context."
                    )
                }
            },
            "required": ["table_id"]
        }
    }
}


def answer_by_id_tool(table_id: str, use_existing_learning: bool = True) -> Dict[str, Any]:
    """
    Attempt to answer a knowledge-base question identified by table_id.

    Args:
        table_id: Knowledge base question identifier
        use_existing_learning: Whether to use existing rethink_summary as guidance

    Returns:
        dict with:
          - table_id: same as input
          - is_correct: bool
          - model_answer: the raw LLM response
          - extracted_answer: answer text from <Answer> tags
          - true_answer: the correct answer
          - existing_flag: existing learning record flag (0/1/2/3/None)
          - strategy_used: 'direct' or 'with_learning'
          - error: error message if failed
    """
    try:
        db = DatabaseManager()
        openai_client = OpenAIClient()
        table_utils = TableUtils()

        knowledge = db.get_knowledge_by_id(table_id)
        if not knowledge:
            return {"table_id": table_id, "error": f"Knowledge entry not found for table_id={table_id}"}

        question = knowledge.get("question", "")
        true_answer = knowledge.get("answer")
        formatted_table = table_utils.table2format(
            table_utils.truncate_table(knowledge["table"])
        )


        # Check existing learning record
        learning_record = db.get_learning_record(table_id)
        existing_flag = learning_record.get("flag") if learning_record else None
        rethink_summary = learning_record.get("rethink_summary", "") if learning_record else ""

        strategy_used = "direct"

        # Use learning context if available and requested
        if use_existing_learning and rethink_summary and existing_flag in (1, 2):
            strategy_used = "with_learning"
            if existing_flag == 1:
                prompt = _build_guided_prompt(question, formatted_table, rethink_summary)
            else:  # flag == 2
                prompt = _build_error_reflection_prompt(question, formatted_table, rethink_summary)
        else:
            prompt = _build_direct_prompt(question, formatted_table)

        messages = [{"role": "user", "content": prompt}]
        model_answer = openai_client.get_llm_response(messages)

        is_correct = table_utils.is_answer_correct(model_answer, true_answer)

        # Extract clean answer from tags
        match = re.search(r"<Answer>([\s\S]*?)</Answer>", model_answer)
        extracted = match.group(1).strip() if match else ""

        record_saved = "none"
        # Save flag=0 when correct on first direct attempt (no prior record)
        # Only write if there is no existing record to avoid overwriting flag=1/2
        if is_correct and existing_flag is None:
            import datetime
            db.add_or_update_learning_record(
                table_id, 0,
                first_answer_time=datetime.datetime.now()
            )
            record_saved = "flag0"

        return {
            "table_id": table_id,
            "is_correct": is_correct,
            "extracted_answer": extracted,
            "true_answer": str(true_answer),
            "strategy_used": strategy_used,
            "record_saved": record_saved,
        }

    except Exception as e:
        import traceback
        return {
            "table_id": table_id,
            "is_correct": False,
            "error": str(e),
            "error_details": traceback.format_exc(),
        }


# ── Prompt builders ────────────────────────────────────────────────────────────

def _build_direct_prompt(question: str, formatted_table: str) -> str:
    return f"""### Task:
You are given a table and a question. Answer accurately using exact cell values.

### Table:
{formatted_table}

### Question:
{question}

### Instructions:
- For value questions: extract the exact cell value(s).
- For Yes/No questions: respond with 'yes' or 'no'.

**MANDATORY**: Put the final answer ONLY inside <Answer></Answer> tags.

### Examples:
- "which team won?" → <Answer>['Brazil']</Answer>
- "are there more than 3 rows?" → <Answer>['yes']</Answer>

<Answer></Answer>"""


def _build_guided_prompt(question: str, formatted_table: str, rethink_summary: str) -> str:
    return f"""### Task:
You are given a table, a question, and a guided learning reflection from a similar past question.
Use the reflection to answer correctly.

### Table:
{formatted_table}

### Question:
{question}

### Guided Learning Reflection:
{rethink_summary}

### Instructions:
Apply the insights from the reflection to analyze the table and answer the question.

**MANDATORY**: Put the final answer ONLY inside <Answer></Answer> tags.

<Answer></Answer>"""


def _build_error_reflection_prompt(question: str, formatted_table: str, rethink_summary: str) -> str:
    return f"""### Task:
You are given a table, a question, and a self-reflection on previous errors.
Use the reflection to avoid the same mistakes.

### Table:
{formatted_table}

### Question:
{question}

### Self-Reflection on Previous Errors:
{rethink_summary}

### Instructions:
Carefully avoid the specific errors identified in your reflection.

**MANDATORY**: Put the final answer ONLY inside <Answer></Answer> tags.

<Answer></Answer>"""
