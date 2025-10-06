"""
Authentication and User Management System for Parkinson's Multiagent System

Handles user roles: Admin, Doctor, Patient
- Admin: Admin123 password, full system access
- Doctor: Doctor ID + password, access to own patients only  
- Patient: Patient ID only, access to own reports only
"""

import asyncio
import logging
import hashlib
import uuid
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class UserRole(Enum):
    ADMIN = "admin"
    DOCTOR = "doctor"
    PATIENT = "patient"


@dataclass
class User:
    """Base user class"""
    user_id: str
    role: UserRole
    name: str
    created_at: datetime
    last_login: Optional[datetime] = None
    active: bool = True


@dataclass
class AdminUser(User):
    """Admin user with full system access"""
    password_hash: str = ""


@dataclass
class DoctorUser(User):
    """Doctor user with access to assigned patients"""
    doctor_id: str = ""
    password_hash: str = ""
    age: int = 0
    specialty: str = "Neurology"
    license_number: Optional[str] = None
    patients: List[str] = None  # List of patient IDs
    
    def __post_init__(self):
        if self.patients is None:
            self.patients = []


@dataclass
class PatientUser(User):
    """Patient user with access to own reports only"""
    patient_id: str = ""
    age: int = 0
    doctor_id: Optional[str] = None  # Assigned doctor
    medical_history: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.medical_history is None:
            self.medical_history = {}


