#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MCP 工具统一注册模块

解决多个工具模块使用装饰器导致互相覆盖的问题
"""

from typing import List, Dict, Callable, Any
from mcp.server import Server
from mcp.types import Tool

from src.storage.database.sqlite_layer import UpdateDataLayer


# 全局工具注册表
_tools: List[Tool] = []
_handlers: Dict[str, Callable] = {}


def register_tool(tool: Tool, handler: Callable):
    """注册单个工具"""
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
