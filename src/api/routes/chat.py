#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Chat API 路由
提供 AI 对话功能
"""

import json
import os
import logging
import re
import calendar
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import List, Optional, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

from ..config import settings
from src.utils.config import get_config
from src.storage.database.sqlite_layer import UpdateDataLayer
from src.mcp.tools import (
    register_update_tools,
    register_stats_tools,
    register_analysis_tools,
)
from src.mcp.tools.registry import get_all_tools, get_handler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])


class ChatMessage(BaseModel):
    """聊天消息"""
    role: str = Field(..., description="消息角色: system/user/assistant")
    content: str = Field(..., description="消息内容")


class ToolFunction(BaseModel):
    """工具函数定义"""
    name: str
    description: str
    parameters: dict = Field(default_factory=dict)


class Tool(BaseModel):
    """工具定义"""
    type: str = "function"
    function: ToolFunction


class ChatRequest(BaseModel):
    """聊天请求"""
    messages: List[ChatMessage] = Field(..., description="消息历史")
    tools: Optional[List[Tool]] = Field(default=None, description="可用工具列表")
    model: Optional[str] = Field(default=None, description="模型名称")
    temperature: Optional[float] = Field(default=0.7, ge=0, le=1)
    max_tokens: Optional[int] = Field(default=4096, ge=1)


class ToolCallFunction(BaseModel):
    """工具调用函数"""
    name: str
    arguments: str


class ToolCall(BaseModel):
    """工具调用"""
    id: str
    type: str = "function"
    function: ToolCallFunction


class ChatChoice(BaseModel):
    """聊天选择"""
    index: int = 0
    message: dict
    finish_reason: str = "stop"


class ChatResponse(BaseModel):
    """聊天响应 - OpenAI 兼容格式"""
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatChoice]


class ToolPlan(BaseModel):
    should_call_tool: bool = False
    tool_name: Optional[str] = None
    arguments: dict = Field(default_factory=dict)
    confidence: float = 0.0
    reason: str = ""


class ParsedQuery(BaseModel):
    vendors: list[str] = Field(default_factory=list)
    date_filters: dict = Field(default_factory=dict)
    intent: str = "search"
    keyword: Optional[str] = None
    wants_highlights: bool = False
    wants_count: bool = False


def _today() -> date:
    return datetime.now().date()


def _current_date_str() -> str:
    return _today().isoformat()


def _build_default_date_range() -> tuple[str, str]:
    current = _today()
    start = date(current.year, 1, 1)
    return start.isoformat(), current.isoformat()


def _month_range(year: int, month: int) -> tuple[str, str]:
    current = _today()
    last_day = calendar.monthrange(year, month)[1]
    end = date(year, month, last_day)
    if end > current:
        end = current
    start = date(year, month, 1)
    return start.isoformat(), end.isoformat()


def _quarter_range(year: int, quarter: int) -> tuple[str, str]:
    start_month = (quarter - 1) * 3 + 1
    start = date(year, start_month, 1)
    end_month = start_month + 2
    end_day = calendar.monthrange(year, end_month)[1]
    end = date(year, end_month, end_day)
    current = _today()
    if end > current:
        end = current
    return start.isoformat(), end.isoformat()


def _latest_occurrence_year(month: int) -> int:
    current = _today()
    return current.year if month <= current.month else current.year - 1


def _extract_latest_user_message(messages: List[ChatMessage]) -> str:
    for msg in reversed(messages):
        if msg.role == "user":
            return msg.content.strip()
    return ""


def _messages_to_transcript(messages: List[ChatMessage]) -> str:
    lines = []
    for msg in messages[-12:]:
        lines.append(f"{msg.role}: {msg.content}")
    return "\n".join(lines)


@lru_cache(maxsize=1)
def _get_chat_tool_db() -> UpdateDataLayer:
    db = UpdateDataLayer()
    register_update_tools(db)
    register_stats_tools(db)
    register_analysis_tools(db)
    return db


def _get_registered_tools():
    _get_chat_tool_db()
    return get_all_tools()


def _normalize_vendor(value: str) -> Optional[str]:
    aliases = {
        "aws": "aws",
        "amazon": "aws",
        "azure": "azure",
        "微软云": "azure",
        "gcp": "gcp",
        "google cloud": "gcp",
        "谷歌云": "gcp",
        "华为云": "huawei",
        "huawei": "huawei",
        "腾讯云": "tencentcloud",
        "tencent cloud": "tencentcloud",
        "tencentcloud": "tencentcloud",
        "火山引擎": "volcengine",
        "volcengine": "volcengine",
    }
    lowered = value.lower()
    for key, normalized in aliases.items():
        if key in lowered:
            return normalized
    return None


def _extract_vendors(text: str) -> list[str]:
    vendor_order = ["aws", "azure", "gcp", "huawei", "tencentcloud", "volcengine"]
    found = []
    lowered = text.lower()
    alias_groups = {
        "aws": ["aws", "amazon"],
        "azure": ["azure", "微软云"],
        "gcp": ["gcp", "google cloud", "谷歌云"],
        "huawei": ["huawei", "华为云"],
        "tencentcloud": ["tencentcloud", "tencent cloud", "腾讯云"],
        "volcengine": ["volcengine", "火山引擎"],
    }
    for vendor in vendor_order:
        if any(alias in lowered for alias in alias_groups[vendor]):
            found.append(vendor)
    return found


def _extract_month_number(text: str) -> Optional[int]:
    numeric_match = re.search(r"(?<!\d)(1[0-2]|0?[1-9])\s*月(?:份)?", text)
    if numeric_match:
        return int(numeric_match.group(1))

    cn_map = {
        "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6,
        "七": 7, "八": 8, "九": 9, "十": 10, "十一": 11, "十二": 12,
    }
    for key, value in cn_map.items():
        if f"{key}月" in text or f"{key}月份" in text:
            return value
    return None


def _extract_date_filters(text: str) -> dict:
    today = _today()
    text = text.strip()
    filters: dict[str, str] = {}

    iso_dates = re.findall(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if len(iso_dates) >= 2:
        filters["date_from"], filters["date_to"] = iso_dates[0], iso_dates[1]
        return filters
    if len(iso_dates) == 1:
        filters["date_from"] = iso_dates[0]
        filters["date_to"] = today.isoformat()
        return filters

    cn_dates = re.findall(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
    if len(cn_dates) >= 2:
        start = cn_dates[0]
        end = cn_dates[1]
        filters["date_from"] = f"{int(start[0]):04d}-{int(start[1]):02d}-{int(start[2]):02d}"
        filters["date_to"] = f"{int(end[0]):04d}-{int(end[1]):02d}-{int(end[2]):02d}"
        return filters

    year_month_match = re.search(r"(20\d{2})年\s*(1[0-2]|0?[1-9])月(?:份)?", text)
    if year_month_match:
        year = int(year_month_match.group(1))
        month = int(year_month_match.group(2))
        date_from, date_to = _month_range(year, month)
        filters["date_from"] = date_from
        filters["date_to"] = date_to
        return filters

    year_match = re.search(r"\b(20\d{2})\b|((20\d{2}))年", text)
    year = None
    if year_match:
        year = int(next(group for group in year_match.groups() if group))

    if "今年" in text:
        year = today.year
    elif "去年" in text:
        year = today.year - 1

    if year:
        filters["date_from"] = f"{year}-01-01"
        filters["date_to"] = f"{year}-12-31" if year < today.year else today.isoformat()
        return filters

    if "本月" in text or "这个月" in text:
        date_from, date_to = _month_range(today.year, today.month)
        filters["date_from"] = date_from
        filters["date_to"] = date_to
        return filters

    if "上个月" in text:
        year = today.year if today.month > 1 else today.year - 1
        month = today.month - 1 if today.month > 1 else 12
        date_from, date_to = _month_range(year, month)
        filters["date_from"] = date_from
        filters["date_to"] = date_to
        return filters

    if "本季度" in text or "这个季度" in text:
        quarter = (today.month - 1) // 3 + 1
        date_from, date_to = _quarter_range(today.year, quarter)
        filters["date_from"] = date_from
        filters["date_to"] = date_to
        return filters

    if "上季度" in text:
        current_quarter = (today.month - 1) // 3 + 1
        year = today.year
        quarter = current_quarter - 1
        if quarter == 0:
            quarter = 4
            year -= 1
        date_from, date_to = _quarter_range(year, quarter)
        filters["date_from"] = date_from
        filters["date_to"] = date_to
        return filters

    if "本周" in text or "这周" in text:
        start = today - timedelta(days=today.weekday())
        filters["date_from"] = start.isoformat()
        filters["date_to"] = today.isoformat()
        return filters

    if "上周" in text:
        end = today - timedelta(days=today.weekday() + 1)
        start = end - timedelta(days=6)
        filters["date_from"] = start.isoformat()
        filters["date_to"] = end.isoformat()
        return filters

    if "最近一周" in text or "近一周" in text:
        filters["date_from"] = (today - timedelta(days=7)).isoformat()
        filters["date_to"] = today.isoformat()
        return filters
    elif "最近7天" in text or "近7天" in text:
        filters["date_from"] = (today - timedelta(days=7)).isoformat()
        filters["date_to"] = today.isoformat()
        return filters
    elif "最近一个月" in text or "近一个月" in text:
        filters["date_from"] = (today - timedelta(days=30)).isoformat()
        filters["date_to"] = today.isoformat()
        return filters
    elif "最近三个月" in text or "近三个月" in text:
        filters["date_from"] = (today - timedelta(days=90)).isoformat()
        filters["date_to"] = today.isoformat()
        return filters
    elif "最近半年" in text or "近半年" in text:
        filters["date_from"] = (today - timedelta(days=180)).isoformat()
        filters["date_to"] = today.isoformat()
        return filters

    month = _extract_month_number(text)
    if month:
        inferred_year = _latest_occurrence_year(month)
        date_from, date_to = _month_range(inferred_year, month)
        filters["date_from"] = date_from
        filters["date_to"] = date_to
        return filters

    return filters


def _extract_keyword(text: str) -> Optional[str]:
    cleaned = re.sub(r"(aws|azure|gcp|google cloud|amazon|华为云|腾讯云|火山引擎|今年|去年|本月|这个月|上个月|本季度|这个季度|上季度|本周|这周|上周|最近一周|近一周|最近7天|近7天|最近一个月|近一个月|最近三个月|近三个月|最近半年|近半年)", " ", text, flags=re.I)
    cleaned = re.sub(r"20\d{2}年\s*(1[0-2]|0?[1-9])月(?:份)?", " ", cleaned)
    cleaned = re.sub(r"(1[0-2]|0?[1-9])月(?:份)?", " ", cleaned)
    cleaned = re.sub(r"\d{4}[-年]\d{0,2}[-月]?\d{0,2}日?", " ", cleaned)
    stop_words = [
        "帮我", "看看", "查一下", "查查", "请问", "一下", "有什么", "哪些", "更新", "动态",
        "统计", "趋势", "多少", "数据", "情况", "方面", "相关", "一下子", "最近", "产品", "服务",
        "对比", "比较", "分析", "帮忙", "我想", "我想看", "给我", "查",
        "重点", "重要", "值得关注", "亮点", "有哪些", "有啥", "有那些", "哪些值得看",
    ]
    for word in stop_words:
        cleaned = cleaned.replace(word, " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ，。,.?")
    if len(cleaned) <= 1:
        return None
    return cleaned or None


def _detect_intent(text: str, vendors: list[str], keyword: Optional[str]) -> str:
    if len(vendors) >= 2 and any(token in text for token in ["对比", "比较", "vs", "VS", "谁更", "谁的"]):
        return "compare"
    if any(token in text for token in ["概览", "整体情况", "全局", "总共有多少数据", "库里有多少"]):
        return "overview"
    if any(token in text for token in ["热度", "最火", "热门", "排名", "重点产品", "最活跃产品"]):
        return "hotness"
    if any(token in text for token in ["类型分布", "新功能", "修复", "安全", "enhancement", "deprecation"]):
        return "type_stats"
    if any(token in text for token in ["多少", "趋势", "时间线", "频率", "统计", "每月", "每周", "按月", "按周", "总量"]):
        return "timeline"
    if any(token in text for token in ["重点", "重要", "亮点", "值得关注", "值得看"]) and not keyword:
        return "highlights"
    return "search"


def _parse_query(messages: List[ChatMessage]) -> ParsedQuery:
    text = _extract_latest_user_message(messages)
    vendors = _extract_vendors(text)
    keyword = _extract_keyword(text)
    intent = _detect_intent(text, vendors, keyword)
    wants_highlights = any(token in text for token in ["重点", "重要", "亮点", "值得关注", "值得看"])
    wants_count = any(token in text for token in ["多少", "总量", "几条", "数量"])

    return ParsedQuery(
        vendors=vendors,
        date_filters=_extract_date_filters(text),
        intent=intent,
        keyword=keyword,
        wants_highlights=wants_highlights,
        wants_count=wants_count,
    )


def _should_try_tool(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    greeting_only = ["你好", "hello", "hi", "在吗", "你是谁"]
    if any(token == lowered.strip() for token in greeting_only):
        return False
    keywords = [
        "更新", "动态", "数据", "统计", "趋势", "比较", "对比", "多少", "详情", "查",
        "看看", "分析", "报告", "热度", "概览", "排名", "哪些", "有什么",
        "aws", "azure", "gcp", "google cloud", "amazon", "华为云", "腾讯云", "火山引擎",
    ]
    return any(keyword in lowered for keyword in keywords)


def _build_heuristic_plan(messages: List[ChatMessage]) -> ToolPlan:
    text = _extract_latest_user_message(messages)
    if not _should_try_tool(text):
        return ToolPlan(should_call_tool=False, confidence=0.0, reason="普通对话无需工具")

    parsed = _parse_query(messages)
    vendors = parsed.vendors
    date_filters = parsed.date_filters

    if parsed.intent == "compare":
        args = {"vendors": vendors[:4], **date_filters}
        if "date_from" not in args and "date_to" not in args:
            date_from, date_to = _build_default_date_range()
            args["date_from"], args["date_to"] = date_from, date_to
        return ToolPlan(should_call_tool=True, tool_name="compare_vendors", arguments=args, confidence=0.9, reason="多厂商对比")

    if parsed.intent == "overview":
        return ToolPlan(should_call_tool=True, tool_name="get_stats_overview", arguments={}, confidence=0.85, reason="全局概览")

    if parsed.intent == "hotness":
        args = {**date_filters}
        if vendors:
            args["vendor"] = vendors[0]
        if "date_from" not in args and "date_to" not in args:
            date_from, date_to = _build_default_date_range()
            args["date_from"], args["date_to"] = date_from, date_to
        return ToolPlan(should_call_tool=True, tool_name="get_product_hotness", arguments=args, confidence=0.85, reason="产品热度查询")

    if parsed.intent == "type_stats":
        args = {**date_filters}
        if vendors:
            args["vendor"] = vendors[0]
        if "date_from" not in args and "date_to" not in args:
            date_from, date_to = _build_default_date_range()
            args["date_from"], args["date_to"] = date_from, date_to
        return ToolPlan(should_call_tool=True, tool_name="get_update_type_stats", arguments=args, confidence=0.8, reason="更新类型分布")

    if parsed.intent == "timeline":
        args = {**date_filters}
        if vendors:
            args["vendor"] = vendors[0]
        if "按周" in text or "每周" in text:
            args["granularity"] = "week"
        elif "按天" in text or "每天" in text:
            args["granularity"] = "day"
        elif "按年" in text or "每年" in text:
            args["granularity"] = "year"
        else:
            args["granularity"] = "month"
        if "date_from" not in args and "date_to" not in args:
            date_from, date_to = _build_default_date_range()
            args["date_from"], args["date_to"] = date_from, date_to
        return ToolPlan(should_call_tool=True, tool_name="get_timeline", arguments=args, confidence=0.78, reason="时间统计查询")

    args = {**date_filters}
    if vendors:
        args["vendor"] = vendors[0]
    if parsed.keyword:
        args["keyword"] = parsed.keyword
    if parsed.intent == "highlights":
        args["limit"] = 30
        return ToolPlan(should_call_tool=True, tool_name="search_updates", arguments=args, confidence=0.82, reason="重点更新筛选")
    if "limit" not in args:
        args["limit"] = 10
    return ToolPlan(should_call_tool=True, tool_name="search_updates", arguments=args, confidence=0.65, reason="更新搜索")


def _sanitize_tool_arguments(tool_name: str, arguments: dict) -> dict:
    tools = {tool.name: tool for tool in _get_registered_tools()}
    tool = tools.get(tool_name)
    if tool is None:
        return {}

    properties = (tool.inputSchema or {}).get("properties", {})
    required = set((tool.inputSchema or {}).get("required", []))
    sanitized = {}

    for key, value in (arguments or {}).items():
        if key not in properties or value is None or value == "":
            continue
        schema = properties[key]
        schema_type = schema.get("type")
        if schema_type == "integer":
            try:
                sanitized[key] = int(value)
            except (TypeError, ValueError):
                continue
        elif schema_type == "boolean":
            if isinstance(value, bool):
                sanitized[key] = value
            elif isinstance(value, str):
                sanitized[key] = value.lower() in {"true", "1", "yes", "是"}
        elif schema_type == "array":
            sanitized[key] = value if isinstance(value, list) else [value]
        else:
            sanitized[key] = str(value).strip() if isinstance(value, str) else value

        enum_values = schema.get("enum")
        if enum_values and sanitized.get(key) not in enum_values:
            sanitized.pop(key, None)

    current = _current_date_str()
    if tool_name in {"search_updates", "get_timeline", "get_vendor_stats", "get_update_type_stats", "get_product_hotness", "compare_vendors", "get_vendor_type_matrix"}:
        if "date_from" in required and "date_from" not in sanitized:
            date_from, _ = _build_default_date_range()
            sanitized["date_from"] = date_from
        if "date_to" in required and "date_to" not in sanitized:
            sanitized["date_to"] = current

    if tool_name in {"get_timeline", "get_product_hotness", "compare_vendors", "get_update_type_stats"}:
        if "date_from" not in sanitized and "date_to" not in sanitized:
            date_from, date_to = _build_default_date_range()
            sanitized["date_from"] = date_from
            sanitized["date_to"] = date_to

    if tool_name == "search_updates" and "limit" not in sanitized:
        sanitized["limit"] = 10

    if tool_name == "get_product_hotness" and "limit" not in sanitized:
        sanitized["limit"] = 10

    return sanitized


def _serialize_tool_result(contents: Any) -> str:
    if contents is None:
        return ""
    if isinstance(contents, list):
        parts = []
        for item in contents:
            text = getattr(item, "text", None)
            if text:
                parts.append(text)
        if parts:
            return "\n\n".join(parts)
    if isinstance(contents, str):
        return contents
    return json.dumps(contents, ensure_ascii=False, default=str)


def _tool_descriptions_for_planner() -> str:
    lines = []
    for tool in _get_registered_tools():
        properties = (tool.inputSchema or {}).get("properties", {})
        params = ", ".join(
            f"{name}:{(schema or {}).get('type', 'string')}"
            for name, schema in properties.items()
        )
        lines.append(f"- {tool.name}({params}) {tool.description}")
    return "\n".join(lines)


def _extract_json_text(response: Any) -> str:
    if response is None:
        return ""
    if hasattr(response, "text") and response.text:
        return response.text
    if hasattr(response, "candidates") and response.candidates:
        candidate = response.candidates[0]
        if hasattr(candidate, "content") and candidate.content.parts:
            return candidate.content.parts[0].text or ""
    return ""


def _generate_with_gemini(
    client: Any,
    model_name: str,
    contents: Any,
    *,
    system_instruction: Optional[str] = None,
    temperature: float = 0.2,
    max_output_tokens: int = 4096,
    response_mime_type: Optional[str] = None,
    response_schema: Optional[dict] = None,
) -> str:
    config_args = {
        "temperature": temperature,
        "max_output_tokens": max_output_tokens,
    }
    if system_instruction:
        config_args["system_instruction"] = system_instruction
    if response_mime_type:
        config_args["response_mime_type"] = response_mime_type
    if response_schema:
        config_args["response_schema"] = response_schema

    response = client.models.generate_content(
        model=model_name,
        contents=contents,
        config=types.GenerateContentConfig(**config_args)
    )
    return _extract_json_text(response)


def _plan_tool_with_model(client: Any, model_name: str, messages: List[ChatMessage]) -> ToolPlan:
    transcript = _messages_to_transcript(messages)
    system_instruction = (
        "你是 CloudNetSpy Chatbox 的工具规划器。"
        f"今天是 {_current_date_str()}。"
        "你的任务是决定是否调用后端数据工具。"
        "如果是闲聊、问候、泛化知识问答，should_call_tool=false。"
        "如果用户在问本系统里的更新、趋势、统计、对比、详情，should_call_tool=true。"
        "涉及日期时，尽量输出绝对日期 YYYY-MM-DD。"
        "厂商只允许 aws, azure, gcp, huawei, tencentcloud, volcengine。"
        "只能从给定工具中选择。"
        "不要输出解释文本，只输出符合 schema 的 JSON。"
    )
    prompt = f"对话记录:\n{transcript}\n\n可用工具:\n{_tool_descriptions_for_planner()}"
    schema = {
        "type": "object",
        "properties": {
            "should_call_tool": {"type": "boolean"},
            "tool_name": {"type": "string", "nullable": True},
            "arguments": {"type": "object"},
            "confidence": {"type": "number"},
            "reason": {"type": "string"},
        },
        "required": ["should_call_tool", "arguments", "confidence", "reason"],
    }
    plan_text = _generate_with_gemini(
        client,
        model_name,
        prompt,
        system_instruction=system_instruction,
        temperature=0.1,
        max_output_tokens=1024,
        response_mime_type="application/json",
        response_schema=schema,
    )
    try:
        plan = ToolPlan.model_validate_json(plan_text)
    except Exception:
        logger.warning("Tool planner returned invalid JSON: %s", plan_text[:300])
        return ToolPlan(should_call_tool=False, confidence=0.0, reason="planner_invalid")

    plan.arguments = _sanitize_tool_arguments(plan.tool_name or "", plan.arguments)
    return plan


async def _execute_tool_plan(plan: ToolPlan) -> tuple[dict, dict]:
    handler = get_handler(plan.tool_name or "")
    if handler is None:
        return (
            {"id": f"call-{datetime.now().timestamp()}", "name": plan.tool_name, "arguments": plan.arguments},
            {"name": plan.tool_name, "result": f"未知工具: {plan.tool_name}", "is_error": True},
        )

    result = await handler(plan.arguments)
    serialized = _serialize_tool_result(result)
    tool_call = {
        "id": f"call-{int(datetime.now().timestamp() * 1000)}",
        "name": plan.tool_name,
        "arguments": plan.arguments,
    }
    tool_result = {
        "name": plan.tool_name,
        "result": serialized,
        "is_error": False,
    }
    return tool_call, tool_result


def _build_chat_system_prompt() -> str:
    prompts_config = get_config("chatbox_prompts")
    prompt_template = prompts_config.get("system_prompt", "你是 CloudNetSpy 的 AI 助手。")
    return (
        prompt_template
        .replace("${currentDate}", _current_date_str())
        .replace("${toolsDescription}", "")
    )


def _build_summary_prompt() -> str:
    prompts_config = get_config("chatbox_prompts")
    return prompts_config.get("summary_prompt", "请根据工具返回的数据，用中文用户友好的方式总结和展示结果。")


def get_gemini_client():
    """获取 Gemini 客户端"""
    if genai is None:
        raise HTTPException(
            status_code=500,
            detail="google-genai 库未安装"
        )
    
    # 加载配置
    ai_config = get_config("ai_model")
    # 优先使用 chatbox 配置，否则回退到 default
    chatbox_config = ai_config.get("chatbox", {})
    default_config = ai_config.get("default", {})
    
    # 合并配置：chatbox 覆盖 default
    config = {**default_config, **chatbox_config}
    
    api_key_env = config.get("api_key_env", "GEMINI_API_KEY")
    api_key = os.getenv(api_key_env)
    
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail=f"未配置 API Key 环境变量: {api_key_env}"
        )
    
    return genai.Client(api_key=api_key), config


def convert_messages_to_contents(messages: List[ChatMessage]) -> tuple[str, list]:
    """
    将消息列表转换为 Gemini 格式
    返回: (system_instruction, contents)
    """
    system_instruction = ""
    contents = []
    
    for msg in messages:
        if msg.role == "system":
            system_instruction += msg.content + "\n"
        elif msg.role == "user":
            contents.append({"role": "user", "parts": [{"text": msg.content}]})
        elif msg.role == "assistant":
            contents.append({"role": "model", "parts": [{"text": msg.content}]})
        elif msg.role == "tool":
            contents.append({"role": "user", "parts": [{"text": f"[TOOL RESULT]\n{msg.content}"}]})
    
    return system_instruction.strip(), contents


def format_tools_prompt(tools: Optional[List[Tool]]) -> str:
    """格式化工具提示"""
    if not tools:
        return ""
    
    tool_descriptions = []
    for tool in tools:
        func = tool.function
        tool_descriptions.append(f"- {func.name}: {func.description}")
    
    return "\n\n可用的分析工具：\n" + "\n".join(tool_descriptions)


@router.get("/prompts")
async def get_chat_prompts():
    """
    获取 Chatbox 提示词配置
    返回系统提示词和总结提示词模板
    """
    try:
        prompts_config = get_config("chatbox_prompts")
        return {
            "system_prompt": prompts_config.get("system_prompt", ""),
            "summary_prompt": prompts_config.get("summary_prompt", ""),
            "tools_description_template": prompts_config.get("tools_description_template", ""),
            "vendor_names": prompts_config.get("vendor_names", {})
        }
    except Exception as e:
        logger.error(f"Failed to load prompts config: {e}")
        # 返回默认提示词
        return {
            "system_prompt": "你是 CloudNetSpy 的 AI 助手，帮助用户分析云厂商的产品更新动态。",
            "summary_prompt": "请根据工具返回的数据，用中文用户友好的方式总结和展示结果。",
            "tools_description_template": "",
            "vendor_names": {}
        }


@router.post("/completions", response_model=ChatResponse)
async def chat_completions(request: ChatRequest):
    """
    处理聊天请求
    兼容 OpenAI Chat Completions API 格式
    """
    import time
    import uuid
    
    try:
        client, config = get_gemini_client()
        model_name = request.model or config.get("model_name")
        if not model_name:
            raise HTTPException(
                status_code=500,
                detail="未配置模型名称 model_name，已禁止默认回退。"
            )
        
        # 转换消息格式
        system_instruction, contents = convert_messages_to_contents(request.messages)
        if not system_instruction:
            system_instruction = _build_chat_system_prompt()

        parsed_query = _parse_query(request.messages)
        tool_plan = _build_heuristic_plan(request.messages)
        if tool_plan.should_call_tool:
            try:
                planned = _plan_tool_with_model(client, model_name, request.messages)
                if planned.should_call_tool and planned.tool_name:
                    tool_plan = planned
            except Exception as plan_error:
                logger.warning("Tool planner failed, fallback to heuristic plan: %s", plan_error)

        logger.info(
            "Chat completion start: model=%s contents_len=%s tool=%s",
            model_name,
            len(contents),
            tool_plan.tool_name if tool_plan.should_call_tool else "none",
        )

        response_text = ""
        assistant_payload = {
            "role": "assistant",
            "content": "",
        }

        try:
            if tool_plan.should_call_tool and tool_plan.tool_name:
                tool_call, tool_result = await _execute_tool_plan(tool_plan)
                summary_prompt = _build_summary_prompt()
                if parsed_query.wants_highlights:
                    summary_prompt += "\n\n额外要求：优先提炼重点更新/关键动作，不要机械罗列；如果数据较多，先给 Top 5。"
                if parsed_query.wants_count:
                    summary_prompt += "\n\n额外要求：如果工具结果里能看出数量或总量，先直接回答数量。"
                summary_input = (
                    f"用户问题: {_extract_latest_user_message(request.messages)}\n\n"
                    f"工具调用: {tool_plan.tool_name}\n"
                    f"参数: {json.dumps(tool_plan.arguments, ensure_ascii=False)}\n\n"
                    f"工具返回数据:\n{tool_result['result']}"
                )
                response_text = _generate_with_gemini(
                    client,
                    model_name,
                    summary_input,
                    system_instruction=summary_prompt,
                    temperature=request.temperature or 0.3,
                    max_output_tokens=request.max_tokens or 4096,
                )
                if not response_text:
                    response_text = "数据已获取，但总结生成失败。请查看工具返回结果。"
                assistant_payload = {
                    "role": "assistant",
                    "content": response_text,
                    "tool_calls": [tool_call],
                    "tool_results": [
                        {
                            "call_id": tool_call["id"],
                            "name": tool_result["name"],
                            "result": tool_result["result"],
                            "is_error": tool_result["is_error"],
                        }
                    ],
                }
            else:
                response_text = _generate_with_gemini(
                    client,
                    model_name,
                    contents,
                    system_instruction=system_instruction,
                    temperature=request.temperature or 0.7,
                    max_output_tokens=request.max_tokens or 4096,
                )
                assistant_payload = {
                    "role": "assistant",
                    "content": response_text,
                    "tool_calls": [],
                    "tool_results": [],
                }
        except Exception as api_error:
            logger.error(f"Gemini API call failed: {api_error}")
            raise HTTPException(status_code=500, detail=f"AI 调用失败: {api_error}")

        # 构建响应
        return ChatResponse(
            id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
            created=int(time.time()),
            model=model_name,
            choices=[
                ChatChoice(
                    message=assistant_payload,
                    finish_reason="stop"
                )
            ]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat completion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
