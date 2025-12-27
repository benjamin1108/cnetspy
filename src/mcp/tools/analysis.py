#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
高级分析工具

提供产品热度、厂商对比等高级分析能力
"""

from mcp.types import Tool, TextContent

from src.storage.database.sqlite_layer import UpdateDataLayer
from .registry import register_tool


def register_analysis_tools(db: UpdateDataLayer):
    """
    注册高级分析相关的 MCP 工具
    
    Args:
        db: 数据库层实例
    """
    
    # 产品热度排行
    async def get_product_hotness(args: dict) -> list[TextContent]:
        vendor = args.get("vendor")
        date_from = args.get("date_from")
        date_to = args.get("date_to")
        limit = min(args.get("limit", 20), 100)
        include_trend = args.get("include_trend", False)
        
        stats = db.get_product_subcategory_statistics(
            vendor=vendor,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            include_trend=include_trend
        )
        
        response_text = "# 产品热度排行榜\n\n"
        
        if vendor:
            response_text += f"**厂商**: {vendor}\n"
        if date_from or date_to:
            response_text += f"**时间范围**: {date_from or '开始'} ~ {date_to or '至今'}\n"
        response_text += "\n"
        
        if not stats:
            response_text += "暂无数据\n"
        else:
            if include_trend:
                response_text += "| 排名 | 产品 | 更新数 | 环比变化 |\n"
                response_text += "|------|------|--------|----------|\n"
            else:
                response_text += "| 排名 | 产品 | 更新数 |\n"
                response_text += "|------|------|--------|\n"
            
            for i, item in enumerate(stats, 1):
                product = item.get('product_subcategory', '未知')
                count = item.get('count', 0)
                
                if include_trend:
                    trend = item.get('trend', {})
                    change = trend.get('change', 0)
                    pct = trend.get('change_percent', 0)
                    
                    if change > 0:
                        trend_text = f"↑ +{change} ({pct:+.1f}%)"
                    elif change < 0:
                        trend_text = f"↓ {change} ({pct:.1f}%)"
                    else:
                        trend_text = "→ 持平"
                    
                    response_text += f"| {i} | {product} | {count:,} | {trend_text} |\n"
                else:
                    response_text += f"| {i} | {product} | {count:,} |\n"
            
            response_text += f"\n## 洞察\n\n"
            top3 = stats[:3]
            response_text += f"- **最热门产品**: {', '.join(s.get('product_subcategory', '') for s in top3)}\n"
            total = sum(s.get('count', 0) for s in stats)
            top3_total = sum(s.get('count', 0) for s in top3)
            if total > 0:
                response_text += f"- **Top 3 占比**: {top3_total/total:.1%}\n"
        
        return [TextContent(type="text", text=response_text)]
    
    register_tool(
        Tool(
            name="get_product_hotness",
            description="""获取产品热度排行榜。

返回更新数量最多的产品子类排名，可分析：
- 哪些产品正在被频繁更新
- 厂商的产品重点投入方向
- 热门产品的变化趋势

适用于：
- 分析各厂商的产品战略重点
- 发现新兴热门产品
- 对比不同厂商的产品布局""",
            inputSchema={
                "type": "object",
                "properties": {
                    "vendor": {"type": "string", "description": "厂商过滤: aws, azure, gcp, huawei, tencentcloud, volcengine"},
                    "date_from": {"type": "string", "description": "开始日期 (YYYY-MM-DD)"},
                    "date_to": {"type": "string", "description": "结束日期 (YYYY-MM-DD)"},
                    "limit": {"type": "integer", "description": "返回数量，默认20，最大100", "default": 20},
                    "include_trend": {"type": "boolean", "description": "是否包含环比趋势", "default": False}
                }
            }
        ),
        get_product_hotness
    )
    
    # 厂商对比
    async def compare_vendors(args: dict) -> list[TextContent]:
        vendors = args.get("vendors", [])
        date_from = args.get("date_from")
        date_to = args.get("date_to")
        
        if not vendors:
            return [TextContent(type="text", text="错误: 需要提供 vendors 参数")]
        
        response_text = "# 厂商对比分析\n\n"
        response_text += f"**对比厂商**: {', '.join(vendors)}\n"
        if date_from or date_to:
            response_text += f"**时间范围**: {date_from or '开始'} ~ {date_to or '至今'}\n"
        response_text += "\n"
        
        # 1. 更新数量对比
        response_text += "## 1. 更新数量对比\n\n"
        response_text += "| 厂商 | 更新数 | 已分析 | 覆盖率 |\n"
        response_text += "|------|--------|--------|--------|\n"
        
        vendor_data = {}
        stats = db.get_vendor_statistics(date_from=date_from, date_to=date_to)
        for vendor in vendors:
            for stat in stats:
                if stat.get('vendor') == vendor:
                    vendor_data[vendor] = stat
                    count = stat.get('count', 0)
                    analyzed = stat.get('analyzed', 0)
                    rate = f"{analyzed/count:.1%}" if count > 0 else "0%"
                    response_text += f"| {vendor} | {count:,} | {analyzed:,} | {rate} |\n"
                    break
            else:
                vendor_data[vendor] = {'count': 0, 'analyzed': 0}
                response_text += f"| {vendor} | 0 | 0 | 0% |\n"
        
        # 2. 更新类型分布对比
        response_text += "\n## 2. 更新类型分布\n\n"
        
        type_data = {}
        all_types = set()
        
        for vendor in vendors:
            types = db.get_update_type_statistics(vendor=vendor, date_from=date_from, date_to=date_to)
            type_data[vendor] = types
            all_types.update(types.keys())
        
        response_text += "| 更新类型 | " + " | ".join(vendors) + " |\n"
        response_text += "|----------|" + "|".join(["--------"] * len(vendors)) + "|\n"
        
        for update_type in sorted(all_types):
            if update_type:
                row = f"| {update_type} |"
                for vendor in vendors:
                    count = type_data.get(vendor, {}).get(update_type, 0)
                    row += f" {count:,} |"
                response_text += row + "\n"
        
        # 3. 热门产品对比
        response_text += "\n## 3. 热门产品 Top 5\n\n"
        
        for vendor in vendors:
            products = db.get_product_subcategory_statistics(
                vendor=vendor, date_from=date_from, date_to=date_to, limit=5
            )
            
            response_text += f"### {vendor.upper()}\n\n"
            if products:
                for i, p in enumerate(products, 1):
                    response_text += f"{i}. {p.get('product_subcategory', '未知')} ({p.get('count', 0)} 条)\n"
            else:
                response_text += "暂无数据\n"
            response_text += "\n"
        
        # 4. 分析洞察
        response_text += "## 4. 分析洞察\n\n"
        
        sorted_vendors = sorted(
            [(v, vendor_data.get(v, {}).get('count', 0)) for v in vendors],
            key=lambda x: x[1], reverse=True
        )
        
        if sorted_vendors[0][1] > 0:
            response_text += f"- **最活跃厂商**: {sorted_vendors[0][0]} ({sorted_vendors[0][1]:,} 条更新)\n"
        
        for vendor in vendors:
            types = type_data.get(vendor, {})
            if types:
                top_type = max(types.items(), key=lambda x: x[1])
                if top_type[1] > 0:
                    response_text += f"- **{vendor} 主要方向**: {top_type[0] or '未分类'} ({top_type[1]} 条)\n"
        
        return [TextContent(type="text", text=response_text)]
    
    register_tool(
        Tool(
            name="compare_vendors",
            description="""对比多个厂商的更新策略。

