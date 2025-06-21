"""
智能模型调度器
根据任务类型自动选择最适合的模型
"""

import asyncio
import time
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from datetime import datetime

from .enhanced_model_manager import (
    get_model_manager, ModelSelectionCriteria, TaskType, ModelCapability
)
from .model_providers import get_or_create_provider


@dataclass
class ModelRequest:
    """模型请求"""
    request_id: str
    task_type: TaskType
    content: Union[str, List[Dict[str, str]]]  # 文本或消息列表
    request_type: str = "generate"  # generate, chat, embedding
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    prefer_local: bool = False
    prefer_fast: bool = False
    prefer_quality: bool = False
    context_length_needed: int = 4096
    required_capabilities: List[ModelCapability] = None
    metadata: Dict[str, Any] = None


@dataclass
class ModelResponse:
    """模型响应"""
    request_id: str
    model_id: str
    content: str
    response_time: float
    success: bool
    error_message: str = ""
    metadata: Dict[str, Any] = None


class IntelligentModelDispatcher:
    """智能模型调度器"""
    
    def __init__(self):
        self.model_manager = get_model_manager()
        self.active_requests: Dict[str, ModelRequest] = {}
        self.request_history: List[Dict[str, Any]] = []
        self.task_performance_cache: Dict[str, Dict[str, float]] = {}
        
        # 任务类型检测规则
        self.task_detection_rules = {
            TaskType.BROWSING: [
                "screenshot", "browser", "webpage", "html", "css", "javascript",
                "visual", "image", "click", "scroll", "navigate"
            ],
            TaskType.WRITING: [
                "write", "article", "blog", "content", "essay", "story",
                "creative", "narrative", "draft", "compose"
            ],
            TaskType.CODING: [
                "code", "program", "function", "class", "algorithm", "debug",
                "python", "javascript", "java", "c++", "sql", "api"
            ],
            TaskType.ANALYSIS: [
                "analyze", "data", "statistics", "report", "chart", "graph",
                "trend", "pattern", "insight", "metrics"
            ],
            TaskType.REASONING: [
                "solve", "logic", "reasoning", "problem", "think", "deduce",
                "infer", "conclude", "explain", "understand"
            ],
            TaskType.CREATIVE: [
                "creative", "design", "art", "imagination", "innovative",
                "brainstorm", "idea", "concept", "original"
            ]
        }
    
    async def dispatch_request(self, request: ModelRequest) -> ModelResponse:
        """调度模型请求"""
        start_time = time.time()
        
        try:
            # 1. 自动检测任务类型（如果未指定）
            if not request.task_type:
                request.task_type = await self._detect_task_type(request.content)
            
            # 2. 选择最佳模型
            model_id = await self._select_optimal_model(request)
            
            if not model_id:
                return ModelResponse(
                    request_id=request.request_id,
                    model_id="",
                    content="",
                    response_time=time.time() - start_time,
                    success=False,
                    error_message="未找到合适的模型"
                )
            
            # 3. 执行请求
            response = await self._execute_request(request, model_id)
            
            # 4. 更新性能统计
            await self._update_performance_stats(request, response)
            
            # 5. 记录请求历史
            self._record_request_history(request, response)
            
            return response
            
        except Exception as e:
            return ModelResponse(
                request_id=request.request_id,
                model_id="",
                content="",
                response_time=time.time() - start_time,
                success=False,
                error_message=str(e)
            )
    
    async def _detect_task_type(self, content: Union[str, List[Dict[str, str]]]) -> TaskType:
        """自动检测任务类型"""
        # 将内容转换为文本
        if isinstance(content, list):
            text = " ".join([msg.get("content", "") for msg in content])
        else:
            text = content
        
        text_lower = text.lower()
        
        # 计算每种任务类型的匹配分数
        task_scores = {}
        for task_type, keywords in self.task_detection_rules.items():
            score = sum(1 for keyword in keywords if keyword in text_lower)
            if score > 0:
                task_scores[task_type] = score
        
        # 返回得分最高的任务类型
        if task_scores:
            best_task = max(task_scores, key=task_scores.get)
            print(f"🎯 检测到任务类型: {best_task.value} (匹配度: {task_scores[best_task]})")
            return best_task
        else:
            print("🎯 使用默认任务类型: CHAT")
            return TaskType.CHAT
    
    async def _select_optimal_model(self, request: ModelRequest) -> Optional[str]:
        """选择最优模型"""
        # 构建选择标准
        criteria = ModelSelectionCriteria(
            task_type=request.task_type,
            required_capabilities=request.required_capabilities or [],
            prefer_local=request.prefer_local,
            prefer_fast=request.prefer_fast,
            prefer_quality=request.prefer_quality,
            context_length_needed=request.context_length_needed
        )
        
        # 根据任务类型调整偏好
        criteria = self._adjust_criteria_by_task(criteria, request)
        
        # 选择模型
        model_id = await self.model_manager.select_best_model(criteria)
        
        if model_id:
            print(f"🤖 为任务 {request.task_type.value} 选择模型: {model_id}")
        
        return model_id
    
    def _adjust_criteria_by_task(self, criteria: ModelSelectionCriteria, request: ModelRequest) -> ModelSelectionCriteria:
        """根据任务类型调整选择标准"""
        
        if request.task_type == TaskType.BROWSING:
            # 浏览器任务需要视觉能力
            criteria.required_capabilities.append(ModelCapability.VISION)
            criteria.prefer_quality = True
            
        elif request.task_type == TaskType.WRITING:
            # 写作任务优先本地小模型
            criteria.prefer_local = True
            criteria.required_capabilities.append(ModelCapability.CREATIVE_WRITING)
            criteria.prefer_fast = True
            
        elif request.task_type == TaskType.CODING:
            # 代码任务需要高质量大模型
            criteria.required_capabilities.append(ModelCapability.CODE_GENERATION)
            criteria.prefer_quality = True
            criteria.min_quality_score = 7
            
        elif request.task_type == TaskType.ANALYSIS:
            # 分析任务需要数据分析能力
            criteria.required_capabilities.append(ModelCapability.DATA_ANALYSIS)
            criteria.prefer_quality = True
            
        elif request.task_type == TaskType.REASONING:
            # 推理任务需要推理能力
            criteria.required_capabilities.append(ModelCapability.REASONING)
            criteria.prefer_quality = True
            criteria.min_quality_score = 6
            
        elif request.task_type == TaskType.UTILITY:
            # 工具任务优先快速便宜的模型
            criteria.prefer_fast = True
            criteria.prefer_cheap = True
            
        return criteria
    
    async def _execute_request(self, request: ModelRequest, model_id: str) -> ModelResponse:
        """执行模型请求"""
        start_time = time.time()
        
        try:
            # 获取模型配置
            config = self.model_manager.get_model_config(model_id)
            if not config:
                raise Exception(f"模型配置不存在: {model_id}")
            
            # 获取或创建提供商
            provider = await get_or_create_provider(model_id, config)
            
            # 准备参数
            kwargs = {}
            if request.max_tokens:
                kwargs["max_tokens"] = request.max_tokens
            if request.temperature is not None:
                kwargs["temperature"] = request.temperature
            
            # 执行请求
            if request.request_type == "chat" and isinstance(request.content, list):
                result = await provider.chat(request.content, **kwargs)
            elif request.request_type == "embedding":
                if isinstance(request.content, str):
                    embedding = await provider.get_embedding(request.content)
                    result = str(embedding)  # 转换为字符串返回
                else:
                    raise Exception("嵌入请求需要字符串内容")
            else:
                # 默认生成请求
                if isinstance(request.content, list):
                    # 将消息转换为提示
                    prompt = self._messages_to_prompt(request.content)
                else:
                    prompt = request.content
                result = await provider.generate(prompt, **kwargs)
            
            response_time = time.time() - start_time
            
            return ModelResponse(
                request_id=request.request_id,
                model_id=model_id,
                content=result,
                response_time=response_time,
                success=True,
                metadata={"provider": config.provider.value}
            )
            
        except Exception as e:
            response_time = time.time() - start_time
            return ModelResponse(
                request_id=request.request_id,
                model_id=model_id,
                content="",
                response_time=response_time,
                success=False,
                error_message=str(e)
            )
    
    def _messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """将消息列表转换为提示"""
        prompt_parts = []
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            
            if role == "system":
                prompt_parts.append(f"System: {content}")
            elif role == "user":
                prompt_parts.append(f"Human: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")
        
        return "\n".join(prompt_parts) + "\nAssistant:"
    
    async def _update_performance_stats(self, request: ModelRequest, response: ModelResponse):
        """更新性能统计"""
        if response.model_id:
            await self.model_manager.update_model_performance(
                response.model_id,
                response.response_time,
                response.success
            )
            
            # 更新任务性能缓存
            task_key = f"{request.task_type.value}_{response.model_id}"
            if task_key not in self.task_performance_cache:
                self.task_performance_cache[task_key] = {"total_time": 0, "count": 0, "success_count": 0}
            
            cache = self.task_performance_cache[task_key]
            cache["total_time"] += response.response_time
            cache["count"] += 1
            if response.success:
                cache["success_count"] += 1
    
    def _record_request_history(self, request: ModelRequest, response: ModelResponse):
        """记录请求历史"""
        history_entry = {
            "timestamp": datetime.now(),
            "request_id": request.request_id,
            "task_type": request.task_type.value,
            "model_id": response.model_id,
            "response_time": response.response_time,
            "success": response.success,
            "content_length": len(str(request.content)),
            "response_length": len(response.content)
        }
        
        self.request_history.append(history_entry)
        
        # 保持最近1000条记录
        if len(self.request_history) > 1000:
            self.request_history = self.request_history[-1000:]
    
    def get_performance_report(self) -> Dict[str, Any]:
        """获取性能报告"""
        if not self.request_history:
            return {"status": "no_data"}
        
        # 总体统计
        total_requests = len(self.request_history)
        successful_requests = sum(1 for entry in self.request_history if entry["success"])
        avg_response_time = sum(entry["response_time"] for entry in self.request_history) / total_requests
        
        # 按任务类型统计
        task_stats = {}
        for entry in self.request_history:
            task_type = entry["task_type"]
            if task_type not in task_stats:
                task_stats[task_type] = {"count": 0, "success_count": 0, "total_time": 0}
            
            task_stats[task_type]["count"] += 1
            if entry["success"]:
                task_stats[task_type]["success_count"] += 1
            task_stats[task_type]["total_time"] += entry["response_time"]
        
        # 计算任务类型平均值
        for task_type, stats in task_stats.items():
            stats["success_rate"] = stats["success_count"] / stats["count"] if stats["count"] > 0 else 0
            stats["avg_response_time"] = stats["total_time"] / stats["count"] if stats["count"] > 0 else 0
        
        # 按模型统计
        model_stats = {}
        for entry in self.request_history:
            model_id = entry["model_id"]
            if model_id not in model_stats:
                model_stats[model_id] = {"count": 0, "success_count": 0, "total_time": 0}
            
            model_stats[model_id]["count"] += 1
            if entry["success"]:
                model_stats[model_id]["success_count"] += 1
            model_stats[model_id]["total_time"] += entry["response_time"]
        
        # 计算模型平均值
        for model_id, stats in model_stats.items():
            stats["success_rate"] = stats["success_count"] / stats["count"] if stats["count"] > 0 else 0
            stats["avg_response_time"] = stats["total_time"] / stats["count"] if stats["count"] > 0 else 0
        
        return {
            "summary": {
                "total_requests": total_requests,
                "successful_requests": successful_requests,
                "success_rate": successful_requests / total_requests if total_requests > 0 else 0,
                "avg_response_time": avg_response_time
            },
            "task_performance": task_stats,
            "model_performance": model_stats,
            "recent_requests": self.request_history[-10:]  # 最近10个请求
        }
    
    async def batch_dispatch(self, requests: List[ModelRequest]) -> List[ModelResponse]:
        """批量调度请求"""
        tasks = [self.dispatch_request(request) for request in requests]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常
        processed_responses = []
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                processed_responses.append(ModelResponse(
                    request_id=requests[i].request_id,
                    model_id="",
                    content="",
                    response_time=0,
                    success=False,
                    error_message=str(response)
                ))
            else:
                processed_responses.append(response)
        
        return processed_responses


