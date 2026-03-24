import os
import json
import logging
import hashlib
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from openai import AsyncOpenAI

from agent.tablesage_agent import TableSageAgent
from agent.router_agent import RouterAgent
from agent.visualization_agent import VisualizationAgent
from mcp_client.connection import all_tools, call_tool, extract_text_content
from document_general.document_genral import generate_tablesage_report
from db.db_manager import DatabaseManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["mcp聊天主体"])

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_API_BASE)

# Initialization handled per request for TableSageAgent
# 初始化Router Agent
router_agent = RouterAgent()
# 初始化Visualization Agent
visualization_agent = VisualizationAgent(mcp_tools=all_tools, tool_caller=call_tool)
# 初始化数据库管理器
db_manager = DatabaseManager()

def generate_session_id(content: Any, table: Optional[Dict] = None) -> str:
    """生成会话ID (兼容旧版接口)"""
    if table:
        return hashlib.md5(f"{str(content)}_{str(table)}".encode()).hexdigest()
    return hashlib.md5(str(content).encode()).hexdigest()

# alias for internal use
generate_content_hash = generate_session_id

# 结果缓存 (兼容旧版接口使用)
class ResultCacheProxy(dict):
    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        # 顺便同步到数据库，确保多流一致性
        try:
            db_manager.save_result_cache(key, value)
        except:
            pass
        
    def get(self, key, default=None):
        # Use dict's own get to avoid recursion and satisfy linter
        val = super().get(key)
        if val is None:
            # 尝试从数据库加载
            try:
                db_val = db_manager.get_result_cache(key)
                return db_val if db_val is not None else default
            except:
                return default
        return val

result_cache = ResultCacheProxy()

# ------------------ API 数据模型 ------------------
class TableData(BaseModel):
    """表格数据模型"""
    header: List[str] = Field(..., description="表格表头")
    rows: List[List[Any]] = Field(..., description="表格行数据")

class QuestionRequest(BaseModel):
    """问题请求模型"""
    question: str = Field(..., min_length=1, description="用户问题")
    table: TableData = Field(..., description="表格数据")
    flag: Optional[bool] = Field(False, description="是否为标志性请求，默认为 False")
    conversation_id: Optional[str] = Field(None, description="会话ID (多轮对话)")
    session_id: Optional[str] = Field(None, description="结果缓存ID (单次请求)")

class CallToolRequest(BaseModel):
    server: str
    name: str
    args: Dict[str, Any] = {}

class ToggleToolRequest(BaseModel):
    tool_name: str
    enabled: bool

class GenerateReportRequest(BaseModel):
    session_id: str

# ------------------ API 实现 ------------------
@router.get("/tools")
async def api_tools():
    return {"tools": [t.model_dump() for t in all_tools]}

@router.post("/tools/toggle")
async def toggle_mcp_tool(request: ToggleToolRequest):
    from mcp_client.connection import toggle_tool
    success = toggle_tool(request.tool_name, request.enabled)
    if success:
        return {"status": "success", "message": f"Tool {request.tool_name} toggled to {request.enabled}"}
    raise HTTPException(status_code=404, detail=f"Tool {request.tool_name} not found")

@router.post("/call-tool")
async def api_call_tool(req: CallToolRequest):
    result = await call_tool(req.server, req.name, req.args)
    # MCP 返回结构兼容性处理
    if hasattr(result, 'content') and result.content: # type: ignore
        content = extract_text_content(result.content) # type: ignore
    else:
        content = str(result)
    return {"result": content}

