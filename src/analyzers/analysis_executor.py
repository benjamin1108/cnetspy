#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
分析执行器 - CLI和API的共享业务逻辑

封装"分析+保存+更新"的完整流程，供以下模块复用：
- scripts/analyze_updates.py (CLI工具)
- src/api/services/analysis_service.py (API服务)
"""

import json
import os
from typing import Dict, Any, Optional
from datetime import datetime
import logging
from tabulate import tabulate

logger = logging.getLogger(__name__)


class AnalysisExecutor:
    """
    分析执行器
    
    职责：
    1. 调用 UpdateAnalyzer 进行AI分析
    2. 保存分析结果到文件（可选）
    3. 更新数据库字段
    4. 记录质量问题到数据库（非网络内容删除、subcategory为空等）
    """
    
    # 当前批次ID（批量分析时设置）
    _current_batch_id: Optional[str] = None
    
    def __init__(self, analyzer, data_layer, config: Dict[str, Any]):
        """
        初始化执行器
        
        Args:
            analyzer: UpdateAnalyzer 实例
            data_layer: UpdateDataLayer 实例
            config: 配置字典
                - enable_file_save: 是否启用文件保存（默认True）
                - output_base_dir: 文件输出根目录（默认 'data/analyzed'）
                - batch_id: 批次ID（可选，批量分析时使用）
        """
        self.analyzer = analyzer
        self.data_layer = data_layer
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # 文件保存配置
        self.enable_file_save = config.get('enable_file_save', True)
        self.output_base_dir = config.get('output_base_dir', 'data/analyzed')
        
        # 设置批次ID
        batch_id = config.get('batch_id')
        if batch_id:
            AnalysisExecutor._current_batch_id = batch_id
    
    @classmethod
    def set_batch_id(cls, batch_id: str) -> None:
        """设置当前批次ID"""
        cls._current_batch_id = batch_id
    
    @classmethod
    def clear_batch_id(cls) -> None:
        """清除批次ID"""
        cls._current_batch_id = None
    
    def execute_analysis(
        self, 
        update_data: Dict[str, Any],
        save_to_db: bool = True,
        save_to_file: Optional[bool] = None
    ) -> Optional[Dict[str, Any]]:
        """
        执行完整的分析流程
        
        Args:
            update_data: 更新数据字典
            save_to_db: 是否保存到数据库（默认True）
            save_to_file: 是否保存到文件（None=使用全局配置）
            
        Returns:
            分析结果字典，失败返回 None
            
        流程：
            1. AI分析
            2. 检查is_network_related（不相关则删除并记录）
            3. 检查product_subcategory（为空则记录问题）
            4. 保存文件（可选）
            5. 更新数据库
        """
        update_id = update_data.get('update_id')
        vendor = update_data.get('vendor', '')
        title = update_data.get('title', '')
        source_url = update_data.get('source_url', '')
        
        try:
            # 1. 执行AI分析
            result = self.analyzer.analyze(update_data)
            if not result:
                self.logger.error(f"AI分析失败: {update_id}")
                # 记录分析失败
                self._record_quality_issue(
                    update_id=update_id,
                    issue_type='analysis_failed',
                    auto_action='kept',
                    vendor=vendor,
                    title=title,
                    source_url=source_url
                )
                return None
            
            # 2. 检查是否与网络相关，不相关则删除
            is_network_related = result.get('is_network_related', True)
            if not is_network_related:
                self._handle_non_network_content(update_id, update_data)
                return {'deleted': True, 'reason': 'not_network_related'}
            
            # 3. 记录 product_subcategory 为空的情况（不删除，仅记录）
            product_subcategory = result.get('product_subcategory', '')
            if not product_subcategory:
                self._record_quality_issue(
                    update_id=update_id,
                    issue_type='empty_subcategory',
                    auto_action='kept',
                    vendor=vendor,
                    title=title,
                    source_url=source_url
                )
                self.logger.warning(f"subcategory为空: {title[:50]}...")
            
            # 4. 保存到文件（如果启用）
            should_save_file = save_to_file if save_to_file is not None else self.enable_file_save
            if should_save_file:
                file_path = self._save_analysis_to_file(update_id, update_data, result)
                if file_path:
                    result['analysis_filepath'] = file_path
                    self.logger.debug(f"分析结果已保存至文件: {file_path}")
            
            # 5. 更新数据库
            if save_to_db:
                success = self.data_layer.update_analysis_fields(update_id, result)
                if not success:
                    self.logger.error(f"数据库更新失败: {update_id}")
                    return None
            
            return result
            
        except Exception as e:
            self.logger.error(f"分析执行异常 {update_id}: {e}")
            return None
    
    def _save_analysis_to_file(
        self, 
        update_id: str, 
        update_data: Dict[str, Any], 
        result: Dict[str, Any]
    ) -> Optional[str]:
        """
        保存分析结果到文件
        
        Args:
            update_id: 更新记录ID
            update_data: 原始更新数据
            result: 分析结果
            
        Returns:
            文件路径，失败返回 None
        """
        try:
            # 创建输出目录
            vendor = update_data.get('vendor', 'unknown')
            output_dir = os.path.join(self.output_base_dir, vendor)
            os.makedirs(output_dir, exist_ok=True)
            
            # 构建分析数据
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
            
            # 生成文件路径
            filename = f"{update_id}.json"
            file_path = os.path.join(output_dir, filename)
            
            # 写入文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(analysis_data, f, ensure_ascii=False, indent=2)
            
            return file_path
            
        except Exception as e:
            self.logger.error(f"保存分析文件失败: {e}")
            return None
    
    def _handle_non_network_content(self, update_id: str, update_data: Dict[str, Any]) -> None:
        """
        处理非网络相关内容：删除记录并记录质量问题
        
        Args:
            update_id: 记录ID
            update_data: 更新数据
        """
        title = update_data.get('title', '')
        source_url = update_data.get('source_url', '')
        vendor = update_data.get('vendor', '')
        raw_filepath = update_data.get('raw_filepath', '')
        
        # 1. 删除数据库记录
        try:
            self.data_layer.delete_update(update_id)
        except Exception as e:
            self.logger.error(f"删除数据库记录失败: {e}")
        
        # 2. 删除原始文件
        if raw_filepath and os.path.exists(raw_filepath):
            try:
                os.remove(raw_filepath)
                self.logger.debug(f"删除原始文件: {raw_filepath}")
            except Exception as e:
                self.logger.error(f"删除原始文件失败: {e}")
        
        # 3. 记录质量问题到数据库
        self._record_quality_issue(
            update_id=update_id,
            issue_type='not_network_related',
            auto_action='deleted',
            vendor=vendor,
            title=title,
            source_url=source_url
        )
        
        self.logger.info(f"删除[非网络内容]: {title[:50]}...")
    
    def _record_quality_issue(
        self,
        update_id: str,
        issue_type: str,
        auto_action: str,
        vendor: str = '',
        title: str = '',
        source_url: str = ''
    ) -> None:
        """
        记录质量问题到数据库
        
        Args:
            update_id: 记录ID
            issue_type: 问题类型
            auto_action: 自动动作 (deleted/kept)
            vendor: 厂商
            title: 标题
            source_url: 来源链接
        """
        try:
            self.data_layer.insert_quality_issue(
                update_id=update_id,
                issue_type=issue_type,
                auto_action=auto_action,
                vendor=vendor,
                title=title,
                source_url=source_url,
                batch_id=AnalysisExecutor._current_batch_id
            )
        except Exception as e:
            self.logger.error(f"记录质量问题失败: {e}")
    
    @classmethod
    def print_analysis_report(cls, data_layer) -> None:
        """
        输出分析报告（从数据库读取）
        
        Args:
            data_layer: UpdateDataLayer 实例
        """
        try:
            stats = data_layer.get_issue_statistics()
            
            if stats['total_open'] == 0 and stats['total_resolved'] == 0:
                return
            
            print("\n" + "=" * 60)
            print("🔍 质量问题报告")
            print("=" * 60)
            
            # 问题统计表格
            status_data = [
                ["⚠️  待处理", stats['total_open']],
                ["✅ 已解决", stats['total_resolved']],
                ["⏭️  已忽略", stats['total_ignored']],
            ]
            print(tabulate(status_data, headers=["状态", "数量"], tablefmt="simple"))
            
            if stats['by_type']:
                print("\n按类型统计(待处理):")
                type_data = [[t, c] for t, c in stats['by_type'].items()]
                print(tabulate(type_data, headers=["问题类型", "数量"], tablefmt="simple"))
            
            if stats['total_open'] > 0:
                print("\n💡 使用 ./run.sh check --issues 查看详情")
            
            print("=" * 60 + "\n")
            
        except Exception as e:
            logger.error(f"获取分析报告失败: {e}")
