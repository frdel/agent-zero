"""
自适应上下文管理器
实现按需启动和智能切换机制
"""

import asyncio
import time
import psutil
import threading
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import json

from .unified_context_reasoning_module import (
    get_unified_context_reasoning_module, UnifiedProcessingConfig,
    ProcessingRequest, ProcessingResult, ProcessingStrategy
)
from .infinite_context_engine import ContextProcessingMode
from .intelligent_model_dispatcher import TaskType


class SystemLoadLevel(Enum):
    """系统负载级别"""
    LOW = "low"           # 低负载 < 30%
    MEDIUM = "medium"     # 中等负载 30-70%
    HIGH = "high"         # 高负载 70-90%
    CRITICAL = "critical" # 临界负载 > 90%


class ContextStrategy(Enum):
    """上下文策略"""
    MINIMAL = "minimal"           # 最小化上下文处理
    STANDARD = "standard"         # 标准上下文处理
    ENHANCED = "enhanced"         # 增强上下文处理
    MAXIMUM = "maximum"           # 最大化上下文处理


@dataclass
class SystemMetrics:
    """系统指标"""
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    memory_available_mb: float = 0.0
    active_requests: int = 0
    queue_length: int = 0
    avg_response_time_ms: float = 0.0
    error_rate: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AdaptiveConfig:
    """自适应配置"""
    # 启动阈值
    infinite_context_threshold: int = 8192      # 启动无限上下文的阈值
    reasoning_threshold: int = 5000             # 启动推理的阈值
    parallel_processing_threshold: int = 3      # 启动并行处理的阈值
    
    # 系统资源阈值
    max_cpu_usage: float = 80.0                 # 最大CPU使用率
    max_memory_usage: float = 85.0              # 最大内存使用率
    min_available_memory_mb: float = 1024.0     # 最小可用内存
    
    # 性能阈值
    max_response_time_ms: float = 30000.0       # 最大响应时间
    max_error_rate: float = 0.1                 # 最大错误率
    max_queue_length: int = 10                  # 最大队列长度
    
    # 自适应参数
    adaptation_interval_seconds: float = 30.0   # 自适应间隔
    metrics_history_size: int = 100             # 指标历史大小
    strategy_switch_cooldown_seconds: float = 60.0  # 策略切换冷却时间
    
    # 预测参数
    enable_predictive_scaling: bool = True      # 启用预测性扩展
    prediction_window_minutes: int = 10        # 预测窗口
    load_spike_threshold: float = 2.0          # 负载峰值阈值