class AuthenticationManager:
    """Manages user authentication and authorization"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.current_user = None
        self.session_token = None
        
        # Default admin credentials
        self.ADMIN_PASSWORD = "Admin123"
        
    async def initialize(self):
        """Initialize authentication system"""
        await self._create_tables()
        await self._create_default_admin()
        logger.info("Authentication system initialized")
    
    async def _create_tables(self):
        """Create user tables in database - use existing users table"""
        # Note: We use the existing users table from DatabaseManager
        # No need to create a conflicting users table
        
        create_admins_table = """
        CREATE TABLE IF NOT EXISTS admins (
            user_id TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
        """
        
        create_doctors_table = """
        CREATE TABLE IF NOT EXISTS doctors (
            user_id TEXT PRIMARY KEY,
            doctor_id TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            age INTEGER,
            specialty TEXT DEFAULT 'Neurology',
            license_number TEXT,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
        """
        
        create_patients_table = """
        CREATE TABLE IF NOT EXISTS patients (
            user_id TEXT PRIMARY KEY,
            patient_id TEXT UNIQUE NOT NULL,
            age INTEGER,
            doctor_id TEXT,
            medical_history TEXT,  -- JSON string
            FOREIGN KEY (user_id) REFERENCES users (user_id),
            FOREIGN KEY (doctor_id) REFERENCES doctors (doctor_id)
        )
        """
        
        create_doctor_patients_table = """
        CREATE TABLE IF NOT EXISTS doctor_patients (
            doctor_id TEXT,
            patient_id TEXT,
            assigned_at TEXT NOT NULL,
            PRIMARY KEY (doctor_id, patient_id),
            FOREIGN KEY (doctor_id) REFERENCES doctors (doctor_id),
            FOREIGN KEY (patient_id) REFERENCES patients (patient_id)
        )
        """
        
        async with self.db_manager.get_connection() as conn:
            await conn.execute(create_admins_table)
            await conn.execute(create_doctors_table)
            await conn.execute(create_patients_table)
            await conn.execute(create_doctor_patients_table)
            await conn.commit()
    
    async def _create_default_admin(self):
        """Create default admin user if not exists"""
        try:
            admin_exists = await self._user_exists("admin", UserRole.ADMIN)
            if not admin_exists:
                admin_user = AdminUser(
                    user_id="admin_001",
                    role=UserRole.ADMIN,
                    name="System Administrator",
                    created_at=datetime.now(),
                    password_hash=self._hash_password(self.ADMIN_PASSWORD)
                )
                await self._store_admin_user(admin_user)
                logger.info("Default admin user created with password: Admin123")
        except Exception as e:
            logger.error(f"Failed to create default admin: {e}")
    
    def _hash_password(self, password: str) -> str:
        """Hash password for secure storage"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        return self._hash_password(password) == password_hash
    
    async def login(self, role: UserRole, **credentials) -> Tuple[bool, str, Optional[User]]:
        """
        Login user based on role
        
        Returns: (success, message, user_object)
        """
        try:
            if role == UserRole.ADMIN:
                return await self._login_admin(credentials.get('password', ''))
            elif role == UserRole.DOCTOR:
                return await self._login_doctor(
                    credentials.get('doctor_id', ''),
                    credentials.get('password', '')
                )
            elif role == UserRole.PATIENT:
                return await self._login_patient(credentials.get('patient_id', ''))
            else:
                return False, "Invalid role", None
                
        except Exception as e:
            logger.error(f"Login error: {e}")
            return False, f"Login failed: {str(e)}", None
    
    async def _login_admin(self, password: str) -> Tuple[bool, str, Optional[AdminUser]]:
        """Login admin user"""
        if not password:
            return False, "Password required for admin", None
        
        admin_user = await self._get_admin_user()
        if not admin_user:
            return False, "Admin user not found", None
        
        if not self._verify_password(password, admin_user.password_hash):
            return False, "Invalid admin password", None
        
        # Update last login
        await self._update_last_login(admin_user.user_id)
        admin_user.last_login = datetime.now()
        
        self.current_user = admin_user
        self.session_token = str(uuid.uuid4())
        
        logger.info(f"Admin user logged in successfully")
        return True, "Admin login successful", admin_user
    
    async def _login_doctor(self, doctor_id: str, password: str) -> Tuple[bool, str, Optional[DoctorUser]]:
        """Login doctor user"""
        if not doctor_id:
            return False, "Doctor ID required", None
        
        if not password:
            return False, "Password required for doctor", None
        
        doctor_user = await self._get_doctor_user(doctor_id)
        if not doctor_user:
            return False, "Doctor not found", None
        
        if not self._verify_password(password, doctor_user.password_hash):
            return False, "Invalid doctor password", None
        
        # Load doctor's patients
        doctor_user.patients = await self._get_doctor_patients(doctor_id)
        
        # Update last login
        await self._update_last_login(doctor_user.user_id)
        doctor_user.last_login = datetime.now()
        
        self.current_user = doctor_user
        self.session_token = str(uuid.uuid4())
        
        logger.info(f"Doctor {doctor_id} logged in successfully")
        return True, f"Doctor login successful. You have {len(doctor_user.patients)} patients.", doctor_user
    
    async def _login_patient(self, patient_id: str) -> Tuple[bool, str, Optional[PatientUser]]:
        """Login patient user (no password required)"""
        if not patient_id:
            return False, "Patient ID required", None
        
        patient_user = await self._get_patient_user(patient_id)
        if not patient_user:
            return False, "Patient not found", None
        
        # Update last login
        await self._update_last_login(patient_user.user_id)
        patient_user.last_login = datetime.now()
        
        self.current_user = patient_user
        self.session_token = str(uuid.uuid4())
        
        logger.info(f"Patient {patient_id} logged in successfully")
        return True, "Patient login successful", patient_user
    
    async def register_doctor(self, name: str, age: int, password: str, 
                            specialty: str = "Neurology", license_number: str = None) -> Tuple[bool, str, str]:
        """
        Register new doctor
        
        Returns: (success, message, doctor_id)
        """
        try:
            # Generate unique doctor ID
            doctor_id = f"DR_{datetime.now().strftime('%Y%m%d')}_{str(uuid.uuid4())[:8].upper()}"
            user_id = f"doctor_{doctor_id}"
            
            # Check if doctor with same name exists
            existing = await self._user_exists(name, UserRole.DOCTOR)
            if existing:
                return False, "Doctor with this name already exists", ""
            
            # Create doctor user
            doctor_user = DoctorUser(
                user_id=user_id,
                role=UserRole.DOCTOR,
                name=name,
                created_at=datetime.now(),
                doctor_id=doctor_id,
                password_hash=self._hash_password(password),
                age=age,
                specialty=specialty,
                license_number=license_number
            )
            
            await self._store_doctor_user(doctor_user)
            
            logger.info(f"New doctor registered: {doctor_id}")
            return True, f"Doctor registered successfully. Your Doctor ID is: {doctor_id}", doctor_id
            
        except Exception as e:
            logger.error(f"Doctor registration error: {e}")
            return False, f"Registration failed: {str(e)}", ""
    
    async def register_patient(self, name: str, age: int, doctor_id: str = None) -> Tuple[bool, str, str]:
        """
        Register new patient
        
        Returns: (success, message, patient_id)
        """
        try:
            # Generate unique patient ID
            patient_id = f"PT_{datetime.now().strftime('%Y%m%d')}_{str(uuid.uuid4())[:8].upper()}"
            user_id = f"patient_{patient_id}"
            
            # Verify doctor exists if provided
            if doctor_id:
                doctor_exists = await self._get_doctor_user(doctor_id)
                if not doctor_exists:
                    return False, "Assigned doctor not found", ""
            
            # Create patient user
            patient_user = PatientUser(
                user_id=user_id,
                role=UserRole.PATIENT,
                name=name,
                created_at=datetime.now(),
                patient_id=patient_id,
                age=age,
                doctor_id=doctor_id
            )
            
            await self._store_patient_user(patient_user)
            
            # Assign to doctor if provided
            if doctor_id:
                await self._assign_patient_to_doctor(doctor_id, patient_id)
            
            logger.info(f"New patient registered: {patient_id}")
            return True, f"Patient registered successfully. Your Patient ID is: {patient_id}", patient_id
            
        except Exception as e:
            logger.error(f"Patient registration error: {e}")
            return False, f"Registration failed: {str(e)}", ""
    
    # Database operations
    async def _user_exists(self, identifier: str, role: UserRole) -> bool:
        """Check if user exists"""
        async with self.db_manager.get_connection() as conn:
            if role == UserRole.ADMIN:
                query = "SELECT 1 FROM users WHERE role = 'admin' AND name = ?"
                result = await conn.execute(query, (identifier,))
            elif role == UserRole.DOCTOR:
                query = "SELECT 1 FROM users u JOIN doctors d ON u.user_id = d.user_id WHERE u.name = ?"
                result = await conn.execute(query, (identifier,))
            elif role == UserRole.PATIENT:
                query = "SELECT 1 FROM users u JOIN patients p ON u.user_id = p.user_id WHERE u.name = ?"
                result = await conn.execute(query, (identifier,))
            
            row = await result.fetchone()
            return row is not None
    
    async def _get_admin_user(self) -> Optional[AdminUser]:
        """Get admin user"""
        async with self.db_manager.get_connection() as conn:
            query = """
            SELECT u.user_id, u.name, u.created_at, u.last_login, a.password_hash
            FROM users u JOIN admins a ON u.user_id = a.user_id
            WHERE u.role = 'admin'
            """
            result = await conn.execute(query)
            row = await result.fetchone()
            
            if row:
                return AdminUser(
                    user_id=row[0],
                    role=UserRole.ADMIN,
                    name=row[1],
                    created_at=datetime.fromisoformat(row[2]),
                    last_login=datetime.fromisoformat(row[3]) if row[3] else None,
                    password_hash=row[4]
                )
            return None
    
    async def _get_doctor_user(self, doctor_id: str) -> Optional[DoctorUser]:
        """Get doctor user by doctor ID"""
        async with self.db_manager.get_connection() as conn:
            query = """
            SELECT u.user_id, u.name, u.created_at, u.last_login, 
                   d.doctor_id, d.password_hash, d.age, d.specialty, d.license_number
            FROM users u JOIN doctors d ON u.user_id = d.user_id
            WHERE d.doctor_id = ? AND u.active = 1
            """
            result = await conn.execute(query, (doctor_id,))
            row = await result.fetchone()
            
            if row:
                return DoctorUser(
                    user_id=row[0],
                    role=UserRole.DOCTOR,
                    name=row[1],
                    created_at=datetime.fromisoformat(row[2]),
                    last_login=datetime.fromisoformat(row[3]) if row[3] else None,
                    doctor_id=row[4],
                    password_hash=row[5],
                    age=row[6],
                    specialty=row[7],
                    license_number=row[8]
                )
            return None
    
    async def _get_patient_user(self, patient_id: str) -> Optional[PatientUser]:
        """Get patient user by patient ID"""
        async with self.db_manager.get_connection() as conn:
            query = """
            SELECT u.user_id, u.name, u.created_at, u.last_login,
                   p.patient_id, p.age, p.doctor_id, p.medical_history
            FROM users u JOIN patients p ON u.user_id = p.user_id
            WHERE p.patient_id = ? AND u.active = 1
            """
            result = await conn.execute(query, (patient_id,))
            row = await result.fetchone()
            
            if row:
                import json
                medical_history = {}
                if row[7]:
                    try:
                        medical_history = json.loads(row[7])
                    except:
                        pass
                
                return PatientUser(
                    user_id=row[0],
                    role=UserRole.PATIENT,
                    name=row[1],
                    created_at=datetime.fromisoformat(row[2]),
                    last_login=datetime.fromisoformat(row[3]) if row[3] else None,
                    patient_id=row[4],
                    age=row[5],
                    doctor_id=row[6],
                    medical_history=medical_history
                )
            return None
    
    async def _store_admin_user(self, admin_user: AdminUser):
        """Store admin user in database"""
        async with self.db_manager.get_connection() as conn:
            # Insert into users table
            await conn.execute("""
                INSERT INTO users (user_id, role, name, created_at, active)
                VALUES (?, ?, ?, ?, ?)
            """, (admin_user.user_id, admin_user.role.value, admin_user.name, 
                  admin_user.created_at.isoformat(), admin_user.active))
            
            # Insert into admins table
            await conn.execute("""
                INSERT INTO admins (user_id, password_hash)
                VALUES (?, ?)
            """, (admin_user.user_id, admin_user.password_hash))
            
            await conn.commit()
    
    async def _store_doctor_user(self, doctor_user: DoctorUser):
        """Store doctor user in database"""
        async with self.db_manager.get_connection() as conn:
            # Insert into users table
            await conn.execute("""
                INSERT INTO users (user_id, role, name, created_at, active)
                VALUES (?, ?, ?, ?, ?)
            """, (doctor_user.user_id, doctor_user.role.value, doctor_user.name,
                  doctor_user.created_at.isoformat(), doctor_user.active))
            
            # Insert into doctors table
            await conn.execute("""
                INSERT INTO doctors (user_id, doctor_id, password_hash, age, specialty, license_number)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (doctor_user.user_id, doctor_user.doctor_id, doctor_user.password_hash,
                  doctor_user.age, doctor_user.specialty, doctor_user.license_number))
            
            await conn.commit()
    
    async def _store_patient_user(self, patient_user: PatientUser):
        """Store patient user in database"""
        import json
        
        async with self.db_manager.get_connection() as conn:
            # Insert into users table
            await conn.execute("""
                INSERT INTO users (user_id, role, name, created_at, active)
                VALUES (?, ?, ?, ?, ?)
            """, (patient_user.user_id, patient_user.role.value, patient_user.name,
                  patient_user.created_at.isoformat(), patient_user.active))
            
            # Insert into patients table
            await conn.execute("""
                INSERT INTO patients (user_id, patient_id, age, doctor_id, medical_history)
                VALUES (?, ?, ?, ?, ?)
            """, (patient_user.user_id, patient_user.patient_id, patient_user.age,
                  patient_user.doctor_id, json.dumps(patient_user.medical_history)))
            
            await conn.commit()
    
    async def _get_doctor_patients(self, doctor_id: str) -> List[str]:
        """Get list of patient IDs assigned to doctor"""
        async with self.db_manager.get_connection() as conn:
            query = "SELECT patient_id FROM doctor_patients WHERE doctor_id = ?"
            result = await conn.execute(query, (doctor_id,))
            rows = await result.fetchall()
            return [row[0] for row in rows]
    
    async def _assign_patient_to_doctor(self, doctor_id: str, patient_id: str):
        """Assign patient to doctor"""
        async with self.db_manager.get_connection() as conn:
            await conn.execute("""
                INSERT OR IGNORE INTO doctor_patients (doctor_id, patient_id, assigned_at)
                VALUES (?, ?, ?)
            """, (doctor_id, patient_id, datetime.now().isoformat()))
            await conn.commit()
    
    async def _update_last_login(self, user_id: str):
        """Update user's last login time"""
        async with self.db_manager.get_connection() as conn:
            await conn.execute("""
                UPDATE users SET last_login = ? WHERE user_id = ?
            """, (datetime.now().isoformat(), user_id))
            await conn.commit()
    
    def logout(self):
        """Logout current user"""
        if self.current_user:
            logger.info(f"User {self.current_user.name} logged out")
        self.current_user = None
        self.session_token = None
    
    def is_authenticated(self) -> bool:
        """Check if user is authenticated"""
        return self.current_user is not None
    
    def has_permission(self, action: str, resource: str = None) -> bool:
        """Check if current user has permission for action"""
        if not self.current_user:
            return False
        
        if self.current_user.role == UserRole.ADMIN:
            return True  # Admin has all permissions
        
        elif self.current_user.role == UserRole.DOCTOR:
            if action in ['view_patient', 'create_report', 'view_report']:
                # Doctor can only access their own patients
                if resource and hasattr(self.current_user, 'patients'):
                    return resource in self.current_user.patients
                return True  # Allow if no specific resource
            elif action in ['register_patient']:
                return True
            return False
        
        elif self.current_user.role == UserRole.PATIENT:
            if action in ['view_report']:
                # Patient can only view their own reports
                if resource:
                    return resource == self.current_user.patient_id
                return True
            return False
        
        return False
    
    def get_current_user(self) -> Optional[User]:
        """Get currently logged in user"""
        return self.current_user