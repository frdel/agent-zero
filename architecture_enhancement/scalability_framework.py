"""
可扩展性和长期发展框架
解决技术债务、版本管理和向后兼容性问题
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import json
import time
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
import semver


class ComponentType(Enum):
    """组件类型"""
    CORE = "core"
    EXTENSION = "extension"
    TOOL = "tool"
    PLUGIN = "plugin"
    MODEL = "model"
    CONFIGURATION = "configuration"


class CompatibilityLevel(Enum):
    """兼容性级别"""
    BREAKING = "breaking"      # 破坏性变更
    MAJOR = "major"           # 主要变更
    MINOR = "minor"           # 次要变更
    PATCH = "patch"           # 补丁变更
    COMPATIBLE = "compatible"  # 完全兼容


@dataclass
class ComponentVersion:
    """组件版本信息"""
    component_id: str
    version: str
    component_type: ComponentType
    dependencies: Dict[str, str] = field(default_factory=dict)
    api_signature: str = ""
    compatibility_level: CompatibilityLevel = CompatibilityLevel.COMPATIBLE
    deprecated_features: List[str] = field(default_factory=list)
    new_features: List[str] = field(default_factory=list)
    migration_guide: str = ""
    release_date: datetime = field(default_factory=datetime.now)


@dataclass
class TechnicalDebt:
    """技术债务项"""
    debt_id: str
    component_id: str
    debt_type: str  # code_smell, performance, security, maintainability
    description: str
    severity: int  # 1-10
    estimated_effort: int  # 工时估算
    impact_areas: List[str] = field(default_factory=list)
    created_date: datetime = field(default_factory=datetime.now)
    priority: int = 5  # 1-10
    status: str = "open"  # open, in_progress, resolved


@dataclass
class ScalabilityMetrics:
    """可扩展性指标"""
    component_count: int
    dependency_complexity: float
    cyclomatic_complexity: float
    coupling_degree: float
    cohesion_level: float
    test_coverage: float
    performance_baseline: Dict[str, float] = field(default_factory=dict)
    resource_utilization: Dict[str, float] = field(default_factory=dict)


class IVersionManager(ABC):
    """版本管理器接口"""
    
    @abstractmethod
    async def register_component(self, component: ComponentVersion) -> bool:
        """注册组件版本"""
        pass
    
    @abstractmethod
    async def check_compatibility(self, component_id: str, target_version: str) -> CompatibilityLevel:
        """检查兼容性"""
        pass
    
    @abstractmethod
    async def get_migration_path(self, component_id: str, from_version: str, to_version: str) -> List[str]:
        """获取迁移路径"""
        pass


class AdvancedVersionManager(IVersionManager):
    """高级版本管理器"""
    
    def __init__(self):
        self.component_registry: Dict[str, List[ComponentVersion]] = {}
        self.compatibility_matrix: Dict[str, Dict[str, CompatibilityLevel]] = {}
        self.migration_scripts: Dict[str, Dict[str, str]] = {}
        self.api_signatures: Dict[str, Dict[str, str]] = {}
    
    async def register_component(self, component: ComponentVersion) -> bool:
        """注册组件版本"""
        try:
            component_id = component.component_id
            
            if component_id not in self.component_registry:
                self.component_registry[component_id] = []
            
            # 检查版本是否已存在
            existing_versions = [v.version for v in self.component_registry[component_id]]
            if component.version in existing_versions:
                return False
            
            # 计算API签名
            component.api_signature = await self._calculate_api_signature(component)
            
            # 添加到注册表
            self.component_registry[component_id].append(component)
            
            # 排序版本
            self.component_registry[component_id].sort(
                key=lambda x: semver.VersionInfo.parse(x.version)
            )
            
            # 更新兼容性矩阵
            await self._update_compatibility_matrix(component)
            
            return True
        except Exception as e:
            print(f"Failed to register component {component.component_id}: {e}")
            return False
    
    async def _calculate_api_signature(self, component: ComponentVersion) -> str:
        """计算API签名"""
        # 这里应该分析组件的公共接口
        # 简化实现：基于组件信息生成哈希
        signature_data = {
            "component_id": component.component_id,
            "component_type": component.component_type.value,
            "dependencies": component.dependencies,
            "new_features": component.new_features
        }
        
        signature_str = json.dumps(signature_data, sort_keys=True)
        return hashlib.sha256(signature_str.encode()).hexdigest()[:16]
    
    async def _update_compatibility_matrix(self, new_component: ComponentVersion):
        """更新兼容性矩阵"""
        component_id = new_component.component_id
        
        if component_id not in self.compatibility_matrix:
            self.compatibility_matrix[component_id] = {}
        
        # 与所有已有版本比较兼容性
        for existing_component in self.component_registry[component_id]:
            if existing_component.version != new_component.version:
                compatibility = await self._assess_compatibility(existing_component, new_component)
                self.compatibility_matrix[component_id][
                    f"{existing_component.version}->{new_component.version}"
                ] = compatibility
    
    async def _assess_compatibility(self, old_component: ComponentVersion, new_component: ComponentVersion) -> CompatibilityLevel:
        """评估兼容性"""
        # API签名比较
        if old_component.api_signature == new_component.api_signature:
            return CompatibilityLevel.COMPATIBLE
        
        # 版本号分析
        old_version = semver.VersionInfo.parse(old_component.version)
        new_version = semver.VersionInfo.parse(new_component.version)
        
        if new_version.major > old_version.major:
            return CompatibilityLevel.BREAKING
        elif new_version.minor > old_version.minor:
            return CompatibilityLevel.MAJOR
        elif new_version.patch > old_version.patch:
            return CompatibilityLevel.MINOR
        else:
            return CompatibilityLevel.PATCH
    
    async def check_compatibility(self, component_id: str, target_version: str) -> CompatibilityLevel:
        """检查兼容性"""
        if component_id not in self.component_registry:
            return CompatibilityLevel.BREAKING
        
        current_versions = self.component_registry[component_id]
        if not current_versions:
            return CompatibilityLevel.BREAKING
        
        latest_version = current_versions[-1].version
        compatibility_key = f"{latest_version}->{target_version}"
        
        return self.compatibility_matrix.get(component_id, {}).get(
            compatibility_key, CompatibilityLevel.BREAKING
        )
    
    async def get_migration_path(self, component_id: str, from_version: str, to_version: str) -> List[str]:
        """获取迁移路径"""
        if component_id not in self.component_registry:
            return []
        
        # 简化实现：直接迁移
        migration_key = f"{from_version}->{to_version}"
        migration_script = self.migration_scripts.get(component_id, {}).get(migration_key, "")
        
        if migration_script:
            return [migration_script]
        else:
            return [f"Manual migration required from {from_version} to {to_version}"]


class TechnicalDebtManager:
    """技术债务管理器"""
    
    def __init__(self):
        self.debt_registry: Dict[str, TechnicalDebt] = {}
        self.debt_metrics: Dict[str, float] = {}
        self.resolution_history: List[Dict[str, Any]] = []
    
    async def register_debt(self, debt: TechnicalDebt) -> bool:
        """注册技术债务"""
        try:
            self.debt_registry[debt.debt_id] = debt
            await self._update_debt_metrics()
            return True
        except Exception as e:
            print(f"Failed to register debt {debt.debt_id}: {e}")
            return False
    
    async def resolve_debt(self, debt_id: str, resolution_notes: str = "") -> bool:
        """解决技术债务"""
        if debt_id not in self.debt_registry:
            return False
        
        debt = self.debt_registry[debt_id]
        debt.status = "resolved"
        
        # 记录解决历史
        self.resolution_history.append({
            "debt_id": debt_id,
            "resolved_date": datetime.now(),
            "resolution_notes": resolution_notes,
            "effort_spent": debt.estimated_effort
        })
        
        await self._update_debt_metrics()
        return True
    
    async def _update_debt_metrics(self):
        """更新债务指标"""
        open_debts = [debt for debt in self.debt_registry.values() if debt.status == "open"]
        
        if open_debts:
            self.debt_metrics = {
                "total_debt_count": len(open_debts),
                "average_severity": sum(debt.severity for debt in open_debts) / len(open_debts),
                "total_estimated_effort": sum(debt.estimated_effort for debt in open_debts),
                "high_priority_count": len([debt for debt in open_debts if debt.priority >= 8]),
                "debt_by_type": self._group_debt_by_type(open_debts)
            }
        else:
            self.debt_metrics = {
                "total_debt_count": 0,
                "average_severity": 0,
                "total_estimated_effort": 0,
                "high_priority_count": 0,
                "debt_by_type": {}
            }
    
    def _group_debt_by_type(self, debts: List[TechnicalDebt]) -> Dict[str, int]:
        """按类型分组债务"""
        debt_by_type = {}
        for debt in debts:
            debt_by_type[debt.debt_type] = debt_by_type.get(debt.debt_type, 0) + 1
        return debt_by_type
    
    async def get_debt_report(self) -> Dict[str, Any]:
        """获取债务报告"""
        await self._update_debt_metrics()
        
        return {
            "metrics": self.debt_metrics,
            "top_priority_debts": await self._get_top_priority_debts(),
            "resolution_trends": await self._analyze_resolution_trends(),
            "recommendations": await self._generate_debt_recommendations()
        }
    
    async def _get_top_priority_debts(self) -> List[Dict[str, Any]]:
        """获取高优先级债务"""
        open_debts = [debt for debt in self.debt_registry.values() if debt.status == "open"]
        sorted_debts = sorted(open_debts, key=lambda x: (x.priority, x.severity), reverse=True)
        
        return [
            {
                "debt_id": debt.debt_id,
                "component_id": debt.component_id,
                "description": debt.description,
                "priority": debt.priority,
                "severity": debt.severity,
                "estimated_effort": debt.estimated_effort
            }
            for debt in sorted_debts[:10]
        ]
    
    async def _analyze_resolution_trends(self) -> Dict[str, Any]:
        """分析解决趋势"""
        if not self.resolution_history:
            return {"trend": "no_data"}
        
        recent_resolutions = [
            res for res in self.resolution_history
            if res["resolved_date"] > datetime.now() - timedelta(days=30)
        ]
        
        return {
            "recent_resolutions": len(recent_resolutions),
            "average_effort": sum(res["effort_spent"] for res in recent_resolutions) / len(recent_resolutions) if recent_resolutions else 0,
            "trend": "improving" if len(recent_resolutions) > len(self.resolution_history) / 4 else "stable"
        }
    
    async def _generate_debt_recommendations(self) -> List[str]:
        """生成债务处理建议"""
        recommendations = []
        
        if self.debt_metrics.get("high_priority_count", 0) > 5:
            recommendations.append("高优先级技术债务过多，建议立即处理")
        
        if self.debt_metrics.get("total_estimated_effort", 0) > 100:
            recommendations.append("技术债务总工作量过大，建议制定分阶段处理计划")
        
        debt_by_type = self.debt_metrics.get("debt_by_type", {})
        if debt_by_type:
            max_type = max(debt_by_type, key=debt_by_type.get)
            recommendations.append(f"建议优先处理{max_type}类型的技术债务")
        
        return recommendations


class ScalabilityAnalyzer:
    """可扩展性分析器"""
    
    def __init__(self):
        self.metrics_history: List[Tuple[datetime, ScalabilityMetrics]] = []
        self.bottleneck_analysis: Dict[str, Any] = {}
        self.scaling_recommendations: List[str] = []
    
    async def analyze_scalability(self, system_components: Dict[str, Any]) -> ScalabilityMetrics:
        """分析系统可扩展性"""
        metrics = ScalabilityMetrics(
            component_count=len(system_components),
            dependency_complexity=await self._calculate_dependency_complexity(system_components),
            cyclomatic_complexity=await self._calculate_cyclomatic_complexity(system_components),
            coupling_degree=await self._calculate_coupling_degree(system_components),
            cohesion_level=await self._calculate_cohesion_level(system_components),
            test_coverage=await self._calculate_test_coverage(system_components)
        )
        
        # 记录历史
        self.metrics_history.append((datetime.now(), metrics))
        
        # 保持最近100次记录
        if len(self.metrics_history) > 100:
            self.metrics_history = self.metrics_history[-100:]
        
        # 分析瓶颈
        await self._analyze_bottlenecks(metrics)
        
        # 生成建议
        await self._generate_scaling_recommendations(metrics)
        
        return metrics
    
    async def _calculate_dependency_complexity(self, components: Dict[str, Any]) -> float:
        """计算依赖复杂度"""
        total_dependencies = 0
        for component in components.values():
            dependencies = component.get("dependencies", [])
            total_dependencies += len(dependencies)
        
        # 归一化到0-1范围
        max_possible_deps = len(components) * (len(components) - 1)
        return total_dependencies / max_possible_deps if max_possible_deps > 0 else 0
    
    async def _calculate_cyclomatic_complexity(self, components: Dict[str, Any]) -> float:
        """计算圈复杂度"""
        # 简化实现：基于组件数量和连接数
        component_count = len(components)
        connection_count = sum(
            len(comp.get("dependencies", [])) for comp in components.values()
        )
        
        # 圈复杂度 = 边数 - 节点数 + 2
        complexity = max(1, connection_count - component_count + 2)
        
        # 归一化
        return min(1.0, complexity / (component_count * 2))
    
    async def _calculate_coupling_degree(self, components: Dict[str, Any]) -> float:
        """计算耦合度"""
        total_coupling = 0
        component_count = len(components)
        
        for component in components.values():
            external_deps = len(component.get("dependencies", []))
            total_coupling += external_deps
        
        # 归一化
        max_coupling = component_count * (component_count - 1)
        return total_coupling / max_coupling if max_coupling > 0 else 0
    
    async def _calculate_cohesion_level(self, components: Dict[str, Any]) -> float:
        """计算内聚度"""
        # 简化实现：基于组件内部功能的相关性
        total_cohesion = 0
        
        for component in components.values():
            # 假设组件有功能列表
            functions = component.get("functions", [])
            if len(functions) > 1:
                # 简单的内聚度计算
                cohesion = 1.0 / len(functions)  # 功能越少，内聚度越高
            else:
                cohesion = 1.0
            
            total_cohesion += cohesion
        
        return total_cohesion / len(components) if components else 0
    
    async def _calculate_test_coverage(self, components: Dict[str, Any]) -> float:
        """计算测试覆盖率"""
        total_coverage = 0
        
        for component in components.values():
            coverage = component.get("test_coverage", 0.5)  # 默认50%
            total_coverage += coverage
        
        return total_coverage / len(components) if components else 0
    
    async def _analyze_bottlenecks(self, metrics: ScalabilityMetrics):
        """分析瓶颈"""
        bottlenecks = {}
        
        if metrics.dependency_complexity > 0.7:
            bottlenecks["dependency"] = "依赖关系过于复杂"
        
        if metrics.coupling_degree > 0.6:
            bottlenecks["coupling"] = "组件间耦合度过高"
        
        if metrics.cohesion_level < 0.5:
            bottlenecks["cohesion"] = "组件内聚度过低"
        
        if metrics.test_coverage < 0.7:
            bottlenecks["testing"] = "测试覆盖率不足"
        
        self.bottleneck_analysis = bottlenecks
    
    async def _generate_scaling_recommendations(self, metrics: ScalabilityMetrics):
        """生成扩展建议"""
        recommendations = []
        
        if metrics.component_count > 100:
            recommendations.append("考虑将系统拆分为微服务架构")
        
        if metrics.dependency_complexity > 0.7:
            recommendations.append("简化组件依赖关系，考虑使用依赖注入")
        
        if metrics.coupling_degree > 0.6:
            recommendations.append("降低组件间耦合，增加抽象层")
        
        if metrics.cohesion_level < 0.5:
            recommendations.append("重构组件以提高内聚度")
        
        if metrics.test_coverage < 0.7:
            recommendations.append("增加单元测试和集成测试")
        
        self.scaling_recommendations = recommendations
    
    def get_scalability_report(self) -> Dict[str, Any]:
        """获取可扩展性报告"""
        if not self.metrics_history:
            return {"status": "no_data"}
        
        latest_metrics = self.metrics_history[-1][1]
        
        return {
            "current_metrics": {
                "component_count": latest_metrics.component_count,
                "dependency_complexity": latest_metrics.dependency_complexity,
                "coupling_degree": latest_metrics.coupling_degree,
                "cohesion_level": latest_metrics.cohesion_level,
                "test_coverage": latest_metrics.test_coverage
            },
            "bottlenecks": self.bottleneck_analysis,
            "recommendations": self.scaling_recommendations,
            "trends": self._analyze_trends(),
            "overall_score": self._calculate_scalability_score(latest_metrics)
        }
    
    def _analyze_trends(self) -> Dict[str, str]:
        """分析趋势"""
        if len(self.metrics_history) < 2:
            return {"trend": "insufficient_data"}
        
        recent = self.metrics_history[-1][1]
        previous = self.metrics_history[-2][1]
        
        trends = {}
        
        if recent.dependency_complexity > previous.dependency_complexity * 1.1:
            trends["dependency_complexity"] = "increasing"
        elif recent.dependency_complexity < previous.dependency_complexity * 0.9:
            trends["dependency_complexity"] = "decreasing"
        else:
            trends["dependency_complexity"] = "stable"
        
        if recent.test_coverage > previous.test_coverage * 1.05:
            trends["test_coverage"] = "improving"
        elif recent.test_coverage < previous.test_coverage * 0.95:
            trends["test_coverage"] = "declining"
        else:
            trends["test_coverage"] = "stable"
        
        return trends
    
    def _calculate_scalability_score(self, metrics: ScalabilityMetrics) -> float:
        """计算可扩展性评分"""
        # 权重分配
        weights = {
            "dependency_complexity": -0.2,  # 负权重，复杂度越低越好
            "coupling_degree": -0.2,       # 负权重，耦合度越低越好
            "cohesion_level": 0.3,         # 正权重，内聚度越高越好
            "test_coverage": 0.3           # 正权重，覆盖率越高越好
        }
        
        score = 0.5  # 基础分数
        
        score += (1 - metrics.dependency_complexity) * weights["dependency_complexity"]
        score += (1 - metrics.coupling_degree) * weights["coupling_degree"]
        score += metrics.cohesion_level * weights["cohesion_level"]
        score += metrics.test_coverage * weights["test_coverage"]
        
        return max(0, min(1, score))


# 全局实例
_version_manager = AdvancedVersionManager()
_debt_manager = TechnicalDebtManager()
_scalability_analyzer = ScalabilityAnalyzer()


def get_version_manager() -> AdvancedVersionManager:
    """获取版本管理器实例"""
    return _version_manager


def get_debt_manager() -> TechnicalDebtManager:
    """获取技术债务管理器实例"""
    return _debt_manager


def get_scalability_analyzer() -> ScalabilityAnalyzer:
    """获取可扩展性分析器实例"""
    return _scalability_analyzer
