#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库存储模块

提供数据库访问层，包括：
- UpdateDataLayer: 统一业务数据层（门面类）
- 各个 Repository: 分领域的数据操作
"""

from src.storage.database.sqlite_layer import UpdateDataLayer
from src.storage.database.base import DatabaseManager, BaseRepository
from src.storage.database.updates_repository import UpdatesRepository
from src.storage.database.analysis_repository import AnalysisRepository
from src.storage.database.tasks_repository import TasksRepository
from src.storage.database.stats_repository import StatsRepository
from src.storage.database.quality_repository import QualityRepository
from src.storage.database.task_report_repository import TaskReport, TaskReportRepository

__all__ = [
    # 主入口
    'UpdateDataLayer',
    # 基础设施
    'DatabaseManager',
    'BaseRepository',
    # 各领域 Repository
    'UpdatesRepository',
    'AnalysisRepository',
    'TasksRepository',
    'StatsRepository',
    'QualityRepository',
    # 任务报告
    'TaskReport',
    'TaskReportRepository',
]
