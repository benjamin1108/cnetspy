#!/usr/bin/env python
# -*- coding: utf-8 -*-

import importlib
import logging
import os
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

from src.utils.threading.process_lock_manager import ProcessLockManager, ProcessType

logger = logging.getLogger(__name__)

@dataclass
class CrawlStats:
    """爬取统计信息"""
    discovered: int = 0      # 发现总数
    new_saved: int = 0       # 新增保存
    skipped_exists: int = 0  # 跳过（已存在）
    skipped_ai: int = 0      # 跳过（AI清洗）
    failed: int = 0          # 失败数


class CrawlerManager:
    """爬虫管理器，负责调度各个爬虫（串行执行）"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化爬虫管理器
        
        Args:
            config: 配置信息
        """
        self.config = config
        self.sources = config.get('sources', {})
        
        # 初始化进程锁管理器
        self.process_lock_manager = ProcessLockManager.get_instance(ProcessType.CRAWLER)
        self.lock_acquired = False
    
    def _get_crawler_class(self, vendor: str, source_type: str):
        """
        动态加载爬虫类
        
        Args:
            vendor: 厂商名称
            source_type: 源类型
            
        Returns:
            爬虫类
        """
        try:
            # 处理source_type中的连字符，转换为下划线格式
            module_source_type = source_type.replace('-', '_')
            
            # 组装模块名和类名
            module_name = f"src.crawlers.vendors.{vendor}.{module_source_type}_crawler"
            
            # 首字母大写，并移除连字符
            class_source_type = ''.join(word.capitalize() for word in source_type.split('-'))
            class_name = f"{vendor.capitalize()}{class_source_type}Crawler"
            
            logger.debug(f"尝试加载模块: {module_name}, 类: {class_name}")
            
            module = importlib.import_module(module_name)
            crawler_class = getattr(module, class_name)
            
            return crawler_class
        except (ImportError, AttributeError) as e:
            logger.warning(f"加载特定爬虫类失败，将使用通用爬虫类: {e}")
            
            # 加载通用爬虫类
            try:
                module_name = f"src.crawlers.vendors.{vendor}.generic_crawler"
                class_name = f"{vendor.capitalize()}GenericCrawler"
                
                module = importlib.import_module(module_name)
                crawler_class = getattr(module, class_name)
                
                return crawler_class
            except (ImportError, AttributeError) as e:
                logger.error(f"加载通用爬虫类失败: {e}")
                return None
    
    def run_crawler(self, vendor: str, source_type: str, source_config: Dict[str, Any]) -> Tuple[List[str], CrawlStats]:
        """
        运行单个爬虫
        
        Args:
            vendor: 厂商名称
            source_type: 源类型
            source_config: 源配置
            
        Returns:
            (爬取结果文件路径列表, 爬取统计信息)
        """
        crawler_class = self._get_crawler_class(vendor, source_type)
        if not crawler_class:
            logger.error(f"未找到合适的爬虫类: {vendor} {source_type}")
            return [], CrawlStats()
        
        # 确保配置中包含正确的测试模式和文章数量限制设置
        config_copy = self.config.copy()
        
        # 将source_config合并到配置中，确保所有参数正确传递
        if 'sources' not in config_copy:
            config_copy['sources'] = {}
        if vendor not in config_copy['sources']:
            config_copy['sources'][vendor] = {}
        config_copy['sources'][vendor][source_type] = source_config
        
        logger.info(f"启动爬虫: {vendor}/{source_type}, " + 
                   f"测试模式: {source_config.get('test_mode', False)}, " + 
                   f"文章限制: {config_copy.get('crawler', {}).get('article_limit', '未设置')}")
        
        # 创建爬虫实例
        crawler = crawler_class(config_copy, vendor, source_type)
        
        files = crawler.run()
        
        # 从爬虫报告中提取统计信息
        report = crawler.crawl_report
        stats = CrawlStats(
            discovered=report.total_discovered,
            new_saved=report.new_saved,
            skipped_exists=report.skipped_exists,
            skipped_ai=report.skipped_ai_cleaned,
            failed=report.failed
        )
        
        return files, stats
    
    def run(self) -> Tuple[Dict[str, Dict[str, List[str]]], Dict[str, Dict[str, CrawlStats]]]:
        """
        运行所有爬虫（串行执行）
        
        Returns:
            (爬取结果, 统计信息)
            - 爬取结果格式: {vendor: {source_type: [file_paths]}}
            - 统计信息格式: {vendor: {source_type: CrawlStats}}
        """
        # 获取进程锁，确保同一时间只有一个爬虫进程在运行
        if not self.process_lock_manager.acquire_lock():
            logger.error("无法获取爬虫进程锁，可能有其他爬虫进程正在运行或互斥进程正在运行")
            return {}, {}
        
        self.lock_acquired = True
        logger.info("已获取爬虫进程锁，开始按顺序串行执行所有爬虫任务")
        
        try:
            results = {}
            all_stats = {}
            
            # 遍历所有数据源
            for vendor, vendor_sources in self.sources.items():
                results[vendor] = {}
                all_stats[vendor] = {}
                
                for source_type, source_config in vendor_sources.items():
                    logger.info(f"开始执行爬虫任务: {vendor}/{source_type}")
                    try:
                        # 直接运行爬虫
                        files, stats = self.run_crawler(vendor, source_type, source_config)
                        results[vendor][source_type] = files
                        all_stats[vendor][source_type] = stats
                        logger.info(f"爬虫任务完成: {vendor}/{source_type}, 发现 {stats.discovered}, 新增 {stats.new_saved}")
                    except Exception as e:
                        logger.error(f"爬虫任务异常: {vendor} {source_type} - {e}")
                        results[vendor][source_type] = []
                        all_stats[vendor][source_type] = CrawlStats()
            
            return results, all_stats
        finally:
            # 释放进程锁
            if self.lock_acquired:
                self.process_lock_manager.release_lock()
                logger.info("已释放爬虫进程锁")
