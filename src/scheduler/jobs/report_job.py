#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
报告生成任务
调用 reports 模块生成周报/月报并推送通知
"""

import logging
from typing import List, Any, Dict
from ..config import JobConfig

logger = logging.getLogger(__name__)


def run_weekly_report(config: JobConfig) -> bool:
    """
    执行周报生成任务
    
    Args:
        config: 任务配置
        
    Returns:
        是否成功
    """
    logger.info("=" * 50)
    logger.info("开始生成周报")
    logger.info("=" * 50)
    
    try:
        from src.reports import WeeklyReport
        
        # 生成报告
        report = WeeklyReport()
        content = report.generate()
        
        if not content:
            logger.warning("周报内容为空")
            return False
        
        # 保存报告
        filepath = report.save()
        logger.info(f"周报已保存: {filepath}")
        
        # 推送通知
        if config.notify:
            _send_report(report, content, config.notify, "周报")
        
        logger.info("周报生成完成")
        return True
        
    except Exception as e:
        logger.error(f"周报生成失败: {e}")
        return False


def run_monthly_report(config: JobConfig) -> bool:
    """
    执行月报生成任务
    
    Args:
        config: 任务配置
        
    Returns:
        是否成功
    """
    logger.info("=" * 50)
    logger.info("开始生成月报")
    logger.info("=" * 50)
    
    try:
        from src.reports import MonthlyReport
        
        # 生成报告
        report = MonthlyReport()
        content = report.generate()
        
        if not content:
            logger.warning("月报内容为空")
            return False
        
        # 保存报告
        filepath = report.save()
        logger.info(f"月报已保存: {filepath}")
        
        # 推送通知
        if config.notify:
            _send_report(report, content, config.notify, "月报")
        
        logger.info("月报生成完成")
        return True
        
    except Exception as e:
        logger.error(f"月报生成失败: {e}")
        return False


def _send_report(report: Any, content: str, channels: List[str], report_type: str) -> None:
    """
    推送报告到指定渠道
    
    Args:
        report: 报告对象
        content: 报告内容
        channels: 推送渠道列表
        report_type: 报告类型（周报/月报）
    """
    try:
        from src.utils.config import get_config
        from src.notification.manager import NotificationManager
        from src.notification.base import NotificationChannel
        
        config = get_config()
        manager = NotificationManager(config.get('notification', {}))
        
        title = f"云网动态{report_type}"
        
        # 构建在线查看链接
        # 假设路径规则: /reports?type=weekly&year=2024&week=1
        base_url = "https://cnetspy.site/next/reports"
        year, week_or_month, _ = report.start_date.isocalendar() if report_type == "周报" else (report.start_date.year, report.start_date.month, 0)
        
        if report_type == "周报":
            online_url = f"{base_url}?type=weekly&year={year}&week={week_or_month}"
        else:
            online_url = f"{base_url}?type=monthly&year={year}&month={week_or_month}"
            
        # 统一尾部引导
        content += f"\n由云竞争情报分析平台自动汇总。 [查看网页版详情]({online_url})"

        # 转换渠道名称
        target_channels = []
        for ch in channels:
            if ch == 'dingtalk':
                target_channels.append(NotificationChannel.DINGTALK)
            elif ch == 'email':
                target_channels.append(NotificationChannel.EMAIL)
        
        if target_channels:
            # 回归到普通 Markdown 发送
            results = manager.send_all(
                title, 
                content, 
                channels=target_channels
            )
            for channel, result in results.items():
                if result.success:
                    logger.info(f"{report_type}已推送到 {channel}")
                else:
                    logger.warning(f"{report_type}推送到 {channel} 失败: {result.message}")
        
    except Exception as e:
        logger.warning(f"报告推送失败: {e}")
