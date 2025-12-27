#!/usr/bin/env python3
"""
遍历AWS Blog API，收集所有tags并找出网络相关的tag
"""
import requests
import time
from collections import Counter

# 网络相关关键词
NETWORK_KEYWORDS = [
    'network', 'vpc', 'direct-connect', 'vpn', 'route', 'dns',
    'cloudfront', 'elb', 'load-balancer', 'api-gateway', 'transit-gateway',
    'private-link', 'endpoint', 'subnet', 'security-group', 'nacl',
    'global-accelerator', 'waf', 'firewall', 'lattice', 'app-mesh',
    'cloud-map', 'interconnect', 'peering', 'nat', 'elastic-ip',
    'bandwidth', 'latency', 'edge', 'cdn', 'networking'
]

def fetch_blog_items(page=0, size=100):
    """获取博客文章列表"""
    url = "https://aws.amazon.com/api/dirs/items/search"
    params = {
        "item.directoryId": "blog-posts",
        "item.locale": "en_US",
        "sort_by": "item.dateCreated",
        "sort_order": "desc",
        "size": size,
        "page": page
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()

def extract_tags(items):
    """从文章中提取所有tags"""
    tags = []
    for item in items:
        # tags在item同级
        tag_list = item.get("tags", [])
        for tag in tag_list:
            tag_name = tag.get("name", "")
            if tag_name:
                tags.append(tag_name)
    return tags

def is_network_related(tag):
    """判断tag是否与网络相关"""
    tag_lower = tag.lower().replace(" ", "-")
    for keyword in NETWORK_KEYWORDS:
        if keyword in tag_lower:
            return True
    return False

import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def main():
    all_tags = []
    page = 0
    total_items = 0
    
    print("开始获取AWS Blog数据...")
    
    while True:
        print(f"正在获取第 {page + 1} 页...")
        data = fetch_blog_items(page=page, size=100)
        
        items = data.get("items", [])
        if not items:
            break
        
        total_items += len(items)
        tags = extract_tags(items)
        all_tags.extend(tags)
        
        metadata = data.get("metadata", {})
        total_hits = metadata.get("totalHits", 0)
        
        print(f"  获取到 {len(items)} 篇文章, 共 {len(tags)} 个tags")
        
        if total_items >= total_hits:
            break
        
        page += 1
        time.sleep(0.5)
    
    # 统计tags
    tag_counter = Counter(all_tags)
    
    # 找出网络相关的tags
    network_tags = {tag: count for tag, count in tag_counter.items() if is_network_related(tag)}
    
    # 输出到文件
    all_tags_file = os.path.join(PROJECT_ROOT, "aws_blog_tags.txt")
    network_tags_file = os.path.join(PROJECT_ROOT, "aws_blog_network_tags.txt")
    
    with open(all_tags_file, "w") as f:
        for tag, count in sorted(tag_counter.items(), key=lambda x: -x[1]):
            f.write(f"{tag}\t{count}\n")
    
    with open(network_tags_file, "w") as f:
        for tag, count in sorted(network_tags.items(), key=lambda x: -x[1]):
            f.write(f"{tag}\t{count}\n")
    
    print(f"\n总计: {total_items} 篇文章, {len(tag_counter)} 个唯一tags, {len(network_tags)} 个网络相关tags")
    print(f"已输出: {all_tags_file}")
    print(f"已输出: {network_tags_file}")

if __name__ == "__main__":
    main()
