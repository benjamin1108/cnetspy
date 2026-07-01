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
        "title_translated": "API 测试更新",
        "description": "Test description",
        "content": "![Preview](https://example.com/preview image.png)\n\nTest content for API testing",
        "content_summary": "这是用于分享预览的测试摘要。",
        "publish_date": "2024-12-28",
        "crawl_time": "2024-12-28T12:00:00"
    }
    db.insert_update(test_update)
    private_update = {
        "update_id": "share-private-001",
        "vendor": "aws",
        "source_channel": "network-blog",
        "source_url": "https://aws.amazon.com/private",
        "source_identifier": "private-001",
        "title": "Private connectivity patterns for Amazon Bedrock AgentCore Gateway Targets",
        "title_translated": "Amazon Bedrock AgentCore Gateway 目标私有连接模式解析",
        "description": "Private connectivity patterns",
        "content": "Test private connectivity content",
        "content_summary": (
            "本文介绍了为 Amazon Bedrock AgentCore Gateway 构建私有连接的四种架构模式，"
            "包括 MCP 服务器私有连接、REST API 私有连接、VPC Link 和 Lambda ENI。"
        ),
        "publish_date": "2026-06-03",
        "crawl_time": "2026-06-04T08:00:00",
    }
    db.insert_update(private_update)
    glued_link_update = {
        "update_id": "62a7fd63-ec38-4bc2-af8d-687c2a36a44b",
        "vendor": "aws",
        "source_channel": "network-blog",
        "source_url": "https://aws.amazon.com/cloud-wan-migration",
        "source_identifier": "cloud-wan-migration",
        "title": "Cloud WAN migration",
        "title_translated": "AWS Cloud WAN 迁移实践",
        "description": "Cloud WAN migration practice",
        "content": "Cloud WAN migration content",
        "content_summary": "介绍 Transit Gateway 到 Cloud WAN 的渐进式迁移实践。",
        "publish_date": "2026-06-30",
        "crawl_time": "2026-07-01T01:00:00",
    }
    db.insert_update(glued_link_update)
    
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

    def test_get_update_detail_normalizes_glued_uuid_link(self, test_client):
        """兼容已发报告中 UUID 后粘连日期标题的旧链接"""
        update_id = "62a7fd63-ec38-4bc2-af8d-687c2a36a44b"
        response = test_client.get(f"/api/v1/updates/{update_id}2026-06-30-network-blog-AWS-Cloud-WAN")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["data"]["update_id"] == update_id


class TestShareRoutes:
    """测试分享预览页面"""

    def test_update_share_preview_has_server_rendered_meta(self, test_client):
        response = test_client.get("/share/updates/api-test-001")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

        html = response.text
        assert '<title>AWS API 测试更新</title>' in html
        assert '<meta property="og:title" content="AWS API 测试更新" />' in html
        assert '<meta property="og:description" content="这是用于分享预览的测试摘要。" />' in html
        assert '<meta property="og:url" content="https://cnetspy.site/next/updates/api-test-001" />' in html
        assert '<meta property="og:image" content="https://example.com/preview%20image.png" />' in html
        assert '<div id="root"></div>' in html

    def test_update_share_preview_normalizes_glued_uuid_canonical_url(self, test_client):
        update_id = "62a7fd63-ec38-4bc2-af8d-687c2a36a44b"
        response = test_client.get(f"/share/updates/{update_id}2026-06-30-network-blog-AWS-Cloud-WAN")
        assert response.status_code == 200

        html = response.text
        assert '<title>AWS Cloud WAN 迁移实践</title>' in html
        assert f'<meta property="og:url" content="https://cnetspy.site/next/updates/{update_id}" />' in html

    def test_update_share_preview_supports_head_probe(self, test_client):
        response = test_client.head("/share/updates/api-test-001")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_update_share_preview_frontloads_private_connectivity_terms(self, test_client):
        response = test_client.get("/share/updates/share-private-001")
        assert response.status_code == 200

        html = response.text
        assert '<meta property="og:title" content="AWS 私网连接：Bedrock AgentCore" />' in html
        assert (
            '<meta property="og:description" '
            'content="私网连接模式：MCP、REST API、VPC Link、Lambda ENI，面向合规 AI Agent 后端访问。" />'
        ) in html


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
