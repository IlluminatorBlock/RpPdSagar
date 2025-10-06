"""
Main entry point for Parkinson's Multiagent System

Comprehensive system with:
- Role-based authentication (admin/doctor/patient)
- File organization and automatic versioning
- RAG pipeline with embeddings (loaded from database initialization)
- Database with foreign key constraints
- Complete multiagent workflow
- Enhanced admin CRUD operations
- Proper report organization
"""

import asyncio
import logging
import logging.config
import signal
import sys
import uuid
from typing import Optional, Dict, Any
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config import config
from core.shared_memory import SharedMemoryInterface
from core.database import DatabaseManager
from services.groq_service import GroqService
from agents.supervisor_agent import SupervisorAgent
from agents.aiml_agent import AIMLAgent
from agents.rag_agent import RAGAgent
from services.mri_processor import MRIProcessor
# EmbeddingsManager is now handled by database initialization - no direct import needed

# Import new authentication and file management components  
from auth.authentication import AuthenticationManager
from utils.file_manager import FileManager
# Configure logging
logging.config.dictConfig(config.logging_config)
logger = logging.getLogger('parkinsons_system.main')


class ParkinsonsMultiagentSystem:
    """
    Main system orchestrator with integrated authentication and file management
    
    Features:
    - Role-based authentication (admin/doctor/patient)
    - Automatic file organization and versioning
    - RAG pipeline with embeddings
    - Complete multiagent workflow
    """
    
    def __init__(self):
        # Core components
        self.shared_memory: Optional[SharedMemoryInterface] = None
        self.database: Optional[DatabaseManager] = None
        self.groq_service: Optional[GroqService] = None
        self.mri_processor: Optional[MRIProcessor] = None
        # embeddings_manager will be retrieved from database after initialization
        
        # Authentication and file management
        self.auth_manager: Optional[AuthenticationManager] = None
        self.file_organizer: Optional[FileManager] = None
        
        # Agents
        self.supervisor_agent: Optional[SupervisorAgent] = None
        self.aiml_agent: Optional[AIMLAgent] = None
        self.rag_agent: Optional[RAGAgent] = None
        
        # System state
        self.is_running = False
        self.initialization_complete = False
        self.shutdown_requested = False
        
        # Current session information
        self.current_user: Optional[Dict[str, Any]] = None
        self.current_session: Optional[Dict[str, Any]] = None
    
    async def initialize(self):
        """Initialize all system components"""
        try:
            logger.info("Starting Parkinson's Multiagent System initialization...")
            
            # Initialize database
            logger.info("Initializing database...")
            db_config = config.database_config
            db_url = db_config['url']
            if db_url.startswith('sqlite:///'):
                db_path = db_url.replace('sqlite:///', '')
            else:
                db_path = db_url
            self.database = DatabaseManager(db_path)
            await self.database.init_database()
            
            # Initialize shared memory
            logger.info("Initializing shared memory...")
            self.shared_memory = SharedMemoryInterface(db_path)
            await self.shared_memory.initialize()
            
            # Initialize Groq service
            logger.info("Initializing Groq service...")
            groq_cfg = config.groq_config
            self.groq_service = GroqService(
                api_key=groq_cfg['api_key'],
                model=groq_cfg['model_chat']
            )
            await self.groq_service.initialize()
            
            # Initialize authentication system FIRST
            logger.info("Initializing authentication system...")
            self.auth_manager = AuthenticationManager(self.database)
            
            # Initialize file organizer
            logger.info("Initializing file organization system...")
            self.file_organizer = FileManager()
            
            # Initialize MRI processor
            logger.info("Initializing MRI processor...")
            self.mri_processor = MRIProcessor(config.mri_processor_config)
            
            # Initialize agents
            logger.info("Initializing agents...")
            await self._initialize_agents()
            
            # Start background tasks
            logger.info("Starting background tasks...")
            await self._start_background_tasks()
            
            self.initialization_complete = True
            logger.info("System initialization completed successfully!")
            
        except Exception as e:
            logger.error(f"System initialization failed: {e}")
            raise
    
    async def _initialize_agents(self):
        """Initialize all agent instances"""
        # Initialize Supervisor Agent
        self.supervisor_agent = SupervisorAgent(
            shared_memory=self.shared_memory,
            groq_service=self.groq_service,
            config=config.agent_config['supervisor']
        )
        await self.supervisor_agent.initialize()
        
        # Initialize AI/ML Agent
        self.aiml_agent = AIMLAgent(
            shared_memory=self.shared_memory,
            groq_service=self.groq_service,
            mri_processor=self.mri_processor,
            config=config.agent_config['aiml']
        )
        await self.aiml_agent.initialize()
        
        # Initialize RAG Agent - get embeddings manager from database
        embeddings_manager = self.database.get_embeddings_manager()
        if embeddings_manager is None:
            logger.warning("Embeddings manager not available - RAG agent will have limited functionality")
        else:
            logger.info("Embeddings manager retrieved from database for RAG agent")
        
        self.rag_agent = RAGAgent(
            shared_memory=self.shared_memory,
            groq_service=self.groq_service,
            embeddings_manager=embeddings_manager,
            config=config.agent_config['rag']
        )
        await self.rag_agent.initialize()
        
        logger.info("All agents initialized successfully")
    
    async def _start_background_tasks(self):
        """Start background monitoring and cleanup tasks"""
        # Background monitoring is now started automatically in agent initialize()
        # Just confirm monitoring is active for backward compatibility
        await self.aiml_agent.start_monitoring()
        await self.rag_agent.start_monitoring()
        
        # Start shared memory cleanup (kept separate as it's not part of agent lifecycle)
        await self.shared_memory.start_cleanup_task()
        
        logger.info("Background tasks confirmed/started")
    
    async def start(self):
        """Start the system"""
        if not self.initialization_complete:
            await self.initialize()
        
        self.is_running = True
        logger.info("Parkinson's Multiagent System is now running!")
        
        # Setup signal handlers for graceful shutdown
        for sig in [signal.SIGTERM, signal.SIGINT]:
            signal.signal(sig, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        if not self.shutdown_requested:
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            self.shutdown_requested = True
            self.is_running = False
        else:
            logger.info("Shutdown already in progress, ignoring repeated signal")
    
    async def shutdown(self):
        """Gracefully shutdown the system"""
        logger.info("Starting system shutdown...")
        self.is_running = False
        
        try:
            # Stop agents
            if self.aiml_agent:
                await self.aiml_agent.shutdown()
            if self.rag_agent:
                await self.rag_agent.shutdown()
            if self.supervisor_agent:
                await self.supervisor_agent.shutdown()
            
            # Stop shared memory
            if self.shared_memory:
                await self.shared_memory.shutdown()
            
            # Close Groq service
            if self.groq_service:
                await self.groq_service.close()
            
            # Close database
            if self.database:
                await self.database.close()
            
            logger.info("System shutdown completed successfully")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    
    async def health_check(self) -> dict:
        """Perform system health check"""
        health_status = {
            'system_status': 'healthy' if self.is_running else 'stopped',
            'initialization_complete': self.initialization_complete,
            'components': {}
        }
        
        # Check database
        if self.database:
            try:
                db_health = await self.database.health_check()
                health_status['components']['database'] = db_health
            except Exception as e:
                health_status['components']['database'] = {'status': 'error', 'error': str(e)}
        
        # Check shared memory
        if self.shared_memory:
            try:
                sm_health = await self.shared_memory.health_check()
                health_status['components']['shared_memory'] = sm_health
            except Exception as e:
                health_status['components']['shared_memory'] = {'status': 'error', 'error': str(e)}
        
        # Check Groq service
        if self.groq_service:
            try:
                groq_health = await self.groq_service.health_check()
                health_status['components']['groq_service'] = groq_health
            except Exception as e:
                health_status['components']['groq_service'] = {'status': 'error', 'error': str(e)}
        
        # Check agents
        for agent_name, agent in [
            ('supervisor', self.supervisor_agent),
            ('aiml', self.aiml_agent),
            ('rag', self.rag_agent)
        ]:
            if agent:
                try:
                    agent_health = await agent.health_check()
                    health_status['components'][f'{agent_name}_agent'] = agent_health
                except Exception as e:
                    health_status['components'][f'{agent_name}_agent'] = {'status': 'error', 'error': str(e)}
        
        return health_status
    
    async def process_user_input(self, message: str, metadata: dict = None) -> dict:
        """Process user input through the system"""
        if not self.is_running or not self.supervisor_agent:
            raise RuntimeError("System is not running or not properly initialized")
        
        if metadata is None:
            metadata = {}
        
        return await self.supervisor_agent.process_user_input(message, metadata)
    
    async def generate_authenticated_report(self, session_id: str, patient_id: str = None) -> Optional[str]:
        """
        Generate a role-based report using the current authenticated user.
        
        Args:
            session_id: Session identifier for the report
            patient_id: Optional patient ID (required for doctor reports)
            
        Returns:
            Path to generated report or None if failed
        """
        if not self.current_user:
            logger.error("No authenticated user found for report generation")
            return None
            
        # Convert dict to AuthUser-like object for compatibility
        class AuthUserCompat:
            def __init__(self, user_dict):
                self.id = user_dict.get('id')
                self.name = user_dict.get('name')
                self.role = user_dict.get('role')  # String role from auth system
        
        auth_user = AuthUserCompat(self.current_user)
        
        try:
            # Use RAG agent's authenticated report generation
            report_path = await self.rag_agent.generate_authenticated_report(
                session_id=session_id,
                auth_user=auth_user,
                patient_id=patient_id
            )
            
            if report_path:
                logger.info(f"✅ Authenticated report generated for {auth_user.role} {auth_user.id}: {report_path}")
            else:
                logger.error("❌ Failed to generate authenticated report")
                
            return report_path
            
        except Exception as e:
            logger.error(f"Error generating authenticated report: {e}")
            return None
    
    async def authenticate_user(self) -> bool:
        """
        Handle user authentication with role-based access
        Returns True if authentication successful, False otherwise
        """
        try:
            print("\n" + "="*60)
            print("🏥 PARKINSON'S MULTIAGENT SYSTEM")
            print("="*60)
            
            # Use the interactive authentication flow
            auth_result = await self.auth_manager.start_authentication_flow()
            
            if auth_result["success"]:
                self.current_user = auth_result["user"]
                user_role = auth_result["role"]
                permissions = auth_result.get("permissions", [])
                
                # Create session information
                self.current_session = {
                    "session_id": f"session_{uuid.uuid4().hex[:8]}",
                    "user": self.current_user,
                    "role": user_role,
                    "permissions": permissions,
                    "authenticated_at": asyncio.get_event_loop().time()
                }
                
                # Set up file directories for the user
                if user_role == "patient":
                    patient_id = self.current_user.get("patient_id")
                    if patient_id:
                        self.file_organizer.ensure_patient_structure(patient_id)
                elif user_role == "doctor":
                    doctor_id = self.current_user.get("doctor_id")
                    if doctor_id:
                        self.file_organizer.ensure_doctor_structure(doctor_id)
                
                print(f"\n🎉 Welcome to the Parkinson's Multiagent System!")
                print(f"   Role: {user_role.title()}")
                print(f"   User: {self.current_user.get('name', 'Unknown')}")
                
                if user_role == "doctor" and "assigned_patients" in self.current_user:
                    patient_count = len(self.current_user["assigned_patients"])
                    print(f"   Assigned Patients: {patient_count}")
                elif user_role == "patient":
                    if "patient_id" in self.current_user:
                        print(f"   Patient ID: {self.current_user['patient_id']}")
                    if "assigned_doctor_name" in self.current_user:
                        doctor_name = self.current_user["assigned_doctor_name"]
                        print(f"   Assigned Doctor: {doctor_name}")
                    
                    # Special message for new patients
                    if auth_result.get('new_patient', False):
                        print("\n🆕 New Patient Setup Complete!")
                        print("📝 Your profile has been created successfully.")
                        print("💡 Next Steps:")
                        print("   • Type 'profile' to view your complete information")
                        print("   • Type 'help' to see all available commands")
                        print("   • Ask medical questions about Parkinson's disease")
                        print("   • Upload MRI scans for analysis (when available)")
                        if self.current_user.get('assigned_doctor_name') != 'Not assigned':
                            print(f"   • Contact your assigned doctor: {self.current_user.get('assigned_doctor_name')}")
                        else:
                            print("   • Consider getting assigned to a doctor for better care")
                
                return True
            else:
                print(f"❌ Authentication failed: {auth_result.get('message', 'Unknown error')}")
                return False
                
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            print(f"❌ Authentication error: {e}")
            return False
    
    def get_user_context(self) -> Dict[str, Any]:
        """Get current user context for agent operations"""
        if not self.current_session:
            return {}
        
        context = {
            "session_id": self.current_session["session_id"],
            "user_role": self.current_session["role"],
            "user_id": self.current_user.get("id"),
            "permissions": self.current_session["permissions"]
        }
        
        # Add role-specific context
        if self.current_session["role"] == "patient":
            context.update({
                "patient_id": self.current_user.get("patient_id"),
                "patient_name": self.current_user.get("name"),
                "assigned_doctor_id": self.current_user.get("assigned_doctor_id")
            })
        elif self.current_session["role"] == "doctor":
            context.update({
                "doctor_id": self.current_user.get("doctor_id"),
                "doctor_name": self.current_user.get("name"),
                "assigned_patients": self.current_user.get("assigned_patients", [])
            })
        elif self.current_session["role"] == "admin":
            context["admin_privileges"] = True
        
        return context
    
    async def store_session_report(self, content: str, report_type: str = "consultation") -> str:
        """Store a report for the current session"""
        if not self.current_session or not self.file_organizer:
            raise RuntimeError("No active session or file organizer not initialized")
        
        user_role = self.current_session["role"]
        
        if user_role == "patient":
            # Patient session - store in patient directory
            patient_id = self.current_user.get("patient_id")
            if not patient_id:
                raise ValueError("Patient ID not found")
            
            # Generate unique report ID
            report_id = f"RPT_{asyncio.get_event_loop().time():.0f}_{uuid.uuid4().hex[:6]}"
            
            patient_path, doctor_path = self.file_organizer.save_report_legacy(
                patient_id=patient_id,
                doctor_id=self.current_user.get("assigned_doctor_id", "SYSTEM"),
                report_id=report_id,
                content=content.encode('utf-8'),
                create_doctor_copy=True
            )
            
            result = {"report_id": report_id, "patient_path": patient_path}
            
        elif user_role == "doctor":
            # Doctor session - need patient context (could prompt or use last interaction)
            doctor_id = self.current_user.get("doctor_id")
            if not doctor_id:
                raise ValueError("Doctor ID not found")
            
            # For doctor sessions, we'd need to specify which patient
            # This is a simplified version - in practice you'd track the current consultation
            assigned_patients = self.current_user.get("assigned_patients", [])
            if assigned_patients:
                patient_id = assigned_patients[0].get("patient_id")  # Use first patient as example
            else:
                patient_id = "UNASSIGNED"
            
            # Generate unique report ID
            report_id = f"RPT_{asyncio.get_event_loop().time():.0f}_{uuid.uuid4().hex[:6]}"
            
            patient_path, doctor_path = self.file_organizer.save_report(
                patient_id=patient_id,
                doctor_id=doctor_id,
                report_id=report_id,
                content=content.encode('utf-8'),
                create_doctor_copy=True
            )
            
            result = {"report_id": report_id, "patient_path": patient_path}
            
        else:
            # Admin or other roles - generic storage
            # Generate unique report ID
            report_id = f"RPT_{asyncio.get_event_loop().time():.0f}_{uuid.uuid4().hex[:6]}"
            
            patient_path, doctor_path = self.file_organizer.save_report(
                patient_id="ADMIN_SESSION",
                doctor_id="ADMIN", 
                report_id=report_id,
                content=content.encode('utf-8'),
                create_doctor_copy=True
            )
            
            result = {"report_id": report_id, "patient_path": patient_path}
        
        return result.get("report_id", "unknown")
    
    def should_create_report(self, response, user_input: str) -> bool:
        """
        Check if a report should be created based on the response and user intent
        Only create reports when explicitly requested or when dealing with medical analysis
        """
        try:
            # Check if response has intent information
            if hasattr(response, 'metadata') and response.metadata:
                intent = response.metadata.get('detected_intent', {})
                # Only create report if report was explicitly requested
                if intent.get('report_requested', False):
                    return True
                # Don't create report for chat-only interactions
                if intent.get('type') == 'chat_only':
                    return False
            
            # Check user input for explicit report keywords
            report_keywords = ['generate report', 'create report', 'save report', 'document this', 'medical report']
            user_lower = user_input.lower()
            if any(keyword in user_lower for keyword in report_keywords):
                return True
            
            # Check if MRI analysis was performed (should create report)
            if hasattr(response, 'metadata') and response.metadata:
                intent = response.metadata.get('detected_intent', {})
                if intent.get('prediction_requested', False) and intent.get('has_mri_file', False):
                    return True
                    
            return False
            
        except Exception as e:
            logger.warning(f"Error checking report creation intent: {e}")
            return False


async def collect_patient_info() -> dict:
    """Collect patient information for the session"""
    print("\n=== Patient Information ===")
    patient_name = input("Patient name: ").strip()
    if not patient_name:
        patient_name = "Unknown Patient"
    
    patient_id = f"patient_{uuid.uuid4().hex[:8]}"
    print(f"Generated Patient ID: {patient_id}")
    
    return {
        "patient_id": patient_id,
        "patient_name": patient_name
    }


async def collect_doctor_info() -> dict:
    """Collect doctor information for the session"""
    print("\n=== Doctor Information ===")
    doctor_name = input("Doctor name (optional): ").strip()
    if not doctor_name:
        doctor_name = "System Generated"
    
    doctor_id = f"doctor_{uuid.uuid4().hex[:8]}"
    if doctor_name != "System Generated":
        print(f"Generated Doctor ID: {doctor_id}")
    
    return {
        "doctor_id": doctor_id,
        "doctor_name": doctor_name
    }


async def main():
    """
    Main application entry point with integrated authentication
    
    Flow:
    1. Initialize system components
    2. User authentication (admin/doctor/patient)
    3. Interactive session based on user role
    4. Automatic file organization and report storage
    """
    system = ParkinsonsMultiagentSystem()
    
    try:
        # Initialize system components
        print("🔧 Initializing Parkinson's Multiagent System...")
        await system.start()
        
        # Authenticate user first
        print("\n📋 Authentication required to proceed...")
        authenticated = await system.authenticate_user()
        
        if not authenticated:
            print("❌ Authentication failed. Exiting...")
            return
        
        # Get user context for the session
        user_context = system.get_user_context()
        user_role = user_context.get("user_role")
        
        # Role-specific welcome and instructions
        print(f"\n💡 HELP - Available Commands:")
        print("   'quit' or 'exit' - Exit the system")
        print("   'health' - Check system health")
        print("   'profile' - Show your profile information")
        print("   'help' - Show this help message")
        
        if user_role == "doctor":
            print("   'patients' - List your assigned patients")
            print("   'new-assessment' - Start complete new patient assessment")
            print("   'assess <patient_id>' - Assess existing patient")
            print("   'reports' - Manage patient reports")
        elif user_role == "patient":
            print("   'reports' - View your medical reports")
            print("   'doctor' - View your assigned doctor information")
            print("   'symptoms' - Report symptoms or ask about Parkinson's")
            print("   'upload' - Upload MRI scans for analysis")
            print("   'history' - View your medical history")
        elif user_role == "admin":
            print("   'users' - Manage system users")
            print("   'system' - System administration")
            print("   'search <query>' - Search knowledge base")
            print("   'kb <query>' - Query knowledge base via RAG")
            print("   'stats' - View system statistics")
            print("   'logs' - View recent system logs")
        
        print("\n💬 You can also ask medical questions or describe symptoms...")
        print("    Example: 'I have tremors in my hands' or 'Analyze MRI scan'")
        
        # Interactive session loop
        while system.is_running and not system.shutdown_requested:
            try:
                user_input = input(f"\n[{user_role.upper()}] > ").strip()
                
                if user_input.lower() in ['quit', 'exit']:
                    break
                elif user_input.lower() == 'health':
                    health = await system.health_check()
                    print(f"📊 System Health: {health.get('system_status', 'unknown')}")
                    for component, status in health.get('components', {}).items():
                        print(f"   {component}: {status.get('status', 'unknown')}")
                        
                elif user_input.lower() == 'profile':
                    print(f"👤 Profile Information:")
                    print(f"   Name: {system.current_user.get('name', 'Unknown')}")
                    print(f"   Role: {user_role}")
                    print(f"   ID: {system.current_user.get('patient_id') or system.current_user.get('doctor_id') or system.current_user.get('id')}")
                    
                elif user_input.lower() == 'help':
                    # Show help again
                    continue
                    
                elif user_input.lower() == 'patients' and user_role == "doctor":
                    patients = system.current_user.get("assigned_patients", [])
                    print(f"👥 Assigned Patients ({len(patients)}):")
                    for patient in patients:
                        print(f"   - {patient.get('name')} (ID: {patient.get('patient_id')})")
                        
                elif (user_input.lower() in ['new-assessment', 'new-patient', 'nnew-assesment', 'new assessment'] 
                      and user_role == "doctor"):
                    await handle_new_patient_assessment(system)
                    
                elif user_input.lower().startswith('assess ') and user_role == "doctor":
                    patient_id = user_input[7:].strip()
                    await handle_existing_patient_assessment(system, patient_id)
                        
                elif user_input.lower() == 'doctor' and user_role == "patient":
                    doctor_name = system.current_user.get("assigned_doctor_name", "Not assigned")
                    print(f"👨‍⚕️ Assigned Doctor: {doctor_name}")
                
                # Enhanced Admin Commands
                elif user_input.lower() == 'users' and user_role == "admin":
                    await handle_admin_users_command(system)
                    
                elif user_input.lower() == 'system' and user_role == "admin":
                    await handle_admin_system_command(system)
                    
                elif user_input.lower().startswith('search ') and user_role == "admin":
                    query = user_input[7:].strip()
                    await handle_admin_search_command(system, query)
                    
                elif user_input.lower().startswith('kb ') and user_role == "admin":
                    kb_query = user_input[3:].strip()
                    await handle_admin_kb_command(system, kb_query)
                    
                elif user_input.lower() == 'stats' and user_role == "admin":
                    await handle_admin_stats_command(system)
                    
                elif user_input.lower() == 'logs' and user_role == "admin":
                    await handle_admin_logs_command(system)
                    
                elif user_input:
                    # Process medical query through the multiagent system
                    print("🤖 Processing your request...")
                    
                    # Add user context to metadata
                    metadata = user_context.copy()
                    metadata.update({
                        "timestamp": asyncio.get_event_loop().time(),
                        "input_type": "text_query"
                    })
                    
                    try:
                        response = await system.process_user_input(user_input, metadata)
                        
                        # Display response
                        if hasattr(response, 'content'):
                            response_text = response.content
                        else:
                            response_text = response.get('message', 'No response generated')
                        
                        print(f"🏥 System Response:")
                        print(f"   {response_text}")
                        
                        # Only store as report if explicitly requested
                        if system.should_create_report(response, user_input):
                            try:
                                report_content = f"User Query: {user_input}\n\nSystem Response: {response_text}"
                                report_id = await system.store_session_report(report_content, "consultation")
                                print(f"📄 Interaction saved as report: {report_id}")
                            except Exception as e:
                                print(f"⚠️ Could not save report: {e}")
                        
                    except Exception as e:
                        print(f"❌ Error processing request: {e}")
                        logger.error(f"Error processing user input: {e}")
                
            except KeyboardInterrupt:
                system.shutdown_requested = True
                print("\n⚠️ Shutdown requested...")
                break
            except Exception as e:
                print(f"❌ Session error: {e}")
                logger.error(f"Session error: {e}")
                
        # Graceful exit message
        if system.shutdown_requested:
            print("\n👋 Thank you for using the Parkinson's Multiagent System!")
            logger.info("User requested shutdown, cleaning up...")
    
    except Exception as e:
        logger.error(f"System error: {e}")
        print(f"❌ System error: {e}")
    
    finally:
        # Graceful shutdown
        print("🔧 Shutting down system components...")
        await system.shutdown()
        print("✅ Goodbye!")
        import sys
        sys.exit(1)


async def auth_only():
    """
    Quick authentication test without full system initialization
    Use this for testing authentication flow only
    """
    print("🔐 Authentication System Test")
    
    try:
        # Initialize only database and auth
        db_manager = DatabaseManager()
        await db_manager.init_database()
        
        auth_manager = AuthenticationManager(db_manager)
        
        # Run authentication flow
        auth_result = await auth_manager.start_authentication_flow()
        
        if auth_result["success"]:
            print(f"\n✅ Authentication successful!")
            print(f"   User: {auth_result['user']['name']}")
            print(f"   Role: {auth_result['role']}")
            print(f"   Permissions: {', '.join(auth_result.get('permissions', []))}")
        else:
            print(f"\n❌ Authentication failed: {auth_result.get('message')}")
            
        await db_manager.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")


# Enhanced Admin Commands
async def handle_admin_users_command(system):
    """Enhanced user management command for admin"""
    print("\n👥 USER MANAGEMENT")
    print("=" * 50)
    
    try:
        # Get all users from database
        db = system.shared_memory.db_manager
        
        # Get user statistics
        users = await db.get_all_users()
        active_users = [u for u in users if u.get('is_active', True)]
        user_roles = {}
        
        for user in users:
            role = user.get('role', 'unknown')
            user_roles[role] = user_roles.get(role, 0) + 1
        
        print("📊 User Statistics:")
        print(f"   Total Users: {len(users)}")
        print(f"   Active Users: {len(active_users)}")
        print(f"   Inactive Users: {len(users) - len(active_users)}")
        
        print("\n👤 Users by Role:")
        for role, count in user_roles.items():
            print(f"   {role.capitalize()}: {count}")
        
        print(f"\n📋 Recent Users (Last 5):")
        recent_users = sorted(users, key=lambda x: x.get('created_at', ''), reverse=True)[:5]
        
        for user in recent_users:
            status = "🟢" if user.get('is_active', True) else "🔴"
            last_login = user.get('last_login', 'Never')
            print(f"   {status} {user.get('username', 'Unknown')} ({user.get('role', 'unknown')}) - Last: {last_login}")
        
        print(f"\n💡 User Management Operations:")
        print(f"   To perform user operations, use these commands in a new session:")
        print(f"   • Create user: python admin_tools.py create-user")
        print(f"   • List all users: python admin_tools.py list-users") 
        print(f"   • Update user: python admin_tools.py update-user <username>")
        print(f"   • Deactivate user: python admin_tools.py deactivate-user <username>")
        print(f"   • Reset password: python admin_tools.py reset-password <username>")
        
    except Exception as e:
        print(f"❌ Error accessing user data: {e}")


async def handle_new_patient_assessment(system):
    """Handle new patient assessment - delegates to RAG agent"""
    try:
        user_role = system.current_user.get('role', 'unknown')
        
        if user_role not in ["admin", "doctor"]:
            print("❌ Only admins and doctors can create patient assessments")
            return
        
        # Delegate to RAG agent for complete workflow
        await system.rag_agent.handle_patient_assessment(
            user_role=user_role,
            user_context=system.get_user_context()
        )
            
    except Exception as e:
        print(f"❌ Error in patient assessment: {e}")
        import traceback
        traceback.print_exc()


async def handle_existing_patient_assessment(system, patient_id: str):
    """Handle assessment for existing patient - delegates to RAG agent"""
    try:
        await system.rag_agent.handle_existing_patient_assessment(
            patient_id=patient_id,
            user_context=system.get_user_context()
        )
    except Exception as e:
        print(f"❌ Error in patient assessment: {e}")


async def handle_admin_system_command(system):
    """Handle system administration command"""
    print("\n🛠️  SYSTEM ADMINISTRATION")
    print("=" * 50)
    
    try:
        # System health check
        health = await system.health_check()
        
        print("📊 System Health Overview:")
        print(f"   Status: {health.get('system_status', 'Unknown')}")
        print(f"   Uptime: {health.get('uptime', 'Unknown')}")
        
        print("\n🔧 Components Status:")
        for component, status in health.get('components', {}).items():
            status_icon = "✅" if status.get('status') == 'healthy' else "⚠️"
            print(f"   {status_icon} {component}: {status.get('status', 'unknown')}")
        
        # Database info
        print("\n💾 Database Information:")
        embeddings_manager = system.shared_memory.db_manager.get_embeddings_manager()
        if embeddings_manager:
            doc_count = len(getattr(embeddings_manager, 'documents', []))
            threshold = getattr(embeddings_manager, 'similarity_threshold', 'Unknown')
            print(f"   Knowledge Base: {doc_count} documents loaded")
            print(f"   Similarity Threshold: {threshold}")
        
        print("\n🔧 System Operations:")
        print("   - Restart components: 'system restart <component>'")
        print("   - Clear cache: 'system clear-cache'")
        print("   - Backup data: 'system backup'")
        print("   - View logs: 'logs'")
        
    except Exception as e:
        print(f"❌ Error getting system info: {e}")


async def handle_admin_search_command(system, query):
    """Handle knowledge base search for admin"""
    print(f"\n🔍 KNOWLEDGE BASE SEARCH: '{query}'")
    print("=" * 50)
    
    try:
        embeddings_manager = system.shared_memory.db_manager.get_embeddings_manager()
        
        if not embeddings_manager:
            print("❌ Knowledge base not available")
            return
        
        print("⏳ Searching knowledge base...")
        results = await embeddings_manager.search_similar(query, k=5)
        
        if results:
            print(f"✅ Found {len(results)} results:")
            for i, result in enumerate(results, 1):
                similarity = result.get('similarity', 0)
                source = result.get('metadata', {}).get('source_file', 'Unknown')
                content = result.get('text', '')[:200] + "..."
                
                print(f"\n📄 Result {i}:")
                print(f"   Similarity: {similarity:.4f}")
                print(f"   Source: {source}")
                print(f"   Content: {content}")
        else:
            print("❌ No results found")
            
    except Exception as e:
        print(f"❌ Search error: {e}")


async def handle_admin_kb_command(system, query):
    """Handle knowledge base query command"""
    print(f"\n📚 KNOWLEDGE BASE QUERY: '{query}'")
    print("=" * 50)
    
    try:
        # This simulates how the RAG system processes queries
        embeddings_manager = system.shared_memory.db_manager.get_embeddings_manager()
        
        if not embeddings_manager:
            print("❌ Knowledge base not available")
            return
        
        print("🤖 Processing query through RAG system...")
        
        # Search knowledge base
        results = await embeddings_manager.search_similar(query, k=3)
        
        if results:
            print(f"✅ RAG Knowledge Retrieved:")
            for i, result in enumerate(results, 1):
                similarity = result.get('similarity', 0)
                source = result.get('metadata', {}).get('source_file', 'Unknown')
                content = result.get('text', '')[:300] + "..."
                
                print(f"\n📖 Knowledge Source {i}:")
                print(f"   Relevance: {similarity:.4f}")
                print(f"   Document: {source}")
                print(f"   Content: {content}")
        else:
            print("⚠️ No relevant knowledge found")
        
    except Exception as e:
        print(f"❌ KB query error: {e}")


async def handle_admin_stats_command(system):
    """Handle system statistics command"""
    print("\n📊 SYSTEM STATISTICS")
    print("=" * 50)
    
    try:
        # Knowledge base stats
        embeddings_manager = system.shared_memory.db_manager.get_embeddings_manager()
        if embeddings_manager:
            doc_count = len(getattr(embeddings_manager, 'documents', []))
            print(f"📚 Knowledge Base:")
            print(f"   Documents: {doc_count}")
            print(f"   Similarity Threshold: {getattr(embeddings_manager, 'similarity_threshold', 'N/A')}")
        
        # System performance (placeholder - you can add real metrics)
        print(f"\n⚡ Performance Metrics:")
        print(f"   Average Response Time: [Implement metrics tracking]")
        print(f"   Total Queries Processed: [Implement counter]")
        print(f"   Reports Generated: [Implement counter]")
        
        # System resources (optional - requires psutil package)
        try:
            import psutil
            memory = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=1)
            print(f"\n💾 System Resources:")
            print(f"   Memory Usage: {memory.percent:.1f}%")
            print(f"   Available Memory: {memory.available / (1024**3):.1f} GB")
            print(f"   CPU Usage: {cpu_percent:.1f}%")
        except ImportError:
            print(f"\n💾 System Resources: [Install 'pip install psutil' for detailed metrics]")
        except Exception as e:
            print(f"   ⚠️ Could not get system stats: {e}")
        
    except Exception as e:
        print(f"❌ Stats error: {e}")


