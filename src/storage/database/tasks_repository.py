#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Tasks Repository - 批量分析任务管理

提供 analysis_tasks 表的 CRUD 操作。
"""

import json
from datetime import datetime
from typing import Dict, List, Any, Optional

from src.storage.database.base import BaseRepository


class TasksRepository(BaseRepository):
    """批量分析任务管理"""
    
    def create_analysis_task(self, task_data: Dict[str, Any]) -> bool:
        """
        创建批量分析任务记录
        
        Args:
            task_data: 任务数据，包含：
                - task_id: 任务 ID
                - task_name: 任务名称
                - task_status: 任务状态
                - vendor: 厂商（可选）
                - total_count: 总数量
                - started_at: 开始时间
                
        Returns:
            成功返回 True
        """
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute('''
                        INSERT INTO analysis_tasks (
                            task_id, update_id, task_name, task_status,
                            task_result, started_at
                        ) VALUES (?, NULL, ?, ?, ?, ?)
                    ''', (
                        task_data['task_id'],
                        task_data.get('task_name', 'batch_analysis'),
                        task_data.get('task_status', 'queued'),
                        json.dumps({
                            'filters': task_data.get('filters', '{}'),
                            'vendor': task_data.get('vendor'),
                            'total_count': task_data.get('total_count', 0),
                            'completed_count': 0,
                            'success_count': 0,
                            'fail_count': 0
                        }),
                        task_data.get('started_at')
                    ))
                    
                    conn.commit()
                    return True
                    
        except Exception as e:
            self.logger.error(f"创建任务失败: {e}")
            return False
    
    def update_task_status(
        self, 
        task_id: str, 
        status: str, 
        progress: Optional[Dict] = None,
        error: Optional[str] = None
    ) -> bool:
        """
        更新任务状态
        
        Args:
            task_id: 任务 ID
            status: 任务状态
            progress: 进度信息（可选）
            error: 错误消息（可选）
            
        Returns:
            成功返回 True
        """
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    
                    update_fields = ['task_status = ?']
                    params = [status]
                    
                    if progress:
                        update_fields.append('task_result = ?')
                        params.append(json.dumps(progress))
                    
                    if error:
                        update_fields.append('error_message = ?')
                        params.append(error)
                    
                    if status in ['completed', 'failed']:
                        update_fields.append('completed_at = ?')
                        params.append(datetime.now().isoformat())
                    
                    params.append(task_id)
                    
                    sql = f"UPDATE analysis_tasks SET {', '.join(update_fields)} WHERE task_id = ?"
                    cursor.execute(sql, params)
                    conn.commit()
                    
                    return cursor.rowcount > 0
                    
        except Exception as e:
            self.logger.error(f"更新任务状态失败: {e}")
            return False
    
    def increment_task_progress(
        self, 
        task_id: str, 
        success: bool,
        error_msg: Optional[str] = None
    ) -> bool:
        """
        增加任务进度计数（线程安全）
        
        Args:
            task_id: 任务 ID
            success: 是否成功
            error_msg: 错误消息（可选）
            
        Returns:
            成功返回 True
        """
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # 获取当前进度
                    cursor.execute(
                        'SELECT task_result, task_status FROM analysis_tasks WHERE task_id = ?',
                        (task_id,)
                    )
                    row = cursor.fetchone()
                    if not row:
                        return False
                    
                    result = json.loads(row['task_result'])
                    result['completed_count'] = result.get('completed_count', 0) + 1
                    
                    if success:
                        result['success_count'] = result.get('success_count', 0) + 1
                    else:
                        result['fail_count'] = result.get('fail_count', 0) + 1
                        if error_msg:
                            errors = result.get('errors', [])
                            errors.append(error_msg)
                            result['errors'] = errors[-100:]  # 保留最近 100 条错误
                    
                    # 判断是否完成
                    if result['completed_count'] >= result['total_count']:
                        status = 'completed'
                        completed_at = datetime.now().isoformat()
                        cursor.execute(
                            'UPDATE analysis_tasks SET task_status = ?, task_result = ?, completed_at = ? WHERE task_id = ?',
                            (status, json.dumps(result), completed_at, task_id)
                        )
                    else:
                        # 更新为 running 状态
                        current_status = row['task_status']
                        if current_status == 'queued':
                            cursor.execute(
                                'UPDATE analysis_tasks SET task_status = ?, task_result = ? WHERE task_id = ?',
                                ('running', json.dumps(result), task_id)
                            )
                        else:
                            cursor.execute(
                                'UPDATE analysis_tasks SET task_result = ? WHERE task_id = ?',
                                (json.dumps(result), task_id)
                            )
                    
                    conn.commit()
                    return True
                    
        except Exception as e:
            self.logger.error(f"更新任务进度失败: {e}")
            return False
    
    def get_task_by_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        根据 task_id 获取任务记录
        
        Args:
            task_id: 任务 ID
            
        Returns:
            任务数据字典，不存在返回 None
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM analysis_tasks WHERE task_id = ?', (task_id,))
                
                row = cursor.fetchone()
                if row:
                    task = dict(row)
                    # 解析 task_result JSON
                    if task.get('task_result'):
                        task['task_result'] = json.loads(task['task_result'])
                    return task
                return None
                
        except Exception as e:
            self.logger.error(f"获取任务记录失败: {e}")
            return None
    
    def list_tasks_paginated(
        self, 
        limit: int = 20, 
        offset: int = 0,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        分页查询任务列表（按创建时间倒序）
        
        Args:
            limit: 每页数量
            offset: 偏移量
            status: 状态过滤（可选：queued/running/completed/failed）
            
        Returns:
            任务列表
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 构建 SQL
                where_clauses = ["task_name = 'batch_analysis'"]
                params = []
                
                if status:
                    where_clauses.append("task_status = ?")
                    params.append(status)
                
                where_clause = " AND ".join(where_clauses)
                params.extend([limit, offset])
                
                cursor.execute(f'''
                    SELECT * FROM analysis_tasks
                    WHERE {where_clause}
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                ''', params)
                
                tasks = []
                for row in cursor.fetchall():
                    task = dict(row)
                    if task.get('task_result'):
                        task['task_result'] = json.loads(task['task_result'])
                    tasks.append(task)
                
                return tasks
                
        except Exception as e:
            self.logger.error(f"查询任务列表失败: {e}")
            return []
