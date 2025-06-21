"""
架构增强集成测试框架
验证所有新组件的集成效果和性能表现
"""

import asyncio
import time
import json
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

# 导入新架构组件
from .universal_framework import (
    get_plugin_manager, get_config_abstractor, get_task_planner,
    UniversalAgentConfig, TaskType, DomainType
)
from .intelligence_framework import (
    get_reasoning_engine, get_context_engine,
    DecisionContext, ReasoningType, ContextType
)
from .learning_framework import (
    get_learning_engine, get_performance_evaluator,
    LearningEvent, LearningType
)
from .scalability_framework import (
    get_version_manager, get_debt_manager, get_scalability_analyzer,
    ComponentVersion, ComponentType, TechnicalDebt
)


class TestType(Enum):
    """测试类型"""
    UNIT = "unit"
    INTEGRATION = "integration"
    PERFORMANCE = "performance"
    STRESS = "stress"
    COMPATIBILITY = "compatibility"


class TestStatus(Enum):
    """测试状态"""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TestResult:
    """测试结果"""
    test_id: str
    test_name: str
    test_type: TestType
    status: TestStatus
    execution_time: float
    details: Dict[str, Any] = field(default_factory=dict)
    error_message: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


class ArchitectureIntegrationTester:
    """架构集成测试器"""
    
    def __init__(self):
        self.test_results: List[TestResult] = []
        self.test_suite: Dict[str, List[str]] = {}
        self.performance_baselines: Dict[str, float] = {}
        self._initialize_test_suite()
    
    def _initialize_test_suite(self):
        """初始化测试套件"""
        self.test_suite = {
            "universal_framework": [
                "test_plugin_manager_registration",
                "test_config_abstractor_templates",
                "test_task_planner_analysis",
                "test_capability_discovery"
            ],
            "intelligence_framework": [
                "test_reasoning_engine_decisions",
                "test_context_understanding",
                "test_multi_modal_reasoning",
                "test_decision_explanation"
            ],
            "learning_framework": [
                "test_adaptive_learning",
                "test_knowledge_graph_building",
                "test_user_profile_updates",
                "test_performance_evaluation"
            ],
            "scalability_framework": [
                "test_version_management",
                "test_debt_tracking",
                "test_scalability_analysis",
                "test_compatibility_checking"
            ],
            "integration_tests": [
                "test_end_to_end_workflow",
                "test_cross_component_communication",
                "test_data_flow_integrity",
                "test_error_handling_cascade"
            ],
            "performance_tests": [
                "test_response_time_benchmarks",
                "test_memory_usage_optimization",
                "test_concurrent_request_handling",
                "test_scalability_limits"
            ]
        }
    
    async def run_full_test_suite(self) -> Dict[str, Any]:
        """运行完整测试套件"""
        print("🚀 开始架构增强集成测试...")
        start_time = time.time()
        
        all_results = {}
        
        # 运行各个模块的测试
        for module_name, test_methods in self.test_suite.items():
            print(f"\n📋 测试模块: {module_name}")
            module_results = await self._run_module_tests(module_name, test_methods)
            all_results[module_name] = module_results
        
        # 生成综合报告
        total_time = time.time() - start_time
        report = await self._generate_comprehensive_report(all_results, total_time)
        
        print(f"\n✅ 测试完成，总耗时: {total_time:.2f}秒")
        return report
    
    async def _run_module_tests(self, module_name: str, test_methods: List[str]) -> List[TestResult]:
        """运行模块测试"""
        results = []
        
        for test_method in test_methods:
            print(f"  🔍 执行测试: {test_method}")
            
            try:
                # 动态调用测试方法
                if hasattr(self, test_method):
                    result = await getattr(self, test_method)()
                    results.append(result)
                    
                    status_icon = "✅" if result.status == TestStatus.PASSED else "❌"
                    print(f"    {status_icon} {result.test_name}: {result.status.value} ({result.execution_time:.3f}s)")
                else:
                    # 创建跳过的测试结果
                    result = TestResult(
                        test_id=f"{module_name}_{test_method}",
                        test_name=test_method,
                        test_type=TestType.UNIT,
                        status=TestStatus.SKIPPED,
                        execution_time=0,
                        error_message="Test method not implemented"
                    )
                    results.append(result)
                    print(f"    ⏭️  {test_method}: SKIPPED (未实现)")
                    
            except Exception as e:
                result = TestResult(
                    test_id=f"{module_name}_{test_method}",
                    test_name=test_method,
                    test_type=TestType.UNIT,
                    status=TestStatus.FAILED,
                    execution_time=0,
                    error_message=str(e)
                )
                results.append(result)
                print(f"    ❌ {test_method}: FAILED - {str(e)}")
        
        self.test_results.extend(results)
        return results
    
    # ==================== 通用框架测试 ====================
    
    async def test_plugin_manager_registration(self) -> TestResult:
        """测试插件管理器注册功能"""
        start_time = time.time()
        
        try:
            plugin_manager = get_plugin_manager()
            
            # 模拟插件注册
            class MockPlugin:
                @property
                def name(self) -> str:
                    return "test_plugin"
                
                @property
                def version(self) -> str:
                    return "1.0.0"
                
                @property
                def capabilities(self):
                    return []
                
                async def initialize(self, context):
                    return True
                
                async def execute(self, action, params):
                    return {"result": "success"}
                
                async def cleanup(self):
                    pass
            
            mock_plugin = MockPlugin()
            success = await plugin_manager.register_plugin(mock_plugin)
            
            execution_time = time.time() - start_time
            
            return TestResult(
                test_id="universal_plugin_registration",
                test_name="Plugin Manager Registration",
                test_type=TestType.UNIT,
                status=TestStatus.PASSED if success else TestStatus.FAILED,
                execution_time=execution_time,
                details={"registered_plugins": len(plugin_manager._plugins)}
            )
            
        except Exception as e:
            return TestResult(
                test_id="universal_plugin_registration",
                test_name="Plugin Manager Registration",
                test_type=TestType.UNIT,
                status=TestStatus.FAILED,
                execution_time=time.time() - start_time,
                error_message=str(e)
            )
    
    async def test_config_abstractor_templates(self) -> TestResult:
        """测试配置抽象器模板功能"""
        start_time = time.time()
        
        try:
            config_abstractor = get_config_abstractor()
            
            # 测试配置模板获取
            variables = {
                "DOCKER_HOST": "localhost",
                "SSH_PORT": "22",
                "HTTP_PORT": "80"
            }
            
            config = config_abstractor.get_config_for_environment("docker_remote", variables)
            
            execution_time = time.time() - start_time
            
            # 验证配置是否正确替换变量
            success = (
                "localhost" in str(config) and
                "22" in str(config) and
                "80" in str(config)
            )
            
            return TestResult(
                test_id="universal_config_templates",
                test_name="Config Abstractor Templates",
                test_type=TestType.UNIT,
                status=TestStatus.PASSED if success else TestStatus.FAILED,
                execution_time=execution_time,
                details={"config_keys": list(config.keys()) if isinstance(config, dict) else []}
            )
            
        except Exception as e:
            return TestResult(
                test_id="universal_config_templates",
                test_name="Config Abstractor Templates",
                test_type=TestType.UNIT,
                status=TestStatus.FAILED,
                execution_time=time.time() - start_time,
                error_message=str(e)
            )
    
    async def test_task_planner_analysis(self) -> TestResult:
        """测试任务规划器分析功能"""
        start_time = time.time()
        
        try:
            task_planner = get_task_planner()
            
            # 测试任务规划
            task_description = "Create a Python script to analyze data"
            plan = await task_planner.plan_task(
                task_description, 
                TaskType.DEVELOPMENT, 
                DomainType.TECHNICAL
            )
            
            execution_time = time.time() - start_time
            
            # 验证规划结果
            success = (
                "task_id" in plan and
                "execution_steps" in plan and
                len(plan["execution_steps"]) > 0
            )
            
            return TestResult(
                test_id="universal_task_planning",
                test_name="Task Planner Analysis",
                test_type=TestType.UNIT,
                status=TestStatus.PASSED if success else TestStatus.FAILED,
                execution_time=execution_time,
                details={
                    "plan_keys": list(plan.keys()),
                    "steps_count": len(plan.get("execution_steps", []))
                }
            )
            
        except Exception as e:
            return TestResult(
                test_id="universal_task_planning",
                test_name="Task Planner Analysis",
                test_type=TestType.UNIT,
                status=TestStatus.FAILED,
                execution_time=time.time() - start_time,
                error_message=str(e)
            )
    
    async def test_capability_discovery(self) -> TestResult:
        """测试能力发现功能"""
        start_time = time.time()
        
        try:
            plugin_manager = get_plugin_manager()
            
            # 测试能力发现
            capabilities = plugin_manager.get_available_capabilities()
            
            execution_time = time.time() - start_time
            
            return TestResult(
                test_id="universal_capability_discovery",
                test_name="Capability Discovery",
                test_type=TestType.UNIT,
                status=TestStatus.PASSED,
                execution_time=execution_time,
                details={"capabilities_count": len(capabilities)}
            )
            
        except Exception as e:
            return TestResult(
                test_id="universal_capability_discovery",
                test_name="Capability Discovery",
                test_type=TestType.UNIT,
                status=TestStatus.FAILED,
                execution_time=time.time() - start_time,
                error_message=str(e)
            )
    
    # ==================== 智能框架测试 ====================
    
    async def test_reasoning_engine_decisions(self) -> TestResult:
        """测试推理引擎决策功能"""
        start_time = time.time()
        
        try:
            reasoning_engine = get_reasoning_engine()
            
            # 创建决策上下文
            context = DecisionContext(
                task_description="Analyze user data and generate report",
                available_tools=["data_query", "statistical_analysis", "report_generator"],
                current_state={"data_available": True, "user_permissions": "read"},
                objectives=["accuracy", "speed"],
                constraints=["privacy_compliance"]
            )
            
            # 执行推理
            decision = await reasoning_engine.reason(context)
            
            execution_time = time.time() - start_time
            
            # 验证决策结果
            success = (
                decision.chosen_action and
                len(decision.reasoning_chain) > 0 and
                0 <= decision.confidence_score <= 1
            )
            
            return TestResult(
                test_id="intelligence_reasoning_decisions",
                test_name="Reasoning Engine Decisions",
                test_type=TestType.UNIT,
                status=TestStatus.PASSED if success else TestStatus.FAILED,
                execution_time=execution_time,
                details={
                    "chosen_action": decision.chosen_action,
                    "confidence": decision.confidence_score,
                    "reasoning_steps": len(decision.reasoning_chain)
                }
            )
            
        except Exception as e:
            return TestResult(
                test_id="intelligence_reasoning_decisions",
                test_name="Reasoning Engine Decisions",
                test_type=TestType.UNIT,
                status=TestStatus.FAILED,
                execution_time=time.time() - start_time,
                error_message=str(e)
            )
    
    async def test_context_understanding(self) -> TestResult:
        """测试上下文理解功能"""
        start_time = time.time()
        
        try:
            context_engine = get_context_engine()
            
            # 测试上下文分析
            user_input = "Help me create a Python script for data analysis"
            session_id = "test_session_123"
            
            analysis = await context_engine.analyze_context(user_input, session_id)
            
            execution_time = time.time() - start_time
            
            # 验证分析结果
            success = (
                "context_analysis" in analysis and
                "comprehensive_understanding" in analysis and
                "context_confidence" in analysis
            )
            
            return TestResult(
                test_id="intelligence_context_understanding",
                test_name="Context Understanding",
                test_type=TestType.UNIT,
                status=TestStatus.PASSED if success else TestStatus.FAILED,
                execution_time=execution_time,
                details={
                    "confidence": analysis.get("context_confidence", 0),
                    "intent": analysis.get("comprehensive_understanding", {}).get("primary_intent", "unknown")
                }
            )
            
        except Exception as e:
            return TestResult(
                test_id="intelligence_context_understanding",
                test_name="Context Understanding",
                test_type=TestType.UNIT,
                status=TestStatus.FAILED,
                execution_time=time.time() - start_time,
                error_message=str(e)
            )
    
    # ==================== 学习框架测试 ====================
    
    async def test_adaptive_learning(self) -> TestResult:
        """测试自适应学习功能"""
        start_time = time.time()
        
        try:
            learning_engine = get_learning_engine()
            
            # 创建学习事件
            event = LearningEvent(
                event_id="test_event_001",
                event_type="tool_usage",
                input_data={"tool_name": "data_analysis", "parameters": {"format": "csv"}},
                output_data={"result": "success", "response_time": 2.5},
                success=True,
                context={"user_id": "test_user", "task_type": "analysis"}
            )
            
            # 执行学习
            success = await learning_engine.learn_from_interaction(event)
            
            execution_time = time.time() - start_time
            
            return TestResult(
                test_id="learning_adaptive_learning",
                test_name="Adaptive Learning",
                test_type=TestType.UNIT,
                status=TestStatus.PASSED if success else TestStatus.FAILED,
                execution_time=execution_time,
                details={
                    "knowledge_nodes": len(learning_engine.knowledge_graph),
                    "user_profiles": len(learning_engine.user_profiles)
                }
            )
            
        except Exception as e:
            return TestResult(
                test_id="learning_adaptive_learning",
                test_name="Adaptive Learning",
                test_type=TestType.UNIT,
                status=TestStatus.FAILED,
                execution_time=time.time() - start_time,
                error_message=str(e)
            )
    
    # ==================== 可扩展性框架测试 ====================
    
    async def test_version_management(self) -> TestResult:
        """测试版本管理功能"""
        start_time = time.time()
        
        try:
            version_manager = get_version_manager()
            
            # 创建组件版本
            component = ComponentVersion(
                component_id="test_component",
                version="1.0.0",
                component_type=ComponentType.CORE,
                dependencies={"python": ">=3.8"},
                new_features=["feature1", "feature2"]
            )
            
            # 注册组件
            success = await version_manager.register_component(component)
            
            execution_time = time.time() - start_time
            
            return TestResult(
                test_id="scalability_version_management",
                test_name="Version Management",
                test_type=TestType.UNIT,
                status=TestStatus.PASSED if success else TestStatus.FAILED,
                execution_time=execution_time,
                details={"registered_components": len(version_manager.component_registry)}
            )
            
        except Exception as e:
            return TestResult(
                test_id="scalability_version_management",
                test_name="Version Management",
                test_type=TestType.UNIT,
                status=TestStatus.FAILED,
                execution_time=time.time() - start_time,
                error_message=str(e)
            )
    
    # ==================== 集成测试 ====================
    
    async def test_end_to_end_workflow(self) -> TestResult:
        """测试端到端工作流"""
        start_time = time.time()
        
        try:
            # 模拟完整的工作流程
            # 1. 任务规划
            task_planner = get_task_planner()
            plan = await task_planner.plan_task(
                "Create a data analysis report",
                TaskType.DATA_ANALYSIS,
                DomainType.TECHNICAL
            )
            
            # 2. 推理决策
            reasoning_engine = get_reasoning_engine()
            context = DecisionContext(
                task_description="Create a data analysis report",
                available_tools=["data_query", "analysis_tool"],
                current_state={}
            )
            decision = await reasoning_engine.reason(context)
            
            # 3. 学习记录
            learning_engine = get_learning_engine()
            event = LearningEvent(
                event_id="e2e_test",
                event_type="workflow",
                input_data={"plan": plan},
                output_data={"decision": decision.chosen_action},
                success=True
            )
            await learning_engine.learn_from_interaction(event)
            
            execution_time = time.time() - start_time
            
            return TestResult(
                test_id="integration_end_to_end",
                test_name="End-to-End Workflow",
                test_type=TestType.INTEGRATION,
                status=TestStatus.PASSED,
                execution_time=execution_time,
                details={
                    "workflow_steps": ["planning", "reasoning", "learning"],
                    "total_components": 3
                }
            )
            
        except Exception as e:
            return TestResult(
                test_id="integration_end_to_end",
                test_name="End-to-End Workflow",
                test_type=TestType.INTEGRATION,
                status=TestStatus.FAILED,
                execution_time=time.time() - start_time,
                error_message=str(e)
            )
    
    # ==================== 性能测试 ====================
    
    async def test_response_time_benchmarks(self) -> TestResult:
        """测试响应时间基准"""
        start_time = time.time()
        
        try:
            # 测试各组件的响应时间
            response_times = {}
            
            # 测试推理引擎
            reasoning_start = time.time()
            reasoning_engine = get_reasoning_engine()
            context = DecisionContext(
                task_description="Simple task",
                available_tools=["tool1"],
                current_state={}
            )
            await reasoning_engine.reason(context)
            response_times["reasoning_engine"] = time.time() - reasoning_start
            
            # 测试上下文引擎
            context_start = time.time()
            context_engine = get_context_engine()
            await context_engine.analyze_context("test input", "session1")
            response_times["context_engine"] = time.time() - context_start
            
            execution_time = time.time() - start_time
            
            # 检查是否满足性能要求（< 5秒）
            max_response_time = max(response_times.values())
            success = max_response_time < 5.0
            
            return TestResult(
                test_id="performance_response_time",
                test_name="Response Time Benchmarks",
                test_type=TestType.PERFORMANCE,
                status=TestStatus.PASSED if success else TestStatus.FAILED,
                execution_time=execution_time,
                details={
                    "response_times": response_times,
                    "max_response_time": max_response_time
                }
            )
            
        except Exception as e:
            return TestResult(
                test_id="performance_response_time",
                test_name="Response Time Benchmarks",
                test_type=TestType.PERFORMANCE,
                status=TestStatus.FAILED,
                execution_time=time.time() - start_time,
                error_message=str(e)
            )
    
    async def _generate_comprehensive_report(self, all_results: Dict[str, List[TestResult]], total_time: float) -> Dict[str, Any]:
        """生成综合测试报告"""
        
        # 统计总体结果
        total_tests = sum(len(results) for results in all_results.values())
        passed_tests = sum(
            len([r for r in results if r.status == TestStatus.PASSED])
            for results in all_results.values()
        )
        failed_tests = sum(
            len([r for r in results if r.status == TestStatus.FAILED])
            for results in all_results.values()
        )
        skipped_tests = sum(
            len([r for r in results if r.status == TestStatus.SKIPPED])
            for results in all_results.values()
        )
        
        # 计算成功率
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        # 性能统计
        performance_results = [r for results in all_results.values() for r in results if r.test_type == TestType.PERFORMANCE]
        avg_response_time = sum(r.execution_time for r in performance_results) / len(performance_results) if performance_results else 0
        
        # 生成报告
        report = {
            "summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "skipped": skipped_tests,
                "success_rate": f"{success_rate:.1f}%",
                "total_execution_time": f"{total_time:.2f}s"
            },
            "module_results": {},
            "performance_metrics": {
                "average_response_time": f"{avg_response_time:.3f}s",
                "performance_tests_count": len(performance_results)
            },
            "failed_tests": [],
            "recommendations": []
        }
        
        # 模块结果统计
        for module_name, results in all_results.items():
            module_passed = len([r for r in results if r.status == TestStatus.PASSED])
            module_total = len(results)
            module_success_rate = (module_passed / module_total * 100) if module_total > 0 else 0
            
            report["module_results"][module_name] = {
                "passed": module_passed,
                "total": module_total,
                "success_rate": f"{module_success_rate:.1f}%"
            }
        
        # 失败测试详情
        for results in all_results.values():
            for result in results:
                if result.status == TestStatus.FAILED:
                    report["failed_tests"].append({
                        "test_name": result.test_name,
                        "error": result.error_message,
                        "execution_time": result.execution_time
                    })
        
        # 生成建议
        if success_rate < 80:
            report["recommendations"].append("总体成功率偏低，需要重点关注失败的测试用例")
        
        if avg_response_time > 3.0:
            report["recommendations"].append("平均响应时间较长，建议优化性能")
        
        if failed_tests > 0:
            report["recommendations"].append(f"有{failed_tests}个测试失败，建议优先修复")
        
        return report


async def main():
    """主测试函数"""
    tester = ArchitectureIntegrationTester()
    report = await tester.run_full_test_suite()
    
    # 保存测试报告
    with open("architecture_test_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    
    print("\n" + "="*60)
    print("📊 测试报告摘要")
    print("="*60)
    print(f"总测试数: {report['summary']['total_tests']}")
    print(f"通过: {report['summary']['passed']}")
    print(f"失败: {report['summary']['failed']}")
    print(f"跳过: {report['summary']['skipped']}")
    print(f"成功率: {report['summary']['success_rate']}")
    print(f"总耗时: {report['summary']['total_execution_time']}")
    
    if report['failed_tests']:
        print(f"\n❌ 失败测试:")
        for failed_test in report['failed_tests']:
            print(f"  - {failed_test['test_name']}: {failed_test['error']}")
    
    if report['recommendations']:
        print(f"\n💡 建议:")
        for rec in report['recommendations']:
            print(f"  - {rec}")
    
    print(f"\n📄 详细报告已保存到: architecture_test_report.json")


if __name__ == "__main__":
    asyncio.run(main())
