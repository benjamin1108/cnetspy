#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
报告生成模块
提供周报、月报等报告生成能力
"""

from .base import BaseReport
from .weekly_report import WeeklyReport
from .monthly_report import MonthlyReport

__all__ = [
    'BaseReport',
    'WeeklyReport',
    'MonthlyReport',
]
