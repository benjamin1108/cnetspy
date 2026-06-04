#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
分享预览页面

为 SPA 详情页生成服务端可见的 Open Graph 元数据，供钉钉、微信等分享抓取器读取。
"""

import html
import re
from pathlib import Path
from typing import Optional
from urllib.parse import quote, urlsplit, urlunsplit

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from src.storage.database.sqlite_layer import UpdateDataLayer
from ..config import settings
from ..dependencies import get_db
from ..services.update_service import UpdateService


router = APIRouter(tags=["分享预览"])

DEFAULT_TITLE = "CloudNetSpy - 云计算竞争情报系统"
DEFAULT_DESCRIPTION = "多云更新聚合 + AI智能分析 + 情报推送"
SHARE_TITLE_MAX_LENGTH = 34
SHARE_DESCRIPTION_MAX_LENGTH = 86
VENDOR_LABELS = {
    "aws": "AWS",
    "azure": "Azure",
    "gcp": "GCP",
    "huawei": "华为云",
    "tencentcloud": "腾讯云",
    "volcengine": "火山引擎",
}


@router.api_route(
    "/share/updates/{update_id}",
    methods=["GET", "HEAD"],
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def update_share_preview(
    update_id: str,
    db: UpdateDataLayer = Depends(get_db),
):
    """
    返回带有动态 OG 标签的 SPA HTML。

    Nginx 将公开路径 /next/updates/{id} 转发到这里；浏览器仍会加载同一个
    React 应用，分享抓取器则能在首包 HTML 中读到标题、摘要和图片。
    """
    service = UpdateService(db)
    update = service.get_update_detail(update_id)
    metadata = _build_update_metadata(update_id, update)
    html_content = _inject_share_metadata(_load_spa_index_html(), metadata)
    return HTMLResponse(html_content)


def _build_update_metadata(update_id: str, update: Optional[dict]) -> dict:
    canonical_url = _join_url(settings.public_site_url, f"/next/updates/{update_id}")

    if not update:
        return {
            "title": DEFAULT_TITLE,
            "description": DEFAULT_DESCRIPTION,
            "url": canonical_url,
            "image": _join_url(settings.public_site_url, "/next/vite.svg"),
            "published_time": "",
        }

    raw_title = _compact_text(
        update.get("title_translated") or update.get("title") or DEFAULT_TITLE,
        max_length=120,
    )
    raw_description = _compact_text(
        update.get("content_summary") or update.get("description") or raw_title or DEFAULT_DESCRIPTION,
        max_length=260,
    )
    image = _extract_first_markdown_image(
        update.get("content_translated") or update.get("content") or ""
    )
    title = _build_share_title(raw_title, update)
    description = _build_share_description(raw_description, raw_title, update)

    return {
        "title": title or DEFAULT_TITLE,
        "description": description or DEFAULT_DESCRIPTION,
        "url": canonical_url,
        "image": image or _join_url(settings.public_site_url, "/next/vite.svg"),
        "published_time": str(update.get("publish_date") or ""),
    }


def _build_share_title(title: str, update: dict) -> str:
    vendor = VENDOR_LABELS.get((update.get("vendor") or "").lower(), update.get("vendor") or "")
    normalized = _normalize_share_text(title)
    normalized = _strip_vendor_prefix(normalized)

    if "私网连接" in normalized:
        subject = normalized.split("私网连接", 1)[0]
        subject = re.sub(r"(目标|模式|解析|实践)$", "", subject).strip(" ：:-")
        subject = _fit_words(subject, 21)
        return _truncate_text(f"{vendor} 私网连接：{subject}".strip(), SHARE_TITLE_MAX_LENGTH)

    prefix = f"{vendor} " if vendor and not normalized.startswith(vendor) else ""
    return _truncate_text(f"{prefix}{normalized}", SHARE_TITLE_MAX_LENGTH)


def _build_share_description(description: str, title: str, update: dict) -> str:
    source = _normalize_share_text(description)
    title_text = _normalize_share_text(title)

    if "私网连接" in source or "私网连接" in title_text:
        terms = _extract_known_terms(source)
        if terms:
            return _truncate_text(
                f"私网连接模式：{'、'.join(terms)}，面向合规 AI Agent 后端访问。",
                SHARE_DESCRIPTION_MAX_LENGTH,
            )

    source = _strip_intro_prefix(source)
    return _truncate_text(source or DEFAULT_DESCRIPTION, SHARE_DESCRIPTION_MAX_LENGTH)


def _normalize_share_text(text: str) -> str:
    text = text or ""
    text = text.replace("私有连接", "私网连接")
    text = text.replace("Amazon ", "")
    return re.sub(r"\s+", " ", text).strip()


def _strip_vendor_prefix(text: str) -> str:
    return re.sub(r"^(AWS|Azure|GCP|Google Cloud|华为云|腾讯云|火山引擎)\s+", "", text).strip()


def _strip_intro_prefix(text: str) -> str:
    stripped = re.sub(
        r"^(本文|文章|本篇文章|这篇文章)(主要)?(介绍了|介绍|讲解了|说明了|概述了)",
        "",
        text,
    )
    if stripped != text:
        return stripped.strip(" ，。:：")
    return text.strip()


def _extract_known_terms(text: str) -> list[str]:
    candidates = [
        ("MCP", r"\bMCP\b|MCP 服务器"),
        ("REST API", r"\bREST API\b"),
        ("VPC Lattice", r"\bVPC Lattice\b"),
        ("VPC Link", r"\bVPC Link\b"),
        ("Lambda ENI", r"\bLambda\b|ENI\b|Hyperplane ENI"),
    ]
    terms = []
    for label, pattern in candidates:
        if re.search(pattern, text, flags=re.IGNORECASE) and label not in terms:
            terms.append(label)
    return terms[:5]


def _truncate_text(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - 3].rstrip() + "..."


def _fit_words(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text

    parts = text.split()
    if len(parts) <= 1:
        return _truncate_text(text, max_length)

    while parts and len(" ".join(parts)) > max_length:
        parts.pop()
    return " ".join(parts) or _truncate_text(text, max_length)


def _load_spa_index_html() -> str:
    for path in _candidate_index_paths():
        if path and path.exists():
            return path.read_text(encoding="utf-8")

    return """<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>CloudNetSpy - 云计算竞争情报系统</title>
    <meta name="description" content="多云更新聚合 + AI智能分析 + 情报推送" />
  </head>
  <body>
    <div id="root"></div>
  </body>
