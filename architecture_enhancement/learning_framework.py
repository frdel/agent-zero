"""
持续学习框架
实现自适应学习、知识图谱构建和性能自我评估
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import json
import time
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict, deque


class LearningType(Enum):
    """学习类型"""
    SUPERVISED = "supervised"      # 监督学习
    UNSUPERVISED = "unsupervised"  # 无监督学习
    REINFORCEMENT = "reinforcement"  # 强化学习
    TRANSFER = "transfer"          # 迁移学习
    INCREMENTAL = "incremental"    # 增量学习


class KnowledgeType(Enum):
    """知识类型"""
    FACTUAL = "factual"           # 事实性知识
    PROCEDURAL = "procedural"     # 程序性知识
    CONCEPTUAL = "conceptual"     # 概念性知识
    METACOGNITIVE = "metacognitive"  # 元认知知识


@dataclass
class LearningEvent:
    """学习事件"""
    event_id: str
    event_type: str
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    feedback: Optional[Dict[str, Any]] = None
    success: Optional[bool] = None
    timestamp: datetime = field(default_factory=datetime.now)
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class KnowledgeNode:
    """知识节点"""
    node_id: str
    knowledge_type: KnowledgeType
    content: Dict[str, Any]
    confidence: float
    source: str
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    success_rate: float = 1.0
    related_nodes: Set[str] = field(default_factory=set)


@dataclass
class UserProfile:
    """用户画像"""
    user_id: str
    preferences: Dict[str, float] = field(default_factory=dict)
    behavior_patterns: Dict[str, List[Any]] = field(default_factory=dict)
    skill_level: Dict[str, float] = field(default_factory=dict)
    interaction_history: List[Dict[str, Any]] = field(default_factory=list)
    learning_style: str = "adaptive"
    feedback_patterns: Dict[str, float] = field(default_factory=dict)


class ILearningEngine(ABC):
    """学习引擎接口"""
    
    @abstractmethod
    async def learn_from_interaction(self, event: LearningEvent) -> bool:
        """从交互中学习"""
        pass
    
    @abstractmethod
    async def update_knowledge(self, knowledge: Dict[str, Any]) -> None:
        """更新知识"""
        pass
    
    @abstractmethod
    async def get_recommendations(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """获取推荐"""
        pass


class AdaptiveLearningEngine(ILearningEngine):
    """自适应学习引擎"""
    
    def __init__(self):
        self.learning_history: deque = deque(maxlen=10000)
        self.knowledge_graph: Dict[str, KnowledgeNode] = {}
        self.user_profiles: Dict[str, UserProfile] = {}
        self.learning_patterns: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.performance_metrics: Dict[str, float] = {}
        self._initialize_learning_patterns()
    
    def _initialize_learning_patterns(self):
        """初始化学习模式"""
        self.learning_patterns = {
            "tool_usage": [],
            "problem_solving": [],
            "user_interaction": [],
            "error_recovery": [],
            "optimization": []
        }
    
    async def learn_from_interaction(self, event: LearningEvent) -> bool:
        """从交互中学习"""
        try:
            # 1. 记录学习事件
            self.learning_history.append(event)
            
            # 2. 更新知识图谱
            await self._update_knowledge_graph(event)
            
            # 3. 更新用户画像
            await self._update_user_profile(event)
            
            # 4. 提取学习模式
            await self._extract_learning_patterns(event)
            
            # 5. 更新性能指标
            await self._update_performance_metrics(event)
            
            return True
        except Exception as e:
            print(f"Learning from interaction failed: {e}")
            return False
    
    async def _update_knowledge_graph(self, event: LearningEvent):
        """更新知识图谱"""
        # 从事件中提取知识
        knowledge_items = await self._extract_knowledge_from_event(event)
        
        for item in knowledge_items:
            node_id = item["id"]
            
            if node_id in self.knowledge_graph:
                # 更新现有节点
                node = self.knowledge_graph[node_id]
                node.content.update(item["content"])
                node.updated_at = datetime.now()
                node.access_count += 1
                
                # 更新成功率
                if event.success is not None:
                    node.success_rate = (node.success_rate * (node.access_count - 1) + 
                                       (1.0 if event.success else 0.0)) / node.access_count
            else:
                # 创建新节点
                node = KnowledgeNode(
                    node_id=node_id,
                    knowledge_type=item["type"],
                    content=item["content"],
                    confidence=item.get("confidence", 0.8),
                    source=item.get("source", "interaction")
                )
                self.knowledge_graph[node_id] = node
            
            # 建立关联
            await self._establish_knowledge_relations(node, event)
    
    async def _extract_knowledge_from_event(self, event: LearningEvent) -> List[Dict[str, Any]]:
        """从事件中提取知识"""
        knowledge_items = []
        
        # 工具使用知识
        if "tool_name" in event.input_data:
            tool_name = event.input_data["tool_name"]
            knowledge_items.append({
                "id": f"tool_usage_{tool_name}",
                "type": KnowledgeType.PROCEDURAL,
                "content": {
                    "tool_name": tool_name,
                    "usage_context": event.context,
                    "success": event.success,
                    "parameters": event.input_data.get("parameters", {}),
                    "output": event.output_data
                },
                "confidence": 0.9 if event.success else 0.6
            })
        
        # 问题解决知识
        if "problem_type" in event.context:
            problem_type = event.context["problem_type"]
            knowledge_items.append({
                "id": f"problem_solving_{problem_type}",
                "type": KnowledgeType.CONCEPTUAL,
                "content": {
                    "problem_type": problem_type,
                    "solution_approach": event.input_data,
                    "outcome": event.output_data,
                    "success": event.success
                },
                "confidence": 0.8
            })
        
        # 用户偏好知识
        if "user_id" in event.context:
            user_id = event.context["user_id"]
            knowledge_items.append({
                "id": f"user_preference_{user_id}",
                "type": KnowledgeType.METACOGNITIVE,
                "content": {
                    "user_id": user_id,
                    "interaction_type": event.event_type,
                    "preferences": event.feedback or {},
                    "satisfaction": event.success
                },
                "confidence": 0.7
            })
        
        return knowledge_items
    
    async def _establish_knowledge_relations(self, node: KnowledgeNode, event: LearningEvent):
        """建立知识关联"""
        # 查找相关节点
        related_nodes = []
        
        for other_id, other_node in self.knowledge_graph.items():
            if other_id != node.node_id:
                similarity = await self._calculate_knowledge_similarity(node, other_node)
                if similarity > 0.6:
                    related_nodes.append(other_id)
        
        # 更新关联
        node.related_nodes.update(related_nodes)
        for related_id in related_nodes:
            self.knowledge_graph[related_id].related_nodes.add(node.node_id)
    
    async def _calculate_knowledge_similarity(self, node1: KnowledgeNode, node2: KnowledgeNode) -> float:
        """计算知识相似度"""
        # 简单的相似度计算
        if node1.knowledge_type != node2.knowledge_type:
            return 0.0
        
        # 基于内容的相似度
        content1_str = json.dumps(node1.content, sort_keys=True)
        content2_str = json.dumps(node2.content, sort_keys=True)
        
        # 简单的字符串相似度
        common_chars = set(content1_str) & set(content2_str)
        total_chars = set(content1_str) | set(content2_str)
        
        return len(common_chars) / len(total_chars) if total_chars else 0.0
    
    async def _update_user_profile(self, event: LearningEvent):
        """更新用户画像"""
        user_id = event.context.get("user_id")
        if not user_id:
            return
        
        if user_id not in self.user_profiles:
            self.user_profiles[user_id] = UserProfile(user_id=user_id)
        
        profile = self.user_profiles[user_id]
        
        # 更新交互历史
        profile.interaction_history.append({
            "event_id": event.event_id,
            "event_type": event.event_type,
            "timestamp": event.timestamp,
            "success": event.success
        })
        
        # 更新偏好
        if event.feedback:
            for key, value in event.feedback.items():
                if key in profile.preferences:
                    # 加权平均更新
                    profile.preferences[key] = (profile.preferences[key] * 0.8 + value * 0.2)
                else:
                    profile.preferences[key] = value
        
        # 更新行为模式
        behavior_key = event.event_type
        if behavior_key not in profile.behavior_patterns:
            profile.behavior_patterns[behavior_key] = []
        
        profile.behavior_patterns[behavior_key].append({
            "timestamp": event.timestamp,
            "input": event.input_data,
            "output": event.output_data,
            "success": event.success
        })
        
        # 保持最近100次行为
        if len(profile.behavior_patterns[behavior_key]) > 100:
            profile.behavior_patterns[behavior_key] = profile.behavior_patterns[behavior_key][-100:]
    
    async def _extract_learning_patterns(self, event: LearningEvent):
        """提取学习模式"""
        # 工具使用模式
        if "tool_name" in event.input_data:
            pattern = {
                "pattern_type": "tool_usage",
                "tool_name": event.input_data["tool_name"],
                "context": event.context,
                "success": event.success,
                "timestamp": event.timestamp
            }
            self.learning_patterns["tool_usage"].append(pattern)
        
        # 问题解决模式
        if "problem_type" in event.context:
            pattern = {
                "pattern_type": "problem_solving",
                "problem_type": event.context["problem_type"],
                "approach": event.input_data,
                "success": event.success,
                "timestamp": event.timestamp
            }
            self.learning_patterns["problem_solving"].append(pattern)
        
        # 保持最近1000个模式
        for pattern_type in self.learning_patterns:
            if len(self.learning_patterns[pattern_type]) > 1000:
                self.learning_patterns[pattern_type] = self.learning_patterns[pattern_type][-1000:]
    
    async def _update_performance_metrics(self, event: LearningEvent):
        """更新性能指标"""
        # 总体成功率
        recent_events = list(self.learning_history)[-100:]  # 最近100次交互
        success_count = sum(1 for e in recent_events if e.success)
        self.performance_metrics["overall_success_rate"] = success_count / len(recent_events) if recent_events else 0.0
        
        # 工具使用成功率
        if "tool_name" in event.input_data:
            tool_name = event.input_data["tool_name"]
            tool_events = [e for e in recent_events if e.input_data.get("tool_name") == tool_name]
            tool_success_count = sum(1 for e in tool_events if e.success)
            self.performance_metrics[f"tool_success_rate_{tool_name}"] = (
                tool_success_count / len(tool_events) if tool_events else 0.0
            )
        
        # 响应时间（如果有的话）
        if "response_time" in event.output_data:
            response_time = event.output_data["response_time"]
            if "avg_response_time" in self.performance_metrics:
                self.performance_metrics["avg_response_time"] = (
                    self.performance_metrics["avg_response_time"] * 0.9 + response_time * 0.1
                )
            else:
                self.performance_metrics["avg_response_time"] = response_time
    
    async def update_knowledge(self, knowledge: Dict[str, Any]) -> None:
        """更新知识"""
        node_id = knowledge.get("id", f"manual_{int(time.time())}")
        
        if node_id in self.knowledge_graph:
            node = self.knowledge_graph[node_id]
            node.content.update(knowledge.get("content", {}))
            node.updated_at = datetime.now()
        else:
            node = KnowledgeNode(
                node_id=node_id,
                knowledge_type=KnowledgeType(knowledge.get("type", "factual")),
                content=knowledge.get("content", {}),
                confidence=knowledge.get("confidence", 0.8),
                source="manual"
            )
            self.knowledge_graph[node_id] = node
    
    async def get_recommendations(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """获取推荐"""
        recommendations = []
        
        # 基于用户画像的推荐
        user_id = context.get("user_id")
        if user_id and user_id in self.user_profiles:
            user_recs = await self._get_user_based_recommendations(user_id, context)
            recommendations.extend(user_recs)
        
        # 基于知识图谱的推荐
        knowledge_recs = await self._get_knowledge_based_recommendations(context)
        recommendations.extend(knowledge_recs)
        
        # 基于学习模式的推荐
        pattern_recs = await self._get_pattern_based_recommendations(context)
        recommendations.extend(pattern_recs)
        
        # 去重并排序
        unique_recs = {}
        for rec in recommendations:
            rec_id = rec.get("id", rec.get("recommendation"))
            if rec_id not in unique_recs or rec.get("confidence", 0) > unique_recs[rec_id].get("confidence", 0):
                unique_recs[rec_id] = rec
        
        sorted_recs = sorted(unique_recs.values(), key=lambda x: x.get("confidence", 0), reverse=True)
        return sorted_recs[:10]  # 返回前10个推荐
    
    async def _get_user_based_recommendations(self, user_id: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """基于用户画像的推荐"""
        profile = self.user_profiles[user_id]
        recommendations = []
        
        # 基于偏好推荐
        for pref_key, pref_value in profile.preferences.items():
            if pref_value > 0.7:  # 高偏好
                recommendations.append({
                    "id": f"user_pref_{pref_key}",
                    "type": "user_preference",
                    "recommendation": f"基于您的偏好推荐: {pref_key}",
                    "confidence": pref_value,
                    "reason": f"您对{pref_key}的偏好度为{pref_value:.2f}"
                })
        
        # 基于行为模式推荐
        for behavior_type, behaviors in profile.behavior_patterns.items():
            if len(behaviors) >= 5:  # 有足够的行为数据
                success_rate = sum(1 for b in behaviors if b.get("success")) / len(behaviors)
                if success_rate > 0.8:
                    recommendations.append({
                        "id": f"user_behavior_{behavior_type}",
                        "type": "behavior_pattern",
                        "recommendation": f"建议继续使用{behavior_type}方式",
                        "confidence": success_rate,
                        "reason": f"您在{behavior_type}方面的成功率为{success_rate:.2f}"
                    })
        
        return recommendations
    
    async def _get_knowledge_based_recommendations(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """基于知识图谱的推荐"""
        recommendations = []
        
        # 查找相关知识节点
        relevant_nodes = []
        for node_id, node in self.knowledge_graph.items():
            relevance = await self._calculate_context_relevance(node, context)
            if relevance > 0.5:
                relevant_nodes.append((node, relevance))
        
        # 基于相关节点生成推荐
        for node, relevance in sorted(relevant_nodes, key=lambda x: x[1], reverse=True)[:5]:
            recommendations.append({
                "id": f"knowledge_{node.node_id}",
                "type": "knowledge_based",
                "recommendation": f"基于知识推荐: {node.content.get('description', node.node_id)}",
                "confidence": relevance * node.confidence,
                "reason": f"相关度: {relevance:.2f}, 知识可信度: {node.confidence:.2f}"
            })
        
        return recommendations
    
    async def _calculate_context_relevance(self, node: KnowledgeNode, context: Dict[str, Any]) -> float:
        """计算上下文相关性"""
        relevance = 0.0
        
        # 检查内容匹配
        node_content_str = json.dumps(node.content).lower()
        for key, value in context.items():
            if str(value).lower() in node_content_str:
                relevance += 0.2
        
        # 检查知识类型匹配
        if context.get("knowledge_type") == node.knowledge_type.value:
            relevance += 0.3
        
        # 检查成功率
        relevance += node.success_rate * 0.3
        
        return min(1.0, relevance)
    
    async def _get_pattern_based_recommendations(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """基于学习模式的推荐"""
        recommendations = []
        
        # 分析工具使用模式
        tool_patterns = self.learning_patterns["tool_usage"]
        if tool_patterns:
            # 找出成功率最高的工具
            tool_success = defaultdict(list)
            for pattern in tool_patterns:
                tool_name = pattern["tool_name"]
                tool_success[tool_name].append(pattern["success"])
            
            for tool_name, successes in tool_success.items():
                success_rate = sum(successes) / len(successes)
                if success_rate > 0.8 and len(successes) >= 3:
                    recommendations.append({
                        "id": f"pattern_tool_{tool_name}",
                        "type": "pattern_based",
                        "recommendation": f"推荐使用工具: {tool_name}",
                        "confidence": success_rate,
                        "reason": f"该工具的历史成功率为{success_rate:.2f}"
                    })
        
        return recommendations
    
    def get_learning_summary(self) -> Dict[str, Any]:
        """获取学习摘要"""
        return {
            "total_interactions": len(self.learning_history),
            "knowledge_nodes": len(self.knowledge_graph),
            "user_profiles": len(self.user_profiles),
            "performance_metrics": self.performance_metrics,
            "learning_patterns_count": {
                pattern_type: len(patterns) 
                for pattern_type, patterns in self.learning_patterns.items()
            }
        }


class PerformanceEvaluator:
    """性能评估器"""
    
    def __init__(self):
        self.evaluation_history: List[Dict[str, Any]] = []
        self.benchmarks: Dict[str, float] = {}
        self.improvement_trends: Dict[str, List[float]] = defaultdict(list)
    
    async def evaluate_performance(self, learning_engine: AdaptiveLearningEngine) -> Dict[str, Any]:
        """评估性能"""
        current_time = datetime.now()
        
        # 获取当前性能指标
        current_metrics = learning_engine.performance_metrics.copy()
        
        # 计算改进趋势
        for metric_name, metric_value in current_metrics.items():
            self.improvement_trends[metric_name].append(metric_value)
            # 保持最近50个数据点
            if len(self.improvement_trends[metric_name]) > 50:
                self.improvement_trends[metric_name] = self.improvement_trends[metric_name][-50:]
        
        # 生成评估报告
        evaluation_report = {
            "timestamp": current_time,
            "current_metrics": current_metrics,
            "improvement_trends": self._calculate_trends(),
            "recommendations": await self._generate_improvement_recommendations(learning_engine),
            "overall_score": self._calculate_overall_score(current_metrics)
        }
        
        self.evaluation_history.append(evaluation_report)
        return evaluation_report
    
    def _calculate_trends(self) -> Dict[str, str]:
        """计算趋势"""
        trends = {}
        
        for metric_name, values in self.improvement_trends.items():
            if len(values) >= 10:
                recent_avg = np.mean(values[-10:])
                older_avg = np.mean(values[-20:-10]) if len(values) >= 20 else np.mean(values[:-10])
                
                if recent_avg > older_avg * 1.05:
                    trends[metric_name] = "improving"
                elif recent_avg < older_avg * 0.95:
                    trends[metric_name] = "declining"
                else:
                    trends[metric_name] = "stable"
            else:
                trends[metric_name] = "insufficient_data"
        
        return trends
    
    async def _generate_improvement_recommendations(self, learning_engine: AdaptiveLearningEngine) -> List[str]:
        """生成改进建议"""
        recommendations = []
        
        # 基于性能指标的建议
        metrics = learning_engine.performance_metrics
        
        if metrics.get("overall_success_rate", 0) < 0.7:
            recommendations.append("总体成功率较低，建议优化决策逻辑")
        
        if metrics.get("avg_response_time", 0) > 5.0:
            recommendations.append("平均响应时间较长，建议优化处理流程")
        
        # 基于知识图谱的建议
        if len(learning_engine.knowledge_graph) < 100:
            recommendations.append("知识图谱规模较小，建议增加学习数据")
        
        # 基于用户画像的建议
        if len(learning_engine.user_profiles) > 0:
            avg_interactions = np.mean([
                len(profile.interaction_history) 
                for profile in learning_engine.user_profiles.values()
            ])
            if avg_interactions < 10:
                recommendations.append("用户交互数据不足，建议增加用户参与度")
        
        return recommendations
    
    def _calculate_overall_score(self, metrics: Dict[str, float]) -> float:
        """计算总体评分"""
        score_components = []
        
        # 成功率权重 40%
        success_rate = metrics.get("overall_success_rate", 0)
        score_components.append(success_rate * 0.4)
        
        # 响应时间权重 20%（越快越好）
        response_time = metrics.get("avg_response_time", 10)
        response_score = max(0, 1 - response_time / 10)  # 10秒为基准
        score_components.append(response_score * 0.2)
        
        # 学习能力权重 40%（基于改进趋势）
        learning_score = 0.5  # 默认分数
        trends = self._calculate_trends()
        improving_count = sum(1 for trend in trends.values() if trend == "improving")
        total_trends = len(trends)
        if total_trends > 0:
            learning_score = improving_count / total_trends
        score_components.append(learning_score * 0.4)
        
        return sum(score_components)


# 全局实例
_learning_engine = AdaptiveLearningEngine()
_performance_evaluator = PerformanceEvaluator()


def get_learning_engine() -> AdaptiveLearningEngine:
    """获取学习引擎实例"""
    return _learning_engine


def get_performance_evaluator() -> PerformanceEvaluator:
    """获取性能评估器实例"""
    return _performance_evaluator
