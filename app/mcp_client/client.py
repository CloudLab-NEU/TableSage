import os
import json
import asyncio
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, APIRouter
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
# MCP/LLM 相关依赖
from openai import AsyncOpenAI
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession
from mcp.types import Tool, TextContent
from pydantic import BaseModel, Field
import re
from core_progress.tablesage_processor import TableSageProcessor
import hashlib


# 初始化TableSage处理器
table_sage_processor = TableSageProcessor(confidence_threshold=0.8)

# 加载环境变量
load_dotenv()

import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["mcp聊天主体"])

# MCP 配置
MCP_CONFIG_PATH = os.getenv("MCP_CONFIG_PATH", "./mcp_client/mcp.json")

# LLM 配置
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")

# 工具缓存
class MCPServerConfig(BaseModel):
    name: str
    url: str
    description: Optional[str] = ""

class MCPToolInfo(BaseModel):
    server: str
    name: str
    description: str
    input_schema: Dict[str, Any]

# 全局缓存
mcp_servers: Dict[str, MCPServerConfig] = {}
all_tools: List[MCPToolInfo] = []
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_API_BASE)

# 答题结果缓存
result_cache: Dict[str, Any] = {}

def generate_session_id(user_question: str, user_table: Dict) -> str:
    """基于问题和表格生成会话ID"""
    content = f"{user_question}_{str(user_table)}"
    return hashlib.md5(content.encode()).hexdigest()

