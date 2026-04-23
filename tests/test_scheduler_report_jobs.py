#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
调度周报/月报任务测试
"""

from datetime import datetime

from src.scheduler.config import SchedulerConfig
from src.scheduler.jobs import report_job


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
        monkeypatch.setattr(report_job, "_send_report", lambda *args, **kwargs: None)
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
        monkeypatch.setattr(report_job, "_send_report", lambda *args, **kwargs: None)

        generate_calls = []
        monkeypatch.setattr(
            "src.reports.cli._generate_report_image",
            lambda *args, **kwargs: generate_calls.append(args),
        )

        assert report_job.run_monthly_report(config) is True
        assert generate_calls == []