</html>"""


def _candidate_index_paths() -> list[Path]:
    configured_path = Path(settings.spa_index_path).expanduser() if settings.spa_index_path else None
    project_root = Path(__file__).resolve().parents[3]

    paths = []
    if configured_path:
        paths.append(configured_path)
    paths.extend(
        [
            Path.home() / "cnetspy-deploy" / "index.html",
            project_root / "web" / "dist" / "index.html",
            project_root / "web" / "index.html",
        ]
    )
    return paths


def _inject_share_metadata(index_html: str, metadata: dict) -> str:
    title = _escape_attr(metadata["title"])
    description = _escape_attr(metadata["description"])
    canonical_url = _escape_attr(metadata["url"])
    image = _escape_attr(metadata["image"])
    published_time = _escape_attr(metadata.get("published_time") or "")

    index_html = re.sub(
        r"<title>.*?</title>",
        f"<title>{title}</title>",
        index_html,
        count=1,
        flags=re.IGNORECASE | re.DOTALL,
    )
    index_html = re.sub(
        r'<meta\s+name=["\']description["\'][^>]*>',
        f'<meta name="description" content="{description}" />',
        index_html,
        count=1,
        flags=re.IGNORECASE,
    )

    tags = [
        f'<link rel="canonical" href="{canonical_url}" />',
        '<meta property="og:type" content="article" />',
        f'<meta property="og:title" content="{title}" />',
        f'<meta property="og:description" content="{description}" />',
        f'<meta property="og:url" content="{canonical_url}" />',
        f'<meta property="og:image" content="{image}" />',
        '<meta name="twitter:card" content="summary_large_image" />',
        f'<meta name="twitter:title" content="{title}" />',
        f'<meta name="twitter:description" content="{description}" />',
        f'<meta name="twitter:image" content="{image}" />',
    ]

    if published_time:
        tags.append(f'<meta property="article:published_time" content="{published_time}" />')

    metadata_html = "\n    ".join(tags)
    if "</head>" in index_html:
        return index_html.replace("</head>", f"    {metadata_html}\n  </head>", 1)
    return f"{index_html}\n{metadata_html}\n"


def _compact_text(value: str, max_length: int) -> str:
    text = value or ""
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[`*_>#|~-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    if len(text) <= max_length:
        return text
    return text[: max_length - 3].rstrip() + "..."


def _extract_first_markdown_image(markdown: str) -> str:
    match = re.search(r"!\[[^\]]*\]\(([^)]+)\)", markdown or "")
    if not match:
        return ""

    raw_url = match.group(1).strip().strip("<>")
    if not raw_url:
        return ""

    if raw_url.startswith("/"):
        raw_url = _join_url(settings.public_site_url, raw_url)

    if not raw_url.startswith(("http://", "https://")):
        return ""

    return _normalize_url(raw_url)


def _normalize_url(url: str) -> str:
    parts = urlsplit(url)
    path = quote(parts.path, safe="/:%")
    query = quote(parts.query, safe="=&?/:%,+")
    return urlunsplit((parts.scheme, parts.netloc, path, query, parts.fragment))


def _join_url(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + "/" + path.lstrip("/")


def _escape_attr(value: str) -> str:
    return html.escape(value or "", quote=True)
