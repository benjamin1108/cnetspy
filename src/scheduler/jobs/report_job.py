#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
报告生成任务
调用 reports 模块生成周报/月报并推送通知
"""

import logging
from typing import Any
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
        
        logger.info("月报生成完成")
        return True
        
    except Exception as e:
        logger.error(f"月报生成失败: {e}")
        return False

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
