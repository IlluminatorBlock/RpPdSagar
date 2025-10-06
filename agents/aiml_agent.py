"""
AI/ML Agent for Parkinson's Multiagent System

This agent specializes in MRI processing and Parkinson's disease prediction.
It ONLY processes MRI scans when PREDICT_PARKINSONS flag is set in shared memory.
"""

import asyncio
import logging
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime
import os
import numpy as np
from PIL import Image

from models.agent_interfaces import PredictionAgent
from models.data_models import (
    ActionFlagType, PredictionResult, PredictionType, 
    ProcessingStatus, MRIData
)
from services.groq_service import GroqService
from services.mri_processor import MRIProcessor

# Try to import TensorFlow for real model support
try:
    import tensorflow as tf
    TF_AVAILABLE = True
except ImportError:
    tf = None
    TF_AVAILABLE = False

# Configure enhanced logging for AI/ML operations
logger = logging.getLogger(__name__)

# Debug mode flag - controlled by environment variable
DEBUG_MODE = os.getenv('DEBUG_MODE', 'true').lower() == 'true'

def debug_log(message: str, context: dict = None):
    """Enhanced debug logging with context"""
    print(f"[PRINT] ENTERED debug_log function")
    if DEBUG_MODE:
        if context:
            logger.debug(f"[AIML-DEBUG] {message} | Context: {context}")
        else:
            logger.debug(f"[AIML-DEBUG] {message}")
    print(f"[PRINT] EXITING debug_log function")

def error_log_with_context(message: str, error: Exception, context: dict = None):
    """Enhanced error logging with full traceback and context - FIXED to prevent model dumping"""
    print(f"[PRINT] ENTERED error_log_with_context function")
    import traceback
    
    # FIXED: Only log the error type and message, not the full exception object
    error_info = {
        'error_type': type(error).__name__,
        'error_message': str(error)[:500],  # Limit error message length
        'traceback': traceback.format_exc()[:1000] if DEBUG_MODE else str(error)[:200]  # Limit traceback length
    }
    if context:
        error_info['context'] = context
    
    logger.error(f"[AIML-ERROR] {message} | Details: {error_info}")
    print(f"[PRINT] EXITING error_log_with_context function")
    return error_info


