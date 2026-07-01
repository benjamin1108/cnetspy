#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
报告生成基类
"""

import logging
import os
import re
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)

UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


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

    def _normalize_update_id(self, update_id: Any) -> Optional[str]:
        """
        Normalize AI-returned update IDs back to IDs known by this report.

        Gemini occasionally appends nearby fields such as publish date and title
        to update_id. Reports should never emit those glued IDs because the
        public detail route only accepts the actual stored update_id.
        """
        candidate = str(update_id or "").strip()
        if not candidate:
            return None

        update_map = getattr(self, "_update_map", None) or {}
        if candidate in update_map:
            return candidate

        if update_map:
            prefix_matches = [
                known_id
                for known_id in update_map
                if known_id and len(str(known_id)) >= 8 and candidate.startswith(str(known_id))
            ]
            if prefix_matches:
                normalized = max(prefix_matches, key=len)
                logger.warning("归一化报告 update_id: %s -> %s", candidate, normalized)
                return normalized

            contains_matches = [
                known_id
                for known_id in update_map
                if known_id and len(str(known_id)) >= 8 and str(known_id) in candidate
            ]
            if len(contains_matches) == 1:
                normalized = contains_matches[0]
                logger.warning("归一化报告 update_id: %s -> %s", candidate, normalized)
                return normalized

            uuid_match = UUID_RE.search(candidate)
            if uuid_match and uuid_match.group(0) in update_map:
                normalized = uuid_match.group(0)
                logger.warning("归一化报告 update_id: %s -> %s", candidate, normalized)
                return normalized

            logger.warning("报告引用了未知 update_id，跳过链接: %s", candidate)
            return None

        uuid_match = UUID_RE.search(candidate)
        if uuid_match and uuid_match.group(0) != candidate:
            normalized = uuid_match.group(0)
            logger.warning("归一化报告 update_id: %s -> %s", candidate, normalized)
            return normalized

        return candidate

    def _sanitize_insight_update_ids(self, value: Any) -> Any:
        """Recursively normalize all update_id fields in an AI insight payload."""
        if isinstance(value, dict):
            for key, child in list(value.items()):
                if key == "update_id":
                    value[key] = self._normalize_update_id(child) or ""
                else:
                    value[key] = self._sanitize_insight_update_ids(child)
            return value

        if isinstance(value, list):
            for index, child in enumerate(value):
                value[index] = self._sanitize_insight_update_ids(child)
            return value

        return value
