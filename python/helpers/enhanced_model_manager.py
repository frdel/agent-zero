"""
增强的模型管理器
支持多种模型提供商和智能模型选择
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import json
import time
from datetime import datetime


class ModelProvider(Enum):
    """模型提供商枚举"""
    OPENAI = "openai"
    OPENAI_COMPATIBLE = "openai_compatible"  # 兼容OpenAI API的云服务
    VLLM = "vllm"                           # 本地vLLM
    LLAMACPP = "llamacpp"                   # 本地LlamaCpp
    ANTHROPIC = "anthropic"
    HUGGINGFACE = "huggingface"
    AZURE = "azure"
    GOOGLE = "google"


class ModelCapability(Enum):
    """模型能力枚举"""
    TEXT_GENERATION = "text_generation"
    CODE_GENERATION = "code_generation"
    VISION = "vision"
    MULTIMODAL = "multimodal"
    EMBEDDING = "embedding"
    CHAT = "chat"
    COMPLETION = "completion"
    FUNCTION_CALLING = "function_calling"
    REASONING = "reasoning"
    CREATIVE_WRITING = "creative_writing"
    DATA_ANALYSIS = "data_analysis"


class TaskType(Enum):
    """任务类型枚举"""
    BROWSING = "browsing"                   # 浏览器任务
    WRITING = "writing"                     # 文章写作
    CODING = "coding"                       # 代码编写
    ANALYSIS = "analysis"                   # 数据分析
    REASONING = "reasoning"                 # 推理任务
    CREATIVE = "creative"                   # 创意任务
    CHAT = "chat"                          # 对话任务
    EMBEDDING = "embedding"                # 嵌入任务
    UTILITY = "utility"                    # 工具任务


@dataclass
class ModelConfig:
    """增强的模型配置"""
    provider: ModelProvider
    name: str
    endpoint: Optional[str] = None
    api_key: Optional[str] = None
    
    # 基础配置
    ctx_length: int = 4096
    max_tokens: Optional[int] = None
    temperature: float = 0.7
    
    # 能力配置
    capabilities: List[ModelCapability] = field(default_factory=list)
    vision: bool = False
    function_calling: bool = False
    
    # 性能配置
    speed_score: int = 5  # 1-10，速度评分
    quality_score: int = 5  # 1-10，质量评分
    cost_score: int = 5  # 1-10，成本评分（越高越便宜）
    
    # 限制配置
    limit_requests: int = 0
    limit_input: int = 0
    limit_output: int = 0
    
    # 本地模型特定配置
    model_path: Optional[str] = None
    gpu_layers: int = 0
    threads: int = 4
    
    # 其他配置
    kwargs: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    priority: int = 5  # 1-10，优先级
    
    # 使用统计
    usage_count: int = 0
    success_rate: float = 1.0
    avg_response_time: float = 0.0


@dataclass
class ModelSelectionCriteria:
    """模型选择标准"""
    task_type: TaskType
    required_capabilities: List[ModelCapability] = field(default_factory=list)
    prefer_local: bool = False
    prefer_fast: bool = False
    prefer_quality: bool = False
    prefer_cheap: bool = False
    max_cost: Optional[float] = None
    max_response_time: Optional[float] = None
    min_quality_score: int = 3
    context_length_needed: int = 4096


class IModelProvider(ABC):
    """模型提供商接口"""
    
    @abstractmethod
    async def initialize(self, config: ModelConfig) -> bool:
        """初始化模型"""
        pass
    
    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> str:
        """生成文本"""
        pass
    
    @abstractmethod
    async def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """对话生成"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """检查模型是否可用"""
        pass
    
    @abstractmethod
    async def get_embedding(self, text: str) -> List[float]:
        """获取文本嵌入"""
        pass


class EnhancedModelManager:
    """增强的模型管理器"""
    
    def __init__(self):
        self.models: Dict[str, ModelConfig] = {}
        self.providers: Dict[str, IModelProvider] = {}
        self.task_model_mapping: Dict[TaskType, List[str]] = {}
        self.model_performance_history: Dict[str, List[Dict[str, Any]]] = {}
        self._initialize_default_mappings()
    
    def _initialize_default_mappings(self):
        """初始化默认的任务-模型映射"""
        self.task_model_mapping = {
            TaskType.BROWSING: [],      # 多模态模型优先
            TaskType.WRITING: [],       # 小型本地模型优先
            TaskType.CODING: [],        # 大型代码模型优先
            TaskType.ANALYSIS: [],      # 分析能力强的模型
            TaskType.REASONING: [],     # 推理能力强的模型
            TaskType.CREATIVE: [],      # 创意能力强的模型
            TaskType.CHAT: [],          # 对话模型
            TaskType.EMBEDDING: [],     # 嵌入模型
            TaskType.UTILITY: []        # 工具模型
        }
    
    def register_model(self, model_id: str, config: ModelConfig) -> bool:
        """注册模型"""
        try:
            self.models[model_id] = config
            
            # 根据模型能力更新任务映射
            self._update_task_mappings(model_id, config)
            
            print(f"✅ 已注册模型: {model_id} ({config.provider.value})")
            return True
        except Exception as e:
            print(f"❌ 注册模型失败 {model_id}: {e}")
            return False
    
    def _update_task_mappings(self, model_id: str, config: ModelConfig):
        """更新任务映射"""
        # 浏览器任务 - 优先多模态模型
        if ModelCapability.VISION in config.capabilities or config.vision:
            self.task_model_mapping[TaskType.BROWSING].append(model_id)
        
        # 写作任务 - 优先本地小模型
        if (config.provider in [ModelProvider.VLLM, ModelProvider.LLAMACPP] and
            ModelCapability.CREATIVE_WRITING in config.capabilities):
            self.task_model_mapping[TaskType.WRITING].insert(0, model_id)
        elif ModelCapability.TEXT_GENERATION in config.capabilities:
            self.task_model_mapping[TaskType.WRITING].append(model_id)
        
        # 代码任务 - 优先大型代码模型
        if ModelCapability.CODE_GENERATION in config.capabilities:
            if config.quality_score >= 8:  # 高质量模型优先
                self.task_model_mapping[TaskType.CODING].insert(0, model_id)
            else:
                self.task_model_mapping[TaskType.CODING].append(model_id)
        
        # 分析任务
        if ModelCapability.DATA_ANALYSIS in config.capabilities:
            self.task_model_mapping[TaskType.ANALYSIS].append(model_id)
        
        # 推理任务
        if ModelCapability.REASONING in config.capabilities:
            self.task_model_mapping[TaskType.REASONING].append(model_id)
        
        # 创意任务
        if ModelCapability.CREATIVE_WRITING in config.capabilities:
            self.task_model_mapping[TaskType.CREATIVE].append(model_id)
        
        # 对话任务
        if ModelCapability.CHAT in config.capabilities:
            self.task_model_mapping[TaskType.CHAT].append(model_id)
        
        # 嵌入任务
        if ModelCapability.EMBEDDING in config.capabilities:
            self.task_model_mapping[TaskType.EMBEDDING].append(model_id)
        
        # 工具任务 - 优先快速、便宜的模型
        if config.speed_score >= 7 and config.cost_score >= 7:
            self.task_model_mapping[TaskType.UTILITY].insert(0, model_id)
        else:
            self.task_model_mapping[TaskType.UTILITY].append(model_id)
    
    async def select_best_model(self, criteria: ModelSelectionCriteria) -> Optional[str]:
        """选择最佳模型"""
        candidates = self._get_candidate_models(criteria)
        
        if not candidates:
            print(f"⚠️ 未找到符合条件的模型: {criteria.task_type}")
            return None
        
        # 评分和排序
        scored_candidates = []
        for model_id in candidates:
            score = await self._calculate_model_score(model_id, criteria)
            scored_candidates.append((model_id, score))
        
        # 按分数排序
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        
        best_model = scored_candidates[0][0]
        print(f"🎯 为任务 {criteria.task_type.value} 选择模型: {best_model}")
        
        return best_model
    
    def _get_candidate_models(self, criteria: ModelSelectionCriteria) -> List[str]:
        """获取候选模型"""
        # 从任务映射开始
        candidates = self.task_model_mapping.get(criteria.task_type, []).copy()
        
        # 如果任务映射为空，从所有模型中筛选
        if not candidates:
            candidates = list(self.models.keys())
        
        # 过滤条件
        filtered_candidates = []
        for model_id in candidates:
            config = self.models[model_id]
            
            # 检查是否启用
            if not config.enabled:
                continue
            
            # 检查必需能力
            if criteria.required_capabilities:
                if not all(cap in config.capabilities for cap in criteria.required_capabilities):
                    continue
            
            # 检查本地偏好
            if criteria.prefer_local:
                if config.provider not in [ModelProvider.VLLM, ModelProvider.LLAMACPP]:
                    continue
            
            # 检查上下文长度
            if config.ctx_length < criteria.context_length_needed:
                continue
            
            # 检查质量要求
            if config.quality_score < criteria.min_quality_score:
                continue
            
            filtered_candidates.append(model_id)
        
        return filtered_candidates
    
    async def _calculate_model_score(self, model_id: str, criteria: ModelSelectionCriteria) -> float:
        """计算模型评分"""
        config = self.models[model_id]
        score = 0.0
        
        # 基础分数
        score += config.priority * 10
        
        # 性能偏好
        if criteria.prefer_fast:
            score += config.speed_score * 15
        
        if criteria.prefer_quality:
            score += config.quality_score * 15
        
        if criteria.prefer_cheap:
            score += config.cost_score * 15
        
        # 本地偏好
        if criteria.prefer_local and config.provider in [ModelProvider.VLLM, ModelProvider.LLAMACPP]:
            score += 20
        
        # 成功率加成
        score += config.success_rate * 10
        
        # 响应时间惩罚
        if config.avg_response_time > 0:
            if criteria.max_response_time and config.avg_response_time > criteria.max_response_time:
                score -= 30
            else:
                score -= config.avg_response_time * 2
        
        # 能力匹配加成
        capability_match = len(set(criteria.required_capabilities) & set(config.capabilities))
        score += capability_match * 5
        
        return score
    
    async def update_model_performance(self, model_id: str, response_time: float, success: bool):
        """更新模型性能统计"""
        if model_id not in self.models:
            return
        
        config = self.models[model_id]
        
        # 更新使用次数
        config.usage_count += 1
        
        # 更新成功率
        total_attempts = config.usage_count
        previous_successes = (total_attempts - 1) * config.success_rate
        new_successes = previous_successes + (1 if success else 0)
        config.success_rate = new_successes / total_attempts
        
        # 更新平均响应时间
        if config.avg_response_time == 0:
            config.avg_response_time = response_time
        else:
            config.avg_response_time = (config.avg_response_time * 0.8 + response_time * 0.2)
        
        # 记录性能历史
        if model_id not in self.model_performance_history:
            self.model_performance_history[model_id] = []
        
        self.model_performance_history[model_id].append({
            "timestamp": datetime.now(),
            "response_time": response_time,
            "success": success
        })
        
        # 保持最近100条记录
        if len(self.model_performance_history[model_id]) > 100:
            self.model_performance_history[model_id] = self.model_performance_history[model_id][-100:]
    
    def get_model_config(self, model_id: str) -> Optional[ModelConfig]:
        """获取模型配置"""
        return self.models.get(model_id)
    
    def list_models_by_task(self, task_type: TaskType) -> List[str]:
        """按任务类型列出模型"""
        return self.task_model_mapping.get(task_type, [])
    
    def get_model_statistics(self) -> Dict[str, Any]:
        """获取模型统计信息"""
        stats = {
            "total_models": len(self.models),
            "enabled_models": len([m for m in self.models.values() if m.enabled]),
            "provider_distribution": {},
            "capability_distribution": {},
            "performance_summary": {}
        }
        
        # 提供商分布
        for config in self.models.values():
            provider = config.provider.value
            stats["provider_distribution"][provider] = stats["provider_distribution"].get(provider, 0) + 1
        
        # 能力分布
        for config in self.models.values():
            for capability in config.capabilities:
                cap_name = capability.value
                stats["capability_distribution"][cap_name] = stats["capability_distribution"].get(cap_name, 0) + 1
        
        # 性能摘要
        for model_id, config in self.models.items():
            stats["performance_summary"][model_id] = {
                "usage_count": config.usage_count,
                "success_rate": f"{config.success_rate:.2f}",
                "avg_response_time": f"{config.avg_response_time:.2f}s",
                "quality_score": config.quality_score,
                "speed_score": config.speed_score
            }
        
        return stats
    
    def export_config(self) -> Dict[str, Any]:
        """导出配置"""
        config_data = {
            "models": {},
            "task_mappings": {}
        }
        
        # 导出模型配置
        for model_id, config in self.models.items():
            config_data["models"][model_id] = {
                "provider": config.provider.value,
                "name": config.name,
                "endpoint": config.endpoint,
                "capabilities": [cap.value for cap in config.capabilities],
                "vision": config.vision,
                "function_calling": config.function_calling,
                "speed_score": config.speed_score,
                "quality_score": config.quality_score,
                "cost_score": config.cost_score,
                "priority": config.priority,
                "enabled": config.enabled,
                "kwargs": config.kwargs
            }
        
        # 导出任务映射
        for task_type, model_list in self.task_model_mapping.items():
            config_data["task_mappings"][task_type.value] = model_list
        
        return config_data
    
    def import_config(self, config_data: Dict[str, Any]) -> bool:
        """导入配置"""
        try:
            # 导入模型配置
            for model_id, model_data in config_data.get("models", {}).items():
                config = ModelConfig(
                    provider=ModelProvider(model_data["provider"]),
                    name=model_data["name"],
                    endpoint=model_data.get("endpoint"),
                    capabilities=[ModelCapability(cap) for cap in model_data.get("capabilities", [])],
                    vision=model_data.get("vision", False),
                    function_calling=model_data.get("function_calling", False),
                    speed_score=model_data.get("speed_score", 5),
                    quality_score=model_data.get("quality_score", 5),
                    cost_score=model_data.get("cost_score", 5),
                    priority=model_data.get("priority", 5),
                    enabled=model_data.get("enabled", True),
                    kwargs=model_data.get("kwargs", {})
                )
                self.register_model(model_id, config)
            
            # 导入任务映射
            for task_name, model_list in config_data.get("task_mappings", {}).items():
                task_type = TaskType(task_name)
                self.task_model_mapping[task_type] = model_list
            
            return True
        except Exception as e:
            print(f"❌ 导入配置失败: {e}")
            return False


# 全局模型管理器实例
_model_manager = EnhancedModelManager()


def get_model_manager() -> EnhancedModelManager:
    """获取模型管理器实例"""
    return _model_manager
