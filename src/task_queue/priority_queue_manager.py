"""
Advanced Task Prioritization and Queue Management System

Provides intelligent task queuing with:
- Priority-based routing (critical, high, normal, low)
- Resource-aware scheduling
- Queue analytics and monitoring
- Workload balancing across agents
- Dynamic priority adjustment
"""

import asyncio
import heapq
import time
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    """Task priority levels"""
    CRITICAL = 1    # Emergency tasks, process immediately
    HIGH = 2        # Important tasks, process next
    NORMAL = 3      # Standard tasks, normal queue
    LOW = 4         # Background tasks, process when idle


@dataclass
class QueuedTask:
    """Task wrapper for priority queue"""
    task_id: str
    task_data: Dict[str, Any]
    priority: TaskPriority
    environment_id: str
    created_at: datetime
    estimated_duration: Optional[int] = None  # minutes
    deadline: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    dependencies: List[str] = field(default_factory=list)
    
    # Internal fields for queue management
    queue_entry_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    priority_score: float = field(init=False)
    
    def __post_init__(self):
        """Calculate dynamic priority score"""
        self.priority_score = self._calculate_priority_score()
    
    def _calculate_priority_score(self) -> float:
        """
        Calculate dynamic priority score considering:
        - Base priority level
        - Age in queue (older tasks get higher priority)
        - Deadline urgency
        - Retry attempts
        """
        base_score = self.priority.value * 1000
        
        # Age factor: older tasks get priority boost
        age_minutes = (datetime.now(timezone.utc) - self.queue_entry_time).total_seconds() / 60
        age_boost = min(age_minutes * 2, 500)  # Cap at 500 points
        
        # Deadline urgency factor
        deadline_penalty = 0
        if self.deadline:
            time_to_deadline = (self.deadline - datetime.now(timezone.utc)).total_seconds() / 60
            if time_to_deadline < 60:  # Less than 1 hour
                deadline_penalty = -1000  # Urgent!
            elif time_to_deadline < 240:  # Less than 4 hours
                deadline_penalty = -500
        
        # Retry penalty (failed tasks get lower priority)
        retry_penalty = self.retry_count * 100
        
        return base_score - age_boost + deadline_penalty + retry_penalty
    
    def update_priority_score(self):
        """Recalculate priority score (for dynamic re-prioritization)"""
        self.priority_score = self._calculate_priority_score()
    
    def __lt__(self, other):
        """Comparison for heapq (lower score = higher priority)"""
        return self.priority_score < other.priority_score


