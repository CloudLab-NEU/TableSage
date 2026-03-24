import os
import json
import asyncio
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from dotenv import load_dotenv

from mcp.client.sse import sse_client
from mcp.client.session import ClientSession
from mcp.types import Tool, TextContent
from fastapi import HTTPException

# 加载环境变量
load_dotenv()

logger = logging.getLogger(__name__)

# MCP 配置
MCP_CONFIG_PATH = os.getenv("MCP_CONFIG_PATH", "./mcp_client/mcp.json")

class MCPServerConfig(BaseModel):
    name: str
    url: str
    description: Optional[str] = ""

class MCPToolInfo(BaseModel):
    server: str
    name: str
    description: str
    input_schema: Dict[str, Any]
    enabled: bool = True

# 全局缓存
mcp_servers: Dict[str, MCPServerConfig] = {}
all_tools: List[MCPToolInfo] = []
disabled_tools: set = set()

DISABLED_TOOLS_PATH = os.path.join(os.path.dirname(MCP_CONFIG_PATH), "disabled_tools.json")

def load_disabled_tools() -> set:
    try:
        if os.path.exists(DISABLED_TOOLS_PATH):
            with open(DISABLED_TOOLS_PATH, 'r', encoding='utf-8') as f:
                return set(json.load(f))
    except Exception:
        pass
    return set()

def save_disabled_tools(disabled_set: set):
    with open(DISABLED_TOOLS_PATH, 'w', encoding='utf-8') as f:
        json.dump(list(disabled_set), f)

def load_mcp_config():
    """
    加载 MCP 配置
    """
    global mcp_servers, disabled_tools
    disabled_tools = load_disabled_tools()
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
    global disabled_tools
    return MCPToolInfo(
        server=server_name,
        name=tool.name,
        description=tool.description or "无描述",
        input_schema=tool.inputSchema or {"type": "object", "properties": {}},
        enabled=(tool.name not in disabled_tools)
    )

def toggle_tool(tool_name: str, enable: bool) -> bool:
    global disabled_tools, all_tools
    for t in all_tools:
        if t.name == tool_name:
            t.enabled = enable
            if enable and tool_name in disabled_tools:
                disabled_tools.remove(tool_name)
            elif not enable:
                disabled_tools.add(tool_name)
            save_disabled_tools(disabled_tools)
            return True
    return False

def get_enabled_tools() -> List[MCPToolInfo]:
    return [t for t in all_tools if t.enabled]

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
