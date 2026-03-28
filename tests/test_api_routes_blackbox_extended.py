#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API 路由黑盒测试补强
"""

import os
import shutil
import sys
import tempfile

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture(scope="module")
def extended_client():
    from src.api.app import app
    from src.api.dependencies import get_db
    from src.storage.database import UpdateDataLayer
    from src.storage.database.base import DatabaseManager

    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_api_extended.db")

    with DatabaseManager._lock:
        DatabaseManager._instance = None

    db = UpdateDataLayer(db_path=db_path)
    db.batch_insert_updates(
        [
            {
                "update_id": "raw-ok",
                "vendor": "aws",
                "source_channel": "whatsnew",
                "source_url": "https://aws.example.com/raw-ok",
                "source_identifier": "raw-ok",
                "title": "AWS raw content",
                "description": "content exists",
                "content": "# Markdown Content",
                "publish_date": "2024-12-28",
                "crawl_time": "2024-12-28T12:00:00",
                "product_subcategory": "VPC",
                "tags": '["cloud"]',
            },
            {
                "update_id": "raw-empty",
                "vendor": "aws",
                "source_channel": "network-blog",
                "source_url": "https://aws.example.com/raw-empty",
                "source_identifier": "raw-empty",
                "title": "AWS empty content",
                "description": "content missing",
                "content": "",
                "publish_date": "2024-12-27",
                "crawl_time": "2024-12-27T12:00:00",
                "product_subcategory": "VPC",
            },
            {
                "update_id": "azure-blog",
                "vendor": "azure",
                "source_channel": "blog",
                "source_url": "https://azure.example.com/blog",
                "source_identifier": "azure-blog",
                "title": "Azure blog",
                "description": "azure content",
                "content": "azure content",
                "publish_date": "2024-12-26",
                "crawl_time": "2024-12-26T12:00:00",
                "product_subcategory": "Load Balancer",
            },
        ]
    )

    def override_get_db():
        return db

    app.dependency_overrides[get_db] = override_get_db

    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        with DatabaseManager._lock:
            DatabaseManager._instance = None
        shutil.rmtree(temp_dir, ignore_errors=True)


class BrokenDB:
    def get_database_stats(self):
        raise RuntimeError("db unavailable")


class TestUpdatesRawContentBlackBox:
    def test_get_raw_content_returns_markdown(self, extended_client):
        response = extended_client.get("/api/v1/updates/raw-ok/raw")

        assert response.status_code == 200
        assert response.text == "# Markdown Content"
        assert response.headers["content-type"].startswith("text/markdown")

    def test_get_raw_content_returns_404_when_update_missing(self, extended_client):
        response = extended_client.get("/api/v1/updates/not-exists/raw")

        assert response.status_code == 404
        assert response.json()["detail"] == "更新记录不存在: not-exists"

    def test_get_raw_content_returns_404_when_content_empty(self, extended_client):
        response = extended_client.get("/api/v1/updates/raw-empty/raw")

        assert response.status_code == 404
        assert response.json()["detail"] == "内容为空"


class TestHealthRouteBlackBox:
    def test_health_endpoint_returns_unhealthy_payload_on_database_error(self):
        from src.api.app import app
        from src.api.dependencies import get_db

        app.dependency_overrides[get_db] = lambda: BrokenDB()

        try:
            response = TestClient(app).get("/health")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.json() == {
            "status": "unhealthy",
            "database": {
                "connected": False,
                "error": "db unavailable",
            },
        }


class TestVendorMetadataBlackBox:
    def test_unknown_vendor_products_returns_404(self, extended_client):
        response = extended_client.get("/api/v1/vendors/not-a-vendor/products")

        assert response.status_code == 404
        assert response.json()["detail"] == "厂商不存在: not-a-vendor"

    def test_source_channels_merges_all_blog_variants(self, extended_client):
        response = extended_client.get("/api/v1/source-channels")

        assert response.status_code == 200
        assert response.json()["data"] == [
            {"value": "blog", "label": "Blog", "count": 2},
            {"value": "whatsnew", "label": "What's New", "count": 1},
        ]

    def test_product_subcategories_aggregate_across_vendors(self, extended_client):
        response = extended_client.get("/api/v1/product-subcategories")

        assert response.status_code == 200
        assert response.json()["data"] == [
            {"value": "VPC", "count": 2},
            {"value": "Load Balancer", "count": 1},
        ]
