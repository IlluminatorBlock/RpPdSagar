"""
Shared Memory Interface for Parkinson's Multiagent System

This module implements the central communication hub for all agents,
providing action flags, event bus, and coordinated data access.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
import json
import uuid

from core.database import DatabaseManager
from models.data_models import (
    ActionFlag, ActionFlagType, ActionFlagStatus, SessionData, 
    PredictionResult, MedicalReport, AgentMessage, MRIData
)

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class EventSubscription:
    """Represents an event subscription"""
    subscriber_id: str
    event_types: List[str]
    callback: Callable
    created_at: datetime


class EventBus:
    """
    Event-driven communication system for real-time agent coordination
    """
    
    def __init__(self):
        self.subscribers: Dict[str, EventSubscription] = {}
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.running = False
        self._event_processor_task = None
    
    async def start(self):
        """Start the event bus"""
        self.running = True
        self._event_processor_task = asyncio.create_task(self._process_events())
        logger.info("Event bus started")
    
    async def stop(self):
        """Stop the event bus"""
        self.running = False
        if self._event_processor_task:
            self._event_processor_task.cancel()
            try:
                await self._event_processor_task
            except asyncio.CancelledError:
                pass
        logger.info("Event bus stopped")
    
    def subscribe(self, subscriber_id: str, event_types: List[str], callback: Callable) -> str:
        """Subscribe to specific event types"""
        subscription = EventSubscription(
            subscriber_id=subscriber_id,
            event_types=event_types,
            callback=callback,
            created_at=datetime.now()
        )
        self.subscribers[subscriber_id] = subscription
        logger.info(f"Subscriber {subscriber_id} registered for events: {event_types}")
        return subscriber_id
    
    def unsubscribe(self, subscriber_id: str):
        """Unsubscribe from events"""
        if subscriber_id in self.subscribers:
            del self.subscribers[subscriber_id]
            logger.info(f"Subscriber {subscriber_id} unsubscribed")
    
    async def publish(self, event_type: str, data: Dict[str, Any], session_id: str):
        """Publish an event to the bus"""
        logger.debug(f"[EVENT_PUBLISH] Type: {event_type}, Session: {session_id}, Data: {str(data)[:100]}...")
        
        event = {
            'event_id': str(uuid.uuid4()),
            'event_type': event_type,
            'data': data,
            'session_id': session_id,
            'timestamp': datetime.now().isoformat()
        }
        await self.event_queue.put(event)
        logger.debug(f"[EVENT_QUEUED] Event {event['event_id']} queued for processing")
    
    async def _process_events(self):
        """Process events from the queue"""
        while self.running:
            try:
                # Wait for event with timeout to allow periodic cleanup
                event = await asyncio.wait_for(self.event_queue.get(), timeout=1.0)
                
                # Notify subscribers
                for subscriber_id, subscription in self.subscribers.items():
                    if event['event_type'] in subscription.event_types:
                        try:
                            if asyncio.iscoroutinefunction(subscription.callback):
                                await subscription.callback(event)
                            else:
                                subscription.callback(event)
                        except Exception as e:
                            logger.error(f"Error in subscriber {subscriber_id}: {e}")
                
            except asyncio.TimeoutError:
                # Periodic maintenance - could add cleanup here
                continue
            except Exception as e:
                logger.error(f"Event processing error: {e}")


class SharedMemoryInterface:
    """
    Central communication hub for all agent interactions.
    Implements action flags, event bus, and coordinated data access.
    """
    
    def __init__(self, database_path: str):
        self.db_manager = DatabaseManager(database_path)
        self.event_bus = EventBus()
        self.memory_cache: Dict[str, Any] = {}
        self.cache_ttl = 300  # 5 minutes
        self.cache_timestamps: Dict[str, datetime] = {}
        self._monitoring_task = None
        self._flag_cleanup_task = None
    
    async def initialize(self):
        """Initialize the shared memory system"""
        logger.debug("[LIFECYCLE] Initializing SharedMemoryInterface")
        
        await self.db_manager.init_database()
        await self.event_bus.start()
        
        # Start background tasks
        self._monitoring_task = asyncio.create_task(self._monitor_action_flags())
        self._flag_cleanup_task = asyncio.create_task(self._cleanup_expired_flags())
        
        logger.info("Shared memory interface initialized")
    
    async def shutdown(self):
        """Shutdown the shared memory system"""
        logger.debug("[LIFECYCLE] Shutting down SharedMemoryInterface")
        
        await self.event_bus.stop()
        
        # Cancel background tasks
        if self._monitoring_task:
            self._monitoring_task.cancel()
        if self._flag_cleanup_task:
            self._flag_cleanup_task.cancel()
        
        logger.info("Shared memory interface shutdown")
    
    async def start_cleanup_task(self, interval: int = 60):
        """Start background cleanup task for main.py compatibility"""
        logger.debug(f"[CLEANUP] Starting cleanup task with {interval}s interval")
        
        # Additional cleanup task that can be started independently
        if not hasattr(self, '_additional_cleanup_task') or self._additional_cleanup_task is None:
            self._additional_cleanup_task = asyncio.create_task(self._additional_cleanup_loop(interval))
            logger.info("SharedMemory additional cleanup task started")
        else:
            logger.info("SharedMemory cleanup task already running")
    
    async def stop_cleanup_task(self):
        """Stop background cleanup task for main.py compatibility"""
        logger.debug("[CLEANUP] Stopping additional cleanup task")
        
        if hasattr(self, '_additional_cleanup_task') and self._additional_cleanup_task:
            self._additional_cleanup_task.cancel()
            try:
                await self._additional_cleanup_task
            except asyncio.CancelledError:
                pass
            self._additional_cleanup_task = None
            
        logger.info("SharedMemory additional cleanup task stopped")
    
    async def _additional_cleanup_loop(self, interval: int):
        """Additional cleanup loop for expired sessions and stale data"""
        while True:
            try:
                logger.debug("[CLEANUP] Running additional cleanup cycle")
                
                # Cleanup expired sessions
                expired_sessions = await self.db_manager.cleanup_expired_sessions()
                if expired_sessions > 0:
                    logger.info(f"[CLEANUP] Removed {expired_sessions} expired sessions")
                
                # Cleanup stale cache entries
                current_time = datetime.now()
                stale_keys = [
                    key for key, timestamp in self.cache_timestamps.items()
                    if (current_time - timestamp).total_seconds() > self.cache_ttl
                ]
                
                for key in stale_keys:
                    del self.memory_cache[key]
                    del self.cache_timestamps[key]
                
                if stale_keys:
                    logger.debug(f"[CLEANUP] Removed {len(stale_keys)} stale cache entries")
                
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                logger.debug("[CLEANUP] Additional cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"[CLEANUP] Error in additional cleanup: {e}")
                await asyncio.sleep(5)  # Back off on error
    
    # Action Flag Operations
    async def set_action_flag(self, flag_type: ActionFlagType, session_id: str, 
                            data: Dict[str, Any], priority: int = 0, 
                            expires_in_minutes: int = 30) -> str:
        """Set an action flag to trigger agent workflow"""
        expires_at = datetime.now() + timedelta(minutes=expires_in_minutes)
        
        action_flag = ActionFlag(
            flag_id=str(uuid.uuid4()),
            session_id=session_id,
            flag_type=flag_type,
            status=ActionFlagStatus.PENDING,
            priority=priority,
            data=data,
            expires_at=expires_at
        )
        
        flag_id = await self.db_manager.create_action_flag(action_flag)
        
        # Publish event for real-time notification
        await self.event_bus.publish(
            f"flag_created_{flag_type.value}", 
            {
                'flag_id': flag_id,
                'flag_type': flag_type.value,
                'priority': priority,
                'data': data
            },
            session_id
        )
        
        logger.info(f"Set action flag: {flag_type.value} for session {session_id}")
        return flag_id
    
    async def get_pending_flags(self, flag_type: Optional[ActionFlagType] = None) -> List[ActionFlag]:
        """Get all pending action flags"""
        return await self.db_manager.get_pending_flags(flag_type)
    
    async def claim_action_flag(self, flag_id: str, agent_id: str) -> bool:
        """Claim an action flag for processing"""
        success = await self.db_manager.update_action_flag_status(
            flag_id, ActionFlagStatus.IN_PROGRESS, agent_id
        )
        
        if success:
            logger.info(f"Agent {agent_id} claimed flag {flag_id}")
            # Publish event
            flag = await self._get_flag_by_id(flag_id)
            if flag:
                await self.event_bus.publish(
                    f"flag_claimed_{flag.flag_type.value}",
                    {'flag_id': flag_id, 'agent_id': agent_id},
                    flag.session_id
                )
        
        return success
    
    async def complete_action_flag(self, flag_id: str) -> bool:
        """Mark an action flag as completed"""
        success = await self.db_manager.update_action_flag_status(
            flag_id, ActionFlagStatus.COMPLETED
        )
        
        if success:
            logger.info(f"Completed action flag {flag_id}")
            # Publish completion event
            flag = await self._get_flag_by_id(flag_id)
            if flag:
                await self.event_bus.publish(
                    f"flag_completed_{flag.flag_type.value}",
                    {'flag_id': flag_id},
                    flag.session_id
                )
        
        return success
    
    async def fail_action_flag(self, flag_id: str) -> bool:
        """Mark an action flag as failed"""
        success = await self.db_manager.update_action_flag_status(
            flag_id, ActionFlagStatus.FAILED
        )
        
        if success:
            logger.info(f"Failed action flag {flag_id}")
            # Publish failure event
            flag = await self._get_flag_by_id(flag_id)
            if flag:
                await self.event_bus.publish(
                    f"flag_failed_{flag.flag_type.value}",
                    {'flag_id': flag_id},
                    flag.session_id
                )
        
        return success
    
    async def _get_flag_by_id(self, flag_id: str) -> Optional[ActionFlag]:
        """Helper to get flag by ID"""
        # This would need to be implemented in database manager
        # For now, return None as placeholder
        return None
    
    # Session Data Operations
    async def create_session(self, session_data: SessionData) -> str:
        """Create a new session"""
        session_id = await self.db_manager.create_session(session_data)
        
        # Cache session data
        self._cache_data(f"session_{session_id}", session_data)
        
        # Publish session created event
        await self.event_bus.publish(
            "session_created",
            {'session_id': session_id, 'input_type': session_data.input_type.value},
            session_id
        )
        
        return session_id
    
    async def get_session_data(self, session_id: str) -> Optional[SessionData]:
        """Get session data"""
        # Try cache first
        cached = self._get_cached_data(f"session_{session_id}")
        if cached:
            return cached
        
        # Get from database
        session_data = await self.db_manager.get_session(session_id)
        if session_data:
            self._cache_data(f"session_{session_id}", session_data)
        
        return session_data
    
    # Prediction Operations
    async def store_prediction(self, prediction: PredictionResult) -> str:
        """Store prediction result"""
        prediction_id = await self.db_manager.store_prediction(prediction)
        
        # Cache prediction
        self._cache_data(f"prediction_{prediction.session_id}", prediction)
        
        # Publish prediction stored event
        await self.event_bus.publish(
            "prediction_stored",
            {
                'prediction_id': prediction_id,
                'binary_result': prediction.binary_result,
                'stage_result': prediction.stage_result,
                'confidence_score': prediction.confidence_score
            },
            prediction.session_id
        )
        
        return prediction_id
    
    async def get_latest_prediction(self, session_id: str) -> Optional[PredictionResult]:
        """Get the latest prediction for a session"""
        # Try cache first
        cached = self._get_cached_data(f"prediction_{session_id}")
        if cached:
            return cached
        
        # Get from database
        prediction = await self.db_manager.get_latest_prediction(session_id)
        if prediction:
            self._cache_data(f"prediction_{session_id}", prediction)
        
        return prediction
    
    async def get_all_predictions(self, session_id: str) -> List[PredictionResult]:
        """Get all predictions for a session"""
        return await self.db_manager.get_predictions_by_session(session_id)
    
    # Report Operations
    async def store_report(self, report: MedicalReport) -> str:
        """Store medical report"""
        report_id = await self.db_manager.store_medical_report(report)
        
        # Cache report
        self._cache_data(f"report_{report.session_id}", report)
        
        # Publish report stored event
        await self.event_bus.publish(
            "report_stored",
            {
                'report_id': report_id,
                'report_type': report.report_type,
                'title': report.title
            },
            report.session_id
        )
        
        return report_id
    
    async def get_reports(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all reports for a session"""
        return await self.db_manager.get_reports_by_session(session_id)
    
    async def check_existing_reports(self, patient_id: str) -> List[Dict[str, Any]]:
        """Check existing reports for a patient"""
        return await self.db_manager.check_existing_reports(patient_id)
    
    # MRI Data Operations
    async def store_mri_data(self, mri_data: MRIData) -> str:
        """Store MRI scan data"""
        scan_id = await self.db_manager.store_mri_scan(mri_data)
        
        # Cache MRI data
        self._cache_data(f"mri_{mri_data.session_id}", mri_data)
        
        # Publish MRI stored event
        await self.event_bus.publish(
            "mri_stored",
            {
                'scan_id': scan_id,
                'file_path': mri_data.file_path,
                'file_type': mri_data.file_type
            },
            mri_data.session_id
        )
        
        return scan_id
    
    async def get_mri_data(self, session_id: str) -> List[Dict[str, Any]]:
        """Get MRI data for a session"""
        return await self.db_manager.get_mri_scans_by_session(session_id)
    
    # Agent Communication
    async def send_agent_message(self, sender: str, receiver: str, message_type: str, 
                                payload: Dict[str, Any], session_id: str) -> str:
        """Send message between agents"""
        message = AgentMessage(
            message_id=str(uuid.uuid4()),
            sender=sender,
            receiver=receiver,
            message_type=message_type,
            payload=payload,
            session_id=session_id
        )
        
        message_id = await self.db_manager.send_agent_message(message)
        
        # Publish message event
        await self.event_bus.publish(
            f"message_{receiver}",
            {
                'message_id': message_id,
                'sender': sender,
                'message_type': message_type,
                'payload': payload
            },
            session_id
        )
        
        return message_id
    
    async def get_agent_messages(self, receiver: str) -> List[Dict[str, Any]]:
        """Get unprocessed messages for an agent"""
        return await self.db_manager.get_agent_messages(receiver, processed=False)
    
    async def mark_message_processed(self, message_id: str) -> bool:
        """Mark a message as processed"""
        return await self.db_manager.mark_message_processed(message_id)
    
    # Event System
    def subscribe_to_events(self, agent_id: str, event_types: List[str], 
                          callback: Callable) -> str:
        """Subscribe agent to specific events"""
        return self.event_bus.subscribe(agent_id, event_types, callback)
    
    def unsubscribe_from_events(self, agent_id: str):
        """Unsubscribe agent from events"""
        self.event_bus.unsubscribe(agent_id)
    
    # Cache Management
    def _cache_data(self, key: str, data: Any):
        """Cache data with timestamp"""
        self.memory_cache[key] = data
        self.cache_timestamps[key] = datetime.now()
    
    def _get_cached_data(self, key: str) -> Optional[Any]:
        """Get cached data if not expired"""
        if key in self.memory_cache:
            timestamp = self.cache_timestamps.get(key)
            if timestamp and (datetime.now() - timestamp).seconds < self.cache_ttl:
                return self.memory_cache[key]
            else:
                # Remove expired cache
                self.memory_cache.pop(key, None)
                self.cache_timestamps.pop(key, None)
        return None
    
    def _clear_cache(self):
        """Clear all cached data"""
        self.memory_cache.clear()
        self.cache_timestamps.clear()
    
    # Background Tasks
    async def _monitor_action_flags(self):
        """Monitor action flags for processing"""
        while True:
            try:
                await asyncio.sleep(5)  # Check every 5 seconds
                
                # Check for flags that have been in progress too long
                # This could be expanded to implement timeout handling
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error monitoring action flags: {e}")
    
    async def _cleanup_expired_flags(self):
        """Clean up expired action flags"""
        while True:
            try:
                await asyncio.sleep(60)  # Run every minute
                cleaned_count = await self.db_manager.cleanup_expired_flags()
                if cleaned_count > 0:
                    logger.info(f"Cleaned up {cleaned_count} expired action flags")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error cleaning up expired flags: {e}")
    
    # System Health
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on shared memory system"""
        db_health = await self.db_manager.health_check()
        
        return {
            'shared_memory': {
                'status': 'healthy' if db_health.get('status') == 'healthy' else 'unhealthy',
                'cache_size': len(self.memory_cache),
                'event_subscribers': len(self.event_bus.subscribers),
                'event_queue_size': self.event_bus.event_queue.qsize(),
                'timestamp': datetime.now().isoformat()
            },
            'database': db_health
        }
    
    # Workflow Coordination Methods
    async def wait_for_completion(self, session_id: str, flag_type: ActionFlagType, 
                                timeout_seconds: int = 300) -> bool:
        """Wait for a specific action flag to complete"""
        start_time = datetime.now()
        
        # Map flag types to their completion equivalents
        completion_flag_map = {
            ActionFlagType.PREDICT_PARKINSONS: ActionFlagType.PREDICTION_COMPLETE,
            ActionFlagType.GENERATE_REPORT: ActionFlagType.REPORT_COMPLETE
        }
        
        completion_flag = completion_flag_map.get(flag_type)
        if not completion_flag:
            logger.warning(f"No completion flag mapping for {flag_type}")
            return False
        
        while (datetime.now() - start_time).seconds < timeout_seconds:
            # Check database for completion flag
            try:
                flags = await self.db_manager.get_pending_flags(completion_flag)
                session_flags = [f for f in flags if f.session_id == session_id]
                
                if session_flags:
                    logger.info(f"Found completion flag {completion_flag.value} for session {session_id}")
                    return True
                    
            except Exception as e:
                logger.error(f"Error checking completion flags: {e}")
            
            await asyncio.sleep(0.5)  # Check every 500ms
            
        logger.warning(f"Timeout waiting for {completion_flag.value} for session {session_id}")
        return False  # Timeout
    
    async def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """Get complete session summary"""
        return await self.db_manager.get_session_summary(session_id)