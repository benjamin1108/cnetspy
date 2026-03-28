#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库脏数据与极端参数测试
"""

import os
import sys
import threading
from fastapi.testclient import TestClient

PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, PROJECT_ROOT)


class TestDirtyDataIntegration:
    def test_api_sanitizes_dirty_update_rows(self, data_layer):
        from src.api.app import app
        from src.api.dependencies import get_db

        with data_layer._db_manager.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO updates (
                    update_id, vendor, source_channel, source_url, source_identifier,
                    title, content, publish_date, crawl_time, title_translated, tags
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "dirty-row-1",
                    "aws",
                    "network-blog",
                    "https://example.com/dirty",
                    "dirty-1",
                    "Dirty Row",
                    "raw content",
                    "not-a-date",
                    "2024-12-28 12:30:45",
                    "null",
                    "{bad json",
                ),
            )
            conn.commit()

        app.dependency_overrides[get_db] = lambda: data_layer
        try:
            client = TestClient(app)
            response = client.get("/api/v1/updates/dirty-row-1")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["tags"] == []
        assert data["has_analysis"] is False
        assert data["publish_date"] is None
        assert data["crawl_time"] == "2024-12-28T12:30:45Z"


class TestExtremeQueryParameters:
    def test_repository_falls_back_on_invalid_sort_and_order(self, data_layer, batch_update_data):
        data_layer.batch_insert_updates(batch_update_data)

        results = data_layer.query_updates_paginated(
            filters={},
            limit=5,
            offset=0,
            sort_by="publish_date; DROP TABLE updates",
            order="sideways",
        )

        assert len(results) == 5
        dates = [row["publish_date"] for row in results]
        assert dates == sorted(dates, reverse=True)
        assert data_layer.count_updates_with_filters() == len(batch_update_data)

    def test_blog_filter_matches_all_blog_variants(self, data_layer):
        data_layer.batch_insert_updates(
            [
                {
                    "update_id": "blog-1",
                    "vendor": "aws",
                    "source_channel": "blog",
                    "source_url": "https://example.com/blog-1",
                    "source_identifier": "blog-1",
                    "title": "Blog one",
                    "content": "content",
                    "publish_date": "2024-12-28",
                    "crawl_time": "2024-12-28T10:00:00",
                },
                {
                    "update_id": "blog-2",
                    "vendor": "aws",
                    "source_channel": "network-blog",
                    "source_url": "https://example.com/blog-2",
                    "source_identifier": "blog-2",
                    "title": "Blog two",
                    "content": "content",
                    "publish_date": "2024-12-27",
                    "crawl_time": "2024-12-27T10:00:00",
                },
                {
                    "update_id": "wn-1",
                    "vendor": "aws",
                    "source_channel": "whatsnew",
                    "source_url": "https://example.com/wn-1",
                    "source_identifier": "wn-1",
                    "title": "WhatsNew",
                    "content": "content",
                    "publish_date": "2024-12-26",
                    "crawl_time": "2024-12-26T10:00:00",
                },
            ]
        )

        results = data_layer.query_updates_paginated(
            filters={"source_channel": "blog"},
            limit=10,
            offset=0,
        )

        assert {row["update_id"] for row in results} == {"blog-1", "blog-2"}

    def test_api_rejects_extreme_pagination_params(self, data_layer):
        from src.api.app import app
        from src.api.dependencies import get_db

        app.dependency_overrides[get_db] = lambda: data_layer
        try:
            client = TestClient(app)
            bad_page = client.get("/api/v1/updates?page=0")
            bad_page_size = client.get("/api/v1/updates?page_size=101")
            bad_analysis_page = client.get("/api/v1/analysis/tasks?page_size=0")
            bad_hotness_limit = client.get("/api/v1/stats/product-hotness?limit=101")
        finally:
            app.dependency_overrides.clear()

        assert bad_page.status_code == 422
        assert bad_page_size.status_code == 422
        assert bad_analysis_page.status_code == 422
        assert bad_hotness_limit.status_code == 422


class TestConcurrentDatabaseAccess:
    def test_concurrent_inserts_are_persisted(self, data_layer):
        failures = []

        def insert_one(idx: int):
            try:
                ok = data_layer.insert_update(
                    {
                        "update_id": f"concurrent-{idx}",
                        "vendor": "aws",
                        "source_channel": "whatsnew",
                        "source_url": f"https://example.com/concurrent-{idx}",
                        "source_identifier": f"concurrent-{idx}",
                        "title": f"Concurrent {idx}",
                        "content": "payload",
                        "publish_date": "2024-12-28",
                        "crawl_time": f"2024-12-28T12:{idx:02d}:00",
                    }
                )
                if not ok:
                    failures.append(idx)
            except Exception as exc:
                failures.append((idx, str(exc)))

        threads = [threading.Thread(target=insert_one, args=(i,)) for i in range(20)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert failures == []
        assert data_layer.count_updates() == 20
