"""
Agent Selection Module for MAAS AI Engine

Provides intelligent agent selection capabilities including:
- Advanced capability matching
- Workload balancing
- Performance-based selection
- Multi-objective optimization
"""

from .intelligent_selector import (
    IntelligentAgentSelector,
    SelectionStrategy,
    AgentCapability,
    TaskRequirements,
    SelectionScore,
    agent_selector,
    initialize_default_agents
)

__all__ = [
    "IntelligentAgentSelector",
    "SelectionStrategy", 
    "AgentCapability",
    "TaskRequirements",
    "SelectionScore",
    "agent_selector",
    "initialize_default_agents"
]