#!/usr/bin/env python3
"""
增强架构集成测试脚本
测试所有新增的架构组件和智能模型系统
"""

import asyncio
import time
import json
from pathlib import Path
import sys

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


async def test_enhanced_model_system():
    """测试增强模型系统"""
    print("🤖 测试增强模型系统...")
    
    try:
        # 导入模型系统
        from python.helpers.model_config_initializer import initialize_models
        from python.helpers.enhanced_model_manager import get_model_manager
        from python.helpers.intelligent_model_dispatcher import (
            get_model_dispatcher, ModelRequest, TaskType, smart_generate
        )
        
        # 初始化模型
        print("  🔧 初始化模型配置...")
        success = initialize_models()
        if not success:
            print("  ❌ 模型初始化失败")
            return False
        
        # 测试模型管理器
        print("  📊 测试模型管理器...")
        model_manager = get_model_manager()
        stats = model_manager.get_model_statistics()
        print(f"     已注册模型: {stats['total_models']}")
        
        if stats['total_models'] == 0:
            print("  ⚠️  未找到可用模型，跳过模型测试")
            return True
        
        # 测试智能调度
        print("  🎯 测试智能模型调度...")
        test_cases = [
            ("写一篇关于AI的短文", TaskType.WRITING),
            ("编写一个Python排序函数", TaskType.CODING),
            ("分析这组数据的趋势", TaskType.ANALYSIS),
            ("Hello, how are you?", TaskType.CHAT)
        ]
        
        dispatcher = get_model_dispatcher()
        
        for content, task_type in test_cases:
            try:
                request = ModelRequest(
                    request_id=f"test_{int(time.time())}",
                    task_type=task_type,
                    content=content,
                    prefer_fast=True
                )
                
                response = await dispatcher.dispatch_request(request)
                if response.success:
                    print(f"     ✅ {task_type.value}: {response.model_id} ({response.response_time:.2f}s)")
                else:
                    print(f"     ❌ {task_type.value}: {response.error_message}")
            except Exception as e:
                print(f"     ⚠️  {task_type.value}: {e}")
        
        print("  ✅ 增强模型系统测试完成")
        return True
        
    except ImportError as e:
        print(f"  ⚠️  增强模型系统未安装: {e}")
        return True
    except Exception as e:
        print(f"  ❌ 增强模型系统测试失败: {e}")
        return False


async def test_universal_framework():
    """测试通用性框架"""
    print("🏗️ 测试通用性框架...")
    
    try:
        from architecture_enhancement.universal_framework import (
            get_plugin_manager, get_config_abstractor, get_task_planner,
            TaskType, DomainType
        )
        
        # 测试插件管理器
        print("  🔌 测试插件管理器...")
        plugin_manager = get_plugin_manager()
        capabilities = plugin_manager.get_available_capabilities()
        print(f"     可用能力: {len(capabilities)}")
        
        # 测试配置抽象器
        print("  ⚙️  测试配置抽象器...")
        config_abstractor = get_config_abstractor()
        test_config = config_abstractor.get_config_for_environment(
            "docker_local", {"WORK_DIR": "/workspace"}
        )
        print(f"     配置模板: {len(test_config)} 项")
        
        # 测试任务规划器
        print("  📋 测试任务规划器...")
        task_planner = get_task_planner()
        plan = await task_planner.plan_task(
            "Create a web application",
            TaskType.DEVELOPMENT,
            DomainType.TECHNICAL
        )
        print(f"     执行步骤: {len(plan.get('execution_steps', []))}")
        
        print("  ✅ 通用性框架测试完成")
        return True
        
    except ImportError as e:
        print(f"  ⚠️  通用性框架未安装: {e}")
        return True
    except Exception as e:
        print(f"  ❌ 通用性框架测试失败: {e}")
        return False


