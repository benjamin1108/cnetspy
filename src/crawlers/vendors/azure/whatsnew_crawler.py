#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import logging
import json
import hashlib
import time
import os
import html2text
from datetime import datetime
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup

from src.crawlers.common.base_crawler import BaseCrawler

logger = logging.getLogger(__name__)

class AzureWhatsnewCrawler(BaseCrawler):
    """Azure What's New爬虫"""

    def __init__(self, config: Dict[str, Any], vendor: str, source_type: str):
        super().__init__(config, vendor, source_type)
        self.api_url = "https://www.microsoft.com/releasecommunications/api/v2/azure"
        self.params = {
            "$count": "true",
            "includeFacets": "true",
            "top": "100",
            "skip": "0",
            "filter": "products/any(f:f%20in%20(%27Application%20Gateway%27,%20%27Azure%20Bastion%27,%20%27Azure%20DDoS%20Protection%27,%20%27Azure%20DNS%27,%20%27Azure%20ExpressRoute%27,%20%27Azure%20Firewall%27,%20%27Azure%20Firewall%20Manager%27,%20%27Azure%20Front%20Door%27,%20%27Azure%20NAT%20Gateway%27,%20%27Azure%20Private%20Link%27,%20%27Azure%20Route%20Server%27,%20%27Azure%20Virtual%20Network%20Manager%27,%20%27Content%20Delivery%20Network%27,%20%27Load%20Balancer%27,%20%27Network%20Watcher%27,%20%27Traffic%20Manager%27,%20%27Virtual%20Network%27,%20%27Virtual%20WAN%27,%20%27VPN%20Gateway%27,%20%27Web%20Application%20Firewall%27))",
            "orderby": "modified%20desc"
        }

    def _get_identifier_strategy(self) -> str:
        """Azure使用API-based策略"""
        return 'api_based'
    
    def _get_identifier_components(self, update: Dict[str, Any]) -> List[str]:
        """
        Azure updates: hash(api_base + id)
        
        Args:
            update: 更新数据字典
            
        Returns:
            [api_base, id]
        """
        api_base = "https://www.microsoft.com/releasecommunications/api/v2/azure"
        update_id = update.get('update_id', '')
        return [api_base, update_id]

    def _crawl(self) -> List[str]:
        """
        爬取Azure Updates
        
        Returns:
            保存的文件路径列表
        """
        logger.info("开始爬取Azure Updates")
        
        # 从API获取更新列表
        api_updates = self._fetch_from_api()
        if not api_updates:
            logger.warning("未API获取到更新")
            return []
        
        logger.info(f"API返回 {len(api_updates)} 条更新")
        
        # 检查是否启用强制模式
        force_mode = self.crawler_config.get('force', False)
        
        # 处理每条更新
        saved_files = []
        skipped_count = 0
        
        for api_data in api_updates:
            update = self._process_update(api_data)
            if not update:
                continue
            
            # 检查是否已存在（使用source_identifier）
            source_url = update['source_url']
            source_identifier = update['source_identifier']
            if not force_mode and self.check_exists_in_db(source_url, source_identifier):
                logger.debug(f"跳过已存在: {update['title']}")
                skipped_count += 1
                continue
            
            # 保存文件
            filepath = self._save_update(update)
            if filepath:
                saved_files.append(filepath)
        
        logger.info(f"保存 {len(saved_files)} 个更新文件，跳过 {skipped_count} 个已存在")
        return saved_files

    def _fetch_from_api(self) -> List[Dict[str, Any]]:
        """从Azure API获取更新列表，使用主动skip分页"""
        updates = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        top = int(self.params.get('top', 100))
        skip = 0
        total_count = None
        max_pages = self.crawler_config.get('article_limit')  # 从配置读取
        
        while True:
            self.params['skip'] = str(skip)
            url_with_params = f"{self.api_url}?{'&'.join(f'{k}={v}' for k, v in self.params.items())}"
            logger.debug(f"请求Azure API: skip={skip}, top={top}")
            
            try:
                response = requests.get(url_with_params, headers=headers, timeout=30)
                if response.status_code != 200:
                    logger.error(f"API请求失败: {response.status_code}")
                    break

                data = response.json()
                
                # 首次获取总数
                if total_count is None:
                    total_count = data.get('@odata.count', 0)
                    logger.info(f"Azure API总更新数: {total_count}")
                
                page_updates = data.get('value', [])
                updates.extend(page_updates)
                
                logger.debug(f"本页获取 {len(page_updates)} 条，累计 {len(updates)}/{total_count} 条")
                
                # 判断是否继续：本页数据少于top 或 已获取全部 或 达到最大限制
                if len(page_updates) < top or len(updates) >= total_count or len(updates) >= max_pages:
                    break
                
                # 主动计算下一页skip
                skip += top
                time.sleep(1)  # 等待防止过频
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON解析失败: {e}")
                break
            except Exception as e:
                logger.error(f"请求异常: {e}")
                break

        return updates
    
    def _process_update(self, api_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        处理单条API数据，转换为Update字典
        
        Args:
            api_data: API返回的原始数据
            
        Returns:
            Update字典或None
        """
        try:
            # 提取基本字段
            update_id = api_data.get('id', '')
            title = api_data.get('title', '')
            description_html = api_data.get('description', '')
            created = api_data.get('created', '')
            modified = api_data.get('modified', '')
            products = api_data.get('products', [])
            
            if not title or not description_html:
                logger.warning(f"数据不完整，跳过: {update_id}")
                return None
            
            # 提取日期 (YYYY-MM-DD)
            publish_date = created.split('T')[0] if created else datetime.now().strftime('%Y-%m-%d')
            
            # 从HTML提取纯文本内容
            content = self._extract_content(description_html)
            
            # 提取产品名称（多个产品用逗号连接）
            product_name = ', '.join(products[:3]) if products else 'Azure Networking'
            
            # Azure Updates没有独立URL，使用统一的列表页
            source_url = "https://azure.microsoft.com/en-us/updates/"
            
            # 生成 source_identifier（API base URL + ID hash）
            api_base = "https://www.microsoft.com/releasecommunications/api/v2/azure"
            identifier_content = f"{api_base}|{update_id}"
            source_identifier = hashlib.md5(identifier_content.encode('utf-8')).hexdigest()[:12]
            
            # 构建 Update字典
            update = {
                'title': title,
                'description': content[:500] if content else '',
                'content': content,
                'publish_date': publish_date,
                'source_url': source_url,
                'source_identifier': source_identifier,
                'product_name': product_name
            }
            
            return update
            
        except Exception as e:
            logger.error(f"处理更新失败: {e}")
            return None
    
    def _extract_content(self, html_content: str) -> str:
        """从HTML提取纯文本内容"""
        try:
            # 使用BeautifulSoup解析HTML
            soup = BeautifulSoup(html_content, 'lxml')
            
            # 移除script和style标签
            for unwanted in soup.find_all(['script', 'style']):
                unwanted.decompose()
            
            # 使用html2text转换为Markdown
            h = html2text.HTML2Text()
            h.ignore_links = False
            h.ignore_images = False
            h.body_width = 0
            
            content = h.handle(str(soup))
            return content.strip()
            
        except Exception as e:
            logger.debug(f"提取内容失败: {e}")
            # 如果解析失败，返回纯文本
            soup = BeautifulSoup(html_content, 'lxml')
            return soup.get_text(separator='\n', strip=True)
    
    def _save_update(self, update: Dict[str, Any]) -> Optional[str]:
        """
        保存单条更新（使用基类方法）
        
        Args:
            update: 更新条目
            
        Returns:
            是否成功
        """
        try:
            # 直接调用基类的 save_update 方法，基类会统一生成元数据头
            success = self.save_update(update)
            
            if success:
                logger.debug(f"保存更新: {update.get('title', '')}")
            
            return success
            
        except Exception as e:
            logger.error(f"保存更新失败: {e}")
            return None
