#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AnalysisService 白盒测试
"""

import json
from types import SimpleNamespace
from unittest.mock import mock_open

import pytest

from src.api.services.analysis_service import AnalysisService


class StubAnalysisDB:
    def __init__(self):
        self.update_record = None
        self.count_value = 0
        self.created_task = None
        self.task = None
        self.task_rows = []
        self.query_rows = []
        self.status_updates = []
        self.progress_updates = []
        self.updated_analysis = []
        self.db_stats = {"total_updates": 0, "latest_crawl_time": None}
        self.vendor_stats = []
        self.update_type_stats = {}
        self.coverage = 0.0
        self.latest_daily_task_time = None

    def get_update_by_id(self, update_id):
        return self.update_record

    def count_updates_with_filters(self, **filters):
        self.last_count_filters = filters
        return self.count_value

    def create_analysis_task(self, task_data):
        self.created_task = task_data

    def get_task_by_id(self, task_id):
        return self.task

    def update_task_status(self, task_id, status, error_message=None):
        self.status_updates.append((task_id, status, error_message))

    def query_updates_paginated(self, **kwargs):
        self.last_query_kwargs = kwargs
        return self.query_rows

    def increment_task_progress(self, task_id, success_count, fail_count):
        self.progress_updates.append((task_id, success_count, fail_count))

    def list_tasks_paginated(self, limit, offset, status):
        self.last_list_args = (limit, offset, status)
        return self.task_rows

    def get_database_stats(self):
        return self.db_stats

    def get_vendor_statistics(self):
        return self.vendor_stats

    def get_update_type_statistics(self):
        return self.update_type_stats

    def get_analysis_coverage(self):
        return self.coverage

    def get_latest_daily_task_time(self):
        return self.latest_daily_task_time

    def update_analysis_fields(self, update_id, fields):
        self.updated_analysis.append((update_id, fields))


class FakeExecutor:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def execute_analysis(self, update_data):
        self.calls.append(update_data)
        return self.result


class FakeFuture:
    def __init__(self, result):
        self._result = result

    def result(self):
        return self._result


class FakePool:
    def __init__(self, max_workers):
        self.max_workers = max_workers

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def submit(self, fn, arg):
        return FakeFuture(fn(arg))


class TestAnalysisServiceWhiteBox:
    def test_analyze_single_returns_not_found(self):
        service = AnalysisService(StubAnalysisDB())

        result = service.analyze_single("missing")

        assert result == {
            "update_id": "missing",
            "success": False,
            "error": "更新记录不存在",
        }

    def test_analyze_single_skips_existing_analysis(self):
        db = StubAnalysisDB()
        db.update_record = {
            "update_id": "u-1",
            "title_translated": "已有分析",
            "content_summary": "summary",
            "update_type": "new_feature",
            "tags": '["a", "b"]',
            "product_subcategory": "VPC",
            "analysis_filepath": "/tmp/x.json",
        }
        service = AnalysisService(db)

        result = service.analyze_single("u-1")

        assert result["success"] is True
        assert result["skipped"] is True
        assert result["tags"] == ["a", "b"]

    def test_analyze_single_executes_when_force_enabled(self):
        db = StubAnalysisDB()
        db.update_record = {"update_id": "u-2", "title_translated": "已有分析"}
        service = AnalysisService(db)
        executor = FakeExecutor(
            {
                "title_translated": "新分析",
                "content_summary": "摘要",
                "update_type": "enhancement",
                "tags": '["network"]',
                "product_subcategory": "Load Balancer",
                "analysis_filepath": "/tmp/analysis.json",
            }
        )
        service.executor = executor

        result = service.analyze_single("u-2", force=True)

        assert result["success"] is True
        assert result["title_translated"] == "新分析"
        assert result["tags"] == ["network"]
        assert executor.calls == [db.update_record]

    def test_analyze_single_returns_failure_when_executor_returns_none(self):
        db = StubAnalysisDB()
        db.update_record = {"update_id": "u-3"}
        service = AnalysisService(db)
        service.executor = FakeExecutor(None)

        result = service.analyze_single("u-3")

        assert result == {
            "update_id": "u-3",
            "success": False,
            "error": "AI分析失败",
        }

    def test_create_batch_task_raises_when_no_records(self):
        db = StubAnalysisDB()
        service = AnalysisService(db)

        with pytest.raises(ValueError, match="未找到符合条件的更新记录"):
            service.create_batch_task({"vendor": "aws"})

    def test_create_batch_task_creates_task_record(self):
        db = StubAnalysisDB()
        db.count_value = 3
        service = AnalysisService(db)

        task_id = service.create_batch_task({"vendor": "aws"})

        assert task_id.startswith("task_")
        assert db.created_task["task_id"] == task_id
        assert db.created_task["task_status"] == "queued"
        assert json.loads(db.created_task["filters"]) == {"vendor": "aws"}
        assert db.created_task["total_count"] == 3

    def test_execute_batch_task_returns_when_task_missing(self):
        db = StubAnalysisDB()
        service = AnalysisService(db)

        service.execute_batch_task("missing-task")

        assert db.status_updates == []
        assert db.progress_updates == []

    def test_execute_batch_task_updates_progress_and_completion(self, monkeypatch):
        db = StubAnalysisDB()
        db.task = {
            "task_result": json.dumps(
                {"filters": json.dumps({"vendor": "aws"}), "total_count": 2}
            )
        }
        db.query_rows = [{"update_id": "1"}, {"update_id": "2"}]
        service = AnalysisService(db)
        service.executor = FakeExecutor({"ok": True})

        monkeypatch.setattr("src.api.services.analysis_service.ThreadPoolExecutor", FakePool)
        monkeypatch.setattr("src.api.services.analysis_service.as_completed", lambda futures: list(futures.keys()))

        service.execute_batch_task("task-1", max_workers=2)

        assert db.status_updates[0] == ("task-1", "running", None)
        assert db.status_updates[-1] == ("task-1", "completed", None)
        assert db.progress_updates == [("task-1", 1, 0), ("task-1", 2, 0)]
        assert db.last_query_kwargs == {"filters": {"vendor": "aws"}, "limit": 50, "offset": 0}

    def test_execute_batch_task_marks_failed_on_exception(self, monkeypatch):
        db = StubAnalysisDB()
        db.task = {"task_result": {"filters": {}, "total_count": 1}}
        service = AnalysisService(db)
        service.executor = FakeExecutor({"ok": True})

        def broken_query(**kwargs):
            raise RuntimeError("query failed")

        db.query_updates_paginated = broken_query
        monkeypatch.setattr("src.api.services.analysis_service.ThreadPoolExecutor", FakePool)
        monkeypatch.setattr("src.api.services.analysis_service.as_completed", lambda futures: list(futures.keys()))

        service.execute_batch_task("task-err")

        assert db.status_updates[0] == ("task-err", "running", None)
        assert db.status_updates[-1] == ("task-err", "failed", "query failed")

    def test_get_task_detail_parses_json_and_formats_progress(self):
        db = StubAnalysisDB()
        db.task = {
            "task_id": "task-1",
            "task_status": "running",
            "task_result": json.dumps(
                {
                    "filters": json.dumps({"vendor": "aws"}),
                    "total_count": 10,
                    "completed_count": 4,
                    "success_count": 3,
                    "fail_count": 1,
                }
            ),
            "created_at": "2024-12-28 10:00:00",
            "started_at": "2024-12-28 10:01:00",
            "completed_at": None,
        }
        service = AnalysisService(db)

        result = service.get_task_detail("task-1")

        assert result["status"] == "running"
        assert result["filters"] == {"vendor": "aws"}
        assert result["processed_count"] == 4
        assert result["progress"] == 0.4
        assert result["created_at"] == "2024-12-28T10:00:00Z"

    def test_list_tasks_paginated_handles_invalid_payloads(self):
        db = StubAnalysisDB()
        db.task_rows = [
            {
                "task_id": "task-1",
                "task_status": "queued",
                "task_result": "",
                "created_at": "2024-12-28",
            },
            {
                "task_id": "task-2",
                "task_status": "completed",
                "task_result": {
                    "filters": {"vendor": "aws"},
                    "total_count": 2,
                    "completed_count": 2,
                    "success_count": 1,
                    "fail_count": 1,
                },
                "created_at": "2024-12-29 11:00:00",
            },
        ]
        service = AnalysisService(db)

        items, pagination = service.list_tasks_paginated(page=2, page_size=2, status="completed")

        assert len(items) == 2
        assert items[0]["filters"] == {}
        assert items[0]["progress"] == 0.0
        assert items[1]["filters"] == {"vendor": "aws"}
        assert items[1]["progress"] == 1.0
        assert pagination.page == 2
        assert pagination.total == 2
        assert db.last_list_args == (2, 2, "completed")

    def test_get_stats_overview_builds_response(self):
        db = StubAnalysisDB()
        db.db_stats = {"total_updates": 9, "latest_crawl_time": "2024-12-28T10:00:00Z"}
        db.vendor_stats = [{"vendor": "aws", "count": 5, "analyzed": 4}]
        db.update_type_stats = {"new_feature": 3}
        db.coverage = 0.75
        db.latest_daily_task_time = "2024-12-28T08:00:00Z"
        service = AnalysisService(db)

        result = service.get_stats_overview()

        assert result == {
            "total_updates": 9,
            "vendors": {"aws": {"total": 5, "analyzed": 4}},
            "update_types": {"new_feature": 3},
            "last_crawl_time": "2024-12-28T10:00:00Z",
            "last_daily_task_time": "2024-12-28T08:00:00Z",
            "analysis_coverage": 0.75,
        }

    def test_strip_metadata_header_removes_prefixed_metadata(self):
        service = AnalysisService(StubAnalysisDB())
        content = (
            "发布时间: 2024-12-28\n"
            "厂商: AWS\n"
            "产品: VPC\n\n"
            "正文内容\n"
        )

        result = service._strip_metadata_header(content)

        assert result == "正文内容"

    def test_translate_content_returns_existing_translation(self):
        db = StubAnalysisDB()
        db.update_record = {"content_translated": "已有翻译"}
        service = AnalysisService(db)

        result = service.translate_content("u-1")

        assert result["success"] is True
        assert result["skipped"] is True

    def test_translate_content_returns_error_when_missing_content(self):
        db = StubAnalysisDB()
        db.update_record = {"content_translated": "", "content": ""}
        service = AnalysisService(db)

        result = service.translate_content("u-2")

        assert result == {
            "update_id": "u-2",
            "success": False,
            "error": "无原文内容可翻译",
        }

    def test_translate_content_handles_missing_prompt(self, monkeypatch):
        db = StubAnalysisDB()
        db.update_record = {"content": "hello"}
        service = AnalysisService(db)
        monkeypatch.setattr("builtins.open", lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError()))

        result = service.translate_content("u-3")

        assert result["success"] is False
        assert result["error"] == "翻译 Prompt 模板不存在"

    def test_translate_content_handles_client_init_failure(self, monkeypatch):
        db = StubAnalysisDB()
        db.update_record = {"content": "hello", "title_translated": "标题"}
        service = AnalysisService(db)

        monkeypatch.setattr("builtins.open", mock_open(read_data="translate {title}: {content}"))
        monkeypatch.setattr("src.utils.config.get_config", lambda: {"ai_model": {"default": {"model_name": "x"}}})
        monkeypatch.setattr("src.analyzers.gemini_client.GeminiClient", lambda config: (_ for _ in ()).throw(RuntimeError("init failed")))

        result = service.translate_content("u-4")

        assert result["success"] is False
        assert result["error"] == "AI 客户端初始化失败: init failed"

    def test_translate_content_handles_generation_failure(self, monkeypatch):
        db = StubAnalysisDB()
        db.update_record = {"content": "hello", "title_translated": "标题"}
        service = AnalysisService(db)

        class BrokenClient:
            def __init__(self, config):
                pass

            def generate_text(self, prompt):
                raise RuntimeError("generation failed")

        monkeypatch.setattr("builtins.open", mock_open(read_data="translate {title}: {content}"))
        monkeypatch.setattr("src.utils.config.get_config", lambda: {"ai_model": {"default": {"model_name": "x"}}})
        monkeypatch.setattr("src.analyzers.gemini_client.GeminiClient", BrokenClient)

        result = service.translate_content("u-5")

        assert result["success"] is False
        assert result["error"] == "翻译失败: generation failed"

    def test_translate_content_handles_save_failure(self, monkeypatch):
        db = StubAnalysisDB()
        db.update_record = {"content": "hello", "title_translated": "标题"}
        service = AnalysisService(db)

        class SuccessClient:
            def __init__(self, config):
                pass

            def generate_text(self, prompt):
                return "翻译结果"

        def broken_update(update_id, fields):
            raise RuntimeError("save failed")

        db.update_analysis_fields = broken_update
        monkeypatch.setattr("builtins.open", mock_open(read_data="translate {title}: {content}"))
        monkeypatch.setattr("src.utils.config.get_config", lambda: {"ai_model": {"default": {"model_name": "x"}}})
        monkeypatch.setattr("src.analyzers.gemini_client.GeminiClient", SuccessClient)

        result = service.translate_content("u-6")

        assert result["success"] is False
        assert result["error"] == "保存翻译结果失败: save failed"

    def test_translate_content_succeeds_and_strips_metadata(self, monkeypatch):
        db = StubAnalysisDB()
        db.update_record = {
            "content": "发布时间: 2024-12-28\n厂商: AWS\n\n正文内容",
            "title_translated": "标题",
        }
        service = AnalysisService(db)

        class SuccessClient:
            def __init__(self, config):
                self.config = config

            def generate_text(self, prompt):
                assert "正文内容" in prompt
                assert "发布时间" not in prompt
                return "翻译后的正文"

        monkeypatch.setattr("builtins.open", mock_open(read_data="translate {title}: {content}"))
        monkeypatch.setattr("src.utils.config.get_config", lambda: {"ai_model": {"default": {"model_name": "x"}}})
        monkeypatch.setattr("src.analyzers.gemini_client.GeminiClient", SuccessClient)

        result = service.translate_content("u-7")

        assert result == {
            "update_id": "u-7",
            "success": True,
            "content_translated": "翻译后的正文",
        }
        assert db.updated_analysis == [("u-7", {"content_translated": "翻译后的正文"})]
