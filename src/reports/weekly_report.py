#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
周报生成器
"""

import os
import json
import logging
import markdown
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

# 路径配置
PROMPT_DIR = os.path.join(os.path.dirname(__file__), '..', 'analyzers', 'prompts')
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')


class WeeklyReport(BaseReport):
    """
    周报生成器

    汇总过去一周的更新分析结果，并调用 AI 生成洞察摘要
    支持生成 Markdown 和 HTML 格式
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
        return "weekly"

    @property
    def report_name(self) -> str:
        return "周报"

    def _query_analyzed_updates(self) -> List[Dict[str, Any]]:
        """
        查询时间范围内已分析的更新
        """
        date_from = self.start_date.strftime('%Y-%m-%d')
        date_to = self.end_date.strftime('%Y-%m-%d')

        with self._db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT
                    update_id, vendor, source_channel, update_type,
                    title_translated, content_summary, publish_date,
                    product_subcategory
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

    def _generate_ai_insight(self, updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        调用 AI 生成周报核心洞察 (JSON)
        """
        if not self._gemini or not updates:
            return {}

        try:
            # 加载提示词模板
            prompt_file = os.path.join(PROMPT_DIR, 'weekly_insight.prompt.txt')
            if not os.path.exists(prompt_file):
                logger.warning(f"提示词文件不存在: {prompt_file}")
                return {}

            with open(prompt_file, 'r', encoding='utf-8') as f:
                prompt_template = f.read()

            # 准备数据（包含 source_channel 以便区分 Blog 和 Feature）
            updates_for_ai = []
            for u in updates:
                updates_for_ai.append({
                    'update_id': u['update_id'],
                    'vendor': u['vendor'],
                    'title': u.get('title_translated', ''),
                    'source_channel': u.get('source_channel', ''),
                    'summary': self._format_summary(u.get('content_summary', ''))[:100]
                })

            updates_json = json.dumps(updates_for_ai, ensure_ascii=False, indent=2)
            date_range = f"{self.start_date.strftime('%Y-%m-%d')} 至 {self.end_date.strftime('%Y-%m-%d')}"

            # 替换变量
            prompt = prompt_template.replace('{date_range}', date_range)
            prompt = prompt.replace('{updates_json}', updates_json)

            # 调用 AI
            logger.info("调用 Gemini 生成周报洞察 (JSON)...")
            response = self._gemini.generate_text(prompt)

            # 清理可能的 Markdown 标记
            response = response.strip()
            if response.startswith('```json'):
                response = response[7:]
            elif response.startswith('```'):
                response = response[3:]
            if response.endswith('```'):
                response = response[:-3]
            response = response.strip()

            result = json.loads(response)

            # 数据清洗：防止 AI 返回嵌套结构 (e.g. { "insight_summary": { ...real_data... } })
            if isinstance(result, dict):
                # 检查是否嵌套在 insight_summary 中
                if 'insight_title' not in result and \
                   'insight_summary' in result and \
                   isinstance(result['insight_summary'], dict):
                    logger.warning("检测到 AI 返回了嵌套的 JSON 结构，正在进行解包...")
                    result = result['insight_summary']
                
                # 再次检查常见的错误根节点 (e.g. { "report": { ... } })
                elif len(result) == 1 and isinstance(list(result.values())[0], dict):
                    key = list(result.keys())[0]
                    # 如果这唯一的 key 看起来不像是有意义的数据字段 (insight_title/summary)
                    if key not in ['insight_title', 'insight_summary', 'top_updates']:
                        logger.warning(f"检测到 AI 返回了单根节点 '{key}'，正在尝试解包...")
                        result = list(result.values())[0]

            return result

        except Exception as e:
            logger.error(f"AI 周报洞察生成失败: {e}")
            return {}

    def _render_card_html(self, update: Dict) -> str:
        # 这个方法可能不再需要了，或者只用于 Quick Scan 中的某些场景？
        # 新的逻辑是在 _render_html 中根据 JSON 结构渲染
        pass

    def _render_html(self, updates: List[Dict], insight: Dict[str, Any]) -> str:
        """生成 HTML 报告"""
        template_file = os.path.join(TEMPLATE_DIR, 'weekly_report.html')
        with open(template_file, 'r', encoding='utf-8') as f:
            template = f.read()

        # 日期范围
        date_range = f"{self.start_date.strftime('%Y-%m-%d')} 至 {self.end_date.strftime('%Y-%m-%d')}"
        year, week, _ = self.start_date.isocalendar()
        report_week = f"{year}年第{week}周"

        # 1. Top Feature Updates
        top_updates_html = ""
        if insight.get('top_updates'):
            for item in insight['top_updates']:
                vendor = item.get('vendor', 'Unknown')
                vendor_lower = vendor.lower()

                # 尝试根据名称找到对应的原始 update_id (可选，为了链接)
                # 这里简化处理，直接展示文本

                top_updates_html += f'''
<div class="feature-card">
    <div class="feature-header">
        <span class="vendor-badge vendor-{vendor_lower}">{vendor}</span>
        <h3 class="feature-title">{item.get('product', '')}</h3>
    </div>
    <div class="feature-grid">
        <div class="feature-item">
            <span class="feature-label">痛点</span>
            <span class="feature-val">{item.get('pain_point', '')}</span>
        </div>
        <div class="feature-item">
            <span class="feature-label">价值</span>
            <span class="feature-val">{item.get('value', '')}</span>
        </div>
        <div class="feature-item">
            <span class="feature-label">点评</span>
            <span class="feature-val">{item.get('comment', '')}</span>
        </div>
    </div>
</div>
'''

        # 2. Featured Blogs
        featured_blogs_html = ""
        if insight.get('featured_blogs'):
            for blog in insight['featured_blogs']:
                vendor = blog.get('vendor', 'Unknown')
                vendor_lower = vendor.lower()
                url = blog.get('url', '#')

                featured_blogs_html += f'''
<div class="blog-card">
    <div class="blog-icon">📚</div>
    <div class="blog-content">
        <h4>
            <span class="vendor-badge vendor-{vendor_lower}" style="font-size: 0.7rem; margin-right: 6px;">{vendor}</span>
            <a href="{url}" target="_blank">{blog.get('title', '')}</a>
        </h4>
        <p class="blog-reason">{blog.get('reason', '')}</p>
    </div>
</div>
'''

        # 3. Quick Scan
        quick_scan_html = ""
        if insight.get('quick_scan'):
            for group in insight['quick_scan']:
                vendor = group.get('vendor', 'Unknown')
                vendor_lower = vendor.lower()
                items_html = ""
                for item in group.get('items', []):
                    items_html += f"<li>{item}</li>"

                quick_scan_html += f'''
<div class="scan-column">
    <div class="scan-vendor">
        <span class="vendor-badge vendor-{vendor_lower}">{vendor}</span>
    </div>
    <ul class="scan-list">
        {items_html}
    </ul>
</div>
'''

        # 替换模板变量
        html = template
        html = html.replace('{{date_range}}', date_range)
        html = html.replace('{{report_week}}', report_week)
        html = html.replace('{{insight_title}}', escape(insight.get('insight_title', '本周技术周报')))
        html = html.replace('{{insight_summary}}', escape(insight.get('insight_summary', '')))

        # 处理条件块
        if top_updates_html:
            html = html.replace('{{top_updates_html}}', top_updates_html)
            html = html.replace('{{#if top_updates_html}}', '').replace('{{/if}}', '')
        else:
            # 简单移除标签（实际应该用正则更严谨，但这里简化）
            html = html.replace('{{#if top_updates_html}}', '<div style="display:none">').replace('{{/if}}', '</div>')

        if featured_blogs_html:
            html = html.replace('{{featured_blogs_html}}', featured_blogs_html)
            html = html.replace('{{#if featured_blogs_html}}', '').replace('{{/if}}', '')
        else:
            html = html.replace('{{#if featured_blogs_html}}', '<div style="display:none">').replace('{{/if}}', '</div>')

        html = html.replace('{{quick_scan_html}}', quick_scan_html)

        return html

    def _save_html_file(self, html_content: str) -> str:
        """保存 HTML 文件"""
        base_dir = os.path.abspath(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        )
        report_dir = os.path.join(base_dir, 'data', 'report', 'weekly')
        os.makedirs(report_dir, exist_ok=True)

        # 获取该周是当年的第几周
        year, week, _ = self.start_date.isocalendar()
        filename = f"{year}-W{week}.html"
        filepath = os.path.join(report_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)

        logger.info(f"HTML 报告已保存: {filepath}")
        return filepath

    def _save_to_database(self, updates: List[Dict], ai_insight: Dict[str, Any], html_content: str, html_filepath: str):
        """保存到数据库"""
        try:
            # 统计数据
            vendor_stats = {}
            for u in updates:
                vendor = u['vendor']
                if vendor not in vendor_stats:
                    vendor_stats[vendor] = {'count': 0, 'updates': []}
                vendor_stats[vendor]['count'] += 1
                vendor_stats[vendor]['updates'].append({
                    'update_id': u['update_id'],
                    'title': u.get('title_translated', ''),
                    'publish_date': u.get('publish_date', '')
                })

            # 计算周次
            year, week, _ = self.start_date.isocalendar()

            self._report_repo.save_report(
                report_type='weekly',
                year=year,
                month=None,
                week=week,
                date_from=self.start_date.strftime('%Y-%m-%d'),
                date_to=self.end_date.strftime('%Y-%m-%d'),
                ai_summary=ai_insight,
                vendor_stats=vendor_stats,
                total_count=len(updates),
                html_content=html_content,
                html_filepath=html_filepath
            )
            logger.info(f"周报已保存到数据库 (Year: {year}, Week: {week})")

        except Exception as e:
            logger.error(f"保存周报到数据库失败: {e}")

    def generate(self) -> str:
        """
        生成周报内容
        """
        logger.info(f"生成周报: {self.start_date.strftime('%Y-%m-%d')} 至 {self.end_date.strftime('%Y-%m-%d')}")

        # 查询数据
        updates = self._query_analyzed_updates()

        if not updates:
            return self._generate_empty_report()

        # 生成 AI 洞察
        ai_insight = self._generate_ai_insight(updates)

        # 1. 生成 HTML 报告
        html_content = self._render_html(updates, ai_insight)

        # 2. 保存 HTML 文件
        html_filepath = self._save_html_file(html_content)

        # 3. 保存到数据库
        self._save_to_database(updates, ai_insight, html_content, html_filepath)

        # 4. 为了兼容通知发送，同时生成 Markdown 格式的 _content
        lines = []
        date_range_str = f"{self.start_date.strftime('%Y年%m月%d日')} - {self.end_date.strftime('%Y年%m月%d日')}"
        lines.append(f"# 【云技术周报】 {date_range_str} 竞争动态速览")
        lines.append("")

        if ai_insight:
            if ai_insight.get('insight_title'):
                lines.append(f"## {ai_insight['insight_title']}")
                lines.append("")
            if ai_insight.get('insight_summary'):
                lines.append(ai_insight['insight_summary'])
                lines.append("")

            if ai_insight.get('top_updates'):
                lines.append("### 🌟 本周亮点")
                lines.append("")
                for item in ai_insight['top_updates']:
                    vendor = item.get('vendor', 'Unknown')
                    product = item.get('product', '')
                    lines.append(f"- **[{vendor}] {product}**")
                    if item.get('pain_point'):
                        lines.append(f"  - **痛点:** {item.get('pain_point', '')}")
                    if item.get('value'):
                        lines.append(f"  - **价值:** {item.get('value', '')}")
                    if item.get('comment'):
                        lines.append(f"  - **点评:** {item.get('comment', '')}")
                    lines.append("")

            if ai_insight.get('featured_blogs'):
                lines.append("### 📚 精选博客")
                lines.append("")
                for blog in ai_insight['featured_blogs']:
                    vendor = blog.get('vendor', 'Unknown')
                    title = blog.get('title', '')
                    url = blog.get('url', '#')
                    lines.append(f"- **[{vendor}] [{title}]({url})**")
                    if blog.get('reason'):
                        lines.append(f"  - **推荐理由:** {blog.get('reason', '')}")
                    lines.append("")

            if ai_insight.get('quick_scan'):
                lines.append("### ⚡️ 快速浏览")
                lines.append("")
                for group in ai_insight['quick_scan']:
                    vendor = group.get('vendor', 'Unknown')
                    lines.append(f"- **{vendor}**")
                    for item in group.get('items', []):
                        lines.append(f"  - {item}")
                    lines.append("")
            
            lines.append("---")
            lines.append("")

        lines.append("## 📋 本周更新详情")
        lines.append("")

        for update in updates:
            vendor = update['vendor']
            vendor_name = VENDOR_DISPLAY_NAMES.get(vendor, vendor.upper())
            title = update['title_translated']
            update_id = update['update_id']
            summary = update['content_summary']
            link = self._build_update_link(update_id)
            formatted_summary = self._format_summary(summary)

            lines.append(f"### [[{vendor_name}] {title}]({link})")
            lines.append("")
            lines.append(formatted_summary)
            lines.append("")
            lines.append("")

        lines.append(f"由云竞争情报分析平台自动汇总。 [前往平台查看更多详情]({SITE_BASE_URL})")

        self._content = '\n'.join(lines)
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
