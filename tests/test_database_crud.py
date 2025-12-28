#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库 CRUD 操作测试

测试覆盖：
- 单条插入/查询/删除
- 批量插入
- 去重检查
- 分页查询
- 统计功能
"""

import pytest


class TestUpdatesCRUD:
    """Updates 表 CRUD 测试"""
    
    def test_insert_single_update(self, data_layer, sample_update_data):
        """测试单条插入"""
        result = data_layer.insert_update(sample_update_data)
        assert result is True
        
        # 验证插入成功
        record = data_layer.get_update_by_id(sample_update_data["update_id"])
        assert record is not None
        assert record["vendor"] == "aws"
        assert record["title"] == sample_update_data["title"]
    
    def test_insert_duplicate_rejected(self, data_layer, sample_update_data):
        """测试重复插入被拒绝"""
        # 第一次插入
        result1 = data_layer.insert_update(sample_update_data)
        assert result1 is True
        
        # 第二次插入应该被拒绝
        result2 = data_layer.insert_update(sample_update_data)
        assert result2 is False
    
    def test_check_update_exists(self, data_layer, sample_update_data):
        """测试存在性检查"""
        # 插入前检查
        exists_before = data_layer.check_update_exists(
            sample_update_data["source_url"],
            sample_update_data["source_identifier"]
        )
        assert exists_before is False
        
        # 插入
        data_layer.insert_update(sample_update_data)
        
        # 插入后检查
        exists_after = data_layer.check_update_exists(
            sample_update_data["source_url"],
            sample_update_data["source_identifier"]
        )
        assert exists_after is True
    
    def test_delete_update(self, data_layer, sample_update_data):
        """测试删除操作"""
        # 先插入
        data_layer.insert_update(sample_update_data)
        update_id = sample_update_data["update_id"]
        
        # 确认存在
        assert data_layer.get_update_by_id(update_id) is not None
        
        # 删除
        result = data_layer.delete_update(update_id)
        assert result is True
        
        # 确认已删除
        assert data_layer.get_update_by_id(update_id) is None
    
    def test_batch_insert(self, data_layer, batch_update_data):
        """测试批量插入"""
        inserted, skipped = data_layer.batch_insert_updates(batch_update_data)
        
        assert inserted == len(batch_update_data)
        assert skipped == 0
        
        # 验证总数（注意：count_updates 默认只统计 whatsnew，所以使用原始 SQL 查询）
        with data_layer._db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM updates")
            total = cursor.fetchone()[0]
        assert total == len(batch_update_data)
    
    def test_batch_insert_skip_duplicates(self, data_layer, batch_update_data):
        """测试批量插入跳过重复"""
        # 第一次批量插入
        inserted1, skipped1 = data_layer.batch_insert_updates(batch_update_data)
        assert inserted1 == len(batch_update_data)
        
        # 第二次批量插入（全部应该被跳过）
        inserted2, skipped2 = data_layer.batch_insert_updates(batch_update_data)
        assert inserted2 == 0
        assert skipped2 == len(batch_update_data)


class TestPaginatedQuery:
    """分页查询测试"""
    
    def test_paginated_query_basic(self, data_layer, batch_update_data):
        """测试基本分页查询"""
        data_layer.batch_insert_updates(batch_update_data)
        
        # 第一页
        page1 = data_layer.query_updates_paginated(
            filters={},
            limit=5,
            offset=0
        )
        assert len(page1) == 5
        
        # 第二页
        page2 = data_layer.query_updates_paginated(
            filters={},
            limit=5,
            offset=5
        )
        assert len(page2) == 5
        
        # 确保不重复
        page1_ids = {r["update_id"] for r in page1}
        page2_ids = {r["update_id"] for r in page2}
        assert page1_ids.isdisjoint(page2_ids)
    
    def test_paginated_query_with_vendor_filter(self, data_layer, batch_update_data):
        """测试按厂商过滤的分页查询"""
        data_layer.batch_insert_updates(batch_update_data)
        
        results = data_layer.query_updates_paginated(
            filters={"vendor": "aws"},
            limit=100,
            offset=0
        )
        
        assert len(results) > 0
        for r in results:
            assert r["vendor"] == "aws"
    
    def test_paginated_query_sort_order(self, data_layer, batch_update_data):
        """测试排序"""
        data_layer.batch_insert_updates(batch_update_data)
        
        # 按日期降序
        results_desc = data_layer.query_updates_paginated(
            filters={},
            limit=10,
            offset=0,
            sort_by="publish_date",
            order="desc"
        )
        
        dates = [r["publish_date"] for r in results_desc]
        assert dates == sorted(dates, reverse=True)


class TestStatistics:
    """统计功能测试"""
    
    def test_count_updates(self, data_layer, batch_update_data):
        """测试总数统计（注意：count_updates 默认只统计 whatsnew）"""
        data_layer.batch_insert_updates(batch_update_data)
        
        # whatsnew 渠道占一半
        whatsnew_count = len([u for u in batch_update_data if u['source_channel'] == 'whatsnew'])
        total = data_layer.count_updates()
        assert total == whatsnew_count
    
    def test_count_with_vendor_filter(self, data_layer, batch_update_data):
        """测试按厂商统计"""
        data_layer.batch_insert_updates(batch_update_data)
        
        aws_count = data_layer.count_updates_with_filters(vendor="aws")
        azure_count = data_layer.count_updates_with_filters(vendor="azure")
        
        assert aws_count > 0
        assert azure_count > 0
        assert aws_count + azure_count <= len(batch_update_data)
    
    def test_get_vendor_statistics(self, data_layer, batch_update_data):
        """测试厂商统计"""
        data_layer.batch_insert_updates(batch_update_data)
        
        stats = data_layer.get_vendor_statistics()
        
        assert len(stats) > 0
        vendors = {s["vendor"] for s in stats}
        assert "aws" in vendors
        assert "azure" in vendors
    
    def test_get_database_stats(self, data_layer, batch_update_data):
        """测试数据库统计概览"""
        data_layer.batch_insert_updates(batch_update_data)
        
        stats = data_layer.get_database_stats()
        
        assert "total_updates" in stats
        # 注意: get_database_stats 只统计 source_channel='whatsnew' 的记录
        # 测试数据中一半是 whatsnew，一半是 blog
        whatsnew_count = len([u for u in batch_update_data if u['source_channel'] == 'whatsnew'])
        assert stats["total_updates"] == whatsnew_count
    
    def test_get_available_years(self, data_layer, batch_update_data):
        """测试年份列表获取"""
        data_layer.batch_insert_updates(batch_update_data)
        
        years = data_layer.get_available_years()
        
        assert 2024 in years
    
    def test_get_source_channel_statistics(self, data_layer, batch_update_data):
        """测试来源渠道统计"""
        data_layer.batch_insert_updates(batch_update_data)
        
        stats = data_layer.get_source_channel_statistics()
        
        assert len(stats) > 0
        # API 返回的字段是 'value' 而不是 'source_channel'
        channels = {s["value"] for s in stats}
        assert "blog" in channels
        assert "whatsnew" in channels
