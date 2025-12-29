#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
爬取任务
每日定时爬取所有厂商数据，完成后自动触发分析，生成报告并推送
"""

import logging
from datetime import datetime, date
from typing import Dict, Any, Optional, Tuple

from ..config import JobConfig

logger = logging.getLogger(__name__)


def run_daily_crawl_analyze(config: JobConfig) -> bool:
    """
    执行每日爬取+分析任务
    
    流程:
    1. 爬取所有配置的厂商数据
    2. 爬取完成后自动触发分析（如果配置了 auto_analyze）
    3. 收集统计数据，生成报告
    4. 保存报告并发送邮件通知
    
    Args:
        config: 任务配置
        
    Returns:
        是否成功
    """
    from src.storage.database.task_report_repository import TaskReport, TaskReportRepository
    
    logger.info("=" * 50)
    logger.info("开始执行每日爬取+分析任务")
    logger.info("=" * 50)
    
    # 初始化报告
    report = TaskReport(
        task_date=date.today().isoformat(),
        task_type="daily_crawl_analyze"
    )
    report.start()
    
    params = config.params
    vendors = params.get('vendors', [])
    auto_analyze = params.get('auto_analyze', True)
    notify_on_complete = params.get('notify_on_complete', False)
    
    success = True
    
    try:
        # 1. 执行爬取
        crawl_success, crawl_stats = _run_crawl_with_stats(vendors)
        
        # 记录爬取统计（包含发现数、跳过数、新增数）
        for vendor, source_stats in crawl_stats.items():
            for source_type, stat_detail in source_stats.items():
                # stat_detail 是 {'discovered': x, 'new': y, 'skipped': z, ...}
                if isinstance(stat_detail, dict):
                    new_count = stat_detail.get('new', 0)
                    discovered = stat_detail.get('discovered', 0)
                    skipped = stat_detail.get('skipped', 0)
                else:
                    new_count = stat_detail
                    discovered = 0
                    skipped = 0
                report.add_crawl_result(vendor, source_type, new_count, discovered, skipped)
        
        if not crawl_success:
            logger.error("爬取任务失败")
            success = False
        
        # 2. 自动分析
        analyze_stats = {'success': 0, 'failed': 0, 'pending': 0}
        if auto_analyze and crawl_success:
            logger.info("爬取完成，开始自动分析...")
            from .analyze_job import run_analyze_with_stats
            analyze_success, analyze_stats = run_analyze_with_stats(start_time=report.start_time)
            if not analyze_success:
                logger.warning("分析任务部分失败")
        
        # 记录分析统计
        report.analyze_pending = analyze_stats.get('pending', 0)
        report.analyze_success = analyze_stats.get('success', 0)
        report.analyze_failed = analyze_stats.get('failed', 0)
        
        # 3. 收集质量问题统计（只统计本次任务产生的）
        _collect_quality_issues(report, report.start_time)
        
        # 4. 完成报告
        report.finish(success)
        
        # 5. 生成 HTML 报告
        report.report_content = _generate_report_html(report)
        
        # 6. 保存报告
        try:
            repo = TaskReportRepository()
            repo.save_report(report)
            logger.info("任务报告已保存")
        except Exception as e:
            logger.error(f"保存报告失败: {e}")
        
        # 7. 发送通知
        if notify_on_complete and config.notify:
            _send_report_email(report)
        
        logger.info("=" * 50)
        logger.info(f"每日爬取+分析任务完成，状态: {report.status}")
        logger.info("=" * 50)
        
        return success
        
    except Exception as e:
        logger.error(f"每日爬取+分析任务异常: {e}")
        report.finish(success=False)
        return False


def _run_crawl_with_stats(vendors: list) -> Tuple[bool, Dict[str, Dict[str, Dict[str, int]]]]:
    """
    执行爬取并返回统计
    
    Args:
        vendors: 厂商列表，空列表表示爬取所有
        
    Returns:
        (是否成功, 爬取统计字典)
        统计字典格式: {vendor: {source_type: {'discovered': x, 'new': y}}}
    """
    stats: Dict[str, Dict[str, Dict[str, int]]] = {}
    
    try:
        from src.utils.config import get_config
        from src.crawlers.common.crawler_manager import CrawlerManager
        
        config = get_config()
        
        # 过滤厂商
        if vendors:
            sources = config.get('sources', {})
            config['sources'] = {v: sources[v] for v in vendors if v in sources}
            logger.info(f"爬取厂商: {vendors}")
        else:
            logger.info("爬取所有厂商")
        
        # 运行爬虫
        crawler_manager = CrawlerManager(config)
        result, crawl_stats = crawler_manager.run()
        
        if not result and not crawl_stats:
            return False, stats
        
        # 统计结果（使用详细统计信息）
        total_discovered = 0
        total_new = 0
        for vendor, vendor_stats in crawl_stats.items():
            if vendor not in stats:
                stats[vendor] = {}
            for source_type, s in vendor_stats.items():
                stats[vendor][source_type] = {
                    'discovered': s.discovered,
                    'new': s.new_saved,
                    'skipped': s.skipped_exists,
                    'ai_cleaned': s.skipped_ai,
                    'failed': s.failed
                }
                total_discovered += s.discovered
                total_new += s.new_saved
                if s.discovered > 0 or s.new_saved > 0:
                    logger.info(f"爬取完成: {vendor}/{source_type} - 发现 {s.discovered}, 新增 {s.new_saved}")
        
        logger.info(f"爬取总计: 发现 {total_discovered}, 新增 {total_new}")
        return True, stats
        
    except Exception as e:
        logger.error(f"爬取异常: {e}")
        return False, stats


def _collect_quality_issues(report, start_time: datetime) -> None:
    """
    从 quality_issues 表收集本次任务产生的质量问题
    
    Args:
        report: 任务报告对象
        start_time: 任务开始时间，只统计此时间之后检测到的问题
    """
    try:
        from src.storage.database.quality_repository import QualityRepository
        
        repo = QualityRepository()
        start_time_str = start_time.isoformat() if start_time else datetime.now().isoformat()
        
        # 获取本次任务产生的质量问题
        with repo._get_connection() as conn:
            cursor = conn.cursor()
            
            # 查询任务开始后的非网络相关记录
            cursor.execute('''
                SELECT update_id, vendor, title FROM quality_issues
                WHERE issue_type = 'not_network_related'
                AND detected_at >= ?
            ''', (start_time_str,))
            for row in cursor.fetchall():
                report.add_non_network(row['vendor'], row['title'], row['update_id'])
            
            # 查询任务开始后的无产品分类记录
            cursor.execute('''
                SELECT update_id, vendor, title FROM quality_issues
                WHERE issue_type = 'empty_subcategory'
                AND detected_at >= ?
            ''', (start_time_str,))
            for row in cursor.fetchall():
                report.add_missing_subcategory(row['vendor'], row['title'], row['update_id'])
            
            # 查询任务开始后的分析失败记录
            cursor.execute('''
                SELECT update_id, vendor, title FROM quality_issues
                WHERE issue_type = 'analysis_failed'
                AND detected_at >= ?
            ''', (start_time_str,))
            for row in cursor.fetchall():
                report.add_failed(row['vendor'], row['title'], row['update_id'], 'AI 分析失败')
                
    except Exception as e:
        logger.error(f"收集质量问题失败: {e}")


def _generate_report_html(report) -> str:
    """生成 HTML 报告"""
    try:
        from src.scheduler.reports.email_template import generate_daily_report_html
        
        start_time_str = report.start_time.strftime('%H:%M') if report.start_time else ''
        end_time_str = report.end_time.strftime('%H:%M') if report.end_time else ''
        
        return generate_daily_report_html(
            task_date=report.task_date,
            start_time=start_time_str,
            end_time=end_time_str,
            duration_seconds=report.duration_seconds,
            status=report.status,
            crawl_stats=report.crawl_stats,
            crawl_total=report.crawl_total,
            crawl_discovered=report.crawl_discovered,
            crawl_skipped=report.crawl_skipped,
            analyze_success=report.analyze_success,
            analyze_failed=report.analyze_failed,
            marked_non_network=report.marked_non_network,
            missing_subcategory=report.missing_subcategory,
            non_network_items=[{'vendor': i.vendor, 'title': i.title, 'update_id': i.update_id} for i in report.non_network_items],
            missing_subcat_items=[{'vendor': i.vendor, 'title': i.title, 'update_id': i.update_id} for i in report.missing_subcat_items],
            failed_items=[{'vendor': i.vendor, 'title': i.title, 'update_id': i.update_id, 'reason': i.reason} for i in report.failed_items]
        )
    except Exception as e:
        logger.error(f"生成 HTML 报告失败: {e}")
        return ""


def _send_report_email(report) -> None:
    """发送报告邮件"""
    try:
        from src.utils.config import get_config
        from src.notification import NotificationManager
        
        config = get_config()
        manager = NotificationManager(config.get('notification', {}))
        
        title = f"每日数据更新报告 - {report.task_date}"
        
        # 发送 HTML 邮件
        if report.report_content:
            # 通过邮件发送 HTML
            email_notifier = manager.get_notifier('email')
            if email_notifier and email_notifier.enabled:
                email_notifier.send_html(title, report.report_content)
                logger.info("报告邮件已发送")
        
    except Exception as e:
        logger.warning(f"发送报告邮件失败: {e}")
