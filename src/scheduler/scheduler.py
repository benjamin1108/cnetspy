#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
调度器核心
基于 APScheduler 实现定时任务调度
"""

import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
import threading

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, JobExecutionEvent

from .config import SchedulerConfig, JobConfig

logger = logging.getLogger(__name__)


class Scheduler:
    """
    定时任务调度器
    
    集成到 API 主进程，作为后台线程运行
    
    使用示例:
        from src.scheduler import Scheduler
        from src.utils.config import get_config
        
        config = get_config()
        scheduler = Scheduler(config.get('scheduler', {}))
        scheduler.start()
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化调度器
        
        Args:
            config: 调度器配置字典
        """
        self.config = SchedulerConfig.from_dict(config)
        self._scheduler: Optional[BackgroundScheduler] = None
        self._lock = threading.Lock()
        self._running = False
        
        # 任务执行函数映射
        self._job_functions: Dict[str, Callable] = {}
        
        # 注册内置任务
        self._register_builtin_jobs()
    
    def _register_builtin_jobs(self) -> None:
        """注册内置任务函数"""
        from .jobs import crawl_job, analyze_job, report_job
        
        self._job_functions = {
            'daily_crawl_analyze': crawl_job.run_daily_crawl_analyze,
            'weekly_report': report_job.run_weekly_report,
            'monthly_report': report_job.run_monthly_report,
        }
    
    def start(self) -> bool:
        """
        启动调度器
        
        Returns:
            是否成功启动
        """
        if not self.config.enabled:
            logger.info("调度器未启用")
            return False
        
        with self._lock:
            if self._running:
                logger.warning("调度器已在运行")
                return True
            
            try:
                self._scheduler = BackgroundScheduler(
                    timezone=self.config.timezone
                )
                
                # 添加任务监听
                self._scheduler.add_listener(
                    self._on_job_event,
                    EVENT_JOB_EXECUTED | EVENT_JOB_ERROR
                )
                
                # 注册所有启用的任务
                for job_name, job_config in self.config.get_enabled_jobs().items():
                    self._add_job(job_name, job_config)
                
                self._scheduler.start()
                self._running = True
                
                logger.info(f"调度器已启动，时区: {self.config.timezone}")
                self._log_scheduled_jobs()
                
                return True
                
            except Exception as e:
                logger.error(f"调度器启动失败: {e}")
                return False
    
    def stop(self) -> None:
        """停止调度器"""
        with self._lock:
            if self._scheduler and self._running:
                self._scheduler.shutdown(wait=False)
                self._running = False
                logger.info("调度器已停止")
    
    def is_running(self) -> bool:
        """检查调度器是否运行中"""
        return self._running
    
    def _add_job(self, job_name: str, job_config: JobConfig) -> None:
        """添加任务到调度器"""
        if job_name not in self._job_functions:
            logger.warning(f"未找到任务函数: {job_name}")
            return
        
        try:
            trigger = CronTrigger.from_crontab(job_config.cron)
            
            self._scheduler.add_job(
                self._job_functions[job_name],
                trigger=trigger,
                id=job_name,
                name=job_name,
                kwargs={'config': job_config},
                replace_existing=True
            )
            
            logger.debug(f"已注册任务: {job_name} ({job_config.cron})")
            
        except Exception as e:
            logger.error(f"注册任务失败 {job_name}: {e}")
    
    def _on_job_event(self, event: JobExecutionEvent) -> None:
        """任务执行事件回调"""
        job_id = event.job_id
        
        if event.exception:
            logger.error(f"任务执行失败: {job_id}, 错误: {event.exception}")
        else:
            logger.info(f"任务执行完成: {job_id}")
    
    def _log_scheduled_jobs(self) -> None:
        """打印已调度的任务列表"""
        if not self._scheduler:
            return
        
        jobs = self._scheduler.get_jobs()
        if not jobs:
            logger.info("当前无已调度任务")
            return
        
        logger.info(f"已调度 {len(jobs)} 个任务:")
        for job in jobs:
            next_run = job.next_run_time
            next_run_str = next_run.strftime('%Y-%m-%d %H:%M:%S') if next_run else '未调度'
            logger.info(f"  - {job.id}: 下次执行 {next_run_str}")
    
    def run_job_now(self, job_name: str) -> bool:
        """
        立即执行指定任务
        
        Args:
            job_name: 任务名称
            
        Returns:
            是否成功触发
        """
        job_config = self.config.get_job(job_name)
        if not job_config:
            logger.error(f"未找到任务配置: {job_name}")
            return False
        
        if job_name not in self._job_functions:
            logger.error(f"未找到任务函数: {job_name}")
            return False
        
        try:
            logger.info(f"手动触发任务: {job_name}")
            self._job_functions[job_name](config=job_config)
            return True
        except Exception as e:
            logger.error(f"任务执行失败: {job_name}, 错误: {e}")
            return False
    
    def get_jobs_status(self) -> List[Dict[str, Any]]:
        """
        获取所有任务状态
        
        Returns:
            任务状态列表
        """
        result = []
        
        for job_name, job_config in self.config.jobs.items():
            status = {
                'name': job_name,
                'cron': job_config.cron,
                'enabled': job_config.enabled,
                'next_run': None,
            }
            
            if self._scheduler and self._running:
                job = self._scheduler.get_job(job_name)
                if job and job.next_run_time:
                    status['next_run'] = job.next_run_time.isoformat()
            
            result.append(status)
        
        return result
