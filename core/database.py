"""
Database Manager for Parkinson's Multiagent System

This module provides comprehensive database operations for all system data,
implementing the complete schema as specified in the documentation.
"""

import sqlite3
import aiosqlite
import asyncio
from typing import List, Dict, Optional, Any, Union
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from models.data_models import (
    SessionData, MRIData, PredictionResult, MedicalReport, 
    KnowledgeEntry, LabResult, ActionFlag, AgentMessage,
    User, Patient,
    ActionFlagType, ActionFlagStatus, SessionStatus,
    dict_to_session_data, dict_to_prediction_result, dict_to_action_flag,
    dict_to_user, dict_to_patient
)

# Configure logging
logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Central database manager for all system data operations.
    Implements the complete database schema with async operations.
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.connection_pool = None
        self._ensure_db_directory()
    
    def _ensure_db_directory(self):
        """Ensure the database directory exists"""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
    
    async def _migrate_database(self) -> None:
        """Migrate existing database to new schema"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                # Check if we need to migrate sessions table
                cursor = await db.execute("PRAGMA table_info(sessions)")
                columns = await cursor.fetchall()
                column_names = [col[1] for col in columns]
                
                if 'patient_id' not in column_names:
                    logger.info("Migrating sessions table to include patient/doctor fields...")
                    
                    # Add new columns to sessions table
                    await db.execute("ALTER TABLE sessions ADD COLUMN patient_id TEXT")
                    await db.execute("ALTER TABLE sessions ADD COLUMN patient_name TEXT")
                    await db.execute("ALTER TABLE sessions ADD COLUMN doctor_id TEXT")
                    await db.execute("ALTER TABLE sessions ADD COLUMN doctor_name TEXT")
                    
                    # Create indexes for new columns
                    await db.execute("CREATE INDEX IF NOT EXISTS idx_sessions_patient_id ON sessions(patient_id)")
                    await db.execute("CREATE INDEX IF NOT EXISTS idx_sessions_doctor_id ON sessions(doctor_id)")
                    
                    logger.info("Sessions table migration completed")
                
                # Check if we need to migrate mri_scans table
                cursor = await db.execute("PRAGMA table_info(mri_scans)")
                columns = await cursor.fetchall()
                column_names = [col[1] for col in columns]
                
                if 'binary_data' not in column_names:
                    logger.info("Migrating mri_scans table to include binary_data field...")
                    await db.execute("ALTER TABLE mri_scans ADD COLUMN binary_data BLOB")
                    logger.info("MRI scans table migration completed")
                
                await db.commit()
                
            except Exception as e:
                logger.error(f"Database migration failed: {e}")
                # Continue anyway - the create table methods will handle missing tables
    
    async def init_database(self) -> None:
        """Initialize database with complete schema"""
        # Run migrations first
        await self._migrate_database()
        
        async with aiosqlite.connect(self.db_path) as db:
            # Enable foreign keys
            await db.execute("PRAGMA foreign_keys = ON;")
            
            # Create all tables (IF NOT EXISTS will skip existing ones)
            await self._create_users_table(db)
            await self._create_patients_table(db)
            await self._create_sessions_table(db)
            await self._create_mri_scans_table(db)
            await self._create_predictions_table(db)
            await self._create_medical_reports_table(db)
            await self._create_knowledge_entries_table(db)
            await self._create_lab_results_table(db)
            await self._create_action_flags_table(db)
            await self._create_agent_messages_table(db)
            
            await db.commit()
            logger.info("Database initialized successfully")
    
    async def _create_users_table(self, db: aiosqlite.Connection):
        """Create users table"""
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE,
                name TEXT,
                user_type TEXT DEFAULT 'patient',
                preferences JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_users_type ON users(user_type);")
    
    async def _create_patients_table(self, db: aiosqlite.Connection):
        """Create patients table"""
        await db.execute("""
            CREATE TABLE IF NOT EXISTS patients (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                age INTEGER,
                gender TEXT,
                medical_history JSON,
                contact_info JSON,
                assigned_doctor TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (assigned_doctor) REFERENCES users(id)
            );
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_patients_name ON patients(name);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_patients_assigned_doctor ON patients(assigned_doctor);")

    async def _create_sessions_table(self, db: aiosqlite.Connection):
        """Create sessions table"""
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                patient_id TEXT,
                patient_name TEXT,
                doctor_id TEXT,
                doctor_name TEXT,
                input_type TEXT NOT NULL,
                output_format TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata JSON,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (patient_id) REFERENCES patients(id),
                FOREIGN KEY (doctor_id) REFERENCES users(id)
            );
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_sessions_patient_id ON sessions(patient_id);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_sessions_doctor_id ON sessions(doctor_id);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON sessions(created_at);")
    
    async def _create_mri_scans_table(self, db: aiosqlite.Connection):
        """Create MRI scans table"""
        await db.execute("""
            CREATE TABLE IF NOT EXISTS mri_scans (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                original_filename TEXT,
                file_path TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_size INTEGER,
                image_dimensions TEXT,
                binary_data BLOB,
                preprocessing_applied JSON,
                upload_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processing_timestamp TIMESTAMP,
                processing_status TEXT DEFAULT 'pending',
                metadata JSON,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_mri_scans_session_id ON mri_scans(session_id);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_mri_scans_processing_status ON mri_scans(processing_status);")
    
    async def _create_predictions_table(self, db: aiosqlite.Connection):
        """Create predictions table"""
        await db.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                mri_scan_id TEXT,
                prediction_type TEXT NOT NULL,
                binary_result TEXT,
                stage_result TEXT,
                confidence_score REAL,
                binary_confidence REAL,
                stage_confidence REAL,
                uncertainty_metrics JSON,
                model_version TEXT,
                processing_time REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata JSON,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
                FOREIGN KEY (mri_scan_id) REFERENCES mri_scans(id) ON DELETE SET NULL
            );
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_predictions_session_id ON predictions(session_id);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_predictions_binary_result ON predictions(binary_result);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_predictions_stage_result ON predictions(stage_result);")
    
    async def _create_medical_reports_table(self, db: aiosqlite.Connection):
        """Create medical reports table"""
        await db.execute("""
            CREATE TABLE IF NOT EXISTS medical_reports (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                prediction_id TEXT,
                report_type TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                recommendations JSON,
                format_type TEXT DEFAULT 'text',
                generated_by TEXT DEFAULT 'RAG_Agent',
                confidence_level REAL,
                disclaimer TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_path TEXT,
                metadata JSON,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
                FOREIGN KEY (prediction_id) REFERENCES predictions(id) ON DELETE SET NULL
            );
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_reports_session_id ON medical_reports(session_id);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_reports_type ON medical_reports(report_type);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_reports_created_at ON medical_reports(created_at);")
    
    async def _create_knowledge_entries_table(self, db: aiosqlite.Connection):
        """Create knowledge entries table"""
        await db.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_entries (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                category TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_url TEXT,
                author TEXT,
                publication_date TIMESTAMP,
                credibility_score REAL DEFAULT 1.0,
                embedding BLOB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata JSON
            );
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_category ON knowledge_entries(category);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_source_type ON knowledge_entries(source_type);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_credibility ON knowledge_entries(credibility_score);")
    
    async def _create_lab_results_table(self, db: aiosqlite.Connection):
        """Create lab results table"""
        await db.execute("""
            CREATE TABLE IF NOT EXISTS lab_results (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                test_type TEXT NOT NULL,
                test_name TEXT NOT NULL,
                value TEXT NOT NULL,
                unit TEXT,
                reference_range TEXT,
                interpretation TEXT,
                test_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata JSON,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_lab_results_session_id ON lab_results(session_id);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_lab_results_test_type ON lab_results(test_type);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_lab_results_interpretation ON lab_results(interpretation);")
    
    async def _create_action_flags_table(self, db: aiosqlite.Connection):
        """Create action flags table"""
        await db.execute("""
            CREATE TABLE IF NOT EXISTS action_flags (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                flag_type TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                priority INTEGER DEFAULT 0,
                data JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                agent_assigned TEXT,
                metadata JSON,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_action_flags_session_id ON action_flags(session_id);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_action_flags_type ON action_flags(flag_type);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_action_flags_status ON action_flags(status);")
    
    async def _create_agent_messages_table(self, db: aiosqlite.Connection):
        """Create agent messages table"""
        await db.execute("""
            CREATE TABLE IF NOT EXISTS agent_messages (
                message_id TEXT PRIMARY KEY,
                sender TEXT NOT NULL,
                receiver TEXT NOT NULL,
                message_type TEXT NOT NULL,
                payload JSON NOT NULL,
                session_id TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                correlation_id TEXT,
                processed BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_messages_receiver ON agent_messages(receiver);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_messages_session_id ON agent_messages(session_id);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_messages_processed ON agent_messages(processed);")
    
    # User Operations
    async def create_user(self, user: User) -> str:
        """Create a new user"""
        async with aiosqlite.connect(self.db_path) as db:
            data = user.to_db_dict()
            await db.execute("""
                INSERT INTO users (id, email, name, user_type, preferences, created_at, last_active)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                data['id'], data['email'], data['name'], data['user_type'],
                data['preferences'], data['created_at'], data['last_active']
            ))
            await db.commit()
            logger.info(f"Created user: {user.user_id}")
            return user.user_id
    
    async def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = await cursor.fetchone()
            if row:
                return dict_to_user(dict(row))
            return None
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM users WHERE email = ?", (email,))
            row = await cursor.fetchone()
            if row:
                return dict_to_user(dict(row))
            return None
    
    # Patient Operations
    async def create_patient(self, patient: Patient) -> str:
        """Create a new patient"""
        async with aiosqlite.connect(self.db_path) as db:
            data = patient.to_db_dict()
            await db.execute("""
                INSERT INTO patients (id, name, age, gender, medical_history, contact_info, 
                                    assigned_doctor, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data['id'], data['name'], data['age'], data['gender'],
                data['medical_history'], data['contact_info'], data['assigned_doctor'],
                data['created_at'], data['updated_at']
            ))
            await db.commit()
            logger.info(f"Created patient: {patient.patient_id}")
            return patient.patient_id
    
    async def get_patient(self, patient_id: str) -> Optional[Patient]:
        """Get patient by ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM patients WHERE id = ?", (patient_id,))
            row = await cursor.fetchone()
            if row:
                return dict_to_patient(dict(row))
            return None
    
    async def get_patient_by_name(self, name: str) -> Optional[Patient]:
        """Get patient by name"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM patients WHERE name = ?", (name,))
            row = await cursor.fetchone()
            if row:
                return dict_to_patient(dict(row))
            return None
    
    async def get_patients_by_doctor(self, doctor_id: str) -> List[Patient]:
        """Get all patients assigned to a doctor"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM patients WHERE assigned_doctor = ?", (doctor_id,))
            rows = await cursor.fetchall()
            return [dict_to_patient(dict(row)) for row in rows]
    
    async def check_existing_reports(self, patient_id: str) -> List[Dict[str, Any]]:
        """Check if patient has existing reports"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT r.*, s.created_at as session_date 
                FROM medical_reports r
                JOIN sessions s ON r.session_id = s.id
                WHERE s.patient_id = ?
                ORDER BY r.created_at DESC
            """, (patient_id,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    # Session Operations
    async def create_session(self, session_data: SessionData) -> str:
        """Create a new session"""
        async with aiosqlite.connect(self.db_path) as db:
            data = session_data.to_db_dict()  # Use to_db_dict which properly serializes metadata
            await db.execute("""
                INSERT INTO sessions (id, user_id, patient_id, patient_name, doctor_id, doctor_name, 
                                    input_type, output_format, status, created_at, updated_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data['id'], data['user_id'], data['patient_id'], data['patient_name'],
                data['doctor_id'], data['doctor_name'], data['input_type'], data['output_format'],
                data['status'], data['created_at'], data['updated_at'], data['metadata']
            ))
            await db.commit()
            logger.info(f"Created session: {session_data.session_id}")
            return session_data.session_id
    
    async def get_session(self, session_id: str) -> Optional[SessionData]:
        """Get session by ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
            row = await cursor.fetchone()
            if row:
                return dict_to_session_data(dict(row))
            return None
    
    async def update_session_status(self, session_id: str, status: SessionStatus) -> bool:
        """Update session status"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE sessions SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
            """, (status.value, session_id))
            await db.commit()
            return True
    
    # Action Flag Operations
    async def create_action_flag(self, action_flag: ActionFlag) -> str:
        """Create a new action flag"""
        async with aiosqlite.connect(self.db_path) as db:
            data = action_flag.to_dict()
            # Serialize metadata and data dictionaries for SQLite storage
            import json
            metadata_json = json.dumps(data['metadata']) if data['metadata'] else '{}'
            data_json = json.dumps(data['data']) if data['data'] else '{}'
            
            await db.execute("""
                INSERT INTO action_flags (id, session_id, flag_type, status, priority, data, 
                                        created_at, updated_at, expires_at, agent_assigned, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data['id'], data['session_id'], data['flag_type'], data['status'], data['priority'],
                data_json, data['created_at'], data['updated_at'], data['expires_at'],
                data['agent_assigned'], metadata_json
            ))
            await db.commit()
            logger.info(f"Created action flag: {action_flag.flag_type.value} for session {action_flag.session_id}")
            return action_flag.flag_id
    
    async def get_pending_flags(self, flag_type: Optional[ActionFlagType] = None) -> List[ActionFlag]:
        """Get all pending action flags, optionally filtered by type"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if flag_type:
                cursor = await db.execute("""
                    SELECT * FROM action_flags 
                    WHERE flag_type = ? AND status = 'pending' AND expires_at > CURRENT_TIMESTAMP
                    ORDER BY priority DESC, created_at ASC
                """, (flag_type.value,))
            else:
                cursor = await db.execute("""
                    SELECT * FROM action_flags 
                    WHERE status = 'pending' AND expires_at > CURRENT_TIMESTAMP
                    ORDER BY priority DESC, created_at ASC
                """)
            
            rows = await cursor.fetchall()
            return [dict_to_action_flag(dict(row)) for row in rows]
    
    async def update_action_flag_status(self, flag_id: str, status: ActionFlagStatus, agent_assigned: Optional[str] = None) -> bool:
        """Update action flag status"""
        async with aiosqlite.connect(self.db_path) as db:
            if agent_assigned:
                await db.execute("""
                    UPDATE action_flags SET status = ?, agent_assigned = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE id = ?
                """, (status.value, agent_assigned, flag_id))
            else:
                await db.execute("""
                    UPDATE action_flags SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
                """, (status.value, flag_id))
            await db.commit()
            return True
    
    async def cleanup_expired_flags(self) -> int:
        """Clean up expired action flags"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                UPDATE action_flags SET status = 'expired' 
                WHERE expires_at < CURRENT_TIMESTAMP AND status = 'pending'
            """)
            await db.commit()
            return cursor.rowcount
    
    # MRI Operations
    async def store_mri_scan(self, mri_data: MRIData) -> str:
        """Store MRI scan data"""
        async with aiosqlite.connect(self.db_path) as db:
            data = mri_data.to_db_dict()  # Use to_db_dict which properly serializes metadata and preprocessing_applied
            await db.execute("""
                INSERT INTO mri_scans (id, session_id, original_filename, file_path, file_type,
                                     file_size, image_dimensions, binary_data, preprocessing_applied,
                                     upload_timestamp, processing_timestamp, processing_status, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data['id'], data['session_id'], data['original_filename'], data['file_path'],
                data['file_type'], data['file_size'], data['image_dimensions'], data['binary_data'],
                data['preprocessing_applied'], data['upload_timestamp'],
                data['processing_timestamp'], data['processing_status'], data['metadata']
            ))
            await db.commit()
            logger.info(f"Stored MRI scan: {mri_data.scan_id}")
            return mri_data.scan_id
    
    async def get_mri_scans_by_session(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all MRI scans for a session"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM mri_scans WHERE session_id = ?", (session_id,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def get_mri_binary_data(self, scan_id: str) -> Optional[bytes]:
        """Get MRI binary data by scan ID"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT binary_data FROM mri_scans WHERE id = ?", (scan_id,))
            row = await cursor.fetchone()
            if row and row[0]:
                return row[0]
            return None
    
    async def get_mri_scans_by_patient(self, patient_id: str) -> List[Dict[str, Any]]:
        """Get all MRI scans for a patient"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT m.* FROM mri_scans m
                JOIN sessions s ON m.session_id = s.id
                WHERE s.patient_id = ?
                ORDER BY m.upload_timestamp DESC
            """, (patient_id,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    # Prediction Operations
    async def store_prediction(self, prediction: PredictionResult) -> str:
        """Store prediction result"""
        async with aiosqlite.connect(self.db_path) as db:
            data = prediction.to_db_dict()  # Use to_db_dict which properly serializes metadata and uncertainty_metrics
            await db.execute("""
                INSERT INTO predictions (id, session_id, mri_scan_id, prediction_type, binary_result,
                                       stage_result, confidence_score, binary_confidence, stage_confidence,
                                       uncertainty_metrics, model_version, processing_time, created_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data['id'], data['session_id'], data['mri_scan_id'], data['prediction_type'],
                data['binary_result'], data['stage_result'], data['confidence_score'],
                data['binary_confidence'], data['stage_confidence'], data['uncertainty_metrics'],
                data['model_version'], data['processing_time'], data['created_at'], data['metadata']
            ))
            await db.commit()
            logger.info(f"Stored prediction: {prediction.prediction_id}")
            return prediction.prediction_id
    
    async def get_predictions_by_session(self, session_id: str) -> List[PredictionResult]:
        """Get all predictions for a session"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM predictions WHERE session_id = ?", (session_id,))
            rows = await cursor.fetchall()
            return [dict_to_prediction_result(dict(row)) for row in rows]
    
    async def get_latest_prediction(self, session_id: str) -> Optional[PredictionResult]:
        """Get the most recent prediction for a session"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM predictions WHERE session_id = ? 
                ORDER BY created_at DESC LIMIT 1
            """, (session_id,))
            row = await cursor.fetchone()
            if row:
                return dict_to_prediction_result(dict(row))
            return None
    
    # Medical Report Operations
    async def store_medical_report(self, report: MedicalReport) -> str:
        """Store medical report"""
        async with aiosqlite.connect(self.db_path) as db:
            data = report.to_db_dict()  # Use to_db_dict which properly serializes metadata and recommendations
            await db.execute("""
                INSERT INTO medical_reports (id, session_id, prediction_id, report_type, title, content,
                                           recommendations, format_type, generated_by, confidence_level,
                                           disclaimer, created_at, file_path, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data['id'], data['session_id'], data['prediction_id'], data['report_type'],
                data['title'], data['content'], data['recommendations'], data['format_type'],
                data['generated_by'], data['confidence_level'], data['disclaimer'],
                data['created_at'], data['file_path'], data['metadata']
            ))
            await db.commit()
            logger.info(f"Stored medical report: {report.report_id}")
            return report.report_id
    
    async def get_reports_by_session(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all reports for a session"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM medical_reports WHERE session_id = ?", (session_id,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    # Knowledge Base Operations
    async def store_knowledge_entry(self, entry: KnowledgeEntry) -> str:
        """Store knowledge base entry"""
        async with aiosqlite.connect(self.db_path) as db:
            data = entry.to_dict()
            # Serialize metadata dictionary for SQLite storage
            import json
            metadata_json = json.dumps(data['metadata']) if data['metadata'] else '{}'
            
            await db.execute("""
                INSERT INTO knowledge_entries (id, title, content, category, source_type, source_url,
                                             author, publication_date, credibility_score, embedding,
                                             created_at, updated_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data['id'], data['title'], data['content'], data['category'], data['source_type'],
                data['source_url'], data['author'], data['publication_date'], data['credibility_score'],
                data['embedding'], data['created_at'], data['updated_at'], metadata_json
            ))
            await db.commit()
            return entry.entry_id
    
    async def search_knowledge_entries(self, category: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Search knowledge base entries"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if category:
                cursor = await db.execute("""
                    SELECT * FROM knowledge_entries WHERE category = ? 
                    ORDER BY credibility_score DESC, created_at DESC LIMIT ?
                """, (category, limit))
            else:
                cursor = await db.execute("""
                    SELECT * FROM knowledge_entries 
                    ORDER BY credibility_score DESC, created_at DESC LIMIT ?
                """, (limit,))
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    # Agent Message Operations
    async def send_agent_message(self, message: AgentMessage) -> str:
        """Send message between agents"""
        async with aiosqlite.connect(self.db_path) as db:
            data = message.to_dict()
            # Serialize payload dictionary for SQLite storage
            import json
            payload_json = json.dumps(data['payload']) if data['payload'] else '{}'
            
            await db.execute("""
                INSERT INTO agent_messages (message_id, sender, receiver, message_type, payload,
                                          session_id, timestamp, correlation_id, processed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data['message_id'], data['sender'], data['receiver'], data['message_type'],
                payload_json, data['session_id'], data['timestamp'],
                data['correlation_id'], data['processed']
            ))
            await db.commit()
            return message.message_id
    
    async def get_agent_messages(self, receiver: str, processed: bool = False) -> List[Dict[str, Any]]:
        """Get messages for a specific agent"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM agent_messages WHERE receiver = ? AND processed = ?
                ORDER BY timestamp ASC
            """, (receiver, processed))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def mark_message_processed(self, message_id: str) -> bool:
        """Mark a message as processed"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE agent_messages SET processed = TRUE WHERE message_id = ?", (message_id,))
            await db.commit()
            return True
    
    # Utility Operations
    async def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """Get complete session summary with all related data"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            # Get session data
            session_cursor = await db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
            session_row = await session_cursor.fetchone()
            
            if not session_row:
                return {}
            
            session_data = dict(session_row)
            
            # Get related data
            mri_cursor = await db.execute("SELECT * FROM mri_scans WHERE session_id = ?", (session_id,))
            mri_scans = [dict(row) for row in await mri_cursor.fetchall()]
            
            predictions_cursor = await db.execute("SELECT * FROM predictions WHERE session_id = ?", (session_id,))
            predictions = [dict(row) for row in await predictions_cursor.fetchall()]
            
            reports_cursor = await db.execute("SELECT * FROM medical_reports WHERE session_id = ?", (session_id,))
            reports = [dict(row) for row in await reports_cursor.fetchall()]
            
            flags_cursor = await db.execute("SELECT * FROM action_flags WHERE session_id = ?", (session_id,))
            action_flags = [dict(row) for row in await flags_cursor.fetchall()]
            
            return {
                'session': session_data,
                'mri_scans': mri_scans,
                'predictions': predictions,
                'reports': reports,
                'action_flags': action_flags
            }
    
    async def cleanup_old_sessions(self, days_old: int = 30) -> int:
        """Clean up old sessions and related data"""
        cutoff_date = datetime.now() - timedelta(days=days_old)
        
        async with aiosqlite.connect(self.db_path) as db:
            # Clean up old sessions (cascading deletes will handle related data)
            cursor = await db.execute("""
                DELETE FROM sessions WHERE created_at < ? AND status IN ('completed', 'error')
            """, (cutoff_date.isoformat(),))
            await db.commit()
            return cursor.rowcount
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform database health check"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Count records in main tables
                session_count = await (await db.execute("SELECT COUNT(*) FROM sessions")).fetchone()
                prediction_count = await (await db.execute("SELECT COUNT(*) FROM predictions")).fetchone()
                report_count = await (await db.execute("SELECT COUNT(*) FROM medical_reports")).fetchone()
                knowledge_count = await (await db.execute("SELECT COUNT(*) FROM knowledge_entries")).fetchone()
                
                return {
                    'status': 'healthy',
                    'database_path': self.db_path,
                    'sessions': session_count[0],
                    'predictions': prediction_count[0],
                    'reports': report_count[0],
                    'knowledge_entries': knowledge_count[0],
                    'timestamp': datetime.now().isoformat()
                }
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions from the database.
        Returns the number of expired sessions removed.
        """
        try:
            # For now, implement basic cleanup based on created_at timestamp
            # Sessions older than 24 hours are considered expired
            from datetime import datetime, timedelta
            
            cutoff_time = datetime.now() - timedelta(hours=24)
            
            async with aiosqlite.connect(self.db_path) as db:
                # Count expired sessions first
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM sessions WHERE created_at < ?",
                    (cutoff_time.isoformat(),)
                )
                count_result = await cursor.fetchone()
                expired_count = count_result[0] if count_result else 0
                
                # Delete expired sessions
                if expired_count > 0:
                    await db.execute(
                        "DELETE FROM sessions WHERE created_at < ?",
                        (cutoff_time.isoformat(),)
                    )
                    await db.commit()
                    logger.info(f"Cleaned up {expired_count} expired sessions")
                
                return expired_count
                
        except Exception as e:
            logger.error(f"Error cleaning up expired sessions: {e}")
            return 0
    
    async def close(self):
        """Close database connections and cleanup resources"""
        logger.debug("[LIFECYCLE] Closing DatabaseManager")
        
        try:
            # Close any open connections in the pool
            if hasattr(self, 'connection_pool') and self.connection_pool:
                # For aiosqlite, we don't have a persistent pool, but we ensure cleanup
                logger.debug("[DATABASE] Cleaning up connection pool")
                logger.info("Database connections cleaned up")
            
            logger.info("Database manager closed successfully")
            
        except Exception as e:
            logger.error(f"Error closing database: {e}")
            raise