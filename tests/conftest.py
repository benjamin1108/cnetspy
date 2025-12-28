#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Pytest 共享 Fixtures
"""

import os
import sys
import pytest
import tempfile
import shutil

# 添加项目根目录到路径
PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture(scope="session")
def project_root():
    """项目根目录"""
    return PROJECT_ROOT


@pytest.fixture(scope="function")
def temp_db_path():
    """创建临时测试数据库路径"""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_updates.db")
    yield db_path
    # 清理
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="function")
def data_layer(temp_db_path):
    """创建测试用 UpdateDataLayer 实例"""
    from src.storage.database import UpdateDataLayer
    from src.storage.database.base import DatabaseManager
    
    # 重置 DatabaseManager 单例，确保使用临时数据库
    with DatabaseManager._lock:
        DatabaseManager._instance = None
    
    layer = UpdateDataLayer(db_path=temp_db_path)
    yield layer
    
    # 清理：重置单例
    with DatabaseManager._lock:
        DatabaseManager._instance = None


@pytest.fixture
def sample_update_data():
    """示例更新数据"""
    return {
        "update_id": "test-update-001",
        "vendor": "aws",
        "source_channel": "blog",
        "source_url": "https://aws.amazon.com/blogs/networking/test-post",
        "source_identifier": "test-post-001",
        "title": "Test AWS Networking Update",
        "description": "This is a test update for CI/CD",
        "content": "Full content of the test update...",
        "publish_date": "2024-12-28",
        "crawl_time": "2024-12-28T12:00:00",
        "product_name": "VPC",
        "product_category": "Networking",
        "raw_filepath": "/data/raw/aws/test.json"
    }


@pytest.fixture
def sample_analysis_result():
    """示例分析结果"""
    return {
        "title_translated": "测试 AWS 网络更新",
        "content_summary": "这是一个用于CI/CD的测试更新",
        "update_type": "new_feature",
        "product_subcategory": "Virtual Private Cloud",
        "is_network_related": True,
        "tags": '["VPC", "网络", "测试"]'
    }


@pytest.fixture
def batch_update_data():
    """批量测试数据"""
    vendors = ["aws", "azure", "gcp", "huawei", "tencentcloud", "volcengine"]
    channels = ["blog", "whatsnew"]
    updates = []
    
    for i, vendor in enumerate(vendors):
        for j, channel in enumerate(channels):
            idx = i * len(channels) + j
            updates.append({
                "update_id": f"batch-{vendor}-{channel}-{idx}",
                "vendor": vendor,
                "source_channel": channel,
                "source_url": f"https://{vendor}.com/{channel}/post-{idx}",
                "source_identifier": f"{vendor}-{channel}-post-{idx}",
                "title": f"Test {vendor.upper()} {channel} Update {idx}",
                "description": f"Test update from {vendor}",
                "content": f"Full content of test update {idx} from {vendor}",  # 必须有 content
                "publish_date": f"2024-12-{15+i:02d}",
                "crawl_time": f"2024-12-28T{10+j}:00:00",
            })
    
    return updates
