#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
调度器运行时任务锁测试
"""

from src.scheduler.scheduler import Scheduler


class DummyConfig:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.timezone = "Asia/Shanghai"
        self.jobs = {}

    def get_enabled_jobs(self):
        return {}

    def get_job(self, name):
        return self.jobs.get(name)


class DummyJobConfig:
    def __init__(self, name="daily_crawl_analyze", cron="0 8 * * *"):
        self.name = name
        self.cron = cron
        self.enabled = True
        self.params = {}
        self.notify = []


class FakeLock:
    def __init__(self, lock_file_path, logger=None):
        self.lock_file_path = lock_file_path
        self.logger = logger
        self.release_calls = 0

    def acquire(self, blocking=False):
        return True

    def release(self):
        self.release_calls += 1
        return True


class RejectingLock(FakeLock):
    def acquire(self, blocking=False):
        return False


class TestSchedulerRuntimeLock:
    def test_run_job_with_lock_executes_once_and_releases(self, monkeypatch):
        scheduler = Scheduler({})
        job_config = DummyJobConfig()
        calls = []
        fake_lock = FakeLock("/tmp/test.lock")

        monkeypatch.setattr("src.scheduler.scheduler.SchedulerConfig.from_dict", lambda config: DummyConfig())
        monkeypatch.setattr("src.scheduler.scheduler.DistributedLock", lambda path, logger=None: fake_lock)
        scheduler._job_functions = {
            "daily_crawl_analyze": lambda config: calls.append(config.name) or True,
        }

        assert scheduler._run_job_with_lock("daily_crawl_analyze", job_config) is True
        assert calls == ["daily_crawl_analyze"]
        assert fake_lock.release_calls == 1

    def test_run_job_with_lock_skips_when_duplicate_triggered(self, monkeypatch):
        scheduler = Scheduler({})
        job_config = DummyJobConfig()
        calls = []

        monkeypatch.setattr("src.scheduler.scheduler.SchedulerConfig.from_dict", lambda config: DummyConfig())
        monkeypatch.setattr("src.scheduler.scheduler.DistributedLock", lambda path, logger=None: RejectingLock(path, logger))
        scheduler._job_functions = {
            "daily_crawl_analyze": lambda config: calls.append(config.name) or True,
        }

        assert scheduler._run_job_with_lock("daily_crawl_analyze", job_config) is False
        assert calls == []