# ------------------ 工具加载 ------------------
def load_mcp_config():
    """
    加载 MCP 配置
    """
    global mcp_servers
    try:
        with open(MCP_CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
        mcp_servers.clear()
        for name, server_config in config.get("mcpServers", {}).items():
            mcp_servers[name] = MCPServerConfig(
                name=name,
                url=server_config["url"],
                description=server_config.get("description", ""),
            )
    except Exception as e:
        raise RuntimeError(f"加载 MCP 配置失败: {e}")

def tool_to_info(server_name: str, tool: Tool) -> MCPToolInfo:
    """
    将 MCP 工具转换为工具信息
    """
    return MCPToolInfo(
        server=server_name,
        name=tool.name,
        description=tool.description or "无描述",
        input_schema=tool.inputSchema or {"type": "object", "properties": {}}
    )

async def get_tools_from_server(name: str, config: MCPServerConfig) -> List[MCPToolInfo]:
    """
    从 MCP 服务器获取工具
    """
    async with sse_client(config.url) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            return [tool_to_info(name, t) for t in tools_result.tools]

async def load_all_tools():
    """
    加载所有工具
    """
    global all_tools
    all_tools.clear()
    tasks = [get_tools_from_server(name, config) for name, config in mcp_servers.items()]
    results = await asyncio.gather(*tasks)
    for tool_list in results:
        all_tools.extend(tool_list)

# ------------------ API 数据模型 ------------------
class ChatMessage(BaseModel):
    role: str  # user/assistant/tool
    content: str

class TableData(BaseModel):
    """表格数据模型"""
    header: List[str] = Field(..., description="表格表头")
    rows: List[List[Any]] = Field(..., description="表格行数据")

class QuestionRequest(BaseModel):
    """问题请求模型"""
    question: str = Field(..., min_length=1, description="用户问题")
    table: TableData = Field(..., description="表格数据")
    flag: Optional[bool] = Field(False, description="是否为标志性请求，默认为 False")

class CallToolRequest(BaseModel):
    server: str
    name: str
    args: Dict[str, Any] = {}

class GenerateReportRequest(BaseModel):
    session_id: str

# ------------------ 工具调用 ------------------
async def call_tool(server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Any:
    config = mcp_servers.get(server_name)
    if not config:
        raise HTTPException(status_code=404, detail=f"服务器 {server_name} 不存在")
    async with sse_client(config.url) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            return result

def extract_text_content(content_list: List[Any]) -> str:
    text_parts: List[str] = []
    for content in content_list:
        if isinstance(content, TextContent):
            text_parts.append(content.text)
        elif hasattr(content, 'text'):
            text_parts.append(str(content.text))
        else:
            text_parts.append(str(content))
    return "\n".join(text_parts) if text_parts else "✅ 操作完成，但没有返回文本内容"

# ------------------ API 实现 ------------------
@router.get("/tools")
async def api_tools():
    return {"tools": [t.model_dump() for t in all_tools]}

@router.post("/call-tool")
async def api_call_tool(req: CallToolRequest):
    result = await call_tool(req.server, req.name, req.args)
    # MCP 返回结构兼容性处理
    if hasattr(result, 'content'):
        content = extract_text_content(result.content)
    else:
        content = str(result)
    return {"result": content}

@router.post("/answer")
async def api_chat(request: QuestionRequest):
    # 构建 LLM 消息历史，首条为 system
    messages = [
        {"role": "system", "content": "You are a smart assistant that can use various MCP tools to help users with their tasks."}
    ]
    flag_prompt = ""
# ,You don't need to answer the question.
    print(request.flag)
    if request.flag:
        flag_prompt = "You need to generate a chart and call the MCP tool"
    else:
        flag_prompt = "No tools are required; just answer the questions."
    print(flag_prompt)    

    user_table = {
        "header": request.table.header,
        "rows": request.table.rows
    }

    prompt = f"""
        ### Table Format:
        {user_table}
        
        ### Question:
        {request.question+' '+flag_prompt}
    
    """
    messages.append({"role": "user", "content": prompt})

    # 构建 tools 列表
    openai_tools = []
    for t in all_tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": f"{t.server}_{t.name}",
                "description": f"[{t.server}] {t.description}",
                "parameters": t.input_schema
            }
        })

    # 第一次 LLM 调用
    kwargs = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": 0.1
    }

    if openai_tools:
        kwargs["tools"] = openai_tools
        kwargs["tool_choice"] = "auto"
    try:
        response = await openai_client.chat.completions.create(**kwargs)
        message = response.choices[0].message
        print(f"LLM Response: {message}")
        toolCalls = []
        # 工具调用
        if hasattr(message, 'tool_calls') and message.tool_calls:
            # 1. tool_calls 作为 assistant 消息加入历史
            messages.append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    } for tc in message.tool_calls
                ]  # 转换为 openai 格式
            })
            # 2. 依次调用工具，结果以 tool 消息加入历史
            for tool_call in message.tool_calls:
                function_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)
                # 解析 server/tool
                parts = function_name.split('_', 1)
                if len(parts) == 2:
                    server_name, tool_name = parts
                else:
                    server_name, tool_name = all_tools[0].server, function_name
                try:
                    fun_call_result = await call_tool(server_name, tool_name, arguments)
                    content = extract_text_content(fun_call_result.content)
                    toolCalls.append({
                        "name": tool_name,
                        "result": content,
                        "tool_call_id": tool_call.id
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": content
                    })
                except Exception as e:
                    toolCalls.append({
                        "name": function_name,
                        "error": str(e),
                        "tool_call_id": tool_call.id
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": f"错误: {str(e)}"
                    })
            return {
                "tool_calls": toolCalls,
            }
        
        else:
            # 生成会话ID
            session_id = generate_session_id(request.question, user_table)
            
            def event_stream():
                user_table = {
                    "header": request.table.header,
                    "rows": request.table.rows
                }
                try:
                    for item in table_sage_processor.process_stream(request.question, user_table):
                        # 添加session_id到每个响应
                        item["session_id"] = session_id
                        
                        # 如果是最终结果，缓存起来
                        if item.get("step") == "end":
                            complete_result = item.get("complete_result")
                            if complete_result:
                                result_cache[session_id] = complete_result
                                # 添加报告生成提示
                                item["report_available"] = True
                                item["generate_report_url"] = f"/api/chat/generate-report/{session_id}"
                        
                        yield json.dumps(item, ensure_ascii=False) + "\n"
                except Exception as e:
                    error_item = {
                        "step": "error",
                        "error": str(e),
                        "session_id": session_id
                    }
                    yield json.dumps(error_item, ensure_ascii=False) + "\n"

            return StreamingResponse(event_stream(), media_type="text/event-stream")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM/对话处理失败: {e}")

@router.post("/generate-report/{session_id}")
async def generate_report(session_id: str):
    """根据会话ID生成报告"""
    try:
        # 从缓存中获取结果
        complete_result = result_cache.get(session_id)
        if not complete_result:
            raise HTTPException(status_code=404, detail="会话不存在或已过期")
        
        # 生成报告
        report_path = table_sage_processor.generate_result_report(complete_result)
        
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
