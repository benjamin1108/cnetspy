#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
LiteLLM 客户端封装

保留 GeminiClient 类名作为兼容入口，底层通过 LiteLLM 调用 Gemini、DashScope
等不同 LLM 服务商，并提供错误处理、重试机制和速率限制功能。
"""

import os
import time
import json
import logging
import re
import threading
from typing import Dict, Any, Optional, List

# LiteLLM 默认会启用较详细的 DEBUG 日志。必须在 import litellm 前设置。
os.environ.setdefault("LITELLM_LOG", "WARNING")

try:
    import litellm
except ImportError:
    litellm = None


class GeminiClient:
    """LiteLLM 客户端（兼容旧 GeminiClient 调用名）"""
    
    # 全局锁，用于控制所有实例的 API 调用频率
    _global_lock = threading.Lock()
    _last_api_call_time = 0

    _PROVIDER_API_KEY_ENV = {
        "gemini": "GEMINI_API_KEY",
        "dashscope": "DASHSCOPE_API_KEY",
    }
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化 LiteLLM 客户端
        
        Args:
            config: AI 模型配置字典
        """
        self.logger = logging.getLogger(__name__)
        self.config = config
        
        # 检查 litellm 库是否可用
        if litellm is None:
            raise ImportError(
                "litellm 库未安装。请运行: pip install litellm"
            )
        self._configure_litellm_logging()

        raw_model_name = config.get('model_name')
        if not raw_model_name:
            raise ValueError("未配置模型名称 model_name，已禁止默认回退。")

        raw_provider = config.get('provider')
        inferred_provider = raw_model_name.split('/', 1)[0] if '/' in raw_model_name else None
        self.provider = (raw_provider or inferred_provider or "gemini").lower()
        self.model_name = self._normalize_model_name(raw_model_name, self.provider)

        # 获取 API Key。DashScope/Gemini 默认分别读取 DASHSCOPE_API_KEY/GEMINI_API_KEY。
        self.api_key_env = config.get('api_key_env') or self._PROVIDER_API_KEY_ENV.get(self.provider)
        api_key = os.getenv(self.api_key_env) if self.api_key_env else None
        
        if not api_key:
            raise ValueError(
                f"未找到 API Key。请设置环境变量: {self.api_key_env}"
            )

        self.api_key = api_key
        self.api_base = self._resolve_api_base(config)
        self._ensure_provider_environment()

        # 获取生成参数
        self.generation_config = config.get('generation', {})

        # 定义响应 Schema（结构化输出）
        self.response_schema = {
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

        # 速率限制配置
        rate_limit_config = config.get('rate_limit', {})
        self.interval_seconds = rate_limit_config.get('interval', 0.5)
        self.max_retries = rate_limit_config.get('max_retries', 3)
        self.retry_backoff_base = rate_limit_config.get('retry_backoff_base', 2.0)
        
        self.logger.info(
            "LiteLLM 客户端初始化成功: provider=%s, 模型=%s",
            self.provider,
            self.model_name,
        )

    @staticmethod
    def _normalize_model_name(model_name: str, provider: str) -> str:
        """把本地短模型名规范化为 LiteLLM 模型名。"""
        if '/' in model_name:
            return model_name
        if provider == "gemini":
            return f"gemini/{model_name}"
        if provider == "dashscope":
            return f"dashscope/{model_name}"
        return model_name

    @staticmethod
    def _resolve_api_base(config: Dict[str, Any]) -> Optional[str]:
        api_base_env = config.get("api_base_env")
        if api_base_env:
            env_value = os.getenv(api_base_env)
            if env_value:
                return env_value
        return config.get("api_base")

    def _ensure_provider_environment(self) -> None:
        """LiteLLM 读取部分 provider 的标准环境变量，这里做一次兼容注入。"""
        standard_env = self._PROVIDER_API_KEY_ENV.get(self.provider)
        if standard_env:
            os.environ.setdefault(standard_env, self.api_key)
        if self.provider == "dashscope" and self.api_base:
            os.environ.setdefault("DASHSCOPE_API_BASE", self.api_base)

    @staticmethod
    def _configure_litellm_logging() -> None:
        """压制 LiteLLM 内部调试和费用估算噪声。"""
        if litellm is None:
            return

        for attr, value in (
            ("set_verbose", False),
            ("suppress_debug_info", True),
            ("log_level", "WARNING"),
        ):
            try:
                setattr(litellm, attr, value)
            except Exception:
                pass

        for logger_name in ("LiteLLM", "litellm", "openai", "httpx", "httpcore"):
            logging.getLogger(logger_name).setLevel(logging.WARNING)

        verbose_logger = getattr(litellm, "verbose_logger", None)
        if verbose_logger is not None:
            verbose_logger.setLevel(logging.WARNING)
    
    def generate_content(self, prompt: str) -> str:
        """
        调用 LLM 生成结构化分析内容
        
        Args:
            prompt: 提示词
            
        Returns:
            生成的文本内容
            
        Raises:
            Exception: API 调用失败
        """
        return self.complete_messages(
            [{"role": "user", "content": prompt}],
            response_mime_type="application/json",
            response_schema=self.response_schema,
            response_name="update_analysis",
        )
    
    def generate_text(self, prompt: str, response_mime_type: Optional[str] = None, response_schema: Optional[Dict[str, Any]] = None) -> str:
        """
        调用 LLM 生成内容（支持结构化输出）
        
        Args:
            prompt: 提示词
            response_mime_type: 响应 MIME 类型，例如 "application/json"
            response_schema: 结构化输出的 Schema 字典
            
        Returns:
            生成的文本内容
        """
        return self.complete_messages(
            [{"role": "user", "content": prompt}],
            response_mime_type=response_mime_type,
            response_schema=response_schema,
            response_name="structured_response",
        )

    def complete_messages(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
        response_mime_type: Optional[str] = None,
        response_schema: Optional[Dict[str, Any]] = None,
        response_name: str = "response",
    ) -> str:
        """
        使用 OpenAI Chat Completions 兼容消息格式调用 LiteLLM。

        Args:
            messages: [{"role": "user"|"assistant"|"system", "content": "..."}]
            temperature: 本次调用温度，默认读取配置
            max_output_tokens: 本次最大输出 token，默认读取配置
            response_mime_type: 响应 MIME 类型，例如 "application/json"
            response_schema: JSON Schema，支持时会以 response_format 传给模型
            response_name: JSON Schema 名称
        """
        use_schema = bool(response_mime_type == "application/json" and response_schema)

        for attempt in range(self.max_retries):
            try:
                self._wait_for_global_rate_limit()

                params = self._build_completion_params(
                    messages,
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                    response_schema=response_schema if use_schema else None,
                    response_name=response_name,
                )

                mode_str = "结构化 JSON" if use_schema else "纯文本"
                self.logger.debug(
                    "调用 LiteLLM API (%s, provider=%s, 模型=%s, 尝试 %s/%s)",
                    mode_str,
                    self.provider,
                    self.model_name,
                    attempt + 1,
                    self.max_retries,
                )

                response = litellm.completion(**params)
                text = self._extract_response_text(response)
                if text:
                    self.logger.debug(f"API 调用成功，响应长度: {len(text)}")
                    return text

                raise Exception("API 返回空响应")

            except Exception as e:
                error_msg = str(e)
                self.logger.warning(f"API 调用失败 (尝试 {attempt + 1}/{self.max_retries}): {error_msg}")

                if use_schema and self._is_response_format_error(error_msg):
                    self.logger.warning("当前模型不支持结构化 response_format，降级为纯文本 JSON 输出")
                    use_schema = False
                    continue

                if '429' in error_msg or 'quota' in error_msg.lower() or 'rate limit' in error_msg.lower():
                    backoff_time = self.interval_seconds * (self.retry_backoff_base ** attempt) * 2
                    self.logger.warning(f"API 速率限制，等待 {backoff_time:.1f} 秒后重试")
                    time.sleep(backoff_time)
                elif self._is_permission_error(error_msg):
                    raise Exception(f"API 权限失败，请检查 API Key 配置: {error_msg}")
                else:
                    if attempt < self.max_retries - 1:
                        backoff_time = self.interval_seconds * (self.retry_backoff_base ** attempt)
                        time.sleep(backoff_time)
                    else:
                        raise Exception(f"API 调用失败: {error_msg}")

        raise Exception(f"API 调用失败，已达到最大重试次数: {self.max_retries}")

    def _build_completion_params(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: Optional[float],
        max_output_tokens: Optional[int],
        response_schema: Optional[Dict[str, Any]],
        response_name: str,
    ) -> Dict[str, Any]:
        generation_config = self.generation_config
        params = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature if temperature is not None else generation_config.get('temperature', 0.5),
            "top_p": generation_config.get('top_p', 0.9),
            "max_tokens": max_output_tokens if max_output_tokens is not None else generation_config.get('max_output_tokens', 65535),
        }
        if self.api_base:
            params["api_base"] = self.api_base
        if response_schema:
            params["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": response_name,
                    "schema": response_schema,
                },
            }
        return params

    @staticmethod
    def _extract_response_text(response: Any) -> str:
        """从 LiteLLM/OpenAI 兼容响应里提取文本。"""
        choices = response.get("choices") if isinstance(response, dict) else getattr(response, "choices", None)
        if not choices:
            return ""

        choice = choices[0]
        message = choice.get("message") if isinstance(choice, dict) else getattr(choice, "message", None)
        if not message:
            return ""

        content = message.get("content") if isinstance(message, dict) else getattr(message, "content", None)
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text") or item.get("content")
                else:
                    text = getattr(item, "text", None) or getattr(item, "content", None)
                if text:
                    parts.append(str(text))
            return "\n".join(parts)
        return ""

    @staticmethod
    def _is_response_format_error(error_msg: str) -> bool:
        error_lower = error_msg.lower()
        return (
            "response_format" in error_lower
            or "json_schema" in error_lower
            or "schema" in error_lower and "support" in error_lower
            or "unsupported parameter" in error_lower
        )

    @staticmethod
    def _is_permission_error(error_msg: str) -> bool:
        """判断是否为不应重试的认证或权限错误。"""
        error_lower = error_msg.lower()
        return (
            '401' in error_msg
            or '403' in error_msg
            or 'authentication' in error_lower
            or 'permission_denied' in error_lower
            or 'forbidden' in error_lower
        )
    
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
