#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""从 API 爬取所有数据，然后匹配数据库中 subcate 为空的记录"""

import requests
import sqlite3
import time

def main():
    # 1. 获取数据库中 subcate 为空的记录
    conn = sqlite3.connect('data/sqlite/updates.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT title, source_url FROM updates 
        WHERE vendor='aws' AND source_channel='whatsnew'
        AND (product_subcategory IS NULL OR product_subcategory = '')
    """)
    db_records = cursor.fetchall()
    print(f"数据库中共 {len(db_records)} 条 subcate 为空的记录\n")
    conn.close()
    
    # 用 URL 做匹配 key
    db_urls = {url: title for title, url in db_records}
    
    api_url = "https://aws.amazon.com/api/dirs/items/search"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # 爬虫原始的 tag 过滤条件（包含大类 tag）
    tags_filter = "whats-new-v2#general-products#amazon-vpc|whats-new-v2#general-products#aws-direct-connect|whats-new-v2#general-products#amazon-route-53|whats-new-v2#general-products#elastic-load-balancing|whats-new-v2#general-products#amazon-cloudfront|whats-new-v2#general-products#amazon-api-gateway|whats-new-v2#marketing-marchitecture#networking|whats-new-v2#marketing-marchitecture#networking-and-content-delivery|whats-new-v2#general-products#aws-global-accelerator|whats-new-v2#general-products#aws-transit-gateway|whats-new-v2#general-products#aws-vpn|whats-new-v2#general-products#aws-site-to-site|whats-new-v2#general-products#aws-client-vpn|whats-new-v2#general-products#aws-app-mesh"
    
    # 核心网络产品 tag 列表
    core_product_tags = {
        "amazon-vpc", "aws-direct-connect", "amazon-route-53", 
        "elastic-load-balancing", "amazon-cloudfront", "amazon-api-gateway",
        "aws-global-accelerator", "aws-transit-gateway", "aws-vpn",
        "aws-site-to-site", "aws-client-vpn", "aws-app-mesh",
        "aws-privatelink", "aws-network-firewall", "amazon-vpc-lattice"
    }
    
    # 2. 爬取 API 中所有数据
    print("正在从 API 爬取所有数据...")
    all_api_items = []
    
    for page in range(20):  # 最多2000条
        params = {
            "item.directoryId": "whats-new-v2",
            "sort_by": "item.additionalFields.postDateTime",
            "sort_order": "desc",
            "size": "100",
            "page": str(page),
            "item.locale": "en_US",
            "tags.id": tags_filter
        }
        try:
            resp = requests.get(api_url, params=params, headers=headers, timeout=30)
            items = resp.json().get("items", [])
            if not items:
                break
            all_api_items.extend(items)
            print(f"  已获取 {len(all_api_items)} 条...")
            time.sleep(0.3)
        except Exception as e:
            print(f"  请求失败: {e}")
            break
    
    print(f"\nAPI 共返回 {len(all_api_items)} 条数据\n")
    
    # 3. 建立 URL -> item 的索引
    api_by_url = {}
    for item in all_api_items:
        url_path = item.get("item", {}).get("additionalFields", {}).get("headlineUrl", "")
        if not url_path.startswith("http"):
            if not url_path.startswith("/"):
                url_path = "/" + url_path
            full_url = f"https://aws.amazon.com{url_path}"
        else:
            full_url = url_path
        # 统一去掉末尾斜杠
        full_url = full_url.rstrip("/")
        api_by_url[full_url] = item
    
    # 4. 匹配数据库中的记录
    print("=" * 60)
    print("匹配结果")
    print("=" * 60 + "\n")
    
    matched_by_category = []  # 只通过大类 tag 匹配的
    matched_by_product = []   # 通过具体产品 tag 匹配的
    not_found = []
    
    for db_url, db_title in db_urls.items():
        # 统一去掉末尾斜杠
        db_url_normalized = db_url.rstrip("/")
        
        if db_url_normalized in api_by_url:
            item = api_by_url[db_url_normalized]
            tags = [t.get("name", "") for t in item.get("tags", [])]
            
            # 分析匹配原因
            product_tags = [t for t in tags if t in core_product_tags]
            has_networking = "networking" in tags or "networking-and-content-delivery" in tags
            
            print(f"{db_title[:60]}")
            print(f"  URL: {db_url}")
            print(f"  Tags: {[t for t in tags if not t.isdigit() and t not in ['Launch Announcement', 'General']]}")
            
            if product_tags:
                print(f"  匹配原因: 具体产品 tag {product_tags}")
                matched_by_product.append((db_title, tags))
            elif has_networking:
                print(f"  匹配原因: 大类 tag (networking/networking-and-content-delivery)")
                matched_by_category.append((db_title, tags))
            else:
                print(f"  匹配原因: 未知")
            print()
        else:
            not_found.append((db_title, db_url))
    
    # 5. 统计结果
    print("\n" + "=" * 60)
    print("统计结果")
    print("=" * 60)
    print(f"\n通过具体产品 tag 匹配: {len(matched_by_product)} 条")
    print(f"通过大类 tag 匹配: {len(matched_by_category)} 条")
    print(f"API 中未找到: {len(not_found)} 条")
    
    if not_found:
        print("\n=== API 中未找到的记录 ===")
        for title, url in not_found:
            print(f"  {title[:50]}")
            print(f"    {url}")

if __name__ == "__main__":
    main()
