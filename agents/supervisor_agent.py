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
            # Create UserInput object from simple message
            user_input = UserInput(
                session_id=metadata.get("session_id", str(uuid.uuid4())),
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
            return self._create_error_response(user_input.session_id if 'user_input' in locals() else "unknown", str(e))
    
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
        Handle chat-only requests without prediction or reporting.
        Uses Groq API for conversational responses.
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
            
            # Use Groq service for chat response
            chat_response = await self.groq_service.handle_chat_request(
                user_input.content, session_context
            )
            
            return Response(
                response_id=str(uuid.uuid4()),
                session_id=user_input.session_id,
                content=chat_response,
                format_type=user_input.output_format,
                generated_by="SupervisorAgent_Chat",
                confidence_score=0.8,  # High confidence for chat responses
                timestamp=datetime.now()
            )
            
        except Exception as e:
            self._handle_error(e, "handling chat request")
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
        """Handle report generation when prediction data already exists"""
        try:
            # Check if prediction data exists for this session or user
            prediction = await self.shared_memory.get_latest_prediction(session_id)
            
            if not prediction:
                return self._create_error_response(session_id,
                    "No previous MRI analysis found. Please upload an MRI scan for analysis first.")
            
            # Check for existing reports before generating new one
            session_data = await self.shared_memory.get_session_data(session_id)
            if session_data:
                existing_reports_info = await self._check_existing_reports(session_data)
                if existing_reports_info:
                    # Ask user about existing reports
                    existing_reports_message = await self._ask_user_about_existing_reports(session_id, existing_reports_info)
                    return self._create_response(session_id, existing_reports_message)

            # Set GENERATE_REPORT flag
            flag_id = await self.shared_memory.set_action_flag(
                flag_type=ActionFlagType.GENERATE_REPORT,
                session_id=session_id,
                data={
                    "report_type": "standalone",
                    "user_request": user_input.content
                },
                priority=1
            )
            
            # Wait for report completion
            report_completed = await self._wait_for_report_completion(session_id)
            
            if report_completed:
                reports = await self.shared_memory.get_reports(session_id)
                if reports:
                    latest_report = reports[-1]
                    
                    return Response(
                        response_id=str(uuid.uuid4()),
                        session_id=session_id,
                        content=latest_report['content'],
                        format_type=user_input.output_format,
                        generated_by="SupervisorAgent_Report",
                        confidence_score=latest_report.get('confidence_level', 0.8),
                        timestamp=datetime.now()
                    )
            
            return self._create_error_response(session_id, "Report generation failed.")
            
        except Exception as e:
            self._handle_error(e, "handling report-only workflow")
            return self._create_error_response(session_id, "Error generating report.")
    
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
    
    async def process_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a task assigned to the supervisor agent.
        Note: Supervisor primarily handles user input via process_user_input.
        This method handles internal system tasks.
        """
        task_type = task_data.get('type', 'unknown')
        session_id = task_data.get('session_id', 'system')
        
        try:
            if task_type == 'system_status':
                return await self.health_check()
            
            elif task_type == 'session_cleanup':
                # Clean up old sessions
                cutoff_time = datetime.now() - timedelta(hours=24)
                await self.shared_memory.cleanup_old_sessions(cutoff_time)
                return {'status': 'completed', 'action': 'session_cleanup'}
            
            elif task_type == 'flag_status_report':
                # Report on current action flags
                pending = await self.shared_memory.get_pending_action_flags()
                claimed = await self.shared_memory.get_claimed_action_flags()
                completed = await self.shared_memory.get_completed_action_flags()
                
                return {
                    'status': 'completed',
                    'flag_summary': {
                        'pending': len(pending),
                        'claimed': len(claimed), 
                        'completed': len(completed)
                    }
                }
            
            else:
                logger.warning(f"Unknown task type for supervisor: {task_type}")
                return {
                    'status': 'failed',
                    'error': f'Unknown task type: {task_type}'
                }
                
        except Exception as e:
            logger.error(f"Error processing supervisor task {task_type}: {e}")
            return {
                'status': 'failed',
                'error': str(e)
            }
    
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
                "combined_workflows": True
            }
        }