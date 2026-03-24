"""
Strategy By ID Tool

When the Agent's direct answer for a knowledge-base question (by table_id)
is wrong, the Agent calls this tool to retry using a specific reasoning strategy.
If the strategy succeeds, the tool generates a student reflection summary and
updates the learning record (flag=1 + rethink_summary).
If it fails after all strategies, it generates an error summary (flag=2).

This replaces the hardcoded strategy loop in GuidancingProcessor with an
Agent-callable tool that gives the Agent control over which strategy to try and when.
"""
import re
from typing import Any, Dict, List, Optional

from openai_api.openai_client import OpenAIClient
from db.db_manager import DatabaseManager
from utils.utils import TableUtils

AVAILABLE_STRATEGIES = ["cot", "column_sorting", "schema_linking"]

# ── OpenAI function-calling schema ────────────────────────────────────────────
STRATEGY_BY_ID_SCHEMA = {
    "type": "function",
    "function": {
        "name": "apply_strategy_by_id",
        "description": (
            "Apply a reasoning strategy to re-attempt a knowledge-base question that was answered incorrectly. "
            "Strategies available: 'cot' (Chain of Thought), 'column_sorting', 'schema_linking'. "
            "If the strategy succeeds, a student reflection is generated and saved (flag=1). "
            "Call this after 'answer_by_id' returns is_correct=False. "
            "Try different strategies in order if one fails—the Agent decides the order."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "table_id": {
                    "type": "string",
                    "description": "The table_id of the question to retry."
                },
                "strategy": {
                    "type": "string",
                    "enum": ["cot", "column_sorting", "schema_linking"],
                    "description": "The reasoning strategy to apply."
                },
                "save_record": {
                    "type": "boolean",
                    "description": (
                        "If true and answer is correct, save a learning record (flag=1 + rethink_summary). "
                        "If this is the last strategy attempt and still wrong, save error record (flag=2)."
                    )
                },
                "is_final_attempt": {
                    "type": "boolean",
                    "description": (
                        "Set to true when this is the last strategy being tried. "
                        "If wrong on the final attempt, an error summary will be saved (flag=2)."
                    )
                }
            },
            "required": ["table_id", "strategy"]
        }
    }
}


def apply_strategy_by_id_tool(
    table_id: str,
    strategy: str,
    save_record: bool = True,
    is_final_attempt: bool = False
) -> Dict[str, Any]:
    """
    Apply a strategy to re-attempt a wrongly answered knowledge-base question.

    Args:
        table_id: Knowledge base question ID
        strategy: 'cot', 'column_sorting', or 'schema_linking'
        save_record: Whether to persist learning records to DB
        is_final_attempt: If True and still wrong, save error record (flag=2)

    Returns:
        dict with:
          - table_id, strategy, is_correct, model_answer, extracted_answer, true_answer
          - record_saved: 'flag1' / 'flag2' / 'none'
          - rethink_summary: generated reflection (if correct)
          - error_summary: generated error analysis (if final_attempt and wrong)
    """
    try:
        db = DatabaseManager()
        openai_client = OpenAIClient()
        table_utils = TableUtils()

        knowledge = db.get_knowledge_by_id(table_id)
        if not knowledge:
            return {"table_id": table_id, "error": f"Knowledge not found for table_id={table_id}"}

        question = knowledge.get("question", "")
        true_answer = knowledge.get("answer")
        formatted_table = table_utils.table2format(
            table_utils.truncate_table(knowledge["table"])
        )

        # Get strategy content from knowledge entry
        strategy_content = _get_strategy_content(knowledge, strategy)

        prompt = _build_strategy_prompt(question, formatted_table, strategy, strategy_content)
        messages = [{"role": "user", "content": prompt}]
        model_answer = openai_client.get_llm_response(messages)

        is_correct = table_utils.is_answer_correct(model_answer, true_answer)
        match = re.search(r"<Answer>([\s\S]*?)</Answer>", model_answer)
        extracted = match.group(1).strip() if match else ""

        result = {
            "table_id": table_id,
            "strategy": strategy,
            "is_correct": is_correct,
            "extracted_answer": extracted,
            "true_answer": str(true_answer),
            "record_saved": "none",
        }

        if not save_record:
            return result

        if is_correct:
            # Generate reflection and save flag=1 record
            rethink_summary = _generate_student_reflection(
                openai_client, knowledge, strategy, model_answer
            )
            import datetime
            db.add_or_update_learning_record(
                table_id, 1,
                rethink_summary=rethink_summary,
                first_answer_time=datetime.datetime.now()
            )
            # Upsert teaching record
            existing_teaching = db.get_teaching_record(table_id)
            teaching_record = {
                "table_id": table_id,
                "strategy_type": strategy,
                "created_at": datetime.datetime.now(),
            }
            if existing_teaching:
                db.update_teaching_record(table_id, teaching_record)
            else:
                db.add_teaching_record(teaching_record)

            result["record_saved"] = "flag1"

        elif is_final_attempt:
            # All strategies failed → generate error summary, save flag=2
            error_summary = _generate_error_summary(
                openai_client, knowledge, AVAILABLE_STRATEGIES, str(true_answer), model_answer
            )
            db.update_learning_record_with_rethink(table_id, 2, error_summary)
            db.delete_teaching_record(table_id)

            result["record_saved"] = "flag2"

        return result

    except Exception as e:
        import traceback
        return {
            "table_id": table_id,
            "strategy": strategy,
            "is_correct": False,
            "error": str(e),
            "error_details": traceback.format_exc(),
        }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_strategy_content(knowledge: Dict[str, Any], strategy: str) -> str:
    """Get strategy-specific content from the knowledge entry."""
    field_map = {
        "cot": "cot",
        "column_sorting": "coloumn_sorting",  # typo preserved from original DB
        "schema_linking": "schema_linking",
    }
    db_field = field_map.get(strategy, strategy)
    strategy_data = knowledge.get("strategy", {})
    return str(strategy_data.get(db_field, "")) if isinstance(strategy_data, dict) else ""


