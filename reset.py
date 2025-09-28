#!/usr/bin/env python3
"""
Reset Script for Parkinson's Multiagent System

This script completely resets the system to a fresh state by:
1. Deleting ALL database files completely
2. Deleting all embeddings files and directories
3. Cleaning up all data directories
4. Removing all log files and directories
5. Clearing all Python cache files and directories (excluding virtual environment)
6. Removing all temporary and backup files (excluding virtual environment)

After running this script, executing main.py will be like a fresh start.
"""

import asyncio
import logging
import shutil
import os
from pathlib import Path
from typing import List, Set

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SystemReset:
    """
    Comprehensive system reset utility
    """

    def __init__(self, base_dir: str = None):
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent
        self.data_dir = self.base_dir / "data"
        self.logs_dir = self.base_dir / "logs"
        self.models_dir = self.base_dir / "models"

    async def reset_database(self) -> bool:
        """
        Delete ALL database files completely

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("Starting database reset...")

            # Specific database files
            db_files = [
                self.data_dir / "parkinsons_system.db",
                self.data_dir / "test_parkinsons.db"
            ]

            # Also find any other .db, .sqlite, .sqlite3 files in data directory
            for ext in ['*.db', '*.sqlite', '*.sqlite3']:
                for db_file in self.data_dir.glob(ext):
                    if db_file not in db_files:  # Avoid duplicates
                        db_files.append(db_file)

            deleted_count = 0
            for db_path in db_files:
                if db_path.exists():
                    try:
                        db_path.unlink()
                        logger.info(f"Deleted database file: {db_path}")
                        deleted_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to delete database file {db_path}: {e}")
                        return False

            logger.info(f"Database files deleted successfully: {deleted_count} files removed")
            return True

        except Exception as e:
            logger.error(f"Database reset failed: {e}")
            return False

    def reset_embeddings(self) -> bool:
        """
        Delete all embeddings files and directory

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("Starting embeddings reset...")

            embeddings_dir = self.data_dir / "embeddings"

            if embeddings_dir.exists():
                # Delete the entire embeddings directory
                shutil.rmtree(embeddings_dir)
                logger.info(f"Deleted embeddings directory: {embeddings_dir}")

                # Recreate empty directory
                embeddings_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Recreated empty embeddings directory: {embeddings_dir}")
            else:
                logger.info("Embeddings directory does not exist, skipping...")

            return True

        except Exception as e:
            logger.error(f"Embeddings reset failed: {e}")
            return False

    def reset_data_directories(self) -> bool:
        """
        Clean up all data directories (delete everything inside)

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("Starting data directories reset...")

            # Directories to clean (delete everything inside, keep directory structure)
            dirs_to_clean = [
                self.data_dir / "mri_scans",
                self.data_dir / "reports",
                self.data_dir / "documents"
            ]

            for dir_path in dirs_to_clean:
                if dir_path.exists():
                    # Delete everything inside the directory
                    for item in dir_path.iterdir():
                        try:
                            if item.is_file():
                                item.unlink()
                                logger.info(f"Deleted file: {item}")
                            elif item.is_dir():
                                shutil.rmtree(item)
                                logger.info(f"Deleted directory: {item}")
                        except Exception as e:
                            logger.warning(f"Failed to delete {item}: {e}")
                else:
                    # Create directory if it doesn't exist
                    dir_path.mkdir(parents=True, exist_ok=True)
                    logger.info(f"Created directory: {dir_path}")

            return True

        except Exception as e:
            logger.error(f"Data directories reset failed: {e}")
            return False

    def reset_logs(self) -> bool:
        """
        Delete all log files and recreate logs directory

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("Starting logs reset...")

            if self.logs_dir.exists():
                # Delete the entire logs directory
                shutil.rmtree(self.logs_dir)
                logger.info(f"Deleted logs directory: {self.logs_dir}")

            # Recreate empty logs directory
            self.logs_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Recreated empty logs directory: {self.logs_dir}")

            return True

        except Exception as e:
            logger.error(f"Logs reset failed: {e}")
            return False

    def reset_models_cache(self) -> bool:
        """
        Clean up model cache files

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("Starting models cache reset...")

            if self.models_dir.exists():
                # Delete cache files but keep model files
                cache_files = list(self.models_dir.glob("__pycache__/*"))
                for cache_file in cache_files:
                    try:
                        cache_file.unlink()
                        logger.info(f"Deleted cache file: {cache_file.name}")
                    except Exception as e:
                        logger.warning(f"Failed to delete {cache_file}: {e}")

                # Also clean up any .pyc files
                pyc_files = list(self.models_dir.glob("**/*.pyc"))
                for pyc_file in pyc_files:
                    try:
                        pyc_file.unlink()
                        logger.info(f"Deleted compiled file: {pyc_file.name}")
                    except Exception as e:
                        logger.warning(f"Failed to delete {pyc_file}: {e}")

            return True

        except Exception as e:
            logger.error(f"Models cache reset failed: {e}")
            return False

    def reset_pycache(self) -> bool:
        """
        Clean up all Python cache directories and files in the project (excluding virtual environment)

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("Starting Python cache reset...")
            logger.info("Note: Virtual environment cache files are excluded to avoid permission issues")

            pycache_dirs_deleted = 0
            pyc_files_deleted = 0
            pyo_files_deleted = 0

            # Find all __pycache__ directories in the project (excluding .venv)
            for pycache_dir in self.base_dir.rglob("__pycache__"):
                # Skip virtual environment cache directories
                if ".venv" in str(pycache_dir) or "venv" in str(pycache_dir):
                    logger.info(f"Skipping virtual environment cache: {pycache_dir}")
                    continue

                try:
                    shutil.rmtree(pycache_dir)
                    logger.info(f"Deleted cache directory: {pycache_dir}")
                    pycache_dirs_deleted += 1
                except Exception as e:
                    logger.warning(f"Failed to delete cache directory {pycache_dir}: {e}")

            # Find all .pyc files (excluding virtual environment)
            for pyc_file in self.base_dir.rglob("*.pyc"):
                # Skip virtual environment files
                if ".venv" in str(pyc_file) or "venv" in str(pyc_file):
                    continue

                try:
                    pyc_file.unlink()
                    logger.info(f"Deleted compiled file: {pyc_file}")
                    pyc_files_deleted += 1
                except Exception as e:
                    logger.warning(f"Failed to delete compiled file {pyc_file}: {e}")

            # Find all .pyo files (optimized bytecode) (excluding virtual environment)
            for pyo_file in self.base_dir.rglob("*.pyo"):
                # Skip virtual environment files
                if ".venv" in str(pyo_file) or "venv" in str(pyo_file):
                    continue

                try:
                    pyo_file.unlink()
                    logger.info(f"Deleted optimized file: {pyo_file}")
                    pyo_files_deleted += 1
                except Exception as e:
                    logger.warning(f"Failed to delete optimized file {pyo_file}: {e}")

            logger.info(f"Python cache cleanup: {pycache_dirs_deleted} directories, {pyc_files_deleted} .pyc files, {pyo_files_deleted} .pyo files removed")
            return True

        except Exception as e:
            logger.error(f"Python cache reset failed: {e}")
            return False

    def reset_temp_files(self) -> bool:
        """
        Clean up temporary files throughout the project (excluding virtual environment)

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("Starting temporary files reset...")
            logger.info("Note: Virtual environment files are excluded to avoid permission issues")

            temp_extensions = ['*.tmp', '*.temp', '*.bak', '*.backup', '*.swp', '*.swo', '*~']
            temp_files_deleted = 0

            for ext in temp_extensions:
                for temp_file in self.base_dir.rglob(ext):
                    # Skip virtual environment files
                    if ".venv" in str(temp_file) or "venv" in str(temp_file):
                        continue

                    try:
                        temp_file.unlink()
                        logger.info(f"Deleted temporary file: {temp_file}")
                        temp_files_deleted += 1
                    except Exception as e:
                        logger.warning(f"Failed to delete temporary file {temp_file}: {e}")

            # Also clean up any .cache directories (excluding virtual environment)
            cache_dirs_deleted = 0
            for cache_dir in self.base_dir.rglob(".cache"):
                # Skip virtual environment cache directories
                if ".venv" in str(cache_dir) or "venv" in str(cache_dir):
                    continue

                try:
                    shutil.rmtree(cache_dir)
                    logger.info(f"Deleted cache directory: {cache_dir}")
                    cache_dirs_deleted += 1
                except Exception as e:
                    logger.warning(f"Failed to delete cache directory {cache_dir}: {e}")

            logger.info(f"Temporary files cleanup: {temp_files_deleted} files, {cache_dirs_deleted} cache directories removed")
            return True

        except Exception as e:
            logger.error(f"Temporary files reset failed: {e}")
            return False

    async def full_reset(self) -> bool:
        """
        Perform complete system reset

        Returns:
            True if all reset operations successful, False otherwise
        """
        logger.info("=" * 60)
        logger.info("STARTING COMPLETE SYSTEM RESET")
        logger.info("=" * 60)

        operations = [
            ("Database Files", self.reset_database),
            ("Embeddings", lambda: asyncio.create_task(self._async_wrapper(self.reset_embeddings))),
            ("Data Directories", lambda: asyncio.create_task(self._async_wrapper(self.reset_data_directories))),
            ("Logs", lambda: asyncio.create_task(self._async_wrapper(self.reset_logs))),
            ("Models Cache", lambda: asyncio.create_task(self._async_wrapper(self.reset_models_cache))),
            ("Python Cache", lambda: asyncio.create_task(self._async_wrapper(self.reset_pycache))),
            ("Temporary Files", lambda: asyncio.create_task(self._async_wrapper(self.reset_temp_files)))
        ]

        success_count = 0
        total_operations = len(operations)

        for name, operation in operations:
            logger.info(f"Resetting {name}...")
            try:
                if asyncio.iscoroutinefunction(operation):
                    result = await operation()
                else:
                    # Handle sync functions wrapped in async
                    result = await operation()

                if result:
                    logger.info(f"✓ {name} reset successful")
                    success_count += 1
                else:
                    logger.error(f"✗ {name} reset failed")
            except Exception as e:
                logger.error(f"✗ {name} reset failed with exception: {e}")

        logger.info("=" * 60)
        logger.info(f"RESET COMPLETE: {success_count}/{total_operations} operations successful")
        logger.info("=" * 60)

        if success_count == total_operations:
            logger.info("🎉 System has been completely reset!")
            logger.info("You can now run main.py for a fresh start.")
            return True
        else:
            logger.warning("⚠️  Some reset operations failed. System may not be fully reset.")
            return False

    async def _async_wrapper(self, sync_func):
        """Wrapper to run sync functions in async context"""
        return sync_func()


async def main():
    """Main reset function"""
    print("Parkinson's Multiagent System - Complete Reset")
    print("=" * 50)

    # Confirm reset
    confirm = input("⚠️  WARNING: This will delete ALL data files, databases, embeddings, logs, cache, and temporary files!\n"
                   "This includes ALL .db files, ALL embeddings, ALL logs, ALL __pycache__ directories, and ALL temp files!\n"
                   "This action CANNOT be undone!\n"
                   "Are you sure you want to completely reset the entire system? (type 'YES' to confirm): ")

    if confirm != 'YES':
        print("Reset cancelled.")
        return

    print("\nStarting complete system reset...")

    # Perform reset
    reset_tool = SystemReset()
    success = await reset_tool.full_reset()

    if success:
        print("\n✅ Complete system reset completed successfully!")
        print("All databases, embeddings, logs, cache files, and temporary files have been deleted.")
        print("You can now run 'python main.py' to start fresh.")
    else:
        print("\n❌ Complete system reset completed with errors.")
        print("Check the logs above for details.")


if __name__ == "__main__":
    # Run the reset
    asyncio.run(main())