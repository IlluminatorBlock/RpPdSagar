"""
Comprehensive Audit Logging System

This module implements audit logging for all system actions:
- Log all retrieval queries with query, retrieved_doc_ids, scores
- Log report creation/deletion
- Log user authentication events
- Log permission checks and access attempts
- Track all database operations

Features:
- Structured logging with JSON format
- Database storage for audit events
- Query performance tracking
- User activity monitoring
- Security event tracking
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum

from core.database import DatabaseManager

logger = logging.getLogger(__name__)

class AuditEventType(Enum):
    """Types of audit events."""
    # Authentication events
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    REGISTRATION = "registration"
    
    # Data access events  
    READ_REPORT = "read_report"
    CREATE_REPORT = "create_report"
    UPDATE_REPORT = "update_report"
    DELETE_REPORT = "delete_report"
    
    # RAG/Knowledge base events
    KNOWLEDGE_QUERY = "knowledge_query"
    EMBEDDING_GENERATED = "embedding_generated"
    DOCUMENT_INDEXED = "document_indexed"
    
    # Permission events
    PERMISSION_CHECK = "permission_check"
    ACCESS_DENIED = "access_denied"
    
    # System events
    SYSTEM_START = "system_start"
    SYSTEM_ERROR = "system_error"
    DATABASE_MIGRATION = "database_migration"

@dataclass
class AuditEvent:
    """Structured audit event."""
    event_id: str
    event_type: AuditEventType
    actor_id: str
    actor_role: str
    target_id: Optional[str] = None
    target_type: Optional[str] = None
    action: str = ""
    details: Dict[str, Any] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None
    performance_metrics: Optional[Dict] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.event_id is None:
            self.event_id = str(uuid.uuid4())
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.details is None:
            self.details = {}

class AuditLogger:
    """Central audit logging system."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        
        # Setup structured logger for audit events
        self.audit_logger = logging.getLogger('audit')
        self.audit_logger.setLevel(logging.INFO)
        
        # Add file handler for audit logs
        if not self.audit_logger.handlers:
            handler = logging.FileHandler('logs/audit.log')
            formatter = logging.Formatter(
                '%(asctime)s - AUDIT - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.audit_logger.addHandler(handler)
            
    async def log_event(self, event: AuditEvent):
        """Log an audit event to both database and file."""
        try:
            # Log to database
            await self._log_to_database(event)
            
            # Log to file
            self._log_to_file(event)
            
        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")
            # Still try to log to file even if DB fails
            try:
                self._log_to_file(event)
            except Exception as file_error:
                logger.error(f"Failed to log to file: {file_error}")
                
    async def _log_to_database(self, event: AuditEvent):
        """Store audit event in database."""
        try:
            # Fix actor_role constraint - map 'system' to 'admin' for database compatibility
            actor_role = event.actor_role
            if actor_role not in ['admin', 'doctor', 'patient']:
                actor_role = 'admin'  # Default system operations to admin role
                
            async with self.db_manager.get_connection() as conn:
                await conn.execute("""
                    INSERT INTO audit_logs 
                    (log_id, action, actor_id, actor_role, target_id, target_type,
                     details, ip_address, user_agent, success, error_message, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event.event_id,
                    f"{event.event_type.value}:{event.action}" if event.action else event.event_type.value,
                    event.actor_id,
                    actor_role,  # Use the corrected role
                    event.target_id,
                    event.target_type,
                    json.dumps(event.details) if event.details else None,
                    event.ip_address,
                    event.user_agent,
                    event.success,
                    event.error_message,
                    event.timestamp.isoformat()
                ))
                
                await conn.commit()
                
        except Exception as e:
            logger.error(f"Error storing audit event in database: {e}")
            raise
            
    def _log_to_file(self, event: AuditEvent):
        """Log audit event to structured log file."""
        log_entry = {
            'event_id': event.event_id,
            'event_type': event.event_type.value,
            'actor_id': event.actor_id,
            'actor_role': event.actor_role,
            'target_id': event.target_id,
            'target_type': event.target_type,
            'action': event.action,
            'details': event.details,
            'success': event.success,
            'error_message': event.error_message,
            'performance_metrics': event.performance_metrics,
            'timestamp': event.timestamp.isoformat()
        }
        
        self.audit_logger.info(json.dumps(log_entry))
        
    # Convenience methods for common audit events
    
    async def log_authentication(self, actor_id: str, actor_role: str, 
                               success: bool, details: Dict = None,
                               error_message: str = None):
        """Log authentication event."""
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=AuditEventType.LOGIN_SUCCESS if success else AuditEventType.LOGIN_FAILURE,
            actor_id=actor_id,
            actor_role=actor_role,
            action="authenticate",
            success=success,
            error_message=error_message,
            details=details or {}
        )
        
        await self.log_event(event)
        
    async def log_knowledge_query(self, actor_id: str, actor_role: str,
                                query: str, retrieved_docs: List[Dict], 
                                performance_metrics: Dict = None):
        """Log knowledge base query with retrieved documents."""
        
        # Fix actor_role constraint - map 'system' to 'admin' for database compatibility
        if actor_role not in ['admin', 'doctor', 'patient']:
            actor_role = 'admin'  # Default system operations to admin role
        
        # Extract document IDs and scores
        doc_details = []
        for doc in retrieved_docs:
            doc_details.append({
                'doc_id': doc.get('id', 'unknown'),
                'score': doc.get('score', 0.0),
                'content_preview': doc.get('content', '')[:100] if doc.get('content') else ''
            })
        
        details = {
            'query': query,
            'query_length': len(query),
            'num_results': len(retrieved_docs),
            'retrieved_documents': doc_details,
            'performance_metrics': performance_metrics or {}
        }
        
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=AuditEventType.KNOWLEDGE_QUERY,
            actor_id=actor_id,
            actor_role=actor_role,
            action="retrieve_knowledge",
            target_type="knowledge_base",
            details=details,
            performance_metrics=performance_metrics
        )
        
        await self.log_event(event)
        
    async def log_report_action(self, actor_id: str, actor_role: str,
                              action: str, report_id: str, patient_id: str,
                              success: bool = True, error_message: str = None,
                              details: Dict = None):
        """Log report-related actions."""
        
        event_type_map = {
            'create': AuditEventType.CREATE_REPORT,
            'read': AuditEventType.READ_REPORT,
            'update': AuditEventType.UPDATE_REPORT,
            'delete': AuditEventType.DELETE_REPORT
        }
        
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type_map.get(action, AuditEventType.READ_REPORT),
            actor_id=actor_id,
            actor_role=actor_role,
            target_id=report_id,
            target_type="report",
            action=action,
            success=success,
            error_message=error_message,
            details={
                'patient_id': patient_id,
                **(details or {})
            }
        )
        
        await self.log_event(event)
        
    async def log_permission_check(self, actor_id: str, actor_role: str,
                                 requested_action: str, target_id: str,
                                 target_type: str, granted: bool,
                                 details: Dict = None):
        """Log permission check results."""
        
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=AuditEventType.PERMISSION_CHECK if granted else AuditEventType.ACCESS_DENIED,
            actor_id=actor_id,
            actor_role=actor_role,
            target_id=target_id,
            target_type=target_type,
            action=requested_action,
            success=granted,
            error_message="Access denied" if not granted else None,
            details=details or {}
        )
        
        await self.log_event(event)
        
    async def log_embedding_operation(self, actor_id: str, content_id: str,
                                    operation: str, content_type: str,
                                    performance_metrics: Dict = None,
                                    details: Dict = None):
        """Log embedding generation/indexing operations."""
        
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=AuditEventType.EMBEDDING_GENERATED,
            actor_id=actor_id,
            actor_role="system",
            target_id=content_id,
            target_type=content_type,
            action=operation,
            performance_metrics=performance_metrics,
            details=details or {}
        )
        
        await self.log_event(event)
        
    async def get_audit_logs(self, actor_id: Optional[str] = None,
                           event_type: Optional[AuditEventType] = None,
                           start_date: Optional[datetime] = None,
                           end_date: Optional[datetime] = None,
                           limit: int = 100) -> List[Dict]:
        """Retrieve audit logs with filtering."""
        
        try:
            query = "SELECT * FROM audit_logs WHERE 1=1"
            params = []
            
            if actor_id:
                query += " AND actor_id = ?"
                params.append(actor_id)
                
            if event_type:
                query += " AND action LIKE ?"
                params.append(f"{event_type.value}%")
                
            if start_date:
                query += " AND timestamp >= ?"
                params.append(start_date.isoformat())
                
            if end_date:
                query += " AND timestamp <= ?"
                params.append(end_date.isoformat())
                
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            async with self.db_manager.get_connection() as conn:
                cursor = await conn.execute(query, params)
                rows = await cursor.fetchall()
                
                logs = []
                for row in rows:
                    log_entry = {
                        'log_id': row[0],
                        'action': row[1], 
                        'actor_id': row[2],
                        'actor_role': row[3],
                        'target_id': row[4],
                        'target_type': row[5],
                        'details': json.loads(row[6]) if row[6] else {},
                        'ip_address': row[7],
                        'user_agent': row[8],
                        'success': row[9],
                        'error_message': row[10],
                        'timestamp': row[11]
                    }
                    logs.append(log_entry)
                    
                return logs
                
        except Exception as e:
            logger.error(f"Error retrieving audit logs: {e}")
            return []
            
    async def get_user_activity_summary(self, actor_id: str, 
                                      days: int = 30) -> Dict:
        """Get activity summary for a user."""
        
        try:
            start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            start_date = start_date.replace(day=start_date.day - days)
            
            async with self.db_manager.get_connection() as conn:
                # Get total events
                cursor = await conn.execute("""
                    SELECT COUNT(*) FROM audit_logs 
                    WHERE actor_id = ? AND timestamp >= ?
                """, (actor_id, start_date.isoformat()))
                
                total_events = (await cursor.fetchone())[0]
                
                # Get events by type
                cursor = await conn.execute("""
                    SELECT action, COUNT(*) as count
                    FROM audit_logs 
                    WHERE actor_id = ? AND timestamp >= ?
                    GROUP BY action
                    ORDER BY count DESC
                """, (actor_id, start_date.isoformat()))
                
                events_by_type = {}
                for row in await cursor.fetchall():
                    events_by_type[row[0]] = row[1]
                    
                # Get recent activity
                cursor = await conn.execute("""
                    SELECT action, target_type, timestamp, success
                    FROM audit_logs 
                    WHERE actor_id = ? AND timestamp >= ?
                    ORDER BY timestamp DESC
                    LIMIT 10
                """, (actor_id, start_date.isoformat()))
                
                recent_activity = []
                for row in await cursor.fetchall():
                    recent_activity.append({
                        'action': row[0],
                        'target_type': row[1],
                        'timestamp': row[2],
                        'success': row[3]
                    })
                    
                return {
                    'actor_id': actor_id,
                    'period_days': days,
                    'total_events': total_events,
                    'events_by_type': events_by_type,
                    'recent_activity': recent_activity,
                    'generated_at': datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error getting user activity summary: {e}")
            return {}


# Global audit logger instance
_audit_logger = None

async def get_audit_logger(db_manager: DatabaseManager) -> AuditLogger:
    """Get or create global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger(db_manager)
    return _audit_logger

# Convenience functions for common audit operations

async def log_auth_event(db_manager: DatabaseManager, actor_id: str, 
                        actor_role: str, success: bool, details: Dict = None):
    """Log authentication event."""
    audit_logger = await get_audit_logger(db_manager)
    await audit_logger.log_authentication(actor_id, actor_role, success, details)

async def log_query_event(db_manager: DatabaseManager, actor_id: str,
                         actor_role: str, query: str, results: List[Dict],
                         performance: Dict = None):
    """Log knowledge query event."""
    audit_logger = await get_audit_logger(db_manager)
    await audit_logger.log_knowledge_query(actor_id, actor_role, query, results, performance)

async def log_report_event(db_manager: DatabaseManager, actor_id: str,
                          actor_role: str, action: str, report_id: str,
                          patient_id: str, success: bool = True, details: Dict = None):
    """Log report action event."""
    audit_logger = await get_audit_logger(db_manager)
    await audit_logger.log_report_action(actor_id, actor_role, action, report_id, patient_id, success, None, details)

async def log_permission_event(db_manager: DatabaseManager, actor_id: str,
                              actor_role: str, action: str, target_id: str,
                              target_type: str, granted: bool):
    """Log permission check event."""
    audit_logger = await get_audit_logger(db_manager)
    await audit_logger.log_permission_check(actor_id, actor_role, action, target_id, target_type, granted)