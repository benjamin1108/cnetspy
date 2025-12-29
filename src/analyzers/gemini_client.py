#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Gemini API 客户端封装

提供 Gemini API 调用、错误处理、重试机制和速率限制功能
"""

import os
import time
import json
import logging
import re
import threading
from typing import Dict, Any, Optional
from datetime import datetime

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None


class GeminiClient:
    """Gemini API 客户端"""
    
    # 全局锁，用于控制所有实例的 API 调用频率
    _global_lock = threading.Lock()
    _last_api_call_time = 0
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化 Gemini 客户端
        
        Args:
            config: AI 模型配置字典
        """
        self.logger = logging.getLogger(__name__)
        self.config = config
        
        # 检查 genai 库是否可用
        if genai is None:
            raise ImportError(
                "google-genai 库未安装。请运行: pip install google-genai"
            )
        
        # 获取 API Key
        api_key_env = config.get('api_key_env', 'GEMINI_API_KEY')
        api_key = os.getenv(api_key_env)
        
        if not api_key:
            raise ValueError(
                f"未找到 API Key。请设置环境变量: {api_key_env}"
            )
        
        # 创建客户端实例 (新 SDK 方式)
        self.client = genai.Client(api_key=api_key)
        
        # 获取模型名称
        self.model_name = config.get('model_name', 'gemini-2.0-flash-exp')
        
        # 获取生成参数
        generation_config = config.get('generation', {})
        
        # 定义响应 Schema（结构化输出）
        response_schema = {
            "type": "object",
            "properties": {
                "is_network_related": {
                    "type": "boolean",
                    "description": "是否与云网络产品/服务相关"
                },
                "title_translated": {
                    "type": "string",
                    "description": "中文翻译标题，不超过50字"
                },
                "content_summary": {
                    "type": "string",
                    "description": "结构化摘要，使用Markdown格式，150-500字"
                },
                "update_type": {
                    "type": "string",
                    "description": "更新类型分类"
                },
                "product_subcategory": {
                    "type": "string",
                    "description": "产品子类，小写英文+数字+下划线"
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "3-8个关键词标签"
                }
            },
            "required": ["is_network_related", "title_translated", "content_summary", "update_type", "product_subcategory", "tags"]
        }
        
        # 保存生成配置 (启用结构化输出)
        self.generation_config = types.GenerateContentConfig(
            temperature=generation_config.get('temperature', 0.5),
            top_p=generation_config.get('top_p', 0.9),
            top_k=generation_config.get('top_k', 40),
            max_output_tokens=generation_config.get('max_output_tokens', 65535),
            response_mime_type="application/json",
            response_schema=response_schema,
        )
        
        # 速率限制配置
        rate_limit_config = config.get('rate_limit', {})
        self.interval_seconds = rate_limit_config.get('interval', 0.5)
        self.max_retries = rate_limit_config.get('max_retries', 3)
        self.retry_backoff_base = rate_limit_config.get('retry_backoff_base', 2.0)
        
        self.logger.info(f"Gemini 客户端初始化成功: 模型={self.model_name}")
    
    def generate_content(self, prompt: str) -> str:
        """
        调用 Gemini API 生成内容
        
        Args:
            prompt: 提示词
            
        Returns:
            生成的文本内容
            
        Raises:
            Exception: API 调用失败
        """
        for attempt in range(self.max_retries):
            try:
                # 全局速率限制控制
                self._wait_for_global_rate_limit()
                
                # 记录请求
                self.logger.debug(f"调用 Gemini API (尝试 {attempt + 1}/{self.max_retries})")
                
                # 调用 API (新 SDK 方式)
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=self.generation_config
                )
                
                # 提取文本
                if response and response.text:
                    self.logger.debug(f"API 调用成功，响应长度: {len(response.text)}")
                    return response.text
                else:
                    raise Exception("API 返回空响应")
                    
            except Exception as e:
                error_msg = str(e)
                self.logger.warning(f"API 调用失败 (尝试 {attempt + 1}/{self.max_retries}): {error_msg}")
                
                # 检查是否是速率限制错误
                if '429' in error_msg or 'quota' in error_msg.lower():
                    # 速率限制，使用更长的退避时间
                    backoff_time = self.interval_seconds * (self.retry_backoff_base ** attempt) * 2
                    self.logger.warning(f"API 速率限制，等待 {backoff_time:.1f} 秒后重试")
                    time.sleep(backoff_time)
                elif '401' in error_msg or 'authentication' in error_msg.lower():
                    # 认证失败，不重试
                    raise Exception(f"API 认证失败，请检查 API Key: {error_msg}")
                else:
                    # 其他错误，指数退避重试
                    if attempt < self.max_retries - 1:
                        backoff_time = self.interval_seconds * (self.retry_backoff_base ** attempt)
                        self.logger.warning(f"等待 {backoff_time:.1f} 秒后重试")
                        time.sleep(backoff_time)
                    else:
                        # 最后一次尝试失败
                        raise Exception(f"API 调用失败，已重试 {self.max_retries} 次: {error_msg}")
        
        raise Exception(f"API 调用失败，已达到最大重试次数: {self.max_retries}")
    
    def generate_text(self, prompt: str) -> str:
        """
        调用 Gemini API 生成纯文本内容（不使用 JSON Schema）
        
        Args:
            prompt: 提示词
            
        Returns:
            生成的纯文本内容
        """
        # 纯文本配置（不使用 JSON schema）
        generation_config = self.config.get('generation', {})
        text_config = types.GenerateContentConfig(
            temperature=generation_config.get('temperature', 0.5),
            top_p=generation_config.get('top_p', 0.9),
            top_k=generation_config.get('top_k', 40),
            max_output_tokens=generation_config.get('max_output_tokens', 65535),
        )
        
        for attempt in range(self.max_retries):
            try:
                self._wait_for_global_rate_limit()
                self.logger.debug(f"调用 Gemini API (纯文本模式, 尝试 {attempt + 1}/{self.max_retries})")
                
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=text_config
                )
                
                if response and response.text:
                    self.logger.debug(f"API 调用成功，响应长度: {len(response.text)}")
                    return response.text
                else:
                    raise Exception("API 返回空响应")
                    
            except Exception as e:
                error_msg = str(e)
                self.logger.warning(f"API 调用失败 (尝试 {attempt + 1}/{self.max_retries}): {error_msg}")
                
                if '429' in error_msg or 'quota' in error_msg.lower():
                    backoff_time = self.interval_seconds * (self.retry_backoff_base ** attempt) * 2
                    self.logger.warning(f"API 速率限制，等待 {backoff_time:.1f} 秒后重试")
                    time.sleep(backoff_time)
                elif '401' in error_msg or 'authentication' in error_msg.lower():
                    raise Exception(f"API 认证失败: {error_msg}")
                else:
                    if attempt < self.max_retries - 1:
                        backoff_time = self.interval_seconds * (self.retry_backoff_base ** attempt)
                        time.sleep(backoff_time)
                    else:
                        raise Exception(f"API 调用失败: {error_msg}")
        
        raise Exception(f"API 调用失败，已达到最大重试次数: {self.max_retries}")
    
    def parse_json_response(self, text: str) -> Dict[str, Any]:
        """
        解析 JSON 响应
        
        Args:
            text: API 返回的文本
            
        Returns:
            解析后的字典
            
        Raises:
            ValueError: JSON 解析失败
        """
        try:
            # 尝试直接解析
            parsed = json.loads(text)
            
            # 处理数组包装的情况
            if isinstance(parsed, list) and len(parsed) > 0:
                self.logger.debug("检测到数组格式响应，提取第一个元素")
                return parsed[0]
            
            return parsed
            
        except json.JSONDecodeError:
            # 尝试提取 JSON 部分
            self.logger.warning("直接解析 JSON 失败，尝试提取 JSON 内容")
            
            # 尝试匹配 ```json ... ``` 格式
            json_match = re.search(r'```json\s*\n(.*?)\n```', text, re.DOTALL)
            if json_match:
                try:
                    parsed = json.loads(json_match.group(1))
                    if isinstance(parsed, list) and len(parsed) > 0:
                        return parsed[0]
                    return parsed
                except json.JSONDecodeError:
                    pass
            
            # 尝试匹配 { ... } 格式
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                try:
                    parsed = json.loads(json_match.group(0))
                    if isinstance(parsed, list) and len(parsed) > 0:
                        return parsed[0]
                    return parsed
                except json.JSONDecodeError:
                    pass
            
            # 记录原始响应
            self.logger.error(f"JSON 解析失败，原始响应: {text[:500]}")
            raise ValueError(f"无法从响应中提取有效的 JSON: {text[:200]}")
    
    def _wait_for_global_rate_limit(self):
        """全局速率限制控制（线程安全）"""
        with GeminiClient._global_lock:
            current_time = time.time()
            elapsed = current_time - GeminiClient._last_api_call_time
            
            if elapsed < self.interval_seconds:
                wait_time = self.interval_seconds - elapsed
                self.logger.debug(f"全局限速：等待 {wait_time:.2f} 秒")
                time.sleep(wait_time)
            
            # 更新全局请求时间
            GeminiClient._last_api_call_time = time.time()
    
    def validate_response(self, data: Dict[str, Any]) -> bool:
        """
        验证响应数据的完整性
        
        Args:
            data: 解析后的响应数据
            
        Returns:
            验证是否通过
        """
        required_fields = [
            'title_translated',
            'content_summary',
            'update_type',
            'product_subcategory',
            'tags'
        ]
        
        missing_fields = []
        for field in required_fields:
            if field not in data:
                missing_fields.append(field)
        
        if missing_fields:
            self.logger.warning(f"响应缺少必需字段: {', '.join(missing_fields)}")
            self.logger.debug(f"完整响应内容: {data}")
            return False
        
        # 验证 tags 是否为列表
        if not isinstance(data.get('tags'), list):
            self.logger.warning("tags 字段不是列表类型")
            self.logger.debug(f"完整响应内容: {data}")
            return False
        
        return True
