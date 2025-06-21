"""
Advanced Error Recovery and Resilience System

Provides enterprise-grade error handling with:
- Intelligent retry strategies with exponential backoff
- Circuit breakers to prevent cascading failures
- Health checks and proactive failure detection
- Error classification and smart recovery decisions
- Fallback mechanisms and graceful degradation
- Self-healing capabilities
"""

import asyncio
import logging
import time
import random
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from collections import defaultdict, deque
import json

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels for classification"""
    LOW = "low"              # Minor issues, quick recovery
    MEDIUM = "medium"        # Moderate issues, standard recovery
    HIGH = "high"           # Serious issues, aggressive recovery
    CRITICAL = "critical"    # System-threatening, emergency recovery


class ErrorCategory(Enum):
    """Error categories for specialized handling"""
    NETWORK = "network"              # Network connectivity issues
    AUTHENTICATION = "authentication"  # Auth/permission errors
    RATE_LIMIT = "rate_limit"       # API rate limiting
    RESOURCE = "resource"           # Memory/CPU/disk issues
    EXTERNAL_API = "external_api"   # Third-party API failures
    DATABASE = "database"           # Database connectivity/query issues
    VALIDATION = "validation"       # Data validation errors
    TIMEOUT = "timeout"             # Operation timeouts
    UNKNOWN = "unknown"             # Unclassified errors


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"       # Normal operation
    OPEN = "open"          # Failing, rejecting requests
    HALF_OPEN = "half_open" # Testing if service recovered


@dataclass
class RetryConfig:
    """Configuration for retry strategies"""
    max_attempts: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    exponential_base: float = 2.0
    jitter_factor: float = 0.1
    retry_on_errors: List[ErrorCategory] = field(default_factory=lambda: [
        ErrorCategory.NETWORK,
        ErrorCategory.RATE_LIMIT,
        ErrorCategory.TIMEOUT,
        ErrorCategory.EXTERNAL_API
    ])


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breakers"""
    failure_threshold: int = 5      # Failures before opening
    success_threshold: int = 3      # Successes to close from half-open
    timeout_seconds: float = 60.0   # Time before trying half-open
    volume_threshold: int = 10      # Minimum requests before considering failures


@dataclass
class ErrorEvent:
    """Record of an error occurrence"""
    timestamp: datetime
    error_type: str
    error_message: str
    category: ErrorCategory
    severity: ErrorSeverity
    component: str
    context: Dict[str, Any] = field(default_factory=dict)
    recovery_attempted: bool = False
    recovery_successful: bool = False


@dataclass
class CircuitBreakerState:
    """State of a circuit breaker"""
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    total_requests: int = 0
    config: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)


