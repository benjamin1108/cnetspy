#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
报告生成命令行入口

用法:
    python -m src.reports.cli --weekly
    python -m src.reports.cli --monthly
    python -m src.reports.cli --weekly --force
    python -m src.reports.cli --weekly --send
"""

import argparse
import sys
import logging
import logging.config
import os
import yaml
from datetime import datetime, timedelta
from calendar import monthrange
from typing import Optional

from src.reports.weekly_report import WeeklyReport
from src.reports.monthly_report import MonthlyReport
from src.reports.image_generator import ReportImageGenerator, ReportImageResult
from src.storage.database.reports_repository import ReportRepository
from src.notification import NotificationManager
from src.utils.config import get_config

logger = logging.getLogger(__name__)

def init_logging():
    """初始化日志系统"""
    try:
        config_file = os.path.join(os.path.dirname(__file__), '../../config/logging.yaml')
        config_file = os.path.abspath(config_file)
        
        with open(config_file, 'r', encoding='utf-8') as f:
            log_config = yaml.safe_load(f)['logging']
        
        # 确保日志目录存在
        log_filename = log_config.get('handlers', {}).get('file', {}).get('filename')
        if log_filename:
            log_dir = os.path.dirname(log_filename)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)
        
        logging.config.dictConfig(log_config)
    except Exception as e:
        logging.basicConfig(level=logging.INFO)
        print(f"日志配置加载失败，使用默认配置: {e}")

def send_notification(content: str, report_type: str, year: int, week_or_month: int):
    """发送通知"""
    try:
        config = get_config()
        manager = NotificationManager(config.get('notification', {}))
        
        title = ""
        if report_type == 'weekly':
            title = f"云技术周报 ({year}年第{week_or_month}周)"
        else:
            title = f"云技术月报 ({year}年{week_or_month}月)"
            
        # 使用 send_all 发送到所有启用渠道
        results = manager.send_all(title, content)
        
        # 打印结果
        for channel, result in results.items():
            status = "成功" if result.success else f"失败 ({result.message})"
            print(f"  → [通知] {channel}: {status}")
            
    except Exception as e:
        print(f"  → [错误] 通知发送失败: {e}")

def _parse_robot_names(robot_names: Optional[str]) -> Optional[list]:
    """解析逗号分隔的钉钉机器人名称"""
    if not robot_names:
        return None
    names = [name.strip() for name in robot_names.split(',') if name.strip()]
    return names or None


def _send_image_notification(
    title: str,
    image_result: ReportImageResult,
    online_url: str,
    report_content: str,
    robot_names: Optional[list] = None,
):
    """推送报告长图到钉钉"""
    try:
        if not image_result.download_url:
            print(f"  → [警告] 长图已保存但无公网下载链接，跳过钉钉图片推送: {image_result.filepath}")
            return

        config = get_config()
        manager = NotificationManager(config.get('notification', {}))
        content = (
            f"## {title}\n\n"
            f"![{title}]({image_result.download_url})\n\n"
            f"{report_content}\n\n"
            f"[点击查看在线报告]({online_url})"
        )
        result = manager.send_dingtalk(title, content, timeout=20, robot_names=robot_names)
        status = "成功" if result.success else f"失败 ({result.message})"
        print(f"  → [长图推送] dingtalk: {status}")
    except Exception as e:
        print(f"  → [错误] 长图推送到钉钉失败: {e}")


def _generate_report_image(
    report,
    report_type: str,
    title: str,
    content: str,
    filename: str,
) -> ReportImageResult:
    """生成报告长图并保存到 data/report/{type}/"""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    output_path = os.path.join(base_dir, 'data', 'report', report_type, filename)
    generator = ReportImageGenerator()
    return generator.generate_report_image(
        report_type=report_type,
        title=title,
        content=content,
        output_path=output_path,
    )


def generate_weekly_report(
    year: int,
    week: int,
    force: bool = False,
    send: bool = False,
    output: bool = False,
    image: bool = False,
    send_image: bool = False,
    dingtalk_robots: Optional[str] = None,
):
    """
    生成或获取周报
    """
    repo = ReportRepository()
    
    # 1. 计算起止日期
    # ISO 8601: 第一周必须包含 1月4日
    first_day = datetime(year, 1, 4)
    # 计算第一周的周一
    first_monday = first_day - timedelta(days=first_day.weekday())
    # 计算目标周的周一
    start_date = first_monday + timedelta(weeks=week-1)
    end_date = start_date + timedelta(days=6)
    
    # 设置时间范围 (00:00:00 - 23:59:59)
    start_dt = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_dt = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    date_str = f"{start_dt.strftime('%m-%d')} ~ {end_dt.strftime('%m-%d')}"
    print(f"\n[处理中] {year}年第{week}周 ({date_str})")

    content = ""
    
    # 2. 检查数据库缓存
    existing_report = repo.get_report('weekly', year, week=week)
    
    report = None

    if existing_report and not force:
        print(f"  → [缓存] 发现已有报告 (ID: {existing_report.get('id')})，跳过生成")
        
        # 从缓存加载 AI 摘要
        ai_summary = existing_report.get('ai_summary')
        if not ai_summary:
            print("  → [警告] 缓存报告缺少 AI 摘要，尝试重新生成")
            # 只有摘要缺失才回退到生成
            report = WeeklyReport(start_date=start_dt, end_date=end_dt)
            content = report.generate()
        else:
            # 使用现有摘要重新渲染 Markdown (用于通知)
            report = WeeklyReport(start_date=start_dt, end_date=end_dt)
            content = report.render_markdown(ai_summary)
            if output:
                print(content)
    else:
        action = "重新生成" if force and existing_report else "生成"
        print(f"  → [{action}] 开始 AI 分析与生成...")
        try:
            report = WeeklyReport(start_date=start_dt, end_date=end_dt)
            content = report.generate()
            print(f"  → [成功] 周报已生成")
            if output:
                print(content)
        except Exception as e:
            print(f"  → [失败] 生成出错: {e}")
            import traceback
            traceback.print_exc()
            return False

    # 3. 发送通知
    if send and content:
        send_notification(content, 'weekly', year, week)

    # 4. 生成/推送长图
    if (image or send_image) and content:
        try:
            if report is None:
                report = WeeklyReport(start_date=start_dt, end_date=end_dt)
            image_title = f"云网络竞争动态周报 {year}年第{week}周"
            filename = f"{year}-W{week}.png"
            image_result = _generate_report_image(report, 'weekly', image_title, content, filename)
            print(f"  → [长图] 已生成: {image_result.filepath}")
            if image_result.model:
                print(f"  → [长图] 实际模型: {image_result.model}")

            if send_image:
                online_url = f"https://cnetspy.site/next/reports?type=weekly&year={year}&week={week}"
                _send_image_notification(
                    image_title,
                    image_result,
                    online_url,
                    content,
                    robot_names=_parse_robot_names(dingtalk_robots),
                )
        except Exception as e:
            print(f"  → [失败] 长图生成/推送出错: {e}")
            return False
    
    return True

def generate_monthly_report(
    year: int,
    month: int,
    force: bool = False,
    send: bool = False,
    output: bool = False,
    image: bool = False,
    send_image: bool = False,
    dingtalk_robots: Optional[str] = None,
):
    """
    生成或获取月报
    """
    repo = ReportRepository()
    
    # 1. 计算起止日期
    _, last_day = monthrange(year, month)
    start_date = datetime(year, month, 1)
    end_date = datetime(year, month, last_day, 23, 59, 59)
    
    print(f"\n[处理中] {year}年{month}月")
    
    content = ""
    
    # 2. 检查数据库缓存
    existing_report = repo.get_report('monthly', year, month=month)
    
    report = None

    if existing_report and not force:
        print(f"  → [缓存] 发现已有报告 (ID: {existing_report.get('id')})，跳过生成")
        
        ai_summary = existing_report.get('ai_summary')
        if not ai_summary:
            print("  → [警告] 缓存报告缺少 AI 摘要，尝试重新生成")
            report = MonthlyReport(start_date=start_date, end_date=end_date)
            content = report.generate()
        else:
            report = MonthlyReport(start_date=start_date, end_date=end_date)
            content = report.render_markdown(ai_summary)
            if output:
                print(content)
    else:
        action = "重新生成" if force and existing_report else "生成"
        print(f"  → [{action}] 开始 AI 分析与生成...")
        try:
            report = MonthlyReport(start_date=start_date, end_date=end_date)
            content = report.generate()
            print(f"  → [成功] 月报已生成")
            if output:
                print(content)
        except Exception as e:
            print(f"  → [失败] 生成出错: {e}")
            return False

    # 3. 发送通知
    if send and content:
        send_notification(content, 'monthly', year, month)

    # 4. 生成/推送长图
    if (image or send_image) and content:
        try:
            if report is None:
                report = MonthlyReport(start_date=start_date, end_date=end_date)
            image_title = f"云网络竞争动态月报 {year}年{month}月"
            filename = f"{year}-{month:02d}.png"
            image_result = _generate_report_image(report, 'monthly', image_title, content, filename)
            print(f"  → [长图] 已生成: {image_result.filepath}")
            if image_result.model:
                print(f"  → [长图] 实际模型: {image_result.model}")

            if send_image:
                online_url = f"https://cnetspy.site/next/reports?type=monthly&year={year}&month={month}"
                _send_image_notification(
                    image_title,
                    image_result,
                    online_url,
                    content,
                    robot_names=_parse_robot_names(dingtalk_robots),
                )
        except Exception as e:
            print(f"  → [失败] 长图生成/推送出错: {e}")
            return False
        
    return True

def main():
    init_logging()
    
    parser = argparse.ArgumentParser(description='生成周报/月报')
    parser.add_argument('--weekly', action='store_true', help='生成周报')
    parser.add_argument('--monthly', action='store_true', help='生成月报')
    parser.add_argument('--year', type=int, help='指定年份，如 2025')
    parser.add_argument('--month', type=int, help='指定月份，如 11')
    parser.add_argument('--week', type=int, help='指定周次，如 47')
    parser.add_argument('--force', action='store_true', help='强制重新生成（忽略缓存）')
    parser.add_argument('--send', action='store_true', help='发送通知')
    parser.add_argument('--image', action='store_true', help='生成 4K 9:16 报告长图')
    parser.add_argument('--send-image', action='store_true', help='生成长图并推送到钉钉')
    parser.add_argument('--dingtalk-robots', help='仅推送到指定钉钉机器人，多个名称用英文逗号分隔')
    parser.add_argument('--output', action='store_true', help='输出HTML内容到控制台')
    
    args = parser.parse_args()
    
    if not args.weekly and not args.monthly:
        parser.print_help()
        sys.exit(1)
        
    current_year = datetime.now().year
    
    # ==================== 周报逻辑 ====================
    if args.weekly:
        # 情况 A: 指定具体某一周 (--year 2025 --week 10)
        if args.year and args.week:
            generate_weekly_report(args.year, args.week, args.force, args.send, args.output, args.image, args.send_image, args.dingtalk_robots)
            
        # 情况 B: 指定某月的所有周 (--year 2025 --month 11)
        elif args.year and args.month:
            year = args.year
            month = args.month
            print(f"批量生成 {year}年{month}月 的所有周报")
            print("=" * 60)
            
            # 找到所有 Thursday 落在该月的周 (ISO 标准: 周属于哪个月看周四)
            _, last_day = monthrange(year, month)
            processed_weeks = set()
            
            for day in range(1, last_day + 1):
                d = datetime(year, month, day)
                if d.weekday() == 3: # Thursday
                    iso_year, iso_week, _ = d.isocalendar()
                    if (iso_year, iso_week) not in processed_weeks:
                        processed_weeks.add((iso_year, iso_week))
                        generate_weekly_report(iso_year, iso_week, args.force, args.send, args.output, args.image, args.send_image, args.dingtalk_robots)
        
        # 情况 C: 默认生成最新一周
        else:
            # 默认生成上周（根据 WeeklyReport 的默认逻辑）
            # 为了获取正确的 year/week 传递给 generate_weekly_report，我们先计算一下
            today = datetime.now()
            # 默认 WeeklyReport 生成的是上周一到上周日
            last_week_day = today - timedelta(days=7) 
            iso_year, iso_week, _ = last_week_day.isocalendar()
            
            print(f"默认生成最新一周 ({iso_year}年第{iso_week}周)")
            generate_weekly_report(iso_year, iso_week, args.force, args.send, args.output, args.image, args.send_image, args.dingtalk_robots)

    # ==================== 月报逻辑 ====================
    elif args.monthly:
        # 情况 A: 指定具体某一月 (--year 2025 --month 11)
        if args.year and args.month:
            generate_monthly_report(args.year, args.month, args.force, args.send, args.output, args.image, args.send_image, args.dingtalk_robots)
            
        # 情况 B: 批量生成某年所有月份 (--year 2025)
        elif args.year and not args.month:
            year = args.year
            today = datetime.now()
            
            months_to_process = []
            if year < today.year:
                months_to_process = range(1, 13)
            elif year == today.year:
                months_to_process = range(1, today.month + 1)
            else:
                print(f"错误: 无法生成未来年份 {year} 的报告")
                sys.exit(1)
                
            print(f"批量生成 {year} 全年 ({len(months_to_process)}个月)")
            print("=" * 60)
            
            for m in months_to_process:
                generate_monthly_report(year, m, args.force, args.send, args.output, args.image, args.send_image, args.dingtalk_robots)
                
        # 情况 C: 默认生成最新一个月
        else:
            today = datetime.now()
            # 如果是月初(1号)，生成上个月
            if today.day == 1:
                last_month_date = today - timedelta(days=1)
                year = last_month_date.year
                month = last_month_date.month
            else:
                # 否则生成当月
                year = today.year
                month = today.month
            
            print(f"默认生成最新月报 ({year}年{month}月)")
            generate_monthly_report(year, month, args.force, args.send, args.output, args.image, args.send_image, args.dingtalk_robots)

if __name__ == '__main__':
    main()
