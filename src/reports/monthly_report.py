#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
月报生成器

架构分层：
- 数据层：程序统计（总数、厂商分布）
- 认知层：AI 生成 JSON 格式的洞察摘要（与周报结构一致）
- 表现层：程序拼接 HTML 报告
"""

import os
import json
import re
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

# 站点配置
SITE_BASE_URL = "https://cnetspy.site/next"

# 路径配置
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
        # 默认日期逻辑
        if start_date is None or end_date is None:
            today = datetime.now()
            
            # 如果是每月 1 号，则默认生成上个月的全量月报
            if today.day == 1:
                # 上月最后一天
                last_month_end = today.replace(day=1) - timedelta(seconds=1)
                # 上月第一天
                last_month_start = last_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                
                start_date = start_date or last_month_start
                end_date = end_date or last_month_end
            else:
                # 否则统计当月 1 号至今
                start_date = start_date or today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                end_date = end_date or today
        
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
        return "monthly"
    
    @property
    def report_name(self) -> str:
        return "月报"
    
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
                    title_translated, title, content, content_summary, publish_date,
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

    def _generate_ai_insight(self, updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        调用 AI 生成月报核心洞察 (JSON)
        结构适配前端：insight_title, insight_summary, landmark_updates, solution_analysis, noteworthy_updates
        """
        if not self._gemini or not updates:
            return {}

        # 定义结构化输出 Schema (适配前端展示需求)
        monthly_report_schema = {
            "type": "object",
            "properties": {
                "insight_title": {"type": "string"},
                "insight_summary": {"type": "string"},
                "landmark_updates": {
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
                "solution_analysis": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "theme": {"type": "string"},
                            "summary": {"type": "string"},
                            "references": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "update_id": {"type": "string"},
                                        "title": {"type": "string"}
                                    }
                                }
                            }
                        },
                        "required": ["theme", "summary", "references"]
                    }
                },
                "noteworthy_updates": {
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
                                        "reason": {"type": "string"}
                                    },
                                    "required": ["update_id", "content", "reason"]
                                }
                            }
                        },
                        "required": ["vendor", "items"]
                    }
                }
            },
            "required": ["insight_title", "insight_summary", "landmark_updates", "solution_analysis", "noteworthy_updates"]
        }

        try:
            # 加载提示词模板
            prompt_file = os.path.join(PROMPT_DIR, 'monthly_insight.prompt.txt')
            if not os.path.exists(prompt_file):
                logger.warning(f"提示词文件不存在: {prompt_file}")
                return {}

            with open(prompt_file, 'r', encoding='utf-8') as f:
                prompt_template = f.read()

            # 准备数据：包含完整的原文和所有元数据
            updates_for_ai = []
            for u in updates:
                content_raw = u.get('content', '')

                updates_for_ai.append({
                    'update_id': u['update_id'],
                    'vendor': u['vendor'],
                    'publish_date': u.get('publish_date', ''),
                    'source_channel': u.get('source_channel', ''),
                    'update_type': u.get('update_type', ''),
                    'subcategory': u.get('product_subcategory', ''),
                    'title': u.get('title_translated') or u.get('title', ''),
                    'content_raw': content_raw
                })

            updates_json = json.dumps(updates_for_ai, ensure_ascii=False, indent=2)
            # 保留 ID 映射方便后续查阅
            self._update_map = {u['update_id']: u for u in updates}

            # 统计元数据
            stats_summary = f"本月总更新数: {len(updates)}\n"
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

            logger.info("调用 Gemini 生成月报洞察 (结构化模式)...")
            response = self._gemini.generate_text(
                prompt, 
                response_mime_type="application/json",
                response_schema=monthly_report_schema
            )
            result = json.loads(response.strip())
            return result

        except Exception as e:
            logger.error(f"AI 月报洞察生成失败: {e}")
            return {}

    def _render_html(self, updates: List[Dict], insight: Dict[str, Any]) -> str:
        """生成 HTML 报告"""
        template_file = os.path.join(TEMPLATE_DIR, 'monthly_report.html')
        with open(template_file, 'r', encoding='utf-8') as f:
            template = f.read()

        # 日期显示
        month_str = self.start_date.strftime('%Y年%m月')
        if self.end_date.day < 28:
            month_str += f"（截止{self.end_date.strftime('%m月%d日')}）"
        date_range = f"{self.start_date.strftime('%Y-%m-%d')} 至 {self.end_date.strftime('%Y-%m-%d')}"

        # 1. Landmark Updates HTML
        landmark_updates_html = ""
        if insight.get('landmark_updates'):
            for i, item in enumerate(insight['landmark_updates']):
                vendor = item.get('vendor', 'Unknown')
                vendor_lower = vendor.lower()
                update_id = item.get('update_id')
                link = self._build_update_link(update_id) if update_id else "#"
                
                title = item.get('title', '')
                pain_point = item.get('pain_point', '')
                value = item.get('value', '')
                comment = item.get('comment', '')

                landmark_updates_html += f'''
<div class="feature-card">
    <div class="landmark-number">0{i+1}</div>
    <div class="feature-header">
        <span class="badge badge-{vendor_lower}">{vendor}</span>
        <h4 class="feature-title"><a href="{link}" target="_blank" class="card-link">{title}</a></h4>
    </div>
    <div class="feature-grid">
        <div class="feature-item">
            <span class="feature-label">痛点</span>
            <span class="feature-val">{pain_point}</span>
        </div>
        <div class="feature-item">
            <span class="feature-label">价值</span>
            <span class="feature-val">{value}</span>
        </div>
        <div class="feature-item" style="grid-column: 1 / -1;">
            <span class="feature-label">点评</span>
            <span class="feature-val" style="font-style: italic; color: hsl(var(--primary));">“{comment}”</span>
        </div>
    </div>
</div>
'''

        # 2. Noteworthy Updates HTML
        noteworthy_updates_html = ""
        if insight.get('noteworthy_updates'):
            for group in insight['noteworthy_updates']:
                vendor = group.get('vendor', 'Unknown')
                vendor_lower = vendor.lower()
                items = group.get('items', [])
                
                if not items:
                    continue
                    
                current_vendor_items_html = ""
                for item in items:
                    content = item.get('content', '')
                    update_id = item.get('update_id')
                    reason = item.get('reason', '')
                    link = self._build_update_link(update_id) if update_id else "#"
                    
                    # 月报中的 Noteworthy Updates 全部视为重要，添加高亮样式和图标
                    item_class = 'scan-item scan-item-noteworthy'
                    icon_html = '<span class="scan-icon">✨</span>'
                    
                    current_vendor_items_html += f'''
<div class="{item_class}">
    <a href="{link}" target="_blank" class="card-link">{icon_html}{content}</a>
    <span class="text-xs text-muted block mt-1">{reason}</span>
</div>'''

                if current_vendor_items_html:
                    noteworthy_updates_html += f'''
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

        # 3. Solution Analysis HTML
        solution_analysis_html = ""
        if insight.get('solution_analysis'):
            for sol in insight['solution_analysis']:
                theme = sol.get('theme', '')
                summary = sol.get('summary', '')
                
                refs_html = ""
                if sol.get('references'):
                    for ref in sol['references']:
                        update_id = ref.get('update_id')
                        link = self._build_update_link(update_id) if update_id else "#"
                        refs_html += f'<a href="{link}" target="_blank" class="text-xs border border-color px-2 py-1 rounded hover:bg-muted/50">{ref.get("title", "")}</a>'

                solution_analysis_html += f'''
