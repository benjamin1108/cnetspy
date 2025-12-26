#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
中间件模块
"""

from .cors import setup_cors
from .error_handler import setup_error_handlers

__all__ = ['setup_cors', 'setup_error_handlers']
