"""
Infini-Attention 核心实现
移植自 https://github.com/jlamprou/Infini-Attention
针对零号行动项目进行优化和集成
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import math
from typing import Optional, Tuple, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import numpy as np


class MemoryCompressionStrategy(Enum):
    """记忆压缩策略"""
    LINEAR_ATTENTION = "linear_attention"  # 线性注意力压缩
    DELTA_RULE = "delta_rule"             # 增量规则压缩
    ADAPTIVE = "adaptive"                 # 自适应压缩


@dataclass
class InfiniAttentionConfig:
    """Infini-Attention 配置"""
    # 基础配置
    hidden_size: int = 768
    num_attention_heads: int = 12
    head_dim: int = 64
    segment_length: int = 2048
    
    # 记忆配置
    memory_compression_strategy: MemoryCompressionStrategy = MemoryCompressionStrategy.LINEAR_ATTENTION
    memory_update_rate: float = 0.1
    memory_decay_factor: float = 0.95
    
    # 性能配置
    enable_memory_cache: bool = True
    max_memory_segments: int = 1000
    memory_cleanup_threshold: int = 10000
    
    # 调试配置
    enable_memory_visualization: bool = False
    memory_stats_interval: int = 100


class CompressiveMemory(nn.Module):
    """压缩记忆模块"""
    
    def __init__(self, config: InfiniAttentionConfig):
        super().__init__()
        self.config = config
        self.num_heads = config.num_attention_heads
        self.head_dim = config.head_dim
        
        # 记忆矩阵 M 和归一化向量 z
        self.register_buffer(
            "M", 
            torch.zeros(self.num_heads, self.head_dim, self.head_dim),
            persistent=False
        )
        self.register_buffer(
            "z", 
            torch.zeros(self.num_heads, self.head_dim),
            persistent=False
        )
        
        # 可学习的混合参数
        self.beta = nn.Parameter(torch.randn(1))
        
        # 记忆统计
        self.memory_usage_count = 0
        self.memory_update_count = 0
        self.memory_stats = {}
    
    def retrieve_from_memory(self, Q: torch.Tensor) -> torch.Tensor:
        """从压缩记忆中检索信息
        
        Args:
            Q: 查询张量 [batch, num_heads, seq_len, head_dim]
            
        Returns:
            检索到的记忆信息 [batch, num_heads, seq_len, head_dim]
        """
        # 使用线性注意力机制检索记忆
        # A_mem = (Q * φ(K)) * M / (Q * φ(K) * z + ε)
        
        # 应用激活函数 φ(x) = ELU(x) + 1
        Q_activated = F.elu(Q) + 1  # [batch, num_heads, seq_len, head_dim]
        
        # 计算分子: Q_activated @ M
        numerator = torch.matmul(Q_activated, self.M)  # [batch, num_heads, seq_len, head_dim]
        
        # 计算分母: Q_activated @ z + ε
        denominator = torch.matmul(Q_activated, self.z.unsqueeze(-1)) + 1e-8  # [batch, num_heads, seq_len, 1]
        
        # 检索结果
        A_mem = numerator / denominator  # [batch, num_heads, seq_len, head_dim]
        
        self.memory_usage_count += 1
        return A_mem
    
    def update_memory(self, K: torch.Tensor, V: torch.Tensor, use_delta_rule: bool = False) -> None:
        """更新压缩记忆
        
        Args:
            K: 键张量 [batch, num_heads, seq_len, head_dim]
            V: 值张量 [batch, num_heads, seq_len, head_dim]
            use_delta_rule: 是否使用增量规则
        """
        # 应用激活函数
        K_activated = F.elu(K) + 1  # [batch, num_heads, seq_len, head_dim]
        
        if use_delta_rule:
            # 增量规则: 只更新预测错误的部分
            # 首先检索当前的值
            V_retrieved = self.retrieve_from_memory(K)
            
            # 计算预测误差
            V_error = V - V_retrieved
            
            # 更新记忆矩阵
            delta_M = torch.matmul(K_activated.transpose(-2, -1), V_error)
        else:
            # 标准线性注意力更新
            delta_M = torch.matmul(K_activated.transpose(-2, -1), V)
        
        # 批量平均并更新记忆矩阵
        delta_M_avg = delta_M.mean(dim=0)  # [num_heads, head_dim, head_dim]
        self.M.data += delta_M_avg * self.config.memory_update_rate
        
        # 更新归一化向量
        delta_z = K_activated.sum(dim=-2).mean(dim=0)  # [num_heads, head_dim]
        self.z.data += delta_z * self.config.memory_update_rate
        
        # 应用记忆衰减
        self.M.data *= self.config.memory_decay_factor
        self.z.data *= self.config.memory_decay_factor
        
        self.memory_update_count += 1
        
        # 定期清理记忆以防止数值不稳定
        if self.memory_update_count % self.config.memory_cleanup_threshold == 0:
            self._cleanup_memory()
    
    def _cleanup_memory(self):
        """清理记忆以防止数值不稳定"""
        # 检查并修复数值异常
        if torch.isnan(self.M).any() or torch.isinf(self.M).any():
            print("⚠️ 检测到记忆矩阵数值异常，重置记忆")
            self.reset_memory()
            return
        
        # 归一化记忆矩阵
        M_norm = torch.norm(self.M, dim=(-2, -1), keepdim=True)
        if M_norm.max() > 100:  # 防止记忆矩阵过大
            self.M.data /= (M_norm / 10).clamp(min=1.0)
        
        # 归一化 z 向量
        z_norm = torch.norm(self.z, dim=-1, keepdim=True)
        if z_norm.max() > 100:
            self.z.data /= (z_norm / 10).clamp(min=1.0)
    
    def reset_memory(self):
        """重置记忆"""
        self.M.zero_()
        self.z.zero_()
        self.memory_usage_count = 0
        self.memory_update_count = 0
        self.memory_stats.clear()
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """获取记忆统计信息"""
        return {
            "memory_usage_count": self.memory_usage_count,
            "memory_update_count": self.memory_update_count,
            "memory_matrix_norm": torch.norm(self.M).item(),
            "z_vector_norm": torch.norm(self.z).item(),
            "beta_value": torch.sigmoid(self.beta).item(),
            "memory_size_mb": (self.M.numel() + self.z.numel()) * 4 / (1024 * 1024)
        }


class InfiniAttentionLayer(nn.Module):
    """Infini-Attention 层"""
    
    def __init__(self, config: InfiniAttentionConfig):
        super().__init__()
        self.config = config
        self.hidden_size = config.hidden_size
        self.num_heads = config.num_attention_heads
        self.head_dim = config.head_dim
        self.segment_length = config.segment_length
        
        # 线性投影层
        self.q_proj = nn.Linear(self.hidden_size, self.num_heads * self.head_dim, bias=True)
        self.k_proj = nn.Linear(self.hidden_size, self.num_heads * self.head_dim, bias=True)
        self.v_proj = nn.Linear(self.hidden_size, self.num_heads * self.head_dim, bias=True)
        self.o_proj = nn.Linear(self.num_heads * self.head_dim, self.hidden_size, bias=False)
        
        # 压缩记忆
        self.compressive_memory = CompressiveMemory(config)
        
        # 位置编码（简化版）
        self.register_buffer(
            "position_bias",
            self._create_position_bias(config.segment_length),
            persistent=False
        )
    
    def _create_position_bias(self, max_length: int) -> torch.Tensor:
        """创建位置偏置"""
        position = torch.arange(max_length).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, self.head_dim, 2) * 
                           -(math.log(10000.0) / self.head_dim))
        
        pos_emb = torch.zeros(max_length, self.head_dim)
        pos_emb[:, 0::2] = torch.sin(position * div_term)
        pos_emb[:, 1::2] = torch.cos(position * div_term)
        
        return pos_emb
    
    def forward(
        self,
        hidden_states: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
        is_segment_boundary: bool = False,
        **kwargs
    ) -> Tuple[torch.Tensor, Dict[str, Any]]:
        """
        前向传播
        
        Args:
            hidden_states: 输入张量 [batch, seq_len, hidden_size]
            attention_mask: 注意力掩码 [batch, seq_len]
            is_segment_boundary: 是否为段边界
            
        Returns:
            输出张量和统计信息
        """
        batch_size, seq_len, _ = hidden_states.size()
        
        # 线性投影
        Q = self.q_proj(hidden_states)  # [batch, seq_len, num_heads * head_dim]
        K = self.k_proj(hidden_states)
        V = self.v_proj(hidden_states)
        
        # 重塑为多头格式
        Q = Q.view(batch_size, seq_len, self.num_heads, self.head_dim).transpose(1, 2)
        K = K.view(batch_size, seq_len, self.num_heads, self.head_dim).transpose(1, 2)
        V = V.view(batch_size, seq_len, self.num_heads, self.head_dim).transpose(1, 2)
        
        # 添加位置编码
        if seq_len <= self.position_bias.size(0):
            pos_bias = self.position_bias[:seq_len].unsqueeze(0).unsqueeze(0)  # [1, 1, seq_len, head_dim]
            Q = Q + pos_bias
            K = K + pos_bias
        
        # 1. 从压缩记忆中检索信息
        memory_output = self.compressive_memory.retrieve_from_memory(Q)
        
        # 2. 计算局部注意力（当前段内的注意力）
        local_output = self._compute_local_attention(Q, K, V, attention_mask)
        
        # 3. 混合记忆注意力和局部注意力
        combined_output = self._combine_attention_outputs(local_output, memory_output)
        
        # 4. 更新压缩记忆
        self.compressive_memory.update_memory(
            K, V, 
            use_delta_rule=(self.config.memory_compression_strategy == MemoryCompressionStrategy.DELTA_RULE)
        )
        
        # 5. 输出投影
        combined_output = combined_output.transpose(1, 2).contiguous()
        combined_output = combined_output.view(batch_size, seq_len, self.hidden_size)
        output = self.o_proj(combined_output)
        
        # 6. 如果是段边界，可选择性重置记忆
        if is_segment_boundary and self.config.max_memory_segments > 0:
            if self.compressive_memory.memory_update_count > self.config.max_memory_segments:
                self.compressive_memory.reset_memory()
        
        # 统计信息
        stats = {
            "memory_stats": self.compressive_memory.get_memory_stats(),
            "sequence_length": seq_len,
            "is_segment_boundary": is_segment_boundary
        }
        
        return output, stats
    
    def _compute_local_attention(
        self, 
        Q: torch.Tensor, 
        K: torch.Tensor, 
        V: torch.Tensor, 
        attention_mask: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """计算局部注意力"""
        # 标准的缩放点积注意力
        scale = math.sqrt(self.head_dim)
        scores = torch.matmul(Q, K.transpose(-2, -1)) / scale
        
        # 应用注意力掩码
        if attention_mask is not None:
            # 扩展掩码维度以匹配注意力分数
            mask = attention_mask.unsqueeze(1).unsqueeze(2)  # [batch, 1, 1, seq_len]
            scores = scores.masked_fill(mask == 0, float('-inf'))
        
        # 应用因果掩码（确保只能看到之前的位置）
        seq_len = Q.size(-2)
        causal_mask = torch.triu(torch.ones(seq_len, seq_len, device=Q.device), diagonal=1).bool()
        scores = scores.masked_fill(causal_mask, float('-inf'))
        
        # Softmax 和加权求和
        attn_weights = F.softmax(scores, dim=-1)
        local_output = torch.matmul(attn_weights, V)
        
        return local_output
    
    def _combine_attention_outputs(
        self, 
        local_output: torch.Tensor, 
        memory_output: torch.Tensor
    ) -> torch.Tensor:
        """混合局部注意力和记忆注意力的输出"""
        # 使用可学习的 beta 参数进行加权混合
        beta = torch.sigmoid(self.compressive_memory.beta)
        combined = beta * memory_output + (1 - beta) * local_output
        return combined
    
    def reset_memory(self):
        """重置记忆"""
        self.compressive_memory.reset_memory()
    
    def get_memory_info(self) -> Dict[str, Any]:
        """获取记忆信息"""
        return self.compressive_memory.get_memory_stats()


class SegmentProcessor:
    """分段处理器"""
    
    def __init__(self, segment_length: int = 2048):
        self.segment_length = segment_length
    
    def segment_sequence(
        self, 
        input_ids: torch.Tensor, 
        attention_mask: Optional[torch.Tensor] = None
    ) -> List[Tuple[torch.Tensor, Optional[torch.Tensor], bool]]:
        """
        将长序列分割成段
        
        Args:
            input_ids: 输入序列 [batch, seq_len]
            attention_mask: 注意力掩码 [batch, seq_len]
            
        Returns:
            分段列表，每个元素为 (segment_input_ids, segment_attention_mask, is_last_segment)
        """
        seq_len = input_ids.size(1)
        segments = []
        
        for start_idx in range(0, seq_len, self.segment_length):
            end_idx = min(start_idx + self.segment_length, seq_len)
            is_last_segment = (end_idx == seq_len)
            
            segment_input_ids = input_ids[:, start_idx:end_idx]
            segment_attention_mask = None
            if attention_mask is not None:
                segment_attention_mask = attention_mask[:, start_idx:end_idx]
            
            segments.append((segment_input_ids, segment_attention_mask, is_last_segment))
        
        return segments
    
    def reconstruct_sequence(self, segment_outputs: List[torch.Tensor]) -> torch.Tensor:
        """重构完整序列"""
        return torch.cat(segment_outputs, dim=1)
