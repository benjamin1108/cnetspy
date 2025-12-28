#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
分析流程测试

测试覆盖：
- 未分析记录查询
- 分析字段更新
- 分析覆盖率统计
- 分析执行器集成
"""

import pytest


class TestAnalysisOperations:
    """分析相关操作测试"""
    
    def test_get_unanalyzed_updates(self, data_layer, sample_update_data):
        """测试获取未分析记录"""
        # 插入未分析记录
        data_layer.insert_update(sample_update_data)
        
        # 获取未分析列表
        unanalyzed = data_layer.get_unanalyzed_updates()
        
        assert len(unanalyzed) == 1
        assert unanalyzed[0]["update_id"] == sample_update_data["update_id"]
    
    def test_get_unanalyzed_with_vendor_filter(self, data_layer, batch_update_data):
        """测试按厂商过滤未分析记录"""
        data_layer.batch_insert_updates(batch_update_data)
        
        aws_unanalyzed = data_layer.get_unanalyzed_updates(vendor="aws")
        azure_unanalyzed = data_layer.get_unanalyzed_updates(vendor="azure")
        
        for record in aws_unanalyzed:
            assert record["vendor"] == "aws"
        
        for record in azure_unanalyzed:
            assert record["vendor"] == "azure"
    
    def test_get_unanalyzed_with_limit(self, data_layer, batch_update_data):
        """测试限制返回数量"""
        data_layer.batch_insert_updates(batch_update_data)
        
        limited = data_layer.get_unanalyzed_updates(limit=3)
        
        # 应该返回3条或所有记录（如果不足3条）
        assert len(limited) <= 3
        assert len(limited) > 0
    
    def test_count_unanalyzed_updates(self, data_layer, batch_update_data):
        """测试未分析记录计数"""
        data_layer.batch_insert_updates(batch_update_data)
        
        count = data_layer.count_unanalyzed_updates()
        
        # 应该有未分析记录
        assert count > 0
        assert count <= len(batch_update_data)
    
    def test_update_analysis_fields(self, data_layer, sample_update_data, sample_analysis_result):
        """测试更新分析字段"""
        # 插入原始记录
        data_layer.insert_update(sample_update_data)
        update_id = sample_update_data["update_id"]
        
        # 更新分析字段
        result = data_layer.update_analysis_fields(update_id, sample_analysis_result)
        assert result is True
        
        # 验证更新成功
        record = data_layer.get_update_by_id(update_id)
        assert record["title_translated"] == sample_analysis_result["title_translated"]
        assert record["content_summary"] == sample_analysis_result["content_summary"]
        assert record["update_type"] == sample_analysis_result["update_type"]
        assert record["product_subcategory"] == sample_analysis_result["product_subcategory"]
    
    def test_analyzed_record_not_in_unanalyzed(self, data_layer, sample_update_data, sample_analysis_result):
        """测试已分析记录不在未分析列表中"""
        # 插入并分析
        data_layer.insert_update(sample_update_data)
        data_layer.update_analysis_fields(sample_update_data["update_id"], sample_analysis_result)
        
        # 获取未分析列表
        unanalyzed = data_layer.get_unanalyzed_updates()
        
        assert len(unanalyzed) == 0
    
    def test_get_analysis_coverage(self, data_layer, batch_update_data, sample_analysis_result):
        """测试分析覆盖率计算"""
        data_layer.batch_insert_updates(batch_update_data)
        
        # 初始覆盖率应该是0
        coverage_initial = data_layer.get_analysis_coverage()
        assert coverage_initial == 0.0
        
        # 分析几条记录
        analyzed_count = 0
        for update in batch_update_data[:3]:
            success = data_layer.update_analysis_fields(update["update_id"], sample_analysis_result)
            if success:
                analyzed_count += 1
        
        # 如果有成功分析的，覆盖率应该大于0
        if analyzed_count > 0:
            coverage_after = data_layer.get_analysis_coverage()
            assert coverage_after > 0


class TestAnalysisExecutor:
    """分析执行器测试"""
    
    def test_executor_import(self):
        """测试执行器可以正常导入"""
        from src.analyzers.analysis_executor import AnalysisExecutor
        assert AnalysisExecutor is not None
    
    def test_executor_batch_id_management(self):
        """测试批次ID管理"""
        from src.analyzers.analysis_executor import AnalysisExecutor
        
        # 设置批次ID
        AnalysisExecutor.set_batch_id("test-batch-001")
        assert AnalysisExecutor._current_batch_id == "test-batch-001"
        
        # 清除批次ID
        AnalysisExecutor.clear_batch_id()
        assert AnalysisExecutor._current_batch_id is None
    
    def test_executor_print_report(self, data_layer):
        """测试报告输出"""
        from src.analyzers.analysis_executor import AnalysisExecutor
        
        # 应该不抛出异常
        AnalysisExecutor.print_analysis_report(data_layer)
