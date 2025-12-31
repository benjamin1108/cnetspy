#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
月报生成器

架构分层：
- 数据层：程序统计（总数、厂商分布、热点领域）
- 认知层：AI 生成 JSON 格式的洞察摘要
- 表现层：程序拼接 HTML 报告
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from html import escape

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

# 更新类型显示名称
UPDATE_TYPE_LABELS = {
    'new_product': '新产品',
    'new_feature': '新功能',
    'enhancement': '功能增强',
    'pricing': '价格调整',
    'deprecation': '功能下线',
    'region': '区域扩展',
    'security': '安全更新',
    'fix': '问题修复',
    'compliance': '合规认证'
}

# 站点配置
SITE_BASE_URL = "https://cnetspy.site/next"

# 提示词和模板路径
PROMPT_DIR = os.path.join(os.path.dirname(__file__), '..', 'analyzers', 'prompts')
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')


class MonthlyReport(BaseReport):
    """
    月报生成器
    
    生成流程：
    1. 数据层：查询统计数据
    2. AI 层：生成 JSON 格式的洞察
    3. 渲染层：拼接 HTML 报告
    4. 存储：保存到文件 + 入库
    """
    
    def __init__(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ):
        # 默认统计当月截止今天
        if start_date is None or end_date is None:
            today = datetime.now()
            start_date = today.replace(day=1)  # 当月第一天
            end_date = today  # 截止今天
        
        super().__init__(start_date, end_date)
        self._db = DatabaseManager()
        self._report_repo = ReportRepository()
        
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
    
    # ==================== 数据层 ====================
    
    def _get_stats(self) -> Dict[str, Any]:
        """
        统计数据（程序计算，不依赖 AI）
        
        Returns:
            包含 total_count, vendor_stats, category_stats, top_vendor 的字典
        """
        date_from = self.start_date.strftime('%Y-%m-%d')
        date_to = self.end_date.strftime('%Y-%m-%d')
        
        with self._db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 查询所有已分析的更新
            cursor.execute('''
                SELECT 
                    update_id, vendor, source_channel, update_type,
                    title, title_translated, content_summary, 
                    publish_date, product_subcategory
                FROM updates
                WHERE publish_date >= ? AND publish_date <= ?
                    AND title_translated IS NOT NULL 
                    AND title_translated != ''
                    AND LENGTH(TRIM(title_translated)) >= 2
                ORDER BY vendor, publish_date DESC
            ''', (date_from, date_to))
            
            updates = [dict(row) for row in cursor.fetchall()]
        
        # 厂商统计
        vendor_stats = {}
        for u in updates:
            vendor = u['vendor']
            if vendor not in vendor_stats:
                vendor_stats[vendor] = {'count': 0, 'updates': []}
            vendor_stats[vendor]['count'] += 1
            vendor_stats[vendor]['updates'].append(u)
        
        # 类别统计
        category_stats = {}
        for u in updates:
            cat = u.get('product_subcategory') or '其他'
            category_stats[cat] = category_stats.get(cat, 0) + 1
        
        # 最活跃厂商
        top_vendor = None
        top_vendor_count = 0
        for vendor, stats in vendor_stats.items():
            if stats['count'] > top_vendor_count:
                top_vendor = vendor
                top_vendor_count = stats['count']
        
        return {
            'total_count': len(updates),
            'vendor_stats': vendor_stats,
            'category_stats': category_stats,
            'top_vendor': top_vendor,
            'top_vendor_count': top_vendor_count,
            'updates': updates
        }
    
    def _get_updates_for_ai(self, updates: List[Dict]) -> List[Dict]:
        """
        获取用于 AI 分析的更新列表（精简字段，全量）
        """
        result = []
        for u in updates:
            result.append({
                'vendor': u['vendor'],
                'title': u.get('title_translated') or u.get('title') or '',
                'type': u.get('update_type') or '',
                'category': u.get('product_subcategory') or ''
            })
        return result
    
    # ==================== AI 认知层 ====================
    
    def _generate_ai_insight(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用 AI 生成 JSON 格式的洞察摘要
        
        Returns:
            {
                "insight_title": "...",
                "insight_summary": "...",
                "top_trends": [...]
            }
        """
        # 默认返回值
        default_insight = {
            'insight_title': '本月云产品动态',
            'insight_summary': f"本月监测到 {stats['total_count']} 条更新，涉及 {len(stats['vendor_stats'])} 个厂商。",
            'top_trends': []
        }
        
        if not self._gemini:
            return default_insight
        
        # 更新数量太少，不调用 AI
        if stats['total_count'] < 5:
            return default_insight
        
        try:
            # 加载提示词模板
            prompt_file = os.path.join(PROMPT_DIR, 'monthly_insight.prompt.txt')
            if not os.path.exists(prompt_file):
                logger.warning(f"提示词文件不存在: {prompt_file}")
                return default_insight
            
            with open(prompt_file, 'r', encoding='utf-8') as f:
                prompt_template = f.read()
            
            # 构建输入数据
            month_str = self.start_date.strftime('%Y年%m月')
            vendor_stats_str = ', '.join([
                f"{VENDOR_DISPLAY_NAMES.get(v, v)}({s['count']}条)"
                for v, s in sorted(stats['vendor_stats'].items(), key=lambda x: x[1]['count'], reverse=True)
            ])
            
            # 类别 Top 5
            category_sorted = sorted(stats['category_stats'].items(), key=lambda x: x[1], reverse=True)[:5]
            category_stats_str = ', '.join([f"{cat}({cnt}条)" for cat, cnt in category_sorted])
            
            updates_for_ai = self._get_updates_for_ai(stats['updates'])
            updates_json = json.dumps(updates_for_ai, ensure_ascii=False, indent=2)
            
            # 替换模板变量
            prompt = prompt_template.replace('{month_str}', month_str)
            prompt = prompt.replace('{total_count}', str(stats['total_count']))
            prompt = prompt.replace('{vendor_stats}', vendor_stats_str)
            prompt = prompt.replace('{category_stats}', category_stats_str)
            prompt = prompt.replace('{updates_json}', updates_json)
            
            # 调用 AI
            logger.info("调用 Gemini 生成月度洞察 JSON...")
            response = self._gemini.generate_text(prompt)
            
            # DEBUG: 打印原始响应
            logger.debug(f"AI 原始响应 (前500字符): {response[:500]}")
            logger.debug(f"AI 响应长度: {len(response)} 字符")
            
            # 解析 JSON
            # 尝试清理可能的 Markdown 代码块
            response = response.strip()
            if response.startswith('```json'):
                response = response[7:]
            if response.startswith('```'):
                response = response[3:]
            if response.endswith('```'):
                response = response[:-3]
            response = response.strip()
            
            logger.debug(f"清理后的响应 (前300字符): {response[:300]}")
            
            insight = json.loads(response)
            logger.info(f"AI 洞察生成成功: {insight.get('insight_title', '')}")
            logger.debug(f"解析得到的 insight: {insight}")
            
            # 确保字段存在
            return {
                'insight_title': insight.get('insight_title', default_insight['insight_title']),
                'insight_summary': insight.get('insight_summary', default_insight['insight_summary']),
                'top_trends': insight.get('top_trends', [])
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"AI 返回的 JSON 解析失败: {e}")
            logger.error(f"无法解析的响应内容: {response[:1000]}")
            return default_insight
        except Exception as e:
            logger.error(f"AI 洞察生成失败: {e}")
            logger.error(f"异常时的响应: {response[:500] if 'response' in locals() else 'N/A'}")
            return default_insight
    
    # ==================== 渲染层 ====================
    
    def _render_card_html(self, update: Dict, is_hero: bool = False) -> str:
        """
        渲染单个更新卡片的 HTML
        
        Args:
            update: 更新数据
            is_hero: 是否为 Hero Card（占 2 列）
        """
        vendor = update['vendor']
        vendor_slug = vendor.lower()
        vendor_display = VENDOR_DISPLAY_NAMES.get(vendor, vendor.upper())
        
        update_id = update['update_id']
        title = escape(update.get('title_translated') or update.get('title') or '')
        summary = escape(update.get('content_summary') or '')[:200]
        publish_date = update.get('publish_date', '')[:10]
        update_type = update.get('update_type') or ''
        type_label = UPDATE_TYPE_LABELS.get(update_type, update_type or '其他')
        category = escape(update.get('product_subcategory') or '')
        
        link = f"{SITE_BASE_URL}/updates/{update_id}"
        
        # 格式化日期为 MM-DD
        date_display = publish_date[5:] if len(publish_date) >= 10 else publish_date
        
        if is_hero:
            return f'''
<div class="glass-card update-card rounded-2xl p-6 md:col-span-2 relative overflow-hidden group" data-vendor="{vendor}">
    <div class="flex justify-between items-start mb-4">
        <span class="badge badge-{vendor_slug}">{vendor_display}</span>
        <span class="text-xs font-mono text-muted">{date_display}</span>
    </div>
    <div>
        <h3 class="text-lg font-bold mb-2 leading-tight text-primary">
            <a href="{link}" target="_blank" class="card-link transition-colors">
                {title}
            </a>
        </h3>
        <p class="text-sm line-clamp-2 text-secondary">
            {summary}
        </p>
    </div>
    <div class="mt-4 flex gap-2">
        <span class="type-tag type-{update_type if update_type else 'default'}">
            {type_label}
        </span>
    </div>
</div>
'''
        else:
            return f'''
<div class="glass-card update-card rounded-2xl p-5 md:col-span-1 group" data-vendor="{vendor}">
    <div class="flex justify-between items-start mb-3">
        <span class="badge badge-{vendor_slug}">{vendor_display}</span>
        <span class="text-xs font-mono text-muted">{date_display}</span>
    </div>
    <div class="flex-1 flex flex-col">
        <h3 class="text-sm font-semibold mb-2 leading-snug text-primary">
            <a href="{link}" target="_blank" class="card-link transition-colors">
                {title}
            </a>
        </h3>
        <p class="text-xs line-clamp-3 mb-2 text-muted">
            {summary}
        </p>
    </div>
    <div class="mt-auto pt-3 border-t border-color flex justify-between items-center">
        <span class="text-xs px-2 py-0.5 rounded glass-card text-muted">
            {category}
        </span>
        <a href="{link}" target="_blank" class="text-muted hover:text-primary transition">
            <i class="fa-solid fa-arrow-right text-xs"></i>
        </a>
    </div>
</div>
'''
    
    def _render_trend_html(self, trend: Dict) -> str:
        """渲染单个趋势项的 HTML（卡片式布局）"""
        emoji = trend.get('emoji', '📊')
        title = escape(trend.get('title', ''))
        desc = escape(trend.get('desc', ''))
        
        return f'''
<div class="flex gap-3 p-3 rounded-lg glass-card">
    <span class="text-2xl">{emoji}</span>
    <div>
        <h4 class="font-medium text-sm mb-1 text-primary">{title}</h4>
        <p class="text-xs leading-relaxed text-secondary">{desc}</p>
    </div>
</div>
'''
    
    def _render_category_bar_html(self, category: str, count: int, max_count: int) -> str:
        """渲染热点领域进度条"""
        percent = (count / max_count * 100) if max_count > 0 else 0
        category_display = escape(category)
        
        return f'''
<div class="flex items-center gap-3">
    <div class="w-24 text-xs text-right truncate text-secondary">{category_display}</div>
    <div class="flex-1 progress-bar">
        <div class="progress-fill" style="width: {percent:.0f}%; background: hsl(var(--primary));"></div>
    </div>
    <div class="w-8 text-xs text-primary">{count}</div>
</div>
'''
    
    def _render_report_html(self, stats: Dict, insight: Dict) -> str:
        """
        组装完整的 HTML 报告
        """
        # 加载模板
        template_file = os.path.join(TEMPLATE_DIR, 'monthly_report.html')
        with open(template_file, 'r', encoding='utf-8') as f:
            template = f.read()
        
        # 标题：如果截止日不是月末，标注截止日期
        month_str = self.start_date.strftime('%Y年%m月')
        if self.end_date.day < 28:  # 不是月末
            month_str += f"（截止{self.end_date.strftime('%m月%d日')}）"
        
        date_range = f"{self.start_date.strftime('%Y-%m-%d')} 至 {self.end_date.strftime('%Y-%m-%d')}"
        
        # 最活跃厂商
        top_vendor_name = VENDOR_DISPLAY_NAMES.get(stats['top_vendor'], stats['top_vendor'] or '-')
        top_vendor_count = stats['top_vendor_count']
        
        # 趋势 HTML
        top_trends_html = ''
        if insight.get('top_trends'):
            for trend in insight['top_trends']:
                top_trends_html += self._render_trend_html(trend)
        
        # 热点领域 Top 3
        category_sorted = sorted(stats['category_stats'].items(), key=lambda x: x[1], reverse=True)[:3]
        max_cat_count = category_sorted[0][1] if category_sorted else 1
        category_bars_html = ''
        for cat, cnt in category_sorted:
            category_bars_html += self._render_category_bar_html(cat, cnt, max_cat_count)
        
        # 更新卡片 HTML
        details_html = ''
        all_updates = stats['updates']
        
        # Hero 类型：new_product, pricing, compliance
        hero_types = {'new_product', 'pricing', 'compliance'}
        
        for i, u in enumerate(all_updates):
            is_hero = u.get('update_type') in hero_types and i < 10  # 前 10 条中的重要类型用 Hero
            details_html += self._render_card_html(u, is_hero=is_hero)
        
        # 厂商筛选按钮 HTML
        vendor_filter_buttons = ''
        vendor_order = ['aws', 'azure', 'gcp', 'huawei', 'tencentcloud', 'volcengine']
        for vendor in vendor_order:
            if vendor in stats['vendor_stats']:
                vendor_display = VENDOR_DISPLAY_NAMES.get(vendor, vendor.upper())
                vendor_filter_buttons += f'<button class="vendor-filter-btn" data-vendor="{vendor}" onclick="filterByVendor(\'{vendor}\')">{vendor_display}</button>\n'
        
        # 替换模板变量
        html = template
        html = html.replace('{{report_month}}', month_str)
        html = html.replace('{{date_range}}', date_range)
        html = html.replace('{{total_count}}', str(stats['total_count']))
        html = html.replace('{{top_vendor_name}}', top_vendor_name)
        html = html.replace('{{top_vendor_count}}', str(top_vendor_count))
        html = html.replace('{{insight_title}}', escape(insight.get('insight_title', '')))
        html = html.replace('{{insight_summary}}', escape(insight.get('insight_summary', '')))
        html = html.replace('{{top_trends_html}}', top_trends_html)
        html = html.replace('{{category_bars_html}}', category_bars_html)
        html = html.replace('{{vendor_filter_buttons}}', vendor_filter_buttons)
        html = html.replace('{{details_html_content}}', details_html)
        
        # 处理条件渲染
        if top_trends_html:
            html = html.replace('{{#if top_trends}}', '').replace('{{/if}}', '')
        else:
            # 移除空的趋势区块
            import re
            html = re.sub(r'\{\{#if top_trends\}\}.*?\{\{/if\}\}', '', html, flags=re.DOTALL)
        
        return html
    
    # ==================== 主流程 ====================
    
    def generate(self) -> str:
        """
        生成月报
        
        Returns:
            HTML 格式的月报内容
        """
        logger.info(f"生成月报: {self.start_date.strftime('%Y-%m-%d')} 至 {self.end_date.strftime('%Y-%m-%d')}")
        
        # 1. 数据层：获取统计数据
        stats = self._get_stats()
        
        if stats['total_count'] == 0:
            return self._generate_empty_report()
        
        # 2. AI 层：生成洞察
        insight = self._generate_ai_insight(stats)
        
        # 3. 渲染层：生成 HTML
        html_content = self._render_report_html(stats, insight)
        
        # 4. 保存文件
        html_filepath = self._save_html_file(html_content)
        
        # 5. 存入数据库
        self._save_to_database(stats, insight, html_content, html_filepath)
        
        self._content = html_content
        logger.info(f"月报生成完成，包含 {stats['total_count']} 条更新，保存至: {html_filepath}")
        
        return html_content
    
    def _save_html_file(self, html_content: str) -> str:
        """
        保存 HTML 文件到 data/report 目录
        
        Returns:
            文件路径
        """
        # 获取项目根目录
        base_dir = os.path.abspath(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        )
        report_dir = os.path.join(base_dir, 'data', 'report', 'monthly')
        os.makedirs(report_dir, exist_ok=True)
        
        # 文件名：2024-12.html（总是覆盖当月最新版本）
        filename = f"{self.start_date.strftime('%Y-%m')}.html"
        filepath = os.path.join(report_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"HTML 报告已保存: {filepath}")
        return filepath
    
    def _save_to_database(
        self,
        stats: Dict[str, Any],
        insight: Dict[str, Any],
        html_content: str,
        html_filepath: str
    ) -> None:
        """
        将报告数据保存到数据库
        """
        try:
            # 构建厂商统计数据
            vendor_stats_db = {}
            for vendor, data in stats['vendor_stats'].items():
                vendor_stats_db[vendor] = {
                    'count': data['count'],
                    'updates': [{
                        'update_id': u['update_id'],
                        'title': u.get('title_translated') or u.get('title') or '',
                        'publish_date': u.get('publish_date', ''),
                        'update_type': u.get('update_type', '')
                    } for u in data['updates']]
                }
            
            # AI 摘要（直接保存 JSON 字典，前端会更喜欢）
            # 注意：ReportRepository 已经更新支持传入 dict

            # 保存报告
            report_id = self._report_repo.save_report(
                report_type='monthly',
                year=self.start_date.year,
                month=self.start_date.month,
                week=None,
                date_from=self.start_date.strftime('%Y-%m-%d'),
                date_to=self.end_date.strftime('%Y-%m-%d'),
                ai_summary=insight,
                vendor_stats=vendor_stats_db,
                total_count=stats['total_count'],
                html_content=html_content,
                html_filepath=html_filepath
            )
            logger.info(f"报告已保存到数据库，ID: {report_id}")
            
        except Exception as e:
            logger.error(f"保存报告到数据库失败: {e}")
    
    def _generate_empty_report(self) -> str:
        """生成空报告"""
        month_str = self.start_date.strftime('%Y年%m月')
        
        # 简单的空报告 HTML
        html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>CloudNetSpy Monthly Report - {month_str}</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; background: #09090b; color: #e4e4e7; padding: 40px; text-align: center; }}
        h1 {{ color: #fff; }}
    </style>
</head>
<body>
    <h1>{month_str} 月报</h1>
    <p>本月暂无新的云产品动态更新。</p>
    <p><a href="{SITE_BASE_URL}" style="color: #818cf8;">前往平台查看更多</a></p>
</body>
</html>'''
        
        self._content = html
        return html
