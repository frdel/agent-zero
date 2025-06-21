"""
API使用优化配置和工具
用于减少不必要的API调用和令牌使用
"""

from dataclasses import dataclass
from typing import Dict, Any
import time
from python.helpers import tokens


@dataclass
class APIOptimizationConfig:
    """API优化配置"""
    # 记忆相关优化
    memory_fragment_interval: int = 5  # 记忆片段的间隔
    memory_solution_interval: int = 3  # 记忆解决方案的间隔
    memory_recall_interval: int = 5    # 记忆检索的间隔
    
    # Token限制
    max_history_tokens: int = 4000     # 历史记录最大token数
    max_memory_query_tokens: int = 2000 # 记忆查询最大token数
    
    # 缓存设置
    enable_response_cache: bool = True  # 启用响应缓存
    cache_ttl_seconds: int = 300       # 缓存生存时间（5分钟）
    
    # 批处理设置
    batch_memory_operations: bool = True  # 批量处理记忆操作
    batch_size: int = 5                   # 批处理大小


class APIUsageOptimizer:
    """API使用优化器"""
    
    def __init__(self, config: APIOptimizationConfig = None):
        self.config = config or APIOptimizationConfig()
        self._response_cache: Dict[str, Dict[str, Any]] = {}
        self._last_memory_operations: Dict[str, float] = {}
    
    def should_memorize_fragments(self, agent, conversation_length: int) -> bool:
        """检查是否应该记忆对话片段"""
        key = f"{agent.context.id}_fragments"
        last_time = self._last_memory_operations.get(key, 0)
        current_time = time.time()
        
        # 检查时间间隔
        if current_time - last_time < 60 * self.config.memory_fragment_interval:
            return False
        
        # 检查对话长度
        if conversation_length < 3:
            return False
        
        self._last_memory_operations[key] = current_time
        return True
    
    def should_memorize_solutions(self, agent, conversation_length: int, has_solution: bool) -> bool:
        """检查是否应该记忆解决方案"""
        if not has_solution:
            return False
            
        key = f"{agent.context.id}_solutions"
        last_time = self._last_memory_operations.get(key, 0)
        current_time = time.time()
        
        # 检查时间间隔
        if current_time - last_time < 60 * self.config.memory_solution_interval:
            return False
        
        # 检查对话长度
        if conversation_length < 4:
            return False
        
        self._last_memory_operations[key] = current_time
        return True
    
    def should_recall_memories(self, agent, iteration: int, user_message_content: str) -> bool:
        """检查是否应该检索记忆"""
        # 第一次迭代总是检索
        if iteration == 0:
            return True
        
        # 检查间隔
        if iteration % self.config.memory_recall_interval != 0:
            return False
        
        # 检查是否包含问题或请求
        if user_message_content:
            content = user_message_content.lower()
            question_indicators = ['?', 'how', 'what', 'why', 'when', 'where', 'help', 'explain']
            return any(indicator in content for indicator in question_indicators)
        
        return False
    
    def optimize_history_for_memory(self, full_history: str) -> str:
        """优化历史记录用于记忆操作"""
        # 限制token数量
        if tokens.approximate_tokens(full_history) <= self.config.max_history_tokens:
            return full_history
        
        # 截取最近的对话
        return tokens.trim_to_tokens(full_history, self.config.max_history_tokens, "end")
    
    def get_cached_response(self, cache_key: str) -> str | None:
        """获取缓存的响应"""
        if not self.config.enable_response_cache:
            return None
        
        cached = self._response_cache.get(cache_key)
        if not cached:
            return None
        
        # 检查缓存是否过期
        if time.time() - cached['timestamp'] > self.config.cache_ttl_seconds:
            del self._response_cache[cache_key]
            return None
        
        return cached['response']
    
    def cache_response(self, cache_key: str, response: str):
        """缓存响应"""
        if not self.config.enable_response_cache:
            return
        
        self._response_cache[cache_key] = {
            'response': response,
            'timestamp': time.time()
        }
        
        # 清理过期缓存
        self._cleanup_expired_cache()
    
    def _cleanup_expired_cache(self):
        """清理过期的缓存"""
        current_time = time.time()
        expired_keys = [
            key for key, value in self._response_cache.items()
            if current_time - value['timestamp'] > self.config.cache_ttl_seconds
        ]
        
        for key in expired_keys:
            del self._response_cache[key]


# 全局优化器实例
_global_optimizer = None

def get_optimizer() -> APIUsageOptimizer:
    """获取全局API优化器实例"""
    global _global_optimizer
    if _global_optimizer is None:
        _global_optimizer = APIUsageOptimizer()
    return _global_optimizer

def set_optimization_config(config: APIOptimizationConfig):
    """设置优化配置"""
    global _global_optimizer
    _global_optimizer = APIUsageOptimizer(config)
