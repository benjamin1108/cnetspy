#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
补全 analysis_filepath 字段脚本

遍历 data/analyzed 目录下的所有 JSON 文件，
将文件路径回写到数据库的 analysis_filepath 字段
"""

import os
import sys
import sqlite3
import logging
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.logging.colored_logger import setup_colored_logging


def backfill_analysis_filepath():
    """补全 analysis_filepath 字段"""
    
    # 设置日志
    setup_colored_logging(level=logging.INFO)
    logger = logging.getLogger('backfill')
    
    # 项目根目录
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 数据库路径
    db_path = os.path.join(project_root, 'data', 'sqlite', 'updates.db')
    if not os.path.exists(db_path):
        logger.error(f"数据库文件不存在: {db_path}")
        return
    
    # 分析结果目录
    analyzed_dir = os.path.join(project_root, 'data', 'analyzed')
    if not os.path.exists(analyzed_dir):
        logger.error(f"分析结果目录不存在: {analyzed_dir}")
        return
    
    # 连接数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 统计
    total_files = 0
    updated_count = 0
    not_found_count = 0
    
    try:
        # 遍历所有厂商目录
        for vendor in os.listdir(analyzed_dir):
            vendor_dir = os.path.join(analyzed_dir, vendor)
            
            if not os.path.isdir(vendor_dir):
                continue
            
            logger.info(f"处理 {vendor} 厂商的分析结果...")
            vendor_updated = 0
            
            # 遍历该厂商的所有 JSON 文件
            for filename in os.listdir(vendor_dir):
                if not filename.endswith('.json'):
                    continue
                
                total_files += 1
                
                # 提取 update_id（文件名去掉.json后缀）
                update_id = filename[:-5]
                
                # 构建文件路径
                file_path = os.path.join(vendor_dir, filename)
                
                # 更新数据库
                cursor.execute(
                    'UPDATE updates SET analysis_filepath = ?, updated_at = CURRENT_TIMESTAMP WHERE update_id = ?',
                    (file_path, update_id)
                )
                
                if cursor.rowcount > 0:
                    updated_count += 1
                    vendor_updated += 1
                else:
                    not_found_count += 1
                    logger.warning(f"未找到记录: {update_id}")
            
            logger.info(f"  ✅ {vendor}: 更新 {vendor_updated} 条")
        
        # 提交事务
        conn.commit()
        
        # 打印统计
        logger.info("\n" + "=" * 50)
        logger.info("补全完成！")
        logger.info(f"扫描文件数: {total_files}")
        logger.info(f"成功更新: {updated_count}")
        logger.info(f"未找到记录: {not_found_count}")
        logger.info("=" * 50)
        
    except Exception as e:
        conn.rollback()
        logger.error(f"补全失败: {e}")
        raise
    
    finally:
        conn.close()


if __name__ == '__main__':
    backfill_analysis_filepath()
