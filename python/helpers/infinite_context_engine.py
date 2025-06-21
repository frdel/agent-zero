"""
无限上下文引擎
集成 Infini-Attention 与零号行动的智能推理引擎
"""

import asyncio
import time
import torch
import torch.nn as nn
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import json
from datetime import datetime

from .infini_attention_core import (
    InfiniAttentionLayer, InfiniAttentionConfig, SegmentProcessor,
    MemoryCompressionStrategy
)

# 尝试导入现有的智能推理引擎
try:
    from architecture_enhancement.intelligence_framework import (
        get_reasoning_engine, get_context_engine, DecisionContext
    )
    INTELLIGENCE_FRAMEWORK_AVAILABLE = True
except ImportError:
    INTELLIGENCE_FRAMEWORK_AVAILABLE = False


class ContextProcessingMode(Enum):
    """上下文处理模式"""
    STANDARD = "standard"           # 标准模式，使用传统注意力
    INFINITE = "infinite"           # 无限模式，使用 Infini-Attention
    ADAPTIVE = "adaptive"           # 自适应模式，根据上下文长度自动选择
    HYBRID = "hybrid"              # 混合模式，同时使用两种方式


@dataclass
class ContextSegment:
    """上下文段"""
    segment_id: str
    content: str
    tokens: List[int]
    attention_mask: Optional[List[int]] = None
    timestamp: datetime = field(default_factory=datetime.now)
    importance_score: float = 1.0
    segment_type: str = "general"  # general, code, analysis, etc.
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InfiniteContextConfig:
    """无限上下文配置"""
    # Infini-Attention 配置
    infini_config: InfiniAttentionConfig = field(default_factory=InfiniAttentionConfig)
    
    # 上下文管理配置
    max_context_length: int = 1000000  # 最大上下文长度
    segment_length: int = 2048         # 段长度
    overlap_length: int = 256          # 段重叠长度
    
    # 智能切换配置
    adaptive_threshold: int = 8192     # 自适应切换阈值
    enable_smart_segmentation: bool = True
    enable_context_compression: bool = True
    
    # 性能配置
    enable_parallel_processing: bool = True
    max_concurrent_segments: int = 4
    memory_optimization: bool = True
    
    # 集成配置
    integrate_with_reasoning: bool = True
    enable_context_learning: bool = True
    context_importance_weighting: bool = True


