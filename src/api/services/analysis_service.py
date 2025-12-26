#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
分析业务服务

处理AI分析任务的创建、执行和管理
"""

import json
import uuid
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.storage.database.sqlite_layer import UpdateDataLayer
from src.analyzers.update_analyzer import UpdateAnalyzer
from src.analyzers.analysis_executor import AnalysisExecutor
from ..config import settings
from ..schemas.common import PaginationMeta
from ..utils.time_utils import format_dict_datetimes
import logging

logger = logging.getLogger(__name__)


class AnalysisService:
    """分析业务服务"""
    
    def __init__(self, db: UpdateDataLayer):
        """
        初始化服务
        
        Args:
            db: UpdateDataLayer 实例
        """
        self.db = db
        self.executor = None  # 延迟初始化（需要UpdateAnalyzer）
    
    def _get_executor(self) -> AnalysisExecutor:
        """
        获取或创建 AnalysisExecutor 实例
        
        延迟初始化，避免启动时就加载AI模型
        """
        if self.executor is None:
            # 创建 UpdateAnalyzer（需要 config 参数）
            from src.utils.config import get_config
            config = get_config()
            analyzer = UpdateAnalyzer(config)
            
            # 创建 AnalysisExecutor（复用CLI的业务逻辑）
            executor_config = {
                'enable_file_save': settings.save_analysis_files,
                'output_base_dir': settings.analysis_output_dir
            }
            self.executor = AnalysisExecutor(analyzer, self.db, executor_config)
        
        return self.executor
    
    def analyze_single(self, update_id: str, force: bool = False) -> Dict:
        """
        单条分析
        
        Args:
            update_id: 更新ID
            force: 是否强制重新分析
            
        Returns:
            分析结果字典
        """
        # 1. 查询更新记录
        update_data = self.db.get_update_by_id(update_id)
        if not update_data:
            return {
                'update_id': update_id,
                'success': False,
                'error': '更新记录不存在'
            }
        
        # 2. 检查是否已分析（非强制模式）
        if not force:
            title_trans = update_data.get('title_translated', '').strip()
            if title_trans and len(title_trans) >= 2 and title_trans not in ['N/A', '暂无']:
                return {
                    'update_id': update_id,
                    'success': True,
                    'title_translated': title_trans,
                    'content_summary': update_data.get('content_summary'),
                    'update_type': update_data.get('update_type'),
                    'tags': json.loads(update_data.get('tags', '[]')) if update_data.get('tags') else [],
                    'product_subcategory': update_data.get('product_subcategory'),
                    'analysis_filepath': update_data.get('analysis_filepath'),
                    'error': None,
                    'skipped': True,
                    'message': '已有分析结果，跳过'
                }
        
        # 3. 执行分析（调用共享的 AnalysisExecutor）
        executor = self._get_executor()
        result = executor.execute_analysis(update_data)
        
        if not result:
            return {
                'update_id': update_id,
                'success': False,
                'error': 'AI分析失败'
            }
        
        # 4. 返回分析结果
        return {
            'update_id': update_id,
            'success': True,
            'title_translated': result.get('title_translated'),
            'content_summary': result.get('content_summary'),
            'update_type': result.get('update_type'),
            'tags': json.loads(result.get('tags', '[]')) if isinstance(result.get('tags'), str) else result.get('tags', []),
            'product_subcategory': result.get('product_subcategory'),
            'analysis_filepath': result.get('analysis_filepath'),
            'error': None
        }
    
    def create_batch_task(self, filters: dict, batch_size: int = 50) -> str:
        """
        创建批量分析任务
        
        Args:
            filters: 过滤条件
            batch_size: 批处理大小
            
        Returns:
            任务ID
        """
        # 1. 查询符合条件的总数
        total_count = self.db.count_updates_with_filters(**filters)
        
        if total_count == 0:
            raise ValueError("未找到符合条件的更新记录")
        
        # 2. 创建任务记录
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        filters_json = json.dumps(filters, ensure_ascii=False)
        
        task_data = {
            'task_id': task_id,
            'task_name': 'batch_analysis',
            'task_status': 'queued',
            'filters': filters_json,
            'total_count': total_count
        }
        self.db.create_analysis_task(task_data)
        
        logger.info(f"批量分析任务已创建: {task_id}, 总数: {total_count}")
        return task_id
    
    def execute_batch_task(self, task_id: str, max_workers: int = 3):
        """
        执行批量分析任务（后台运行）
        
        Args:
            task_id: 任务ID
            max_workers: 最大并发数
            
        注意：此方法应在后台线程中运行
        """
        try:
            # 1. 获取任务信息
            task = self.db.get_task_by_id(task_id)
            if not task:
                logger.error(f"任务不存在: {task_id}")
                return
            
            # 2. 更新任务状态为运行中
            self.db.update_task_status(task_id, 'running')
            
            # 3. 解析过滤条件
            task_result_raw = task.get('task_result', {})
            # task_result 可能是 JSON 字符串
            if isinstance(task_result_raw, str):
                if task_result_raw.strip():
                    try:
                        task_result = json.loads(task_result_raw)
                    except json.JSONDecodeError:
                        task_result = {}
                else:
                    task_result = {}
            else:
                task_result = task_result_raw if isinstance(task_result_raw, dict) else {}
            
            filters_str = task_result.get('filters', '{}')
            if isinstance(filters_str, str):
                if filters_str.strip():
                    try:
                        filters = json.loads(filters_str)
                    except json.JSONDecodeError:
                        filters = {}
                else:
                    filters = {}
            else:
                filters = filters_str if isinstance(filters_str, dict) else {}
            
            total_count = task_result.get('total_count', 0)
            
            # 4. 分批查询数据
            batch_size = 50
            executor = self._get_executor()
            success_count = 0
            fail_count = 0
            
            for offset in range(0, total_count, batch_size):
                # 查询当前批次
                rows = self.db.query_updates_paginated(
                    filters=filters,
                    limit=batch_size,
                    offset=offset
                )
                
                # 并发分析当前批次
                with ThreadPoolExecutor(max_workers=max_workers) as pool:
                    futures = {
                        pool.submit(executor.execute_analysis, dict(row)): row
                        for row in rows
                    }
                    
                    for future in as_completed(futures):
                        result = future.result()
                        if result:
                            success_count += 1
                        else:
                            fail_count += 1
                        
                        # 更新进度
                        self.db.increment_task_progress(task_id, success_count, fail_count)
            
            # 5. 任务完成
            self.db.update_task_status(task_id, 'completed')
            logger.info(f"批量分析任务完成: {task_id}, 成功: {success_count}, 失败: {fail_count}")
            
        except Exception as e:
            logger.error(f"批量分析任务执行失败 {task_id}: {e}")
            self.db.update_task_status(task_id, 'failed', str(e))
    
    def get_task_detail(self, task_id: str) -> Optional[Dict]:
        """
        获取任务详情
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务详情字典，不存在返回None
        """
        task = self.db.get_task_by_id(task_id)
        if not task:
            return None
        
        # 提取 task_result 中的字段到顶级
        task = dict(task)
        task_result_raw = task.get('task_result', {})
        
        # task_result 可能是 JSON 字符串，需要解析
        if isinstance(task_result_raw, str):
            if task_result_raw.strip():
                try:
                    task_result = json.loads(task_result_raw)
                except json.JSONDecodeError:
                    task_result = {}
            else:
                task_result = {}
        else:
            task_result = task_result_raw if isinstance(task_result_raw, dict) else {}
        
        # 解析 filters
        filters_str = task_result.get('filters', '{}')
        if isinstance(filters_str, str):
            if filters_str.strip():
                try:
                    task['filters'] = json.loads(filters_str)
                except json.JSONDecodeError:
                    task['filters'] = {}
            else:
                task['filters'] = {}
        else:
            task['filters'] = filters_str if isinstance(filters_str, dict) else {}
        
        # 提取统计字段
        task['total_count'] = task_result.get('total_count', 0)
        task['processed_count'] = task_result.get('completed_count', 0)  # 注意：数据库用的是 completed_count
        task['success_count'] = task_result.get('success_count', 0)
        task['fail_count'] = task_result.get('fail_count', 0)
        
        # 计算进度
        if task['total_count'] > 0:
            task['progress'] = task['processed_count'] / task['total_count']
        else:
            task['progress'] = 0.0
        
        # 重命名 status 字段
        task['status'] = task.pop('task_status', 'unknown')
        
        # 格式化时间字段为 ISO 8601 UTC
        format_dict_datetimes(task, ['created_at', 'started_at', 'completed_at'])
        
        return task
    
    def list_tasks_paginated(
        self, 
        page: int, 
        page_size: int,
        status: Optional[str] = None
    ) -> Tuple[List[Dict], PaginationMeta]:
        """
        分页查询任务列表
        
        Args:
            page: 页码
            page_size: 每页数量
            status: 状态过滤
            
        Returns:
            (任务列表, 分页元数据) 元组
        """
        # 1. 查询总数（简化版，直接用全部任务数）
        # TODO: 如果需要按status过滤，需要在UpdateDataLayer添加count方法
        offset = (page - 1) * page_size
        
        # 2. 查询当前页
        rows = self.db.list_tasks_paginated(
            limit=page_size,
            offset=offset,
            status=status
        )
        
        # 3. 处理任务数据
        items = []
        for row in rows:
            task = dict(row)
            task_result_raw = task.get('task_result', {})
            
            # task_result 可能是 JSON 字符串，需要解析
            if isinstance(task_result_raw, str):
                # 空字符串或空白字符串视为空字典
                if task_result_raw.strip():
                    try:
                        task_result = json.loads(task_result_raw)
                    except json.JSONDecodeError:
                        task_result = {}
                else:
                    task_result = {}
            else:
                task_result = task_result_raw if isinstance(task_result_raw, dict) else {}
            
            # 解析 filters
            filters_str = task_result.get('filters', '{}')
            # 确保 filters_str 不是空字符串
            if isinstance(filters_str, str):
                if filters_str.strip():
                    try:
                        task['filters'] = json.loads(filters_str)
                    except json.JSONDecodeError:
                        task['filters'] = {}
                else:
                    task['filters'] = {}
            else:
                task['filters'] = filters_str if isinstance(filters_str, dict) else {}
            
            # 提取统计字段
            task['total_count'] = task_result.get('total_count', 0)
            task['processed_count'] = task_result.get('completed_count', 0)
            task['success_count'] = task_result.get('success_count', 0)
            task['fail_count'] = task_result.get('fail_count', 0)
            
            # 计算进度
            if task['total_count'] > 0:
                task['progress'] = task['processed_count'] / task['total_count']
            else:
                task['progress'] = 0.0
            
            # 重命名 status 字段
            task['status'] = task.pop('task_status', 'unknown')
            
            # 格式化时间字段为 ISO 8601 UTC
            format_dict_datetimes(task, ['created_at', 'started_at', 'completed_at'])
            
            items.append(task)
        
        # 4. 构建分页元数据（简化版）
        total = len(rows)  # 实际应该查询真实总数
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        
        pagination = PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages
        )
        
        return items, pagination
    
    def get_stats_overview(self) -> Dict:
        """
        获取全局统计概览
        
        Returns:
            统计数据字典
        """
        # 1. 基础统计
        db_stats = self.db.get_database_stats()
        
        # 2. 按厂商统计
        vendor_stats = self.db.get_vendor_statistics()
        vendors = {}
        for row in vendor_stats:
            vendors[row['vendor']] = {
                'total': row['count'],  # 数据库返回的是 count 字段
                'analyzed': row['analyzed']
            }
        
        # 3. 按更新类型统计
        update_types = {}
        # TODO: 需要在UpdateDataLayer添加 get_update_type_statistics() 方法
        # 暂时返回空字典
        
        # 4. 分析覆盖率
        coverage = self.db.get_analysis_coverage()  # 直接返回 float 值
        
        # 5. 最后爬取时间
        last_crawl = db_stats.get('latest_crawl_time')
        
        return {
            'total_updates': db_stats.get('total_updates', 0),
            'vendors': vendors,
            'update_types': update_types,
            'last_crawl_time': last_crawl,
            'analysis_coverage': coverage
        }
