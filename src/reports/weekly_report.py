#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
周报生成器
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from .base import BaseReport
from src.storage.database import DatabaseManager

logger = logging.getLogger(__name__)

# 厂商显示名称
VENDOR_DISPLAY_NAMES = {
    'aws': 'AWS',
    'azure': 'Azure',
    'gcp': 'GCP',
    'huawei': '华为云',
    'tencentcloud': '腾讯云',
    'volcengine': '火山引擎'
}

# 站点配置
SITE_BASE_URL = "https://cnetspy.site/next"


class WeeklyReport(BaseReport):
    """
    周报生成器
    
    汇总过去一周的更新分析结果
    """
    
    def __init__(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ):
        # 默认统计过去7天
        if end_date is None:
            end_date = datetime.now()
        if start_date is None:
            start_date = end_date - timedelta(days=7)
        
        super().__init__(start_date, end_date)
        self._db = DatabaseManager()
    
    @property
    def report_type(self) -> str:
        return "weekly"
    
    @property
    def report_name(self) -> str:
        return "周报"
    
    def _query_analyzed_updates(self) -> List[Dict[str, Any]]:
        """
        查询时间范围内已分析的更新
        
        Returns:
            已分析更新列表
        """
        date_from = self.start_date.strftime('%Y-%m-%d')
        date_to = self.end_date.strftime('%Y-%m-%d')
        
        with self._db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    update_id, vendor, source_channel, 
                    title_translated, content_summary, publish_date
                FROM updates
                WHERE publish_date >= ? AND publish_date <= ?
                    AND title_translated IS NOT NULL 
                    AND title_translated != ''
                    AND LENGTH(TRIM(title_translated)) >= 2
                    AND content_summary IS NOT NULL
                    AND content_summary != ''
                ORDER BY publish_date DESC, vendor
            ''', (date_from, date_to))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def _build_update_link(self, update_id: str) -> str:
        """构建更新详情链接"""
        return f"{SITE_BASE_URL}/updates/{update_id}"
    
    def _format_summary(self, content_summary: str) -> str:
        """
        格式化摘要内容，提取核心段落
        
        Args:
            content_summary: 原始摘要（Markdown格式）
            
        Returns:
            精简后的摘要文本
        """
        if not content_summary:
            return ""
        
        # 提取正文内容，移除标题行和空行
        lines = content_summary.strip().split('\n')
        content_lines = []
        
        for line in lines:
            line = line.strip()
            # 跳过标题行和空行
            if line.startswith('#') or not line:
                continue
            # 跳过特定区块标题
            if line.startswith('## ') or line.startswith('**相关'):
                continue
            content_lines.append(line)
        
        # 合并为一段文字
        text = ' '.join(content_lines)
        
        # 限制长度（约200字）
        if len(text) > 250:
            text = text[:247] + '...'
        
        return text
    
    def generate(self) -> str:
        """
        生成周报内容
        
        Returns:
            Markdown 格式的周报内容
        """
        logger.info(f"生成周报: {self.start_date.strftime('%Y-%m-%d')} 至 {self.end_date.strftime('%Y-%m-%d')}")
        
        # 查询数据
        updates = self._query_analyzed_updates()
        
        if not updates:
            return self._generate_empty_report()
        
        # 构建报告
        lines = []
        
        # 标题
        date_range = f"{self.start_date.strftime('%Y年%m月%d日')} - {self.end_date.strftime('%Y年%m月%d日')}"
        lines.append(f"# 【云技术周报】 {date_range} 竞争动态速览")
        lines.append("")
        lines.append("")
        lines.append("汇集本周主要云厂商的技术产品动态，助您快速掌握核心变化。")
        lines.append("")
        lines.append("")
        
        # 更新条目
        for update in updates:
            vendor = update['vendor']
            vendor_name = VENDOR_DISPLAY_NAMES.get(vendor, vendor.upper())
            title = update['title_translated']
            update_id = update['update_id']
            summary = update['content_summary']
            
            link = self._build_update_link(update_id)
            formatted_summary = self._format_summary(summary)
            
            # 格式：### [[厂商] 标题](链接)
            lines.append(f"### [[{vendor_name}] {title}]({link})")
            lines.append("")
            lines.append(formatted_summary)
            lines.append("")
            lines.append("")
        
        # 底部署名
        lines.append(f"由云竞争情报分析平台自动汇总。 [前往平台查看更多详情]({SITE_BASE_URL})")
        
        self._content = '\n'.join(lines)
        logger.info(f"周报生成完成，包含 {len(updates)} 条更新")
        return self._content
    
    def _generate_empty_report(self) -> str:
        """生成空报告"""
        date_range = f"{self.start_date.strftime('%Y年%m月%d日')} - {self.end_date.strftime('%Y年%m月%d日')}"
        content = f"""# 【云技术周报】 {date_range} 竞争动态速览


汇集本周主要云厂商的技术产品动态，助您快速掌握核心变化。


> 本周暂无新的云产品动态更新。


由云竞争情报分析平台自动汇总。 [前往平台查看更多详情]({SITE_BASE_URL})
"""
        self._content = content
        return content
