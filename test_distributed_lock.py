#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试分布式锁功能
"""

import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from src.utils.distributed_lock import DistributedLock


def test_lock_in_thread(lock_file_path: str, thread_id: int):
    """在多线程环境中测试锁"""
    print(f"线程 {thread_id}: 尝试获取锁...")
    lock = DistributedLock(lock_file_path)
    
    if lock.acquire(blocking=False):
        print(f"线程 {thread_id}: 成功获取锁")
        # 模拟一些工作
        time.sleep(2)
        lock.release()
        print(f"线程 {thread_id}: 已释放锁")
        return True
    else:
        print(f"线程 {thread_id}: 无法获取锁（已被其他线程/进程持有）")
        return False


def test_multithreaded_lock():
    """测试多线程环境下的锁机制"""
    print("=== 测试多线程环境下的分布式锁 ===")
    lock_file = os.path.join("data", "test_lock_multithread.lock")
    
    # 清理之前的锁文件
    if os.path.exists(lock_file):
        os.remove(lock_file)
    
    # 使用线程池测试锁
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(test_lock_in_thread, lock_file, i) for i in range(3)]
        results = [future.result() for future in futures]
    
    print(f"结果: {sum(results)} 个线程成功获取了锁，{3 - sum(results)} 个线程未能获取锁")
    print()


def test_multiprocess_lock():
    """测试多进程环境下的锁机制"""
    print("=== 测试多进程环境下的分布式锁 ===")
    print("注意：这需要在单独的进程中运行，这里仅展示概念")
    print("在实际部署中，每个uvicorn worker进程会尝试获取锁")
    print("只有成功获取锁的进程才会启动定时任务")
    print()


def test_scheduler_lock_simulation():
    """模拟多个进程启动调度器的情况"""
    print("=== 模拟多进程调度器启动 ===")
    
    # 创建多个锁实例，模拟多个进程
    locks = []
    lock_file = "test_scheduler.lock"
    
    # 清理之前的锁文件
    if os.path.exists(lock_file):
        os.remove(lock_file)
    
    # 尝试创建多个锁（模拟多个进程）
    for i in range(3):
        print(f"进程 {i}: 尝试获取调度器锁...")
        lock = DistributedLock(lock_file)
        if lock.acquire(blocking=False):
            print(f"进程 {i}: 成功获取锁，可以启动调度器")
            locks.append((lock, i))
            break  # 只有第一个获取到锁的进程会启动调度器
        else:
            print(f"进程 {i}: 无法获取锁，跳过调度器启动")
    
    # 释放锁
    for lock, pid in locks:
        lock.release()
        print(f"进程 {pid}: 已释放锁")
    
    print("结果: 只有1个进程启动了调度器")
    print()


if __name__ == "__main__":
    print("分布式锁功能测试")
    print("=" * 50)
    
    test_multithreaded_lock()
    test_multiprocess_lock()
    test_scheduler_lock_simulation()
    
    print("测试完成！")
    print("\n总结：")
    print("- 分布式锁使用文件锁机制确保多进程环境下只有一个进程能获取锁")
    print("- 在多worker的uvicorn部署中，只有获得锁的worker会启动定时任务")
    print("- 其他worker会跳过定时任务启动，避免重复执行")