class InfiniteContextEngine:
    """无限上下文引擎"""
    
    def __init__(self, config: InfiniteContextConfig):
        self.config = config
        self.infini_attention = InfiniAttentionLayer(config.infini_config)
        self.segment_processor = SegmentProcessor(config.segment_length)
        
        # 上下文管理
        self.context_segments: List[ContextSegment] = []
        self.context_cache: Dict[str, Any] = {}
        self.processing_stats = {
            "total_segments_processed": 0,
            "total_tokens_processed": 0,
            "memory_usage_mb": 0,
            "processing_time_ms": 0
        }
        
        # 智能推理引擎集成
        self.reasoning_engine = None
        self.context_understanding_engine = None
        if INTELLIGENCE_FRAMEWORK_AVAILABLE and config.integrate_with_reasoning:
            try:
                self.reasoning_engine = get_reasoning_engine()
                self.context_understanding_engine = get_context_engine()
            except Exception as e:
                print(f"⚠️ 智能推理引擎集成失败: {e}")
        
        # 模式状态
        self.current_mode = ContextProcessingMode.ADAPTIVE
        self.mode_switch_history = []
    
    async def process_context(
        self,
        context: Union[str, List[str], torch.Tensor],
        mode: Optional[ContextProcessingMode] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        处理上下文
        
        Args:
            context: 上下文内容
            mode: 处理模式
            metadata: 元数据
            
        Returns:
            处理结果
        """
        start_time = time.time()
        
        # 确定处理模式
        processing_mode = mode or self._determine_processing_mode(context)
        
        # 预处理上下文
        processed_context = await self._preprocess_context(context, metadata)
        
        # 根据模式处理
        if processing_mode == ContextProcessingMode.INFINITE:
            result = await self._process_with_infinite_attention(processed_context)
        elif processing_mode == ContextProcessingMode.STANDARD:
            result = await self._process_with_standard_attention(processed_context)
        elif processing_mode == ContextProcessingMode.ADAPTIVE:
            result = await self._process_with_adaptive_mode(processed_context)
        elif processing_mode == ContextProcessingMode.HYBRID:
            result = await self._process_with_hybrid_mode(processed_context)
        else:
            raise ValueError(f"不支持的处理模式: {processing_mode}")
        
        # 后处理和统计
        processing_time = (time.time() - start_time) * 1000
        self.processing_stats["processing_time_ms"] += processing_time
        
        # 集成智能推理
        if self.reasoning_engine and self.config.integrate_with_reasoning:
            result = await self._integrate_with_reasoning(result, processed_context)
        
        # 学习和优化
        if self.config.enable_context_learning:
            await self._learn_from_processing(processed_context, result, processing_mode)
        
        return {
            "result": result,
            "processing_mode": processing_mode.value,
            "processing_time_ms": processing_time,
            "context_stats": self._get_context_stats(),
            "memory_stats": self.infini_attention.get_memory_info()
        }
    
    def _determine_processing_mode(self, context: Union[str, List[str], torch.Tensor]) -> ContextProcessingMode:
        """确定处理模式"""
        # 估算上下文长度
        if isinstance(context, str):
            context_length = len(context.split())
        elif isinstance(context, list):
            context_length = sum(len(str(item).split()) for item in context)
        elif isinstance(context, torch.Tensor):
            context_length = context.size(-1)
        else:
            context_length = 0
        
        # 根据长度和配置决定模式
        if context_length > self.config.adaptive_threshold:
            return ContextProcessingMode.INFINITE
        else:
            return ContextProcessingMode.STANDARD
    
    async def _preprocess_context(
        self, 
        context: Union[str, List[str], torch.Tensor], 
        metadata: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """预处理上下文"""
        processed = {
            "raw_context": context,
            "metadata": metadata or {},
            "segments": [],
            "total_length": 0
        }
        
        # 转换为统一格式
        if isinstance(context, str):
            # 简单分词（实际应用中应使用专业分词器）
            tokens = context.split()
            processed["tokens"] = tokens
            processed["total_length"] = len(tokens)
        elif isinstance(context, list):
            # 处理多个上下文片段
            all_tokens = []
            for item in context:
                tokens = str(item).split()
                all_tokens.extend(tokens)
            processed["tokens"] = all_tokens
            processed["total_length"] = len(all_tokens)
        elif isinstance(context, torch.Tensor):
            # 直接使用张量
            processed["tensor"] = context
            processed["total_length"] = context.size(-1)
        
        # 智能分段
        if self.config.enable_smart_segmentation:
            processed["segments"] = await self._smart_segmentation(processed)
        else:
            processed["segments"] = self._simple_segmentation(processed)
        
        return processed
    
    async def _smart_segmentation(self, processed_context: Dict[str, Any]) -> List[ContextSegment]:
        """智能分段"""
        segments = []
        tokens = processed_context.get("tokens", [])
        
        if not tokens:
            return segments
        
        # 使用上下文理解引擎进行智能分段
        if self.context_understanding_engine:
            try:
                # 分析上下文结构
                analysis = await self.context_understanding_engine.analyze_context(
                    " ".join(tokens), "segmentation_session"
                )
                
                # 根据分析结果进行分段
                segment_boundaries = self._extract_segment_boundaries(analysis, len(tokens))
            except Exception as e:
                print(f"⚠️ 智能分段失败，使用简单分段: {e}")
                segment_boundaries = list(range(0, len(tokens), self.config.segment_length))
        else:
            segment_boundaries = list(range(0, len(tokens), self.config.segment_length))
        
        # 创建段
        for i, start_idx in enumerate(segment_boundaries):
            end_idx = min(start_idx + self.config.segment_length, len(tokens))
            
            segment = ContextSegment(
                segment_id=f"seg_{i}_{int(time.time())}",
                content=" ".join(tokens[start_idx:end_idx]),
                tokens=list(range(start_idx, end_idx)),  # 简化的token索引
                timestamp=datetime.now(),
                segment_type=self._classify_segment_type(tokens[start_idx:end_idx])
            )
            
            segments.append(segment)
        
        return segments
    
    def _simple_segmentation(self, processed_context: Dict[str, Any]) -> List[ContextSegment]:
        """简单分段"""
        segments = []
        tokens = processed_context.get("tokens", [])
        
        for i in range(0, len(tokens), self.config.segment_length):
            end_idx = min(i + self.config.segment_length, len(tokens))
            
            segment = ContextSegment(
                segment_id=f"simple_seg_{i}_{int(time.time())}",
                content=" ".join(tokens[i:end_idx]),
                tokens=list(range(i, end_idx)),
                timestamp=datetime.now()
            )
            
            segments.append(segment)
        
        return segments
    
    def _extract_segment_boundaries(self, analysis: Dict[str, Any], total_length: int) -> List[int]:
        """从分析结果中提取分段边界"""
        # 简化实现，实际应根据语义边界进行分段
        boundaries = []
        
        # 尝试从分析结果中获取语义边界
        semantic_boundaries = analysis.get("semantic_boundaries", [])
        
        if semantic_boundaries:
            for boundary in semantic_boundaries:
                if isinstance(boundary, (int, float)) and 0 <= boundary < total_length:
                    boundaries.append(int(boundary))
        
        # 如果没有语义边界，使用固定长度分段
        if not boundaries:
            boundaries = list(range(0, total_length, self.config.segment_length))
        
        return sorted(boundaries)
    
    def _classify_segment_type(self, tokens: List[str]) -> str:
        """分类段类型"""
        content = " ".join(tokens).lower()
        
        # 简单的关键词匹配分类
        if any(keyword in content for keyword in ["def ", "class ", "import ", "function"]):
            return "code"
        elif any(keyword in content for keyword in ["analyze", "data", "chart", "statistics"]):
            return "analysis"
        elif any(keyword in content for keyword in ["write", "article", "story", "content"]):
            return "writing"
        else:
            return "general"
    
    async def _process_with_infinite_attention(self, processed_context: Dict[str, Any]) -> Dict[str, Any]:
        """使用无限注意力处理"""
        segments = processed_context["segments"]
        segment_results = []
        
        # 重置记忆（如果需要）
        if len(segments) > 0:
            self.infini_attention.reset_memory()
        
        # 逐段处理
        for i, segment in enumerate(segments):
            is_last_segment = (i == len(segments) - 1)
            
            # 模拟将文本转换为张量（实际应使用tokenizer）
            # 这里使用简化的方法
            segment_tensor = self._text_to_tensor(segment.content)
            
            # 处理段
            segment_output, segment_stats = self.infini_attention.forward(
                segment_tensor,
                is_segment_boundary=is_last_segment
            )
            
            segment_results.append({
                "segment_id": segment.segment_id,
                "output": segment_output,
                "stats": segment_stats
            })
            
            # 更新统计
            self.processing_stats["total_segments_processed"] += 1
            self.processing_stats["total_tokens_processed"] += len(segment.tokens)
        
        return {
            "mode": "infinite_attention",
            "segment_results": segment_results,
            "total_segments": len(segments),
            "memory_info": self.infini_attention.get_memory_info()
        }
    
    async def _process_with_standard_attention(self, processed_context: Dict[str, Any]) -> Dict[str, Any]:
        """使用标准注意力处理"""
        # 简化实现，实际应调用标准的注意力机制
        return {
            "mode": "standard_attention",
            "result": "使用标准注意力处理的结果",
            "context_length": processed_context["total_length"]
        }
    
    async def _process_with_adaptive_mode(self, processed_context: Dict[str, Any]) -> Dict[str, Any]:
        """自适应模式处理"""
        context_length = processed_context["total_length"]
        
        if context_length > self.config.adaptive_threshold:
            return await self._process_with_infinite_attention(processed_context)
        else:
            return await self._process_with_standard_attention(processed_context)
    
    async def _process_with_hybrid_mode(self, processed_context: Dict[str, Any]) -> Dict[str, Any]:
        """混合模式处理"""
        # 同时使用两种方式处理，然后合并结果
        infinite_result = await self._process_with_infinite_attention(processed_context)
        standard_result = await self._process_with_standard_attention(processed_context)
        
        return {
            "mode": "hybrid",
            "infinite_result": infinite_result,
            "standard_result": standard_result,
            "combined_confidence": 0.8  # 简化的置信度计算
        }
    
    async def _integrate_with_reasoning(
        self, 
        result: Dict[str, Any], 
        processed_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """与智能推理引擎集成"""
        if not self.reasoning_engine:
            return result
        
        try:
            # 创建决策上下文
            decision_context = DecisionContext(
                task_description="上下文处理优化",
                available_tools=["infinite_attention", "standard_attention"],
                current_state={
                    "context_length": processed_context["total_length"],
                    "processing_mode": result.get("mode", "unknown"),
                    "memory_usage": self.infini_attention.get_memory_info()
                },
                objectives=["efficiency", "accuracy", "memory_optimization"]
            )
            
            # 执行推理
            reasoning_result = await self.reasoning_engine.reason(decision_context)
            
            # 将推理结果集成到处理结果中
            result["reasoning"] = {
                "decision": reasoning_result.chosen_action,
                "confidence": reasoning_result.confidence_score,
                "reasoning_chain": reasoning_result.reasoning_chain
            }
            
        except Exception as e:
            print(f"⚠️ 推理引擎集成失败: {e}")
        
        return result
    
    async def _learn_from_processing(
        self, 
        processed_context: Dict[str, Any], 
        result: Dict[str, Any], 
        mode: ContextProcessingMode
    ):
        """从处理过程中学习"""
        # 记录处理历史
        self.mode_switch_history.append({
            "timestamp": datetime.now(),
            "context_length": processed_context["total_length"],
            "mode": mode.value,
            "processing_time": result.get("processing_time_ms", 0),
            "success": True  # 简化的成功判断
        })
        
        # 保持历史记录在合理范围内
        if len(self.mode_switch_history) > 1000:
            self.mode_switch_history = self.mode_switch_history[-500:]
    
    def _text_to_tensor(self, text: str) -> torch.Tensor:
        """将文本转换为张量（简化实现）"""
        # 实际应用中应使用专业的tokenizer
        words = text.split()
        # 简化的词汇表映射
        vocab = {word: i for i, word in enumerate(set(words))}
        token_ids = [vocab.get(word, 0) for word in words]
        
        # 填充到固定长度
        max_length = min(len(token_ids), self.config.segment_length)
        if len(token_ids) < max_length:
            token_ids.extend([0] * (max_length - len(token_ids)))
        else:
            token_ids = token_ids[:max_length]
        
        # 转换为张量并添加batch维度
        tensor = torch.tensor(token_ids).unsqueeze(0)  # [1, seq_len]
        
        # 简化的嵌入（实际应使用embedding层）
        hidden_size = self.config.infini_config.hidden_size
        embedded = torch.randn(1, tensor.size(1), hidden_size)  # [1, seq_len, hidden_size]
        
        return embedded
    
    def _get_context_stats(self) -> Dict[str, Any]:
        """获取上下文统计信息"""
        return {
            "total_segments": len(self.context_segments),
            "processing_stats": self.processing_stats.copy(),
            "current_mode": self.current_mode.value,
            "mode_switch_count": len(self.mode_switch_history)
        }
    
    def reset_context(self):
        """重置上下文"""
        self.context_segments.clear()
        self.context_cache.clear()
        self.infini_attention.reset_memory()
        self.processing_stats = {
            "total_segments_processed": 0,
            "total_tokens_processed": 0,
            "memory_usage_mb": 0,
            "processing_time_ms": 0
        }
    
    def get_performance_report(self) -> Dict[str, Any]:
        """获取性能报告"""
        return {
            "processing_stats": self.processing_stats,
            "memory_stats": self.infini_attention.get_memory_info(),
            "context_stats": self._get_context_stats(),
            "mode_history": self.mode_switch_history[-10:],  # 最近10次模式切换
            "efficiency_metrics": self._calculate_efficiency_metrics()
        }
    
    def _calculate_efficiency_metrics(self) -> Dict[str, float]:
        """计算效率指标"""
        if not self.mode_switch_history:
            return {}
        
        recent_history = self.mode_switch_history[-100:]  # 最近100次
        
        avg_processing_time = sum(h.get("processing_time", 0) for h in recent_history) / len(recent_history)
        infinite_mode_ratio = sum(1 for h in recent_history if h.get("mode") == "infinite") / len(recent_history)
        
        return {
            "avg_processing_time_ms": avg_processing_time,
            "infinite_mode_usage_ratio": infinite_mode_ratio,
            "total_tokens_per_second": self.processing_stats["total_tokens_processed"] / max(self.processing_stats["processing_time_ms"] / 1000, 1),
            "memory_efficiency_score": 1.0 - min(self.processing_stats["memory_usage_mb"] / 1000, 1.0)
        }


# 全局实例
_infinite_context_engine = None


def get_infinite_context_engine(config: Optional[InfiniteContextConfig] = None) -> InfiniteContextEngine:
    """获取无限上下文引擎实例"""
    global _infinite_context_engine
    
    if _infinite_context_engine is None:
        if config is None:
            config = InfiniteContextConfig()
        _infinite_context_engine = InfiniteContextEngine(config)
    
    return _infinite_context_engine


def reset_infinite_context_engine():
    """重置无限上下文引擎"""
    global _infinite_context_engine
    if _infinite_context_engine:
        _infinite_context_engine.reset_context()
        _infinite_context_engine = None
