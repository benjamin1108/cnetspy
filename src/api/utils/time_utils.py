#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
时间格式化工具

将数据库返回的时间转换为 ISO 8601 标准格式（UTC）
"""

from datetime import datetime
from typing import Optional, Union


def format_datetime_utc(dt: Optional[Union[str, datetime]]) -> Optional[str]:
    """
    将时间转换为 ISO 8601 UTC 格式
    
    Args:
        dt: 时间字符串或 datetime 对象
        
    Returns:
        ISO 8601 格式字符串，如 "2025-12-26T10:59:04Z"
        
    Examples:
        >>> format_datetime_utc("2025-12-26 10:59:04")
        "2025-12-26T10:59:04Z"
        >>> format_datetime_utc(None)
        None
    """
    if dt is None:
        return None
    
    if isinstance(dt, str):
        if not dt.strip():
            return None
        # 已经是 ISO 格式（带 T 和 Z）
        if 'T' in dt and dt.endswith('Z'):
            return dt
        # 已经是 ISO 格式（带时区偏移）
        if 'T' in dt and ('+' in dt or dt.endswith('Z')):
            return dt
        # SQLite 格式: "2025-12-26 10:59:04"
        try:
            parsed = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
            return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            # 尝试只有日期的情况
            try:
                parsed = datetime.strptime(dt, "%Y-%m-%d")
                return parsed.strftime("%Y-%m-%dT00:00:00Z")
            except ValueError:
                return dt  # 返回原值
    
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    return str(dt)


def format_datetime_iso(dt: Optional[Union[str, datetime]]) -> Optional[str]:
    """
    将时间转换为 ISO 8601 格式（不带 Z 后缀）
    
    Args:
        dt: 时间字符串或 datetime 对象
        
    Returns:
        ISO 8601 格式字符串，如 "2025-12-26T10:59:04"
    """
    result = format_datetime_utc(dt)
    if result and result.endswith('Z'):
        return result[:-1]
    return result


def format_dict_datetimes(data: dict, fields: list[str]) -> dict:
    """
    批量格式化字典中的时间字段
    
    Args:
        data: 原始数据字典
        fields: 需要格式化的字段名列表
        
    Returns:
        格式化后的字典（原地修改）
        
    Example:
        >>> format_dict_datetimes(
        ...     {"created_at": "2025-12-26 10:00:00", "name": "test"},
        ...     ["created_at"]
        ... )
        {"created_at": "2025-12-26T10:00:00Z", "name": "test"}
    """
    for field in fields:
        if field in data and data[field]:
            data[field] = format_datetime_utc(data[field])
    return data
