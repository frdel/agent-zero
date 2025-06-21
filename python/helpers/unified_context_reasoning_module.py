"""
统一上下文-推理-调用管理模块
整合无限上下文、智能推理和模型调用优化
"""

import asyncio
import time
import json
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

# 导入核心组件
from .infinite_context_engine import (
    get_infinite_context_engine, InfiniteContextConfig, ContextProcessingMode
)
from .intelligent_model_dispatcher import (
    get_model_dispatcher, ModelRequest, TaskType, smart_generate, smart_chat
)

# 尝试导入智能推理引擎
try:
    from architecture_enhancement.intelligence_framework import (
        get_reasoning_engine, get_context_engine, DecisionContext
    )
    INTELLIGENCE_FRAMEWORK_AVAILABLE = True
except ImportError:
    INTELLIGENCE_FRAMEWORK_AVAILABLE = False


class ProcessingStrategy(Enum):
    """处理策略"""
    CONTEXT_FIRST = "context_first"        # 上下文优先
    REASONING_FIRST = "reasoning_first"     # 推理优先
    PARALLEL = "parallel"                   # 并行处理
    ADAPTIVE = "adaptive"                   # 自适应策略


class OptimizationLevel(Enum):
    """优化级别"""
    BASIC = "basic"                         # 基础优化
    STANDARD = "standard"                   # 标准优化
    AGGRESSIVE = "aggressive"               # 激进优化
    CUSTOM = "custom"                       # 自定义优化


@dataclass
class UnifiedProcessingConfig:
    """统一处理配置"""
    # 上下文配置
    infinite_context_config: InfiniteContextConfig = field(default_factory=InfiniteContextConfig)
    enable_infinite_context: bool = True
    context_length_threshold: int = 8192
    
    # 推理配置
    enable_intelligent_reasoning: bool = True
    reasoning_depth: int = 3
    reasoning_timeout_seconds: float = 30.0
    
    # 模型调用配置
    enable_smart_model_selection: bool = True
    model_selection_strategy: str = "quality_first"
    max_api_calls_per_request: int = 5
    
    # 处理策略
    processing_strategy: ProcessingStrategy = ProcessingStrategy.ADAPTIVE
    optimization_level: OptimizationLevel = OptimizationLevel.STANDARD
    
    # 性能配置
    enable_caching: bool = True
    cache_ttl_seconds: int = 3600
    enable_parallel_processing: bool = True
    max_concurrent_tasks: int = 3
    
    # 监控配置
    enable_performance_monitoring: bool = True
    enable_cost_tracking: bool = True
    enable_quality_assessment: bool = True


@dataclass
class ProcessingRequest:
    """处理请求"""
    request_id: str
    content: Union[str, List[str]]
    task_type: Optional[TaskType] = None
    context_mode: Optional[ContextProcessingMode] = None
    processing_strategy: Optional[ProcessingStrategy] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    priority: int = 5  # 1-10，优先级
    timeout_seconds: float = 120.0
    
    # 特殊要求
    require_reasoning: bool = False
    require_infinite_context: bool = False
    max_context_length: Optional[int] = None
    preferred_models: List[str] = field(default_factory=list)


@dataclass
class ProcessingResult:
    """处理结果"""
    request_id: str
    success: bool
    result: Any
    processing_time_ms: float
    
    # 详细信息
    context_info: Dict[str, Any] = field(default_factory=dict)
    reasoning_info: Dict[str, Any] = field(default_factory=dict)
    model_info: Dict[str, Any] = field(default_factory=dict)
    
    # 性能指标
    api_calls_made: int = 0
    tokens_processed: int = 0
    cost_estimate: float = 0.0
    quality_score: float = 0.0
    
    # 错误信息
    error_message: str = ""
    warnings: List[str] = field(default_factory=list)


