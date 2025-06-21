"""
零号行动项目优化配置文件
包含API使用优化、记忆系统改进和插件集成优化的配置
"""

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class APIOptimizationSettings:
    """API使用优化设置"""
    
    # 记忆操作频率控制
    memory_fragment_interval: int = 5  # 每5次对话记忆一次片段
    memory_solution_interval: int = 3  # 每3次对话记忆一次解决方案
    memory_recall_interval: int = 5    # 每5次迭代检索一次记忆
    
    # Token使用限制
    max_history_tokens: int = 4000     # 历史记录最大token数
    max_memory_query_tokens: int = 2000 # 记忆查询最大token数
    min_conversation_length: int = 3    # 开始记忆的最小对话长度
    
    # 缓存设置
    enable_response_cache: bool = True  # 启用响应缓存
    cache_ttl_seconds: int = 300       # 缓存生存时间（5分钟）
    
    # 批处理设置
    batch_memory_operations: bool = True  # 批量处理记忆操作
    batch_size: int = 5                   # 批处理大小


@dataclass
class MemoryPersistenceSettings:
    """记忆持久化设置"""
    
    # 持久化控制
    enable_cross_session_memory: bool = True  # 启用跨会话记忆
    auto_save_important_memories: bool = True # 自动保存重要记忆
    max_persistent_memories: int = 50         # 最大持久化记忆数量
    
    # 记忆重要性评分阈值
    importance_threshold: float = 0.7         # 记忆重要性阈值
    user_info_boost: float = 0.3             # 用户信息重要性加成
    solution_boost: float = 0.2              # 解决方案重要性加成
    
    # 记忆清理设置
    auto_cleanup_old_memories: bool = True    # 自动清理旧记忆
    memory_retention_days: int = 30           # 记忆保留天数
    max_memory_size_mb: int = 100            # 最大记忆存储大小（MB）


@dataclass
class PluginIntegrationSettings:
    """插件集成优化设置"""
    
    # 插件发现设置
    enable_plugin_discovery: bool = True     # 启用插件发现
    plugin_relevance_threshold: float = 0.3  # 插件相关性阈值
    max_recommended_plugins: int = 3         # 最大推荐插件数量
    
    # 工具匹配设置
    enable_fuzzy_tool_matching: bool = True  # 启用模糊工具匹配
    fuzzy_match_threshold: float = 0.5       # 模糊匹配阈值
    prefer_mcp_tools: bool = True            # 优先使用MCP工具
    
    # 插件使用统计
    track_plugin_usage: bool = True          # 跟踪插件使用情况
    suggest_underused_plugins: bool = True   # 建议使用不足的插件


@dataclass
class OptimizationConfig:
    """完整的优化配置"""
    
    api_optimization: APIOptimizationSettings
    memory_persistence: MemoryPersistenceSettings
    plugin_integration: PluginIntegrationSettings
    
    # 全局设置
    enable_optimization_logging: bool = True  # 启用优化日志
    optimization_log_level: str = "INFO"     # 优化日志级别
    
    @classmethod
    def create_default(cls) -> 'OptimizationConfig':
        """创建默认配置"""
        return cls(
            api_optimization=APIOptimizationSettings(),
            memory_persistence=MemoryPersistenceSettings(),
            plugin_integration=PluginIntegrationSettings()
        )
    
    @classmethod
    def create_conservative(cls) -> 'OptimizationConfig':
        """创建保守的优化配置（减少API调用）"""
        return cls(
            api_optimization=APIOptimizationSettings(
                memory_fragment_interval=10,  # 更少的记忆操作
                memory_solution_interval=5,
                memory_recall_interval=8,
                max_history_tokens=2000,      # 更少的token使用
                min_conversation_length=5,
                enable_response_cache=True,
                cache_ttl_seconds=600         # 更长的缓存时间
            ),
            memory_persistence=MemoryPersistenceSettings(
                max_persistent_memories=30,   # 更少的持久化记忆
                importance_threshold=0.8      # 更高的重要性阈值
            ),
            plugin_integration=PluginIntegrationSettings(
                plugin_relevance_threshold=0.5,  # 更高的相关性阈值
                max_recommended_plugins=2
            )
        )
    
    @classmethod
    def create_aggressive(cls) -> 'OptimizationConfig':
        """创建激进的优化配置（最大化功能）"""
        return cls(
            api_optimization=APIOptimizationSettings(
                memory_fragment_interval=2,   # 更频繁的记忆操作
                memory_solution_interval=1,
                memory_recall_interval=3,
                max_history_tokens=8000,      # 更多的token使用
                min_conversation_length=1,
                enable_response_cache=True,
                cache_ttl_seconds=120         # 更短的缓存时间
            ),
            memory_persistence=MemoryPersistenceSettings(
                max_persistent_memories=100,  # 更多的持久化记忆
                importance_threshold=0.5      # 更低的重要性阈值
            ),
            plugin_integration=PluginIntegrationSettings(
                plugin_relevance_threshold=0.2,  # 更低的相关性阈值
                max_recommended_plugins=5
            )
        )
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            'api_optimization': self.api_optimization.__dict__,
            'memory_persistence': self.memory_persistence.__dict__,
            'plugin_integration': self.plugin_integration.__dict__,
            'enable_optimization_logging': self.enable_optimization_logging,
            'optimization_log_level': self.optimization_log_level
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'OptimizationConfig':
        """从字典创建配置"""
        return cls(
            api_optimization=APIOptimizationSettings(**data.get('api_optimization', {})),
            memory_persistence=MemoryPersistenceSettings(**data.get('memory_persistence', {})),
            plugin_integration=PluginIntegrationSettings(**data.get('plugin_integration', {})),
            enable_optimization_logging=data.get('enable_optimization_logging', True),
            optimization_log_level=data.get('optimization_log_level', 'INFO')
        )


# 全局配置实例
_global_config = None

def get_optimization_config() -> OptimizationConfig:
    """获取全局优化配置"""
    global _global_config
    if _global_config is None:
        _global_config = OptimizationConfig.create_default()
    return _global_config

def set_optimization_config(config: OptimizationConfig):
    """设置全局优化配置"""
    global _global_config
    _global_config = config

def load_optimization_config_from_file(file_path: str) -> OptimizationConfig:
    """从文件加载优化配置"""
    import json
    from python.helpers import files
    
    try:
        if files.exists(file_path):
            data = json.loads(files.read_file(file_path))
            return OptimizationConfig.from_dict(data)
        else:
            # 如果文件不存在，创建默认配置并保存
            config = OptimizationConfig.create_default()
            save_optimization_config_to_file(config, file_path)
            return config
    except Exception as e:
        print(f"Error loading optimization config: {e}")
        return OptimizationConfig.create_default()

def save_optimization_config_to_file(config: OptimizationConfig, file_path: str):
    """保存优化配置到文件"""
    import json
    from python.helpers import files
    
    try:
        files.make_dirs(file_path)
        files.write_file(file_path, json.dumps(config.to_dict(), indent=2))
    except Exception as e:
        print(f"Error saving optimization config: {e}")


# 预定义配置
CONSERVATIVE_CONFIG = OptimizationConfig.create_conservative()
DEFAULT_CONFIG = OptimizationConfig.create_default()
AGGRESSIVE_CONFIG = OptimizationConfig.create_aggressive()
