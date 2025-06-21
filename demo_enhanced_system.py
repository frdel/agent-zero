#!/usr/bin/env python3
"""
零号行动增强系统演示
展示智能模型选择和架构增强功能
"""

import asyncio
import time
from pathlib import Path
import sys

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


async def demo_intelligent_model_selection():
    """演示智能模型选择"""
    print("🤖 智能模型选择演示")
    print("=" * 50)
    
    try:
        from python.helpers.model_config_initializer import initialize_models
        from python.helpers.intelligent_model_dispatcher import (
            smart_generate, smart_chat, TaskType, ModelRequest, get_model_dispatcher
        )
        
        # 初始化模型系统
        print("🔧 初始化模型系统...")
        success = initialize_models()
        if not success:
            print("❌ 模型系统初始化失败")
            return
        
        # 演示不同任务类型的智能选择
        demo_tasks = [
            {
                "description": "浏览器任务 - 分析网页截图",
                "content": "请分析这个网页截图中的主要元素和布局",
                "task_type": TaskType.BROWSING,
                "icon": "🌐"
            },
            {
                "description": "写作任务 - 创作文章",
                "content": "写一篇关于人工智能发展趋势的500字文章",
                "task_type": TaskType.WRITING,
                "icon": "✍️"
            },
            {
                "description": "代码任务 - 编程实现",
                "content": "用Python实现一个快速排序算法，包含详细注释",
                "task_type": TaskType.CODING,
                "icon": "💻"
            },
            {
                "description": "分析任务 - 数据分析",
                "content": "分析销售数据的季度趋势，找出关键增长点",
                "task_type": TaskType.ANALYSIS,
                "icon": "📊"
            },
            {
                "description": "推理任务 - 逻辑推理",
                "content": "解释为什么机器学习模型会出现过拟合现象",
                "task_type": TaskType.REASONING,
                "icon": "🤔"
            }
        ]
        
        dispatcher = get_model_dispatcher()
        
        for i, task in enumerate(demo_tasks, 1):
            print(f"\n{task['icon']} 演示 {i}: {task['description']}")
            print(f"任务内容: {task['content']}")
            
            start_time = time.time()
            
            try:
                # 创建模型请求
                request = ModelRequest(
                    request_id=f"demo_{i}_{int(time.time())}",
                    task_type=task['task_type'],
                    content=task['content'],
                    prefer_fast=True  # 演示时优先速度
                )
                
                # 调度请求
                response = await dispatcher.dispatch_request(request)
                
                execution_time = time.time() - start_time
                
                if response.success:
                    print(f"✅ 选择模型: {response.model_id}")
                    print(f"⏱️  执行时间: {execution_time:.2f}秒")
                    print(f"📝 响应长度: {len(response.content)}字符")
                    
                    # 显示响应的前100个字符
                    preview = response.content[:100] + "..." if len(response.content) > 100 else response.content
                    print(f"📄 响应预览: {preview}")
                else:
                    print(f"❌ 执行失败: {response.error_message}")
                
            except Exception as e:
                print(f"⚠️  任务执行异常: {e}")
            
            print("-" * 50)
        
        # 显示性能报告
        print("\n📊 性能报告:")
        report = dispatcher.get_performance_report()
        summary = report.get('summary', {})
        
        print(f"总请求数: {summary.get('total_requests', 0)}")
        print(f"成功率: {summary.get('success_rate', 0):.2%}")
        print(f"平均响应时间: {summary.get('avg_response_time', 0):.2f}秒")
        
        # 按任务类型显示性能
        task_performance = report.get('task_performance', {})
        if task_performance:
            print("\n按任务类型性能:")
            for task_type, stats in task_performance.items():
                print(f"  {task_type}: 成功率 {stats.get('success_rate', 0):.2%}, "
                      f"平均时间 {stats.get('avg_response_time', 0):.2f}秒")
        
    except ImportError:
        print("⚠️  智能模型系统未安装，跳过演示")
    except Exception as e:
        print(f"❌ 演示失败: {e}")


