"""
Intelligent Agent Selection for AI Engine

Implements advanced agent selection algorithms with:
- Capability matching
- Workload balancing  
- Performance-based selection
- Multi-objective optimization
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum
import asyncio
import json

logger = logging.getLogger(__name__)


class SelectionStrategy(Enum):
    """Agent selection strategies"""
    CAPABILITY_FIRST = "capability_first"
    LOAD_BALANCED = "load_balanced"
    PERFORMANCE_FIRST = "performance_first"
    HYBRID_OPTIMIZED = "hybrid_optimized"


@dataclass
class AgentCapability:
    """Agent capability assessment"""
    agent_id: str
    agent_type: str
    specializations: List[str]
    capability_score: float  # 0.0 - 1.0
    performance_history: float  # 0.0 - 1.0
    current_load: float  # 0.0 - 1.0
    availability: bool
    last_task_completion: Optional[datetime]


@dataclass
class TaskRequirements:
    """Task requirements for agent selection"""
    task_type: str
    priority: str
    required_capabilities: List[str]
    estimated_complexity: float  # 0.0 - 1.0
    deadline: Optional[datetime]
    preferred_model: Optional[str]


@dataclass
class SelectionScore:
    """Agent selection score with breakdown"""
    agent_id: str
    total_score: float
    capability_score: float
    load_score: float
    performance_score: float
    availability_score: float
    reasoning: str


class IntelligentAgentSelector:
    """
    Advanced agent selection system for AI Engine
    
    Provides intelligent agent selection based on multiple factors:
    - Task-agent capability matching
    - Current workload distribution
    - Historical performance data
    - Real-time availability
    """
    
    def __init__(self, strategy: SelectionStrategy = SelectionStrategy.HYBRID_OPTIMIZED):
        self.strategy = strategy
        self.agent_capabilities: Dict[str, AgentCapability] = {}
        self.selection_history: List[Dict[str, Any]] = []
        
        # Weights for hybrid optimization
        self.weights = {
            "capability": 0.4,
            "load_balance": 0.3,
            "performance": 0.2,
            "availability": 0.1
        }
        
    async def register_agent_capability(self, agent_capability: AgentCapability):
        """Register or update agent capability information"""
        self.agent_capabilities[agent_capability.agent_id] = agent_capability
        logger.info(f"Registered agent capability: {agent_capability.agent_id} ({agent_capability.agent_type})")
        
    async def update_agent_workload(self, agent_id: str, current_load: float):
        """Update agent's current workload"""
        if agent_id in self.agent_capabilities:
            self.agent_capabilities[agent_id].current_load = current_load
            logger.debug(f"Updated workload for {agent_id}: {current_load}")
            
    async def update_agent_performance(self, agent_id: str, performance_score: float):
        """Update agent's performance score based on task completion"""
        if agent_id in self.agent_capabilities:
            # Use exponential moving average for performance history
            current = self.agent_capabilities[agent_id].performance_history
            alpha = 0.3  # Learning rate
            new_score = alpha * performance_score + (1 - alpha) * current
            self.agent_capabilities[agent_id].performance_history = new_score
            self.agent_capabilities[agent_id].last_task_completion = datetime.now(timezone.utc)
            logger.debug(f"Updated performance for {agent_id}: {new_score}")
            
    async def select_best_agent(self, task_requirements: TaskRequirements) -> Optional[SelectionScore]:
        """
        Select the best agent for the given task requirements
        
        Args:
            task_requirements: Task requirements and constraints
            
        Returns:
            SelectionScore with best agent selection, or None if no suitable agent
        """
        logger.info(f"Selecting agent for task type '{task_requirements.task_type}' with strategy '{self.strategy.value}'")
        
        # Get available agents
        available_agents = [
            agent for agent in self.agent_capabilities.values()
            if agent.availability
        ]
        
        if not available_agents:
            logger.warning("No available agents for task assignment")
            return None
            
        # Score all available agents
        agent_scores = []
        for agent in available_agents:
            score = await self._calculate_agent_score(agent, task_requirements)
            if score.total_score > 0:  # Only include viable agents
                agent_scores.append(score)
                
        if not agent_scores:
            logger.warning("No suitable agents found for task requirements")
            return None
            
        # Sort by total score (highest first)
        agent_scores.sort(key=lambda x: x.total_score, reverse=True)
        
        best_selection = agent_scores[0]
        
        # Record selection for analytics
        self.selection_history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "task_type": task_requirements.task_type,
            "selected_agent": best_selection.agent_id,
            "score": best_selection.total_score,
            "strategy": self.strategy.value,
            "alternatives": len(agent_scores) - 1
        })
        
        logger.info(f"Selected agent {best_selection.agent_id} with score {best_selection.total_score:.3f}")
        logger.debug(f"Selection reasoning: {best_selection.reasoning}")
        
        return best_selection
        
    async def _calculate_agent_score(self, agent: AgentCapability, requirements: TaskRequirements) -> SelectionScore:
        """Calculate comprehensive score for agent-task matching"""
        
        # 1. Capability Score - How well agent matches task requirements
        capability_score = await self._calculate_capability_score(agent, requirements)
        
        # 2. Load Balance Score - Prefer agents with lower current load
        load_score = 1.0 - agent.current_load
        
        # 3. Performance Score - Historical performance
        performance_score = agent.performance_history
        
        # 4. Availability Score - Real-time availability and responsiveness
        availability_score = await self._calculate_availability_score(agent)
        
        # Apply strategy-specific weights
        if self.strategy == SelectionStrategy.CAPABILITY_FIRST:
            weights = {"capability": 0.7, "load_balance": 0.1, "performance": 0.1, "availability": 0.1}
        elif self.strategy == SelectionStrategy.LOAD_BALANCED:
            weights = {"capability": 0.2, "load_balance": 0.6, "performance": 0.1, "availability": 0.1}
        elif self.strategy == SelectionStrategy.PERFORMANCE_FIRST:
            weights = {"capability": 0.2, "load_balance": 0.1, "performance": 0.6, "availability": 0.1}
        else:  # HYBRID_OPTIMIZED
            weights = self.weights
            
        # Calculate weighted total score
        total_score = (
            capability_score * weights["capability"] +
            load_score * weights["load_balance"] +
            performance_score * weights["performance"] +
            availability_score * weights["availability"]
        )
        
        # Generate reasoning
        reasoning = (
            f"Capability: {capability_score:.3f}, "
            f"Load: {load_score:.3f}, "
            f"Performance: {performance_score:.3f}, "
            f"Availability: {availability_score:.3f}"
        )
        
        return SelectionScore(
            agent_id=agent.agent_id,
            total_score=total_score,
            capability_score=capability_score,
            load_score=load_score,
            performance_score=performance_score,
            availability_score=availability_score,
            reasoning=reasoning
        )
        
    async def _calculate_capability_score(self, agent: AgentCapability, requirements: TaskRequirements) -> float:
        """Calculate how well agent capabilities match task requirements"""
        
        # Base score for agent type matching
        type_match_score = 0.0
        if requirements.task_type in agent.specializations:
            type_match_score = 1.0
        elif any(spec in requirements.task_type for spec in agent.specializations):
            type_match_score = 0.7  # Partial match
        elif "general" in agent.specializations or agent.agent_type == "manager":
            type_match_score = 0.5  # Can handle general tasks
            
        # Capability requirements matching
        capability_match_score = 0.0
        if requirements.required_capabilities:
            matches = sum(1 for cap in requirements.required_capabilities 
                         if cap in agent.specializations)
            capability_match_score = matches / len(requirements.required_capabilities)
        else:
            capability_match_score = 1.0  # No specific requirements
            
        # Combine scores
        capability_score = (type_match_score * 0.7 + capability_match_score * 0.3)
        
        # Apply agent's inherent capability score
        return capability_score * agent.capability_score
        
    async def _calculate_availability_score(self, agent: AgentCapability) -> float:
        """Calculate agent availability score"""
        
        base_score = 1.0 if agent.availability else 0.0
        
        # Penalize if agent hasn't completed tasks recently (might be stale)
        if agent.last_task_completion:
            time_since_last = datetime.now(timezone.utc) - agent.last_task_completion
            if time_since_last.total_seconds() > 3600:  # More than 1 hour
                base_score *= 0.9
            elif time_since_last.total_seconds() > 86400:  # More than 1 day
                base_score *= 0.7
                
        return base_score
        
    def get_selection_analytics(self) -> Dict[str, Any]:
        """Get selection analytics and statistics"""
        if not self.selection_history:
            return {"message": "No selection history available"}
            
        # Calculate analytics
        total_selections = len(self.selection_history)
        agent_usage = {}
        task_type_distribution = {}
        
        for selection in self.selection_history:
            agent_id = selection["selected_agent"]
            task_type = selection["task_type"]
            
            agent_usage[agent_id] = agent_usage.get(agent_id, 0) + 1
            task_type_distribution[task_type] = task_type_distribution.get(task_type, 0) + 1
            
        return {
            "total_selections": total_selections,
            "strategy": self.strategy.value,
            "agent_usage_distribution": agent_usage,
            "task_type_distribution": task_type_distribution,
            "registered_agents": len(self.agent_capabilities),
            "available_agents": sum(1 for a in self.agent_capabilities.values() if a.availability)
        }