@router.post("/answer")
async def api_chat(request: QuestionRequest):
    user_table = {
        "header": request.table.header,
        "rows": request.table.rows
    }
    
    # 确定 conversation_id 和 session_context
    conversation_id = request.conversation_id or generate_content_hash(request.question)
    session_context = db_manager.get_session_context(conversation_id)
    
    # 检测表格是否变更
    current_table_hash = generate_content_hash(user_table)
    if session_context["table_hash"] != current_table_hash:
        logger.info(f"Table changed for session {conversation_id}. Resetting context.")
        db_manager.reset_session_context(conversation_id, current_table_hash)
        session_context = {"table_hash": current_table_hash, "history": [], "reasoning_summary": ""}

    # 确定 session_id (用于 Viz/Report 缓存)
    session_id = request.session_id or generate_content_hash(f"{conversation_id}_{request.question}")
    cached_data = db_manager.get_result_cache(session_id)
    has_cached_data = cached_data is not None

    table_schema_str = ", ".join([str(h) for h in user_table["header"]])

    # --- SEMANTIC CACHE ---
    # Construct a robust semantic key for identical question + table schema
    semantic_key = f"SEM_{generate_content_hash(request.question + current_table_hash)}"
    semantic_cached_result = db_manager.get_result_cache(semantic_key)
    
    # If high confidence cache exists, directly yield results (skip Router and Agent)
    if semantic_cached_result and semantic_cached_result.get("confidence", 0) >= 0.8:
        logger.info(f"Hit semantic cache for question: {request.question}")
        async def fast_stream():
            plan_mock = {"needs_data_query": False, "needs_visualization": False, "needs_report": False, "core_question": request.question, "visualization_instruction": ""}
            yield f"data: {json.dumps({'step': 'router', 'plan': plan_mock, 'message': '命中语义缓存，跳过大模型分析'}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'step': 'end', 'message': '答题流程结束', 'complete_result': semantic_cached_result}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'step': 'task_done', 'report_available': True, 'generate_report_url': f'/api/chat/generate-report/{semantic_key}'}, ensure_ascii=False)}\n\n"
        return StreamingResponse(fast_stream(), media_type="text/event-stream")

    # 1. Router Agent 进行意图分析 (带入历史记录)
    plan = await router_agent.analyze_intent(
        request.question, 
        has_cached_data, 
        table_schema_str,
        history=session_context["history"]
    )
    
    # 2. 从 plan 中提取指令
    needs_data_query = plan.get("needs_data_query", True)
    needs_visualization = plan.get("needs_visualization", False) or request.flag
    needs_report = plan.get("needs_report", False)
    core_question = plan.get("core_question", request.question)
    visualization_instruction = plan.get("visualization_instruction", "生成图表")
    
    # 构建流式响应生成器
    async def event_stream():
        nonlocal cached_data, has_cached_data
        
        # 0. 基础输入校验
        table_is_empty = not user_table.get("header") and not user_table.get("rows")
        if table_is_empty and not has_cached_data:
            yield json.dumps({
                "step": "error", 
                "error": "抱歉，我没有发现您上传的表格数据或之前的对话历史。请先上传表格并描述您想要分析的问题。"
            }, ensure_ascii=False) + "\n"
            return

        yield f"data: {json.dumps({'step': 'router', 'plan': plan}, ensure_ascii=False)}\n\n"

        # 核心逻辑：若 Router 明确需要查询，则运行 Data Agent。
        # 若 Router 认为不需要查询（即直接针对库表进行 Viz/Report），则跳过 Data Agent。
        should_run_data_agent = needs_data_query
        
        # 优化：如果是直接绘图/报告且没有历史缓存，我们初始化一个基于原表的上下文，避免强制跑 Data Agent 的 ReAct 循环
        if not should_run_data_agent and (needs_visualization or needs_report) and not has_cached_data:
            cached_data = {
                "answer": "直接对原始表格数据进行操作。",
                "user_question": request.question,
                "user_table": user_table,
                "confidence": 1.0,
                "reasoning": "用户请求直接对当前表格进行可视化或报告生成，无需额外数据检索。"
            }
            has_cached_data = True
            logger.info(f"Using direct table context for {session_id} to skip Data Agent.")

        if should_run_data_agent:
            import asyncio
            loop = asyncio.get_event_loop()
            agent = TableSageAgent(max_steps=10)
            
            gen = agent.run_stream(
                question=core_question,
                table=user_table,
                session_history=session_context["history"],
                reasoning_summary=session_context["reasoning_summary"]
            )
            
            def get_next_chunk():
                try:
                    return next(gen)
                except StopIteration:
                    return None
                except Exception as e:
                    return {"step": "error", "error": str(e)}

            try:
                while True:
                    chunk = await loop.run_in_executor(None, get_next_chunk)
                    if chunk is None:
                        break
                        
                    chunk["conversation_id"] = conversation_id
                    chunk["session_id"] = session_id
                    
                    if chunk.get("step") == "end":
                        cached_data = chunk.get("complete_result")
                        if cached_data:
                            # 1. 保存结果缓存 (用于绘图/报告)
                            db_manager.save_result_cache(session_id, cached_data)
                            # 2. 存入语义缓存 (仅当置信度高时)
                            if cached_data.get("confidence", 0) >= 0.8:
                                db_manager.save_result_cache(semantic_key, cached_data)
                    
                    yield f"data: {json.dumps(chunk, ensure_ascii=False, default=str)}\n\n"
                    
                    if chunk.get("step") == "error":
                        break
            except Exception as e:
                error_item = {"step": "error", "error": f"Data Agent 错误: {str(e)}", "session_id": session_id}
                yield f"data: {json.dumps(error_item, ensure_ascii=False)}\n\n"
                return

        # 任何情况下都尝试保存对话历史 (保持 Router 上下文)
        # 如果 Data Agent 没跑，我们也需要记录这一轮
        final_answer = ""
        final_reasoning = ""
        if cached_data:
            final_answer = cached_data.get("answer", "")
            final_reasoning = cached_data.get("reasoning", "")
        
        db_manager.update_session_history(
            conversation_id,
            current_table_hash,
            request.question,
            final_answer,
            reasoning_summary=final_reasoning
        )
        logger.info(f"Session history updated for {conversation_id}. Answer length: {len(final_answer)}")

        # (B) Visualization Agent (MCP 图表)
        if needs_visualization:
            if cached_data:
                yield f"data: {json.dumps({'step': 'visualization_start', 'message': '开始调用MCP生成图表...'}, ensure_ascii=False)}\n\n"
                try:
                    toolCalls = await visualization_agent.generate_chart(user_table, cached_data, visualization_instruction)
                    
                    if len(toolCalls) == 1 and toolCalls[0].get("name") == "none":
                        yield f"data: {json.dumps({'step': 'visualization_done', 'message': toolCalls[0].get('message'), 'content': toolCalls[0].get('content')}, ensure_ascii=False)}\n\n"
                    else:
                        yield f"data: {json.dumps({'step': 'visualization_done', 'tool_calls': toolCalls, 'message': '图表生成完毕'}, ensure_ascii=False)}\n\n"
                except Exception as e:
                    yield f"data: {json.dumps({'step': 'error', 'error': f'Visualization Agent 错误: {str(e)}'}, ensure_ascii=False)}\n\n"
            else:
                yield f"data: {json.dumps({'step': 'error', 'error': '无法生成图表：未获取到有效的答题数据上下文。'}, ensure_ascii=False)}\n\n"

        # (C) Report Agent 处理
        if needs_report:
            if cached_data:
                yield f"data: {json.dumps({'step': 'report_start', 'message': '开始生成分析报告...'}, ensure_ascii=False)}\n\n"
                try:
                    # 1. 状态流：准备数据
                    yield f"data: {json.dumps({'step': 'report_status', 'message': '正在整合数据和上下文...'}, ensure_ascii=False)}\n\n"
                    
                    # 2. 状态流与内容流：生成执行摘要 (Executive Summary)
                    yield f"data: {json.dumps({'step': 'report_status', 'message': '正在生成执行摘要...'}, ensure_ascii=False)}\n\n"
                    
                    summary_prompt = f"请根据以下数据分析结果写一份简短的管理层执行摘要（100字左右）：\n问题：{cached_data.get('user_question')}\n回答：{cached_data.get('answer')}"
                    
                    response = await openai_client.chat.completions.create(
                        model=LLM_MODEL,
                        messages=[{"role": "user", "content": summary_prompt}],
                        stream=True,
                        temperature=0.3
                    )
                    
                    full_summary = ""
                    async for chunk in response:
                        content = chunk.choices[0].delta.content
                        if content:
                            full_summary += content
                            yield f"data: {json.dumps({'step': 'report_chunk', 'content': content}, ensure_ascii=False)}\n\n"

                    # 3. 状态流：打包排版文档
                    yield f"data: {json.dumps({'step': 'report_status', 'message': '正在排版并生成 Word 文档...'}, ensure_ascii=False)}\n\n"
                    
                    import asyncio
                    loop = asyncio.get_event_loop()
                    report_path = await loop.run_in_executor(
                        None,
                        generate_tablesage_report,
                        cached_data.get("user_question", ""),
                        cached_data.get("user_table", {}),
                        cached_data
                    )
                    
                    from backend_api.file_service_api import file_service
                    user_q = cached_data.get("user_question", "")
                    file_id = file_service.register_file(
                        report_path,
                        f"TableSage_Report_{user_q[:20].replace(' ', '_')}.docx"
                    )
                    yield f"data: {json.dumps({'step': 'report_done', 'file_id': file_id, 'download_url': f'/api/files/download/{file_id}', 'message': '报告生成成功', 'summary': full_summary}, ensure_ascii=False)}\n\n"
                except Exception as e:
                    yield f"data: {json.dumps({'step': 'error', 'error': f'Report Agent 错误: {str(e)}'}, ensure_ascii=False)}\n\n"
            else:
                yield f"data: {json.dumps({'step': 'error', 'error': '无法生成报告：未获取到有效的答题数据上下文。'}, ensure_ascii=False)}\n\n"
        
        # 结尾处理
        if cached_data and not needs_report:
            yield f"data: {json.dumps({'step': 'task_done', 'report_available': True, 'generate_report_url': f'/api/chat/generate-report/{session_id}'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@router.post("/generate-report/{session_id}")
async def generate_report(session_id: str):
    """根据会话ID生成报告"""
    try:
        # 从数据库缓存中获取结果
        complete_result = db_manager.get_result_cache(session_id)
        if not complete_result:
            raise HTTPException(status_code=404, detail="会话不存在或已过期")
        
        # 生成报告
        report_path = generate_tablesage_report(
            complete_result.get("user_question", ""),
            complete_result.get("user_table", {}),
            complete_result
        )
        
        # 注册文件到文件服务
        from backend_api.file_service_api import file_service
        user_question = complete_result.get("user_question", "")
        file_id = file_service.register_file(
            report_path,
            f"TableSage_Report_{user_question[:20].replace(' ', '_')}.docx"
        )
        
        return {
            "success": True,
            "file_id": file_id,
            "download_url": f"/api/files/download/{file_id}",
            "message": "报告生成成功"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
