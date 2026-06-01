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
