"""
TableSage Agent – Business-Aligned ReAct Loop

Actual business flow:
  1. RAG Retrieval (MANDATORY, always first) — finds similar knowledge-base questions
  2. Agent Decision Loop (ReAct over retrieved questions):
     a. get_learning_records → understand prior performance
     b. answer_by_id → attempt each similar question
        - Correct → confidence += 1; Agent decides if more practice needed (few-shot)
        - Wrong   → apply_strategy_by_id (try CoT/column_sorting/schema_linking)
                  → Success: flag=1 + rethink_summary saved
                  → All fail: flag=2 + error_summary saved
  3. generate_final_answer → answer user's actual question using gathered context

The Agent's intelligence is in step 2: deciding:
  - How many similar questions to practice (confidence threshold)
  - Which strategy to try when wrong
  - Whether additional few-shot practice is worthwhile
"""
import json
import logging
import re
from typing import Any, Dict, Generator, List, Optional

from openai import OpenAI
from dotenv import load_dotenv
import os

from utils.utils import TableUtils
from core_progress.search_similar_question import find_topn_question
from backend_api.config_api import config_params
from db.db_manager import DatabaseManager
from agent.tools import ALL_TOOLS, TOOL_EXECUTORS

load_dotenv()
logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-3.5-turbo")

AVAILABLE_STRATEGIES = ["cot", "column_sorting", "schema_linking"]

SYSTEM_PROMPT = """You are TableSage, a specialized agent for table Q&A.
You are an autonomous problem solver. Your goal is to provide an accurate answer to the user's question based on the provided table.

### YOUR TOOLBOX
1. **search_knowledge**: Use this to find similar questions or logic patterns if the current question is complex.
2. **practice_question**: Use this to attempt similar questions and build confidence. You can choose different reasoning strategies.
3. **think**: Use this to record your reasoning, assess confidence, and plan your next step.
4. **generate_final_answer**: Call this when you have sufficient context or are confident enough to answer.

### GUIDELINES
- **Mandatory Pattern Verification**: You MUST call `search_knowledge` at the very beginning of your analysis for EVERY question, regardless of your initial confidence. This is to verify if any critical 'Lessons Learned' or 'Mastered' patterns exist in the knowledge base that could affect your logic.
- **Valuable Lessons (Scan and Skip)**: When `search_knowledge` returns results, check their `history_status`. 
    - If status is 'Mastered' or 'Lesson Learned', you **DO NOT** need to practice it. Use the `rethink_summary` immediately to boost your confidence and logic.
    - Only use `practice_question` for 'New' questions or if you need to verify a specific strategy on a 'Lesson Learned' pattern.
- **Drafting & Calculation**: Use the `think` tool to perform ALL mathematical calculations, logic derivations, and strategy planning. Call `generate_final_answer` ONLY ONCE as your absolute last action after all logic is 100% complete and verified.
- **Format**: All final answers must be wrapped in `<Answer>` tags (e.g., `<Answer>['value']</Answer>`).

DO NOT use conversational filler. Provide your reasoning ONLY when calling the `think` tool.
"""