<div class="blog-card">
    <div class="blog-accent bg-primary"></div>
    <div class="blog-content w-full">
        <h4 class="text-xl mb-2">{theme}</h4>
        <p class="text-sm text-secondary mb-4">{summary}</p>
        <div class="flex flex-wrap gap-2">
            {refs_html}
        </div>
    </div>
</div>
'''

        # 替换模板变量
        html = template
        html = html.replace('{{report_month}}', month_str)
        html = html.replace('{{date_range}}', date_range)
        
        insight_title = insight.get('insight_title', '本月技术月报')
        if not insight_title.startswith('本月主题'):
            insight_title = f"本月主题：{insight_title}"
            
        html = html.replace('{{insight_title}}', escape(insight_title))
        html = html.replace('{{insight_summary}}', escape(insight.get('insight_summary', '')))

        # 条件块处理
        if landmark_updates_html:
            html = html.replace('{{landmark_updates_html}}', landmark_updates_html)
            html = html.replace('{{#if landmark_updates_html}}', '').replace('{{/if}}', '')
        else:
            html = re.sub(r'{{#if landmark_updates_html}}.*?{{/if}}', '', html, flags=re.DOTALL)

        if noteworthy_updates_html:
            html = html.replace('{{quick_scan_html}}', noteworthy_updates_html) # 复用 quick_scan 的坑位
            html = html.replace('{{#if quick_scan_html}}', '').replace('{{/if}}', '')
        else:
            html = re.sub(r'{{#if quick_scan_html}}.*?{{/if}}', '', html, flags=re.DOTALL)

        if solution_analysis_html:
            html = html.replace('{{featured_blogs_html}}', solution_analysis_html) # 复用 featured_blogs 的坑位
            html = html.replace('{{#if featured_blogs_html}}', '').replace('{{/if}}', '')
        else:
            html = re.sub(r'{{#if featured_blogs_html}}.*?{{/if}}', '', html, flags=re.DOTALL)

        # 替换 Section Titles (因为复用了变量名，需要修正显示的标题)
        html = html.replace('月度关键发布 // LANDMARKS', '月度关键发布 // LANDMARKS') # 保持不变
        html = html.replace('竞争阵地概览 // BATTLEGROUND', '其他重要更新 // NOTEWORTHY')
        html = html.replace('必读好文 // SPOTLIGHT', '深度技术洞察 // SOLUTIONS')

        return html

    def generate(self) -> str:
        """
        生成月报内容
        """
        logger.info(f"生成月报: {self.start_date.strftime('%Y-%m-%d')} 至 {self.end_date.strftime('%Y-%m-%d')}")

        # 1. 查询数据
        updates = self._query_analyzed_updates()
        if not updates:
            logger.info("本月无更新，生成空报告")
            ai_insight = {
                'insight_title': '本月暂无重大动态',
                'insight_summary': '本月主要云厂商（AWS, Azure, GCP, 华为云等）暂无重大的网络产品功能更新或发布。',
                'landmark_updates': [],
                'solution_analysis': [],
                'noteworthy_updates': []
            }
        else:
            # 2. 生成 AI 洞察
            ai_insight = self._generate_ai_insight(updates)

        # 3. 生成 HTML 报告
        html_content = self._render_html(updates, ai_insight)

        # 4. 保存 HTML 文件
        html_filepath = self._save_html_file(html_content)

        # 5. 保存到数据库
        self._save_to_database(updates, ai_insight, html_content, html_filepath)
        
        # 6. 生成 Markdown 内容 (用于推送)
        return self.render_markdown(ai_insight)

    def render_markdown(self, ai_insight: Dict[str, Any]) -> str:
        """
        根据 AI 洞察生成 Markdown 内容
        """
        updates = []
        # 确保 _update_map 存在
        if not hasattr(self, '_update_map') or not self._update_map:
            updates = self._query_analyzed_updates()
            self._update_map = {u['update_id']: u for u in updates}

        if not updates and not ai_insight.get('landmark_updates') and not ai_insight.get('noteworthy_updates'):
            self._generate_empty_report()
            return self._content

        lines = []
        month_str = self.start_date.strftime('%Y年%m月')
        lines.append(f"# 【云网络竞争动态月报】 {month_str}")
        lines.append("")

        if ai_insight:
            if ai_insight.get('insight_title'):
                lines.append(f"## {ai_insight['insight_title']}")
                lines.append("")
            if ai_insight.get('insight_summary'):
                lines.append(ai_insight['insight_summary'])
                lines.append("")

            # 1. 月度里程碑 (Landmarks)
            if ai_insight.get('landmark_updates'):
                lines.append("### 🌟 月度关键发布 (Landmarks)")
                lines.append("")
                for item in ai_insight['landmark_updates']:
                    vendor = item.get('vendor', 'Unknown')
                    title = item.get('title', '')
                    update_id = item.get('update_id')
                    link = self._build_update_link(update_id) if update_id else ""
                    
                    title_text = f"**[{vendor}] {title}**"
                    if link:
                        lines.append(f"- [{title_text}]({link})")
                    else:
                        lines.append(f"- {title_text}")

                    if item.get('pain_point'):
                        lines.append(f"  - **痛点:** {item.get('pain_point', '')}")
                    if item.get('value'):
                        lines.append(f"  - **价值:** {item.get('value', '')}")
                    lines.append("")

            # 2. 行业洞察 (Solutions)
            if ai_insight.get('solution_analysis'):
                lines.append("### 📚 解决方案洞察 (Solutions)")
                lines.append("")
                for sol in ai_insight['solution_analysis']:
                    theme = sol.get('theme', '')
                    summary = sol.get('summary', '')
                    lines.append(f"- **{theme}**")
                    lines.append(f"  - {summary}")
                    
                    # 引用链接
                    if sol.get('references'):
                        ref_links = []
                        for ref in sol['references']:
                            ref_id = ref.get('update_id')
                            ref_title = ref.get('title', '查看详情')
                            if ref_id:
                                ref_links.append(f"[{ref_title}]({self._build_update_link(ref_id)})")
                        if ref_links:
                            lines.append(f"  - *相关阅读: {' | '.join(ref_links)}*")
                    lines.append("")

            # 3. 其他重要更新 (Noteworthy)
            if ai_insight.get('noteworthy_updates'):
                lines.append("### ⚡️ 其他重要更新 (Noteworthy)")
                lines.append("")
                for group in ai_insight['noteworthy_updates']:
                    vendor = group.get('vendor', 'Unknown')
                    lines.append(f"- **{vendor}**")
                    for item in group.get('items', []):
                        content = item.get('content', '')
                        update_id = item.get('update_id')
                        reason = item.get('reason', '')
                        link = self._build_update_link(update_id) if update_id else None
                        
                        if link:
                            lines.append(f"  - [{content}]({link})")
                        else:
                            lines.append(f"  - {content}")
                        if reason:
                            lines.append(f"    - *{reason}*")
                    lines.append("")
            
            lines.append("---")
            lines.append("")

        self._content = '\n'.join(lines)
        return self._content

    def _save_html_file(self, html_content: str) -> str:
        """保存 HTML 文件"""
        base_dir = os.path.abspath(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        )
        report_dir = os.path.join(base_dir, 'data', 'report', 'monthly')
        os.makedirs(report_dir, exist_ok=True)
        
        filename = f"{self.start_date.strftime('%Y-%m')}.html"
        filepath = os.path.join(report_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"HTML 报告已保存: {filepath}")
        return filepath

    def _save_to_database(self, updates: List[Dict], ai_insight: Dict[str, Any], html_content: str, html_filepath: str):
        """保存到数据库"""
        try:
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

            self._report_repo.save_report(
                report_type='monthly',
                year=self.start_date.year,
                month=self.start_date.month,
                week=None,
                date_from=self.start_date.strftime('%Y-%m-%d'),
                date_to=self.end_date.strftime('%Y-%m-%d'),
                ai_summary=ai_insight,
                vendor_stats=vendor_stats,
                total_count=len(updates),
                html_content=html_content,
                html_filepath=html_filepath
            )
            logger.info(f"月报已保存到数据库")

        except Exception as e:
            logger.error(f"保存月报到数据库失败: {e}")

    def _generate_empty_report(self) -> str:
        """生成空报告"""
        month_str = self.start_date.strftime('%Y年%m月')
        content = f"""# 【云网络竞争动态月报】 {month_str}

汇总本月主要云厂商的技术产品动态，深度剖析竞争态势。

> 本月暂无新的云产品动态更新。
"""
        self._content = content
        return content