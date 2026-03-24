"""
Final Answer Tool

After the Agent has answered similar knowledge-base questions (building
confidence and accumulating few-shot context), this tool generates the
FINAL answer for the user's actual question using all gathered context.

This is the equivalent of the original FinalAnswerProcessor but now
the Agent explicitly passes in the contextualized learning it gathered.
"""
import re
from typing import Any, Dict, List, Optional

from openai_api.openai_client import OpenAIClient
from db.db_manager import DatabaseManager
from utils.utils import TableUtils
from core_progress.search_similar_question import string_similarity

# ── OpenAI function-calling schema ────────────────────────────────────────────
FINAL_ANSWER_SCHEMA = {
    "type": "function",
    "function": {
        "name": "generate_final_answer",
        "description": (
            "Generate the FINAL answer for the USER's actual question, using the "
            "context and few-shot learning gathered from answering similar knowledge-base questions. "
            "CRITICAL: Call this as the ABSOLUTE LAST step ONLY after you have finished ALL "
            "calculations, steps, and logic in your 'think' tool and are 100% ready to output the answer. "
            "Pass the list of correctly-answered table_ids as few_shot_ids."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "user_question": {
                    "type": "string",
                    "description": "The original user question."
                },
                "user_table": {
                    "type": "object",
                    "description": "The original user table with 'header' and 'rows'."
                },
                "few_shot_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Table IDs of similar questions correctly answered with guidance (strategy_ids, flag=1). "
                        "Their rethink_summaries provide POSITIVE few-shot guidance. "
                        "Do NOT pass flag=0 (mastered) IDs here."
                    )
                },
                "reflection_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Table IDs where previously attempted but guidance was wrong (flag=2). "
                        "Their rethink_summaries serve as Reflection Records—mistakes to avoid. "
                        "Pass at most the top-2 by similarity."
                    )
                },
                "is_training": {
                    "type": "boolean",
                    "description": "If true, record the answer outcome (requires true_answer)."
                },
                "true_answer": {
                    "type": "string",
                    "description": "The gold answer, required when is_training=true."
                }
            },
            "required": ["user_question", "user_table"]
        }
    }
}