class TableSageAgent:
    """
    Business-aligned ReAct Agent for TableSage.
    RAG retrieval is a fixed first step; the Agent drives the practice+strategy loop.
    """

    def __init__(
        self,
        max_steps: int = 10,
        model: Optional[str] = None,
    ):
        self.max_steps = max_steps
        self.model = model or LLM_MODEL
        self._client = OpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_API_BASE or None,
        )

    # ── Public: synchronous ──────────────────────────────────────────────────
    def run(
        self,
        question: str,
        table: Dict[str, Any],
        is_training: bool = False,
        true_answer: Optional[str] = None,
        session_history: Optional[List[Dict[str, Any]]] = None,
        reasoning_summary: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run the full Agent pipeline and return a complete result dict.
        """
        # Step 1: Initialize Messages (No RAG result needed anymore)
        messages = self._build_initial_messages(
            question, table, session_history, reasoning_summary
        )
        reasoning_trace: List[Dict[str, Any]] = []
        tools_used: List[str] = []
        final_answer_context: Dict[str, Any] = {}
        last_confidence_score: Optional[float] = None
        retrieved_ids: List[str] = [] # Track IDs seen in this session to avoid redundancy

        for step in range(1, self.max_steps + 1):
            logger.info(f"[Agent] Step {step}/{self.max_steps}")

            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=ALL_TOOLS,
                tool_choice="auto",
                temperature=0.1,
                timeout=60.0,
            )

            msg = response.choices[0].message
            finish_reason = response.choices[0].finish_reason

            logger.info(f"[Agent] Step {step} LLM content: {(msg.content or '')[:200]}")
            logger.info(f"[Agent] Step {step} finish_reason={finish_reason}, tool_calls={len(msg.tool_calls or [])}")

            if finish_reason == "stop" or not msg.tool_calls:
                final_text = msg.content or ""
                reasoning_trace.append({
                    "step": step, "type": "agent_done",
                    "content": final_text,
                })
                break

            # Append assistant message
            messages.append({
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in msg.tool_calls
                ],
            })

            for tc in msg.tool_calls:
                tool_name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                logger.info(f"[Agent] Step {step} -> Tool: {tool_name}, args: {json.dumps(args, ensure_ascii=False, default=str)[:200]}")

                # ReAct logic is now fully driven by the Agent's choices.
                if tool_name == "generate_final_answer":
                    # --- Confidence Guard ---
                    # Check if 'think' was called and what the confidence was
                    has_thought = any(t["type"] == "tool_call" and t["tool"] == "think" for t in reasoning_trace)
                    low_confidence = last_confidence_score is not None and last_confidence_score < 0.8
                    
                    if not has_thought or low_confidence:
                        tool_result = {
                            "error": "Rethink required. You must call 'think' to assess your logic and ensure confidence >= 0.8 "
                                     "before calling generate_final_answer. If your confidence is still low, perform a 'search_knowledge'."
                        }
                    else:
                        args["user_question"] = question
                        args["user_table"] = table
                        args["is_training"] = is_training
                        if is_training and true_answer:
                            args["true_answer"] = true_answer
                        tool_result = self._execute_tool(tool_name, args)
                elif tool_name == "search_knowledge":
                    # Auto-inject current question, table, and excluded IDs for fresh results
                    args["user_question"] = question
                    args["user_table"] = table
                    args["exclude_ids"] = retrieved_ids
                    tool_result = self._execute_tool(tool_name, args)
                    
                    # Track newly retrieved IDs
                    if isinstance(tool_result, dict) and "results" in tool_result:
                        for res in tool_result["results"]:
                            if "table_id" in res:
                                retrieved_ids.append(res["table_id"])
                else:
                    # Execute tool
                    tool_result = self._execute_tool(tool_name, args)
                tools_used.append(tool_name)

                if tool_name == "generate_final_answer":
                    final_answer_context = tool_result
                elif tool_name == "think" and "confidence_score" in tool_result:
                    last_confidence_score = tool_result["confidence_score"]

                summary = _summarize(tool_result)
                logger.info(f"[Agent] Step {step} <- Result: {summary}")
                reasoning_trace.append({
                    "step": step,
                    "type": "tool_call",
                    "tool": tool_name,
                    "arguments": args,
                    "result_summary": summary,
                })

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(tool_result, ensure_ascii=False, default=str),
                })

        # Determine final confidence: use actual LLM thought if available, else default
        final_confidence = last_confidence_score if last_confidence_score is not None else 0.5

        # Extract <Answer> from LLM's final text (Route B: LLM generates answer itself)
        final_text = ""
        for t in reversed(reasoning_trace):
            if t.get("type") == "agent_done":
                final_text = t.get("content", "")
                break
        
        extracted_answer = ""
        if final_text:
            match = re.search(r"<Answer>([\s\S]*?)</Answer>", final_text)
            extracted_answer = match.group(1).strip() if match else ""

        # Training mode: validate answer at agent level
        is_correct = None
        if is_training and true_answer is not None and extracted_answer:
            from utils.utils import TableUtils as _TU
            is_correct = _TU().is_answer_correct(final_text, true_answer)

        return {
            "answer": extracted_answer,
            "raw_answer": final_text,
            "context_used": final_answer_context.get("context_used", "direct"),
            "confidence": final_confidence,
            "similar_questions": [], # Now dynamic
            "flow_path": "agent",
            "reasoning_trace": reasoning_trace,
            "tools_used": tools_used,
            "total_steps": len([t for t in reasoning_trace if t["type"] == "tool_call"]),
            "user_question": question,
            "user_table": table,
            "true_answer": true_answer,
            "is_correct": is_correct,
        }

    # ── Public: streaming generator ──────────────────────────────────────────
    def run_stream(
        self,
        question: str,
        table: Dict[str, Any],
        is_training: bool = False,
        true_answer: Optional[str] = None,
        session_history: Optional[List[Dict[str, Any]]] = None,
        reasoning_summary: Optional[str] = None
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Stream Agent execution step-by-step.
        Yields dicts with 'step' key: start → rag → thinking → tool_call → tool_result → end/error
        """
        yield {"step": "start", "message": "TableSage Agent 开始处理"}

        try:
            # Step 1: Initialize Messages
            messages = self._build_initial_messages(
                question, table, session_history, reasoning_summary
            )
            reasoning_trace: List[Dict[str, Any]] = []
            tools_used: List[str] = []
            final_answer_context: Dict[str, Any] = {}
            last_confidence_score: Optional[float] = None
            retrieved_ids: List[str] = [] # Track IDs seen in this session

            for step_num in range(1, self.max_steps + 1):
                yield {"step": "thinking", "message": f"Step {step_num}: Agent 正在决策..."}

                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=ALL_TOOLS,
                    tool_choice="auto",
                    temperature=0.1,
                    timeout=60.0,
                )

                msg = response.choices[0].message
                finish_reason = response.choices[0].finish_reason

                logger.info(f"[Agent-Stream] Step {step_num} LLM content: {(msg.content or '')[:200]}")
                logger.info(f"[Agent-Stream] Step {step_num} finish_reason={finish_reason}, tool_calls={len(msg.tool_calls or [])}")

                if finish_reason == "stop" or not msg.tool_calls:
                    final_text = msg.content or ""
                    reasoning_trace.append({
                        "step": step_num, "type": "agent_done",
                        "content": final_text,
                    })
                    break

                messages.append({
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [
                        {"id": tc.id, "type": "function",
                         "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                        for tc in msg.tool_calls
                    ],
                })

                for tc in msg.tool_calls:
                    tool_name = tc.function.name
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        args = {}

                    logger.info(f"[Agent-Stream] Step {step_num} -> Tool: {tool_name}, args: {json.dumps(args, ensure_ascii=False, default=str)[:200]}")

                    yield {"step": "tool_call", "tool": tool_name,
                           "message": f"调用工具: {tool_name}"}

                    # ReAct logic is now fully driven by the Agent's choices.
                    if tool_name == "generate_final_answer":
                        # --- Confidence Guard ---
                        has_thought = any(t["type"] == "tool_call" and t["tool"] == "think" for t in reasoning_trace)
                        low_conf = last_confidence_score is not None and last_confidence_score < 0.8
                        
                        if not has_thought or low_conf:
                            tool_result = {
                                "error": "Rethink required. You must call 'think' to assess your logic and ensure confidence >= 0.8 "
                                         "before calling generate_final_answer. If your confidence is still low, perform a 'search_knowledge'."
                            }
                        else:
                            args["user_question"] = question
                            args["user_table"] = table
                            args["is_training"] = is_training
                            if is_training and true_answer:
                                args["true_answer"] = true_answer
                            tool_result = self._execute_tool(tool_name, args)
                    elif tool_name == "search_knowledge":
                        # Auto-inject current question, table, and excluded IDs
                        args["user_question"] = question
                        args["user_table"] = table
                        args["exclude_ids"] = retrieved_ids
                        tool_result = self._execute_tool(tool_name, args)

                        # Track newly retrieved IDs
                        if isinstance(tool_result, dict) and "results" in tool_result:
                            for res in tool_result["results"]:
                                if "table_id" in res:
                                    retrieved_ids.append(res["table_id"])
                    else:
                        # Robust argument check
                        if not isinstance(args, dict):
                            tool_result = {"error": f"Tool arguments must be an object, but got {type(args).__name__}"}
                        else:
                            tool_result = self._execute_tool(tool_name, args)
                        
                    tools_used.append(tool_name)

                    if tool_name == "generate_final_answer":
                        final_answer_context = tool_result
                    elif tool_name == "think" and "confidence_score" in tool_result:
                        last_confidence_score = tool_result["confidence_score"]

                    summary = _summarize(tool_result)
                    logger.info(f"[Agent-Stream] Step {step_num} <- Result (Summary): {summary}")
                    # 使用 INFO 级别让用户能看到传回模型的具体内容
                    logger.info(f"[Agent-Stream] Step {step_num} <- Result (Full): {json.dumps(tool_result, ensure_ascii=False, default=str)[:1000]}")
                    
                    reasoning_trace.append({
                        "step": step_num, "type": "tool_call",
                        "tool": tool_name, "arguments": args,
                        "result_summary": summary,
                    })

                    yield {"step": "tool_result", "tool": tool_name,
                           "result_summary": summary, "message": f"{tool_name} 执行完成"}

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(tool_result, ensure_ascii=False, default=str),
                    })

            # Determine final confidence
            final_confidence = last_confidence_score if last_confidence_score is not None else 0.5

            # Extract <Answer> from LLM's final text (Route B)
            final_text = ""
            for t in reversed(reasoning_trace):
                if t.get("type") == "agent_done":
                    final_text = t.get("content", "")
                    break
            
            extracted_answer = ""
            if final_text:
                match = re.search(r"<Answer>([\s\S]*?)</Answer>", final_text)
                extracted_answer = match.group(1).strip() if match else ""

            # Training mode: validate answer at agent level
            is_correct_val = None
            if is_training and true_answer is not None and extracted_answer:
                from utils.utils import TableUtils as _TU
                is_correct_val = _TU().is_answer_correct(final_text, true_answer)

            complete_result = {
                "answer": extracted_answer,
                "raw_answer": final_text,
                "context_used": final_answer_context.get("context_used", "direct"),
                "confidence": final_confidence,
                "similar_questions": [], # Now dynamic
                "flow_path": "agent",
                "reasoning_trace": reasoning_trace,
                "tools_used": tools_used,
                "user_question": question,
                "user_table": table,
                "true_answer": true_answer,
                "is_correct": is_correct_val,
            }
            yield {
                "step": "end",
                "message": "Agent 答题流程完成",
                "answer": complete_result["answer"],
                "complete_result": complete_result,
            }

        except Exception as e:
            import traceback
            yield {"step": "error", "error": str(e), "error_details": traceback.format_exc()}

    # (Internal methods _rag_retrieval and _estimate_final_confidence removed in favor of Agentic ReAct)

    # ── Private: build initial messages ──────────────────────────────────────
    def _build_initial_messages(
        self,
        question: str,
        table: Dict[str, Any],
        session_history: Optional[List[Dict[str, Any]]] = None,
        reasoning_summary: Optional[str] = None
    ) -> List[Dict]:
        formatted_table = TableUtils.table2format(table)

        # Build Session Context if available
        session_info = ""
        if session_history or reasoning_summary:
            session_info = "## Session History & Context\n"
            if reasoning_summary:
                session_info += f"### Previous Reasoning Summary:\n{reasoning_summary}\n\n"
            if session_history:
                session_info += "### Recent Conversation History:\n"
                for i, turn in enumerate(session_history[-3:]): # Last 3 turns
                    session_info += f"Q: {turn.get('question')}\nA: {turn.get('answer')}\n"
                session_info += "\n"

        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"{session_info}"
                    f"## User's Question:\n{question}\n\n"
                    f"## User's Table:\n{formatted_table}\n\n"
                    "**INSTRUCTIONS**: Analyze the question and table.\n"
                    "1. If unsure, use `search_knowledge` to find similar patterns.\n"
                    "2. **Scan Results**: If you see 'Mastered' or 'Lesson Learned' questions, read their `rethink_summary`. "
                    "These are your cheat sheets. Use them to INCREASE your confidence via 'think' without wasting turns on practice.\n"
                    "3. **Targeted Practice**: Only use `practice_question` on 'New' questions or to verify a strategy for complex patterns.\n"
                    "4. Call `generate_final_answer` once confidence is >= 0.8."
                ),
            },
        ]

    # ── Private: tool dispatch ────────────────────────────────────────────────
    def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        executor = TOOL_EXECUTORS.get(tool_name)
        if executor is None:
            return {"error": f"Unknown tool: {tool_name}"}
        try:
            return executor(**arguments)
        except TypeError as e:
            return {"error": f"Argument error for '{tool_name}': {str(e)}"}
        except Exception as e:
            import traceback
            return {"error": str(e), "error_details": traceback.format_exc()}

    # (Static method _estimate_final_confidence removed)


