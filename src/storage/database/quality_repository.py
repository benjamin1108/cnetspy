#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Quality Repository - 质量问题追踪

提供 quality_issues 表的 CRUD 操作，用于追踪 AI 分析过程中的质量问题。

issue_type:
    - empty_subcategory: product_subcategory 为空
    - not_network_related: 非网络相关内容（已自动删除）
    - invalid_subcategory: subcategory 不在枚举中
    - analysis_failed: AI 分析失败

auto_action:
    - deleted: 记录已被自动删除
    - kept: 记录已保留，等待人工处理

status:
    - open: 待处理
    - resolved: 已解决
    - ignored: 已忽略
"""

from datetime import datetime
from typing import Dict, List, Any, Optional

from src.storage.database.base import BaseRepository


class QualityRepository(BaseRepository):
    """质量问题追踪操作"""
    
    def insert_quality_issue(
        self,
        update_id: str,
        issue_type: str,
        auto_action: str,
        vendor: Optional[str] = None,
        title: Optional[str] = None,
        source_url: Optional[str] = None,
        batch_id: Optional[str] = None
    ) -> bool:
        """
        插入质量问题记录
        
        Args:
            update_id: 关联的更新记录 ID
            issue_type: 问题类型
            auto_action: 自动执行的动作 (deleted/kept)
            vendor: 厂商
            title: 标题（冗余存储）
            source_url: 来源链接（冗余存储）
            batch_id: 批次 ID（批量分析时生成）
            
        Returns:
            成功返回 True
        """
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # 确定初始状态
                    status = 'resolved' if auto_action == 'deleted' else 'open'
                    resolved_at = datetime.now().isoformat() if auto_action == 'deleted' else None
                    resolution = 'auto_deleted' if auto_action == 'deleted' else None
                    
                    cursor.execute('''
                        INSERT INTO quality_issues (
                            update_id, vendor, title, source_url,
                            issue_type, auto_action, batch_id,
                            detected_at, status, resolved_at, resolution
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        update_id,
                        vendor,
                        title,
                        source_url,
                        issue_type,
                        auto_action,
                        batch_id,
                        datetime.now().isoformat(),
                        status,
                        resolved_at,
                        resolution
                    ))
                    
                    conn.commit()
                    self.logger.debug(f"记录质量问题: {issue_type} - {update_id}")
                    return True
                    
        except Exception as e:
            self.logger.error(f"插入质量问题记录失败: {e}")
            return False
    
    def get_open_issues(
        self,
        issue_type: Optional[str] = None,
        vendor: Optional[str] = None,
        batch_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        获取待处理的质量问题
        
        Args:
            issue_type: 问题类型过滤
            vendor: 厂商过滤
            batch_id: 批次 ID 过滤
            limit: 每页数量
            offset: 偏移量
            
        Returns:
            质量问题列表
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                where_clauses = ["status = 'open'"]
                params = []
                
                if issue_type:
                    where_clauses.append("issue_type = ?")
                    params.append(issue_type)
                
                if vendor:
                    where_clauses.append("vendor = ?")
                    params.append(vendor)
                
                if batch_id:
                    where_clauses.append("batch_id = ?")
                    params.append(batch_id)
                
                where_clause = " AND ".join(where_clauses)
                params.extend([limit, offset])
                
                sql = f'''
                    SELECT * FROM quality_issues
                    WHERE {where_clause}
                    ORDER BY detected_at DESC
                    LIMIT ? OFFSET ?
                '''
                
                cursor.execute(sql, params)
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            self.logger.error(f"查询待处理问题失败: {e}")
            return []
    
    def count_open_issues(
        self,
        issue_type: Optional[str] = None,
        vendor: Optional[str] = None
    ) -> int:
        """
        统计待处理的质量问题数量
        
        Args:
            issue_type: 问题类型过滤
            vendor: 厂商过滤
            
        Returns:
            问题数量
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                where_clauses = ["status = 'open'"]
                params = []
                
                if issue_type:
                    where_clauses.append("issue_type = ?")
                    params.append(issue_type)
                
                if vendor:
                    where_clauses.append("vendor = ?")
                    params.append(vendor)
                
                where_clause = " AND ".join(where_clauses)
                
                sql = f"SELECT COUNT(*) as count FROM quality_issues WHERE {where_clause}"
                cursor.execute(sql, params)
                
                result = cursor.fetchone()
                return result['count'] if result else 0
                
        except Exception as e:
            self.logger.error(f"统计待处理问题失败: {e}")
            return 0
    
    def get_deleted_issues(
        self,
        issue_type: Optional[str] = None,
        vendor: Optional[str] = None,
        batch_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        获取已删除的记录（审计日志）
        
        Args:
            issue_type: 问题类型过滤
            vendor: 厂商过滤
            batch_id: 批次 ID 过滤
            limit: 每页数量
            offset: 偏移量
            
        Returns:
            已删除记录列表
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                where_clauses = ["auto_action = 'deleted'"]
                params = []
                
                if issue_type:
                    where_clauses.append("issue_type = ?")
                    params.append(issue_type)
                
                if vendor:
                    where_clauses.append("vendor = ?")
                    params.append(vendor)
                
                if batch_id:
                    where_clauses.append("batch_id = ?")
                    params.append(batch_id)
                
                where_clause = " AND ".join(where_clauses)
                params.extend([limit, offset])
                
                sql = f'''
                    SELECT * FROM quality_issues
                    WHERE {where_clause}
                    ORDER BY detected_at DESC
                    LIMIT ? OFFSET ?
                '''
                
                cursor.execute(sql, params)
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            self.logger.error(f"查询已删除记录失败: {e}")
            return []
    
    def resolve_issue(
        self,
        issue_id: int,
        resolution: str
    ) -> bool:
        """
        解决质量问题
        
        Args:
            issue_id: 问题 ID
            resolution: 解决方式 (deleted/fixed/ignored)
            
        Returns:
            成功返回 True
        """
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # 如果是 deleted，同步更新 auto_action 以阻止重爬
                    if resolution == 'deleted':
                        cursor.execute('''
                            UPDATE quality_issues
                            SET status = 'resolved',
                                resolved_at = ?,
                                resolution = ?,
                                auto_action = 'deleted'
                            WHERE id = ?
                        ''', (datetime.now().isoformat(), resolution, issue_id))
                    else:
                        cursor.execute('''
                            UPDATE quality_issues
                            SET status = 'resolved',
                                resolved_at = ?,
                                resolution = ?
                            WHERE id = ?
                        ''', (datetime.now().isoformat(), resolution, issue_id))
                    
                    conn.commit()
                    return cursor.rowcount > 0
                    
        except Exception as e:
            self.logger.error(f"解决问题失败: {e}")
            return False
    
    def ignore_issue(self, issue_id: int) -> bool:
        """
        忽略质量问题
        
        Args:
            issue_id: 问题 ID
            
        Returns:
            成功返回 True
        """
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute('''
                        UPDATE quality_issues
                        SET status = 'ignored',
                            resolved_at = ?,
                            resolution = 'ignored'
                        WHERE id = ?
                    ''', (datetime.now().isoformat(), issue_id))
                    
                    conn.commit()
                    return cursor.rowcount > 0
                    
        except Exception as e:
            self.logger.error(f"忽略问题失败: {e}")
            return False
    
    def get_issue_statistics(self) -> Dict[str, Any]:
        """
        获取质量问题统计
        
        Returns:
            统计信息字典
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 按状态统计
                cursor.execute('''
                    SELECT status, COUNT(*) as count
                    FROM quality_issues
                    GROUP BY status
                ''')
                status_stats = {row['status']: row['count'] for row in cursor.fetchall()}
                
                # 按类型统计（只统计 open 的）
                cursor.execute('''
                    SELECT issue_type, COUNT(*) as count
                    FROM quality_issues
                    WHERE status = 'open'
                    GROUP BY issue_type
                ''')
                type_stats = {row['issue_type']: row['count'] for row in cursor.fetchall()}
                
                # 按厂商统计（只统计 open 的）
                cursor.execute('''
                    SELECT vendor, COUNT(*) as count
                    FROM quality_issues
                    WHERE status = 'open'
                    GROUP BY vendor
                ''')
                vendor_stats = {row['vendor']: row['count'] for row in cursor.fetchall()}
                
                return {
                    'total_open': status_stats.get('open', 0),
                    'total_resolved': status_stats.get('resolved', 0),
                    'total_ignored': status_stats.get('ignored', 0),
                    'by_type': type_stats,
                    'by_vendor': vendor_stats
                }
                
        except Exception as e:
            self.logger.error(f"获取问题统计失败: {e}")
            return {
                'total_open': 0,
                'total_resolved': 0,
                'total_ignored': 0,
                'by_type': {},
                'by_vendor': {}
            }
    
    def get_issues_by_batch(self, batch_id: str) -> List[Dict[str, Any]]:
        """
        获取指定批次的所有问题
        
        Args:
            batch_id: 批次 ID
            
        Returns:
            问题列表
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM quality_issues
                    WHERE batch_id = ?
                    ORDER BY detected_at DESC
                ''', (batch_id,))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            self.logger.error(f"查询批次问题失败: {e}")
            return []
    
    def get_issue_by_id(self, issue_id: int) -> Optional[Dict[str, Any]]:
        """
        根据 ID 获取问题记录
        
        Args:
            issue_id: 问题 ID
            
        Returns:
            问题数据字典，不存在返回 None
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM quality_issues WHERE id = ?', (issue_id,))
                
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None
                
        except Exception as e:
            self.logger.error(f"获取问题记录失败: {e}")
            return None
    
    def check_cleaned_by_ai(
        self,
        source_url: str
    ) -> bool:
        """
        检查某条记录是否已被 AI 清洗过（通过 source_url 查询）
        
        用于爬虫去重：如果某条 URL 已被 AI 分析判定为问题记录并删除，
        则不应再次爬取。检查所有类型的删除记录（not_network_related、
        empty_subcategory 等）。
        
        Args:
            source_url: 源链接
            
        Returns:
            如果已被清洗返回 True，否则返回 False
        """
        if not source_url:
            return False
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 检查 quality_issues 表中是否存在该 source_url 且为自动删除
                # 不限制 issue_type，所有被删除的记录都应跳过
                cursor.execute('''
                    SELECT 1 FROM quality_issues
                    WHERE source_url = ?
                    AND auto_action = 'deleted'
                    LIMIT 1
                ''', (source_url,))
                
                result = cursor.fetchone()
                return result is not None
                
        except Exception as e:
            self.logger.error(f"检查AI清洗状态失败: {e}")
            return False
    
    def get_cleaned_urls(
        self,
        issue_type: str = 'not_network_related',
        vendor: Optional[str] = None
    ) -> List[str]:
        """
        获取所有被 AI 清洗过的 source_url 列表
        
        用于批量查询优化，避免逐条检查。
        
        Args:
            issue_type: 问题类型（默认 'not_network_related'）
            vendor: 厂商过滤（可选）
            
        Returns:
            被清洗的 source_url 列表
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                sql = '''
                    SELECT DISTINCT source_url FROM quality_issues
                    WHERE issue_type = ?
                    AND auto_action = 'deleted'
                    AND source_url IS NOT NULL
                '''
                params = [issue_type]
                
                if vendor:
                    sql += " AND vendor = ?"
                    params.append(vendor)
                
                cursor.execute(sql, params)
                return [row['source_url'] for row in cursor.fetchall()]
                
        except Exception as e:
            self.logger.error(f"获取清洗URL列表失败: {e}")
            return []
