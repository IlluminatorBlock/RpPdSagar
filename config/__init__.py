"""
Configuration package for Parkinson's Multiagent System
Re-exports all configuration from config.config module
"""

from .config import (
    Config,
    config,
    PARKINSON_MODEL_PATH,
    GROQ_API_KEY,
    enable_mock_predictions
)

__all__ = [
    'Config',
    'config',
    'PARKINSON_MODEL_PATH',
    'GROQ_API_KEY',
    'enable_mock_predictions'
]