class AdaptiveContextManager:
    """自适应上下文管理器"""
    
    def __init__(self, config: AdaptiveConfig):
        self.config = config
        self.unified_module = None
        
        # 系统监控
        self.system_metrics_history: List[SystemMetrics] = []
        self.current_metrics = SystemMetrics()
        self.monitoring_active = False
        self.monitoring_thread = None
        
        # 自适应状态
        self.current_strategy = ContextStrategy.STANDARD
        self.last_strategy_switch = datetime.now()
        self.strategy_switch_history: List[Dict[str, Any]] = []
        
        # 请求队列和处理
        self.request_queue: asyncio.Queue = asyncio.Queue()
        self.active_requests: Dict[str, ProcessingRequest] = {}
        self.processing_workers: List[asyncio.Task] = []
        
        # 性能统计
        self.performance_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "avg_response_time_ms": 0.0,
            "strategy_switches": 0,
            "resource_optimizations": 0
        }
        
        # 预测模型（简化实现）
        self.load_predictor = LoadPredictor() if config.enable_predictive_scaling else None
    
    async def initialize(self):
        """初始化管理器"""
        # 初始化统一模块
        unified_config = UnifiedProcessingConfig()
        self.unified_module = get_unified_context_reasoning_module(unified_config)
        
        # 启动系统监控
        await self.start_monitoring()
        
        # 启动处理工作器
        await self.start_processing_workers()
        
        print("✅ 自适应上下文管理器初始化完成")
    
    async def start_monitoring(self):
        """启动系统监控"""
        if not self.monitoring_active:
            self.monitoring_active = True
            self.monitoring_thread = threading.Thread(
                target=self._monitoring_loop,
                daemon=True
            )
            self.monitoring_thread.start()
    
    def _monitoring_loop(self):
        """监控循环"""
        while self.monitoring_active:
            try:
                # 收集系统指标
                metrics = self._collect_system_metrics()
                self.current_metrics = metrics
                self.system_metrics_history.append(metrics)
                
                # 保持历史记录在合理范围内
                if len(self.system_metrics_history) > self.config.metrics_history_size:
                    self.system_metrics_history = self.system_metrics_history[-self.config.metrics_history_size//2:]
                
                # 检查是否需要调整策略
                asyncio.run_coroutine_threadsafe(
                    self._check_and_adapt_strategy(),
                    asyncio.get_event_loop()
                )
                
                time.sleep(self.config.adaptation_interval_seconds)
                
            except Exception as e:
                print(f"⚠️ 监控循环异常: {e}")
                time.sleep(5)
    
    def _collect_system_metrics(self) -> SystemMetrics:
        """收集系统指标"""
        try:
            cpu_usage = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            memory_usage = memory.percent
            memory_available_mb = memory.available / (1024 * 1024)
            
            return SystemMetrics(
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                memory_available_mb=memory_available_mb,
                active_requests=len(self.active_requests),
                queue_length=self.request_queue.qsize(),
                timestamp=datetime.now()
            )
        except Exception as e:
            print(f"⚠️ 收集系统指标失败: {e}")
            return SystemMetrics()
    
    async def _check_and_adapt_strategy(self):
        """检查并调整策略"""
        if not self._can_switch_strategy():
            return
        
        # 分析当前系统状态
        load_level = self._analyze_system_load()
        optimal_strategy = self._determine_optimal_strategy(load_level)
        
        # 如果需要切换策略
        if optimal_strategy != self.current_strategy:
            await self._switch_strategy(optimal_strategy, f"系统负载: {load_level.value}")
    
    def _can_switch_strategy(self) -> bool:
        """检查是否可以切换策略"""
        cooldown_elapsed = (
            datetime.now() - self.last_strategy_switch
        ).total_seconds() >= self.config.strategy_switch_cooldown_seconds
        
        return cooldown_elapsed
    
    def _analyze_system_load(self) -> SystemLoadLevel:
        """分析系统负载级别"""
        if not self.system_metrics_history:
            return SystemLoadLevel.LOW
        
        recent_metrics = self.system_metrics_history[-5:]  # 最近5个指标
        avg_cpu = sum(m.cpu_usage for m in recent_metrics) / len(recent_metrics)
        avg_memory = sum(m.memory_usage for m in recent_metrics) / len(recent_metrics)
        
        # 综合评估负载级别
        if avg_cpu > 90 or avg_memory > 90:
            return SystemLoadLevel.CRITICAL
        elif avg_cpu > 70 or avg_memory > 70:
            return SystemLoadLevel.HIGH
        elif avg_cpu > 30 or avg_memory > 30:
            return SystemLoadLevel.MEDIUM
        else:
            return SystemLoadLevel.LOW
    
    def _determine_optimal_strategy(self, load_level: SystemLoadLevel) -> ContextStrategy:
        """确定最优策略"""
        current_queue_length = self.request_queue.qsize()
        active_requests = len(self.active_requests)
        
        # 根据负载级别和队列状态确定策略
        if load_level == SystemLoadLevel.CRITICAL:
            return ContextStrategy.MINIMAL
        elif load_level == SystemLoadLevel.HIGH:
            if current_queue_length > 5:
                return ContextStrategy.MINIMAL
            else:
                return ContextStrategy.STANDARD
        elif load_level == SystemLoadLevel.MEDIUM:
            if current_queue_length < 3 and active_requests < 5:
                return ContextStrategy.ENHANCED
            else:
                return ContextStrategy.STANDARD
        else:  # LOW
            if current_queue_length == 0 and active_requests < 3:
                return ContextStrategy.MAXIMUM
            else:
                return ContextStrategy.ENHANCED
    
    async def _switch_strategy(self, new_strategy: ContextStrategy, reason: str):
        """切换策略"""
        old_strategy = self.current_strategy
        self.current_strategy = new_strategy
        self.last_strategy_switch = datetime.now()
        
        # 记录切换历史
        switch_record = {
            "timestamp": self.last_strategy_switch,
            "from_strategy": old_strategy.value,
            "to_strategy": new_strategy.value,
            "reason": reason,
            "system_metrics": self.current_metrics.__dict__.copy()
        }
        self.strategy_switch_history.append(switch_record)
        
        # 保持历史记录在合理范围内
        if len(self.strategy_switch_history) > 100:
            self.strategy_switch_history = self.strategy_switch_history[-50:]
        
        # 更新统计
        self.performance_stats["strategy_switches"] += 1
        
        print(f"🔄 策略切换: {old_strategy.value} → {new_strategy.value} (原因: {reason})")
        
        # 调整处理工作器数量
        await self._adjust_workers(new_strategy)
    
    async def _adjust_workers(self, strategy: ContextStrategy):
        """调整工作器数量"""
        if strategy == ContextStrategy.MINIMAL:
            target_workers = 1
        elif strategy == ContextStrategy.STANDARD:
            target_workers = 2
        elif strategy == ContextStrategy.ENHANCED:
            target_workers = 3
        else:  # MAXIMUM
            target_workers = 4
        
        current_workers = len(self.processing_workers)
        
        if target_workers > current_workers:
            # 增加工作器
            for _ in range(target_workers - current_workers):
                worker = asyncio.create_task(self._processing_worker())
                self.processing_workers.append(worker)
        elif target_workers < current_workers:
            # 减少工作器
            workers_to_remove = current_workers - target_workers
            for _ in range(workers_to_remove):
                if self.processing_workers:
                    worker = self.processing_workers.pop()
                    worker.cancel()
    
    async def start_processing_workers(self):
        """启动处理工作器"""
        # 根据当前策略启动适当数量的工作器
        await self._adjust_workers(self.current_strategy)
    
    async def _processing_worker(self):
        """处理工作器"""
        while True:
            try:
                # 从队列获取请求
                request = await self.request_queue.get()
                
                # 添加到活跃请求
                self.active_requests[request.request_id] = request
                
                # 根据当前策略调整请求
                adjusted_request = self._adjust_request_for_strategy(request)
                
                # 处理请求
                start_time = time.time()
                result = await self.unified_module.process_request(adjusted_request)
                processing_time = (time.time() - start_time) * 1000
                
                # 更新统计
                self._update_processing_stats(result, processing_time)
                
                # 从活跃请求中移除
                self.active_requests.pop(request.request_id, None)
                
                # 标记任务完成
                self.request_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"⚠️ 处理工作器异常: {e}")
                # 从活跃请求中移除
                if 'request' in locals():
                    self.active_requests.pop(request.request_id, None)
                    self.request_queue.task_done()
    
    def _adjust_request_for_strategy(self, request: ProcessingRequest) -> ProcessingRequest:
        """根据策略调整请求"""
        adjusted_request = request
        
        if self.current_strategy == ContextStrategy.MINIMAL:
            # 最小化处理
            adjusted_request.require_reasoning = False
            adjusted_request.require_infinite_context = False
            adjusted_request.processing_strategy = ProcessingStrategy.ADAPTIVE
            adjusted_request.timeout_seconds = min(request.timeout_seconds, 30.0)
            
        elif self.current_strategy == ContextStrategy.STANDARD:
            # 标准处理
            content_length = len(str(request.content))
            adjusted_request.require_infinite_context = content_length > self.config.infinite_context_threshold
            adjusted_request.processing_strategy = ProcessingStrategy.ADAPTIVE
            
        elif self.current_strategy == ContextStrategy.ENHANCED:
            # 增强处理
            content_length = len(str(request.content))
            adjusted_request.require_infinite_context = content_length > self.config.infinite_context_threshold // 2
            adjusted_request.require_reasoning = content_length > self.config.reasoning_threshold
            adjusted_request.processing_strategy = ProcessingStrategy.PARALLEL
            
        else:  # MAXIMUM
            # 最大化处理
            adjusted_request.require_infinite_context = True
            adjusted_request.require_reasoning = True
            adjusted_request.processing_strategy = ProcessingStrategy.PARALLEL
        
        return adjusted_request
    
    def _update_processing_stats(self, result: ProcessingResult, processing_time: float):
        """更新处理统计"""
        self.performance_stats["total_requests"] += 1
        
        if result.success:
            self.performance_stats["successful_requests"] += 1
        else:
            self.performance_stats["failed_requests"] += 1
        
        # 更新平均响应时间
        total_requests = self.performance_stats["total_requests"]
        current_avg = self.performance_stats["avg_response_time_ms"]
        new_avg = (current_avg * (total_requests - 1) + processing_time) / total_requests
        self.performance_stats["avg_response_time_ms"] = new_avg
    
    async def submit_request(self, request: ProcessingRequest) -> str:
        """提交请求"""
        # 检查系统负载
        if self._should_reject_request():
            raise Exception("系统负载过高，请求被拒绝")
        
        # 添加到队列
        await self.request_queue.put(request)
        
        return f"请求 {request.request_id} 已提交到队列"
    
    def _should_reject_request(self) -> bool:
        """检查是否应该拒绝请求"""
        # 检查队列长度
        if self.request_queue.qsize() > self.config.max_queue_length:
            return True
        
        # 检查系统资源
        if (self.current_metrics.cpu_usage > self.config.max_cpu_usage or
            self.current_metrics.memory_usage > self.config.max_memory_usage or
            self.current_metrics.memory_available_mb < self.config.min_available_memory_mb):
            return True
        
        return False
    
    def get_status_report(self) -> Dict[str, Any]:
        """获取状态报告"""
        return {
            "current_strategy": self.current_strategy.value,
            "system_metrics": self.current_metrics.__dict__,
            "performance_stats": self.performance_stats.copy(),
            "queue_status": {
                "queue_length": self.request_queue.qsize(),
                "active_requests": len(self.active_requests),
                "worker_count": len(self.processing_workers)
            },
            "recent_strategy_switches": self.strategy_switch_history[-5:],
            "load_prediction": self.load_predictor.predict() if self.load_predictor else None
        }
    
    async def shutdown(self):
        """关闭管理器"""
        # 停止监控
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        
        # 取消所有工作器
        for worker in self.processing_workers:
            worker.cancel()
        
        # 等待队列清空
        await self.request_queue.join()
        
        print("✅ 自适应上下文管理器已关闭")


