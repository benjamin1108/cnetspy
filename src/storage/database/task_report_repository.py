#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
任务报告数据库操作
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict

from src.storage.database.base import BaseRepository

logger = logging.getLogger(__name__)


@dataclass
class IssueItem:
    """问题项"""
    vendor: str
    title: str
    update_id: str
    reason: Optional[str] = None


@dataclass
class TaskReport:
    """
    任务执行报告数据类
    """
    task_date: str
    task_type: str  # daily_crawl_analyze, weekly_report, monthly_report
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: int = 0
    status: str = "pending"  # pending, running, success, partial_fail, failed
    
    # 爬取统计
    crawl_stats: Dict[str, Dict[str, int]] = field(default_factory=dict)  # {vendor: {source_type: new_count}}
    crawl_total: int = 0           # 新增总数
    crawl_discovered: int = 0     # 发现总数
    crawl_skipped: int = 0        # 跳过总数
    
    # 分析统计
    analyze_pending: int = 0
    analyze_success: int = 0
    analyze_failed: int = 0
    marked_non_network: int = 0
    missing_subcategory: int = 0
    
    # 问题详情
    non_network_items: List[IssueItem] = field(default_factory=list)
    missing_subcat_items: List[IssueItem] = field(default_factory=list)
    failed_items: List[IssueItem] = field(default_factory=list)
    
    # 报告内容
    report_content: str = ""
    
    def start(self):
        """标记任务开始"""
        self.start_time = datetime.now()
        self.status = "running"
    
    def finish(self, success: bool = True):
        """标记任务结束"""
        self.end_time = datetime.now()
        if self.start_time:
            self.duration_seconds = int((self.end_time - self.start_time).total_seconds())
        
        if not success:
            self.status = "failed"
        elif self.analyze_failed > 0 or self.marked_non_network > 0 or self.missing_subcategory > 0:
            self.status = "partial_fail"
        else:
            self.status = "success"
    
    def add_crawl_result(self, vendor: str, source_type: str, new_count: int, discovered: int = 0, skipped: int = 0):
        """添加爬取结果
        
        Args:
            vendor: 厂商
            source_type: 源类型
            new_count: 新增数
            discovered: 发现数
            skipped: 跳过数
        """
        if vendor not in self.crawl_stats:
            self.crawl_stats[vendor] = {}
        self.crawl_stats[vendor][source_type] = new_count
        self.crawl_total += new_count
        self.crawl_discovered += discovered
        self.crawl_skipped += skipped
    
    def add_non_network(self, vendor: str, title: str, update_id: str):
        """添加非网络相关项"""
        self.non_network_items.append(IssueItem(vendor=vendor, title=title, update_id=update_id))
        self.marked_non_network += 1
    
    def add_missing_subcategory(self, vendor: str, title: str, update_id: str):
        """添加无产品分类项"""
        self.missing_subcat_items.append(IssueItem(vendor=vendor, title=title, update_id=update_id))
        self.missing_subcategory += 1
    
    def add_failed(self, vendor: str, title: str, update_id: str, reason: str):
        """添加分析失败项"""
        self.failed_items.append(IssueItem(vendor=vendor, title=title, update_id=update_id, reason=reason))
        self.analyze_failed += 1
    
    def get_issue_details(self) -> Dict[str, Any]:
        """获取问题详情 JSON"""
        return {
            "non_network": [asdict(item) for item in self.non_network_items],
            "missing_subcategory": [asdict(item) for item in self.missing_subcat_items],
            "failed": [asdict(item) for item in self.failed_items]
        }


class TaskReportRepository(BaseRepository):
    """任务报告数据库操作"""
    
    def save_report(self, report: TaskReport) -> int:
        """
        保存任务报告
        
        Args:
            report: TaskReport 对象
            
        Returns:
            插入的记录 ID
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO task_reports (
                        task_date, task_type, start_time, end_time, duration_seconds,
                        status, crawl_stats, crawl_total, analyze_pending, analyze_success,
                        analyze_failed, marked_non_network, missing_subcategory,
                        issue_details, report_content
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    report.task_date,
                    report.task_type,
                    report.start_time.isoformat() if report.start_time else None,
                    report.end_time.isoformat() if report.end_time else None,
                    report.duration_seconds,
                    report.status,
                    json.dumps(report.crawl_stats, ensure_ascii=False),
                    report.crawl_total,
                    report.analyze_pending,
                    report.analyze_success,
                    report.analyze_failed,
                    report.marked_non_network,
                    report.missing_subcategory,
                    json.dumps(report.get_issue_details(), ensure_ascii=False),
                    report.report_content
                ))
                
                conn.commit()
                return cursor.lastrowid
                
        except Exception as e:
            self.logger.error(f"保存任务报告失败: {e}")
            raise
    
    def get_report_by_date(self, task_date: str, task_type: str = "daily_crawl_analyze") -> Optional[Dict[str, Any]]:
        """
        按日期获取报告
        
        Args:
            task_date: 日期字符串 YYYY-MM-DD
            task_type: 任务类型
            
        Returns:
            报告数据字典
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM task_reports
                    WHERE task_date = ? AND task_type = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                ''', (task_date, task_type))
                
                row = cursor.fetchone()
                if row:
                    result = dict(row)
                    if result.get('crawl_stats'):
                        result['crawl_stats'] = json.loads(result['crawl_stats'])
                    if result.get('issue_details'):
                        result['issue_details'] = json.loads(result['issue_details'])
                    return result
                return None
                
        except Exception as e:
            self.logger.error(f"获取任务报告失败: {e}")
            return None
    
    def get_recent_reports(self, days: int = 7, task_type: str = "daily_crawl_analyze") -> List[Dict[str, Any]]:
        """
        获取最近的报告列表
        
        Args:
            days: 天数
            task_type: 任务类型
            
        Returns:
            报告列表
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM task_reports
                    WHERE task_type = ? AND task_date >= date('now', ?)
                    ORDER BY task_date DESC
                ''', (task_type, f'-{days} days'))
                
                results = []
                for row in cursor.fetchall():
                    result = dict(row)
                    if result.get('crawl_stats'):
                        result['crawl_stats'] = json.loads(result['crawl_stats'])
                    if result.get('issue_details'):
                        result['issue_details'] = json.loads(result['issue_details'])
                    results.append(result)
                
                return results
                
        except Exception as e:
            self.logger.error(f"获取报告列表失败: {e}")
            return []
