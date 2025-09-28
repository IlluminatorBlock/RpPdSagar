"""
Core Data Models for Parkinson's Multiagent System

This module contains all the data models and enums used throughout the system,
following the exact specifications from the database schema documentation.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Union
from datetime import datetime, timedelta
from enum import Enum
import uuid
import json


def _serialize_for_database(obj):
    """Helper function to serialize complex objects for database storage"""
    if isinstance(obj, (dict, list)):
        return json.dumps(obj)
    return obj


# Enums for type safety and consistency
class InputType(Enum):
    TEXT = "text"
    VOICE = "voice"
    MRI = "mri"
    LAB_DATA = "lab_data"
    MIXED = "mixed"


class OutputFormat(Enum):
    TEXT = "text"
    VOICE = "voice"
    PDF = "pdf"


class SessionStatus(Enum):
    ACTIVE = "active"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


class PredictionType(Enum):
    BINARY = "binary"
    STAGE = "stage"
    SEVERITY = "severity"


class ProcessingStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ActionFlagType(Enum):
    PREDICT_PARKINSONS = "PREDICT_PARKINSONS"
    GENERATE_REPORT = "GENERATE_REPORT"
    PREDICTION_COMPLETE = "PREDICTION_COMPLETE"
    REPORT_COMPLETE = "REPORT_COMPLETE"
    VOICE_OUTPUT = "VOICE_OUTPUT"
    COMPLETE_SESSION = "COMPLETE_SESSION"
    TEST_FLAG = "TEST_FLAG"


class ActionFlagStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


# Core Data Models
@dataclass
class User:
    """Represents a user in the system (patient or doctor)"""
    user_id: str
    email: Optional[str] = None
    name: Optional[str] = None
    user_type: str = 'patient'  # 'patient' or 'doctor'
    preferences: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if self.user_id is None:
            self.user_id = str(uuid.uuid4())

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.user_id,
            'email': self.email,
            'name': self.name,
            'user_type': self.user_type,
            'preferences': self.preferences,
            'created_at': self.created_at.isoformat(),
            'last_active': self.last_active.isoformat()
        }
    
    def to_db_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage with JSON serialization"""
        db_dict = self.to_dict()
        db_dict['preferences'] = _serialize_for_database(self.preferences)
        return db_dict


@dataclass
class Patient:
    """Represents patient-specific information"""
    patient_id: str
    name: str
    age: Optional[int] = None
    gender: Optional[str] = None
    medical_history: Dict[str, Any] = field(default_factory=dict)
    contact_info: Dict[str, str] = field(default_factory=dict)
    assigned_doctor: Optional[str] = None  # Doctor's user_id
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if self.patient_id is None:
            self.patient_id = str(uuid.uuid4())

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.patient_id,
            'name': self.name,
            'age': self.age,
            'gender': self.gender,
            'medical_history': self.medical_history,
            'contact_info': self.contact_info,
            'assigned_doctor': self.assigned_doctor,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    def to_db_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage with JSON serialization"""
        db_dict = self.to_dict()
        db_dict['medical_history'] = _serialize_for_database(self.medical_history)
        db_dict['contact_info'] = _serialize_for_database(self.contact_info)
        return db_dict


@dataclass
class UserInput:
    """Represents user input to the system"""
    input_type: InputType
    content: str
    output_format: OutputFormat = OutputFormat.TEXT
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    patient_id: Optional[str] = None
    doctor_id: Optional[str] = None
    mri_file_path: Optional[str] = None
    lab_data: Optional[Dict[str, Any]] = None
    voice_file_path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if self.session_id is None:
            self.session_id = str(uuid.uuid4())


@dataclass
class SessionData:
    """Represents a user session in the system"""
    session_id: str
    input_type: InputType
    output_format: OutputFormat
    user_id: Optional[str] = None
    patient_id: Optional[str] = None
    patient_name: Optional[str] = None
    doctor_id: Optional[str] = None
    doctor_name: Optional[str] = None
    status: SessionStatus = SessionStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.session_id,
            'user_id': self.user_id,
            'patient_id': self.patient_id,
            'patient_name': self.patient_name,
            'doctor_id': self.doctor_id,
            'doctor_name': self.doctor_name,
            'input_type': self.input_type.value,
            'output_format': self.output_format.value,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'metadata': self.metadata
        }
    
    def to_db_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage with JSON serialization"""
        db_dict = self.to_dict()
        # Serialize complex types for database
        db_dict['metadata'] = _serialize_for_database(self.metadata)
        return db_dict


