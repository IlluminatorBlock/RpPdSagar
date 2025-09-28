"""
Configuration management for Parkinson's Multiagent System
"""

import os
from typing import Dict, Any
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # If python-dotenv is not installed, try to load manually
    env_file = Path(__file__).parent / '.env'
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#') and line:
                    key, value = line.split('=', 1)
                    # Strip whitespace and quotes from key and value
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and value:
                        os.environ[key] = value


class Config:
    """Central configuration management"""
    
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.data_dir = self.base_dir / "data"
        self.logs_dir = self.base_dir / "logs"
        
        # Ensure directories exist
        self.data_dir.mkdir(exist_ok=True)
        self.logs_dir.mkdir(exist_ok=True)
    
    @property
    def database_config(self) -> Dict[str, Any]:
        """Database configuration"""
        return {
            'url': os.getenv('DATABASE_URL', f'sqlite:///{self.data_dir}/parkinsons_system.db'),
            'echo': os.getenv('DATABASE_ECHO', 'false').lower() == 'true',
            'pool_size': int(os.getenv('DATABASE_POOL_SIZE', '10')),
            'max_overflow': int(os.getenv('DATABASE_MAX_OVERFLOW', '20'))
        }
    
    @property
    def groq_config(self) -> Dict[str, Any]:
        """Groq API configuration"""
        return {
            'api_key': os.getenv('GROQ_API_KEY', ''),
            'model_chat': os.getenv('GROQ_MODEL_CHAT', 'llama3-8b-8192'),
            'model_analysis': os.getenv('GROQ_MODEL_ANALYSIS', 'llama3-70b-8192'),
            'model_report': os.getenv('GROQ_MODEL_REPORT', 'llama3-70b-8192'),
            'max_tokens': int(os.getenv('GROQ_MAX_TOKENS', '4096')),
            'temperature': float(os.getenv('GROQ_TEMPERATURE', '0.1')),
            'timeout': int(os.getenv('GROQ_TIMEOUT', '30'))
        }
    
    @property
    def mri_processor_config(self) -> Dict[str, Any]:
        """MRI Processor configuration"""
        return {
            'target_dimensions': (256, 256, 128),
            'normalization_method': 'z_score',
            'preprocessing_pipeline': [
                'skull_stripping',
                'normalization', 
                'registration',
                'noise_reduction'
            ],
            'min_quality_score': 0.6,
            'supported_formats': ['dicom', 'png', 'jpeg', 'jpg', 'nii', 'nifti']
        }
    
    @property
    def embeddings_config(self) -> Dict[str, Any]:
        """Embeddings manager configuration"""
        return {
            'embedding_model': 'all-MiniLM-L6-v2',
            'embedding_dimension': 384,
            'max_sequence_length': 512,
            'embeddings_dir': str(self.data_dir / 'embeddings'),
            'cache_size': 1000,
            'enable_caching': True,
            'similarity_threshold': 0.7,
            'max_search_results': 10
        }
    
    @property
    def agent_config(self) -> Dict[str, Any]:
        """Agent configuration"""
        return {
            'supervisor': {
                'response_timeout': 30,
                'max_retries': 3,
                'intent_confidence_threshold': 0.8
            },
            'aiml': {
                'processing_timeout': 120,
                'max_retries': 2,
                'feature_validation_threshold': 0.6,
                'model_path': str(self.base_dir / 'models' / 'parkinsons_model.keras'),
                'model_version': 'v1.0',
                'confidence_threshold': 0.7,
                'enable_mock_predictions': False  # Force real model usage
            },
            'rag': {
                'generation_timeout': 60,
                'max_retries': 2,
                'knowledge_search_limit': 5,
                'min_relevance_score': 0.7
            }
        }
    
    @property
    def shared_memory_config(self) -> Dict[str, Any]:
        """Shared memory configuration"""
        return {
            'cache_size': 1000,
            'cache_ttl': 3600,  # 1 hour
            'event_queue_size': 100,
            'cleanup_interval': 300,  # 5 minutes
            'max_session_age': 86400  # 24 hours
        }
    
    @property
    def logging_config(self) -> Dict[str, Any]:
        """Logging configuration"""
        return {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'standard': {
                    'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
                },
                'detailed': {
                    'format': '%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s'
                }
            },
            'handlers': {
                'console': {
                    'level': 'INFO',
                    'class': 'logging.StreamHandler',
                    'formatter': 'standard'
                },
                'file': {
                    'level': 'DEBUG',
                    'class': 'logging.FileHandler',
                    'filename': str(self.logs_dir / 'system.log'),
                    'formatter': 'detailed'
                }
            },
            'loggers': {
                'parkinsons_system': {
                    'handlers': ['console', 'file'],
                    'level': 'DEBUG',
                    'propagate': False
                }
            },
            'root': {
                'level': 'INFO',
                'handlers': ['console']
            }
        }


# Global configuration instance
config = Config()

# Model paths and constants
PARKINSON_MODEL_PATH = str(config.base_dir / 'models' / 'parkinsons_model.keras')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

# Configuration shortcuts for backward compatibility
enable_mock_predictions = config.agent_config['aiml']['enable_mock_predictions']