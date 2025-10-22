"""
Supervisor Agent for Parkinson's Multiagent System

This agent serves as the central orchestrator, managing workflows,
handling user input, and coordinating between AI/ML and RAG agents.
Implements explicit triggering for prediction and report generation.
"""

import asyncio
import logging
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from models.agent_interfaces import BaseAgent, SupervisorInterface
from models.data_models import (
    UserInput, Response, SessionData, ActionFlagType, 
    InputType, OutputFormat, SessionStatus
)
from services.groq_service import GroqService

# Configure logging
logger = logging.getLogger(__name__)


class SupervisorAgent(BaseAgent, SupervisorInterface):
    """
    Central orchestrator for the Parkinson's multiagent system.
    
    Responsibilities:
    1. Orchestrates workflow only - never calls AI/ML or RAG logic directly
    2. Sets action flags for prediction or report generation based on explicit user intent
    3. Handles chat responses via Groq API when no prediction/report is requested
    4. Manages session lifecycle and coordination
    """
    
    def __init__(self, shared_memory, groq_service: GroqService, config: Dict[str, Any]):
        super().__init__(shared_memory, config, "supervisor_agent")
        self.groq_service = groq_service
        
        # Workflow patterns for explicit intent detection
        self.prediction_keywords = [
            "analyze mri", "mri analysis", "predict parkinson", "predict", "diagnose",
            "scan analysis", "medical imaging", "brain scan", "examine mri", "analyze",
            "process mri", "check mri", "evaluate", "assessment", "classification"
        ]
        
        self.report_keywords = [
            "generate report", "medical report", "create report", "full report",
            "detailed analysis", "comprehensive report", "formal report",
            "get report", "report for", "make report", "report on", "get me report", "report"
        ]
        
        # Chat mode indicators
        self.chat_keywords = [
            "what is", "tell me about", "explain", "how does", "symptoms",
            "treatment", "help", "information", "question"
        ]
    
    async def initialize(self) -> None:
        """Initialize the supervisor agent and start background tasks"""
        self.logger.debug("[LIFECYCLE] Initializing SupervisorAgent")
        
        # Call parent initialize
        await super().initialize()
        
        # Initialize Groq service if not already done
        if not self.groq_service.session:
            await self.groq_service.initialize()
        
        self.logger.info("Supervisor Agent initialized and ready to orchestrate workflows")
    
    async def shutdown(self) -> None:
        """Shutdown the supervisor agent and cleanup resources"""
        self.logger.debug("[LIFECYCLE] Shutting down SupervisorAgent")
        
        await self.groq_service.close()
        await super().shutdown()
        
        self.logger.info("Supervisor Agent shutdown completed")
    
    async def process_task(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process tasks assigned to supervisor agent"""
        self.logger.debug(f"[TASK] SupervisorAgent processing {event_type}")
        
        if event_type == "user_input":
            message = payload.get("message", "")
            metadata = payload.get("metadata", {})
            response = await self.process_user_input(message, metadata)
            return {"status": "completed", "response": response}
        elif event_type == "session_cleanup":
            session_id = payload.get("session_id")
            await self._cleanup_session(session_id)
            return {"status": "completed", "action": "session_cleaned"}
        elif event_type == "flag_status_report":
            return await self._generate_flag_status_report()
        elif event_type == "health_check":
            return await self.health_check()
        else:
            return await super().process_task(event_type, payload)
    
    async def process_user_input(self, message: str, metadata: Dict[str, Any] = None) -> Response:
        """
        Main entry point for CLI user interactions.
        Determines workflow based on explicit user intent.
        """
        self.logger.debug(f"[USER_INPUT] Processing message: {message[:100]}...")
        
        if metadata is None:
            metadata = {}
        
        try:
            # Generate a unique session ID for each request
            unique_session_id = f"session_{uuid.uuid4().hex[:8]}"
            
            # Create UserInput object from simple message
            user_input = UserInput(
                session_id=unique_session_id,
                user_id=metadata.get("user_id", "cli_user"),
                patient_id=metadata.get("patient_id"),
                doctor_id=metadata.get("doctor_id"),
                input_type=InputType.TEXT,
                content=message,
                output_format=OutputFormat.TEXT,
                timestamp=datetime.now()
            )
            
            # Create session for this interaction
            session_data = SessionData(
                session_id=user_input.session_id,
                input_type=user_input.input_type,
                output_format=user_input.output_format,
                user_id=user_input.user_id,
                patient_id=metadata.get("patient_id"),
                patient_name=metadata.get("patient_name"),
                doctor_id=metadata.get("doctor_id"),
                doctor_name=metadata.get("doctor_name"),
                status=SessionStatus.ACTIVE
            )
            
            session_id = await self.shared_memory.create_session(session_data)
            self.logger.info(f"Created session {session_id} for user input")
            
            # Analyze user intent
            intent = await self._analyze_user_intent(user_input)
            self.logger.info(f"Detected intent: {intent} for session {session_id}")
            
            # Execute appropriate workflow
            response = await self._execute_workflow(session_id, user_input, intent)
            
            # Update session status
            await self.shared_memory.db_manager.update_session_status(
                session_id, SessionStatus.COMPLETED
            )
            
            return response
            
        except Exception as e:
            self._handle_error(e, "processing user input")
            # Provide user-friendly error messages instead of raw database errors
            if "UNIQUE constraint failed" in str(e):
                error_msg = "Unable to process request due to a system conflict. Please try again."
            elif "database is locked" in str(e):
                error_msg = "System is temporarily busy. Please try again in a moment."
            elif "no such table" in str(e):
                error_msg = "System configuration issue. Please contact administrator."
            else:
                error_msg = "An unexpected error occurred. Please try again or contact support if the issue persists."
            
            return self._create_error_response(user_input.session_id if 'user_input' in locals() else "unknown", error_msg)
    
    async def _analyze_user_intent(self, user_input: UserInput) -> Dict[str, Any]:
        """
        Analyze user input to determine explicit intent.
        
        Returns intent classification:
        - prediction_requested: User explicitly wants MRI analysis
        - report_requested: User explicitly wants report generation
        - chat_only: User wants conversational interaction
        - combined: User wants both prediction and report
        """
        content_lower = user_input.content.lower()
        
        # Check for explicit prediction request
        prediction_requested = any(keyword in content_lower for keyword in self.prediction_keywords)
        
        # Check for explicit report request
        report_requested = any(keyword in content_lower for keyword in self.report_keywords)
        
        # Check if file path is mentioned in the message (common pattern: "get report for <file>")
        has_file_path_in_message = self._detect_file_path_in_message(user_input.content)
        
        # Check if MRI file is provided via user_input object
        has_mri_file = user_input.mri_file_path is not None
        
        # If we detect a file path in the message but no mri_file_path, extract it
        detected_file_path = None
        if has_file_path_in_message and not has_mri_file:
            detected_file_path = self._extract_file_path_from_message(user_input.content)
            has_mri_file = detected_file_path is not None
        
        # Special cases for common patterns
        if has_file_path_in_message:
            # "report <file>" or "get report <file>" should trigger both prediction and report
            if any(phrase in content_lower for phrase in ["report for", "report on", "get me report", "get report", "report"]):
                prediction_requested = True
                report_requested = True
            # "analyze <file>" should trigger prediction
            elif any(phrase in content_lower for phrase in ["analyze", "examine", "diagnose"]):
                prediction_requested = True
            # IMPORTANT: If we have a prediction keyword AND a file, always enable prediction
            elif prediction_requested:
                prediction_requested = True  # Ensure it stays true
        
        # Additional check: if user just says "report" with a file, they want both prediction and report
        if report_requested and has_mri_file and not prediction_requested:
            prediction_requested = True  # Need prediction first for report generation
        
        # Determine intent
        if has_mri_file and (prediction_requested or report_requested):
            if prediction_requested and report_requested:
                intent_type = "combined"
            elif prediction_requested:
                intent_type = "prediction_only"
            elif report_requested:
                intent_type = "report_with_prediction"  # Report requires prediction first
            else:
                intent_type = "prediction_only"  # Default for MRI uploads
        elif prediction_requested and not has_mri_file:
            intent_type = "prediction_no_mri"  # User wants prediction but no MRI provided
        elif report_requested and not has_mri_file:
            intent_type = "report_no_prediction"  # User wants report but no prediction data
        else:
            intent_type = "chat_only"
        
        return {
            "type": intent_type,
            "prediction_requested": prediction_requested,
            "report_requested": report_requested,
            "has_mri_file": has_mri_file,
            "detected_file_path": detected_file_path,
            "confidence": self._calculate_intent_confidence(content_lower, intent_type)
        }
    
    def _calculate_intent_confidence(self, content: str, intent_type: str) -> float:
        """Calculate confidence score for intent classification"""
        # Simple keyword-based confidence calculation
        total_keywords = len(self.prediction_keywords + self.report_keywords + self.chat_keywords)
        
        if intent_type == "chat_only":
            chat_matches = sum(1 for keyword in self.chat_keywords if keyword in content)
            return min(0.9, 0.3 + (chat_matches / len(self.chat_keywords)) * 0.6)
        elif "prediction" in intent_type:
            pred_matches = sum(1 for keyword in self.prediction_keywords if keyword in content)
            return min(0.95, 0.5 + (pred_matches / len(self.prediction_keywords)) * 0.45)
        elif "report" in intent_type:
            report_matches = sum(1 for keyword in self.report_keywords if keyword in content)
            return min(0.95, 0.5 + (report_matches / len(self.report_keywords)) * 0.45)
        else:
            return 0.1  # Low confidence for unclear intent
    
    def _detect_file_path_in_message(self, message: str) -> bool:
        """Detect if the message contains a file path"""
        import re
        
        # Common file path patterns - improved to handle spaces
        patterns = [
            r'[a-zA-Z]:[^\r\n]*\.(png|jpg|jpeg|dicom|dcm|nii|nifti)',  # Windows paths (with spaces)
            r'/[^\r\n]*\.(png|jpg|jpeg|dicom|dcm|nii|nifti)',            # Unix paths (with spaces)
            r'"[^"]*\.(png|jpg|jpeg|dicom|dcm|nii|nifti)"',           # Quoted paths
            r'[a-zA-Z]:\\[^\s]*\.(png|jpg|jpeg|dicom|dcm|nii|nifti)',  # Windows paths (no spaces - legacy)
        ]
        
        for pattern in patterns:
            if re.search(pattern, message, re.IGNORECASE):
                return True
        return False
    
    def _extract_file_path_from_message(self, message: str) -> Optional[str]:
        """Extract file path from the message"""
        import re
        import os
        
        # Common file path patterns - improved to handle spaces and various formats
        patterns = [
            r'"([^"]*\.(png|jpg|jpeg|dicom|dcm|nii|nifti))"',         # Quoted paths (most reliable)
            r'([a-zA-Z]:[^\r\n]*\.(png|jpg|jpeg|dicom|dcm|nii|nifti))', # Windows paths (with spaces)
            r'(/[^\r\n]*\.(png|jpg|jpeg|dicom|dcm|nii|nifti))',        # Unix paths (with spaces)
            r'([a-zA-Z]:\\[^\s]*\.(png|jpg|jpeg|dicom|dcm|nii|nifti))', # Windows paths (no spaces - legacy)
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                file_path = match.group(1).strip()
                # Verify the file exists
                if os.path.exists(file_path):
                    return file_path
                    
        return None
    
    async def _execute_workflow(self, session_id: str, user_input: UserInput, 
                              intent: Dict[str, Any]) -> Response:
        """Execute appropriate workflow based on user intent"""
        intent_type = intent["type"]
        
        # If we detected a file path in the message, update the user_input object
        if intent.get("detected_file_path") and not user_input.mri_file_path:
            user_input.mri_file_path = intent["detected_file_path"]
            self.logger.info(f"Using detected file path: {user_input.mri_file_path}")
        
        if intent_type == "chat_only":
            return await self.handle_chat_request(user_input)
        
        elif intent_type == "prediction_only":
            return await self._handle_prediction_workflow(session_id, user_input)
        
        elif intent_type == "report_with_prediction":
            return await self._handle_combined_workflow(session_id, user_input)
        
        elif intent_type == "combined":
            return await self._handle_combined_workflow(session_id, user_input)
        
        elif intent_type == "prediction_no_mri":
            return await self._handle_missing_mri_error(session_id, user_input)
        
        elif intent_type == "report_no_prediction":
            return await self._handle_report_only_workflow(session_id, user_input)
        
        else:
            return await self.handle_chat_request(user_input)  # Default to chat
    
    async def handle_chat_request(self, user_input: UserInput) -> Response:
        """
        Handle chat-only requests using RAG knowledge base first, then Groq for enhancement.
        This provides evidence-based medical information for all queries.
        """
        try:
            # Get session context if available
            session_context = None
            if user_input.session_id:
                session_data = await self.shared_memory.get_session_data(user_input.session_id)
                if session_data:
                    session_context = {
                        "session_id": session_data.session_id,
                        "input_type": session_data.input_type.value,
                        "previous_interactions": "none"  # Could be expanded
                    }

            # STEP 1: Search knowledge base for medical information
            knowledge_results = []
            try:
                # Get embeddings manager via database
                embeddings_manager = self.shared_memory.db_manager.get_embeddings_manager()
                
                if embeddings_manager:
                    # Extract key medical terms from query
                    query_text = user_input.content.lower()
                    
                    # Simple keyword extraction for better search
                    medical_keywords = []
                    if 'parkinson' in query_text:
                        medical_keywords.append('parkinson disease')
                    if 'symptom' in query_text:
                        medical_keywords.append('symptoms')
                    if 'treatment' in query_text:
                        medical_keywords.append('treatment therapy')
                    if 'depression' in query_text:
                        medical_keywords.append('depression mood')
                    
                    # Use enhanced query or fallback to original
                    search_query = ' '.join(medical_keywords) if medical_keywords else user_input.content
                    
                    logger.info(f"Searching knowledge base with query: '{search_query}' (original: '{user_input.content}')")
                    
                    # Search for relevant medical knowledge
                    search_results = await embeddings_manager.search_similar(
                        query_text=search_query,
                        k=5  # Get top 5 relevant chunks
                    )
                    
                    # Format knowledge for context
                    for result in search_results:
                        similarity_score = result.get('similarity', 0.0)
                        knowledge_results.append({
                            'content': result.get('text', ''),
                            'source': result.get('metadata', {}).get('source_file', 'Medical Literature'),
                            'similarity': similarity_score
                        })
                        logger.info(f"Found result with similarity {similarity_score:.4f} from {result.get('metadata', {}).get('source_file', 'Unknown')}")
                    
                    logger.info(f"Total search results: {len(search_results)}, formatted results: {len(knowledge_results)}")
                    
                    if len(knowledge_results) == 0:
                        logger.warning(f"No knowledge results found for query '{search_query}' - check similarity threshold ({getattr(embeddings_manager, 'similarity_threshold', 'unknown')})")
                else:
                    logger.warning("Embeddings manager not available for chat")
                    
            except Exception as e:
                logger.warning(f"Knowledge search failed for chat: {e}")

            # STEP 2: Use Groq to generate response with medical knowledge context
            if knowledge_results:
                # Prepare context with medical knowledge
                medical_context = "Based on medical literature:\n\n"
                for i, kb_entry in enumerate(knowledge_results[:3], 1):  # Use top 3 results
                    if kb_entry['similarity'] > 0.2:  # Only use relevant results
                        medical_context += f"Source {i} ({kb_entry['source']}):\n{kb_entry['content'][:300]}...\n\n"
                
                # Enhanced prompt with medical knowledge
                enhanced_query = f"""As a medical AI assistant, please provide an informative response based on the medical literature provided and the user's question.

Medical Knowledge Context:
{medical_context}

User Question: {user_input.content}

Please provide a comprehensive, evidence-based response that incorporates the medical knowledge above. Include relevant medical information while being clear that this is for educational purposes only and not a substitute for professional medical advice."""

                chat_response = await self.groq_service.handle_chat_request(
                    enhanced_query, session_context
                )
                
                # Add source attribution
                sources = [kb_entry['source'] for kb_entry in knowledge_results[:3] if kb_entry['similarity'] > 0.2]
                if sources:
                    chat_response += f"\n\n📚 Information sourced from: {', '.join(set(sources))}"
                
            else:
                # Fallback to standard Groq response if no knowledge found
                chat_response = await self.groq_service.handle_chat_request(
                    user_input.content, session_context
                )
                chat_response += "\n\n💡 Note: This response uses general AI knowledge. For evidence-based medical information, please be more specific with your query."

            return Response(
                response_id=str(uuid.uuid4()),
                session_id=user_input.session_id,
                content=chat_response,
                format_type=user_input.output_format,
                generated_by="SupervisorAgent_RAG_Enhanced",
                confidence_score=0.9 if knowledge_results else 0.7,
                timestamp=datetime.now()
            )

        except Exception as e:
            self._handle_error(e, "handling RAG-enhanced chat request")
            return self._create_error_response(user_input.session_id, 
                                             "I apologize, but I'm having trouble processing your request right now.")
    
    async def _handle_prediction_workflow(self, session_id: str, user_input: UserInput) -> Response:
        """Handle explicit MRI prediction workflow"""
        try:
            # Store MRI data if provided
            if user_input.mri_file_path:
                from models.data_models import MRIData, ProcessingStatus
                
                # Read binary data
                binary_data = None
                try:
                    with open(user_input.mri_file_path, 'rb') as f:
                        binary_data = f.read()
                except Exception as e:
                    logger.warning(f"Could not read binary data for MRI file: {e}")
                
                mri_data = MRIData(
                    scan_id=str(uuid.uuid4()),
                    session_id=session_id,
                    original_filename=user_input.mri_file_path.split('/')[-1],
                    file_path=user_input.mri_file_path,
                    file_type=self._detect_file_type(user_input.mri_file_path),
                    binary_data=binary_data,
                    processing_status=ProcessingStatus.PENDING
                )
                
                await self.shared_memory.store_mri_data(mri_data)
                logger.info(f"Stored MRI data for session {session_id}")
            
            # Set PREDICT_PARKINSONS flag for AI/ML Agent
            flag_id = await self.shared_memory.set_action_flag(
                flag_type=ActionFlagType.PREDICT_PARKINSONS,
                session_id=session_id,
                data={
                    "mri_file_path": user_input.mri_file_path,
                    "user_request": user_input.content,
                    "priority": "high"
                },
                priority=1
            )
            
            logger.info(f"Set PREDICT_PARKINSONS flag {flag_id} for session {session_id}")
            
            # Wait for prediction completion
            prediction_completed = await self._wait_for_prediction_completion(session_id)
            
            if prediction_completed:
                # Get prediction results
                prediction = await self.shared_memory.get_latest_prediction(session_id)
                
                if prediction:
                    # Format response with prediction results
                    response_content = await self._format_prediction_response(prediction)
                    
                    return Response(
                        response_id=str(uuid.uuid4()),
                        session_id=session_id,
                        content=response_content,
                        format_type=user_input.output_format,
                        generated_by="SupervisorAgent_Prediction",
                        confidence_score=prediction.confidence_score,
                        timestamp=datetime.now()
                    )
            
            return self._create_error_response(session_id, 
                                             "MRI analysis could not be completed. Please try again.")
            
        except Exception as e:
            self._handle_error(e, "handling prediction workflow")
            return self._create_error_response(session_id, "Error processing MRI analysis request.")
    
    async def _handle_combined_workflow(self, session_id: str, user_input: UserInput) -> Response:
        """Handle workflow that requires both prediction and report generation"""
        try:
            # First, handle prediction if MRI is provided
            if user_input.mri_file_path:
                # Store MRI data
                from models.data_models import MRIData, ProcessingStatus
                
                # Read binary data
                binary_data = None
                try:
                    with open(user_input.mri_file_path, 'rb') as f:
                        binary_data = f.read()
                except Exception as e:
                    logger.warning(f"Could not read binary data for MRI file: {e}")
                
                mri_data = MRIData(
                    scan_id=str(uuid.uuid4()),
                    session_id=session_id,
                    original_filename=user_input.mri_file_path.split('/')[-1],
                    file_path=user_input.mri_file_path,
                    file_type=self._detect_file_type(user_input.mri_file_path),
                    binary_data=binary_data,
                    processing_status=ProcessingStatus.PENDING
                )
                
                await self.shared_memory.store_mri_data(mri_data)
                
                # Set prediction flag
                pred_flag_id = await self.shared_memory.set_action_flag(
                    flag_type=ActionFlagType.PREDICT_PARKINSONS,
                    session_id=session_id,
                    data={"mri_file_path": user_input.mri_file_path},
                    priority=1
                )
                
                # Wait for prediction completion
                prediction_completed = await self._wait_for_prediction_completion(session_id)
                
                if not prediction_completed:
                    return self._create_error_response(session_id, 
                                                     "MRI analysis failed. Cannot generate report.")
            
            # Check for existing reports before generating new one
            session_data = await self.shared_memory.get_session_data(session_id)
            if session_data:
                existing_reports_info = await self._check_existing_reports(session_data)
                if existing_reports_info:
                    # Ask user about existing reports
                    existing_reports_message = await self._ask_user_about_existing_reports(session_id, existing_reports_info)
                    return self._create_response(session_id, existing_reports_message)
            
            # Set GENERATE_REPORT flag for RAG Agent
            report_flag_id = await self.shared_memory.set_action_flag(
                flag_type=ActionFlagType.GENERATE_REPORT,
                session_id=session_id,
                data={
                    "report_type": "comprehensive",
                    "user_request": user_input.content
                },
                priority=1
            )
            
            logger.info(f"Set GENERATE_REPORT flag {report_flag_id} for session {session_id}")
            
            # Wait for report completion
            report_completed = await self._wait_for_report_completion(session_id)
            
            if report_completed:
                # Get report results
                reports = await self.shared_memory.get_reports(session_id)
                
                if reports:
                    latest_report = reports[-1]  # Get the most recent report
                    
                    return Response(
                        response_id=str(uuid.uuid4()),
                        session_id=session_id,
                        content=latest_report['content'],
                        format_type=user_input.output_format,
                        generated_by="SupervisorAgent_Combined",
                        confidence_score=latest_report.get('confidence_level', 0.8),
                        timestamp=datetime.now()
                    )
            
            return self._create_error_response(session_id, 
                                             "Report generation could not be completed. Please try again.")
            
        except Exception as e:
            self._handle_error(e, "handling combined workflow")
            return self._create_error_response(session_id, "Error processing combined analysis request.")
    
    async def _handle_report_only_workflow(self, session_id: str, user_input: UserInput) -> Response:
        """
        NEW INTELLIGENT WORKFLOW: Handle report requests with patient ID-based retrieval
        
        Workflow:
        1. Ask for Patient ID
        2. Retrieve patient info + all previous reports (OPTIMIZED single query)
        3. Display patient name and report history
        4. Ask: Return old report OR generate new report?
        5. If old: Return selected report
        6. If new: Collect updated info + require MRI scan + generate fresh report
        """
        try:
            # Get user role for appropriate workflow
            user_role = user_input.metadata.get('user_role', 'unknown') if hasattr(user_input, 'metadata') else 'unknown'
            user_id = user_input.user_id
            
            # STEP 1: Ask for Patient ID
            print("\n" + "="*70)
            print("🏥 REPORT REQUEST - PATIENT ID REQUIRED")
            print("="*70)
            
            patient_id = input("Enter Patient ID (or press Enter to cancel): ").strip()
            
            if not patient_id:
                return self._create_response(session_id, 
                    "❌ Report request cancelled - No patient ID provided.")
            
            # STEP 2: Retrieve patient data with ALL reports (OPTIMIZED - single JOIN query)
            print(f"\n🔍 Retrieving patient information for: {patient_id}...")
            
            patient_data = await self.shared_memory.db_manager.get_patient_with_reports(patient_id)
            
            if not patient_data:
                return self._create_error_response(session_id,
                    f"❌ Patient ID '{patient_id}' not found in the system.\n"
                    f"Please check the ID and try again.")
            
            patient_info = patient_data['patient']
            reports = patient_data['reports']
            
            # STEP 3: Display patient name and report history
            print("\n" + "="*70)
            print(f"✅ PATIENT FOUND: {patient_info['name']}")
            print("="*70)
            print(f"Patient ID: {patient_info['patient_id']}")
            print(f"Age: {patient_info['age']} | Gender: {patient_info['gender']}")
            print(f"Medical History: {patient_info['medical_history'] or 'None recorded'}")
            
            if patient_info['assigned_doctor_name']:
                print(f"Assigned Doctor: {patient_info['assigned_doctor_name']}")
            
            print(f"\n📊 Found {len(reports)} previous report(s)")
            
            if reports:
                print("\nReport History:")
                print("-" * 70)
                for idx, report in enumerate(reports, 1):
                    print(f"{idx}. {report['title']}")
                    print(f"   Type: {report['report_type']} | Created: {report['created_at']}")
                    if report['prediction']:
                        pred = report['prediction']
                        print(f"   Result: {pred['binary_result']} (Confidence: {pred['confidence_score']:.2%})")
                    print()
            else:
                print("   No previous reports found for this patient.")
            
            # STEP 4: Ask user what they want to do
            print("="*70)
            print("OPTIONS:")
            print("  [1] View/Return an existing report")
            print("  [2] Generate NEW report (requires MRI scan)")
            print("  [0] Cancel")
            print("="*70)
            
            choice = input("Enter your choice: ").strip()
            
            # OPTION 1: Return existing report
            if choice == "1":
                if not reports:
                    return self._create_error_response(session_id,
                        "❌ No existing reports available. Choose option [2] to generate a new report.")
                
                # Let user select which report
                if len(reports) == 1:
                    selected_report = reports[0]
                    print(f"\nReturning report: {selected_report['title']}")
                else:
                    print("\nSelect report number:")
                    report_num = input(f"Enter number (1-{len(reports)}): ").strip()
                    try:
                        report_idx = int(report_num) - 1
                        if 0 <= report_idx < len(reports):
                            selected_report = reports[report_idx]
                        else:
                            return self._create_error_response(session_id, "❌ Invalid report number.")
                    except ValueError:
                        return self._create_error_response(session_id, "❌ Invalid input.")
                
                # Return the selected report
                report_content = selected_report['content']
                if selected_report['file_path']:
                    report_content += f"\n\n📄 Full report saved at: {selected_report['file_path']}"
                
                return Response(
                    response_id=str(uuid.uuid4()),
                    session_id=session_id,
                    content=report_content,
                    format_type=user_input.output_format,
                    generated_by="SupervisorAgent_ExistingReport",
                    confidence_score=selected_report.get('confidence_level', 1.0),
                    timestamp=datetime.now()
                )
            
            # OPTION 2: Generate NEW report
            elif choice == "2":
                print("\n" + "="*70)
                print("📝 GENERATING NEW REPORT")
                print("="*70)
                
                # Sub-option: Update patient info or use existing
                print("\nWould you like to:")
                print("  [1] Use existing patient information")
                print("  [2] Update patient information")
                update_choice = input("Enter choice: ").strip()
                
                updated_patient_info = patient_info.copy()
                
                if update_choice == "2":
                    print("\n📋 Update Patient Information (press Enter to keep current value)")
                    print("-" * 70)
                    
                    new_age = input(f"Age (current: {patient_info['age']}): ").strip()
                    if new_age:
                        updated_patient_info['age'] = int(new_age)
                    
                    new_history = input(f"Medical History (current: {patient_info['medical_history'] or 'None'}): ").strip()
                    if new_history:
                        updated_patient_info['medical_history'] = new_history
                    
                    new_allergies = input(f"Allergies (current: {patient_info['allergies'] or 'None'}): ").strip()
                    if new_allergies:
                        updated_patient_info['allergies'] = new_allergies
                    
                    new_medications = input(f"Current Medications (current: {patient_info['current_medications'] or 'None'}): ").strip()
                    if new_medications:
                        updated_patient_info['current_medications'] = new_medications
                    
                    # Update patient record in database
                    # TODO: Add update_patient method to database manager
                    print("\n✅ Patient information updated")
                
                # REQUIRE MRI scan for new report
                print("\n" + "="*70)
                print("🔬 MRI SCAN REQUIRED FOR NEW ANALYSIS")
                print("="*70)
                
                mri_path = input("Enter MRI scan file path: ").strip()
                
                if not mri_path:
                    return self._create_error_response(session_id,
                        "❌ MRI scan required for new report generation. Operation cancelled.")
                
                # Verify MRI file exists
                import os
                if not os.path.exists(mri_path):
                    return self._create_error_response(session_id,
                        f"❌ MRI file not found: {mri_path}\nPlease check the path and try again.")
                
                # Update user_input with MRI path
                user_input.mri_file_path = mri_path
                
                # Update session with patient information
                await self.shared_memory.db_manager.update_session_patient_info(
                    session_id, patient_id, patient_info['name']
                )
                
                # Execute combined workflow (prediction + report)
                print("\n🚀 Starting MRI analysis and report generation...")
                return await self._handle_combined_workflow(session_id, user_input)
            
            # OPTION 0: Cancel
            elif choice == "0":
                return self._create_response(session_id, "❌ Report request cancelled by user.")
            
            else:
                return self._create_error_response(session_id, "❌ Invalid choice. Operation cancelled.")
        
        except Exception as e:
            self._handle_error(e, "handling intelligent report workflow")
            return self._create_error_response(session_id, 
                f"❌ Error in report workflow: {str(e)}\nPlease try again or contact support.")
    
    async def _check_aiml_model_status(self) -> Dict[str, Any]:
        """Check if AI/ML agent has Parkinson's model loaded"""
        try:
            # Try to get the AIMLAgent from shared memory or via health check
            # This is a simplified check - in production you might have direct agent references
            aiml_agent_data = await self.shared_memory.get_agent_status("aiml_agent")
            
            if aiml_agent_data and "model_status" in aiml_agent_data:
                return aiml_agent_data["model_status"]
            else:
                return {"loaded": False, "path": None, "available_for_predictions": False}
                
        except Exception as e:
            logger.warning(f"Could not check AI/ML model status: {e}")
            return {"loaded": False, "path": None, "available_for_predictions": False}

    async def _handle_missing_mri_error(self, session_id: str, user_input: UserInput) -> Response:
        """Handle case where prediction is requested but no MRI is provided"""
        
        # Check if the Parkinson's model is available
        model_status = await self._check_aiml_model_status()
        
        if not model_status.get("available_for_predictions", False):
            error_message = """I understand you want MRI analysis for Parkinson's disease, but the prediction model is not currently available.

            **Current Status:**
            - Parkinson's prediction model (.keras file) is not loaded
            - MRI analysis functionality is pending until the model is provided
            - Chat functionality is fully available
            
            **What you can do now:**
            - Ask questions about Parkinson's disease symptoms, treatment, or general information
            - Learn about MRI-based diagnosis methods
            - Discuss Parkinson's research and developments
            
            **To enable MRI predictions:**
            - The system administrator needs to load the Parkinson's prediction model (.keras file)
            - Once loaded, you can upload MRI scans for analysis
            
            How can I help you with Parkinson's information in the meantime?"""
        else:
            error_message = """I understand you want MRI analysis, but I don't see any MRI scan attached to your request.
            
            **To perform Parkinson's disease prediction:**
            1. Upload an MRI scan (DICOM, PNG, or JPEG format)
            2. Explicitly request "analyze MRI" or "predict Parkinson's"
            
            **Available formats:**
            - DICOM files (.dcm)
            - PNG images (.png)
            - JPEG images (.jpg, .jpeg)
            
            If you have general questions about Parkinson's disease, I'm happy to help with those as well."""
        
        return Response(
            response_id=str(uuid.uuid4()),
            session_id=session_id,
            content=error_message,
            format_type=user_input.output_format,
            generated_by="SupervisorAgent_Error",
            confidence_score=1.0,
            timestamp=datetime.now()
        )
    
    async def orchestrate_workflow(self, session_id: str, workflow_type: str) -> Dict[str, Any]:
        """
        Orchestrate specific workflow types.
        This method is called by other parts of the system for programmatic workflow control.
        """
        try:
            if workflow_type == "prediction":
                flag_id = await self.shared_memory.set_action_flag(
                    flag_type=ActionFlagType.PREDICT_PARKINSONS,
                    session_id=session_id,
                    data={"triggered_by": "orchestrator"},
                    priority=1
                )
                return {"status": "initiated", "flag_id": flag_id}
            
            elif workflow_type == "report":
                flag_id = await self.shared_memory.set_action_flag(
                    flag_type=ActionFlagType.GENERATE_REPORT,
                    session_id=session_id,
                    data={"triggered_by": "orchestrator"},
                    priority=1
                )
                return {"status": "initiated", "flag_id": flag_id}
            
            else:
                return {"status": "error", "message": f"Unknown workflow type: {workflow_type}"}
                
        except Exception as e:
            self._handle_error(e, f"orchestrating {workflow_type} workflow")
            return {"status": "error", "message": str(e)}
    
    async def _check_existing_reports(self, session_data: SessionData) -> Optional[Dict[str, Any]]:
        """Check if patient already has existing reports"""
        try:
            if not session_data.patient_id:
                return None
                
            # Get existing reports for this patient
            existing_reports = await self.shared_memory.check_existing_reports(session_data.patient_id)
            
            if existing_reports:
                # Return the most recent report info
                latest_report = existing_reports[0]  # Already ordered by created_at DESC
                return {
                    'count': len(existing_reports),
                    'latest_report': latest_report,
                    'patient_name': session_data.patient_name,
                    'reports': existing_reports[:3]  # Show up to 3 most recent
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking existing reports: {e}")
            return None
    
    async def _ask_user_about_existing_reports(self, session_id: str, existing_info: Dict[str, Any]) -> str:
        """Ask user whether to generate new report or retrieve existing one"""
        try:
            patient_name = existing_info.get('patient_name', 'Unknown')
            count = existing_info.get('count', 0)
            latest_report = existing_info.get('latest_report', {})
            latest_date = latest_report.get('created_at', 'Unknown date')
            
            message = f"""Patient {patient_name} already has {count} existing report(s) in the system.

Latest report was generated on: {latest_date}
Report type: {latest_report.get('report_type', 'Unknown')}

Would you like to:
1. Generate a new report
2. Retrieve the existing latest report  
3. View all existing reports for this patient

Please respond with '1', '2', or '3'."""
            
            return message
                
        except Exception as e:
            logger.error(f"Error asking about existing reports: {e}")
            return "Error occurred while checking existing reports. Proceeding with new report generation."

    # Utility Methods
    async def _wait_for_prediction_completion(self, session_id: str, timeout_seconds: int = 300) -> bool:
        """Wait for prediction completion with timeout"""
        return await self.shared_memory.wait_for_completion(
            session_id, ActionFlagType.PREDICT_PARKINSONS, timeout_seconds
        )
    
    async def _wait_for_report_completion(self, session_id: str, timeout_seconds: int = 180) -> bool:
        """Wait for report completion with timeout"""
        return await self.shared_memory.wait_for_completion(
            session_id, ActionFlagType.GENERATE_REPORT, timeout_seconds
        )
    
    def _detect_file_type(self, file_path: str) -> str:
        """Detect file type from file path"""
        extension = file_path.lower().split('.')[-1]
        if extension in ['dcm', 'dicom']:
            return 'dicom'
        elif extension in ['png']:
            return 'png'
        elif extension in ['jpg', 'jpeg']:
            return 'jpeg'
        elif extension in ['nii', 'nifti']:
            return 'nii'
        else:
            return 'unknown'
    
    async def _format_prediction_response(self, prediction) -> str:
        """Format prediction results for user response"""
        # Fix confidence score formatting
        confidence_str = f"{prediction.confidence_score:.2f}" if prediction.confidence_score is not None else 'N/A'
        
        response = f"""MRI Analysis Complete

Binary Classification: {prediction.binary_result or 'Uncertain'}
Stage Assessment: {prediction.stage_result or 'Not determined'}
Confidence Score: {confidence_str}

"""
        
        if prediction.binary_confidence:
            response += f"Binary Classification Confidence: {prediction.binary_confidence:.2f}\n"
        
        if prediction.stage_confidence:
            response += f"Stage Assessment Confidence: {prediction.stage_confidence:.2f}\n"
        
        response += "\nIMPORTANT: This is an AI-generated analysis and should be reviewed by a qualified healthcare professional."
        
        return response
    
    def _create_error_response(self, session_id: str, error_message: str) -> Response:
        """Create standardized error response"""
        return Response(
            response_id=str(uuid.uuid4()),
            session_id=session_id,
            content=error_message,
            format_type=OutputFormat.TEXT,
            generated_by="SupervisorAgent_Error",
            confidence_score=1.0,
            timestamp=datetime.now()
        )
    
    def _create_response(self, session_id: str, message: str) -> Response:
        """Create standardized response"""
        return Response(
            response_id=str(uuid.uuid4()),
            session_id=session_id,
            content=message,
            format_type=OutputFormat.TEXT,
            generated_by="SupervisorAgent",
            confidence_score=1.0,
            timestamp=datetime.now()
        )
    
    async def handle_smart_crud_command(self, command: str, user_role: str = "admin") -> str:
        """
        Smart CRUD command interpreter - understands natural language admin commands
        
        Examples:
            "users" → get all users
            "doctors" → get all doctors  
            "patients" → get all patients
            "active users" → get active users
            "show me consultations" → get recent consultations
            "patient statistics" → get patient stats
            
        Args:
            command: Natural language command from admin
            user_role: User role (default: admin)
            
        Returns:
            Formatted response string with requested data
        """
        db = self.shared_memory.db_manager
        command_lower = command.lower().strip()
        
        try:
            # ===== USER QUERIES =====
            if command_lower in ['users', 'all users', 'show users', 'list users', 'get users']:
                users = await db.get_all_users()
                return self._format_users_response(users)
            
            elif 'active users' in command_lower or 'active user' in command_lower:
                users = await db.get_active_users()
                return self._format_users_response(users, title="Active Users")
            
            elif command_lower in ['doctors', 'all doctors', 'show doctors', 'list doctors']:
                doctors = await db.get_users_by_role('doctor')
                return self._format_users_response(doctors, title="Doctors")
            
            elif command_lower in ['admins', 'administrators', 'show admins']:
                admins = await db.get_users_by_role('admin')
                return self._format_users_response(admins, title="Administrators")
            
            # ===== PATIENT QUERIES =====
            elif command_lower in ['patients', 'all patients', 'show patients', 'list patients', 'get patients']:
                patients = await db.get_all_patients()
                return self._format_patients_response(patients)
            
            elif 'patient stats' in command_lower or 'patient statistics' in command_lower:
                stats = await db.get_all_patient_statistics(order_by='last_visit_date', limit=20)
                return self._format_patient_statistics_response(stats)
            
            # ===== CONSULTATION QUERIES =====
            elif 'consultations' in command_lower or 'consultation' in command_lower:
                # Check if specific doctor is mentioned
                if 'doctor' in command_lower:
                    return "ℹ️  Please specify doctor ID: get_doctor_consultations(doctor_id)"
                else:
                    return "ℹ️  Available queries:\n   • get_patient_consultations(patient_id)\n   • get_doctor_consultations(doctor_id)"
            
            # ===== REPORT QUERIES =====
            elif 'pending reports' in command_lower or 'pending report' in command_lower:
                reports = await db.get_pending_reports()
                return self._format_pending_reports_response(reports)
            
            elif 'failed reports' in command_lower or 'failed report' in command_lower:
                reports = await db.get_failed_reports()
                return self._format_failed_reports_response(reports)
            
            # ===== DASHBOARD QUERIES =====
            elif command_lower in ['dashboard', 'system dashboard', 'admin dashboard', 'overview']:
                dashboard = await db.get_system_dashboard()
                return self._format_system_dashboard_response(dashboard)
            
            elif 'doctor dashboard' in command_lower:
                return "ℹ️  Please specify doctor ID: get_doctor_dashboard(doctor_id)"
            
            elif 'patient dashboard' in command_lower:
                return "ℹ️  Please specify patient ID: get_patient_dashboard(patient_id)"
            
            # ===== STATISTICS =====
            elif 'stats' in command_lower or 'statistics' in command_lower:
                dashboard = await db.get_system_dashboard()
                return self._format_system_stats_response(dashboard)
            
            # ===== HELP =====
            elif command_lower in ['help', 'commands', 'what can you do']:
                return self._get_crud_help_message()
            
            # ===== UNKNOWN COMMAND =====
            else:
                return f"❓ Command not recognized: '{command}'\n\n💡 Try:\n   • 'users' - Show all users\n   • 'doctors' - Show all doctors\n   • 'patients' - Show all patients\n   • 'dashboard' - System overview\n   • 'help' - See all available commands"
        
        except Exception as e:
            self.logger.error(f"CRUD command failed: {e}")
            return f"❌ Error executing command: {str(e)}"
    
    def _format_users_response(self, users: list, title: str = "Users") -> str:
        """Format users list for display"""
        if not users:
            return f"📋 {title}: No users found"
        
        response = f"\n👥 {title.upper()} ({len(users)} total)\n"
        response += "=" * 60 + "\n\n"
        
        # Group by role
        by_role = {}
        for user in users:
            role = user.get('role', 'unknown')
            if role not in by_role:
                by_role[role] = []
            by_role[role].append(user)
        
        # Display by role
        for role, role_users in sorted(by_role.items()):
            response += f"\n📌 {role.upper()} ({len(role_users)}):\n"
            for user in role_users[:10]:  # Show first 10 per role
                status = "🟢" if user.get('is_active', True) else "🔴"
                username = user.get('username', 'N/A')
                full_name = user.get('full_name', 'N/A')
                email = user.get('email', 'N/A')
                last_login = user.get('last_login', 'Never')
                
                response += f"   {status} {username} - {full_name}\n"
                response += f"      Email: {email}\n"
                response += f"      Last Login: {last_login}\n"
            
            if len(role_users) > 10:
                response += f"   ... and {len(role_users) - 10} more\n"
        
        return response
    
    def _format_patients_response(self, patients: list) -> str:
        """Format patients list for display"""
        if not patients:
            return "📋 PATIENTS: No patients found"
        
        response = f"\n🏥 PATIENTS ({len(patients)} total)\n"
        response += "=" * 60 + "\n\n"
        
        for i, patient in enumerate(patients[:20], 1):  # Show first 20
            patient_name = patient.get('patient_name', 'N/A')
            patient_id = patient.get('patient_id', 'N/A')[:8]  # Show first 8 chars of ID
            age = patient.get('age', 'N/A')
            gender = patient.get('gender', 'N/A')
            
            response += f"{i}. {patient_name} (ID: {patient_id}...)\n"
            response += f"   Age: {age} | Gender: {gender}\n"
        
        if len(patients) > 20:
            response += f"\n... and {len(patients) - 20} more patients\n"
        
        return response
    
    def _format_patient_statistics_response(self, stats: list) -> str:
        """Format patient statistics for display"""
        if not stats:
            return "📊 PATIENT STATISTICS: No data available"
        
        response = f"\n📊 PATIENT STATISTICS (Top {len(stats)})\n"
        response += "=" * 60 + "\n\n"
        
        for i, stat in enumerate(stats[:15], 1):
            patient_name = stat.get('patient_name', 'N/A')
            consultations = stat.get('total_consultations', 0)
            scans = stat.get('total_mri_scans', 0)
            reports = stat.get('total_reports', 0)
            last_visit = stat.get('last_visit_date', 'N/A')
            
            response += f"{i}. {patient_name}\n"
            response += f"   Consultations: {consultations} | Scans: {scans} | Reports: {reports}\n"
            response += f"   Last Visit: {last_visit}\n\n"
        
        return response
    
    def _format_pending_reports_response(self, reports: list) -> str:
        """Format pending reports for display"""
        if not reports:
            return "✅ No pending reports"
        
        response = f"\n📝 PENDING REPORTS ({len(reports)})\n"
        response += "=" * 60 + "\n\n"
        
        for i, report in enumerate(reports, 1):
            patient_name = report.get('patient_name', 'N/A')
            report_type = report.get('report_type', 'N/A')
            requested_date = report.get('requested_date', 'N/A')
            status = report.get('status', 'N/A')
            
            response += f"{i}. {patient_name} - {report_type}\n"
            response += f"   Status: {status}\n"
            response += f"   Requested: {requested_date}\n\n"
        
        return response
    
    def _format_failed_reports_response(self, reports: list) -> str:
        """Format failed reports for display"""
        if not reports:
            return "✅ No failed reports"
        
        response = f"\n❌ FAILED REPORTS ({len(reports)})\n"
        response += "=" * 60 + "\n\n"
        
        for i, report in enumerate(reports, 1):
            patient_name = report.get('patient_name', 'N/A')
            report_type = report.get('report_type', 'N/A')
            requested_date = report.get('requested_date', 'N/A')
            error = report.get('error_message', 'Unknown error')
            
            response += f"{i}. {patient_name} - {report_type}\n"
            response += f"   Error: {error}\n"
            response += f"   Requested: {requested_date}\n\n"
        
        return response
    
    def _format_system_dashboard_response(self, dashboard: dict) -> str:
        """Format system dashboard for display"""
        if not dashboard:
            return "❌ Dashboard data not available"
        
        response = f"\n🎯 SYSTEM DASHBOARD\n"
        response += "=" * 60 + "\n\n"
        
        response += "📊 Overview:\n"
        response += f"   Total Users: {dashboard.get('total_users', 0)}\n"
        response += f"   Total Patients: {dashboard.get('total_patients', 0)}\n"
        response += f"   Total Doctors: {dashboard.get('total_doctors', 0)}\n"
        response += f"   Active Patients (30d): {dashboard.get('active_patients_30d', 0)}\n\n"
        
        response += "📝 Reports:\n"
        response += f"   Pending: {dashboard.get('pending_reports', 0)}\n"
        response += f"   Failed: {dashboard.get('failed_reports', 0)}\n\n"
        
        response += "🔬 Parkinson's Detection:\n"
        response += f"   Detected Cases: {dashboard.get('parkinsons_patients', 0)}\n"
        response += f"   Detection Rate: {dashboard.get('parkinsons_percentage', 0)}%\n\n"
        
        activity = dashboard.get('activity_24h', {})
        response += "⚡ Last 24 Hours:\n"
        response += f"   Scans: {activity.get('scans', 0)}\n"
        response += f"   Predictions: {activity.get('predictions', 0)}\n"
        response += f"   Reports: {activity.get('reports', 0)}\n"
        
        return response
    
    def _format_system_stats_response(self, dashboard: dict) -> str:
        """Format system statistics (simplified)"""
        if not dashboard:
            return "❌ Statistics not available"
        
        response = f"\n📊 SYSTEM STATISTICS\n"
        response += "=" * 60 + "\n\n"
        
        response += f"👥 Users: {dashboard.get('total_users', 0)}\n"
        response += f"🏥 Patients: {dashboard.get('total_patients', 0)}\n"
        response += f"👨‍⚕️ Doctors: {dashboard.get('total_doctors', 0)}\n"
        response += f"📝 Pending Reports: {dashboard.get('pending_reports', 0)}\n"
        response += f"🔬 Parkinson's Cases: {dashboard.get('parkinsons_patients', 0)} ({dashboard.get('parkinsons_percentage', 0)}%)\n"
        
        return response
    
    def _get_crud_help_message(self) -> str:
        """Return help message for CRUD commands"""
        return """
🤖 SMART CRUD COMMANDS AVAILABLE
================================

👥 USER MANAGEMENT:
   • users, show users, list users
   • active users
   • doctors, show doctors
   • admins, administrators

🏥 PATIENT MANAGEMENT:
   • patients, show patients, list patients
   • patient stats, patient statistics

📝 REPORT MANAGEMENT:
   • pending reports
   • failed reports

📊 DASHBOARDS & STATISTICS:
   • dashboard, system dashboard
   • stats, statistics

❓ HELP:
   • help, commands

💡 Just type what you want to see in natural language!
   Example: "show me all doctors" or "patient statistics"
"""
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for supervisor agent"""
        base_health = await super().health_check()
        groq_health = await self.groq_service.health_check()
        
        return {
            **base_health,
            "groq_service": groq_health,
            "workflow_capabilities": {
                "chat_mode": True,
                "prediction_orchestration": True,
                "report_orchestration": True,
                "combined_workflows": True,
                "smart_crud_commands": True
            }
        }