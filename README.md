# MAAS AI Engine Microservice

## Overview

The MAAS AI Engine is a **separate microservice** responsible for AI task processing, agent management, and task execution. It communicates with the main MAAS Platform via **Redis pub/sub messaging** to eliminate polling and create a scalable, event-driven architecture.

## Architecture

```
┌─────────────────────┐         Redis Pub/Sub         ┌─────────────────────┐
│   MAAS Platform     │◄─────────────────────────────►│   MAAS AI Engine    │
│   (Port 8000)       │                               │   (Port 8001)       │
├─────────────────────┤                               ├─────────────────────┤
│ • User Interface    │                               │ • Task Worker       │
│ • Task Creation     │                               │ • AI Agent Manager  │
│ • Status Monitoring │                               │ • Task Execution    │
│ • Authentication    │                               │ • MCP Integration   │
│ • Database Updates  │                               │ • Result Generation │
└─────────────────────┘                               └─────────────────────┘
          │                                                       │
          └─────────────── Shared Database ──────────────────────┘
```

## Communication Flow

### Task Execution Flow
1. **Main Platform**: Creates task in database with status `CREATED`
2. **Main Platform**: Publishes `task_execute` message to Redis
3. **AI Engine**: Receives message and starts task processing
4. **AI Engine**: Updates task status to `IN_PROGRESS` via message
5. **AI Engine**: Executes task using appropriate AI agent
6. **AI Engine**: Publishes completion/failure message with results
7. **Main Platform**: Receives result and updates database
8. **Main Platform**: Notifies user of completion

## Message Schemas

### Redis Channels
- `task_requests` - Main Platform → AI Engine
- `task_results` - AI Engine → Main Platform
- `task_status` - Bidirectional status updates

### Message Types

#### 1. Task Execution Request
**Channel**: `task_requests`
**Direction**: Main Platform → AI Engine

```json
{
  "message_type": "task_execute",
  "task_id": "code_generation_a4e953b2_20250613_050638",
  "timestamp": "2025-06-14T05:51:38.986513Z",
  "source": "maas_platform",
  "data": {
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
}
```

#### 2. Task Status Update
**Channel**: `task_status`
**Direction**: AI Engine → Main Platform

```json
{
  "message_type": "task_status_update",
  "task_id": "code_generation_a4e953b2_20250613_050638",
  "timestamp": "2025-06-14T05:52:15.123456Z",
  "source": "ai_engine",
  "data": {
    "status": "IN_PROGRESS",
    "progress_percentage": 45,
    "current_step": "Generating code structure",
    "agent_id": "code_generator_658e1617",
    "estimated_completion": "2025-06-14T05:53:30.000000Z"
  }
}
```

#### 3. Task Completion
**Channel**: `task_results`
**Direction**: AI Engine → Main Platform

```json
{
  "message_type": "task_completed",
  "task_id": "code_generation_a4e953b2_20250613_050638",
  "timestamp": "2025-06-14T05:53:28.789012Z",
  "source": "ai_engine",
  "data": {
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
}
```

#### 4. Task Failure
**Channel**: `task_results`
**Direction**: AI Engine → Main Platform

```json
{
  "message_type": "task_failed",
  "task_id": "code_generation_a4e953b2_20250613_050638",
  "timestamp": "2025-06-14T05:52:45.567890Z",
  "source": "ai_engine",
  "data": {
    "status": "FAILED",
    "error_type": "agent_timeout",
    "error_message": "Agent failed to respond within 300 seconds",
    "error_details": {
      "agent_id": "code_generator_658e1617",
      "timeout_duration": 300,
      "last_response_time": "2025-06-14T05:47:45.567890Z"
    },
    "retry_possible": true,
    "retry_count": 1,
    "max_retries": 3
  }
}
```

## API Endpoints

### Health & Status Endpoints

#### GET /health
**Purpose**: Health check for the AI Engine service
**Response**:
```json
{
  "status": "healthy",
  "service": "maas-ai-engine",
  "version": "1.0.0",
  "timestamp": "2025-06-14T05:51:38.986513Z",
  "components": {
    "redis": "connected",
    "database": "connected",
    "agents": "3_active",
    "mcp_servers": "4_connected"
  }
}
```

#### GET /stats
**Purpose**: Detailed statistics and metrics
**Response**:
```json
{
  "service": "maas-ai-engine",
  "uptime_seconds": 3600,
  "tasks": {
    "total_processed": 156,
    "currently_processing": 3,
    "success_rate": 0.94,
    "average_execution_time": 45.7
  },
  "agents": {
    "total_agents": 5,
    "active_agents": 3,
    "agents_by_type": {
      "code_generator": 2,
      "research_agent": 1,
      "testing_agent": 1,
      "documentation": 1
    }
  },
  "resources": {
    "memory_usage": "234MB",
    "cpu_usage": "12%",
    "queue_depth": 2
  }
}
```

### Agent Management Endpoints

#### GET /agents
**Purpose**: List all available agents
**Response**:
```json
{
  "agents": [
    {
      "agent_id": "code_generator_658e1617",
      "type": "code_generator",
      "status": "active",
      "environment_id": "615dfdb3-1051-449e-b858-e4ea9220837a",
      "capabilities": ["python", "javascript", "api_development"],
      "current_load": 0.3,
      "last_activity": "2025-06-14T05:50:15.123456Z"
    }
  ]
}
```

#### POST /agents/{agent_id}/execute
**Purpose**: Directly execute a task on a specific agent (for testing)
**Request**:
```json
{
  "task_type": "code_generation",
  "input_data": {
    "description": "Create a REST API endpoint",
    "language": "python",
    "framework": "fastapi"
  }
}
```

### Task Management Endpoints

