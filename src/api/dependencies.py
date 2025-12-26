#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
依赖注入

提供数据库连接、分析器等依赖
"""

from typing import Generator
from src.storage.database.sqlite_layer import UpdateDataLayer
from .config import settings


def get_db() -> Generator[UpdateDataLayer, None, None]:
    """
    获取数据库连接（依赖注入）
    
    Yields:
        UpdateDataLayer 实例
    """
    db = UpdateDataLayer(db_path=settings.db_path)
    try:
        yield db
    finally:
        # SQLite 不需要显式关闭连接（使用上下文管理器）
        pass
