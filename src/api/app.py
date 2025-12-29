#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FastAPI 应用入口
"""

import logging
from contextlib import asynccontextmanager
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
from .routes.chat import router as chat_router

# 调度器（可选）
_scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global _scheduler
    
    # Startup
    logger = logging.getLogger("uvicorn")
    logger.info(f"🚀 {settings.app_name} v{settings.version} 启动成功")
    logger.info(f"📖 API文档: http://{settings.host}:{settings.port}/docs")
    
    # 启动调度器
    _scheduler = _start_scheduler(logger)
    
    yield
    
    # Shutdown
    if _scheduler:
        _scheduler.stop()
    logger.info(f"👋 {settings.app_name} 已关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="云计算竞争情报系统 - 多云更新聚合 + AI智能分析",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
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
app.include_router(chat_router)

# 静态文件服务（测试页面）
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


def _start_scheduler(logger):
    """启动调度器（如果配置启用）"""
    try:
        from src.utils.config import get_config
        from src.scheduler import Scheduler
        
        config = get_config()
        scheduler_config = config.get('scheduler', {})
        
        if not scheduler_config.get('enabled', False):
            logger.info("📅 调度器未启用")
            return None
        
        scheduler = Scheduler(scheduler_config)
        if scheduler.start():
            logger.info("📅 调度器已启动")
            return scheduler
        
    except Exception as e:
        logger.warning(f"调度器启动失败: {e}")
    
    return None
