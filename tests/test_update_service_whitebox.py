#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
UpdateService 白盒测试
"""

from datetime import date, datetime

from src.api.services.update_service import UpdateService


class StubDB:
    """最小化数据库桩对象。"""

    def __init__(self, count=0, rows=None, detail=None):
        self.count = count
        self.rows = rows or []
        self.detail = detail
        self.last_query = None

    def count_updates_with_filters(self, **filters):
        self.last_count_filters = filters
        return self.count

    def query_updates_paginated(self, filters, limit, offset, sort_by, order):
        self.last_query = {
            "filters": filters,
            "limit": limit,
            "offset": offset,
            "sort_by": sort_by,
            "order": order,
        }
        return self.rows

    def get_update_by_id(self, update_id):
        self.last_detail_id = update_id
        return self.detail


class TestUpdateServiceWhiteBox:
    """覆盖内部数据转换与分页逻辑。"""

    def test_process_update_row_handles_invalid_tags_and_internal_fields(self):
        row = {
            "update_id": "u-1",
            "title_translated": "N/A",
            "tags": '{"tag":"wrong-shape"}',
            "publish_date": "2024-12-28",
            "crawl_time": "2024-12-28 12:00:00",
            "created_at": datetime(2024, 12, 28, 12, 30, 0),
            "updated_at": "2024-12-28",
            "source_identifier": "internal-id",
            "file_hash": "hash",
            "metadata_json": "{}",
            "priority": 10,
            "content": "full content",
            "content_summary": "summary",
        }

        result = UpdateService(StubDB())._process_update_row(row)

        assert result["tags"] == []
        assert result["has_analysis"] is False
        assert result["publish_date"] == date(2024, 12, 28)
        assert result["crawl_time"] == "2024-12-28T12:00:00Z"
        assert result["created_at"] == "2024-12-28T12:30:00Z"
        assert result["updated_at"] == "2024-12-28T00:00:00Z"
        assert "source_identifier" not in result
        assert "file_hash" not in result
        assert "metadata_json" not in result
        assert "priority" not in result
        assert "content" not in result
        assert "content_summary" not in result

    def test_process_update_row_preserves_content_for_detail_and_marks_valid_analysis(self):
        row = {
            "update_id": "u-2",
            "title_translated": "测试 AWS 网络更新",
            "tags": '["VPC", "网络"]',
            "publish_date": "bad-date",
            "content": "full content",
            "content_summary": "summary",
        }

        result = UpdateService(StubDB())._process_update_row(row, include_content=True)

        assert result["tags"] == ["VPC", "网络"]
        assert result["has_analysis"] is True
        assert result["publish_date"] is None
        assert result["content"] == "full content"
        assert result["content_summary"] == "summary"

    def test_process_update_row_treats_short_or_nullish_titles_as_unanalyzed(self):
        service = UpdateService(StubDB())

        for invalid_title in ["A", "暂无", "None", "null", "  "]:
            result = service._process_update_row(
                {"update_id": f"id-{invalid_title}", "title_translated": invalid_title}
            )
            assert result["has_analysis"] is False

    def test_get_updates_paginated_builds_offset_and_pagination(self):
        rows = [
            {
                "update_id": "u-3",
                "title_translated": "有效分析",
                "tags": '["tag-1"]',
                "publish_date": "2024-12-20",
            }
        ]
        db = StubDB(count=5, rows=rows)
        service = UpdateService(db)

        items, pagination = service.get_updates_paginated(
            filters={"vendor": "aws"},
            page=2,
            page_size=2,
            sort_by="crawl_time",
            order="asc",
        )

        assert len(items) == 1
        assert items[0]["update_id"] == "u-3"
        assert db.last_query == {
            "filters": {"vendor": "aws"},
            "limit": 2,
            "offset": 2,
            "sort_by": "crawl_time",
            "order": "asc",
        }
        assert pagination.page == 2
        assert pagination.page_size == 2
        assert pagination.total == 5
        assert pagination.total_pages == 3

    def test_get_update_detail_returns_none_when_record_missing(self):
        service = UpdateService(StubDB(detail=None))
        assert service.get_update_detail("missing-id") is None
