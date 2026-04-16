#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
报告长图生成器

调用 draw.mindfree.top 的异步图片任务 API，将周报/月报内容生成 9:16 长图。
"""

import base64
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)


DEFAULT_BASE_URL = "https://draw.mindfree.top"
DEFAULT_STYLE_ID = "clay-cute-3d"
DEFAULT_TIMEOUT_SECONDS = 900
DEFAULT_POLL_INTERVAL_SECONDS = 3
MAX_PROMPT_CONTENT_CHARS = 12000


@dataclass
class ReportImageResult:
    """报告长图生成结果"""

    task_id: str
    filepath: str
    download_url: Optional[str] = None
    model: Optional[str] = None


class ReportImageGenerator:
    """调用图片生成 API 并保存生成结果"""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        poll_interval_seconds: int = DEFAULT_POLL_INTERVAL_SECONDS,
        session: Optional[requests.Session] = None,
    ):
        self.base_url = (base_url or os.getenv("REPORT_IMAGE_API_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.style_id = os.getenv("REPORT_IMAGE_STYLE_ID") or DEFAULT_STYLE_ID
        self.timeout_seconds = timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.session = session or requests.Session()

    def generate_report_image(
        self,
        *,
        report_type: str,
        title: str,
        content: str,
        output_path: str,
    ) -> ReportImageResult:
        """
        创建图片任务、轮询完成状态，并保存 PNG。

        API 参数固定为 4K、9:16、质量优先模型。
        """
        task_id = self._create_task(title=title, content=content)
        task = self._wait_for_completion(task_id)
        download_url = self._first_download_url(task, task_id)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        if download_url:
            self._download_image(download_url, output_path)
        else:
            self._save_base64_image(task, output_path)

        model = task.get("model")
        logger.info("%s 长图已保存: %s, model=%s", report_type, output_path, model)
        return ReportImageResult(
            task_id=task_id,
            filepath=output_path,
            download_url=download_url,
            model=model,
        )

    def _create_task(self, *, title: str, content: str) -> str:
        user_content = self._build_user_content(title, content)
        response = self.session.post(
            f"{self.base_url}/api/tasks",
            json={
                "styleId": self.style_id,
                "userContent": user_content,
                "count": 1,
                "aspect": "9:16",
                "size": "4K",
                "modelMode": "quality",
            },
            timeout=30,
        )
        response.raise_for_status()

        data = response.json()
        task_id = data.get("taskId")
        if not task_id:
            raise RuntimeError(f"图片任务创建失败，响应缺少 taskId: {data}")

        logger.info("图片任务已创建: %s", task_id)
        return task_id

    def _wait_for_completion(self, task_id: str) -> Dict[str, Any]:
        deadline = time.monotonic() + self.timeout_seconds

        while True:
            response = self.session.get(f"{self.base_url}/api/tasks/{task_id}", timeout=30)
            response.raise_for_status()
            data = response.json()
            status = data.get("status")

            if status == "completed":
                return data
            if status == "error":
                raise RuntimeError(f"图片任务失败: {data.get('error') or data}")
            if time.monotonic() >= deadline:
                raise TimeoutError(f"图片任务超时未完成: {task_id}")

            time.sleep(self.poll_interval_seconds)

    def _first_download_url(self, task: Dict[str, Any], task_id: str) -> Optional[str]:
        download_urls = task.get("downloadUrls") or []
        if download_urls:
            download_url = str(download_urls[0])
        else:
            download_url = f"/api/tasks/{task_id}/images/1"

        if download_url.startswith("http://") or download_url.startswith("https://"):
            return download_url
        return urljoin(f"{self.base_url}/", download_url.lstrip("/"))

    def _download_image(self, download_url: str, output_path: str) -> None:
        response = self.session.get(download_url, timeout=120)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        if "image/" not in content_type:
            raise RuntimeError(f"下载结果不是图片: {content_type}")

        with open(output_path, "wb") as f:
            f.write(response.content)

    def _save_base64_image(self, task: Dict[str, Any], output_path: str) -> None:
        images = task.get("images") or []
        if not images:
            raise RuntimeError(f"图片任务完成但未返回 downloadUrls 或 images: {task.get('id')}")

        with open(output_path, "wb") as f:
            f.write(base64.b64decode(images[0]))

    def _build_user_content(self, title: str, content: str) -> str:
        clipped_content = content[:MAX_PROMPT_CONTENT_CHARS]
        return f"""请将以下云网络竞争动态报告设计成一张中文竖版长图。

硬性要求：
- 输出比例为 9:16，适合手机端阅读。
- 使用 4K 清晰度，中文标题和正文必须清晰可读。
- 使用服务端 styleId 对应的封装风格。
- 不要虚构厂商 Logo，不要把技术术语画成难以辨认的装饰文字。
- 保留报告中的核心标题、主题摘要、重点更新、快速浏览和链接标题信息。
- 信息层级清晰，适合直接发布到钉钉群。

长图标题：
{title}

报告内容：
{clipped_content}
"""
