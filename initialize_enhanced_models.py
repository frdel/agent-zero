#!/usr/bin/env python3
"""
增强模型系统初始化脚本
自动配置和启动智能模型管理系统
"""

import os
import sys
import asyncio
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from python.helpers.model_config_initializer import get_model_initializer, initialize_models
from python.helpers.enhanced_model_manager import get_model_manager
from python.helpers.intelligent_model_dispatcher import get_model_dispatcher


def print_banner():
    """打印启动横幅"""
    print("=" * 60)
    print("🚀 零号行动 - 增强模型系统初始化")
    print("=" * 60)
    print("支持的模型提供商:")
    print("  📡 OpenAI兼容端点 (OPENAI_ENDPOINT)")
    print("  🏠 vLLM本地服务 (VLLM)")
    print("  🦙 LlamaCpp GGUF模型 (LLAMACPP)")
    print("=" * 60)


def check_environment():
    """检查环境变量配置"""
    print("\n🔍 检查环境配置...")
    
    config_found = False
    
    # 检查OpenAI兼容端点
    openai_endpoint = os.getenv("OPENAI_ENDPOINT")
    openai_api_key = os.getenv("OPENAI_ENDPOINT_API_KEY")
    
    if openai_endpoint and openai_api_key:
        print(f"  ✅ OpenAI兼容端点: {openai_endpoint}")
        config_found = True
    else:
        print("  ⚠️  OpenAI兼容端点未配置")
        print("     设置 OPENAI_ENDPOINT 和 OPENAI_ENDPOINT_API_KEY")
    
    # 检查vLLM配置
    vllm_endpoint = os.getenv("VLLM_ENDPOINT", "http://localhost:8000")
    print(f"  📍 vLLM端点: {vllm_endpoint}")
    
    # 检查LlamaCpp配置
    llamacpp_endpoint = os.getenv("LLAMACPP_ENDPOINT", "http://localhost:8080")
    print(f"  📍 LlamaCpp端点: {llamacpp_endpoint}")
    
    # 检查传统OpenAI配置
    openai_api_key_traditional = os.getenv("OPENAI_API_KEY")
    if openai_api_key_traditional:
        print("  ✅ 传统OpenAI API密钥已配置")
        config_found = True
    
    if not config_found:
        print("\n⚠️  警告: 未检测到任何模型配置")
        print("请至少配置一种模型提供商")
    
    return config_found


def create_sample_env_file():
    """创建示例环境配置文件"""
    sample_env_content = """# 零号行动增强模型系统配置示例

# OpenAI兼容端点配置（云端大模型）
OPENAI_ENDPOINT=https://api.openai.com/v1
OPENAI_ENDPOINT_API_KEY=your_api_key_here

# 或者使用其他兼容OpenAI API的服务
# OPENAI_ENDPOINT=https://api.anthropic.com/v1
# OPENAI_ENDPOINT_API_KEY=your_anthropic_key

# vLLM本地服务配置
VLLM_ENDPOINT=http://localhost:8000
VLLM_MODEL_NAME=llama-2-7b-chat
VLLM_CODE_MODEL_NAME=codellama-7b-instruct

# LlamaCpp配置
LLAMACPP_ENDPOINT=http://localhost:8080
LLAMACPP_MODEL_PATH=/path/to/your/model.gguf
LLAMACPP_THREADS=4
LLAMACPP_GPU_LAYERS=0
LLAMACPP_EMBEDDING_MODEL=true

# 传统OpenAI配置（备用）
OPENAI_API_KEY=your_openai_key_here

# 其他配置
PYTHONPATH=.
"""
    
    env_file = project_root / ".env.example"
    with open(env_file, "w", encoding="utf-8") as f:
        f.write(sample_env_content)
    
    print(f"\n📄 已创建示例配置文件: {env_file}")
    print("请复制为 .env 文件并填入您的配置")


async def test_model_system():
    """测试模型系统"""
    print("\n🧪 测试模型系统...")
    
    try:
        # 测试模型管理器
        model_manager = get_model_manager()
        stats = model_manager.get_model_statistics()
        
        print(f"  📊 已注册模型数量: {stats['total_models']}")
        print(f"  ✅ 启用模型数量: {stats['enabled_models']}")
        
        if stats['total_models'] == 0:
            print("  ⚠️  未找到可用模型")
            return False
        
        # 测试调度器
        dispatcher = get_model_dispatcher()
        
        # 简单测试请求
        from python.helpers.intelligent_model_dispatcher import ModelRequest, TaskType
        
        test_request = ModelRequest(
            request_id="test_001",
            task_type=TaskType.CHAT,
            content="Hello, this is a test message.",
            prefer_fast=True
        )
        
        print("  🔄 测试模型调度...")
        response = await dispatcher.dispatch_request(test_request)
        
        if response.success:
            print(f"  ✅ 模型调度测试成功")
            print(f"     使用模型: {response.model_id}")
            print(f"     响应时间: {response.response_time:.2f}秒")
            print(f"     响应长度: {len(response.content)}字符")
        else:
            print(f"  ❌ 模型调度测试失败: {response.error_message}")
            return False
        
        return True
        
    except Exception as e:
        print(f"  ❌ 测试失败: {e}")
        return False


def print_usage_guide():
    """打印使用指南"""
    print("\n" + "=" * 60)
    print("📚 使用指南")
    print("=" * 60)
    
    print("\n🎯 任务类型自动识别:")
    print("  • 浏览器任务 → 多模态模型 (支持视觉)")
    print("  • 写作任务 → 本地小模型 (快速便宜)")
    print("  • 代码任务 → 大型代码模型 (高质量)")
    print("  • 分析任务 → 分析专用模型")
    print("  • 推理任务 → 推理能力强的模型")
    
    print("\n🔧 手动使用API:")
    print("```python")
    print("from python.helpers.intelligent_model_dispatcher import smart_generate, TaskType")
    print("")
    print("# 自动选择模型")
    print("result = await smart_generate('写一篇关于AI的文章')")
    print("")
    print("# 指定任务类型")
    print("code = await smart_generate('写一个排序算法', task_type=TaskType.CODING)")
    print("```")
    
    print("\n⚙️  配置管理:")
    print("  • 配置文件: config/model_config.json")
    print("  • 环境变量: .env")
    print("  • 运行时调整: 通过API动态配置")
    
    print("\n📊 性能监控:")
    print("```python")
    print("from python.helpers.intelligent_model_dispatcher import get_model_dispatcher")
    print("dispatcher = get_model_dispatcher()")
    print("report = dispatcher.get_performance_report()")
    print("```")


async def main():
    """主函数"""
    print_banner()
    
    # 检查环境
    has_config = check_environment()
    
    if not has_config:
        create_sample_env_file()
        print("\n❌ 请先配置环境变量后重新运行")
        return
    
    # 初始化模型系统
    print("\n🔧 初始化模型系统...")
    success = initialize_models()
    
    if not success:
        print("❌ 模型系统初始化失败")
        return
    
    # 测试系统
    test_success = await test_model_system()
    
    if test_success:
        print("\n✅ 增强模型系统初始化完成！")
        print_usage_guide()
    else:
        print("\n❌ 系统测试失败，请检查配置")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 初始化已取消")
    except Exception as e:
        print(f"\n❌ 初始化过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