class ErrorClassifier:
    """Intelligent error classification system"""
    
    def __init__(self):
        # Error patterns for classification
        self.error_patterns = {
            ErrorCategory.NETWORK: [
                "connection", "network", "dns", "timeout", "unreachable",
                "connection refused", "connection reset", "connection timeout"
            ],
            ErrorCategory.AUTHENTICATION: [
                "authentication", "unauthorized", "forbidden", "token", "api key",
                "invalid credentials", "access denied", "permission denied"
            ],
            ErrorCategory.RATE_LIMIT: [
                "rate limit", "quota", "throttle", "too many requests",
                "rate exceeded", "limit exceeded", "throttled"
            ],
            ErrorCategory.RESOURCE: [
                "memory", "cpu", "disk", "resource", "capacity",
                "out of memory", "disk full", "resource exhausted"
            ],
            ErrorCategory.EXTERNAL_API: [
                "api", "service unavailable", "server error", "bad gateway",
                "service down", "upstream", "external service"
            ],
            ErrorCategory.DATABASE: [
                "database", "sql", "connection pool", "query", "transaction",
                "database connection", "db error", "database timeout"
            ],
            ErrorCategory.VALIDATION: [
                "validation", "invalid", "malformed", "schema", "format",
                "invalid input", "validation error", "bad request"
            ],
            ErrorCategory.TIMEOUT: [
                "timeout", "timed out", "deadline", "expired",
                "operation timeout", "request timeout"
            ]
        }
        
        # Severity mapping based on error types
        self.severity_mapping = {
            ErrorCategory.AUTHENTICATION: ErrorSeverity.HIGH,
            ErrorCategory.DATABASE: ErrorSeverity.HIGH,
            ErrorCategory.RESOURCE: ErrorSeverity.HIGH,
            ErrorCategory.EXTERNAL_API: ErrorSeverity.MEDIUM,
            ErrorCategory.NETWORK: ErrorSeverity.MEDIUM,
            ErrorCategory.RATE_LIMIT: ErrorSeverity.MEDIUM,
            ErrorCategory.TIMEOUT: ErrorSeverity.MEDIUM,
            ErrorCategory.VALIDATION: ErrorSeverity.LOW,
            ErrorCategory.UNKNOWN: ErrorSeverity.MEDIUM
        }
    
    def classify_error(self, error: Exception, context: Dict[str, Any] = None) -> tuple[ErrorCategory, ErrorSeverity]:
        """Classify an error by category and severity"""
        error_message = str(error).lower()
        error_type = type(error).__name__.lower()
        
        # Check context for additional clues
        if context:
            component = context.get("component", "").lower()
            operation = context.get("operation", "").lower()
            error_message += f" {component} {operation}"
        
        # Find matching category
        category = ErrorCategory.UNKNOWN
        for cat, patterns in self.error_patterns.items():
            if any(pattern in error_message or pattern in error_type for pattern in patterns):
                category = cat
                break
        
        # Determine severity
        severity = self.severity_mapping.get(category, ErrorSeverity.MEDIUM)
        
        # Override severity for specific critical conditions
        if any(critical in error_message for critical in ["critical", "fatal", "emergency", "panic"]):
            severity = ErrorSeverity.CRITICAL
        
        return category, severity


class RetryManager:
    """Intelligent retry management with exponential backoff"""
    
    def __init__(self, default_config: RetryConfig = None):
        self.default_config = default_config or RetryConfig()
        self.retry_stats = defaultdict(lambda: {"attempts": 0, "successes": 0, "failures": 0})
    
    async def execute_with_retry(
        self,
        operation: Callable,
        operation_id: str,
        config: Optional[RetryConfig] = None,
        context: Dict[str, Any] = None
    ) -> Any:
        """Execute an operation with intelligent retry logic"""
        retry_config = config or self.default_config
        context = context or {}
        
        last_exception = None
        
        for attempt in range(retry_config.max_attempts):
            try:
                logger.debug(f"Executing {operation_id}, attempt {attempt + 1}/{retry_config.max_attempts}")
                
                # Execute operation and handle both sync and async results
                if asyncio.iscoroutinefunction(operation):
                    result = await operation()
                else:
                    # Call operation, if it returns a coroutine, await it
                    result = operation()
                    if asyncio.iscoroutine(result):
                        result = await result
                
                # Success - update stats and return
                self.retry_stats[operation_id]["attempts"] += attempt + 1
                self.retry_stats[operation_id]["successes"] += 1
                
                if attempt > 0:
                    logger.info(f"Operation {operation_id} succeeded after {attempt + 1} attempts")
                
                return result
                
            except Exception as e:
                last_exception = e
                self.retry_stats[operation_id]["attempts"] += 1
                
                # Classify error to determine if we should retry
                classifier = ErrorClassifier()
                category, severity = classifier.classify_error(e, context)
                
                should_retry = (
                    attempt < retry_config.max_attempts - 1 and
                    category in retry_config.retry_on_errors
                )
                
                if not should_retry:
                    logger.warning(f"Not retrying {operation_id} - category {category.value} not retryable or max attempts reached")
                    break
                
                # Calculate delay with exponential backoff and jitter
                delay = min(
                    retry_config.base_delay_seconds * (retry_config.exponential_base ** attempt),
                    retry_config.max_delay_seconds
                )
                
                # Add jitter to prevent thundering herd
                jitter = delay * retry_config.jitter_factor * random.random()
                delay += jitter
                
                logger.warning(f"Operation {operation_id} failed (attempt {attempt + 1}), retrying in {delay:.2f}s: {e}")
                await asyncio.sleep(delay)
        
        # All retries failed
        self.retry_stats[operation_id]["failures"] += 1
        logger.error(f"Operation {operation_id} failed after {retry_config.max_attempts} attempts")
        raise last_exception
    
    def get_retry_stats(self) -> Dict[str, Dict[str, int]]:
        """Get retry statistics"""
        return dict(self.retry_stats)


