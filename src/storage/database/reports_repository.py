#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
报告数据仓库

存储和查询周报/月报数据
"""

import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from .base import BaseRepository


class ReportRepository(BaseRepository):
    """
    报告数据仓库
    
    负责报告的存储和查询
    """
    
    def save_report(
        self,
        report_type: str,
        year: int,
        month: Optional[int],
        week: Optional[int],
        date_from: str,
        date_to: str,
        ai_summary: str,
        vendor_stats: Dict[str, Any],
        total_count: int
    ) -> int:
        """
        保存报告（存在则更新）
        
        Args:
            report_type: 报告类型 (weekly/monthly)
            year: 年份
            month: 月份（月报必填）
            week: 周数（周报必填）
            date_from: 开始日期
            date_to: 结束日期
            ai_summary: AI 生成的摘要
            vendor_stats: 厂商统计数据
            total_count: 更新总数
            
        Returns:
            报告 ID
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 检查是否已存在
                cursor.execute('''
                    SELECT id FROM reports 
                    WHERE report_type = ? AND year = ? AND month = ?
                ''', (report_type, year, month))
                
                existing = cursor.fetchone()
                now = datetime.now().isoformat()
                vendor_stats_json = json.dumps(vendor_stats, ensure_ascii=False)
                
                if existing:
                    # 更新
                    cursor.execute('''
                        UPDATE reports SET
                            date_from = ?,
                            date_to = ?,
                            ai_summary = ?,
                            vendor_stats = ?,
                            total_count = ?,
                            generated_at = ?
                        WHERE id = ?
                    ''', (date_from, date_to, ai_summary, vendor_stats_json, 
                          total_count, now, existing['id']))
                    conn.commit()
                    return existing['id']
                else:
                    # 插入
                    cursor.execute('''
                        INSERT INTO reports 
                        (report_type, year, month, week, date_from, date_to, 
                         ai_summary, vendor_stats, total_count, generated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (report_type, year, month, week, date_from, date_to,
                          ai_summary, vendor_stats_json, total_count, now))
                    conn.commit()
                    return cursor.lastrowid
                    
        except Exception as e:
            self.logger.error(f"保存报告失败: {e}")
            raise
    
    def get_report(
        self,
        report_type: str,
        year: int,
        month: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        获取报告
        
        Args:
            report_type: 报告类型
            year: 年份
            month: 月份
            
        Returns:
            报告数据字典，不存在返回 None
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM reports 
                    WHERE report_type = ? AND year = ? AND month = ?
                ''', (report_type, year, month))
                
                row = cursor.fetchone()
                if not row:
                    return None
                
                result = dict(row)
                # 解析 JSON 字段
                if result.get('vendor_stats'):
                    result['vendor_stats'] = json.loads(result['vendor_stats'])
                    
                return result
                
        except Exception as e:
            self.logger.error(f"获取报告失败: {e}")
            return None
    
    def get_available_reports(self, report_type: str) -> List[Dict[str, Any]]:
        """
        获取可用的报告列表
        
        Args:
            report_type: 报告类型
            
        Returns:
            报告列表（仅包含基本信息）
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT id, report_type, year, month, week, 
                           date_from, date_to, total_count, generated_at
                    FROM reports 
                    WHERE report_type = ?
                    ORDER BY year DESC, month DESC
                ''', (report_type,))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            self.logger.error(f"获取报告列表失败: {e}")
            return []
