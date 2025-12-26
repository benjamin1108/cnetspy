#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FastAPI 应用入口
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import os
from .config import settings
from .middleware import setup_cors, setup_error_handlers
from .routes import health_router
from .routes.updates import router as updates_router
from .routes.analysis import router as analysis_router
from .routes.stats import router as stats_router
from .routes.vendors import router as vendors_router


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="云计算竞争情报系统 - 多云更新聚合 + AI智能分析",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# 配置中间件
setup_cors(app)
setup_error_handlers(app)

# 注册路由
app.include_router(health_router)
app.include_router(updates_router)
app.include_router(analysis_router)
app.include_router(stats_router)
app.include_router(vendors_router)

# 静态文件服务（测试页面）
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    import logging
    logger = logging.getLogger("uvicorn")
    logger.info(f"🚀 {settings.app_name} v{settings.version} 启动成功")
    logger.info(f"📖 API文档: http://{settings.host}:{settings.port}/docs")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    import logging
    logger = logging.getLogger("uvicorn")
    logger.info(f"👋 {settings.app_name} 已关闭")
