#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
统计分析工具

提供云厂商更新的统计和趋势分析能力
"""

from mcp.types import Tool, TextContent

from src.storage.database.sqlite_layer import UpdateDataLayer
from .registry import register_tool


def register_stats_tools(db: UpdateDataLayer):
    """
    注册统计分析相关的 MCP 工具
    
    Args:
        db: 数据库层实例
    """
    
    # 全局统计概览
    async def get_stats_overview(args: dict) -> list[TextContent]:
        total = db.count_updates()
        vendor_stats = db.get_vendor_statistics()
        type_stats = db.get_update_type_statistics()
        coverage = db.get_analysis_coverage()
        
        response_text = "# 系统统计概览\n\n"
        response_text += f"## 总体数据\n\n"
        response_text += f"- **更新总数**: {total:,} 条\n"
        response_text += f"- **分析覆盖率**: {coverage:.1%}\n\n"
        
        response_text += f"## 厂商分布\n\n"
        response_text += "| 厂商 | 更新数 | 已分析 | 覆盖率 |\n"
        response_text += "|------|--------|--------|--------|\n"
        
        for stat in vendor_stats:
            vendor = stat.get('vendor', 'unknown')
            count = stat.get('count', 0)
            analyzed = stat.get('analyzed', 0)
            rate = f"{analyzed/count:.1%}" if count > 0 else "0%"
            response_text += f"| {vendor} | {count:,} | {analyzed:,} | {rate} |\n"
        
        response_text += f"\n## 更新类型分布\n\n"
        if type_stats:
            response_text += "| 类型 | 数量 |\n"
            response_text += "|------|------|\n"
            for update_type, count in sorted(type_stats.items(), key=lambda x: x[1], reverse=True):
                if count > 0:
                    response_text += f"| {update_type or '未分类'} | {count:,} |\n"
        
        return [TextContent(type="text", text=response_text)]
    
    register_tool(
        Tool(
            name="get_stats_overview",
            description="""获取系统全局统计概览。

返回整体统计数据：
- 更新总数
- 各厂商更新数量和分析覆盖率
- 更新类型分布
- 最后爬取时间

适用于：
- 了解系统当前数据规模
- 快速获取各厂商数据量对比
- 检查数据时效性""",
            inputSchema={"type": "object", "properties": {}}
        ),
        get_stats_overview
    )
    
    # 时间线统计
    async def get_timeline(args: dict) -> list[TextContent]:
        granularity = args.get("granularity", "month")
        date_from = args.get("date_from")
        date_to = args.get("date_to")
        vendor = args.get("vendor")
        
        if granularity not in ['day', 'week', 'month', 'year']:
            granularity = 'month'
        
        timeline = db.get_timeline_statistics(
            granularity=granularity,
            date_from=date_from,
            date_to=date_to,
            vendor=vendor
        )
        
        granularity_label = {'day': '日', 'week': '周', 'month': '月', 'year': '年'}.get(granularity, '月')
        
        response_text = f"# 更新时间线统计（按{granularity_label}）\n\n"
        
        if vendor:
            response_text += f"**厂商筛选**: {vendor}\n\n"
        if date_from or date_to:
            response_text += f"**时间范围**: {date_from or '开始'} ~ {date_to or '至今'}\n\n"
        
        if not timeline:
            response_text += "暂无数据\n"
        else:
            response_text += "| 时间 | 更新数 |\n"
            response_text += "|------|--------|\n"
            
            for item in timeline:
                date = item.get('date', '')
                count = item.get('count', 0)
                response_text += f"| {date} | {count:,} |\n"
            
            total = sum(item.get('count', 0) for item in timeline)
            avg = total / len(timeline) if timeline else 0
            max_item = max(timeline, key=lambda x: x.get('count', 0)) if timeline else {}
            min_item = min(timeline, key=lambda x: x.get('count', 0)) if timeline else {}
            
            response_text += f"\n## 统计摘要\n\n"
            response_text += f"- **总计**: {total:,} 条\n"
            response_text += f"- **平均**: {avg:.1f} 条/{granularity_label}\n"
            response_text += f"- **最高**: {max_item.get('date', '')} ({max_item.get('count', 0):,} 条)\n"
            response_text += f"- **最低**: {min_item.get('date', '')} ({min_item.get('count', 0):,} 条)\n"
        
        return [TextContent(type="text", text=response_text)]
    
    register_tool(
        Tool(
            name="get_timeline",
            description="""获取更新时间线统计。

按时间维度统计更新数量，支持不同粒度：
- day: 按天统计
- week: 按周统计  
- month: 按月统计
- year: 按年统计