class AIMLAgent(PredictionAgent):
    """
    AI/ML Agent for MRI processing and Parkinson's prediction.
    
    Key Requirements:
    1. Processes MRI scans ONLY when PREDICT_PARKINSONS flag is set
    2. Stores prediction results in shared memory
    3. Sets PREDICTION_COMPLETE flag after processing
    4. Never runs prediction logic automatically - only on explicit flags
    """
    
    def __init__(self, shared_memory, groq_service: GroqService, mri_processor: MRIProcessor, config: Dict[str, Any]):
        print(f"[PRINT] ENTERED AIMLAgent.__init__ method")
        super().__init__(shared_memory, config, "aiml_agent")
        self.groq_service = groq_service
        self.mri_processor = mri_processor
        
        # Model configuration
        self.model_version = config.get('model_version', 'v1.0')
        self.confidence_threshold = config.get('confidence_threshold', 0.7)
        
        # TensorFlow model (will be loaded during initialization)
        self.model = None
        
        # Processing statistics
        self.predictions_processed = 0
        self.total_processing_time = 0.0
        print(f"[PRINT] EXITING AIMLAgent.__init__ method")
    
    async def initialize(self) -> None:
        """Initialize AI/ML Agent and start background tasks"""
        print(f"[PRINT] ENTERED AIMLAgent.initialize method")
        self.logger.debug("[LIFECYCLE] Initializing AIMLAgent")
        
        # Call parent initialize first
        await super().initialize()
        
        # Initialize Groq service if needed
        if not self.groq_service.session:
            await self.groq_service.initialize()
        
        # Initialize TensorFlow model if available
        print("[SIMPLE] About to call _initialize_tensorflow_model")
        await self._initialize_tensorflow_model()
        print("[SIMPLE] Finished calling _initialize_tensorflow_model")
        
        self.logger.info("AI/ML Agent initialized - monitoring for PREDICT_PARKINSONS flags")
        print(f"[PRINT] EXITING AIMLAgent.initialize method")
    
    async def shutdown(self) -> None:
        """Shutdown AI/ML Agent and cleanup resources"""
        self.logger.debug("[LIFECYCLE] Shutting down AIMLAgent")
        
        # Cleanup MRI processor if needed
        if hasattr(self.mri_processor, 'shutdown'):
            await self.mri_processor.shutdown()
        
        await super().shutdown()
        self.logger.info("AI/ML Agent shutdown completed")
    
    async def process_task(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process AI/ML tasks"""
        self.logger.debug(f"[TASK] AIMLAgent processing {event_type}")
        
        if event_type.startswith('flag_created_PREDICT_PARKINSONS'):
            return await self._handle_prediction_flag(payload)
        elif event_type == "health_check":
            return await self.health_check()
        else:
            return await super().process_task(event_type, payload)
    
    async def start_monitoring(self) -> None:
        """Legacy method for main.py compatibility - monitoring starts in initialize()"""
        self.logger.info("AI/ML Agent monitoring confirmed - already started in initialize()")
    
    # Legacy methods for backward compatibility
    async def start(self) -> None:
        """Legacy method - use initialize() instead"""
        await self.initialize()
    
    async def stop(self) -> None:
        """Legacy method - use shutdown() instead"""
        await self.shutdown()
    
    async def _initialize_tensorflow_model(self):
        """Initialize TensorFlow model for real predictions with comprehensive audit logging - FIXED"""
        print(f"[PRINT] ENTERED AIMLAgent._initialize_tensorflow_model method")
        print(f"[SIMPLE-START] Very first line of _initialize_tensorflow_model")
        print(f"[SIMPLE] Starting TensorFlow model initialization. TF_AVAILABLE: {TF_AVAILABLE}")
        
        debug_log("Starting TensorFlow model initialization", {
            "tf_available": TF_AVAILABLE,
            "mock_enabled": self.config.get('enable_mock_predictions', False)
        })
        
        # Audit: Check configuration - use config instead of environment
        use_mock = self.config.get('enable_mock_predictions', False)
        
        if use_mock:
            debug_log("Using mock predictions due to ENABLE_MOCK_PREDICTIONS=true")
            self.model = None
            logger.info("[AUDIT] TensorFlow model disabled (mock predictions enabled)")
            return
            
        if not TF_AVAILABLE:
            debug_log("TensorFlow not available, predictions will use Groq fallback")
            self.model = None
            logger.warning("[AUDIT] TensorFlow not available, using Groq AI fallback for predictions")
            return
        
        # Audit: Attempt real model loading with comprehensive validation
        try:
            model_path = os.path.join(os.path.dirname(__file__), '..', 'models', 'parkinsons_model.keras')
            debug_log("Attempting to load TensorFlow model", {"model_path": model_path})
            
            # Audit: File existence check
            if not os.path.exists(model_path):
                debug_log("Model file not found, predictions will use Groq fallback", {"path": model_path})
                self.model = None
                logger.warning(f"[AUDIT] Model file not found at {model_path}, using Groq AI fallback")
                return
            
            # Audit: File size and basic validation
            file_size = os.path.getsize(model_path) / (1024 * 1024)  # MB
            debug_log("Model file validation", {
                "size_mb": round(file_size, 2),
                "readable": os.access(model_path, os.R_OK)
            })
            
            if file_size < 1:  # Less than 1MB seems suspicious for a real model
                logger.warning(f"[AUDIT] Model file seems too small ({file_size:.2f}MB), might be corrupted")
            
            # Audit: Model loading with multiple approaches
            debug_log("Loading TensorFlow model...")
            
            # Try different loading approaches in order of preference
            model_loaded = False
            
            # Approach 1: Try standalone Keras (for Keras 3 models)
            try:
                import keras
                self.model = keras.models.load_model(model_path)
                model_loaded = True
                logger.info(f"[AUDIT] ✅ Model loaded successfully using standalone Keras")
            except ImportError:
                logger.info(f"[AUDIT] Standalone Keras not available, trying TensorFlow Keras")
            except Exception as keras_error:
                logger.warning(f"[AUDIT] Standalone Keras loading failed: {keras_error}")
            
            # Approach 2: Try TensorFlow's Keras (for TF 2.x models)
            if not model_loaded:
                try:
                    self.model = tf.keras.models.load_model(model_path)
                    model_loaded = True
                    logger.info(f"[AUDIT] ✅ Model loaded successfully using TensorFlow Keras")
                except Exception as tf_error:
                    logger.error(f"[AUDIT] TensorFlow Keras loading also failed: {tf_error}")
                    raise tf_error  # Re-raise the last error for proper handling
            
            if not model_loaded:
                raise RuntimeError("Failed to load model with any available method")
            
            # Audit: Model architecture validation
            input_shape = self.model.input_shape
            output_shape = self.model.output_shape

            # Audit: Expected shape validation (256x256x3 RGB input)
            expected_input = (None, 256, 256, 3)
            if input_shape != expected_input:
                logger.warning(f"[AUDIT] Model input shape {input_shape} doesn't match expected {expected_input}")
            
            logger.info(f"[AUDIT] ✅ TensorFlow model successfully loaded and validated")
            
            # Debug: Verify model object is correctly assigned
            logger.info(f"[DEBUG] Model object type: {type(self.model)}")
            logger.info(f"[DEBUG] Model is None: {self.model is None}")
            print(f"[SIMPLE] Model loaded successfully! Type: {type(self.model)}")
            
        except Exception as e:
            error_context = {
                "model_path": model_path if 'model_path' in locals() else "unknown",
                "tensorflow_version": tf.__version__ if TF_AVAILABLE else "not_available",
                "exception_type": type(e).__name__
            }
            
            # FIXED: Don't log the full exception which might contain the model
            logger.error(f"[AUDIT] Model loading failed: {type(e).__name__}: {str(e)[:200]}")
            logger.error(f"[AUDIT] Exception context: {error_context}")
            
            error_log_with_context("Failed to load TensorFlow model, will use Groq fallback", e, error_context)
            
            # Fallback to Groq AI service
            self.model = None
            # FIXED: Don't include the exception object in the log message
            logger.warning(f"[AUDIT] ⚠️ Failed to load TensorFlow model: {type(e).__name__}, using Groq AI fallback")
        
        print(f"[PRINT] EXITING AIMLAgent._initialize_tensorflow_model method")
    
    async def _setup_event_subscriptions(self):
        """Setup event subscriptions specific to AI/ML processing"""
        await super()._setup_event_subscriptions()
        
        # Subscribe specifically to PREDICT_PARKINSONS flags
        prediction_events = [
            f"flag_created_{ActionFlagType.PREDICT_PARKINSONS.value}",
            f"flag_claimed_{ActionFlagType.PREDICT_PARKINSONS.value}"
        ]
        
        self.shared_memory.subscribe_to_events(
            f"{self.agent_id}_predictions",
            prediction_events,
            self._handle_prediction_event
        )
        
        logger.info("AI/ML Agent subscribed to prediction events")
    
    async def _handle_prediction_event(self, event: Dict[str, Any]):
        """Handle prediction flag events"""
        try:
            event_type = event.get('event_type')
            data = event.get('data', {})
            session_id = event.get('session_id')
            
            if event_type == f"flag_created_{ActionFlagType.PREDICT_PARKINSONS.value}":
                flag_id = data.get('flag_id')
                
                if flag_id and session_id:
                    logger.info(f"Detected PREDICT_PARKINSONS flag {flag_id} for session {session_id}")
                    
                    # Claim the flag for processing
                    claimed = await self.shared_memory.claim_action_flag(flag_id, self.agent_id)
                    
                    if claimed:
                        logger.info(f"Claimed prediction flag {flag_id}")
                        await self._process_prediction_request(flag_id, session_id, data)
                    else:
                        logger.info(f"Failed to claim prediction flag {flag_id} - may be processed by another instance")
            
            self.last_activity = datetime.now()
            
        except Exception as e:
            self._handle_error(e, "handling prediction event")
    
    async def _process_prediction_request(self, flag_id: str, session_id: str, flag_data: Dict[str, Any]):
        """
        Process a prediction request triggered by PREDICT_PARKINSONS flag.
        This is the ONLY way this agent processes MRI scans.
        """
        start_time = datetime.now()
        
        try:
            logger.info(f"Starting MRI prediction processing for session {session_id}")
            
            # Get MRI data from shared memory
            mri_data_list = await self.shared_memory.get_mri_data(session_id)
            
            if not mri_data_list:
                await self._fail_prediction(flag_id, session_id, "No MRI data found for session")
                return
            
            # Process the most recent MRI scan
            mri_data = mri_data_list[-1]  # Get latest scan
            mri_file_path = mri_data.get('file_path')
            
            if not mri_file_path or not os.path.exists(mri_file_path):
                await self._fail_prediction(flag_id, session_id, f"MRI file not found: {mri_file_path}")
                return
            
            # Process MRI scan
            prediction_result = await self.process_mri_scan(session_id, mri_file_path)
            
            # Store prediction in shared memory
            prediction = PredictionResult(
                prediction_id=str(uuid.uuid4()),
                session_id=session_id,
                mri_scan_id=mri_data.get('id'),
                prediction_type=PredictionType.BINARY,
                binary_result=prediction_result.get('binary_result'),
                stage_result=prediction_result.get('stage_result'),
                confidence_score=prediction_result.get('confidence_score'),
                binary_confidence=prediction_result.get('binary_confidence'),
                stage_confidence=prediction_result.get('stage_confidence'),
                uncertainty_metrics=prediction_result.get('uncertainty_metrics', {}),
                # model_version=self.model_version,
                processing_time=(datetime.now() - start_time).total_seconds()
            )
            
            prediction_id = await self.shared_memory.store_prediction(prediction)
            
            # Complete the action flag
            await self.shared_memory.complete_action_flag(flag_id)
            
            # Set PREDICTION_COMPLETE flag
            await self.shared_memory.set_action_flag(
                flag_type=ActionFlagType.PREDICTION_COMPLETE,
                session_id=session_id,
                data={
                    'prediction_id': prediction_id,
                    'binary_result': prediction.binary_result,
                    'confidence_score': prediction.confidence_score,
                    'processed_by': self.agent_id
                }
            )
            
            # Update statistics
            self.predictions_processed += 1
            self.total_processing_time += prediction.processing_time
            
            logger.info(f"Successfully completed prediction for session {session_id}, prediction ID: {prediction_id}")
            
        except Exception as e:
            await self._fail_prediction(flag_id, session_id, f"Prediction processing failed: {str(e)}")
            self._handle_error(e, f"processing prediction request {flag_id}")
    
    async def process_mri_scan(self, session_id: str, mri_file_path: str) -> Dict[str, Any]:
        """
        Main MRI processing and prediction pipeline.
        Only called when PREDICT_PARKINSONS flag is set.
        """
        try:
            logger.info(f"Processing MRI scan: {mri_file_path}")
            
            # Step 1: Preprocess the MRI image
            processed_image_data = await self.preprocess_image(mri_file_path)
            
            # Step 2: Extract medical features
            features = await self.extract_features(processed_image_data)
            
            # Step 3: Classify Parkinson's disease
            classification_result = await self.classify_parkinsons(features)
            
            # Step 4: Calculate confidence and uncertainty
            confidence_analysis = await self._calculate_confidence_metrics(classification_result, features)
            
            # Step 5: Generate explanation using Groq
            explanation = await self._generate_prediction_explanation(classification_result, features)
            
            return {
                'binary_result': classification_result.get('binary_classification'),
                'stage_result': classification_result.get('stage_classification'),
                'confidence_score': confidence_analysis.get('overall_confidence'),
                'binary_confidence': confidence_analysis.get('binary_confidence'),
                'stage_confidence': confidence_analysis.get('stage_confidence'),
                'uncertainty_metrics': confidence_analysis.get('uncertainty_metrics', {}),
                'key_indicators': classification_result.get('key_indicators', []),
                'explanation': explanation,
                'processing_metadata': {
                    'file_path': mri_file_path,
                    'model_version': self.model_version,
                    'processing_timestamp': datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error processing MRI scan {mri_file_path}: {e}")
            raise
    
    async def preprocess_image(self, mri_file_path: str) -> Dict[str, Any]:
        """Preprocess MRI image for analysis"""
        try:
            # Use MRI processor service
            if self.mri_processor:
                processed_data = await self.mri_processor.preprocess_mri(mri_file_path)
                return processed_data
            else:
                # Fallback processing
                return {
                    'file_path': mri_file_path,
                    'preprocessing_applied': ['normalization', 'resizing'],
                    'image_dimensions': '256x256x128',
                    'status': 'processed'
                }
                
        except Exception as e:
            logger.error(f"Error preprocessing MRI image {mri_file_path}: {e}")
            raise
    
    async def extract_features(self, processed_image_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract medical features from preprocessed MRI data"""
        try:
            # Use MRI processor for feature extraction
            if self.mri_processor:
                features = await self.mri_processor.extract_features(processed_image_data)
                
                # CRITICAL: Include the processed data for the real TensorFlow model
                features['processed_data'] = processed_image_data.get('processed_data')
                
                return features
            else:
                # Mock feature extraction - include processed data for real model
                return {
                    'anatomical_features': {
                        'substantia_nigra_volume': 0.75,
                        'putamen_intensity': 0.82,
                        'caudate_nucleus_shape': 0.68
                    },
                    'intensity_features': {
                        'mean_intensity': 145.2,
                        'contrast': 0.73,
                        'homogeneity': 0.61
                    },
                    'morphological_features': {
                        'brain_volume': 1420.5,
                        'ventricular_volume': 58.3,
                        'cortical_thickness': 2.8
                    },
                    'feature_quality': 0.87,
                    'processed_data': processed_image_data.get('processed_data')  # Include for real model
                }
                
        except Exception as e:
            logger.error(f"Error extracting features: {e}")
            raise
    
    async def classify_parkinsons(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classify Parkinson's disease using extracted features and AI models.
        Uses real TensorFlow model if available, otherwise falls back to Groq AI.
        """
        print(f"[PRINT] ENTERED AIMLAgent.classify_parkinsons method")
        try:
            # Debug: Check conditions for real model usage
            has_model = self.model is not None
            has_processed_data = 'processed_data' in features
            
            # If model is None but should be available, try reloading it
            if not has_model and TF_AVAILABLE:
                logger.info("[MODEL_RELOAD] Model is None, attempting to reload...")
                try:
                    # Try to reload the model with detailed error tracking
                    model_path = os.path.join(os.path.dirname(__file__), '..', 'models', 'parkinsons_model.keras')
                    logger.info(f"[MODEL_RELOAD] Loading from: {model_path}")
                    logger.info(f"[MODEL_RELOAD] File exists: {os.path.exists(model_path)}")
                    
                    if os.path.exists(model_path):
                        logger.info(f"[MODEL_RELOAD] File size: {os.path.getsize(model_path) / (1024*1024):.2f} MB")
                        # Load model directly here instead of calling _initialize_tensorflow_model
                        self.model = tf.keras.models.load_model(model_path)
                        logger.info("[MODEL_RELOAD] Model loaded successfully!")
                        logger.info(f"[MODEL_RELOAD] Model type: {type(self.model)}")
                        has_model = True
                    else:
                        logger.error(f"[MODEL_RELOAD] Model file not found")
                        
                except Exception as e:
                    import traceback
                    logger.error(f"[MODEL_RELOAD] Exception type: {type(e).__name__}")
                    logger.error(f"[MODEL_RELOAD] Exception message: {str(e)[:200]}")  # FIXED: Limit message length
                    logger.error(f"[MODEL_RELOAD] Full traceback: {traceback.format_exc()[:500]}")  # FIXED: Limit traceback
                    has_model = False
                    
                logger.info(f"[MODEL_RELOAD] Model reload result: {has_model}")
            
            logger.info(f"[MODEL_CHECK] Has TensorFlow model: {has_model}")
            logger.info(f"[MODEL_CHECK] Has processed_data: {has_processed_data}")
            if has_processed_data:
                logger.info(f"[MODEL_CHECK] Processed data type: {type(features['processed_data'])}")
            logger.info(f"[MODEL_CHECK] Available feature keys: {list(features.keys())}")
            
            # Check if we have a real model and processed data
            if has_model and has_processed_data:
                logger.info("[MODEL_CHECK] ✅ Using real TensorFlow model")
                result = await self._classify_with_real_model(features)
                print(f"[PRINT] EXITING AIMLAgent.classify_parkinsons method (real model path)")
                return result
            else:
                logger.warning(f"[MODEL_CHECK] ❌ Falling back to Groq. Model: {has_model}, Data: {has_processed_data}")
                result = await self._classify_with_groq(features)
                print(f"[PRINT] EXITING AIMLAgent.classify_parkinsons method (groq fallback path)")
                return result
                
        except Exception as e:
            logger.error(f"Error in Parkinson's classification: {e}")
            # Return uncertain classification on error
            result = {
                'binary_classification': 'uncertain',
                'stage_classification': 'uncertain',
                'confidence_scores': {'binary_confidence': 0.1, 'stage_confidence': 0.1},
                'key_indicators': ['Classification error occurred'],
                'uncertainty_factors': [f'Processing error: {str(e)}'],
                'recommendations': ['Manual review required due to processing error']
            }
            print(f"[PRINT] EXITING AIMLAgent.classify_parkinsons method (with exception)")
            return result
    
    async def _classify_with_real_model(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Classify using the real TensorFlow model with comprehensive prediction audit"""
        print(f"[PRINT] ENTERED AIMLAgent._classify_with_real_model method")
        start_time = datetime.now()
        
        debug_log("Starting real model classification", {
            "model_available": self.model is not None,
            "features_keys": list(features.keys())
        })
        
        try:
            # Audit: Check if TensorFlow model is available
            if self.model is None:
                debug_log("TensorFlow model not available, falling back to Groq")
                return await self._classify_with_groq(features)
            
            # Audit: Input validation
            processed_image = features.get('processed_data')
            if processed_image is None:
                raise ValueError("No processed image data found in features")
            
            # The MRI processor returns processed data in a different format
            # Extract the actual image array for TensorFlow
            if isinstance(processed_image, dict):
                # Try both 'processed_array' and 'image_array' keys
                image_array = processed_image.get('processed_array')
                if image_array is None:
                    image_array = processed_image.get('image_array')
                if image_array is None:
                    raise ValueError("No processed array found in processed data. Available keys: " + str(list(processed_image.keys())))
            else:
                image_array = processed_image
            
            debug_log("Preparing image for model", {
                "input_shape": image_array.shape if hasattr(image_array, 'shape') else "unknown",
                "input_type": type(image_array).__name__
            })
            
            # Ensure we have a numpy array in the right format
            if not isinstance(image_array, np.ndarray):
                raise ValueError(f"Expected numpy array, got {type(image_array)}")
            
            # Convert grayscale to RGB if needed (model expects 3 channels)
            if len(image_array.shape) == 2:
                # 2D grayscale -> 3D RGB by repeating channels
                image_array = np.stack([image_array, image_array, image_array], axis=-1)
            elif len(image_array.shape) == 3 and image_array.shape[-1] == 1:
                # 3D grayscale (H, W, 1) -> RGB (H, W, 3)
                image_array = np.concatenate([image_array, image_array, image_array], axis=-1)
            elif len(image_array.shape) == 3 and image_array.shape[-1] != 3:
                raise ValueError(f"Unexpected number of channels: {image_array.shape[-1]}, expected 1 or 3")
            
            debug_log("Image channels converted", {
                "final_shape": image_array.shape,
                "channels": image_array.shape[-1] if len(image_array.shape) >= 3 else "N/A"
            })
            
            # Prepare image for model (add batch dimension if needed)
            if len(image_array.shape) == 3:
                image_batch = np.expand_dims(image_array, axis=0)
            else:
                image_batch = image_array
            
            debug_log("Image batch prepared", {
                "batch_shape": image_batch.shape,
                "expected_shape": (1, 256, 256, 3)
            })
            
            # Audit: Model prediction
            debug_log("Running model inference...")
            prediction_raw = self.model.predict(image_batch, verbose=0)
            prediction = prediction_raw[0][0]  # Extract scalar probability
            
            prediction_time = (datetime.now() - start_time).total_seconds()
            
            debug_log("Model prediction completed", {
                "raw_output_shape": prediction_raw.shape,
                "prediction_value": float(prediction),
                "inference_time_ms": round(prediction_time * 1000, 2)
            })
            
            # Audit: Prediction interpretation
            binary_classification = 'parkinsons' if prediction > 0.5 else 'no_parkinsons'
            confidence = float(prediction) if prediction > 0.5 else float(1 - prediction)
            
            # Audit: Confidence thresholds
            confidence_levels = {
                "high_confidence": confidence > 0.8,
                "medium_confidence": 0.6 <= confidence <= 0.8,
                "low_confidence": confidence < 0.6
            }
            
            # Stage estimation with audit logging
            if binary_classification == 'parkinsons':
                if confidence > 0.9:
                    stage = '3'  # High confidence = advanced stage
                    stage_reasoning = "High confidence suggests advanced pathology"
                elif confidence > 0.7:
                    stage = '2'  # Medium confidence = moderate stage
                    stage_reasoning = "Medium confidence suggests moderate pathology"
                else:
                    stage = '1'  # Lower confidence = early stage
                    stage_reasoning = "Lower confidence suggests early-stage or mild pathology"
            else:
                stage = 'uncertain'
                stage_reasoning = "No Parkinson's detected, stage classification not applicable"
            
            debug_log("Classification interpretation", {
                "binary_result": binary_classification,
                "confidence": confidence,
                "confidence_level": [k for k, v in confidence_levels.items() if v][0] if any(confidence_levels.values()) else "very_low",
                "stage": stage,
                "stage_reasoning": stage_reasoning
            })
            
            # Audit: Quality assessment
            quality_factors = {
                "model_confidence": float(confidence),
                "feature_quality": float(features.get('feature_quality', 0.0)),
                "preprocessing_quality": bool(features.get('preprocessing_status') == 'processed'),
                "inference_speed": bool(prediction_time < 5.0)  # Should be fast
            }
            
            overall_quality = sum([
                quality_factors["model_confidence"],
                quality_factors["feature_quality"],
                1.0 if quality_factors["preprocessing_quality"] else 0.0,
                1.0 if quality_factors["inference_speed"] else 0.0
            ]) / 4.0
            
            debug_log("Prediction quality assessment", {
                "overall_quality": round(overall_quality, 3),
                "quality_factors": quality_factors
            })
            
            result = {
                'binary_classification': binary_classification,
                'stage_classification': stage,
                'confidence_scores': {
                    'binary_confidence': float(confidence),
                    'stage_confidence': float(confidence * 0.8),  # Slightly lower confidence for stage
                    'overall_quality': float(overall_quality)
                },
                'key_indicators': [
                    f'Neural network prediction: {float(prediction):.3f}',
                    f'Confidence level: {[k for k, v in confidence_levels.items() if v][0] if any(confidence_levels.values()) else "very_low"}',
                    stage_reasoning
                ],
                'uncertainty_factors': [],
                'recommendations': [],
                'prediction_metadata': {
                    'model_type': 'TensorFlow/Keras',
                    'inference_time': float(prediction_time),
                    'raw_prediction': float(prediction),
                    'quality_assessment': quality_factors
                }
            }
            
            # Add uncertainty factors and recommendations based on confidence
            if confidence < 0.6:
                result['uncertainty_factors'].append('Low model confidence')
                result['recommendations'].append('Consider additional imaging or clinical assessment')
            
            if features.get('feature_quality', 1.0) < 0.5:
                result['uncertainty_factors'].append('Poor image quality detected')
                result['recommendations'].append('Image quality may affect prediction accuracy')
            
            debug_log("Real model classification completed", {
                "final_result": binary_classification,
                "stage": stage,
                "confidence": confidence,
                "total_processing_time_ms": round(prediction_time * 1000, 2)
            })
            
            print(f"[PRINT] EXITING AIMLAgent._classify_with_real_model method (success path)")
            return result
            
        except Exception as e:
            prediction_time = (datetime.now() - start_time).total_seconds()
            error_context = {
                "prediction_time": prediction_time,
                "model_type": "TensorFlow",
                "features_available": list(features.keys())
            }
            error_log_with_context("Real model classification failed, falling back to Groq", e, error_context)
            
            # Fallback to Groq service
            print(f"[PRINT] EXITING AIMLAgent._classify_with_real_model method (exception fallback to groq)")
            return await self._classify_with_groq(features)
    
    async def _classify_with_groq(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Classify using Groq AI service (fallback method)"""
        print(f"[PRINT] ENTERED AIMLAgent._classify_with_groq method")
        # Prepare metadata about the image
        image_metadata = {
            'feature_quality': features.get('feature_quality', 0.5),
            'anatomical_regions': list(features.get('anatomical_features', {}).keys()) if 'anatomical_features' in features else [],
            'processing_quality': 'high' if features.get('feature_quality', 0.5) > 0.8 else 'medium'
        }
        
        # Use Groq service for analysis
        classification_result = await self.groq_service.analyze_mri_features(features, image_metadata)
        
        # Validate and process results
        validated_result = self._validate_classification_result(classification_result)
        
        print(f"[PRINT] EXITING AIMLAgent._classify_with_groq method")
        return validated_result
    
    def _validate_classification_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and sanitize classification results"""
        valid_binary = ['parkinsons', 'no_parkinsons', 'uncertain']
        valid_stages = ['1', '2', '3', '4', 'uncertain']
        
        # Ensure binary result is valid
        binary_result = result.get('binary_classification', 'uncertain')
        if binary_result not in valid_binary:
            binary_result = 'uncertain'
        
        # Ensure stage result is valid
        stage_result = result.get('stage_classification', 'uncertain')
        if stage_result not in valid_stages:
            stage_result = 'uncertain'
        
        # Validate confidence scores
        confidence_scores = result.get('confidence_scores', {})
        binary_confidence = max(0.0, min(1.0, confidence_scores.get('binary_confidence', 0.1)))
        stage_confidence = max(0.0, min(1.0, confidence_scores.get('stage_confidence', 0.1)))
        
        return {
            'binary_classification': binary_result,
            'stage_classification': stage_result,
            'confidence_scores': {
                'binary_confidence': binary_confidence,
                'stage_confidence': stage_confidence
            },
            'key_indicators': result.get('key_indicators', []),
            'uncertainty_factors': result.get('uncertainty_factors', []),
            'recommendations': result.get('recommendations', [])
        }
    
    async def _calculate_confidence_metrics(self, classification_result: Dict[str, Any], 
                                          features: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate comprehensive confidence and uncertainty metrics"""
        confidence_scores = classification_result.get('confidence_scores', {})
        binary_conf = confidence_scores.get('binary_confidence', 0.1)
        stage_conf = confidence_scores.get('stage_confidence', 0.1)
        
        # Calculate overall confidence
        feature_quality = features.get('feature_quality', 0.5)
        overall_confidence = (binary_conf + stage_conf + feature_quality) / 3.0
        
        # Calculate uncertainty metrics
        uncertainty_factors = classification_result.get('uncertainty_factors', [])
        uncertainty_score = 1.0 - overall_confidence
        
        return {
            'overall_confidence': overall_confidence,
            'binary_confidence': binary_conf,
            'stage_confidence': stage_conf,
            'uncertainty_metrics': {
                'uncertainty_score': uncertainty_score,
                'feature_quality_impact': 1.0 - feature_quality,
                'model_uncertainty': uncertainty_score * 0.5,
                'data_uncertainty': uncertainty_score * 0.3,
                'uncertainty_factors': uncertainty_factors
            }
        }
    
    def _convert_numpy_types(self, obj):
        """Convert numpy types to Python native types for JSON serialization"""
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, dict):
            return {key: self._convert_numpy_types(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_numpy_types(item) for item in obj]
        else:
            return obj

    async def _generate_prediction_explanation(self, classification_result: Dict[str, Any], 
                                             features: Dict[str, Any]) -> str:
        """Generate human-readable explanation of prediction using Groq"""
        try:
            # Convert numpy types to prevent JSON serialization errors
            safe_classification = self._convert_numpy_types(classification_result)
            safe_features = self._convert_numpy_types(features)
            
            explanation = await self.groq_service.explain_prediction({
                'classification': safe_classification,
                'features': safe_features,
                'model_version': self.model_version
            })
            return explanation
            
        except Exception as e:
            logger.warning(f"Failed to generate prediction explanation: {e}")
            return f"Prediction completed: {classification_result.get('binary_classification', 'uncertain')}"
    
    async def _fail_prediction(self, flag_id: str, session_id: str, error_message: str):
        """Handle prediction failure"""
        try:
            # Mark the action flag as failed
            await self.shared_memory.fail_action_flag(flag_id)
            
            # Store a failed prediction result
            failed_prediction = PredictionResult(
                prediction_id=str(uuid.uuid4()),
                session_id=session_id,
                mri_scan_id=None,
                prediction_type=PredictionType.BINARY,
                binary_result='error',
                stage_result='error',
                confidence_score=0.0,
                model_version=self.model_version,
                metadata={'error': error_message, 'status': 'failed'}
            )
            
            await self.shared_memory.store_prediction(failed_prediction)
            
            logger.error(f"Prediction failed for session {session_id}: {error_message}")
            
        except Exception as e:
            logger.error(f"Error handling prediction failure: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for AI/ML agent"""
        base_health = await super().health_check()
        
        return {
            **base_health,
            "mri_processor_status": "initialized" if self.mri_processor else "not_initialized",
            "tensorflow_model_status": "loaded" if self.model else "not_loaded",
            "groq_service_status": "connected" if self.groq_service.session else "not_connected",
            "processing_stats": {
                "predictions_processed": self.predictions_processed,
                "total_processing_time": self.total_processing_time,
                "average_processing_time": (
                    self.total_processing_time / self.predictions_processed 
                    if self.predictions_processed > 0 else 0
                )
            },
            "model_info": {
                "version": self.model_version,
                "confidence_threshold": self.confidence_threshold
            }
        }