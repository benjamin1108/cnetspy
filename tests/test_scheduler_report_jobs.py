#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
调度周报/月报任务测试
"""

import logging
from datetime import datetime, timedelta

from src.scheduler.config import SchedulerConfig
from src.scheduler.jobs import analyze_job, crawl_job, report_job
from src.storage.database.task_report_repository import TaskReport


class DummyReport:
    def __init__(self, start_date):
        self.start_date = start_date

    def generate(self):
        return "report content"

    def save(self):
        return "/tmp/report.html"


class TestSchedulerConfigReportImageFlags:
    def test_weekly_and_monthly_report_enable_image_flags_by_default(self):
        config = SchedulerConfig.from_dict(
            {
                "enabled": True,
                "jobs": {
                    "weekly_report": {"enabled": True, "cron": "0 9 * * mon"},
                    "monthly_report": {"enabled": True, "cron": "0 9 1 * *"},
                },
            }
        )

        assert config.jobs["weekly_report"].params["generate_image"] is True
        assert config.jobs["weekly_report"].params["send_image"] is True
        assert config.jobs["monthly_report"].params["generate_image"] is True
        assert config.jobs["monthly_report"].params["send_image"] is True


class TestScheduledReportJobs:
    def test_run_weekly_report_generates_and_sends_image_by_default(self, monkeypatch):
        calls = []
        config = SchedulerConfig.from_dict({"jobs": {"weekly_report": {}}}).jobs["weekly_report"]

        monkeypatch.setattr("src.reports.WeeklyReport", lambda: DummyReport(datetime(2026, 4, 20)))
        monkeypatch.setattr(
            "src.reports.cli._generate_report_image",
            lambda report, report_key, image_title, content, filename: calls.append(
                ("generate", report_key, image_title, filename)
            ) or type("ImageResult", (), {"filepath": "/tmp/weekly.png", "model": "test-model"})(),
        )
        monkeypatch.setattr(
            "src.reports.cli._send_image_notification",
            lambda title, image_result, online_url, report_content, robot_names=None: calls.append(
                ("send", title, online_url, robot_names)
            ),
        )

        assert report_job.run_weekly_report(config) is True
        assert ("generate", "weekly", "云网络竞争动态周报 2026年第17周", "2026-W17.png") in calls
        assert ("send", "云网络竞争动态周报 2026年第17周", "https://cnetspy.site/next/reports?type=weekly&year=2026&week=17", None) in calls

    def test_run_monthly_report_can_disable_image_generation(self, monkeypatch):
        config = SchedulerConfig.from_dict(
            {
                "jobs": {
                    "monthly_report": {
                        "generate_image": False,
                        "send_image": False,
                    }
                }
            }
        ).jobs["monthly_report"]

        monkeypatch.setattr("src.reports.MonthlyReport", lambda start_date, end_date: DummyReport(start_date))

        generate_calls = []
        monkeypatch.setattr(
            "src.reports.cli._generate_report_image",
            lambda *args, **kwargs: generate_calls.append(args),
        )

        assert report_job.run_monthly_report(config) is True
        assert generate_calls == []


class TestAnalyzeJobStats:
    def test_run_analyze_with_stats_returns_false_when_records_failed(self, monkeypatch, caplog):
        pending_counts = [3, 0]

        class DummyResult:
            returncode = 0
            stdout = "summary: failed=3"
            stderr = "403 PERMISSION_DENIED unrestricted key"

        monkeypatch.setattr(
            analyze_job,
            "_count_pending_analysis",
            lambda vendor=None, source=None: pending_counts.pop(0),
        )
        monkeypatch.setattr(analyze_job, "_count_failed_analysis", lambda start_time=None: 3)
        monkeypatch.setattr(analyze_job.subprocess, "run", lambda *args, **kwargs: DummyResult())

        caplog.set_level(logging.WARNING)

        success, stats = analyze_job.run_analyze_with_stats(start_time=datetime.now())

        assert success is False
        assert stats == {"pending": 3, "success": 0, "failed": 3}
        assert "存在 3 条分析失败" in caplog.text
        assert "403 PERMISSION_DENIED unrestricted key" in caplog.text


class TestDailyCrawlAnalyzeIssueStats:
    def test_collect_quality_issues_does_not_double_count_existing_failure_stats(self, data_layer):
        start_time = datetime.now() - timedelta(minutes=1)
        report = TaskReport(task_date="2026-06-18", task_type="daily_crawl_analyze")
        report.start_time = start_time
        report.analyze_failed = 1

        data_layer.insert_quality_issue(
            update_id="failed-001",
            issue_type="analysis_failed",
            auto_action="kept",
            vendor="gcp",
            title="Failed update",
            source_url="https://example.com/failed",
        )

        analyze_failed_from_stats = report.analyze_failed
        crawl_job._collect_quality_issues(report, start_time)
        crawl_job._sync_analyze_failed_count(report, analyze_failed_from_stats)

        assert len(report.failed_items) == 1
        assert report.analyze_failed == 1
