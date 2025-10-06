"""
Enhanced Authentication and Authorization System

This module implements role-based access control (RBAC) with proper database integration.
Supports three user roles: Admin, Doctor, Patient with different authentication flows.

Authentication Flow:
1. First input must be role: 'admin', 'doctor', 'patient'
2. Admin: username + password (default: admin/Admin123)
3. Doctor: doctor_id, if exists request password, if not create new doctor
4. Patient: patient_id, if exists retrieve profile, if not create new patient

RBAC Rules:
- Admin: full CRUD on all users, reports, scans
- Doctor: only see patients assigned to them, their own reports
- Patient: only see their own reports + scans
"""

import asyncio
import bcrypt
import logging
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union, Any
from dataclasses import dataclass

from core.database import DatabaseManager
from utils.file_manager import ensure_patient_structure, ensure_doctor_structure

logger = logging.getLogger(__name__)

class UserRole(Enum):
    """User roles in the system."""
    ADMIN = "admin"
    DOCTOR = "doctor" 
    PATIENT = "patient"

@dataclass
class AuthUser:
    """Authenticated user information."""
    id: str
    username: str
    name: str
    role: UserRole
    email: Optional[str] = None
    specialization: Optional[str] = None  # For doctors
    age: Optional[int] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None

class AuthenticationManager:
    """Enhanced authentication manager with proper database integration."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.DEFAULT_ADMIN_PASSWORD = "Admin123"
        
    async def initialize(self):
        """Initialize authentication system with default admin."""
        await self._create_default_admin()
        logger.info("Authentication system initialized")
        
    async def _create_default_admin(self):
        """Create default admin user if not exists."""
        try:
            # Check if admin exists
            async with self.db_manager.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT id FROM users WHERE username = ? AND role = ?
                """, ("admin", UserRole.ADMIN.value))
                
                existing_admin = await cursor.fetchone()
                
                if not existing_admin:
                    # Create default admin
                    admin_id = str(uuid.uuid4())
                    password_hash = bcrypt.hashpw(
                        self.DEFAULT_ADMIN_PASSWORD.encode('utf-8'), 
                        bcrypt.gensalt()
                    ).decode('utf-8')
                    
                    await conn.execute("""
                        INSERT INTO users 
                        (id, username, email, password_hash, name, role, is_active, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        admin_id,
                        "admin",
                        "admin@parkinsons.system",
                        password_hash,
                        "System Administrator",
                        UserRole.ADMIN.value,
                        True,
                        datetime.now().isoformat()
                    ))
                    
                    await conn.commit()
                    logger.info(f"Created default admin user with ID: {admin_id}")
                else:
                    logger.info("Default admin user already exists")
                    
        except Exception as e:
            logger.error(f"Error creating default admin: {e}")
            raise
            
    async def authenticate_admin(self, username: str, password: str) -> Tuple[bool, str, Optional[AuthUser]]:
        """
        Authenticate admin user with username and password.
        
        Args:
            username: Admin username
            password: Admin password
            
        Returns:
            Tuple of (success, message, user_data)
        """
        try:
            async with self.db_manager.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT id, username, email, password_hash, name, is_active, created_at, last_login
                    FROM users 
                    WHERE username = ? AND role = ?
                """, (username, UserRole.ADMIN.value))
                
                user_row = await cursor.fetchone()
                
                if not user_row:
                    return False, "Invalid credentials", None
                    
                # Check if user is active
                if not user_row[5]:  # is_active
                    return False, "Account is disabled", None
                
                # Verify password
                stored_hash = user_row[3].encode('utf-8')
                if not bcrypt.checkpw(password.encode('utf-8'), stored_hash):
                    return False, "Invalid credentials", None
                
                # Update last login
                await conn.execute("""
                    UPDATE users SET last_login = ? WHERE id = ?
                """, (datetime.now().isoformat(), user_row[0]))
                await conn.commit()
                
                # Create AuthUser object
                auth_user = AuthUser(
                    id=user_row[0],
                    username=user_row[1],
                    name=user_row[4],
                    role=UserRole.ADMIN,
                    email=user_row[2],
                    is_active=user_row[5],
                    created_at=datetime.fromisoformat(user_row[6]) if user_row[6] else None,
                    last_login=datetime.fromisoformat(user_row[7]) if user_row[7] else None
                )
                
                await self._log_audit("admin_login", user_row[0], UserRole.ADMIN.value, 
                                    None, {"username": username}, True)
                
                return True, "Authentication successful", auth_user
                
        except Exception as e:
            logger.error(f"Error authenticating admin: {e}")
            await self._log_audit("admin_login", "", UserRole.ADMIN.value, 
                                None, {"username": username, "error": str(e)}, False)
            return False, "Authentication error", None
            
    async def authenticate_doctor(self, doctor_id: str, password: Optional[str] = None) -> Tuple[bool, str, Optional[AuthUser]]:
        """
        Authenticate doctor by doctor_id. If doctor doesn't exist, returns info for registration.
        
        Args:
            doctor_id: Unique doctor identifier
            password: Password for existing doctors
            
        Returns:
            Tuple of (success, message, user_data)
        """
        try:
            async with self.db_manager.get_connection() as conn:
                # Check if doctor exists
                cursor = await conn.execute("""
                    SELECT u.id, u.username, u.email, u.password_hash, u.name, 
                           u.specialization, u.age, u.is_active, u.created_at, u.last_login,
                           d.doctor_id, d.license_number
                    FROM users u
                    JOIN doctors d ON u.id = d.user_id
                    WHERE d.doctor_id = ? AND u.role = ?
                """, (doctor_id, UserRole.DOCTOR.value))
                
                doctor_row = await cursor.fetchone()
                
                if not doctor_row:
                    return False, "DOCTOR_NOT_FOUND", None
                    
                # Check if account is active
                if not doctor_row[7]:  # is_active
                    return False, "Account is disabled", None
                
                # If no password provided, this is just checking existence
                if password is None:
                    return False, "PASSWORD_REQUIRED", None
                
                # Verify password
                stored_hash = doctor_row[3].encode('utf-8')
                if not bcrypt.checkpw(password.encode('utf-8'), stored_hash):
                    return False, "Invalid password", None
                
                # Update last login
                await conn.execute("""
                    UPDATE users SET last_login = ? WHERE id = ?
                """, (datetime.now().isoformat(), doctor_row[0]))
                await conn.commit()
                
                # Create AuthUser object
                auth_user = AuthUser(
                    id=doctor_row[0],
                    username=doctor_row[1] or doctor_id,
                    name=doctor_row[4],
                    role=UserRole.DOCTOR,
                    email=doctor_row[2],
                    specialization=doctor_row[5],
                    age=doctor_row[6],
                    is_active=doctor_row[7],
                    created_at=datetime.fromisoformat(doctor_row[8]) if doctor_row[8] else None,
                    last_login=datetime.fromisoformat(doctor_row[9]) if doctor_row[9] else None
                )
                
                await self._log_audit("doctor_login", doctor_row[0], UserRole.DOCTOR.value,
                                    None, {"doctor_id": doctor_id}, True)
                
                return True, "Authentication successful", auth_user
                
        except Exception as e:
            logger.error(f"Error authenticating doctor: {e}")
            await self._log_audit("doctor_login", "", UserRole.DOCTOR.value,
                                None, {"doctor_id": doctor_id, "error": str(e)}, False)
            return False, "Authentication error", None
            
    async def authenticate_patient(self, patient_id: str) -> Tuple[bool, str, Optional[AuthUser]]:
        """
        Authenticate patient by patient_id. If patient doesn't exist, returns info for registration.
        
        Args:
            patient_id: Unique patient identifier
            
        Returns:
            Tuple of (success, message, user_data)
        """
        try:
            async with self.db_manager.get_connection() as conn:
                # Check if patient exists
                cursor = await conn.execute("""
                    SELECT u.id, u.username, u.email, u.name, u.age, u.gender,
                           u.is_active, u.created_at, u.last_login,
                           p.patient_id, p.assigned_doctor_id
                    FROM users u
                    LEFT JOIN patients p ON u.id = p.user_id
                    WHERE p.patient_id = ? AND u.role = ?
                """, (patient_id, UserRole.PATIENT.value))
                
                patient_row = await cursor.fetchone()
                
                if not patient_row:
                    return False, "PATIENT_NOT_FOUND", None
                    
                # Check if account is active
                if not patient_row[6]:  # is_active
                    return False, "Account is disabled", None
                
                # Update last login (no password required for patients)
                await conn.execute("""
                    UPDATE users SET last_login = ? WHERE id = ?
                """, (datetime.now().isoformat(), patient_row[0]))
                await conn.commit()
                
                # Create AuthUser object
                auth_user = AuthUser(
                    id=patient_row[0],
                    username=patient_row[1] or patient_id,
                    name=patient_row[3],
                    role=UserRole.PATIENT,
                    email=patient_row[2],
                    age=patient_row[4],
                    is_active=patient_row[6],
                    created_at=datetime.fromisoformat(patient_row[7]) if patient_row[7] else None,
                    last_login=datetime.fromisoformat(patient_row[8]) if patient_row[8] else None
                )
                
                await self._log_audit("patient_login", patient_row[0], UserRole.PATIENT.value,
                                    None, {"patient_id": patient_id}, True)
                
                return True, "Authentication successful", auth_user
                
        except Exception as e:
            logger.error(f"Error authenticating patient: {e}")
            await self._log_audit("patient_login", "", UserRole.PATIENT.value,
                                None, {"patient_id": patient_id, "error": str(e)}, False)
            return False, "Authentication error", None
            
    async def register_doctor(self, doctor_id: str, name: str, password: str,
                            age: Optional[int] = None, specialization: Optional[str] = None,
                            license_number: Optional[str] = None, 
                            email: Optional[str] = None) -> Tuple[bool, str, Optional[AuthUser]]:
        """
        Register a new doctor in the system.
        
        Args:
            doctor_id: Unique doctor identifier
            name: Full name
            password: Password for the account
            age: Doctor's age
            specialization: Medical specialization
            license_number: Medical license number
            email: Email address
            
        Returns:
            Tuple of (success, message, user_data)
        """
        try:
            async with self.db_manager.get_connection() as conn:
                # Check if doctor_id already exists
                cursor = await conn.execute("""
                    SELECT doctor_id FROM doctors WHERE doctor_id = ?
                """, (doctor_id,))
                
                if await cursor.fetchone():
                    return False, "Doctor ID already exists", None
                
                # Create user account
                user_id = str(uuid.uuid4())
                password_hash = bcrypt.hashpw(
                    password.encode('utf-8'), 
                    bcrypt.gensalt()
                ).decode('utf-8')
                
                # Insert into users table
                await conn.execute("""
                    INSERT INTO users 
                    (id, username, email, password_hash, name, role, age, specialization, is_active, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id,
                    doctor_id,  # Use doctor_id as username
                    email,
                    password_hash,
                    name,
                    UserRole.DOCTOR.value,
                    age,
                    specialization,
                    True,
                    datetime.now().isoformat()
                ))
                
                # Insert into doctors table
                await conn.execute("""
                    INSERT INTO doctors 
                    (doctor_id, user_id, specialization, license_number, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    doctor_id,
                    user_id,
                    specialization,
                    license_number,
                    datetime.now().isoformat()
                ))
                
                await conn.commit()
                
                # Create doctor directory structure
                ensure_doctor_structure(doctor_id)
                
                # Create AuthUser object
                auth_user = AuthUser(
                    id=user_id,
                    username=doctor_id,
                    name=name,
                    role=UserRole.DOCTOR,
                    email=email,
                    specialization=specialization,
                    age=age,
                    is_active=True,
                    created_at=datetime.now()
                )
                
                await self._log_audit("doctor_registered", user_id, UserRole.DOCTOR.value,
                                    None, {"doctor_id": doctor_id, "name": name}, True)
                
                logger.info(f"Registered new doctor: {doctor_id} ({name})")
                return True, "Doctor registered successfully", auth_user
                
        except Exception as e:
            logger.error(f"Error registering doctor: {e}")
            await self._log_audit("doctor_registration_failed", "", UserRole.DOCTOR.value,
                                None, {"doctor_id": doctor_id, "error": str(e)}, False)
            return False, "Registration failed", None
            
    async def register_patient(self, patient_id: str, name: str, age: Optional[int] = None,
                             gender: Optional[str] = None, email: Optional[str] = None,
                             assigned_doctor_id: Optional[str] = None) -> Tuple[bool, str, Optional[AuthUser]]:
        """
        Register a new patient in the system.
        
        Args:
            patient_id: Unique patient identifier
            name: Full name
            age: Patient's age
            gender: Patient's gender
            email: Email address
            assigned_doctor_id: ID of assigned doctor
            
        Returns:
            Tuple of (success, message, user_data)
        """
        try:
            async with self.db_manager.get_connection() as conn:
                # Check if patient_id already exists
                cursor = await conn.execute("""
                    SELECT patient_id FROM patients WHERE patient_id = ?
                """, (patient_id,))
                
                if await cursor.fetchone():
                    return False, "Patient ID already exists", None
                
                # Create user account (no password for patients)
                user_id = str(uuid.uuid4())
                
                # Insert into users table
                await conn.execute("""
                    INSERT INTO users 
                    (id, username, email, name, role, age, gender, is_active, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id,
                    patient_id,  # Use patient_id as username
                    email,
                    name,
                    UserRole.PATIENT.value,
                    age,
                    gender,
                    True,
                    datetime.now().isoformat()
                ))
                
                # Insert into patients table
                await conn.execute("""
                    INSERT INTO patients 
                    (patient_id, user_id, name, age, gender, assigned_doctor_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    patient_id,
                    user_id,
                    name,
                    age,
                    gender,
                    assigned_doctor_id,
                    datetime.now().isoformat()
                ))
                
                await conn.commit()
                
                # Create patient directory structure
                ensure_patient_structure(patient_id)
                
                # Create AuthUser object
                auth_user = AuthUser(
                    id=user_id,
                    username=patient_id,
                    name=name,
                    role=UserRole.PATIENT,
                    email=email,
                    age=age,
                    is_active=True,
                    created_at=datetime.now()
                )
                
                await self._log_audit("patient_registered", user_id, UserRole.PATIENT.value,
                                    None, {"patient_id": patient_id, "name": name}, True)
                
                logger.info(f"Registered new patient: {patient_id} ({name})")
                return True, "Patient registered successfully", auth_user
                
        except Exception as e:
            logger.error(f"Error registering patient: {e}")
            await self._log_audit("patient_registration_failed", "", UserRole.PATIENT.value,
                                None, {"patient_id": patient_id, "error": str(e)}, False)
            return False, "Registration failed", None
            
    async def check_permissions(self, user: AuthUser, action: str, 
                              target_id: Optional[str] = None, 
                              target_type: Optional[str] = None) -> bool:
        """
        Check if user has permission to perform an action.
        
        Args:
            user: Authenticated user
            action: Action to perform (e.g., 'read_report', 'create_report')
            target_id: ID of target resource
            target_type: Type of target resource
            
        Returns:
            True if permission granted, False otherwise
        """
        try:
            # Admin has all permissions
            if user.role == UserRole.ADMIN:
                return True
                
            # Doctor permissions
            if user.role == UserRole.DOCTOR:
                if action in ['read_report', 'create_report', 'update_report']:
                    # Doctors can only access reports for their assigned patients
                    if target_type == 'report' and target_id:
                        return await self._check_doctor_patient_assignment(user.id, target_id)
                    return True  # Allow general report operations
                    
                elif action in ['read_patient', 'update_patient']:
                    # Doctors can only access their assigned patients
                    if target_id:
                        return await self._check_doctor_patient_assignment(user.id, target_id)
                        
                return action in ['read_own_profile', 'update_own_profile']
                
            # Patient permissions
            if user.role == UserRole.PATIENT:
                if action in ['read_report', 'read_scan']:
                    # Patients can only access their own resources
                    if target_id:
                        return await self._check_patient_ownership(user.id, target_id, target_type)
                        
                return action in ['read_own_profile', 'update_own_profile']
                
            return False
            
        except Exception as e:
            logger.error(f"Error checking permissions: {e}")
            return False
            
    async def _check_doctor_patient_assignment(self, doctor_user_id: str, 
                                             patient_id: str) -> bool:
        """Check if a doctor is assigned to a patient."""
        try:
            async with self.db_manager.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT p.patient_id
                    FROM patients p
                    JOIN doctors d ON p.assigned_doctor_id = d.doctor_id
                    WHERE d.user_id = ? AND p.patient_id = ?
                """, (doctor_user_id, patient_id))
                
                return await cursor.fetchone() is not None
                
        except Exception as e:
            logger.error(f"Error checking doctor-patient assignment: {e}")
            return False
            
    async def _check_patient_ownership(self, patient_user_id: str, 
                                     resource_id: str, resource_type: str) -> bool:
        """Check if a patient owns a resource."""
        try:
            async with self.db_manager.get_connection() as conn:
                if resource_type == 'report':
                    # Use medical_reports table (new table) instead of deprecated reports table
                    cursor = await conn.execute("""
                        SELECT mr.id
                        FROM medical_reports mr
                        JOIN sessions s ON mr.session_id = s.id
                        JOIN patients p ON s.patient_id = p.patient_id
                        WHERE p.user_id = ? AND mr.id = ?
                    """, (patient_user_id, resource_id))
                    
                elif resource_type == 'scan':
                    cursor = await conn.execute("""
                        SELECT s.id
                        FROM mri_scans s
                        JOIN patients p ON s.patient_id = p.patient_id
                        WHERE p.user_id = ? AND s.id = ?
                    """, (patient_user_id, resource_id))
                    
                else:
                    return False
                    
                return await cursor.fetchone() is not None
                
        except Exception as e:
            logger.error(f"Error checking patient ownership: {e}")
            return False
            
    async def _log_audit(self, action: str, actor_id: str, actor_role: str,
                        target_id: Optional[str], details: Dict, 
                        success: bool, error_message: Optional[str] = None):
        """Log an audit event."""
        try:
            async with self.db_manager.get_connection() as conn:
                log_id = str(uuid.uuid4())
                
                await conn.execute("""
                    INSERT INTO audit_logs 
                    (log_id, action, actor_id, actor_role, target_id, details, 
                     success, error_message, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    log_id,
                    action,
                    actor_id or "anonymous",
                    actor_role,
                    target_id,
                    str(details),  # Convert dict to string for now
                    success,
                    error_message,
                    datetime.now().isoformat()
                ))
                
                await conn.commit()
                
        except Exception as e:
            logger.error(f"Error logging audit event: {e}")
            
    async def get_user_by_id(self, user_id: str) -> Optional[AuthUser]:
        """Get user information by ID."""
        try:
            async with self.db_manager.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT id, username, email, name, role, age, specialization,
                           is_active, created_at, last_login
                    FROM users 
                    WHERE id = ?
                """, (user_id,))
                
                user_row = await cursor.fetchone()
                
                if not user_row:
                    return None
                    
                return AuthUser(
                    id=user_row[0],
                    username=user_row[1],
                    name=user_row[3],
                    role=UserRole(user_row[4]),
                    email=user_row[2],
                    age=user_row[5],
                    specialization=user_row[6],
                    is_active=user_row[7],
                    created_at=datetime.fromisoformat(user_row[8]) if user_row[8] else None,
                    last_login=datetime.fromisoformat(user_row[9]) if user_row[9] else None
                )
                
        except Exception as e:
            logger.error(f"Error getting user by ID: {e}")
            return None
    
    async def start_authentication_flow(self) -> Dict[str, Any]:
        """Main authentication entry point - interactive flow"""
        print("\n=== PARKINSON'S MULTIAGENT SYSTEM ===")
        print("Please specify your role:")
        print("1. admin")
        print("2. doctor") 
        print("3. patient")
        
        while True:
            role_choice = input("\nEnter your role (admin/doctor/patient): ").strip().lower()
            
            if role_choice == "admin":
                return await self.handle_admin_auth()
            elif role_choice == "doctor":
                return await self.handle_doctor_auth()
            elif role_choice == "patient":
                return await self.handle_patient_auth()
            else:
                print("❌ Invalid role. Please enter: admin, doctor, or patient")
    
    async def handle_admin_auth(self) -> Dict[str, Any]:
        """Handle admin authentication interactively"""
        print("\n--- ADMIN LOGIN ---")
        
        username = input("Username: ").strip()
        password = input("Password: ").strip()
        
        success, error_message, user = await self.authenticate_admin(username, password)
        
        if success:
            print(f"✅ Welcome, {user.name}!")
            print("🔑 Admin privileges: Full system access")
            
            return {
                "success": True,
                "user": {
                    'id': user.id,
                    'username': user.username,
                    'name': user.name,
                    'role': user.role.value
                },
                "role": user.role.value,
                "permissions": ['full_crud', 'all_users', 'all_reports', 'all_scans', 'delete_users']
            }
        else:
            print(f"❌ {error_message}")
            return {"success": False, "message": error_message}
    
    async def handle_doctor_auth(self) -> Dict[str, Any]:
        """Handle doctor authentication interactively"""
        print("\n--- DOCTOR ACCESS ---")
        
        doctor_id = input("Enter your Doctor ID: ").strip()
        
        # Validate doctor_id is not empty
        if not doctor_id:
            print("❌ Doctor ID cannot be empty")
            print("To create a new doctor profile, you'll be prompted to choose an ID.")
            create_new = input("Create new doctor profile? (y/n): ").strip().lower()
            if create_new == 'y':
                return await self._create_new_doctor("")
            else:
                return {"success": False, "message": "Doctor ID required"}
        
        # Check if doctor exists
        async with self.db_manager.get_connection() as conn:
            cursor = await conn.execute("""
                SELECT d.doctor_id, d.user_id, u.name, u.password_hash, u.specialization, d.license_number
                FROM doctors d
                JOIN users u ON d.user_id = u.id  
                WHERE d.doctor_id = ? AND u.is_active = 1
            """, (doctor_id,))
            
            doctor = await cursor.fetchone()
            
            if doctor:
                # Doctor exists, ask for password
                print(f"Doctor found: {doctor[2]}")
                password = input("Enter your password: ").strip()
                
                if bcrypt.checkpw(password.encode('utf-8'), doctor[3].encode('utf-8')):
                    # Get assigned patients
                    cursor = await conn.execute("""
                        SELECT patient_id, name FROM patients 
                        WHERE assigned_doctor_id = ?
                    """, (doctor_id,))
                    
                    assigned_patients = await cursor.fetchall()
                    
                    user_data = {
                        'id': doctor[1],
                        'doctor_id': doctor[0],
                        'name': doctor[2],
                        'role': 'doctor',
                        'specialization': doctor[4],
                        'license_number': doctor[5],
                        'assigned_patients': [{'patient_id': p[0], 'name': p[1]} for p in assigned_patients]
                    }
                    
                    print(f"✅ Welcome Dr. {doctor[2]}!")
                    print(f"🔑 Doctor privileges: {len(assigned_patients)} assigned patients")
                    
                    await self._update_last_login(doctor[1])
                    
                    return {
                        "success": True,
                        "user": user_data,
                        "role": 'doctor',
                        "permissions": ['view_assigned_patients', 'create_reports', 'view_own_reports']
                    }
                else:
                    print("❌ Invalid password")
                    return {"success": False, "message": "Invalid password"}
            else:
                # Doctor doesn't exist, create new profile
                return await self._create_new_doctor(doctor_id)
    
    async def handle_patient_auth(self) -> Dict[str, Any]:
        """Handle patient authentication interactively"""
        print("\n--- PATIENT ACCESS ---")
        
        patient_id = input("Enter your Patient ID: ").strip()
        
        async with self.db_manager.get_connection() as conn:
            # Check if patient exists
            cursor = await conn.execute("""
                SELECT p.patient_id, p.user_id, p.name, p.age, p.gender, 
                       p.assigned_doctor_id, d.doctor_id, u_doc.name as doctor_name
                FROM patients p
                LEFT JOIN doctors d ON p.assigned_doctor_id = d.doctor_id
                LEFT JOIN users u_doc ON d.user_id = u_doc.id
                WHERE p.patient_id = ?
            """, (patient_id,))
            
            patient = await cursor.fetchone()
            
            if patient:
                # Patient exists, load profile
                user_data = {
                    'id': patient[1] if patient[1] else f"patient_{patient[0]}",
                    'patient_id': patient[0],
                    'name': patient[2],
                    'role': 'patient',
                    'age': patient[3],
                    'gender': patient[4],
                    'assigned_doctor_id': patient[5],
                    'assigned_doctor_name': patient[7] if patient[7] else 'Not assigned'
                }
                
                print(f"✅ Welcome {patient[2]}!")
                print(f"🏥 Assigned Doctor: {patient[7] if patient[7] else 'Not assigned'}")
                
                return {
                    "success": True,
                    "user": user_data,
                    "role": 'patient',
                    "permissions": ['view_own_reports', 'view_own_scans']
                }
            else:
                # Patient doesn't exist, create new profile
                return await self._create_new_patient(patient_id)
    
    async def _create_new_doctor(self, doctor_id: str) -> Dict[str, Any]:
        """Create new doctor profile interactively"""
        print(f"\n--- CREATE NEW DOCTOR PROFILE ---")
        
        # Allow doctor to create their own ID if none provided
        if not doctor_id or doctor_id.strip() == '':
            print("Let's create your doctor profile.")
            doctor_id = input("Choose your Doctor ID: ").strip()
            
            if not doctor_id:
                print("❌ Doctor ID is required")
                return {"success": False, "message": "Doctor ID is required"}
        else:
            print(f"Doctor ID '{doctor_id}' not found. Let's create your profile.")
        
        # ADMIN AUTHENTICATION REQUIRED
        print("\n🔐 Admin authorization required to create doctor account")
        admin_username = input("Admin Username: ").strip()
        admin_password = input("Admin Password: ").strip()
        
        # Verify admin credentials
        try:
            async with self.db_manager.get_connection() as conn:
                # Check if doctor_id already exists
                cursor = await conn.execute("""
                    SELECT doctor_id FROM doctors WHERE doctor_id = ?
                """, (doctor_id,))
                
                if await cursor.fetchone():
                    print(f"❌ Doctor ID '{doctor_id}' already exists")
                    return {"success": False, "message": "Doctor ID already exists"}
                
                # Verify admin credentials
                cursor = await conn.execute("""
                    SELECT password_hash FROM users 
                    WHERE username = ? AND role = 'admin' AND is_active = 1
                """, (admin_username,))
                
                admin_row = await cursor.fetchone()
                
                if not admin_row:
                    print("❌ Admin account not found or inactive")
                    return {"success": False, "message": "Admin authentication failed"}
                
                # Verify password
                if not bcrypt.checkpw(admin_password.encode('utf-8'), admin_row[0].encode('utf-8')):
                    print("❌ Invalid admin password")
                    return {"success": False, "message": "Admin authentication failed"}
                
                print("✅ Admin authenticated successfully\n")
                
        except Exception as e:
            logger.error(f"Error verifying admin credentials: {e}")
            print(f"❌ Authentication error: {e}")
            return {"success": False, "message": "Authentication error"}
        
        # Proceed with doctor profile creation
        name = input("Full Name: ").strip()
        age = int(input("Age: ").strip())
        specialization = input("Specialization (e.g., Neurology): ").strip()
        license_number = input("Medical License Number: ").strip()
        email = input("Email: ").strip()
        phone = input("Phone: ").strip()
        
        # Set password
        password = input("Set your password: ").strip()
        password_confirm = input("Confirm password: ").strip()
        
        if password != password_confirm:
            print("❌ Passwords don't match")
            return {"success": False, "message": "Passwords don't match"}
        
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # Create user and doctor records
        user_id = f"user_{uuid.uuid4().hex[:8]}"
        
        try:
            async with self.db_manager.get_connection() as conn:
                # Create user record
                await conn.execute("""
                    INSERT INTO users (
                        id, username, email, password_hash, name, role, age, 
                        specialization, license_number, phone, is_active, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id, f"dr_{doctor_id}", email, password_hash, name, "doctor", 
                    age, specialization, license_number, phone, 1, 
                    datetime.now().isoformat(), datetime.now().isoformat()
                ))
                
                # Create doctor record
                await conn.execute("""
                    INSERT INTO doctors (
                        doctor_id, user_id, specialization, license_number, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    doctor_id, user_id, specialization, license_number,
                    datetime.now().isoformat(), datetime.now().isoformat()
                ))
                
                await conn.commit()
            
            user_data = {
                'id': user_id,
                'doctor_id': doctor_id,
                'name': name,
                'role': 'doctor',
                'specialization': specialization,
                'license_number': license_number,
                'assigned_patients': []
            }
            
            print(f"✅ Doctor profile created successfully!")
            print(f"🆔 Your Doctor ID: {doctor_id}")
            print(f"👨‍⚕️ Welcome Dr. {name}!")
            
            return {
                "success": True,
                "user": user_data,
                "role": 'doctor',
                "permissions": ['view_assigned_patients', 'create_reports', 'view_own_reports'],
                "new_doctor": True
            }
            
        except Exception as e:
            print(f"❌ Error creating doctor profile: {e}")
            return {"success": False, "message": f"Database error: {e}"}
    
    async def _create_new_patient(self, patient_id: str) -> Dict[str, Any]:
        """Create new patient profile interactively"""
        print(f"\n--- CREATE NEW PATIENT PROFILE ---")
        if not patient_id or patient_id.strip() == '':
            # Generate new patient ID if empty
            patient_id = f"PAT_{uuid.uuid4().hex[:8].upper()}"
            print(f"Generating new Patient ID: {patient_id}")
        else:
            print(f"Patient ID '{patient_id}' not found. Let's create your profile.")
        
        name = input("Full Name: ").strip()
        age = int(input("Age: ").strip())
        gender = input("Gender (male/female/other): ").strip().lower()
        
        # Optional fields
        medical_history = input("Medical History (optional): ").strip() or None
        emergency_contact_name = input("Emergency Contact Name (optional): ").strip() or None
        emergency_contact_phone = input("Emergency Contact Phone (optional): ").strip() or None
        allergies = input("Known Allergies (optional): ").strip() or None
        
        # Doctor assignment
        doctor_choice = input("\nHave you consulted with a doctor before? (y/n): ").strip().lower()
        assigned_doctor_id = None
        assigned_doctor_name = "Not assigned"
        
        if doctor_choice == 'y':
            doctor_id = input("Enter your Doctor's ID: ").strip()
            if doctor_id:
                # Verify doctor exists
                async with self.db_manager.get_connection() as conn:
                    cursor = await conn.execute("""
                        SELECT d.doctor_id, u.name 
                        FROM doctors d 
                        JOIN users u ON d.user_id = u.id 
                        WHERE d.doctor_id = ?
                    """, (doctor_id,))
                    doctor = await cursor.fetchone()
                    
                    if doctor:
                        assigned_doctor_id = doctor[0]
                        assigned_doctor_name = doctor[1]
                        print(f"✅ Doctor {doctor[1]} (ID: {doctor[0]}) will be assigned to you.")
                    else:
                        print(f"⚠️ Doctor ID '{doctor_id}' not found. You can assign a doctor later.")
        
        # Create patient record
        try:
            async with self.db_manager.get_connection() as conn:
                await conn.execute("""
                    INSERT INTO patients (
                        patient_id, name, age, gender, medical_history,
                        emergency_contact_name, emergency_contact_phone, 
                        allergies, assigned_doctor_id, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    patient_id, name, age, gender, medical_history,
                    emergency_contact_name, emergency_contact_phone,
                    allergies, assigned_doctor_id, datetime.now().isoformat(), datetime.now().isoformat()
                ))
                
                await conn.commit()
            
            user_data = {
                'id': f"patient_{patient_id}",
                'patient_id': patient_id,
                'name': name,
                'role': 'patient', 
                'age': age,
                'gender': gender,
                'medical_history': medical_history,
                'emergency_contact_name': emergency_contact_name,
                'emergency_contact_phone': emergency_contact_phone,
                'allergies': allergies,
                'assigned_doctor_id': assigned_doctor_id,
                'assigned_doctor_name': assigned_doctor_name
            }
            
            print(f"✅ Patient profile created successfully!")
            print(f"🆔 Your Patient ID: {patient_id}")
            print(f"👤 Welcome {name}!")
            print(f"🏥 Assigned Doctor: {assigned_doctor_name}")
            print("📋 You can now access your medical reports and scans.")
            
            return {
                "success": True,
                "user": user_data,
                "role": 'patient',
                "permissions": ['view_own_reports', 'view_own_scans'],
                "new_patient": True
            }
            
        except Exception as e:
            print(f"❌ Error creating patient profile: {e}")
            return {"success": False, "message": f"Database error: {e}"}
    
    async def _update_last_login(self, user_id: str):
        """Update last login timestamp"""
        async with self.db_manager.get_connection() as conn:
            await conn.execute("""
                UPDATE users SET last_login = ? WHERE id = ?
            """, (datetime.now().isoformat(), user_id))
            await conn.commit()