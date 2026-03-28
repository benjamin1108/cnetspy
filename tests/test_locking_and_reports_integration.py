#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
锁与报告仓库真实集成测试
"""

import json
import os

from src.storage.database.base import DatabaseManager
from src.storage.database.reports_repository import ReportRepository
from src.utils.distributed_lock import DistributedLock, distributed_lock


class TestDistributedLockIntegration:
    def test_nonblocking_lock_contention_and_release(self, temp_db_path):
        lock_path = f"{temp_db_path}.lock"
        lock1 = DistributedLock(lock_path)
        lock2 = DistributedLock(lock_path)

        assert lock1.acquire(blocking=False) is True
        assert lock2.acquire(blocking=False) is False
        assert lock1.is_locked() is True

        assert lock1.release() is True
        assert lock2.acquire(blocking=False) is True
        assert lock2.release() is True
        assert os.path.exists(lock_path) is False

    def test_context_manager_releases_lock_after_exit(self, temp_db_path):
        lock_path = f"{temp_db_path}.ctx.lock"

        with distributed_lock(lock_path):
            assert os.path.exists(lock_path) is True

        probe = DistributedLock(lock_path)
        assert probe.acquire(blocking=False) is True
        assert probe.release() is True


class TestReportsRepositoryIntegration:
    def test_save_and_update_weekly_report_round_trip(self, temp_db_path):
        DatabaseManager.reset_instance()
        repo = ReportRepository(DatabaseManager(temp_db_path))

        report_id = repo.save_report(
            report_type="weekly",
            year=2024,
            month=None,
            week=52,
            date_from="2024-12-23",
            date_to="2024-12-29",
            ai_summary={"summary": "first"},
            vendor_stats={"aws": {"count": 1}},
            total_count=1,
            html_content="<html>v1</html>",
            html_filepath="/tmp/weekly-v1.html",
        )
        updated_id = repo.save_report(
            report_type="weekly",
            year=2024,
            month=None,
            week=52,
            date_from="2024-12-23",
            date_to="2024-12-29",
            ai_summary="markdown summary",
            vendor_stats={"aws": {"count": 2}},
            total_count=2,
            html_content="<html>v2</html>",
            html_filepath="/tmp/weekly-v2.html",
        )

        report = repo.get_report("weekly", 2024, week=52)

        assert updated_id == report_id
        assert report["ai_summary"] == "markdown summary"
        assert report["vendor_stats"] == {"aws": {"count": 2}}
        assert report["total_count"] == 2
        assert report["html_filepath"] == "/tmp/weekly-v2.html"

    def test_get_report_tolerates_dirty_vendor_stats_json(self, temp_db_path):
        DatabaseManager.reset_instance()
        manager = DatabaseManager(temp_db_path)
        repo = ReportRepository(manager)

        report_id = repo.save_report(
            report_type="monthly",
            year=2024,
            month=12,
            week=None,
            date_from="2024-12-01",
            date_to="2024-12-31",
            ai_summary={"summary": "monthly"},
            vendor_stats={"aws": {"count": 3}},
            total_count=3,
        )

        with manager.get_connection() as conn:
            conn.execute(
                "UPDATE reports SET vendor_stats = ?, ai_summary = ? WHERE id = ?",
                ("{bad json", "plain markdown summary", report_id),
            )
            conn.commit()

        report = repo.get_report("monthly", 2024, month=12)

        assert report["vendor_stats"] == {}
        assert report["ai_summary"] == "plain markdown summary"

    def test_get_available_reports_returns_sorted_real_rows(self, temp_db_path):
        DatabaseManager.reset_instance()
        repo = ReportRepository(DatabaseManager(temp_db_path))

        repo.save_report(
            report_type="monthly",
            year=2023,
            month=12,
            week=None,
            date_from="2023-12-01",
            date_to="2023-12-31",
            total_count=1,
        )
        repo.save_report(
            report_type="monthly",
            year=2024,
            month=1,
            week=None,
            date_from="2024-01-01",
            date_to="2024-01-31",
            total_count=2,
        )

        reports = repo.get_available_reports("monthly")

        assert [r["year"] for r in reports[:2]] == [2024, 2023]
