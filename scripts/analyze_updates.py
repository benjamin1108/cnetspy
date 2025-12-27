#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
更新记录分析脚本

命令行工具，用于对爬取的更新记录进行 AI 分析
"""

import os
import sys
import argparse
import logging
import time
import json
from datetime import datetime
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.config.config_loader import load_config_directory, load_yaml_file
from src.utils.logging.colored_logger import setup_colored_logging
from src.storage.database.sqlite_layer import UpdateDataLayer
from src.analyzers.update_analyzer import UpdateAnalyzer


class AnalyzeUpdatesScript:
    """更新记录分析脚本"""
    
    def __init__(self, args):
        """
        初始化脚本
        
        Args:
            args: 命令行参数
        """
        self.args = args
        
        # 设置日志
        log_level = logging.DEBUG if args.verbose else logging.INFO
        setup_colored_logging(level=log_level)
        self.logger = logging.getLogger('analyze_updates')
        
        # 加载配置
        self.config = self._load_config()
        
        # 初始化数据库层
        self.data_layer = UpdateDataLayer()
        
        # 初始化分析器
        try:
            ai_config = self.config.get('ai_model', {})
            self.analyzer = UpdateAnalyzer(ai_config)
            self.logger.info("分析器初始化成功")
        except Exception as e:
            self.logger.error(f"分析器初始化失败: {e}")
            sys.exit(1)
    
    def _load_config(self):
        """加载配置文件"""
        try:
            # 加载主配置
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_dir = os.path.join(project_root, 'config')
            main_config = load_config_directory(config_dir)
            
            # 加载 AI 模型配置
            ai_config_path = os.path.join(config_dir, 'ai_model.yaml')
            
            if os.path.exists(ai_config_path):
                ai_config_full = load_yaml_file(ai_config_path)
                # 使用 'default' 节点而不是 'ai_model'
                main_config['ai_model'] = ai_config_full.get('default', {})
            else:
                self.logger.error(f"AI 模型配置文件不存在: {ai_config_path}")
                sys.exit(1)
            
            return main_config
            
        except Exception as e:
            self.logger.error(f"加载配置失败: {e}")
            sys.exit(1)
    
    def run(self):
        """执行分析任务"""
        if self.args.update_id:
            # 单条分析模式
            self._analyze_single()
        elif self.args.batch:
            # 多 ID 批量分析模式
            self._analyze_by_ids()
        else:
            # 批量分析模式（默认）
            self._analyze_batch()
    
    def _analyze_single(self):
        """分析单条记录"""
        update_id = self.args.update_id
        
        self.logger.info(f"开始分析单条记录: {update_id}")
        
        # 查询记录
        update_data = self.data_layer.get_update_by_id(update_id)
        
        if not update_data:
            self.logger.error(f"未找到记录: {update_id}")
            return
        
        # 检查是否已分析
        if update_data.get('title_translated') and not self.args.force:
            self.logger.warning(f"记录已分析过，跳过（使用 --force 强制重新分析）")
            return
        
        # 执行分析
        result = self.analyzer.analyze(update_data)
        
        if result:
            # 保存分析结果到文件
            file_path = self._save_analysis_to_file(update_id, update_data, result)
            if file_path:
                self.logger.info(f"📄 分析结果已保存至: {file_path}")
                # 回写文件路径到数据库
                result['analysis_filepath'] = file_path
            
            # 更新数据库
            if not self.args.dry_run:
                success = self.data_layer.update_analysis_fields(update_id, result)
                if success:
                    self.logger.info(f"✅ 分析成功并已保存")
                else:
                    self.logger.error(f"❌ 数据库更新失败")
            else:
                self.logger.info(f"✅ 分析成功（预览模式，未写入数据库）")
                self.logger.info(f"分析结果:\n{self._format_result(result)}")
        else:
            self.logger.error(f"❌ 分析失败")
    
    def _save_analysis_to_file(self, update_id: str, update_data: dict, result: dict) -> Optional[str]:
        """
        保存分析结果到文件
        
        Args:
            update_id: 更新记录 ID
            update_data: 原始更新数据
            result: 分析结果
            
        Returns:
            保存的文件路径，失败返回 None
        """
        try:
            # 创建输出目录
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            vendor = update_data.get('vendor', 'unknown')
            output_dir = os.path.join(project_root, 'data', 'analyzed', vendor)
            os.makedirs(output_dir, exist_ok=True)
            
            # 构建完整的分析数据
            analysis_data = {
                'update_id': update_id,
                'vendor': vendor,
                'source_channel': update_data.get('source_channel', ''),
                'original_title': update_data.get('title', ''),
                'source_url': update_data.get('source_url', ''),
                'publish_date': update_data.get('publish_date', ''),
                'analyzed_at': datetime.now().isoformat(),
                'analysis': {
                    'title_translated': result.get('title_translated', ''),
                    'content_summary': result.get('content_summary', ''),
                    'update_type': result.get('update_type', ''),
                    'product_subcategory': result.get('product_subcategory', ''),
                    'tags': json.loads(result.get('tags', '[]')) if isinstance(result.get('tags'), str) else result.get('tags', [])
                }
            }
            
            # 生成文件名
            filename = f"{update_id}.json"
            file_path = os.path.join(output_dir, filename)
            
            # 写入文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(analysis_data, f, ensure_ascii=False, indent=2)
            
            return file_path
            
        except Exception as e:
            self.logger.error(f"保存分析结果到文件失败: {e}")
            return None
    
    def _analyze_by_ids(self):
        """按指定 ID 列表分析"""
        # 解析 ID 列表（支持逗号分隔）
        id_list = [id.strip() for id in self.args.batch.split(',') if id.strip()]
        
        if not id_list:
            self.logger.error("未提供有效的 ID")
            return
        
        self.logger.info(f"🔄 开始分析 {len(id_list)} 条指定记录...")
        
        # 获取记录
        updates = []
        for update_id in id_list:
            update_data = self.data_layer.get_update_by_id(update_id)
            if update_data:
                # 检查是否已分析
                if update_data.get('title_translated') and not self.args.force:
                    self.logger.warning(f"跳过已分析: {update_id}（使用 --force 强制）")
                    continue
                updates.append(update_data)
            else:
                self.logger.warning(f"未找到记录: {update_id}")
        
        if not updates:
            self.logger.info("没有待处理的记录")
            return
        
        # 统计变量
        process_count = len(updates)
        success_count = 0
        fail_count = 0
        start_time = time.time()
        
        self.logger.info(f"📊 待处理记录: {process_count} 条")
        
        # 并发处理
        batch_config = self.config.get('ai_model', {}).get('batch_processing', {})
        max_workers = batch_config.get('max_workers', 5)
        self.logger.info(f"⚡ 并发线程数: {max_workers}")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_update = {
                executor.submit(self._analyze_single_item, update_data): update_data
                for update_data in updates
            }
            
            for idx, future in enumerate(as_completed(future_to_update), 1):
                update_data = future_to_update[future]
                update_id = update_data.get('update_id', 'unknown')
                
                try:
                    success = future.result()
                    if success:
                        success_count += 1
                        self.logger.debug(f"✓ {idx}/{process_count} {update_id}")
                    else:
                        fail_count += 1
                        self.logger.warning(f"✗ {idx}/{process_count} {update_id} - 分析失败")
                except Exception as e:
                    fail_count += 1
                    self.logger.error(f"✗ {idx}/{process_count} {update_id} - 异常: {e}")
                
                self._print_progress(idx, process_count, success_count, fail_count, start_time)
        
        # 最终进度和统计
        self._print_progress(process_count, process_count, success_count, fail_count, start_time)
        total_time = time.time() - start_time
        self._print_summary(process_count, success_count, fail_count, total_time)

    def _analyze_batch(self):
        """批量分析（并发处理）"""
        # 统计待处理数量
        total = self.data_layer.count_unanalyzed_updates(
            vendor=self.args.vendor,
            source_channel=self.args.source,
            include_analyzed=self.args.force
        )
        
        if total == 0:
            mode_desc = "记录" if self.args.force else "待分析的记录"
            self.logger.info(f"没有{mode_desc}")
            return
        
        # 确定处理数量
        limit = self.args.limit if self.args.limit else total
        process_count = min(limit, total)
        
        mode_desc = "强制重新分析" if self.args.force else "批量分析"
        self.logger.info(f"🔄 开始{mode_desc}...")
        total_desc = "总记录" if self.args.force else "未分析"
        self.logger.info(f"📊 待处理记录: {process_count} 条（共 {total} 条{total_desc}）")
        
        # 获取待处理记录
        updates = self.data_layer.get_unanalyzed_updates(
            limit=limit,
            vendor=self.args.vendor,
            source_channel=self.args.source,
            include_analyzed=self.args.force
        )
        
        # 统计变量
        success_count = 0
        fail_count = 0
        start_time = time.time()
        
        # 并发线程数：从配置读取
        batch_config = self.config.get('ai_model', {}).get('batch_processing', {})
        max_workers = batch_config.get('max_workers', 5)
        self.logger.info(f"⚡ 并发线程数: {max_workers}")
        
        # 使用线程池并发处理
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交任务
            future_to_update = {
                executor.submit(self._analyze_single_item, update_data): update_data
                for update_data in updates
            }
            
            # 处理完成的任务
            for idx, future in enumerate(as_completed(future_to_update), 1):
                update_data = future_to_update[future]
                update_id = update_data.get('update_id', 'unknown')
                
                try:
                    # 获取结果
                    success = future.result()
                    
                    if success:
                        success_count += 1
                        self.logger.debug(f"✓ {idx}/{process_count} {update_id}")
                    else:
                        fail_count += 1
                        self.logger.warning(f"✗ {idx}/{process_count} {update_id} - 分析失败")
                        
                except Exception as e:
                    fail_count += 1
                    self.logger.error(f"✗ {idx}/{process_count} {update_id} - 异常: {e}")
                
                # 显示进度
                self._print_progress(idx, process_count, success_count, fail_count, start_time)
        
        # 最终进度
        self._print_progress(process_count, process_count, success_count, fail_count, start_time)
        
        # 显示统计
        total_time = time.time() - start_time
        self._print_summary(process_count, success_count, fail_count, total_time)
    
    def _analyze_single_item(self, update_data: dict) -> bool:
        """
        分析单条记录（线程安全）
        
        Args:
            update_data: 更新数据
            
        Returns:
            是否成功
        """
        update_id = update_data.get('update_id', 'unknown')
        
        try:
            # 执行分析
            result = self.analyzer.analyze(update_data)
            
            if result:
                # 保存分析结果到文件
                file_path = self._save_analysis_to_file(update_id, update_data, result)
                if file_path:
                    # 回写文件路径到 result
                    result['analysis_filepath'] = file_path
                
                # 更新数据库
                if not self.args.dry_run:
                    return self.data_layer.update_analysis_fields(update_id, result)
                else:
                    return True
            else:
                return False
                
        except Exception as e:
            self.logger.error(f"分析异常 {update_id}: {e}")
            return False
    
    def _print_progress(self, current, total, success, fail, start_time):
        """打印进度条"""
        percent = (current / total) * 100 if total > 0 else 0
        elapsed = time.time() - start_time
        
        # 计算进度条
        bar_length = 20
        filled = int(bar_length * current / total) if total > 0 else 0
        bar = '█' * filled + '░' * (bar_length - filled)
        
        # 格式化时间
        elapsed_str = self._format_time(elapsed)
        
        # 打印（覆盖当前行）
        print(f"\r[{bar}] {current}/{total} ({percent:.1f}%) | "
              f"成功: {success} | 失败: {fail} | 耗时: {elapsed_str}", end='', flush=True)
    
    def _print_summary(self, total, success, fail, elapsed):
        """打印统计摘要"""
        print("\n")  # 换行
        self.logger.info("✅ 分析完成!")
        self.logger.info(f"总计: {total} 条")
        self.logger.info(f"成功: {success} 条 ({success/total*100:.1f}%)")
        self.logger.info(f"失败: {fail} 条 ({fail/total*100:.1f}%)")
        self.logger.info(f"总耗时: {self._format_time(elapsed)}")
    
    def _format_time(self, seconds):
        """格式化时间"""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.0f}m{seconds%60:.0f}s"
        else:
            hours = seconds / 3600
            minutes = (seconds % 3600) / 60
            return f"{hours:.0f}h{minutes:.0f}m"
    
    def _format_result(self, result):
        """格式化分析结果"""
        lines = []
        for key, value in result.items():
            if key == 'tags':
                lines.append(f"  {key}: {value}")
            else:
                # 截断过长的内容
                value_str = str(value)
                if len(value_str) > 100:
                    value_str = value_str[:100] + "..."
                lines.append(f"  {key}: {value_str}")
        return "\n".join(lines)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='更新记录 AI 分析工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  # 批量分析（默认）
  %(prog)s

  # 分析单条记录
  %(prog)s --update-id abc123

  # 批量分析前 100 条
  %(prog)s --limit 100

  # 仅分析 AWS 记录
  %(prog)s --vendor aws

  # 预览模式（不写入数据库）
  %(prog)s --limit 10 --dry-run
        '''
    )
    
    # 单条/多条分析选项
    parser.add_argument(
        '--update-id',
        type=str,
        help='分析指定 ID 的更新记录'
    )
    parser.add_argument(
        '--batch',
        type=str,
        help='批量分析多个指定 ID（逗号分隔，如: id1,id2,id3）'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='限制批量处理数量'
    )
    parser.add_argument(
        '--vendor',
        type=str,
        choices=['aws', 'azure', 'gcp', 'huawei', 'tencentcloud', 'volcengine'],
        help='仅分析指定厂商的记录'
    )
    parser.add_argument(
        '--source',
        type=str,
        help='仅分析指定数据源类型（如 blog, whatsnew）'
    )
    
    # 通用选项
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='预览模式，不实际写入数据库'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='强制重新分析已分析过的记录'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='显示详细日志'
    )
    
    args = parser.parse_args()
    
    # 执行脚本
    script = AnalyzeUpdatesScript(args)
    script.run()


if __name__ == '__main__':
    main()