分析指定厂商在特定时间段内的：
- 更新数量对比
- 更新类型分布对比
- 热门产品对比
- 活跃度趋势对比

适用于：
- 竞争对手分析
- 多云策略规划
- 行业趋势洞察""",
            inputSchema={
                "type": "object",
                "properties": {
                    "vendors": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要对比的厂商列表，如 ['aws', 'azure', 'gcp']"
                    },
                    "date_from": {"type": "string", "description": "开始日期 (YYYY-MM-DD)"},
                    "date_to": {"type": "string", "description": "结束日期 (YYYY-MM-DD)"}
                },
                "required": ["vendors"]
            }
        ),
        compare_vendors
    )
    
    # 厂商-更新类型矩阵
    async def get_vendor_type_matrix(args: dict) -> list[TextContent]:
        date_from = args.get("date_from")
        date_to = args.get("date_to")
        
        matrix = db.get_vendor_update_type_matrix(date_from=date_from, date_to=date_to)
        
        response_text = "# 厂商-更新类型矩阵\n\n"
        
        if date_from or date_to:
            response_text += f"**时间范围**: {date_from or '开始'} ~ {date_to or '至今'}\n\n"
        
        if not matrix:
            response_text += "暂无数据\n"
        else:
            all_types = set()
            for item in matrix:
                update_types = item.get('update_types', {})
                all_types.update(update_types.keys())
            
            all_types = sorted([t for t in all_types if t])
            
            response_text += "| 厂商 | 总计 | " + " | ".join(all_types[:8]) + " |\n"
            response_text += "|------|------|" + "|".join(["------"] * min(len(all_types), 8)) + "|\n"
            
            for item in matrix:
                vendor = item.get('vendor', 'unknown')
                total = item.get('total', 0)
                update_types = item.get('update_types', {})
                
                row = f"| {vendor} | {total:,} |"
                for t in all_types[:8]:
                    count = update_types.get(t, 0)
                    row += f" {count} |"
                response_text += row + "\n"
            
            response_text += "\n## 策略分析\n\n"
            
            for item in matrix:
                vendor = item.get('vendor')
                update_types = item.get('update_types', {})
                total = item.get('total', 0)
                
                if total > 0:
                    sorted_types = sorted(update_types.items(), key=lambda x: x[1], reverse=True)
                    top_types = [(t, c) for t, c in sorted_types[:3] if c > 0 and t]
                    
                    if top_types:
                        type_summary = ", ".join([f"{t}({c/total:.0%})" for t, c in top_types])
                        response_text += f"- **{vendor}**: {type_summary}\n"
        
        return [TextContent(type="text", text=response_text)]
    
    register_tool(
        Tool(
            name="get_vendor_type_matrix",
            description="""获取厂商-更新类型矩阵。

返回每个厂商的更新类型分布，用于分析：
- 各厂商的产品策略方向（新功能 vs 增强 vs 废弃）
- 安全更新的关注程度
- 区域扩展的力度

适用于：
- 分析厂商战略方向
- 对比产品成熟度
- 评估厂商的技术投入重点""",
            inputSchema={
                "type": "object",
                "properties": {
                    "date_from": {"type": "string", "description": "开始日期 (YYYY-MM-DD)"},
                    "date_to": {"type": "string", "description": "结束日期 (YYYY-MM-DD)"}
                }
            }
        ),
        get_vendor_type_matrix
    )
