#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
报告生成基类
"""

import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class BaseReport(ABC):
    """
    报告生成抽象基类
    
    子类需实现 generate() 方法
    """
    
    # 报告保存目录
    REPORTS_DIR = "data/reports"
    
    def __init__(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ):
        """
        初始化报告
        
        Args:
            start_date: 报告起始日期
            end_date: 报告结束日期
        """
        self.start_date = start_date
        self.end_date = end_date or datetime.now()
        self._content: Optional[str] = None
    
    @property
    @abstractmethod
    def report_type(self) -> str:
        """报告类型标识（如 weekly, monthly）"""
        pass
    
    @property
    @abstractmethod
    def report_name(self) -> str:
        """报告名称（如 周报, 月报）"""
        pass
    
    @abstractmethod
    def generate(self) -> str:
        """
        生成报告内容
        
        Returns:
            Markdown 格式的报告内容
        """
        pass
    
    def save(self, filepath: Optional[str] = None) -> str:
        """
        保存报告到文件
        
        Args:
            filepath: 自定义文件路径，默认自动生成
            
        Returns:
            保存的文件路径
        """
        if self._content is None:
            self._content = self.generate()
        
        if filepath is None:
            filepath = self._generate_filepath()
        
        # 确保目录存在
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(self._content)
        
        logger.info(f"报告已保存: {filepath}")
        return filepath
    
    def _generate_filepath(self) -> str:
        """生成默认文件路径"""
        date_str = self.end_date.strftime('%Y%m%d')
        filename = f"{self.report_type}_{date_str}.md"
        return os.path.join(self.REPORTS_DIR, self.report_type, filename)
    
    def get_content(self) -> str:
        """获取报告内容"""
        if self._content is None:
            self._content = self.generate()
        return self._content
