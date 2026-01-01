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
            ai_model_config = config.get('ai_model', {})
            # 优先使用报告生成专属配置，否则回退到默认
            ai_config = ai_model_config.get('report_generation', ai_model_config.get('default', {}))
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
            
            # 查询所有已分析的更新 (包含 content 原文)
            cursor.execute('''
                SELECT 
                    update_id, vendor, source_channel, update_type,
                    title, title_translated, content, content_summary, 
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
        
        # 领域统计 (Battleground Data)
        # 结构: { category: { vendor: [updates] } }
        category_battleground = {}
        for u in updates:
            cat = u.get('product_subcategory') or '其他'
            vendor = u['vendor']
            if cat not in category_battleground:
                category_battleground[cat] = {}
            if vendor not in category_battleground[cat]:
                category_battleground[cat][vendor] = []
            category_battleground[cat][vendor].append(u)
        
        # 类别简单统计 (用于图表)
        category_stats = {}
        for cat, vendors in category_battleground.items():
            category_stats[cat] = sum(len(ups) for ups in vendors.values())
        
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
            'category_battleground': category_battleground,
            'top_vendor': top_vendor,
            'top_vendor_count': top_vendor_count,
            'updates': updates
        }
    
    def _get_updates_for_ai(self, stats: Dict[str, Any]) -> Dict[str, str]:
        """
        将数据分为 Feature（产品动作）和 Blog（方案深度）两部分喂给 AI
        包含原始 content 和所有元数据，确保深度洞察的准确性
        """
        updates = stats['updates']
        
        # 1. 提取所有 Blog 数据 (用于解决方案分析)
        blogs = [u for u in updates if u.get('source_channel') == 'blog']
        blogs_simplified = []
        for b in blogs:
            # 彻底取消截断，保留全部原文
            content_raw = b.get('content', '')
                
            blogs_simplified.append({
                'update_id': b['update_id'],
                'vendor': b['vendor'],
                'publish_date': b.get('publish_date', ''),
                'title': b.get('title_translated') or b.get('title', ''),
                'category': b.get('product_subcategory', ''),
                'summary_ai': b.get('content_summary', ''),
                'content_raw': content_raw
            })
        
        # 2. 提取所有 Feature 数据并按领域聚合
        features = [u for u in updates if u.get('source_channel') != 'blog']
        type_weight = {'new_product': 100, 'pricing': 80, 'new_feature': 60, 'enhancement': 40}
        
        battleground = {}
        for u in features:
            cat = u.get('product_subcategory') or '其他'
            if cat not in battleground: battleground[cat] = {}
            if u['vendor'] not in battleground[cat]: battleground[cat][u['vendor']] = []
            battleground[cat][u['vendor']].append(u)
            
        battleground_simplified = {}
        for cat, vendors in battleground.items():
            battleground_simplified[cat] = {}
            for vendor, ups in vendors.items():
                sorted_ups = sorted(ups, key=lambda x: type_weight.get(x.get('update_type'), 0), reverse=True)
                
                ups_data = []
                for u in sorted_ups:
                    content_raw = u.get('content', '')
                        
                    ups_data.append({
                        'update_id': u['update_id'],
                        'vendor': u['vendor'],
                        'update_type': u.get('update_type', ''),
                        'publish_date': u.get('publish_date', ''),
                        'title': u.get('title_translated') or u.get('title', ''),
                        'summary_ai': u.get('content_summary', ''),
                        'content_raw': content_raw
                    })
                battleground_simplified[cat][vendor] = ups_data
                
        return {
            'battleground_json': json.dumps(battleground_simplified, ensure_ascii=False, indent=2),
            'blogs_json': json.dumps(blogs_simplified, ensure_ascii=False, indent=2)
        }
    
    # ==================== AI 认知层 ====================
    
    def _generate_ai_insight(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用 AI 生成 JSON 格式的月度战略洞察 (使用结构化输出)
        """
        default_insight = {
            'insight_title': '月度云竞争战略分析',
            'insight_summary': f"本月监测到 {stats['total_count']} 条更新。",
            'landmark_updates': [],
            'noteworthy_updates': [],
            'featured_blogs': [],
            'solution_analysis': []
        }
        
        if not self._gemini or stats['total_count'] < 5:
            return default_insight
        
        # 定义结构化输出 Schema
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
                            "title": {"type": "string"},
                            "product": {"type": "string"},
                            "pain_point": {"type": "string"},
                            "value": {"type": "string"},
                            "comment": {"type": "string"}
                        },
                        "required": ["update_id", "vendor", "title", "product", "pain_point", "value", "comment"]
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
                },
                "featured_blogs": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "update_id": {"type": "string"},
                            "vendor": {"type": "string"},
                            "title": {"type": "string"},
                            "reason": {"type": "string"}
                        },
                        "required": ["update_id", "vendor", "title", "reason"]
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
                        "required": ["theme", "summary"]
                    }
                }
            },
            "required": ["insight_title", "insight_summary", "landmark_updates", "noteworthy_updates", "featured_blogs", "solution_analysis"]
        }

        try:
            prompt_file = os.path.join(PROMPT_DIR, 'monthly_insight.prompt.txt')
            with open(prompt_file, 'r', encoding='utf-8') as f:
                prompt_template = f.read()
            
            # 准备结构化数据
            ai_data = self._get_updates_for_ai(stats)
            
            # 替换变量
            prompt = prompt_template.replace('{month_str}', self.start_date.strftime('%Y年%m月'))
            prompt = prompt.replace('{total_count}', str(stats['total_count']))
            prompt = prompt.replace('{battleground_json}', ai_data['battleground_json'])
            prompt = prompt.replace('{blogs_json}', ai_data['blogs_json'])
            
            # 调用 AI (启用 Structured Output)
            logger.info("调用 Gemini-3-Pro 生成月度深度洞察 (结构化模式)...")
            response = self._gemini.generate_text(
                prompt, 
                response_mime_type="application/json",
                response_schema=monthly_report_schema
            )
            
            # 解析 JSON
            result = json.loads(response.strip())
            return result
            
        except Exception as e:
            logger.error(f"月报 AI 洞察生成失败: {e}")
            return default_insight
            
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
        组装完整的 HTML 月报
        """
        # 加载模板
        template_file = os.path.join(TEMPLATE_DIR, 'monthly_report.html')
        with open(template_file, 'r', encoding='utf-8') as f:
            template = f.read()
        
        # 标题：如果截止日不是月末，标注截止日期
        month_str = self.start_date.strftime('%Y年%m月')
        if self.end_date.day < 28:
            month_str += f"（截止{self.end_date.strftime('%m月%d日')}）"
        
        date_range = f"{self.start_date.strftime('%Y-%m-%d')} 至 {self.end_date.strftime('%Y-%m-%d')}"
        
        # 1. Landmark Updates HTML
        landmark_updates_html = ''
        if insight.get('landmark_updates'):
            for i, item in enumerate(insight['landmark_updates']):
                vendor = item.get('vendor', 'Unknown')
                vendor_slug = vendor.lower()
                title = escape(item.get('title', ''))
                impact = escape(item.get('impact', ''))
                update_id = item.get('update_id', '')
                link = f"{SITE_BASE_URL}/updates/{update_id}" if update_id else "#"
                
                landmark_updates_html += f'''
<div class="landmark-card">
    <div class="landmark-number">0{i+1}</div>
    <div style="margin-bottom: 12px;">
        <span class="badge badge-{vendor_slug}">{vendor}</span>
    </div>
    <h5 style="margin: 0 0 12px 0; font-size: 1.1rem; font-weight: 700;">
        <a href="{link}" style="color: inherit; text-decoration: none;">{title}</a>
    </h5>
    <div class="landmark-impact">“{impact}”</div>
</div>
'''

        # 2. Battleground HTML
        battleground_html = ''
        if insight.get('battleground_analysis'):
            for bg in insight['battleground_analysis']:
                cat = escape(bg.get('category', ''))
                summary = escape(bg.get('summary', ''))
                
                battleground_html += f'''
<div class="battleground-row">
    <div class="battleground-cat">{cat}</div>
    <div class="battleground-summary">{summary}</div>
</div>
'''

        # 3. Featured Blogs HTML (必读好文)
        featured_blogs_html = ""
        if insight.get('featured_blogs'):
            for blog in insight['featured_blogs']:
                vendor = blog.get('vendor', 'Unknown')
                vendor_slug = vendor.lower()
                update_id = blog.get('update_id')
                link = f"{SITE_BASE_URL}/updates/{update_id}" if update_id else "#"
                
                featured_blogs_html += f'''
<div class="glass-card p-6 rounded-2xl border-l-4 border-l-{vendor_slug if vendor_slug in ['aws', 'azure'] else 'primary'}">
    <div class="flex justify-between items-start mb-2">
        <span class="badge badge-{vendor_slug}">{vendor}</span>
    </div>
    <h5 class="text-lg font-bold mb-2">
        <a href="{link}" target="_blank" class="hover:text-primary transition">{escape(blog.get('title', ''))}</a>
    </h5>
    <p class="text-sm text-muted italic">“{escape(blog.get('reason', ''))}”</p>
</div>
'''
        
        # 替换模板变量
        html = template
        html = html.replace('{{report_month}}', month_str)
        html = html.replace('{{date_range}}', date_range)
        html = html.replace('{{insight_title}}', escape(insight.get('insight_title', '')))
        html = html.replace('{{insight_summary}}', escape(insight.get('insight_summary', '')))

        # 处理条件块
        if landmark_updates_html:
            html = html.replace('{{landmark_updates_html}}', landmark_updates_html)
            html = html.replace('{{#if landmark_updates_html}}', '').replace('{{/if}}', '')
        else:
            html = re.sub(r'{{#if landmark_updates_html}}.*?{{/if}}', '', html, flags=re.DOTALL)

        if battleground_html:
            html = html.replace('{{battleground_html}}', battleground_html)
            html = html.replace('{{#if battleground_html}}', '').replace('{{/if}}', '')
        else:
            html = re.sub(r'{{#if battleground_html}}.*?{{/if}}', '', html, flags=re.DOTALL)

        if featured_blogs_html:
            html = html.replace('{{featured_blogs_html}}', featured_blogs_html)
            html = html.replace('{{#if featured_blogs_html}}', '').replace('{{/if}}', '')
        else:
            html = re.sub(r'{{#if featured_blogs_html}}.*?{{/if}}', '', html, flags=re.DOTALL)
        
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
