import os
import json
import logging
from typing import Dict, Any, List
from openai import AsyncOpenAI
from utils.utils import TableUtils
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE")
# You can define a specific model for visualization, defaulting to standard LLM
VISUALIZATION_LLM_MODEL = os.getenv("VISUALIZATION_LLM_MODEL", os.getenv("LLM_MODEL", "gpt-4o"))

class VisualizationAgent:
    """
    VisualizationAgent 负责接收包含数据的结果和用户的绘图指令，
    自主调用后端的 MCP 工具进行图表生成。
    """
    def __init__(self, mcp_tools: List[Any], tool_caller: Any):
        self._client = AsyncOpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_API_BASE or None,
        )
        self.model = VISUALIZATION_LLM_MODEL
        self.mcp_tools = mcp_tools
        self.tool_caller = tool_caller # the call_tool function from client.py
        
        # Create a robust mapping for tool lookup
        self.tool_map = {f"{getattr(t, 'server')}_{getattr(t, 'name')}": (getattr(t, 'server'), getattr(t, 'name')) for t in mcp_tools}

    async def generate_chart(self, user_table: Dict[str, Any], cached_data: Dict[str, Any], instruction: str) -> List[Dict[str, Any]]:
        """
        调用 LLM 结合 MCP Tool 绘制图表
        """
        # 1. Reload tools to respect dynamic enabled/disabled toggles
        try:
            from mcp_client.connection import get_enabled_tools, load_mcp_config, load_all_tools
            if not self.mcp_tools:
                load_mcp_config()
                await load_all_tools()
            self.mcp_tools = get_enabled_tools()
            # Update map
            self.tool_map = {f"{getattr(t, 'server')}_{getattr(t, 'name')}": (getattr(t, 'server'), getattr(t, 'name')) for t in self.mcp_tools}
        except Exception as e:
            logger.error(f"Failed to load MCP tools: {e}")

        messages = [
            {"role": "system", "content": "You are a specialized Data Visualization Agent. Your ONLY way to generate charts is by calling the provided MCP tools. DO NOT provide Python code blocks or descriptions of how to draw; instead, directly call the appropriate tool with the data derived from the table and answer context. If you cannot draw a chart, explain why, but NEVER output raw python code unless explicitly asked to provide the script itself."}
        ]
        
        # Format the full table for context visibility
        formatted_table = TableUtils.table2format(user_table)
        context_prompt = f"### Table Content:\n{formatted_table}\n\n### Answer Data Context: {cached_data.get('answer', '')}\n### Instruction: {instruction}"
        messages.append({"role": "user", "content": context_prompt})

        openai_tools = []
        for t in self.mcp_tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": f"{t.server}_{t.name}",
                    "description": f"[{t.server}] {t.description}",
                    "parameters": t.input_schema
                }
            })
        
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1
        }
        if openai_tools:
            kwargs["tools"] = openai_tools
            kwargs["tool_choice"] = "auto"
            
        try:
            response = await self._client.chat.completions.create(**kwargs)
            message = response.choices[0].message
            
            toolCalls = []
            if hasattr(message, 'tool_calls') and message.tool_calls:
                for tool_call in message.tool_calls:
                    function_name = tool_call.function.name
                    raw_args = tool_call.function.arguments
                    arguments = {}
                    try:
                        import ast
                        arguments = json.loads(raw_args)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Tool arguments JSON decode failed, attempting literal_eval. Error: {e}")
                        try:
                            # ast.literal_eval can handle Python-style dicts with single quotes
                            arguments = ast.literal_eval(raw_args)
                        except Exception as eval_e:
                            logger.error(f"Failed to parse tool arguments with literal_eval: {eval_e}")
                            try:
                                # Final desperate attempt: replace single quotes with double quotes
                                repaired = raw_args.replace("'", '"')
                                arguments = json.loads(repaired)
                            except:
                                toolCalls.append({
                                    "name": function_name, 
                                    "error": f"Failed to parse tool arguments: {e}", 
                                    "tool_call_id": tool_call.id
                                })
                                continue
                    
                    # Robust lookup and validation
                    if function_name in self.tool_map:
                        server_name, tool_name = self.tool_map[function_name]
                    else:
                        # Attempt to find by just tool_name if prefix is missing
                        matches = [info for fullName, info in self.tool_map.items() if fullName.endswith(f"_{function_name}")]
                        if matches:
                            server_name, tool_name = matches[0]
                        else:
                            toolCalls.append({
                                "name": function_name, 
                                "error": f"Tool '{function_name}' not found or not available.", 
                                "tool_call_id": tool_call.id
                            })
                            continue

                    try:
                        fun_call_result = await self.tool_caller(server_name, tool_name, arguments)
                        
                        # Extract content using the logic similar to connection.extract_text_content
                        # Since tool_caller returns the raw MCP result object
                        content_str = ""
                        if hasattr(fun_call_result, 'content') and fun_call_result.content: # type: ignore
                            from mcp_client.connection import extract_text_content
                            content_str = extract_text_content(fun_call_result.content) # type: ignore
                        else:
                            content_str = str(fun_call_result)
                        
                        # 检测是否为本地文件路径，如果是则注册并转换为URL
                        if content_str and os.path.exists(content_str) and os.path.isfile(content_str):
                            try:
                                from backend_api.file_service_api import file_service
                                file_id = file_service.register_file(content_str)
                                content_str = f"/api/files/download/{file_id}"
                                logger.info(f"Registered file {file_id} for path {content_str}")
                            except Exception as fe:
                                logger.error(f"Failed to register file: {fe}")
                            
                        toolCalls.append({
                            "name": tool_name,
                            "server": server_name,
                            "result": "MCP Tool 调用成功",
                            "content": content_str,
                            "arguments": arguments,
                            "tool_call_id": tool_call.id
                        })
                    except Exception as e:
                        toolCalls.append({"name": function_name, "error": str(e), "tool_call_id": tool_call.id})
                return toolCalls
            else:
                return [{"name": "none", "message": "模型没有调用任何 MCP 工具", "content": message.content}]

        except Exception as e:
            logger.error(f"Visualization Agent 发生错误: {str(e)}")
            raise e