def _build_strategy_prompt(
    question: str,
    formatted_table: str,
    strategy: str,
    strategy_content: str
) -> str:
    base = f"""### Task:
You are given a table and a question. Use the provided reasoning strategy to answer accurately.

### Table:
{formatted_table}

### Question:
{question}
"""

    if strategy == "cot":
        strategy_section = f"""
### Chain-of-Thought (CoT) Strategy:
Break down the problem step by step: TARGET → COLUMNS → CONDITIONS → RESULT.
{f"### CoT Guide from Knowledge Base:{chr(10)}{strategy_content}" if strategy_content else ""}
"""
    elif strategy == "column_sorting":
        strategy_section = f"""
### Column Sorting Strategy:
Identify and prioritize the most relevant columns for this question, then extract the answer.
{f"### Column Relevance from Knowledge Base:{chr(10)}{strategy_content}" if strategy_content else ""}
"""
    elif strategy == "schema_linking":
        strategy_section = f"""
### Schema Linking Strategy:
Map question concepts to specific table column names, then look up the answer.
{f"### Schema Linking from Knowledge Base:{chr(10)}{strategy_content}" if strategy_content else ""}
"""
    else:
        strategy_section = ""

    suffix = """
**MANDATORY**: Put the final answer ONLY inside <Answer></Answer> tags.

### Examples:
- "which country won?" → <Answer>['France']</Answer>
- "are there more wins than losses?" → <Answer>['yes']</Answer>

<Answer></Answer>"""
    return base + strategy_section + suffix


def _generate_student_reflection(
    client: OpenAIClient,
    knowledge: Dict[str, Any],
    strategy: str,
    model_answer: str
) -> str:
    """Generate a student self-reflection summary when strategy succeeds."""
    question = knowledge.get("question", "")
    true_answer = knowledge.get("answer", "")
    table_utils = TableUtils()
    formatted_table = table_utils.table2format(
        table_utils.truncate_table(knowledge["table"])
    )

    prompt = f"""As a student, generate a concise self-reflection on how you solved this table question using the {strategy} strategy.

Table: {formatted_table}
Question: {question}
Your answer: {model_answer}
Correct answer: {true_answer}
Strategy: {strategy}

Include THREE sections:
## Section 1: Strategy Understanding – Why {strategy} worked here.
## Section 2: Solution Process – Key steps you took.
## Section 3: Key Learning Points – What to apply to similar questions.
"""
    messages = [{"role": "user", "content": prompt}]
    return client.get_llm_response(messages)


def _generate_error_summary(
    client: OpenAIClient,
    knowledge: Dict[str, Any],
    strategies_tried: List[str],
    true_answer: str,
    model_answer: str
) -> str:
    """Generate an error summary when all strategies fail."""
    question = knowledge.get("question", "")
    table_utils = TableUtils()
    formatted_table = table_utils.table2format(
        table_utils.truncate_table(knowledge["table"])
    )

    prompt = f"""As a student, generate a self-reflection error summary for a question you consistently answer incorrectly.

Table: {formatted_table}
Question: {question}
Your answer: {model_answer}
Correct answer: {true_answer}
Strategies tried: {', '.join(strategies_tried)}

Include THREE sections:
## Section 1: Error Analysis – What specifically went wrong.
## Section 2: Root Cause – What concept or step you misunderstood.
## Section 3: Improvement Plan – How to approach similar questions differently.
"""
    messages = [{"role": "user", "content": prompt}]
    return client.get_llm_response(messages)
