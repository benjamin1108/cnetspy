#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
调度配置加载
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class JobConfig:
    """任务配置"""
    name: str
    cron: str
    enabled: bool = True
    params: Dict[str, Any] = field(default_factory=dict)
    notify: List[str] = field(default_factory=list)


@dataclass
class SchedulerConfig:
    """调度器配置"""
    enabled: bool = False
    timezone: str = "Asia/Shanghai"
    jobs: Dict[str, JobConfig] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> 'SchedulerConfig':
        """从字典加载配置"""
        if not config:
            return cls()
        
        jobs = {}
        jobs_config = config.get('jobs', {})
        
        # 解析每日爬取+分析任务
        if 'daily_crawl_analyze' in jobs_config:
            job_cfg = jobs_config['daily_crawl_analyze']
            jobs['daily_crawl_analyze'] = JobConfig(
                name='daily_crawl_analyze',
                cron=job_cfg.get('cron', '0 8 * * *'),
                enabled=job_cfg.get('enabled', True),
                params={
                    'vendors': job_cfg.get('vendors', []),
                    'auto_analyze': job_cfg.get('auto_analyze', True),
                    'notify_on_complete': job_cfg.get('notify_on_complete', False),
                },
                notify=job_cfg.get('notify', [])
            )
        
        # 解析周报任务
        if 'weekly_report' in jobs_config:
            job_cfg = jobs_config['weekly_report']
            jobs['weekly_report'] = JobConfig(
                name='weekly_report',
                cron=job_cfg.get('cron', '0 9 * * 1'),
                enabled=job_cfg.get('enabled', True),
                notify=job_cfg.get('notify', ['dingtalk'])
            )
        
        # 解析月报任务
        if 'monthly_report' in jobs_config:
            job_cfg = jobs_config['monthly_report']
            jobs['monthly_report'] = JobConfig(
                name='monthly_report',
                cron=job_cfg.get('cron', '0 9 1 * *'),
                enabled=job_cfg.get('enabled', True),
                notify=job_cfg.get('notify', ['dingtalk', 'email'])
            )
        
        return cls(
            enabled=config.get('enabled', False),
            timezone=config.get('timezone', 'Asia/Shanghai'),
            jobs=jobs
        )
    
    def get_job(self, name: str) -> Optional[JobConfig]:
        """获取指定任务配置"""
        return self.jobs.get(name)
    
    def get_enabled_jobs(self) -> Dict[str, JobConfig]:
        """获取所有启用的任务"""
        return {name: job for name, job in self.jobs.items() if job.enabled}
