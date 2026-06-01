#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
周报生成器
"""

import os
import json
import re
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
        # 默认统计上一个完整自然周 (周一到周日)
        if start_date is None or end_date is None:
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            # 计算到上周一的偏移量
            # today.weekday() 返回 0 (周一) 到 6 (周日)
            days_since_monday = today.weekday()
            
            # 上周一 00:00:00
            last_monday = today - timedelta(days=days_since_monday + 7)
            # 上周日 23:59:59
            last_sunday = last_monday + timedelta(days=6, hours=23, minutes=59, seconds=59)
            
            start_date = start_date or last_monday
            end_date = end_date or last_sunday

        super().__init__(start_date, end_date)
        self._db = DatabaseManager()
        self._report_repo = ReportRepository()

        # 初始化 Gemini 客户端
        try:
            config = get_config()
            
            # 兼容扁平配置结构（config_loader 默认行为）和嵌套结构
            if 'report_generation' in config:
                # 情况1: 配置扁平化，report_generation 直接在根下
                ai_config = config['report_generation']
            elif 'ai_model' in config:
                # 情况2: 配置嵌套在 ai_model 下
                ai_model_config = config['ai_model']
                ai_config = ai_model_config.get('report_generation', ai_model_config.get('default', {}))
            else:
                # 情况3: 回退到根目录下的 default
                ai_config = config.get('default', {})
                
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
                    title_translated, content, content_summary, publish_date,
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

    def _get_updates_for_render(self) -> List[Dict[str, Any]]:
        """获取用于 Markdown 渲染的更新列表。"""
        if hasattr(self, '_update_map') and self._update_map:
            return list(self._update_map.values())

        updates = self._query_analyzed_updates()
        self._update_map = {u['update_id']: u for u in updates}
        return updates

    def _generate_fallback_insight(self, updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """AI 洞察失败时，用已分析数据生成可读兜底报告。"""
        if not updates:
            return {
                'insight_title': '本周暂无云产品动态',
                'insight_summary': '本周主要云厂商暂无重大的网络产品功能更新或发布。',
                'top_updates': [],
                'quick_scan': [],
                'featured_blogs': []
            }

        self._update_map = {u['update_id']: u for u in updates}

        vendor_counts: Dict[str, int] = {}
        for update in updates:
            vendor = update.get('vendor', '')
            vendor_counts[vendor] = vendor_counts.get(vendor, 0) + 1

        vendor_summary = '、'.join(
            f"{VENDOR_DISPLAY_NAMES.get(vendor, vendor)} {count} 条"
            for vendor, count in sorted(vendor_counts.items())
        )
        date_range = f"{self.start_date.strftime('%Y-%m-%d')} 至 {self.end_date.strftime('%Y-%m-%d')}"

        top_source_updates = updates[:5]
        top_updates = []
        for update in top_source_updates:
            vendor = update.get('vendor', '')
            source_channel = update.get('source_channel') or 'updates'
            product = update.get('product_subcategory') or source_channel
            summary = self._format_summary(update.get('content_summary') or '')
            top_updates.append({
                'update_id': update.get('update_id', ''),
                'vendor': VENDOR_DISPLAY_NAMES.get(vendor, vendor),
                'product': product,
                'title': update.get('title_translated') or update.get('title') or '',
                'pain_point': f"来自 {source_channel}，发布日期 {update.get('publish_date') or '未知'}。",
                'value': summary or '该更新已完成网络相关分析，建议结合产品路线和客户场景评估影响。',
                'comment': 'AI 洞察生成失败，本条由本地分析摘要自动兜底整理。'
            })

        top_ids = {item['update_id'] for item in top_updates}
        quick_scan = []
        grouped_updates: Dict[str, List[Dict[str, Any]]] = {}
        for update in updates:
            if update.get('update_id') in top_ids:
                continue
            vendor = update.get('vendor', '')
            grouped_updates.setdefault(vendor, []).append(update)

        for vendor, vendor_updates in sorted(grouped_updates.items()):
            items = []
            for update in vendor_updates[:8]:
                title = update.get('title_translated') or update.get('title') or ''
                if not title:
                    continue
                items.append({
                    'update_id': update.get('update_id', ''),
                    'content': f"{title}（{update.get('publish_date') or '日期未知'}）",
                    'is_noteworthy': False
                })
            if items:
                quick_scan.append({
                    'vendor': VENDOR_DISPLAY_NAMES.get(vendor, vendor),
                    'items': items
                })

        featured_blogs = []
        for update in updates:
            if 'blog' not in (update.get('source_channel') or '').lower():
                continue
            featured_blogs.append({
                'update_id': update.get('update_id', ''),
                'vendor': VENDOR_DISPLAY_NAMES.get(update.get('vendor', ''), update.get('vendor', '')),
                'title': update.get('title_translated') or update.get('title') or '',
                'url': self._build_update_link(update.get('update_id', '')),
                'reason': self._format_summary(update.get('content_summary') or '') or '本周网络相关技术文章，建议补看。'
            })
            if len(featured_blogs) >= 3:
                break

        top_titles = '；'.join(item['title'] for item in top_updates[:3] if item.get('title'))
        insight_summary = (
            f"{date_range} 共跟踪到 {len(updates)} 条已分析云网络动态，覆盖 {vendor_summary}。"
        )
        if top_titles:
            insight_summary += f" 重点包括：{top_titles}。"

        return {
            'insight_title': '本周云网络动态速览',
            'insight_summary': insight_summary,
            'top_updates': top_updates,
            'quick_scan': quick_scan,
            'featured_blogs': featured_blogs
        }

    def _generate_ai_insight(self, updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        调用 AI 生成周报核心洞察 (JSON) (使用结构化输出)
        """
        if not self._gemini or not updates:
            return {}

        # 定义结构化输出 Schema
        weekly_report_schema = {
            "type": "object",
            "properties": {
                "insight_title": {"type": "string"},
                "insight_summary": {"type": "string"},
                "top_updates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "update_id": {"type": "string"},
                            "vendor": {"type": "string"},
                            "product": {"type": "string"},
                            "title": {"type": "string"},
                            "pain_point": {"type": "string"},
                            "value": {"type": "string"},
                            "comment": {"type": "string"}
                        },
                        "required": ["update_id", "vendor", "product", "title", "pain_point", "value", "comment"]
                    }
                },
                "featured_blogs": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "update_id": {"type": "string"},
                            "vendor": {"type": "string"},
                            "title": {"type": "string"},
                            "url": {"type": "string"},
                            "reason": {"type": "string"}
                        },
                        "required": ["update_id", "vendor", "title", "reason"]
                    }
                },
                "quick_scan": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "vendor": {"type": "string"},
                            "items": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "update_id": {"type": "string"},
                                        "content": {"type": "string"},
                                        "is_noteworthy": {"type": "boolean"}
                                    },
                                    "required": ["update_id", "content", "is_noteworthy"]
                                }
                            }
                        },
                        "required": ["vendor", "items"]
                    }
                }
            },
            "required": ["insight_title", "insight_summary", "top_updates", "featured_blogs", "quick_scan"]
        }

        try:
            # 加载提示词模板
            prompt_file = os.path.join(PROMPT_DIR, 'weekly_insight.prompt.txt')
            if not os.path.exists(prompt_file):
                logger.warning(f"提示词文件不存在: {prompt_file}")
                return {}

            with open(prompt_file, 'r', encoding='utf-8') as f:
                prompt_template = f.read()

            # 准备数据：包含完整的原文和所有元数据，确保 AI 洞察的深度和准确性
            updates_for_ai = []
            for u in updates:
                # 彻底取消原文截断，确保 AI 能看到每一个字节的技术细节
                content_raw = u.get('content', '')

                updates_for_ai.append({
                    'update_id': u['update_id'],
                    'vendor': u['vendor'],
                    'publish_date': u.get('publish_date', ''),
                    'source_channel': u.get('source_channel', ''),
                    'update_type': u.get('update_type', ''),
                    'subcategory': u.get('product_subcategory', ''),
                    'title': u.get('title_translated', ''),
                    'content_raw': content_raw                   # 提供原始全文，不再截断
                })

            updates_json = json.dumps(updates_for_ai, ensure_ascii=False, indent=2)
            # 同时保留一个 ID 到 完整信息的映射，方便后续渲染时找回原始链接
            self._update_map = {u['update_id']: u for u in updates}

            # 统计元数据，帮助 AI 感知规模
            stats_summary = f"本周总更新数: {len(updates)}\n"
            vendor_counts = {}
            for u in updates_for_ai:
                v = u['vendor']
                vendor_counts[v] = vendor_counts.get(v, 0) + 1
            for v, count in vendor_counts.items():
                stats_summary += f"- {v}: {count} 条\n"

            date_range = f"{self.start_date.strftime('%Y-%m-%d')} 至 {self.end_date.strftime('%Y-%m-%d')}"

            # 替换变量
            prompt = prompt_template.replace('{date_range}', date_range)
            prompt = prompt.replace('{updates_json}', updates_json)
            prompt = prompt.replace('{stats_summary}', stats_summary)

            # 调用 AI (开启结构化输出模式)
            logger.info("调用 Gemini 生成周报洞察 (结构化模式)...")

            response = self._gemini.generate_text(
                prompt, 
                response_mime_type="application/json",
                response_schema=weekly_report_schema
            )

            result = json.loads(response.strip())
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
                update_id = item.get('update_id')
                link = self._build_update_link(update_id) if update_id else "#"
                
                title = item.get('title', '')
                product = item.get('product', '')
                
                display_title = title
                
                # # 智能标题拼接：如果标题里已经包含产品名，就直接用标题；否则用 "产品: 标题"
                # if product and title and product.lower() in title.lower():
                #     display_title = title
                # elif product and title:
                #     display_title = f"{product}: {title}"
                # else:
                #     display_title = title or product

                top_updates_html += f'''
<div class="feature-card">
    <div class="feature-header">
        <span class="badge badge-{vendor_lower}">{vendor}</span>
        <h4 class="feature-title"><a href="{link}" target="_blank" class="card-link">{display_title}</a></h4>
    </div>
    <div class="feature-grid">
        <div class="feature-item">
            <span class="feature-label">场景/痛点</span>
            <span class="feature-val">{item.get('pain_point', '')}</span>
        </div>
        <div class="feature-item">
            <span class="feature-label">核心价值</span>
            <span class="feature-val">{item.get('value', '')}</span>
        </div>
        <div class="feature-item" style="grid-column: 1 / -1;">
            <span class="feature-label">专家点评</span>
            <span class="feature-val" style="font-style: italic; color: hsl(var(--primary));">“{item.get('comment', '')}”</span>
        </div>
    </div>
</div>
'''

        # 2. Quick Scan
        quick_scan_html = ""
        if insight.get('quick_scan'):
            for group in insight['quick_scan']:
                vendor = group.get('vendor', 'Unknown')
                vendor_lower = vendor.lower()
                items = group.get('items', [])
                
                if not items:
                    continue
                    
                # 预渲染 items 内容，只有当内容不为空时才添加该厂商板块
                current_vendor_items_html = ""
                for item in items:
                    # 兼容新旧格式
                    content = item.get('content', '') if isinstance(item, dict) else item
                    if not content or str(content).strip() == "":
                        continue

                    update_id = item.get('update_id') if isinstance(item, dict) else None
                    is_noteworthy = item.get('is_noteworthy', False) if isinstance(item, dict) else False
                    
                    link = self._build_update_link(update_id) if update_id else "#"
                    
                    item_class = 'scan-item scan-item-noteworthy' if is_noteworthy else 'scan-item'
                    icon_html = '<span class="scan-icon">✨</span>' if is_noteworthy else ''
                    
                    current_vendor_items_html += f'''
<div class="{item_class}">
    <a href="{link}" target="_blank" class="card-link">{icon_html}{content}</a>
</div>'''

                # 只有当该厂商下确实有有效 items 时，才渲染厂商行
                if current_vendor_items_html:
                    quick_scan_html += f'''
<div class="scan-row">
    <div class="scan-vendor-side">
        <div class="scan-vendor-name">
            <span class="scan-vendor-dot bg-{vendor_lower}"></span>
            {vendor}
        </div>
    </div>
    <div class="scan-grid">
        {current_vendor_items_html}
    </div>
</div>
'''

        # 3. Featured Blogs
        featured_blogs_html = ""
        if insight.get('featured_blogs'):
            for blog in insight['featured_blogs']:
                vendor = blog.get('vendor', 'Unknown')
                vendor_lower = vendor.lower()
                update_id = blog.get('update_id')
                
                # 优先使用内部链接，如果没有则使用 AI 返回的 url
                link = "#"
                if update_id and update_id in self._update_map:
                    link = self._build_update_link(update_id)
                else:
                    link = blog.get('url', '#')

                featured_blogs_html += f'''
<div class="blog-card">
    <div class="blog-accent bg-{vendor_lower}"></div>
    <div class="blog-content">
        <h4><a href="{link}" target="_blank" class="card-link">{blog.get('title', '')}</a></h4>
        <p class="blog-reason">{blog.get('reason', '')}</p>
    </div>
</div>
'''

        # 替换模板变量
        html = template
        html = html.replace('{{date_range}}', date_range)
        html = html.replace('{{report_week}}', report_week)
        
        insight_title = insight.get('insight_title', '本周技术周报')
        if not insight_title.startswith('本周主题'):
            insight_title = f"本周主题：{insight_title}"
            
        html = html.replace('{{insight_title}}', escape(insight_title))
        html = html.replace('{{insight_summary}}', escape(insight.get('insight_summary', '')))

        # 处理条件块：如果 html 为空，则移除整个板块（利用占位符）
        if top_updates_html:
            html = html.replace('{{top_updates_html}}', top_updates_html)
            html = html.replace('{{#if top_updates_html}}', '').replace('{{/if}}', '')
        else:
            # 彻底移除该板块
            html = re.sub(r'{{#if top_updates_html}}.*?{{/if}}', '', html, flags=re.DOTALL)

        if quick_scan_html:
            html = html.replace('{{quick_scan_html}}', quick_scan_html)
            html = html.replace('{{#if quick_scan_html}}', '').replace('{{/if}}', '')
        else:
            html = re.sub(r'{{#if quick_scan_html}}.*?{{/if}}', '', html, flags=re.DOTALL)

        if featured_blogs_html:
            html = html.replace('{{featured_blogs_html}}', featured_blogs_html)
            html = html.replace('{{#if featured_blogs_html}}', '').replace('{{/if}}', '')
        else:
            html = re.sub(r'{{#if featured_blogs_html}}.*?{{/if}}', '', html, flags=re.DOTALL)

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
            logger.info("本周无更新，生成空报告")
            # 构建空 AI 洞察对象
            ai_insight = {
                'insight_title': '本周暂无云产品动态',
                'insight_summary': '本周主要云厂商（AWS, Azure, GCP, 华为云等）暂无重大的网络产品功能更新或发布。',
                'top_updates': [],
                'quick_scan': [],
                'featured_blogs': []
            }
        else:
            # 生成 AI 洞察
            ai_insight = self._generate_ai_insight(updates)
            if not ai_insight:
                logger.warning("AI 周报洞察为空，使用本地兜底摘要")
                ai_insight = self._generate_fallback_insight(updates)

        # 1. 生成 HTML 报告
        html_content = self._render_html(updates, ai_insight)

        # 2. 保存 HTML 文件
        html_filepath = self._save_html_file(html_content)

        # 3. 保存到数据库
        self._save_to_database(updates, ai_insight, html_content, html_filepath)
        
        # 4. 生成 Markdown 内容 (用于通知)
        return self.render_markdown(ai_insight)

    def render_markdown(self, ai_insight: Dict[str, Any]) -> str:
        """
        根据 AI 洞察生成 Markdown 内容
        """
        updates = self._get_updates_for_render()
        if updates and not ai_insight:
            ai_insight = self._generate_fallback_insight(updates)
        
        # 如果是空报告（没有 updates 且 ai_insight 显示无内容）
        if not updates and not ai_insight.get('top_updates') and not ai_insight.get('quick_scan'):
             self._generate_empty_report()
             return self._content

        lines = []
        date_range_str = f"{self.start_date.strftime('%Y年%m月%d日')} - {self.end_date.strftime('%Y年%m月%d日')}"
        lines.append(f"# 【云网络竞争动态周报】 {date_range_str} 竞争动态速览")
        lines.append("")

        if ai_insight:
            if ai_insight.get('insight_title'):
                lines.append(f"## 本周主题：{ai_insight['insight_title']}")
                lines.append("")
            if ai_insight.get('insight_summary'):
                lines.append(ai_insight['insight_summary'])
                lines.append("")

            # 1. 重点更新 (Key Updates)
            if ai_insight.get('top_updates'):
                lines.append("### 🌟 重点更新 (Key Updates)")
                lines.append("")
                for item in ai_insight['top_updates']:
                    vendor = item.get('vendor', 'Unknown')
                    product = item.get('product', '')
                    full_title = item.get('title', '')
                    update_id = item.get('update_id')
                    link = self._build_update_link(update_id) if update_id else ""
                    
                    # 优先展示发布标题，如果标题里没包含产品名，则加上产品名
                    display_title = full_title if full_title else product
                    if product and full_title and product.lower() not in full_title.lower():
                        display_title = f"{product}: {full_title}"
                    
                    title_text = f"**[{vendor}] {display_title}**"
                    if link:
                        lines.append(f"- [{title_text}]({link})")
                    else:
                        lines.append(f"- {title_text}")

                    if item.get('pain_point'):
                        lines.append(f"  - **痛点:** {item.get('pain_point', '')}")
                    if item.get('value'):
                        lines.append(f"  - **价值:** {item.get('value', '')}")
                    if item.get('comment'):
                        lines.append(f"  - **点评:** {item.get('comment', '')}")
                    lines.append("")

            # 2. 其他更新 (Other Updates)
            if ai_insight.get('quick_scan'):
                lines.append("### ⚡️ 其他更新 (Other Updates)")
                lines.append("")
                for group in ai_insight['quick_scan']:
                    vendor = group.get('vendor', 'Unknown')
                    lines.append(f"- **{vendor}**")
                    for item in group.get('items', []):
                        content = item.get('content', '') if isinstance(item, dict) else item
                        update_id = item.get('update_id') if isinstance(item, dict) else None
                        is_noteworthy = item.get('is_noteworthy', False) if isinstance(item, dict) else False
                        
                        link = self._build_update_link(update_id) if update_id else None
                        star = "✨ " if is_noteworthy else ""
                        
                        if link:
                            lines.append(f"  - {star}[{content}]({link})")
                        else:
                            lines.append(f"  - {star}{content}")
                    lines.append("")

            # 3. 精选博客 (Featured Blogs)
            if ai_insight.get('featured_blogs'):
                lines.append("### 📚 必读好文 // SPOTLIGHT")
                lines.append("")
                for blog in ai_insight['featured_blogs']:
                    vendor = blog.get('vendor', 'Unknown')
                    title = blog.get('title', '')
                    update_id = blog.get('update_id')
                    
                    link = "#"
                    if update_id and update_id in self._update_map:
                        link = self._build_update_link(update_id)
                    else:
                        link = blog.get('url', '#')

                    lines.append(f"- **[{vendor}] [{title}]({link})**")
                    if blog.get('reason'):
                        lines.append(f"  - **推荐理由:** {blog.get('reason', '')}")
                    lines.append("")
            
            lines.append("---")
            lines.append("")

        self._content = '\n'.join(lines)
        return self._content

    def _generate_empty_report(self) -> str:
        """生成空报告"""
        date_range = f"{self.start_date.strftime('%Y年%m月%d日')} - {self.end_date.strftime('%Y年%m月%d日')}"
        content = f"""# 【云网络竞争动态周报】 {date_range} 竞争动态速览

汇集本周主要云厂商的技术产品动态，助您快速掌握核心变化。

> 本周暂无新的云产品动态更新。
"""
        self._content = content
        return content
