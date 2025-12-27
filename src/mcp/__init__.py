#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CloudNetSpy MCP Server

提供 AI 对话分析能力，允许 LLM 调用内部 API 工具进行复杂分析
"""

# 延迟导入，避免循环引用警告
def create_server():
    from .server import create_server as _create_server
    return _create_server()

def run_server():
    from .server import run_server as _run_server
    return _run_server()

__all__ = ['create_server', 'run_server']
