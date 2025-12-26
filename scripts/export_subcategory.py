#!/usr/bin/env python3
"""导出 product_subcategory 分组数据到 CSV"""

import sqlite3
import csv
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "sqlite" / "updates.db"
OUTPUT_PATH = Path(__file__).parent.parent / "data" / "subcategory_export.csv"


def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            product_subcategory,
            GROUP_CONCAT(DISTINCT vendor) as vendors,
            GROUP_CONCAT(DISTINCT product_name) as product_names,
            GROUP_CONCAT(DISTINCT title) as titles,
            COUNT(*) as count
        FROM updates 
        WHERE product_subcategory IS NOT NULL AND product_subcategory != ''
        GROUP BY product_subcategory
        ORDER BY product_subcategory
    ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    with open(OUTPUT_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['product_subcategory', 'vendors', 'product_names', 'titles', 'count'])
        writer.writerows(rows)
    
    print(f"已导出 {len(rows)} 条记录到 {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
