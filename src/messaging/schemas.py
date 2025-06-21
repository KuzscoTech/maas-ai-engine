"""
Message schemas for Redis pub/sub communication between MAAS Platform and AI Engine
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, validator


class MessageType(str, Enum):
    """Types of messages exchanged between services"""
    # Task execution flow
    TASK_EXECUTE = "task_execute"
    TASK_STATUS_UPDATE = "task_status_update"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    
    # Agent management
    AGENT_STATUS = "agent_status"
    AGENT_HEARTBEAT = "agent_heartbeat"
    
    # System events
    SYSTEM_STATUS = "system_status"
    HEALTH_CHECK = "health_check"


class MessageSource(str, Enum):
    """Source services for messages"""
    MAAS_PLATFORM = "maas_platform"
    AI_ENGINE = "ai_engine"


class TaskStatus(str, Enum):
    """Task status values"""
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ErrorType(str, Enum):
    """Types of errors that can occur during task processing"""
    AGENT_UNAVAILABLE = "agent_unavailable"
    AGENT_TIMEOUT = "agent_timeout"
    INVALID_INPUT = "invalid_input"
    SYSTEM_ERROR = "system_error"
    AUTHENTICATION_ERROR = "authentication_error"
    RESOURCE_EXHAUSTED = "resource_exhausted"


class BaseMessage(BaseModel):
    """Base message schema for all pub/sub messages"""
    message_type: MessageType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: MessageSource
    message_id: Optional[str] = None
    
    class Config:
        use_enum_values = True


class TaskExecuteMessage(BaseMessage):
    """Message to request task execution by AI Engine"""
    message_type: MessageType = MessageType.TASK_EXECUTE
    task_id: str
    data: Dict[str, Any] = Field(
        description="Task data including type, environment_id, agent_id, input_data, configuration"
    )
    
    @validator('data')
    def validate_task_data(cls, v):
        required_fields = ['task_type', 'environment_id', 'input_data']
        for field in required_fields:
            if field not in v:
                raise ValueError(f"Required field '{field}' missing from data")
        return v


class TaskStatusUpdateMessage(BaseMessage):
    """Message for task status updates during processing"""
    message_type: MessageType = MessageType.TASK_STATUS_UPDATE
    task_id: str
    data: Dict[str, Any] = Field(
        description="Status update data including status, progress, current_step, etc."
    )
    
    @validator('data')
    def validate_status_data(cls, v):
        if 'status' not in v:
            raise ValueError("Status field is required")
        return v


class TaskCompletedMessage(BaseMessage):
    """Message sent when task is successfully completed"""
    message_type: MessageType = MessageType.TASK_COMPLETED
    task_id: str
    data: Dict[str, Any] = Field(
        description="Completion data including output_data, execution_time, agent_id, metadata"
    )
    
    @validator('data')
    def validate_completion_data(cls, v):
        required_fields = ['status', 'output_data']
        for field in required_fields:
            if field not in v:
                raise ValueError(f"Required field '{field}' missing from completion data")
        return v


class TaskFailedMessage(BaseMessage):
    """Message sent when task fails"""
    message_type: MessageType = MessageType.TASK_FAILED
    task_id: str
    data: Dict[str, Any] = Field(
        description="Failure data including error_type, error_message, retry_possible, etc."
    )
    
    @validator('data')
    def validate_failure_data(cls, v):
        required_fields = ['status', 'error_type', 'error_message']
        for field in required_fields:
            if field not in v:
                raise ValueError(f"Required field '{field}' missing from failure data")
        return v


class AgentStatusMessage(BaseMessage):
    """Message for agent status updates"""
    message_type: MessageType = MessageType.AGENT_STATUS
    agent_id: str
    data: Dict[str, Any] = Field(
        description="Agent status data including status, load, capabilities, etc."
    )


class SystemStatusMessage(BaseMessage):
    """Message for system-wide status updates"""
    message_type: MessageType = MessageType.SYSTEM_STATUS
    data: Dict[str, Any] = Field(
        description="System status data including service health, resource usage, etc."
    )


# Example message data structures for documentation
EXAMPLE_TASK_EXECUTE_DATA = {
    "task_type": "code_generation",
    "environment_id": "615dfdb3-1051-449e-b858-e4ea9220837a",
    "agent_id": "code_generator_658e1617",
    "input_data": {
        "description": "generate a hello world program",
        "language": "python",
        "requirements": []
    },
    "configuration": {
        "timeout": 300,
        "max_retries": 3,
        "priority": "normal"
    }
}

EXAMPLE_TASK_STATUS_DATA = {
    "status": "IN_PROGRESS",
    "progress_percentage": 45,
    "current_step": "Generating code structure",
    "agent_id": "code_generator_658e1617",
    "estimated_completion": "2025-06-14T05:53:30.000000Z"
}

EXAMPLE_TASK_COMPLETED_DATA = {
    "status": "COMPLETED",
    "execution_time_seconds": 73,
    "agent_id": "code_generator_658e1617",
    "output_data": {
        "code": "print('Hello, World!')",
        "language": "python",
        "file_name": "hello_world.py",
        "explanation": "A simple Python program that prints 'Hello, World!' to the console.",
        "dependencies": [],
        "test_cases": [
            {
                "input": "",
                "expected_output": "Hello, World!"
            }
        ]
    },
    "metadata": {
        "tokens_used": 157,
        "model_used": "gemini-2.0-flash",
        "cost_estimate": 0.0023
    }
}

EXAMPLE_TASK_FAILED_DATA = {
    "status": "FAILED",
    "error_type": "agent_timeout",
    "error_message": "Agent failed to respond within 300 seconds",
    "error_details": {
        "agent_id": "code_generator_658e1617",
        "timeout_duration": 300,
        "last_response_time": "2025-06-14T05:47:45.567890Z"
    },
    "retry_possible": True,
    "retry_count": 1,
    "max_retries": 3
}