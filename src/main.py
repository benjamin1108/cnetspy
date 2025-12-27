#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
云计算竞争情报爬虫系统 - 主入口
精简版：仅保留爬虫数据采集功能
"""

import argparse
import logging
import logging.config
import os
import sys
from typing import Dict, Any, Optional

# 添加项目根目录到路径
base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, base_dir)

from src.crawlers.common.crawler_manager import CrawlerManager
from src.utils.config.config_loader import get_config as load_config

logger = logging.getLogger(__name__)


def get_config(args: argparse.Namespace) -> Dict[str, Any]:
    """加载配置文件"""
    return load_config(
        base_dir=base_dir,
        config_path=args.config
    )


def setup_logging(config: Dict[str, Any], debug: bool = False) -> None:
    """配置日志系统"""
    log_config = config.get('logging')
    
    if not log_config:
        logging.basicConfig(
            level=logging.DEBUG if debug else logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        return
    
    try:
        # 确保日志目录存在
        log_filename = log_config.get('handlers', {}).get('file', {}).get('filename')
        if log_filename:
            log_dir = os.path.dirname(log_filename)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)
        
        # 调试模式下设置控制台为DEBUG级别
        if debug and 'console' in log_config.get('handlers', {}):
            log_config['handlers']['console']['level'] = 'DEBUG'
        
        logging.config.dictConfig(log_config)
        logger.debug("日志系统配置完成")
        
    except Exception as e:
        logging.basicConfig(level=logging.INFO)
        logger.error(f"日志配置失败，使用默认配置: {e}")


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="云计算竞争情报爬虫")
    parser.add_argument("--vendor", help="指定厂商: aws, azure, gcp, huawei, tencentcloud, volcengine")
    parser.add_argument("--source", help="指定数据源: blog, whatsnew, updates等")
    parser.add_argument("--limit", type=int, default=0, help="每个源的文章数量限制")
    parser.add_argument("--config", help="配置文件路径")
    parser.add_argument("--force", action="store_true", help="强制重新爬取，忽略已存在的数据")
    parser.add_argument("--debug", action="store_true", help="调试模式")
    return parser.parse_args()


def run_crawler(args: argparse.Namespace) -> int:
    """
    运行爬虫
    
    Returns:
        0: 成功
        1: 失败
    """
    config = get_config(args)
    
    # 过滤厂商和数据源
    sources = config.get('sources', {})
    
    if args.vendor:
        # 指定了厂商
        if args.vendor not in sources:
            logger.error(f"未找到厂商配置: {args.vendor}")
            return 1
        config['sources'] = {args.vendor: sources[args.vendor]}
        
        # 过滤数据源
        if args.source:
            vendor_sources = config['sources'][args.vendor]
            if args.source not in vendor_sources:
                logger.error(f"未找到数据源配置: {args.vendor}/{args.source}")
                return 1
            config['sources'][args.vendor] = {args.source: vendor_sources[args.source]}
            logger.info(f"爬取目标: {args.vendor}/{args.source}")
        else:
            logger.info(f"爬取目标: {args.vendor} (全部数据源)")
    elif args.source:
        # 仅指定数据源类型，过滤所有厂商中匹配的数据源
        filtered_sources = {}
        source_pattern = args.source.lower()
        
        for vendor, vendor_sources in sources.items():
            matching_sources = {}
            for source_name, source_config in vendor_sources.items():
                # 匹配规则：source_name 包含指定的类型（如 blog 匹配 network-blog, tech-blog 等）
                if source_pattern in source_name.lower():
                    matching_sources[source_name] = source_config
            
            if matching_sources:
                filtered_sources[vendor] = matching_sources
        
        if not filtered_sources:
            logger.error(f"未找到匹配的数据源: {args.source}")
            return 1
        
        config['sources'] = filtered_sources
        matched_count = sum(len(v) for v in filtered_sources.values())
        logger.info(f"爬取目标: 所有厂商的 {args.source} 数据源 (共 {matched_count} 个)")
    else:
        logger.info("爬取目标: 全部厂商")
    
    # 设置限制
    if args.limit > 0:
        config.setdefault('crawler', {})['article_limit'] = args.limit
        logger.info(f"文章数量限制: {args.limit}")
    
    # 强制模式
    if args.force:
        config.setdefault('crawler', {})['force'] = True
        logger.info("强制模式: 忽略已存在的数据")
    
    # 运行爬虫
    crawler_manager = CrawlerManager(config)
    result = crawler_manager.run()
    
    if not result:
        logger.error("爬虫任务失败")
        return 1
    
    # 输出结果摘要
    total_files = 0
    for vendor, vendor_results in result.items():
        for source_type, files in vendor_results.items():
            count = len(files)
            total_files += count
            if count > 0:
                logger.info(f"完成: {vendor}/{source_type} - {count} 个文件")
    
    logger.info(f"爬取完成，共 {total_files} 个文件")
    return 0


def main() -> int:
    """主入口"""
    args = parse_args()
    config = get_config(args)
    
    setup_logging(config, debug=args.debug)
    
    if args.debug:
        logger.info("调试模式已启用")
    
    return run_crawler(args)


if __name__ == "__main__":
    sys.exit(main())
