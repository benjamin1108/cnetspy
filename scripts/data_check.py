#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据字段全面排查脚本

检查所有厂商的所有字段数据完整性和有效性
"""

import os
import sys
import re
import sqlite3
import argparse
from datetime import datetime
from collections import defaultdict
from tabulate import tabulate

# 添加项目根目录到路径
PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.storage.database import UpdateDataLayer

# 数据库路径
DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'sqlite', 'updates.db')

# 所有厂商
VENDORS = ['aws', 'azure', 'gcp', 'huawei', 'tencentcloud', 'volcengine']

# 必填字段
REQUIRED_FIELDS = ['update_id', 'vendor', 'source_channel', 'source_url', 'title', 'publish_date']

# 所有字段
ALL_FIELDS = [
    'update_id', 'vendor', 'source_channel', 'update_type', 'source_url', 'source_identifier',
    'title', 'title_translated', 'description', 'content', 'content_summary',
    'publish_date', 'crawl_time', 'product_name', 'product_category', 'product_subcategory', 'priority', 'tags',
    'raw_filepath', 'analysis_filepath', 'file_hash', 'metadata_json'
]

# 日期格式正则
DATE_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}')
URL_PATTERN = re.compile(r'^https?://')


class DataChecker:
    """数据检查器"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.issues = defaultdict(list)
        self.stats = {}
    
    def connect(self):
        """连接数据库"""
        if not os.path.exists(self.db_path):
            print(f"❌ 数据库不存在: {self.db_path}")
            sys.exit(1)
        return sqlite3.connect(self.db_path)
    
    def run_all_checks(self):
        """运行所有检查"""
        print("=" * 60)
        print("📊 数据字段全面排查报告")
        print("=" * 60)
        print(f"数据库: {self.db_path}")
        print(f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # 1. 基础统计
        self.check_basic_stats()
        
        # 2. 各厂商统计
        self.check_vendor_stats()
        
        # 3. 字段完整度
        self.check_field_completeness()
        
        # 4. 必填字段检查
        self.check_required_fields()
        
        # 5. 日期格式检查
        self.check_date_format()
        
        # 6. URL格式检查
        self.check_url_format()
        
        # 7. 重复数据检查
        self.check_duplicates()
        
        # 8. 异常值检查
        self.check_anomalies()
        
        # 9. AI 分析质量校验
        self.check_ai_quality()
        
        # 10. 输出问题汇总
        self.print_issues_summary()
    
    def check_basic_stats(self):
        """基础统计"""
        print("📈 1. 基础统计")
        print("-" * 40)
        
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM updates")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT MIN(publish_date), MAX(publish_date) FROM updates WHERE publish_date IS NOT NULL AND publish_date != ''")
        date_range = cursor.fetchone()
        
        cursor.execute("SELECT MIN(crawl_time), MAX(crawl_time) FROM updates WHERE crawl_time IS NOT NULL")
        crawl_range = cursor.fetchone()
        
        # 数据库文件大小
        db_size = os.path.getsize(self.db_path) / 1024 / 1024
        
        print(f"  总记录数: {total}")
        print(f"  发布日期范围: {date_range[0]} ~ {date_range[1]}")
        print(f"  爬取时间范围: {crawl_range[0][:10] if crawl_range[0] else 'N/A'} ~ {crawl_range[1][:10] if crawl_range[1] else 'N/A'}")
        print(f"  数据库大小: {db_size:.2f} MB")
        print()
        
        conn.close()
    
    def check_vendor_stats(self):
        """各厂商统计"""
        print("🏢 2. 各厂商数据统计")
        print("-" * 40)
        
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT vendor, source_channel, COUNT(*) as count 
            FROM updates 
            GROUP BY vendor, source_channel 
            ORDER BY vendor, source_channel
        """)
        
        vendor_data = defaultdict(dict)
        for row in cursor.fetchall():
            vendor, channel, count = row
            vendor_data[vendor][channel] = count
        
        # 构建表格
        table_data = []
        for vendor in VENDORS:
            if vendor in vendor_data:
                channels = vendor_data[vendor]
                total = sum(channels.values())
                channel_str = ', '.join([f"{k}:{v}" for k, v in channels.items()])
                table_data.append([vendor, total, channel_str])
            else:
                table_data.append([vendor, 0, "无数据"])
                self.issues['missing_vendor'].append(vendor)
        
        print(tabulate(table_data, headers=['厂商', '总数', '渠道分布'], tablefmt='simple'))
        print()
        
        conn.close()
    
    def check_field_completeness(self):
        """字段完整度检查"""
        print("📋 3. 字段完整度")
        print("-" * 40)
        
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM updates")
        total = cursor.fetchone()[0]
        
        if total == 0:
            print("  无数据")
            conn.close()
            return
        
        table_data = []
        for field in ALL_FIELDS:
            cursor.execute(f"""
                SELECT COUNT(*) FROM updates 
                WHERE {field} IS NOT NULL AND {field} != ''
            """)
            filled = cursor.fetchone()[0]
            rate = (filled / total) * 100
            status = "✓" if rate > 90 else ("⚠" if rate > 50 else "✗")
            table_data.append([field, filled, f"{rate:.1f}%", status])
            
            if rate < 50 and field in REQUIRED_FIELDS:
                self.issues['low_completeness'].append(f"{field}: {rate:.1f}%")
        
        print(tabulate(table_data, headers=['字段', '已填充', '完整率', '状态'], tablefmt='simple'))
        print()
        
        conn.close()
    
    def check_required_fields(self):
        """必填字段检查"""
        print("⚠️  4. 必填字段空值检查")
        print("-" * 40)
        
        conn = self.connect()
        cursor = conn.cursor()
        
        has_issue = False
        for field in REQUIRED_FIELDS:
            # 查询空值记录的具体信息
            cursor.execute(f"""
                SELECT update_id, vendor, title, source_url FROM updates 
                WHERE {field} IS NULL OR {field} = ''
                LIMIT 10
            """)
            records = cursor.fetchall()
            
            if records:
                has_issue = True
                # 统计总数
                cursor.execute(f"""
                    SELECT vendor, COUNT(*) as count FROM updates 
                    WHERE {field} IS NULL OR {field} = ''
                    GROUP BY vendor
                """)
                for vendor, count in cursor.fetchall():
                    print(f"  ❌ {vendor}: {field} 字段为空 ({count} 条)")
                    self.issues['empty_required'].append(f"{vendor}.{field}: {count}条")
                
                # 输出具体记录
                for update_id, vendor, title, source_url in records:
                    title_short = (title[:50] + '...') if title and len(title) > 50 else (title or 'N/A')
                    print(f"     └ [{vendor}] {update_id}")
                    print(f"       标题: {title_short}")
                    print(f"       链接: {source_url or 'N/A'}")
        
        if not has_issue:
            print("  ✓ 所有必填字段完整")
        print()
        
        conn.close()
    
    def check_date_format(self):
        """日期格式检查"""
        print("📅 5. 日期格式检查")
        print("-" * 40)
        
        conn = self.connect()
        cursor = conn.cursor()
        
        # 检查 publish_date
        cursor.execute("""
            SELECT vendor, publish_date, COUNT(*) as count FROM updates 
            WHERE publish_date IS NOT NULL AND publish_date != ''
            GROUP BY vendor, publish_date
        """)
        
        invalid_dates = defaultdict(list)
        for vendor, date_str, count in cursor.fetchall():
            if not DATE_PATTERN.match(str(date_str)):
                invalid_dates[vendor].append((date_str, count))
        
        if invalid_dates:
            for vendor, dates in invalid_dates.items():
                for date_str, count in dates[:3]:  # 只显示前3个
                    print(f"  ❌ {vendor}: 无效日期格式 '{date_str}' ({count}条)")
                    self.issues['invalid_date'].append(f"{vendor}: {date_str}")
                if len(dates) > 3:
                    print(f"      ... 还有 {len(dates) - 3} 种格式问题")
        else:
            print("  ✓ 所有日期格式正确")
        print()
        
        conn.close()
    
    def check_url_format(self):
        """URL格式检查"""
        print("🔗 6. URL格式检查")
        print("-" * 40)
        
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT update_id, vendor, title, source_url FROM updates 
            WHERE source_url IS NOT NULL AND source_url != ''
        """)
        
        invalid_records = []  # (update_id, vendor, title, url)
        for update_id, vendor, title, url in cursor.fetchall():
            if not URL_PATTERN.match(str(url)):
                invalid_records.append((update_id, vendor, title, url))
        
        if invalid_records:
            # 按厂商统计
            vendor_counts = defaultdict(int)
            for _, vendor, _, _ in invalid_records:
                vendor_counts[vendor] += 1
            
            for vendor, count in vendor_counts.items():
                print(f"  ❌ {vendor}: {count} 条无效URL")
                self.issues['invalid_url'].append(f"{vendor}: {count}条")
            
            # 输出具体记录（最多10条）
            for update_id, vendor, title, url in invalid_records[:10]:
                title_short = (title[:50] + '...') if title and len(title) > 50 else (title or 'N/A')
                print(f"     └ [{vendor}] {update_id}")
                print(f"       标题: {title_short}")
                print(f"       URL: {url or 'N/A'}")
            
            if len(invalid_records) > 10:
                print(f"     ... 还有 {len(invalid_records) - 10} 条")
        else:
            print("  ✓ 所有URL格式正确")
        print()
        
        conn.close()
    
    def check_duplicates(self):
        """重复数据检查"""
        print("🔄 7. 重复数据检查")
        print("-" * 40)
        
        conn = self.connect()
        cursor = conn.cursor()
        
        # 检查 source_url + source_identifier 重复
        cursor.execute("""
            SELECT vendor, source_url, source_identifier, COUNT(*) as count 
            FROM updates 
            GROUP BY source_url, source_identifier 
            HAVING count > 1
        """)
        
        duplicates = cursor.fetchall()
        if duplicates:
            dup_by_vendor = defaultdict(int)
            for vendor, url, identifier, count in duplicates:
                dup_by_vendor[vendor] += count - 1
            
            for vendor, count in dup_by_vendor.items():
                print(f"  ⚠️ {vendor}: {count} 条重复记录")
                self.issues['duplicates'].append(f"{vendor}: {count}条")
        else:
            print("  ✓ 无重复数据")
        print()
        
        conn.close()
    
    def check_anomalies(self):
        """异常值检查"""
        print("🔍 8. 异常值检查")
        print("-" * 40)
        
        conn = self.connect()
        cursor = conn.cursor()
        
        anomalies = []
        
        # 检查未来日期
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute(f"""
            SELECT update_id, vendor, title, publish_date FROM updates 
            WHERE publish_date > '{today}'
            LIMIT 10
        """)
        future_records = cursor.fetchall()
        if future_records:
            cursor.execute(f"""
                SELECT vendor, COUNT(*) FROM updates 
                WHERE publish_date > '{today}'
                GROUP BY vendor
            """)
            for vendor, count in cursor.fetchall():
                anomalies.append(f"{vendor}: {count}条未来日期")
                self.issues['anomalies'].append(f"{vendor}: 未来日期{count}条")
            # 输出具体记录
            for update_id, vendor, title, pub_date in future_records:
                title_short = (title[:50] + '...') if title and len(title) > 50 else (title or 'N/A')
                print(f"     └ [{vendor}] {update_id}")
                print(f"       日期: {pub_date} | 标题: {title_short}")
        
        # 检查过短标题 (少于5个字符) - 仅信息展示，不作为告警
        cursor.execute("""
            SELECT vendor, COUNT(*) FROM updates 
            WHERE LENGTH(title) < 2
            GROUP BY vendor
        """)
        short_title_vendors = []
        for vendor, count in cursor.fetchall():
            if count > 0:
                short_title_vendors.append((vendor, count))
        
        # 检查空内容
        cursor.execute("""
            SELECT update_id, vendor, title FROM updates 
            WHERE (content IS NULL OR content = '') AND (description IS NULL OR description = '')
            LIMIT 10
        """)
        empty_content_records = cursor.fetchall()
        if empty_content_records:
            cursor.execute("""
                SELECT vendor, COUNT(*) FROM updates 
                WHERE (content IS NULL OR content = '') AND (description IS NULL OR description = '')
                GROUP BY vendor
            """)
            for vendor, count in cursor.fetchall():
                if count > 0:
                    anomalies.append(f"{vendor}: {count}条无内容和描述")
            # 输出具体记录
            for update_id, vendor, title in empty_content_records:
                title_short = (title[:50] + '...') if title and len(title) > 50 else (title or 'N/A')
                print(f"     └ [{vendor}] {update_id}")
                print(f"       标题: {title_short}")
        
        # 检查无效的 vendor 值
        cursor.execute(f"""
            SELECT DISTINCT vendor FROM updates 
            WHERE vendor NOT IN ({','.join(['?' for _ in VENDORS])})
        """, VENDORS)
        invalid_vendors = [row[0] for row in cursor.fetchall()]
        if invalid_vendors:
            anomalies.append(f"未知厂商: {', '.join(invalid_vendors)}")
            self.issues['anomalies'].append(f"未知厂商: {invalid_vendors}")
        
        if anomalies:
            for a in anomalies:
                print(f"  ⚠️ {a}")
        else:
            print("  ✓ 未发现异常值")
        print()
        
        # 打印过短标题详情（仅信息展示）
        if short_title_vendors:
            self.print_short_titles(conn, short_title_vendors)
        
        conn.close()
    
    def check_ai_quality(self):
        """
AI 分析质量校验
        
        校验规则：
        1. 翻译标题不含中文
        2. 摘要为空
        3. update_type 无效
        4. 必填字段缺失
        """
        print("🤖 9. AI 分析质量校验")
        print("-" * 40)
        
        conn = self.connect()
        cursor = conn.cursor()
        
        # 统计已分析数据
        cursor.execute("""
            SELECT COUNT(*) FROM updates 
            WHERE title_translated IS NOT NULL
        """)
        total_analyzed = cursor.fetchone()[0]
        
        if total_analyzed == 0:
            print("  无已分析数据")
            print()
            conn.close()
            return
        
        print(f"  已分析记录数: {total_analyzed}")
        print()
        
        quality_issues = []
        
        # 1. 检查翻译标题不含中文
        cursor.execute("""
            SELECT vendor, COUNT(*) FROM updates 
            WHERE title_translated IS NOT NULL
            GROUP BY vendor
        """)
        vendor_analyzed = {vendor: count for vendor, count in cursor.fetchall()}
        
        no_chinese_records = []
        for vendor, analyzed_count in vendor_analyzed.items():
            # 使用 Python 正则检查中文
            cursor.execute("""
                SELECT update_id, title, title_translated, publish_date, source_url FROM updates 
                WHERE vendor = ? AND title_translated IS NOT NULL
            """, (vendor,))
            
            for update_id, title, title_translated, date, url in cursor.fetchall():
                if not re.search(r'[一-鿿]', title_translated or ''):
                    no_chinese_records.append({
                        'vendor': vendor,
                        'update_id': update_id,
                        'title': title,
                        'title_translated': title_translated,
                        'date': date,
                        'url': url
                    })
        
        if no_chinese_records:
            for record in no_chinese_records:
                quality_issues.append(f"{record['vendor']}: 翻译标题不含中文")
                print(f"\n  ❌ {record['vendor']}: 翻译标题不含中文")
                print(f"     ID: {record['update_id']}")
                print(f"     日期: {record['date']}")
                print(f"     原标题: {record['title'][:80]}")
                print(f"     翻译后: {record['title_translated'][:80]}")
                print(f"     URL: {record['url']}")
        
        # 2. 检查摘要为空
        cursor.execute("""
            SELECT vendor, update_id, title, publish_date FROM updates 
            WHERE title_translated IS NOT NULL 
            AND (content_summary IS NULL OR content_summary = '')
        """)
        empty_summary_records = cursor.fetchall()
        
        if empty_summary_records:
            for vendor, update_id, title, date in empty_summary_records:
                quality_issues.append(f"{vendor}: 摘要为空")
                print(f"\n  ❌ {vendor}: 摘要为空")
                print(f"     ID: {update_id}")
                print(f"     日期: {date}")
                print(f"     标题: {title[:80]}")
        
        # 3. 检查 update_type 无效
        valid_types = [
            'new_product', 'new_feature', 'enhancement', 'deprecation', 
            'pricing', 'region', 'security', 'fix', 'performance', 
            'compliance', 'integration', 'other'
        ]
        placeholders = ','.join(['?' for _ in valid_types])
        cursor.execute(f"""
            SELECT vendor, update_id, title, update_type, publish_date FROM updates 
            WHERE title_translated IS NOT NULL 
            AND (update_type IS NULL OR update_type = '' OR update_type NOT IN ({placeholders}))
        """, valid_types)
        
        invalid_type_records = cursor.fetchall()
        if invalid_type_records:
            for vendor, update_id, title, update_type, date in invalid_type_records:
                quality_issues.append(f"{vendor}: update_type无效")
                print(f"\n  ❌ {vendor}: update_type无效")
                print(f"     ID: {update_id}")
                print(f"     日期: {date}")
                print(f"     标题: {title[:80]}")
                print(f"     当前值: '{update_type}'")
        
        # 4. 检查必填字段缺失（已分析但字段为空）
        ai_required_fields = ['title_translated', 'content_summary', 'update_type']
        for field in ai_required_fields:
            cursor.execute(f"""
                SELECT vendor, COUNT(*) FROM updates 
                WHERE title_translated IS NOT NULL 
                AND ({field} IS NULL OR {field} = '')
                GROUP BY vendor
            """)
            for vendor, count in cursor.fetchall():
                if count > 0 and field != 'title_translated':  # title_translated 已在上面检查
                    quality_issues.append(f"{vendor}: {count}条{field}为空")
        
        # 输出结果汇总
        if quality_issues:
            for issue in quality_issues:
                self.issues['ai_quality'].append(issue)
        else:
            print("  ✓ AI 分析质量合格")
        print()
        
        conn.close()
    
    def print_short_titles(self, conn, short_title_vendors):
        """打印过短标题详情"""
        print("📝 8.1 短标题记录（仅信息）")
        print("-" * 40)
        
        # 先打印汇总
        for vendor, count in short_title_vendors:
            print(f"  {vendor}: {count}条")
        
        cursor = conn.cursor()
        cursor.execute('''
            SELECT vendor, title, product_name, publish_date 
            FROM updates 
            WHERE LENGTH(title) < 2 
            ORDER BY vendor, publish_date
        ''')
        rows = cursor.fetchall()
        
        current_vendor = None
        for vendor, title, product, date in rows:
            if vendor != current_vendor:
                print(f"\n  === {vendor.upper()} ===")
                current_vendor = vendor
            print(f"    [{date}] \"{title}\" - {product}")
        print()
    
    def print_issues_summary(self):
        """输出问题汇总"""
        print("=" * 60)
        print("📝 问题汇总")
        print("=" * 60)
        
        total_issues = sum(len(v) for v in self.issues.values())
        
        if total_issues == 0:
            print("✅ 恭喜！未发现任何数据问题。")
        else:
            print(f"⚠️ 共发现 {total_issues} 个问题:")
            print()
            
            issue_types = {
                'missing_vendor': '缺失厂商数据',
                'low_completeness': '字段完整度低',
                'empty_required': '必填字段为空',
                'invalid_date': '日期格式错误',
                'invalid_url': 'URL格式错误',
                'duplicates': '重复数据',
                'anomalies': '数据异常',
                'ai_quality': 'AI分析质量问题'
            }
            
            for key, label in issue_types.items():
                if self.issues[key]:
                    print(f"  [{label}]")
                    for issue in self.issues[key]:
                        print(f"    - {issue}")
                    print()
    
    def list_empty_subcategory(self) -> list:
        """列出所有已分析但 subcategory 为空的记录"""
        print("=" * 60)
        print("📊 已分析但 subcategory 为空的记录")
        print("=" * 60)
        
        conn = self.connect()
        cursor = conn.cursor()
        
        # 查询已分析（title_translated 不为空）但 subcategory 为空的记录
        cursor.execute("""
            SELECT update_id, vendor, source_channel, title, title_translated, publish_date, source_url
            FROM updates 
            WHERE title_translated IS NOT NULL AND title_translated != ''
            AND (product_subcategory IS NULL OR product_subcategory = '')
            ORDER BY vendor, publish_date DESC
        """)
        
        records = cursor.fetchall()
        conn.close()
        
        if not records:
            print("✅ 没有已分析但 subcategory 为空的记录")
            return []
        
        # 按厂商分组统计
        vendor_stats = defaultdict(int)
        for record in records:
            vendor_stats[record[1]] += 1
        
        print(f"\n共 {len(records)} 条记录:")
        for vendor, count in sorted(vendor_stats.items()):
            print(f"  {vendor}: {count} 条")
        print()
        
        # 显示详细列表（使用中文翻译标题）
        print("-" * 60)
        table_data = []
        for update_id, vendor, channel, title, title_translated, date, url in records:
            # 优先显示中文翻译标题
            display_title = title_translated if title_translated else title
            table_data.append([vendor, date, display_title[:50], update_id[:20]])
        
        print(tabulate(table_data, headers=['厂商', '日期', '标题', 'ID'], tablefmt='simple'))
        print()
        
        return [r[0] for r in records]  # 返回 update_id 列表
    
    def delete_empty_subcategory(self, update_ids: list, confirmed: bool = False) -> int:
        """删除指定的记录"""
        if not update_ids:
            print("没有需要删除的记录")
            return 0
        
        if not confirmed:
            print(f"\n⚠️  即将删除 {len(update_ids)} 条记录")
            confirm = input("确认删除？(yes/no): ").strip().lower()
            if confirm != 'yes':
                print("已取消删除")
                return 0
        
        conn = self.connect()
        cursor = conn.cursor()
        
        # 批量删除
        placeholders = ','.join(['?' for _ in update_ids])
        cursor.execute(f"DELETE FROM updates WHERE update_id IN ({placeholders})", update_ids)
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        print(f"\n✅ 已删除 {deleted_count} 条记录")
        return deleted_count