@dataclass
class QueueMetrics:
    """Queue performance metrics"""
    total_tasks_processed: int = 0
    average_wait_time_minutes: float = 0.0
    average_processing_time_minutes: float = 0.0
    current_queue_depth: int = 0
    tasks_by_priority: Dict[TaskPriority, int] = field(default_factory=lambda: defaultdict(int))
    environment_queue_depths: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    agent_workload: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class PriorityQueueManager:
    """
    Advanced task queue manager with priority-based routing and analytics
    """
    
    def __init__(self):
        self.task_queue: List[QueuedTask] = []  # heapq-managed priority queue
        self.processing_tasks: Dict[str, QueuedTask] = {}  # Currently processing
        self.completed_tasks: deque = deque(maxlen=1000)  # Recent completions for metrics
        self.failed_tasks: deque = deque(maxlen=500)  # Recent failures
        
        # Queue management
        self.queue_lock = asyncio.Lock()
        self.max_concurrent_tasks = 10
        self.queue_metrics = QueueMetrics()
        
        # Environment-specific settings
        self.environment_limits: Dict[str, int] = {}  # Max concurrent per environment
        self.environment_queues: Dict[str, List[QueuedTask]] = defaultdict(list)
        
        # Background tasks
        self._queue_maintenance_task = None
        self._metrics_update_task = None
        
    async def start(self):
        """Start queue management background tasks"""
        logger.info("Starting priority queue manager...")
        
        self._queue_maintenance_task = asyncio.create_task(self._queue_maintenance_loop())
        self._metrics_update_task = asyncio.create_task(self._metrics_update_loop())
        
        logger.info("Priority queue manager started")
    
    async def stop(self):
        """Stop queue management background tasks"""
        logger.info("Stopping priority queue manager...")
        
        if self._queue_maintenance_task:
            self._queue_maintenance_task.cancel()
        if self._metrics_update_task:
            self._metrics_update_task.cancel()
            
        logger.info("Priority queue manager stopped")
    
    async def enqueue_task(self, task_data: Dict[str, Any]) -> str:
        """
        Add task to priority queue
        
        Args:
            task_data: Task information including priority, environment_id, etc.
            
        Returns:
            task_id: Unique identifier for the queued task
        """
        async with self.queue_lock:
            # Parse priority
            priority_str = task_data.get("priority", "normal").lower()
            priority_map = {
                "critical": TaskPriority.CRITICAL,
                "high": TaskPriority.HIGH,
                "normal": TaskPriority.NORMAL,
                "low": TaskPriority.LOW
            }
            priority = priority_map.get(priority_str, TaskPriority.NORMAL)
            
            # Parse deadline
            deadline = None
            if task_data.get("deadline"):
                try:
                    deadline = datetime.fromisoformat(task_data["deadline"].replace("Z", "+00:00"))
                except:
                    logger.warning(f"Invalid deadline format: {task_data.get('deadline')}")
            
            # Parse created_at timestamp
            created_at = datetime.now(timezone.utc)
            if task_data.get("created_at"):
                try:
                    created_at = datetime.fromisoformat(task_data["created_at"].replace("Z", "+00:00"))
                except:
                    logger.warning(f"Invalid created_at format: {task_data.get('created_at')}")
            
            # Create queued task
            queued_task = QueuedTask(
                task_id=task_data["id"],
                task_data=task_data,
                priority=priority,
                environment_id=task_data["environment_id"],
                created_at=created_at,
                estimated_duration=task_data.get("estimated_duration_minutes"),
                deadline=deadline,
                max_retries=task_data.get("max_retries", 3)
            )
            
            # Add to priority queue
            heapq.heappush(self.task_queue, queued_task)
            
            # Update metrics
            self.queue_metrics.current_queue_depth = len(self.task_queue)
            self.queue_metrics.tasks_by_priority[priority] += 1
            self.queue_metrics.environment_queue_depths[queued_task.environment_id] += 1
            
            logger.info(f"Task {task_data['id'][:8]} queued with {priority.name} priority")
            logger.debug(f"Queue depth: {len(self.task_queue)}, Priority distribution: {dict(self.queue_metrics.tasks_by_priority)}")
            
            return queued_task.task_id
    
    async def get_next_task(self, agent_capabilities: Optional[Dict[str, Any]] = None) -> Optional[QueuedTask]:
        """
        Get next highest priority task from queue
        
        Args:
            agent_capabilities: Optional agent capabilities for task matching
            
        Returns:
            QueuedTask or None if queue is empty or no suitable tasks
        """
        async with self.queue_lock:
            if not self.task_queue:
                return None
            
            # Check if we're at max concurrent tasks
            if len(self.processing_tasks) >= self.max_concurrent_tasks:
                logger.debug(f"Max concurrent tasks reached: {len(self.processing_tasks)}/{self.max_concurrent_tasks}")
                return None
            
            # Find the highest priority task that can be processed
            available_tasks = []
            
            # Temporarily extract all tasks to find the best match
            temp_queue = []
            while self.task_queue:
                task = heapq.heappop(self.task_queue)
                
                # Check environment limits
                env_processing = sum(1 for t in self.processing_tasks.values() 
                                   if t.environment_id == task.environment_id)
                env_limit = self.environment_limits.get(task.environment_id, 3)  # Default 3 per env
                
                if env_processing < env_limit:
                    # Check agent capability matching if provided
                    if agent_capabilities:
                        if self._task_matches_agent(task, agent_capabilities):
                            available_tasks.append(task)
                        else:
                            temp_queue.append(task)
                    else:
                        available_tasks.append(task)
                else:
                    temp_queue.append(task)
            
            # Restore queue with remaining tasks
            for task in temp_queue:
                heapq.heappush(self.task_queue, task)
            
            if not available_tasks:
                logger.debug("No available tasks matching current constraints")
                return None
            
            # Get highest priority available task
            selected_task = min(available_tasks, key=lambda t: t.priority_score)
            
            # Put non-selected tasks back in queue
            for task in available_tasks:
                if task != selected_task:
                    heapq.heappush(self.task_queue, task)
            
            # Move to processing
            self.processing_tasks[selected_task.task_id] = selected_task
            
            # Update metrics
            self.queue_metrics.current_queue_depth = len(self.task_queue)
            self.queue_metrics.environment_queue_depths[selected_task.environment_id] -= 1
            
            wait_time = (datetime.now(timezone.utc) - selected_task.queue_entry_time).total_seconds() / 60
            logger.info(f"Task {selected_task.task_id[:8]} dequeued after {wait_time:.1f}min wait")
            
            return selected_task
    
    def _task_matches_agent(self, task: QueuedTask, agent_capabilities: Dict[str, Any]) -> bool:
        """Check if task requirements match agent capabilities"""
        task_type = task.task_data.get("task_type", "")
        agent_types = agent_capabilities.get("supported_task_types", [])
        
        return task_type in agent_types or not agent_types  # If no types specified, accept all
    
    async def mark_task_completed(self, task_id: str, result: Dict[str, Any]):
        """Mark task as completed and update metrics"""
        async with self.queue_lock:
            if task_id not in self.processing_tasks:
                logger.warning(f"Task {task_id} not found in processing tasks")
                return
            
            task = self.processing_tasks.pop(task_id)
            
            # Calculate processing time
            processing_time = (datetime.now(timezone.utc) - task.queue_entry_time).total_seconds() / 60
            
            # Store completion info
            completion_info = {
                "task": task,
                "completed_at": datetime.now(timezone.utc),
                "processing_time_minutes": processing_time,
                "result": result
            }
            self.completed_tasks.append(completion_info)
            
            # Update metrics
            self._update_completion_metrics(completion_info)
            
            logger.info(f"Task {task_id[:8]} completed in {processing_time:.1f}min")
    
    async def mark_task_failed(self, task_id: str, error: str, retry: bool = True):
        """Mark task as failed and optionally retry"""
        async with self.queue_lock:
            if task_id not in self.processing_tasks:
                logger.warning(f"Task {task_id} not found in processing tasks")
                return
            
            task = self.processing_tasks.pop(task_id)
            task.retry_count += 1
            
            failure_info = {
                "task": task,
                "failed_at": datetime.now(timezone.utc),
                "error": error,
                "retry_count": task.retry_count
            }
            self.failed_tasks.append(failure_info)
            
            # Retry if within limits
            if retry and task.retry_count <= task.max_retries:
                # Lower priority for retries and re-queue
                if task.priority != TaskPriority.LOW:
                    task.priority = TaskPriority(min(task.priority.value + 1, TaskPriority.LOW.value))
                
                task.update_priority_score()
                heapq.heappush(self.task_queue, task)
                
                logger.warning(f"Task {task_id[:8]} failed (retry {task.retry_count}/{task.max_retries}): {error}")
            else:
                logger.error(f"Task {task_id[:8]} permanently failed after {task.retry_count} attempts: {error}")
    
    def _update_completion_metrics(self, completion_info: Dict[str, Any]):
        """Update queue performance metrics"""
        self.queue_metrics.total_tasks_processed += 1
        
        # Update average processing time
        new_time = completion_info["processing_time_minutes"]
        if self.queue_metrics.average_processing_time_minutes == 0:
            self.queue_metrics.average_processing_time_minutes = new_time
        else:
            # Exponential moving average
            alpha = 0.1
            self.queue_metrics.average_processing_time_minutes = (
                alpha * new_time + (1 - alpha) * self.queue_metrics.average_processing_time_minutes
            )
    
    async def _queue_maintenance_loop(self):
        """Background task for queue maintenance"""
        while True:
            try:
                await self._rebalance_queue()
                await asyncio.sleep(30)  # Run every 30 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in queue maintenance: {e}")
                await asyncio.sleep(60)
    
    async def _rebalance_queue(self):
        """Rebalance queue priorities and clean up stale tasks"""
        async with self.queue_lock:
            if not self.task_queue:
                return
            
            # Update priority scores for all queued tasks (aging factor)
            temp_tasks = []
            while self.task_queue:
                task = heapq.heappop(self.task_queue)
                task.update_priority_score()
                temp_tasks.append(task)
            
            # Rebuild heap with updated priorities
            for task in temp_tasks:
                heapq.heappush(self.task_queue, task)
            
            logger.debug(f"Queue rebalanced: {len(self.task_queue)} tasks")
    
    async def _metrics_update_loop(self):
        """Background task for metrics updates"""
        while True:
            try:
                await self._update_metrics()
                await asyncio.sleep(60)  # Update every minute
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error updating metrics: {e}")
                await asyncio.sleep(60)
    
    async def _update_metrics(self):
        """Update queue metrics"""
        self.queue_metrics.last_updated = datetime.now(timezone.utc)
        self.queue_metrics.current_queue_depth = len(self.task_queue)
        
        # Calculate wait times from recent completions
        if self.completed_tasks:
            recent_wait_times = []
            for completion in list(self.completed_tasks)[-100:]:  # Last 100 tasks
                task = completion["task"]
                wait_time = (completion["completed_at"] - task.queue_entry_time).total_seconds() / 60
                recent_wait_times.append(wait_time)
            
            if recent_wait_times:
                self.queue_metrics.average_wait_time_minutes = sum(recent_wait_times) / len(recent_wait_times)
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status and metrics"""
        return {
            "queue_depth": len(self.task_queue),
            "processing_count": len(self.processing_tasks),
            "metrics": {
                "total_processed": self.queue_metrics.total_tasks_processed,
                "avg_wait_time_min": round(self.queue_metrics.average_wait_time_minutes, 2),
                "avg_processing_time_min": round(self.queue_metrics.average_processing_time_minutes, 2),
                "tasks_by_priority": {p.name: count for p, count in self.queue_metrics.tasks_by_priority.items()},
                "environment_depths": dict(self.queue_metrics.environment_queue_depths),
                "last_updated": self.queue_metrics.last_updated.isoformat()
            },
            "currently_processing": [
                {
                    "task_id": task.task_id,
                    "priority": task.priority.name,
                    "environment_id": task.environment_id,
                    "started_at": task.queue_entry_time.isoformat()
                }
                for task in self.processing_tasks.values()
            ]
        }


# Global priority queue manager instance
priority_queue_manager = PriorityQueueManager()