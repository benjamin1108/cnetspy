#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API 应用白盒测试
"""

import logging
from unittest.mock import MagicMock, mock_open

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import src.api.app as app_module
from src.api.dependencies import get_db
from src.api.middleware.error_handler import setup_error_handlers


class TestApiAppWhiteBox:
    """覆盖应用初始化和配置分支。"""

    def test_validate_ai_model_config_supports_nested_config(self, monkeypatch):
        monkeypatch.setattr(
            app_module,
            "get_config",
            lambda: {
                "ai_model": {
                    "default": {"model_name": "gemini"},
                    "chatbox": {"model_name": "gpt"},
                }
            },
        )

        app_module._validate_ai_model_config()

    def test_validate_ai_model_config_supports_flat_config(self, monkeypatch):
        monkeypatch.setattr(
            app_module,
            "get_config",
            lambda: {
                "default": {"model_name": "gemini"},
                "chatbox": {"model_name": "gpt"},
            },
        )

        app_module._validate_ai_model_config()

    def test_validate_ai_model_config_raises_with_missing_keys(self, monkeypatch):
        monkeypatch.setattr(
            app_module,
            "get_config",
            lambda: {"ai_model": {"default": {"model_name": ""}, "chatbox": {}}},
        )

        with pytest.raises(RuntimeError) as exc_info:
            app_module._validate_ai_model_config()

        assert "ai_model.default.model_name" in str(exc_info.value)
        assert "ai_model.chatbox.model_name" in str(exc_info.value)

    def test_setup_logging_falls_back_when_config_file_missing(self, monkeypatch):
        basic_config = MagicMock()
        monkeypatch.setattr(app_module.os.path, "exists", lambda path: False)
        monkeypatch.setattr(app_module.logging, "basicConfig", basic_config)

        app_module._setup_logging()

        basic_config.assert_called_once_with(level=logging.INFO)

    def test_setup_logging_warns_and_falls_back_on_invalid_config(self, monkeypatch):
        basic_config = MagicMock()
        warning_logger = MagicMock()

        monkeypatch.setattr(app_module.os.path, "exists", lambda path: True)
        monkeypatch.setattr(app_module.logging, "basicConfig", basic_config)
        monkeypatch.setattr(app_module.logging, "getLogger", lambda name=None: warning_logger)
        monkeypatch.setattr("builtins.open", mock_open(read_data="logging: {}"))
        monkeypatch.setattr(app_module.yaml, "safe_load", lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad yaml")))

        app_module._setup_logging()

        basic_config.assert_called_once_with(level=logging.INFO)
        warning_logger.warning.assert_called_once()

    def test_start_scheduler_returns_none_when_disabled(self, monkeypatch):
        logger = MagicMock()
        monkeypatch.setattr("src.utils.config.get_config", lambda: {"scheduler": {"enabled": False}})

        assert app_module._start_scheduler(logger) is None
        logger.info.assert_called_with("📅 调度器未启用")

    def test_start_scheduler_returns_scheduler_when_started(self, monkeypatch):
        logger = MagicMock()

        class DummyScheduler:
            def __init__(self, config):
                self.config = config

            def start(self):
                return True

        monkeypatch.setattr("src.utils.config.get_config", lambda: {"scheduler": {"enabled": True, "timezone": "UTC"}})
        monkeypatch.setattr("src.scheduler.Scheduler", DummyScheduler)

        scheduler = app_module._start_scheduler(logger)

        assert isinstance(scheduler, DummyScheduler)
        assert scheduler.config["enabled"] is True
        logger.info.assert_called_with("📅 调度器已启动")

    def test_start_scheduler_returns_none_when_lock_not_acquired(self, monkeypatch):
        logger = MagicMock()

        class DummyScheduler:
            def __init__(self, config):
                self.config = config

            def start(self):
                return False

        monkeypatch.setattr("src.utils.config.get_config", lambda: {"scheduler": {"enabled": True}})
        monkeypatch.setattr("src.scheduler.Scheduler", DummyScheduler)

        assert app_module._start_scheduler(logger) is None
        logger.info.assert_called_with("📅 调度器未启动（可能因为调度器进程锁已被其他进程获取）")

    def test_start_scheduler_returns_none_on_exception(self, monkeypatch):
        logger = MagicMock()
        monkeypatch.setattr(
            "src.utils.config.get_config",
            lambda: (_ for _ in ()).throw(RuntimeError("config error")),
        )

        assert app_module._start_scheduler(logger) is None
        logger.warning.assert_called_once()


class TestApiErrorHandlers:
    """覆盖全局错误处理响应。"""

    def test_value_error_handler_returns_400_payload(self):
        app = FastAPI()
        setup_error_handlers(app)

        @app.get("/value-error")
        async def value_error():
            raise ValueError("bad request")

        response = TestClient(app).get("/value-error")

        assert response.status_code == 400
        assert response.json() == {
            "success": False,
            "error": "bad request",
            "message": "请求参数错误",
        }

    def test_global_exception_handler_returns_500_payload(self):
        app = FastAPI()
        setup_error_handlers(app)

        @app.get("/runtime-error")
        async def runtime_error():
            raise RuntimeError("boom")

        response = TestClient(app, raise_server_exceptions=False).get("/runtime-error")

        assert response.status_code == 500
        assert response.json() == {
            "success": False,
            "error": "boom",
            "message": "服务器内部错误",
        }


class TestApiDependencies:
    """覆盖依赖注入生成器。"""

    def test_get_db_yields_data_layer_with_configured_path(self, monkeypatch):
        monkeypatch.setattr("src.api.dependencies.settings.db_path", "/tmp/test-app.db")

        generator = get_db()
        db = next(generator)

        try:
            assert db.db_path == "/tmp/test-app.db"
        finally:
            with pytest.raises(StopIteration):
                next(generator)
