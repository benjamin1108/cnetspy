#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
配置加载模块

支持两种导入方式：
- from src.utils.config import get_config
- from src.utils.config_loader import get_config (兼容旧代码)
"""

from src.utils.config.config_loader import (
    get_config,
    load_yaml_file,
    load_config_directory,
    merge_configs,
    file_has_changed,
)

__all__ = [
    'get_config',
    'load_yaml_file',
    'load_config_directory',
    'merge_configs',
    'file_has_changed',
]