# Global selector instance
agent_selector = IntelligentAgentSelector()


async def initialize_default_agents():
    """Initialize default agent capabilities for AI Engine"""
    
    default_agents = [
        AgentCapability(
            agent_id="code_generator_001",
            agent_type="code_generator",
            specializations=["code_generation", "python", "javascript", "api_development"],
            capability_score=0.9,
            performance_history=0.8,
            current_load=0.0,
            availability=True,
            last_task_completion=None
        ),
        AgentCapability(
            agent_id="research_agent_001", 
            agent_type="research_agent",
            specializations=["research", "analysis", "information_gathering", "web_search"],
            capability_score=0.85,
            performance_history=0.75,
            current_load=0.0,
            availability=True,
            last_task_completion=None
        ),
        AgentCapability(
            agent_id="testing_agent_001",
            agent_type="testing_agent", 
            specializations=["testing", "validation", "quality_assurance", "test_automation"],
            capability_score=0.8,
            performance_history=0.85,
            current_load=0.0,
            availability=True,
            last_task_completion=None
        ),
        AgentCapability(
            agent_id="manager_agent_001",
            agent_type="manager",
            specializations=["general", "coordination", "task_management", "delegation"],
            capability_score=0.7,
            performance_history=0.8,
            current_load=0.0,
            availability=True,
            last_task_completion=None
        )
    ]
    
    for agent_cap in default_agents:
        await agent_selector.register_agent_capability(agent_cap)
        
    logger.info(f"Initialized {len(default_agents)} default agent capabilities")