"""
智能化提升框架
增强决策逻辑、推理能力和上下文理解
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import json
import time
from datetime import datetime, timedelta


class ReasoningType(Enum):
    """推理类型"""
    DEDUCTIVE = "deductive"  # 演绎推理
    INDUCTIVE = "inductive"  # 归纳推理
    ABDUCTIVE = "abductive"  # 溯因推理
    ANALOGICAL = "analogical"  # 类比推理
    CAUSAL = "causal"  # 因果推理


class ContextType(Enum):
    """上下文类型"""
    IMMEDIATE = "immediate"  # 即时上下文
    SESSION = "session"      # 会话上下文
    HISTORICAL = "historical"  # 历史上下文
    DOMAIN = "domain"        # 领域上下文
    USER = "user"           # 用户上下文


@dataclass
class ReasoningStep:
    """推理步骤"""
    step_id: str
    reasoning_type: ReasoningType
    premise: str
    conclusion: str
    confidence: float
    evidence: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class DecisionContext:
    """决策上下文"""
    task_description: str
    available_tools: List[str]
    current_state: Dict[str, Any]
    constraints: List[str] = field(default_factory=list)
    objectives: List[str] = field(default_factory=list)
    risk_factors: List[str] = field(default_factory=list)
    time_constraints: Optional[timedelta] = None


@dataclass
class DecisionResult:
    """决策结果"""
    chosen_action: str
    reasoning_chain: List[ReasoningStep]
    confidence_score: float
    alternative_actions: List[Tuple[str, float]] = field(default_factory=list)
    risk_assessment: Dict[str, float] = field(default_factory=dict)
    expected_outcome: str = ""


class IReasoningEngine(ABC):
    """推理引擎接口"""
    
    @abstractmethod
    async def reason(self, context: DecisionContext) -> DecisionResult:
        """执行推理"""
        pass
    
    @abstractmethod
    def add_knowledge(self, knowledge: Dict[str, Any]) -> None:
        """添加知识"""
        pass
    
    @abstractmethod
    def get_reasoning_explanation(self, decision: DecisionResult) -> str:
        """获取推理解释"""
        pass


class MultiModalReasoningEngine(IReasoningEngine):
    """多模态推理引擎"""
    
    def __init__(self):
        self.knowledge_base: Dict[str, Any] = {}
        self.reasoning_patterns: Dict[str, List[str]] = {}
        self.decision_history: List[Tuple[DecisionContext, DecisionResult]] = []
        self._load_reasoning_patterns()
    
    def _load_reasoning_patterns(self):
        """加载推理模式"""
        self.reasoning_patterns = {
            "tool_selection": [
                "分析任务需求",
                "评估工具能力",
                "匹配需求与能力",
                "考虑约束条件",
                "选择最优工具"
            ],
            "problem_solving": [
                "问题分解",
                "子问题分析",
                "解决方案生成",
                "方案评估",
                "最优方案选择"
            ],
            "risk_assessment": [
                "识别潜在风险",
                "评估风险概率",
                "评估风险影响",
                "制定缓解策略",
                "风险接受决策"
            ]
        }
    
    async def reason(self, context: DecisionContext) -> DecisionResult:
        """执行多模态推理"""
        reasoning_chain = []
        
        # 1. 任务分析推理
        task_analysis = await self._analyze_task(context)
        reasoning_chain.append(ReasoningStep(
            step_id="task_analysis",
            reasoning_type=ReasoningType.DEDUCTIVE,
            premise=f"任务描述: {context.task_description}",
            conclusion=f"任务类型: {task_analysis['type']}, 复杂度: {task_analysis['complexity']}",
            confidence=task_analysis['confidence']
        ))
        
        # 2. 工具选择推理
        tool_selection = await self._select_tools(context, task_analysis)
        reasoning_chain.append(ReasoningStep(
            step_id="tool_selection",
            reasoning_type=ReasoningType.ANALOGICAL,
            premise=f"可用工具: {context.available_tools}",
            conclusion=f"推荐工具: {tool_selection['recommended']}",
            confidence=tool_selection['confidence'],
            evidence=tool_selection['evidence']
        ))
        
        # 3. 风险评估推理
        risk_assessment = await self._assess_risks(context, tool_selection)
        reasoning_chain.append(ReasoningStep(
            step_id="risk_assessment",
            reasoning_type=ReasoningType.CAUSAL,
            premise=f"选择的工具和方法",
            conclusion=f"风险评估: {risk_assessment}",
            confidence=0.8
        ))
        
        # 4. 最终决策
        final_decision = await self._make_final_decision(context, task_analysis, tool_selection, risk_assessment)
        
        decision_result = DecisionResult(
            chosen_action=final_decision['action'],
            reasoning_chain=reasoning_chain,
            confidence_score=final_decision['confidence'],
            alternative_actions=final_decision['alternatives'],
            risk_assessment=risk_assessment,
            expected_outcome=final_decision['expected_outcome']
        )
        
        # 记录决策历史
        self.decision_history.append((context, decision_result))
        
        return decision_result
    
    async def _analyze_task(self, context: DecisionContext) -> Dict[str, Any]:
        """分析任务"""
        # 使用关键词分析和模式匹配
        description = context.task_description.lower()
        
        # 任务类型识别
        task_type = "general"
        if any(word in description for word in ["code", "program", "develop"]):
            task_type = "development"
        elif any(word in description for word in ["analyze", "data", "report"]):
            task_type = "analysis"
        elif any(word in description for word in ["write", "create", "content"]):
            task_type = "creation"
        
        # 复杂度评估
        complexity_indicators = [
            len(context.constraints),
            len(context.objectives),
            len(description.split()),
            1 if context.time_constraints else 0
        ]
        complexity = min(10, sum(complexity_indicators) // 2 + 1)
        
        return {
            "type": task_type,
            "complexity": complexity,
            "confidence": 0.8,
            "key_concepts": description.split()[:5]
        }
    
    async def _select_tools(self, context: DecisionContext, task_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """选择工具"""
        available_tools = context.available_tools
        task_type = task_analysis["type"]
        
        # 基于任务类型的工具偏好
        tool_preferences = {
            "development": ["code_execution", "file_management", "version_control"],
            "analysis": ["data_query", "statistical_analysis", "visualization"],
            "creation": ["document_creation", "image_generation", "text_processing"],
            "general": ["search_engine", "knowledge_tool", "memory_load"]
        }
        
        preferred_tools = tool_preferences.get(task_type, tool_preferences["general"])
        
        # 计算工具匹配分数
        tool_scores = {}
        for tool in available_tools:
            score = 0.5  # 基础分数
            
            # 偏好匹配
            if any(pref in tool.lower() for pref in preferred_tools):
                score += 0.3
            
            # 历史成功率
            historical_success = self._get_tool_success_rate(tool, task_type)
            score += historical_success * 0.2
            
            tool_scores[tool] = score
        
        # 选择最佳工具
        best_tools = sorted(tool_scores.items(), key=lambda x: x[1], reverse=True)[:3]
        
        return {
            "recommended": [tool for tool, score in best_tools],
            "confidence": best_tools[0][1] if best_tools else 0.5,
            "evidence": [f"{tool}: {score:.2f}" for tool, score in best_tools]
        }
    
    async def _assess_risks(self, context: DecisionContext, tool_selection: Dict[str, Any]) -> Dict[str, float]:
        """评估风险"""
        risks = {}
        
        # 工具风险
        for tool in tool_selection["recommended"]:
            tool_risk = self._get_tool_risk_level(tool)
            risks[f"tool_risk_{tool}"] = tool_risk
        
        # 时间风险
        if context.time_constraints:
            time_pressure = min(1.0, 1.0 / context.time_constraints.total_seconds() * 3600)
            risks["time_pressure"] = time_pressure
        
        # 复杂度风险
        complexity_risk = min(1.0, len(context.constraints) * 0.1 + len(context.objectives) * 0.1)
        risks["complexity_risk"] = complexity_risk
        
        return risks
    
    async def _make_final_decision(self, context: DecisionContext, task_analysis: Dict[str, Any], 
                                 tool_selection: Dict[str, Any], risk_assessment: Dict[str, float]) -> Dict[str, Any]:
        """做出最终决策"""
        recommended_tools = tool_selection["recommended"]
        
        # 选择主要行动
        if recommended_tools:
            primary_action = f"use_tool:{recommended_tools[0]}"
        else:
            primary_action = "analyze_further"
        
        # 生成替代方案
        alternatives = []
        for i, tool in enumerate(recommended_tools[1:3], 1):
            alternatives.append((f"use_tool:{tool}", 0.8 - i * 0.1))
        
        # 计算总体信心度
        tool_confidence = tool_selection["confidence"]
        risk_factor = 1.0 - max(risk_assessment.values()) if risk_assessment else 1.0
        overall_confidence = (tool_confidence + risk_factor) / 2
        
        return {
            "action": primary_action,
            "confidence": overall_confidence,
            "alternatives": alternatives,
            "expected_outcome": f"Successfully complete {task_analysis['type']} task using {recommended_tools[0] if recommended_tools else 'analysis'}"
        }
    
    def _get_tool_success_rate(self, tool: str, task_type: str) -> float:
        """获取工具历史成功率"""
        # 从决策历史中计算成功率
        relevant_decisions = [
            (ctx, result) for ctx, result in self.decision_history
            if tool in result.chosen_action and task_type in ctx.task_description.lower()
        ]
        
        if not relevant_decisions:
            return 0.5  # 默认成功率
        
        success_count = sum(1 for _, result in relevant_decisions if result.confidence_score > 0.7)
        return success_count / len(relevant_decisions)
    
    def _get_tool_risk_level(self, tool: str) -> float:
        """获取工具风险级别"""
        # 基于工具类型的风险评估
        high_risk_tools = ["code_execution", "file_management", "system_admin"]
        medium_risk_tools = ["web_scraping", "data_modification", "email_sending"]
        
        if any(risk_tool in tool.lower() for risk_tool in high_risk_tools):
            return 0.7
        elif any(risk_tool in tool.lower() for risk_tool in medium_risk_tools):
            return 0.4
        else:
            return 0.2
    
    def add_knowledge(self, knowledge: Dict[str, Any]) -> None:
        """添加知识到知识库"""
        self.knowledge_base.update(knowledge)
    
    def get_reasoning_explanation(self, decision: DecisionResult) -> str:
        """获取推理解释"""
        explanation = f"决策: {decision.chosen_action}\n"
        explanation += f"信心度: {decision.confidence_score:.2f}\n\n"
        explanation += "推理过程:\n"
        
        for i, step in enumerate(decision.reasoning_chain, 1):
            explanation += f"{i}. {step.reasoning_type.value}推理:\n"
            explanation += f"   前提: {step.premise}\n"
            explanation += f"   结论: {step.conclusion}\n"
            explanation += f"   信心度: {step.confidence:.2f}\n"
            if step.evidence:
                explanation += f"   证据: {', '.join(step.evidence)}\n"
            explanation += "\n"
        
        if decision.alternative_actions:
            explanation += "备选方案:\n"
            for action, confidence in decision.alternative_actions:
                explanation += f"- {action} (信心度: {confidence:.2f})\n"
        
        return explanation


class ContextualUnderstandingEngine:
    """上下文理解引擎"""
    
    def __init__(self):
        self.context_memory: Dict[ContextType, Dict[str, Any]] = {
            context_type: {} for context_type in ContextType
        }
        self.context_weights: Dict[ContextType, float] = {
            ContextType.IMMEDIATE: 1.0,
            ContextType.SESSION: 0.8,
            ContextType.HISTORICAL: 0.6,
            ContextType.DOMAIN: 0.7,
            ContextType.USER: 0.9
        }
    
    async def analyze_context(self, current_input: str, session_id: str) -> Dict[str, Any]:
        """分析当前上下文"""
        context_analysis = {
            "immediate_context": self._analyze_immediate_context(current_input),
            "session_context": self._get_session_context(session_id),
            "historical_patterns": self._analyze_historical_patterns(current_input),
            "domain_context": self._infer_domain_context(current_input),
            "user_context": self._get_user_context(session_id)
        }
        
        # 计算综合上下文理解
        comprehensive_understanding = self._synthesize_context(context_analysis)
        
        return {
            "context_analysis": context_analysis,
            "comprehensive_understanding": comprehensive_understanding,
            "context_confidence": self._calculate_context_confidence(context_analysis)
        }
    
    def _analyze_immediate_context(self, input_text: str) -> Dict[str, Any]:
        """分析即时上下文"""
        return {
            "intent": self._extract_intent(input_text),
            "entities": self._extract_entities(input_text),
            "sentiment": self._analyze_sentiment(input_text),
            "urgency": self._assess_urgency(input_text)
        }
    
    def _extract_intent(self, text: str) -> str:
        """提取意图"""
        text_lower = text.lower()
        
        if any(word in text_lower for word in ["create", "build", "make", "develop"]):
            return "creation"
        elif any(word in text_lower for word in ["analyze", "examine", "study", "investigate"]):
            return "analysis"
        elif any(word in text_lower for word in ["help", "assist", "support", "guide"]):
            return "assistance"
        elif any(word in text_lower for word in ["find", "search", "lookup", "discover"]):
            return "information_seeking"
        else:
            return "general"
    
    def _extract_entities(self, text: str) -> List[str]:
        """提取实体"""
        # 简单的实体提取（实际应用中可使用NER模型）
        import re
        
        # 提取可能的文件名、URL、技术术语等
        entities = []
        
        # 文件名模式
        file_pattern = r'\b\w+\.\w+\b'
        entities.extend(re.findall(file_pattern, text))
        
        # URL模式
        url_pattern = r'https?://[^\s]+'
        entities.extend(re.findall(url_pattern, text))
        
        # 技术术语（大写字母开头的词）
        tech_pattern = r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)*\b'
        entities.extend(re.findall(tech_pattern, text))
        
        return list(set(entities))
    
    def _analyze_sentiment(self, text: str) -> str:
        """分析情感"""
        positive_words = ["good", "great", "excellent", "amazing", "perfect", "love"]
        negative_words = ["bad", "terrible", "awful", "hate", "wrong", "error"]
        
        text_lower = text.lower()
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        else:
            return "neutral"
    
    def _assess_urgency(self, text: str) -> str:
        """评估紧急程度"""
        urgent_words = ["urgent", "asap", "immediately", "quickly", "fast", "emergency"]
        text_lower = text.lower()
        
        if any(word in text_lower for word in urgent_words):
            return "high"
        elif any(word in text_lower for word in ["soon", "today", "now"]):
            return "medium"
        else:
            return "low"
    
    def _get_session_context(self, session_id: str) -> Dict[str, Any]:
        """获取会话上下文"""
        return self.context_memory[ContextType.SESSION].get(session_id, {})
    
    def _analyze_historical_patterns(self, current_input: str) -> Dict[str, Any]:
        """分析历史模式"""
        historical_data = self.context_memory[ContextType.HISTORICAL]
        
        # 查找相似的历史请求
        similar_requests = []
        current_words = set(current_input.lower().split())
        
        for hist_input, hist_data in historical_data.items():
            hist_words = set(hist_input.lower().split())
            similarity = len(current_words & hist_words) / len(current_words | hist_words)
            
            if similarity > 0.3:
                similar_requests.append((hist_input, similarity, hist_data))
        
        return {
            "similar_requests": sorted(similar_requests, key=lambda x: x[1], reverse=True)[:3],
            "common_patterns": self._identify_common_patterns(similar_requests)
        }
    
    def _infer_domain_context(self, input_text: str) -> Dict[str, Any]:
        """推断领域上下文"""
        domain_keywords = {
            "technical": ["code", "programming", "software", "algorithm", "database"],
            "business": ["revenue", "profit", "market", "customer", "sales"],
            "scientific": ["research", "experiment", "hypothesis", "data", "analysis"],
            "creative": ["design", "art", "creative", "content", "writing"]
        }
        
        text_lower = input_text.lower()
        domain_scores = {}
        
        for domain, keywords in domain_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text_lower)
            domain_scores[domain] = score
        
        primary_domain = max(domain_scores, key=domain_scores.get) if any(domain_scores.values()) else "general"
        
        return {
            "primary_domain": primary_domain,
            "domain_scores": domain_scores,
            "confidence": max(domain_scores.values()) / len(domain_keywords[primary_domain]) if primary_domain != "general" else 0.5
        }
    
    def _get_user_context(self, session_id: str) -> Dict[str, Any]:
        """获取用户上下文"""
        return self.context_memory[ContextType.USER].get(session_id, {})
    
    def _synthesize_context(self, context_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """综合上下文分析"""
        # 综合各种上下文信息
        immediate = context_analysis["immediate_context"]
        domain = context_analysis["domain_context"]
        
        return {
            "primary_intent": immediate["intent"],
            "domain": domain["primary_domain"],
            "urgency_level": immediate["urgency"],
            "sentiment": immediate["sentiment"],
            "key_entities": immediate["entities"],
            "contextual_relevance": self._calculate_relevance(context_analysis)
        }
    
    def _calculate_context_confidence(self, context_analysis: Dict[str, Any]) -> float:
        """计算上下文理解的信心度"""
        confidence_factors = []
        
        # 即时上下文信心度
        immediate = context_analysis["immediate_context"]
        if immediate["entities"]:
            confidence_factors.append(0.8)
        else:
            confidence_factors.append(0.5)
        
        # 领域上下文信心度
        domain_confidence = context_analysis["domain_context"]["confidence"]
        confidence_factors.append(domain_confidence)
        
        # 历史模式信心度
        historical = context_analysis["historical_patterns"]
        if historical["similar_requests"]:
            confidence_factors.append(0.7)
        else:
            confidence_factors.append(0.4)
        
        return sum(confidence_factors) / len(confidence_factors)
    
    def _calculate_relevance(self, context_analysis: Dict[str, Any]) -> float:
        """计算上下文相关性"""
        # 基于各种上下文因素计算相关性分数
        relevance_score = 0.5  # 基础分数
        
        # 如果有历史相似请求，增加相关性
        if context_analysis["historical_patterns"]["similar_requests"]:
            relevance_score += 0.2
        
        # 如果领域明确，增加相关性
        if context_analysis["domain_context"]["confidence"] > 0.7:
            relevance_score += 0.2
        
        # 如果有明确实体，增加相关性
        if context_analysis["immediate_context"]["entities"]:
            relevance_score += 0.1
        
        return min(1.0, relevance_score)
    
    def _identify_common_patterns(self, similar_requests: List[Tuple[str, float, Dict[str, Any]]]) -> List[str]:
        """识别常见模式"""
        if not similar_requests:
            return []
        
        # 简单的模式识别
        patterns = []
        
        # 检查是否有重复的操作类型
        operations = [req[2].get("operation", "") for req in similar_requests if req[2].get("operation")]
        if operations:
            most_common_op = max(set(operations), key=operations.count)
            patterns.append(f"常见操作: {most_common_op}")
        
        return patterns
    
    def update_context(self, context_type: ContextType, key: str, value: Any) -> None:
        """更新上下文信息"""
        self.context_memory[context_type][key] = value
    
    def get_context_summary(self, session_id: str) -> str:
        """获取上下文摘要"""
        session_context = self._get_session_context(session_id)
        user_context = self._get_user_context(session_id)
        
        summary = f"会话上下文: {len(session_context)} 项信息\n"
        summary += f"用户上下文: {len(user_context)} 项信息\n"
        summary += f"历史记录: {len(self.context_memory[ContextType.HISTORICAL])} 项\n"
        
        return summary


# 全局实例
_reasoning_engine = MultiModalReasoningEngine()
_context_engine = ContextualUnderstandingEngine()


def get_reasoning_engine() -> MultiModalReasoningEngine:
    """获取推理引擎实例"""
    return _reasoning_engine


def get_context_engine() -> ContextualUnderstandingEngine:
    """获取上下文理解引擎实例"""
    return _context_engine
