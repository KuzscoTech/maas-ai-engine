"""
Redis client for pub/sub messaging between MAAS Platform and AI Engine
"""

import asyncio
import json
import logging
from typing import Dict, Any, Callable, Optional, List
from datetime import datetime, timezone

import redis.asyncio as redis
from pydantic import ValidationError

from .schemas import (
    BaseMessage, MessageType, MessageSource,
    TaskExecuteMessage, TaskStatusUpdateMessage, 
    TaskCompletedMessage, TaskFailedMessage,
    AgentStatusMessage, SystemStatusMessage
)

logger = logging.getLogger(__name__)


class RedisChannels:
    """Redis channel names for different message types"""
    TASK_REQUESTS = "maas:task_requests"
    TASK_RESULTS = "maas:task_results"
    TASK_STATUS = "maas:task_status"
    AGENT_STATUS = "maas:agent_status"
    SYSTEM_STATUS = "maas:system_status"
    HEALTH_CHECK = "maas:health_check"


class RedisMessenger:
    """
    Redis pub/sub client for inter-service communication
    
    Handles:
    - Publishing messages to Redis channels
    - Subscribing to channels and routing messages
    - Message serialization/deserialization
    - Connection management and reconnection
    - Error handling and logging
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379/1", service_name: str = "ai_engine"):
        self.redis_url = redis_url
        self.service_name = service_name
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None
        self.message_handlers: Dict[str, List[Callable]] = {}
        self.is_connected = False
        self.is_listening = False
        
        # Message type to class mapping
        self.message_classes = {
            MessageType.TASK_EXECUTE: TaskExecuteMessage,
            MessageType.TASK_STATUS_UPDATE: TaskStatusUpdateMessage,
            MessageType.TASK_COMPLETED: TaskCompletedMessage,
            MessageType.TASK_FAILED: TaskFailedMessage,
            MessageType.AGENT_STATUS: AgentStatusMessage,
            MessageType.SYSTEM_STATUS: SystemStatusMessage,
        }
    
    async def connect(self) -> bool:
        """Establish connection to Redis"""
        try:
            self.redis_client = redis.from_url(self.redis_url)
            await self.redis_client.ping()
            self.is_connected = True
            logger.info(f"Connected to Redis at {self.redis_url}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.is_connected = False
            return False
    
    async def disconnect(self):
        """Close Redis connection"""
        try:
            if self.pubsub:
                await self.pubsub.close()
            if self.redis_client:
                await self.redis_client.close()
            self.is_connected = False
            self.is_listening = False
            logger.info("Disconnected from Redis")
        except Exception as e:
            logger.error(f"Error disconnecting from Redis: {e}")
    
    async def publish_message(self, channel: str, message: BaseMessage) -> bool:
        """
        Publish a message to a Redis channel
        
        Args:
            channel: Redis channel name
            message: Message object to publish
            
        Returns:
            True if published successfully, False otherwise
        """
        if not self.is_connected:
            logger.error("Not connected to Redis")
            return False
        
        try:
            # Add metadata
            message.source = MessageSource.AI_ENGINE if self.service_name == "ai_engine" else MessageSource.MAAS_PLATFORM
            message.timestamp = datetime.now(timezone.utc)
            
            # Serialize message
            message_data = message.model_dump_json()
            
            # Publish to Redis
            await self.redis_client.publish(channel, message_data)
            logger.info(f"Published message to {channel}: {message.message_type}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to publish message to {channel}: {e}")
            return False
    
    async def subscribe_to_channels(self, channels: List[str]):
        """Subscribe to multiple Redis channels"""
        if not self.is_connected:
            logger.error("Not connected to Redis")
            return
        
        try:
            self.pubsub = self.redis_client.pubsub()
            for channel in channels:
                await self.pubsub.subscribe(channel)
                logger.info(f"Subscribed to channel: {channel}")
        except Exception as e:
            logger.error(f"Failed to subscribe to channels: {e}")
    
    def add_message_handler(self, channel: str, handler: Callable):
        """
        Add a message handler for a specific channel
        
        Args:
            channel: Redis channel name
            handler: Async function to handle messages
        """
        if channel not in self.message_handlers:
            self.message_handlers[channel] = []
        self.message_handlers[channel].append(handler)
        logger.debug(f"Added message handler for channel: {channel}")
    
    async def start_listening(self):
        """Start listening for messages on subscribed channels"""
        if not self.pubsub:
            logger.error("No active subscription")
            return
        
        self.is_listening = True
        logger.info("Started listening for messages")
        
        try:
            async for message in self.pubsub.listen():
                if not self.is_listening:
                    break
                    
                if message['type'] == 'message':
                    await self._handle_message(message)
                    
        except Exception as e:
            logger.error(f"Error in message listener: {e}")
            self.is_listening = False
            
            # Attempt to reconnect
            if self.is_connected:
                await asyncio.sleep(5)
                logger.info("Attempting to restart message listener")
                asyncio.create_task(self.start_listening())
    
    def stop_listening(self):
        """Stop listening for messages"""
        self.is_listening = False
        logger.info("Stopped listening for messages")
    
    async def _handle_message(self, redis_message):
        """Handle incoming Redis message"""
        try:
            # Parse message data
            raw_data = redis_message['data']
            if isinstance(raw_data, bytes):
                raw_data = raw_data.decode('utf-8')
            
            message_data = json.loads(raw_data)
            channel = redis_message['channel'].decode('utf-8') if isinstance(redis_message['channel'], bytes) else redis_message['channel']
            
            # Validate and deserialize message
            message = await self._deserialize_message(message_data)
            if not message:
                return
            
            # Route to handlers
            if channel in self.message_handlers:
                for handler in self.message_handlers[channel]:
                    try:
                        await handler(message)
                    except Exception as e:
                        logger.error(f"Error in message handler: {e}")
            else:
                logger.warning(f"No handlers registered for channel: {channel}")
                
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    async def _deserialize_message(self, message_data: Dict[str, Any]) -> Optional[BaseMessage]:
        """Deserialize message data into appropriate message object"""
        try:
            message_type = message_data.get('message_type')
            if not message_type:
                logger.error("Message missing message_type field")
                return None
            
            # Get appropriate message class
            message_class = self.message_classes.get(MessageType(message_type))
            if not message_class:
                logger.error(f"Unknown message type: {message_type}")
                return None
            
            # Deserialize message
            return message_class(**message_data)
            
        except ValidationError as e:
            logger.error(f"Message validation error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error deserializing message: {e}")
            return None
    
    async def publish_task_execute(self, task_id: str, task_data: Dict[str, Any]) -> bool:
        """Convenience method to publish task execution request"""
        message = TaskExecuteMessage(
            task_id=task_id, 
            data=task_data,
            source=MessageSource.AI_ENGINE if self.service_name == "ai_engine" else MessageSource.MAAS_PLATFORM
        )
        return await self.publish_message(RedisChannels.TASK_REQUESTS, message)
    
    async def publish_task_status(self, task_id: str, status_data: Dict[str, Any]) -> bool:
        """Convenience method to publish task status update"""
        message = TaskStatusUpdateMessage(
            task_id=task_id, 
            data=status_data,
            source=MessageSource.AI_ENGINE if self.service_name == "ai_engine" else MessageSource.MAAS_PLATFORM
        )
        return await self.publish_message(RedisChannels.TASK_STATUS, message)
    
    async def publish_task_completed(self, task_id: str, completion_data: Dict[str, Any]) -> bool:
        """Convenience method to publish task completion"""
        message = TaskCompletedMessage(
            task_id=task_id, 
            data=completion_data,
            source=MessageSource.AI_ENGINE if self.service_name == "ai_engine" else MessageSource.MAAS_PLATFORM
        )
        return await self.publish_message(RedisChannels.TASK_RESULTS, message)
    
    async def publish_task_failed(self, task_id: str, failure_data: Dict[str, Any]) -> bool:
        """Convenience method to publish task failure"""
        message = TaskFailedMessage(
            task_id=task_id, 
            data=failure_data,
            source=MessageSource.AI_ENGINE if self.service_name == "ai_engine" else MessageSource.MAAS_PLATFORM
        )
        return await self.publish_message(RedisChannels.TASK_RESULTS, message)
    
    async def publish_agent_status(self, agent_id: str, status_data: Dict[str, Any]) -> bool:
        """Convenience method to publish agent status"""
        message = AgentStatusMessage(
            source=MessageSource.AI_ENGINE if self.service_name == "ai_engine" else MessageSource.MAAS_PLATFORM,
            agent_id=agent_id, 
            data=status_data
        )
        return await self.publish_message(RedisChannels.AGENT_STATUS, message)
    
    async def publish_system_status(self, status_data: Dict[str, Any]) -> bool:
        """Convenience method to publish system status"""
        message = SystemStatusMessage(
            source=MessageSource.AI_ENGINE if self.service_name == "ai_engine" else MessageSource.MAAS_PLATFORM,
            data=status_data
        )
        return await self.publish_message(RedisChannels.SYSTEM_STATUS, message)
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on Redis connection"""
        try:
            if not self.is_connected:
                return {"status": "disconnected", "error": "Not connected to Redis"}
            
            # Test Redis connectivity
            latency = await self.redis_client.ping()
            
            # Get Redis info
            info = await self.redis_client.info('server')
            
            return {
                "status": "healthy",
                "connected": self.is_connected,
                "listening": self.is_listening,
                "latency_ms": latency * 1000 if isinstance(latency, (int, float)) else None,
                "redis_version": info.get('redis_version'),
                "channels_subscribed": len(self.message_handlers)
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "connected": False,
                "listening": False
            }