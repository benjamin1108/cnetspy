#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
日志模块

支持两种导入方式：
- from src.utils.logging import ColoredLogger
- from src.utils.colored_logger import ColoredLogger (兼容旧代码)
"""

from src.utils.logging.colored_logger import (
    Colors,
    ColoredFormatter,
    setup_colored_logging,
)

__all__ = [
    'Colors',
    'ColoredFormatter',
    'setup_colored_logging',
]
