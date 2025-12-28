#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AWS Whatsnew Networking 大类tag引入内容预览
用于检查大类tag（networking/networking-and-content-delivery）引入的边缘案例
"""

import requests
import time
from typing import Set, List, Dict, Any

# API配置
API_URL = "https://aws.amazon.com/api/dirs/items/search"

# 核心网络产品tag（精确匹配）
CORE_PRODUCT_TAGS: Set[str] = {
    'whats-new-v2#general-products#amazon-vpc',
    'whats-new-v2#general-products#aws-direct-connect',
    'whats-new-v2#general-products#amazon-route-53',
    'whats-new-v2#general-products#elastic-load-balancing',
    'whats-new-v2#general-products#amazon-cloudfront',
    'whats-new-v2#general-products#amazon-api-gateway',
    'whats-new-v2#general-products#aws-global-accelerator',
    'whats-new-v2#general-products#aws-transit-gateway',
    'whats-new-v2#general-products#aws-vpn',
    'whats-new-v2#general-products#aws-site-to-site',
    'whats-new-v2#general-products#aws-client-vpn',
    'whats-new-v2#general-products#aws-app-mesh',
    'whats-new-v2#general-products#aws-privatelink',
    'whats-new-v2#general-products#aws-network-firewall',
    'whats-new-v2#general-products#amazon-vpc-lattice',
}

# 大类tag（宽松匹配，会引入边缘案例）
BROAD_CATEGORY_TAGS: Set[str] = {
    # 'whats-new-v2#marketing-marchitecture#networking',  # 暂时排除
    'whats-new-v2#marketing-marchitecture#networking-and-content-delivery',
}


def fetch_whatsnew_by_tag(tag: str, page: int = 0, size: int = 100) -> dict:
    """通过指定tag获取whatsnew"""
    params = {
        "item.directoryId": "whats-new-v2",
        "item.locale": "en_US",
        "sort_by": "item.dateCreated",
        "sort_order": "desc",
        "size": size,
        "page": page,
        "tags.id": tag
    }
    headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
    resp = requests.get(API_URL, params=params, headers=headers, timeout=30)
    return resp.json()


def extract_product_tags(tags: List[Dict[str, Any]]) -> List[str]:
    """提取产品标签"""
    products = []
    for tag in tags:
        if isinstance(tag, dict):
            tag_id = tag.get('id', '')
            if 'general-products' in tag_id:
                name = tag.get('name', tag_id.split('#')[-1])
                products.append(name)
    return products


def has_core_product_tag(tags: List[Dict[str, Any]]) -> bool:
    """检查是否有核心网络产品tag"""
    for tag in tags:
        if isinstance(tag, dict):
            tag_id = tag.get('id', '')
            if tag_id in CORE_PRODUCT_TAGS:
                return True
    return False


def print_article(idx: int, title: str, link: str, pub_date: str, products: List[str], matched_by: str):
    print(f"\n{'─'*80}")
    print(f"#{idx}  [{pub_date}]  匹配来源: {matched_by}")
    print(f"📰 {title}")
    print(f"🔗 {link}")
    print(f"📌 产品标签: {', '.join(products) if products else '无'}")


def main():
    print("="*80)
    print("AWS Whatsnew Networking 大类tag引入内容预览")
    print("检查大类tag（networking/networking-and-content-delivery）引入的边缘案例")
    print("="*80)
    
    # 收集所有通过大类tag匹配的文章
    broad_match_items = []
    core_match_count = 0
    
    for broad_tag in BROAD_CATEGORY_TAGS:
        tag_name = broad_tag.split('#')[-1]
        print(f"\n⏳ 扫描大类tag: {tag_name}...")
        
        for page in range(10):  # 最多扫描10页
            data = fetch_whatsnew_by_tag(broad_tag, page=page)
            items = data.get('items', [])
            if not items:
                break
            
            for item in items:
                date_created = item.get('item', {}).get('dateCreated', '')
                pub_date = date_created[:10] if date_created else 'N/A'
                
                # 只看2025年
                if not pub_date.startswith('2025'):
                    continue
                
                tags = item.get('tags', [])
                fields = item.get('item', {}).get('additionalFields', {})
                title = fields.get('headline', 'N/A')
                link = f"https://aws.amazon.com{fields.get('headlineUrl', '')}"
                products = extract_product_tags(tags)
                
                # 判断是否有核心产品tag
                if has_core_product_tag(tags):
                    core_match_count += 1
                else:
                    # 这是边缘案例：只有大类tag，没有核心产品tag
                    broad_match_items.append({
                        'title': title,
                        'link': link,
                        'pub_date': pub_date,
                        'products': products,
                        'matched_by': tag_name
                    })
            
            time.sleep(0.15)
    
    # 去重（按链接）
    seen_links = set()
    unique_items = []
    for item in broad_match_items:
        if item['link'] not in seen_links:
            seen_links.add(item['link'])
            unique_items.append(item)
    
    # 按日期倒序
    unique_items.sort(key=lambda x: x['pub_date'], reverse=True)
    
    print(f"\n\n{'='*80}")
    print(f"📊 边缘案例预览（只有大类tag，无核心产品tag）")
    print(f"{'='*80}")
    
    for idx, item in enumerate(unique_items, 1):
        print_article(
            idx, 
            item['title'], 
            item['link'], 
            item['pub_date'], 
            item['products'],
            item['matched_by']
        )
    
    print(f"\n\n{'='*80}")
    print(f"📊 统计结果 (2025年):")
    print(f"   核心产品tag匹配: {core_match_count} 篇")
    print(f"   大类tag边缘案例: {len(unique_items)} 篇")
    print(f"\n💡 边缘案例需要通过AI分析判断subcategory，为空则清理")


if __name__ == '__main__':
    main()