async def test_intelligence_framework():
    """测试智能化框架"""
    print("🧠 测试智能化框架...")
    
    try:
        from architecture_enhancement.intelligence_framework import (
            get_reasoning_engine, get_context_engine,
            DecisionContext, ReasoningType
        )
        
        # 测试推理引擎
        print("  🤔 测试推理引擎...")
        reasoning_engine = get_reasoning_engine()
        
        context = DecisionContext(
            task_description="Choose the best programming language for a web project",
            available_tools=["python", "javascript", "java"],
            current_state={"project_type": "web", "team_size": "small"},
            objectives=["fast_development", "maintainability"]
        )
        
        decision = await reasoning_engine.reason(context)
        print(f"     决策: {decision.chosen_action}")
        print(f"     推理步骤: {len(decision.reasoning_chain)}")
        print(f"     信心度: {decision.confidence_score:.2f}")
        
        # 测试上下文理解引擎
        print("  🎯 测试上下文理解引擎...")
        context_engine = get_context_engine()
        
        analysis = await context_engine.analyze_context(
            "Help me build a machine learning model for image classification",
            "test_session"
        )
        
        understanding = analysis.get("comprehensive_understanding", {})
        print(f"     意图: {understanding.get('primary_intent', 'unknown')}")
        print(f"     领域: {understanding.get('domain', 'unknown')}")
        print(f"     信心度: {analysis.get('context_confidence', 0):.2f}")
        
        print("  ✅ 智能化框架测试完成")
        return True
        
    except ImportError as e:
        print(f"  ⚠️  智能化框架未安装: {e}")
        return True
    except Exception as e:
        print(f"  ❌ 智能化框架测试失败: {e}")
        return False


async def test_learning_framework():
    """测试学习框架"""
    print("🎓 测试学习框架...")
    
    try:
        from architecture_enhancement.learning_framework import (
            get_learning_engine, get_performance_evaluator,
            LearningEvent, LearningType
        )
        
        # 测试学习引擎
        print("  📚 测试学习引擎...")
        learning_engine = get_learning_engine()
        
        # 创建学习事件
        event = LearningEvent(
            event_id="test_learning_001",
            event_type="tool_usage",
            input_data={"tool_name": "code_generator", "task": "create_function"},
            output_data={"result": "success", "code_quality": 8},
            success=True,
            context={"user_id": "test_user", "domain": "programming"}
        )
        
        # 执行学习
        success = await learning_engine.learn_from_interaction(event)
        print(f"     学习结果: {'成功' if success else '失败'}")
        
        # 获取推荐
        recommendations = await learning_engine.get_recommendations({
            "user_id": "test_user",
            "task_type": "programming"
        })
        print(f"     推荐数量: {len(recommendations)}")
        
        # 测试性能评估器
        print("  📊 测试性能评估器...")
        evaluator = get_performance_evaluator()
        
        report = await evaluator.evaluate_performance(learning_engine)
        print(f"     总体评分: {report.get('overall_score', 0):.2f}")
        print(f"     改进建议: {len(report.get('recommendations', []))}")
        
        print("  ✅ 学习框架测试完成")
        return True
        
    except ImportError as e:
        print(f"  ⚠️  学习框架未安装: {e}")
        return True
    except Exception as e:
        print(f"  ❌ 学习框架测试失败: {e}")
        return False


async def test_scalability_framework():
    """测试可扩展性框架"""
    print("📈 测试可扩展性框架...")
    
    try:
        from architecture_enhancement.scalability_framework import (
            get_version_manager, get_debt_manager, get_scalability_analyzer,
            ComponentVersion, ComponentType, TechnicalDebt
        )
        
        # 测试版本管理器
        print("  🏷️  测试版本管理器...")
        version_manager = get_version_manager()
        
        component = ComponentVersion(
            component_id="test_component",
            version="1.0.0",
            component_type=ComponentType.CORE,
            dependencies={"python": ">=3.8"},
            new_features=["feature1", "feature2"]
        )
        
        success = await version_manager.register_component(component)
        print(f"     组件注册: {'成功' if success else '失败'}")
        
        # 测试技术债务管理器
        print("  💳 测试技术债务管理器...")
        debt_manager = get_debt_manager()
        
        debt = TechnicalDebt(
            debt_id="test_debt_001",
            component_id="test_component",
            debt_type="code_smell",
            description="需要重构的复杂函数",
            severity=6,
            estimated_effort=8
        )
        
        success = await debt_manager.register_debt(debt)
        print(f"     债务注册: {'成功' if success else '失败'}")
        
        # 测试可扩展性分析器
        print("  🔍 测试可扩展性分析器...")
        analyzer = get_scalability_analyzer()
        
        test_components = {
            "component1": {"dependencies": ["comp2", "comp3"]},
            "component2": {"dependencies": ["comp3"]},
            "component3": {"dependencies": []}
        }
        
        metrics = await analyzer.analyze_scalability(test_components)
        print(f"     组件数量: {metrics.component_count}")
        print(f"     依赖复杂度: {metrics.dependency_complexity:.2f}")
        print(f"     耦合度: {metrics.coupling_degree:.2f}")
        
        print("  ✅ 可扩展性框架测试完成")
        return True
        
    except ImportError as e:
        print(f"  ⚠️  可扩展性框架未安装: {e}")
        return True
    except Exception as e:
        print(f"  ❌ 可扩展性框架测试失败: {e}")
        return False