class UnifiedContextReasoningModule:
    """统一上下文推理模块"""
    
    def __init__(self, config: UnifiedProcessingConfig):
        self.config = config
        
        # 初始化核心组件
        self.infinite_context_engine = None
        self.model_dispatcher = None
        self.reasoning_engine = None
        self.context_understanding_engine = None
        
        # 初始化组件
        self._initialize_components()
        
        # 缓存和状态管理
        self.request_cache: Dict[str, ProcessingResult] = {}
        self.processing_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "total_processing_time_ms": 0,
            "total_api_calls": 0,
            "total_cost": 0.0
        }
        
        # 性能监控
        self.performance_history: List[Dict[str, Any]] = []
        self.optimization_suggestions: List[str] = []
    
    def _initialize_components(self):
        """初始化组件"""
        try:
            # 初始化无限上下文引擎
            if self.config.enable_infinite_context:
                self.infinite_context_engine = get_infinite_context_engine(
                    self.config.infinite_context_config
                )
            
            # 初始化模型调度器
            if self.config.enable_smart_model_selection:
                self.model_dispatcher = get_model_dispatcher()
            
            # 初始化智能推理引擎
            if self.config.enable_intelligent_reasoning and INTELLIGENCE_FRAMEWORK_AVAILABLE:
                self.reasoning_engine = get_reasoning_engine()
                self.context_understanding_engine = get_context_engine()
            
            print("✅ 统一上下文推理模块初始化完成")
            
        except Exception as e:
            print(f"⚠️ 组件初始化部分失败: {e}")
    
    async def process_request(self, request: ProcessingRequest) -> ProcessingResult:
        """处理请求"""
        start_time = time.time()
        
        try:
            # 检查缓存
            if self.config.enable_caching:
                cached_result = self._check_cache(request)
                if cached_result:
                    return cached_result
            
            # 预处理请求
            processed_request = await self._preprocess_request(request)
            
            # 根据策略选择处理方式
            if processed_request.processing_strategy == ProcessingStrategy.CONTEXT_FIRST:
                result = await self._process_context_first(processed_request)
            elif processed_request.processing_strategy == ProcessingStrategy.REASONING_FIRST:
                result = await self._process_reasoning_first(processed_request)
            elif processed_request.processing_strategy == ProcessingStrategy.PARALLEL:
                result = await self._process_parallel(processed_request)
            else:  # ADAPTIVE
                result = await self._process_adaptive(processed_request)
            
            # 后处理
            final_result = await self._postprocess_result(result, processed_request)
            
            # 计算处理时间
            processing_time = (time.time() - start_time) * 1000
            final_result.processing_time_ms = processing_time
            
            # 更新统计
            self._update_stats(final_result)
            
            # 缓存结果
            if self.config.enable_caching and final_result.success:
                self._cache_result(request, final_result)
            
            return final_result
            
        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            return ProcessingResult(
                request_id=request.request_id,
                success=False,
                result=None,
                processing_time_ms=processing_time,
                error_message=str(e)
            )
    
    async def _preprocess_request(self, request: ProcessingRequest) -> ProcessingRequest:
        """预处理请求"""
        # 自动检测任务类型
        if not request.task_type:
            request.task_type = self._detect_task_type(request.content)
        
        # 自动选择处理策略
        if not request.processing_strategy:
            request.processing_strategy = self._select_processing_strategy(request)
        
        # 自动选择上下文模式
        if not request.context_mode:
            request.context_mode = self._select_context_mode(request)
        
        return request
    
    def _detect_task_type(self, content: Union[str, List[str]]) -> TaskType:
        """检测任务类型"""
        if isinstance(content, list):
            text = " ".join(str(item) for item in content)
        else:
            text = str(content)
        
        text_lower = text.lower()
        
        # 简单的关键词匹配
        if any(word in text_lower for word in ["screenshot", "browser", "webpage", "visual"]):
            return TaskType.BROWSING
        elif any(word in text_lower for word in ["write", "article", "creative", "story"]):
            return TaskType.WRITING
        elif any(word in text_lower for word in ["code", "program", "function", "debug"]):
            return TaskType.CODING
        elif any(word in text_lower for word in ["analyze", "data", "statistics", "report"]):
            return TaskType.ANALYSIS
        elif any(word in text_lower for word in ["solve", "logic", "reasoning", "problem"]):
            return TaskType.REASONING
        else:
            return TaskType.CHAT
    
    def _select_processing_strategy(self, request: ProcessingRequest) -> ProcessingStrategy:
        """选择处理策略"""
        # 根据任务类型和内容长度选择策略
        content_length = len(str(request.content))
        
        if request.require_reasoning and content_length > self.config.context_length_threshold:
            return ProcessingStrategy.PARALLEL
        elif request.require_reasoning:
            return ProcessingStrategy.REASONING_FIRST
        elif content_length > self.config.context_length_threshold:
            return ProcessingStrategy.CONTEXT_FIRST
        else:
            return ProcessingStrategy.ADAPTIVE
    
    def _select_context_mode(self, request: ProcessingRequest) -> ContextProcessingMode:
        """选择上下文模式"""
        content_length = len(str(request.content))
        
        if request.require_infinite_context or content_length > self.config.context_length_threshold:
            return ContextProcessingMode.INFINITE
        else:
            return ContextProcessingMode.ADAPTIVE
    
    async def _process_context_first(self, request: ProcessingRequest) -> ProcessingResult:
        """上下文优先处理"""
        result = ProcessingResult(
            request_id=request.request_id,
            success=True,
            result=None
        )
        
        # 1. 处理上下文
        if self.infinite_context_engine:
            context_result = await self.infinite_context_engine.process_context(
                request.content,
                mode=request.context_mode,
                metadata=request.metadata
            )
            result.context_info = context_result
        
        # 2. 基于上下文结果进行推理
        if self.reasoning_engine and request.require_reasoning:
            reasoning_result = await self._perform_reasoning(request, result.context_info)
            result.reasoning_info = reasoning_result
        
        # 3. 模型调用
        model_result = await self._perform_model_call(request, result.context_info, result.reasoning_info)
        result.model_info = model_result
        result.result = model_result.get("response", "")
        
        return result
    
    async def _process_reasoning_first(self, request: ProcessingRequest) -> ProcessingResult:
        """推理优先处理"""
        result = ProcessingResult(
            request_id=request.request_id,
            success=True,
            result=None
        )
        
        # 1. 先进行推理
        if self.reasoning_engine:
            reasoning_result = await self._perform_reasoning(request)
            result.reasoning_info = reasoning_result
        
        # 2. 基于推理结果处理上下文
        if self.infinite_context_engine:
            context_result = await self.infinite_context_engine.process_context(
                request.content,
                mode=request.context_mode,
                metadata={**request.metadata, "reasoning_guidance": result.reasoning_info}
            )
            result.context_info = context_result
        
        # 3. 模型调用
        model_result = await self._perform_model_call(request, result.context_info, result.reasoning_info)
        result.model_info = model_result
        result.result = model_result.get("response", "")
        
        return result
    
    async def _process_parallel(self, request: ProcessingRequest) -> ProcessingResult:
        """并行处理"""
        result = ProcessingResult(
            request_id=request.request_id,
            success=True,
            result=None
        )
        
        # 并行执行上下文处理和推理
        tasks = []
        
        if self.infinite_context_engine:
            context_task = self.infinite_context_engine.process_context(
                request.content,
                mode=request.context_mode,
                metadata=request.metadata
            )
            tasks.append(("context", context_task))
        
        if self.reasoning_engine and request.require_reasoning:
            reasoning_task = self._perform_reasoning(request)
            tasks.append(("reasoning", reasoning_task))
        
        # 等待并行任务完成
        if tasks:
            task_results = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)
            
            for i, (task_type, _) in enumerate(tasks):
                task_result = task_results[i]
                if not isinstance(task_result, Exception):
                    if task_type == "context":
                        result.context_info = task_result
                    elif task_type == "reasoning":
                        result.reasoning_info = task_result
        
        # 模型调用
        model_result = await self._perform_model_call(request, result.context_info, result.reasoning_info)
        result.model_info = model_result
        result.result = model_result.get("response", "")
        
        return result
    
    async def _process_adaptive(self, request: ProcessingRequest) -> ProcessingResult:
        """自适应处理"""
        # 根据请求特征动态选择最佳策略
        content_length = len(str(request.content))
        complexity_score = self._calculate_complexity_score(request)
        
        if complexity_score > 0.8 and content_length > self.config.context_length_threshold:
            return await self._process_parallel(request)
        elif complexity_score > 0.6:
            return await self._process_reasoning_first(request)
        elif content_length > self.config.context_length_threshold:
            return await self._process_context_first(request)
        else:
            # 简单请求，直接模型调用
            return await self._process_simple(request)
    
    def _calculate_complexity_score(self, request: ProcessingRequest) -> float:
        """计算请求复杂度分数"""
        score = 0.0
        
        # 基于任务类型
        if request.task_type in [TaskType.REASONING, TaskType.ANALYSIS]:
            score += 0.3
        elif request.task_type in [TaskType.CODING]:
            score += 0.2
        
        # 基于内容长度
        content_length = len(str(request.content))
        if content_length > 10000:
            score += 0.3
        elif content_length > 5000:
            score += 0.2
        elif content_length > 1000:
            score += 0.1
        
        # 基于特殊要求
        if request.require_reasoning:
            score += 0.2
        if request.require_infinite_context:
            score += 0.2
        
        return min(score, 1.0)
    
    async def _process_simple(self, request: ProcessingRequest) -> ProcessingResult:
        """简单处理（直接模型调用）"""
        result = ProcessingResult(
            request_id=request.request_id,
            success=True,
            result=None
        )
        
        # 直接进行模型调用
        model_result = await self._perform_model_call(request)
        result.model_info = model_result
        result.result = model_result.get("response", "")
        
        return result
    
    async def _perform_reasoning(
        self, 
        request: ProcessingRequest, 
        context_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """执行推理"""
        if not self.reasoning_engine:
            return {"error": "推理引擎不可用"}
        
        try:
            # 创建决策上下文
            decision_context = DecisionContext(
                task_description=str(request.content)[:500],  # 限制长度
                available_tools=["context_processing", "model_calling"],
                current_state={
                    "task_type": request.task_type.value if request.task_type else "unknown",
                    "content_length": len(str(request.content)),
                    "context_info": context_info
                },
                objectives=["accuracy", "efficiency", "cost_optimization"]
            )
            
            # 执行推理
            reasoning_result = await self.reasoning_engine.reason(decision_context)
            
            return {
                "decision": reasoning_result.chosen_action,
                "confidence": reasoning_result.confidence_score,
                "reasoning_chain": reasoning_result.reasoning_chain,
                "success": True
            }
            
        except Exception as e:
            return {"error": str(e), "success": False}
    
    async def _perform_model_call(
        self,
        request: ProcessingRequest,
        context_info: Optional[Dict[str, Any]] = None,
        reasoning_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """执行模型调用"""
        if not self.model_dispatcher:
            # 回退到简单的文本生成
            return {
                "response": f"处理了请求: {str(request.content)[:100]}...",
                "model_used": "fallback",
                "success": True
            }
        
        try:
            # 构建模型请求
            model_request = ModelRequest(
                request_id=f"unified_{request.request_id}",
                task_type=request.task_type or TaskType.CHAT,
                content=str(request.content),
                prefer_quality=True,
                metadata={
                    "context_info": context_info,
                    "reasoning_info": reasoning_info,
                    "original_request": request.metadata
                }
            )
            
            # 调用模型
            model_response = await self.model_dispatcher.dispatch_request(model_request)
            
            return {
                "response": model_response.content if model_response.success else "",
                "model_used": model_response.model_id,
                "response_time": model_response.response_time,
                "success": model_response.success,
                "error": model_response.error_message if not model_response.success else None
            }
            
        except Exception as e:
            return {"error": str(e), "success": False}
    
    async def _postprocess_result(
        self, 
        result: ProcessingResult, 
        request: ProcessingRequest
    ) -> ProcessingResult:
        """后处理结果"""
        # 计算质量分数
        result.quality_score = self._calculate_quality_score(result, request)
        
        # 估算成本
        result.cost_estimate = self._estimate_cost(result)
        
        # 统计token数量
        result.tokens_processed = self._count_tokens(request.content, result.result)
        
        # 统计API调用次数
        result.api_calls_made = self._count_api_calls(result)
        
        return result
    
    def _calculate_quality_score(self, result: ProcessingResult, request: ProcessingRequest) -> float:
        """计算质量分数"""
        # 简化的质量评估
        score = 0.5  # 基础分数
        
        if result.success:
            score += 0.3
        
        if result.result and len(str(result.result)) > 10:
            score += 0.2
        
        return min(score, 1.0)
    
    def _estimate_cost(self, result: ProcessingResult) -> float:
        """估算成本"""
        # 简化的成本估算
        base_cost = 0.001  # 基础成本
        
        if result.context_info:
            base_cost += 0.002
        
        if result.reasoning_info:
            base_cost += 0.001
        
        if result.api_calls_made > 0:
            base_cost += result.api_calls_made * 0.01
        
        return base_cost
    
    def _count_tokens(self, input_content: Any, output_content: Any) -> int:
        """统计token数量"""
        # 简化的token计数
        input_tokens = len(str(input_content).split())
        output_tokens = len(str(output_content).split()) if output_content else 0
        return input_tokens + output_tokens
    
    def _count_api_calls(self, result: ProcessingResult) -> int:
        """统计API调用次数"""
        calls = 0
        
        if result.context_info:
            calls += 1
        
        if result.reasoning_info:
            calls += 1
        
        if result.model_info:
            calls += 1
        
        return calls
    
    def _check_cache(self, request: ProcessingRequest) -> Optional[ProcessingResult]:
        """检查缓存"""
        # 简化的缓存检查
        cache_key = f"{request.task_type}_{hash(str(request.content))}"
        return self.request_cache.get(cache_key)
    
    def _cache_result(self, request: ProcessingRequest, result: ProcessingResult):
        """缓存结果"""
        cache_key = f"{request.task_type}_{hash(str(request.content))}"
        self.request_cache[cache_key] = result
        
        # 限制缓存大小
        if len(self.request_cache) > 1000:
            # 删除最旧的一半
            keys_to_delete = list(self.request_cache.keys())[:500]
            for key in keys_to_delete:
                del self.request_cache[key]
    
    def _update_stats(self, result: ProcessingResult):
        """更新统计信息"""
        self.processing_stats["total_requests"] += 1
        if result.success:
            self.processing_stats["successful_requests"] += 1
        
        self.processing_stats["total_processing_time_ms"] += result.processing_time_ms
        self.processing_stats["total_api_calls"] += result.api_calls_made
        self.processing_stats["total_cost"] += result.cost_estimate
        
        # 记录性能历史
        self.performance_history.append({
            "timestamp": datetime.now(),
            "request_id": result.request_id,
            "success": result.success,
            "processing_time_ms": result.processing_time_ms,
            "quality_score": result.quality_score,
            "cost": result.cost_estimate
        })
        
        # 保持历史记录在合理范围内
        if len(self.performance_history) > 1000:
            self.performance_history = self.performance_history[-500:]
    
    def get_performance_report(self) -> Dict[str, Any]:
        """获取性能报告"""
        if not self.performance_history:
            return {"status": "no_data"}
        
        recent_history = self.performance_history[-100:]  # 最近100个请求
        
        avg_processing_time = sum(h["processing_time_ms"] for h in recent_history) / len(recent_history)
        success_rate = sum(1 for h in recent_history if h["success"]) / len(recent_history)
        avg_quality = sum(h["quality_score"] for h in recent_history) / len(recent_history)
        avg_cost = sum(h["cost"] for h in recent_history) / len(recent_history)
        
        return {
            "overall_stats": self.processing_stats,
            "recent_performance": {
                "avg_processing_time_ms": avg_processing_time,
                "success_rate": success_rate,
                "avg_quality_score": avg_quality,
                "avg_cost": avg_cost
            },
            "optimization_suggestions": self.optimization_suggestions,
            "cache_stats": {
                "cache_size": len(self.request_cache),
                "cache_hit_rate": 0.0  # 简化实现
            }
        }
    
    def reset_stats(self):
        """重置统计信息"""
        self.processing_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "total_processing_time_ms": 0,
            "total_api_calls": 0,
            "total_cost": 0.0
        }
        self.performance_history.clear()
        self.request_cache.clear()


# 全局实例
_unified_module = None


def get_unified_context_reasoning_module(
    config: Optional[UnifiedProcessingConfig] = None
) -> UnifiedContextReasoningModule:
    """获取统一上下文推理模块实例"""
    global _unified_module
    
    if _unified_module is None:
        if config is None:
            config = UnifiedProcessingConfig()
        _unified_module = UnifiedContextReasoningModule(config)
    
    return _unified_module


# 便捷函数
async def unified_process(
    content: Union[str, List[str]],
    task_type: Optional[TaskType] = None,
    require_reasoning: bool = False,
    require_infinite_context: bool = False,
    **kwargs
) -> ProcessingResult:
    """统一处理函数"""
    module = get_unified_context_reasoning_module()
    
    request = ProcessingRequest(
        request_id=f"unified_{int(time.time())}",
        content=content,
        task_type=task_type,
        require_reasoning=require_reasoning,
        require_infinite_context=require_infinite_context,
        metadata=kwargs
    )
    
    return await module.process_request(request)
