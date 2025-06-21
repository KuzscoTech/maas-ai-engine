"""
Advanced Error Recovery Module

Provides enterprise-grade error handling and resilience features:
- Intelligent retry strategies with exponential backoff
- Circuit breakers to prevent cascading failures  
- Health checks and proactive failure detection
- Error classification and smart recovery decisions
- Fallback mechanisms and graceful degradation
"""

from .advanced_recovery_manager import (
    recovery_manager,
    AdvancedRecoveryManager,
    RetryManager,
    CircuitBreaker,
    ErrorClassifier,
    ErrorCategory,
    ErrorSeverity,
    RetryConfig,
    CircuitBreakerConfig
)

__all__ = [
    'recovery_manager',
    'AdvancedRecoveryManager', 
    'RetryManager',
    'CircuitBreaker',
    'ErrorClassifier',
    'ErrorCategory',
    'ErrorSeverity',
    'RetryConfig',
    'CircuitBreakerConfig'
]