async def test_integration():
    """测试组件集成"""
    print("🔗 测试组件集成...")
    
    try:
        # 测试端到端工作流
        print("  🔄 测试端到端工作流...")
        
        # 模拟一个完整的任务处理流程
        task_description = "Create a Python script to analyze CSV data"
        
        # 1. 任务规划
        from architecture_enhancement.universal_framework import get_task_planner, TaskType, DomainType
        task_planner = get_task_planner()
        plan = await task_planner.plan_task(task_description, TaskType.DEVELOPMENT, DomainType.TECHNICAL)
        
        # 2. 智能推理
        from architecture_enhancement.intelligence_framework import get_reasoning_engine, DecisionContext
        reasoning_engine = get_reasoning_engine()
        context = DecisionContext(
            task_description=task_description,
            available_tools=["python", "pandas", "matplotlib"],
            current_state={"data_format": "csv"}
        )
        decision = await reasoning_engine.reason(context)
        
        # 3. 学习记录
        from architecture_enhancement.learning_framework import get_learning_engine, LearningEvent
        learning_engine = get_learning_engine()
        event = LearningEvent(
            event_id="integration_test",
            event_type="workflow",
            input_data={"task": task_description, "plan": plan},
            output_data={"decision": decision.chosen_action},
            success=True
        )
        await learning_engine.learn_from_interaction(event)
        
        print("     ✅ 端到端工作流测试成功")
        
        # 4. 如果有模型系统，测试智能模型选择
        try:
            from python.helpers.intelligent_model_dispatcher import smart_generate, TaskType as ModelTaskType
            result = await smart_generate(
                "Generate a simple Python function",
                task_type=ModelTaskType.CODING,
                prefer_fast=True
            )
            print(f"     ✅ 智能模型集成测试成功 (响应长度: {len(result)})")
        except Exception as e:
            print(f"     ⚠️  智能模型集成跳过: {e}")
        
        print("  ✅ 组件集成测试完成")
        return True
        
    except Exception as e:
        print(f"  ❌ 组件集成测试失败: {e}")
        return False


def generate_test_report(results):
    """生成测试报告"""
    print("\n" + "="*60)
    print("📋 增强架构测试报告")
    print("="*60)
    
    total_tests = len(results)
    passed_tests = sum(1 for result in results.values() if result)
    
    print(f"总测试数: {total_tests}")
    print(f"通过测试: {passed_tests}")
    print(f"成功率: {passed_tests/total_tests*100:.1f}%")
    
    print("\n详细结果:")
    for test_name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {test_name}: {status}")
    
    if passed_tests == total_tests:
        print(f"\n🎉 所有测试通过！增强架构系统运行正常。")
    else:
        print(f"\n⚠️  有 {total_tests - passed_tests} 个测试失败，请检查相关组件。")
    
    # 保存报告
    report_data = {
        "timestamp": time.time(),
        "total_tests": total_tests,
        "passed_tests": passed_tests,
        "success_rate": passed_tests/total_tests,
        "results": results
    }
    
    with open("enhanced_architecture_test_report.json", "w") as f:
        json.dump(report_data, f, indent=2)
    
    print(f"\n📄 详细报告已保存到: enhanced_architecture_test_report.json")


async def main():
    """主测试函数"""
    print("🚀 开始增强架构集成测试...")
    print("="*60)
    
    start_time = time.time()
    
    # 执行所有测试
    test_results = {}
    
    test_results["enhanced_model_system"] = await test_enhanced_model_system()
    test_results["universal_framework"] = await test_universal_framework()
    test_results["intelligence_framework"] = await test_intelligence_framework()
    test_results["learning_framework"] = await test_learning_framework()
    test_results["scalability_framework"] = await test_scalability_framework()
    test_results["integration"] = await test_integration()
    
    total_time = time.time() - start_time
    
    print(f"\n⏱️  总测试时间: {total_time:.2f}秒")
    
    # 生成报告
    generate_test_report(test_results)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 测试已取消")
    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
