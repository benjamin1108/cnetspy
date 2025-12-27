#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AWS Networking 博客频道过滤预览
用于检查哪些文章被过滤掉
"""

import requests
import time
from typing import Set

# API配置
API_URL = "https://aws.amazon.com/api/dirs/items/search"

# 保留的博客频道（网络主频道 + 云产品相关频道）
ALLOWED_BLOG_CHANNELS: Set[str] = {
    'networking-and-content-delivery',
    'aws', 'containers', 'compute', 'security', 'storage', 'database',
    'architecture', 'hpc', 'infrastructure-and-automation',
}

def fetch_blog_items(page: int = 0, size: int = 100) -> dict:
    params = {
        "item.directoryId": "blog-posts",
        "item.locale": "en_US",
        "sort_by": "item.dateCreated",
        "sort_order": "desc",
        "size": size,
        "page": page,
        "tags.id": "blog-posts#category#networking-content-delivery"
    }
    headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
    resp = requests.get(API_URL, params=params, headers=headers, timeout=30)
    return resp.json()

def extract_channel(url: str) -> str:
    if '/blogs/' in url:
        parts = url.split('/blogs/')[1].split('/')
        if parts:
            return parts[0]
    return 'unknown'

def print_article(idx: int, title: str, link: str, pub_date: str, blog_channel: str):
    print(f"\n{'─'*80}")
    print(f"#{idx}  [{pub_date}]")
    print(f"📰 {title}")
    print(f"🔗 {link}")
    print(f"📌 博客频道: {blog_channel}")

def main():
    print("="*80)
    print("保留的文章预览（云产品频道，排除网络主频道）")
    print(f"保留频道: {', '.join(sorted(ALLOWED_BLOG_CHANNELS - {'networking-and-content-delivery'}))}")
    print("="*80)
    
    kept_count, filtered_count, total, kept_channels = 0, 0, 0, {}
    result = None
    
    for page in range(50):
        print(f"\r⏳ 扫描第 {page+1} 页... (保留 {kept_count}, 过滤 {filtered_count})", end='', flush=True)
        
        data = fetch_blog_items(page=page)
        items = data.get('items', [])
        if not items:
            break
        
        for item in items:
            total += 1
            
            fields = item.get('item', {}).get('additionalFields', {})
            title = fields.get('title', 'N/A')
            link = fields.get('link', '')
            
            date_created = item.get('item', {}).get('dateCreated', '')
            pub_date = date_created[:10] if date_created else 'N/A'
            
            channel = extract_channel(link)
            
            if channel in ALLOWED_BLOG_CHANNELS:
                # 只保留2025年的文章
                if pub_date.startswith('2025'):
                    kept_count += 1
                    kept_channels[channel] = kept_channels.get(channel, 0) + 1
                    # 不显示网络主频道，只显示其他云产品频道
                    if channel != 'networking-and-content-delivery':
                        print_article(kept_count, title, link, pub_date, channel)
            else:
                filtered_count += 1
            
            # 遇到2024年停止
            if pub_date.startswith('2024'):
                result = (kept_count, filtered_count, total, kept_channels)
                break
        
        if result:
            kept_count, filtered_count, total, kept_channels = result
            break
        
        time.sleep(0.15)
    
    print(f"\n\n{'='*80}")
    print(f"📊 统计结果:")
    print(f"   总扫描: {total} 篇")
    print(f"   保留: {kept_count} 篇")
    print(f"   过滤: {filtered_count} 篇")
    print(f"\n📌 保留的频道分布:")
    for ch, cnt in sorted(kept_channels.items(), key=lambda x: -x[1]):
        print(f"   {ch}: {cnt} 篇")

if __name__ == '__main__':
    main()
