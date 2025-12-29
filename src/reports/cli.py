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
import logging
import logging.config
import os
import yaml

# 初始化日志配置
def init_logging():
    """初始化日志系统"""
    try:
        # 加载日志配置
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
        logging.basicConfig(level=logging.DEBUG)
        print(f"日志配置加载失败，使用默认配置: {e}")


def main():
    # 初始化日志
    init_logging()
    
    parser = argparse.ArgumentParser(description='生成周报/月报')
    parser.add_argument('--weekly', action='store_true', help='生成周报')
    parser.add_argument('--monthly', action='store_true', help='生成月报')
    parser.add_argument('--year', type=int, help='指定年份，如 2025')
    parser.add_argument('--month', type=int, help='指定月份，如 11')
    parser.add_argument('--send', action='store_true', help='发送通知')
    parser.add_argument('--output', action='store_true', help='输出HTML内容到控制台（默认不输出）')
    
    args = parser.parse_args()
    
    if not args.weekly and not args.monthly:
        parser.print_help()
        sys.exit(1)
    
    from datetime import datetime
    from calendar import monthrange
    from .weekly_report import WeeklyReport
    from .monthly_report import MonthlyReport
    
    # 处理周报
    if args.weekly:
        report = WeeklyReport()
        content = report.generate()
        
        if args.output:
            print(content)
        
        if args.send:
            from src.utils.config import get_config
            from src.notification import NotificationManager
            
            config = get_config()
            manager = NotificationManager(config.get('notification', {}))
            manager.send(content, report_type='weekly')
            print("已发送周报通知")
        
        return
    
    # 处理月报
    # 判断是否批量生成
    if args.year and not args.month:
        # 批量生成指定年份的所有月份报告
        year = args.year
        today = datetime.now()
        
        # 确定要生成的月份范围
        if year < today.year:
            # 历史年份，生成 1-12 月
            months = range(1, 13)
        elif year == today.year:
            # 当年，生成到当前月
            months = range(1, today.month + 1)
        else:
            # 未来年份，不生成
            print(f"错误：无法生成未来年份 {year} 的报告")
            sys.exit(1)
        
        print(f"\n开始批量生成 {year} 年月报，共 {len(list(months))} 个月份\n")
        print("=" * 60)
        
        success_count = 0
        fail_count = 0
        
        for month in months:
            try:
                print(f"\n[正在生成] {year}年{month}月")
                
                # 获取该月的天数
                _, last_day = monthrange(year, month)
                start_date = datetime(year, month, 1)
                end_date = datetime(year, month, last_day, 23, 59, 59)
                
                # 生成报告
                report = MonthlyReport(start_date=start_date, end_date=end_date)
                content = report.generate()
                
                print(f"[✓ 成功] {year}年{month}月 报告已生成")
                success_count += 1
                
                # 如果需要发送通知
                if args.send:
                    from src.utils.config import get_config
                    from src.notification import NotificationManager
                    
                    config = get_config()
                    manager = NotificationManager(config.get('notification', {}))
                    manager.send(content, report_type='monthly', year=year, month=month)
                    print(f"  → 已发送 {year}年{month}月 报告通知")
                
            except Exception as e:
                print(f"[✗ 失败] {year}年{month}月: {e}")
                fail_count += 1
                continue
        
        print("\n" + "=" * 60)
        print(f"\n批量生成完成：")
        print(f"  ✓ 成功: {success_count} 个月")
        print(f"  ✗ 失败: {fail_count} 个月")
        return
    
    # 生成单个月报
    start_date = None
    end_date = None
    
    if args.year and args.month:
        # 指定了年月，生成完整月份的报告
        year = args.year
        month = args.month
        
        # 验证月份
        if month < 1 or month > 12:
            print(f"错误：月份必须在 1-12 之间，当前为 {month}")
            sys.exit(1)
        
        # 获取该月的天数
        _, last_day = monthrange(year, month)
        
        start_date = datetime(year, month, 1)
        end_date = datetime(year, month, last_day, 23, 59, 59)
        
        print(f"生成 {year}年{month}月 完整月份报告：{start_date.date()} 至 {end_date.date()}")
    
    report = MonthlyReport(start_date=start_date, end_date=end_date)
    
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