# ── Helper ────────────────────────────────────────────────────────────────────
def _summarize(result: Dict[str, Any]) -> str:
    """Create a brief summary of a tool result for the trace."""
    if "error" in result and not result.get("mastered_ids") and not result.get("attempt_ids"):
        return f"Error: {result['error']}"
    # search_knowledge (new) result
    if "results" in result:
        count = len(result.get("results", []))
        return f"Search results: found {count} candidates."
    
    # practice_question (new) result
    if "is_correct" in result and "strategy_used" in result:
        return (f"Practice: id={result.get('table_id')}, strategy={result.get('strategy_used')}, "
                f"correct={result.get('is_correct')}, record={result.get('record_saved')}")

    # (Legacy results handled as fallback)
    if "is_correct" in result:
        correct = result["is_correct"]
        table_id = result.get("table_id", "?")
        return (f"table_id={table_id}, "
                f"is_correct={correct}, record={result.get('record_saved', 'none')}")
    # think result
    if "has_sufficient_context" in result:
        conf = result.get("confidence_score")
        suff = result.get("has_sufficient_context")
        return f"Think: sufficient_context={suff}, confidence={conf:.2f}"
    # generate_final_answer (context-prep) result
    if "enriched_context" in result:
        ctx = result.get("context_used", "direct")
        return f"Context prepared: type={ctx}, few_shot={result.get('few_shot_count', 0)}, reflection={result.get('reflection_count', 0)}"
    return str(result)[:200]
