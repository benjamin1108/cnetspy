#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Chat API 路由
提供 AI 对话功能
"""

import os
import logging
from typing import List, Optional, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

from ..config import settings
from src.utils.config import get_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])


class ChatMessage(BaseModel):
    """聊天消息"""
    role: str = Field(..., description="消息角色: system/user/assistant")
    content: str = Field(..., description="消息内容")


class ToolFunction(BaseModel):
    """工具函数定义"""
    name: str
    description: str
    parameters: dict = Field(default_factory=dict)


class Tool(BaseModel):
    """工具定义"""
    type: str = "function"
    function: ToolFunction


class ChatRequest(BaseModel):
    """聊天请求"""
    messages: List[ChatMessage] = Field(..., description="消息历史")
    tools: Optional[List[Tool]] = Field(default=None, description="可用工具列表")
    model: Optional[str] = Field(default=None, description="模型名称")
    temperature: Optional[float] = Field(default=0.7, ge=0, le=1)
    max_tokens: Optional[int] = Field(default=4096, ge=1)


class ToolCallFunction(BaseModel):
    """工具调用函数"""
    name: str
    arguments: str


class ToolCall(BaseModel):
    """工具调用"""
    id: str
    type: str = "function"
    function: ToolCallFunction


class ChatChoice(BaseModel):
    """聊天选择"""
    index: int = 0
    message: dict
    finish_reason: str = "stop"


class ChatResponse(BaseModel):
    """聊天响应 - OpenAI 兼容格式"""
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatChoice]


def get_gemini_client():
    """获取 Gemini 客户端"""
    if genai is None:
        raise HTTPException(
            status_code=500,
            detail="google-genai 库未安装"
        )
    
    # 加载配置
    ai_config = get_config("ai_model")
    # 优先使用 chatbox 配置，否则回退到 default
    chatbox_config = ai_config.get("chatbox", {})
    default_config = ai_config.get("default", {})
    
    # 合并配置：chatbox 覆盖 default
    config = {**default_config, **chatbox_config}
    
    api_key_env = config.get("api_key_env", "GEMINI_API_KEY")
    api_key = os.getenv(api_key_env)
    
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail=f"未配置 API Key 环境变量: {api_key_env}"
        )
    
    return genai.Client(api_key=api_key), config


def convert_messages_to_contents(messages: List[ChatMessage]) -> tuple[str, list]:
    """
    将消息列表转换为 Gemini 格式
    返回: (system_instruction, contents)
    """
    system_instruction = ""
    contents = []
    
    for msg in messages:
        if msg.role == "system":
            system_instruction += msg.content + "\n"
        elif msg.role == "user":
            contents.append({"role": "user", "parts": [{"text": msg.content}]})
        elif msg.role == "assistant":
            contents.append({"role": "model", "parts": [{"text": msg.content}]})
    
    return system_instruction.strip(), contents


def format_tools_prompt(tools: Optional[List[Tool]]) -> str:
    """格式化工具提示"""
    if not tools:
        return ""
    
    tool_descriptions = []
    for tool in tools:
        func = tool.function
        tool_descriptions.append(f"- {func.name}: {func.description}")
    
    return "\n\n可用的分析工具：\n" + "\n".join(tool_descriptions)


@router.get("/prompts")
async def get_chat_prompts():
    """
    获取 Chatbox 提示词配置
    返回系统提示词和总结提示词模板
    """
    try:
        prompts_config = get_config("chatbox_prompts")
        return {
            "system_prompt": prompts_config.get("system_prompt", ""),
            "summary_prompt": prompts_config.get("summary_prompt", ""),
            "tools_description_template": prompts_config.get("tools_description_template", ""),
            "vendor_names": prompts_config.get("vendor_names", {})
        }
    except Exception as e:
        logger.error(f"Failed to load prompts config: {e}")
        # 返回默认提示词
        return {
            "system_prompt": "你是 CloudNetSpy 的 AI 助手，帮助用户分析云厂商的产品更新动态。",
            "summary_prompt": "请根据工具返回的数据，用中文用户友好的方式总结和展示结果。",
            "tools_description_template": "",
            "vendor_names": {}
        }


@router.post("/completions", response_model=ChatResponse)
async def chat_completions(request: ChatRequest):
    """
    处理聊天请求
    兼容 OpenAI Chat Completions API 格式
    """
    import time
    import uuid
    
    try:
        client, config = get_gemini_client()
        model_name = request.model or config.get("model_name", "gemini-2.0-flash-exp")
        
        # 转换消息格式
        system_instruction, contents = convert_messages_to_contents(request.messages)
        
        # 添加工具信息到系统提示
        if request.tools:
            tools_prompt = format_tools_prompt(request.tools)
            system_instruction += tools_prompt
        
        # 配置生成参数
        generation_config = {
            "temperature": request.temperature,
            "max_output_tokens": request.max_tokens,
        }
        
        # 调用 Gemini API
        logger.info(f"Calling Gemini API: model={model_name}, contents_len={len(contents)}")
        logger.debug(f"System instruction: {system_instruction[:200]}...")
        
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction if system_instruction else None,
                    **generation_config
                )
            )
            
            # 提取响应文本
            if response is None:
                logger.error("Gemini API returned None response")
                response_text = ""
            elif hasattr(response, 'text') and response.text:
                response_text = response.text
                logger.info(f"Got response: {len(response_text)} chars")
            elif hasattr(response, 'candidates') and response.candidates:
                # 尝试从 candidates 中获取文本
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and candidate.content.parts:
                    response_text = candidate.content.parts[0].text
                    logger.info(f"Got response from candidates: {len(response_text)} chars")
                else:
                    logger.error(f"No text in candidate: {candidate}")
                    # 检查是否被安全审查拦截
                    if hasattr(candidate, 'finish_reason'):
                        logger.error(f"Finish reason: {candidate.finish_reason}")
                    if hasattr(candidate, 'safety_ratings'):
                        logger.error(f"Safety ratings: {candidate.safety_ratings}")
                    response_text = ""
            else:
                logger.error(f"Unexpected response format: {type(response)}")
                # 检查 prompt_feedback
                if hasattr(response, 'prompt_feedback'):
                    logger.error(f"Prompt feedback: {response.prompt_feedback}")
                response_text = ""
        except Exception as api_error:
            logger.error(f"Gemini API call failed: {api_error}")
            raise HTTPException(status_code=500, detail=f"AI 调用失败: {api_error}")
        
        # 构建响应
        return ChatResponse(
            id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
            created=int(time.time()),
            model=model_name,
            choices=[
                ChatChoice(
                    message={
                        "role": "assistant",
                        "content": response_text
                    },
                    finish_reason="stop"
                )
            ]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat completion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
