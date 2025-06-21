"""
Enhanced Metrics and Monitoring System

Provides comprehensive analytics for:
- Agent performance tracking
- System performance monitoring  
- Usage analytics and patterns
- Cost tracking and optimization
- Real-time dashboard metrics
"""

import asyncio
import time
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from collections import defaultdict, deque
from enum import Enum
import json

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics collected"""
    COUNTER = "counter"        # Incremental values (tasks completed)
    GAUGE = "gauge"           # Current values (queue depth)
    HISTOGRAM = "histogram"   # Distribution of values (response times)
    TIMER = "timer"          # Duration measurements


@dataclass
class MetricPoint:
    """Individual metric data point"""
    timestamp: datetime
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentPerformanceMetrics:
    """Agent-specific performance metrics"""
    agent_id: str
    agent_name: str
    agent_type: str
    environment_id: str
    
    # Task execution metrics
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_processing_time_seconds: float = 0.0
    average_processing_time_seconds: float = 0.0
    
    # Success rate metrics
    success_rate: float = 0.0
    error_rate: float = 0.0
    
    # Task type breakdown
    task_types_handled: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    
    # Quality metrics
    ai_confidence_scores: List[float] = field(default_factory=list)
    average_confidence: float = 0.0
    
    # Recent activity
    last_task_completed: Optional[datetime] = None
    recent_processing_times: deque = field(default_factory=lambda: deque(maxlen=100))
    
    # Cost tracking
    ai_api_calls: int = 0
    estimated_cost_usd: float = 0.0


@dataclass
class SystemPerformanceMetrics:
    """System-wide performance metrics"""
    # Throughput metrics
    total_tasks_processed: int = 0
    tasks_per_minute: float = 0.0
    tasks_per_hour: float = 0.0
    peak_throughput: float = 0.0
    
    # Queue performance
    average_queue_wait_time_seconds: float = 0.0
    max_queue_depth: int = 0
    current_queue_depth: int = 0
    
    # Error tracking
    total_errors: int = 0
    error_rate_percentage: float = 0.0
    error_types: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    
    # Resource utilization
    active_agents: int = 0
    agent_utilization_percentage: float = 0.0
    concurrent_tasks: int = 0
    max_concurrent_tasks: int = 10
    
    # Response time distribution
    response_time_p50: float = 0.0  # 50th percentile
    response_time_p95: float = 0.0  # 95th percentile
    response_time_p99: float = 0.0  # 99th percentile


@dataclass
class UsageAnalytics:
    """Usage patterns and analytics"""
    # Environment activity
    environment_usage: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    most_active_environment: str = ""
    
    # Task patterns
    task_type_distribution: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    most_common_task_type: str = ""
    
    # Time-based patterns
    hourly_task_distribution: Dict[int, int] = field(default_factory=lambda: defaultdict(int))
    daily_task_distribution: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    peak_usage_hour: int = 0
    
    # Priority analysis
    priority_distribution: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    
    # User behavior
    unique_users: int = 0
    user_task_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    most_active_user: str = ""


class MetricsCollector:
    """
    Advanced metrics collection and analytics system
    """
    
    def __init__(self):
        # Storage for metrics
        self.agent_metrics: Dict[str, AgentPerformanceMetrics] = {}
        self.system_metrics = SystemPerformanceMetrics()
        self.usage_analytics = UsageAnalytics()
        
        # Time-series data storage (in-memory for now)
        self.metric_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))
        
        # Real-time tracking
        self.task_start_times: Dict[str, datetime] = {}
        self.recent_task_completions: deque = deque(maxlen=1000)
        self.recent_errors: deque = deque(maxlen=500)
        
        # Background tasks
        self._collection_task = None
        self._running = False
        
        # Configuration
        self.collection_interval_seconds = 30
        self.retention_hours = 24
        
    async def start(self):
        """Start metrics collection"""
        logger.info("Starting enhanced metrics collection...")
        
        self._running = True
        self._collection_task = asyncio.create_task(self._collection_loop())
        
        logger.info("Metrics collection started")
    
    async def stop(self):
        """Stop metrics collection"""
        logger.info("Stopping metrics collection...")
        
        self._running = False
        if self._collection_task:
            self._collection_task.cancel()
            
        logger.info("Metrics collection stopped")
    
    def record_task_started(self, task_id: str, task_data: Dict[str, Any]):
        """Record when a task starts processing"""
        self.task_start_times[task_id] = datetime.now(timezone.utc)
        
        # Update usage analytics
        task_type = task_data.get("task_type", "unknown")
        environment_id = task_data.get("environment_id", "unknown")
        priority = task_data.get("priority", "normal")
        user_id = task_data.get("created_by_agent_id", "unknown")
        
        self.usage_analytics.task_type_distribution[task_type] += 1
        self.usage_analytics.environment_usage[environment_id] += 1
        self.usage_analytics.priority_distribution[priority] += 1
        self.usage_analytics.user_task_counts[user_id] += 1
        
        # Time-based analytics
        now = datetime.now(timezone.utc)
        hour = now.hour
        day = now.strftime("%Y-%m-%d")
        
        self.usage_analytics.hourly_task_distribution[hour] += 1
        self.usage_analytics.daily_task_distribution[day] += 1
        
        # Update system metrics
        self.system_metrics.total_tasks_processed += 1
        self.system_metrics.concurrent_tasks += 1
        
        logger.debug(f"Task {task_id[:8]} started - type: {task_type}, env: {environment_id[:8]}")
    
    def record_task_completed(self, task_id: str, agent_id: str, result_data: Dict[str, Any]):
        """Record successful task completion"""
        completion_time = datetime.now(timezone.utc)
        
        # Calculate processing time
        if task_id in self.task_start_times:
            start_time = self.task_start_times.pop(task_id)
            processing_time = (completion_time - start_time).total_seconds()
        else:
            processing_time = 0
            logger.warning(f"No start time found for task {task_id}")
        
        # Update agent metrics
        if agent_id not in self.agent_metrics:
            self._initialize_agent_metrics(agent_id, result_data)
        
        agent_metric = self.agent_metrics[agent_id]
        agent_metric.tasks_completed += 1
        agent_metric.total_processing_time_seconds += processing_time
        agent_metric.last_task_completed = completion_time
        agent_metric.recent_processing_times.append(processing_time)
        
        # Update task type breakdown
        task_type = result_data.get("task_type", "unknown")
        agent_metric.task_types_handled[task_type] += 1
        
        # Update AI confidence if available
        if "ai_confidence_score" in result_data:
            confidence = result_data["ai_confidence_score"]
            agent_metric.ai_confidence_scores.append(confidence)
        
        # Update derived metrics
        self._update_agent_derived_metrics(agent_metric)
        
        # Record completion for system metrics
        completion_info = {
            "task_id": task_id,
            "agent_id": agent_id,
            "processing_time": processing_time,
            "completed_at": completion_time,
            "task_type": task_type
        }
        self.recent_task_completions.append(completion_info)
        
        # Update system metrics
        self.system_metrics.concurrent_tasks = max(0, self.system_metrics.concurrent_tasks - 1)
        
        # Store time-series data
        self._store_metric_point("task_completion", processing_time, {
            "agent_id": agent_id,
            "task_type": task_type
        })
        
        logger.debug(f"Task {task_id[:8]} completed by {agent_id[:8]} in {processing_time:.2f}s")
    
    def record_task_failed(self, task_id: str, agent_id: Optional[str], error_info: Dict[str, Any]):
        """Record task failure"""
        failure_time = datetime.now(timezone.utc)
        
        # Calculate processing time if available
        processing_time = 0
        if task_id in self.task_start_times:
            start_time = self.task_start_times.pop(task_id)
            processing_time = (failure_time - start_time).total_seconds()
        
        # Update agent metrics if agent was assigned
        if agent_id and agent_id in self.agent_metrics:
            agent_metric = self.agent_metrics[agent_id]
            agent_metric.tasks_failed += 1
            self._update_agent_derived_metrics(agent_metric)
        
        # Record error for system metrics
        error_type = error_info.get("error_type", "unknown")
        self.system_metrics.total_errors += 1
        self.system_metrics.error_types[error_type] += 1
        
        error_record = {
            "task_id": task_id,
            "agent_id": agent_id,
            "error_type": error_type,
            "error_message": error_info.get("error_message", ""),
            "failed_at": failure_time,
            "processing_time": processing_time
        }
        self.recent_errors.append(error_record)
        
        # Update system metrics
        self.system_metrics.concurrent_tasks = max(0, self.system_metrics.concurrent_tasks - 1)
        
        # Store time-series data
        self._store_metric_point("task_failure", 1, {
            "error_type": error_type,
            "agent_id": agent_id or "unknown"
        })
        
        logger.warning(f"Task {task_id[:8]} failed: {error_type}")
    
    def record_ai_api_call(self, agent_id: str, provider: str, model: str, cost_estimate: float = 0.0):
        """Record AI API usage for cost tracking"""
        if agent_id not in self.agent_metrics:
            # Create minimal agent metrics if needed
            self.agent_metrics[agent_id] = AgentPerformanceMetrics(
                agent_id=agent_id,
                agent_name=f"agent_{agent_id[:8]}",
                agent_type="unknown",
                environment_id="unknown"
            )
        
        agent_metric = self.agent_metrics[agent_id]
        agent_metric.ai_api_calls += 1
        agent_metric.estimated_cost_usd += cost_estimate
        
        # Store time-series data
        self._store_metric_point("ai_api_call", cost_estimate, {
            "agent_id": agent_id,
            "provider": provider,
            "model": model
        })
        
        logger.debug(f"AI API call recorded: {provider}/{model} - ${cost_estimate:.4f}")
    
    def update_queue_metrics(self, queue_depth: int, processing_count: int):
        """Update current queue state metrics"""
        self.system_metrics.current_queue_depth = queue_depth
        self.system_metrics.max_queue_depth = max(self.system_metrics.max_queue_depth, queue_depth)
        self.system_metrics.concurrent_tasks = processing_count
        
        # Store time-series data
        self._store_metric_point("queue_depth", queue_depth)
        self._store_metric_point("concurrent_tasks", processing_count)
    
    def _initialize_agent_metrics(self, agent_id: str, context_data: Dict[str, Any]):
        """Initialize metrics for a new agent"""
        self.agent_metrics[agent_id] = AgentPerformanceMetrics(
            agent_id=agent_id,
            agent_name=context_data.get("agent_name", f"agent_{agent_id[:8]}"),
            agent_type=context_data.get("agent_type", "unknown"),
            environment_id=context_data.get("environment_id", "unknown")
        )
    
    def _update_agent_derived_metrics(self, agent_metric: AgentPerformanceMetrics):
        """Update calculated metrics for an agent"""
        total_tasks = agent_metric.tasks_completed + agent_metric.tasks_failed
        
        if total_tasks > 0:
            agent_metric.success_rate = agent_metric.tasks_completed / total_tasks
            agent_metric.error_rate = agent_metric.tasks_failed / total_tasks
        
        if agent_metric.tasks_completed > 0:
            agent_metric.average_processing_time_seconds = (
                agent_metric.total_processing_time_seconds / agent_metric.tasks_completed
            )
        
        if agent_metric.ai_confidence_scores:
            agent_metric.average_confidence = sum(agent_metric.ai_confidence_scores) / len(agent_metric.ai_confidence_scores)
    
    def _store_metric_point(self, metric_name: str, value: float, labels: Dict[str, str] = None):
        """Store a metric point in time-series data"""
        point = MetricPoint(
            timestamp=datetime.now(timezone.utc),
            value=value,
            labels=labels or {}
        )
        self.metric_history[metric_name].append(point)
    
    async def _collection_loop(self):
        """Background loop for metrics collection and computation"""
        while self._running:
            try:
                await self._compute_system_metrics()
                await self._compute_usage_analytics()
                await self._cleanup_old_data()
                await asyncio.sleep(self.collection_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in metrics collection: {e}")
                await asyncio.sleep(60)
    
    async def _compute_system_metrics(self):
        """Compute system-wide metrics"""
        now = datetime.now(timezone.utc)
        
        # Compute throughput metrics
        recent_completions = [
            c for c in self.recent_task_completions
            if (now - c["completed_at"]).total_seconds() <= 300  # Last 5 minutes
        ]
        
        if recent_completions:
            self.system_metrics.tasks_per_minute = len(recent_completions) / 5
            self.system_metrics.tasks_per_hour = self.system_metrics.tasks_per_minute * 60
            
            # Update peak throughput
            self.system_metrics.peak_throughput = max(
                self.system_metrics.peak_throughput,
                self.system_metrics.tasks_per_minute
            )
        
        # Compute error rate
        total_tasks = self.system_metrics.total_tasks_processed
        if total_tasks > 0:
            self.system_metrics.error_rate_percentage = (
                self.system_metrics.total_errors / total_tasks * 100
            )
        
        # Compute response time percentiles
        recent_times = [c["processing_time"] for c in recent_completions]
        if recent_times:
            recent_times.sort()
            n = len(recent_times)
            self.system_metrics.response_time_p50 = recent_times[int(n * 0.5)]
            self.system_metrics.response_time_p95 = recent_times[int(n * 0.95)]
            self.system_metrics.response_time_p99 = recent_times[int(n * 0.99)]
        
        # Compute agent utilization
        active_agents = len([a for a in self.agent_metrics.values() if a.tasks_completed > 0])
        self.system_metrics.active_agents = active_agents
        
        if self.system_metrics.max_concurrent_tasks > 0:
            self.system_metrics.agent_utilization_percentage = (
                self.system_metrics.concurrent_tasks / self.system_metrics.max_concurrent_tasks * 100
            )
    
    async def _compute_usage_analytics(self):
        """Compute usage patterns and analytics"""
        # Find most active environment
        if self.usage_analytics.environment_usage:
            self.usage_analytics.most_active_environment = max(
                self.usage_analytics.environment_usage.items(),
                key=lambda x: x[1]
            )[0]
        
        # Find most common task type
        if self.usage_analytics.task_type_distribution:
            self.usage_analytics.most_common_task_type = max(
                self.usage_analytics.task_type_distribution.items(),
                key=lambda x: x[1]
            )[0]
        
        # Find peak usage hour
        if self.usage_analytics.hourly_task_distribution:
            self.usage_analytics.peak_usage_hour = max(
                self.usage_analytics.hourly_task_distribution.items(),
                key=lambda x: x[1]
            )[0]
        
        # Find most active user
        if self.usage_analytics.user_task_counts:
            self.usage_analytics.most_active_user = max(
                self.usage_analytics.user_task_counts.items(),
                key=lambda x: x[1]
            )[0]
        
        # Count unique users
        self.usage_analytics.unique_users = len(self.usage_analytics.user_task_counts)
    
    async def _cleanup_old_data(self):
        """Clean up old metric data"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.retention_hours)
        
        # Clean up recent completions
        self.recent_task_completions = deque([
            c for c in self.recent_task_completions
            if c["completed_at"] > cutoff_time
        ], maxlen=1000)
        
        # Clean up recent errors
        self.recent_errors = deque([
            e for e in self.recent_errors
            if e["failed_at"] > cutoff_time
        ], maxlen=500)
        
        # Clean up time-series data
        for metric_name, points in self.metric_history.items():
            self.metric_history[metric_name] = deque([
                p for p in points if p.timestamp > cutoff_time
            ], maxlen=10000)
    
    def get_comprehensive_metrics(self) -> Dict[str, Any]:
        """Get all metrics in a comprehensive report"""
        return {
            "system_performance": {
                "throughput": {
                    "total_tasks_processed": self.system_metrics.total_tasks_processed,
                    "tasks_per_minute": round(self.system_metrics.tasks_per_minute, 2),
                    "tasks_per_hour": round(self.system_metrics.tasks_per_hour, 2),
                    "peak_throughput": round(self.system_metrics.peak_throughput, 2)
                },
                "quality": {
                    "error_rate_percentage": round(self.system_metrics.error_rate_percentage, 2),
                    "total_errors": self.system_metrics.total_errors,
                    "error_breakdown": dict(self.system_metrics.error_types)
                },
                "performance": {
                    "response_time_p50": round(self.system_metrics.response_time_p50, 2),
                    "response_time_p95": round(self.system_metrics.response_time_p95, 2),
                    "response_time_p99": round(self.system_metrics.response_time_p99, 2),
                    "current_queue_depth": self.system_metrics.current_queue_depth,
                    "max_queue_depth": self.system_metrics.max_queue_depth
                },
                "resources": {
                    "active_agents": self.system_metrics.active_agents,
                    "concurrent_tasks": self.system_metrics.concurrent_tasks,
                    "max_concurrent_tasks": self.system_metrics.max_concurrent_tasks,
                    "utilization_percentage": round(self.system_metrics.agent_utilization_percentage, 1)
                }
            },
            "agent_performance": {
                agent_id: {
                    "basic_info": {
                        "agent_name": metrics.agent_name,
                        "agent_type": metrics.agent_type,
                        "environment_id": metrics.environment_id
                    },
                    "task_stats": {
                        "tasks_completed": metrics.tasks_completed,
                        "tasks_failed": metrics.tasks_failed,
                        "success_rate": round(metrics.success_rate, 3),
                        "average_processing_time": round(metrics.average_processing_time_seconds, 2)
                    },
                    "quality": {
                        "average_confidence": round(metrics.average_confidence, 3),
                        "task_types_handled": dict(metrics.task_types_handled)
                    },
                    "cost": {
                        "ai_api_calls": metrics.ai_api_calls,
                        "estimated_cost_usd": round(metrics.estimated_cost_usd, 4)
                    }
                }
                for agent_id, metrics in self.agent_metrics.items()
            },
            "usage_analytics": {
                "patterns": {
                    "most_active_environment": self.usage_analytics.most_active_environment,
                    "most_common_task_type": self.usage_analytics.most_common_task_type,
                    "peak_usage_hour": self.usage_analytics.peak_usage_hour,
                    "unique_users": self.usage_analytics.unique_users
                },
                "distributions": {
                    "task_types": dict(self.usage_analytics.task_type_distribution),
                    "environments": dict(self.usage_analytics.environment_usage),
                    "priorities": dict(self.usage_analytics.priority_distribution),
                    "hourly_usage": dict(self.usage_analytics.hourly_task_distribution)
                }
            },
            "metadata": {
                "collection_interval_seconds": self.collection_interval_seconds,
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "retention_hours": self.retention_hours
            }
        }


# Global metrics collector instance
metrics_collector = MetricsCollector()