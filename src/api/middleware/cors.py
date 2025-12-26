#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CORS 跨域配置
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ..config import settings


def setup_cors(app: FastAPI) -> None:
    """
    配置 CORS 中间件
    
    Args:
        app: FastAPI 应用实例
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
