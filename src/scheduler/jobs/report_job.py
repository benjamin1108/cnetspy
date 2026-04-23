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

        _generate_and_send_report_image(
            report=report,
            content=content,
            report_type="周报",
            config=config,
        )
        
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
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo
        from src.reports import MonthlyReport

        # 生成上个月完整月报（避免时区导致的范围偏移）
        now = datetime.now(ZoneInfo("Asia/Shanghai"))
        last_month_end = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(seconds=1)
        last_month_start = last_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        report = MonthlyReport(start_date=last_month_start, end_date=last_month_end)
        content = report.generate()
        
        if not content:
            logger.warning("月报内容为空")
            return False
        
        # 保存报告
        filepath = report.save()
        logger.info(f"月报已保存: {filepath}")

        _generate_and_send_report_image(
            report=report,
            content=content,
            report_type="月报",
            config=config,
        )
        
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
        
        title = f"云网络竞争动态{report_type}"
        
        # 构建在线查看链接
        # 假设路径规则: /reports?type=weekly&year=2024&week=1
        base_url = "https://cnetspy.site/next/reports"
        year, week_or_month, _ = report.start_date.isocalendar() if report_type == "周报" else (report.start_date.year, report.start_date.month, 0)
        
        if report_type == "周报":
            online_url = f"{base_url}?type=weekly&year={year}&week={week_or_month}"
        else:
            online_url = f"{base_url}?type=monthly&year={year}&month={week_or_month}"
            
        # 统一尾部引导
        content += f"\n由CNetSpy竞争分析平台自动汇总。 [点击访问]({online_url})"

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


def _generate_and_send_report_image(
    report: Any,
    content: str,
    report_type: str,
    config: JobConfig,
) -> None:
    """按调度配置生成报告长图，并在需要时推送到钉钉。"""
    try:
        generate_image = config.params.get("generate_image", True)
        send_image = config.params.get("send_image", True)
        if not generate_image and not send_image:
            return

        from src.reports.cli import (
            _generate_report_image,
            _parse_robot_names,
            _send_image_notification,
        )

        if report_type == "周报":
            year, week, _ = report.start_date.isocalendar()
            image_title = f"云网络竞争动态周报 {year}年第{week}周"
            filename = f"{year}-W{week}.png"
            online_url = f"https://cnetspy.site/next/reports?type=weekly&year={year}&week={week}"
            report_key = "weekly"
        else:
            year = report.start_date.year
            month = report.start_date.month
            image_title = f"云网络竞争动态月报 {year}年{month}月"
            filename = f"{year}-{month:02d}.png"
            online_url = f"https://cnetspy.site/next/reports?type=monthly&year={year}&month={month}"
            report_key = "monthly"

        image_result = _generate_report_image(
            report,
            report_key,
            image_title,
            content,
            filename,
        )
        logger.info("%s长图已生成: %s", report_type, image_result.filepath)
        if image_result.model:
            logger.info("%s长图实际模型: %s", report_type, image_result.model)

        if send_image:
            _send_image_notification(
                image_title,
                image_result,
                online_url,
                content,
                robot_names=_parse_robot_names(config.params.get("dingtalk_robots")),
            )
    except Exception as e:
        logger.warning("%s长图生成或推送失败: %s", report_type, e)
