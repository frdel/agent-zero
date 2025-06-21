"""
模型配置初始化器
自动配置和注册各种模型提供商
"""

import os
import json
from typing import Dict, Any, List
from python.helpers import dotenv

from .enhanced_model_manager import (
    get_model_manager, ModelConfig, ModelProvider, ModelCapability, TaskType
)


class ModelConfigInitializer:
    """模型配置初始化器"""
    
    def __init__(self):
        self.model_manager = get_model_manager()
        self.config_loaded = False
    
    def initialize_from_env(self) -> bool:
        """从环境变量初始化模型配置"""
        try:
            print("🚀 开始从环境变量初始化模型配置...")
            
            # 加载环境变量
            dotenv.load_dotenv()
            
            # 初始化各种模型提供商
            self._init_openai_compatible_models()
            self._init_vllm_models()
            self._init_llamacpp_models()
            self._init_default_models()
            
            # 保存配置
            self._save_model_config()
            
            self.config_loaded = True
            print("✅ 模型配置初始化完成")
            
            # 打印配置摘要
            self._print_config_summary()
            
            return True
            
        except Exception as e:
            print(f"❌ 模型配置初始化失败: {e}")
            return False
    
    def _init_openai_compatible_models(self):
        """初始化OpenAI兼容模型"""
        # 检查OpenAI兼容端点
        openai_endpoint = os.getenv("OPENAI_ENDPOINT")
        openai_api_key = os.getenv("OPENAI_ENDPOINT_API_KEY")
        
        if openai_endpoint and openai_api_key:
            print(f"🔗 配置OpenAI兼容端点: {openai_endpoint}")
            
            # 通用云端大模型配置
            cloud_large_model = ModelConfig(
                provider=ModelProvider.OPENAI_COMPATIBLE,
                name="gpt-4-turbo",  # 可以根据实际端点调整
                endpoint=openai_endpoint,
                api_key=openai_api_key,
                ctx_length=128000,
                capabilities=[
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.CODE_GENERATION,
                    ModelCapability.REASONING,
                    ModelCapability.CHAT,
                    ModelCapability.FUNCTION_CALLING
                ],
                vision=True,  # 假设支持视觉
                function_calling=True,
                speed_score=7,
                quality_score=9,
                cost_score=3,  # 云端模型成本较高
                priority=8
            )
            
            self.model_manager.register_model("cloud_large_model", cloud_large_model)
            
            # 多模态模型（用于浏览器任务）
            multimodal_model = ModelConfig(
                provider=ModelProvider.OPENAI_COMPATIBLE,
                name="gpt-4-vision-preview",
                endpoint=openai_endpoint,
                api_key=openai_api_key,
                ctx_length=128000,
                capabilities=[
                    ModelCapability.VISION,
                    ModelCapability.MULTIMODAL,
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.REASONING
                ],
                vision=True,
                speed_score=6,
                quality_score=9,
                cost_score=2,  # 多模态模型成本更高
                priority=9  # 浏览器任务的首选
            )
            
            self.model_manager.register_model("multimodal_browser_model", multimodal_model)
    
    def _init_vllm_models(self):
        """初始化vLLM本地模型"""
        # 检查vLLM配置
        vllm_endpoint = os.getenv("VLLM_ENDPOINT", "http://localhost:8000")
        vllm_model_name = os.getenv("VLLM_MODEL_NAME", "local-model")
        
        print(f"🏠 配置vLLM本地模型: {vllm_endpoint}")
        
        # 本地写作模型（小型快速）
        local_writing_model = ModelConfig(
            provider=ModelProvider.VLLM,
            name=vllm_model_name,
            endpoint=vllm_endpoint,
            ctx_length=8192,
            capabilities=[
                ModelCapability.TEXT_GENERATION,
                ModelCapability.CREATIVE_WRITING,
                ModelCapability.CHAT
            ],
            speed_score=9,  # 本地模型速度快
            quality_score=6,  # 质量中等
            cost_score=10,  # 本地模型成本最低
            priority=7,
            kwargs={
                "top_p": 0.9,
                "top_k": 40,
                "repetition_penalty": 1.1
            }
        )
        
        self.model_manager.register_model("local_writing_model", local_writing_model)
        
        # 本地代码模型（如果有专门的代码模型）
        code_model_name = os.getenv("VLLM_CODE_MODEL_NAME")
        if code_model_name:
            local_code_model = ModelConfig(
                provider=ModelProvider.VLLM,
                name=code_model_name,
                endpoint=vllm_endpoint,
                ctx_length=16384,
                capabilities=[
                    ModelCapability.CODE_GENERATION,
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.REASONING
                ],
                speed_score=8,
                quality_score=7,
                cost_score=10,
                priority=6
            )
            
            self.model_manager.register_model("local_code_model", local_code_model)
    
    def _init_llamacpp_models(self):
        """初始化LlamaCpp GGUF模型"""
        # 检查LlamaCpp配置
        llamacpp_endpoint = os.getenv("LLAMACPP_ENDPOINT", "http://localhost:8080")
        llamacpp_model_path = os.getenv("LLAMACPP_MODEL_PATH")
        
        print(f"🦙 配置LlamaCpp模型: {llamacpp_endpoint}")
        
        # 本地GGUF模型
        local_gguf_model = ModelConfig(
            provider=ModelProvider.LLAMACPP,
            name="local-gguf-model",
            endpoint=llamacpp_endpoint,
            model_path=llamacpp_model_path,
            ctx_length=4096,
            capabilities=[
                ModelCapability.TEXT_GENERATION,
                ModelCapability.CHAT,
                ModelCapability.EMBEDDING
            ],
            speed_score=7,
            quality_score=6,
            cost_score=10,  # 本地模型成本最低
            priority=5,
            threads=int(os.getenv("LLAMACPP_THREADS", "4")),
            gpu_layers=int(os.getenv("LLAMACPP_GPU_LAYERS", "0")),
            kwargs={
                "top_k": 40,
                "top_p": 0.9,
                "repeat_penalty": 1.1,
                "temperature": 0.7
            }
        )
        
        self.model_manager.register_model("local_gguf_model", local_gguf_model)
        
        # 嵌入模型（如果支持）
        if os.getenv("LLAMACPP_EMBEDDING_MODEL"):
            embedding_model = ModelConfig(
                provider=ModelProvider.LLAMACPP,
                name="embedding-model",
                endpoint=llamacpp_endpoint,
                ctx_length=512,
                capabilities=[ModelCapability.EMBEDDING],
                speed_score=8,
                quality_score=7,
                cost_score=10,
                priority=8
            )
            
            self.model_manager.register_model("local_embedding_model", embedding_model)
    
    def _init_default_models(self):
        """初始化默认模型配置"""
        # 如果没有配置任何外部模型，使用默认配置
        if len(self.model_manager.models) == 0:
            print("⚠️ 未检测到外部模型配置，使用默认模型")
            
            # 默认OpenAI模型（需要API密钥）
            openai_api_key = os.getenv("OPENAI_API_KEY")
            if openai_api_key:
                default_openai = ModelConfig(
                    provider=ModelProvider.OPENAI,
                    name="gpt-3.5-turbo",
                    api_key=openai_api_key,
                    ctx_length=16385,
                    capabilities=[
                        ModelCapability.TEXT_GENERATION,
                        ModelCapability.CHAT,
                        ModelCapability.CODE_GENERATION
                    ],
                    speed_score=8,
                    quality_score=7,
                    cost_score=6,
                    priority=6
                )
                
                self.model_manager.register_model("default_openai", default_openai)
        
        # 确保有工具模型
        self._ensure_utility_model()
    
    def _ensure_utility_model(self):
        """确保有工具模型"""
        utility_models = self.model_manager.list_models_by_task(TaskType.UTILITY)
        
        if not utility_models:
            # 选择一个快速便宜的模型作为工具模型
            all_models = list(self.model_manager.models.keys())
            if all_models:
                # 选择速度和成本评分最高的模型
                best_utility_model = None
                best_score = 0
                
                for model_id in all_models:
                    config = self.model_manager.get_model_config(model_id)
                    score = config.speed_score + config.cost_score
                    if score > best_score:
                        best_score = score
                        best_utility_model = model_id
                
                if best_utility_model:
                    # 将该模型添加到工具任务映射
                    self.model_manager.task_model_mapping[TaskType.UTILITY].append(best_utility_model)
                    print(f"🔧 设置工具模型: {best_utility_model}")
    
    def _save_model_config(self):
        """保存模型配置到文件"""
        try:
            config_data = self.model_manager.export_config()
            
            # 确保配置目录存在
            config_dir = "config"
            os.makedirs(config_dir, exist_ok=True)
            
            # 保存配置
            config_file = os.path.join(config_dir, "model_config.json")
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            print(f"💾 模型配置已保存到: {config_file}")
            
        except Exception as e:
            print(f"⚠️ 保存模型配置失败: {e}")
    
    def _print_config_summary(self):
        """打印配置摘要"""
        stats = self.model_manager.get_model_statistics()
        
        print("\n" + "="*50)
        print("📊 模型配置摘要")
        print("="*50)
        print(f"总模型数: {stats['total_models']}")
        print(f"启用模型数: {stats['enabled_models']}")
        
        print("\n📡 提供商分布:")
        for provider, count in stats['provider_distribution'].items():
            print(f"  - {provider}: {count}个模型")
        
        print("\n🎯 能力分布:")
        for capability, count in stats['capability_distribution'].items():
            print(f"  - {capability}: {count}个模型")
        
        print("\n🔧 任务模型映射:")
        for task_type, model_list in self.model_manager.task_model_mapping.items():
            if model_list:
                print(f"  - {task_type.value}: {len(model_list)}个模型")
        
        print("="*50)
    
    def load_config_from_file(self, config_file: str) -> bool:
        """从文件加载配置"""
        try:
            if not os.path.exists(config_file):
                print(f"⚠️ 配置文件不存在: {config_file}")
                return False
            
            with open(config_file, "r", encoding="utf-8") as f:
                config_data = json.load(f)
            
            success = self.model_manager.import_config(config_data)
            if success:
                self.config_loaded = True
                print(f"✅ 从文件加载配置成功: {config_file}")
                self._print_config_summary()
            
            return success
            
        except Exception as e:
            print(f"❌ 从文件加载配置失败: {e}")
            return False
    
    def create_sample_config(self) -> Dict[str, Any]:
        """创建示例配置"""
        return {
            "models": {
                "cloud_gpt4": {
                    "provider": "openai_compatible",
                    "name": "gpt-4-turbo",
                    "endpoint": "https://api.openai.com",
                    "capabilities": ["text_generation", "code_generation", "reasoning", "chat"],
                    "vision": True,
                    "function_calling": True,
                    "speed_score": 7,
                    "quality_score": 9,
                    "cost_score": 3,
                    "priority": 8,
                    "enabled": True
                },
                "local_vllm": {
                    "provider": "vllm",
                    "name": "llama-2-7b-chat",
                    "endpoint": "http://localhost:8000",
                    "capabilities": ["text_generation", "creative_writing", "chat"],
                    "speed_score": 9,
                    "quality_score": 6,
                    "cost_score": 10,
                    "priority": 7,
                    "enabled": True
                },
                "local_llamacpp": {
                    "provider": "llamacpp",
                    "name": "local-gguf-model",
                    "endpoint": "http://localhost:8080",
                    "capabilities": ["text_generation", "chat", "embedding"],
                    "speed_score": 7,
                    "quality_score": 6,
                    "cost_score": 10,
                    "priority": 5,
                    "enabled": True
                }
            },
            "task_mappings": {
                "browsing": ["cloud_gpt4"],
                "writing": ["local_vllm", "local_llamacpp"],
                "coding": ["cloud_gpt4", "local_vllm"],
                "analysis": ["cloud_gpt4"],
                "reasoning": ["cloud_gpt4"],
                "creative": ["local_vllm"],
                "chat": ["local_vllm", "cloud_gpt4"],
                "embedding": ["local_llamacpp"],
                "utility": ["local_llamacpp", "local_vllm"]
            }
        }


# 全局初始化器实例
_initializer = ModelConfigInitializer()


def get_model_initializer() -> ModelConfigInitializer:
    """获取模型初始化器实例"""
    return _initializer


def initialize_models() -> bool:
    """初始化模型配置"""
    return _initializer.initialize_from_env()


def load_model_config(config_file: str = "config/model_config.json") -> bool:
    """加载模型配置"""
    return _initializer.load_config_from_file(config_file)
