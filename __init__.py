# Parkinson's Multiagent System
# Main package initialization

__version__ = "1.0.0"
__author__ = "Parkinson's Research Team"
__description__ = "Multiagent system for Parkinson's disease analysis with explicit triggering"

# Import main components for easy access
from .main import ParkinsonsMultiagentSystem
from .config import config

__all__ = [
    'ParkinsonsMultiagentSystem',
    'config'
]