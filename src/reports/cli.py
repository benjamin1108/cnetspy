#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
报告生成命令行入口

用法:
    python -m src.reports.cli --weekly
    python -m src.reports.cli --monthly
    python -m src.reports.cli --weekly --send
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description='生成周报/月报')
    parser.add_argument('--weekly', action='store_true', help='生成周报')
    parser.add_argument('--monthly', action='store_true', help='生成月报')
    parser.add_argument('--send', action='store_true', help='发送通知')
    parser.add_argument('--output', action='store_true', help='输出HTML内容到控制台（默认不输出）')
    
    args = parser.parse_args()
    
    if not args.weekly and not args.monthly:
        parser.print_help()
        sys.exit(1)
    
    from .weekly_report import WeeklyReport
    from .monthly_report import MonthlyReport
    
    if args.weekly:
        report = WeeklyReport()
    else:
        report = MonthlyReport()
    
    # 生成报告
    content = report.generate()
    
    # 只在明确请求时才输出HTML
    if args.output:
        print(content)
    
    # 发送通知
    if args.send:
        from src.utils.config import get_config
        from src.notification import NotificationManager
        
        config = get_config()
        manager = NotificationManager(config.get('notification', {}))
        title = f'云网动态{report.report_name}'
        result = manager.send_all(title, content)
        
        print('\n---', file=sys.stderr)
        for ch, r in result.items():
            status = '成功' if r.success else '失败'
            print(f'推送 {ch}: {status}', file=sys.stderr)


if __name__ == '__main__':
    main()
