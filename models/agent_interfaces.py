"""
Agent Interfaces and Base Classes for Parkinson's Multiagent System

This module defines the common interfaces and base functionality
that all agents must implement for proper system integration.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
import asyncio
import logging
import uuid

from models.data_models import (
    ActionFlag, ActionFlagType, ActionFlagStatus, SessionData,
    UserInput, Response, AgentMessage
)

# Configure logging
logger = logging.getLogger(__name__)


class AgentInterface(ABC):
    """
    Abstract base interface that all agents must implement.
    Defines the contract for agent behavior and communication.
    """
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the agent and start background tasks"""
        pass
    
    @abstractmethod
    async def process_task(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process a task/event assigned to this agent"""
        pass
    
    @abstractmethod
    async def shutdown(self) -> None:
        """Shutdown the agent and cleanup all resources"""
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Return the health status of this agent"""
        pass
    
    @abstractmethod
    def get_agent_id(self) -> str:
        """Return the unique identifier for this agent"""
        pass


class SupervisorInterface(ABC):
    """
    Interface for the Supervisor Agent specifically.
    Handles workflow orchestration and user interaction.
    """
    
    @abstractmethod
    async def process_user_input(self, user_input: UserInput) -> Response:
        """Process user input and coordinate agent workflow"""
        pass
    
    @abstractmethod
    async def orchestrate_workflow(self, session_id: str, workflow_type: str) -> Dict[str, Any]:
        """Orchestrate multi-agent workflow based on user request"""
        pass
    
    @abstractmethod
    async def handle_chat_request(self, user_input: UserInput) -> Response:
        """Handle chat-only requests without prediction or reporting"""
        pass


class PredictionInterface(ABC):
    """
    Interface for the AI/ML Agent for medical predictions.
    Handles MRI processing and Parkinson's classification.
    """
    
    @abstractmethod
    async def process_mri_scan(self, session_id: str, mri_file_path: str) -> Dict[str, Any]:
        """Process MRI scan and generate Parkinson's prediction"""
        pass
    
    @abstractmethod
    async def extract_features(self, mri_file_path: str) -> Dict[str, Any]:
        """Extract medical features from MRI scan"""
        pass
    
    @abstractmethod
    async def classify_parkinsons(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Classify Parkinson's disease from extracted features"""
        pass


class ReportGenerationInterface(ABC):
    """
    Interface for the RAG Agent for report generation.
    Handles knowledge retrieval and medical report creation.
    """
    
    @abstractmethod
    async def generate_medical_report(self, session_id: str) -> Dict[str, Any]:
        """Generate comprehensive medical report"""
        pass
    
    @abstractmethod
    async def search_knowledge_base(self, query: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search medical knowledge base for relevant information"""
        pass
    
    @abstractmethod
    async def synthesize_report_content(self, prediction_data: Dict[str, Any], 
                                      knowledge_entries: List[Dict[str, Any]]) -> str:
        """Synthesize report content from prediction and knowledge"""
        pass


class BaseAgent(AgentInterface):
    """
    Base implementation for all agents in the system.
    Provides common functionality for communication, monitoring, and error handling.
    """
    
    def __init__(self, shared_memory, config: Dict[str, Any], agent_id: Optional[str] = None):
        self.agent_id = agent_id or f"{self.__class__.__name__.lower()}_{id(self)}"
        self.shared_memory = shared_memory
        self.config = config
        self.running = False
        self.monitoring_task = None
        self.error_count = 0
        self.last_activity = datetime.now()
        self.is_initialized = False
        self.is_shutdown = False
        
        # Setup logging for this agent
        self.logger = logging.getLogger(f"{__name__}.{self.agent_id}")
        
        # Event subscriptions
        self.event_subscriptions: List[str] = []
    
    async def initialize(self) -> None:
        """Initialize the agent and start background tasks"""
        if self.is_initialized:
            self.logger.warning(f"Agent {self.agent_id} already initialized")
            return
            
        self.logger.debug(f"[LIFECYCLE] Initializing agent {self.agent_id}")
        
        self.running = True
        self.last_activity = datetime.now()
        
        # Subscribe to relevant events
        await self._setup_event_subscriptions()
        
        # Start monitoring task inside initialize
        self.monitoring_task = asyncio.create_task(self._monitor_tasks())
        
        self.is_initialized = True
        self.logger.info(f"Agent {self.agent_id} initialized successfully")
    
    async def process_task(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process a task/event - to be overridden by subclasses"""
        self.logger.debug(f"[TASK] Processing {event_type} with payload: {payload}")
        return {"status": "completed", "message": "Base implementation - override in subclass"}
    
    async def shutdown(self) -> None:
        """Shutdown the agent and cleanup all resources"""
        if self.is_shutdown:
            self.logger.warning(f"Agent {self.agent_id} already shutdown")
            return
            
        self.logger.debug(f"[LIFECYCLE] Shutting down agent {self.agent_id}")
        
        self.running = False
        
        # Cancel monitoring task
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        # Unsubscribe from events
        self.shared_memory.unsubscribe_from_events(self.agent_id)
        
        self.is_shutdown = True
        self.logger.info(f"Agent {self.agent_id} shutdown completed")
    
    # Legacy methods for backward compatibility (will be removed)
    async def start(self) -> None:
        """Legacy method - use initialize() instead"""
        await self.initialize()
    
    async def stop(self) -> None:
        """Legacy method - use shutdown() instead"""
        await self.shutdown()
    
    def get_agent_id(self) -> str:
        """Return the unique identifier for this agent"""
        return self.agent_id
    
    async def health_check(self) -> Dict[str, Any]:
        """Return the health status of this agent"""
        return {
            'agent_id': self.agent_id,
            'status': 'healthy' if self.running else 'stopped',
            'running': self.running,
            'error_count': self.error_count,
            'last_activity': self.last_activity.isoformat(),
            'uptime_seconds': (datetime.now() - self.last_activity).total_seconds() if self.running else 0
        }
    
    async def _setup_event_subscriptions(self):
        """Setup event subscriptions for this agent"""
        # Default subscriptions - subclasses can override
        default_events = [
            f"message_{self.agent_id}",
            "session_created",
            "system_shutdown"
        ]
        
        self.shared_memory.subscribe_to_events(
            self.agent_id,
            default_events,
            self._handle_event
        )
    
    async def _handle_event(self, event: Dict[str, Any]):
        """Handle incoming events"""
        try:
            event_type = event.get('event_type')
            
            if event_type == f"message_{self.agent_id}":
                await self._handle_agent_message(event.get('data', {}))
            elif event_type == "system_shutdown":
                await self.stop()
            
            self.last_activity = datetime.now()
            
        except Exception as e:
            self.error_count += 1
            self.logger.error(f"Error handling event {event.get('event_type')}: {e}")
    
    async def _handle_agent_message(self, message_data: Dict[str, Any]):
        """Handle messages sent to this agent"""
        message_id = message_data.get('message_id')
        sender = message_data.get('sender')
        message_type = message_data.get('message_type')
        payload = message_data.get('payload', {})
        
        self.logger.info(f"Received message from {sender}: {message_type}")
        
        # Process the message based on type
        try:
            await self._process_agent_message(message_type, payload)
            
            # Mark message as processed
            if message_id:
                await self.shared_memory.mark_message_processed(message_id)
                
        except Exception as e:
            self.error_count += 1
            self.logger.error(f"Error processing message {message_type}: {e}")
    
    async def _process_agent_message(self, message_type: str, payload: Dict[str, Any]):
        """Process specific agent messages - to be overridden by subclasses"""
        pass
    
    async def _monitor_tasks(self):
        """Monitor for tasks assigned to this agent"""
        while self.running:
            try:
                # Check for unprocessed messages
                messages = await self.shared_memory.get_agent_messages(self.agent_id)
                
                for message in messages:
                    await self._handle_agent_message(message)
                
                # Check for relevant action flags (to be implemented by subclasses)
                await self._check_action_flags()
                
                # Sleep before next check
                await asyncio.sleep(self.config.get('monitoring_interval', 5))
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.error_count += 1
                self.logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(5)  # Back off on error
    
    async def _check_action_flags(self):
        """Check for action flags relevant to this agent - to be overridden"""
        pass
    
    async def send_message(self, receiver: str, message_type: str, 
                          payload: Dict[str, Any], session_id: str) -> str:
        """Send a message to another agent"""
        return await self.shared_memory.send_agent_message(
            sender=self.agent_id,
            receiver=receiver,
            message_type=message_type,
            payload=payload,
            session_id=session_id
        )
    
    async def set_action_flag(self, flag_type: ActionFlagType, session_id: str, 
                            data: Dict[str, Any], priority: int = 0) -> str:
        """Set an action flag for workflow coordination"""
        return await self.shared_memory.set_action_flag(
            flag_type=flag_type,
            session_id=session_id,
            data=data,
            priority=priority
        )
    
    async def complete_action_flag(self, flag_id: str) -> bool:
        """Mark an action flag as completed"""
        return await self.shared_memory.complete_action_flag(flag_id)
    
    async def fail_action_flag(self, flag_id: str) -> bool:
        """Mark an action flag as failed"""
        return await self.shared_memory.fail_action_flag(flag_id)
    
    def _handle_error(self, error: Exception, context: str = ""):
        """Standard error handling for agents"""
        self.error_count += 1
        error_msg = f"Agent {self.agent_id} error"
        if context:
            error_msg += f" in {context}"
        error_msg += f": {str(error)}"
        
        self.logger.error(error_msg)
        
        # Could implement circuit breaker pattern here
        if self.error_count > self.config.get('max_errors', 10):
            self.logger.critical(f"Agent {self.agent_id} exceeded maximum errors, stopping")
            asyncio.create_task(self.stop())


class PredictionAgent(BaseAgent, PredictionInterface):
    """
    Base class for AI/ML agents that perform medical predictions.
    Implements common prediction workflow patterns.
    """
    
    def __init__(self, shared_memory_interface, config: Dict[str, Any], agent_id: Optional[str] = None):
        super().__init__(shared_memory_interface, config, agent_id)
        self.prediction_flags = [ActionFlagType.PREDICT_PARKINSONS]
    
    async def process_task(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process prediction tasks"""
        self.logger.debug(f"[PREDICTION] Processing {event_type}")
        
        if event_type.startswith('flag_created_'):
            return await self._handle_prediction_flag(payload)
        
        return await super().process_task(event_type, payload)
    
    async def _setup_event_subscriptions(self):
        """Setup prediction-specific event subscriptions"""
        await super()._setup_event_subscriptions()
        
        # Subscribe to prediction flags
        prediction_events = [f"flag_created_{flag.value}" for flag in self.prediction_flags]
        
        self.shared_memory.subscribe_to_events(
            f"{self.agent_id}_predictions",
            prediction_events,
            self._handle_prediction_flag
        )
    
    async def _handle_prediction_flag(self, event: Dict[str, Any]):
        """Handle prediction flag events"""
        try:
            data = event.get('data', {})
            flag_id = data.get('flag_id')
            session_id = event.get('session_id')
            
            if flag_id and session_id:
                # Claim the flag
                claimed = await self.shared_memory.claim_action_flag(flag_id, self.agent_id)
                if claimed:
                    # Process the prediction task
                    await self._process_prediction_task(flag_id, session_id, data)
                    
        except Exception as e:
            self._handle_error(e, "handling prediction flag")
    
    async def _process_prediction_task(self, flag_id: str, session_id: str, data: Dict[str, Any]):
        """Process a prediction task"""
        try:
            # Get MRI data for the session
            mri_data_list = await self.shared_memory.get_mri_data(session_id)
            
            if not mri_data_list:
                await self.fail_action_flag(flag_id)
                self.logger.error(f"No MRI data found for session {session_id}")
                return
            
            # Process the most recent MRI scan
            mri_data = mri_data_list[-1]  # Get the latest scan
            
            # Perform prediction
            result = await self.process_mri_scan(session_id, mri_data['file_path'])
            
            # Store prediction result
            from models.data_models import PredictionResult, PredictionType
            prediction = PredictionResult(
                prediction_id=str(uuid.uuid4()),
                session_id=session_id,
                mri_scan_id=mri_data['id'],
                prediction_type=PredictionType.BINARY,
                binary_result=result.get('binary_result'),
                stage_result=result.get('stage_result'),
                confidence_score=result.get('confidence_score'),
                binary_confidence=result.get('binary_confidence'),
                stage_confidence=result.get('stage_confidence'),
                model_version=result.get('model_version', 'v1.0'),
                processing_time=result.get('processing_time')
            )
            
            await self.shared_memory.store_prediction(prediction)
            
            # Complete the flag
            await self.complete_action_flag(flag_id)
            
            self.logger.info(f"Completed prediction for session {session_id}")
            
        except Exception as e:
            await self.fail_action_flag(flag_id)
            self._handle_error(e, f"processing prediction task {flag_id}")


class ReportAgent(BaseAgent, ReportGenerationInterface):
    """
    Base class for RAG agents that generate medical reports.
    Implements common report generation workflow patterns.
    """
    
    def __init__(self, shared_memory_interface, config: Dict[str, Any], agent_id: Optional[str] = None):
        super().__init__(shared_memory_interface, config, agent_id)
        self.report_flags = [ActionFlagType.GENERATE_REPORT]
    
    async def process_task(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process report generation tasks"""
        self.logger.debug(f"[REPORT] Processing {event_type}")
        
        if event_type.startswith('flag_created_'):
            return await self._handle_report_flag(payload)
        
        return await super().process_task(event_type, payload)
    
    async def _setup_event_subscriptions(self):
        """Setup report-specific event subscriptions"""
        await super()._setup_event_subscriptions()
        
        # Subscribe to report generation flags
        report_events = [f"flag_created_{flag.value}" for flag in self.report_flags]
        
        self.shared_memory.subscribe_to_events(
            f"{self.agent_id}_reports",
            report_events,
            self._handle_report_flag
        )
    
    async def _handle_report_flag(self, event: Dict[str, Any]):
        """Handle report generation flag events"""
        try:
            data = event.get('data', {})
            flag_id = data.get('flag_id')
            session_id = event.get('session_id')
            
            if flag_id and session_id:
                # Claim the flag
                claimed = await self.shared_memory.claim_action_flag(flag_id, self.agent_id)
                if claimed:
                    # Process the report generation task
                    await self._process_report_task(flag_id, session_id, data)
                    
        except Exception as e:
            self._handle_error(e, "handling report flag")
    
    async def _process_report_task(self, flag_id: str, session_id: str, data: Dict[str, Any]):
        """Process a report generation task"""
        try:
            # Generate the medical report
            result = await self.generate_medical_report(session_id)
            
            # Store the report
            from models.data_models import MedicalReport
            report = MedicalReport(
                report_id=str(uuid.uuid4()),
                session_id=session_id,
                prediction_id=result.get('prediction_id'),
                report_type=result.get('report_type', 'full'),
                title=result.get('title', 'Medical Analysis Report'),
                content=result.get('content', ''),
                recommendations=result.get('recommendations', []),
                confidence_level=result.get('confidence_level')
            )
            
            await self.shared_memory.store_report(report)
            
            # Complete the flag
            await self.complete_action_flag(flag_id)
            
            self.logger.info(f"Completed report generation for session {session_id}")
            
        except Exception as e:
            await self.fail_action_flag(flag_id)
            self._handle_error(e, f"processing report task {flag_id}")


# Error handling decorators
def handle_agent_errors(func):
    """Decorator for handling agent method errors"""
    async def wrapper(self, *args, **kwargs):
        try:
            return await func(self, *args, **kwargs)
        except Exception as e:
            if hasattr(self, '_handle_error'):
                self._handle_error(e, func.__name__)
            else:
                logger.error(f"Error in {func.__name__}: {e}")
            raise
    return wrapper


def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """Decorator for retrying failed operations"""
    def decorator(func):
        async def wrapper(self, *args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await func(self, *args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {e}")
                    await asyncio.sleep(delay * (2 ** attempt))  # Exponential backoff
            return None
        return wrapper
    return decorator