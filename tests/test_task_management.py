#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
批量任务管理测试

测试覆盖：
- 任务创建
- 状态更新
- 进度追踪
- 分页查询
"""

import pytest
import uuid
from datetime import datetime


class TestTaskManagement:
    """批量任务管理测试"""
    
    def test_create_analysis_task(self, data_layer):
        """测试创建分析任务"""
        task_id = str(uuid.uuid4())
        task_data = {
            "task_id": task_id,
            "total_count": 100,
            "vendor": "aws",
            "source_channel": "blog"
        }
        
        result = data_layer.create_analysis_task(task_data)
        assert result is True
        
        # 验证任务创建成功
        task = data_layer.get_task_by_id(task_id)
        assert task is not None
        assert task["task_id"] == task_id
        # total_count 在 task_result JSON 中
        assert task["task_result"]["total_count"] == 100
        # 状态字段是 task_status，默认是 queued
        assert task["task_status"] == "queued"
    
    def test_update_task_status(self, data_layer):
        """测试更新任务状态"""
        task_id = str(uuid.uuid4())
        data_layer.create_analysis_task({"task_id": task_id, "total_count": 50})
        
        # 更新为 running
        result = data_layer.update_task_status(task_id, "running")
        assert result is True
        
        task = data_layer.get_task_by_id(task_id)
        assert task["task_status"] == "running"
        
        # 更新为 completed
        result = data_layer.update_task_status(task_id, "completed")
        assert result is True
        
        task = data_layer.get_task_by_id(task_id)
        assert task["task_status"] == "completed"
    
    def test_update_task_with_error(self, data_layer):
        """测试更新任务错误信息"""
        task_id = str(uuid.uuid4())
        data_layer.create_analysis_task({"task_id": task_id, "total_count": 50})
        
        error_msg = "API rate limit exceeded"
        result = data_layer.update_task_status(task_id, "failed", error=error_msg)
        assert result is True
        
        task = data_layer.get_task_by_id(task_id)
        assert task["task_status"] == "failed"
        # error_message 字段通过 error 参数设置
        assert task.get("error_message") == error_msg
    
    def test_increment_task_progress_success(self, data_layer):
        """测试增加成功进度"""
        task_id = str(uuid.uuid4())
        data_layer.create_analysis_task({"task_id": task_id, "total_count": 10})
        data_layer.update_task_status(task_id, "running")
        
        # 增加5次成功进度
        for i in range(5):
            result = data_layer.increment_task_progress(task_id, success=True)
            assert result is True
        
        task = data_layer.get_task_by_id(task_id)
        # success_count 在 task_result JSON 中
        assert task["task_result"]["success_count"] == 5
        assert task["task_result"]["fail_count"] == 0
    
    def test_increment_task_progress_failure(self, data_layer):
        """测试增加失败进度"""
        task_id = str(uuid.uuid4())
        data_layer.create_analysis_task({"task_id": task_id, "total_count": 10})
        data_layer.update_task_status(task_id, "running")
        
        # 增加3次失败进度
        for i in range(3):
            result = data_layer.increment_task_progress(
                task_id, 
                success=False, 
                error_msg=f"Error {i}"
            )
            assert result is True
        
        task = data_layer.get_task_by_id(task_id)
        # fail_count 在 task_result JSON 中
        assert task["task_result"]["fail_count"] == 3
    
    def test_list_tasks_paginated(self, data_layer):
        """测试分页查询任务"""
        # 创建多个任务
        for i in range(15):
            task_id = str(uuid.uuid4())
            data_layer.create_analysis_task({"task_id": task_id, "total_count": 10})
        
        # 第一页
        page1 = data_layer.list_tasks_paginated(limit=10, offset=0)
        assert len(page1) == 10
        
        # 第二页
        page2 = data_layer.list_tasks_paginated(limit=10, offset=10)
        assert len(page2) == 5
    
    def test_list_tasks_with_status_filter(self, data_layer):
        """测试按状态过滤任务"""
        # 创建不同状态的任务
        for i in range(3):
            task_id = str(uuid.uuid4())
            data_layer.create_analysis_task({"task_id": task_id, "total_count": 10})
        
        for i in range(2):
            task_id = str(uuid.uuid4())
            data_layer.create_analysis_task({"task_id": task_id, "total_count": 10})
            data_layer.update_task_status(task_id, "running")
        
        # 过滤 queued (默认状态，不是 pending)
        queued_tasks = data_layer.list_tasks_paginated(status="queued")
        assert len(queued_tasks) == 3
        
        # 过滤 running
        running_tasks = data_layer.list_tasks_paginated(status="running")
        assert len(running_tasks) == 2
    
    def test_get_nonexistent_task(self, data_layer):
        """测试获取不存在的任务"""
        task = data_layer.get_task_by_id("nonexistent-task-id")
        assert task is None
