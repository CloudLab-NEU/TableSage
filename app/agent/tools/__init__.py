"""
TableSage Agent Tools

Aligned with actual business flow:
  1. RAG retrieval (always first, done by the Agent main loop, not a tool)
  2. Agent tool loop:
     - get_learning_records: understand prior performance on retrieved questions
     - answer_by_id: attempt each similar question, building confidence
     - apply_strategy_by_id: retry wrong answers with CoT/column_sorting/schema_linking
     - think: explicit ReAct Thought step – record reasoning about context sufficiency
     - generate_final_answer: produce final answer for the user's actual question
"""
from agent.tools.answer_by_id_tool import answer_by_id_tool, ANSWER_BY_ID_SCHEMA
from agent.tools.strategy_by_id_tool import apply_strategy_by_id_tool, STRATEGY_BY_ID_SCHEMA
from agent.tools.learning_record_tool import get_learning_records_tool, LEARNING_RECORD_SCHEMA
from agent.tools.final_answer_tool import generate_final_answer_tool, FINAL_ANSWER_SCHEMA
from agent.tools.think_tool import think_tool, THINK_TOOL_SCHEMA
from agent.tools.search_knowledge_tool import search_knowledge_tool, SEARCH_KNOWLEDGE_SCHEMA
from agent.tools.practice_question_tool import practice_question_tool, PRACTICE_QUESTION_SCHEMA

ALL_TOOLS = [
    THINK_TOOL_SCHEMA,
    FINAL_ANSWER_SCHEMA,
    SEARCH_KNOWLEDGE_SCHEMA,
    PRACTICE_QUESTION_SCHEMA,
]

TOOL_EXECUTORS = {
    "think": think_tool,
    "generate_final_answer": generate_final_answer_tool,
    "search_knowledge": search_knowledge_tool,
    "practice_question": practice_question_tool,
}

__all__ = [
    "ALL_TOOLS",
    "TOOL_EXECUTORS",
    "ANSWER_BY_ID_SCHEMA",
    "STRATEGY_BY_ID_SCHEMA",
    "LEARNING_RECORD_SCHEMA",
    "THINK_TOOL_SCHEMA",
    "FINAL_ANSWER_SCHEMA",
]