# 全局调度器实例
_dispatcher = IntelligentModelDispatcher()


def get_model_dispatcher() -> IntelligentModelDispatcher:
    """获取模型调度器实例"""
    return _dispatcher


# 便捷函数
async def smart_generate(content: str, task_type: TaskType = None, **kwargs) -> str:
    """智能生成文本"""
    request = ModelRequest(
        request_id=f"gen_{int(time.time())}",
        task_type=task_type,
        content=content,
        request_type="generate",
        **kwargs
    )
    
    response = await _dispatcher.dispatch_request(request)
    if response.success:
        return response.content
    else:
        raise Exception(f"生成失败: {response.error_message}")


async def smart_chat(messages: List[Dict[str, str]], task_type: TaskType = None, **kwargs) -> str:
    """智能对话"""
    request = ModelRequest(
        request_id=f"chat_{int(time.time())}",
        task_type=task_type,
        content=messages,
        request_type="chat",
        **kwargs
    )
    
    response = await _dispatcher.dispatch_request(request)
    if response.success:
        return response.content
    else:
        raise Exception(f"对话失败: {response.error_message}")


async def smart_embedding(text: str, **kwargs) -> List[float]:
    """智能嵌入"""
    request = ModelRequest(
        request_id=f"emb_{int(time.time())}",
        task_type=TaskType.EMBEDDING,
        content=text,
        request_type="embedding",
        **kwargs
    )
    
    response = await _dispatcher.dispatch_request(request)
    if response.success:
        # 解析嵌入结果
        import ast
        return ast.literal_eval(response.content)
    else:
        raise Exception(f"嵌入失败: {response.error_message}")
