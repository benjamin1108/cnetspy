#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查特定文章的内容，分析为什么会有网络产品标签"""

import requests

def main():
    api_url = "https://aws.amazon.com/api/dirs/items/search"
    headers = {"User-Agent": "Mozilla/5.0"}

    # 要检查的标题关键词
    keywords = [
        "Amazon QuickSight launches themes",
        "AWS MLOps Framework solution",
        "Amazon Personalize improves quality",
        "Amazon Connect Contact Lens real-time dashboards"
    ]

    for keyword in keywords:
        params = {
            "item.directoryId": "whats-new-v2",
            "size": "5",
            "item.locale": "en_US",
            "q": keyword
        }
        
        resp = requests.get(api_url, params=params, headers=headers, timeout=15)
        data = resp.json()
        
        for item in data.get("items", []):
            title = item.get("item", {}).get("additionalFields", {}).get("headline", "")
            if keyword[:20].lower() in title.lower():
                content = item.get("item", {}).get("additionalFields", {}).get("postBody", "")
                tags = [t.get("name", "") for t in item.get("tags", [])]
                
                print("=" * 70)
                print(f"标题: {title}")
                print(f"Tags: {[t for t in tags if not t.isdigit()]}")
                print(f"\n内容:")
                # 打印前1500字符
                print(content[:1500] if content else "[无内容]")
                print()
                break

if __name__ == "__main__":
    main()
