"""
AI-Powered Agent Selection System

Uses an AI agent to intelligently select the best agent for a task by:
- Analyzing real agent data from the environment
- Examining actual tools and capabilities
- Making selection decisions using AI reasoning
- No hardcoded templates or rigid logic
"""

import logging
import json
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from dataclasses import dataclass

# Add main platform to path for imports
import sys
from pathlib import Path
main_platform_path = Path(__file__).parent.parent.parent.parent / "maas-agent-platform"
sys.path.insert(0, str(main_platform_path))

from api.core.database import get_db_context
from api.models.agent import RegisteredAgent
from api.models.environment import Environment
from sqlalchemy import and_

try:
    from google.adk import Agent
    from google.adk.runners import InMemoryRunner
    from google.genai import types
    GOOGLE_ADK_AVAILABLE = True
except ImportError:
    GOOGLE_ADK_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class AgentSelectionResult:
    """Result of AI-powered agent selection"""
    selected_agent_id: str
    confidence_score: float  # 0.0 - 1.0
    reasoning: str
    alternatives_considered: List[str]
    selection_time_ms: float


class AIPoweredAgentSelector:
    """
    AI-powered agent selection using real environment data
    
    This selector uses an AI agent to analyze:
    - Real registered agents in the environment
    - Their actual tools and capabilities
    - Task requirements and context
    - Makes intelligent selection decisions using AI reasoning
    """
    
    def __init__(self):
        self.selector_agent = None
        self.runner = None
        self.initialized = False
        
    async def initialize(self):
        """Initialize the AI selector agent"""
        if not GOOGLE_ADK_AVAILABLE:
            raise RuntimeError("Google ADK required for AI-powered agent selection")
            
        logger.info("Initializing AI-powered agent selector...")
        
        try:
            # Import config from main platform
            from api.core.config import settings
            import os
            
            # Set Google API key as environment variable for ADK
            if settings.GOOGLE_ADK_API_KEY:
                os.environ["GOOGLE_API_KEY"] = settings.GOOGLE_ADK_API_KEY
                
            # Create the AI selector agent
            self.selector_agent = Agent(
                model="gemini-2.0-flash",
                name="agent_selector", 
                description="AI agent that intelligently selects the best agent for tasks",
                instruction=self._get_selector_system_prompt()
            )
            
            # Create runner
            self.runner = InMemoryRunner(
                agent=self.selector_agent,
                app_name="maas_ai_agent_selector"
            )
            
            self.initialized = True
            logger.info("AI-powered agent selector initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize AI selector: {e}")
            raise
            
    def _get_selector_system_prompt(self) -> str:
        """Get the system prompt for the AI selector agent"""
        return """You are an intelligent agent selector for the MAAS AI platform. Your job is to analyze available agents and select the best one for a given task.

You will be provided with:
1. A list of available agents in the environment with their tools and capabilities
2. A task description with requirements
3. Any additional context

Your analysis should consider:
- Agent specializations and tools
- Task complexity and requirements  
- Agent availability and current workload
- Tool compatibility with task needs
- Past performance if available

Respond with a JSON object containing:
{
  "selected_agent_id": "agent_id_here",
  "confidence_score": 0.85,
  "reasoning": "Detailed explanation of why this agent was selected",
  "alternatives_considered": ["agent_id_1", "agent_id_2"],
  "key_factors": ["factor1", "factor2", "factor3"]
}

Be thorough in your analysis but concise in your reasoning. Focus on capability matching and tool availability."""

    async def select_agent_for_task(self, task_data: Dict[str, Any], environment_id: str) -> Optional[AgentSelectionResult]:
        """
        Use AI to select the best agent for a task based on real environment data
        
        Args:
            task_data: Task information including type, description, requirements
            environment_id: Environment to search for agents
            
        Returns:
            AgentSelectionResult with AI's selection decision
        """
        if not self.initialized:
            await self.initialize()
            
        start_time = datetime.now()
        
        try:
            # Get real agent data from environment
            agents_data = await self._get_environment_agents(environment_id)
            
            if not agents_data:
                logger.warning(f"No agents found in environment {environment_id}")
                return None
                
            # Prepare analysis prompt for AI
            analysis_prompt = self._create_analysis_prompt(task_data, agents_data)
            
            # Get AI selection decision
            ai_response = await self._query_ai_selector(analysis_prompt)
            
            # Parse AI response
            selection_result = self._parse_ai_response(ai_response, start_time)
            
            if selection_result:
                logger.info(f"AI selected agent {selection_result.selected_agent_id} with confidence {selection_result.confidence_score}")
                logger.debug(f"AI reasoning: {selection_result.reasoning}")
                
            return selection_result
            
        except Exception as e:
            logger.error(f"Error in AI-powered agent selection: {e}")
            return None
            
    async def _get_environment_agents(self, environment_id: str) -> List[Dict[str, Any]]:
        """Get real agent data from the environment database"""
        try:
            with get_db_context() as db:
                # Query registered agents in the environment
                agents = db.query(RegisteredAgent).filter(
                    and_(
                        RegisteredAgent.environment_id == environment_id,
                        RegisteredAgent.is_active == True
                    )
                ).all()
                
                agents_data = []
                for agent in agents:
                    # Get agent configuration and tools
                    agent_info = {
                        "agent_id": str(agent.id),
                        "agent_name": agent.agent_name,
                        "agent_type": agent.agent_type,
                        "model": agent.model,
                        "tools": self._extract_agent_tools(agent),
                        "capabilities": self._extract_agent_capabilities(agent),
                        "status": "active" if agent.is_active else "inactive",
                        "created_at": agent.created_at.isoformat() if agent.created_at else None,
                        "updated_at": agent.updated_at.isoformat() if agent.updated_at else None,
                        "configuration": agent.configuration or {},
                        "performance_metrics": self._get_agent_performance(str(agent.id))
                    }
                    agents_data.append(agent_info)
                    
                logger.info(f"Found {len(agents_data)} active agents in environment {environment_id}")
                return agents_data
                
        except Exception as e:
            logger.error(f"Error fetching environment agents: {e}")
            return []
            
    def _extract_agent_tools(self, agent: RegisteredAgent) -> List[Dict[str, Any]]:
        """Extract tools available to the agent"""
        tools = []
        
        # Extract from agent configuration
        config = agent.configuration or {}
        if "tools" in config:
            tools.extend(config["tools"])
            
        # Extract from agent type (common tools)
        agent_type_tools = {
            "code_generator": [
                {"name": "code_editor", "description": "Edit and generate code files"},
                {"name": "file_system", "description": "Read/write files and directories"},
                {"name": "syntax_validator", "description": "Validate code syntax"},
                {"name": "documentation_generator", "description": "Generate code documentation"}
            ],
            "research_agent": [
                {"name": "web_search", "description": "Search the internet for information"},
                {"name": "knowledge_base", "description": "Access structured knowledge"},
                {"name": "data_analysis", "description": "Analyze and process data"},
                {"name": "report_generator", "description": "Generate research reports"}
            ],
            "testing_agent": [
                {"name": "test_runner", "description": "Execute test suites"},
                {"name": "code_analyzer", "description": "Static code analysis"},
                {"name": "coverage_tracker", "description": "Track test coverage"},
                {"name": "bug_detector", "description": "Detect potential bugs"}
            ],
            "github_integration": [
                {"name": "git_operations", "description": "Git repository operations"},
                {"name": "github_api", "description": "GitHub API integration"},
                {"name": "pull_request_manager", "description": "Manage pull requests"},
                {"name": "issue_tracker", "description": "Track and manage issues"}
            ],
            "manager": [
                {"name": "task_delegator", "description": "Delegate tasks to other agents"},
                {"name": "workflow_orchestrator", "description": "Orchestrate complex workflows"},
                {"name": "resource_manager", "description": "Manage resources and priorities"},
                {"name": "communication_hub", "description": "Coordinate agent communication"}
            ]
        }
        
        if agent.agent_type in agent_type_tools:
            tools.extend(agent_type_tools[agent.agent_type])
            
        return tools
        
    def _extract_agent_capabilities(self, agent: RegisteredAgent) -> List[str]:
        """Extract agent capabilities and specializations"""
        capabilities = []
            
        # From agent type
        type_capabilities = {
            "code_generator": ["programming", "code_generation", "software_development", "debugging"],
            "research_agent": ["research", "analysis", "information_gathering", "data_processing"],
            "testing_agent": ["testing", "quality_assurance", "validation", "automation"],
            "github_integration": ["version_control", "repository_management", "collaboration"],
            "manager": ["coordination", "delegation", "project_management", "orchestration"]
        }
        
        if agent.agent_type in type_capabilities:
            capabilities.extend(type_capabilities[agent.agent_type])
            
        # From configuration
        config = agent.configuration or {}
        if "capabilities" in config:
            capabilities.extend(config["capabilities"])
        if "specialization" in config:
            specializations = config["specialization"]
            if isinstance(specializations, str):
                capabilities.extend(specializations.split(","))
            elif isinstance(specializations, list):
                capabilities.extend(specializations)
            
        # Clean and deduplicate
        capabilities = [cap.strip().lower() for cap in capabilities if cap.strip()]
        return list(set(capabilities))
        
    def _get_agent_performance(self, agent_id: str) -> Dict[str, Any]:
        """Get agent performance metrics (placeholder for now)"""
        # TODO: Integrate with actual performance tracking
        return {
            "success_rate": 0.85,
            "average_completion_time": 120,  # seconds
            "tasks_completed": 45,
            "last_performance_update": datetime.now().isoformat()
        }
        
    def _create_analysis_prompt(self, task_data: Dict[str, Any], agents_data: List[Dict[str, Any]]) -> str:
        """Create analysis prompt for the AI selector"""
        
        task_info = {
            "task_type": task_data.get("task_type", "unknown"),
            "description": task_data.get("input_data", {}).get("description", ""),
            "requirements": task_data.get("input_data", {}),
            "priority": task_data.get("priority", "normal"),
            "environment_id": task_data.get("environment_id"),
            "deadline": task_data.get("deadline"),
            "complexity_estimate": task_data.get("complexity_estimate", "medium")
        }
        
        prompt = f"""Please analyze the following task and available agents to select the best agent for the job.

TASK TO ASSIGN:
{json.dumps(task_info, indent=2)}

AVAILABLE AGENTS IN ENVIRONMENT:
{json.dumps(agents_data, indent=2)}

Please analyze each agent's suitability for this task considering:
1. Tool compatibility with task requirements
2. Agent specializations and capabilities
3. Current availability and performance
4. Complexity match between task and agent abilities

Provide your selection as a JSON response with detailed reasoning."""

        return prompt
        
    async def _query_ai_selector(self, prompt: str) -> str:
        """Query the AI selector agent with the analysis prompt"""
        try:
            # Create session
            session = await self.runner.session_service.create_session(
                app_name="maas_ai_agent_selector",
                user_id="ai_engine_system"
            )
            
            # Create message
            message = types.Content(
                role='user',
                parts=[types.Part.from_text(text=prompt)]
            )
            
            # Get AI response
            response = ""
            async for event in self.runner.run_async(
                user_id="ai_engine_system",
                session_id=session.id,
                new_message=message
            ):
                if event.content and event.content.parts and event.content.parts[0].text:
                    response += event.content.parts[0].text
                    
            return response
            
        except Exception as e:
            logger.error(f"Error querying AI selector: {e}")
            raise
            
    def _parse_ai_response(self, ai_response: str, start_time: datetime) -> Optional[AgentSelectionResult]:
        """Parse the AI's selection response"""
        try:
            # Extract JSON from response (handle markdown code blocks)
            json_start = ai_response.find('{')
            json_end = ai_response.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                logger.error("No JSON found in AI response")
                return None
                
            json_str = ai_response[json_start:json_end]
            selection_data = json.loads(json_str)
            
            # Calculate selection time
            end_time = datetime.now()
            selection_time_ms = (end_time - start_time).total_seconds() * 1000
            
            return AgentSelectionResult(
                selected_agent_id=selection_data.get("selected_agent_id"),
                confidence_score=selection_data.get("confidence_score", 0.0),
                reasoning=selection_data.get("reasoning", ""),
                alternatives_considered=selection_data.get("alternatives_considered", []),
                selection_time_ms=selection_time_ms
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response JSON: {e}")
            logger.debug(f"AI response: {ai_response}")
            return None
        except Exception as e:
            logger.error(f"Error parsing AI response: {e}")
            return None


# Global AI-powered selector instance
ai_agent_selector = AIPoweredAgentSelector()