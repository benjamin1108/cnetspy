#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Stats Repository - 统计查询操作

提供各类统计数据查询功能。
"""

import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from src.storage.database.base import BaseRepository


# 厂商名称映射（避免硬编码在方法中）
VENDOR_NAMES = {
    'aws': 'Amazon Web Services',
    'azure': 'Microsoft Azure',
    'gcp': 'Google Cloud Platform',
    'huawei': '华为云',
    'tencentcloud': '腾讯云',
    'volcengine': '火山引擎'
}


class StatsRepository(BaseRepository):
    """统计查询操作"""
    
    def get_database_stats(self) -> Dict[str, Any]:
        """
        获取数据库统计信息
        
        Returns:
            统计信息字典
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 总记录数（只统计 whatsnew）
                cursor.execute(
                    "SELECT COUNT(*) as total FROM updates WHERE source_channel = 'whatsnew'"
                )
                total_updates = cursor.fetchone()['total']
                
                # 按厂商统计（只统计 whatsnew）
                cursor.execute('''
                    SELECT vendor, COUNT(*) as count 
                    FROM updates 
                    WHERE source_channel = 'whatsnew'
                    GROUP BY vendor
                ''')
                vendor_stats = {row['vendor']: row['count'] for row in cursor.fetchall()}
                
                # 按类型统计（只统计 whatsnew）
                cursor.execute('''
                    SELECT update_type, COUNT(*) as count 
                    FROM updates 
                    WHERE source_channel = 'whatsnew'
                    GROUP BY update_type
                    ORDER BY count DESC
                    LIMIT 10
                ''')
                type_stats = {row['update_type']: row['count'] for row in cursor.fetchall()}
                
                # 文件大小
                db_path = self.db_path
                file_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0
                
                # 最后爬取时间
                cursor.execute('''
                    SELECT MAX(crawl_time) as latest_crawl_time 
                    FROM updates
                ''')
                row = cursor.fetchone()
                latest_crawl_time = row['latest_crawl_time'] if row else None
                
                return {
                    'total_updates': total_updates,
                    'vendor_stats': vendor_stats,
                    'type_stats': type_stats,
                    'file_size_bytes': file_size,
                    'file_size_mb': round(file_size / 1024 / 1024, 2),
                    'db_path': db_path,
                    'latest_crawl_time': latest_crawl_time
                }
                
        except Exception as e:
            self.logger.error(f"获取数据库统计信息失败: {e}")
            return {
                'total_updates': 0,
                'vendor_stats': {},
                'type_stats': {},
                'file_size_bytes': 0,
                'file_size_mb': 0,
                'db_path': self.db_path
            }
    
    def get_vendor_statistics(
        self, 
        date_from: Optional[str] = None, 
        date_to: Optional[str] = None,
        include_trend: bool = False
    ) -> List[Dict[str, Any]]:
        """
        按厂商统计
        
        Args:
            date_from: 开始日期（可选）
            date_to: 结束日期（可选）
            include_trend: 是否包含环比趋势数据
            
        Returns:
            厂商统计列表，每项包含 vendor, count, analyzed, trend（可选）
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                where_clauses = ["source_channel = 'whatsnew'"]
                params = []
                
                if date_from:
                    where_clauses.append("publish_date >= ?")
                    params.append(date_from)
                
                if date_to:
                    where_clauses.append("publish_date <= ?")
                    params.append(date_to)
                
                where_clause = " AND ".join(where_clauses)
                
                sql = f"""
                    SELECT 
                        vendor,
                        COUNT(*) as count,
                        SUM(CASE 
                            WHEN title_translated IS NOT NULL 
                                AND title_translated != '' 
                                AND LENGTH(TRIM(title_translated)) >= 2
                                AND title_translated NOT IN ('N/A', '暂无', 'None', 'null')
                            THEN 1 
                            ELSE 0 
                        END) as analyzed
                    FROM updates
                    WHERE {where_clause}
                    GROUP BY vendor
                    ORDER BY count DESC
                """
                
                cursor.execute(sql, params)
                results = [dict(row) for row in cursor.fetchall()]
                
                # 如果需要环比趋势
                if include_trend and results:
                    results = self._add_vendor_trend(cursor, results, date_from, date_to)
                
                return results
                
        except Exception as e:
            self.logger.error(f"厂商统计查询失败: {e}")
            return []
    
    def _add_vendor_trend(
        self, 
        cursor, 
        current_results: List[Dict[str, Any]],
        date_from: Optional[str],
        date_to: Optional[str]
    ) -> List[Dict[str, Any]]:
        """为厂商统计添加环比趋势数据"""
        # 计算对比周期
        if date_from and date_to:
            try:
                current_start = datetime.strptime(date_from, '%Y-%m-%d')
                current_end = datetime.strptime(date_to, '%Y-%m-%d')
                period_days = (current_end - current_start).days + 1
                prev_end = current_start - timedelta(days=1)
                prev_start = prev_end - timedelta(days=period_days - 1)
            except ValueError:
                current_end = datetime.now()
                current_start = current_end - timedelta(days=30)
                prev_end = current_start - timedelta(days=1)
                prev_start = prev_end - timedelta(days=29)
        else:
            current_end = datetime.now()
            current_start = current_end - timedelta(days=30)
            prev_end = current_start - timedelta(days=1)
            prev_start = prev_end - timedelta(days=29)
        
        prev_from = prev_start.strftime('%Y-%m-%d')
        prev_to = prev_end.strftime('%Y-%m-%d')
        
        # 查询上一周期数据
        prev_sql = """
            SELECT vendor, COUNT(*) as count
            FROM updates
            WHERE source_channel = 'whatsnew' AND publish_date >= ? AND publish_date <= ?
            GROUP BY vendor
        """
        cursor.execute(prev_sql, [prev_from, prev_to])
        prev_data = {row['vendor']: row['count'] for row in cursor.fetchall()}
        
        # 为每个厂商添加趋势数据
        for item in current_results:
            vendor = item['vendor']
            current_count = item['count']
            prev_count = prev_data.get(vendor, 0)
            
            if prev_count > 0:
                change_percent = ((current_count - prev_count) / prev_count) * 100
            else:
                change_percent = 100.0 if current_count > 0 else 0.0
            
            if change_percent > 0:
                direction = 'up'
            elif change_percent < 0:
                direction = 'down'
            else:
                direction = 'flat'
            
            item['trend'] = {
                'change_percent': round(change_percent, 1),
                'direction': direction,
                'current_period': current_count,
                'previous_period': prev_count
            }
        
        return current_results
    
    def get_update_type_statistics(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        vendor: Optional[str] = None
    ) -> Dict[str, int]:
        """
        按更新类型统计
        
        Args:
            date_from: 开始日期（可选）
            date_to: 结束日期（可选）
            vendor: 厂商过滤（可选）
            
        Returns:
            更新类型统计字典，key 为类型名，value 为数量
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                where_clauses = [
                    "source_channel = 'whatsnew'",
                    "update_type IS NOT NULL",
                    "update_type != ''"
                ]
                params = []
                
                if date_from:
                    where_clauses.append("publish_date >= ?")
                    params.append(date_from)
                
                if date_to:
                    where_clauses.append("publish_date <= ?")
                    params.append(date_to)
                
                if vendor:
                    where_clauses.append("vendor = ?")
                    params.append(vendor)
                
                where_clause = " AND ".join(where_clauses)
                
                sql = f"""
                    SELECT 
                        update_type,
                        COUNT(*) as count
                    FROM updates
                    WHERE {where_clause}
                    GROUP BY update_type
                    ORDER BY count DESC
                """
                
                cursor.execute(sql, params)
                result = {}
                for row in cursor.fetchall():
                    result[row['update_type']] = row['count']
                return result
                
        except Exception as e:
            self.logger.error(f"更新类型统计查询失败: {e}")
            return {}
    
    def get_timeline_statistics(
        self,
        granularity: str = "day",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        vendor: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取时间线统计数据
        
        Args:
            granularity: 粒度 (day/week/month/year)
            date_from: 开始日期
            date_to: 结束日期
            vendor: 厂商过滤
            
        Returns:
            时间线统计列表，每项包含 date, count, vendors
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 根据粒度确定日期格式
                granularity_map = {
                    "year": ("strftime('%Y', publish_date)", "%Y"),
                    "month": ("strftime('%Y-%m', publish_date)", "%Y-%m"),
                    "week": ("strftime('%Y-W%W', publish_date)", "%Y-W%W"),
                    "day": ("DATE(publish_date)", "%Y-%m-%d")
                }
                date_expr, _ = granularity_map.get(granularity, granularity_map["day"])
                
                where_clauses = ["source_channel = 'whatsnew'", "publish_date IS NOT NULL"]
                params = []
                
                if date_from:
                    where_clauses.append("publish_date >= ?")
                    params.append(date_from)
                
                if date_to:
                    where_clauses.append("publish_date <= ?")
                    params.append(date_to)
                
                if vendor:
                    where_clauses.append("vendor = ?")
                    params.append(vendor)
                
                where_clause = " AND ".join(where_clauses)
                
                sql = f"""
                    SELECT 
                        {date_expr} as date,
                        vendor,
                        COUNT(*) as count
                    FROM updates
                    WHERE {where_clause}
                    GROUP BY {date_expr}, vendor
                    ORDER BY date DESC
                """
                
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                
                # 聚合结果
                date_stats = {}
                for row in rows:
                    date = row['date']
                    if date not in date_stats:
                        date_stats[date] = {'date': date, 'count': 0, 'vendors': {}}
                    date_stats[date]['count'] += row['count']
                    date_stats[date]['vendors'][row['vendor']] = row['count']
                
                result = list(date_stats.values())
                result.sort(key=lambda x: x['date'], reverse=True)
                
                return result
                
        except Exception as e:
            self.logger.error(f"时间线统计查询失败: {e}")
            return []
    
    def get_vendors_list(self) -> List[Dict[str, Any]]:
        """
        获取厂商列表及元数据
        
        Returns:
            厂商列表，每项包含 vendor, name, total_updates, source_channels
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                sql = """
                    SELECT 
                        vendor,
                        COUNT(*) as total_updates,
                        GROUP_CONCAT(DISTINCT source_channel) as source_channels
                    FROM updates
                    GROUP BY vendor
                    ORDER BY total_updates DESC
                """
                
                cursor.execute(sql)
                results = []
                
                for row in cursor.fetchall():
                    vendor = row['vendor']
                    channels = row['source_channels'].split(',') if row['source_channels'] else []
                    results.append({
                        'vendor': vendor,
                        'name': VENDOR_NAMES.get(vendor, vendor.title()),
                        'total_updates': row['total_updates'],
                        'source_channels': channels
                    })
                
                return results
                
        except Exception as e:
            self.logger.error(f"厂商列表查询失败: {e}")
            return []
    
    def get_vendor_products(self, vendor: str) -> List[Dict[str, Any]]:
        """
        获取指定厂商的产品子类列表
        
        Args:
            vendor: 厂商标识
            
        Returns:
            产品子类列表，每项包含 product_subcategory, count
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                sql = """
                    SELECT 
                        product_subcategory,
                        COUNT(*) as count
                    FROM updates
                    WHERE vendor = ?
                        AND product_subcategory IS NOT NULL
                        AND product_subcategory != ''
                    GROUP BY product_subcategory
                    ORDER BY count DESC
                """
                
                cursor.execute(sql, (vendor,))
                
                results = []
                for row in cursor.fetchall():
                    results.append({
                        'product_subcategory': row['product_subcategory'],
                        'count': row['count']
                    })
                
                return results
                
        except Exception as e:
            self.logger.error(f"厂商产品列表查询失败: {e}")
            return []
    
    def get_available_years(self) -> List[int]:
        """
        获取数据库中有数据的年份列表
        
        Returns:
            年份列表，降序排列
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                sql = """
                    SELECT DISTINCT strftime('%Y', publish_date) as year
                    FROM updates
                    WHERE publish_date IS NOT NULL
                    ORDER BY year DESC
                """
                
                cursor.execute(sql)
                
                return [int(row['year']) for row in cursor.fetchall() if row['year']]
                
        except Exception as e:
            self.logger.error(f"获取年份列表失败: {e}")
            return []
    
    def get_source_channel_statistics(self) -> List[Dict[str, Any]]:
        """
        获取来源类型统计
        
        Returns:
            来源类型统计列表，每项包含 value, count
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                sql = """
                    SELECT 
                        source_channel,
                        COUNT(*) as count
                    FROM updates
                    WHERE source_channel IS NOT NULL AND source_channel != ''
                    GROUP BY source_channel
                    ORDER BY count DESC
                """
                
                cursor.execute(sql)
                
                results = []
                for row in cursor.fetchall():
                    results.append({
                        'value': row['source_channel'],
                        'count': row['count']
                    })
                
                return results
                
        except Exception as e:
            self.logger.error(f"来源类型统计失败: {e}")
            return []
    
    def get_tags_list(self, vendor: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取标签列表统计
        
        Args:
            vendor: 厂商过滤（可选）
            
        Returns:
            标签统计列表，每项包含 value, count
        """
        try:
            import json
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                where_clause = "tags IS NOT NULL AND tags != '' AND tags != '[]'"
                params = []
                
                if vendor:
                    where_clause += " AND vendor = ?"
                    params.append(vendor)
                
                sql = f"""
                    SELECT tags FROM updates
                    WHERE {where_clause}
                """
                
                cursor.execute(sql, params)
                
                # 统计所有标签的出现次数
                tag_counts = {}
                for row in cursor.fetchall():
                    try:
                        tags = json.loads(row['tags']) if isinstance(row['tags'], str) else row['tags']
                        if isinstance(tags, list):
                            for tag in tags:
                                if tag and isinstance(tag, str):
                                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
                    except (json.JSONDecodeError, TypeError):
                        continue
                
                # 转换为结果列表并按数量排序
                results = [
                    {'value': tag, 'count': count}
                    for tag, count in tag_counts.items()
                ]
                results.sort(key=lambda x: x['count'], reverse=True)
                
                return results
                
        except Exception as e:
            self.logger.error(f"标签统计失败: {e}")
            return []
    
    def get_product_subcategory_statistics(
        self,
        vendor: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 20,
        include_trend: bool = False
    ) -> List[Dict[str, Any]]:
        """
        获取产品子类热度统计
        
        Args:
            vendor: 厂商过滤（可选）
            date_from: 开始日期（可选）
            date_to: 结束日期（可选）
            limit: 返回数量限制
            include_trend: 是否包含环比趋势数据
            
        Returns:
            产品子类统计列表
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                where_clauses = [
                    "source_channel = 'whatsnew'",
                    "product_subcategory IS NOT NULL",
                    "product_subcategory != ''"
                ]
                params = []
                
                if vendor:
                    where_clauses.append("vendor = ?")
                    params.append(vendor)
                
                if date_from:
                    where_clauses.append("publish_date >= ?")
                    params.append(date_from)
                
                if date_to:
                    where_clauses.append("publish_date <= ?")
                    params.append(date_to)
                
                where_clause = " AND ".join(where_clauses)
                params.append(limit)
                
                sql = f"""
                    SELECT 
                        product_subcategory,
                        COUNT(*) as count
                    FROM updates
                    WHERE {where_clause}
                    GROUP BY product_subcategory
                    ORDER BY count DESC
                    LIMIT ?
                """
                
                cursor.execute(sql, params)
                
                results = []
                for row in cursor.fetchall():
                    results.append({
                        'product_subcategory': row['product_subcategory'],
                        'count': row['count']
                    })
                
                if include_trend and results and date_from and date_to:
                    results = self._add_product_trend(cursor, results, vendor, date_from, date_to)
                
                return results
                
        except Exception as e:
            self.logger.error(f"产品子类统计失败: {e}")
            return []
    
    def _add_product_trend(
        self,
        cursor,
        current_results: List[Dict[str, Any]],
        vendor: Optional[str],
        date_from: str,
        date_to: str
    ) -> List[Dict[str, Any]]:
        """为产品热度添加环比趋势数据"""
        try:
            current_start = datetime.strptime(date_from, '%Y-%m-%d')
            current_end = datetime.strptime(date_to, '%Y-%m-%d')
            period_days = (current_end - current_start).days + 1
            prev_end = current_start - timedelta(days=1)
            prev_start = prev_end - timedelta(days=period_days - 1)
        except ValueError:
            return current_results
        
        prev_from = prev_start.strftime('%Y-%m-%d')
        prev_to = prev_end.strftime('%Y-%m-%d')
        
        where_clauses = [
            "source_channel = 'whatsnew'",
            "product_subcategory IS NOT NULL",
            "product_subcategory != ''",
            "publish_date >= ?",
            "publish_date <= ?"
        ]
        params = [prev_from, prev_to]
        
        if vendor:
            where_clauses.append("vendor = ?")
            params.append(vendor)
        
        prev_sql = f"""
            SELECT product_subcategory, COUNT(*) as count
            FROM updates
            WHERE {' AND '.join(where_clauses)}
            GROUP BY product_subcategory
        """
        cursor.execute(prev_sql, params)
        prev_data = {row['product_subcategory']: row['count'] for row in cursor.fetchall()}
        
        for item in current_results:
            product = item['product_subcategory']
            current_count = item['count']
            prev_count = prev_data.get(product, 0)
            
            if prev_count > 0:
                change_percent = ((current_count - prev_count) / prev_count) * 100
            else:
                change_percent = 100.0 if current_count > 0 else 0.0
            
            if change_percent > 0:
                direction = 'up'
            elif change_percent < 0:
                direction = 'down'
            else:
                direction = 'flat'
            
            item['trend'] = {
                'change_percent': round(change_percent, 1),
                'direction': direction,
                'current_period': current_count,
                'previous_period': prev_count
            }
        
        return current_results
    
    def get_vendor_update_type_matrix(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取厂商-更新类型交叉统计矩阵
        
        Args:
            date_from: 开始日期（可选）
            date_to: 结束日期（可选）
            
        Returns:
            厂商统计列表，每项包含 vendor, total, update_types
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                where_clauses = [
                    "update_type IS NOT NULL",
                    "update_type != ''"
                ]
                params = []
                
                if date_from:
                    where_clauses.append("publish_date >= ?")
                    params.append(date_from)
                
                if date_to:
                    where_clauses.append("publish_date <= ?")
                    params.append(date_to)
                
                where_clause = " AND ".join(where_clauses)
                
                sql = f"""
                    SELECT 
                        vendor,
                        update_type,
                        COUNT(*) as count
                    FROM updates
                    WHERE {where_clause}
                    GROUP BY vendor, update_type
                    ORDER BY vendor, count DESC
                """
                
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                
                vendor_stats = {}
                for row in rows:
                    vendor = row['vendor']
                    if vendor not in vendor_stats:
                        vendor_stats[vendor] = {'vendor': vendor, 'total': 0, 'update_types': {}}
                    vendor_stats[vendor]['total'] += row['count']
                    vendor_stats[vendor]['update_types'][row['update_type']] = row['count']
                
                result = list(vendor_stats.values())
                result.sort(key=lambda x: x['total'], reverse=True)
                
                return result
                
        except Exception as e:
            self.logger.error(f"厂商更新类型矩阵查询失败: {e}")
            return []