适用于：
- 分析更新发布频率趋势
- 对比不同时期的活跃度
- 发现周期性规律""",
            inputSchema={
                "type": "object",
                "properties": {
                    "granularity": {
                        "type": "string",
                        "description": "统计粒度: day, week, month, year",
                        "enum": ["day", "week", "month", "year"],
                        "default": "month"
                    },
                    "date_from": {"type": "string", "description": "开始日期 (YYYY-MM-DD)"},
                    "date_to": {"type": "string", "description": "结束日期 (YYYY-MM-DD)"},
                    "vendor": {"type": "string", "description": "厂商过滤"}
                }
            }
        ),
        get_timeline
    )
    
    # 厂商统计
    async def get_vendor_stats(args: dict) -> list[TextContent]:
        date_from = args.get("date_from")
        date_to = args.get("date_to")
        include_trend = args.get("include_trend", False)
        
        stats = db.get_vendor_statistics(
            date_from=date_from,
            date_to=date_to,
            include_trend=include_trend
        )
        
        response_text = "# 厂商统计对比\n\n"
        
        if date_from or date_to:
            response_text += f"**时间范围**: {date_from or '开始'} ~ {date_to or '至今'}\n\n"
        
        if not stats:
            response_text += "暂无数据\n"
        else:
            if include_trend:
                response_text += "| 厂商 | 更新数 | 已分析 | 覆盖率 | 环比变化 |\n"
                response_text += "|------|--------|--------|--------|----------|\n"
            else:
                response_text += "| 厂商 | 更新数 | 已分析 | 覆盖率 |\n"
                response_text += "|------|--------|--------|--------|\n"
            
            total_count = 0
            total_analyzed = 0
            
            for stat in stats:
                vendor = stat.get('vendor', 'unknown')
                count = stat.get('count', 0)
                analyzed = stat.get('analyzed', 0)
                rate = f"{analyzed/count:.1%}" if count > 0 else "0%"
                
                total_count += count
                total_analyzed += analyzed
                
                if include_trend:
                    trend = stat.get('trend', {})
                    change = trend.get('change', 0)
                    trend_text = f"+{change}" if change > 0 else str(change)
                    response_text += f"| {vendor} | {count:,} | {analyzed:,} | {rate} | {trend_text} |\n"
                else:
                    response_text += f"| {vendor} | {count:,} | {analyzed:,} | {rate} |\n"
            
            response_text += f"\n## 汇总\n\n"
            response_text += f"- **厂商数**: {len(stats)}\n"
            response_text += f"- **总更新数**: {total_count:,}\n"
            response_text += f"- **总分析数**: {total_analyzed:,}\n"
            if total_count > 0:
                response_text += f"- **整体覆盖率**: {total_analyzed/total_count:.1%}\n"
        
        return [TextContent(type="text", text=response_text)]
    
    register_tool(
        Tool(
            name="get_vendor_stats",
            description="""获取各厂商统计数据。

返回每个厂商的：
- 更新总数
- 已分析数量
- 分析覆盖率
- 环比趋势（可选）

适用于：
- 厂商间数据量对比
- 分析覆盖率对比
- 发现活跃/沉寂的厂商""",
            inputSchema={
                "type": "object",
                "properties": {
                    "date_from": {"type": "string", "description": "开始日期 (YYYY-MM-DD)"},
                    "date_to": {"type": "string", "description": "结束日期 (YYYY-MM-DD)"},
                    "include_trend": {"type": "boolean", "description": "是否包含环比趋势数据", "default": False}
                }
            }
        ),
        get_vendor_stats
    )
    
    # 更新类型统计
    async def get_update_type_stats(args: dict) -> list[TextContent]:
        vendor = args.get("vendor")
        date_from = args.get("date_from")
        date_to = args.get("date_to")
        
        stats = db.get_update_type_statistics(
            vendor=vendor,
            date_from=date_from,
            date_to=date_to
        )
        
        response_text = "# 更新类型分布\n\n"
        
        if vendor:
            response_text += f"**厂商**: {vendor}\n"
        if date_from or date_to:
            response_text += f"**时间范围**: {date_from or '开始'} ~ {date_to or '至今'}\n"
        response_text += "\n"
        
        if not stats:
            response_text += "暂无数据\n"
        else:
            total = sum(stats.values())
            
            response_text += "| 更新类型 | 数量 | 占比 |\n"
            response_text += "|----------|------|------|\n"
            
            for update_type, count in sorted(stats.items(), key=lambda x: x[1], reverse=True):
                if count > 0:
                    pct = f"{count/total:.1%}" if total > 0 else "0%"
                    type_label = update_type or '未分类'
                    response_text += f"| {type_label} | {count:,} | {pct} |\n"
            
            response_text += f"\n**总计**: {total:,} 条更新\n"
        
        return [TextContent(type="text", text=response_text)]
    
    register_tool(
        Tool(
            name="get_update_type_stats",
            description="""获取更新类型分布统计。

返回各更新类型的数量：
- new_feature: 新功能
- enhancement: 功能增强
- deprecation: 功能废弃
- security: 安全更新
- pricing: 价格变更
- region: 区域扩展

适用于：
- 分析厂商的产品策略方向
- 对比不同厂商的更新类型偏好
- 发现安全/废弃等重要更新""",
            inputSchema={
                "type": "object",
                "properties": {
                    "vendor": {"type": "string", "description": "厂商过滤"},
                    "date_from": {"type": "string", "description": "开始日期 (YYYY-MM-DD)"},
                    "date_to": {"type": "string", "description": "结束日期 (YYYY-MM-DD)"}
                }
            }
        ),
        get_update_type_stats
    )
