"""
模型提供商实现
支持OpenAI兼容、vLLM、LlamaCpp等多种提供商
"""

import asyncio
import aiohttp
import json
import time
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod

from .enhanced_model_manager import IModelProvider, ModelConfig, ModelProvider


class OpenAICompatibleProvider(IModelProvider):
    """OpenAI兼容的模型提供商"""
    
    def __init__(self):
        self.config: Optional[ModelConfig] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.initialized = False
    
    async def initialize(self, config: ModelConfig) -> bool:
        """初始化模型"""
        try:
            self.config = config
            
            # 创建HTTP会话
            timeout = aiohttp.ClientTimeout(total=60)
            self.session = aiohttp.ClientSession(timeout=timeout)
            
            # 验证连接
            if config.endpoint:
                await self._test_connection()
            
            self.initialized = True
            print(f"✅ OpenAI兼容模型初始化成功: {config.name}")
            return True
            
        except Exception as e:
            print(f"❌ OpenAI兼容模型初始化失败: {e}")
            return False
    
    async def _test_connection(self) -> bool:
        """测试连接"""
        try:
            headers = {
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json"
            }
            
            # 尝试获取模型列表
            async with self.session.get(
                f"{self.config.endpoint}/v1/models",
                headers=headers
            ) as response:
                if response.status == 200:
                    return True
                else:
                    print(f"⚠️ 连接测试失败，状态码: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"⚠️ 连接测试异常: {e}")
            return False
    
    async def generate(self, prompt: str, **kwargs) -> str:
        """生成文本"""
        if not self.initialized or not self.session:
            raise Exception("模型未初始化")
        
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.config.name,
            "prompt": prompt,
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens or 1000),
            "temperature": kwargs.get("temperature", self.config.temperature),
            "stream": False
        }
        
        # 添加其他参数
        data.update(self.config.kwargs)
        data.update(kwargs)
        
        try:
            async with self.session.post(
                f"{self.config.endpoint}/v1/completions",
                headers=headers,
                json=data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result["choices"][0]["text"]
                else:
                    error_text = await response.text()
                    raise Exception(f"API调用失败: {response.status} - {error_text}")
                    
        except Exception as e:
            raise Exception(f"生成文本失败: {e}")
    
    async def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """对话生成"""
        if not self.initialized or not self.session:
            raise Exception("模型未初始化")
        
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.config.name,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens or 1000),
            "temperature": kwargs.get("temperature", self.config.temperature),
            "stream": False
        }
        
        # 添加其他参数
        data.update(self.config.kwargs)
        data.update(kwargs)
        
        try:
            async with self.session.post(
                f"{self.config.endpoint}/v1/chat/completions",
                headers=headers,
                json=data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result["choices"][0]["message"]["content"]
                else:
                    error_text = await response.text()
                    raise Exception(f"API调用失败: {response.status} - {error_text}")
                    
        except Exception as e:
            raise Exception(f"对话生成失败: {e}")
    
    def is_available(self) -> bool:
        """检查模型是否可用"""
        return self.initialized and self.session is not None
    
    async def get_embedding(self, text: str) -> List[float]:
        """获取文本嵌入"""
        if not self.initialized or not self.session:
            raise Exception("模型未初始化")
        
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.config.name,
            "input": text
        }
        
        try:
            async with self.session.post(
                f"{self.config.endpoint}/v1/embeddings",
                headers=headers,
                json=data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result["data"][0]["embedding"]
                else:
                    error_text = await response.text()
                    raise Exception(f"API调用失败: {response.status} - {error_text}")
                    
        except Exception as e:
            raise Exception(f"获取嵌入失败: {e}")
    
    async def cleanup(self):
        """清理资源"""
        if self.session:
            await self.session.close()
            self.session = None
        self.initialized = False


class VLLMProvider(IModelProvider):
    """vLLM本地模型提供商"""
    
    def __init__(self):
        self.config: Optional[ModelConfig] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.initialized = False
    
    async def initialize(self, config: ModelConfig) -> bool:
        """初始化vLLM模型"""
        try:
            self.config = config
            
            # 创建HTTP会话
            timeout = aiohttp.ClientTimeout(total=120)  # vLLM可能需要更长时间
            self.session = aiohttp.ClientSession(timeout=timeout)
            
            # 默认端口
            if not config.endpoint:
                config.endpoint = "http://localhost:8000"
            
            # 测试连接
            await self._test_vllm_connection()
            
            self.initialized = True
            print(f"✅ vLLM模型初始化成功: {config.name}")
            return True
            
        except Exception as e:
            print(f"❌ vLLM模型初始化失败: {e}")
            return False
    
    async def _test_vllm_connection(self) -> bool:
        """测试vLLM连接"""
        try:
            async with self.session.get(f"{self.config.endpoint}/health") as response:
                return response.status == 200
        except Exception:
            # 尝试模型列表端点
            try:
                async with self.session.get(f"{self.config.endpoint}/v1/models") as response:
                    return response.status == 200
            except Exception as e:
                print(f"⚠️ vLLM连接测试失败: {e}")
                return False
    
    async def generate(self, prompt: str, **kwargs) -> str:
        """生成文本"""
        if not self.initialized or not self.session:
            raise Exception("vLLM模型未初始化")
        
        data = {
            "model": self.config.name,
            "prompt": prompt,
            "max_tokens": kwargs.get("max_tokens", 1000),
            "temperature": kwargs.get("temperature", self.config.temperature),
            "stream": False
        }
        
        # 添加vLLM特定参数
        data.update(self.config.kwargs)
        data.update(kwargs)
        
        try:
            async with self.session.post(
                f"{self.config.endpoint}/v1/completions",
                json=data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result["choices"][0]["text"]
                else:
                    error_text = await response.text()
                    raise Exception(f"vLLM调用失败: {response.status} - {error_text}")
                    
        except Exception as e:
            raise Exception(f"vLLM生成失败: {e}")
    
    async def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """对话生成"""
        if not self.initialized or not self.session:
            raise Exception("vLLM模型未初始化")
        
        data = {
            "model": self.config.name,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", 1000),
            "temperature": kwargs.get("temperature", self.config.temperature),
            "stream": False
        }
        
        data.update(self.config.kwargs)
        data.update(kwargs)
        
        try:
            async with self.session.post(
                f"{self.config.endpoint}/v1/chat/completions",
                json=data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result["choices"][0]["message"]["content"]
                else:
                    error_text = await response.text()
                    raise Exception(f"vLLM调用失败: {response.status} - {error_text}")
                    
        except Exception as e:
            raise Exception(f"vLLM对话失败: {e}")
    
    def is_available(self) -> bool:
        """检查模型是否可用"""
        return self.initialized and self.session is not None
    
    async def get_embedding(self, text: str) -> List[float]:
        """获取文本嵌入（如果支持）"""
        # vLLM主要用于生成，嵌入功能有限
        raise NotImplementedError("vLLM暂不支持嵌入功能")
    
    async def cleanup(self):
        """清理资源"""
        if self.session:
            await self.session.close()
            self.session = None
        self.initialized = False


class LlamaCppProvider(IModelProvider):
    """LlamaCpp本地模型提供商"""
    
    def __init__(self):
        self.config: Optional[ModelConfig] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.initialized = False
    
    async def initialize(self, config: ModelConfig) -> bool:
        """初始化LlamaCpp模型"""
        try:
            self.config = config
            
            # 创建HTTP会话
            timeout = aiohttp.ClientTimeout(total=180)  # LlamaCpp可能需要更长时间
            self.session = aiohttp.ClientSession(timeout=timeout)
            
            # 默认端口
            if not config.endpoint:
                config.endpoint = "http://localhost:8080"
            
            # 测试连接
            await self._test_llamacpp_connection()
            
            self.initialized = True
            print(f"✅ LlamaCpp模型初始化成功: {config.name}")
            return True
            
        except Exception as e:
            print(f"❌ LlamaCpp模型初始化失败: {e}")
            return False
    
    async def _test_llamacpp_connection(self) -> bool:
        """测试LlamaCpp连接"""
        try:
            async with self.session.get(f"{self.config.endpoint}/health") as response:
                return response.status == 200
        except Exception:
            # 尝试生成端点
            try:
                test_data = {"prompt": "test", "n_predict": 1}
                async with self.session.post(
                    f"{self.config.endpoint}/completion",
                    json=test_data
                ) as response:
                    return response.status == 200
            except Exception as e:
                print(f"⚠️ LlamaCpp连接测试失败: {e}")
                return False
    
    async def generate(self, prompt: str, **kwargs) -> str:
        """生成文本"""
        if not self.initialized or not self.session:
            raise Exception("LlamaCpp模型未初始化")
        
        data = {
            "prompt": prompt,
            "n_predict": kwargs.get("max_tokens", 1000),
            "temperature": kwargs.get("temperature", self.config.temperature),
            "stream": False
        }
        
        # 添加LlamaCpp特定参数
        data.update({
            "top_k": kwargs.get("top_k", 40),
            "top_p": kwargs.get("top_p", 0.9),
            "repeat_penalty": kwargs.get("repeat_penalty", 1.1),
            "n_threads": self.config.threads
        })
        
        data.update(self.config.kwargs)
        data.update(kwargs)
        
        try:
            async with self.session.post(
                f"{self.config.endpoint}/completion",
                json=data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result["content"]
                else:
                    error_text = await response.text()
                    raise Exception(f"LlamaCpp调用失败: {response.status} - {error_text}")
                    
        except Exception as e:
            raise Exception(f"LlamaCpp生成失败: {e}")
    
    async def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """对话生成"""
        # 将消息转换为单个提示
        prompt = self._messages_to_prompt(messages)
        return await self.generate(prompt, **kwargs)
    
    def _messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """将消息列表转换为提示"""
        prompt_parts = []
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            
            if role == "system":
                prompt_parts.append(f"System: {content}")
            elif role == "user":
                prompt_parts.append(f"User: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")
        
        prompt_parts.append("Assistant:")
        return "\n".join(prompt_parts)
    
    def is_available(self) -> bool:
        """检查模型是否可用"""
        return self.initialized and self.session is not None
    
    async def get_embedding(self, text: str) -> List[float]:
        """获取文本嵌入"""
        if not self.initialized or not self.session:
            raise Exception("LlamaCpp模型未初始化")
        
        data = {
            "content": text
        }
        
        try:
            async with self.session.post(
                f"{self.config.endpoint}/embedding",
                json=data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result["embedding"]
                else:
                    error_text = await response.text()
                    raise Exception(f"LlamaCpp嵌入调用失败: {response.status} - {error_text}")
                    
        except Exception as e:
            raise Exception(f"LlamaCpp嵌入失败: {e}")
    
    async def cleanup(self):
        """清理资源"""
        if self.session:
            await self.session.close()
            self.session = None
        self.initialized = False


class ModelProviderFactory:
    """模型提供商工厂"""
    
    @staticmethod
    def create_provider(provider_type: ModelProvider) -> IModelProvider:
        """创建模型提供商实例"""
        if provider_type in [ModelProvider.OPENAI, ModelProvider.OPENAI_COMPATIBLE, 
                           ModelProvider.ANTHROPIC, ModelProvider.AZURE]:
            return OpenAICompatibleProvider()
        elif provider_type == ModelProvider.VLLM:
            return VLLMProvider()
        elif provider_type == ModelProvider.LLAMACPP:
            return LlamaCppProvider()
        else:
            raise ValueError(f"不支持的模型提供商: {provider_type}")


# 全局提供商注册表
_provider_registry: Dict[str, IModelProvider] = {}


async def get_or_create_provider(model_id: str, config: ModelConfig) -> IModelProvider:
    """获取或创建模型提供商"""
    if model_id in _provider_registry:
        return _provider_registry[model_id]
    
    # 创建新的提供商
    provider = ModelProviderFactory.create_provider(config.provider)
    
    # 初始化
    if await provider.initialize(config):
        _provider_registry[model_id] = provider
        return provider
    else:
        raise Exception(f"模型提供商初始化失败: {model_id}")


async def cleanup_all_providers():
    """清理所有提供商"""
    for provider in _provider_registry.values():
        try:
            await provider.cleanup()
        except Exception as e:
            print(f"清理提供商时出错: {e}")
    
    _provider_registry.clear()
