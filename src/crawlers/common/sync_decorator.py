#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
统一业务数据层 - CrawlerIntegration组件

负责将现有爬虫与新数据层集成,实现数据双写(文件系统+数据库)。
采用装饰器模式,在爬虫保存数据后自动同步到数据库。
"""

import os
import logging
import functools
from typing import Dict, Any, Optional, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


class CrawlerIntegration:
    """爬虫集成管理器"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化集成管理器"""
        if self._initialized:
            return
        
        self.logger = logging.getLogger(__name__)
        self.enabled = True  # 是否启用数据库同步
        self.data_layer = None
        
        # 延迟初始化,避免循环导入
        self._pending_updates = []
        
        CrawlerIntegration._initialized = True
    
    def initialize(self):
        """延迟初始化数据层组件"""
        if self.data_layer is None:
            try:
                from src.storage.database.sqlite_layer import UpdateDataLayer
                
                self.data_layer = UpdateDataLayer()
                self.logger.debug("CrawlerIntegration数据层已初始化")
            except Exception as e:
                self.logger.error(f"初始化数据层组件失败: {e}")
                self.enabled = False
    
    def _create_update_data(self, vendor: str, source_type: str, metadata_entry: Dict[str, Any], url_key: str) -> Dict[str, Any]:
        """从爬虫元数据创建Update数据"""
        import uuid
        from datetime import datetime
        
        return {
            'update_id': str(uuid.uuid4()),
            'vendor': vendor,
            'source_channel': source_type,
            'update_type': '',  # 由AI分类填充，参见 UpdateType 枚举
            'title': metadata_entry.get('title', ''),
            'description': metadata_entry.get('description', ''),
            'content': metadata_entry.get('content', ''),
            'publish_date': metadata_entry.get('publish_date', ''),
            'source_url': metadata_entry.get('source_url', url_key),
            'source_identifier': metadata_entry.get('source_identifier', ''),
            'product_name': metadata_entry.get('product_name', ''),
            'raw_filepath': metadata_entry.get('filepath', ''),
            'file_hash': metadata_entry.get('file_hash', ''),
            'crawl_time': metadata_entry.get('crawl_time', datetime.now().isoformat())
        }
    
    def sync_to_database(
        self, 
        vendor: str, 
        source_type: str, 
        url_key: str,
        metadata_entry: Dict[str, Any]
    ) -> bool:
        """
        同步单条记录到数据库
        
        Args:
            vendor: 厂商标识
            source_type: 源类型
            url_key: URL键
            metadata_entry: 元数据条目
            
        Returns:
            成功返回True,失败返回False
        """
        if not self.enabled:
            return False
        
        # 延迟初始化
        if self.data_layer is None:
            self.initialize()
        
        if not self.enabled or self.data_layer is None:
            return False
        
        try:
            # 从爬虫元数据创建Update数据
            update_data = self._create_update_data(
                vendor, 
                source_type, 
                metadata_entry,
                url_key
            )
            
            # 检查是否已存在
            if self.data_layer.check_update_exists(
                update_data['source_url'], 
                update_data.get('source_identifier', '')
            ):
                self.logger.debug(f"Update已存在,跳过: {url_key}")
                return True
            
            # 插入数据库
            success = self.data_layer.insert_update(update_data)
            
            if success:
                self.logger.debug(f"成功同步到数据库: {vendor}/{source_type}/{url_key}")
            else:
                self.logger.warning(f"同步到数据库失败(可能重复): {url_key}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"同步到数据库异常: {vendor}/{source_type}/{url_key}, {e}")
            return False
    
    def batch_sync_to_database(
        self,
        vendor: str,
        source_type: str,
        metadata_dict: Dict[str, Dict[str, Any]]
    ) -> Dict[str, int]:
        """
        批量同步到数据库
        
        Args:
            vendor: 厂商标识
            source_type: 源类型
            metadata_dict: 元数据字典
            
        Returns:
            统计结果 {success, failed, skipped}
        """
        if not self.enabled:
            return {'success': 0, 'failed': 0, 'skipped': 0}
        
        # 延迟初始化
        if self.data_layer is None:
            self.initialize()
        
        if not self.enabled or self.data_layer is None:
            return {'success': 0, 'failed': 0, 'skipped': 0}
        
        result = {'success': 0, 'failed': 0, 'skipped': 0}
        updates_batch = []
        
        try:
            for url_key, metadata_entry in metadata_dict.items():
                try:
                    # 调试日志：输出元数据内容
                    self.logger.debug(f"处理元数据: url_key={url_key[:50] if url_key else None}, "
                                     f"title={metadata_entry.get('title', '')[:30] if metadata_entry.get('title') else None}, "
                                     f"source_identifier={metadata_entry.get('source_identifier')}")
                    
                    # 创建Update数据
                    update_data = self._create_update_data(
                        vendor, 
                        source_type, 
                        metadata_entry,
                        url_key
                    )
                    
                    # 检查是否已存在
                    if self.data_layer.check_update_exists(
                        update_data['source_url'], 
                        update_data.get('source_identifier', '')
                    ):
                        result['skipped'] += 1
                        continue
                    
                    updates_batch.append(update_data)
                    
                except Exception as e:
                    self.logger.error(f"处理单条记录失败: {url_key}, {e}")
                    result['failed'] += 1
            
            # 批量插入
            if updates_batch:
                success_count, fail_count = self.data_layer.batch_insert_updates(updates_batch)
                result['success'] = success_count
                result['failed'] += fail_count
            
            self.logger.debug(f"批量同步: {vendor}/{source_type}, "
                           f"成功{result['success']}, 跳过{result['skipped']}, 失败{result['failed']}")
            
        except Exception as e:
            self.logger.error(f"批量同步异常: {vendor}/{source_type}, {e}")
        
        return result
    
    def disable(self):
        """禁用数据库同步"""
        self.enabled = False
        self.logger.debug("数据库同步已禁用")
    
    def enable(self):
        """启用数据库同步"""
        self.enabled = True
        if self.data_layer is None:
            self.initialize()
        self.logger.debug("数据库同步已启用")


# 全局单例实例
_crawler_integration = CrawlerIntegration()


def sync_to_database_decorator(func: Callable) -> Callable:
    """
    装饰器:在保存数据后自动同步到数据库
    
    用于装饰BaseCrawler的batch_sync_to_database方法
    """
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        # 执行原始方法
        result = func(self, *args, **kwargs)
        
        # 尝试同步到数据库
        try:
            # 获取vendor和source_type
            vendor = getattr(self, 'vendor', None)
            source_type = getattr(self, 'source_type', None)
            
            logger.debug(f"同步到数据库: {vendor}/{source_type}")
            
            if vendor and source_type:
                # 检查是否有待同步的数据
                if hasattr(self, '_pending_sync_updates') and self._pending_sync_updates:
                    count = len(self._pending_sync_updates)
                    sync_result = _crawler_integration.batch_sync_to_database(
                        vendor,
                        source_type,
                        self._pending_sync_updates
                    )
                    logger.info(f"数据库同步完成: 成功{sync_result.get('success', 0)}, 跳过{sync_result.get('skipped', 0)}, 失败{sync_result.get('failed', 0)}")
                    # 同步完成后清空
                    self._pending_sync_updates = {}
                else:
                    logger.debug("无待同步数据")
        except Exception as e:
            # 数据库同步失败不影响爬虫主流程
            logger.error(f"同步到数据库失败(不影响爬虫): {e}")
        
        return result
    
    return wrapper


def get_crawler_integration() -> CrawlerIntegration:
    """获取CrawlerIntegration全局实例"""
    return _crawler_integration


# 为现有爬虫提供的便捷方法
def enable_database_sync():
    """启用数据库同步"""
    _crawler_integration.enable()


def disable_database_sync():
    """禁用数据库同步"""
    _crawler_integration.disable()


def sync_crawler_data(vendor: str, source_type: str, metadata_dict: Dict[str, Dict[str, Any]]):
    """
    手动同步爬虫数据到数据库
    
    Args:
        vendor: 厂商标识
        source_type: 源类型
        metadata_dict: 元数据字典
    """
    return _crawler_integration.batch_sync_to_database(vendor, source_type, metadata_dict)
