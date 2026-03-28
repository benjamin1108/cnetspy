#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
剩余 API 路由黑盒测试
"""

import json
import os
import sys
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.api.app import app
from src.api.dependencies import get_db


@pytest.fixture
def simple_client():
    class DummyDB:
        pass

    app.dependency_overrides[get_db] = lambda: DummyDB()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


class TestAnalysisRoutesBlackBox:
    def test_analyze_single_returns_payload(self, simple_client, monkeypatch):
        monkeypatch.setattr(
            "src.api.routes.analysis.AnalysisService.analyze_single",
            lambda self, update_id, force=False: {
                "update_id": update_id,
                "success": True,
                "title_translated": "标题",
                "content_summary": "摘要",
                "update_type": "new_feature",
                "tags": ["network"],
                "product_subcategory": "VPC",
                "analysis_filepath": "/tmp/a.json",
                "error": None,
            },
        )

        response = simple_client.post("/api/v1/analysis/single/u-1?force=true")

        assert response.status_code == 200
        assert response.json()["data"]["update_id"] == "u-1"

    def test_analyze_single_returns_500_on_service_failure(self, simple_client, monkeypatch):
        monkeypatch.setattr(
            "src.api.routes.analysis.AnalysisService.analyze_single",
            lambda self, update_id, force=False: {"success": False, "error": "分析失败"},
        )

        response = simple_client.post("/api/v1/analysis/single/u-2")

        assert response.status_code == 500
        assert response.json()["detail"] == "分析失败"

    def test_translate_route_returns_500_on_failure(self, simple_client, monkeypatch):
        monkeypatch.setattr(
            "src.api.routes.analysis.AnalysisService.translate_content",
            lambda self, update_id: {"success": False, "error": "翻译失败"},
        )

        response = simple_client.post("/api/v1/analysis/translate/u-3")

        assert response.status_code == 500
        assert response.json()["detail"] == "翻译失败"

    def test_batch_route_returns_400_when_no_records(self, simple_client, monkeypatch):
        monkeypatch.setattr(
            "src.api.routes.analysis.AnalysisService.create_batch_task",
            lambda self, filters, batch_size=50: (_ for _ in ()).throw(ValueError("未找到符合条件的更新记录")),
        )

        response = simple_client.post("/api/v1/analysis/batch", json={"filters": {"vendor": "aws"}, "batch_size": 10})

        assert response.status_code == 400
        assert response.json()["detail"] == "未找到符合条件的更新记录"

    def test_batch_route_returns_task_detail(self, simple_client, monkeypatch):
        monkeypatch.setattr(
            "src.api.routes.analysis.AnalysisService.create_batch_task",
            lambda self, filters, batch_size=50: "task-1",
        )
        monkeypatch.setattr(
            "src.api.routes.analysis.AnalysisService.execute_batch_task",
            lambda self, task_id: None,
        )
        monkeypatch.setattr(
            "src.api.routes.analysis.AnalysisService.get_task_detail",
            lambda self, task_id: {
                "task_id": task_id,
                "status": "queued",
                "filters": {"vendor": "aws"},
                "total_count": 3,
                "processed_count": 0,
                "success_count": 0,
                "fail_count": 0,
                "progress": 0.0,
                "created_at": "2024-12-28T10:00:00Z",
                "started_at": None,
                "completed_at": None,
                "error_message": None,
            },
        )

        response = simple_client.post("/api/v1/analysis/batch", json={"filters": {"vendor": "aws"}, "batch_size": 10})

        assert response.status_code == 200
        assert response.json()["data"]["task_id"] == "task-1"

    def test_get_task_status_returns_404(self, simple_client, monkeypatch):
        monkeypatch.setattr("src.api.routes.analysis.AnalysisService.get_task_detail", lambda self, task_id: None)

        response = simple_client.get("/api/v1/analysis/tasks/missing")

        assert response.status_code == 404

    def test_list_tasks_returns_500_when_service_raises(self, simple_client, monkeypatch):
        monkeypatch.setattr(
            "src.api.routes.analysis.AnalysisService.list_tasks_paginated",
            lambda self, page, page_size, status=None: (_ for _ in ()).throw(RuntimeError("boom")),
        )

        response = simple_client.get("/api/v1/analysis/tasks")

        assert response.status_code == 500
        assert response.json()["detail"] == "boom"


class TestReportsRoutesBlackBox:
    def test_get_report_rejects_invalid_type(self, simple_client):
        response = simple_client.get("/api/v1/reports/daily")

        assert response.status_code == 200
        assert response.json()["success"] is False

    def test_get_report_returns_error_when_missing_report(self, simple_client, monkeypatch):
        monkeypatch.setattr("src.api.routes.reports.ReportRepository", lambda: SimpleNamespace(get_report=lambda *args, **kwargs: None))

        response = simple_client.get("/api/v1/reports/weekly?year=2024&week=1")

        assert response.status_code == 200
        assert response.json()["success"] is False
        assert "报告未生成" in response.json()["error"]

    def test_get_report_returns_enriched_report(self, simple_client, monkeypatch):
        report_data = {
            "date_from": "2024-12-23",
            "date_to": "2024-12-29",
            "generated_at": "2024-12-29T09:00:00Z",
            "ai_summary": "summary",
            "html_filepath": "/tmp/report.html",
            "total_count": 1,
            "vendor_stats": {
                "aws": {
                    "count": 1,
                    "updates": [
                        {
                            "update_id": "u-1",
                            "title": "AWS 发布",
                            "publish_date": "2024-12-28",
                            "update_type": "new_feature",
                        }
                    ],
                }
            },
        }

        monkeypatch.setattr("src.api.routes.reports.ReportRepository", lambda: SimpleNamespace(get_report=lambda *args, **kwargs: report_data))

        class ReportDB:
            def get_update_by_id(self, update_id):
                return {
                    "title": "AWS 发布",
                    "content_summary": "摘要",
                    "product_subcategory": "VPC",
                    "source_channel": "whatsnew",
                    "update_type": "new_feature",
                    "publish_date": "2024-12-28",
                }

        app.dependency_overrides[get_db] = lambda: ReportDB()
        try:
            response = TestClient(app).get("/api/v1/reports/weekly?year=2024&week=1")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        body = response.json()["data"]
        assert body["report_type"] == "weekly"
        assert body["vendor_summaries"][0]["vendor"] == "aws"
        assert body["updates_by_vendor"]["aws"][0]["content_summary"] == "摘要"

    def test_available_months_and_weeks_filter_invalid_rows(self, simple_client, monkeypatch):
        monkeypatch.setattr(
            "src.api.routes.reports.ReportRepository",
            lambda: SimpleNamespace(
                get_available_reports=lambda report_type: [
                    {"year": 2024, "month": 12, "week": 52, "date_from": "2024-12-23", "date_to": "2024-12-29"},
                    {"year": None, "month": None, "week": None},
                ]
            ),
        )

        months = simple_client.get("/api/v1/reports/monthly/available-months")
        weeks = simple_client.get("/api/v1/reports/weekly/available-weeks")

        assert months.status_code == 200
        assert months.json()["data"] == [{"year": 2024, "month": 12, "label": "2024年12月"}]
        assert weeks.json()["data"] == [
            {
                "year": 2024,
                "week": 52,
                "label": "2024年第52周",
                "date_from": "2024-12-23",
                "date_to": "2024-12-29",
            }
        ]


class TestChatRoutesBlackBox:
    def test_get_prompts_returns_default_on_error(self, simple_client, monkeypatch):
        monkeypatch.setattr(
            "src.api.routes.chat.get_config",
            lambda key=None: (_ for _ in ()).throw(RuntimeError("config missing")),
        )

        response = simple_client.get("/api/v1/chat/prompts")

        assert response.status_code == 200
        assert "CloudNetSpy" in response.json()["system_prompt"]

    def test_get_prompts_returns_configured_values(self, simple_client, monkeypatch):
        monkeypatch.setattr(
            "src.api.routes.chat.get_config",
            lambda key=None: {
                "system_prompt": "sys",
                "summary_prompt": "sum",
                "tools_description_template": "tpl",
                "vendor_names": {"aws": "AWS"},
            },
        )

        response = simple_client.get("/api/v1/chat/prompts")

        assert response.status_code == 200
        assert response.json()["system_prompt"] == "sys"

    def test_chat_completions_returns_500_when_model_name_missing(self, simple_client, monkeypatch):
        monkeypatch.setattr("src.api.routes.chat.get_gemini_client", lambda: (SimpleNamespace(), {}))

        response = simple_client.post(
            "/api/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "hello"}]},
        )

        assert response.status_code == 500
        assert "model_name" in response.json()["detail"]

    def test_chat_completions_returns_500_when_api_call_fails(self, simple_client, monkeypatch):
        class ConfigType:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        class BrokenClient:
            class models:
                @staticmethod
                def generate_content(**kwargs):
                    raise RuntimeError("api down")

        monkeypatch.setattr("src.api.routes.chat.types", SimpleNamespace(GenerateContentConfig=ConfigType))
        monkeypatch.setattr(
            "src.api.routes.chat.get_gemini_client",
            lambda: (BrokenClient(), {"model_name": "gemini-test"}),
        )

        response = simple_client.post(
            "/api/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "hello"}]},
        )

        assert response.status_code == 500
        assert response.json()["detail"] == "AI 调用失败: api down"

    def test_chat_completions_returns_text_response(self, simple_client, monkeypatch):
        class ConfigType:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        class Client:
            class models:
                @staticmethod
                def generate_content(**kwargs):
                    return SimpleNamespace(text="你好，已收到。")

        monkeypatch.setattr("src.api.routes.chat.types", SimpleNamespace(GenerateContentConfig=ConfigType))
        monkeypatch.setattr(
            "src.api.routes.chat.get_gemini_client",
            lambda: (Client(), {"model_name": "gemini-test"}),
        )

        response = simple_client.post(
            "/api/v1/chat/completions",
            json={
                "messages": [
                    {"role": "system", "content": "system"},
                    {"role": "user", "content": "hello"},
                ],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "list_updates",
                            "description": "List updates",
                            "parameters": {},
                        },
                    }
                ],
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["model"] == "gemini-test"
        assert body["choices"][0]["message"]["content"] == "你好，已收到。"
