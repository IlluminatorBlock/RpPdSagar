"""
Main entry point for Parkinson's Multiagent System
"""

import asyncio
import logging
import logging.config
import signal
import sys
import uuid
from typing import Optional
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
from knowledge_base.embeddings_manager import EmbeddingsManager

# Configure logging
logging.config.dictConfig(config.logging_config)
logger = logging.getLogger('parkinsons_system.main')


class ParkinsonsMultiagentSystem:
    """Main system orchestrator"""
    
    def __init__(self):
        self.shared_memory: Optional[SharedMemoryInterface] = None
        self.database: Optional[DatabaseManager] = None
        self.groq_service: Optional[GroqService] = None
        self.mri_processor: Optional[MRIProcessor] = None
        self.embeddings_manager: Optional[EmbeddingsManager] = None
        
        # Agents
        self.supervisor_agent: Optional[SupervisorAgent] = None
        self.aiml_agent: Optional[AIMLAgent] = None
        self.rag_agent: Optional[RAGAgent] = None
        
        # System state
        self.is_running = False
        self.initialization_complete = False
        self.shutdown_requested = False
    
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
            
            # Initialize MRI processor
            logger.info("Initializing MRI processor...")
            self.mri_processor = MRIProcessor(config.mri_processor_config)
            
            # Initialize embeddings manager
            logger.info("Initializing embeddings manager...")
            self.embeddings_manager = EmbeddingsManager(config.embeddings_config)
            await self.embeddings_manager.initialize()
            
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
        
        # Initialize RAG Agent
        self.rag_agent = RAGAgent(
            shared_memory=self.shared_memory,
            groq_service=self.groq_service,
            embeddings_manager=self.embeddings_manager,
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
    """Main application entry point"""
    system = ParkinsonsMultiagentSystem()
    
    try:
        # Initialize and start the system
        await system.start()
        
        # Interactive loop for testing
        print("\nParkinson's Multiagent System is ready!")
        print("Type 'quit' to exit, 'health' for health check, or enter a message:")
        
        # Collect patient and doctor information once
        patient_info = await collect_patient_info()
        doctor_info = await collect_doctor_info()
        
        while system.is_running and not system.shutdown_requested:
            try:
                user_input = input("\n> ").strip()
                
                if user_input.lower() == 'quit':
                    break
                elif user_input.lower() == 'health':
                    health = await system.health_check()
                    print(f"Health Status: {health}")
                elif user_input:
                    # Generate unique session ID for each interaction
                    session_id = f"session_{uuid.uuid4().hex[:8]}"
                    metadata = {
                        "session_id": session_id, 
                        "user_id": "cli_user",
                        "patient_id": patient_info["patient_id"],
                        "patient_name": patient_info["patient_name"],
                        "doctor_id": doctor_info["doctor_id"],
                        "doctor_name": doctor_info["doctor_name"]
                    }
                    response = await system.process_user_input(user_input, metadata)
                    if hasattr(response, 'content'):
                        # Response object from SupervisorAgent
                        print(f"System: {response.content}")
                    else:
                        # Dictionary response (fallback)
                        print(f"System: {response.get('message', 'No response')}")
                
            except KeyboardInterrupt:
                system.shutdown_requested = True
                break
            except Exception as e:
                print(f"Error: {e}")
                
        # Check if shutdown was requested
        if system.shutdown_requested:
            logger.info("Shutdown requested, cleaning up...")
    
    except Exception as e:
        logger.error(f"System error: {e}")
    
    finally:
        # Graceful shutdown
        await system.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)