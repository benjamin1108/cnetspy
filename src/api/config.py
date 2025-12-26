#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API 配置管理
"""

import os
from typing import List
from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class APISettings(BaseSettings):
    """API 配置"""
    
    model_config = ConfigDict(
        env_file=".env",
        env_prefix="API_",
        extra="ignore"  # 忽略额外的环境变量
    )
    
    # 应用信息
    app_name: str = "CloudNetSpy API"
    version: str = "2.0.0"
    debug: bool = False
    
    # 数据库
    db_path: str = "data/sqlite/updates.db"
    
    # CORS配置
    cors_origins: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    
    # 分析文件保存配置
    save_analysis_files: bool = True  # 保存分析结果到文件
    analysis_output_dir: str = "data/analyzed"
    
    # 服务器配置
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4


settings = APISettings()
