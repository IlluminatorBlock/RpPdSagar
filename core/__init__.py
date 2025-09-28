# Core package initialization

from .database import DatabaseManager
from .shared_memory import SharedMemoryInterface

__all__ = [
    'DatabaseManager',
    'SharedMemoryInterface'
]