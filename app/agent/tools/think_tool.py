"""
Think Tool – ReAct "Thought" Step

The LLM calls this tool to explicitly record its reasoning about whether
the accumulated practice context is sufficient to answer the user's original question.

This makes the Observation → Thought phase of the ReAct loop transparent:
instead of the agent silently deciding to stop, it must verbalise *why* it
thinks it has (or hasn't) enough context and give an explicit confidence score.

The tool does NOT enforce a hard stop – the LLM still decides whether to
call generate_final_answer or do more practice.  The thought is logged in
the reasoning_trace and the confidence_score is surfaced in the final result.
"""
from typing import Any, Dict, Optional

# ── OpenAI function-calling schema ────────────────────────────────────────────
THINK_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "think",
        "description": (
            "Record your reasoning about whether you currently have enough context "
            "to accurately answer the user's ORIGINAL question. "
            "Call this tool after each answer_by_id or apply_strategy_by_id result "
            "to make your Thought step explicit in the ReAct loop. "
            "This is NOT a final answer tool – use it to think out loud. "
            "After calling this, decide whether to practice another question "
            "or proceed to generate_final_answer."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reasoning": {
                    "type": "string",
                    "description": (
                        "Your step-by-step reasoning about the current state of knowledge. "
                        "Mention: what patterns/strategies you've learned so far, "
                        "how similar the practiced questions are to the user's question, "
                        "and what (if anything) is still unclear."
                    ),
                },
                "has_sufficient_context": {
                    "type": "boolean",
                    "description": (
                        "True if you believe you already have enough understanding "
                        "to answer the user's original question accurately. "
                        "False if you think more practice would meaningfully help."
                    ),
                },
                "confidence_score": {
                    "type": "number",
                    "description": (
                        "Your self-assessed confidence that you can answer the user's "
                        "original question correctly, given the context accumulated so far. "
                        "Range: 0.0 to 1.0. "
                        "CRITICAL: If you have NOT yet called search_knowledge for this question, "
                        "your confidence_score MUST NOT exceed 0.7, as you haven't verified the "
                        "knowledge base for potential hidden patterns or lessons."
                    ),
                },
                "draft_logic": {
                    "type": "string",
                    "description": (
                        "If you are about to answer, provide a brief draft of your reasoning "
                        "or the formula you intend to use. This allows you to 'double check' "
                        "your work before calling generate_final_answer."
                    ),
                },
            },
            "required": ["reasoning", "has_sufficient_context", "confidence_score"],
        },
    },
}


def think_tool(
    reasoning: str,
    has_sufficient_context: bool,
    confidence_score: float,
    draft_logic: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Record the agent's explicit ReAct Thought step.

    Args:
        reasoning: The LLM's step-by-step reasoning about context sufficiency.
        has_sufficient_context: Whether the LLM believes it has enough context now.
        confidence_score: Self-assessed confidence [0.0, 1.0].

    Returns:
        dict with the recorded thought, acknowledged back to the LLM so it
        can continue the ReAct loop.
    """
    # Clamp confidence to valid range
    confidence_score = max(0.0, min(1.0, float(confidence_score)))

    return {
        "acknowledged": True,
        "has_sufficient_context": bool(has_sufficient_context),
        "confidence_score": round(confidence_score, 3),
        "message": (
            "Thought recorded. "
            + (
                "You may proceed to generate_final_answer."
                if has_sufficient_context
                else "Consider practicing another question if attempt_ids remain."
            )
        ),
    }
