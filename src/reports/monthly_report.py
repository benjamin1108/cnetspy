#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
月报生成器
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from calendar import monthrange

from .base import BaseReport
from src.storage.database import DatabaseManager
from src.storage.database.reports_repository import ReportRepository
from src.utils.config import get_config
from src.analyzers.gemini_client import GeminiClient

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

# 提示词模板路径
PROMPT_DIR = os.path.join(os.path.dirname(__file__), '..', 'analyzers', 'prompts')


class MonthlyReport(BaseReport):
    """
    月报生成器
    
    汇总过去一个月的更新分析结果
    """
    
    def __init__(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ):
        # 默认统计上个月
        if start_date is None or end_date is None:
            today = datetime.now()
            # 上个月最后一天
            first_of_this_month = today.replace(day=1)
            end_date = first_of_this_month - timedelta(days=1)
            # 上个月第一天
            start_date = end_date.replace(day=1)
        
        super().__init__(start_date, end_date)
        self._db = DatabaseManager()
        self._report_repo = ReportRepository()
        
        # 保存生成的数据（用于存入数据库）
        self._ai_summary = ""
        self._vendor_stats = {}
        
        # 初始化 Gemini 客户端
        try:
            config = get_config()
            ai_config = config.get('ai_model', {})
            self._gemini = GeminiClient(ai_config)
        except Exception as e:
            logger.warning(f"Gemini 客户端初始化失败: {e}")
            self._gemini = None
    
    @property
    def report_type(self) -> str:
        return "monthly"
    
    @property
    def report_name(self) -> str:
        return "月报"
    
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
                ORDER BY vendor, publish_date DESC
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
    
    def _group_by_vendor(self, updates: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """按厂商分组"""
        grouped = {}
        for update in updates:
            vendor = update['vendor']
            if vendor not in grouped:
                grouped[vendor] = []
            grouped[vendor].append(update)
        return grouped
    
    def _generate_ai_summary(self, updates: List[Dict[str, Any]], grouped: Dict[str, List[Dict[str, Any]]]) -> str:
        """
        调用 AI 生成月度趋势摘要
        
        Args:
            updates: 所有更新列表
            grouped: 按厂商分组的更新
            
        Returns:
            AI 生成的趋势摘要
        """
        if not self._gemini:
            return ""
        
        try:
            # 加载提示词模板
            prompt_file = os.path.join(PROMPT_DIR, 'monthly_summary.prompt.txt')
            if not os.path.exists(prompt_file):
                logger.warning(f"提示词文件不存在: {prompt_file}")
                return ""
            
            with open(prompt_file, 'r', encoding='utf-8') as f:
                prompt_template = f.read()
            
            # 构建更新数据摘要
            updates_summary = []
            for vendor, vendor_updates in grouped.items():
                vendor_name = VENDOR_DISPLAY_NAMES.get(vendor, vendor.upper())
                updates_summary.append(f"### {vendor_name} ({len(vendor_updates)} 条)")
                for u in vendor_updates[:10]:  # 每个厂商最多10条
                    updates_summary.append(f"- {u['title_translated']}")
                updates_summary.append("")
            
            updates_data = '\n'.join(updates_summary)
            
            # 替换模板变量
            month_str = self.start_date.strftime('%Y年%m月')
            prompt = prompt_template.replace('{month_str}', month_str)
            prompt = prompt.replace('{updates_data}', updates_data)
            
            # 调用 AI
            logger.info("调用 Gemini 生成月度趋势摘要...")
            summary = self._gemini.generate_text(prompt)
            logger.info(f"AI 摘要生成成功，长度: {len(summary)} 字")
            return summary.strip()
            
        except Exception as e:
            logger.error(f"AI 摘要生成失败: {e}")
            return ""
    
    def generate(self) -> str:
        """
        生成月报内容
        
        Returns:
            Markdown 格式的月报内容
        """
        logger.info(f"生成月报: {self.start_date.strftime('%Y-%m-%d')} 至 {self.end_date.strftime('%Y-%m-%d')}")
        
        # 查询数据
        updates = self._query_analyzed_updates()
        
        if not updates:
            return self._generate_empty_report()
        
        # 按厂商分组
        grouped = self._group_by_vendor(updates)
        
        # 构建报告
        lines = []
        
        # 标题
        month_str = self.start_date.strftime('%Y年%m月')
        lines.append(f"# 【云技术月报】 {month_str} 竞争动态总览")
        lines.append("")
        lines.append(f"汇集本月主要云厂商的技术产品动态，共 {len(updates)} 条更新。")
        lines.append("")
        
        # AI 趋势摘要
        self._ai_summary = self._generate_ai_summary(updates, grouped)
        if self._ai_summary:
            lines.append("## 月度趋势分析")
            lines.append("")
            lines.append(self._ai_summary)
            lines.append("")
            lines.append("---")
            lines.append("")
        
        # 按厂商分组输出
        # 厂商排序：AWS -> Azure -> GCP -> 国内云
        vendor_order = ['aws', 'azure', 'gcp', 'huawei', 'tencentcloud', 'volcengine']
        
        for vendor in vendor_order:
            if vendor not in grouped:
                continue
            
            vendor_updates = grouped[vendor]
            vendor_name = VENDOR_DISPLAY_NAMES.get(vendor, vendor.upper())
            
            lines.append(f"## {vendor_name} ({len(vendor_updates)} 条)")
            lines.append("")
            
            for update in vendor_updates:
                title = update['title_translated']
                update_id = update['update_id']
                summary = update['content_summary']
                
                link = self._build_update_link(update_id)
                formatted_summary = self._format_summary(summary)
                
                lines.append(f"### [{title}]({link})")
                lines.append("")
                lines.append(formatted_summary)
                lines.append("")
                lines.append("")
        
        # 处理未在预定义列表中的厂商
        for vendor, vendor_updates in grouped.items():
            if vendor in vendor_order:
                continue
            
            vendor_name = VENDOR_DISPLAY_NAMES.get(vendor, vendor.upper())
            
            lines.append(f"## {vendor_name} ({len(vendor_updates)} 条)")
            lines.append("")
            
            for update in vendor_updates:
                title = update['title_translated']
                update_id = update['update_id']
                summary = update['content_summary']
                
                link = self._build_update_link(update_id)
                formatted_summary = self._format_summary(summary)
                
                lines.append(f"### [{title}]({link})")
                lines.append("")
                lines.append(formatted_summary)
                lines.append("")
                lines.append("")
        
        # 底部署名
        lines.append(f"由云竞争情报分析平台自动汇总。 [前往平台查看更多详情]({SITE_BASE_URL})")
        
        self._content = '\n'.join(lines)
        logger.info(f"月报生成完成，包含 {len(updates)} 条更新")
        
        # 保存到数据库
        self._save_to_database(updates, grouped)
        
        return self._content
    
    def _save_to_database(self, updates: List[Dict[str, Any]], grouped: Dict[str, List[Dict[str, Any]]]) -> None:
        """
        将报告数据保存到数据库
        
        Args:
            updates: 所有更新列表
            grouped: 按厂商分组的更新
        """
        try:
            # 构建厂商统计数据
            vendor_stats = {}
            for vendor, vendor_updates in grouped.items():
                vendor_stats[vendor] = {
                    'count': len(vendor_updates),
                    'updates': [{
                        'update_id': u['update_id'],
                        'title': u['title_translated'],
                        'publish_date': u['publish_date']
                    } for u in vendor_updates]
                }
            
            # 保存报告
            report_id = self._report_repo.save_report(
                report_type='monthly',
                year=self.start_date.year,
                month=self.start_date.month,
                week=None,
                date_from=self.start_date.strftime('%Y-%m-%d'),
                date_to=self.end_date.strftime('%Y-%m-%d'),
                ai_summary=self._ai_summary,
                vendor_stats=vendor_stats,
                total_count=len(updates)
            )
            logger.info(f"报告已保存到数据库，ID: {report_id}")
            
        except Exception as e:
            logger.error(f"保存报告到数据库失败: {e}")
    
    def _generate_empty_report(self) -> str:
        """生成空报告"""
        month_str = self.start_date.strftime('%Y年%m月')
        content = f"""# 【云技术月报】 {month_str} 竞争动态总览


汇集本月主要云厂商的技术产品动态。


> 本月暂无新的云产品动态更新。


由云竞争情报分析平台自动汇总。 [前往平台查看更多详情]({SITE_BASE_URL})
"""
        self._content = content
        return content
