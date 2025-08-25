"""
润色服务模块

使用OpenAI Python库调用大语言模型API对文本进行润色处理
支持多种模型服务（OpenAI、DeepSeek、Qwen等）
"""

import json
import logging
import time
from typing import Dict, Any, Optional
from openai import OpenAI

logger = logging.getLogger("PolishService")


class OpenAIPolishService:
    """
    OpenAI润色服务类
    
    使用OpenAI Python库调用大语言模型API进行文本润色
    """
    
    def __init__(self, api_key: str, base_url: str = None, model: str = "gpt-3.5-turbo"):
        """
        初始化OpenAI润色服务
        
        Args:
            api_key: API密钥
            base_url: API基础URL，如果为None则使用OpenAI官方API
            model: 使用的模型名称
        """
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        
        # 创建OpenAI客户端
        if base_url:
            self.client = OpenAI(api_key=api_key, base_url=base_url)
        else:
            self.client = OpenAI(api_key=api_key)
    
    def polish_text(self, text: str, prompt_template: str, performance_config: dict = None) -> Optional[str]:
        """
        对文本进行润色处理

        Args:
            text: 需要润色的原始文本
            prompt_template: 提示词模板，包含{text}占位符
            performance_config: 性能配置参数

        Returns:
            Optional[str]: 润色后的文本，如果失败则返回None
        """
        # 使用默认性能配置
        if performance_config is None:
            performance_config = {
                "timeout": 15,
                "temperature": 0.3
            }

        try:
            # 构建完整的提示词
            prompt = prompt_template.format(text=text)

            # 构建消息列表
            messages = [
                {
                    "role": "system",
                    "content": "你是一位专业的文本编辑，擅长优化文本的流畅度和表达效果。请严格按照用户的要求进行文本润色。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]

            # 发送API请求 - 使用配置的性能参数
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=performance_config.get("temperature", 0.3),
                max_tokens=min(4000, len(text) * 2),  # 动态调整最大token数
                timeout=performance_config.get("timeout", 15)
            )

            # 提取润色后的文本
            if response.choices and len(response.choices) > 0:
                polished_text = response.choices[0].message.content.strip()
                logger.info("润色成功，文本长度: %d -> %d", len(text), len(polished_text))
                return polished_text
            else:
                logger.error("API响应为空")
                return None

        except Exception as e:
            logger.exception("润色处理异常: %s", str(e))
            return None

    def polish_text_with_retry(self, text: str, prompt_template: str, max_retries: int = 2, performance_config: dict = None) -> Optional[str]:
        """
        带重试机制的文本润色

        Args:
            text: 待润色文本
            prompt_template: 提示模板
            max_retries: 最大重试次数
            performance_config: 性能配置参数

        Returns:
            润色后的文本，失败时返回None
        """
        for attempt in range(max_retries + 1):
            try:
                result = self.polish_text(text, prompt_template, performance_config)
                if result:
                    return result
                logger.warning("润色返回空结果，尝试重试 %d/%d", attempt + 1, max_retries + 1)
            except Exception as e:
                if attempt < max_retries:
                    logger.warning("润色失败，%d秒后重试 %d/%d: %s",
                                 (attempt + 1) * 2, attempt + 1, max_retries + 1, str(e))
                    time.sleep((attempt + 1) * 2)  # 指数退避
                else:
                    logger.error("润色最终失败: %s", str(e))

        return None


class DeepSeekPolishService(OpenAIPolishService):
    """
    DeepSeek润色服务类

    继承自OpenAIPolishService，专门用于DeepSeek API
    """

    def __init__(self, api_key: str):
        """
        初始化DeepSeek润色服务

        Args:
            api_key: DeepSeek API密钥
        """
        super().__init__(
            api_key=api_key,
            base_url="https://api.deepseek.com",
            model="deepseek-chat"
        )


class QwenPolishService(OpenAIPolishService):
    """
    Qwen润色服务类

    继承自OpenAIPolishService，专门用于Qwen API
    """

    def __init__(self, api_key: str):
        """
        初始化Qwen润色服务

        Args:
            api_key: Qwen API密钥
        """
        super().__init__(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/api/v1",
            model="qwen-turbo"
        )


class PolishManager:
    """
    润色管理器类

    负责管理润色服务的配置和调用，支持多种服务类型
    """

    def __init__(self, polishing_config: Dict[str, Any], polished_dir: str):
        """
        初始化润色管理器

        Args:
            polishing_config: 润色配置字典
            polished_dir: 润色结果保存目录
        """
        self.config = polishing_config
        self.polished_dir = polished_dir
        self.enabled = polishing_config.get("enabled", False)

        # 如果启用润色功能，初始化服务
        if self.enabled:
            service_type = polishing_config.get("service", "openai")
            api_key = polishing_config.get("api_key")

            if not api_key:
                logger.error("润色功能已启用但缺少API密钥")
                self.enabled = False
            else:
                try:
                    # 根据服务类型创建对应的服务实例
                    if service_type == "openai":
                        model = polishing_config.get("model", "gpt-3.5-turbo")
                        self.service = OpenAIPolishService(api_key, model=model)
                    elif service_type == "deepseek":
                        self.service = DeepSeekPolishService(api_key)
                    elif service_type == "qwen":
                        self.service = QwenPolishService(api_key)
                    else:
                        # 自定义服务
                        base_url = polishing_config.get("base_url")
                        model = polishing_config.get("model", "gpt-3.5-turbo")
                        self.service = OpenAIPolishService(api_key, base_url, model)

                    logger.info("润色服务初始化成功: %s", service_type)
                except Exception as e:
                    logger.error("润色服务初始化失败: %s", str(e))
                    self.enabled = False

    def polish_text(self, text: str) -> Optional[str]:
        """
        对文本进行润色

        Args:
            text: 需要润色的文本

        Returns:
            Optional[str]: 润色后的文本，如果润色失败或未启用则返回原文本
        """
        if not self.enabled or not text.strip():
            return text

        try:
            prompt_template = self.config.get("prompt_template", "请润色以下文本：{text}")
            performance_config = self.config.get("performance", {})

            # 使用重试机制
            if hasattr(self.service, 'polish_text_with_retry'):
                max_retries = performance_config.get("max_retries", 2)
                polished_text = self.service.polish_text_with_retry(text, prompt_template, max_retries, performance_config)
            else:
                polished_text = self.service.polish_text(text, prompt_template, performance_config)
            
            if polished_text:
                return polished_text
            else:
                logger.warning("润色失败，返回原文本")
                return text
                
        except Exception as e:
            logger.exception("润色处理异常: %s", str(e))
            return text
    
    def save_polished_text(self, original_path: str, polished_text: str) -> Optional[str]:
        """
        保存润色后的文本到指定目录
        
        Args:
            original_path: 原始文件路径
            polished_text: 润色后的文本
            
        Returns:
            Optional[str]: 保存的文件路径，如果失败则返回None
        """
        try:
            import os
            
            # 确保润色目录存在
            os.makedirs(self.polished_dir, exist_ok=True)
            
            # 生成润色后的文件名
            import os.path
            base_name = os.path.basename(original_path)
            name_without_ext = os.path.splitext(base_name)[0]
            polished_filename = f"polished_{name_without_ext}.txt"
            polished_path = os.path.join(self.polished_dir, polished_filename)
            
            # 保存润色后的文本
            with open(polished_path, "w", encoding="utf-8") as f:
                f.write(polished_text)
            
            logger.info("润色结果已保存: %s", polished_path)
            return polished_path
            
        except Exception as e:
            logger.exception("保存润色结果失败: %s", str(e))
            return None
