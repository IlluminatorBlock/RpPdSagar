"""
RAG Agent for Parkinson's Multiagent System

This agent specializes in report generation and knowledge retrieval.
It ONLY generates reports when GENERATE_REPORT flag is set in shared memory.
"""

import asyncio
import logging
import uuid
import os
from typing import Dict, List, Optional, Any
from datetime import datetime

from models.agent_interfaces import ReportAgent
from models.data_models import (
    ActionFlagType, MedicalReport, KnowledgeEntry
)
from services.groq_service import GroqService
from utils.pdf_generator import pdf_generator

# Configure logging
logger = logging.getLogger(__name__)


class RAGAgent(ReportAgent):
    """
    RAG (Retrieval-Augmented Generation) Agent for medical report generation.
    
    Key Requirements:
    1. Monitors GENERATE_REPORT flag only
    2. Retrieves prediction + session data from shared memory
    3. Generates reports when explicitly requested
    4. Stores report in shared memory and sets REPORT_COMPLETE flag
    5. Never generates reports automatically - only on explicit flags
    """
    
    def __init__(self, shared_memory, groq_service: GroqService, embeddings_manager, config: Dict[str, Any]):
        super().__init__(shared_memory, config, "rag_agent")
        self.groq_service = groq_service
        self.embeddings_manager = embeddings_manager
        
        # Knowledge base configuration
        self.knowledge_base_size = 0
        self.embedding_dimension = config.get('embedding_dimension', 768)
        
        # Report generation statistics
        self.reports_generated = 0
        self.total_generation_time = 0.0
        
        # Report templates and configurations
        self.report_templates = {
            'comprehensive': 'full_medical_report',
            'summary': 'brief_summary',
            'patient_friendly': 'patient_report',
            'clinical': 'clinical_notes'
        }
    
    async def initialize(self) -> None:
        """Initialize RAG Agent and start background tasks"""
        self.logger.debug("[LIFECYCLE] Initializing RAGAgent")
        
        # Call parent initialize first
        await super().initialize()
        
        # Initialize Groq service if needed
        if not self.groq_service.session:
            await self.groq_service.initialize()
        
        # Initialize knowledge base
        await self._initialize_knowledge_base()
        
        self.logger.info("RAG Agent initialized - monitoring for GENERATE_REPORT flags")
    
    async def shutdown(self) -> None:
        """Shutdown RAG Agent and cleanup resources"""
        self.logger.debug("[LIFECYCLE] Shutting down RAGAgent")
        
        # Cleanup embeddings manager if needed
        if hasattr(self.embeddings_manager, 'shutdown'):
            await self.embeddings_manager.shutdown()
        
        await super().shutdown()
        self.logger.info("RAG Agent shutdown completed")
    
    async def process_task(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process RAG tasks"""
        self.logger.debug(f"[TASK] RAGAgent processing {event_type}")
        
        if event_type.startswith('flag_created_GENERATE_REPORT'):
            return await self._handle_report_flag(payload)
        elif event_type == "health_check":
            return await self.health_check()
        else:
            return await super().process_task(event_type, payload)
    
    async def start_monitoring(self) -> None:
        """Legacy method for main.py compatibility - monitoring starts in initialize()"""
        self.logger.info("RAG Agent monitoring confirmed - already started in initialize()")
    
    # Legacy methods for backward compatibility
    async def start(self) -> None:
        """Legacy method - use initialize() instead"""
        await self.initialize()
    
    async def stop(self) -> None:
        """Legacy method - use shutdown() instead"""
        await self.shutdown()
    
    async def _initialize_knowledge_base(self):
        """Initialize medical knowledge base with comprehensive document loading"""
        try:
            # First load any existing documents from directory
            logger.info("Loading medical documents from knowledge base...")
            document_stats = await self.embeddings_manager.load_documents_from_directory()
            
            # Load knowledge entries from database
            knowledge_entries = await self.shared_memory.db_manager.search_knowledge_entries(limit=100)
            self.knowledge_base_size = len(knowledge_entries) + document_stats.get('total_chunks', 0)
            
            if document_stats.get('total_chunks', 0) > 0:
                logger.info(f"Loaded {document_stats['total_chunks']} chunks from {document_stats['loaded_files']} medical documents")
            
            if self.knowledge_base_size == 0:
                logger.warning("No documents found - loading default medical knowledge")
                await self._load_default_knowledge()
            else:
                logger.info(f"Knowledge base initialized with {self.knowledge_base_size} entries")
                
                # Add default knowledge to supplement document-based knowledge
                await self._load_default_knowledge()
            
        except Exception as e:
            logger.error(f"Failed to initialize knowledge base: {e}")
            await self._load_default_knowledge()
    
    async def _load_default_knowledge(self):
        """Load default Parkinson's medical knowledge"""
        default_knowledge = [
            {
                'title': 'Parkinson\'s Disease Overview',
                'content': 'Parkinson\'s disease is a progressive neurodegenerative disorder affecting movement, caused by loss of dopamine-producing neurons in the substantia nigra.',
                'category': 'overview',
                'source_type': 'medical_guideline',
                'credibility_score': 0.95
            },
            {
                'title': 'Hoehn and Yahr Scale',
                'content': 'The Hoehn and Yahr scale is used to describe symptom progression: Stage 1 (unilateral symptoms), Stage 2 (bilateral symptoms), Stage 3 (postural instability), Stage 4 (significant disability), Stage 5 (wheelchair bound).',
                'category': 'staging',
                'source_type': 'clinical_guideline',
                'credibility_score': 0.98
            },
            {
                'title': 'Parkinson\'s Treatment Options',
                'content': 'Treatment includes dopamine replacement therapy (levodopa), dopamine agonists, MAO-B inhibitors, physical therapy, occupational therapy, and in advanced cases, deep brain stimulation.',
                'category': 'treatment',
                'source_type': 'clinical_guideline',
                'credibility_score': 0.96
            },
            {
                'title': 'Early Parkinson\'s Symptoms',
                'content': 'Early symptoms may include tremor at rest, bradykinesia (slowness of movement), rigidity, postural instability, and non-motor symptoms like loss of smell, sleep disorders, and depression.',
                'category': 'symptoms',
                'source_type': 'medical_journal',
                'credibility_score': 0.94
            }
        ]
        
        for knowledge_data in default_knowledge:
            knowledge_entry = KnowledgeEntry(
                entry_id=str(uuid.uuid4()),
                title=knowledge_data['title'],
                content=knowledge_data['content'],
                category=knowledge_data['category'],
                source_type=knowledge_data['source_type'],
                credibility_score=knowledge_data['credibility_score']
            )
            
            await self.shared_memory.db_manager.store_knowledge_entry(knowledge_entry)
        
        self.knowledge_base_size = len(default_knowledge)
        logger.info(f"Loaded {len(default_knowledge)} default knowledge entries")
    
    async def _setup_event_subscriptions(self):
        """Setup event subscriptions specific to report generation"""
        await super()._setup_event_subscriptions()
        
        # Subscribe specifically to GENERATE_REPORT flags
        report_events = [
            f"flag_created_{ActionFlagType.GENERATE_REPORT.value}",
            f"flag_claimed_{ActionFlagType.GENERATE_REPORT.value}"
        ]
        
        self.shared_memory.subscribe_to_events(
            f"{self.agent_id}_reports",
            report_events,
            self._handle_report_event
        )
        
        logger.info("RAG Agent subscribed to report generation events")
    
    async def _handle_report_event(self, event: Dict[str, Any]):
        """Handle report generation flag events"""
        try:
            event_type = event.get('event_type')
            data = event.get('data', {})
            session_id = event.get('session_id')
            
            if event_type == f"flag_created_{ActionFlagType.GENERATE_REPORT.value}":
                flag_id = data.get('flag_id')
                
                if flag_id and session_id:
                    logger.info(f"Detected GENERATE_REPORT flag {flag_id} for session {session_id}")
                    
                    # Claim the flag for processing
                    claimed = await self.shared_memory.claim_action_flag(flag_id, self.agent_id)
                    
                    if claimed:
                        logger.info(f"Claimed report generation flag {flag_id}")
                        await self._process_report_request(flag_id, session_id, data)
                    else:
                        logger.info(f"Failed to claim report flag {flag_id} - may be processed by another instance")
            
            self.last_activity = datetime.now()
            
        except Exception as e:
            self._handle_error(e, "handling report event")
    
    async def _process_report_request(self, flag_id: str, session_id: str, flag_data: Dict[str, Any]):
        """
        Process a report generation request triggered by GENERATE_REPORT flag.
        This is the ONLY way this agent generates reports.
        """
        start_time = datetime.now()
        
        try:
            logger.info(f"Starting report generation for session {session_id}")
            
            # Generate the medical report
            report_data = await self.generate_medical_report(session_id)
            
            # Determine report type from flag data
            report_type = flag_data.get('report_type', 'comprehensive')
            
            # Create medical report object
            medical_report = MedicalReport(
                report_id=str(uuid.uuid4()),
                session_id=session_id,
                prediction_id=report_data.get('prediction_id'),
                report_type=report_type,
                title=report_data.get('title', 'Medical Analysis Report'),
                content=report_data.get('content', ''),
                recommendations=report_data.get('recommendations', []),
                confidence_level=report_data.get('confidence_level', 0.8),
                disclaimer=report_data.get('disclaimer', 'This report is AI-generated and should be reviewed by a medical professional.'),
                metadata={
                    'generation_time': (datetime.now() - start_time).total_seconds(),
                    'knowledge_entries_used': report_data.get('knowledge_entries_count', 0),
                    'flag_id': flag_id
                }
            )
            
            # Store report in shared memory
            report_id = await self.shared_memory.store_report(medical_report)
            
            # Automatically generate PDF reports (both doctor and patient versions)
            try:
                logger.info(f"Automatically generating PDF reports for session {session_id}")
                
                # Generate doctor report
                doctor_pdf_path = await self.generate_pdf_report(session_id, None, "doctor")
                logger.info(f"Doctor PDF report generated: {doctor_pdf_path}")
                
                # Generate patient report  
                patient_pdf_path = await self.generate_pdf_report(session_id, None, "patient")
                logger.info(f"Patient PDF report generated: {patient_pdf_path}")
                
                # Update the medical report to include PDF paths
                medical_report.metadata['doctor_pdf_path'] = doctor_pdf_path
                medical_report.metadata['patient_pdf_path'] = patient_pdf_path
                medical_report.metadata['pdf_generated'] = True
                
            except Exception as pdf_error:
                logger.error(f"Failed to generate PDF reports for session {session_id}: {pdf_error}")
                medical_report.metadata['pdf_generated'] = False
                medical_report.metadata['pdf_error'] = str(pdf_error)
            
            # Complete the action flag
            await self.shared_memory.complete_action_flag(flag_id)
            
            # Set REPORT_COMPLETE flag
            await self.shared_memory.set_action_flag(
                flag_type=ActionFlagType.REPORT_COMPLETE,
                session_id=session_id,
                data={
                    'report_id': report_id,
                    'report_type': report_type,
                    'confidence_level': medical_report.confidence_level,
                    'processed_by': self.agent_id
                }
            )
            
            # Update statistics
            self.reports_generated += 1
            self.total_generation_time += medical_report.metadata['generation_time']
            
            logger.info(f"Successfully completed report generation for session {session_id}, report ID: {report_id}")
            
        except Exception as e:
            await self._fail_report_generation(flag_id, session_id, f"Report generation failed: {str(e)}")
            self._handle_error(e, f"processing report request {flag_id}")
    
    async def generate_medical_report(self, session_id: str) -> Dict[str, Any]:
        """
        Generate comprehensive medical report.
        Only called when GENERATE_REPORT flag is set.
        """
        try:
            logger.info(f"Generating medical report for session {session_id}")
            
            # Step 1: Retrieve session data with patient/doctor information
            session_data = await self.shared_memory.get_session_data(session_id)
            patient_id = session_data.patient_id if session_data else "Unknown"
            patient_name = session_data.patient_name if session_data else "Unknown Patient"
            doctor_id = session_data.doctor_id if session_data else "Unknown"
            doctor_name = session_data.doctor_name if session_data else "Unknown Doctor"
            
            # Step 2: Retrieve prediction data from shared memory
            prediction_data = await self._retrieve_prediction_data(session_id)
            
            # Step 3: Retrieve MRI scan information (exclude binary data)
            mri_scans_raw = await self.shared_memory.get_mri_data(session_id)
            mri_scans = [{k: v for k, v in mri.items() if k != 'binary_data'} for mri in mri_scans_raw]
            mri_info = "No MRI scan provided" if not mri_scans else f"MRI scan available (File: {mri_scans[0].get('original_filename', 'Unknown')})"
            
            # Step 4: Search knowledge base for relevant information
            knowledge_entries = await self._search_relevant_knowledge(prediction_data, session_id)
            
            # Step 5: Retrieve additional session context
            session_context = await self._get_session_context(session_id)
            
            # Step 6: Generate report using Groq service
            report_content = await self.groq_service.generate_medical_report(
                prediction_data, knowledge_entries, session_context
            )
            
            # Step 7: Generate patient-specific recommendations
            recommendations = await self.groq_service.synthesize_patient_recommendations(
                prediction_data, knowledge_entries
            )
            
            # Prepare full report data for formatting
            full_report_data = {
                'session_id': session_id,
                'patient_id': patient_id,
                'patient_name': patient_name,
                'doctor_id': doctor_id,
                'doctor_name': doctor_name,
                'mri_info': mri_info,
                'title': report_content.get('title', 'Parkinson\'s Disease Analysis Report'),
                'executive_summary': report_content.get('executive_summary', 'MRI analysis completed using AI-assisted evaluation.'),
                'clinical_findings': report_content.get('clinical_findings', 'Clinical findings based on AI analysis.'),
                'diagnostic_assessment': report_content.get('diagnostic_assessment', 'Assessment based on available data.'),
                'recommendations': recommendations,
                'disclaimer': report_content.get('disclaimer', 'This report is AI-generated and requires professional medical review.')
            }
            
            return {
                'session_id': session_id,
                'patient_id': patient_id,
                'patient_name': patient_name,
                'doctor_id': doctor_id,
                'doctor_name': doctor_name,
                'mri_info': mri_info,
                'prediction_id': prediction_data.get('prediction_id'),
                'title': full_report_data['title'],
                'content': self._format_report_content(full_report_data, "doctor"),  # Default to doctor format
                'patient_content': self._format_report_content(full_report_data, "patient"),  # Add patient version
                'recommendations': recommendations,
                'confidence_level': self._calculate_report_confidence(prediction_data, knowledge_entries),
                'disclaimer': full_report_data['disclaimer'],
                'knowledge_entries_count': len(knowledge_entries)
            }
            
        except Exception as e:
            logger.error(f"Error generating medical report for session {session_id}: {e}")
            raise

    async def generate_pdf_report(self, session_id: str, output_path: Optional[str] = None, report_type: str = "doctor") -> str:
        """
        Generate a PDF medical report for the given session.
        
        Args:
            session_id: Session identifier for the report
            output_path: Optional custom output path for the PDF file
            report_type: "doctor" or "patient" for different report styles
            
        Returns:
            Path to generated PDF file
        """
        try:
            logger.info(f"Generating {report_type} PDF report for session {session_id}")
            
            # Get session data with patient/doctor information
            session_data = await self.shared_memory.get_session_data(session_id)
            patient_id = session_data.patient_id if session_data else f"PID_{session_id[:8]}"
            patient_name = session_data.patient_name if session_data else "Unknown Patient"
            doctor_id = session_data.doctor_id if session_data else f"DID_{session_id[:8]}"
            doctor_name = session_data.doctor_name if session_data else "Dr. AI System"
            
            # Get MRI scan information (exclude binary data)
            mri_scans_raw = await self.shared_memory.get_mri_data(session_id)
            mri_scans = [{k: v for k, v in mri.items() if k != 'binary_data'} for mri in mri_scans_raw]
            mri_info = "No MRI scan provided" if not mri_scans else f"MRI scan available (File: {mri_scans[0].get('original_filename', 'Unknown')})"
            mri_file_path = mri_scans[0].get('file_path') if mri_scans else None
            
            # Get prediction data directly (don't regenerate report to avoid API limits)
            prediction_data = await self._retrieve_prediction_data(session_id)
            
            # Get existing report from database if available
            reports = await self.shared_memory.get_reports(session_id)
            latest_report = reports[-1] if reports else None
            
            # Prepare PDF report data with fallback content
            pdf_data = {
                'report_id': f"RPT_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                'session_id': session_id,
                'patient_id': patient_id,
                'patient_name': patient_name,
                'doctor_id': doctor_id,
                'doctor_name': doctor_name,
                'mri_info': mri_info,
                'mri_file_path': mri_file_path,
                'report_type': f'{report_type.title()} Report - Comprehensive Analysis',
                'executive_summary': self._get_executive_summary(prediction_data, report_type),
                'clinical_findings': self._extract_clinical_findings_for_pdf(prediction_data, report_type),
                'diagnostic_assessment': self._extract_diagnostic_assessment(None, prediction_data),
                'prediction': {
                    'binary_classification': prediction_data.get('binary_result', 'N/A'),
                    'stage_classification': prediction_data.get('stage_result', 'N/A'),
                    'confidence': prediction_data.get('confidence_score', 0.0),
                    'processing_time': prediction_data.get('processing_time', 0.0)
                },
                'recommendations': self._get_recommendations_for_pdf(prediction_data, report_type),
                'references': self._get_references_for_pdf(report_type),
                'report_for': report_type
            }
            
            # Determine output path
            if output_path is None:
                reports_dir = os.path.join('data', 'reports')
                os.makedirs(reports_dir, exist_ok=True)
                output_path = os.path.join(reports_dir, f"{report_type}_report_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
            
            # Ensure absolute path
            output_path = os.path.abspath(output_path)
            
            # Generate PDF using the PDF generator
            pdf_path = pdf_generator.generate_medical_report_pdf(pdf_data, output_path)
            
            # Verify file was created
            if os.path.exists(pdf_path):
                file_size = os.path.getsize(pdf_path)
                logger.info(f"PDF report generated successfully: {pdf_path} (Size: {file_size} bytes)")
            else:
                logger.error(f"PDF file was not created at: {pdf_path}")
                raise Exception(f"PDF file creation failed: {pdf_path}")
            
            return pdf_path
            
        except Exception as e:
            logger.error(f"Error generating PDF report for session {session_id}: {e}")
            raise

    def _extract_clinical_findings(self, report_data: Dict[str, Any], prediction_data: Dict[str, Any]) -> str:
        """Extract and format clinical findings for PDF"""
        findings = []
        
        # Add prediction results as clinical findings
        binary_result = prediction_data.get('binary_result', 'unknown')
        confidence = prediction_data.get('confidence_score', 0.0)
        
        if binary_result == 'parkinsons':
            findings.append(f"AI analysis indicates positive markers for Parkinson's disease (confidence: {confidence:.1%}).")
        elif binary_result == 'no_parkinsons':
            findings.append(f"AI analysis indicates negative markers for Parkinson's disease (confidence: {confidence:.1%}).")
        else:
            findings.append("AI analysis results are inconclusive. Manual review recommended.")
        
        # Add stage information if available
        stage_result = prediction_data.get('stage_result', 'unknown')
        if stage_result != 'unknown':
            findings.append(f"Estimated stage classification: {stage_result}")
        
        return " ".join(findings) if findings else "Clinical findings based on AI analysis of provided data."
    
    def _extract_diagnostic_assessment(self, report_data: Dict[str, Any], prediction_data: Dict[str, Any]) -> str:
        """Extract and format diagnostic assessment for PDF"""
        confidence = prediction_data.get('confidence_score', 0.0)
        
        if confidence > 0.8:
            assessment = "High confidence in AI analysis results. Recommend clinical correlation."
        elif confidence > 0.6:
            assessment = "Moderate confidence in AI analysis results. Additional evaluation may be beneficial."
        elif confidence > 0.4:
            assessment = "Low confidence in AI analysis results. Manual review strongly recommended."
        else:
            assessment = "Very low confidence in AI analysis results. Results should be interpreted with extreme caution."
        
        assessment += " This assessment is based on computational analysis and requires professional medical interpretation."
        return assessment
    
    def _extract_references(self, report_data: Dict[str, Any]) -> List[str]:
        """Extract medical references for PDF"""
        return [
            "Parkinson's Disease Clinical Guidelines (Movement Disorder Society)",
            "MRI Diagnostic Criteria for Neurodegenerative Diseases",
            "AI-Assisted Medical Imaging Analysis Standards",
            "Evidence-Based Parkinson's Disease Diagnosis Protocol"
        ]

    def _get_executive_summary(self, prediction_data: Dict[str, Any], report_type: str) -> str:
        """Generate executive summary based on report type"""
        binary_result = prediction_data.get('binary_result', 'unknown')
        confidence = prediction_data.get('confidence_score', 0.0)
        
        if report_type == "doctor":
            return f"""MRI analysis completed using AI-assisted evaluation with {confidence:.1%} confidence. 
Binary classification: {binary_result}. This report provides detailed findings for clinical review and decision-making. 
The analysis includes comprehensive feature extraction and model predictions for diagnostic consideration."""
        else:  # patient report
            if binary_result == 'parkinsons':
                return f"""Your MRI scan has been analyzed using advanced AI technology. The analysis suggests some indicators 
that may be associated with Parkinson's disease. Please discuss these results with your doctor, who will provide 
you with a complete explanation and next steps."""
            else:
                return f"""Your MRI scan has been analyzed using advanced AI technology. The analysis did not identify 
strong indicators of Parkinson's disease. Please discuss these results with your doctor for complete evaluation."""

    def _extract_clinical_findings_for_pdf(self, prediction_data: Dict[str, Any], report_type: str) -> str:
        """Extract clinical findings formatted for PDF based on report type"""
        binary_result = prediction_data.get('binary_result', 'unknown')
        confidence = prediction_data.get('confidence_score', 0.0)
        stage_result = prediction_data.get('stage_result', 'unknown')
        
        if report_type == "doctor":
            findings = []
            if binary_result == 'parkinsons':
                findings.append(f"AI analysis indicates positive markers for Parkinson's disease (confidence: {confidence:.1%}).")
                findings.append("Features analyzed include anatomical structures, intensity patterns, morphological characteristics, and texture analysis.")
            elif binary_result == 'no_parkinsons':
                findings.append(f"AI analysis indicates negative markers for Parkinson's disease (confidence: {confidence:.1%}).")
            else:
                findings.append("AI analysis results are inconclusive. Manual review recommended.")
            
            if stage_result != 'unknown':
                findings.append(f"Estimated stage classification: {stage_result} (Hoehn and Yahr scale).")
            
            findings.append("Recommendation: Clinical correlation required for definitive diagnosis.")
            return " ".join(findings)
        else:  # patient report
            if binary_result == 'parkinsons':
                return f"""The scan analysis shows some patterns that may be related to Parkinson's disease. 
This does not mean you definitely have Parkinson's disease. Your doctor will need to review these results 
along with your symptoms and medical history to make a proper diagnosis."""
            else:
                return f"""The scan analysis did not show strong patterns associated with Parkinson's disease. 
However, this is just one part of a complete medical evaluation. Your doctor will review all aspects 
of your health to provide you with the best care."""

    def _get_recommendations_for_pdf(self, prediction_data: Dict[str, Any], report_type: str) -> List[str]:
        """Get recommendations based on report type"""
        binary_result = prediction_data.get('binary_result', 'unknown')
        
        if report_type == "doctor":
            return [
                "Follow-up with movement disorder specialist for clinical correlation",
                "Consider DaTscan imaging for additional confirmation if clinically indicated",
                "Monitor patient symptoms for progression using standardized scales",
                "Implement lifestyle modifications and exercise therapy",
                "Consider neuropsychological evaluation if cognitive symptoms present"
            ]
        else:  # patient report
            if binary_result == 'parkinsons':
                return [
                    "Schedule a follow-up appointment with your doctor to discuss these results",
                    "Bring a list of any symptoms you've been experiencing",
                    "Continue taking your current medications as prescribed",
                    "Stay active with regular exercise as approved by your doctor",
                    "Consider joining a support group if recommended by your healthcare team"
                ]
            else:
                return [
                    "Schedule a follow-up appointment with your doctor to discuss these results",
                    "Continue with your regular health check-ups",
                    "Maintain a healthy lifestyle with regular exercise",
                    "Report any new symptoms to your healthcare provider",
                    "Follow your doctor's recommendations for ongoing care"
                ]

    def _get_references_for_pdf(self, report_type: str) -> List[str]:
        """Get references based on report type"""
        if report_type == "doctor":
            return [
                "Movement Disorder Society Clinical Diagnostic Criteria for Parkinson's Disease",
                "MRI-based Diagnostic Guidelines for Neurodegenerative Diseases",
                "AI-Assisted Medical Imaging: Best Practices and Validation",
                "Hoehn and Yahr Staging Scale for Parkinson's Disease"
            ]
        else:  # patient report
            return [
                "Parkinson's Disease Foundation Patient Resources",
                "Understanding MRI Scans: A Patient Guide",
                "Living with Neurological Conditions: Support and Information"
            ]
    
    async def _retrieve_prediction_data(self, session_id: str) -> Dict[str, Any]:
        """Retrieve prediction data from shared memory"""
        try:
            # Get the latest prediction for this session
            prediction = await self.shared_memory.get_latest_prediction(session_id)
            
            if not prediction:
                logger.warning(f"No prediction data found for session {session_id}")
                return {
                    'prediction_id': None,
                    'binary_result': 'no_prediction',
                    'stage_result': 'unknown',
                    'confidence_score': 0.0,
                    'status': 'no_prediction_available'
                }
            
            return {
                'prediction_id': prediction.prediction_id,
                'binary_result': prediction.binary_result,
                'stage_result': prediction.stage_result,
                'confidence_score': prediction.confidence_score,
                'binary_confidence': prediction.binary_confidence,
                'stage_confidence': prediction.stage_confidence,
                'uncertainty_metrics': prediction.uncertainty_metrics,
                'model_version': prediction.model_version,
                'processing_time': prediction.processing_time,
                'created_at': prediction.created_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error retrieving prediction data: {e}")
            return {'status': 'error', 'message': str(e)}
    
    async def search_knowledge_base(self, query: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search medical knowledge base for relevant information"""
        try:
            # Search knowledge entries in database
            knowledge_entries = await self.shared_memory.db_manager.search_knowledge_entries(
                category=category, limit=10
            )
            
            # For now, return all entries since we don't have semantic search implemented
            # In production, this would use vector similarity search
            return knowledge_entries
            
        except Exception as e:
            logger.error(f"Error searching knowledge base: {e}")
            return []
    
    async def _search_relevant_knowledge(self, prediction_data: Dict[str, Any], session_id: str) -> List[Dict[str, Any]]:
        """Search for knowledge relevant to the prediction results"""
        try:
            relevant_entries = []
            
            # Search based on prediction results
            binary_result = prediction_data.get('binary_result', '')
            stage_result = prediction_data.get('stage_result', '')
            
            # Get general Parkinson's information
            general_entries = await self.search_knowledge_base("parkinson", category=None)
            relevant_entries.extend(general_entries[:2])  # Top 2 general entries
            
            # Get stage-specific information if available
            if stage_result and stage_result != 'uncertain':
                stage_entries = await self.search_knowledge_base(f"stage {stage_result}", category="staging")
                relevant_entries.extend(stage_entries[:2])
            
            # Get treatment information
            treatment_entries = await self.search_knowledge_base("treatment", category="treatment")
            relevant_entries.extend(treatment_entries[:2])
            
            # Get symptom information
            symptom_entries = await self.search_knowledge_base("symptoms", category="symptoms")
            relevant_entries.extend(symptom_entries[:2])
            
            # Remove duplicates and limit to top 8 entries
            unique_entries = []
            seen_ids = set()
            
            for entry in relevant_entries:
                entry_id = entry.get('id')
                if entry_id not in seen_ids:
                    unique_entries.append(entry)
                    seen_ids.add(entry_id)
                    
                if len(unique_entries) >= 8:
                    break
            
            logger.info(f"Found {len(unique_entries)} relevant knowledge entries for session {session_id}")
            return unique_entries
            
        except Exception as e:
            logger.error(f"Error searching relevant knowledge: {e}")
            return []
    
    async def _get_session_context(self, session_id: str) -> Dict[str, Any]:
        """Get additional session context"""
        try:
            # Get session summary from shared memory
            session_summary = await self.shared_memory.get_session_summary(session_id)
            
            # Get MRI data but exclude binary data for JSON serialization
            mri_data = await self.shared_memory.get_mri_data(session_id)
            
            # Filter out binary data from MRI data to avoid JSON serialization issues
            clean_mri_data = []
            for mri in mri_data:
                clean_mri = {k: v for k, v in mri.items() if k != 'binary_data'}
                clean_mri_data.append(clean_mri)
            
            return {
                'session_id': session_id,
                'session_data': session_summary.get('session', {}),
                'mri_scans': clean_mri_data,
                'has_mri_data': len(clean_mri_data) > 0
            }
            
        except Exception as e:
            logger.warning(f"Error getting session context: {e}")
            return {'session_id': session_id}
    
    def _format_report_content(self, report_content: Dict[str, Any], report_type: str = "doctor") -> str:
        """Format the report content into a clean, readable medical report"""
        
        # Extract patient information
        session_id = report_content.get('session_id', 'Unknown')
        patient_id = report_content.get('patient_id', 'Unknown')
        patient_name = report_content.get('patient_name', 'Unknown Patient')
        doctor_id = report_content.get('doctor_id', 'Unknown')
        doctor_name = report_content.get('doctor_name', 'Unknown Doctor')
        mri_info = report_content.get('mri_info', 'No MRI scan provided')
        
        if report_type == "patient":
            return self._format_patient_report(report_content, session_id, patient_id, patient_name, doctor_id, doctor_name, mri_info)
        else:
            return self._format_doctor_report(report_content, session_id, patient_id, patient_name, doctor_id, doctor_name, mri_info)
    
    def _format_patient_report(self, report_content: Dict[str, Any], session_id: str, patient_id: str, 
                              patient_name: str, doctor_id: str, doctor_name: str, mri_info: str) -> str:
        """Format patient-friendly report with simplified language"""
        
        try:
            title = report_content.get('title', 'Your Health Report')
            executive_summary = report_content.get('executive_summary', 'Your scan has been reviewed.')
            clinical_findings = report_content.get('clinical_findings', 'The analysis is complete.')
            diagnostic_assessment = report_content.get('diagnostic_assessment', 'Results are being reviewed.')
            recommendations = report_content.get('recommendations', [])
            disclaimer = report_content.get('disclaimer', 'This report should be discussed with your doctor.')
            
            # Clean up text (same cleaning function as before)
            def clean_text(text):
                if isinstance(text, str):
                    text = text.replace('```json', '').replace('```', '')
                    text = text.replace('\\"', '"')
                    if text.strip().startswith('{') and '"title":' in text:
                        try:
                            import json
                            import re
                            json_match = re.search(r'\{.*\}', text, re.DOTALL)
                            if json_match:
                                try:
                                    parsed = json.loads(json_match.group())
                                    return parsed.get('executive_summary', 'Your scan has been analyzed.')
                                except:
                                    pass
                        except:
                            pass
                        return "Your scan has been analyzed. Please discuss with your doctor."
                    import re
                    text = re.sub(r'\s+', ' ', text).strip()
                    return text
                return str(text)
            
            executive_summary = clean_text(executive_summary)
            clinical_findings = clean_text(clinical_findings)
            diagnostic_assessment = clean_text(diagnostic_assessment)
            
            # Build patient-friendly report
            formatted_content = f"""# **Your Medical Report**

## **Patient Information**
• **Patient Name:** {patient_name}
• **Patient ID:** {patient_id}
• **Session ID:** {session_id}
• **Attending Doctor:** {doctor_name}
• **Doctor ID:** {doctor_id}
• **MRI Scan:** {mri_info}

## **Summary**
{executive_summary}

## **What We Found**
{clinical_findings}

## **What This Means**
{diagnostic_assessment}

## **Next Steps**
"""
            
            # Format recommendations in simple language
            if isinstance(recommendations, list) and recommendations:
                for i, rec in enumerate(recommendations, 1):
                    rec_clean = clean_text(rec)
                    formatted_content += f"**{i}.** {rec_clean}\n"
            else:
                formatted_content += "**1.** Schedule a follow-up appointment with your doctor\n"
                formatted_content += "**2.** Continue your current medications as prescribed\n"
                formatted_content += "**3.** Stay active with regular exercise\n"
                formatted_content += "**4.** Ask your doctor any questions you may have\n"
            
            formatted_content += f"""
## **Important Note**
*{clean_text(disclaimer)} Please discuss these results with your healthcare provider.*

---
**Report Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            
            return formatted_content.strip()
            
        except Exception as e:
            logger.error(f"Error formatting patient report: {e}")
            return self._get_fallback_patient_report(session_id, patient_id, patient_name, doctor_id, doctor_name, mri_info)
    
    def _format_doctor_report(self, report_content: Dict[str, Any], session_id: str, patient_id: str, 
                             patient_name: str, doctor_id: str, doctor_name: str, mri_info: str) -> str:
        """Format detailed medical report for healthcare providers"""
        
        try:
            title = report_content.get('title', 'Parkinson\'s Disease Analysis Report')
            executive_summary = report_content.get('executive_summary', 'MRI analysis completed using AI-assisted evaluation.')
            clinical_findings = report_content.get('clinical_findings', 'Clinical findings based on AI analysis.')
            diagnostic_assessment = report_content.get('diagnostic_assessment', 'Assessment based on available data.')
            recommendations = report_content.get('recommendations', [])
            disclaimer = report_content.get('disclaimer', 'This report is AI-generated and requires professional medical review.')
            
            # Clean up text (same cleaning function)
            def clean_text(text):
                if isinstance(text, str):
                    text = text.replace('```json', '').replace('```', '')
                    text = text.replace('\\"', '"')
                    if text.strip().startswith('{') and '"title":' in text:
                        try:
                            import json
                            import re
                            json_match = re.search(r'\{.*\}', text, re.DOTALL)
                            if json_match:
                                try:
                                    parsed = json.loads(json_match.group())
                                    return parsed.get('executive_summary', 'Clinical analysis completed.')
                                except:
                                    pass
                        except:
                            pass
                        return "Clinical analysis indicates markers for assessment. Further evaluation recommended."
                    import re
                    text = re.sub(r'\s+', ' ', text).strip()
                    return text
                return str(text)
            
            executive_summary = clean_text(executive_summary)
            clinical_findings = clean_text(clinical_findings)
            diagnostic_assessment = clean_text(diagnostic_assessment)

            # Extract additional fields for doctor report
            probability_score = report_content.get('probability_score', None)
            model_output = report_content.get('model_output', None)
            patient_history = report_content.get('patient_history', 'No prior history available.')
            scan_date = report_content.get('scan_date', datetime.now().strftime('%Y-%m-%d'))
            symptom_checklist = report_content.get('symptom_checklist', 'Not provided.')
            stored_scans = report_content.get('stored_scans', [])

            # Build detailed medical report
            formatted_content = f"""# **{title}**

## **Patient Information**
• **Patient Name:** {patient_name}
• **Patient ID:** {patient_id}
• **Session ID:** {session_id}
• **Attending Physician:** {doctor_name}
• **Physician ID:** {doctor_id}
• **Scan Date:** {scan_date}
• **Imaging Study:** {mri_info}

## **Patient History**
{patient_history}

## **Stored MRI Scans**
{', '.join(stored_scans) if stored_scans else 'No previous scans found.'}

## **Executive Summary**
{executive_summary}

## **Clinical Findings**
{clinical_findings}

## **Model Output**
{model_output if model_output else 'No technical output available.'}

## **Probability Score**
{probability_score if probability_score is not None else 'Not available.'}

## **Symptom Checklist**
{symptom_checklist}

## **Diagnostic Assessment**
{diagnostic_assessment}

## **Suggested Investigations**
- UPDRS motor examination
- Blood work for rule-outs
- Neuropsychological assessment

## **Medication Plan**
[Doctor input required]

## **Clinical Recommendations**
"""
            
            # Format clinical recommendations
            if isinstance(recommendations, list) and recommendations:
                for i, rec in enumerate(recommendations, 1):
                    rec_clean = clean_text(rec)
                    formatted_content += f"**{i}.** {rec_clean}\n"
            else:
                formatted_content += "**1.** Refer to movement disorder specialist for comprehensive evaluation\n"
                formatted_content += "**2.** Consider additional diagnostic imaging (DaTscan) for confirmation\n"
                formatted_content += "**3.** Monitor symptom progression with standardized rating scales\n"
                formatted_content += "**4.** Implement evidence-based exercise therapy program\n"
                formatted_content += "**5.** Consider pharmacological intervention if clinically indicated\n"
            
            formatted_content += f"""
## **Medical Disclaimer**
*{clean_text(disclaimer)}*

---
**Report Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Generated By:** AI-Assisted Medical Analysis System
"""
            
            return formatted_content.strip()
            
        except Exception as e:
            logger.error(f"Error formatting doctor report: {e}")
            return self._get_fallback_doctor_report(session_id, patient_id, patient_name, doctor_id, doctor_name, mri_info)
    
    def _get_fallback_patient_report(self, session_id: str, patient_id: str, patient_name: str, 
                                    doctor_id: str, doctor_name: str, mri_info: str) -> str:
        """Fallback patient report if formatting fails"""
        return f"""# **Your Medical Report**

## **Patient Information**
• **Patient Name:** {patient_name}
• **Patient ID:** {patient_id}
• **Session ID:** {session_id}
• **Attending Doctor:** {doctor_name}
• **Doctor ID:** {doctor_id}
• **MRI Scan:** {mri_info}

## **Summary**
Your scan has been completed and analyzed. Please discuss the results with your doctor.

## **What We Found**
The analysis has been completed using advanced technology to help your doctor understand your condition.

## **Next Steps**
**1.** Schedule a follow-up appointment with your doctor
**2.** Continue your current medications as prescribed
**3.** Stay active with regular exercise
**4.** Ask your doctor any questions you may have

## **Important Note**
*This report should be discussed with your healthcare provider.*

---
**Report Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    def _get_fallback_doctor_report(self, session_id: str, patient_id: str, patient_name: str, 
                                   doctor_id: str, doctor_name: str, mri_info: str) -> str:
        """Fallback doctor report if formatting fails"""
        return f"""# **Parkinson's Disease Analysis Report**

## **Patient Information**
• **Patient Name:** {patient_name}
• **Patient ID:** {patient_id}
• **Session ID:** {session_id}
• **Attending Physician:** {doctor_name}
• **Physician ID:** {doctor_id}
• **Imaging Study:** {mri_info}

## **Executive Summary**
MRI analysis completed using AI-assisted evaluation. This report provides preliminary findings for clinical review.

## **Clinical Findings**
AI analysis indicates markers for Parkinson's disease assessment. Further clinical evaluation recommended.

## **Diagnostic Assessment**
Assessment based on computational analysis and requires professional medical interpretation.

## **Clinical Recommendations**
**1.** Refer to movement disorder specialist for comprehensive evaluation
**2.** Consider additional diagnostic imaging for confirmation
**3.** Monitor symptom progression with standardized rating scales
**4.** Implement evidence-based exercise therapy program

## **Medical Disclaimer**
*This AI-generated report is for screening purposes only and requires professional medical interpretation.*

---
**Report Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Generated By:** AI-Assisted Medical Analysis System
"""
    
    def _calculate_report_confidence(self, prediction_data: Dict[str, Any], 
                                   knowledge_entries: List[Dict[str, Any]]) -> float:
        """Calculate confidence level for the generated report"""
        prediction_confidence = prediction_data.get('confidence_score', 0.5)
        knowledge_quality = len(knowledge_entries) / 10.0  # Normalize by expected max entries
        
        # Combine factors
        report_confidence = (prediction_confidence * 0.7) + (knowledge_quality * 0.3)
        
        return min(1.0, max(0.1, report_confidence))
    
    async def synthesize_report_content(self, prediction_data: Dict[str, Any], 
                                      knowledge_entries: List[Dict[str, Any]]) -> str:
        """Synthesize report content from prediction and knowledge"""
        try:
            # Use Groq service to synthesize content
            report_data = await self.groq_service.generate_medical_report(
                prediction_data, knowledge_entries, None
            )
            
            return self._format_report_content(report_data)
            
        except Exception as e:
            logger.error(f"Error synthesizing report content: {e}")
            return "Error generating report content. Please consult with a healthcare professional."
    
    async def _fail_report_generation(self, flag_id: str, session_id: str, error_message: str):
        """Handle report generation failure"""
        try:
            # Mark the action flag as failed
            await self.shared_memory.fail_action_flag(flag_id)
            
            # Store a failed report
            failed_report = MedicalReport(
                report_id=str(uuid.uuid4()),
                session_id=session_id,
                prediction_id=None,
                report_type='error',
                title='Report Generation Failed',
                content=f'Report generation encountered an error: {error_message}',
                recommendations=['Please try again or consult with a healthcare professional'],
                confidence_level=0.0,
                metadata={'error': error_message, 'status': 'failed'}
            )
            
            await self.shared_memory.store_report(failed_report)
            
            logger.error(f"Report generation failed for session {session_id}: {error_message}")
            
        except Exception as e:
            logger.error(f"Error handling report generation failure: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for RAG agent"""
        base_health = await super().health_check()
        
        return {
            **base_health,
            "knowledge_base_status": {
                "entries_count": self.knowledge_base_size,
                "embedding_dimension": self.embedding_dimension
            },
            "groq_service_status": "connected" if self.groq_service.session else "not_connected",
            "generation_stats": {
                "reports_generated": self.reports_generated,
                "total_generation_time": self.total_generation_time,
                "average_generation_time": (
                    self.total_generation_time / self.reports_generated 
                    if self.reports_generated > 0 else 0
                )
            },
            "report_templates": list(self.report_templates.keys())
        }
    
    # Required abstract method implementations
    async def process_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a generic task - delegates to specific methods"""
        task_type = task_data.get('type')
        
        if task_type == 'generate_report':
            session_id = task_data.get('session_id')
            
            if session_id:
                result = await self.generate_medical_report(session_id)
                return {'status': 'completed', 'result': result}
            else:
                return {'status': 'error', 'message': 'Missing session_id'}
        
        elif task_type == 'generate_pdf_report':
            session_id = task_data.get('session_id')
            output_path = task_data.get('output_path')
            
            if session_id:
                try:
                    pdf_path = await self.generate_pdf_report(session_id, output_path)
                    return {'status': 'completed', 'pdf_path': pdf_path}
                except Exception as e:
                    return {'status': 'error', 'message': f'PDF generation failed: {str(e)}'}
            else:
                return {'status': 'error', 'message': 'Missing session_id'}
        
        elif task_type == 'search_knowledge':
            query = task_data.get('query', '')
            category = task_data.get('category')
            
            results = await self.search_knowledge_base(query, category)
            return {'status': 'completed', 'results': results}
        
        else:
            return {'status': 'error', 'message': f'Unknown task type: {task_type}'}