class LoadPredictor:
    """负载预测器（简化实现）"""
    
    def __init__(self):
        self.history: List[float] = []
    
    def update(self, load: float):
        """更新负载历史"""
        self.history.append(load)
        if len(self.history) > 100:
            self.history = self.history[-50:]
    
    def predict(self) -> Dict[str, Any]:
        """预测未来负载"""
        if len(self.history) < 5:
            return {"prediction": "insufficient_data"}
        
        # 简单的线性趋势预测
        recent = self.history[-10:]
        trend = (recent[-1] - recent[0]) / len(recent)
        
        predicted_load = recent[-1] + trend * 5  # 预测5个时间点后的负载
        
        return {
            "current_load": recent[-1],
            "predicted_load": max(0, min(100, predicted_load)),
            "trend": "increasing" if trend > 0.1 else "decreasing" if trend < -0.1 else "stable",
            "confidence": min(len(self.history) / 50, 1.0)
        }


# 全局实例
_adaptive_manager = None


async def get_adaptive_context_manager(config: Optional[AdaptiveConfig] = None) -> AdaptiveContextManager:
    """获取自适应上下文管理器实例"""
    global _adaptive_manager
    
    if _adaptive_manager is None:
        if config is None:
            config = AdaptiveConfig()
        _adaptive_manager = AdaptiveContextManager(config)
        await _adaptive_manager.initialize()
    
    return _adaptive_manager


# 便捷函数
async def adaptive_process(
    content: Union[str, List[str]],
    task_type: Optional[TaskType] = None,
    priority: int = 5,
    **kwargs
) -> str:
    """自适应处理函数"""
    manager = await get_adaptive_context_manager()
    
    request = ProcessingRequest(
        request_id=f"adaptive_{int(time.time())}",
        content=content,
        task_type=task_type,
        priority=priority,
        metadata=kwargs
    )
    
    return await manager.submit_request(request)
