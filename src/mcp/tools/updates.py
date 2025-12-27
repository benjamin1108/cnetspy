#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
更新数据查询工具

提供云厂商更新的搜索和详情查询能力
"""

import json
from mcp.types import Tool, TextContent

from src.storage.database.sqlite_layer import UpdateDataLayer
from .registry import register_tool


def register_update_tools(db: UpdateDataLayer):
    """
    注册更新数据相关的 MCP 工具
    
    Args:
        db: 数据库层实例
    """
    
    # 搜索更新工具
    async def search_updates(args: dict) -> list[TextContent]:
        """执行更新搜索"""
        filters = {}
        
        if args.get("vendor"):
            filters["vendor"] = args["vendor"]
        if args.get("keyword"):
            filters["keyword"] = args["keyword"]
        if args.get("date_from"):
            filters["date_from"] = args["date_from"]
        if args.get("date_to"):
            filters["date_to"] = args["date_to"]
        if args.get("update_type"):
            filters["update_type"] = args["update_type"]
        if args.get("product_name"):
            filters["product_name"] = args["product_name"]
        if args.get("subcategory"):
            filters["subcategory"] = args["subcategory"]
        
        limit = min(args.get("limit", 20), 100)
        
        # 查询数据库
        rows = db.query_updates_paginated(
            filters=filters,
            limit=limit,
            offset=0,
            sort_by="publish_date",
            order="desc"
        )
        
        # 格式化结果
        results = []
        for row in rows:
            tags = []
            if row.get('tags'):
                try:
                    tags = json.loads(row['tags'])
                except (json.JSONDecodeError, TypeError):
                    tags = []
            
            results.append({
                "update_id": row.get("update_id"),
                "vendor": row.get("vendor"),
                "title": row.get("title"),
                "title_translated": row.get("title_translated"),
                "publish_date": row.get("publish_date"),
                "update_type": row.get("update_type"),
                "product_name": row.get("product_name"),
                "subcategory": row.get("subcategory"),
                "tags": tags,
                "summary_zh": row.get("summary_zh") or row.get("content_summary") or ""
            })
        
        # 构建响应
        if not results:
            response_text = "未找到匹配的更新记录。\n\n"
            response_text += f"搜索条件: {json.dumps(filters, ensure_ascii=False, indent=2)}"
        else:
            response_text = f"找到 {len(results)} 条更新记录：\n\n"
            for i, item in enumerate(results, 1):
                title = item['title_translated'] or item['title']
                response_text += f"### {i}. {title}\n"
                response_text += f"- **update_id**: `{item['update_id']}`\n"
                response_text += f"- **厂商**: {item['vendor']}\n"
                response_text += f"- **日期**: {item['publish_date']}\n"
                response_text += f"- **类型**: {item['update_type'] or '未分类'}\n"
                response_text += f"- **产品**: {item['subcategory'] or item['product_name'] or '未知'}\n"
                if item['tags']:
                    response_text += f"- **标签**: {', '.join(item['tags'][:5])}\n"
                if item['summary_zh']:
                    summary = item['summary_zh'][:200] + '...' if len(item['summary_zh']) > 200 else item['summary_zh']
                    response_text += f"- **摘要**: {summary}\n"
                response_text += "\n"
        
        return [TextContent(type="text", text=response_text)]
    
    register_tool(
        Tool(
            name="search_updates",
            description="""搜索云厂商更新信息。

可搜索 AWS、Azure、GCP、华为云、腾讯云、火山引擎等厂商的产品更新。
支持按厂商、日期范围、关键词、更新类型、产品子类等条件过滤。

返回匹配的更新列表，包含标题、日期、厂商、更新类型、摘要等信息。
适用于：
- 查找某厂商最近的更新
- 搜索特定产品或功能的更新
- 按产品子类过滤（如 Google Cloud VPC, Amazon VPC）""",
            inputSchema={
                "type": "object",
                "properties": {
                    "vendor": {
                        "type": "string",
                        "description": "厂商标识: aws, azure, gcp, huawei, tencentcloud, volcengine",
                        "enum": ["aws", "azure", "gcp", "huawei", "tencentcloud", "volcengine"]
                    },
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词，匹配标题和内容"
                    },
                    "subcategory": {
                        "type": "string",
                        "description": "产品子类名称，如 Google Cloud VPC, Amazon VPC"
                    },
                    "date_from": {
                        "type": "string",
                        "description": "开始日期 (YYYY-MM-DD)"
                    },
                    "date_to": {
                        "type": "string",
                        "description": "结束日期 (YYYY-MM-DD)"
                    },
                    "update_type": {
                        "type": "string",
                        "description": "更新类型: new_feature, enhancement, deprecation, security, pricing, region 等"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回结果数量限制，默认20，最大100",
                        "default": 20
                    }
                }
            }
        ),
        search_updates
    )
    
    # 获取更新详情工具
    async def get_update_detail(args: dict) -> list[TextContent]:
        """获取更新详情"""
        update_id = args.get("update_id")
        if not update_id:
            return [TextContent(type="text", text="错误: 需要提供 update_id 参数")]
        
        row = db.get_update_by_id(update_id)
        
        if not row:
            return [TextContent(type="text", text=f"未找到更新记录: {update_id}")]
        
        tags = []
        if row.get('tags'):
            try:
                tags = json.loads(row['tags'])
            except (json.JSONDecodeError, TypeError):
                tags = []
        
        response_text = f"# {row.get('title_translated') or row.get('title')}\n\n"
        response_text += f"**原始标题**: {row.get('title')}\n\n"
        response_text += f"## 基本信息\n\n"
        response_text += f"| 属性 | 值 |\n|------|------|\n"
        response_text += f"| update_id | `{row.get('update_id')}` |\n"
        response_text += f"| 厂商 | {row.get('vendor')} |\n"
        response_text += f"| 来源 | {row.get('source_channel')} |\n"
        response_text += f"| 发布日期 | {row.get('publish_date')} |\n"
        response_text += f"| 更新类型 | {row.get('update_type') or '未分类'} |\n"
        response_text += f"| 产品子类 | {row.get('subcategory') or '未知'} |\n"
        
        if tags:
            response_text += f"| 标签 | {', '.join(tags)} |\n"
        
        response_text += f"| 来源链接 | {row.get('source_url')} |\n\n"
        
        # 中文摘要
        if row.get('summary_zh'):
            response_text += f"## 中文摘要\n\n{row.get('summary_zh')}\n\n"
        
        # AI 摘要
        if row.get('content_summary'):
            response_text += f"## AI 分析摘要\n\n{row.get('content_summary')}\n\n"
        
        # 完整内容
        content = row.get('content', '')
        if content:
            response_text += f"## 完整内容\n\n{content}\n"
        
        return [TextContent(type="text", text=response_text)]
    
    register_tool(
        Tool(
            name="get_update_detail",
            description="""获取单条更新的完整详情。

返回更新的完整信息，包括：
- 原始标题和中文翻译
- 完整内容和AI摘要
- 产品分类和标签
- 发布日期和来源链接

适用于：
- 深入了解某条更新的具体内容
- 获取更新的AI分析结果
- 查看原文链接""",
            inputSchema={
                "type": "object",
                "properties": {
                    "update_id": {
                        "type": "string",
                        "description": "更新记录的唯一标识符"
                    }
                },
                "required": ["update_id"]
            }
        ),
        get_update_detail
    )
