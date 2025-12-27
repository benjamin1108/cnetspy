#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CloudNetSpy MCP Server 主入口

基于 MCP (Model Context Protocol) 协议，为 LLM 提供云厂商情报分析工具

支持两种运行模式：
- stdio: 本地进程通信（默认，Claude Desktop/Cursor 使用）
- sse: HTTP 长连接（远程调用）
"""

import sys
import asyncio
import logging
from mcp.server import Server
from mcp.server.stdio import stdio_server

from src.storage.database.sqlite_layer import UpdateDataLayer
from .tools import register_update_tools, register_stats_tools, register_analysis_tools, setup_server_handlers

logger = logging.getLogger(__name__)


def create_server() -> Server:
    """
    创建并配置 MCP Server
    
    Returns:
        配置完成的 MCP Server 实例
    """
    # 创建 MCP Server
    server = Server("cloudnetspy")
    
    # 初始化数据库连接
    db = UpdateDataLayer()
    
    # 注册工具（收集到全局注册表）
    register_update_tools(db)
    register_stats_tools(db)
    register_analysis_tools(db)
    
    # 设置 Server 处理器（一次性注册所有工具）
    setup_server_handlers(server)
    
    logger.info("CloudNetSpy MCP Server 初始化完成")
    
    return server


async def run_server(mode: str = "stdio", host: str = "0.0.0.0", port: int = 8089):
    """
    运行 MCP Server
    
    Args:
        mode: 运行模式 - "stdio" 或 "sse"
        host: SSE 模式监听地址
        port: SSE 模式监听端口
    """
    server = create_server()
    
    if mode == "sse":
        # SSE 模式：通过 HTTP 远程调用
        from mcp.server.sse import SseServerTransport
        from starlette.applications import Starlette
        from starlette.routing import Route, Mount
        from starlette.responses import Response
        import uvicorn
        
        sse = SseServerTransport("/messages/")
        
        async def handle_sse(request):
            async with sse.connect_sse(
                request.scope, request.receive, request._send
            ) as streams:
                await server.run(
                    streams[0], streams[1],
                    server.create_initialization_options()
                )
            # 返回空响应避免 NoneType 错误
            return Response()
        
        app = Starlette(
            routes=[
                Route("/sse", endpoint=handle_sse),
                Mount("/messages/", app=sse.handle_post_message),
            ]
        )
        
        logger.info(f"MCP Server (SSE) 启动于 http://{host}:{port}")
        logger.info(f"SSE 端点: http://{host}:{port}/sse")
        
        config = uvicorn.Config(app, host=host, port=port, log_level="info")
        server_instance = uvicorn.Server(config)
        await server_instance.serve()
    else:
        # stdio 模式：本地进程通信
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options()
            )


def main():
    """命令行入口"""
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 解析命令行参数
    mode = "stdio"
    host = "0.0.0.0"
    port = 8089
    
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--sse":
            mode = "sse"
        elif args[i] == "--host" and i + 1 < len(args):
            host = args[i + 1]
            i += 1
        elif args[i] == "--port" and i + 1 < len(args):
            port = int(args[i + 1])
            i += 1
        i += 1
    
    # 运行服务器
    asyncio.run(run_server(mode=mode, host=host, port=port))


if __name__ == "__main__":
    main()