def generate_final_answer_tool(
    user_question: str,
    user_table: Dict[str, Any],
    few_shot_ids: Optional[List[str]] = None,
    reflection_ids: Optional[List[str]] = None,
    is_training: bool = False,
    true_answer: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Prepare enriched context for the final answer.
    
    This tool does NOT generate the answer itself. It fetches relevant
    learning contexts from the database and returns them. The ReAct loop
    LLM will then use this context (plus its accumulated reasoning) to
    generate the final answer directly with <Answer></Answer> tags.
    """
    try:
        db = DatabaseManager()
        table_utils = TableUtils()
        formatted_table = table_utils.table2format(user_table)

        # Ensure lists
        if isinstance(few_shot_ids, str):
            few_shot_ids = [few_shot_ids]
        if isinstance(reflection_ids, str):
            reflection_ids = [reflection_ids]
            
        # Gather Success Strategy context (flag=1)
        success_strategy_context = _build_few_shot_context(
            db, table_utils, (few_shot_ids or [])[:2]
        )
        
        # Gather Reflection context (flag=2)
        reflection_context = _build_reflection_context_from_ids(
            db, table_utils, (reflection_ids or [])[:2]
        )

        # Build the context prompt for the ReAct LLM
        context_parts = []
        if success_strategy_context:
            context_parts.append(
                f"### Success Strategies from Similar Questions:\n{success_strategy_context}"
            )
        if reflection_context:
            context_parts.append(
                f"### Reflection Records (Mistakes to Avoid):\n{reflection_context}"
            )

        # Determine context type
        if success_strategy_context and reflection_context:
            context_used = "strategy_and_reflection"
        elif success_strategy_context:
            context_used = "strategy_only"
        elif reflection_context:
            context_used = "reflection_only"
        else:
            context_used = "direct"

        enriched_context = "\n\n".join(context_parts) if context_parts else ""

        result = {
            "enriched_context": enriched_context,
            "context_used": context_used,
            "few_shot_count": len(few_shot_ids or []),
            "reflection_count": len(reflection_ids or []),
            "instruction": (
                "NOW output the final answer for the user's question based on the table and context.\n\n"
                "### Instructions:\n"
                "Combine the context above with your PREVIOUS calculations from 'think' to provide the answer.\n"
                "1. Carefully review the table structure, including headers and rows.\n"
                "2. Identify the relevant data needed to answer the question and use the exact cell value(s) from the table to answer the question.\n"
                "3. Carefully read the question to understand what type of answer is expected:\n"
                "   - **Value-based questions**: Extract specific data from table.\n"
                "   - **Yes/No questions**: Find values, then judge with 'yes'/'no'.\n\n"
                "**MANDATORY FORMAT REQUIREMENT**: You MUST put the final answer in the placeholder <Answer></Answer>, "
                "DO NOT include any explanation, reasoning, or additional text outside the Answer tags.\n\n"
                "### Example Answers:\n"
                "- For the question \"scotland played their first match of the 1951 british home championship against which team?\", "
                "the answer is <Answer>['England']</Answer>.\n"
                "- For another question \"are there at least 2 nationalities on the chart?\", "
                "the answer is <Answer>['yes']</Answer>."
            ),
        }

        # Pass training info through for agent-level validation
        if is_training:
            result["is_training"] = True
            result["true_answer"] = str(true_answer) if true_answer else ""

        return result

    except Exception as e:
        import traceback
        return {
            "enriched_context": "",
            "context_used": "error",
            "error": str(e),
            "instruction": "Context preparation failed. Answer the question directly using the table.",
        }


# ── Context builders ────────────────────────────────────────────────────────────

def _build_few_shot_context(
    db: DatabaseManager,
    table_utils: TableUtils,
    table_ids: List[str]
) -> str:
    """Build positive few-shot context from flag=1 learning records (top-2 max)."""
    contexts = []
    for table_id in table_ids:  # caller already sliced to [:2]
        learning = db.get_learning_record(table_id)
        if not learning:
            continue
        flag = learning.get("flag")
        rethink = learning.get("rethink_summary", "")
        if flag == 1 and rethink:
            knowledge = db.get_knowledge_by_id(table_id)
            if knowledge:
                teaching = db.get_teaching_record(table_id)
                strategy = teaching.get("strategy_type", "direct") if teaching else "direct"
                orig_q = knowledge.get("question", "")
                orig_table = table_utils.table2format(
                    table_utils.truncate_table(knowledge.get("table", {"header": [], "rows": []}))
                )

                contexts.append(
                    f"**Similar Question [{strategy}]**: {orig_q}\n"
                    f"**Table**: {orig_table}\n"
                    f"**Learning Reflection**: {rethink}"
                )
    return "\n\n---\n\n".join(contexts)


def _build_reflection_context_from_ids(
    db: DatabaseManager,
    table_utils: TableUtils,
    table_ids: List[str]
) -> str:
    """Build Reflection context from flag=2 records (top-2 max)."""
    contexts = []
    for table_id in table_ids:
        learning = db.get_learning_record(table_id)
        if not learning or learning.get("flag") != 2:
            continue
        rethink = learning.get("rethink_summary", "")
        knowledge = db.get_knowledge_by_id(table_id)
        orig_q = knowledge.get("question", "") if knowledge else ""
        orig_table = ""
        if knowledge:
            orig_table = table_utils.table2format(
                table_utils.truncate_table(knowledge.get("table", {"header": [], "rows": []}))
            )
        if rethink:
            contexts.append(
                f"**Similar Question (Reflection - Avoid these mistakes)**: {orig_q}\n"
                f"**Table**: {orig_table}\n"
                f"**Reflection Details**: {rethink}"
            )
    return "\n\n---\n\n".join(contexts)


def _find_error_context(db: DatabaseManager, user_question: str) -> str:
    """Fallback: search error_records collection by string similarity (legacy)."""
    try:
        error_records = list(db.error_records.find({}))
        best_similarity = 0.0
        best_record = None
        for record in error_records:
            eq = record.get("question", "")
            if eq:
                sim = string_similarity(user_question, eq)
                if sim > 0.5 and sim > best_similarity:
                    best_similarity = sim
                    best_record = record
        if best_record:
            return (
                f"**Similar Error Question**: {best_record.get('question', '')}\n"
                f"**Error Analysis**: {best_record.get('error_reflection', '')}"
            )
    except Exception:
        pass
    return ""


def _save_error_record(db, openai_client, question, table, formatted_table, model_answer, true_answer):
    """Save error record in training mode."""
    prompt = f"""As a tutor, analyze this incorrect table-question answer.

Table: {formatted_table}
Question: {question}
Student's Answer: {model_answer}
Correct Answer: {true_answer}

Provide:
## Section 1: Error Identification
## Section 2: Correct Approach
## Section 3: Learning Points
"""
    messages = [{"role": "user", "content": prompt}]
    reflection = openai_client.get_llm_response(messages, model="gpt-4o")
    db.error_records.insert_one({
        "question": question,
        "table": table,
        "model_answer": model_answer,
        "true_answer": true_answer,
        "error_reflection": reflection,
    })


# ── Prompt templates ────────────────────────────────────────────────────────────

def _prompt_direct(question: str, table: str) -> str:
    return f"""### Task:
Answer the question using the table data.

### Table:
{table}

### Question:
{question}

**MANDATORY**: Put the final answer ONLY inside <Answer></Answer> tags.

<Answer></Answer>"""


def _prompt_with_strategy(question: str, table: str, strategy_ctx: str) -> str:
    return f"""### Task:
Answer the question using the table data. Use the Success Strategies from similar questions.

### Table:
{table}

### Question:
{question}

### Success Strategies from Similar Questions:
{strategy_ctx}

### Instructions:
Apply the strategies and insights from the records above.

**MANDATORY**: Put the final answer ONLY inside <Answer></Answer> tags.

<Answer></Answer>"""


def _prompt_with_reflection(question: str, table: str, reflection_ctx: str) -> str:
    return f"""### Task:
Answer the question. A similar question was previously attempted but guidance was inconsistent—use the Reflection Record to avoid the same mistakes.

### Table:
{table}

### Question:
{question}

### Reflection Record from Similar Question:
{reflection_ctx}

**MANDATORY**: Put the final answer ONLY inside <Answer></Answer> tags.

<Answer></Answer>"""


def _prompt_with_both_strategy_and_reflection(question: str, table: str, strategy_ctx: str, reflection_ctx: str) -> str:
    return f"""### Task:
Answer the question using both Success Strategies and Reflection Records.

### Table:
{table}

### Question:
{question}

### Success Strategies:
{strategy_ctx}

### Reflection Record (Mistakes to Avoid):
{reflection_ctx}

**MANDATORY**: Put the final answer ONLY inside <Answer></Answer> tags.

<Answer></Answer>"""