async def demo_architecture_components():
    """演示架构组件"""
    print("\n🏗️ 架构组件演示")
    print("=" * 50)
    
    # 演示通用性框架
    try:
        print("🔌 通用性框架演示:")
        from architecture_enhancement.universal_framework import (
            get_plugin_manager, get_config_abstractor, get_task_planner,
            TaskType, DomainType
        )
        
        # 插件管理器
        plugin_manager = get_plugin_manager()
        capabilities = plugin_manager.get_available_capabilities()
        print(f"  可用能力数量: {len(capabilities)}")
        
        # 配置抽象器
        config_abstractor = get_config_abstractor()
        config = config_abstractor.get_config_for_environment("docker_local", {
            "WORK_DIR": "/workspace",
            "PYTHON_PATH": "/usr/bin/python3"
        })
        print(f"  配置模板项数: {len(config)}")
        
        # 任务规划器
        task_planner = get_task_planner()
        plan = await task_planner.plan_task(
            "开发一个数据分析Web应用",
            TaskType.DEVELOPMENT,
            DomainType.TECHNICAL
        )
        print(f"  规划步骤数: {len(plan.get('execution_steps', []))}")
        print(f"  复杂度评估: {plan.get('estimated_complexity', 0)}")
        
    except ImportError:
        print("  ⚠️  通用性框架未安装")
    except Exception as e:
        print(f"  ❌ 通用性框架演示失败: {e}")
    
    # 演示智能化框架
    try:
        print("\n🧠 智能化框架演示:")
        from architecture_enhancement.intelligence_framework import (
            get_reasoning_engine, get_context_engine, DecisionContext
        )
        
        # 推理引擎
        reasoning_engine = get_reasoning_engine()
        context = DecisionContext(
            task_description="选择最适合的机器学习算法",
            available_tools=["sklearn", "tensorflow", "pytorch"],
            current_state={"data_size": "large", "problem_type": "classification"},
            objectives=["accuracy", "interpretability"]
        )
        
        decision = await reasoning_engine.reason(context)
        print(f"  推理决策: {decision.chosen_action}")
        print(f"  信心度: {decision.confidence_score:.2f}")
        print(f"  推理步骤: {len(decision.reasoning_chain)}")
        
        # 上下文理解引擎
        context_engine = get_context_engine()
        analysis = await context_engine.analyze_context(
            "帮我构建一个图像分类模型，需要处理10万张图片",
            "demo_session"
        )
        
        understanding = analysis.get("comprehensive_understanding", {})
        print(f"  识别意图: {understanding.get('primary_intent', 'unknown')}")
        print(f"  领域判断: {understanding.get('domain', 'unknown')}")
        print(f"  理解信心度: {analysis.get('context_confidence', 0):.2f}")
        
    except ImportError:
        print("  ⚠️  智能化框架未安装")
    except Exception as e:
        print(f"  ❌ 智能化框架演示失败: {e}")
    
    # 演示学习框架
    try:
        print("\n🎓 学习框架演示:")
        from architecture_enhancement.learning_framework import (
            get_learning_engine, get_performance_evaluator, LearningEvent
        )
        
        learning_engine = get_learning_engine()
        
        # 模拟学习事件
        events = [
            LearningEvent(
                event_id="demo_learn_1",
                event_type="tool_usage",
                input_data={"tool": "data_analyzer", "task": "trend_analysis"},
                output_data={"accuracy": 0.92, "time": 2.5},
                success=True,
                context={"user_id": "demo_user", "domain": "data_science"}
            ),
            LearningEvent(
                event_id="demo_learn_2",
                event_type="problem_solving",
                input_data={"problem": "optimization", "approach": "gradient_descent"},
                output_data={"convergence": True, "iterations": 150},
                success=True,
                context={"user_id": "demo_user", "domain": "machine_learning"}
            )
        ]
        
        # 执行学习
        for event in events:
            await learning_engine.learn_from_interaction(event)
        
        # 获取学习摘要
        summary = learning_engine.get_learning_summary()
        print(f"  学习交互数: {summary.get('total_interactions', 0)}")
        print(f"  知识节点数: {summary.get('knowledge_nodes', 0)}")
        print(f"  用户画像数: {summary.get('user_profiles', 0)}")
        
        # 获取推荐
        recommendations = await learning_engine.get_recommendations({
            "user_id": "demo_user",
            "task_type": "data_analysis"
        })
        print(f"  生成推荐数: {len(recommendations)}")
        
        # 性能评估
        evaluator = get_performance_evaluator()
        evaluation = await evaluator.evaluate_performance(learning_engine)
        print(f"  系统评分: {evaluation.get('overall_score', 0):.2f}")
        
    except ImportError:
        print("  ⚠️  学习框架未安装")
    except Exception as e:
        print(f"  ❌ 学习框架演示失败: {e}")


def demo_configuration_management():
    """演示配置管理"""
    print("\n⚙️  配置管理演示")
    print("=" * 50)
    
    try:
        from python.helpers.enhanced_model_manager import get_model_manager
        from python.helpers.model_config_initializer import get_model_initializer
        
        model_manager = get_model_manager()
        initializer = get_model_initializer()
        
        # 显示当前配置
        stats = model_manager.get_model_statistics()
        print(f"已注册模型数: {stats['total_models']}")
        print(f"启用模型数: {stats['enabled_models']}")
        
        print("\n提供商分布:")
        for provider, count in stats['provider_distribution'].items():
            print(f"  {provider}: {count}个模型")
        
        print("\n能力分布:")
        for capability, count in stats['capability_distribution'].items():
            print(f"  {capability}: {count}个模型")
        
        # 显示任务映射
        print("\n任务模型映射:")
        for task_type, models in model_manager.task_model_mapping.items():
            if models:
                print(f"  {task_type.value}: {len(models)}个模型")
        
        # 创建示例配置
        sample_config = initializer.create_sample_config()
        print(f"\n示例配置包含 {len(sample_config['models'])} 个模型定义")
        
    except ImportError:
        print("⚠️  配置管理系统未安装")
    except Exception as e:
        print(f"❌ 配置管理演示失败: {e}")


async def main():
    """主演示函数"""
    print("🚀 零号行动增强系统演示")
    print("=" * 60)
    print("本演示将展示以下功能:")
    print("  🤖 智能模型选择和调度")
    print("  🏗️ 架构增强组件")
    print("  ⚙️  配置管理系统")
    print("=" * 60)
    
    start_time = time.time()
    
    # 运行演示
    await demo_intelligent_model_selection()
    await demo_architecture_components()
    demo_configuration_management()
    
    total_time = time.time() - start_time
    
    print("\n" + "=" * 60)
    print("🎉 演示完成！")
    print(f"⏱️  总演示时间: {total_time:.2f}秒")
    print("=" * 60)
    
    print("\n📚 下一步:")
    print("1. 查看 ENHANCED_ARCHITECTURE_README.md 了解详细使用方法")
    print("2. 运行 python test_enhanced_architecture.py 进行完整测试")
    print("3. 配置您的模型提供商并开始使用")
    print("4. 查看 ARCHITECTURE_ENHANCEMENT_ROADMAP.md 了解发展计划")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 演示已取消")
    except Exception as e:
        print(f"\n❌ 演示过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
