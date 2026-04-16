#!/usr/bin/env python
# -*- coding: utf-8 -*-

import base64

from src.reports.image_generator import ReportImageGenerator


class FakeResponse:
    def __init__(self, payload=None, content=b"", headers=None):
        self.payload = payload or {}
        self.content = content
        self.headers = headers or {"Content-Type": "application/json"}

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, completed_payload, image_content=b"png-bytes"):
        self.completed_payload = completed_payload
        self.image_content = image_content
        self.post_payload = None
        self.get_urls = []

    def post(self, url, json, timeout):
        self.post_payload = json
        return FakeResponse({"taskId": "task-1"})

    def get(self, url, timeout):
        self.get_urls.append(url)
        if url.endswith("/api/tasks/task-1"):
            return FakeResponse(self.completed_payload)
        return FakeResponse(content=self.image_content, headers={"Content-Type": "image/png"})


def test_generate_report_image_uses_download_url(tmp_path):
    session = FakeSession({
        "status": "completed",
        "downloadUrls": ["/api/tasks/task-1/images/1"],
        "model": "gemini-quality-model",
    })
    output_path = tmp_path / "weekly.png"

    result = ReportImageGenerator(
        base_url="https://draw.mindfree.top",
        poll_interval_seconds=0,
        session=session,
    ).generate_report_image(
        report_type="weekly",
        title="测试周报",
        content="测试内容",
        output_path=str(output_path),
    )

    assert output_path.read_bytes() == b"png-bytes"
    assert result.task_id == "task-1"
    assert result.download_url == "https://draw.mindfree.top/api/tasks/task-1/images/1"
    assert result.model == "gemini-quality-model"
    assert session.post_payload["styleId"] == "clay-cute-3d"
    assert "prompt" not in session.post_payload
    assert "finalPrompt" not in session.post_payload
    assert session.post_payload["aspect"] == "9:16"
    assert session.post_payload["size"] == "4K"
    assert session.post_payload["modelMode"] == "quality"
    assert "https://draw.mindfree.top/api/tasks/task-1/images/1" in session.get_urls


def test_generate_report_image_builds_download_url_when_field_missing(tmp_path):
    encoded = base64.b64encode(b"fallback-png").decode("ascii")
    session = FakeSession({"status": "completed", "images": [encoded]})
    output_path = tmp_path / "monthly.png"

    result = ReportImageGenerator(
        base_url="https://draw.mindfree.top",
        poll_interval_seconds=0,
        session=session,
    ).generate_report_image(
        report_type="monthly",
        title="测试月报",
        content="测试内容",
        output_path=str(output_path),
    )

    assert output_path.read_bytes() == b"png-bytes"
    assert result.download_url == "https://draw.mindfree.top/api/tasks/task-1/images/1"
