#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 API 路由接口
"""

import pytest
import os
import sys
import tempfile
import shutil
from fastapi.testclient import TestClient

# 添加项目根目录到路径
PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture(scope="module")
def temp_db_path_module():
    """创建模块级临时数据库"""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_api.db")
    yield db_path
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="module")
def test_client(temp_db_path_module):
    """创建测试客户端"""
    from src.storage.database.base import DatabaseManager
    from src.storage.database import UpdateDataLayer
    
    # 重置 DatabaseManager 单例
    with DatabaseManager._lock:
        DatabaseManager._instance = None
    
    # 创建数据库实例
    db = UpdateDataLayer(db_path=temp_db_path_module)
    
    # 添加一些测试数据
    test_update = {
        "update_id": "api-test-001",
        "vendor": "aws",
        "source_channel": "whatsnew",
        "source_url": "https://aws.amazon.com/test",
        "source_identifier": "test-001",
        "title": "API Test Update",
        "description": "Test description",
        "content": "Test content for API testing",
        "publish_date": "2024-12-28",
        "crawl_time": "2024-12-28T12:00:00"
    }
    db.insert_update(test_update)
    
    # 创建 FastAPI 应用
    from src.api.app import app
    from src.api.dependencies import get_db
    
    # 覆盖依赖
    def override_get_db():
        return db
    
    app.dependency_overrides[get_db] = override_get_db
    
    client = TestClient(app)
    yield client
    
    # 清理
    app.dependency_overrides.clear()
    with DatabaseManager._lock:
        DatabaseManager._instance = None


class TestHealthRoutes:
    """测试健康检查路由"""
    
    def test_root_endpoint(self, test_client):
        """测试根路径"""
        response = test_client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "status" in data
        assert data["status"] == "running"
    
    def test_health_endpoint(self, test_client):
        """测试健康检查"""
        response = test_client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert "database" in data
        assert data["database"]["connected"] is True


class TestStatsRoutes:
    """测试统计接口"""
    
    def test_stats_overview(self, test_client):
        """测试统计概览"""
        response = test_client.get("/api/v1/stats/overview")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "data" in data
    
    def test_stats_timeline_default(self, test_client):
        """测试时间线统计（默认参数）"""
        response = test_client.get("/api/v1/stats/timeline")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
    
    def test_stats_timeline_with_params(self, test_client):
        """测试时间线统计（带参数）"""
        response = test_client.get(
            "/api/v1/stats/timeline",
            params={
                "granularity": "month",
                "date_from": "2024-01-01",
                "date_to": "2024-12-31"
            }
        )
        assert response.status_code == 200
    
    def test_stats_timeline_invalid_granularity(self, test_client):
        """测试无效粒度参数（会回退到默认值）"""
        response = test_client.get(
            "/api/v1/stats/timeline",
            params={"granularity": "invalid"}
        )
        assert response.status_code == 200
    
    def test_stats_vendors(self, test_client):
        """测试厂商统计"""
        response = test_client.get("/api/v1/stats/vendors")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
    
    def test_stats_vendors_with_trend(self, test_client):
        """测试厂商统计（带趋势）"""
        response = test_client.get(
            "/api/v1/stats/vendors",
            params={"include_trend": True}
        )
        assert response.status_code == 200
    
    def test_stats_update_types(self, test_client):
        """测试更新类型统计"""
        response = test_client.get("/api/v1/stats/update-types")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
    
    def test_stats_years(self, test_client):
        """测试获取年份列表"""
        response = test_client.get("/api/v1/stats/years")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)
    
    def test_stats_product_hotness(self, test_client):
        """测试产品热度排行"""
        response = test_client.get("/api/v1/stats/product-hotness")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
    
    def test_stats_vendor_type_matrix(self, test_client):
        """测试厂商类型矩阵"""
        response = test_client.get("/api/v1/stats/vendor-type-matrix")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True


class TestUpdatesRoutes:
    """测试更新列表接口"""
    
    def test_get_updates_list(self, test_client):
        """测试获取更新列表"""
        response = test_client.get("/api/v1/updates")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "data" in data
    
    def test_get_updates_with_filters(self, test_client):
        """测试带过滤的更新列表"""
        response = test_client.get(
            "/api/v1/updates",
            params={
                "vendor": "aws",
                "page": 1,
                "page_size": 10
            }
        )
        assert response.status_code == 200
    
    def test_get_update_detail(self, test_client):
        """测试获取更新详情"""
        response = test_client.get("/api/v1/updates/api-test-001")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
    
    def test_get_update_detail_not_found(self, test_client):
        """测试获取不存在的更新"""
        response = test_client.get("/api/v1/updates/nonexistent-id")
        # 应该返回 404 或者包含错误信息
        assert response.status_code in [200, 404]


class TestVendorsRoutes:
    """测试厂商接口"""
    
    def test_get_vendors_list(self, test_client):
        """测试获取厂商列表"""
        response = test_client.get("/api/v1/vendors")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)
    
    def test_get_vendor_products(self, test_client):
        """测试获取厂商产品列表"""
        response = test_client.get("/api/v1/vendors/aws/products")
        assert response.status_code == 200


class TestAnalysisRoutes:
    """测试分析接口"""
    
    def test_get_analysis_tasks(self, test_client):
        """测试获取分析任务列表"""
        response = test_client.get("/api/v1/analysis/tasks")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True


class TestDocsEndpoint:
    """测试文档接口"""
    
    def test_docs_available(self, test_client):
        """测试 API 文档可访问"""
        response = test_client.get("/docs")
        assert response.status_code == 200
    
    def test_openapi_schema(self, test_client):
        """测试 OpenAPI schema"""
        response = test_client.get("/openapi.json")
        assert response.status_code == 200
        
        data = response.json()
        assert "openapi" in data
        assert "paths" in data
