"""
Agent API – FastAPI routes for the TableSage Agent

Flow:
  1. RAG retrieval (mandatory, inside agent.run)
  2. Agent self-assesses context sufficiency using similarity scores + flag distribution
  3. Practices attempt_ids questions as needed (agent decides how many)
  4. Generates final answer using accumulated few-shot context
"""
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent.tablesage_agent import TableSageAgent
from agent.router_agent import RouterAgent

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agent", tags=["Agent 智能问答"])

# 初始化 Router Agent
router_agent = RouterAgent()


class TableData(BaseModel):
    header: List[str] = Field(..., description="表格表头列名列表")
    rows: List[List[Any]] = Field(..., description="表格行数据")


class AgentAnswerRequest(BaseModel):
    question: str = Field(..., min_length=1, description="用户的自然语言问题")
    table: TableData = Field(..., description="表格数据")
    max_steps: int = Field(10, ge=1, le=20, description="Agent 最大推理步数（默认10）")
    is_training: bool = Field(False, description="是否为训练模式")
    true_answer: Optional[str] = Field(None, description="训练模式下的标准答案")


@router.post(
    "/answer",
    summary="Agent 同步问答",
    description=(
        "使用 TableSage Agent 回答表格问题。\n\n"
        "**流程**: RAG检索 → Agent自主判断信息充足性（基于相似度分数+历史记录分布）→ 按需练题 → 生成最终答案\n\n"
        "Agent 自主决定何时停止练题，无需外部传入置信度阈值。"
    ),
)
async def agent_answer(request: AgentAnswerRequest):
    agent = TableSageAgent(max_steps=request.max_steps)
    table_dict = {"header": request.table.header, "rows": request.table.rows}
    
    # 1. 通过 Router Agent 抽取意图和纯净的核心问题
    table_schema_str = ", ".join(table_dict["header"])
    plan = await router_agent.analyze_intent(request.question, False, table_schema_str)
    core_question = plan.get("core_question", request.question)
    
    result = agent.run(
        question=core_question,
        table=table_dict,
        is_training=request.is_training,
        true_answer=request.true_answer,
    )
    
    # 将路由分析结果注入返回值，方便排查
    if isinstance(result, dict):
        result["router_plan"] = plan
        result["original_question"] = request.question
        
    return result


@router.post(
    "/answer/stream",
    summary="Agent 流式问答（SSE）",
    description=(
        "流式版本，逐步返回 Agent 的每个推理步骤（Server-Sent Events）。\n\n"
        "每行返回一个 JSON 对象，`step` 字段说明当前阶段:\n"
        "- `rag_done`: RAG结果（含相似度分数）\n"
        "- `tool_call` / `tool_result`: 工具调用\n"
        "- `end`: 最终答案"
    ),
)
async def agent_answer_stream(request: AgentAnswerRequest):
    agent = TableSageAgent(max_steps=request.max_steps)
    table_dict = {"header": request.table.header, "rows": request.table.rows}

    # 1. 通过 Router Agent 抽取意图和纯净的核心问题
    table_schema_str = ", ".join(table_dict["header"])
    plan = await router_agent.analyze_intent(request.question, False, table_schema_str)
    core_question = plan.get("core_question", request.question)

    async def event_stream():
        # 首先输出 router 推断结果
        yield f"data: {json.dumps({'step': 'router', 'plan': plan}, ensure_ascii=False, default=str)}\\n\\n"
        
        import asyncio
        loop = asyncio.get_event_loop()
        
        gen = agent.run_stream(
            question=core_question,
            table=table_dict,
            is_training=request.is_training,
            true_answer=request.true_answer,
        )
        
        # Helper to get next chunk safely within a thread
        def get_next_chunk():
            try:
                return next(gen)
            except StopIteration:
                return None
            except Exception as e:
                return {"step": "error", "error": str(e)}

        while True:
            # Poll the generator in a thread
            chunk = await loop.run_in_executor(None, get_next_chunk)
            
            if chunk is None:
                break
                
            yield f"data: {json.dumps(chunk, ensure_ascii=False, default=str)}\n\n"
            
            if chunk.get("step") == "error":
                break

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/info", summary="Agent 配置信息")
async def agent_info():
    from agent.tools import ALL_TOOLS
    import os
    return {
        "agent": "TableSageAgent",
        "confidence_mode": "autonomous (LLM judges from similarity scores + flag distribution)",
        "flow": [
            "1. RAG retrieval",
            "2. get_learning_records -> skip_ids/attempt_ids/error_context_ids + auto_confidence",
            "3. Agent self-assesses: similarity scores >= 0.85 + skip_ids ratio -> may skip practice",
            "4. answer_by_id (for attempt_ids the agent chooses to try)",
            "5. apply_strategy_by_id (cot/column_sorting/schema_linking if wrong)",
            "6. generate_final_answer with few-shot context",
        ],
        "model": os.getenv("LLM_MODEL", "gpt-3.5-turbo"),
        "tools": [
            {"name": t["function"]["name"], "desc": t["function"]["description"][:80] + "..."}
            for t in ALL_TOOLS
        ],
    }