#### GET /tasks/processing
**Purpose**: Get currently processing tasks
**Response**:
```json
{
  "processing_tasks": [
    {
      "task_id": "code_generation_a4e953b2_20250613_050638",
      "status": "IN_PROGRESS",
      "agent_id": "code_generator_658e1617",
      "started_at": "2025-06-14T05:51:38.986513Z",
      "progress": 65,
      "estimated_completion": "2025-06-14T05:53:30.000000Z"
    }
  ]
}
```

## Error Handling

### Error Types and Responses

#### 1. Agent Not Available
```json
{
  "message_type": "task_failed",
  "data": {
    "status": "FAILED",
    "error_type": "agent_unavailable",
    "error_message": "No suitable agent available for task type 'specialized_analysis'",
    "retry_possible": true,
    "retry_delay_seconds": 60
  }
}
```

#### 2. Agent Timeout
```json
{
  "message_type": "task_failed",
  "data": {
    "status": "FAILED",
    "error_type": "agent_timeout",
    "error_message": "Agent did not complete task within timeout period",
    "retry_possible": true,
    "timeout_duration": 300
  }
}
```

#### 3. Invalid Input
```json
{
  "message_type": "task_failed",
  "data": {
    "status": "FAILED",
    "error_type": "invalid_input",
    "error_message": "Required field 'description' missing from input_data",
    "retry_possible": false,
    "validation_errors": [
      {
        "field": "input_data.description",
        "error": "This field is required"
      }
    ]
  }
}
```

#### 4. System Error
```json
{
  "message_type": "task_failed",
  "data": {
    "status": "FAILED",
    "error_type": "system_error",
    "error_message": "Database connection lost during task processing",
    "retry_possible": true,
    "system_details": {
      "component": "database",
      "error_code": "connection_timeout"
    }
  }
}
```

## Internal Architecture

### Components

#### 1. Message Handler
- **Purpose**: Processes incoming Redis messages
- **Responsibilities**:
  - Validate message schemas
  - Route messages to appropriate handlers
  - Handle malformed messages gracefully

#### 2. Task Executor
- **Purpose**: Manages task execution lifecycle
- **Responsibilities**:
  - Agent selection and assignment
  - Task timeout management
  - Progress tracking and updates
  - Result aggregation

#### 3. Agent Manager
- **Purpose**: Manages AI agent lifecycle
- **Responsibilities**:
  - Agent registration and discovery
  - Load balancing across agents
  - Agent health monitoring
  - Capability matching

#### 4. Result Publisher
- **Purpose**: Publishes results back to main platform
- **Responsibilities**:
  - Format result messages
  - Ensure message delivery
  - Handle Redis connection issues

### Configuration

#### Environment Variables
```bash
# Redis Configuration
REDIS_URL=redis://localhost:6379/1
REDIS_TASK_CHANNEL=task_requests
REDIS_RESULT_CHANNEL=task_results

# Database Configuration (shared with main platform)
DATABASE_URL=postgresql://postgres:devpassword@localhost:5432/maas_agent_platform

# AI Engine Configuration
AI_ENGINE_PORT=8001
AI_ENGINE_HOST=0.0.0.0
MAX_CONCURRENT_TASKS=10
TASK_TIMEOUT_SECONDS=300
AGENT_HEARTBEAT_INTERVAL=30

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

## Deployment Strategy

### Development
1. Start main MAAS platform on port 8000
2. Start Redis server
3. Start AI Engine on port 8001
4. Both services share the same database

### Production
1. Deploy AI Engine as separate container/service
2. Use Redis cluster for high availability
3. Scale AI Engine horizontally based on task load
4. Implement circuit breakers for resilience

## Benefits of This Architecture

### 1. **Decoupling**
- Main platform focuses on user interface and task management
- AI Engine focuses on task execution and agent management
- Each service can be developed, deployed, and scaled independently

### 2. **Scalability**
- Multiple AI Engine instances can process tasks in parallel
- Different AI engines can handle different task types
- Load balancing across multiple AI models/providers

### 3. **Reliability**
- If AI Engine fails, main platform remains available
- Message queuing ensures no task loss
- Retry mechanisms handle transient failures

### 4. **Flexibility**
- Easy to swap AI providers (OpenAI, Anthropic, local models)
- Different AI engines for different environments
- A/B testing of different AI configurations

### 5. **Performance**
- No polling overhead
- Real-time status updates
- Efficient resource utilization

## Implementation Steps

### Phase 1: Core Infrastructure
1. ✅ Create microservice directory structure
2. ✅ Design message schemas and API contracts
3. 🚧 Implement Redis pub/sub communication layer
4. 🚧 Create basic AI Engine server structure

### Phase 2: Task Processing
1. ⏳ Implement task execution engine
2. ⏳ Add agent management and selection
3. ⏳ Implement result publishing
4. ⏳ Add error handling and retries

### Phase 3: Integration
1. ⏳ Update main platform to publish task messages
2. ⏳ Update main platform to listen for results
3. ⏳ Remove old polling-based task worker
4. ⏳ Add monitoring and health checks

### Phase 4: Enhancement
1. ⏳ Add task prioritization and queuing
2. ⏳ Implement advanced agent selection algorithms
3. ⏳ Add metrics and monitoring
4. ⏳ Performance optimization and caching

## Testing Strategy

### Unit Tests
- Message schema validation
- Agent selection logic
- Error handling scenarios
- Redis communication

### Integration Tests
- End-to-end task execution
- Multiple concurrent tasks
- Failure recovery scenarios
- Performance benchmarks

### Load Tests
- High-volume task processing
- Agent capacity limits
- Redis message throughput
- Memory and CPU usage

---

This architecture ensures a **clean separation of concerns**, **improved scalability**, and **easier maintenance** while providing **real-time task processing** without the overhead of constant polling.