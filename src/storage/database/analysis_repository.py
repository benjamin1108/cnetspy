#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Analysis Repository - 分析相关操作

提供 AI 分析相关的查询和更新操作。
"""

from typing import Dict, List, Any, Optional

from src.storage.database.base import BaseRepository


class AnalysisRepository(BaseRepository):
    """分析相关数据库操作"""
    
    def get_unanalyzed_updates(
        self, 
        limit: Optional[int] = None, 
        vendor: Optional[str] = None,
        source_channel: Optional[str] = None,
        include_analyzed: bool = False
    ) -> List[Dict[str, Any]]:
        """
        获取未分析的更新记录
        
        Args:
            limit: 最大返回数量，None 表示不限制
            vendor: 指定厂商，None 表示所有厂商
            source_channel: 指定数据源类型（如 blog, whatsnew），支持模糊匹配
            include_analyzed: 是否包含已分析的记录（用于 --force）
            
        Returns:
            未分析的更新记录列表
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 构建查询条件
                where_clauses = [
                    "content IS NOT NULL",
                    "content != ''"
                ]
                
                # 如果不包含已分析的，添加未分析条件
                if not include_analyzed:
                    where_clauses.append("title_translated IS NULL")
                
                params = []
                
                if vendor:
                    where_clauses.append("vendor = ?")
                    params.append(vendor)
                
                # source_channel 模糊匹配（如 blog 匹配 network-blog, tech-blog 等）
                if source_channel:
                    where_clauses.append("source_channel LIKE ?")
                    params.append(f"%{source_channel}%")
                
                where_clause = " AND ".join(where_clauses)
                
                # 构建查询 SQL
                sql = f'''
                    SELECT update_id, vendor, source_channel, title, content,
                           source_url, raw_filepath, product_name, product_category
                    FROM updates
                    WHERE {where_clause}
                    ORDER BY publish_date DESC
                '''
                
                if limit:
                    sql += f" LIMIT {limit}"
                
                cursor.execute(sql, params)
                
                results = [dict(row) for row in cursor.fetchall()]
                record_type = "记录" if include_analyzed else "未分析记录"
                self.logger.debug(f"查询到 {len(results)} 条{record_type}")
                
                return results
                
        except Exception as e:
            self.logger.error(f"获取更新记录失败: {e}")
            return []
    
    def count_unanalyzed_updates(
        self, 
        vendor: Optional[str] = None, 
        source_channel: Optional[str] = None,
        include_analyzed: bool = False
    ) -> int:
        """
        统计未分析的更新记录数量
        
        Args:
            vendor: 指定厂商，None 表示所有厂商
            source_channel: 指定数据源类型（如 blog, whatsnew），支持模糊匹配
            include_analyzed: 是否包含已分析的记录（用于 --force）
            
        Returns:
            未分析记录数量
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 构建查询条件
                where_clauses = [
                    "content IS NOT NULL",
                    "content != ''"
                ]
                
                # 如果不包含已分析的，添加未分析条件
                if not include_analyzed:
                    where_clauses.append("title_translated IS NULL")
                
                params = []
                
                if vendor:
                    where_clauses.append("vendor = ?")
                    params.append(vendor)
                
                # source_channel 模糊匹配
                if source_channel:
                    where_clauses.append("source_channel LIKE ?")
                    params.append(f"%{source_channel}%")
                
                where_clause = " AND ".join(where_clauses)
                
                sql = f"SELECT COUNT(*) as count FROM updates WHERE {where_clause}"
                cursor.execute(sql, params)
                
                result = cursor.fetchone()
                return result['count'] if result else 0
                
        except Exception as e:
            self.logger.error(f"统计未分析记录失败: {e}")
            return 0
    
    def update_analysis_fields(
        self, 
        update_id: str, 
        fields: Dict[str, Any]
    ) -> bool:
        """
        更新分析字段
        
        Args:
            update_id: 更新记录 ID
            fields: 要更新的字段字典，支持的字段包括：
                   title_translated, content_summary, update_type,
                   product_subcategory, tags, analysis_filepath
                   
        Returns:
            成功返回 True，失败返回 False
        """
        allowed_fields = {
            'title_translated',
            'content_translated',
            'content_summary',
            'update_type',
            'product_subcategory',
            'tags',
            'analysis_filepath'
        }
        
        # 过滤非法字段
        update_fields = {k: v for k, v in fields.items() if k in allowed_fields}
        
        if not update_fields:
            self.logger.warning("没有有效的字段需要更新")
            return False
        
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # 构建 UPDATE SQL
                    set_clauses = [f"{field} = ?" for field in update_fields.keys()]
                    set_clauses.append("updated_at = CURRENT_TIMESTAMP")
                    set_clause = ", ".join(set_clauses)
                    
                    values = list(update_fields.values())
                    values.append(update_id)
                    
                    sql = f"UPDATE updates SET {set_clause} WHERE update_id = ?"
                    
                    cursor.execute(sql, values)
                    conn.commit()
                    
                    if cursor.rowcount > 0:
                        self.logger.debug(f"更新分析字段成功: {update_id}")
                        return True
                    else:
                        self.logger.warning(f"未找到更新记录: {update_id}")
                        return False
                    
        except Exception as e:
            self.logger.error(f"更新分析字段失败: {e}")
            return False
    
    def get_analysis_coverage(self) -> float:
        """
        获取分析覆盖率
        
        Returns:
            分析覆盖率（0.0 - 1.0）
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 总数（只统计 whatsnew）
                cursor.execute("""
                    SELECT COUNT(*) as total FROM updates 
                    WHERE source_channel = 'whatsnew'
                """)
                total = cursor.fetchone()['total']
                
                if total == 0:
                    return 0.0
                
                # 已分析数
                cursor.execute("""
                    SELECT COUNT(*) as analyzed FROM updates 
                    WHERE source_channel = 'whatsnew'
                    AND title_translated IS NOT NULL 
                    AND title_translated != ''
                    AND LENGTH(TRIM(title_translated)) >= 2
                """)
                analyzed = cursor.fetchone()['analyzed']
                
                return analyzed / total
                
        except Exception as e:
            self.logger.error(f"获取分析覆盖率失败: {e}")
            return 0.0
