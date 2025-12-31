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
        ai_summary: Optional[Dict[str, Any]] = None,
        vendor_stats: Dict[str, Any] = {},
        total_count: int = 0,
        html_content: Optional[str] = None,
        html_filepath: Optional[str] = None
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
            ai_summary: AI 生成的摘要（可以是 JSON 字典，也可以是 Markdown 字符串）
            vendor_stats: 厂商统计数据
            total_count: 更新总数
            html_content: HTML 格式的完整报告内容
            html_filepath: HTML 报告文件路径

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

                # 处理 ai_summary：如果是字典则序列化，如果是字符串则直接使用
                ai_summary_value = ai_summary
                if isinstance(ai_summary, dict):
                    ai_summary_value = json.dumps(ai_summary, ensure_ascii=False)

                if existing:
                    # 更新
                    cursor.execute('''
                        UPDATE reports SET
                            date_from = ?,
                            date_to = ?,
                            ai_summary = ?,
                            vendor_stats = ?,
                            total_count = ?,
                            html_content = ?,
                            html_filepath = ?,
                            generated_at = ?
                        WHERE id = ?
                    ''', (date_from, date_to, ai_summary_value, vendor_stats_json,
                          total_count, html_content, html_filepath, now, existing['id']))
                    conn.commit()
                    return existing['id']
                else:
                    # 插入
                    cursor.execute('''
                        INSERT INTO reports
                        (report_type, year, month, week, date_from, date_to,
                         ai_summary, vendor_stats, total_count, html_content, html_filepath, generated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (report_type, year, month, week, date_from, date_to,
                          ai_summary_value, vendor_stats_json, total_count, html_content, html_filepath, now))
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
                    try:
                        result['vendor_stats'] = json.loads(result['vendor_stats'])
                    except json.JSONDecodeError:
                        self.logger.warning(f"Failed to parse vendor_stats JSON for report {result.get('id')}")
                        result['vendor_stats'] = {}


                # 处理 ai_summary：尝试解析 JSON，失败则视为 Markdown（旧数据）
                if result.get('ai_summary'):
                    try:
                        result['ai_summary'] = json.loads(result['ai_summary'])
                    except (json.JSONDecodeError, TypeError):
                        # 旧数据是 Markdown 字符串，保持原样，由上层/前端处理兼容性
                        pass

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
