#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MCP 工具统一注册模块

解决多个工具模块使用装饰器导致互相覆盖的问题
"""

from typing import List, Dict, Callable, Any, Optional
from mcp.server import Server
from mcp.types import Tool

from src.storage.database.sqlite_layer import UpdateDataLayer
from src.utils.config import get_config


# 全局工具注册表
_tools: List[Tool] = []
_handlers: Dict[str, Callable] = {}
_tools_config: Optional[Dict] = None


def get_tool_config(tool_name: str) -> Dict:
    """
    获取工具配置（描述和参数说明）
    
    Args:
        tool_name: 工具名称
    
    Returns:
        工具配置字典，包含 description 和 params
    """
    global _tools_config
    
    if _tools_config is None:
        try:
            _tools_config = get_config("mcp_tools")
        except Exception:
            _tools_config = {}
    
    return _tools_config.get(tool_name, {})


def get_tool_description(tool_name: str, default: str = "") -> str:
    """
    获取工具描述
    
    Args:
        tool_name: 工具名称
        default: 默认描述（配置不存在时使用）
    
    Returns:
        工具描述字符串
    """
    config = get_tool_config(tool_name)
    return config.get("description", default).strip()


def get_param_description(tool_name: str, param_name: str, default: str = "") -> str:
    """
    获取参数描述
    
    Args:
        tool_name: 工具名称
        param_name: 参数名称
        default: 默认描述
    
    Returns:
        参数描述字符串
    """
    config = get_tool_config(tool_name)
    params = config.get("params", {})
    return params.get(param_name, default)


def register_tool(tool: Tool, handler: Callable):
    """
    注册单个工具
    
    如果工具已存在（按名称判断），则跳过注册避免重复
    """
    # 检查是否已注册（避免重复）
    if tool.name in _handlers:
        return
    
    _tools.append(tool)
    _handlers[tool.name] = handler


def get_all_tools() -> List[Tool]:
    """获取所有已注册工具"""
    return _tools


def get_handler(name: str) -> Callable:
    """获取工具处理函数"""
    return _handlers.get(name)


def setup_server_handlers(server: Server):
    """
    设置 Server 的工具处理器
    在所有工具注册完成后调用一次
    """
    
    @server.list_tools()
    async def list_all_tools():
        return get_all_tools()
    
    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        handler = get_handler(name)
        if handler:
            return await handler(arguments)
        return None