@dataclass
class MRIData:
    """Represents MRI scan data and metadata"""
    scan_id: str
    session_id: str
    original_filename: Optional[str]
    file_path: str
    file_type: str  # 'dicom', 'png', 'jpeg', 'nii'
    file_size: Optional[int] = None
    image_dimensions: Optional[str] = None
    binary_data: Optional[bytes] = None
    preprocessing_applied: List[str] = field(default_factory=list)
    upload_timestamp: datetime = field(default_factory=datetime.now)
    processing_timestamp: Optional[datetime] = None
    processing_status: ProcessingStatus = ProcessingStatus.PENDING
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.scan_id is None:
            self.scan_id = str(uuid.uuid4())

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.scan_id,
            'session_id': self.session_id,
            'original_filename': self.original_filename,
            'file_path': self.file_path,
            'file_type': self.file_type,
            'file_size': self.file_size,
            'image_dimensions': self.image_dimensions,
            'binary_data': self.binary_data,
            'preprocessing_applied': self.preprocessing_applied,
            'upload_timestamp': self.upload_timestamp.isoformat(),
            'processing_timestamp': self.processing_timestamp.isoformat() if self.processing_timestamp else None,
            'processing_status': self.processing_status.value,
            'metadata': self.metadata
        }
    
    def to_db_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage with JSON serialization"""
        db_dict = self.to_dict()
        # Serialize complex types for database
        db_dict['preprocessing_applied'] = _serialize_for_database(self.preprocessing_applied)
        db_dict['metadata'] = _serialize_for_database(self.metadata)
        return db_dict


@dataclass
class PredictionResult:
    """Represents AI/ML prediction results with confidence metrics"""
    prediction_id: str
    session_id: str
    mri_scan_id: Optional[str]
    prediction_type: PredictionType
    binary_result: Optional[str] = None  # 'parkinsons', 'no_parkinsons', 'uncertain'
    stage_result: Optional[str] = None   # '1', '2', '3', '4', 'uncertain'
    confidence_score: Optional[float] = None  # Overall confidence (0.0 - 1.0)
    binary_confidence: Optional[float] = None
    stage_confidence: Optional[float] = None
    uncertainty_metrics: Dict[str, Any] = field(default_factory=dict)
    model_version: Optional[str] = None
    processing_time: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.prediction_id is None:
            self.prediction_id = str(uuid.uuid4())

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.prediction_id,
            'session_id': self.session_id,
            'mri_scan_id': self.mri_scan_id,
            'prediction_type': self.prediction_type.value,
            'binary_result': self.binary_result,
            'stage_result': self.stage_result,
            'confidence_score': self.confidence_score,
            'binary_confidence': self.binary_confidence,
            'stage_confidence': self.stage_confidence,
            'uncertainty_metrics': self.uncertainty_metrics,
            'model_version': self.model_version,
            'processing_time': self.processing_time,
            'created_at': self.created_at.isoformat(),
            'metadata': self.metadata
        }
    
    def to_db_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage with JSON serialization"""
        db_dict = self.to_dict()
        # Serialize complex types for database
        db_dict['uncertainty_metrics'] = _serialize_for_database(self.uncertainty_metrics)
        db_dict['metadata'] = _serialize_for_database(self.metadata)
        return db_dict


