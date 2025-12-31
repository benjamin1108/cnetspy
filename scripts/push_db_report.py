import os
import sys
import json
import sqlite3
from datetime import datetime

# 添加项目路径
sys.path.append(os.getcwd())

from src.notification.manager import NotificationManager
from src.notification.base import NotificationChannel

def send_existing_report():
    db_path = "data/sqlite/updates.db"
    
    # 1. 从数据库读取已存在的报告
    print(f"正在从数据库读取 2025-W47 周报数据...")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM reports 
        WHERE report_type = 'weekly' AND year = 2025 AND week = 47
        LIMIT 1
    """)
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        print("❌ 未在数据库中找到 2025-W47 的周报记录。")
        return

    # 2. 解析 AI 洞察数据
    ai_insight = json.loads(row['ai_summary'])
    
    # 3. 按照最新的“极致简约”逻辑重新构建 Markdown
    lines = []
    date_range = f"{row['date_from']} 至 {row['date_to']}"
    lines.append(f"## {ai_insight.get('insight_title', '云技术周报')}")
    lines.append("")
    lines.append(ai_insight.get('insight_summary', ''))
    lines.append("")

    # 1. 核心亮点
    if ai_insight.get('top_updates'):
        lines.append("### 🌟 核心亮点 (Key Updates)")
        lines.append("")
        for item in ai_insight['top_updates']:
            vendor = item.get('vendor', 'Unknown')
            product = item.get('product', '')
            update_id = item.get('update_id')
            # 内部链接
            link = f"https://cnetspy.site/next/updates/{update_id}" if update_id else ""
            
            title_text = f"**[{vendor}] {product}**"
            if link:
                lines.append(f"- [{title_text}]({link})")
            else:
                lines.append(f"- {title_text}")

            if item.get('pain_point'): lines.append(f"  - **痛点:** {item.get('pain_point')}")
            if item.get('value'): lines.append(f"  - **价值:** {item.get('value')}")
            if item.get('comment'): lines.append(f"  - **点评:** {item.get('comment')}")
            lines.append("")

    # 2. 快速浏览
    if ai_insight.get('quick_scan'):
        lines.append("### ⚡️ 快速浏览 (Quick Scan)")
        lines.append("")
        for group in ai_insight['quick_scan']:
            vendor = group.get('vendor', 'Unknown')
            lines.append(f"- **{vendor}**")
            for item in ai_insight['quick_scan']:
                # 兼容处理：老数据可能是字符串，新数据是字典
                content = item.get('content', '') if isinstance(item, dict) else item
                uid = item.get('update_id') if isinstance(item, dict) else None
                is_nw = item.get('is_noteworthy', False) if isinstance(item, dict) else False
                
                star = "✨ " if is_nw else ""
                if uid:
                    lines.append(f"  - {star}[{content}](https://cnetspy.site/next/updates/{uid})")
                else:
                    lines.append(f"  - {star}{content}")
            lines.append("")

    # 3. 精选博客
    if ai_insight.get('featured_blogs'):
        lines.append("### 📚 精选博客 (Featured Blogs)")
        lines.append("")
        for blog in ai_insight['featured_blogs']:
            vendor = blog.get('vendor', 'Unknown')
            title = blog.get('title', '')
            url = blog.get('url', '#')
            # 这里的链接优先使用 url
            lines.append(f"- **[{vendor}] [{title}]({url})**")
            if blog.get('reason'):
                lines.append(f"  - **推荐理由:** {blog.get('reason')}")
            lines.append("")

    # 4. 推送
    from src.utils.config import get_config
    config = get_config()
    manager = NotificationManager(config.get('notification', {}))
    
    online_url = f"https://cnetspy.site/next/reports?type=weekly&year=2025&week=47"
    
    print("🚀 正在将数据库中的真实报告推送到钉钉...")
    result = manager.send_dingtalk(
        title=f"云网动态周报 (2025-W47)",
        content="\n".join(lines),
        single_url=online_url,
        single_title="查看在线完整版",
        robot_names=["TEST-BOT"]
    )
    
    if result.success:
        print("✅ 发送成功！")
    else:
        print(f"❌ 发送失败: {result.message}")

if __name__ == "__main__":
    send_existing_report()