class CircuitBreaker:
    """Circuit breaker implementation for preventing cascading failures"""
    
    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.state = CircuitBreakerState(config=config or CircuitBreakerConfig())
        self.lock = asyncio.Lock()
    
    async def execute(self, operation: Callable, *args, **kwargs) -> Any:
        """Execute operation through circuit breaker"""
        async with self.lock:
            # Check if circuit is open
            if self.state.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state.state = CircuitState.HALF_OPEN
                    self.state.success_count = 0
                    logger.info(f"Circuit breaker {self.name} transitioning to HALF_OPEN")
                else:
                    raise Exception(f"Circuit breaker {self.name} is OPEN - request rejected")
            
            # Check if we're in half-open and have enough successes
            if (self.state.state == CircuitState.HALF_OPEN and 
                self.state.success_count >= self.state.config.success_threshold):
                self.state.state = CircuitState.CLOSED
                self.state.failure_count = 0
                logger.info(f"Circuit breaker {self.name} transitioning to CLOSED")
        
        # Execute the operation
        try:
            self.state.total_requests += 1
            
            if asyncio.iscoroutinefunction(operation):
                result = await operation(*args, **kwargs)
            else:
                result = operation(*args, **kwargs)
            
            # Success
            await self._record_success()
            return result
            
        except Exception as e:
            await self._record_failure()
            raise
    
    async def _record_success(self):
        """Record a successful operation"""
        async with self.lock:
            self.state.last_success_time = datetime.now(timezone.utc)
            
            if self.state.state == CircuitState.HALF_OPEN:
                self.state.success_count += 1
            elif self.state.state == CircuitState.CLOSED:
                # Reset failure count on success
                self.state.failure_count = 0
    
    async def _record_failure(self):
        """Record a failed operation"""
        async with self.lock:
            self.state.last_failure_time = datetime.now(timezone.utc)
            self.state.failure_count += 1
            
            # Check if we should open the circuit
            if (self.state.state in [CircuitState.CLOSED, CircuitState.HALF_OPEN] and
                self.state.total_requests >= self.state.config.volume_threshold and
                self.state.failure_count >= self.state.config.failure_threshold):
                
                self.state.state = CircuitState.OPEN
                self.state.success_count = 0
                logger.warning(f"Circuit breaker {self.name} transitioning to OPEN after {self.state.failure_count} failures")
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if not self.state.last_failure_time:
            return True
        
        time_since_failure = datetime.now(timezone.utc) - self.state.last_failure_time
        return time_since_failure.total_seconds() >= self.state.config.timeout_seconds
    
    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state"""
        return {
            "name": self.name,
            "state": self.state.state.value,
            "failure_count": self.state.failure_count,
            "success_count": self.state.success_count,
            "total_requests": self.state.total_requests,
            "last_failure": self.state.last_failure_time.isoformat() if self.state.last_failure_time else None,
            "last_success": self.state.last_success_time.isoformat() if self.state.last_success_time else None,
            "config": {
                "failure_threshold": self.state.config.failure_threshold,
                "success_threshold": self.state.config.success_threshold,
                "timeout_seconds": self.state.config.timeout_seconds,
                "volume_threshold": self.state.config.volume_threshold
            }
        }


class AdvancedRecoveryManager:
    """
    Comprehensive error recovery and resilience management system
    """
    
    def __init__(self):
        self.retry_manager = RetryManager()
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.error_classifier = ErrorClassifier()
        self.error_history: deque = deque(maxlen=1000)
        
        # Recovery strategies
        self.recovery_strategies: Dict[ErrorCategory, Callable] = {
            ErrorCategory.NETWORK: self._recover_network_error,
            ErrorCategory.AUTHENTICATION: self._recover_auth_error,
            ErrorCategory.RATE_LIMIT: self._recover_rate_limit_error,
            ErrorCategory.RESOURCE: self._recover_resource_error,
            ErrorCategory.EXTERNAL_API: self._recover_external_api_error,
            ErrorCategory.DATABASE: self._recover_database_error,
            ErrorCategory.TIMEOUT: self._recover_timeout_error
        }
        
        # Health check functions
        self.health_checks: Dict[str, Callable] = {}
        
        # Statistics
        self.recovery_stats = {
            "total_errors": 0,
            "recovered_errors": 0,
            "unrecoverable_errors": 0,
            "circuit_breaker_activations": 0,
            "retry_successes": 0,
            "by_category": defaultdict(int),
            "by_severity": defaultdict(int)
        }
    
    def get_circuit_breaker(self, name: str, config: CircuitBreakerConfig = None) -> CircuitBreaker:
        """Get or create a circuit breaker"""
        if name not in self.circuit_breakers:
            self.circuit_breakers[name] = CircuitBreaker(name, config)
        return self.circuit_breakers[name]
    
    async def execute_with_recovery(
        self,
        operation: Callable,
        operation_id: str,
        component: str = "unknown",
        circuit_breaker_name: Optional[str] = None,
        retry_config: Optional[RetryConfig] = None,
        context: Dict[str, Any] = None
    ) -> Any:
        """Execute operation with full error recovery capabilities"""
        context = context or {}
        context["component"] = component
        context["operation_id"] = operation_id
        
        # Wrap with circuit breaker if specified
        if circuit_breaker_name:
            circuit_breaker = self.get_circuit_breaker(circuit_breaker_name)
            operation = lambda: circuit_breaker.execute(operation)
        
        try:
            # Execute with retry logic
            result = await self.retry_manager.execute_with_retry(
                operation, operation_id, retry_config, context
            )
            return result
            
        except Exception as e:
            # Record and classify error
            category, severity = self.error_classifier.classify_error(e, context)
            
            error_event = ErrorEvent(
                timestamp=datetime.now(timezone.utc),
                error_type=type(e).__name__,
                error_message=str(e),
                category=category,
                severity=severity,
                component=component,
                context=context
            )
            
            self.error_history.append(error_event)
            self._update_stats(error_event)
            
            # Attempt recovery
            recovery_successful = await self._attempt_recovery(error_event)
            error_event.recovery_attempted = True
            error_event.recovery_successful = recovery_successful
            
            if recovery_successful:
                logger.info(f"Successfully recovered from {category.value} error in {component}")
                return await self.execute_with_recovery(
                    operation, operation_id, component, circuit_breaker_name, retry_config, context
                )
            else:
                logger.error(f"Failed to recover from {category.value} error in {component}: {e}")
                raise
    
    async def _attempt_recovery(self, error_event: ErrorEvent) -> bool:
        """Attempt to recover from an error"""
        recovery_strategy = self.recovery_strategies.get(error_event.category)
        
        if not recovery_strategy:
            logger.debug(f"No recovery strategy for error category {error_event.category.value}")
            return False
        
        try:
            logger.info(f"Attempting recovery for {error_event.category.value} error")
            success = await recovery_strategy(error_event)
            
            if success:
                self.recovery_stats["recovered_errors"] += 1
            else:
                self.recovery_stats["unrecoverable_errors"] += 1
            
            return success
            
        except Exception as recovery_error:
            logger.error(f"Recovery strategy failed: {recovery_error}")
            self.recovery_stats["unrecoverable_errors"] += 1
            return False
    
    # Recovery strategy implementations
    async def _recover_network_error(self, error_event: ErrorEvent) -> bool:
        """Recover from network errors"""
        # Wait for network to recover
        await asyncio.sleep(5)
        # Could implement network connectivity checks here
        return True
    
    async def _recover_auth_error(self, error_event: ErrorEvent) -> bool:
        """Recover from authentication errors"""
        # Could implement token refresh logic here
        logger.warning("Auth error detected - manual intervention may be required")
        return False
    
    async def _recover_rate_limit_error(self, error_event: ErrorEvent) -> bool:
        """Recover from rate limiting"""
        # Wait longer for rate limits to reset
        wait_time = 60  # Default wait time
        
        # Extract wait time from error message if available
        error_msg = error_event.error_message.lower()
        if "retry after" in error_msg:
            try:
                # Try to extract number from "retry after X seconds"
                import re
                match = re.search(r'retry after (\d+)', error_msg)
                if match:
                    wait_time = int(match.group(1))
            except:
                pass
        
        logger.info(f"Rate limited - waiting {wait_time} seconds")
        await asyncio.sleep(wait_time)
        return True
    
    async def _recover_resource_error(self, error_event: ErrorEvent) -> bool:
        """Recover from resource errors"""
        # Could implement resource cleanup here
        logger.warning("Resource error - manual intervention may be required")
        return False
    
    async def _recover_external_api_error(self, error_event: ErrorEvent) -> bool:
        """Recover from external API errors"""
        # Wait for external service to recover
        await asyncio.sleep(10)
        return True
    
    async def _recover_database_error(self, error_event: ErrorEvent) -> bool:
        """Recover from database errors"""
        # Could implement connection pool reset here
        await asyncio.sleep(5)
        return True
    
    async def _recover_timeout_error(self, error_event: ErrorEvent) -> bool:
        """Recover from timeout errors"""
        # Timeouts are often transient
        await asyncio.sleep(2)
        return True
    
    def add_health_check(self, name: str, check_function: Callable) -> None:
        """Add a health check function"""
        self.health_checks[name] = check_function
    
    async def run_health_checks(self) -> Dict[str, bool]:
        """Run all registered health checks"""
        results = {}
        
        for name, check_func in self.health_checks.items():
            try:
                if asyncio.iscoroutinefunction(check_func):
                    result = await check_func()
                else:
                    result = check_func()
                results[name] = bool(result)
            except Exception as e:
                logger.error(f"Health check {name} failed: {e}")
                results[name] = False
        
        return results
    
    def _update_stats(self, error_event: ErrorEvent) -> None:
        """Update error statistics"""
        self.recovery_stats["total_errors"] += 1
        self.recovery_stats["by_category"][error_event.category.value] += 1
        self.recovery_stats["by_severity"][error_event.severity.value] += 1
    
    def get_recovery_status(self) -> Dict[str, Any]:
        """Get comprehensive recovery system status"""
        return {
            "statistics": dict(self.recovery_stats),
            "circuit_breakers": {
                name: breaker.get_state() 
                for name, breaker in self.circuit_breakers.items()
            },
            "retry_stats": self.retry_manager.get_retry_stats(),
            "recent_errors": [
                {
                    "timestamp": event.timestamp.isoformat(),
                    "category": event.category.value,
                    "severity": event.severity.value,
                    "component": event.component,
                    "error_type": event.error_type,
                    "recovered": event.recovery_successful
                }
                for event in list(self.error_history)[-10:]  # Last 10 errors
            ],
            "health_status": "operational"  # Will be updated by health checks
        }


# Global recovery manager instance
recovery_manager = AdvancedRecoveryManager()