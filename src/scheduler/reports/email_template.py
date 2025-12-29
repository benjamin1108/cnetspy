#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
每日任务报告 HTML 邮件模板生成器
"""

from typing import Dict, Any, List
from datetime import datetime


# 厂商名称映射
VENDOR_NAMES = {
    'aws': 'AWS',
    'azure': 'Azure',
    'gcp': 'GCP',
    'huawei': '华为云',
    'tencentcloud': '腾讯云',
    'volcengine': '火山引擎'
}

# 厂商顺序
VENDOR_ORDER = ['aws', 'azure', 'gcp', 'huawei', 'tencentcloud', 'volcengine']


def generate_daily_report_html(
    task_date: str,
    start_time: str,
    end_time: str,
    duration_seconds: int,
    status: str,
    crawl_stats: Dict[str, Dict[str, int]],
    crawl_total: int,
    crawl_discovered: int = 0,
    crawl_skipped: int = 0,
    analyze_success: int = 0,
    analyze_failed: int = 0,
    marked_non_network: int = 0,
    missing_subcategory: int = 0,
    non_network_items: List[Dict[str, str]] = None,
    missing_subcat_items: List[Dict[str, str]] = None,
    failed_items: List[Dict[str, str]] = None
) -> str:
    """
    生成每日任务报告 HTML
    
    Returns:
        HTML 字符串
    """
    # 格式化时间
    duration_min = duration_seconds // 60
    duration_sec = duration_seconds % 60
    duration_str = f"{duration_min}分{duration_sec}秒" if duration_min > 0 else f"{duration_sec}秒"
    
    # 状态标识
    status_map = {
        'success': ('✅ 成功', '#22543d', '#f0fff4'),
        'partial_fail': ('⚠️ 部分异常', '#744210', '#fffaf0'),
        'failed': ('❌ 失败', '#742a2a', '#fff5f5')
    }
    status_text, status_color, status_bg = status_map.get(status, ('⏳ 进行中', '#4a5568', '#f7fafc'))
    
    # 生成爬取统计表格行
    crawl_rows = []
    source_types = set()
    for vendor_stats in crawl_stats.values():
        source_types.update(vendor_stats.keys())
    source_types = sorted(list(source_types))
    
    totals = {st: 0 for st in source_types}
    
    for i, vendor in enumerate(VENDOR_ORDER):
        if vendor not in crawl_stats:
            continue
        
        vendor_data = crawl_stats[vendor]
        row_bg = '#f7fafc' if i % 2 == 1 else '#ffffff'
        
        cells = [f'<td style="padding:10px 12px; border-top:1px solid #e2e8f0; color:#2d3748; background:{row_bg};">{VENDOR_NAMES.get(vendor, vendor)}</td>']
        
        vendor_total = 0
        for st in source_types:
            count = vendor_data.get(st, 0)
            vendor_total += count
            totals[st] += count
            cell_val = str(count) if count > 0 else '-'
            color = '#4A90E2' if count > 0 else '#a0aec0'
            cells.append(f'<td style="padding:10px 12px; border-top:1px solid #e2e8f0; text-align:center; color:{color}; background:{row_bg};">{cell_val}</td>')
        
        cells.append(f'<td style="padding:10px 12px; border-top:1px solid #e2e8f0; text-align:right; font-weight:600; background:{row_bg};">{vendor_total}</td>')
        
        crawl_rows.append('<tr>' + ''.join(cells) + '</tr>')
    
    # 表头
    header_cells = ['<th style="padding:12px; text-align:left; color:#4a5568; font-size:13px; font-weight:600;">厂商</th>']
    for st in source_types:
        header_cells.append(f'<th style="padding:12px; text-align:center; color:#4a5568; font-size:13px; font-weight:600;">{st}</th>')
    header_cells.append('<th style="padding:12px; text-align:right; color:#4a5568; font-size:13px; font-weight:600;">小计</th>')
    
    # 合计行
    total_cells = ['<td style="padding:10px 12px; color:#fff; font-weight:600;">合计</td>']
    for st in source_types:
        total_cells.append(f'<td style="padding:10px 12px; text-align:center; color:#fff; font-weight:600;">{totals[st]}</td>')
    total_cells.append(f'<td style="padding:10px 12px; text-align:right; color:#fff; font-weight:700;">{crawl_total}</td>')
    
    # 生成问题项 HTML
    issues_html = ""
    
    if non_network_items:
        items_html = _generate_issue_items(non_network_items, '#c05621', '#744210')
        issues_html += f'''
        <div style="background:#fffaf0; border:1px solid #fbd38d; border-radius:8px; padding:16px; margin-bottom:12px;">
            <div style="color:#c05621; font-weight:600; margin-bottom:8px;">非网络相关 ({len(non_network_items)}条)</div>
            {items_html}
        </div>
        '''
    
    if missing_subcat_items:
        items_html = _generate_issue_items(missing_subcat_items, '#2b6cb0', '#2c5282')
        issues_html += f'''
        <div style="background:#ebf8ff; border:1px solid #90cdf4; border-radius:8px; padding:16px; margin-bottom:12px;">
            <div style="color:#2b6cb0; font-weight:600; margin-bottom:8px;">无产品分类 ({len(missing_subcat_items)}条)</div>
            {items_html}
        </div>
        '''
    
    if failed_items:
        items_html = _generate_issue_items(failed_items, '#c53030', '#742a2a', show_reason=True)
        issues_html += f'''
        <div style="background:#fff5f5; border:1px solid #feb2b2; border-radius:8px; padding:16px;">
            <div style="color:#c53030; font-weight:600; margin-bottom:8px;">分析失败 ({len(failed_items)}条)</div>
            {items_html}
        </div>
        '''
    
    # 如果没有问题项
    if not issues_html:
        issues_html = '''
        <div style="background:#f0fff4; border:1px solid #9ae6b4; border-radius:8px; padding:16px; text-align:center;">
            <span style="color:#22543d; font-size:14px;">✅ 本次任务无异常项</span>
        </div>
        '''
    
    # 组装完整 HTML
    html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:0; background-color:#f0f4f8; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;">

<table width="100%" cellpadding="0" cellspacing="0" style="max-width:640px; margin:20px auto; background:#ffffff; border-radius:12px; box-shadow:0 4px 6px rgba(0,0,0,0.1);">
    
    <!-- 头部 -->
    <tr>
        <td style="background:linear-gradient(135deg,#4A90E2 0%,#13B5EA 100%); padding:24px 32px; border-radius:12px 12px 0 0;">
            <h1 style="margin:0; color:#ffffff; font-size:22px; font-weight:600;">
                📊 CloudNetSpy每日分析日志
            </h1>
            <p style="margin:8px 0 0; color:rgba(255,255,255,0.9); font-size:14px;">
                {task_date} · {start_time} ~ {end_time} · 耗时 {duration_str}
            </p>
            <p style="margin:6px 0 0;">
                <span style="display:inline-block; background:{status_bg}; color:{status_color}; padding:4px 12px; border-radius:12px; font-size:12px; font-weight:600;">
                    {status_text}
                </span>
            </p>
        </td>
    </tr>
    
    <!-- 爬取统计 -->
    <tr>
        <td style="padding:24px 32px;">
            <h2 style="margin:0 0 16px; color:#1a365d; font-size:16px; font-weight:600; border-left:4px solid #4A90E2; padding-left:12px;">
                🕷️ 爬取统计
            </h2>
            <!-- 爬取汇总 -->
            <div style="display:flex; gap:12px; margin-bottom:16px;">
                <div style="flex:1; background:#f7fafc; border-radius:8px; padding:12px; text-align:center;">
                    <div style="color:#4A90E2; font-size:24px; font-weight:700;">{crawl_discovered}</div>
                    <div style="color:#718096; font-size:12px;">🔍 发现总数</div>
                </div>
                <div style="flex:1; background:#f7fafc; border-radius:8px; padding:12px; text-align:center;">
                    <div style="color:#a0aec0; font-size:24px; font-weight:700;">{crawl_skipped}</div>
                    <div style="color:#718096; font-size:12px;">⏭️ 跳过(已存在)</div>
                </div>
                <div style="flex:1; background:#f0fff4; border-radius:8px; padding:12px; text-align:center;">
                    <div style="color:#22543d; font-size:24px; font-weight:700;">{crawl_total}</div>
                    <div style="color:#48bb78; font-size:12px;">✅ 新增保存</div>
                </div>
            </div>
            <!-- 分厂商统计表格 -->
            <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e2e8f0; border-radius:8px; overflow:hidden;">
                <tr style="background:#f7fafc;">
                    {''.join(header_cells)}
                </tr>
                {''.join(crawl_rows)}
                <tr style="background:#4A90E2;">
                    {''.join(total_cells)}
                </tr>
            </table>
        </td>
    </tr>
    
    <!-- AI 分析统计 -->
    <tr>
        <td style="padding:0 32px 24px;">
            <h2 style="margin:0 0 16px; color:#1a365d; font-size:16px; font-weight:600; border-left:4px solid #13B5EA; padding-left:12px;">
                🤖 AI 分析统计
            </h2>
            <table width="100%" cellpadding="0" cellspacing="8" style="border-spacing:8px;">
                <tr>
                    <td style="padding:16px; background:#f0fff4; border-radius:8px; text-align:center; width:50%;">
                        <div style="color:#22543d; font-size:28px; font-weight:700;">{analyze_success}</div>
                        <div style="color:#48bb78; font-size:13px; margin-top:4px;">✅ 分析成功</div>
                    </td>
                    <td style="padding:16px; background:#fff5f5; border-radius:8px; text-align:center; width:50%;">
                        <div style="color:#742a2a; font-size:28px; font-weight:700;">{analyze_failed}</div>
                        <div style="color:#fc8181; font-size:13px; margin-top:4px;">❌ 分析失败</div>
                    </td>
                </tr>
            </table>
        </td>
    </tr>
    
    <!-- 需关注项 -->
    <tr>
        <td style="padding:0 32px 24px;">
            <h2 style="margin:0 0 16px; color:#1a365d; font-size:16px; font-weight:600; border-left:4px solid #ed8936; padding-left:12px;">
                ⚠️ 需关注项
            </h2>
            {issues_html}
        </td>
    </tr>
    
    <!-- 页脚 -->
    <tr>
        <td style="padding:20px 32px; background:#f7fafc; border-radius:0 0 12px 12px; text-align:center;">
            <p style="margin:0; color:#a0aec0; font-size:12px;">
                此报告由 云网动态分析系统 自动生成
            </p>
        </td>
    </tr>
    
</table>

</body>
</html>'''
    
    return html


def _generate_issue_items(items: List[Dict[str, str]], title_color: str, text_color: str, show_reason: bool = False) -> str:
    """生成问题项列表 HTML"""
    rows = []
    for item in items[:10]:  # 最多显示10条
        vendor = VENDOR_NAMES.get(item.get('vendor', ''), item.get('vendor', ''))
        title = item.get('title', '')[:50]  # 截断过长标题
        update_id = item.get('update_id', '')
        
        row = f'''
        <div style="padding:8px 0; border-bottom:1px solid rgba(0,0,0,0.05);">
            <div style="color:{text_color}; font-size:13px;">
                <strong>{vendor}</strong> · {title}
            </div>
            <div style="color:#a0aec0; font-size:11px; margin-top:2px;">
                ID: {update_id}
            </div>
        '''
        
        if show_reason and item.get('reason'):
            row += f'''
            <div style="color:#e53e3e; font-size:11px; margin-top:2px;">
                原因: {item['reason'][:50]}
            </div>
            '''
        
        row += '</div>'
        rows.append(row)
    
    if len(items) > 10:
        rows.append(f'<div style="color:#a0aec0; font-size:12px; padding:8px 0;">... 还有 {len(items) - 10} 条</div>')
    
    return ''.join(rows)
