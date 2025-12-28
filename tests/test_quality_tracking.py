#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
质量问题追踪测试

测试覆盖：
- 质量问题记录
- 问题查询和过滤
- 问题解决流程
- 统计功能
"""

import pytest


class TestQualityIssueTracking:
    """质量问题追踪测试"""
    
    def test_insert_quality_issue(self, data_layer):
        """测试插入质量问题"""
        result = data_layer.insert_quality_issue(
            update_id="test-update-001",
            issue_type="empty_subcategory",
            auto_action="kept",
            vendor="aws",
            title="Test AWS Update",
            source_url="https://aws.amazon.com/test"
        )
        assert result is True
    
    def test_insert_deleted_issue(self, data_layer):
        """测试插入已删除类型的问题"""
        result = data_layer.insert_quality_issue(
            update_id="test-update-002",
            issue_type="not_network_related",
            auto_action="deleted",
            vendor="azure",
            title="Test Azure Update"
        )
        assert result is True
    
    def test_get_open_issues(self, data_layer):
        """测试获取待处理问题"""
        # 插入一个 kept 类型的问题（应该是 open）
        data_layer.insert_quality_issue(
            update_id="test-001",
            issue_type="empty_subcategory",
            auto_action="kept",
            vendor="aws"
        )
        
        # 插入一个 deleted 类型的问题（应该是 resolved）
        data_layer.insert_quality_issue(
            update_id="test-002",
            issue_type="not_network_related",
            auto_action="deleted",
            vendor="azure"
        )
        
        # 获取 open 问题
        open_issues = data_layer.get_open_issues()
        
        assert len(open_issues) == 1
        assert open_issues[0]["update_id"] == "test-001"
        assert open_issues[0]["issue_type"] == "empty_subcategory"
    
    def test_get_open_issues_with_filter(self, data_layer):
        """测试按条件过滤问题"""
        # 插入多个问题
        data_layer.insert_quality_issue(
            update_id="aws-001",
            issue_type="empty_subcategory",
            auto_action="kept",
            vendor="aws"
        )
        data_layer.insert_quality_issue(
            update_id="azure-001",
            issue_type="empty_subcategory",
            auto_action="kept",
            vendor="azure"
        )
        data_layer.insert_quality_issue(
            update_id="aws-002",
            issue_type="analysis_failed",
            auto_action="kept",
            vendor="aws"
        )
        
        # 按厂商过滤
        aws_issues = data_layer.get_open_issues(vendor="aws")
        assert len(aws_issues) == 2
        
        # 按类型过滤
        empty_issues = data_layer.get_open_issues(issue_type="empty_subcategory")
        assert len(empty_issues) == 2
        
        # 组合过滤
        aws_empty = data_layer.get_open_issues(vendor="aws", issue_type="empty_subcategory")
        assert len(aws_empty) == 1
    
    def test_count_open_issues(self, data_layer):
        """测试统计待处理问题数量"""
        # 插入多个问题
        for i in range(5):
            data_layer.insert_quality_issue(
                update_id=f"test-{i}",
                issue_type="empty_subcategory",
                auto_action="kept",
                vendor="aws"
            )
        
        count = data_layer.count_open_issues()
        assert count == 5
        
        # 按厂商统计
        aws_count = data_layer.count_open_issues(vendor="aws")
        assert aws_count == 5
    
    def test_get_issue_statistics(self, data_layer):
        """测试问题统计"""
        # 插入不同类型的问题
        data_layer.insert_quality_issue(
            update_id="kept-001",
            issue_type="empty_subcategory",
            auto_action="kept",
            vendor="aws"
        )
        data_layer.insert_quality_issue(
            update_id="kept-002",
            issue_type="empty_subcategory",
            auto_action="kept",
            vendor="azure"
        )
        data_layer.insert_quality_issue(
            update_id="deleted-001",
            issue_type="not_network_related",
            auto_action="deleted",
            vendor="gcp"
        )
        
        stats = data_layer.get_issue_statistics()
        
        assert "total_open" in stats
        assert "total_resolved" in stats
        assert "by_type" in stats
        assert "by_vendor" in stats
        
        assert stats["total_open"] == 2
        assert stats["total_resolved"] == 1
    
    def test_resolve_issue(self, data_layer):
        """测试解决问题"""
        # 插入问题
        data_layer.insert_quality_issue(
            update_id="resolve-test",
            issue_type="empty_subcategory",
            auto_action="kept",
            vendor="aws"
        )
        
        # 获取问题ID
        issues = data_layer.get_open_issues()
        assert len(issues) == 1
        issue_id = issues[0]["id"]
        
        # 解决问题
        result = data_layer._quality.resolve_issue(issue_id, "manually_fixed")
        assert result is True
        
        # 验证已解决
        open_issues = data_layer.get_open_issues()
        assert len(open_issues) == 0
    
    def test_ignore_issue(self, data_layer):
        """测试忽略问题"""
        # 插入问题
        data_layer.insert_quality_issue(
            update_id="ignore-test",
            issue_type="empty_subcategory",
            auto_action="kept",
            vendor="aws"
        )
        
        # 获取问题ID
        issues = data_layer.get_open_issues()
        issue_id = issues[0]["id"]
        
        # 忽略问题
        result = data_layer._quality.ignore_issue(issue_id)
        assert result is True
        
        # 验证已忽略（不在 open 列表）
        open_issues = data_layer.get_open_issues()
        assert len(open_issues) == 0
        
        # 统计应该有 1 个 ignored
        stats = data_layer.get_issue_statistics()
        assert stats["total_ignored"] == 1
    
    def test_batch_id_tracking(self, data_layer):
        """测试批次ID追踪"""
        batch_id = "batch-2024-12-28-001"
        
        # 插入多个同批次的问题
        for i in range(3):
            data_layer.insert_quality_issue(
                update_id=f"batch-{i}",
                issue_type="empty_subcategory",
                auto_action="kept",
                vendor="aws",
                batch_id=batch_id
            )
        
        # 按批次过滤
        batch_issues = data_layer.get_open_issues(batch_id=batch_id)
        assert len(batch_issues) == 3
        
        for issue in batch_issues:
            assert issue["batch_id"] == batch_id
    
    def test_get_deleted_issues_for_audit(self, data_layer):
        """测试获取已删除问题（审计日志）"""
        # 插入多个已删除类型的问题
        for i in range(3):
            data_layer.insert_quality_issue(
                update_id=f"deleted-{i}",
                issue_type="not_network_related",
                auto_action="deleted",
                vendor="aws",
                title=f"Deleted Update {i}"
            )
        
        # 获取已删除问题
        deleted = data_layer._quality.get_deleted_issues()
        assert len(deleted) == 3
        
        for issue in deleted:
            assert issue["auto_action"] == "deleted"


class TestAICleanedCheck:
    """测试AI清洗检查功能 - 用于爬虫去重"""
    
    def test_check_cleaned_by_ai_returns_true_for_deleted(self, data_layer):
        """测试已清洗的URL返回True"""
        source_url = "https://aws.amazon.com/test-cleaned"
        
        # 插入一个已清洗的记录
        data_layer.insert_quality_issue(
            update_id="test-cleaned-001",
            issue_type="not_network_related",
            auto_action="deleted",
            vendor="aws",
            title="Test Cleaned Update",
            source_url=source_url
        )
        
        result = data_layer.check_cleaned_by_ai(source_url)
        assert result is True
    
    def test_check_cleaned_by_ai_returns_false_for_kept(self, data_layer):
        """测试保留的URL返回False"""
        source_url = "https://aws.amazon.com/test-kept"
        
        # 插入一个保留的记录
        data_layer.insert_quality_issue(
            update_id="test-kept-001",
            issue_type="not_network_related",
            auto_action="kept",
            vendor="aws",
            title="Test Kept Update",
            source_url=source_url
        )
        
        result = data_layer.check_cleaned_by_ai(source_url)
        assert result is False
    
    def test_check_cleaned_by_ai_returns_false_for_nonexistent(self, data_layer):
        """测试不存在的URL返回False"""
        result = data_layer.check_cleaned_by_ai("https://nonexistent.com/test")
        assert result is False
    
    def test_check_cleaned_by_ai_empty_url_returns_false(self, data_layer):
        """测试空URL返回False"""
        result = data_layer.check_cleaned_by_ai("")
        assert result is False
    
    def test_check_cleaned_by_ai_with_different_issue_type(self, data_layer):
        """测试不同问题类型的检查"""
        source_url = "https://aws.amazon.com/test-empty-sub"
        
        # 插入 empty_subcategory 类型，已删除
        data_layer.insert_quality_issue(
            update_id="test-empty-001",
            issue_type="empty_subcategory",
            auto_action="deleted",
            vendor="aws",
            source_url=source_url
        )
        
        # 默认检查 not_network_related 类型，应返回 False
        result = data_layer.check_cleaned_by_ai(source_url)
        assert result is False
        
        # 指定 empty_subcategory 类型，应返回 True
        result = data_layer.check_cleaned_by_ai(source_url, issue_type="empty_subcategory")
        assert result is True
    
    def test_check_cleaned_by_ai_only_checks_deleted(self, data_layer):
        """测试只检查 deleted 状态，不检查 kept 或 fixed"""
        source_url = "https://aws.amazon.com/test-status"
        
        # 插入 kept 状态
        data_layer.insert_quality_issue(
            update_id="test-status-001",
            issue_type="not_network_related",
            auto_action="kept",
            vendor="aws",
            source_url=source_url
        )
        
        result = data_layer.check_cleaned_by_ai(source_url)
        assert result is False
    
    def test_get_cleaned_urls_returns_list(self, data_layer):
        """测试获取已清洗URL列表"""
        # 插入多个已清洗的记录
        urls = [
            "https://aws.amazon.com/cleaned-1",
            "https://aws.amazon.com/cleaned-2",
            "https://aws.amazon.com/cleaned-3"
        ]
        
        for i, url in enumerate(urls):
            data_layer.insert_quality_issue(
                update_id=f"cleaned-{i}",
                issue_type="not_network_related",
                auto_action="deleted",
                vendor="aws",
                source_url=url
            )
        
        # 插入一个保留的记录
        data_layer.insert_quality_issue(
            update_id="kept-1",
            issue_type="not_network_related",
            auto_action="kept",
            vendor="aws",
            source_url="https://aws.amazon.com/kept-1"
        )
        
        cleaned_urls = data_layer.get_cleaned_urls()
        
        assert len(cleaned_urls) == 3
        for url in urls:
            assert url in cleaned_urls
        assert "https://aws.amazon.com/kept-1" not in cleaned_urls
    
    def test_get_cleaned_urls_with_vendor_filter(self, data_layer):
        """测试按厂商过滤已清洗URL"""
        # AWS URL
        data_layer.insert_quality_issue(
            update_id="aws-cleaned-1",
            issue_type="not_network_related",
            auto_action="deleted",
            vendor="aws",
            source_url="https://aws.amazon.com/cleaned"
        )
        
        # Azure URL
        data_layer.insert_quality_issue(
            update_id="azure-cleaned-1",
            issue_type="not_network_related",
            auto_action="deleted",
            vendor="azure",
            source_url="https://azure.microsoft.com/cleaned"
        )
        
        # 按 AWS 过滤
        aws_cleaned = data_layer.get_cleaned_urls(vendor="aws")
        assert len(aws_cleaned) == 1
        assert "https://aws.amazon.com/cleaned" in aws_cleaned
        
        # 按 Azure 过滤
        azure_cleaned = data_layer.get_cleaned_urls(vendor="azure")
        assert len(azure_cleaned) == 1
        assert "https://azure.microsoft.com/cleaned" in azure_cleaned
    
    def test_get_cleaned_urls_empty_list(self, data_layer):
        """测试无已清洗记录时返回空列表"""
        cleaned_urls = data_layer.get_cleaned_urls()
        assert cleaned_urls == []
    
    def test_check_cleaned_multiple_records_same_url(self, data_layer):
        """测试同URL多条记录的情况"""
        source_url = "https://aws.amazon.com/multi-record"
        
        # 第一次记录: kept
        data_layer.insert_quality_issue(
            update_id="multi-1",
            issue_type="not_network_related",
            auto_action="kept",
            vendor="aws",
            source_url=source_url
        )
        
        # 第二次记录: deleted
        data_layer.insert_quality_issue(
            update_id="multi-2",
            issue_type="not_network_related",
            auto_action="deleted",
            vendor="aws",
            source_url=source_url
        )
        
        # 应该返回 True，因为存在 deleted 记录
        result = data_layer.check_cleaned_by_ai(source_url)
        assert result is True
