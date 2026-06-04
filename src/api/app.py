#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FastAPI 应用入口
"""

import logging
import logging.config
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import os
import yaml
from src.utils.config import get_config
from .config import settings
from .middleware import setup_cors, setup_error_handlers
from .routes import health_router
from .routes.updates import router as updates_router
from .routes.analysis import router as analysis_router
from .routes.stats import router as stats_router
from .routes.vendors import router as vendors_router
from .routes.chat import router as chat_router
from .routes.reports import router as reports_router
from .routes.share import router as share_router

# 调度器（可选）
_scheduler = None


def _setup_logging() -> None:
    """加载统一日志配置，API 日志写入 logs/api.log。"""
    config_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "config", "logging.yaml")
    )
    if not os.path.exists(config_path):
        logging.basicConfig(level=logging.INFO)
        return

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        log_config = raw.get("logging", raw)
        logging.config.dictConfig(log_config)
    except Exception as exc:
        logging.basicConfig(level=logging.INFO)
        logging.getLogger(__name__).warning(
            f"日志配置加载失败，使用默认日志配置: {exc}"
        )


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


_setup_logging()


def _validate_ai_model_config() -> None:
    """启动时校验 AI 模型配置，避免运行期回退或空配置。"""
    config = get_config()
    if "ai_model" in config:
        ai_model = config.get("ai_model", {})
        default_model = (ai_model.get("default") or {}).get("model_name")
        chatbox_model = (ai_model.get("chatbox") or {}).get("model_name")
        default_key = "ai_model.default.model_name"
        chatbox_key = "ai_model.chatbox.model_name"
    else:
        default_model = (config.get("default") or {}).get("model_name")
        chatbox_model = (config.get("chatbox") or {}).get("model_name")
        default_key = "default.model_name"
        chatbox_key = "chatbox.model_name"

    missing = []
    if not default_model:
        missing.append(default_key)
    if not chatbox_model:
        missing.append(chatbox_key)

    if missing:
        raise RuntimeError(f"AI 模型配置缺失: {', '.join(missing)}")


_validate_ai_model_config()

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
app.include_router(reports_router)
app.include_router(share_router)

# 静态文件服务（测试页面）
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# 报告文件服务（HTML 报告）
reports_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'report'))
if os.path.exists(reports_dir):
    app.mount("/reports", StaticFiles(directory=reports_dir), name="reports")


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
        else:
            # 调度器.start()返回False可能是因为没有获取到调度器进程锁
            # 这是正常情况，不需要报错
            logger.info("📅 调度器未启动（可能因为调度器进程锁已被其他进程获取）")
            return None
        
    except Exception as e:
        logger.warning(f"调度器启动失败: {e}")
    
    return None
