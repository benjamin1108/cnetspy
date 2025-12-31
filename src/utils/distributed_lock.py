#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
分布式锁工具类
用于在多进程环境下确保只有一个进程可以执行定时任务
"""

import os
import fcntl
import logging
from typing import Optional
from contextlib import contextmanager


class DistributedLock:
    """
    基于文件锁的分布式锁实现
    用于在多进程环境下确保只有一个进程可以执行定时任务
    """
    
    def __init__(self, lock_file_path: str, logger: Optional[logging.Logger] = None):
        """
        初始化分布式锁
        
        Args:
            lock_file_path: 锁文件路径
            logger: 可选的日志记录器
        """
        self.lock_file_path = lock_file_path
        self.logger = logger or logging.getLogger(__name__)
        self._lock_file = None
        self._acquired = False
        
        # 确保锁文件目录存在
        lock_dir = os.path.dirname(self.lock_file_path)
        os.makedirs(lock_dir, exist_ok=True)
    
    def acquire(self, blocking: bool = True) -> bool:
        """
        获取锁
        
        Args:
            blocking: 是否阻塞等待锁，如果为False，则立即返回获取结果
            
        Returns:
            是否成功获取锁
        """
        try:
            # 以读写模式打开锁文件，如果不存在则创建
            self._lock_file = open(self.lock_file_path, 'w+')
            
            # 尝试获取锁
            if blocking:
                fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX)
            else:
                try:
                    fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except IOError:
                    # 锁已被其他进程持有
                    self._lock_file.close()
                    self._lock_file = None
                    return False
            
            # 获取锁成功后写入进程ID
            self._lock_file.seek(0)
            self._lock_file.truncate()
            self._lock_file.write(str(os.getpid()))
            self._lock_file.flush()
            
            self._acquired = True
            self.logger.debug(f"成功获取分布式锁: {self.lock_file_path}, PID: {os.getpid()}")
            return True
            
        except (IOError, OSError) as e:
            self.logger.error(f"获取分布式锁失败: {e}")
            if self._lock_file:
                self._lock_file.close()
                self._lock_file = None
            return False
    
    def release(self) -> bool:
        """
        释放锁
        
        Returns:
            是否成功释放锁
        """
        if not self._acquired or not self._lock_file:
            return False
        
        try:
            # 释放文件锁
            fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
            self._lock_file.close()
            self._lock_file = None
            self._acquired = False
            
            # 删除锁文件
            try:
                os.remove(self.lock_file_path)
            except OSError:
                pass  # 锁文件可能已被其他进程删除
            
            self.logger.debug(f"成功释放分布式锁: {self.lock_file_path}")
            return True
            
        except (IOError, OSError) as e:
            self.logger.error(f"释放分布式锁失败: {e}")
            return False
    
    def is_locked(self) -> bool:
        """
        检查锁是否被其他进程持有
        
        Returns:
            锁是否被其他进程持有
        """
        try:
            # 尝试以非阻塞方式获取锁
            test_file = open(self.lock_file_path, 'w+')
            try:
                fcntl.flock(test_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                # 如果能获取到锁，说明之前没有其他进程持有锁
                fcntl.flock(test_file.fileno(), fcntl.LOCK_UN)
                test_file.close()
                return False
            except IOError:
                # 无法获取锁，说明被其他进程持有
                test_file.close()
                return True
        except OSError:
            # 文件不存在或其他错误，认为没有锁
            return False
    
    def __enter__(self):
        """上下文管理器入口"""
        acquired = self.acquire(blocking=False)
        if not acquired:
            raise RuntimeError(f"无法获取分布式锁: {self.lock_file_path}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.release()


@contextmanager
def distributed_lock(lock_file_path: str, logger: Optional[logging.Logger] = None):
    """
    分布式锁的上下文管理器
    
    Args:
        lock_file_path: 锁文件路径
        logger: 可选的日志记录器
    """
    lock = DistributedLock(lock_file_path, logger)
    acquired = lock.acquire(blocking=False)
    
    try:
        if not acquired:
            raise RuntimeError(f"无法获取分布式锁: {lock_file_path}")
        yield lock
    finally:
        if acquired:
            lock.release()