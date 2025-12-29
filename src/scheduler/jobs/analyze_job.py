#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
分析任务
批量分析未处理的更新记录
"""

import logging
import subprocess
import sys
import os
from datetime import datetime
from typing import Tuple, Dict

logger = logging.getLogger(__name__)


def run_analyze(
    vendor: str = None,
    source: str = None,
    limit: int = 0
) -> bool:
    """
    执行分析任务
    
    调用现有的 scripts/analyze_updates.py 脚本
    
    Args:
        vendor: 指定厂商
        source: 指定数据源
        limit: 限制数量
        
    Returns:
        是否成功
    """
    success, _ = run_analyze_with_stats(vendor, source, limit)
    return success


def run_analyze_with_stats(
    vendor: str = None,
    source: str = None,
    limit: int = 0,
    start_time: datetime = None
) -> Tuple[bool, Dict[str, int]]:
    """
    执行分析任务并返回统计
    
    Args:
        vendor: 指定厂商
        source: 指定数据源
        limit: 限制数量
        start_time: 任务开始时间（用于统计本次任务产生的问题）
        
    Returns:
        (是否成功, 统计字典 {pending, success, failed})
    """
    logger.info("开始执行分析任务")
    
    stats = {'pending': 0, 'success': 0, 'failed': 0}
    
    try:
        # 分析前查询待分析数
        pending_before = _count_pending_analysis(vendor, source)
        stats['pending'] = pending_before
        logger.info(f"待分析记录数: {pending_before}")
        
        if pending_before == 0:
            logger.info("无待分析记录，跳过分析")
            return True, stats
        
        # 构建命令
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        script_path = os.path.join(base_dir, 'scripts', 'analyze_updates.py')
        
        cmd = [sys.executable, script_path]
        
        if vendor:
            cmd.extend(['--vendor', vendor])
        if source:
            cmd.extend(['--source', source])
        if limit > 0:
            cmd.extend(['--limit', str(limit)])
        
        logger.info(f"执行命令: {' '.join(cmd)}")
        
        # 执行脚本
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=base_dir
        )
        
        # 分析后直接从数据库获取统计
        pending_after = _count_pending_analysis(vendor, source)
        failed_count = _count_failed_analysis(start_time)
        
        # 计算成功数 = 已处理数 - 失败数
        processed = pending_before - pending_after
        success_count = max(0, processed - failed_count)
        
        stats['success'] = success_count
        stats['failed'] = failed_count
        
        logger.info(f"分析统计: 待分析={pending_before}, 成功={success_count}, 失败={failed_count}")
        
        if result.returncode == 0:
            logger.info("分析任务完成")
            return True, stats
        else:
            logger.error(f"分析任务失败: {result.stderr}")
            return False, stats
            
    except Exception as e:
        logger.error(f"分析任务异常: {e}")
        return False, stats


def _count_pending_analysis(vendor: str = None, source: str = None) -> int:
    """
    查询待分析记录数
    
    待分析条件: title_translated IS NULL 或为空
    """
    try:
        from src.storage.database.base import BaseRepository
        
        repo = BaseRepository()
        with repo._get_connection() as conn:
            cursor = conn.cursor()
            
            where_clauses = [
                "(title_translated IS NULL OR title_translated = '' OR LENGTH(TRIM(title_translated)) < 2)"
            ]
            params = []
            
            if vendor:
                where_clauses.append("vendor = ?")
                params.append(vendor)
            
            if source:
                where_clauses.append("source_channel = ?")
                params.append(source)
            
            where_clause = " AND ".join(where_clauses)
            sql = f"SELECT COUNT(*) as count FROM updates WHERE {where_clause}"
            
            cursor.execute(sql, params)
            result = cursor.fetchone()
            return result['count'] if result else 0
            
    except Exception as e:
        logger.error(f"查询待分析数失败: {e}")
        return 0


def _count_failed_analysis(start_time: datetime = None) -> int:
    """
    查询本次任务产生的分析失败数
    
    从 quality_issues 表统计 issue_type = 'analysis_failed' 的记录
    """
    try:
        from src.storage.database.quality_repository import QualityRepository
        
        repo = QualityRepository()
        with repo._get_connection() as conn:
            cursor = conn.cursor()
            
            if start_time:
                start_time_str = start_time.isoformat()
                cursor.execute('''
                    SELECT COUNT(*) as count FROM quality_issues
                    WHERE issue_type = 'analysis_failed'
                    AND detected_at >= ?
                ''', (start_time_str,))
            else:
                # 如果没有 start_time，统计今日的
                cursor.execute('''
                    SELECT COUNT(*) as count FROM quality_issues
                    WHERE issue_type = 'analysis_failed'
                    AND date(detected_at) = date('now')
                ''')
            
            result = cursor.fetchone()
            return result['count'] if result else 0
            
    except Exception as e:
        logger.error(f"查询失败分析数失败: {e}")
        return 0