class QualityIssueChecker:
    """质量问题检查器 - 使用 quality_issues 表"""
    
    def __init__(self):
        self.data_layer = UpdateDataLayer()
    
    def list_issues(
        self,
        issue_type: str = None,
        vendor: str = None,
        show_deleted: bool = False
    ) -> None:
        """列出质量问题"""
        print("=" * 60)
        if show_deleted:
            print("📋 已删除记录审计日志")
        else:
            print("📋 待处理的质量问题")
        print("=" * 60)
        
        # 获取统计信息
        stats = self.data_layer.get_issue_statistics()
        
        print(f"\n总览:")
        print(f"  待处理: {stats['total_open']} 条")
        print(f"  已解决: {stats['total_resolved']} 条")
        print(f"  已忽略: {stats['total_ignored']} 条")
        
        if stats['by_type']:
            print(f"\n按类型统计 (待处理):")
            for t, count in stats['by_type'].items():
                print(f"  - {t}: {count}")
        
        if stats['by_vendor']:
            print(f"\n按厂商统计 (待处理):")
            for v, count in stats['by_vendor'].items():
                print(f"  - {v}: {count}")
        
        # 获取详细列表
        if show_deleted:
            issues = self.data_layer._quality.get_deleted_issues(
                issue_type=issue_type,
                vendor=vendor,
                limit=100
            )
        else:
            issues = self.data_layer.get_open_issues(
                issue_type=issue_type,
                vendor=vendor,
                limit=100
            )
        
        if not issues:
            print(f"\n✅ 无{'已删除' if show_deleted else '待处理'}记录")
            return
        
        print(f"\n" + "-" * 60)
        print(f"详细列表 (最多显示 100 条):")
        print("-" * 60)
        
        table_data = []
        for issue in issues:
            title = issue.get('title', '')[:40]
            table_data.append([
                issue.get('id'),
                issue.get('vendor', ''),
                issue.get('issue_type', ''),
                title,
                issue.get('detected_at', '')[:10]
            ])
        
        print(tabulate(
            table_data, 
            headers=['ID', '厂商', '问题类型', '标题', '检测时间'], 
            tablefmt='simple'
        ))
        print()
    
    def resolve_issue(self, issue_id: int, action: str, confirmed: bool = False) -> bool:
        """
        解决质量问题
        
        Args:
            issue_id: 问题 ID
            action: 动作 (delete/ignore)
            confirmed: 是否已确认
        """
        # 获取问题详情
        issue = self.data_layer._quality.get_issue_by_id(issue_id)
        if not issue:
            print(f"❌ 问题 ID {issue_id} 不存在")
            return False
        
        if issue['status'] != 'open':
            print(f"⚠️  问题 ID {issue_id} 状态为 {issue['status']}，无需处理")
            return False
        
        print(f"\n问题详情:")
        print(f"  ID: {issue['id']}")
        print(f"  类型: {issue['issue_type']}")
        print(f"  厂商: {issue['vendor']}")
        print(f"  标题: {issue['title'][:60]}")
        print(f"  链接: {issue['source_url']}")
        print(f"  检测时间: {issue['detected_at']}")
        
        if action == 'delete':
            if not confirmed:
                confirm = input("\n确认删除对应的更新记录？(yes/no): ").strip().lower()
                if confirm != 'yes':
                    print("已取消")
                    return False
            
            # 删除更新记录
            update_id = issue['update_id']
            success = self.data_layer.delete_update(update_id)
            if success:
                self.data_layer._quality.resolve_issue(issue_id, 'deleted')
                print(f"\n✅ 已删除更新记录 {update_id}，问题已解决")
                return True
            else:
                print(f"\n❌ 删除更新记录失败（可能已被删除）")
                self.data_layer._quality.resolve_issue(issue_id, 'deleted')
                return True
        
        elif action == 'ignore':
            self.data_layer._quality.ignore_issue(issue_id)
            print(f"\n✅ 问题 ID {issue_id} 已标记为忽略")
            return True
        
        else:
            print(f"❌ 未知动作: {action}")
            return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='数据质量检查工具')
    parser.add_argument('--clean-empty', action='store_true', 
                        help='列出并删除已分析但 subcategory 为空的记录')
    parser.add_argument('--list-empty', action='store_true',
                        help='仅列出已分析但 subcategory 为空的记录（不删除）')
    parser.add_argument('--issues', action='store_true',
                        help='查看待处理的质量问题（使用 quality_issues 表）')
    parser.add_argument('--deleted', action='store_true',
                        help='查看已删除记录的审计日志')
    parser.add_argument('--type', type=str, default=None,
                        help='按问题类型过滤 (empty_subcategory/not_network_related/analysis_failed)')
    parser.add_argument('--vendor', type=str, default=None,
                        help='按厂商过滤')
    parser.add_argument('--resolve', type=int, default=None,
                        help='解决指定 ID 的问题')
    parser.add_argument('--delete', action='store_true',
                        help='与 --resolve 配合使用，删除对应记录')
    parser.add_argument('--ignore', action='store_true',
                        help='与 --resolve 配合使用，忽略问题')
    parser.add_argument('-y', '--yes', action='store_true',
                        help='跳过确认提示，直接执行')
    
    args = parser.parse_args()
    
    # 质量问题相关命令
    if args.issues or args.deleted:
        quality_checker = QualityIssueChecker()
        quality_checker.list_issues(
            issue_type=args.type,
            vendor=args.vendor,
            show_deleted=args.deleted
        )
        return
    
    if args.resolve:
        quality_checker = QualityIssueChecker()
        if args.delete:
            quality_checker.resolve_issue(args.resolve, 'delete', confirmed=args.yes)
        elif args.ignore:
            quality_checker.resolve_issue(args.resolve, 'ignore', confirmed=args.yes)
        else:
            print("请指定 --delete 或 --ignore")
        return
    
    # 原有功能
    checker = DataChecker(DB_PATH)
    
    if args.list_empty:
        # 仅列出，不删除
        checker.list_empty_subcategory()
    elif args.clean_empty:
        # 列出并删除
        update_ids = checker.list_empty_subcategory()
        if update_ids:
            checker.delete_empty_subcategory(update_ids, confirmed=args.yes)
    else:
        # 默认运行所有检查
        checker.run_all_checks()


if __name__ == '__main__':
    main()
