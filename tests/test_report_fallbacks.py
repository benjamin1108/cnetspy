#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import datetime

from src.reports.monthly_report import MonthlyReport
from src.reports.weekly_report import WeeklyReport


def test_weekly_markdown_falls_back_when_ai_insight_empty():
    report = object.__new__(WeeklyReport)
    report.start_date = datetime(2026, 5, 25)
    report.end_date = datetime(2026, 5, 31, 23, 59, 59)
    report._update_map = {
        "u-1": {
            "update_id": "u-1",
            "vendor": "aws",
            "source_channel": "whatsnew",
            "title_translated": "AWS Interconnect 推出 500 Mbps 免费档位",
            "content_summary": "降低多云私有互联成本。",
            "publish_date": "2026-05-29",
            "product_subcategory": "interconnect",
        }
    }

    content = report.render_markdown({})

    assert "暂无新的云产品动态更新" not in content
    assert "AWS Interconnect 推出 500 Mbps 免费档位" in content
    assert "本周云网络动态速览" in content


def test_monthly_markdown_falls_back_when_ai_insight_empty():
    report = object.__new__(MonthlyReport)
    report.start_date = datetime(2026, 5, 1)
    report.end_date = datetime(2026, 5, 31, 23, 59, 59)
    report._update_map = {
        "u-1": {
            "update_id": "u-1",
            "vendor": "gcp",
            "source_channel": "network-blog",
            "title_translated": "Google 全球网络演进赋能 AI 时代",
            "content_summary": "介绍全球网络架构演进与 AI 工作负载支撑能力。",
            "publish_date": "2026-05-27",
            "product_subcategory": "global_network",
        }
    }

    content = report.render_markdown({})

    assert "暂无新的云产品动态更新" not in content
    assert "Google 全球网络演进赋能 AI 时代" in content
    assert "本月云网络动态速览" in content


def test_monthly_markdown_normalizes_glued_ai_reference_update_ids():
    report = object.__new__(MonthlyReport)
    report.start_date = datetime(2026, 6, 1)
    report.end_date = datetime(2026, 6, 30, 23, 59, 59)
    update_id = "62a7fd63-ec38-4bc2-af8d-687c2a36a44b"
    glued_id = (
        f"{update_id}2026-06-30-network-blog-AWS Cloud WAN-"
        "基于 Terraform 与 Network MCP Server 的 AWS Transit Gateway 向 AWS Cloud WAN 渐进式迁移实践"
    )
    report._update_map = {
        update_id: {
            "update_id": update_id,
            "vendor": "aws",
            "source_channel": "network-blog",
            "title_translated": "基于 Terraform 与 Network MCP Server 的 AWS Transit Gateway 向 AWS Cloud WAN 渐进式迁移实践",
            "content_summary": "介绍从 Transit Gateway 渐进式迁移到 AWS Cloud WAN 的实践。",
            "publish_date": "2026-06-30",
            "product_subcategory": "AWS Cloud WAN",
        }
    }

    content = report.render_markdown({
        "insight_title": "Cloud WAN 迁移实践集中出现",
        "insight_summary": "本月多篇文章讨论广域网架构迁移。",
        "landmark_updates": [],
        "solution_analysis": [{
            "theme": "AWS Cloud WAN 迁移",
            "summary": "围绕 Transit Gateway 到 Cloud WAN 的渐进式迁移。",
            "references": [{"update_id": glued_id, "title": "查看详情"}],
        }],
        "noteworthy_updates": [],
    })

    assert f"https://cnetspy.site/next/updates/{update_id}" in content
    assert glued_id not in content


def test_weekly_markdown_normalizes_glued_ai_update_ids():
    report = object.__new__(WeeklyReport)
    report.start_date = datetime(2026, 6, 29)
    report.end_date = datetime(2026, 7, 5, 23, 59, 59)
    update_id = "fc2b9941-0cd7-4e32-865c-285eb8391e02"
    glued_id = f"{update_id}2026-06-26-network-blog-AWS Cloud WAN-路由策略实战"
    report._update_map = {
        update_id: {
            "update_id": update_id,
            "vendor": "aws",
            "source_channel": "network-blog",
            "title_translated": "AWS Cloud WAN 路由策略实战",
            "content_summary": "解析全球网络混合场景。",
            "publish_date": "2026-06-26",
            "product_subcategory": "AWS Cloud WAN",
        }
    }

    content = report.render_markdown({
        "insight_title": "Cloud WAN 路由策略",
        "insight_summary": "本周关注 Cloud WAN 路由治理。",
        "top_updates": [{
            "update_id": glued_id,
            "vendor": "AWS",
            "product": "AWS Cloud WAN",
            "title": "AWS Cloud WAN 路由策略实战",
            "pain_point": "跨区域路由策略复杂。",
            "value": "提供策略拆分方法。",
            "comment": "适合全球网络治理场景。",
        }],
        "quick_scan": [],
        "featured_blogs": [],
    })

    assert f"https://cnetspy.site/next/updates/{update_id}" in content
    assert glued_id not in content
