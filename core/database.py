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


class DatabaseConnection:
    """Database connection context manager that enables foreign keys"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.connection = None
    
    async def __aenter__(self):
        self.connection = await aiosqlite.connect(self.db_path)
        await self.connection.execute("PRAGMA foreign_keys = ON")
        return self.connection
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.connection:
            await self.connection.close()


class DatabaseManager:
    """Enhanced database manager for all system data operations.
    Implements the complete database schema with async operations.
    """
    
    def __init__(self, db_path: str = "data/parkinsons_system.db"):
        """Initialize database manager"""
        self.db_path = db_path
        self.embeddings_manager = None  # Will be initialized during database setup
        self._ensure_db_directory()
    
    def _ensure_db_directory(self):
        """Ensure the database directory exists"""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
    
    def get_connection(self):
        """Get database connection context manager with foreign keys enabled"""
        return DatabaseConnection(self.db_path)
    
    def get_embeddings_manager(self):
        """Get the embeddings manager if initialized"""
        return getattr(self, 'embeddings_manager', None)
    
    async def _initialize_embeddings_on_demand(self):
        """Initialize embeddings manager only when database is set up"""
        try:
            logger.info("Initializing embeddings manager during database setup...")
            
            # Only import when needed to avoid loading ML libraries unnecessarily
            from knowledge_base.embeddings_manager import EmbeddingsManager
            
            # Import config to get current settings
            from config import config
            embeddings_config = config.embeddings_config
            
            # Initialize and store as database attribute for access by agents
            self.embeddings_manager = EmbeddingsManager(embeddings_config)
            await self.embeddings_manager.initialize()
            
            logger.info("✅ Embeddings manager initialized successfully and attached to database")
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ Embeddings initialization failed: {e} - continuing without embeddings")
            self.embeddings_manager = None
            return False

    async def _load_existing_embeddings(self):
        """Load existing embeddings manager without creating new embeddings"""
        try:
            # Check if embeddings directory exists and has content
            from config import config
            embeddings_config = config.embeddings_config
            embeddings_dir = Path(embeddings_config.get('embeddings_dir', 'data/embeddings'))
            
            # Look for existing embeddings files
            embeddings_files = []
            if embeddings_dir.exists():
                embeddings_files.extend(embeddings_dir.glob('*.pkl'))
                embeddings_files.extend(embeddings_dir.glob('*.json'))
                embeddings_files.extend(embeddings_dir.glob('*.faiss'))
            
            if embeddings_files:
                logger.info(f"Found existing embeddings files: {len(embeddings_files)} files")
                
                # Initialize embeddings manager to load existing data
                from knowledge_base.embeddings_manager import EmbeddingsManager
                self.embeddings_manager = EmbeddingsManager(embeddings_config)
                await self.embeddings_manager.initialize()
                
                # Embeddings are automatically loaded during initialize()
                
                # Check if we successfully loaded embeddings
                if hasattr(self.embeddings_manager, 'id_to_text') and self.embeddings_manager.id_to_text:
                    chunk_count = len(self.embeddings_manager.id_to_text)
                    logger.info(f"✅ Loaded {chunk_count} existing embeddings successfully")
                else:
                    logger.warning("⚠️ Embeddings files found but no content loaded")
                    self.embeddings_manager = None
            else:
                logger.info("No existing embeddings found - RAG agent will have limited functionality")
                self.embeddings_manager = None
                
        except Exception as e:
            logger.warning(f"⚠️ Failed to load existing embeddings: {e}")
            self.embeddings_manager = None

    async def close(self):
        """Close database connections"""
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
    
    async def initialize(self) -> None:
        """Initialize the database - calls init_database for compatibility"""
        await self.init_database()
    
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
    
    async def init_database(self, initialize_embeddings: bool = False) -> None:
        """
        Initialize database with complete schema
        Args:
            initialize_embeddings: If True, also initialize embeddings (use only during setup)
        """
        # Run migrations first
        await self._migrate_database()
        
        async with aiosqlite.connect(self.db_path) as db:
            # Enable foreign keys
            await db.execute("PRAGMA foreign_keys = ON;")
            
            # Create all tables (IF NOT EXISTS will skip existing ones)
            # Core user management tables
            await self._create_users_table(db)
            await self._create_doctors_table(db)
            await self._create_patients_table(db)
            
            # Session and workflow tables
            await self._create_sessions_table(db)
            await self._create_mri_scans_table(db)
            await self._create_predictions_table(db)
            await self._create_medical_reports_table(db)
            await self._create_action_flags_table(db)
            
            # Agent communication and knowledge base
            await self._create_knowledge_entries_table(db)
            await self._create_agent_messages_table(db)
            
            # NOTE: Following tables are REMOVED (never used in codebase):
            # - embeddings table (embeddings handled by FAISS in files)
            # - audit_logs table (not implemented yet)
            # - lab_results table (not implemented yet)
            
            # Enhanced tables for admin CRUD and patient history
            await self._create_doctor_patient_assignments_table(db)
            await self._create_consultations_table(db)
            await self._create_report_status_table(db)
            await self._create_patient_timeline_table(db)
            await self._create_patient_statistics_table(db)
            
            # Create database triggers for automatic updates
            await self._create_database_triggers(db)
            
            await db.commit()
            
            # Only initialize embeddings if explicitly requested (during setup)
            if initialize_embeddings:
                logger.info("Initializing embeddings as requested...")
                embeddings_success = await self._initialize_embeddings_on_demand()
                
                if embeddings_success:
                    logger.info("✅ Database initialized successfully with embeddings support")
                else:
                    logger.info("✅ Database initialized successfully (embeddings initialization failed)")
            else:
                # Try to load existing embeddings manager if it exists
                await self._load_existing_embeddings()
                logger.info("✅ Database initialized successfully (embeddings loaded if available)")
    
    async def _create_users_table(self, db: aiosqlite.Connection):
        """Create users table with enhanced schema"""
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE,
                email TEXT UNIQUE,
                password_hash TEXT,
                name TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('admin', 'doctor', 'patient')),
                age INTEGER,
                gender TEXT,
                specialization TEXT,  -- For doctors
                license_number TEXT,  -- For doctors
                phone TEXT,
                address TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            );
        """)
        await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username);")
        await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active);")
    
    async def _create_doctors_table(self, db: aiosqlite.Connection):
        """Create doctors table with doctor-specific information"""
        await db.execute("""
            CREATE TABLE IF NOT EXISTS doctors (
                doctor_id TEXT PRIMARY KEY,
                user_id TEXT UNIQUE NOT NULL,
                specialization TEXT,
                license_number TEXT UNIQUE,
                years_experience INTEGER,
                hospital_affiliation TEXT,
                consultation_fee DECIMAL(10,2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_doctors_user_id ON doctors(user_id);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_doctors_specialization ON doctors(specialization);")
        await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_doctors_license ON doctors(license_number);")

    async def _create_patients_table(self, db: aiosqlite.Connection):
        """Create patients table with patient-specific information"""
        await db.execute("""
            CREATE TABLE IF NOT EXISTS patients (
                patient_id TEXT PRIMARY KEY,
                user_id TEXT UNIQUE,
                name TEXT NOT NULL,
                age INTEGER,
                gender TEXT CHECK (gender IN ('male', 'female', 'other')),
                date_of_birth DATE,
                medical_history TEXT,
                emergency_contact_name TEXT,
                emergency_contact_phone TEXT,
                assigned_doctor_id TEXT,
                insurance_info TEXT,
                allergies TEXT,
                current_medications TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (assigned_doctor_id) REFERENCES doctors(doctor_id)
            );
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_patients_user_id ON patients(user_id);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_patients_name ON patients(name);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_patients_assigned_doctor ON patients(assigned_doctor_id);")

    # DEPRECATED: Old reports table removed - use medical_reports table instead
    # This method has been deleted to avoid confusion and data duplication
    # The new medical_reports table provides enhanced functionality

    # NOTE: Unused tables removed - embeddings, audit_logs, lab_results
    # These tables were defined but never used in the codebase:
    # - embeddings: Handled by EmbeddingsManager with FAISS (file-based storage)
    # - audit_logs: Logging feature not yet implemented
    # - lab_results: Lab integration not yet implemented
    
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
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
                FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE SET NULL,
                FOREIGN KEY (doctor_id) REFERENCES users(id) ON DELETE SET NULL
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
    
    # ========== ENHANCED TABLES FOR ADMIN CRUD & PATIENT HISTORY ==========
    
    async def _create_doctor_patient_assignments_table(self, db: aiosqlite.Connection):
        """Create doctor-patient assignments table (many-to-many relationship)"""
        await db.execute("""
            CREATE TABLE IF NOT EXISTS doctor_patient_assignments (
                id TEXT PRIMARY KEY,
                doctor_id TEXT NOT NULL,
                patient_id TEXT NOT NULL,
                assignment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                assignment_type TEXT CHECK (assignment_type IN ('primary', 'consultant', 'specialist')) DEFAULT 'primary',
                is_active BOOLEAN DEFAULT 1,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP,
                FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id) ON DELETE CASCADE,
                FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
                UNIQUE(doctor_id, patient_id, assignment_date)
            );
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_dpa_doctor ON doctor_patient_assignments(doctor_id);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_dpa_patient ON doctor_patient_assignments(patient_id);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_dpa_active ON doctor_patient_assignments(is_active);")
    
    async def _create_consultations_table(self, db: aiosqlite.Connection):
        """Create consultations table for visit/consultation history"""
        await db.execute("""
            CREATE TABLE IF NOT EXISTS consultations (
                id TEXT PRIMARY KEY,
                patient_id TEXT NOT NULL,
                doctor_id TEXT NOT NULL,
                session_id TEXT,
                consultation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                consultation_type TEXT CHECK (consultation_type IN ('in-person', 'telemedicine', 'follow-up', 'emergency')) DEFAULT 'in-person',
                chief_complaint TEXT,
                diagnosis TEXT,
                prescription TEXT,
                notes TEXT,
                next_visit_date TIMESTAMP,
                status TEXT DEFAULT 'completed' CHECK (status IN ('scheduled', 'completed', 'cancelled', 'no-show')),
                duration_minutes INTEGER,
                fee_charged DECIMAL(10,2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
                FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id) ON DELETE CASCADE,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE SET NULL
            );
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_consultations_patient ON consultations(patient_id);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_consultations_doctor ON consultations(doctor_id);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_consultations_date ON consultations(consultation_date);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_consultations_status ON consultations(status);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_consultations_session ON consultations(session_id);")
    
    async def _create_report_status_table(self, db: aiosqlite.Connection):
        """Create report status table for tracking report generation pipeline"""
        await db.execute("""
            CREATE TABLE IF NOT EXISTS report_status (
                id TEXT PRIMARY KEY,
                patient_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                report_id TEXT,
                prediction_id TEXT,
                mri_scan_id TEXT,
                status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'generating', 'generated', 'failed', 'archived')),
                requested_by TEXT NOT NULL,
                requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                generated_at TIMESTAMP,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,
                priority INTEGER DEFAULT 0,
                report_type TEXT,
                metadata JSON,
                FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
                FOREIGN KEY (report_id) REFERENCES medical_reports(id) ON DELETE SET NULL,
                FOREIGN KEY (prediction_id) REFERENCES predictions(id) ON DELETE SET NULL,
                FOREIGN KEY (mri_scan_id) REFERENCES mri_scans(id) ON DELETE SET NULL
            );
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_report_status_patient ON report_status(patient_id);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_report_status_session ON report_status(session_id);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_report_status_status ON report_status(status);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_report_status_requested_by ON report_status(requested_by);")
    
    async def _create_patient_timeline_table(self, db: aiosqlite.Connection):
        """Create patient timeline table for consolidated medical journey"""
        await db.execute("""
            CREATE TABLE IF NOT EXISTS patient_timeline (
                id TEXT PRIMARY KEY,
                patient_id TEXT NOT NULL,
                event_type TEXT NOT NULL CHECK (event_type IN ('scan', 'prediction', 'report', 'consultation', 'diagnosis', 'treatment', 'note')),
                event_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                event_title TEXT NOT NULL,
                event_description TEXT,
                related_id TEXT,
                related_table TEXT,
                doctor_id TEXT,
                session_id TEXT,
                severity TEXT CHECK (severity IN ('info', 'low', 'medium', 'high', 'critical')) DEFAULT 'info',
                metadata JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
                FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id) ON DELETE SET NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE SET NULL
            );
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_timeline_patient ON patient_timeline(patient_id);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_timeline_event_type ON patient_timeline(event_type);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_timeline_event_date ON patient_timeline(event_date);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_timeline_severity ON patient_timeline(severity);")
    
    async def _create_patient_statistics_table(self, db: aiosqlite.Connection):
        """Create patient statistics table for pre-computed metrics"""
        await db.execute("""
            CREATE TABLE IF NOT EXISTS patient_statistics (
                patient_id TEXT PRIMARY KEY,
                total_consultations INTEGER DEFAULT 0,
                total_mri_scans INTEGER DEFAULT 0,
                total_predictions INTEGER DEFAULT 0,
                total_reports INTEGER DEFAULT 0,
                unique_doctors_count INTEGER DEFAULT 0,
                first_visit_date TIMESTAMP,
                last_visit_date TIMESTAMP,
                last_scan_date TIMESTAMP,
                last_report_date TIMESTAMP,
                has_parkinsons BOOLEAN,
                disease_stage TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE
            );
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_patient_stats_last_visit ON patient_statistics(last_visit_date);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_patient_stats_has_parkinsons ON patient_statistics(has_parkinsons);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_patient_stats_stage ON patient_statistics(disease_stage);")
    
    async def _create_database_triggers(self, db: aiosqlite.Connection):
        """Create database triggers for automatic updates"""
        
        # Trigger: Auto-update patient statistics on new consultation
        await db.execute("""
            CREATE TRIGGER IF NOT EXISTS update_stats_on_consultation
            AFTER INSERT ON consultations
            FOR EACH ROW
            BEGIN
                UPDATE patient_statistics
                SET 
                    total_consultations = total_consultations + 1,
                    last_visit_date = NEW.consultation_date,
                    last_updated = CURRENT_TIMESTAMP,
                    unique_doctors_count = (
                        SELECT COUNT(DISTINCT doctor_id) 
                        FROM doctor_patient_assignments 
                        WHERE patient_id = NEW.patient_id AND is_active = 1
                    )
                WHERE patient_id = NEW.patient_id;
            END;
        """)
        
        # Trigger: Auto-update stats on new report
        await db.execute("""
            CREATE TRIGGER IF NOT EXISTS update_stats_on_report
            AFTER INSERT ON medical_reports
            FOR EACH ROW
            BEGIN
                UPDATE patient_statistics
                SET 
                    total_reports = total_reports + 1,
                    last_report_date = NEW.created_at,
                    last_updated = CURRENT_TIMESTAMP
                WHERE patient_id = (SELECT patient_id FROM sessions WHERE id = NEW.session_id);
            END;
        """)
        
        # Trigger: Auto-create timeline entry on MRI scan
        await db.execute("""
            CREATE TRIGGER IF NOT EXISTS timeline_on_scan
            AFTER INSERT ON mri_scans
            FOR EACH ROW
            BEGIN
                INSERT INTO patient_timeline (
                    id, patient_id, event_type, event_date, event_title, 
                    event_description, related_id, related_table, session_id, severity
                )
                SELECT 
                    'timeline_scan_' || NEW.id,
                    s.patient_id,
                    'scan',
                    NEW.upload_timestamp,
                    'MRI Scan Uploaded',
                    'File: ' || COALESCE(NEW.original_filename, 'Unknown'),
                    NEW.id,
                    'mri_scans',
                    NEW.session_id,
                    'info'
                FROM sessions s 
                WHERE s.id = NEW.session_id 
                  AND s.patient_id IS NOT NULL 
                  AND s.patient_id != '';
            END;
        """)
        
        # Trigger: Auto-create timeline entry on prediction
        await db.execute("""
            CREATE TRIGGER IF NOT EXISTS timeline_on_prediction
            AFTER INSERT ON predictions
            FOR EACH ROW
            BEGIN
                INSERT INTO patient_timeline (
                    id, patient_id, event_type, event_date, event_title, 
                    event_description, related_id, related_table, session_id, severity
                )
                SELECT 
                    'timeline_pred_' || NEW.id,
                    s.patient_id,
                    'prediction',
                    NEW.created_at,
                    'Parkinson''s Analysis Completed',
                    'Result: ' || COALESCE(NEW.binary_result, 'Unknown'),
                    NEW.id,
                    'predictions',
                    NEW.session_id,
                    CASE 
                        WHEN NEW.binary_result = 'Parkinsons Detected' THEN 'high'
                        ELSE 'medium'
                    END
                FROM sessions s 
                WHERE s.id = NEW.session_id 
                  AND s.patient_id IS NOT NULL 
                  AND s.patient_id != '';
            END;
        """)
    
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
    
    async def get_all_users(self, role: Optional[str] = None, is_active: Optional[bool] = None) -> List[Dict[str, Any]]:
        """Get all users, optionally filtered by role and active status"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                
                query = "SELECT * FROM users WHERE 1=1"
                params = []
                
                if role:
                    query += " AND role = ?"
                    params.append(role)
                
                if is_active is not None:
                    query += " AND is_active = ?"
                    params.append(1 if is_active else 0)
                
                query += " ORDER BY created_at DESC"
                
                async with db.execute(query, params) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting all users: {e}")
            return []
    
    async def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user by username"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("SELECT * FROM users WHERE username = ?", (username,)) as cursor:
                    row = await cursor.fetchone()
                    return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error getting user by username: {e}")
            return None
    
    async def update_user(self, user_id: str, **updates) -> bool:
        """Update user fields"""
        try:
            if not updates:
                return False
            
            async with aiosqlite.connect(self.db_path) as db:
                # Build update query
                set_clauses = []
                params = []
                
                for key, value in updates.items():
                    if key not in ['id', 'created_at']:  # Don't allow updating these
                        set_clauses.append(f"{key} = ?")
                        params.append(value)
                
                if not set_clauses:
                    return False
                
                # Add updated_at timestamp
                set_clauses.append("updated_at = ?")
                params.append(datetime.now().isoformat())
                params.append(user_id)
                
                query = f"UPDATE users SET {', '.join(set_clauses)} WHERE id = ?"
                await db.execute(query, params)
                await db.commit()
                
                logger.info(f"Updated user {user_id}")
                return True
        except Exception as e:
            logger.error(f"Error updating user: {e}")
            return False
    
    async def deactivate_user(self, user_id: str) -> bool:
        """Deactivate a user account"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    UPDATE users 
                    SET is_active = 0, updated_at = ?
                    WHERE id = ?
                """, (datetime.now().isoformat(), user_id))
                await db.commit()
                logger.info(f"Deactivated user {user_id}")
                return True
        except Exception as e:
            logger.error(f"Error deactivating user: {e}")
            return False
    
    async def activate_user(self, user_id: str) -> bool:
        """Activate a user account"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    UPDATE users 
                    SET is_active = 1, updated_at = ?
                    WHERE id = ?
                """, (datetime.now().isoformat(), user_id))
                await db.commit()
                logger.info(f"Activated user {user_id}")
                return True
        except Exception as e:
            logger.error(f"Error activating user: {e}")
            return False
    
    async def delete_user(self, user_id: str) -> bool:
        """Permanently delete a user (use with caution)"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("DELETE FROM users WHERE id = ?", (user_id,))
                await db.commit()
                logger.info(f"Deleted user {user_id}")
                return True
        except Exception as e:
            logger.error(f"Error deleting user: {e}")
            return False
    
    async def get_users_by_role(self, role: str) -> List[Dict[str, Any]]:
        """Get all users with a specific role"""
        return await self.get_all_users(role=role)
    
    async def get_active_users(self) -> List[Dict[str, Any]]:
        """Get all active users"""
        return await self.get_all_users(is_active=True)
    
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
            cursor = await db.execute("SELECT * FROM patients WHERE assigned_doctor_id = ?", (doctor_id,))
            rows = await cursor.fetchall()
            return [dict_to_patient(dict(row)) for row in rows]
    
    async def get_all_patients(self) -> List[Dict[str, Any]]:
        """Get all patients in the system"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM patients ORDER BY created_at DESC")
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
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
    
    async def update_session_patient_info(self, session_id: str, patient_id: str, patient_name: str) -> bool:
        """Update session with patient information"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    UPDATE sessions 
                    SET patient_id = ?, patient_name = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE id = ?
                """, (patient_id, patient_name, session_id))
                await db.commit()
                logger.info(f"Updated session {session_id} with patient info: {patient_name} ({patient_id})")
                return True
        except Exception as e:
            logger.error(f"Failed to update session patient info: {e}")
            return False
    
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
    
    async def get_reports_by_mri_scan(self, mri_file_path: str) -> List[Dict[str, Any]]:
        """Get all reports associated with a specific MRI scan file"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            # Find session_id from mri_scans, then get reports from that session
            cursor = await db.execute("""
                SELECT mr.*
                FROM medical_reports mr
                INNER JOIN mri_scans mri ON mr.session_id = mri.session_id
                WHERE mri.file_path = ?
                ORDER BY mr.created_at DESC
            """, (mri_file_path,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def get_patient_with_reports(self, patient_id: str) -> Optional[Dict[str, Any]]:
        """
        Get patient information with all their reports (OPTIMIZED with single JOIN query)
        Returns: {
            'patient': {...patient info...},
            'reports': [{...report with prediction info...}]
        }
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            # OPTIMIZED: Single query with JOINs instead of multiple queries
            cursor = await db.execute("""
                SELECT 
                    p.patient_id,
                    p.name as patient_name,
                    p.age,
                    p.gender,
                    p.date_of_birth,
                    p.medical_history,
                    p.allergies,
                    p.current_medications,
                    p.emergency_contact_name,
                    p.emergency_contact_phone,
                    p.assigned_doctor_id,
                    u.name as assigned_doctor_name,
                    mr.id as report_id,
                    mr.title as report_title,
                    mr.report_type,
                    mr.content as report_content,
                    mr.created_at as report_created_at,
                    mr.file_path as report_file_path,
                    mr.confidence_level,
                    pred.id as prediction_id,
                    pred.binary_result,
                    pred.stage_result,
                    pred.confidence_score as pred_confidence,
                    pred.binary_confidence,
                    pred.stage_confidence,
                    s.id as session_id,
                    s.created_at as session_created_at,
                    mri.id as mri_id,
                    mri.file_path as mri_file_path,
                    mri.original_filename as mri_filename
                FROM patients p
                LEFT JOIN doctors d ON p.assigned_doctor_id = d.doctor_id
                LEFT JOIN users u ON d.user_id = u.id
                LEFT JOIN sessions s ON p.patient_id = s.patient_id
                LEFT JOIN medical_reports mr ON s.id = mr.session_id
                LEFT JOIN predictions pred ON mr.prediction_id = pred.id
                LEFT JOIN mri_scans mri ON s.id = mri.session_id
                WHERE p.patient_id = ?
                ORDER BY mr.created_at DESC
            """, (patient_id,))
            
            rows = await cursor.fetchall()
            
            if not rows or not rows[0]['patient_id']:
                return None
            
            # Build patient info from first row
            first_row = rows[0]
            patient_info = {
                'patient_id': first_row['patient_id'],
                'name': first_row['patient_name'],
                'age': first_row['age'],
                'gender': first_row['gender'],
                'date_of_birth': first_row['date_of_birth'],
                'medical_history': first_row['medical_history'],
                'allergies': first_row['allergies'],
                'current_medications': first_row['current_medications'],
                'emergency_contact_name': first_row['emergency_contact_name'],
                'emergency_contact_phone': first_row['emergency_contact_phone'],
                'assigned_doctor_id': first_row['assigned_doctor_id'],
                'assigned_doctor_name': first_row['assigned_doctor_name']
            }
            
            # Build reports list from all rows
            reports = []
            seen_reports = set()
            for row in rows:
                if row['report_id'] and row['report_id'] not in seen_reports:
                    seen_reports.add(row['report_id'])
                    reports.append({
                        'report_id': row['report_id'],
                        'title': row['report_title'],
                        'report_type': row['report_type'],
                        'content': row['report_content'],
                        'created_at': row['report_created_at'],
                        'file_path': row['report_file_path'],
                        'confidence_level': row['confidence_level'],
                        'session_id': row['session_id'],
                        'session_created_at': row['session_created_at'],
                        'mri_file_path': row['mri_file_path'],
                        'mri_filename': row['mri_filename'],
                        'prediction': {
                            'prediction_id': row['prediction_id'],
                            'binary_result': row['binary_result'],
                            'stage_result': row['stage_result'],
                            'confidence_score': row['pred_confidence'],
                            'binary_confidence': row['binary_confidence'],
                            'stage_confidence': row['stage_confidence']
                        } if row['prediction_id'] else None
                    })
            
            return {
                'patient': patient_info,
                'reports': reports,
                'report_count': len(reports)
            }
    
    async def get_admin_dashboard(self) -> Dict[str, Any]:
        """Get comprehensive admin dashboard with all system statistics"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            # Get total counts
            cursor = await db.execute("SELECT COUNT(*) as total FROM doctors")
            total_doctors = (await cursor.fetchone())['total']
            
            cursor = await db.execute("SELECT COUNT(*) as total FROM patients")
            total_patients = (await cursor.fetchone())['total']
            
            cursor = await db.execute("SELECT COUNT(*) as total FROM medical_reports")
            total_reports = (await cursor.fetchone())['total']
            
            cursor = await db.execute("SELECT COUNT(*) as total FROM sessions WHERE status = 'active'")
            active_sessions = (await cursor.fetchone())['total']
            
            # Get doctors with patient counts
            cursor = await db.execute("""
                SELECT 
                    d.doctor_id,
                    d.name as doctor_name,
                    d.specialty,
                    d.license_number,
                    COUNT(DISTINCT p.patient_id) as patient_count,
                    COUNT(DISTINCT s.id) as session_count
                FROM doctors d
                LEFT JOIN patients p ON d.doctor_id = p.assigned_doctor_id
                LEFT JOIN sessions s ON d.doctor_id = s.doctor_id
                GROUP BY d.doctor_id
                ORDER BY patient_count DESC
            """)
            doctors_data = [dict(row) for row in await cursor.fetchall()]
            
            # Get patients with report counts and assigned doctor info
            cursor = await db.execute("""
                SELECT 
                    p.patient_id,
                    p.name as patient_name,
                    p.age,
                    p.gender,
                    p.assigned_doctor_id,
                    d.name as doctor_name,
                    COUNT(DISTINCT s.id) as session_count,
                    COUNT(DISTINCT mr.id) as report_count
                FROM patients p
                LEFT JOIN doctors d ON p.assigned_doctor_id = d.doctor_id
                LEFT JOIN sessions s ON p.patient_id = s.patient_id
                LEFT JOIN medical_reports mr ON s.id = mr.session_id
                GROUP BY p.patient_id
                ORDER BY report_count DESC
            """)
            patients_data = [dict(row) for row in await cursor.fetchall()]
            
            # Get recent activity
            cursor = await db.execute("""
                SELECT 
                    mr.id,
                    mr.title,
                    mr.report_type,
                    mr.created_at,
                    s.patient_name,
                    s.doctor_name
                FROM medical_reports mr
                INNER JOIN sessions s ON mr.session_id = s.id
                ORDER BY mr.created_at DESC
                LIMIT 10
            """)
            recent_reports = [dict(row) for row in await cursor.fetchall()]
            
            return {
                'summary': {
                    'total_doctors': total_doctors,
                    'total_patients': total_patients,
                    'total_reports': total_reports,
                    'active_sessions': active_sessions
                },
                'doctors': doctors_data,
                'patients': patients_data,
                'recent_reports': recent_reports
            }
    
    async def get_doctor_dashboard(self, doctor_id: str) -> Dict[str, Any]:
        """Get dashboard for a specific doctor showing their assigned patients and reports"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            # Get doctor info
            cursor = await db.execute("SELECT * FROM doctors WHERE doctor_id = ?", (doctor_id,))
            doctor_info = dict(await cursor.fetchone())
            
            # Get assigned patients with report counts
            cursor = await db.execute("""
                SELECT 
                    p.patient_id,
                    p.name as patient_name,
                    p.age,
                    p.gender,
                    p.medical_history,
                    p.emergency_contact,
                    COUNT(DISTINCT s.id) as session_count,
                    COUNT(DISTINCT mr.id) as report_count,
                    MAX(mr.created_at) as last_report_date
                FROM patients p
                LEFT JOIN sessions s ON p.patient_id = s.patient_id
                LEFT JOIN medical_reports mr ON s.id = mr.session_id
                WHERE p.assigned_doctor_id = ?
                GROUP BY p.patient_id
                ORDER BY last_report_date DESC
            """, (doctor_id,))
            patients_data = [dict(row) for row in await cursor.fetchall()]
            
            # Get recent reports for this doctor's patients
            cursor = await db.execute("""
                SELECT 
                    mr.id,
                    mr.title,
                    mr.report_type,
                    mr.created_at,
                    mr.file_path,
                    s.patient_name,
                    p.patient_id
                FROM medical_reports mr
                INNER JOIN sessions s ON mr.session_id = s.id
                INNER JOIN patients p ON s.patient_id = p.patient_id
                WHERE p.assigned_doctor_id = ?
                ORDER BY mr.created_at DESC
                LIMIT 20
            """, (doctor_id,))
            recent_reports = [dict(row) for row in await cursor.fetchall()]
            
            # Get session statistics
            cursor = await db.execute("""
                SELECT 
                    COUNT(DISTINCT s.id) as total_sessions,
                    COUNT(DISTINCT CASE WHEN s.status = 'active' THEN s.id END) as active_sessions,
                    COUNT(DISTINCT p.patient_id) as total_patients
                FROM sessions s
                INNER JOIN patients p ON s.patient_id = p.patient_id
                WHERE p.assigned_doctor_id = ?
            """, (doctor_id,))
            stats = dict(await cursor.fetchone())
            
            return {
                'doctor_info': doctor_info,
                'statistics': stats,
                'patients': patients_data,
                'recent_reports': recent_reports
            }
    
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
    
    # ==================== DOCTOR-PATIENT ASSIGNMENT CRUD ====================
    
    async def assign_doctor_to_patient(
        self,
        doctor_id: str,
        patient_id: str,
        assignment_type: str = 'primary',
        notes: Optional[str] = None
    ) -> bool:
        """Assign a doctor to a patient."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO doctor_patient_assignments 
                    (doctor_id, patient_id, assignment_type, assigned_date, notes, is_active)
                    VALUES (?, ?, ?, ?, ?, 1)
                """, (doctor_id, patient_id, assignment_type, datetime.now().isoformat(), notes))
                await db.commit()
                logger.info(f"Assigned doctor {doctor_id} to patient {patient_id} as {assignment_type}")
                return True
        except Exception as e:
            logger.error(f"Error assigning doctor to patient: {e}")
            return False
    
    async def get_patient_doctors(self, patient_id: str) -> List[Dict[str, Any]]:
        """Get all doctors assigned to a patient."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("""
                    SELECT dpa.*, u.full_name as doctor_name, u.email as doctor_email
                    FROM doctor_patient_assignments dpa
                    JOIN users u ON dpa.doctor_id = u.user_id
                    WHERE dpa.patient_id = ? AND dpa.is_active = 1
                    ORDER BY dpa.assigned_date DESC
                """, (patient_id,)) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting patient doctors: {e}")
            return []
    
    async def get_doctor_patients(self, doctor_id: str) -> List[Dict[str, Any]]:
        """Get all patients assigned to a doctor."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("""
                    SELECT dpa.*, p.patient_name, p.age, p.gender, p.phone_number
                    FROM doctor_patient_assignments dpa
                    JOIN patients p ON dpa.patient_id = p.patient_id
                    WHERE dpa.doctor_id = ? AND dpa.is_active = 1
                    ORDER BY dpa.assigned_date DESC
                """, (doctor_id,)) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting doctor patients: {e}")
            return []
    
    async def deactivate_doctor_assignment(self, assignment_id: int) -> bool:
        """Deactivate a doctor-patient assignment."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    UPDATE doctor_patient_assignments 
                    SET is_active = 0 
                    WHERE id = ?
                """, (assignment_id,))
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error deactivating doctor assignment: {e}")
            return False
    
    # ==================== CONSULTATION CRUD ====================
    
    async def create_consultation(
        self,
        patient_id: str,
        doctor_id: str,
        consultation_type: str,
        chief_complaint: str,
        diagnosis: Optional[str] = None,
        prescription: Optional[str] = None,
        follow_up_date: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Optional[int]:
        """Create a new consultation record."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    INSERT INTO consultations 
                    (patient_id, doctor_id, consultation_date, consultation_type, 
                     chief_complaint, diagnosis, prescription, follow_up_date, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    patient_id, doctor_id, datetime.now().isoformat(), consultation_type,
                    chief_complaint, diagnosis, prescription, follow_up_date, notes
                ))
                await db.commit()
                consultation_id = cursor.lastrowid
                logger.info(f"Created consultation {consultation_id} for patient {patient_id}")
                return consultation_id
        except Exception as e:
            logger.error(f"Error creating consultation: {e}")
            return None
    
    async def get_patient_consultations(
        self, 
        patient_id: str, 
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get all consultations for a patient."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                query = """
                    SELECT c.*, u.full_name as doctor_name
                    FROM consultations c
                    JOIN users u ON c.doctor_id = u.user_id
                    WHERE c.patient_id = ?
                    ORDER BY c.consultation_date DESC
                """
                if limit:
                    query += f" LIMIT {limit}"
                
                async with db.execute(query, (patient_id,)) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting patient consultations: {e}")
            return []
    
    async def get_doctor_consultations(
        self, 
        doctor_id: str, 
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get all consultations for a doctor."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                query = """
                    SELECT c.*, p.patient_name, p.age, p.gender
                    FROM consultations c
                    JOIN patients p ON c.patient_id = p.patient_id
                    WHERE c.doctor_id = ?
                    ORDER BY c.consultation_date DESC
                """
                if limit:
                    query += f" LIMIT {limit}"
                
                async with db.execute(query, (doctor_id,)) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting doctor consultations: {e}")
            return []
    
    async def get_consultation_by_id(self, consultation_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific consultation by ID."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("""
                    SELECT c.*, 
                           u.full_name as doctor_name,
                           p.patient_name, p.age, p.gender
                    FROM consultations c
                    JOIN users u ON c.doctor_id = u.user_id
                    JOIN patients p ON c.patient_id = p.patient_id
                    WHERE c.id = ?
                """, (consultation_id,)) as cursor:
                    row = await cursor.fetchone()
                    return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error getting consultation: {e}")
            return None
    
    # ==================== REPORT STATUS CRUD ====================
    
    async def create_report_request(
        self,
        patient_id: str,
        report_type: str,
        requested_by: str
    ) -> Optional[int]:
        """Create a new report generation request."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    INSERT INTO report_status 
                    (patient_id, report_type, status, requested_date, requested_by)
                    VALUES (?, ?, 'pending', ?, ?)
                """, (patient_id, report_type, datetime.now().isoformat(), requested_by))
                await db.commit()
                report_id = cursor.lastrowid
                logger.info(f"Created report request {report_id} for patient {patient_id}")
                return report_id
        except Exception as e:
            logger.error(f"Error creating report request: {e}")
            return None
    
    async def update_report_status(
        self,
        report_id: int,
        status: str,
        report_path: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """Update the status of a report generation request."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                if status == 'generated' and report_path:
                    await db.execute("""
                        UPDATE report_status 
                        SET status = ?, generated_date = ?, report_path = ?
                        WHERE id = ?
                    """, (status, datetime.now().isoformat(), report_path, report_id))
                elif status == 'failed' and error_message:
                    await db.execute("""
                        UPDATE report_status 
                        SET status = ?, error_message = ?
                        WHERE id = ?
                    """, (status, error_message, report_id))
                else:
                    await db.execute("""
                        UPDATE report_status 
                        SET status = ?
                        WHERE id = ?
                    """, (status, report_id))
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error updating report status: {e}")
            return False
    
    async def get_pending_reports(self) -> List[Dict[str, Any]]:
        """Get all pending report generation requests."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("""
                    SELECT rs.*, p.patient_name, p.age
                    FROM report_status rs
                    JOIN patients p ON rs.patient_id = p.patient_id
                    WHERE rs.status IN ('pending', 'generating')
                    ORDER BY rs.requested_date ASC
                """) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting pending reports: {e}")
            return []
    
    async def get_patient_report_status(self, patient_id: str) -> List[Dict[str, Any]]:
        """Get all report status for a patient."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("""
                    SELECT * FROM report_status
                    WHERE patient_id = ?
                    ORDER BY requested_date DESC
                """, (patient_id,)) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting patient report status: {e}")
            return []
    
    async def get_failed_reports(self) -> List[Dict[str, Any]]:
        """Get all failed report generation requests."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("""
                    SELECT rs.*, p.patient_name
                    FROM report_status rs
                    JOIN patients p ON rs.patient_id = p.patient_id
                    WHERE rs.status = 'failed'
                    ORDER BY rs.requested_date DESC
                """) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting failed reports: {e}")
            return []
    
    # ==================== PATIENT TIMELINE CRUD ====================
    
    async def add_timeline_event(
        self,
        patient_id: str,
        event_type: str,
        event_description: str,
        severity: Optional[str] = None,
        related_record_id: Optional[str] = None
    ) -> Optional[int]:
        """Add an event to patient timeline."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    INSERT INTO patient_timeline 
                    (patient_id, event_date, event_type, event_description, severity, related_record_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    patient_id, datetime.now().isoformat(), event_type, 
                    event_description, severity, related_record_id
                ))
                await db.commit()
                event_id = cursor.lastrowid
                logger.info(f"Added timeline event {event_id} for patient {patient_id}")
                return event_id
        except Exception as e:
            logger.error(f"Error adding timeline event: {e}")
            return None
    
    async def get_patient_timeline(
        self, 
        patient_id: str, 
        limit: Optional[int] = None,
        event_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get patient timeline events."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                
                if event_type:
                    query = """
                        SELECT * FROM patient_timeline
                        WHERE patient_id = ? AND event_type = ?
                        ORDER BY event_date DESC
                    """
                    params = (patient_id, event_type)
                else:
                    query = """
                        SELECT * FROM patient_timeline
                        WHERE patient_id = ?
                        ORDER BY event_date DESC
                    """
                    params = (patient_id,)
                
                if limit:
                    query += f" LIMIT {limit}"
                
                async with db.execute(query, params) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting patient timeline: {e}")
            return []
    
    async def get_timeline_by_date_range(
        self,
        patient_id: str,
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        """Get timeline events within a date range."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("""
                    SELECT * FROM patient_timeline
                    WHERE patient_id = ? 
                      AND event_date BETWEEN ? AND ?
                    ORDER BY event_date DESC
                """, (patient_id, start_date, end_date)) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting timeline by date range: {e}")
            return []
    
    # ==================== PATIENT STATISTICS CRUD ====================
    
    async def initialize_patient_statistics(self, patient_id: str) -> bool:
        """Initialize statistics for a new patient."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO patient_statistics 
                    (patient_id, total_consultations, total_mri_scans, total_predictions,
                     total_reports, first_visit_date, last_visit_date, last_updated)
                    VALUES (?, 0, 0, 0, 0, ?, ?, ?)
                """, (
                    patient_id, 
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                ))
                await db.commit()
                logger.info(f"Initialized statistics for patient {patient_id}")
                return True
        except Exception as e:
            logger.error(f"Error initializing patient statistics: {e}")
            return False
    
    async def update_patient_statistics(
        self,
        patient_id: str,
        stat_type: str,
        increment: int = 1
    ) -> bool:
        """Update patient statistics by incrementing a counter."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                valid_stats = ['total_consultations', 'total_mri_scans', 
                              'total_predictions', 'total_reports']
                
                if stat_type not in valid_stats:
                    logger.error(f"Invalid stat type: {stat_type}")
                    return False
                
                await db.execute(f"""
                    UPDATE patient_statistics 
                    SET {stat_type} = {stat_type} + ?,
                        last_visit_date = ?,
                        last_updated = ?
                    WHERE patient_id = ?
                """, (increment, datetime.now().isoformat(), datetime.now().isoformat(), patient_id))
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error updating patient statistics: {e}")
            return False
    
    async def get_patient_statistics(self, patient_id: str) -> Optional[Dict[str, Any]]:
        """Get statistics for a patient."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("""
                    SELECT * FROM patient_statistics
                    WHERE patient_id = ?
                """, (patient_id,)) as cursor:
                    row = await cursor.fetchone()
                    return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error getting patient statistics: {e}")
            return None
    
    async def get_all_patient_statistics(
        self,
        order_by: str = 'last_visit_date',
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get statistics for all patients."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                
                valid_order_fields = ['total_consultations', 'total_mri_scans', 
                                     'total_predictions', 'total_reports', 
                                     'last_visit_date', 'first_visit_date']
                
                if order_by not in valid_order_fields:
                    order_by = 'last_visit_date'
                
                query = f"""
                    SELECT ps.*, p.patient_name, p.age, p.gender
                    FROM patient_statistics ps
                    JOIN patients p ON ps.patient_id = p.patient_id
                    ORDER BY ps.{order_by} DESC
                """
                
                if limit:
                    query += f" LIMIT {limit}"
                
                async with db.execute(query) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting all patient statistics: {e}")
            return []
    
    async def recalculate_patient_statistics(self, patient_id: str) -> bool:
        """Recalculate all statistics for a patient from scratch."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Get counts from various tables
                consultation_count = await db.execute(
                    "SELECT COUNT(*) FROM consultations WHERE patient_id = ?",
                    (patient_id,)
                )
                consultations = (await consultation_count.fetchone())[0]
                
                scan_count = await db.execute(
                    "SELECT COUNT(*) FROM mri_scans WHERE patient_id = ?",
                    (patient_id,)
                )
                scans = (await scan_count.fetchone())[0]
                
                prediction_count = await db.execute(
                    "SELECT COUNT(*) FROM predictions WHERE patient_id = ?",
                    (patient_id,)
                )
                predictions = (await prediction_count.fetchone())[0]
                
                report_count = await db.execute(
                    "SELECT COUNT(*) FROM reports WHERE patient_id = ?",
                    (patient_id,)
                )
                reports = (await report_count.fetchone())[0]
                
                # Get first and last visit dates
                timeline_dates = await db.execute("""
                    SELECT MIN(event_date) as first_date, MAX(event_date) as last_date
                    FROM patient_timeline
                    WHERE patient_id = ?
                """, (patient_id,))
                dates = await timeline_dates.fetchone()
                first_date = dates[0] if dates[0] else datetime.now().isoformat()
                last_date = dates[1] if dates[1] else datetime.now().isoformat()
                
                # Update statistics
                await db.execute("""
                    UPDATE patient_statistics
                    SET total_consultations = ?,
                        total_mri_scans = ?,
                        total_predictions = ?,
                        total_reports = ?,
                        first_visit_date = ?,
                        last_visit_date = ?,
                        last_updated = ?
                    WHERE patient_id = ?
                """, (
                    consultations, scans, predictions, reports,
                    first_date, last_date, datetime.now().isoformat(),
                    patient_id
                ))
                await db.commit()
                logger.info(f"Recalculated statistics for patient {patient_id}")
                return True
        except Exception as e:
            logger.error(f"Error recalculating patient statistics: {e}")
            return False
    
    # ==================== ADMIN DASHBOARD QUERIES ====================
    
    async def get_system_dashboard(self) -> Dict[str, Any]:
        """Get comprehensive system dashboard data."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Total counts
                user_count = await db.execute("SELECT COUNT(*) FROM users WHERE is_active = 1")
                total_users = (await user_count.fetchone())[0]
                
                patient_count = await db.execute("SELECT COUNT(*) FROM patients")
                total_patients = (await patient_count.fetchone())[0]
                
                doctor_count = await db.execute(
                    "SELECT COUNT(*) FROM users WHERE role = 'doctor' AND is_active = 1"
                )
                total_doctors = (await doctor_count.fetchone())[0]
                
                # Active patients (visited in last 30 days)
                thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
                active_count = await db.execute("""
                    SELECT COUNT(DISTINCT patient_id) 
                    FROM patient_timeline 
                    WHERE event_date >= ?
                """, (thirty_days_ago,))
                active_patients = (await active_count.fetchone())[0]
                
                # Pending reports
                pending_count = await db.execute("""
                    SELECT COUNT(*) FROM report_status 
                    WHERE status IN ('pending', 'generating')
                """)
                pending_reports = (await pending_count.fetchone())[0]
                
                # Failed reports
                failed_count = await db.execute("""
                    SELECT COUNT(*) FROM report_status WHERE status = 'failed'
                """)
                failed_reports = (await failed_count.fetchone())[0]
                
                # Patients with Parkinson's (based on predictions)
                parkinsons_count = await db.execute("""
                    SELECT COUNT(DISTINCT p.patient_id) 
                    FROM patients p
                    INNER JOIN sessions s ON s.patient_id = p.patient_id
                    INNER JOIN predictions pr ON pr.session_id = s.session_id
                    WHERE pr.binary_result = 'Positive'
                """)
                parkinsons_patients = (await parkinsons_count.fetchone())[0] or 0
                
                # Recent activity (last 24 hours)
                yesterday = (datetime.now() - timedelta(days=1)).isoformat()
                recent_scans = await db.execute("""
                    SELECT COUNT(*) FROM mri_scans WHERE upload_date >= ?
                """, (yesterday,))
                scans_24h = (await recent_scans.fetchone())[0]
                
                recent_predictions = await db.execute("""
                    SELECT COUNT(*) FROM predictions WHERE prediction_date >= ?
                """, (yesterday,))
                predictions_24h = (await recent_predictions.fetchone())[0]
                
                recent_reports = await db.execute("""
                    SELECT COUNT(*) FROM report_status 
                    WHERE generated_date >= ? AND status = 'generated'
                """, (yesterday,))
                reports_24h = (await recent_reports.fetchone())[0]
                
                return {
                    'total_users': total_users,
                    'total_patients': total_patients,
                    'total_doctors': total_doctors,
                    'active_patients_30d': active_patients,
                    'pending_reports': pending_reports,
                    'failed_reports': failed_reports,
                    'parkinsons_patients': parkinsons_patients,
                    'parkinsons_percentage': round((parkinsons_patients / total_patients * 100) if total_patients > 0 else 0, 1),
                    'activity_24h': {
                        'scans': scans_24h,
                        'predictions': predictions_24h,
                        'reports': reports_24h
                    },
                    'timestamp': datetime.now().isoformat()
                }
        except Exception as e:
            logger.error(f"Error getting system dashboard: {e}")
            return {}
    
    async def get_patient_dashboard(self, patient_id: str) -> Dict[str, Any]:
        """Get comprehensive dashboard for a specific patient."""
        try:
            # Get patient basic info
            patient_info = await self.get_patient_by_id(patient_id)
            if not patient_info:
                return {}
            
            # Get statistics
            stats = await self.get_patient_statistics(patient_id)
            
            # Get assigned doctors
            doctors = await self.get_patient_doctors(patient_id)
            
            # Get recent timeline (last 10 events)
            timeline = await self.get_patient_timeline(patient_id, limit=10)
            
            # Get report status
            reports = await self.get_patient_report_status(patient_id)
            
            # Get recent consultations
            consultations = await self.get_patient_consultations(patient_id, limit=5)
            
            return {
                'patient_info': patient_info,
                'statistics': stats,
                'assigned_doctors': doctors,
                'recent_timeline': timeline,
                'report_status': reports,
                'recent_consultations': consultations,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting patient dashboard: {e}")
            return {}