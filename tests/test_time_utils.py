#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 API 时间格式化工具
"""

import pytest
from datetime import datetime

from src.api.utils.time_utils import (
    format_datetime_utc,
    format_datetime_iso,
    format_dict_datetimes
)


class TestFormatDatetimeUtc:
    """测试 format_datetime_utc 函数"""
    
    def test_none_input(self):
        """测试 None 输入"""
        assert format_datetime_utc(None) is None
    
    def test_empty_string(self):
        """测试空字符串"""
        assert format_datetime_utc("") is None
        assert format_datetime_utc("   ") is None
    
    def test_already_iso_with_z(self):
        """测试已经是 ISO 格式（带 Z）"""
        iso_str = "2025-12-26T10:59:04Z"
        assert format_datetime_utc(iso_str) == iso_str
    
    def test_already_iso_with_timezone(self):
        """测试已经是 ISO 格式（带时区偏移）"""
        iso_str = "2025-12-26T10:59:04+08:00"
        assert format_datetime_utc(iso_str) == iso_str
    
    def test_sqlite_format(self):
        """测试 SQLite 格式"""
        sqlite_str = "2025-12-26 10:59:04"
        expected = "2025-12-26T10:59:04Z"
        assert format_datetime_utc(sqlite_str) == expected
    
    def test_date_only_format(self):
        """测试只有日期的格式"""
        date_str = "2025-12-26"
        expected = "2025-12-26T00:00:00Z"
        assert format_datetime_utc(date_str) == expected
    
    def test_datetime_object(self):
        """测试 datetime 对象"""
        dt = datetime(2025, 12, 26, 10, 59, 4)
        expected = "2025-12-26T10:59:04Z"
        assert format_datetime_utc(dt) == expected
    
    def test_invalid_format_returns_original(self):
        """测试无效格式返回原值"""
        invalid_str = "not-a-date"
        assert format_datetime_utc(invalid_str) == invalid_str
    
    def test_other_type(self):
        """测试其他类型"""
        assert format_datetime_utc(12345) == "12345"


class TestFormatDatetimeIso:
    """测试 format_datetime_iso 函数"""
    
    def test_none_input(self):
        """测试 None 输入"""
        assert format_datetime_iso(None) is None
    
    def test_removes_z_suffix(self):
        """测试移除 Z 后缀"""
        result = format_datetime_iso("2025-12-26 10:59:04")
        assert result == "2025-12-26T10:59:04"
        assert not result.endswith('Z')
    
    def test_already_without_z(self):
        """测试已经没有 Z 后缀"""
        iso_str = "2025-12-26T10:59:04+08:00"
        assert format_datetime_iso(iso_str) == iso_str


class TestFormatDictDatetimes:
    """测试 format_dict_datetimes 函数"""
    
    def test_format_multiple_fields(self):
        """测试格式化多个字段"""
        data = {
            "created_at": "2025-12-26 10:00:00",
            "updated_at": "2025-12-26 11:00:00",
            "name": "test"
        }
        result = format_dict_datetimes(data, ["created_at", "updated_at"])
        
        assert result["created_at"] == "2025-12-26T10:00:00Z"
        assert result["updated_at"] == "2025-12-26T11:00:00Z"
        assert result["name"] == "test"
    
    def test_skip_missing_fields(self):
        """测试跳过不存在的字段"""
        data = {"name": "test"}
        result = format_dict_datetimes(data, ["created_at"])
        assert "created_at" not in result
        assert result["name"] == "test"
    
    def test_skip_none_values(self):
        """测试跳过 None 值"""
        data = {"created_at": None, "name": "test"}
        result = format_dict_datetimes(data, ["created_at"])
        assert result["created_at"] is None
    
    def test_empty_dict(self):
        """测试空字典"""
        data = {}
        result = format_dict_datetimes(data, ["created_at"])
        assert result == {}
    
    def test_modifies_in_place(self):
        """测试原地修改"""
        data = {"created_at": "2025-12-26 10:00:00"}
        result = format_dict_datetimes(data, ["created_at"])
        assert result is data  # 应该是同一个对象