async def handle_admin_logs_command(system):
    """Handle logs viewing command"""
    print("\n📝 SYSTEM LOGS")
    print("=" * 50)
    
    try:
        import os
        log_file = "logs/system.log"
        
        if os.path.exists(log_file):
            print(f"📄 Recent log entries from {log_file}:")
            print("-" * 50)
            
            # Show last 20 lines
            with open(log_file, 'r') as f:
                lines = f.readlines()
                recent_lines = lines[-20:] if len(lines) > 20 else lines
                
                for line in recent_lines:
                    print(f"   {line.strip()}")
        else:
            print(f"⚠️ Log file not found: {log_file}")
            
        print("\n💡 Log Commands:")
        print("   - View full logs: Open logs/system.log")
        print("   - Clear logs: 'system clear-logs'")
        
    except Exception as e:
        print(f"❌ Error reading logs: {e}")


if __name__ == "__main__":
    import sys
    
    # Check for command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "auth":
            # Run authentication test only
            try:
                asyncio.run(auth_only())
            except KeyboardInterrupt:
                print("\n⚠️ Authentication test interrupted")
            except Exception as e:
                print(f"❌ Authentication error: {e}")
            sys.exit(0)
        elif sys.argv[1] == "help":
            print("🏥 Parkinson's Multiagent System")
            print("\nUsage:")
            print("  python main.py        - Run full system with authentication")
            print("  python main.py auth   - Test authentication system only")  
            print("  python main.py help   - Show this help")
            sys.exit(0)
    
    # Run full system
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️ Shutdown requested by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)