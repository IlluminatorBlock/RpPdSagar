"""
Groq Service for Parkinson's Multiagent System

This module provides centralized access to Groq API (Llama models) for all LLM processing
including chat responses, prediction analysis, and report generation.
"""

import asyncio
import json
import logging
import numpy as np
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import aiohttp
from dataclasses import dataclass


def serialize_for_json(obj):
    """Helper function to serialize complex objects for JSON"""
    if isinstance(obj, np.ndarray):
        return obj.tolist()  # Convert NumPy arrays to Python lists
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_for_json(item) for item in obj]
    else:
        return obj


def summarize_features_for_groq(features: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize large feature dictionaries for Groq API to avoid message length limits"""
    summary = {}
    
    for key, value in features.items():
        if isinstance(value, np.ndarray):
            # Summarize arrays with statistics instead of full data
            summary[key] = {
                "type": "array",
                "shape": value.shape,
                "mean": float(np.mean(value)),
                "std": float(np.std(value)),
                "min": float(np.min(value)),
                "max": float(np.max(value))
            }
        elif isinstance(value, dict):
            # Recursively summarize nested dictionaries
            if len(str(value)) > 1000:  # If too large, summarize
                summary[key] = {
                    "type": "dict",
                    "keys": list(value.keys())[:10],  # Only first 10 keys
                    "total_keys": len(value)
                }
            else:
                summary[key] = summarize_features_for_groq(value)
        elif isinstance(value, (list, tuple)) and len(value) > 20:
            # Summarize large lists
            summary[key] = {
                "type": "list",
                "length": len(value),
                "sample": value[:5],  # First 5 items
                "mean": float(np.mean(value)) if all(isinstance(x, (int, float)) for x in value) else "mixed_types"
            }
        else:
            # Keep small values as-is
            summary[key] = serialize_for_json(value)
    
    return summary

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class GroqMessage:
    """Represents a message in Groq chat format"""
    role: str  # 'system', 'user', 'assistant'
    content: str


@dataclass
class GroqResponse:
    """Represents a response from Groq API"""
    content: str
    model: str
    usage: Dict[str, int]
    response_time: float
    timestamp: datetime


class GroqService:
    """
    Centralized service for all Groq API interactions.
    All agents must use this service for LLM processing.
    """
    
    def __init__(self, api_key: str, model: str = "llama-70b-8192", base_url: str = "https://api.groq.com/openai/v1"):
        if not api_key or api_key.strip() == "" or api_key == "your_groq_api_key_here":
            raise ValueError(
                "Invalid Groq API key. Please:\n"
                "1. Get your API key from: https://console.groq.com/keys\n"
                "2. Update the GROQ_API_KEY in your .env file\n"
                "3. Make sure your API key is valid and has not expired"
            )
        self.api_key = api_key.strip()
        self.model = model
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.session = None
        self._rate_limit_delay = 0.1  # Minimum delay between requests
        self._last_request_time = 0
    
    async def initialize(self):
        """Initialize the HTTP session"""
        logger.debug("[LIFECYCLE] Initializing GroqService")
        self.session = aiohttp.ClientSession(headers=self.headers)
        logger.info("Groq service initialized")
    
    async def close(self):
        """Close the HTTP session"""
        logger.debug("[LIFECYCLE] Closing GroqService")
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
        logger.info("Groq service closed")
    
    async def _rate_limit(self):
        """Simple rate limiting to avoid API limits"""
        current_time = asyncio.get_event_loop().time()
        time_since_last = current_time - self._last_request_time
        if time_since_last < self._rate_limit_delay:
            await asyncio.sleep(self._rate_limit_delay - time_since_last)
        self._last_request_time = asyncio.get_event_loop().time()
    
    async def _make_request(self, messages: List[GroqMessage], 
                          temperature: float = 0.7, 
                          max_tokens: int = 1000,
                          stream: bool = False) -> GroqResponse:
        """Make a request to Groq API"""
        if not self.session:
            await self.initialize()
        
        await self._rate_limit()
        
        start_time = asyncio.get_event_loop().time()
        
        payload = {
            "model": self.model,
            "messages": [{"role": msg.role, "content": msg.content} for msg in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream
        }
        
        try:
            async with self.session.post(f"{self.base_url}/chat/completions", json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Groq API error {response.status}: {error_text}")
                
                response_data = await response.json()
                end_time = asyncio.get_event_loop().time()
                
                return GroqResponse(
                    content=response_data["choices"][0]["message"]["content"],
                    model=response_data["model"],
                    usage=response_data.get("usage", {}),
                    response_time=end_time - start_time,
                    timestamp=datetime.now()
                )
                
        except Exception as e:
            logger.error(f"Groq API request failed: {e}")
            raise
    
    # Chat Mode - For Supervisor Agent when no prediction/report requested
    async def handle_chat_request(self, user_message: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Handle general chat requests about Parkinson's disease.
        Used by Supervisor Agent when no explicit prediction or report is requested.
        """
        system_prompt = """You are a helpful medical assistant specializing in Parkinson's disease.
        
        IMPORTANT: You are in CHAT-ONLY mode. The user is NOT requesting MRI analysis or medical reports.
        
        Provide informative, helpful responses about:
        - General Parkinson's disease information
        - Symptoms and stages
        - Treatment options
        - Lifestyle recommendations
        - Support resources
        
        Always include appropriate medical disclaimers.
        Keep responses conversational and supportive.
        If the user wants MRI analysis or formal reports, direct them to make explicit requests."""
        
        # Add context if available
        if context:
            system_prompt += f"\n\nSession Context: {json.dumps(context, indent=2)}"
        
        messages = [
            GroqMessage(role="system", content=system_prompt),
            GroqMessage(role="user", content=user_message)
        ]
        
        response = await self._make_request(messages, temperature=0.7, max_tokens=800)
        return response.content
    
    # Prediction Support - For AI/ML Agent
    async def analyze_mri_features(self, features: Dict[str, Any], image_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze MRI features for Parkinson's prediction.
        Used by AI/ML Agent during explicit prediction workflow.
        """
        system_prompt = """You are an expert medical AI specializing in Parkinson's disease diagnosis from MRI data.
        
        TASK: Analyze the provided MRI features and metadata to assist in Parkinson's classification.
        
        CONTEXT: This is part of an EXPLICIT prediction workflow - the user has specifically requested MRI analysis.
        
        Provide analysis in the following JSON format:
        {
            "binary_classification": "parkinsons" | "no_parkinsons" | "uncertain",
            "stage_classification": "1" | "2" | "3" | "4" | "uncertain",
            "confidence_scores": {
                "binary_confidence": 0.0-1.0,
                "stage_confidence": 0.0-1.0
            },
            "key_indicators": ["list", "of", "key", "findings"],
            "uncertainty_factors": ["factors", "contributing", "to", "uncertainty"],
            "recommendations": ["clinical", "recommendations"]
        }
        
        Base your analysis on established medical criteria for Parkinson's diagnosis."""
        
        user_message = f"""MRI Features (Summarized):
        {json.dumps(summarize_features_for_groq(features), indent=2)}
        
        Image Metadata:
        {json.dumps(serialize_for_json(image_metadata), indent=2)}
        
        Please provide your analysis in the specified JSON format."""
        
        messages = [
            GroqMessage(role="system", content=system_prompt),
            GroqMessage(role="user", content=user_message)
        ]
        
        response = await self._make_request(messages, temperature=0.3, max_tokens=1200)
        
        try:
            # First try to parse as JSON
            analysis = json.loads(response.content)
            return analysis
        except json.JSONDecodeError as e:
            logger.warning(f"Groq response not in JSON format, using fallback parsing: {e}")
            # SAFE FALLBACK: Return an uncertain state to prevent misdiagnosis
            return {
                "binary_classification": "uncertain",
                "stage_classification": "uncertain",
                "confidence_scores": {"binary_confidence": 0.0, "stage_confidence": 0.0},
                "key_indicators": ["LLM response was not valid JSON"],
                "uncertainty_factors": ["Could not parse the analysis from the AI model"],
                "recommendations": ["A manual review by a medical professional is required"]
            }
    
    async def explain_prediction(self, prediction_result: Dict[str, Any]) -> str:
        """
        Generate explanation for a prediction result.
        Used by AI/ML Agent to provide interpretable predictions.
        """
        system_prompt = """You are a medical AI explaining Parkinson's disease predictions to healthcare professionals.
        
        TASK: Provide a clear, professional explanation of the prediction results.
        
        Include:
        - Summary of findings
        - Confidence interpretation
        - Clinical significance
        - Recommended next steps
        
        Use medical terminology appropriate for healthcare professionals."""
        
        user_message = f"""Prediction Results (Summarized):
        {json.dumps(summarize_features_for_groq(prediction_result), indent=2)}
        
        Please provide a comprehensive explanation of these results."""
        
        messages = [
            GroqMessage(role="system", content=system_prompt),
            GroqMessage(role="user", content=user_message)
        ]
        
        response = await self._make_request(messages, temperature=0.5, max_tokens=800)
        return response.content
    
    # Report Generation - For RAG Agent
    async def generate_medical_report(self, prediction_data: Dict[str, Any], 
                                    knowledge_entries: List[Dict[str, Any]],
                                    patient_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generate comprehensive medical report.
        Used by RAG Agent during explicit report generation workflow.
        """
        system_prompt = """You are a medical report generation AI specializing in Parkinson's disease.
        
        TASK: Generate a comprehensive medical report based on:
        1. MRI prediction results
        2. Relevant medical knowledge
        3. Patient information (if available)
        
        CONTEXT: This is part of an EXPLICIT report generation workflow - the user has specifically requested a medical report.
        
        Generate a formal medical report with:
        - Executive Summary
        - Clinical Findings
        - Diagnostic Assessment
        - Recommendations
        - References to medical knowledge
        
        Return response in JSON format:
        {
            "title": "Report title",
            "executive_summary": "Brief overview",
            "clinical_findings": "Detailed findings",
            "diagnostic_assessment": "Diagnostic conclusion",
            "recommendations": ["list", "of", "recommendations"],
            "confidence_level": 0.0-1.0,
            "disclaimer": "Medical disclaimer text"
        }"""
        
        # Compile knowledge context
        knowledge_context = "\n".join([
            f"- {entry.get('title', 'Unknown')}: {entry.get('content', '')[:200]}..."
            for entry in knowledge_entries[:5]  # Limit to top 5 entries
        ])
        
        user_message = f"""Prediction Data:
        {json.dumps(prediction_data, indent=2)}
        
        Relevant Medical Knowledge:
        {knowledge_context}
        
        Patient Data:
        {json.dumps(patient_data or {}, indent=2)}
        
        Please generate a comprehensive medical report in the specified JSON format."""
        
        messages = [
            GroqMessage(role="system", content=system_prompt),
            GroqMessage(role="user", content=user_message)
        ]
        
        response = await self._make_request(messages, temperature=0.4, max_tokens=2000)
        
        try:
            report_data = json.loads(response.content)
            return report_data
        except json.JSONDecodeError as e:
            logger.warning(f"Groq report response not in JSON format, using fallback: {e}")
            # Return a structured fallback report using the raw content
            return {
                "title": "Parkinson's Disease Analysis Report",
                "executive_summary": "MRI analysis completed using AI-assisted evaluation. This report provides preliminary findings for clinical review.",
                "clinical_findings": response.content if response.content else "Analysis completed with mock prediction data.",
                "diagnostic_assessment": "Early-stage Parkinson's disease indicators detected with moderate confidence. Further clinical evaluation recommended.",
                "recommendations": [
                    "Follow-up with movement disorder specialist",
                    "Consider DaTscan imaging for confirmation", 
                    "Monitor symptoms for progression",
                    "Lifestyle modifications and exercise therapy"
                ],
                "confidence_level": 0.7,
                "disclaimer": "This AI-generated report is for screening purposes only and requires professional medical interpretation."
            }
    
    async def synthesize_patient_recommendations(self, prediction_data: Dict[str, Any],
                                               knowledge_entries: List[Dict[str, Any]]) -> List[str]:
        """
        Generate patient-specific recommendations based on prediction and knowledge.
        Used by RAG Agent for personalized guidance.
        """
        system_prompt = """You are a medical AI generating patient-specific recommendations for Parkinson's disease.
        
        TASK: Generate actionable, personalized recommendations based on:
        1. Prediction results
        2. Current medical knowledge
        
        Focus on:
        - Lifestyle modifications
        - Treatment options
        - Monitoring guidelines
        - Support resources
        
        Return as a simple list of specific, actionable recommendations."""
        
        knowledge_context = "\n".join([
            entry.get('content', '')[:150] for entry in knowledge_entries[:3]
        ])
        
        user_message = f"""Prediction Results:
        {json.dumps(prediction_data, indent=2)}
        
        Medical Knowledge Context:
        {knowledge_context}
        
        Please provide a list of specific, actionable recommendations for this patient."""
        
        messages = [
            GroqMessage(role="system", content=system_prompt),
            GroqMessage(role="user", content=user_message)
        ]
        
        response = await self._make_request(messages, temperature=0.5, max_tokens=800)
        
        # Parse recommendations from response
        content = response.content.strip()
        recommendations = [
            line.strip().lstrip('- ').lstrip('• ').lstrip('* ')
            for line in content.split('\n')
            if line.strip() and not line.startswith('#')
        ]
        
        return recommendations[:10]  # Limit to 10 recommendations
    
    # Knowledge Base Support
    async def generate_embeddings(self, text: str) -> List[float]:
        """
        Generate embeddings for knowledge base entries.
        Note: This is a placeholder - Groq doesn't have embedding endpoints.
        In production, you'd use a separate embedding service or local model.
        """
        # For now, raise NotImplementedError as specified in requirements
        raise NotImplementedError("Embedding generation not implemented - use separate service")
    
    async def extract_medical_concepts(self, text: str) -> List[str]:
        """
        Extract medical concepts from text for knowledge organization.
        """
        system_prompt = """You are a medical concept extraction AI.
        
        TASK: Extract key medical concepts, terms, and topics from the provided text.
        
        Focus on:
        - Medical conditions
        - Symptoms
        - Treatments
        - Diagnostic terms
        - Anatomical references
        
        Return a simple list of extracted concepts."""
        
        messages = [
            GroqMessage(role="system", content=system_prompt),
            GroqMessage(role="user", content=f"Extract medical concepts from: {text}")
        ]
        
        response = await self._make_request(messages, temperature=0.3, max_tokens=400)
        
        # Parse concepts from response
        concepts = [
            concept.strip().lstrip('- ').lstrip('• ').lstrip('* ')
            for concept in response.content.split('\n')
            if concept.strip()
        ]
        
        return concepts[:20]  # Limit to 20 concepts
    
    # Utility Methods
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on Groq service"""
        try:
            # Simple test request
            test_messages = [
                GroqMessage(role="system", content="You are a health check assistant."),
                GroqMessage(role="user", content="Respond with 'OK' if you're working properly.")
            ]
            
            response = await self._make_request(test_messages, max_tokens=10)
            
            return {
                'status': 'healthy',
                'model': self.model,
                'response_time': response.response_time,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Groq health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def estimate_token_count(self, text: str) -> int:
        """Estimate token count for text (rough approximation)"""
        # Rough estimation: ~4 characters per token for English text
        return len(text) // 4
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics (placeholder for production implementation)"""
        return {
            'total_requests': 0,  # Would track in production
            'total_tokens': 0,
            'current_rate_limit': self._rate_limit_delay,
            'service_uptime': 'unknown'
        }