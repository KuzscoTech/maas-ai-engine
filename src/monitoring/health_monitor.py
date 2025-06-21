"""
Health monitoring system for MAAS AI Engine
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum

import redis.asyncio as redis
from google.adk import Agent

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status enumeration"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class ComponentHealth:
    """Health status of a component"""
    name: str
    status: HealthStatus
    last_check: datetime
    response_time_ms: Optional[float] = None
    error_message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


@dataclass
class SystemHealth:
    """Overall system health"""
    status: HealthStatus
    timestamp: datetime
    uptime_seconds: float
    components: List[ComponentHealth]
    metrics: Dict[str, Any]


class HealthMonitor:
    """Comprehensive health monitoring for AI Engine"""
    
    def __init__(self, redis_url: str = "redis://:devpassword@localhost:6379/1"):
        self.redis_url = redis_url
        self.redis_client: Optional[redis.Redis] = None
        self.start_time = time.time()
        self.task_count = 0
        self.error_count = 0
        self.last_task_time: Optional[datetime] = None
        
    async def get_system_health(self) -> SystemHealth:
        """Get comprehensive system health status"""
        components = []
        overall_status = HealthStatus.HEALTHY
        
        # Check Redis connectivity
        redis_health = await self._check_redis_health()
        components.append(redis_health)
        if redis_health.status != HealthStatus.HEALTHY:
            overall_status = HealthStatus.DEGRADED
        
        # Check Google ADK availability
        adk_health = await self._check_google_adk_health()
        components.append(adk_health)
        if adk_health.status != HealthStatus.HEALTHY:
            overall_status = HealthStatus.DEGRADED
        
        # Check message processing
        processing_health = await self._check_message_processing_health()
        components.append(processing_health)
        if processing_health.status != HealthStatus.HEALTHY:
            overall_status = HealthStatus.DEGRADED
        
        # Calculate metrics
        uptime = time.time() - self.start_time
        error_rate = (self.error_count / max(self.task_count, 1)) * 100
        
        metrics = {
            "uptime_seconds": uptime,
            "total_tasks_processed": self.task_count,
            "total_errors": self.error_count,
            "error_rate_percentage": error_rate,
            "last_task_processed": self.last_task_time.isoformat() if self.last_task_time else None,
            "tasks_per_minute": (self.task_count / max(uptime / 60, 1)) if uptime > 0 else 0
        }
        
        return SystemHealth(
            status=overall_status,
            timestamp=datetime.now(timezone.utc),
            uptime_seconds=uptime,
            components=components,
            metrics=metrics
        )
    
    async def _check_redis_health(self) -> ComponentHealth:
        """Check Redis connectivity and performance"""
        start_time = time.time()
        
        try:
            if not self.redis_client:
                self.redis_client = redis.from_url(self.redis_url)
            
            # Test basic connectivity
            await self.redis_client.ping()
            
            # Test pub/sub functionality
            test_channel = "maas:health_test"
            test_message = f"health_check_{int(time.time())}"
            
            await self.redis_client.publish(test_channel, test_message)
            
            response_time = (time.time() - start_time) * 1000
            
            # Get Redis info
            info = await self.redis_client.info()
            details = {
                "redis_version": info.get("redis_version"),
                "connected_clients": info.get("connected_clients"),
                "used_memory_human": info.get("used_memory_human"),
                "uptime_in_seconds": info.get("uptime_in_seconds")
            }
            
            status = HealthStatus.HEALTHY if response_time < 100 else HealthStatus.DEGRADED
            
            return ComponentHealth(
                name="redis",
                status=status,
                last_check=datetime.now(timezone.utc),
                response_time_ms=response_time,
                details=details
            )
            
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return ComponentHealth(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                last_check=datetime.now(timezone.utc),
                error_message=str(e)
            )
    
    async def _check_google_adk_health(self) -> ComponentHealth:
        """Check Google ADK availability"""
        start_time = time.time()
        
        try:
            # Test Google ADK agent creation (lightweight test)
            from google.adk import Agent
            
            # Create a minimal test agent
            test_agent = Agent(
                name="health_check_agent",
                model="gemini-2.0-flash"
            )
            
            response_time = (time.time() - start_time) * 1000
            
            return ComponentHealth(
                name="google_adk",
                status=HealthStatus.HEALTHY,
                last_check=datetime.now(timezone.utc),
                response_time_ms=response_time,
                details={"model": "gemini-2.0-flash", "test": "agent_creation_successful"}
            )
            
        except Exception as e:
            logger.error(f"Google ADK health check failed: {e}")
            return ComponentHealth(
                name="google_adk",
                status=HealthStatus.UNHEALTHY,
                last_check=datetime.now(timezone.utc),
                error_message=str(e)
            )
    
    async def _check_message_processing_health(self) -> ComponentHealth:
        """Check message processing health"""
        try:
            # Check if we've processed tasks recently
            if self.last_task_time:
                time_since_last = datetime.now(timezone.utc) - self.last_task_time
                minutes_since_last = time_since_last.total_seconds() / 60
                
                if minutes_since_last > 60:  # No tasks in last hour
                    status = HealthStatus.DEGRADED
                    details = {"minutes_since_last_task": minutes_since_last, "status": "no_recent_activity"}
                else:
                    status = HealthStatus.HEALTHY
                    details = {"minutes_since_last_task": minutes_since_last, "status": "active"}
            else:
                status = HealthStatus.DEGRADED
                details = {"status": "no_tasks_processed_yet"}
            
            return ComponentHealth(
                name="message_processing",
                status=status,
                last_check=datetime.now(timezone.utc),
                details=details
            )
            
        except Exception as e:
            logger.error(f"Message processing health check failed: {e}")
            return ComponentHealth(
                name="message_processing",
                status=HealthStatus.UNHEALTHY,
                last_check=datetime.now(timezone.utc),
                error_message=str(e)
            )
    
    def record_task_processed(self):
        """Record that a task was processed"""
        self.task_count += 1
        self.last_task_time = datetime.now(timezone.utc)
    
    def record_error(self):
        """Record an error"""
        self.error_count += 1
    
    async def cleanup(self):
        """Clean up resources"""
        if self.redis_client:
            await self.redis_client.aclose()


# Global health monitor instance
health_monitor = HealthMonitor()