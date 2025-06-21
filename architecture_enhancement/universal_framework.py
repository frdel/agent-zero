"""
通用性增强框架设计
解决硬编码、提高模块化程度、增强系统适应性
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Type, Protocol
from dataclasses import dataclass, field
from enum import Enum
import importlib
import inspect
from pathlib import Path


class TaskType(Enum):
    """任务类型枚举"""
    DEVELOPMENT = "development"
    DATA_ANALYSIS = "data_analysis"
    CONTENT_CREATION = "content_creation"
    SYSTEM_ADMIN = "system_admin"
    RESEARCH = "research"
    AUTOMATION = "automation"
    CUSTOM = "custom"


class DomainType(Enum):
    """领域类型枚举"""
    GENERAL = "general"
    TECHNICAL = "technical"
    BUSINESS = "business"
    SCIENTIFIC = "scientific"
    CREATIVE = "creative"
    EDUCATIONAL = "educational"


@dataclass
class CapabilityDescriptor:
    """能力描述符"""
    name: str
    description: str
    task_types: List[TaskType]
    domains: List[DomainType]
    required_tools: List[str] = field(default_factory=list)
    optional_tools: List[str] = field(default_factory=list)
    complexity_level: int = 1  # 1-10
    prerequisites: List[str] = field(default_factory=list)


class IPlugin(Protocol):
    """插件接口协议"""
    
    @property
    def name(self) -> str: ...
    
    @property
    def version(self) -> str: ...
    
    @property
    def capabilities(self) -> List[CapabilityDescriptor]: ...
    
    async def initialize(self, context: Dict[str, Any]) -> bool: ...
    
    async def execute(self, action: str, params: Dict[str, Any]) -> Any: ...
    
    async def cleanup(self) -> None: ...


class IToolProvider(Protocol):
    """工具提供者接口"""
    
    @property
    def provider_name(self) -> str: ...
    
    def get_available_tools(self) -> List[Dict[str, Any]]: ...
    
    async def get_tool(self, tool_name: str) -> Optional[Any]: ...
    
    def supports_tool(self, tool_name: str) -> bool: ...


class IConfigurationProvider(Protocol):
    """配置提供者接口"""
    
    def get_config(self, key: str, default: Any = None) -> Any: ...
    
    def set_config(self, key: str, value: Any) -> None: ...
    
    def get_all_configs(self) -> Dict[str, Any]: ...
    
    def validate_config(self, config: Dict[str, Any]) -> bool: ...


@dataclass
class UniversalAgentConfig:
    """通用代理配置"""
    # 核心配置
    agent_type: str = "general"
    task_types: List[TaskType] = field(default_factory=lambda: [TaskType.GENERAL])
    domains: List[DomainType] = field(default_factory=lambda: [DomainType.GENERAL])
    
    # 模型配置（抽象化）
    primary_model: Dict[str, Any] = field(default_factory=dict)
    utility_model: Dict[str, Any] = field(default_factory=dict)
    embedding_model: Dict[str, Any] = field(default_factory=dict)
    
    # 工具配置
    enabled_tool_providers: List[str] = field(default_factory=list)
    tool_preferences: Dict[str, int] = field(default_factory=dict)  # 工具优先级
    
    # 插件配置
    enabled_plugins: List[str] = field(default_factory=list)
    plugin_configs: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # 行为配置
    autonomy_level: int = 5  # 1-10，自主性级别
    risk_tolerance: int = 3  # 1-10，风险容忍度
    learning_enabled: bool = True
    
    # 环境配置（抽象化）
    execution_environment: Dict[str, Any] = field(default_factory=dict)
    resource_limits: Dict[str, Any] = field(default_factory=dict)
    
    # 扩展配置
    custom_extensions: List[str] = field(default_factory=list)
    extension_configs: Dict[str, Dict[str, Any]] = field(default_factory=dict)


class UniversalPluginManager:
    """通用插件管理器"""
    
    def __init__(self):
        self._plugins: Dict[str, IPlugin] = {}
        self._tool_providers: Dict[str, IToolProvider] = {}
        self._config_providers: Dict[str, IConfigurationProvider] = {}
        self._capabilities_registry: Dict[str, List[CapabilityDescriptor]] = {}
    
    async def register_plugin(self, plugin: IPlugin) -> bool:
        """注册插件"""
        try:
            if await plugin.initialize({}):
                self._plugins[plugin.name] = plugin
                self._capabilities_registry[plugin.name] = plugin.capabilities
                return True
        except Exception as e:
            print(f"Failed to register plugin {plugin.name}: {e}")
        return False
    
    def register_tool_provider(self, provider: IToolProvider) -> None:
        """注册工具提供者"""
        self._tool_providers[provider.provider_name] = provider
    
    def register_config_provider(self, provider: IConfigurationProvider) -> None:
        """注册配置提供者"""
        self._config_providers[provider.provider_name] = provider
    
    def find_plugins_for_task(self, task_type: TaskType, domain: DomainType) -> List[str]:
        """根据任务类型和领域查找合适的插件"""
        suitable_plugins = []
        
        for plugin_name, capabilities in self._capabilities_registry.items():
            for capability in capabilities:
                if task_type in capability.task_types and domain in capability.domains:
                    suitable_plugins.append(plugin_name)
                    break
        
        return suitable_plugins
    
    async def get_tool_from_providers(self, tool_name: str) -> Optional[Any]:
        """从所有工具提供者中查找工具"""
        for provider in self._tool_providers.values():
            if provider.supports_tool(tool_name):
                tool = await provider.get_tool(tool_name)
                if tool:
                    return tool
        return None
    
    def get_available_capabilities(self) -> Dict[str, List[CapabilityDescriptor]]:
        """获取所有可用能力"""
        return self._capabilities_registry.copy()


class ConfigurationAbstractor:
    """配置抽象器 - 解决硬编码问题"""
    
    def __init__(self):
        self._config_templates: Dict[str, Dict[str, Any]] = {}
        self._environment_configs: Dict[str, Dict[str, Any]] = {}
        self._load_default_templates()
    
    def _load_default_templates(self):
        """加载默认配置模板"""
        self._config_templates = {
            "docker_local": {
                "execution_environment": {
                    "type": "docker",
                    "image": "agent-zero-runtime",
                    "ports": {"ssh": 22, "http": 80},
                    "volumes": {"/workspace": "/a0", "/work": "/root"}
                }
            },
            "docker_remote": {
                "execution_environment": {
                    "type": "docker_remote",
                    "host": "${DOCKER_HOST}",
                    "ports": {"ssh": "${SSH_PORT}", "http": "${HTTP_PORT}"}
                }
            },
            "local_execution": {
                "execution_environment": {
                    "type": "local",
                    "working_directory": "${WORK_DIR}",
                    "python_path": "${PYTHON_PATH}"
                }
            },
            "cloud_execution": {
                "execution_environment": {
                    "type": "cloud",
                    "provider": "${CLOUD_PROVIDER}",
                    "region": "${CLOUD_REGION}",
                    "instance_type": "${INSTANCE_TYPE}"
                }
            }
        }
    
    def get_config_for_environment(self, env_type: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        """根据环境类型获取配置"""
        template = self._config_templates.get(env_type, {})
        return self._substitute_variables(template, variables)
    
    def _substitute_variables(self, config: Dict[str, Any], variables: Dict[str, Any]) -> Dict[str, Any]:
        """替换配置中的变量"""
        import json
        import re
        
        config_str = json.dumps(config)
        
        # 替换 ${VAR_NAME} 格式的变量
        for var_name, var_value in variables.items():
            pattern = f"\\${{\\s*{var_name}\\s*}}"
            config_str = re.sub(pattern, str(var_value), config_str)
        
        return json.loads(config_str)
    
    def register_config_template(self, name: str, template: Dict[str, Any]):
        """注册新的配置模板"""
        self._config_templates[name] = template


class AdaptiveTaskPlanner:
    """自适应任务规划器"""
    
    def __init__(self, plugin_manager: UniversalPluginManager):
        self.plugin_manager = plugin_manager
        self._task_patterns: Dict[str, Dict[str, Any]] = {}
        self._load_task_patterns()
    
    def _load_task_patterns(self):
        """加载任务模式"""
        self._task_patterns = {
            "development": {
                "required_capabilities": ["code_generation", "testing", "debugging"],
                "preferred_tools": ["code_execution", "file_management", "version_control"],
                "workflow_steps": ["analysis", "planning", "implementation", "testing", "deployment"]
            },
            "data_analysis": {
                "required_capabilities": ["data_processing", "visualization", "statistics"],
                "preferred_tools": ["data_query", "chart_generation", "statistical_analysis"],
                "workflow_steps": ["data_collection", "cleaning", "analysis", "visualization", "reporting"]
            },
            "content_creation": {
                "required_capabilities": ["text_generation", "editing", "formatting"],
                "preferred_tools": ["document_creation", "image_generation", "style_checking"],
                "workflow_steps": ["research", "outline", "drafting", "editing", "publishing"]
            }
        }
    
    async def plan_task(self, task_description: str, task_type: TaskType, domain: DomainType) -> Dict[str, Any]:
        """规划任务执行方案"""
        # 1. 分析任务需求
        task_requirements = await self._analyze_task_requirements(task_description)
        
        # 2. 查找合适的插件
        suitable_plugins = self.plugin_manager.find_plugins_for_task(task_type, domain)
        
        # 3. 生成执行计划
        execution_plan = {
            "task_id": f"task_{hash(task_description)}",
            "task_type": task_type.value,
            "domain": domain.value,
            "requirements": task_requirements,
            "recommended_plugins": suitable_plugins,
            "execution_steps": self._generate_execution_steps(task_type, task_requirements),
            "estimated_complexity": self._estimate_complexity(task_requirements),
            "resource_requirements": self._estimate_resources(task_requirements)
        }
        
        return execution_plan
    
    async def _analyze_task_requirements(self, task_description: str) -> Dict[str, Any]:
        """分析任务需求"""
        # 这里可以使用NLP技术分析任务描述
        # 暂时使用简单的关键词匹配
        keywords = task_description.lower().split()
        
        requirements = {
            "keywords": keywords,
            "complexity_indicators": [],
            "required_capabilities": [],
            "estimated_duration": "medium"
        }
        
        # 基于关键词推断需求
        if any(word in keywords for word in ["code", "program", "develop", "build"]):
            requirements["required_capabilities"].append("code_generation")
        
        if any(word in keywords for word in ["analyze", "data", "statistics"]):
            requirements["required_capabilities"].append("data_analysis")
        
        if any(word in keywords for word in ["write", "create", "content"]):
            requirements["required_capabilities"].append("content_creation")
        
        return requirements
    
    def _generate_execution_steps(self, task_type: TaskType, requirements: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成执行步骤"""
        pattern = self._task_patterns.get(task_type.value, {})
        base_steps = pattern.get("workflow_steps", ["analysis", "execution", "validation"])
        
        steps = []
        for i, step_name in enumerate(base_steps):
            steps.append({
                "step_id": i + 1,
                "name": step_name,
                "description": f"Execute {step_name} phase",
                "required_capabilities": pattern.get("required_capabilities", []),
                "preferred_tools": pattern.get("preferred_tools", [])
            })
        
        return steps
    
    def _estimate_complexity(self, requirements: Dict[str, Any]) -> int:
        """估算任务复杂度"""
        base_complexity = 3
        
        # 根据需求调整复杂度
        capability_count = len(requirements.get("required_capabilities", []))
        complexity_indicators = len(requirements.get("complexity_indicators", []))
        
        return min(10, base_complexity + capability_count + complexity_indicators)
    
    def _estimate_resources(self, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """估算资源需求"""
        return {
            "cpu_intensive": "code_generation" in requirements.get("required_capabilities", []),
            "memory_intensive": "data_analysis" in requirements.get("required_capabilities", []),
            "network_intensive": "web_scraping" in requirements.get("required_capabilities", []),
            "storage_intensive": "file_processing" in requirements.get("required_capabilities", [])
        }


# 全局实例
_plugin_manager = UniversalPluginManager()
_config_abstractor = ConfigurationAbstractor()
_task_planner = AdaptiveTaskPlanner(_plugin_manager)


def get_plugin_manager() -> UniversalPluginManager:
    """获取插件管理器实例"""
    return _plugin_manager


def get_config_abstractor() -> ConfigurationAbstractor:
    """获取配置抽象器实例"""
    return _config_abstractor


def get_task_planner() -> AdaptiveTaskPlanner:
    """获取任务规划器实例"""
    return _task_planner