@dataclass
class MedicalReport:
    """Represents generated medical reports"""
    report_id: str
    session_id: str
    prediction_id: Optional[str]
    report_type: str  # 'full', 'summary', 'patient_friendly'
    title: str
    content: str
    recommendations: List[str] = field(default_factory=list)
    format_type: str = "text"  # 'text', 'pdf', 'html'
    generated_by: str = "RAG_Agent"
    confidence_level: Optional[float] = None
    disclaimer: str = "This report is AI-generated and should be reviewed by a medical professional."
    created_at: datetime = field(default_factory=datetime.now)
    file_path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.report_id is None:
            self.report_id = str(uuid.uuid4())

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.report_id,
            'session_id': self.session_id,
            'prediction_id': self.prediction_id,
            'report_type': self.report_type,
            'title': self.title,
            'content': self.content,
            'recommendations': self.recommendations,
            'format_type': self.format_type,
            'generated_by': self.generated_by,
            'confidence_level': self.confidence_level,
            'disclaimer': self.disclaimer,
            'created_at': self.created_at.isoformat(),
            'file_path': self.file_path,
            'metadata': self.metadata
        }
    
    def to_db_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage with JSON serialization"""
        db_dict = self.to_dict()
        # Serialize complex types for database
        db_dict['recommendations'] = _serialize_for_database(self.recommendations)
        db_dict['metadata'] = _serialize_for_database(self.metadata)
        return db_dict


@dataclass
class KnowledgeEntry:
    """Represents medical knowledge base entries"""
    entry_id: str
    title: str
    content: str
    category: str  # 'symptoms', 'treatments', 'research', 'guidelines'
    source_type: str  # 'medical_journal', 'clinical_guideline', 'textbook'
    source_url: Optional[str] = None
    author: Optional[str] = None
    publication_date: Optional[datetime] = None
    credibility_score: float = 1.0
    embedding: Optional[bytes] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.entry_id is None:
            self.entry_id = str(uuid.uuid4())

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.entry_id,
            'title': self.title,
            'content': self.content,
            'category': self.category,
            'source_type': self.source_type,
            'source_url': self.source_url,
            'author': self.author,
            'publication_date': self.publication_date.isoformat() if self.publication_date else None,
            'credibility_score': self.credibility_score,
            'embedding': self.embedding,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'metadata': self.metadata
        }


@dataclass
class LabResult:
    """Represents laboratory test results"""
    result_id: str
    session_id: str
    test_type: str
    test_name: str
    value: Union[str, float, int]
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    interpretation: Optional[str] = None  # 'normal', 'abnormal', 'borderline'
    test_date: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.result_id is None:
            self.result_id = str(uuid.uuid4())

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.result_id,
            'session_id': self.session_id,
            'test_type': self.test_type,
            'test_name': self.test_name,
            'value': str(self.value),
            'unit': self.unit,
            'reference_range': self.reference_range,
            'interpretation': self.interpretation,
            'test_date': self.test_date.isoformat(),
            'created_at': self.created_at.isoformat(),
            'metadata': self.metadata
        }


@dataclass
class ActionFlag:
    """Represents action flags for inter-agent communication"""
    flag_id: str
    session_id: str
    flag_type: ActionFlagType
    status: ActionFlagStatus = ActionFlagStatus.PENDING
    priority: int = 0
    data: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    agent_assigned: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.flag_id is None:
            self.flag_id = str(uuid.uuid4())
        # Set default expiration to 30 minutes if not specified
        if self.expires_at is None:
            self.expires_at = self.created_at + timedelta(minutes=30)

    def is_expired(self) -> bool:
        """Check if the action flag has expired"""
        return datetime.now() > self.expires_at if self.expires_at else False

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.flag_id,
            'session_id': self.session_id,
            'flag_type': self.flag_type.value,
            'status': self.status.value,
            'priority': self.priority,
            'data': self.data,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'agent_assigned': self.agent_assigned,
            'metadata': self.metadata
        }


@dataclass
class AgentMessage:
    """Represents messages between agents"""
    message_id: str
    sender: str
    receiver: str
    message_type: str
    payload: Dict[str, Any]
    session_id: str
    timestamp: datetime = field(default_factory=datetime.now)
    correlation_id: Optional[str] = None
    processed: bool = False

    def __post_init__(self):
        if self.message_id is None:
            self.message_id = str(uuid.uuid4())

    def to_dict(self) -> Dict[str, Any]:
        return {
            'message_id': self.message_id,
            'sender': self.sender,
            'receiver': self.receiver,
            'message_type': self.message_type,
            'payload': self.payload,
            'session_id': self.session_id,
            'timestamp': self.timestamp.isoformat(),
            'correlation_id': self.correlation_id,
            'processed': self.processed
        }


@dataclass
class Response:
    """Represents system responses to user input"""
    response_id: str
    session_id: str
    content: str
    format_type: OutputFormat
    generated_by: str
    confidence_score: Optional[float] = None
    processing_time: Optional[float] = None
    has_attachments: bool = False
    attachment_paths: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.response_id is None:
            self.response_id = str(uuid.uuid4())

    def to_dict(self) -> Dict[str, Any]:
        return {
            'response_id': self.response_id,
            'session_id': self.session_id,
            'content': self.content,
            'format_type': self.format_type.value,
            'generated_by': self.generated_by,
            'confidence_score': self.confidence_score,
            'processing_time': self.processing_time,
            'has_attachments': self.has_attachments,
            'attachment_paths': self.attachment_paths,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata
        }


# Utility functions for data model conversions
def dict_to_session_data(data: Dict[str, Any]) -> SessionData:
    """Convert dictionary to SessionData object"""
    return SessionData(
        session_id=data['id'],
        user_id=data.get('user_id'),
        patient_id=data.get('patient_id'),
        patient_name=data.get('patient_name'),
        doctor_id=data.get('doctor_id'),
        doctor_name=data.get('doctor_name'),
        input_type=InputType(data['input_type']),
        output_format=OutputFormat(data['output_format']),
        status=SessionStatus(data['status']),
        created_at=datetime.fromisoformat(data['created_at']),
        updated_at=datetime.fromisoformat(data['updated_at']),
        metadata=json.loads(data.get('metadata', '{}'))
    )


def dict_to_prediction_result(data: Dict[str, Any]) -> PredictionResult:
    """Convert dictionary to PredictionResult object"""
    return PredictionResult(
        prediction_id=data['id'],
        session_id=data['session_id'],
        mri_scan_id=data.get('mri_scan_id'),
        prediction_type=PredictionType(data['prediction_type']),
        binary_result=data.get('binary_result'),
        stage_result=data.get('stage_result'),
        confidence_score=data.get('confidence_score'),
        binary_confidence=data.get('binary_confidence'),
        stage_confidence=data.get('stage_confidence'),
        uncertainty_metrics=json.loads(data.get('uncertainty_metrics', '{}')),
        model_version=data.get('model_version'),
        processing_time=data.get('processing_time'),
        created_at=datetime.fromisoformat(data['created_at']),
        metadata=json.loads(data.get('metadata', '{}'))
    )


def dict_to_action_flag(data: Dict[str, Any]) -> ActionFlag:
    """Convert dictionary to ActionFlag object"""
    return ActionFlag(
        flag_id=data['id'],
        session_id=data['session_id'],
        flag_type=ActionFlagType(data['flag_type']),
        status=ActionFlagStatus(data['status']),
        priority=data.get('priority', 0),
        data=json.loads(data.get('data', '{}')),
        created_at=datetime.fromisoformat(data['created_at']),
        updated_at=datetime.fromisoformat(data['updated_at']),
        expires_at=datetime.fromisoformat(data['expires_at']) if data.get('expires_at') else None,
        agent_assigned=data.get('agent_assigned'),
        metadata=json.loads(data.get('metadata', '{}'))
    )


def dict_to_user(data: Dict[str, Any]) -> User:
    """Convert dictionary to User object"""
    return User(
        user_id=data['id'],
        email=data.get('email'),
        name=data.get('name'),
        user_type=data.get('user_type', 'patient'),
        preferences=json.loads(data.get('preferences', '{}')),
        created_at=datetime.fromisoformat(data['created_at']),
        last_active=datetime.fromisoformat(data['last_active'])
    )


def dict_to_patient(data: Dict[str, Any]) -> Patient:
    """Convert dictionary to Patient object"""
    return Patient(
        patient_id=data['id'],
        name=data['name'],
        age=data.get('age'),
        gender=data.get('gender'),
        medical_history=json.loads(data.get('medical_history', '{}')),
        contact_info=json.loads(data.get('contact_info', '{}')),
        assigned_doctor=data.get('assigned_doctor'),
        created_at=datetime.fromisoformat(data['created_at']),
        updated_at=datetime.fromisoformat(data['updated_at'])
    )